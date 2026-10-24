"""Paired prior-only research. Original quotes retained; no price filling or rolling."""
from datetime import datetime
import math
import statistics
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
    lookback: int = Field(default=10, ge=2, le=250)
    min_observations: int = Field(default=5, ge=2, le=250)
    entry_z: float = Field(default=2.5, gt=0, le=100)
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
    a,b = specs
    for spec, rows in zip(specs,histories):
        for row in rows:
            if any(row[k]!=spec[k] for k in ("dataset","symbol","expiry","spec_version","contract_id")):
                raise ValueError("Mixed identity partition")
        if len({r["trading_date"] for r in rows}) != len(rows):
            raise ValueError("Duplicate pair observations")
    maps = [{r["trading_date"]:r for r in rows if r["observed_at"]<=request.as_of and r["available_at"]<=request.as_of} for rows in histories]
    days = sorted(set(maps[0]) | set(maps[1]))
    events, missing = [], []
    for day in days:
        if day not in maps[0] or day not in maps[1]:
            missing.append({"trading_date":day,"reason":"Missing one leg; no forward fill"})
            continue
        rows = [m[day] for m in maps]
        decision = max(r["available_at"] for r in rows)
        p = [normalize(r["price"],s) for r,s in zip(rows,specs)]
        prior = [e for e in events if e["decision_at"]<=decision and e["trading_date"]<day and not e["quality_reasons"]][-request.lookback:]
        basis = statistics.mean(e["raw_pair_spread"] for e in prior) if len(prior)>=request.min_observations else None
        residual = p[0]-p[1]-basis if basis is not None else None
        residuals = [e["residual_spread"] for e in prior if e["residual_spread"] is not None]
        mean = statistics.mean(residuals) if len(residuals)>=request.min_observations else None
        std = statistics.stdev(residuals) if mean is not None else None
        diff = residual-mean if residual is not None and mean is not None else None
        z = diff/std if diff is not None and std is not None and std>1e-9 else None
        quality = []
        for r,s in zip(rows,specs):
            if not s["valid_from"] <= day <= s["valid_to"] or s["available_at"]>decision:
                quality.append(f"Stale/unavailable spec: {s['symbol']}")
            if seconds(decision,r["observed_at"])>request.max_age_days*86400 or seconds(decision,day+'T00:00:00Z')>request.max_age_days*86400:
                quality.append(f"Stale observation: {s['symbol']}")
            if r["volume"]<request.min_volume or r["open_interest"]<request.min_oi:
                quality.append(f"Insufficient volume/OI proxy: {s['symbol']}")
            if day>s["safe_exit_date"]:
                quality.append(f"Past safe exit: {s['symbol']}")
        if quality:
            status,reason = "REJECTED", "; ".join(quality)
        elif mean is None:
            status,reason = "INSUFFICIENT_DATA", f"Need {request.min_observations} prior residuals; have {len(residuals)}"
        elif z is None:
            status,reason = "NO_SIGNAL", "Prior residual standard deviation is zero; z-score undefined"
        elif abs(z)>=request.entry_z:
            status,reason = "INVESTIGATE", f"Absolute z-score {abs(z):.3f} meets threshold {request.entry_z}; investigate costs and basis"
        else:
            status,reason = "NO_SIGNAL", f"Absolute z-score {abs(z):.3f} is below threshold {request.entry_z}"
        events.append({"trading_date":day,"decision_at":decision,"normalized_a":p[0],"normalized_b":p[1],
            "raw_pair_spread":p[0]-p[1],"expected_basis":basis,"residual_spread":residual,"residual_mean":mean,
            "residual_std":std,"baseline":basis+mean if basis is not None and mean is not None else None,
            "difference":diff,"z_score":z,"upper_z":request.entry_z,"lower_z":-request.entry_z,
            "history_count":len(residuals),"status":status,"reason":reason,"quality_reasons":quality,
            "a":rows[0],"b":rows[1],"age_hours":max(seconds(decision,r["observed_at"]) for r in rows)/3600})
    latest = dict(events[-1]) if events else None
    if latest:
        latest["age_hours"] = max(seconds(request.as_of,latest[k]["observed_at"]) for k in ('a','b'))/3600
        if latest["age_hours"]>request.max_age_days*24:
            latest.update(status="REJECTED",reason="Latest paired observation is stale at requested as-of time")
        if missing and missing[-1]["trading_date"]>latest["trading_date"]:
            latest.update(status="REJECTED",reason="Latest date is missing one leg; prior aligned date is shown for context")
    calendar = a["expiry"]!=b["expiry"]
    return {"dataset":request.dataset,"label":request.dataset.upper(),"as_of":request.as_of,"spec_a":a,"spec_b":b,
            "alignment":"CALENDAR_BASIS_DIFFERENCE" if calendar else "EXACT_EXPIRY",
            "expiry_difference_days":(datetime.fromisoformat(a["expiry"])-datetime.fromisoformat(b["expiry"])).days,
            "cautions":CAUTIONS + ([f"Different exact expiries: {a['expiry']} versus {b['expiry']}; calendar basis is unresolved."] if calendar else []),
            "method":{"lookback":request.lookback,"min_observations":request.min_observations,"entry_z":request.entry_z,
                      "basis":"Prior-only rolling mean of raw spread; residual statistics also use prior available observations only; sample std (ddof=1)."},
            "history":events,"latest":latest,"quality":{"missing_dates":missing,"calendar":"Synthetic weekdays; no verified MCX holiday calendar","no_forward_fill":True}}
