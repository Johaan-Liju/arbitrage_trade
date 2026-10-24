"""Local research API backed by immutable imported references and observations."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .domain import DEFAULT_AS_OF, DISCLAIMER, utc
from .reference import ReferenceFailure, ReferenceRegistry
from .ingestion import ImportManifest, import_csv, validate_csv
from .synthetic_v4 import SYNTHETIC_DB, REAL_DB, seed
from .research import research_snapshot, pair_catalog, quote_summary, basis_differences
from .pairs import PairRequest, pair_history
from .backtest import BacktestRequest, simulate
from .store import connection, save_run


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(max_length=5_000_000)
    manifest: ImportManifest
    registry: ReferenceRegistry
    dry_run: bool = True


def create_app(db_path: Path = SYNTHETIC_DB, real_db_path: Path = REAL_DB):
    paths = {"synthetic": Path(db_path), "real": Path(real_db_path)}
    if paths["synthetic"].resolve() == paths["real"].resolve():
        raise ValueError("Synthetic and real databases must be separate")

    @asynccontextmanager
    async def lifespan(app):
        seed(paths["synthetic"])
        yield

    app = FastAPI(title="GoldLens", version="0.4.0", lifespan=lifespan)

    def state(dataset, as_of):
        if dataset not in paths:
            raise HTTPException(404, "Unknown dataset. No synthetic fallback.")
        try:
            utc(as_of)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        try:
            return research_snapshot(paths[dataset], dataset, as_of)
        except ReferenceFailure as error:
            raise HTTPException(404 if error.code == "DATASET_UNAVAILABLE" else 409, f"{error.code}: {error}") from error
        except (ValueError, KeyError, sqlite3.DatabaseError) as error:
            raise HTTPException(409, "Stored dataset/reference validation failed; no substitute data") from error

    @app.get("/api/health")
    def health():
        current = state("synthetic", DEFAULT_AS_OF)
        return {"status": "ok", "app": "GoldLens", "version": "0.4.0", "dataset_version": "demo-v4", "storage": "SQLite",
                "datasets": {"synthetic": "ready", "real": "imported; validated on request" if paths["real"].exists() else "not configured"},
                "observations": sum(len(r) for r in current["histories"].values()), "blocked_observations": len(current["issues"])}

    @app.get("/api/contracts")
    def contracts(dataset: str = "synthetic", as_of: str = DEFAULT_AS_OF):
        current = state(dataset, as_of)
        return {"dataset": dataset, "label": dataset.upper(), "as_of": as_of, "default_as_of": DEFAULT_AS_OF,
                "contracts": current["contracts"], "issues": current["issues"], "disclaimer": disclaimer(dataset)}

    @app.get("/api/research")
    def research(contract_id: str, as_of: str, dataset: str = "synthetic"):
        current = state(dataset, as_of)
        spec = next((s for s in current["contracts"] if s["contract_id"] == contract_id), None)
        if spec is None:
            raise HTTPException(404, "Exact contract/specification not available at this cutoff")
        rows = current["histories"][contract_id]
        metrics, events = quote_summary(rows, spec)
        return {"dataset": dataset, "label": dataset.upper(), "as_of": as_of, "spec": spec,
                "prices": rows, "latest": rows[-1] if rows else None, "metrics": metrics,
                "pairing": pair_catalog(current, spec), "issues": current["issues"],
                "backtest": {"method": "Point-in-time single-contract signal replay", "events": events},
                "disclaimer": disclaimer(dataset)}

    def validated_pair(request):
        current = state(request.dataset, request.as_of)
        specs, histories = [], []
        for identifier in (request.contract_a, request.contract_b):
            spec = next((s for s in current["contracts"] if s["contract_id"] == identifier), None)
            if spec is None:
                raise HTTPException(404, "Exact contract/specification not available at this cutoff")
            if spec["normalization_status"] != "READY":
                raise HTTPException(422, spec["normalization_reason"])
            specs.append(spec)
            histories.append(current["histories"][identifier])
        if specs[0]["expiry"] != specs[1]["expiry"]:
            raise HTTPException(422, "EXACT_EXPIRY_REQUIRED: identical exact expiry dates are required; no calendar substitution")
        if specs[0]["symbol"] == specs[1]["symbol"]:
            raise HTTPException(422, "Pair legs must be distinct instruments; specification versions remain separate")
        result = pair_history(specs, histories, request)
        result.update(pair_id=f"{request.dataset}|{request.contract_a}|{request.contract_b}",
                      basis_differences=basis_differences(*specs),
                      normalization_issues=[i for i in current["issues"] if i["contract_id"] in (request.contract_a, request.contract_b)])
        result["quality"]["calendar"] = "Explicit synthetic session calendar" if request.dataset == "synthetic" else "Imported verified session calendar"
        if request.dataset == "real":
            result["cautions"] = [c for c in result["cautions"] if not c.startswith("SYNTHETIC")]
        return result

    @app.post("/api/pair")
    def pair(request: PairRequest):
        return validated_pair(request)

    @app.post("/backtest")
    @app.post("/api/backtest")
    def backtest(request: BacktestRequest):
        pair = validated_pair(request)
        specs = [pair["spec_a"], pair["spec_b"]]
        if any(not s["safe_exit_date"] or not s["tender_start"] or not s["lot_grams"].is_integer() for s in specs):
            raise HTTPException(422, "Simulation requires explicit safe-exit/delivery dates and whole-gram lot sizes")
        for spec in specs:
            spec["lot_grams"] = int(spec["lot_grams"])
        result = simulate(pair, request)
        result["label"] = f"{request.dataset.upper()} HYPOTHETICAL SIMULATION"
        with connection(paths[request.dataset]) as db:
            save_run(db, result)
        return result

    @app.post("/api/ingest")
    def csv_ingest(request: IngestRequest):
        try:
            if request.dry_run:
                return validate_csv(request.csv_text, request.manifest, request.registry)
            return import_csv(request.csv_text, request.manifest, request.registry, paths[request.manifest.dataset])
        except (ValueError, sqlite3.DatabaseError) as error:
            raise HTTPException(422, f"{getattr(error, 'code', 'IMPORT_FAILED')}: {error}") from error

    @app.get("/api/spec-evidence")
    def spec_evidence():
        return json.loads((Path(__file__).resolve().parents[1] / "docs/evidence/mcx-specs-2026-10-24.json").read_text())

    return app


def disclaimer(dataset):
    return DISCLAIMER if dataset == "synthetic" else "Imported research data. Purity normalization does not remove delivery, location, costs, liquidity, execution or settlement uncertainty. No trade execution or guaranteed arbitrage."


app = create_app()
