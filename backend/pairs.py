"""Paired prior-only research. Original quotes retained; no price filling or rolling."""
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .domain import normalize, utc

CAUTIONS = [
    "SYNTHETIC contracts and liquidity; no evidence of executable arbitrage.",
    "999-equivalent INR/g is a comparison convention, not an executable price.",
    "Delivery location, taxes, premia, maturity, funding and settlement differences may remain.",
    "Volume/OI are daily proxies, not order-book depth or guaranteed two-leg execution.",
]


def seconds(later, earlier):
    return (datetime.fromisoformat(later.replace('Z','+00:00'))-datetime.fromisoformat(earlier.replace('Z','+00:00'))).total_seconds()


class PairRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    contract_a: str
    contract_b: str
    dataset: str = "synthetic"
    as_of: str
    lookback: int = Field(default=10, ge=2, le=250, strict=True)
    min_observations: int = Field(default=5, ge=2, le=250, strict=True)
    entry_z: float = Field(default=2.5, gt=0, le=100, strict=True)
    max_age_days: int = Field(default=4, ge=1, le=30)
    min_volume: int = Field(default=100, ge=0)
    min_oi: int = Field(default=100, ge=0)

    @model_validator(mode="after")
    def validate_request(self):
        utc(self.as_of)
        if self.contract_a == self.contract_b:
            raise ValueError("Select two distinct exact contracts")
        if self.min_observations > self.lookback:
            raise ValueError("Minimum observations exceeds lookback")
        return self


def load_pair(db, request):
    specs, histories = [], []
    for contract in (request.contract_a,request.contract_b):
        found = db.execute("SELECT * FROM specs WHERE contract_id=? AND dataset=? AND available_at<=?",(contract,request.dataset,request.as_of)).fetchone()
        if found is None:
            raise ValueError("Exact contract/specification unavailable at cutoff")
        spec = dict(found)
        normalize(1,spec)  # Fail closed on unverified real terms.
        specs.append(spec)
        histories.append([dict(r) for r in db.execute("SELECT * FROM prices WHERE contract_id=? AND dataset=? AND symbol=? AND expiry=? AND spec_version=? AND observed_at<=? AND available_at<=? AND trading_date<=? ORDER BY trading_date",
            (contract,request.dataset,spec["symbol"],spec["expiry"],spec["spec_version"],request.as_of,request.as_of,request.as_of[:10]))])
    return specs, histories


