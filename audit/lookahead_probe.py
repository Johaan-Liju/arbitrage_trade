"""Independent audit probes: look-ahead bias and expiry mixing. Run from repo root: python audit/lookahead_probe.py"""
import copy, itertools, random, sqlite3, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
from backend.store import fixtures, seed, connection
from backend.pairs import PairRequest, pair_history, load_pair
from backend.backtest import BacktestRequest, simulate

AS_OF = "2026-10-23T18:00:00Z"
specs, prices = fixtures()
by_id = {s["contract_id"]: s for s in specs}
fails = []

def check(cond, msg):
    if not cond:
        fails.append(msg)

def rows_for(cid, data):
    return sorted([r for r in data if r["contract_id"] == cid], key=lambda r: r["trading_date"])

def strip(e):
    return {k: v for k, v in e.items() if k not in ("age_hours",)}

# --- A/B: future-perturbation invariance for every same-expiry-month pair
dates = sorted({r["trading_date"] for r in prices})
pairs = [(a, b) for a, b in itertools.permutations(specs, 2) if a["expiry"][:7] == b["expiry"][:7]]
rng = random.Random(7)
n_pair_checks = n_bt_checks = 0
for a, b in pairs:
    for cut in dates[8:-2:5]:
        future = copy.deepcopy(prices)
        for r in future:
            if r["trading_date"] > cut:
                f = 1 + rng.uniform(-.05, .05)
                for k in ("price", "open", "high", "low", "close"):
                    r[k] = round(r[k] * f, 2)
                r["volume"] = rng.randint(0, 9000)
        sa, sb = by_id[a["contract_id"]], by_id[b["contract_id"]]
        req = PairRequest(contract_a=sa["contract_id"], contract_b=sb["contract_id"], as_of=AS_OF)
        base = pair_history([sa, sb], [rows_for(sa["contract_id"], prices), rows_for(sb["contract_id"], prices)], req)
        pert = pair_history([sa, sb], [rows_for(sa["contract_id"], future), rows_for(sb["contract_id"], future)], req)
        e1 = [strip(e) for e in base["history"] if e["trading_date"] <= cut]
        e2 = [strip(e) for e in pert["history"] if e["trading_date"] <= cut]
        check(e1 == e2, f"PAIR look-ahead: {sa['symbol']}/{sb['symbol']} events<= {cut} changed when future perturbed")
        n_pair_checks += 1
        breq = BacktestRequest(contract_a=sa["contract_id"], contract_b=sb["contract_id"], as_of=AS_OF, allow_calendar=True, entry_z=2.0)
        r1 = simulate(base, breq); r2 = simulate(pert, breq)
        c1 = [c for c in r1["equity_curve"] if c["trading_date"] <= cut]
        c2 = [c for c in r2["equity_curve"] if c["trading_date"] <= cut]
        check(c1 == c2, f"BACKTEST look-ahead: equity<= {cut} changed for {sa['symbol']}/{sb['symbol']}")
        t1 = [(t["signal_date"], t["entry_date"]) for t in r1["trades"] if t["entry_date"] <= cut]
        t2 = [(t["signal_date"], t["entry_date"]) for t in r2["trades"] if t["entry_date"] <= cut]
        check(t1 == t2, f"BACKTEST look-ahead: entries<= {cut} changed")
        rj1 = [x for x in r1["rejections"] if x["trading_date"] <= cut]
        rj2 = [x for x in r2["rejections"] if x["trading_date"] <= cut]
        check(rj1 == rj2, f"BACKTEST look-ahead: rejections<= {cut} changed")
        # Prices-only perturbation (liquidity unchanged): decisions taken on or before cut must not move.
        po = copy.deepcopy(prices)
        for r in po:
            if r["trading_date"] > cut:
                f = 1 + rng.uniform(-.05, .05)
                for k in ("price", "open", "high", "low", "close"):
                    r[k] = round(r[k] * f, 2)
        pp = pair_history([sa, sb], [rows_for(sa["contract_id"], po), rows_for(sb["contract_id"], po)], req)
        r3 = simulate(pp, breq)
        s1 = sorted(t["signal_date"] for t in r1["trades"] if t["signal_date"] <= cut)
        s3 = sorted(t["signal_date"] for t in r3["trades"] if t["signal_date"] <= cut)
        check(s1 == s3, f"BACKTEST look-ahead: signal decisions<= {cut} changed by future prices")
        x1 = sorted(t["exit_signal_date"] for t in r1["trades"] if t["exit_signal_date"] <= cut)
        x3 = sorted(t["exit_signal_date"] for t in r3["trades"] if t["exit_signal_date"] <= cut)
        check(x1 == x3, f"BACKTEST look-ahead: exit decisions<= {cut} changed by future prices")
        n_bt_checks += 1

# --- C: late-arriving observation is not used before its availability
late = copy.deepcopy(prices)
ten = by_id["GOLDTEN:2026-11-24:demo-v3"]; gui = by_id["GOLDGUINEA:2026-11-27:demo-v3"]
target = "2026-10-05"
for r in late:
    if r["contract_id"] == ten["contract_id"] and r["trading_date"] == target:
        r["available_at"] = "2026-10-09T16:05:00Z"; r["ingested_at"] = "2026-10-09T16:05:00Z"
