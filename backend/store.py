from contextlib import contextmanager
from datetime import date, timedelta
import math
from pathlib import Path
import sqlite3

from .domain import Spec, validate_price

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DB = ROOT / "data" / "synthetic" / "goldlens-v1.sqlite3"
REAL_DB = ROOT / "data" / "real" / "goldlens.sqlite3"

SCHEMA = """
CREATE TABLE IF NOT EXISTS specs (
 contract_id TEXT PRIMARY KEY, dataset TEXT NOT NULL CHECK(dataset='synthetic'),
 symbol TEXT NOT NULL, expiry TEXT NOT NULL, spec_version TEXT NOT NULL,
 currency TEXT NOT NULL, unit TEXT NOT NULL, quote_grams REAL NOT NULL CHECK(quote_grams>0),
 available_at TEXT NOT NULL, source TEXT NOT NULL, description TEXT NOT NULL,
 UNIQUE(dataset,symbol,expiry,spec_version)
);
CREATE TABLE IF NOT EXISTS prices (
 contract_id TEXT NOT NULL REFERENCES specs(contract_id), dataset TEXT NOT NULL CHECK(dataset='synthetic'),
 symbol TEXT NOT NULL, expiry TEXT NOT NULL, spec_version TEXT NOT NULL,
 trading_date TEXT NOT NULL, price REAL NOT NULL CHECK(price>0), volume INTEGER NOT NULL CHECK(volume>=0),
 open_interest INTEGER NOT NULL CHECK(open_interest>=0), currency TEXT NOT NULL, unit TEXT NOT NULL,
 source TEXT NOT NULL, observed_at TEXT NOT NULL, available_at TEXT NOT NULL,
 PRIMARY KEY(contract_id,trading_date), CHECK(available_at>=observed_at), CHECK(trading_date<=expiry)
);
CREATE TRIGGER IF NOT EXISTS specs_no_update BEFORE UPDATE ON specs
 BEGIN SELECT RAISE(ABORT,'Specification versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS specs_no_delete BEFORE DELETE ON specs
 BEGIN SELECT RAISE(ABORT,'Specification versions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS prices_identity BEFORE INSERT ON prices
 WHEN NOT EXISTS(SELECT 1 FROM specs s WHERE s.contract_id=NEW.contract_id AND s.dataset=NEW.dataset
 AND s.symbol=NEW.symbol AND s.expiry=NEW.expiry AND s.spec_version=NEW.spec_version
 AND s.currency=NEW.currency AND s.unit=NEW.unit AND s.available_at<=NEW.available_at)
 BEGIN SELECT RAISE(ABORT,'Price identity does not match available specification'); END;
CREATE TRIGGER IF NOT EXISTS prices_no_update BEFORE UPDATE ON prices
 BEGIN SELECT RAISE(ABORT,'Published observations are immutable'); END;
"""


@contextmanager
def connection(path=SYNTHETIC_DB):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()


def fixtures():
    specs, prices = [], []
    # Exact invented dates are explicit, never inferred from a month label.
    contracts = [("GOLDM", 10, "2026-11-20", "2026-12-18"),
                 ("GOLDTEN", 10, "2026-11-24", "2026-12-22"),
                 ("GOLDGUINEA", 8, "2026-11-27", "2026-12-24"),
                 ("GOLDPETAL", 1, "2026-11-30", "2026-12-28")]
    days = [date(2026, 9, 1) + timedelta(days=i) for i in range(53)]
    days = [d for d in days if d.weekday() < 5]  # Demo weekdays, not an exchange calendar.
    for index, (symbol, grams, *expiries) in enumerate(contracts):
        for month, expiry in enumerate(expiries):
            spec = Spec(contract_id=f"{symbol}:{expiry}:demo-v1", symbol=symbol, expiry=expiry,
                        spec_version="demo-v1", quote_grams=grams, available_at="2026-08-01T00:00:00Z").model_dump(mode="json")
            specs.append(spec)
            for i, day in enumerate(days):
                per_gram = 7400 + i * 9 + 72 * math.sin(i / 4) + index * 11 + month * 32 + 12 * math.cos(i + index)
                row = {k: spec[k] for k in ("contract_id", "dataset", "symbol", "expiry", "spec_version", "currency", "unit", "source")}
                row.update(trading_date=day.isoformat(), price=round(per_gram * grams, 2),
                           volume=1600 + (i * 137 + index * 211 + month * 89) % 3500,
                           open_interest=8200 + index * 740 + month * 310 + i * 47,
                           observed_at=f"{day}T16:00:00Z", available_at=f"{day}T16:05:00Z")
                prices.append(validate_price(row, spec))
    return specs, prices


def seed(path=SYNTHETIC_DB):
    path = Path(path)
    if path.resolve() == REAL_DB.resolve():
        raise ValueError("Cannot seed synthetic fixtures into real storage")
    path.parent.mkdir(parents=True, exist_ok=True)
    specs, prices = fixtures()
    with connection(path) as db:
        db.executescript(SCHEMA)
        for table, records in (("specs", specs), ("prices", prices)):
            for row in records:
                keys = list(row)
                if table == "specs":
                    existing = db.execute("SELECT * FROM specs WHERE contract_id=?", (row["contract_id"],)).fetchone()
                else:
                    existing = db.execute("SELECT * FROM prices WHERE contract_id=? AND trading_date=?", (row["contract_id"], row["trading_date"])).fetchone()
                if existing:
                    if dict(existing) != row:
                        raise ValueError(f"Published {table} differ from generator v1; use a new version")
                    continue
                db.execute(f"INSERT INTO {table} ({','.join(keys)}) VALUES ({','.join('?' for _ in keys)})", tuple(row.values()))
    return len(specs), len(prices)


if __name__ == "__main__":
    specs, prices = seed()
    print(f"SYNTHETIC: {specs} specifications, {prices} observations -> {SYNTHETIC_DB}")
