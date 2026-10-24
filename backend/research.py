"""Read immutable imported records, validate their references, then build exact-expiry pairs."""
from decimal import Decimal, InvalidOperation
from itertools import combinations
import json
from pathlib import Path
import sqlite3

from .domain import utc
from .ingestion import check_storage_path
from .normalization import normalize_observation, FORMULA
from .reference import ReferenceFailure, ReferenceRegistry, canonical_hash, official_url

BASIS_FIELDS = ("delivery_locations", "delivery_restrictions", "settlement_method", "settlement_terms", "expiry_restrictions")


def contract_id(spec, listing):
    return f"{spec.instrument}:{listing.expiry}:{spec.version}"


def contract_view(spec, listing):
    return {"contract_id": contract_id(spec, listing), "dataset": spec.dataset, "symbol": spec.instrument,
            "expiry": listing.expiry, "spec_id": spec.spec_id, "spec_version": spec.version, "currency": spec.currency,
            "unit": spec.price_unit, "quote_grams": float(spec.quotation_grams) if spec.quotation_grams else None,
            "lot_grams": float(spec.lot_size_grams) if spec.lot_size_grams else None,
            "purity": float(spec.quote_purity_per_mille / 1000) if spec.quote_purity_per_mille else None,
            "quotation_grams": str(spec.quotation_grams) if spec.quotation_grams else None,
            "lot_size_grams": str(spec.lot_size_grams) if spec.lot_size_grams else None,
            "quote_purity_per_mille": str(spec.quote_purity_per_mille) if spec.quote_purity_per_mille else None,
            "valid_from": spec.effective_date, "valid_to": spec.effective_until or spec.verified_through,
            "delivery_locations": list(spec.delivery_locations), "delivery_location": ", ".join(spec.delivery_locations),
            "delivery_basis": spec.delivery_restrictions, "delivery_restrictions": spec.delivery_restrictions,
            "settlement_method": spec.settlement_method, "settlement_terms": spec.settlement_terms,
            "expiry_restrictions": spec.expiry_restrictions, "verification": spec.verification_status,
            "safe_exit_date": listing.safe_exit_date, "tender_start": listing.delivery_start,
            "delivery_end": listing.delivery_end, "available_at": max(spec.available_at, listing.available_at),
            "source": spec.source_url, "listing_source": listing.source_url, "description": spec.applicability}


def snapshot(path: Path, dataset: str, as_of: str):
    """Use one read transaction so reference and price reads share a snapshot."""
    utc(as_of)
    check_storage_path(path, dataset)
    if not path.exists():
        raise ReferenceFailure("DATASET_UNAVAILABLE", f"{dataset.capitalize()} data is not configured. No substitute dataset.")
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        db.execute("BEGIN")
        if db.execute("PRAGMA user_version").fetchone()[0] != 4:
            raise ReferenceFailure("STORAGE_VERSION", "An explicit v4 imported dataset is required")
        if db.execute("SELECT dataset FROM metadata").fetchall() != [(dataset,)]:
            raise ReferenceFailure("DATASET_MISMATCH", "Database ownership does not match the requested dataset")
        groups = {"spec": [], "listing": [], "calendar": []}
        for kind, identifier, payload, digest in db.execute("SELECT kind,id,payload,sha256 FROM reference_versions ORDER BY kind,id"):
            record = json.loads(payload)
            if kind not in groups or canonical_hash(record) != digest:
                raise ReferenceFailure("REFERENCE_INTEGRITY", "Stored reference hash or kind is invalid")
            expected_id = record.get("spec_id") if kind == "spec" else record.get("calendar_id") if kind == "calendar" else f"{record['instrument']}:{record['expiry']}:{record['spec_id']}"
            if identifier != expected_id:
                raise ReferenceFailure("REFERENCE_INTEGRITY", "Stored reference identifier does not match its payload")
            groups[kind].append(record)
        registry = ReferenceRegistry.model_validate({"specs": groups["spec"], "contracts": groups["listing"], "calendars": groups["calendar"]})
        if any(s.dataset != dataset for s in registry.specs) or any(c.dataset != dataset for c in registry.calendars):
            raise ReferenceFailure("DATASET_MISMATCH", "Reference dataset does not match storage ownership")
        raw = []
        for owner, symbol, expiry, spec_id, day, payload in db.execute("SELECT dataset,instrument,expiry,spec_id,trading_date,payload FROM observations ORDER BY instrument,expiry,spec_id,trading_date"):
            row = json.loads(payload)
            if (owner, symbol, expiry, spec_id, day) != tuple(row.get(k) for k in ("dataset", "instrument", "expiry", "spec_id", "trading_date")) or owner != dataset:
                raise ReferenceFailure("PRICE_IDENTITY", "Stored price identity differs from its payload or dataset")
            raw.append(row)
    return registry, raw