req = PairRequest(contract_a=ten["contract_id"], contract_b=gui["contract_id"], as_of="2026-10-07T18:00:00Z")
res = pair_history([ten, gui], [rows_for(ten["contract_id"], late), rows_for(gui["contract_id"], late)], req)
check(all(e["trading_date"] != target for e in res["history"]), "LATE row visible before availability")
req2 = PairRequest(contract_a=ten["contract_id"], contract_b=gui["contract_id"], as_of=AS_OF)
res2 = pair_history([ten, gui], [rows_for(ten["contract_id"], late), rows_for(gui["contract_id"], late)], req2)
ev = {e["trading_date"]: e for e in res2["history"]}
for d in ("2026-10-06", "2026-10-07", "2026-10-08"):
    # Prior windows for these days must not include the late row (decision_at earlier than its availability)
    check(ev[d]["decision_at"] < "2026-10-09T16:05:00Z", "unexpected decision time")
check(ev[target]["decision_at"] == "2026-10-09T16:05:00Z", "late row decision time should be its availability")

# --- D: fill-timing invariants over a parameter grid
n_trades = 0
for a, b in pairs:
    for ez, lb in itertools.product((1.0, 1.5, 2.0, 2.5, 3.0), (5, 10, 20)):
        mo = min(5, lb)
        breq = BacktestRequest(contract_a=a["contract_id"], contract_b=b["contract_id"], as_of=AS_OF, allow_calendar=True,
                               entry_z=ez, exit_z=min(.5, ez / 2), lookback=lb, min_observations=mo)
        ph = pair_history([a, b], [rows_for(a["contract_id"], prices), rows_for(b["contract_id"], prices)], breq)
        r = simulate(ph, breq)
        for t in r["trades"]:
            n_trades += 1
            check(t["entry_date"] > t["signal_date"], "entry not after signal")
            check(t["exit_date"] > t["exit_signal_date"], "exit not after exit signal")
            check(t["exit_date"] <= r["safe_exit_date"], "exit past safe exit")
            check(len(t["legs"]) == 2 and all(l["entry_fee"] > 0 and l["exit_fee"] > 0 and l["entry_slippage"] > 0 and l["exit_slippage"] > 0 for l in t["legs"]), "costs missing on a leg")
            check({l["expiry"] for l in t["legs"]} == {a["expiry"], b["expiry"]}, "leg expiry mismatch")
            ent = next(e for e in ph["history"] if e["trading_date"] == t["entry_date"])
            check(all(ent[k]["observed_at"] > t["signal_available_at"] for k in ("a", "b")), "fill observed before signal availability")

# --- E: expiry mixing in DB and API loader
with tempfile.TemporaryDirectory() as tmp:
    db_path = Path(tmp) / "probe.sqlite3"
    seed(db_path)
    with connection(db_path) as db:
        mixed = db.execute("SELECT contract_id, count(DISTINCT expiry||symbol||spec_version) n FROM prices GROUP BY contract_id HAVING n>1").fetchall()
        check(not mixed, f"contracts with mixed identity rows: {mixed}")
        per_sym = db.execute("SELECT symbol, count(DISTINCT expiry) FROM contracts GROUP BY symbol").fetchall()
        check(all(n == 2 for _, n in per_sym), "expected two expiries per symbol")
        for a, b in itertools.permutations(specs, 2):
            req = PairRequest(contract_a=a["contract_id"], contract_b=b["contract_id"], as_of=AS_OF)
            sp, hs = load_pair(db, req)
            check(all(r["expiry"] == a["expiry"] and r["contract_id"] == a["contract_id"] for r in hs[0]), "loader mixed expiry A")
            check(all(r["expiry"] == b["expiry"] and r["contract_id"] == b["contract_id"] for r in hs[1]), "loader mixed expiry B")
            ph = pair_history(sp, hs, req)
            want = "EXACT_EXPIRY" if a["expiry"] == b["expiry"] else "CALENDAR_BASIS_DIFFERENCE"
            check(ph["alignment"] == want, "alignment label wrong")
            check(all(e["a"]["trading_date"] == e["b"]["trading_date"] == e["trading_date"] for e in ph["history"]), "pair rows not same trading date")
        # Mixed-identity injection must be rejected by pair_history
        sp, hs = load_pair(db, PairRequest(contract_a=ten["contract_id"], contract_b=gui["contract_id"], as_of=AS_OF))
        dec = [r for r in fixtures()[1] if r["contract_id"] == "GOLDTEN:2026-12-22:demo-v3"][:1]
        try:
            pair_history(sp, [hs[0] + dec, hs[1]], PairRequest(contract_a=ten["contract_id"], contract_b=gui["contract_id"], as_of=AS_OF))
            fails.append("mixed expiry row was accepted")
        except ValueError:
            pass

print(f"pair future-perturbation checks: {n_pair_checks}; backtest checks: {n_bt_checks}; trades checked: {n_trades}")
print("FAILURES:" if fails else "ALL PROBES PASSED")
for f in sorted(set(fails)):
    print(" -", f)
sys.exit(1 if fails else 0)
