"""Evaluate existing data only; write immutable, dataset-separated research reports."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.opportunity import OpportunityRequest
from backend.opportunity_evaluation import evaluate
from backend.synthetic_v4 import SYNTHETIC_DB, REAL_DB


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output-root", type=Path, default=ROOT / "artifacts/research")
    args = parser.parse_args()
    request = OpportunityRequest.model_validate_json(args.request.read_text(encoding="utf-8"))
    result = evaluate({"synthetic": SYNTHETIC_DB, "real": REAL_DB}[request.dataset], request)
    directory = args.output_root / request.dataset
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{result['report_id']}.json"
    content = json.dumps(result, indent=2, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise ValueError("Immutable report collision; existing output not overwritten")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(content)
    print(json.dumps({"report": str(path), "status": result["status"], "coverage": result["coverage"],
                      "folds": [{"start": f["test_start"], "end": f["test_end"], "training_examples": len(f["training_ids"])} for f in result["folds"]],
                      "held_out": result["held_out"]["metrics"], "comparison": result["held_out"]["comparison"]}, indent=2))


if __name__ == "__main__":
    main()
