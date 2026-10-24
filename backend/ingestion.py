"""Strict daily-observation CSV ingestion; no guessing, coercion or partial commits."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import re
import sqlite3
from typing import Literal
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from pydantic import Field, model_validator

from .domain import utc
from .reference import (FrozenModel, ReferenceFailure, ReferenceRegistry, canonical_hash,
                        exact_date, load_registry, normalize_999, official_url)

ROOT = Path(__file__).resolve().parents[1]
CSV_COLUMNS = ("dataset", "instrument", "expiry", "trading_date", "spec_id", "price", "currency", "price_unit",
               "quotation_grams", "quote_purity_per_mille", "volume", "open_interest", "session", "source_url", "observed_at", "available_at")


class ExpectedContract(FrozenModel):
    instrument: str
    expiry: str
    spec_id: str


class ImportManifest(FrozenModel):
    schema_version: Literal["goldlens.csv.v1"]
    dataset: Literal["real", "synthetic"]
    as_of: str
    start_date: str
    end_date: str
    calendar_id: str
    expected_contracts: tuple[ExpectedContract, ...] = Field(min_length=1)
    # User-reviewed plausibility bounds, NOT exchange price bands or market facts.
    min_normalized_inr_per_gram: Decimal = Field(gt=0)
    max_normalized_inr_per_gram: Decimal = Field(gt=0)

    @model_validator(mode="after")
    def structure(self):
        utc(self.as_of)
        start, end = exact_date(self.start_date), exact_date(self.end_date)
        if start > end or (end - start).days > 366:
            raise ValueError("Manifest must cover an ordered range of at most 367 calendar dates")
        if self.end_date > self.as_of[:10]:
            raise ValueError("Manifest range cannot extend beyond as-of date")
        keys = [(c.instrument, c.expiry) for c in self.expected_contracts]
        if len(keys) != len(set(keys)):
            raise ValueError("Each instrument/expiry must have exactly one expected spec per batch")
        for c in self.expected_contracts:
            exact_date(c.expiry)
        if self.min_normalized_inr_per_gram >= self.max_normalized_inr_per_gram:
            raise ValueError("Sanity bounds must be ordered")
        return self


def decimal_cell(value: str, field: str) -> Decimal:
    # Reject currency symbols, scientific notation, thousands separators and excessive precision.
    if not re.fullmatch(r"(?:0|[1-9]\d{0,17})(?:\.\d{1,8})?", value):
        raise ReferenceFailure("INVALID_NUMBER", f"{field}: require plain unsigned decimal, <=18 integer and 8 fractional digits")
    return Decimal(value)


def integer_cell(value: str, field: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9]\d{0,14})", value):
        raise ReferenceFailure("INVALID_NUMBER", f"{field}: require a nonnegative integer, no separators")
    return int(value)


def validate_csv(content: str, manifest: ImportManifest, registry: ReferenceRegistry, existing_keys=()) -> dict:
    issues, normalized, expected_keys = [], [], set()

    def issue(code, message, row=None):
        issues.append({"code": code, "message": message, "row": row})

    if len(content.encode("utf-8")) > 5_000_000:
        issue("FILE_TOO_LARGE", "CSV limit is 5 MB")
        return {"valid": False, "issues": issues, "rows": [], "dataset": manifest.dataset}
    if "\x00" in content:
        issue("SCHEMA_MISMATCH", "NUL bytes are not allowed")
        return {"valid": False, "issues": issues, "rows": [], "dataset": manifest.dataset}
    csv_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    manifest_hash = canonical_hash(manifest.model_dump(mode="json"))
    registry_hash = canonical_hash(registry.model_dump(mode="json"))
    calendar = None
    expected_contracts = {(c.instrument, c.expiry): c for c in manifest.expected_contracts}
    try:
        calendar = registry.calendar(manifest.calendar_id)
        if calendar.dataset != manifest.dataset:
            raise ReferenceFailure("DATASET_MISMATCH", "Calendar belongs to another dataset")
        day = exact_date(manifest.start_date)
        while day <= exact_date(manifest.end_date):
            session_day = calendar.day(day.isoformat(), manifest.as_of)
            for requested in manifest.expected_contracts:
                spec = registry.spec(requested.spec_id)
                if spec.dataset != manifest.dataset or spec.instrument != requested.instrument:
                    raise ReferenceFailure("SPEC_IDENTITY_MISMATCH", "Manifest spec does not match dataset/instrument")
                listing = registry.contract(requested.instrument, requested.expiry, requested.spec_id)
                expected_status = "VERIFIED" if manifest.dataset == "real" else "SYNTHETIC"
                if listing.verification_status != expected_status or not listing.first_trade_date:
                    raise ReferenceFailure("UNCONFIRMED_EXPIRY", "Exact expiry and listing interval must be verified")
                if manifest.dataset == "real" and not official_url(listing.source_url):
                    raise ReferenceFailure("UNCONFIRMED_EXPIRY", "Real listing requires an official MCX source")
                if listing.available_at > manifest.as_of:
                    raise ReferenceFailure("FUTURE_LISTING", "Listing was not known at the cutoff")
                if listing.first_trade_date <= day.isoformat() <= listing.last_trade_date:
                    spec.require_usable(day.isoformat(), manifest.as_of)
                    if session_day.state != "CLOSED":
                        expected_keys.add((manifest.dataset, requested.instrument, requested.expiry, day.isoformat()))
            day += timedelta(days=1)
    except (ReferenceFailure, ValueError) as error:
        issue(getattr(error, "code", "INVALID_REFERENCE"), str(error))

    reader = csv.reader(io.StringIO(content.lstrip("\ufeff")), strict=True)
    seen = set()
    stored = set(tuple(key) for key in existing_keys)
    try:
        header = next(reader, None)
        if header != list(CSV_COLUMNS):
            issue("SCHEMA_MISMATCH", "CSV header and order must exactly match goldlens.csv.v1; no aliases or duplicate/extra columns")
            return {"valid": False, "dataset": manifest.dataset, "issues": issues, "rows": [], "csv_sha256": csv_hash}
        for cells in reader:
            line = reader.line_num
            if len(cells) != len(CSV_COLUMNS):
                issue("SCHEMA_MISMATCH", f"Expected {len(CSV_COLUMNS)} fields; got {len(cells)}", line)
                continue
            original = dict(zip(CSV_COLUMNS, cells))
            row = original
            try:
                if any(not cell or cell != cell.strip() for cell in cells):
                    raise ReferenceFailure("MISSING_OR_PADDED_VALUE", "Every field is required; whitespace is not silently trimmed")
                if row["dataset"] != manifest.dataset:
                    raise ReferenceFailure("DATASET_MISMATCH", "Row dataset does not match import manifest")
                expiry = exact_date(row["expiry"])
                trading_date = exact_date(row["trading_date"])
                key = (manifest.dataset, row["instrument"], row["expiry"], row["trading_date"])
                if key in seen or key in stored:
                    raise ReferenceFailure("DUPLICATE_OBSERVATION", f"Duplicate instrument/expiry/trading-date key: {key}")
                seen.add(key)
                if trading_date > expiry or not manifest.start_date <= row["trading_date"] <= manifest.end_date:
                    raise ReferenceFailure("INVALID_TRADING_DATE", "Trading date exceeds expiry or is outside manifest range")
                requested = expected_contracts.get((row["instrument"], row["expiry"]))
                if not requested or requested.spec_id != row["spec_id"]:
                    raise ReferenceFailure("UNEXPECTED_CONTRACT", "Row contract/spec is not in the explicit import manifest")
                observed, available = utc(row["observed_at"]), utc(row["available_at"])
                if available < observed or available > manifest.as_of or observed > manifest.as_of:
                    raise ReferenceFailure("INVALID_CHRONOLOGY", "Require observed <= available <= explicit as-of")
                if datetime.fromisoformat(observed.replace("Z", "+00:00")).astimezone(ZoneInfo("Asia/Kolkata")).date() != trading_date:
                    raise ReferenceFailure("INVALID_TRADING_DATE", "Observation must belong to its Asia/Kolkata trading date")
                if urlparse(row["source_url"]).scheme not in ("http", "https") or not urlparse(row["source_url"]).hostname:
                    raise ReferenceFailure("MISSING_PROVENANCE", "Price source_url must be an explicit HTTP(S) source")
                price = decimal_cell(row["price"], "price")
                if price <= 0:
                    raise ReferenceFailure("INVALID_PRICE", "Gold price must be strictly positive")
                volume, oi = integer_cell(row["volume"], "volume"), integer_cell(row["open_interest"], "open_interest")
                spec = registry.spec(row["spec_id"])
                spec.require_usable(row["trading_date"], manifest.as_of)
                if spec.instrument != row["instrument"] or spec.dataset != manifest.dataset:
                    raise ReferenceFailure("SPEC_IDENTITY_MISMATCH", "Price does not belong to the referenced spec")
                if row["currency"] != spec.currency or row["price_unit"] != spec.price_unit:
                    raise ReferenceFailure("UNIT_MISMATCH", "Currency/price unit differs from the verified quote basis")
                if decimal_cell(row["quotation_grams"], "quotation_grams") != spec.quotation_grams:
                    raise ReferenceFailure("UNIT_MISMATCH", "Quotation grams must match the spec; lot size is NOT the quotation denominator")
                if decimal_cell(row["quote_purity_per_mille"], "quote_purity_per_mille") != spec.quote_purity_per_mille:
                    raise ReferenceFailure("PURITY_MISMATCH", "Use quoted-price purity, not delivery purity or 9999 notation")
                listing = registry.contract(row["instrument"], row["expiry"], row["spec_id"])
                if not listing.first_trade_date or not listing.first_trade_date <= row["trading_date"] <= listing.last_trade_date:
                    raise ReferenceFailure("OUTSIDE_LISTING", "Observation is outside the explicit contract trading interval")
                if calendar is None:
                    raise ReferenceFailure("UNVERIFIED_CALENDAR", "No verified session calendar")
                market_day = calendar.day(row["trading_date"], manifest.as_of)
                if market_day.state == "CLOSED":
                    raise ReferenceFailure("TRADING_HOLIDAY", "Observation falls on an explicitly closed trading date")
                window = next((w for w in market_day.windows if w.name == row["session"]), None)
                if not window or not window.opens_at <= observed <= window.closes_at:
                    raise ReferenceFailure("CLOSED_SESSION", "Observation is outside the named open session, including partial holidays")
                value = normalize_999(price, spec, row["trading_date"], manifest.as_of)
                if not manifest.min_normalized_inr_per_gram <= value <= manifest.max_normalized_inr_per_gram:
                    raise ReferenceFailure("UNUSUAL_PRICE_REVIEW_REQUIRED", "999-equivalent value is outside the explicit importer sanity bounds; no clipping or inferred unit correction")
                normalized.append({"dataset": manifest.dataset, "instrument": row["instrument"], "expiry": row["expiry"],
                    "trading_date": row["trading_date"], "spec_id": row["spec_id"], "spec_version": spec.version,
                    "price": row["price"], "currency": row["currency"], "price_unit": row["price_unit"],
                    "quotation_grams": str(spec.quotation_grams), "lot_size_grams": str(spec.lot_size_grams),
                    "quote_purity_per_mille": str(spec.quote_purity_per_mille), "volume": volume, "open_interest": oi,
                    "observed_at": observed, "available_at": available,
                    "normalized_available_at": max(available, spec.available_at, listing.available_at, calendar.available_at),
                    "normalized_999_inr_per_gram": str(value), "normalization_formula": "quoted_INR / quotation_grams * 999 / quote_purity_per_mille",
                    "normalization_version": "999-equivalent-v1", "delivery_locations": list(spec.delivery_locations),
                    "delivery_restrictions": spec.delivery_restrictions, "original": original,
                    "provenance": {"source_url": row["source_url"], "spec_source_url": spec.source_url,
                                   "listing_source_url": listing.source_url, "calendar_source_url": calendar.source_url,
                                   "csv_sha256": csv_hash, "manifest_sha256": manifest_hash,
                                   "registry_sha256": registry_hash, "source_line": line, "validated_as_of": manifest.as_of}})
    except csv.Error as error:
        issue("MALFORMED_CSV", str(error), reader.line_num)
    for key in sorted(expected_keys - seen):
        issue("MISSING_OBSERVATION", f"Missing expected open-session observation: {key}")
    if not normalized and not issues:
        issue("EMPTY_BATCH", "No observations to import")
    return {"valid": not issues, "dataset": manifest.dataset, "label": "SYNTHETIC" if manifest.dataset == "synthetic" else "REAL",
            "issues": issues, "rows": normalized if not issues else [], "row_count": len(normalized) if not issues else 0,
            "csv_sha256": csv_hash, "manifest_sha256": manifest_hash, "registry_sha256": registry_hash,
            "policy_note": "Sanity bounds are importer policy, not MCX price limits. No missing data is filled."}


SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (dataset TEXT PRIMARY KEY CHECK(dataset IN ('real','synthetic')));
CREATE TABLE IF NOT EXISTS reference_versions (kind TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, sha256 TEXT NOT NULL, PRIMARY KEY(kind,id));
CREATE TRIGGER IF NOT EXISTS reference_no_update BEFORE UPDATE ON reference_versions BEGIN SELECT RAISE(ABORT,'Reference versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS reference_no_delete BEFORE DELETE ON reference_versions BEGIN SELECT RAISE(ABORT,'Reference versions are immutable'); END;
CREATE TABLE IF NOT EXISTS batches (id TEXT PRIMARY KEY, csv_text TEXT NOT NULL, manifest TEXT NOT NULL, imported_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations (
 dataset TEXT NOT NULL, instrument TEXT NOT NULL, expiry TEXT NOT NULL, trading_date TEXT NOT NULL,
 spec_id TEXT NOT NULL, spec_kind TEXT NOT NULL DEFAULT 'spec', payload TEXT NOT NULL, batch_id TEXT NOT NULL REFERENCES batches(id),
 PRIMARY KEY(dataset,instrument,expiry,trading_date),
 FOREIGN KEY(spec_kind,spec_id) REFERENCES reference_versions(kind,id)
);
CREATE TRIGGER IF NOT EXISTS observation_no_update BEFORE UPDATE ON observations BEGIN SELECT RAISE(ABORT,'Observations are immutable'); END;
CREATE TRIGGER IF NOT EXISTS observation_no_delete BEFORE DELETE ON observations BEGIN SELECT RAISE(ABORT,'Observations are immutable'); END;
"""


