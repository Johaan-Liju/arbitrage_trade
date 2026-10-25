"""Versioned deterministic opportunity research. Daily prices are never observed fills."""
from datetime import date, datetime, timedelta
from decimal import Decimal, localcontext
import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .domain import utc
from .normalization import normalize_observation
from .reference import ReferenceFailure, canonical_hash
from .research import contract_id, snapshot

D = Decimal
PROTOCOL = {
    "version": "opportunity-v1", "lookback": 10, "entry_z": "2.5", "holding_sessions": 5,
    "materiality_return": "0.001", "max_age_hours": 24, "max_skew_minutes": 15,
    "min_volume": 100, "min_oi": 100, "max_participation": "0.01", "max_lots": 100,
    "costs_bps_per_leg_side": {"BASE": {"brokerage": 5, "other": 5, "slippage": 10},
                               "STRESS": {"brokerage": 5, "other": 10, "slippage": 25},
                               "SEVERE": {"brokerage": 5, "other": 15, "slippage": 50}},
    "fixed_inr_per_leg_side": 0, "model": "z2.5_with_severe_cost_reversion_filter",
    "baseline": "fixed_z2.5", "execution": "HYPOTHETICAL_DAILY_PRICE_PROXY",
}
PROTOCOL_HASH = canonical_hash(PROTOCOL)


class PairSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    contract_a: str
    contract_b: str
    calendar_a: str
    calendar_b: str


class OpportunityRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: Literal["synthetic", "real"]
    as_of: str
    pairs: list[PairSelection] = Field(min_length=1, max_length=24)
    initial_history_sessions: int = Field(default=20, ge=10, le=2000, strict=True)
    test_sessions: int = Field(default=5, ge=1, le=250, strict=True)
    embargo_sessions: int = Field(default=6, ge=6, le=250, strict=True)

    @model_validator(mode="after")
    def validate_request(self):
        utc(self.as_of)
        keys = [tuple(sorted((p.contract_a, p.contract_b))) for p in self.pairs]
        if len(set(keys)) != len(keys) or any(a == b for a, b in keys):
            raise ValueError("Pairs must have distinct legs and unique unordered identities")
        return self


def timestamp(value):
    return datetime.fromisoformat(utc(value).replace("Z", "+00:00"))


def days_between(start, end):
    current = date.fromisoformat(start)
    while current <= date.fromisoformat(end):
        yield current.isoformat()
        current += timedelta(days=1)


def common_day(calendars, day, cutoff):
    windows = [c.day(day, cutoff).windows for c in calendars]
    return any(max(a.opens_at, b.opens_at) < min(a.closes_at, b.closes_at)
               for a in windows[0] for b in windows[1])


def cash_outcome(specs, lots, sides, entry, exit_prices):
    """Exact raw-quote P&L and itemized adverse costs; no normalized-price cash shortcut."""
    factors = [D(n) * s.lot_size_grams / s.quotation_grams for s, n in zip(specs, lots)]
    notionals_in = [f * p for f, p in zip(factors, entry)]
    notionals_out = [f * p for f, p in zip(factors, exit_prices)]
    gross = sum(D(side) * f * (x - e) for side, f, e, x in zip(sides, factors, entry, exit_prices))
    initial = sum(notionals_in)
    scenarios = {}
    for name, rates in PROTOCOL["costs_bps_per_leg_side"].items():
        items = [{"leg": i, "side": side, "notional_inr": str(value),
                  **{k + "_inr": str(value * D(rate) / 10000) for k, rate in rates.items()},
                  "fixed_inr": "0"}
                 for i in range(2) for side, value in (("ENTRY", notionals_in[i]), ("EXIT", notionals_out[i]))]
        cost = sum(D(item[k + "_inr"]) for item in items for k in rates)
        scenarios[name] = {"cost_inr": str(cost), "net_inr": str(gross - cost),
                           "net_return": str((gross - cost) / initial), "items": items}
    return {"gross_inr": str(gross), "initial_gross_notional_inr": str(initial), "scenarios": scenarios}


