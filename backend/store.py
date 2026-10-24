"""Immutable specifications and observations; separate synthetic and real databases."""
from contextlib import contextmanager
from datetime import date, timedelta
import json
import math
from pathlib import Path
import sqlite3

from .domain import Spec, validate_price

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_DB = ROOT / "data" / "synthetic" / "goldlens-v3.sqlite3"
REAL_DB = ROOT / "data" / "real" / "goldlens.sqlite3"
SPEC_FIELDS = ("dataset", "symbol", "spec_version", "currency", "unit", "quote_grams", "lot_grams", "purity",
               "valid_from", "valid_to", "delivery_basis", "delivery_location", "expiry_rule",
               "delivery_restrictions", "evidence_url", "verification", "available_at", "source", "description")
SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments(symbol TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS contract_spec_versions (
 dataset TEXT NOT NULL CHECK(dataset IN ('synthetic','real')), symbol TEXT NOT NULL REFERENCES instruments(symbol),
 spec_version TEXT NOT NULL, currency TEXT NOT NULL CHECK(currency='INR'), unit TEXT NOT NULL CHECK(unit='quote'),
 quote_grams REAL NOT NULL CHECK(quote_grams>0), lot_grams INTEGER NOT NULL CHECK(lot_grams>0),
 purity REAL NOT NULL CHECK(purity>0 AND purity<=1), valid_from TEXT NOT NULL, valid_to TEXT NOT NULL,
 delivery_basis TEXT NOT NULL, delivery_location TEXT NOT NULL, expiry_rule TEXT NOT NULL,
 delivery_restrictions TEXT NOT NULL, evidence_url TEXT NOT NULL, verification TEXT NOT NULL,
 available_at TEXT NOT NULL, source TEXT NOT NULL, description TEXT NOT NULL,
 PRIMARY KEY(dataset,symbol,spec_version), CHECK(valid_from<=valid_to),
 CHECK((dataset='synthetic' AND verification='SYNTHETIC') OR (dataset='real' AND verification IN ('VERIFIED','UNVERIFIED')))
);
CREATE TABLE IF NOT EXISTS contracts (
 contract_id TEXT PRIMARY KEY, dataset TEXT NOT NULL, symbol TEXT NOT NULL,
 expiry TEXT NOT NULL, spec_version TEXT NOT NULL, tender_start TEXT NOT NULL, safe_exit_date TEXT NOT NULL,
 UNIQUE(dataset,symbol,expiry,spec_version),
 FOREIGN KEY(dataset,symbol,spec_version) REFERENCES contract_spec_versions(dataset,symbol,spec_version),
 CHECK(safe_exit_date<tender_start AND tender_start<=expiry)
);
CREATE VIEW IF NOT EXISTS specs AS SELECT c.contract_id,c.expiry,c.tender_start,c.safe_exit_date,s.*
 FROM contracts c JOIN contract_spec_versions s USING(dataset,symbol,spec_version);
CREATE TABLE IF NOT EXISTS daily_prices (
 contract_id TEXT NOT NULL REFERENCES contracts(contract_id), dataset TEXT NOT NULL,
 symbol TEXT NOT NULL, expiry TEXT NOT NULL, spec_version TEXT NOT NULL,
 trading_date TEXT NOT NULL, price REAL NOT NULL CHECK(price>0),
 open REAL NOT NULL CHECK(open>0), high REAL NOT NULL CHECK(high>0), low REAL NOT NULL CHECK(low>0), close REAL NOT NULL CHECK(close>0),
 volume INTEGER NOT NULL CHECK(volume>=0), open_interest INTEGER NOT NULL CHECK(open_interest>=0),
 currency TEXT NOT NULL, unit TEXT NOT NULL, source TEXT NOT NULL,
 observed_at TEXT NOT NULL, available_at TEXT NOT NULL, ingested_at TEXT NOT NULL,
 PRIMARY KEY(contract_id,trading_date), CHECK(available_at>=observed_at), CHECK(ingested_at>=available_at),
 CHECK(trading_date<=expiry), CHECK(low<=open AND low<=close AND high>=open AND high>=close)
);
CREATE VIEW IF NOT EXISTS prices AS SELECT * FROM daily_prices;
CREATE TABLE IF NOT EXISTS signals(signal_id TEXT PRIMARY KEY, dataset TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS backtest_runs(run_id TEXT PRIMARY KEY, dataset TEXT NOT NULL, payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS trades(run_id TEXT NOT NULL REFERENCES backtest_runs(run_id), trade_index INTEGER NOT NULL,
 payload TEXT NOT NULL, PRIMARY KEY(run_id,trade_index));
CREATE TRIGGER IF NOT EXISTS prices_identity BEFORE INSERT ON daily_prices
 WHEN NOT EXISTS(SELECT 1 FROM specs s WHERE s.contract_id=NEW.contract_id AND s.dataset=NEW.dataset
 AND s.symbol=NEW.symbol AND s.expiry=NEW.expiry AND s.spec_version=NEW.spec_version
 AND s.currency=NEW.currency AND s.unit=NEW.unit AND s.available_at<=NEW.available_at
 AND NEW.trading_date BETWEEN s.valid_from AND s.valid_to)
 BEGIN SELECT RAISE(ABORT,'Price identity does not match available specification'); END;
"""


@contextmanager
def connection(path=SYNTHETIC_DB):
    db = sqlite3.connect(path)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def insert(db, table, row):
    # Table names only from internal callers, never an API parameter.
    db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))


def initialize(db):
    db.executescript(SCHEMA)
    for table in ("contract_spec_versions", "contracts", "daily_prices"):
        for operation in ("UPDATE", "DELETE"):
            db.execute(f"CREATE TRIGGER IF NOT EXISTS {table}_no_{operation.lower()} BEFORE {operation} ON {table} "
                       "BEGIN SELECT RAISE(ABORT,'Published records are immutable'); END;")


def fixtures(anomaly=140):
    specs, prices = [], []
    contracts = [("GOLDM", 10, 100, .995, "2026-11-20", "2026-12-18"),
                 ("GOLDTEN", 10, 10, .999, "2026-11-24", "2026-12-22"),
                 ("GOLDGUINEA", 8, 8, .999, "2026-11-27", "2026-12-24"),
                 ("GOLDPETAL", 1, 1, .999, "2026-11-30", "2026-12-28")]
    days = [date(2026, 9, 1) + timedelta(days=i) for i in range(53)]
    days = [d for d in days if d.weekday() < 5]  # Invented calendar, NOT MCX holidays.
    for index, (symbol, grams, lot, purity, *expiries) in enumerate(contracts):
        for month, expiry in enumerate(expiries):
            exp = date.fromisoformat(expiry)
            spec = Spec(contract_id=f"{symbol}:{expiry}:demo-v3", symbol=symbol, expiry=expiry,
                        spec_version="demo-v3", quote_grams=grams, lot_grams=lot, purity=purity,
                        valid_from="2026-08-01", valid_to="2026-12-31", verification="SYNTHETIC",
                        delivery_basis="Invented ex-location basis; taxes and premia unresolved",
                        delivery_location="Demo Mumbai" if symbol == "GOLDPETAL" else "Demo Ahmedabad",
                        expiry_rule="Explicit invented expiry; never inferred from month",
                        delivery_restrictions="Invented tender window; no delivery simulation",
                        tender_start=exp-timedelta(days=4), safe_exit_date=exp-timedelta(days=7),
                        evidence_url="synthetic://goldlens/demo-v3", available_at="2026-08-01T00:00:00Z",
                        source="GoldLens deterministic generator v3").model_dump(mode="json")
            specs.append(spec)
            for i, day in enumerate(days):
                per_gram = 7400 + i*9 + 72*math.sin(i/4) + index*11 + month*32 + 12*math.cos(i+index)
                if symbol == "GOLDTEN" and i in (24, 25, 38):
                    per_gram += anomaly  # Deliberate, disclosed anomaly for demo gates.
                quoted = round(per_gram * grams * purity / .999, 2)
                row = {k: spec[k] for k in ("contract_id", "dataset", "symbol", "expiry", "spec_version", "currency", "unit", "source")}
                row.update(trading_date=day.isoformat(), price=quoted, open=quoted, close=quoted,
                           high=round(quoted*1.002, 2), low=round(quoted*.998, 2),
                           volume=1600+(i*137+index*211+month*89)%3500,
                           open_interest=8200+index*740+month*310+i*47,
                           observed_at=f"{day}T16:00:00Z", available_at=f"{day}T16:05:00Z", ingested_at=f"{day}T16:05:00Z")
                prices.append(validate_price(row, spec))
    return specs, prices


def seed(path=SYNTHETIC_DB):
    path = Path(path)
    if path.resolve() == REAL_DB.resolve() or "real" in path.parts:
        raise ValueError("Cannot seed synthetic fixtures into real storage")
    path.parent.mkdir(parents=True, exist_ok=True)
    specs, prices = fixtures()
    with connection(path) as db:
        initialize(db)
        for spec in specs:
            db.execute("INSERT OR IGNORE INTO instruments VALUES (?)", (spec["symbol"],))
            terms = {k: spec[k] for k in SPEC_FIELDS}
            existing = db.execute("SELECT * FROM contract_spec_versions WHERE dataset=? AND symbol=? AND spec_version=?",
                                  (spec["dataset"],spec["symbol"],spec["spec_version"])).fetchone()
            if existing and dict(existing) != terms:
                raise ValueError("Published specifications differ; create a new version")
            if not existing:
                insert(db, "contract_spec_versions", terms)
            contract = {k: spec[k] for k in ("contract_id","dataset","symbol","expiry","spec_version","tender_start","safe_exit_date")}
            existing = db.execute("SELECT * FROM contracts WHERE contract_id=?", (spec["contract_id"],)).fetchone()
            if existing and dict(existing) != contract:
                raise ValueError("Published contracts differ; create a new version")
            if not existing:
                insert(db, "contracts", contract)
        for row in prices:
            existing = db.execute("SELECT * FROM prices WHERE contract_id=? AND trading_date=?", (row["contract_id"],row["trading_date"])).fetchone()
            if existing and dict(existing) != row:
                raise ValueError("Published prices differ; create a new dataset version")
            if not existing:
                insert(db, "daily_prices", row)
    return len(specs), len(prices)


def save_run(db, run):
    db.execute("INSERT OR IGNORE INTO backtest_runs VALUES (?,?,?)", (run["run_id"],run["dataset"],json.dumps(run,sort_keys=True)))
    for i, trade in enumerate(run["trades"]):
        db.execute("INSERT OR IGNORE INTO trades VALUES (?,?,?)", (run["run_id"],i,json.dumps(trade,sort_keys=True)))


if __name__ == "__main__":
    specs, prices = seed()
    print(f"SYNTHETIC: {specs} contracts, {prices} observations -> {SYNTHETIC_DB}")
