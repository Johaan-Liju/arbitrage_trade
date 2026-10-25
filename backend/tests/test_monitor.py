"""Monitor integration coverage; all fixture prices and terms are invented."""
import csv
import io
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from backend.domain import DEFAULT_AS_OF
from backend.ingestion import CSV_COLUMNS, import_csv
from backend.main import create_app
from backend.synthetic_v4 import fixture_batch

A = "GOLDM:2026-11-20:demo-v4"


@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path / "s.sqlite3", tmp_path / "r.sqlite3")) as value:
        yield value


def get(client, **params):
    return client.get("/api/monitor", params={"as_of": DEFAULT_AS_OF, "contract_id": A, **params})


def test_monitor_values_provenance_changes_and_exact_spreads(client):
    response = get(client)
    assert response.status_code == 200
    data = response.json()
    assert data["dataset"] == "synthetic" and len(data["watchlist"]) == 8
    reference = data["selected"]
    assert reference["contract"]["contract_id"] == A
    latest, previous = data["prices"][-2:][::-1]
    assert Decimal(reference["change"]) == Decimal(latest["quoted_price_decimal"]) - Decimal(previous["quoted_price_decimal"])
    assert reference["change_pct"] == pytest.approx(float(Decimal(reference["change"]) / Decimal(previous["quoted_price_decimal"]) * 100))
    for row in data["watchlist"]:
        price = row["latest"]
        assert price["source"] and price["observed_at"] <= data["as_of"] and price["available_at"] <= data["as_of"]
        assert price["spec_version"] == row["contract"]["spec_version"]
        if row["spread"] is not None:
            assert row["contract"]["expiry"] == reference["contract"]["expiry"]
            assert Decimal(row["spread"]) == Decimal(price["normalized_999_inr_per_gram"]) - Decimal(latest["normalized_999_inr_per_gram"])
        if row["contract"]["expiry"] != reference["contract"]["expiry"]:
            assert row["spread"] is None and "expiry differs" in row["spread_reason"]


def test_missing_stale_and_dual_cutoffs(client):
    empty = get(client, as_of="2026-08-31T18:00:00Z").json()
    assert empty["selected"]["freshness"]["status"] == "MISSING" and empty["prices"] == []
    before = get(client, as_of="2026-09-01T16:04:59Z").json()
    after = get(client, as_of="2026-09-01T16:05:00Z").json()
    assert not before["prices"] and len(after["prices"]) == 1
    assert after["selected"]["change"] is None
    stale = get(client, as_of="2026-10-27T18:00:00Z").json()
    assert stale["selected"]["freshness"]["status"] == "STALE"
    assert all(r["spread"] is None for r in stale["watchlist"])
    assert stale["selected"]["freshness"]["age_hours"] > 72
    assert get(client, stale_after_hours=1).json()["selected"]["freshness"]["status"] == "STALE"


def test_monitor_fail_closed_and_validation(client):
    assert get(client, dataset="real").status_code == 404
    assert get(client, dataset="unknown").status_code == 404
    assert get(client, contract_id="GOLDM:2026-11:demo-v4").status_code == 404
    assert get(client, contract_id=A.replace("v4", "v5")).status_code == 404
    assert get(client, as_of="2026-10").status_code == 422
    assert client.get("/api/monitor").status_code == 422
    for limit in (0, 721, "NaN"):
        assert get(client, stale_after_hours=limit).status_code == 422


def test_spreads_withheld_for_misaligned_or_blocked_records(tmp_path):
    from backend.monitor import monitor_view
    from backend.research import research_snapshot
    from backend.synthetic_v4 import seed
    path = tmp_path / "s.sqlite3"
    seed(path)
    state = research_snapshot(path, "synthetic", DEFAULT_AS_OF)
    other = "GOLDTEN:2026-11-20:demo-v4"
    state["histories"][other].pop()
    result = monitor_view(state, A, 72)
    row = next(r for r in result["watchlist"] if r["contract"]["contract_id"] == other)
    assert row["freshness"]["status"] == "FRESH"
    assert row["spread"] is None and "trading dates differ" in row["spread_reason"]
    state["issues"].append({"contract_id": A, "trading_date": "2026-10-23", "code": "INVALID_RECORD", "reason": "Unusable latest source record"})
    blocked = monitor_view(state, A, 72)
    assert blocked["selected"]["freshness"]["status"] == "BLOCKED"
    assert all(r["spread"] is None for r in blocked["watchlist"])


def test_optional_liquidity_survives_ingestion_and_blocks_alerts(tmp_path, monkeypatch):
    content, manifest, registry = fixture_batch()
    rows = list(csv.DictReader(io.StringIO(content)))
    for row in rows:
        row["volume"] = row["open_interest"] = ""
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
    writer.writeheader(); writer.writerows(rows)
    path = tmp_path / "optional.sqlite3"
    result = import_csv(stream.getvalue(), manifest, registry, path)
    assert result["valid"]
    # This deliberately different invented batch is not the published demo seed.
    # Read its validated import without invoking the published seed integrity check.
    monkeypatch.setattr("backend.main.seed", lambda path: None)
    with TestClient(create_app(path, tmp_path / "real.sqlite3")) as client:
        data = get(client).json()
        assert data["selected"]["latest"]["volume"] is None
        assert data["selected"]["latest"]["open_interest"] is None
        assert data["selected"]["freshness"]["status"] == "FRESH"
        pair = client.post("/api/pair", json={"contract_a": A, "contract_b": "GOLDTEN:2026-11-20:demo-v4", "as_of": DEFAULT_AS_OF})
        assert pair.status_code == 200 and pair.json()["status"] == "Insufficient data"
        assert "did not supply volume/OI" in pair.json()["reason"]
