"""Invented v4 fixtures, published through the same strict importer as user CSVs."""
import csv
import io
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
import sqlite3

from .domain import DEFAULT_AS_OF
from .ingestion import CSV_COLUMNS, ImportManifest, import_csv, check_storage_path
from .reference import ReferenceRegistry, canonical_hash
from .store import fixtures as legacy_fixtures

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DB = ROOT / "data/synthetic/goldlens-v4.sqlite3"
REAL_DB = ROOT / "data/real/imports-v4.sqlite3"
SOURCE = "https://synthetic.goldlens.invalid/demo-v4"


def fixture_batch():
    old_specs, old_prices = legacy_fixtures()
    # These are explicitly invented dates, not exchange listings or month inference.
    expiries = {"GOLDM": ("2026-11-20", "2026-12-18"), "GOLDTEN": ("2026-11-20", "2026-12-22"),
                "GOLDGUINEA": ("2026-11-20", "2026-12-24"), "GOLDPETAL": ("2026-11-20", "2026-12-28")}
    windows = {"2026-11-20": ("2026-11-13", "2026-11-16"), "2026-12-18": ("2026-12-11", "2026-12-14"),
               "2026-12-22": ("2026-12-15", "2026-12-18"), "2026-12-24": ("2026-12-17", "2026-12-20"),
               "2026-12-28": ("2026-12-21", "2026-12-24")}
    specs, listings, expected, rows = [], [], [], []
    for symbol, dates in expiries.items():
        source_specs = [s for s in old_specs if s["symbol"] == symbol]
        s = source_specs[0]
        spec_id = f"{symbol}:demo-v4"
        specs.append({"spec_id": spec_id, "instrument": symbol, "dataset": "synthetic", "version": "demo-v4",
            "verification_status": "SYNTHETIC", "source_url": SOURCE, "retrieved_at": "2026-08-01T00:00:00Z",
            "available_at": "2026-08-01T00:00:00Z", "effective_date": "2026-08-01", "verified_through": "2026-12-31",
            "applicability": "Invented v4 terms and knowledge times for synthetic research only",
            "quotation_grams": str(s["quote_grams"]), "lot_size_grams": str(s["lot_grams"]),
            "quote_purity_per_mille": str(Decimal(str(s["purity"])) * 1000),
            "delivery_locations": ["Demo Mumbai" if symbol == "GOLDPETAL" else "Demo Ahmedabad"],
            "expiry_restrictions": "Exact invented listing; expiry is never inferred",
            "delivery_restrictions": "Invented tender delivery; taxes and premia unresolved",
            "settlement_method": "Invented physical delivery",
            "settlement_terms": "Demo petal settlement at location B" if symbol == "GOLDPETAL" else "Demo settlement at location A"})
        for old_spec, expiry in zip(source_specs, dates):
            safe, tender = windows[expiry]
            listings.append({"instrument": symbol, "expiry": expiry, "spec_id": spec_id,
                "first_trade_date": "2026-08-01", "last_trade_date": expiry, "verification_status": "SYNTHETIC",
                "source_url": SOURCE, "available_at": "2026-08-01T00:00:00Z", "safe_exit_date": safe,
                "delivery_start": tender, "delivery_end": expiry})
            expected.append({"instrument": symbol, "expiry": expiry, "spec_id": spec_id})
            for price in [p for p in old_prices if p["contract_id"] == old_spec["contract_id"]]:
                rows.append({"dataset": "synthetic", "instrument": symbol, "expiry": expiry,
                    "trading_date": price["trading_date"], "spec_id": spec_id, "price": str(price["price"]),
                    "currency": "INR", "price_unit": "INR_PER_QUOTATION", "quotation_grams": specs[-1]["quotation_grams"],
                    "quote_purity_per_mille": specs[-1]["quote_purity_per_mille"], "volume": price["volume"],
                    "open_interest": price["open_interest"], "session": "demo", "source_url": SOURCE,
                    "observed_at": price["observed_at"], "available_at": price["available_at"]})
    days = {}
    day = date(2026, 8, 1)
    while day <= date(2026, 12, 31):
        opened = day.weekday() < 5
        days[day.isoformat()] = {"state": "OPEN" if opened else "CLOSED", "windows": [{"name": "demo",
            "opens_at": f"{day}T03:30:00Z", "closes_at": f"{day}T17:30:00Z"}] if opened else []}
        day += timedelta(days=1)
    registry = ReferenceRegistry.model_validate({"specs": specs, "contracts": listings, "calendars": [{
        "calendar_id": "synthetic-sessions-v4", "dataset": "synthetic", "verification_status": "SYNTHETIC",
        "source_url": SOURCE, "available_at": "2026-08-01T00:00:00Z", "coverage_start": "2026-08-01",
        "coverage_end": "2026-12-31", "days": days}]})
    manifest = ImportManifest.model_validate({"schema_version": "goldlens.csv.v1", "dataset": "synthetic",
        "as_of": DEFAULT_AS_OF, "start_date": "2026-09-01", "end_date": "2026-10-23",
        "calendar_id": "synthetic-sessions-v4", "expected_contracts": expected,
        "min_normalized_inr_per_gram": "1000", "max_normalized_inr_per_gram": "20000"})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue(), manifest, registry


def seed(path=SYNTHETIC_DB):
    path = Path(path)
    check_storage_path(path, "synthetic")
    content, manifest, registry = fixture_batch()
    if path.exists():
        # Verify immutable seed content on restart, never overwrite or silently reseed errors.
        with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
            if db.execute("PRAGMA user_version").fetchone()[0] != 4:
                raise ValueError("Synthetic v4 requires a separate v4 database")
            batches = db.execute("SELECT csv_text,manifest FROM batches").fetchall()
            if not any(c == content and ImportManifest.model_validate_json(m) == manifest for c, m in batches):
                raise ValueError("Published synthetic batch differs; use a new dataset version")
            for kind, items in (("spec", [(s.spec_id, s) for s in registry.specs]),
                                ("listing", [(f"{s.instrument}:{s.expiry}:{s.spec_id}", s) for s in registry.contracts]),
                                ("calendar", [(s.calendar_id, s) for s in registry.calendars])):
                for key, record in items:
                    found = db.execute("SELECT sha256 FROM reference_versions WHERE kind=? AND id=?", (kind, key)).fetchone()
                    if not found or found[0] != canonical_hash(record.model_dump(mode="json")):
                        raise ValueError("Published reference differs from synthetic v4")
        return
    result = import_csv(content, manifest, registry, path)
    if not result["valid"]:
        raise ValueError(result["issues"])


if __name__ == "__main__":
    seed()
    print(f"SYNTHETIC demo-v4: 4 specifications, 8 exact listings, 312 prices -> {SYNTHETIC_DB}")
