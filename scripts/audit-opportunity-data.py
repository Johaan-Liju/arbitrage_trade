"""Read-only coverage audit for the opportunity research specification; no labels/model fitting."""
import argparse
from collections import Counter
from datetime import datetime
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.domain import DEFAULT_AS_OF
from backend.research import research_snapshot
from backend.synthetic_v4 import SYNTHETIC_DB, REAL_DB


def audit(path, dataset, as_of):
    if not path.exists():
        return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "exists": False, "dataset": dataset}
    current = research_snapshot(path, dataset, as_of)
    with sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True) as db:
        raw = [json.loads(row[0]) for row in db.execute("SELECT payload FROM observations")]
        references = dict(db.execute("SELECT kind, count(*) FROM reference_versions GROUP BY kind"))
        batches = db.execute("SELECT count(*) FROM batches").fetchone()[0]
    partitions = []
    for spec in current["contracts"]:
        history = current["histories"][spec["contract_id"]]
        days = [r["trading_date"] for r in history]
        partitions.append({"contract_id": spec["contract_id"], "spec_id": spec["spec_id"], "spec_version": spec["spec_version"],
                           "expiry": spec["expiry"], "symbol": spec["symbol"], "rows": len(history),
                           "first": min(days) if days else None, "last": max(days) if days else None,
                           "quotation_grams": spec["quotation_grams"], "lot_size_grams": spec["lot_size_grams"],
                           "quote_purity_per_mille": spec["quote_purity_per_mille"], "verification": spec["verification"],
                           "liquidity_missing": sum(r.get("volume") is None or r.get("open_interest") is None for r in history)})
    pairs = []
    for a, b in combinations(current["contracts"], 2):
        if a["symbol"] == b["symbol"] or a["expiry"] != b["expiry"]:
            continue
        left, right = [current["histories"][s["contract_id"]] for s in (a, b)]
        dates = sorted({r["trading_date"] for r in left} & {r["trading_date"] for r in right})
        # Coverage bounds only: ten preceding records, next-session entry, five sessions held.
        pairs.append({"a": a["contract_id"], "b": b["contract_id"], "exact_expiry": a["expiry"],
                      "aligned_dates": len(dates), "first": dates[0] if dates else None, "last": dates[-1] if dates else None,
                      "after_10_record_warmup": max(0, len(dates) - 10),
                      "complete_fixed_horizon_windows_upper_bound": max(0, len(dates) - 10 - 6),
                      "note": "Upper bound, not threshold crossings, independent trades, validated outcomes or execution"})
    valid = [r for history in current["histories"].values() for r in history]
    lag = Counter((datetime.fromisoformat(r["available_at"]) - datetime.fromisoformat(r["observed_at"])).total_seconds() for r in valid)
    return {"path": str(path.relative_to(ROOT)).replace("\\", "/"), "exists": True, "dataset": dataset,
            "file_sha256": sha256(path.read_bytes()).hexdigest(), "as_of": as_of,
            "stored_observations": len(raw), "usable_observations": len(valid), "blocked_records": current["issues"],
            "reference_counts": references, "batches": batches, "unique_trading_dates": len({r["trading_date"] for r in valid}),
            "observed_fields": sorted({key for row in raw for key in row}),
            "sources": sorted({r["source"] for r in valid}), "availability_lag_seconds_counts": dict(lag),
            "partition_coverage": partitions, "eligible_exact_expiry_pairs": pairs,
            "source_note": "Synthetic records, terms, session calendar and liquidity are invented; not real market evidence" if dataset == "synthetic" else "Imported records; execution not established"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=DEFAULT_AS_OF)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = {"audit_version": "opportunity-v1", "as_of": args.as_of,
              "synthetic": audit(SYNTHETIC_DB, "synthetic", args.as_of), "real": audit(REAL_DB, "real", args.as_of),
              "legacy_files_excluded": sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in (ROOT / "data/synthetic").iterdir() if p.is_file() and p != SYNTHETIC_DB),
              "actions": "Read-only existing datasets; no seeding, training, fills, labels or market requests"}
    content = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content)


if __name__ == "__main__":
    main()
