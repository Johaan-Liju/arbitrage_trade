"""Counterfactual leakage tests and hand accounting; every fixture is invented."""
from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from hashlib import sha256
import json

import pytest
from fastapi.testclient import TestClient

from backend.main import create_app
from backend.opportunity import OpportunityRequest, PairResearch, cash_outcome, predict
from backend.opportunity_evaluation import evaluate, independent_blocks, metrics, walk_forward
from backend.reference import ReferenceFailure, ReferenceRegistry
from backend.research import snapshot
from backend.synthetic_v4 import seed

REQUEST = {"dataset": "synthetic", "as_of": "2026-10-23T18:00:00Z", "pairs": [{
    "contract_a": "GOLDTEN:2026-11-20:demo-v4", "contract_b": "GOLDGUINEA:2026-11-20:demo-v4",
    "calendar_a": "synthetic-sessions-v4", "calendar_b": "synthetic-sessions-v4"}]}


@pytest.fixture(scope="module")
def data(tmp_path_factory):
    path = tmp_path_factory.mktemp("opportunity") / "synthetic.sqlite3"
    seed(path)
    registry, rows = snapshot(path, "synthetic", REQUEST["as_of"])
    return path, registry, rows


def research(data, rows=None, registry=None, **changes):
    _, original_registry, original_rows = data
    req = OpportunityRequest.model_validate({**REQUEST, **changes})
    return PairResearch(registry or original_registry, original_rows if rows is None else rows, req, req.pairs[0])


def prediction_part(record):
    return {k: record.get(k) for k in ("decision_at", "features", "forecast", "baseline_alert", "model_alert", "lots", "sides", "planned_entry", "planned_exit")}


def test_real_file_absent_no_fallback_and_api_validation(data, tmp_path):
    path, _, _ = data
    before = sha256(path.read_bytes()).hexdigest()
    with TestClient(create_app(path, tmp_path / "real.sqlite3")) as client:
        response = client.post("/api/opportunities/evaluate", json=REQUEST)
        assert response.status_code == 200
        report = response.json()
        assert report["status"] == "EXPERIMENTAL" and not report["evidence"]["credible_market_claim"]
        assert report["coverage"]["unique_dates"] == 39 and report["coverage"]["eligible_decisions"] == 29
        assert len(report["folds"]) == 2 and len(report["held_out"]["record_ids"]) == 10
        baseline, model = [report["held_out"]["metrics"][p] for p in ("baseline", "model")]
        assert baseline["alerts"] == 1 and model["alerts"] == 0
        assert baseline["precision_robust_positive"] == 0 and model["precision_robust_positive"] is None
        assert baseline["cost_scenarios"]["BASE"]["precision_above_10bps"] == 1
        assert baseline["cost_scenarios"]["SEVERE"]["mean_net_return_bps"] < 0
        assert baseline["uncertainty"]["precision_interval"] is None
        for endpoint in ("evaluate", "predict"):
            assert client.post(f"/api/opportunities/{endpoint}", json={**REQUEST, "dataset": "real"}).status_code == 404
            assert client.post(f"/api/opportunities/{endpoint}", json={**REQUEST, "dataset": "unknown"}).status_code == 422
        assert client.post("/api/opportunities/evaluate", json={**REQUEST, "embargo_sessions": 5}).status_code == 422
        assert client.post("/api/opportunities/evaluate", json={**REQUEST, "as_of": "2026-10"}).status_code == 422
        assert client.post("/api/opportunities/evaluate", json={**REQUEST, "pairs": REQUEST["pairs"] * 2}).status_code == 422
        bad = {**REQUEST["pairs"][0], "contract_b": "GOLDGUINEA:2026-12-24:demo-v4"}
        assert client.post("/api/opportunities/evaluate", json={**REQUEST, "pairs": [bad]}).status_code == 422
    assert sha256(path.read_bytes()).hexdigest() == before
    assert not (tmp_path / "real.sqlite3").exists()


def test_hand_calculated_cash_and_four_sided_costs(data):
    pair = research(data)
    result = cash_outcome(pair.specs, [4, 5], [-1, 1], [Decimal(100), Decimal(80)], [Decimal(90), Decimal(80)])
    assert Decimal(result["gross_inr"]) == 40  # 4 x short quote gain of 10.
    assert Decimal(result["initial_gross_notional_inr"]) == 800
    base = result["scenarios"]["BASE"]
    assert len(base["items"]) == 4
    assert Decimal(base["cost_inr"]) == Decimal("3.12")  # (800 + 760) * 20 bps.
    assert Decimal(base["net_inr"]) == Decimal("36.88")
    assert Decimal(base["net_return"]) == Decimal("0.0461")


