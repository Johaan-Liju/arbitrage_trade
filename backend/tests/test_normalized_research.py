"""Active v4 API tests. All fixtures, including rejected real candidates, are invented."""
import csv
import io
import json
import sqlite3
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.domain import DEFAULT_AS_OF
from backend.main import create_app
from backend.ingestion import CSV_COLUMNS, import_csv, persist_catalog, validate_csv
from backend.normalization import normalize_observation
from backend.reference import ReferenceRegistry, ReferenceFailure, normalize_999
from backend.research import research_snapshot
from backend.synthetic_v4 import fixture_batch, seed

A = "GOLDM:2026-11-20:demo-v4"
B = "GOLDTEN:2026-11-20:demo-v4"


def write_csv(rows):
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


@pytest.fixture
def batch():
    return fixture_batch()


@pytest.fixture
def app(tmp_path):
    path = tmp_path / "synthetic.sqlite3"
    with TestClient(create_app(path, tmp_path / "real.sqlite3")) as client:
        yield client, path


def get(client, **changes):
    return client.get("/api/research", params={"contract_id": A, "as_of": DEFAULT_AS_OF, **changes})


def test_decimal_normalization_quote_not_lot(batch):
    _, _, registry = batch
    spec = registry.spec("GOLDM:demo-v4")
    assert normalize_999(Decimal("74625"), spec, "2026-10-23", DEFAULT_AS_OF) == Decimal("7492.5")
    changed_lot = spec.model_copy(update={"lot_size_grams": Decimal("10000")})
    assert normalize_999(Decimal("74625"), changed_lot, "2026-10-23", DEFAULT_AS_OF) == Decimal("7492.5")
    precise = Decimal("74625.12345678")
    assert normalize_999(precise, spec, "2026-10-23", DEFAULT_AS_OF) == precise / Decimal(10) * Decimal(999) / Decimal(995)


@pytest.mark.parametrize("field", ["quotation_grams", "quote_purity_per_mille", "lot_size_grams", "settlement_method", "settlement_terms", "delivery_restrictions", "effective_date"])
def test_missing_terms_block_entire_import(batch, field):
    content, manifest, registry = batch
    specs = list(registry.specs)
    specs[0] = specs[0].model_copy(update={field: None})
    result = validate_csv(content, manifest, registry.model_copy(update={"specs": tuple(specs)}))
    assert not result["valid"] and not result["rows"]
    assert any(i["code"] == "UNVERIFIED_SPEC" for i in result["issues"])


def test_unverified_real_and_cross_dataset_fail_closed(batch, tmp_path):
    content, manifest, registry = batch
    real = registry.specs[0].model_copy(update={"dataset": "real", "verification_status": "UNVERIFIED"})
    with pytest.raises(ReferenceFailure, match="not approved"):
        normalize_999(Decimal(74625), real, "2026-10-23", DEFAULT_AS_OF)
    with TestClient(create_app(tmp_path / "s.sqlite3", tmp_path / "r.sqlite3")) as client:
        assert get(client, dataset="real").status_code == 404
        assert not (tmp_path / "r.sqlite3").exists()
        assert get(client, dataset="unknown").status_code == 404
    with pytest.raises(ReferenceFailure, match="reserved"):
        from backend.synthetic_v4 import REAL_DB
        import_csv(content, manifest, registry, REAL_DB)


def test_api_exact_pairs_unmatched_and_decimal_provenance(app):
    client, _ = app
    body = get(client).json()
    assert body["dataset"] == "synthetic" and body["label"] == "SYNTHETIC"
    assert len(body["prices"]) == 39
    assert len(body["pairing"]["matches"]) == 3
    assert len(body["pairing"]["unmatched"]) == 4
    assert all(p["expiry"] == "2026-11-20" for p in body["pairing"]["matches"])
    petal = next(p for p in body["pairing"]["matches"] if "GOLDPETAL" in p["contract_b"])
    assert {d["field"] for d in petal["basis_differences"]} >= {"delivery_locations", "settlement_terms"}
    for row in body["prices"]:
        expected = Decimal(row["quoted_price_decimal"]) / Decimal(10) * Decimal(999) / Decimal(995)
        assert Decimal(row["normalized_999_inr_per_gram"]) == expected
        assert row["spec_id"] == "GOLDM:demo-v4"
        assert row["observed_at"] <= row["available_at"] <= row["normalized_available_at"] <= body["as_of"]
    unmatched = get(client, contract_id="GOLDM:2026-12-18:demo-v4").json()["pairing"]
    assert unmatched["matches"] == [] and len(unmatched["unmatched"]) == 7