def store_registry(db, registry: ReferenceRegistry):
    groups = (("spec", [(s.spec_id, s) for s in registry.specs]),
              ("listing", [(f"{s.instrument}:{s.expiry}:{s.spec_id}", s) for s in registry.contracts]),
              ("calendar", [(s.calendar_id, s) for s in registry.calendars]))
    for kind, records in groups:
        for key, record in records:
            payload = record.model_dump(mode="json")
            digest = canonical_hash(payload)
            existing = db.execute("SELECT sha256 FROM reference_versions WHERE kind=? AND id=?", (kind, key)).fetchone()
            if existing and existing[0] != digest:
                raise ReferenceFailure("IMMUTABLE_REFERENCE", f"{kind} {key} changed; publish a new version ID")
            if not existing:
                db.execute("INSERT INTO reference_versions VALUES (?,?,?,?)", (kind, key, json.dumps(payload, sort_keys=True), digest))


def persist_catalog(registry: ReferenceRegistry, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.executescript(SCHEMA)
        store_registry(db, registry)


def import_csv(content: str, manifest: ImportManifest, registry: ReferenceRegistry, path: Path | None = None) -> dict:
    result = validate_csv(content, manifest, registry)
    if not result["valid"]:
        return result
    path = path or ROOT / "data" / manifest.dataset / "imports.sqlite3"
    # Never allow an explicit path to cross the project's reserved dataset directories.
    opposite = ROOT / "data" / ("real" if manifest.dataset == "synthetic" else "synthetic")
    if path.resolve().is_relative_to(opposite.resolve()):
        raise ReferenceFailure("DATASET_MISMATCH", "Refusing to cross reserved real/synthetic storage paths")
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys=ON")
        db.executescript(SCHEMA)
        db.execute("BEGIN IMMEDIATE")
        dataset = db.execute("SELECT dataset FROM metadata").fetchone()
        if dataset and dataset[0] != manifest.dataset:
            raise ReferenceFailure("DATASET_MISMATCH", "Database belongs to another dataset")
        if not dataset:
            db.execute("INSERT INTO metadata VALUES (?)", (manifest.dataset,))
        existing = db.execute("SELECT dataset,instrument,expiry,trading_date FROM observations").fetchall()
        result = validate_csv(content, manifest, registry, existing)
        if not result["valid"]:
            db.rollback()
            return result
        store_registry(db, registry)
        batch_id = canonical_hash({"csv": result["csv_sha256"], "manifest": result["manifest_sha256"]})
        imported_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        db.execute("INSERT INTO batches VALUES (?,?,?,?)", (batch_id, content, manifest.model_dump_json(), imported_at))
        for row in result["rows"]:
            db.execute("INSERT INTO observations(dataset,instrument,expiry,trading_date,spec_id,payload,batch_id) VALUES (?,?,?,?,?,?,?)",
                       (row["dataset"], row["instrument"], row["expiry"], row["trading_date"], row["spec_id"], json.dumps(row, sort_keys=True), batch_id))
    return {**result, "batch_id": batch_id, "imported_at": imported_at}


def read_observations(path: Path, dataset: str, as_of: str) -> list[dict]:
    utc(as_of)
    if not path.exists():
        return []
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        owner = db.execute("SELECT dataset FROM metadata").fetchone()
        if not owner or owner[0] != dataset:
            raise ReferenceFailure("DATASET_MISMATCH", "Database does not belong to requested dataset")
        records = [json.loads(row[0]) for row in db.execute("SELECT payload FROM observations WHERE dataset=? ORDER BY instrument,expiry,trading_date", (dataset,))]
    return [r for r in records if r["observed_at"] <= as_of and r["available_at"] <= as_of and r["normalized_available_at"] <= as_of]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "import"])
    parser.add_argument("csv_path", type=Path)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--registry", type=Path, help="Explicit reviewed reference snapshot; defaults to the bundled MCX snapshot")
    args = parser.parse_args()
    registry = load_registry(args.registry) if args.registry else load_registry()
    manifest = ImportManifest.model_validate_json(args.manifest.read_text(encoding="utf-8"))
    content = args.csv_path.read_bytes().decode("utf-8")  # Preserve CRLF and original text in batch provenance.
    result = import_csv(content, manifest, registry) if args.action == "import" else validate_csv(content, manifest, registry)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
