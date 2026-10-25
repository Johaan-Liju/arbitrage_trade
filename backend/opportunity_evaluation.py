"""Chronological, purged evaluation of frozen deterministic policies; no fitted parameters."""
from collections import Counter
from datetime import date
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
import random
from statistics import mean

from .opportunity import PROTOCOL, PROTOCOL_HASH, build_records
from . import opportunity
from .reference import canonical_hash


def complete(row):
    return row.get("outcome") is not None and row["outcome"]["status"] == "COMPLETE"


def selected(row, policy):
    return row.get(policy + "_alert", False) if policy != "abstain" else False


def independent_blocks(rows):
    """Conservative blocks: same expiry together, then merge overlapping time envelopes."""
    by_expiry = {}
    for row in rows:
        by_expiry.setdefault(row["expiry"], []).append(row)
    envelopes = sorted(((min(r["decision_at"] for r in group),
                        max(r["outcome"]["label_available_at"] for r in group), group)
                       for group in by_expiry.values()), key=lambda item: item[:2])
    blocks, end = [], ""
    for start, stop, group in envelopes:
        if blocks and start <= end:
            blocks[-1].extend(group)
            end = max(end, stop)
        else:
            blocks.append(list(group)); end = stop
    return blocks


def uncertainty(rows, policy):
    usable = [r for r in rows if selected(r, policy) and complete(r)]
    blocks = independent_blocks(usable)
    result = {"method": "Expiry clusters merged across overlapping outcome/publication windows; percentile bootstrap",
              "level": 0.95, "complete_alerts": len(usable), "independent_blocks": len(blocks),
              "precision_interval": None, "base_mean_net_bps_interval": None}
    positives = sum(r["outcome"]["label"] == "ROBUST_POSITIVE" for r in usable)
    if len(usable) < 100 or len(blocks) < 10 or min(positives, len(usable) - positives) < 30:
        return {**result, "status": "INSUFFICIENT_EVIDENCE",
                "reason": "Require >=100 complete alerts, >=10 nonoverlapping expiry blocks and >=30 outcomes in each class; no row-i.i.d. confidence interval is substituted"}
    rng = random.Random(1729)
    precision, returns = [], []
    for _ in range(1000):
        sample = [r for _ in blocks for r in rng.choice(blocks)]
        precision.append(mean(r["outcome"]["label"] == "ROBUST_POSITIVE" for r in sample))
        returns.append(mean(float(r["outcome"]["scenarios"]["BASE"]["net_return"]) * 10000 for r in sample))
    interval = lambda values: [sorted(values)[24], sorted(values)[974]]
    return {**result, "status": "DESCRIPTIVE_ONLY", "bootstrap_repetitions": 1000, "seed": 1729,
            "precision_interval": interval(precision), "base_mean_net_bps_interval": interval(returns),
            "reason": "Conditional on observed complete outcomes and assumed costs; clustering does not prove independence or execution"}


def metrics(rows, policy):
    eligible = [r for r in rows if r["eligibility"] == "ELIGIBLE"]
    alerts = [r for r in eligible if selected(r, policy)]
    closed = [r for r in alerts if complete(r)]
    censored = [r for r in alerts if not complete(r)]
    successes = sum(r["outcome"]["label"] == "ROBUST_POSITIVE" for r in closed)
    return {"evaluated_pair_decisions": len(rows), "eligible_pair_decisions": len(eligible),
            "distinct_decision_dates": len({r["trading_date"] for r in rows}), "alerts": len(alerts),
            "alert_frequency_per_eligible_decision": len(alerts) / len(eligible) if eligible else None,
            "alert_frequency_per_evaluated_decision": len(alerts) / len(rows) if rows else None,
            "complete_alert_outcomes": len(closed), "censored_alert_outcomes": len(censored),
            "censor_reasons": dict(Counter(r["outcome"]["reason"] for r in censored)),
            "outcome_labels": dict(Counter(r["outcome"]["label"] for r in closed)),
            "precision_robust_positive": successes / len(closed) if closed else None,
            "precision_denominator": "Complete alerted outcomes only; not fill probability",
            "precision_censoring_bounds": [successes / len(alerts), (successes + len(censored)) / len(alerts)] if alerts else None,
            "cost_scenarios": {name: {"precision_above_10bps": mean(Decimal(r["outcome"]["scenarios"][name]["net_return"]) > Decimal("0.001") for r in closed) if closed else None,
                                       "mean_net_return_bps": mean(float(r["outcome"]["scenarios"][name]["net_return"]) * 10000 for r in closed) if closed else None,
                                       "mean_net_inr": mean(float(r["outcome"]["scenarios"][name]["net_inr"]) for r in closed) if closed else None}
                               for name in PROTOCOL["costs_bps_per_leg_side"]},
            "uncertainty": uncertainty(rows, policy),
            "outcome_interpretation": "Hypothetical per-alert daily-price proxy outcomes; overlapping packages are not a portfolio or actual trades"}


def comparison(rows):
    comparable = [r for r in rows if r["baseline_alert"] and complete(r)]
    return {"complete_baseline_candidates": len(comparable),
            "model_abstentions_on_complete_baseline_candidates": sum(not r["model_alert"] for r in comparable),
            "mean_model_minus_baseline_net_bps": {
                name: mean((0 if r["model_alert"] else -float(r["outcome"]["scenarios"][name]["net_return"]) * 10000)
                           for r in comparable) if comparable else None
                for name in PROTOCOL["costs_bps_per_leg_side"]},
            "interpretation": "Paired comparison on complete baseline candidates: model abstention assigned zero exposure. Censored candidates excluded explicitly; no aggregate portfolio P&L or statistical superiority claim",
            "improvement_claim": "UNSUPPORTED"}


