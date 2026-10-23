"""Point-in-time research calculations. No fills, P&L or execution promises."""
import pandas as pd

WINDOW = 5
THRESHOLD = 0.2


def deviation(history: pd.DataFrame):
    if len(history) < WINDOW + 1:
        return {"state": "Warming up", "deviation_pct": None, "baseline": None, "history_count": max(0, len(history) - 1)}
    baseline = float(history.price.iloc[-WINDOW - 1:-1].mean())
    value = (float(history.price.iloc[-1]) / baseline - 1) * 100
    return {"state": "Above baseline" if value > THRESHOLD else "Below baseline" if value < -THRESHOLD else "Within range",
            "deviation_pct": round(value, 3), "baseline": round(baseline, 2), "history_count": WINDOW}


def replay(frame: pd.DataFrame, spec: dict):
    events = []
    for row in frame.to_dict(orient="records"):
        decision_at = row["available_at"]
        if spec["available_at"] > decision_at:
            continue
        # Re-filter at each historical decision, even when the outer query has a later cutoff.
        history = frame[(frame.observed_at <= decision_at) & (frame.available_at <= decision_at)
                        & (frame.trading_date <= row["trading_date"])].sort_values("trading_date")
        events.append({"trading_date": row["trading_date"], "decision_at": decision_at,
                       "price": row["price"], "spec_version": row["spec_version"], **deviation(history)})
    counts = {state: sum(e["state"] == state for e in events) for state in ("Above baseline", "Below baseline", "Within range", "Warming up")}
    return {"method": "Point-in-time signal replay", "window": WINDOW, "threshold_pct": THRESHOLD,
            "events": events, "counts": counts,
            "note": "At each observation's availability time, compare its price with the prior five available trading observations. No simulated trades, fills or P&L. Fees, taxes, slippage and settlement risks are not modeled."}


def comparisons(db, selected: dict, as_of: str, latest: dict | None):
    specs = [dict(s) for s in db.execute("SELECT * FROM specs WHERE dataset=? AND available_at<=? ORDER BY symbol,expiry", (selected["dataset"], as_of))]
    comparisons, signals = [], []
    for spec in specs:
        history = pd.read_sql_query("SELECT * FROM prices WHERE contract_id=? AND dataset=? AND symbol=? AND expiry=? AND spec_version=? AND observed_at<=? AND available_at<=? AND trading_date<=? ORDER BY trading_date", db,
                                    params=(spec["contract_id"], spec["dataset"], spec["symbol"], spec["expiry"], spec["spec_version"], as_of, as_of, as_of[:10]))
        if history.empty:
            continue
        row = history.iloc[-1].to_dict()
        per_gram = float(row["price"]) / spec["quote_grams"]
        aligned = latest is not None and latest["trading_date"] == row["trading_date"]
        selected_per_gram = latest["price"] / selected["quote_grams"] if latest else None
        comparisons.append({"contract_id": spec["contract_id"], "symbol": spec["symbol"], "expiry": spec["expiry"],
                            "spec_version": spec["spec_version"], "trading_date": row["trading_date"], "quote_grams": spec["quote_grams"],
                            "price": float(row["price"]), "price_per_gram": round(per_gram, 2),
                            "gap_pct": round((per_gram / selected_per_gram - 1) * 100, 3) if aligned else None,
                            "aligned_date": aligned, "volume": int(row["volume"]), "open_interest": int(row["open_interest"])})
        signals.append({"contract_id": spec["contract_id"], "symbol": spec["symbol"], "expiry": spec["expiry"], "spec_version": spec["spec_version"],
                        "trading_date": row["trading_date"], "available_at": row["available_at"], **deviation(history)})
    return comparisons, signals