def test_pair_endpoint_enforces_expiry_even_when_calendar_opted_in(app):
    client, _ = app
    req = {"contract_a": A, "contract_b": B, "as_of": DEFAULT_AS_OF}
    pair = client.post("/api/pair", json=req)
    assert pair.status_code == 200 and pair.json()["alignment"] == "EXACT_EXPIRY"
    first = pair.json()["history"][0]
    assert Decimal(first["raw_pair_spread_decimal"]) == Decimal(first["a"]["normalized_999_inr_per_gram"]) - Decimal(first["b"]["normalized_999_inr_per_gram"])
    bad = {**req, "contract_b": "GOLDTEN:2026-12-22:demo-v4"}
    assert client.post("/api/pair", json=bad).status_code == 422
    assert client.post("/api/backtest", json={**bad, "allow_calendar": True}).status_code == 422
    run = client.post("/api/backtest", json={**req, "contract_a": B, "contract_b": "GOLDGUINEA:2026-11-20:demo-v4"})
    assert run.status_code == 200 and run.json()["alignment"] == "EXACT_EXPIRY"


@pytest.mark.parametrize("as_of,count", [("2026-08-31T18:00:00Z", 0), ("2026-09-01T16:04:59Z", 0), ("2026-09-01T16:05:00Z", 1)])
def test_observed_and_available_cutoffs(app, as_of, count):
    client, _ = app
    assert len(get(client, as_of=as_of).json()["prices"]) == count
    assert client.get("/api/research", params={"contract_id": A}).status_code == 422


def test_versions_are_immutable_and_partitioned_at_reference_availability(app, batch):
    client, path = app
    content, manifest, registry = batch
    before = get(client).json()
    values = registry.model_dump(mode="json")
    # Another explicitly invented spec version for the SAME instrument and expiry.
    for spec in values["specs"]:
        spec["spec_id"] = spec["spec_id"].replace("v4", "v5")
        spec["version"] = "demo-v5"
        spec["available_at"] = "2026-10-24T00:00:00Z"
        spec["quotation_grams"] = "20"
    for listing in values["contracts"]:
        listing["spec_id"] = listing["spec_id"].replace("v4", "v5")
    newer = ReferenceRegistry.model_validate(values)
    rows = list(csv.DictReader(io.StringIO(content)))
    for row in rows:
        row["spec_id"] = row["spec_id"].replace("v4", "v5")
        row["quotation_grams"] = "20"
    updated = manifest.model_dump(mode="json")
    updated["as_of"] = "2026-10-25T18:00:00Z"
    updated["min_normalized_inr_per_gram"] = "100"
    for item in updated["expected_contracts"]:
        item["spec_id"] = item["spec_id"].replace("v4", "v5")
    from backend.ingestion import ImportManifest
    result = import_csv(write_csv(rows), ImportManifest.model_validate(updated), newer, path)
    assert result["valid"]
    assert get(client).json() == before
    assert get(client, contract_id=A.replace("v4", "v5")).status_code == 404
    later = get(client, contract_id=A.replace("v4", "v5"), as_of=updated["as_of"]).json()
    assert len(later["prices"]) == 39
    assert all(r["spec_version"] == "demo-v5" for r in later["prices"])
    assert all(r["normalized_available_at"] == "2026-10-24T00:00:00Z" for r in later["prices"])
    assert all(e["decision_at"] >= "2026-10-24T00:00:00Z" for e in later["backtest"]["events"])
    with sqlite3.connect(path) as db:
        for table in ("reference_versions", "observations"):
            with pytest.raises(sqlite3.IntegrityError, match="immutable"):
                db.execute(f"DELETE FROM {table}")
    with pytest.raises(ReferenceFailure, match="changed"):
        persist_catalog(registry.model_copy(update={"specs": (registry.specs[0].model_copy(update={"quotation_grams": Decimal(99)}), *registry.specs[1:])}), path)


def test_missing_leg_no_fill_and_no_latest_gap(app):
    client, path = app
    # Simulate a dataset missing a daily publication, in an isolated test database.
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER observation_no_delete")
        db.execute("DELETE FROM observations WHERE instrument='GOLDTEN' AND expiry='2026-11-20' AND trading_date='2026-10-23'")
    match = next(m for m in get(client).json()["pairing"]["matches"] if m["contract_b"] == B)
    assert match["status"] == "INSUFFICIENT_DATA" and match["latest_spread_999_inr_per_gram"] is None
    pair = client.post("/api/pair", json={"contract_a": A, "contract_b": B, "as_of": DEFAULT_AS_OF}).json()
    assert len(pair["history"]) == 38 and pair["quality"]["missing_dates"]
    assert pair["status"] == "Insufficient data" and pair["latest"]["raw_pair_spread"] is None


