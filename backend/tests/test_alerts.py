"""Paper alert lifecycle, cutoff isolation and fail-closed data gates."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from backend import alerts
from backend.main import create_app
from backend.reference import ReferenceFailure
from backend.synthetic_v4 import seed


@pytest.fixture
def env(tmp_path):
    source = tmp_path / "synthetic" / "source.sqlite3"
    seed(source)
    root = tmp_path / "notifications"
    return source, root


def session(env, **settings):
    return alerts.new_session(*env, alerts.NewSession(dataset="synthetic", settings=settings))


def scan(env, saved, at):
    return alerts.scan(*env, alerts.ScanRequest(dataset="synthetic", session_id=saved["id"], as_of=at))


def history(env, saved, at):
    return alerts.history(env[1], "synthetic", saved["id"], at)


def mutate(monkeypatch, day, change, symbol="GOLDTEN"):
    original = alerts.snapshot

    def changed(*args):
        registry, raw = original(*args)
        raw = deepcopy(raw)
        for row in raw:
            if (row["instrument"], row["expiry"], row["trading_date"]) == (symbol, "2026-11-20", day):
                row.update(change)
        return registry, raw

    monkeypatch.setattr(alerts, "snapshot", changed)


def test_default_model_abstention_and_evaluation_scope(env):
    before = sha256(env[0].read_bytes()).hexdigest()
    saved = session(env)
    result = scan(env, saved, "2026-10-05T18:00:00Z")
    assert result["status"] == "SUPPRESSED" and result["reason"].startswith("COST_FILTER")
    assert history(env, saved, result["as_of"])["alerts"] == []
    catalog = alerts.catalog(env[0], "synthetic", result["as_of"])
    assert catalog["calibration"] == {"evaluated": False, "probability": None,
                                      "reason": "Deterministic scores; probability calibration has not been evaluated"}
    assert catalog["evaluation"]["metrics"]["model"]["alerts"] == 0
    assert catalog["evaluation"]["metrics"]["baseline"]["alerts"] == 1
    assert before == sha256(env[0].read_bytes()).hexdigest()


def test_signal_identity_support_costs_and_no_future_labels(env):
    saved = session(env, policy="baseline")
    result = scan(env, saved, "2026-10-05T18:00:00Z")
    assert len(result["new_alert_ids"]) == 1 and result["prediction"]["outcome"] is None
    alert = history(env, saved, result["as_of"])["alerts"][0]
    assert alert["status"] == "ACTIVE" and alert["outcome"]["status"] == "PENDING_ENTRY"
    assert alert["signal_at"] == result["as_of"] and alert["model_version"] == "opportunity-v1"
    assert alert["horizon"]["entry"] == "2026-10-06" and alert["horizon"]["exit"] == "2026-10-13"
    assert alert["horizon"]["holding_sessions"] == 5
    assert len(alert["observations"]) == 22
    for row in alert["observations"]:
        assert row["observed_at"] <= row["available_at"] <= alert["signal_at"]
        assert row["expiry"] == "2026-11-20" and row["spec_version"] == "demo-v4"
        assert all(row[k] for k in ("currency", "price_unit", "source_url", "spec_id", "contract_id"))
    assert alert["probability"] is None and not alert["calibration_evaluated"]
    assert alert["liquidity_uncertainty"] and alert["settlement_uncertainty"]
    for scenario in alert["record"]["forecast"]["estimated_package"]["scenarios"].values():
        assert len(scenario["items"]) == 4 and float(scenario["cost_inr"]) > 0
    assert history(env, saved, "2026-10-05T17:59:59Z")["alerts"] == []


def test_dedup_cooldown_expiry_and_persistence(env):
    saved = session(env, policy="baseline", cooldown_hours=48, expires_hours=1)
    first = scan(env, saved, "2026-10-05T18:00:00Z")
    repeated = scan(env, saved, "2026-10-05T18:00:00Z")
    assert repeated["repeated_scan"] and not repeated["new_alert_ids"]
    assert scan(env, saved, "2026-10-05T18:01:00Z")["reason"].startswith("DEDUPLICATED")
    assert history(env, saved, "2026-10-05T19:00:00Z")["alerts"][0]["status"] == "EXPIRED"
    assert scan(env, saved, "2026-10-06T18:00:00Z")["reason"].startswith("COOLDOWN")
    assert alerts.sessions(env[1], "synthetic")["sessions"][0]["settings"]["cooldown_hours"] == 48
    assert len(history(env, saved, "2026-10-06T18:00:00Z")["alerts"]) == 1
    alerts.mark_read(env[1], "synthetic", saved["id"], first["new_alert_ids"][0])
    alerts.mark_read(env[1], "synthetic", saved["id"], first["new_alert_ids"][0])
    assert history(env, saved, "2026-10-06T18:00:00Z")["unread_count"] == 0
    with pytest.raises(ReferenceFailure, match="Advance the cutoff"):
        scan(env, saved, "2026-10-05T18:00:00Z")


def test_cooldown_boundary_and_separate_immutable_settings(env):
    saved = session(env, policy="baseline", cooldown_hours=24)
    scan(env, saved, "2026-10-05T18:00:00Z")
    assert scan(env, saved, "2026-10-06T18:00:00Z")["new_alert_ids"]
    stricter = session(env, policy="baseline", min_abs_z="100")
    assert scan(env, stricter, "2026-10-05T18:00:00Z")["reason"].startswith("THRESHOLD")
    assert history(env, saved, "2026-10-06T18:00:00Z")["session"]["settings"]["min_abs_z"] == "2.5"


def test_outcome_maturation_journal_and_historical_cutoff(env):
    saved = session(env, policy="baseline", cooldown_hours=720)
    scan(env, saved, "2026-10-05T18:00:00Z")
    scan(env, saved, "2026-10-13T16:04:59Z")
    early = history(env, saved, "2026-10-13T16:04:59Z")["alerts"][0]
    assert early["outcome"]["status"] == "PENDING_EXIT" and early["outcome"]["label"] is None
    scan(env, saved, "2026-10-13T16:05:00Z")
    final = history(env, saved, "2026-10-13T16:05:00Z")["alerts"][0]
    assert final["outcome"]["status"] == "COMPLETE"
    assert final["outcome"]["label"] == "COST_SENSITIVE_POSITIVE"
    assert float(final["outcome"]["scenarios"]["BASE"]["net_inr"]) > 0
    assert float(final["outcome"]["scenarios"]["SEVERE"]["net_inr"]) < 0
    assert len(final["outcome_history"]) == 3
    assert history(env, saved, "2026-10-05T18:00:00Z")["alerts"][0]["outcome"]["status"] == "PENDING_ENTRY"
    assert final["record"] == early["record"]


@pytest.mark.parametrize("change,code", [({"volume": None}, "LIQUIDITY"), ({"open_interest": None}, "LIQUIDITY"),
                                         ({"source_url": ""}, "MISSING_FIELDS"), ({"price_unit": "wrong"}, "UNIT_MISMATCH"),
                                         ({"available_at": "2026-10-06T18:00:00Z"}, "MISSING_LEG")])
def test_missing_required_inputs_suppress_even_baseline(env, monkeypatch, change, code):
    saved = session(env, policy="baseline")
    mutate(monkeypatch, "2026-10-05", change)
    result = scan(env, saved, "2026-10-05T18:00:00Z")
    assert not result["new_alert_ids"] and code in result["reason"]
    assert result["input_status"] == "BLOCKED"


def test_stale_and_stricter_freshness_suppress(env):
    saved = session(env, policy="baseline")
    result = scan(env, saved, "2026-10-27T18:00:00Z")
    assert "STALE" in result["reason"] and not result["new_alert_ids"]
    saved = session(env, policy="baseline", max_age_hours=1)
    result = scan(env, saved, "2026-10-05T18:00:00Z")
    assert "STALE" in result["reason"] and not result["new_alert_ids"]


def test_missing_exit_is_censored_not_replaced_or_loss(env, monkeypatch):
    saved = session(env, policy="baseline")
    scan(env, saved, "2026-10-05T18:00:00Z")
    original = alerts.snapshot
    def missing(*args):
        registry, rows = original(*args)
        return registry, [r for r in rows if not (r["instrument"] == "GOLDTEN" and r["trading_date"] == "2026-10-13")]
    monkeypatch.setattr(alerts, "snapshot", missing)
    scan(env, saved, "2026-10-14T18:00:00Z")
    outcome = history(env, saved, "2026-10-14T18:00:00Z")["alerts"][0]["outcome"]
    assert outcome["status"] == "CENSORED_EXIT" and outcome["label"] is None
    assert "scenarios" not in outcome


def test_future_changes_do_not_change_frozen_signal(env, monkeypatch):
    first = session(env, policy="baseline")
    scan(env, first, "2026-10-05T18:00:00Z")
    frozen = history(env, first, "2026-10-05T18:00:00Z")["alerts"][0]
    mutate(monkeypatch, "2026-10-13", {"price": "100000"})
    second = session(env, policy="baseline")
    scan(env, second, "2026-10-05T18:00:00Z")
    other = history(env, second, "2026-10-05T18:00:00Z")["alerts"][0]
    assert frozen["record"] == other["record"] and frozen["observations"] == other["observations"]


def test_concurrent_scans_notify_once(env):
    saved = session(env, policy="baseline")
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: scan(env, saved, "2026-10-05T18:00:00Z"), range(2)))
    assert sum(len(r["new_alert_ids"]) for r in results) == 1
    assert len(history(env, saved, "2026-10-05T18:00:00Z")["alerts"]) == 1


def test_evaluation_mismatch_fails_closed(env, monkeypatch, tmp_path):
    saved = session(env, policy="baseline")
    report = json.loads(alerts.REPORT.read_text())
    report["protocol_hash"] = "changed"
    wrong = tmp_path / "wrong-report.json"
    wrong.write_text(json.dumps(report))
    monkeypatch.setattr(alerts, "REPORT", wrong)
    result = scan(env, saved, "2026-10-05T18:00:00Z")
    assert "EVALUATION_MISMATCH" in result["reason"] and not result["new_alert_ids"]


def test_source_loss_suppresses_existing_notification(env):
    saved = session(env, policy="baseline")
    scan(env, saved, "2026-10-05T18:00:00Z")
    result = scan((env[0].with_name("missing.sqlite3"), env[1]), saved, "2026-10-05T18:01:00Z")
    assert not result["new_alert_ids"] and "DATASET_UNAVAILABLE" in result["reason"]
    alert = history(env, saved, "2026-10-05T18:01:00Z")["alerts"][0]
    assert alert["status"] == "SUPPRESSED" and alert["outcome"]["status"] == "UNAVAILABLE"


def test_api_validation_isolation_and_unknown_ids(env, tmp_path):
    real = tmp_path / "real" / "missing.sqlite3"
    with TestClient(create_app(env[0], real, env[1], real_only=False)) as client:
        assert client.get("/api/alerts/catalog?dataset=synthetic").status_code == 200
        assert client.get("/api/alerts/catalog?dataset=real").status_code == 404
        assert client.post("/api/alerts/sessions", json={"dataset": "real"}).status_code == 404
        assert not real.exists() and not (env[1] / "real").exists()
        for settings in ({"min_abs_z": 2}, {"max_age_hours": 25}, {"cooldown_hours": -1}, {"expires_hours": 0},
                         {"min_severe_net_bps": 9}, {"min_abs_z": "NaN"}, {"max_age_hours": True}):
            assert client.post("/api/alerts/sessions", json={"dataset": "synthetic", "settings": settings}).status_code == 422
        created = client.post("/api/alerts/sessions", json={"dataset": "synthetic", "settings": {"policy": "baseline"}}).json()
        payload = {"dataset": "synthetic", "session_id": created["id"], "as_of": "2026-10-05T18:00:00Z"}
        assert client.post("/api/alerts/scan", json=payload).status_code == 200
        assert client.post("/api/alerts/scan", json={**payload, "dataset": "real"}).status_code == 404
        assert client.post("/api/alerts/scan", json={**payload, "as_of": "2026-10"}).status_code == 422
        assert client.get("/api/alerts/sessions?dataset=../synthetic").status_code == 422
        result = client.get("/api/alerts/history", params=payload).json()
        assert len(result["alerts"]) == 1
        assert client.post("/api/alerts/read", params={"dataset": "synthetic", "session_id": created["id"], "alert_id": "unknown"}).status_code == 404