def test_future_prices_cannot_change_prior_predictions(data):
    rows = deepcopy(data[2])
    for row in rows:
        if row["trading_date"] > "2026-10-05":
            row["price"] = str(Decimal(row["price"]) * Decimal("1.7"))
    before, after = research(data).record("2026-10-05"), research(data, rows=rows).record("2026-10-05")
    assert before["baseline_alert"]
    assert prediction_part(before) == prediction_part(after)
    assert before["outcome"] != after["outcome"]  # Label may change; forecast must not.
    partial = research(data, as_of="2026-10-05T16:05:00Z").record("2026-10-05")
    assert prediction_part(partial) == prediction_part(before)
    assert partial["outcome"]["status"] == "CENSORED_ENTRY"
    for prior in before["features"]["prior_provenance"]:
        assert prior["trading_date"] < before["trading_date"] and prior["known_at"] <= before["decision_at"]


def test_next_session_five_session_exit_and_label_maturity(data):
    event = research(data).record("2026-10-05")
    assert event["planned_entry"] == "2026-10-06" and event["planned_exit"] == "2026-10-13"
    assert event["outcome"]["label_available_at"] == "2026-10-13T16:05:00Z"
    assert event["outcome"]["execution_evidence"] == "NONE"
    before = research(data, as_of="2026-10-13T16:04:59Z").record("2026-10-05")
    assert before["outcome"]["status"] == "CENSORED_EXIT" and before["outcome"]["label"] is None
    exact = research(data, as_of="2026-10-13T16:05:00Z").record("2026-10-05")
    assert exact["outcome"]["status"] == "COMPLETE"
    assert all(r["observed_at"] > event["decision_at"] for r in event["outcome"]["entry"])


@pytest.mark.parametrize("stage,day", [("ENTRY", "2026-10-06"), ("EXIT", "2026-10-13")])
def test_missing_endpoint_not_shifted_or_labelled_loss(data, stage, day):
    rows = [r for r in data[2] if not (r["instrument"] == "GOLDTEN" and r["expiry"] == "2026-11-20" and r["trading_date"] == day)]
    outcome = research(data, rows=rows).record("2026-10-05")["outcome"]
    assert outcome["status"] == "CENSORED_" + stage
    assert outcome["label"] is None and outcome["label_available_at"] is None


@pytest.mark.parametrize("change,code", [({"volume": None}, "LIQUIDITY"), ({"open_interest": 100}, "LIQUIDITY"),
                                       ({"spec_version": "future-version"}, "SPEC_IDENTITY_MISMATCH"),
                                       ({"available_at": "2026-10-07T16:05:00Z"}, "STALE")])
def test_decision_quality_fails_closed(data, change, code):
    rows = deepcopy(data[2])
    row = next(r for r in rows if r["instrument"] == "GOLDTEN" and r["expiry"] == "2026-11-20" and r["trading_date"] == "2026-10-05")
    row.update(change)
    event = research(data, rows=rows).record("2026-10-05")
    assert event["eligibility"] == "INELIGIBLE" and code in event["reason"]
    assert not event["model_alert"] and event["outcome"] is None


def test_unavailable_history_and_spec_versions_do_not_leak(data):
    rows = deepcopy(data[2])
    prior = next(r for r in rows if r["instrument"] == "GOLDTEN" and r["expiry"] == "2026-11-20" and r["trading_date"] == "2026-10-02")
    prior["available_at"] = "2026-10-06T16:05:00Z"
    assert "FUTURE_HISTORY" in research(data, rows=rows).record("2026-10-05")["reason"]
    values = data[1].model_dump(mode="json")
    for spec in values["specs"]:
        if spec["instrument"] == "GOLDTEN":
            spec["available_at"] = "2026-10-06T00:00:00Z"
    registry = ReferenceRegistry.model_validate(values)
    with pytest.raises(ReferenceFailure, match="unavailable"):
        research(data, registry=registry, as_of="2026-10-05T18:00:00Z")
    late = research(data, registry=registry).record("2026-10-05")
    assert late["decision_at"] == "2026-10-06T00:00:00Z"
    assert not late["baseline_alert"]  # Prior rows cannot pass their own publication-time freshness.


def test_new_spec_not_merged_and_exact_old_version_still_used(data):
    values = data[1].model_dump(mode="json")
    spec = deepcopy(next(s for s in values["specs"] if s["instrument"] == "GOLDTEN"))
    spec.update(spec_id="GOLDTEN:future", version="future", available_at="2026-10-24T00:00:00Z", quotation_grams="20")
    listing = deepcopy(next(c for c in values["contracts"] if c["spec_id"] == "GOLDTEN:demo-v4"))
    listing["spec_id"] = spec["spec_id"]
    values["specs"].append(spec); values["contracts"].append(listing)
    original = research(data).record("2026-10-05")
    updated = research(data, registry=ReferenceRegistry.model_validate(values)).record("2026-10-05")
    assert prediction_part(original) == prediction_part(updated)
    assert updated["spec_versions"] == ["demo-v4", "demo-v4"]