def test_pair_api_settings_and_retired_percentage_signals(app):
    client, _ = app
    req = {"contract_a": A, "contract_b": B, "as_of": DEFAULT_AS_OF}
    for settings in ({"lookback": 1}, {"lookback": 251}, {"lookback": 2.5},
                     {"lookback": 3, "min_observations": 4}, {"entry_z": 0}, {"entry_z": 101}):
        assert client.post("/api/pair", json={**req, **settings}).status_code == 422
    body = client.post("/api/pair", json={**req, "lookback": 7, "min_observations": 3, "entry_z": 1.5}).json()
    assert body["method"]["lookback"] == 7 and body["method"]["ddof"] == 1
    assert body["method"]["entry_z"] == 1.5 and body["latest"]["sample_count"] == 7
    assert {e["status"] for e in body["history"]} <= {"Investigate", "No signal", "Insufficient data"}
    assert get(client).json()["backtest"]["events"] == []


def test_unusable_latest_reference_returns_reason_instead_of_old_signal(app):
    client, path = app
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER observation_no_update")
        where = "instrument='GOLDM' AND expiry='2026-11-20' AND trading_date='2026-10-23'"
        row = json.loads(db.execute(f"SELECT payload FROM observations WHERE {where}").fetchone()[0])
        row["quotation_grams"] = "100"
        db.execute(f"UPDATE observations SET payload=? WHERE {where}", (json.dumps(row),))
    body = client.post("/api/pair", json={"contract_a": A, "contract_b": B, "as_of": DEFAULT_AS_OF}).json()
    assert body["status"] == "Insufficient data" and "UNIT_MISMATCH" in body["reason"]
    assert body["latest"]["z_score"] is None and body["latest"]["raw_pair_spread"] is None


def test_read_recomputes_normalization_and_blocks_invalid_stored_units(app):
    client, path = app
    before = get(client).json()["prices"][0]
    with sqlite3.connect(path) as db:
        db.execute("DROP TRIGGER observation_no_update")
        where = "instrument='GOLDM' AND expiry='2026-11-20' AND trading_date='2026-09-01'"
        row = json.loads(db.execute(f"SELECT payload FROM observations WHERE {where}").fetchone()[0])
        row["normalized_999_inr_per_gram"] = "999999999999"
        db.execute(f"UPDATE observations SET payload=? WHERE {where}", (json.dumps(row),))
    assert get(client).json()["prices"][0]["normalized_999_inr_per_gram"] == before["normalized_999_inr_per_gram"]
    with sqlite3.connect(path) as db:
        row["quotation_grams"] = "100"
        db.execute(f"UPDATE observations SET payload=? WHERE {where}", (json.dumps(row),))
    body = get(client).json()
    assert len(body["prices"]) == 38
    assert any(i["code"] == "UNIT_MISMATCH" for i in body["issues"])


def test_atomic_import_validation_and_seed_idempotence(batch, tmp_path):
    content, manifest, registry = batch
    path = tmp_path / "demo.sqlite3"
    rows = list(csv.DictReader(io.StringIO(content)))
    rows[-1]["expiry"] = "2026-12"
    result = import_csv(write_csv(rows), manifest, registry, path)
    assert not result["valid"] and not path.exists()
    assert import_csv(content, manifest, registry, path)["valid"]
    assert not import_csv(content, manifest, registry, path)["valid"]
    seed(path)
    assert len(research_snapshot(path, "synthetic", DEFAULT_AS_OF)["histories"][A]) == 39


def test_future_calendar_and_holiday_block_rows(batch):
    content, manifest, registry = batch
    raw = next(csv.DictReader(io.StringIO(content)))
    future = registry.calendars[0].model_copy(update={"available_at": "2026-10-24T00:00:00Z"})
    with pytest.raises(ReferenceFailure, match="not available"):
        normalize_observation(raw, registry.model_copy(update={"calendars": (future,)}), future.calendar_id, DEFAULT_AS_OF)
    with pytest.raises(ReferenceFailure, match="Currency"):
        normalize_observation({**raw, "currency": "USD"}, registry, manifest.calendar_id, DEFAULT_AS_OF)
    with pytest.raises(ReferenceFailure, match="dataset"):
        normalize_observation({**raw, "dataset": "real"}, registry, manifest.calendar_id, DEFAULT_AS_OF)
