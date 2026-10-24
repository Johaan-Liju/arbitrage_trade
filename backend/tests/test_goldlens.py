import sqlite3

from fastapi.testclient import TestClient
import pytest

from backend.domain import DEFAULT_AS_OF, validate_price, normalize
from backend.main import create_app
from backend.store import connection, fixtures, seed, REAL_DB, SPEC_FIELDS

CONTRACT = "GOLDM:2026-11-20:demo-v3"


@pytest.fixture
def app_client(tmp_path):
    path = tmp_path / "synthetic.sqlite3"
    with TestClient(create_app(path)) as client:
        yield client, path


def research(client, **changes):
    params = {"contract_id": CONTRACT, "as_of": DEFAULT_AS_OF, **changes}
    return client.get("/api/research", params=params)


def insert(db, table, row):
    if table == "specs":
        insert(db, "contract_spec_versions", {k: row[k] for k in SPEC_FIELDS})
        insert(db, "contracts", {k: row[k] for k in ("contract_id","dataset","symbol","expiry","spec_version","tender_start","safe_exit_date")})
        return
    if table == "prices":
        table = "daily_prices"
    db.execute(f"INSERT INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))


def test_deterministic_seed_and_separation(tmp_path):
    assert fixtures() == fixtures()
    path = tmp_path / "synthetic.sqlite3"
    assert seed(path) == (8, 312)
    assert seed(path) == (8, 312)
    with connection(path) as db:
        assert db.execute("SELECT count(*) FROM prices").fetchone()[0] == 312
        assert db.execute("SELECT DISTINCT dataset FROM prices").fetchone()[0] == "synthetic"
    with pytest.raises(ValueError, match="real storage"):
        seed(REAL_DB)


@pytest.mark.parametrize("field", ["trading_date", "symbol", "expiry", "spec_version", "currency", "unit", "source", "observed_at", "available_at"])
def test_missing_required_price_fields(field):
    specs, rows = fixtures()
    row = rows[0].copy()
    del row[field]
    with pytest.raises(ValueError):
        validate_price(row, specs[0])


@pytest.mark.parametrize("change", [
    {"expiry": "2026-11"}, {"trading_date": "2026-02-30"}, {"trading_date": "2027-01-01"},
    {"price": float("nan")}, {"price": -1}, {"volume": -1}, {"open_interest": 1.5},
    {"currency": "USD"}, {"spec_version": "other"}, {"dataset": "real"},
    {"available_at": "2026-08-01T00:00:00Z"}, {"observed_at": "2026-09-01"},
])
def test_invalid_prices(change):
    specs, rows = fixtures()
    with pytest.raises(ValueError):
        validate_price({**rows[0], **change}, specs[0])


def test_specs_are_immutable_and_identity_is_enforced(app_client):
    _, path = app_client
    with connection(path) as db:
        for statement in ["UPDATE contract_spec_versions SET quote_grams=999", "DELETE FROM contract_spec_versions"]:
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(statement)
        row = dict(db.execute("SELECT * FROM prices LIMIT 1").fetchone())
        row.update(trading_date="2026-08-31", symbol="WRONG")
        with pytest.raises(sqlite3.IntegrityError, match="identity"):
            insert(db, "prices", row)


def test_health_catalog_and_no_real_fallback(app_client):
    client, _ = app_client
    assert client.get("/api/health").json()["observations"] == 312
    catalog = client.get("/api/contracts").json()
    assert catalog["label"] == "SYNTHETIC"
    assert len(catalog["contracts"]) == 8
    assert {s["symbol"] for s in catalog["contracts"]} == {"GOLDM", "GOLDTEN", "GOLDGUINEA", "GOLDPETAL"}
    assert client.get("/api/contracts", params={"dataset": "real"}).status_code == 404
    assert research(client, dataset="real").status_code == 404
    assert research(client, contract_id="missing").status_code == 404
    assert client.get("/api/research", params={"contract_id": CONTRACT}).status_code == 422
    assert client.post("/api/research").status_code == 405


@pytest.mark.parametrize("cutoff,code,count", [
    ("invalid", 422, None), ("2026-02-30T00:00:00Z", 422, None),
    ("2026-07-31T00:00:00Z", 404, None), ("2026-08-31T18:00:00Z", 200, 0),
    ("2026-09-01T15:59:59Z", 200, 0), ("2026-09-01T16:04:59Z", 200, 0),
    ("2026-09-01T16:05:00Z", 200, 1), (DEFAULT_AS_OF, 200, 39),
])
def test_information_cutoff(app_client, cutoff, code, count):
    client, _ = app_client
    response = research(client, as_of=cutoff)
    assert response.status_code == code
    if code == 200:
        body = response.json()
        assert body["metrics"]["count"] == count
        for row in body["prices"]:
            assert row["observed_at"] <= cutoff and row["available_at"] <= cutoff
        if count == 0:
            assert body["latest"] is None
            assert body["metrics"]["mean_5"] is None
            assert body["backtest"]["events"] == []


def test_server_metrics_and_normalization(app_client):
    client, _ = app_client
    body = research(client).json()
    assert body["metrics"]["mean_5"] == round(sum(r["price"] for r in body["prices"][-5:]) / 5, 2)
    assert len(body["compare"]) == 8
    for row in body["compare"]:
        assert row["price_per_gram"] == round(row["price"] / row["quote_grams"] * .999 / row["purity"], 2)
    own = next(row for row in body["compare"] if row["contract_id"] == CONTRACT)
    assert own["gap_pct"] == 0
    events = body["backtest"]["events"]
    assert all(e["state"] == "Warming up" for e in events[:5])
    assert events[5]["baseline"] == round(sum(r["price"] for r in body["prices"][:5]) / 5, 2)
    assert sum(body["backtest"]["counts"].values()) == 39


def test_late_arrival_never_rewrites_earlier_decisions(app_client):
    client, path = app_client
    before = research(client).json()
    with connection(path) as db:
        row = dict(db.execute("SELECT * FROM prices WHERE contract_id=? ORDER BY trading_date LIMIT 1", (CONTRACT,)).fetchone())
        row.update(trading_date="2026-08-31", observed_at="2026-08-31T16:00:00Z", available_at="2026-10-24T16:05:00Z", ingested_at="2026-10-24T16:05:00Z", price=999999)
        insert(db, "prices", row)
    assert research(client).json() == before
    later = research(client, as_of="2026-10-25T18:00:00Z").json()
    assert later["metrics"]["count"] == 40
    old_events = {r["trading_date"]: r for r in before["backtest"]["events"]}
    for event in later["backtest"]["events"]:
        if event["trading_date"] in old_events:
            assert event == old_events[event["trading_date"]]


def test_version_partition_and_point_in_time_spec(app_client):
    client, path = app_client
    before = research(client).json()
    with connection(path) as db:
        spec = dict(db.execute("SELECT * FROM specs WHERE contract_id=?", (CONTRACT,)).fetchone())
        spec.update(contract_id="GOLDM:2026-11-20:demo-v4", spec_version="demo-v4", available_at="2026-10-24T00:00:00Z")
        insert(db, "specs", spec)
        row = dict(db.execute("SELECT * FROM prices WHERE contract_id=? LIMIT 1", (CONTRACT,)).fetchone())
        row.update(contract_id=spec["contract_id"], spec_version="demo-v4", trading_date="2026-10-24", observed_at="2026-10-24T16:00:00Z", available_at="2026-10-24T16:05:00Z", ingested_at="2026-10-24T16:05:00Z", price=888888)
        insert(db, "prices", row)
    assert research(client).json() == before
    assert research(client, contract_id=spec["contract_id"]).status_code == 404
    later = research(client, contract_id=spec["contract_id"], as_of="2026-10-25T18:00:00Z").json()
    assert later["metrics"]["count"] == 1
    assert later["backtest"]["events"][0]["baseline"] is None
    assert later["backtest"]["events"][0]["spec_version"] == "demo-v4"


def test_contract_partition(app_client):
    client, _ = app_client
    for contract in client.get("/api/contracts").json()["contracts"]:
        body = research(client, contract_id=contract["contract_id"]).json()
        assert len(body["prices"]) == 39
        for row in body["prices"]:
            for key in ("dataset", "symbol", "expiry", "spec_version", "contract_id"):
                assert row[key] == contract[key]
