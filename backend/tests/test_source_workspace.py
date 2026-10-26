"""Invented source snapshots isolated under pytest temporary directories."""
import json
import pytest
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.public_sources import extract
from backend.tests.test_public_sources import page

AS_OF = "2026-10-26T15:00:00Z"


@pytest.fixture
def client(tmp_path):
    root = tmp_path / "sources"
    (root / "GOLDM").mkdir(parents=True)
    value = extract(page(), "GOLDM", "2026-10-26T14:00:00Z")
    (root / "GOLDM/one.json").write_text(json.dumps(value))
    with TestClient(create_app(tmp_path / "synthetic.sqlite3", tmp_path / "real.sqlite3",
                               tmp_path / "notifications", source_root=root)) as api:
        yield api


def test_source_quotes_power_existing_monitor_and_research(client):
    catalog = client.get("/api/contracts", params={"as_of": AS_OF})
    assert catalog.status_code == 200
    contract = catalog.json()["contracts"][0]
    params = {"as_of": AS_OF, "contract_id": contract["contract_id"]}
    monitor = client.get("/api/monitor", params=params)
    assert monitor.status_code == 200
    body = monitor.json()
    assert body["selected"]["latest"]["price"] == 140453
    assert body["selected"]["latest"]["normalized_999_per_g"] is None
    assert body["selected"]["freshness"]["status"] == "STALE"
    assert len(body["prices"]) == 1
    assert body["data_mode"] == "source_quotes"
    assert not body["model_ready"]
    result = client.get("/api/research", params=params)
    assert result.status_code == 200
    assert result.json()["metrics"]["mean_5"] == 140453
    assert client.get("/api/contracts?as_of=2026-10-23T18:00:00Z").json()["contracts"] == []


def test_real_alert_session_scan_history_and_dedup(client):
    catalog = client.get("/api/alerts/catalog", params={"as_of": AS_OF})
    assert catalog.status_code == 200
    assert catalog.json()["model_evaluated"] is False
    created = client.post("/api/alerts/sessions", json={"dataset": "real"})
    assert created.status_code == 200
    identifier = created.json()["id"]
    request = {"dataset": "real", "session_id": identifier, "as_of": AS_OF}
    response = client.post("/api/alerts/scan", json=request)
    assert response.status_code == 200
    scan = response.json()
    assert scan["observations_reviewed"] == 1
    assert scan["input_status"] == "UNVERIFIED"
    assert not scan["signal_eligible"] and scan["new_alert_ids"] == []
    assert client.post("/api/alerts/scan", json=request).json()["repeated_scan"]
    history = client.get("/api/alerts/history", params=request)
    assert history.status_code == 200
    assert history.json()["last_scan"]["reason"].startswith("MODEL_NOT_EVALUATED")
    earlier = {**request, "as_of": "2026-10-26T14:00:00Z"}
    assert client.post("/api/alerts/scan", json=earlier).status_code == 409


def test_corrupt_validated_database_never_falls_back_to_source_quotes(client, tmp_path):
    (tmp_path / "real.sqlite3").write_text("broken database")
    assert client.get("/api/contracts", params={"as_of": AS_OF}).status_code == 409