def research_snapshot(path: Path, dataset: str, as_of: str) -> dict:
    registry, raw = snapshot(path, dataset, as_of)
    contracts, histories, issues = [], {}, []
    by_reference = {}
    for listing in registry.contracts:
        spec = registry.spec(listing.spec_id)
        if spec.available_at > as_of or listing.available_at > as_of:
            continue
        view = contract_view(spec, listing)
        view.update(normalization_status="READY", normalization_reason=None)
        try:
            # Completeness at a known effective date; prices are separately checked at THEIR trading dates.
            spec.require_usable(spec.effective_date or as_of[:10], as_of)
            if listing.instrument != spec.instrument or not listing.first_trade_date or not listing.source_url.strip():
                raise ReferenceFailure("UNCONFIRMED_EXPIRY", "Exact listing terms are missing or inconsistent")
            expected = "SYNTHETIC" if dataset == "synthetic" else "VERIFIED"
            if listing.verification_status != expected or (dataset == "real" and not official_url(listing.source_url)):
                raise ReferenceFailure("UNCONFIRMED_EXPIRY", "Exact listing is not verified")
        except ReferenceFailure as error:
            view.update(normalization_status="BLOCKED", normalization_reason=f"{error.code}: {error}")
        contracts.append(view)
        histories[view["contract_id"]] = []
        by_reference[(listing.instrument, listing.expiry, listing.spec_id)] = view
    for row in raw:
        view = by_reference.get((row["instrument"], row["expiry"], row["spec_id"]))
        if view is None:
            continue  # Unavailable reference versions cannot leak into an earlier snapshot.
        try:
            if utc(row["observed_at"]) > as_of or utc(row["available_at"]) > as_of:
                continue
            result = normalize_observation(row, registry, row["calendar_id"], as_of)
            # Exact Decimal strings remain the authoritative normalized values. Numeric aliases serve charts/legacy simulation.
            result.update(contract_id=view["contract_id"], symbol=row["instrument"], source=row["source_url"],
                unit=row["price_unit"], quoted_price_decimal=str(row["price"]), price=float(row["price"]),
                normalized_999_per_g=float(result["normalized_999_inr_per_gram"]))
            histories[view["contract_id"]].append(result)
        except (ValueError, InvalidOperation, KeyError) as error:
            issues.append({"contract_id": view["contract_id"], "trading_date": row["trading_date"],
                           "code": getattr(error, "code", "INVALID_RECORD"), "reason": str(error)})
    for rows in histories.values():
        rows.sort(key=lambda r: r["trading_date"])
    contracts.sort(key=lambda s: (s["symbol"], s["expiry"], s["spec_version"]))
    return {"dataset": dataset, "as_of": as_of, "contracts": contracts, "histories": histories, "issues": issues}


def basis_differences(left, right):
    result = [{"field": field, "left": left[field], "right": right[field]} for field in BASIS_FIELDS if left[field] != right[field]]
    for field in ("tender_start", "delivery_end", "safe_exit_date"):
        if left[field] != right[field]:
            result.append({"field": field, "left": left[field], "right": right[field]})
    return result


