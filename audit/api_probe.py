"""Audit API probe (run from repo root: python audit/api_probe.py). Needs the backend on 127.0.0.1:8000 and frontend on :3000. Uses only the standard library."""
import json, sys, urllib.request, urllib.error, urllib.parse

B, F = "http://127.0.0.1:8000", "http://127.0.0.1:3000"
TEN, GUI = "GOLDTEN:2026-11-24:demo-v3", "GOLDGUINEA:2026-11-27:demo-v3"
AS_OF = "2026-10-23T18:00:00Z"
results = []

def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"null")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"null")
        except Exception:
            return e.code, None

def expect(name, ok, detail=""):
    results.append((name, ok, detail))

q = urllib.parse.urlencode
pair = {"contract_a": TEN, "contract_b": GUI, "dataset": "synthetic", "as_of": AS_OF}

s, b = call("GET", f"{B}/api/health"); expect("health 200", s == 200 and b["observations"] == 312, f"{s} {b and b.get('observations')}")
s, b = call("GET", f"{B}/api/contracts?{q({'as_of': AS_OF})}"); expect("contracts: 8, all SYNTHETIC", s == 200 and len(b["contracts"]) == 8 and {c['verification'] for c in b['contracts']} == {'SYNTHETIC'}, f"{s}")
s, b = call("GET", f"{B}/api/contracts?{q({'as_of': '2026-07-01T00:00:00Z'})}"); expect("contracts before spec availability: 0", s == 200 and len(b["contracts"]) == 0, f"{s} {b and len(b['contracts'])}")
s, b = call("GET", f"{B}/api/research?{q({'contract_id': TEN, 'as_of': AS_OF})}"); expect("research 39 rows, label SYNTHETIC", s == 200 and len(b["prices"]) == 39 and b["label"] == "SYNTHETIC", f"{s}")
s, b = call("GET", f"{B}/api/research?{q({'contract_id': TEN, 'as_of': '2026-09-15T16:04:59Z'})}")
expect("research cutoff excludes not-yet-available row", s == 200 and max(p["trading_date"] for p in b["prices"]) == "2026-09-14" and all(p["available_at"] <= "2026-09-15T16:04:59Z" for p in b["prices"]), f"{s}")
s, b = call("GET", f"{B}/api/research?{q({'contract_id': TEN, 'as_of': '2026-10-23'})}"); expect("malformed as_of -> 422", s == 422, f"{s}")
s, b = call("GET", f"{B}/api/research?{q({'contract_id': 'GOLDTEN:2026-11-30:demo-v3', 'as_of': AS_OF})}"); expect("unknown expiry -> 404 (no month inference)", s == 404, f"{s}")
for path in ("contracts", "research"):
    s, b = call("GET", f"{B}/api/{path}?{q({'dataset': 'real', 'contract_id': TEN, 'as_of': AS_OF})}"); expect(f"real {path} -> 404 no fallback", s == 404, f"{s}")
s, b = call("POST", f"{B}/api/pair", {**pair, "dataset": "real"}); expect("real pair -> 404", s == 404, f"{s}")
s, b = call("POST", f"{B}/api/pair", pair); expect("pair 200 CALENDAR_BASIS_DIFFERENCE", s == 200 and b["alignment"] == "CALENDAR_BASIS_DIFFERENCE" and b["latest"]["status"] == "INVESTIGATE", f"{s} {b and b.get('alignment')}")
s, b = call("POST", f"{B}/api/pair", {**pair, "contract_b": TEN}); expect("same contract twice -> 422", s == 422, f"{s}")
s, b = call("POST", f"{B}/api/pair", {**pair, "contract_b": "GOLDTEN:2026-12-22:demo-v3"}); expect("same symbol, other expiry -> separate contract, calendar flagged", s == 200 and b["alignment"] == "CALENDAR_BASIS_DIFFERENCE", f"{s}")
s, b = call("POST", f"{B}/api/pair", {**pair, "lookback": 1}); expect("lookback 1 -> 422", s == 422, f"{s}")
s, b = call("POST", f"{B}/api/backtest", pair); expect("backtest default rejects calendar mismatch", s == 200 and b["number_of_trades"] == 0 and any("allow_calendar" in r["reason"] for r in b["rejections"]), f"{s}")
s, b = call("POST", f"{B}/api/backtest", {**pair, "allow_calendar": True}); expect("backtest accepted: 1 trade net 3792.03", s == 200 and b["number_of_trades"] == 1 and round(b["net_pnl"], 2) == 3792.03, f"{s} {b and b.get('net_pnl')}")
s2, b2 = call("POST", f"{B}/backtest", {**pair, "allow_calendar": True}); expect("/backtest alias same run_id", s2 == 200 and b2["run_id"] == b["run_id"], f"{s2}")
s, b = call("POST", f"{B}/api/backtest", {**pair, "allow_calendar": True, "exit_z": 3.0}); expect("exit_z >= entry_z -> 422", s == 422, f"{s}")
s, b = call("POST", f"{B}/api/backtest", {**pair, "allow_calendar": True, "entry_z": 100}); expect("entry_z 100 -> 0 trades, net 0", s == 200 and b["number_of_trades"] == 0 and b["net_pnl"] == 0, f"{s}")
s, b = call("GET", f"{B}/api/spec-evidence"); expect("spec evidence: live_analytics_enabled false", s == 200 and b["live_analytics_enabled"] is False and len(b["specifications"]) == 4, f"{s}")
cols = "contract_id,dataset,symbol,expiry,spec_version,trading_date,price,open,high,low,close,volume,open_interest,currency,unit,source,observed_at,available_at,ingested_at"
good = f"{cols}\n{TEN},synthetic,GOLDTEN,2026-11-24,demo-v3,2026-10-26,79000,79000,79100,78900,79000,2000,9000,INR,quote,audit,2026-10-26T16:00:00Z,2026-10-26T16:05:00Z,2026-10-26T16:05:00Z\n"
s, b = call("POST", f"{B}/api/ingest", {"csv_text": good, "as_of": "2026-10-27T00:00:00Z"}); expect("ingest valid row dry-run accepted, 0 inserted", s == 200 and b["accepted"] and b["inserted"] == 0, f"{s}")
dup = good.replace("2026-10-26", "2026-10-23")
s, b = call("POST", f"{B}/api/ingest", {"csv_text": dup, "as_of": "2026-10-27T00:00:00Z"}); expect("ingest duplicate key rejected", s == 200 and not b["accepted"], f"{s}")
s, b = call("POST", f"{B}/api/ingest", {"csv_text": good, "as_of": "2026-10-26T00:00:00Z"}); expect("ingest future availability rejected", s == 200 and not b["accepted"], f"{s}")
s, b = call("POST", f"{B}/api/ingest", {"csv_text": good, "as_of": "2026-10-27T00:00:00Z", "dataset": "real"}); expect("ingest real -> 404", s == 404, f"{s}")
s, b = call("GET", f"{F}/api/health"); expect("frontend proxy /api/health", s == 200, f"{s}")
s, b = call("POST", f"{F}/api/pair", pair); expect("frontend proxy POST /api/pair", s == 200 and b["alignment"] == "CALENDAR_BASIS_DIFFERENCE", f"{s}")
s, b = call("GET", f"{B}/api/health"); expect("health still 312 after dry runs", b["observations"] == 312, f"{b['observations']}")

for name, ok, detail in results:
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if not ok else ""))
print(f"{sum(ok for _, ok, _ in results)}/{len(results)} passed")
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
