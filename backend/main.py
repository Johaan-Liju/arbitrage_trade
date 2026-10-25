"""Local research API backed by immutable imported references and observations."""
from contextlib import asynccontextmanager
import json
from pathlib import Path
import sqlite3
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from .domain import DEFAULT_AS_OF, DISCLAIMER, utc
from .reference import ReferenceFailure, ReferenceRegistry
from .ingestion import ImportManifest, import_csv, validate_csv
from .synthetic_v4 import SYNTHETIC_DB, REAL_DB, seed
from .research import research_snapshot, pair_catalog, quote_summary, basis_differences
from .pairs import PairRequest, pair_history
from .monitor import monitor_view
from .opportunity import OpportunityRequest, predict as predict_opportunity
from .opportunity_evaluation import evaluate as evaluate_opportunity
from . import alerts


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(max_length=5_000_000)
    manifest: ImportManifest
    registry: ReferenceRegistry
    dry_run: bool = True


def create_app(db_path: Path = SYNTHETIC_DB, real_db_path: Path = REAL_DB, alert_root: Path | None = None):
    paths = {"synthetic": Path(db_path), "real": Path(real_db_path)}
    notification_root = alert_root or Path(__file__).resolve().parents[1] / "data/notifications"
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
                "backtest": {"method": "Single-contract signals retired; use explicitly matched pair rolling spread z-scores", "events": events},
                "disclaimer": disclaimer(dataset)}

    @app.get("/api/monitor")
    def monitor(as_of: str, dataset: str = "synthetic", contract_id: str | None = None,
                stale_after_hours: int = Query(default=72, ge=1, le=720)):
        current = state(dataset, as_of)
        try:
            return {**monitor_view(current, contract_id, stale_after_hours), "disclaimer": disclaimer(dataset)}
        except KeyError as error:
            raise HTTPException(404, str(error)) from error

    @app.post("/api/opportunities/evaluate")
    def opportunities(request: OpportunityRequest):
        return opportunity_response(evaluate_opportunity, request)

    @app.post("/api/opportunities/predict")
    def opportunity_prediction(request: OpportunityRequest):
        return opportunity_response(predict_opportunity, request)

    def alert_response(operation, *args):
        try:
            return operation(*args)
        except ReferenceFailure as error:
            raise HTTPException(404 if error.code in ("DATASET_UNAVAILABLE", "UNKNOWN_SESSION", "UNKNOWN_ALERT") else 409,
                                f"{error.code}: {error}") from error
        except (ValueError, KeyError, OSError, sqlite3.DatabaseError) as error:
            raise HTTPException(409, "Alert inputs or local storage are unavailable; no substitute data") from error

    @app.get("/api/alerts/catalog")
    def alert_catalog(dataset: str = Query(default="synthetic", pattern="^(synthetic|real)$"), as_of: str = DEFAULT_AS_OF):
        return alert_response(alerts.catalog, paths[dataset], dataset, as_of)

    @app.get("/api/alerts/sessions")
    def alert_sessions(dataset: str = Query(default="synthetic", pattern="^(synthetic|real)$")):
        return alert_response(alerts.sessions, notification_root, dataset)

    @app.post("/api/alerts/sessions")
    def create_alert_session(request: alerts.NewSession):
        return alert_response(alerts.new_session, paths[request.dataset], notification_root, request)

    @app.post("/api/alerts/scan")
    def scan_alerts(request: alerts.ScanRequest):
        return alert_response(alerts.scan, paths[request.dataset], notification_root, request)

    @app.get("/api/alerts/history")
    def alert_history(session_id: str, as_of: str,
                      dataset: str = Query(default="synthetic", pattern="^(synthetic|real)$")):
        return alert_response(alerts.history, notification_root, dataset, session_id, as_of)

    @app.post("/api/alerts/read")
    def read_alert(session_id: str, alert_id: str,
                   dataset: str = Query(default="synthetic", pattern="^(synthetic|real)$")):
        return alert_response(alerts.mark_read, notification_root, dataset, session_id, alert_id)

    def opportunity_response(operation, request):
        try:
            return operation(paths[request.dataset], request)
        except ReferenceFailure as error:
            raise HTTPException(404 if error.code in ("DATASET_UNAVAILABLE", "UNKNOWN_CONTRACT", "FUTURE_SPEC") else 422,
                                f"{error.code}: {error}") from error
        except (ValueError, KeyError, sqlite3.DatabaseError) as error:
            raise HTTPException(409, "Stored dataset/reference validation failed; no substitute data") from error

    def validated_pair(request):
        current = state(request.dataset, request.as_of)
        specs, histories = [], []
        for identifier in (request.contract_a, request.contract_b):
            spec = next((s for s in current["contracts"] if s["contract_id"] == identifier), None)
            if spec is None:
                raise HTTPException(404, "Exact contract/specification not available at this cutoff")
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
        issues = result["normalization_issues"]
        latest_day = result["latest"]["trading_date"] if result["latest"] else ""
        blocking = [i for i in issues if i["trading_date"] >= latest_day]
        if blocking:
            reason = "Unusable reference or observation: " + "; ".join(f"{i['trading_date']}: {i['code']}: {i['reason']}" for i in blocking)
            result.update(status="Insufficient data", reason=reason)
            if result["latest"]:
                result["latest"].update(status="Insufficient data", reason=reason, raw_pair_spread=None,
                    raw_pair_spread_decimal=None, prior_mean=None, prior_std=None, baseline=None,
                    expected_basis=None, difference=None, z_score=None, history_count=0, sample_count=0)
        result["quality"]["calendar"] = "Explicit synthetic session calendar" if request.dataset == "synthetic" else "Imported verified session calendar"
        if request.dataset == "real":
            result["cautions"] = [c for c in result["cautions"] if not c.startswith("SYNTHETIC")]
        return result

    @app.post("/api/pair")
    def pair(request: PairRequest):
        return validated_pair(request)

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
