"""Independent arithmetic and point-in-time boundary tests for raw spread signals."""
from copy import deepcopy
import math

import pytest
from pydantic import ValidationError

from backend.pairs import PairRequest, pair_history


def fixture():
    specs = [{"dataset": "synthetic", "contract_id": f"{symbol}:2026-11-20:v1",
              "symbol": symbol, "expiry": "2026-11-20", "spec_version": "v1", "spec_id": f"{symbol}:v1",
              "available_at": "2026-08-31T00:00:00Z", "valid_from": "2026-09-01", "valid_to": "2026-11-20",
              "safe_exit_date": "2026-11-10"} for symbol in ("GOLDM", "GOLDTEN")]
    rows = [[{**{k: s[k] for k in ("dataset", "contract_id", "symbol", "expiry", "spec_version", "spec_id")},
              "trading_date": f"2026-09-{i:02d}", "observed_at": f"2026-09-{i:02d}T16:00:00Z",
              "available_at": f"2026-09-{i:02d}T16:05:00Z", "normalized_available_at": f"2026-09-{i:02d}T16:05:00Z",
              "normalized_999_inr_per_gram": str(7000 + (v if leg == 0 else 0)),
              "price": 7000, "volume": 1000, "open_interest": 1000}
             for i, v in enumerate([1, 2, 3, 4, 5, 10], 1)] for leg, s in enumerate(specs)]
    req = PairRequest(contract_a=specs[0]["contract_id"], contract_b=specs[1]["contract_id"],
                      as_of="2026-09-06T16:05:00Z", lookback=3, min_observations=3, entry_z=6)
    return specs, rows, req


def test_hand_arithmetic_sample_std_window_current_excluded_and_threshold():
    specs, rows, req = fixture()
    result = pair_history(specs, rows, req)
    last = result["latest"]
    assert (last["raw_pair_spread"], last["prior_mean"], last["prior_std"], last["z_score"], last["sample_count"]) == (10, 4, 1, 6, 3)
    assert last["cutoff"] == req.as_of and result["spread_direction"] == "left minus right"
    assert last["status"] == "Investigate"
    above = req.model_copy(update={"entry_z": math.nextafter(6, math.inf)})
    assert pair_history(specs, rows, above)["latest"]["status"] == "No signal"
    changed = deepcopy(rows)
    changed[0][-1]["normalized_999_inr_per_gram"] = "8000"
    after = pair_history(specs, changed, req)
    assert after["history"][:-1] == result["history"][:-1]
    assert after["latest"]["prior_mean"] == 4 and after["latest"]["prior_std"] == 1


@pytest.mark.parametrize("field", ["observed_at", "available_at", "normalized_available_at", "reference"])
def test_late_arrivals_and_reference_cutoffs_at_every_decision(field):
    specs, rows, req = fixture()
    # Date 3 arrives after date 5's decision but before date 6's decision.
    late = "2026-09-05T16:05:01Z"
    if field == "reference":
        rows[0][2]["reference_availability"] = {"calendar": late}
    else:
        rows[0][2][field] = late
    result = pair_history(specs, rows, req)
    event5 = next(e for e in result["history"] if e["trading_date"] == "2026-09-05")
    assert event5["sample_count"] == 3 and event5["prior_mean"] == pytest.approx(7 / 3)  # dates 1,2,4
    assert result["latest"]["prior_mean"] == 4  # late date 3 now eligible
    early = pair_history(specs, rows, req.model_copy(update={"as_of": "2026-09-05T16:05:00Z"}))
    assert early["latest"]["prior_mean"] == event5["prior_mean"]
    # A current cutoff after a late arrival can update latest without rewriting replay.
    req = req.model_copy(update={"as_of": late})
    now = pair_history(specs, rows, req)
    assert next(e for e in now["history"] if e["trading_date"] == "2026-09-05") == event5
    assert now["latest"]["prior_mean"] == 3  # dates 2,3,4


def test_missing_dates_zero_variance_and_inadequate_history():
    specs, rows, req = fixture()
    rows[1].pop(3)
    result = pair_history(specs, rows, req)
    assert result["latest"]["prior_mean"] == pytest.approx(10 / 3)  # 1,2,3,5 => last 3: 2,3,5
    assert [e["trading_date"] for e in result["history"]] == ["2026-09-01", "2026-09-02", "2026-09-03", "2026-09-05", "2026-09-06"]
    assert result["history"][0]["status"] == "Insufficient data"
    assert "Need 3" in result["history"][0]["reason"]
    rows[1].pop()
    missing = pair_history(specs, rows, req)
    assert missing["latest"]["status"] == "Insufficient data" and missing["latest"]["z_score"] is None
    assert missing["latest"]["raw_pair_spread"] is None
    specs, rows, req = fixture()
    for r in rows[0]:
        r["normalized_999_inr_per_gram"] = "7001"
    flat = pair_history(specs, rows, req)["latest"]
    assert flat["status"] == "Insufficient data" and "zero" in flat["reason"] and flat["prior_std"] == 0


@pytest.mark.parametrize("field,value", [("dataset", "real"), ("expiry", "2026-11-21"), ("spec_version", "v2"), ("spec_id", "GOLDM:v2"), ("symbol", "GOLDPETAL")])
def test_no_mixed_identity_history(field, value):
    specs, rows, req = fixture()
    rows[0][0][field] = value
    with pytest.raises(ValueError, match="identity"):
        pair_history(specs, rows, req)


@pytest.mark.parametrize("changes", [{"lookback": 1}, {"lookback": 251}, {"lookback": True}, {"lookback": 3.5}, {"min_observations": 4}, {"entry_z": 0}, {"entry_z": 101}, {"entry_z": float("nan")}, {"entry_z": float("inf")}])
def test_settings_validation(changes):
    _, _, req = fixture()
    with pytest.raises(ValidationError):
        PairRequest.model_validate({**req.model_dump(), **changes})