def pair_history(specs, histories, request):
    """Raw left-minus-right spreads; rolling sample statistics exclude the current date.

    Replay decisions occur when BOTH normalized legs and their references are known.
    Latest is evaluated afresh at the requested as-of (including eligible late arrivals).
    """
    a, b = specs
    for spec, rows, identifier in zip(specs, histories, (request.contract_a, request.contract_b)):
        if spec["dataset"] != request.dataset or spec["contract_id"] != identifier:
            raise ValueError("Mixed identity partition")
        for row in rows:
            if any(row[k] != spec[k] for k in ("dataset", "symbol", "expiry", "spec_version", "contract_id")) or ("spec_id" in spec and row.get("spec_id") != spec["spec_id"]):
                raise ValueError("Mixed identity partition")
        if len({r["trading_date"] for r in rows}) != len(rows):
            raise ValueError("Duplicate pair observations")

    def availability(row, spec):
        return max(row["observed_at"], row["available_at"], row.get("normalized_available_at", row["available_at"]),
                   spec["available_at"], *row.get("reference_availability", {}).values())

    maps = [{r["trading_date"]: r for r in rows if availability(r, spec) <= request.as_of and r["trading_date"] <= request.as_of[:10]}
            for spec, rows in zip(specs, histories)]
    days = sorted(set(maps[0]) | set(maps[1]))
    common = sorted(set(maps[0]) & set(maps[1]))
    missing = [{"trading_date": day, "reason": "Missing one leg or usable reference; no forward fill"} for day in days if day not in common]

    def quality(day, decision):
        reasons = []
        for spec, mapping in zip(specs, maps):
            row = mapping[day]
            if spec.get("normalization_status", "READY") != "READY":
                reasons.append(spec.get("normalization_reason") or "Unusable reference")
            if not spec["valid_from"] <= day <= spec["valid_to"] or availability(row, spec) > decision:
                reasons.append(f"Stale/unavailable spec or reference: {spec['symbol']}")
            if seconds(decision, row["observed_at"]) > request.max_age_days * 86400 or seconds(decision, day + 'T00:00:00Z') > request.max_age_days * 86400:
                reasons.append(f"Stale observation: {spec['symbol']}")
            if row["volume"] < request.min_volume or row["open_interest"] < request.min_oi:
                reasons.append(f"Insufficient volume/OI proxy: {spec['symbol']}")
            if spec["safe_exit_date"] and day > spec["safe_exit_date"]:
                reasons.append(f"Past safe exit: {spec['symbol']}")
        return reasons

    def spread(day):
        values = [Decimal(m[day]["normalized_999_inr_per_gram"]) if "normalized_999_inr_per_gram" in m[day]
                  else Decimal(str(normalize(m[day]["price"], s))) for m, s in zip(maps, specs)]
        return values, values[0] - values[1]

    def evaluate(day, decision):
        # Check all timestamps again at THIS decision; never reuse future replay statistics.
        prior_days = [d for d in common if d < day and all(availability(m[d], s) <= decision for m, s in zip(maps, specs))
                      and not quality(d, max(availability(m[d], s) for m, s in zip(maps, specs)))][-request.lookback:]
        prior = [spread(d)[1] for d in prior_days]
        mean = sum(prior) / len(prior) if prior else None
        std = (sum((v - mean) ** 2 for v in prior) / (len(prior) - 1)).sqrt() if len(prior) >= 2 else None
        values, current = spread(day)
        reasons = quality(day, decision)
        enough = len(prior) >= request.min_observations
        z = float((current - mean) / std) if enough and std and not reasons else None
        if reasons:
            status, reason = "Insufficient data", "; ".join(reasons)
        elif not enough:
            status, reason = "Insufficient data", f"Need {request.min_observations} prior eligible spreads; have {len(prior)}"
        elif not std:
            status, reason = "Insufficient data", "Prior spread standard deviation is zero; z-score undefined"
        elif abs(z) >= request.entry_z:
            status, reason = "Investigate", f"Absolute z-score {abs(z):.3f} meets threshold {request.entry_z}; research flag only. Assess costs, liquidity, execution and settlement uncertainty."
        else:
            status, reason = "No signal", f"Absolute z-score {abs(z):.3f} is below threshold {request.entry_z}"
        return {"trading_date": day, "decision_at": decision, "cutoff": decision,
                "normalized_a": float(values[0]), "normalized_b": float(values[1]),
                "raw_pair_spread": float(current), "raw_pair_spread_decimal": str(current),
                "prior_mean": float(mean) if mean is not None else None,
                "prior_std": float(std) if std is not None else None,
                # Legacy replay aliases now refer directly to prior RAW spread statistics.
                "expected_basis": float(mean) if mean is not None else None, "baseline": float(mean) if mean is not None else None,
                "difference": float(current - mean) if mean is not None else None,
                "z_score": z, "upper_z": request.entry_z, "lower_z": -request.entry_z,
                "history_count": len(prior), "sample_count": len(prior), "status": status, "reason": reason,
                "quality_reasons": reasons, "a": maps[0][day], "b": maps[1][day],
                "age_hours": max(seconds(decision, m[day]["observed_at"]) for m in maps) / 3600}

    events = [evaluate(day, max(availability(m[day], s) for m, s in zip(maps, specs))) for day in common]
    latest = evaluate(common[-1], request.as_of) if common else None
    reason = "No aligned observations with usable references at this cutoff"
    blocked = [s.get("normalization_reason") for s in specs if s.get("normalization_status") == "BLOCKED"]
    if blocked:
        reason = "; ".join(r or "Unusable reference" for r in blocked)
    elif missing and (not latest or missing[-1]["trading_date"] > latest["trading_date"]):
        reason = "Latest trading date is missing one leg or usable reference; no forward fill"
        if latest:
            latest.update(status="Insufficient data", reason=reason, raw_pair_spread=None, raw_pair_spread_decimal=None,
                          prior_mean=None, prior_std=None, baseline=None, expected_basis=None, difference=None,
                          z_score=None, history_count=0, sample_count=0)
    calendar = a["expiry"] != b["expiry"]
    return {"dataset": request.dataset, "label": request.dataset.upper(), "as_of": request.as_of,
            "status": latest["status"] if latest else "Insufficient data", "reason": latest["reason"] if latest else reason,
            "spec_a": a, "spec_b": b, "spread_direction": "left minus right", "unit": "999-purity INR/gram",
            "alignment": "CALENDAR_BASIS_DIFFERENCE" if calendar else "EXACT_EXPIRY",
            "expiry_difference_days": (datetime.fromisoformat(a["expiry"]) - datetime.fromisoformat(b["expiry"])).days,
            "cautions": CAUTIONS + ([f"Different exact expiries: {a['expiry']} versus {b['expiry']}; calendar basis is unresolved."] if calendar else []),
            "method": {"lookback": request.lookback, "min_observations": request.min_observations, "entry_z": request.entry_z,
                       "ddof": 1, "basis": "z = (current left-minus-right spread - prior mean) / prior sample standard deviation (ddof=1). Last lookback eligible preceding trading dates; current date excluded. Investigate when |z| >= threshold; research only, never guaranteed arbitrage."},
            "history": events, "latest": latest,
            "quality": {"missing_dates": missing, "calendar": "Synthetic weekdays; no verified MCX holiday calendar", "no_forward_fill": True}}