def test_missing_prior_session_and_near_deadline_block(data):
    rows = [r for r in data[2] if r["trading_date"] != "2026-10-02"]
    assert "WARMUP_GAP" in research(data, rows=rows).record("2026-10-05")["reason"]
    values = data[1].model_dump(mode="json")
    for listing in values["contracts"]:
        listing["safe_exit_date"] = "2026-10-14"
    assert "SAFETY_DEADLINE" in research(data, registry=ReferenceRegistry.model_validate(values)).record("2026-10-05")["reason"]


def test_current_predictions_enforce_asof_freshness_without_outcomes(data):
    req = OpportunityRequest.model_validate(REQUEST)
    result = predict(data[0], req)
    assert result["predictions"][0]["baseline_alert"]
    assert result["predictions"][0]["outcome"] is None
    assert result["predictions"][0]["features"]["as_of"] == req.as_of
    stale = predict(data[0], req.model_copy(update={"as_of": "2026-10-27T18:00:00Z"}))
    assert "STALE" in stale["predictions"][0]["reason"] and not stale["predictions"][0]["model_alert"]


def fake_record(index, pair="A"):
    day = lambda i: (date(2020, 1, 1) + timedelta(days=i)).isoformat()
    return {"id": f"{pair}-{index}", "pair_id": pair, "trading_date": day(index), "decision_at": day(index) + "T16:05:00Z",
            "expiry": "2020-12-31", "eligibility": "ELIGIBLE", "baseline_alert": True, "model_alert": False,
            "planned_exit": day(index + 6), "outcome": {"status": "COMPLETE", "label": "NEGATIVE",
            "label_available_at": day(index + 6) + "T16:05:00Z",
            "scenarios": {name: {"net_return": "-0.002", "net_inr": "-100"} for name in ("BASE", "STRESS", "SEVERE")}}}


def test_walk_forward_groups_dates_purges_overlap_and_late_labels():
    rows = [fake_record(i, pair) for i in range(40) for pair in ("A", "B")]
    rows[0]["outcome"]["label_available_at"] = "2020-02-01T16:05:00Z"
    folds, heldout = walk_forward(rows, OpportunityRequest.model_validate(REQUEST))
    lookup = {r["id"]: r for r in rows}
    assert len({r["id"] for r in heldout}) == len(heldout)
    for fold in folds:
        for identifier in fold["training_ids"]:
            row = lookup[identifier]
            assert row["outcome"]["label_available_at"] < fold["training_label_cutoff_exclusive"]
            assert row["planned_exit"] < fold["test_start"]
        assert len(fold["test_ids"]) == 2 * len({lookup[i]["trading_date"] for i in fold["test_ids"]})
    assert "A-0" not in folds[0]["training_ids"]
    assert {r["reason"] for r in folds[0]["purged_or_embargoed"]} >= {"EMBARGO", "PURGED_OVERLAPPING_OR_UNAVAILABLE_LABEL"}
    for first, second in zip(folds, folds[1:]):
        assert max(lookup[i]["planned_exit"] for i in first["test_ids"]) < second["test_start"]


def test_uncertainty_clusters_same_expiry_and_overlapping_cycles():
    rows = [fake_record(i) for i in (0, 1, 20)]
    other = deepcopy(rows[0]); other["expiry"] = "2021-01-01"
    assert len(independent_blocks(rows + [other])) == 1


def test_report_reproducible_and_all_labels_have_no_execution(data):
    req = OpportunityRequest.model_validate(REQUEST)
    one, two = evaluate(data[0], req), evaluate(data[0], req)
    assert one == two
    json.dumps(one, allow_nan=False)
    for record in one["records"]:
        if record["outcome"]:
            assert record["outcome"]["execution_evidence"] == "NONE"
            if record["outcome"]["status"] == "COMPLETE":
                assert record["outcome"]["label_available_at"] <= req.as_of


def test_precision_materiality_boundary_uses_decimal():
    row = fake_record(0)
    row["outcome"]["scenarios"]["BASE"]["net_return"] = "0.00100000000000000000001"
    assert metrics([row], "baseline")["cost_scenarios"]["BASE"]["precision_above_10bps"] == 1
    row["outcome"]["scenarios"]["BASE"]["net_return"] = "0.001"
    assert metrics([row], "baseline")["cost_scenarios"]["BASE"]["precision_above_10bps"] == 0
