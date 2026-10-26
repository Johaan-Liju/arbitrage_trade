"""Strict CSV validation. No month-to-expiry inference or silent unit conversion."""
import csv
from io import StringIO
from .domain import Price, validate_price, normalize, utc
from .store import insert

COLUMNS = list(Price.model_fields)


def validate_csv(text, specs, existing=(), expected_dates=None, as_of=None):
    if len(text) > 5_000_000:
        raise ValueError("CSV exceeds 5 MB limit")
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or set(reader.fieldnames) != set(COLUMNS):
        raise ValueError("Mismatched CSV schema; exact columns required: " + ",".join(COLUMNS))
    known = {s["contract_id"]: s for s in specs}
    seen = set(existing)
    rows, errors, warnings = [], [], []
    for line, raw in enumerate(reader, 2):
        if line > 20001:
            raise ValueError("CSV exceeds 20000 rows")
        try:
            if None in raw or any(v is None or not v.strip() for v in raw.values()):
                raise ValueError("Missing observation field or extra column")
            for field in ("price", "open", "high", "low", "close"):
                raw[field] = float(raw[field])
            for field in ("volume", "open_interest"):
                raw[field] = int(raw[field])
            spec = known.get(raw["contract_id"])
            if spec is None:
                raise ValueError("Unknown exact contract/specification")
            row = validate_price(raw, spec)
            key = (row["contract_id"],row["trading_date"])
            if key in seen:
                raise ValueError("Duplicated contract/trading-date key (including existing storage)")
            seen.add(key)
            if as_of and (row["available_at"] > utc(as_of) or row["ingested_at"] > as_of):
                raise ValueError("Future availability/ingestion beyond import cutoff")
            if expected_dates is not None and row["trading_date"] not in expected_dates:
                raise ValueError("Date is not in the explicitly supplied session calendar (holiday/closed)")
            if row["dataset"] == "real" and (expected_dates is None or spec["verification"] != "VERIFIED"):
                raise ValueError("UNVERIFIED specification/calendar blocks real ingestion")
            normalized = normalize(row["price"], spec)
            if normalized < 100 or normalized > 100000:
                warnings.append({"line":line,"reason":"Unusual INR/g; retained for review, not proof of an error"})
            rows.append(row)
        except (ValueError, TypeError) as error:
            errors.append({"line":line,"reason":str(error)})
    if not rows and not errors:
        errors.append({"line":2,"reason":"Missing observations: CSV has no records"})
    if expected_dates is not None:
        for contract_id in {r["contract_id"] for r in rows}:
            missing = sorted(set(expected_dates)-{r["trading_date"] for r in rows if r["contract_id"]==contract_id})
            if missing:
                errors.append({"line":0,"reason":f"Missing observations for {contract_id}: {','.join(missing)}"})
    normalized = [{"contract_id":r["contract_id"],"expiry":r["expiry"],"spec_version":r["spec_version"],
                   "trading_date":r["trading_date"],"original_quote":r["price"],"source":r["source"],
                   "normalized_999_per_g":normalize(r["price"],known[r["contract_id"]])} for r in rows] if not errors else []
    return {"accepted":not errors,"rows":rows if not errors else [],"normalized_observations":normalized,"errors":errors,"warnings":warnings,
            "calendar_status":"EXPLICIT_SESSION_LIST" if expected_dates is not None else "UNVERIFIED; missing sessions cannot be distinguished from holidays"}


def ingest(db, text, specs, expected_dates, as_of, dry_run=True):
    existing = {(r[0],r[1]) for r in db.execute("SELECT contract_id,trading_date FROM prices")}
    result = validate_csv(text,specs,existing,expected_dates,as_of)
    if result["accepted"] and not dry_run:
        for row in result["rows"]:
            insert(db,"daily_prices",row)
    return {**result,"dry_run":dry_run,"inserted":len(result["rows"]) if result["accepted"] and not dry_run else 0}
