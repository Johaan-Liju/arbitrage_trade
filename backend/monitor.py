"""Dataset-scoped monitor built from one validated point-in-time snapshot."""
from datetime import datetime
from decimal import Decimal


def monitor_view(current, selected_id, stale_after_hours):
    contracts = current["contracts"]
    selected = next((s for s in contracts if s["contract_id"] == selected_id), None)
    if selected_id and selected is None:
        raise KeyError("Exact contract/specification not available at this cutoff")
    selected = selected or next((s for s in contracts if s["symbol"] == "GOLDM"), contracts[0] if contracts else None)
    cutoff = datetime.fromisoformat(current["as_of"].replace("Z", "+00:00"))
    rows = []
    for spec in contracts:
        history = current["histories"][spec["contract_id"]]
        latest = history[-1] if history else None
        age = (cutoff - datetime.fromisoformat(latest["observed_at"].replace("Z", "+00:00"))).total_seconds() / 3600 if latest else None
        if latest and current.get("data_mode") == "source_quotes":
            # Collection time is not market time. Use the trading-date start as a conservative age bound.
            age = max(age, (cutoff - datetime.fromisoformat(latest["trading_date"] + "T00:00:00+05:30")).total_seconds() / 3600)
        blocked = [i for i in current["issues"] if i["contract_id"] == spec["contract_id"] and (not latest or i["trading_date"] >= latest["trading_date"])]
        status, reason = "FRESH", "Observation age is within the configured limit at the cutoff"
        if (spec["normalization_status"] != "READY" and current.get("data_mode") != "source_quotes") or blocked:
            status, reason = "BLOCKED", spec["normalization_reason"] or "; ".join(i["reason"] for i in blocked)
        elif latest is None:
            status, reason = "MISSING", "No usable observation both observed and available by this cutoff"
        elif spec["expiry"] < current["as_of"][:10]:
            status, reason = "STALE", "Contract expired before the cutoff"
        elif age > stale_after_hours:
            status, reason = "STALE", "Observation age exceeds the configured limit"
        previous = history[-2] if len(history) > 1 else None
        change = Decimal(latest["quoted_price_decimal"]) - Decimal(previous["quoted_price_decimal"]) if previous else None
        rows.append({"contract": spec, "latest": latest,
                     "change": str(change) if change is not None else None,
                     "change_pct": float(change / Decimal(previous["quoted_price_decimal"]) * 100) if change is not None else None,
                     "previous_trading_date": previous["trading_date"] if previous else None,
                     "freshness": {"status": status, "reason": reason, "age_hours": age},
                     "spread": None, "spread_reason": "No selected reference contract"})
    reference = next((r for r in rows if selected and r["contract"]["contract_id"] == selected["contract_id"]), None)
    for row in rows:
        if reference is None:
            continue
        if row is reference:
            row["spread_reason"] = "Selected reference contract"
        elif row["contract"]["expiry"] != selected["expiry"]:
            row["spread_reason"] = "Exact expiry differs; no substitution"
        elif row["contract"]["symbol"] == selected["symbol"]:
            row["spread_reason"] = "Same symbol; specification versions remain separate"
        elif any(r["contract"]["normalization_status"] != "READY" for r in (row, reference)):
            row["spread_reason"] = "Source quotes available; normalized comparison requires verified quotation terms"
        elif any(r["freshness"]["status"] != "FRESH" for r in (row, reference)):
            row["spread_reason"] = "Missing, blocked or stale leg; spread withheld"
        elif row["latest"]["trading_date"] != reference["latest"]["trading_date"]:
            row["spread_reason"] = "Latest trading dates differ; no forward fill"
        else:
            row["spread"] = str(Decimal(row["latest"]["normalized_999_inr_per_gram"]) - Decimal(reference["latest"]["normalized_999_inr_per_gram"]))
            row["spread_reason"] = "Row minus selected contract; same exact expiry and trading date. Delivery/settlement differences and execution costs remain."
    return {"dataset": current["dataset"], "label": current["dataset"].upper(), "as_of": current["as_of"],
            "data_mode": current.get("data_mode", "validated"), "model_ready": current.get("model_ready", True),
            "stale_after_hours": stale_after_hours, "watchlist": rows, "selected": reference,
            "prices": current["histories"][selected["contract_id"]] if selected else [], "issues": current["issues"],
            "spread_unit": "INR per gram (999 purity)", "spread_direction": "row minus selected contract"}
