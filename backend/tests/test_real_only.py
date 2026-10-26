"""Production defaults must never serve or generate synthetic market data."""
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.synthetic_v4 import fixture_batch


def test_real_only_startup_and_missing_data(tmp_path):
    synthetic = tmp_path / "synthetic.sqlite3"
    real = tmp_path / "real.sqlite3"
    with TestClient(create_app(synthetic, real)) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["datasets"] == {"real": "empty"}
        missing = client.get("/api/contracts")
        assert missing.status_code == 200
        assert missing.json()["contracts"] == []
        for endpoint in ("contracts", "alerts/catalog", "alerts/sessions"):
            assert client.get(f"/api/{endpoint}?dataset=synthetic").status_code == 422
    assert not synthetic.exists()
    assert not real.exists()


def test_synthetic_ingestion_rejected_even_for_dry_run(tmp_path):
    content, manifest, registry = fixture_batch()
    with TestClient(create_app(tmp_path / "s.sqlite3", tmp_path / "r.sqlite3")) as client:
        response = client.post("/api/ingest", json={"csv_text": content,
            "manifest": manifest.model_dump(mode="json"), "registry": registry.model_dump(mode="json"),
            "dry_run": True})
        assert response.status_code == 422
