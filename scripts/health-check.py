"""Check the running backend and the frontend API proxy; no third-party requests."""
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import urlopen


def get(url):
    with urlopen(url, timeout=10) as response:
        return response.status, json.load(response)


for base in ("http://127.0.0.1:8000", "http://127.0.0.1:3000"):
    status, health = get(base + "/api/health")
    assert status == 200 and health["status"] == "ok"
    assert "real" in health["datasets"]
    print(f"PASS {base}/api/health -> {status}; real data: {health['datasets']['real']}")

base = "http://127.0.0.1:3000"
_, catalog = get(base + "/api/contracts")
assert catalog["dataset"] == "real" and catalog["contracts"]
params = {"contract_id": catalog["contracts"][0]["contract_id"], "as_of": catalog["default_as_of"], "dataset": "real"}
_, snapshot = get(base + "/api/research?" + urlencode(params))
assert snapshot["dataset"] == "real" and snapshot["metrics"]["count"] > 0
print(f"PASS frontend proxy -> real research: {snapshot['spec']['symbol']}, {snapshot['metrics']['count']} observations")
params["dataset"] = "synthetic"
try:
    get(base + "/api/research?" + urlencode(params))
    raise AssertionError("Synthetic dataset unexpectedly returned data")
except HTTPError as error:
    assert error.code == 422
    print("PASS synthetic dataset disabled")