class PairResearch:
    def __init__(self, registry, raw, request, selection):
        self.registry, self.request, self.selection = registry, request, selection
        self.specs, self.listings = [], []
        for identifier in (selection.contract_a, selection.contract_b):
            found = [(registry.spec(c.spec_id), c) for c in registry.contracts
                     if contract_id(registry.spec(c.spec_id), c) == identifier]
            if not found:
                raise ReferenceFailure("UNKNOWN_CONTRACT", "Exact contract/specification not found")
            spec, listing = found[0]
            if spec.dataset != request.dataset:
                raise ReferenceFailure("DATASET_MISMATCH", "Pair references belong to another dataset")
            if max(spec.available_at, listing.available_at) > request.as_of:
                raise ReferenceFailure("FUTURE_SPEC", "Exact reference is unavailable at the requested cutoff")
            self.specs.append(spec); self.listings.append(listing)
        if self.listings[0].expiry != self.listings[1].expiry or self.specs[0].instrument == self.specs[1].instrument:
            raise ReferenceFailure("EXACT_EXPIRY_REQUIRED", "Distinct symbols with identical exact expiries required")
        self.calendars = [registry.calendar(c) for c in (selection.calendar_a, selection.calendar_b)]
        if any(c.dataset != request.dataset for c in self.calendars):
            raise ReferenceFailure("DATASET_MISMATCH", "Calendar belongs to another dataset")
        self.maps = []
        for spec, listing, calendar in zip(self.specs, self.listings, self.calendars):
            rows = [r for r in raw if (r["dataset"], r["instrument"], r["expiry"], r["spec_id"]) ==
                    (request.dataset, spec.instrument, listing.expiry, spec.spec_id)
                    and utc(r["observed_at"]) <= request.as_of and utc(r["available_at"]) <= request.as_of]
            if any(r["calendar_id"] != calendar.calendar_id for r in rows):
                raise ReferenceFailure("CALENDAR_PARTITION", "Split experiments at calendar versions; no implicit calendar substitution")
            if len({r["trading_date"] for r in rows}) != len(rows):
                raise ReferenceFailure("DUPLICATE_OBSERVATION", "Duplicate exact observation partition")
            self.maps.append({r["trading_date"]: r for r in rows})
        self.lots = None
        if all(s.lot_size_grams and s.lot_size_grams == int(s.lot_size_grams) for s in self.specs):
            weight = math.lcm(*(int(s.lot_size_grams) for s in self.specs))
            lots = [weight // int(s.lot_size_grams) for s in self.specs]
            if max(lots) <= 100:
                self.lots = lots
        self.pair_id = f"{request.dataset}|{selection.contract_a}|{selection.contract_b}"

    def known_at(self, row, index):
        return max(utc(row["observed_at"]), utc(row["available_at"]), self.specs[index].available_at,
                   self.listings[index].available_at, self.calendars[index].available_at)

    def clean_pair(self, day, cutoff):
        rows = [m.get(day) for m in self.maps]
        if any(r is None for r in rows):
            raise ReferenceFailure("MISSING_LEG", "A scheduled source observation is missing; no forward fill")
        if not self.lots:
            raise ReferenceFailure("LOT_PACKAGE", "No whole-lot equal-weight package within the lot cap")
        cleaned = [normalize_observation(row, self.registry, calendar.calendar_id, cutoff)
                   for row, calendar in zip(rows, self.calendars)]
        for row, lots in zip(cleaned, self.lots):
            if (timestamp(cutoff) - timestamp(row["observed_at"])).total_seconds() > 24 * 3600:
                raise ReferenceFailure("STALE", "Source observation exceeds 24 hours at decision/confirmation")
            for field in ("volume", "open_interest"):
                if row[field] is None or row[field] < 100 or D(lots) > D(row[field]) * D("0.01"):
                    raise ReferenceFailure("LIQUIDITY", "Missing/insufficient source volume or OI for the whole-lot package")
        if abs((timestamp(cleaned[0]["observed_at"]) - timestamp(cleaned[1]["observed_at"])).total_seconds()) > 900:
            raise ReferenceFailure("OBSERVATION_SKEW", "Pair observation skew exceeds 15 minutes")
        return cleaned

    def schedule(self, day, cutoff):
        start = max(c.coverage_start for c in self.calendars)
        end = min(c.coverage_end for c in self.calendars)
        sessions = [d for d in days_between(start, end) if common_day(self.calendars, d, cutoff)]
        if day not in sessions:
            raise ReferenceFailure("CLOSED_SESSION", "Decision does not fall on a common explicit session")
        index = sessions.index(day)
        if index < 10 or len(sessions) <= index + 7:
            raise ReferenceFailure("CALENDAR_COVERAGE", "Require ten prior and seven future common sessions")
        prior, entry, exit_day, buffer = sessions[index - 10:index], sessions[index + 1], sessions[index + 6], sessions[index + 7]
        deadlines = []
        for spec, listing in zip(self.specs, self.listings):
            if not all((spec.verified_through, listing.first_trade_date, listing.safe_exit_date, listing.delivery_start)):
                raise ReferenceFailure("SAFETY_DATES", "Explicit verified validity and delivery/safety dates required")
            deadlines.extend([spec.verified_through, listing.safe_exit_date, listing.last_trade_date, listing.expiry])
            if spec.effective_until:
                deadlines.append(spec.effective_until)
            before_tender = [d for d in sessions if d < listing.delivery_start]
            if not before_tender:
                raise ReferenceFailure("SAFETY_DATES", "No verified common open session before tender")
            deadlines.append(before_tender[-1])
        deadline = min(deadlines)
        if not entry < exit_day < buffer < deadline:
            raise ReferenceFailure("SAFETY_DEADLINE", "Entry, five-session exit and a further session must precede the safety deadline")
        return prior, entry, exit_day, deadline

    def record(self, day, at=None, outcomes=True):
        raw = [m.get(day) for m in self.maps]
        decision = at or (max(self.known_at(r, i) for i, r in enumerate(raw)) if all(raw) else None)
        identity = {"dataset": self.request.dataset, "pair_id": self.pair_id, "trading_date": day,
                    "contract_a": self.selection.contract_a, "contract_b": self.selection.contract_b,
                    "expiry": self.listings[0].expiry, "spec_ids": [s.spec_id for s in self.specs],
                    "spec_versions": [s.version for s in self.specs],
                    "calendar_ids": [c.calendar_id for c in self.calendars]}
        identity.update(protocol_hash=PROTOCOL_HASH, decision_at=decision)
        result = {**identity, "id": canonical_hash(identity), "decision_at": decision, "features": None,
                  "eligibility": "INELIGIBLE", "reason": None, "baseline_alert": False, "model_alert": False,
                  "outcome": None, "outcome_basis": PROTOCOL["execution"], "execution_evidence": "NONE"}
        try:
            if not decision or decision > self.request.as_of:
                raise ReferenceFailure("MISSING_LEG", "Both legs and their references are not known at the evaluation cutoff")
            current = self.clean_pair(day, decision)
            prior, entry, exit_day, deadline = self.schedule(day, decision)
            spreads, provenance = [], []
            for prior_day in prior:
                previous_raw = [m.get(prior_day) for m in self.maps]
                if not all(previous_raw):
                    raise ReferenceFailure("WARMUP_GAP", "Ten consecutive preceding common sessions are required")
                known = max(self.known_at(r, i) for i, r in enumerate(previous_raw))
                if known > decision:
                    raise ReferenceFailure("FUTURE_HISTORY", "A prior observation/reference was unavailable at prediction time")
                previous = self.clean_pair(prior_day, known)
                spreads.append(D(previous[0]["normalized_999_inr_per_gram"]) - D(previous[1]["normalized_999_inr_per_gram"]))
                provenance.append({"trading_date": prior_day, "known_at": known,
                                   "observation_hashes": [canonical_hash(r) for r in previous]})
            mean = sum(spreads) / 10
            variance = sum((s - mean) ** 2 for s in spreads) / 9
            if variance == 0:
                raise ReferenceFailure("ZERO_VARIANCE", "Prior spread variance is zero")
            spread = D(current[0]["normalized_999_inr_per_gram"]) - D(current[1]["normalized_999_inr_per_gram"])
            std = variance.sqrt()
            z = (spread - mean) / std
            sides = [-1, 1] if z > 0 else [1, -1]
            quoted = [D(r["price"]) for r in current]
            # Fixed deterministic hypothesis: spread returns to the prior mean, half through each leg.
            normalized_moves = [(mean - spread) / 2, (spread - mean) / 2]
            projected = [p + move * s.quotation_grams * s.quote_purity_per_mille / 999
                         for p, move, s in zip(quoted, normalized_moves, self.specs)]
            estimate = cash_outcome(self.specs, self.lots, sides, quoted, projected) if min(projected) > 0 else None
            baseline = abs(z) >= D("2.5")
            cost_pass = estimate is not None and D(estimate["scenarios"]["SEVERE"]["net_return"]) > D("0.001")
            result.update(eligibility="ELIGIBLE", reason="Fixed z candidate" if baseline else "Below fixed z threshold",
                          baseline_alert=baseline, model_alert=baseline and cost_pass,
                          sides=sides, lots=self.lots, planned_entry=entry, planned_exit=exit_day, safety_deadline=deadline,
                          features={"as_of": decision, "spread": str(spread), "prior_mean": str(mean),
                                    "prior_std": str(std), "z_score": str(z), "prior_count": 10,
                                    "prior_provenance": provenance,
                                    "current": [{"observed_at": r["observed_at"], "available_at": r["available_at"],
                                                 "reference_availability": r["reference_availability"],
                                                 "source": r["source_url"], "quoted_price": r["price"],
                                                 "volume": r["volume"], "open_interest": r["open_interest"],
                                                 "observation_hash": canonical_hash(r)} for r in current]},
                          forecast={"method": "Frozen prior mean; symmetric normalized-leg reversion; current quotes as entry estimates",
                                    "estimated_package": estimate, "cost_filter_pass": cost_pass,
                                    "probability": None, "claim": "Uncalibrated deterministic hypothesis, not a fill or success probability"})
            if baseline and outcomes:
                result["outcome"] = self.outcome(result)
        except (ReferenceFailure, ValueError, ArithmeticError, KeyError) as error:
            result.update(reason=f"{getattr(error, 'code', 'INVALID_INPUT')}: {error}")
        return result

    def outcome(self, record):
        stage = "ENTRY"
        result = {"status": "CENSORED_ENTRY", "label": None, "label_available_at": None,
                  "as_of": self.request.as_of, "execution_evidence": "NONE", "outcome_basis": PROTOCOL["execution"]}
        try:
            endpoint_rows, confirmations = [], []
            for stage, day in (("ENTRY", record["planned_entry"]), ("EXIT", record["planned_exit"])):
                rows = [m.get(day) for m in self.maps]
                if not all(rows):
                    raise ReferenceFailure("UNAVAILABLE_ENDPOINT", f"Scheduled {stage.lower()} is absent at evaluation cutoff; date not replaced")
                known = max(self.known_at(r, i) for i, r in enumerate(rows))
                if known > self.request.as_of:
                    raise ReferenceFailure("IMMATURE_OUTCOME", "Outcome inputs are not yet available")
                clean = self.clean_pair(day, known)
                if any(r["observed_at"] <= record["decision_at"] for r in clean):
                    raise ReferenceFailure("CHRONOLOGY", "Proxy observations must be strictly later than the prediction")
                if confirmations and any(r["observed_at"] <= confirmations[-1] for r in clean):
                    raise ReferenceFailure("CHRONOLOGY", "Exit observations must follow entry confirmation")
                endpoint_rows.append(clean); confirmations.append(known)
            amounts = cash_outcome(self.specs, self.lots, record["sides"],
                                   [D(r["price"]) for r in endpoint_rows[0]], [D(r["price"]) for r in endpoint_rows[1]])
            returns = {k: D(v["net_return"]) for k, v in amounts["scenarios"].items()}
            if all(v > D("0.001") for v in returns.values()):
                label = "ROBUST_POSITIVE"
            elif returns["BASE"] > D("0.001"):
                label = "COST_SENSITIVE_POSITIVE"
            elif returns["BASE"] < D("-0.001"):
                label = "NEGATIVE"
            else:
                label = "NEAR_ZERO"
            spreads = [D(rows[0]["normalized_999_inr_per_gram"]) - D(rows[1]["normalized_999_inr_per_gram"]) for rows in endpoint_rows]
            return {**result, **amounts, "status": "COMPLETE", "label": label,
                    "label_available_at": max(confirmations), "entry_confirmation": confirmations[0],
                    "entry": endpoint_rows[0], "exit": endpoint_rows[1], "delta_spread": str(spreads[1] - spreads[0]),
                    "convergence": str(D(-record["sides"][0]) * (spreads[0] - spreads[1]))}
        except (ReferenceFailure, ValueError, ArithmeticError, KeyError) as error:
            return {**result, "status": f"CENSORED_{stage}", "reason": f"{getattr(error, 'code', 'INVALID_INPUT')}: {error}"}

    def records(self):
        dates = sorted(set(self.maps[0]) | set(self.maps[1]))
        if not dates:
            return []
        end = min(self.request.as_of[:10], self.listings[0].last_trade_date, self.listings[1].last_trade_date)
        records = []
        for day in days_between(dates[0], end):
            try:
                if not common_day(self.calendars, day, self.request.as_of):
                    continue
            except ReferenceFailure:
                # Unknown calendar coverage cannot silently omit a potentially missing decision.
                pass
            records.append(self.record(day))
        return records


def build_records(path, request):
    registry, raw = snapshot(path, request.dataset, request.as_of)
    known_raw = [r for r in raw if utc(r["observed_at"]) <= request.as_of and utc(r["available_at"]) <= request.as_of]
    registry_data = registry.model_dump(mode="json")
    known_registry = {key: [r for r in registry_data[key] if r["available_at"] <= request.as_of]
                      for key in ("specs", "contracts", "calendars")}
    source_hash = canonical_hash({"references": known_registry, "observations": known_raw})
    with localcontext() as context:
        context.prec = 34
        records = [r for pair in request.pairs for r in PairResearch(registry, known_raw, request, pair).records()]
    return records, source_hash


def predict(path, request):
    registry, raw = snapshot(path, request.dataset, request.as_of)
    predictions = []
    with localcontext() as context:
        context.prec = 34
        for selection in request.pairs:
            research = PairResearch(registry, raw, request, selection)
            dates = sorted(set(research.maps[0]) | set(research.maps[1]))
            if not dates:
                predictions.append({"pair_id": research.pair_id, "eligibility": "INELIGIBLE",
                                    "reason": "No source observations at the cutoff", "baseline_alert": False,
                                    "model_alert": False, "decision_at": request.as_of, "outcome": None})
            else:
                predictions.append(research.record(dates[-1], at=request.as_of, outcomes=False))
    return {"dataset": request.dataset, "as_of": request.as_of, "status": "EXPERIMENTAL",
            "protocol": PROTOCOL, "protocol_hash": PROTOCOL_HASH, "predictions": predictions,
            "execution_evidence": "NONE", "probability": None,
            "limitations": "Uncalibrated deterministic research; current freshness enforced. Estimated costs and reversion are assumptions. No observed fills or trade execution."}