def pair_catalog(state: dict, selected: dict) -> dict:
    matches, unmatched, rows = [], [], []
    histories = state["histories"]
    for other in state["contracts"]:
        latest = histories[other["contract_id"]][-1] if histories[other["contract_id"]] else None
        rows.append({"contract": other, "latest": latest,
                     "reason": other["normalization_reason"] or (None if latest else "No usable prices available at this cutoff")})
        if other["contract_id"] == selected["contract_id"]:
            continue
        reason = None
        if other["expiry"] != selected["expiry"]:
            reason = f"Exact expiry differs: {other['expiry']} versus {selected['expiry']}; no nearby-expiry substitution"
        elif other["symbol"] == selected["symbol"]:
            reason = "Same instrument; alternative specification versions are separate partitions, not another pair leg"
        elif selected["normalization_status"] != "READY" or other["normalization_status"] != "READY":
            reason = selected["normalization_reason"] or other["normalization_reason"]
        if reason:
            unmatched.append({"contract": other, "reason": reason})
            continue
        a, b = histories[selected["contract_id"]], histories[other["contract_id"]]
        common = sorted({r["trading_date"] for r in a} & {r["trading_date"] for r in b})
        aligned = bool(a and b and a[-1]["trading_date"] == b[-1]["trading_date"])
        spread = str(Decimal(a[-1]["normalized_999_inr_per_gram"]) - Decimal(b[-1]["normalized_999_inr_per_gram"])) if aligned else None
        matches.append({"pair_id": f"{state['dataset']}|{selected['contract_id']}|{other['contract_id']}",
            "contract_a": selected["contract_id"], "contract_b": other["contract_id"], "expiry": selected["expiry"],
            "basis_differences": basis_differences(selected, other), "common_observations": len(common),
            "latest_common_trading_date": common[-1] if common else None, "latest_spread_999_inr_per_gram": spread,
            "latest_available_at": max(a[-1]["normalized_available_at"], b[-1]["normalized_available_at"]) if aligned else None,
            "status": "ALIGNED" if aligned else "INSUFFICIENT_DATA",
            "reason": "Exact expiry and latest trading date match; delivery/settlement basis still matters" if aligned else "No matching latest trading date; no forward fill or stale-price substitution"})
    return {"matches": matches, "unmatched": unmatched, "normalization": rows, "formula": FORMULA,
            "unit": "INR per gram (999 purity)", "spread_direction": "A minus B"}


def quote_summary(rows, spec):
    """Keep existing single-contract indicators, with full reference availability in historical replay."""
    def signal(history):
        if len(history) < 6:
            return {"state": "Warming up", "baseline": None, "deviation_pct": None, "history_count": max(0, len(history) - 1)}
        baseline = sum(Decimal(r["quoted_price_decimal"]) for r in history[-6:-1]) / 5
        deviation = (Decimal(history[-1]["quoted_price_decimal"]) / baseline - 1) * 100
        return {"state": "Above baseline" if deviation > Decimal("0.2") else "Below baseline" if deviation < Decimal("-0.2") else "Within range",
                "baseline": float(baseline), "deviation_pct": float(deviation), "history_count": 5}
    events = []
    for row in rows:
        decision = row["normalized_available_at"]
        history = [r for r in rows if r["observed_at"] <= decision and r["available_at"] <= decision and r["normalized_available_at"] <= decision and r["trading_date"] <= row["trading_date"]]
        events.append({"trading_date": row["trading_date"], "decision_at": decision, "price": row["price"], "spec_version": spec["spec_version"], **signal(history)})
    mean = sum(Decimal(r["quoted_price_decimal"]) for r in rows[-5:]) / min(5, len(rows)) if rows else None
    change = (Decimal(rows[-1]["quoted_price_decimal"]) / Decimal(rows[-2]["quoted_price_decimal"]) - 1) * 100 if len(rows) > 1 else None
    return {"mean_5": float(mean) if mean is not None else None, "change_pct": float(change) if change is not None else None, "count": len(rows)}, events
