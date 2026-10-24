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
    assert health["datasets"]["real"] == "not configured"
    print(f"PASS {base}/api/health -> {status}; SQLite; {health['observations']} synthetic observations")

base = "http://127.0.0.1:3000"
_, catalog = get(base + "/api/contracts")
assert len(catalog["contracts"]) == 8
params = {"contract_id": "GOLDPETAL:2026-11-30:demo-v3", "as_of": catalog["default_as_of"], "dataset": "synthetic"}
_, snapshot = get(base + "/api/research?" + urlencode(params))
assert snapshot["spec"]["symbol"] == "GOLDPETAL" and snapshot["metrics"]["count"] == 39
print("PASS frontend proxy -> FastAPI research: GOLDPETAL, 39 observations, SYNTHETIC")
params["dataset"] = "real"
try:
    get(base + "/api/research?" + urlencode(params))
    raise AssertionError("Real dataset unexpectedly returned data")
except HTTPError as error:
    assert error.code == 404
    print("PASS real dataset -> 404; no fallback")