def walk_forward(records, request):
    dates = sorted({r["trading_date"] for r in records})
    folds, held_out = [], []
    start = request.initial_history_sessions
    while start < len(dates):
        test_dates = dates[start:start + request.test_sessions]
        test = [r for r in records if r["trading_date"] in test_dates]
        # Fold is frozen before ANY prediction in it; delayed labels must also clear the embargo.
        boundary = min([r["decision_at"] for r in test if r["decision_at"]] + [test_dates[0] + "T00:00:00Z"])
        embargo_date = dates[start - request.embargo_sessions] if start >= request.embargo_sessions else dates[0]
        embargo_cutoff = embargo_date + "T00:00:00Z"
        earlier = [r for r in records if r["trading_date"] < test_dates[0] and r["baseline_alert"]]
        train, removed = [], []
        for row in earlier:
            if not complete(row):
                reason = "CENSORED_OR_IMMATURE"
            elif row["decision_at"] >= boundary or row["outcome"]["label_available_at"] >= boundary or row["planned_exit"] >= test_dates[0]:
                reason = "PURGED_OVERLAPPING_OR_UNAVAILABLE_LABEL"
            elif row["planned_exit"] >= embargo_date or row["outcome"]["label_available_at"] >= embargo_cutoff:
                reason = "EMBARGO"
            else:
                train.append(row); continue
            removed.append({"id": row["id"], "reason": reason})
        fold = {"index": len(folds), "test_start": test_dates[0], "test_end": test_dates[-1],
                "frozen_at": boundary, "training_label_cutoff_exclusive": min(boundary, embargo_cutoff),
                "training_ids": [r["id"] for r in train], "purged_or_embargoed": removed,
                "test_ids": [r["id"] for r in test], "parameter_fitting": "NONE: both policies frozen before replay",
                "training_role": "Audited expanding history available to a future approved learner; deterministic policies do not fit outcomes",
                "metrics": {p: metrics(test, p) for p in ("baseline", "model", "abstain")},
                "comparison": comparison(test)}
        folds.append(fold); held_out.extend(test)
        # Six excluded common dates plus actual planned horizons prevent cross-fold test overlap.
        last_exit = max([r.get("planned_exit", r["trading_date"]) for r in test] + [test_dates[-1]])
        start += len(test_dates) + request.embargo_sessions
        while start < len(dates) and dates[start] <= last_exit:
            start += 1
    return folds, held_out


def evaluate(path, request):
    records, source_hash = build_records(path, request)
    records.sort(key=lambda r: (r["trading_date"], r["pair_id"]))
    folds, held_out = walk_forward(records, request)
    dates = sorted({r["trading_date"] for r in records})
    completed = [r for r in held_out if r["baseline_alert"] and complete(r)]
    expiry_cycles = len({r["expiry"] for r in completed})
    span = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days if dates else 0
    reasons = ["Costs/slippage are unverified sensitivity budgets; execution evidence is absent",
               "Immutable daily observations do not provide authentic source-revision vintages",
               "No prospective untouched market validation or calibrated probabilities; no fitted ML model"]
    if request.dataset == "synthetic":
        reasons.insert(0, "Synthetic generator, deliberate GOLDTEN anomalies and prior inspection: pipeline experiment only, not market evaluation")
    if span < 730:
        reasons.append(f"Only {span} calendar days of selected history; proposed collection gate is at least 24 months")
    if expiry_cycles < 12:
        reasons.append(f"Only {expiry_cycles} expiry cycles with complete held-out candidates; proposed collection gate is 12")
    if len(completed) < 100:
        reasons.append(f"Only {len(completed)} complete held-out baseline candidates; at least 100 proposed for reporting")
    if not folds:
        reasons.append("No held-out fold after the requested initial history")
    implementation_hash = sha256(Path(__file__).read_bytes() + Path(opportunity.__file__).read_bytes()).hexdigest()
    result = {"protocol": PROTOCOL, "protocol_hash": PROTOCOL_HASH, "implementation_hash": implementation_hash,
              "request": request.model_dump(),
              "source_snapshot_hash": source_hash, "dataset": request.dataset, "as_of": request.as_of,
              "status": "EXPERIMENTAL", "evaluation_kind": "SYNTHETIC_PIPELINE_EXPERIMENT" if request.dataset == "synthetic" else "REAL_DATA_EXPERIMENT",
              "evidence": {"credible_market_claim": False, "missing_or_insufficient": reasons,
                           "selected_calendar_span_days": span, "complete_held_out_expiry_cycles": expiry_cycles},
              "records": records, "folds": folds,
              "held_out": {"metrics": {p: metrics(held_out, p) for p in ("baseline", "model", "abstain")},
                           "comparison": comparison(held_out), "record_ids": [r["id"] for r in held_out]},
              "coverage": {"scheduled_pair_decisions": len(records), "unique_dates": len(dates),
                           "eligible_decisions": sum(r["eligibility"] == "ELIGIBLE" for r in records),
                           "ineligible_reasons": dict(Counter(r["reason"] for r in records if r["eligibility"] != "ELIGIBLE")),
                           "not_held_out_decisions": len(records) - len(held_out)},
              "disclaimer": "Research only. Hypothetical daily-price proxies, invented cost scenarios and uncertain liquidity/settlement. No observed fills, trade execution or guaranteed arbitrage."}
    result["report_id"] = canonical_hash(result)
    return result
