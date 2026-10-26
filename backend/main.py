"""Local research API backed by immutable imported references and observations."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
<<<<<<< HEAD
import json
from hashlib import sha256

from fastapi import FastAPI, HTTPException
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from .domain import DEFAULT_AS_OF, DISCLAIMER, utc, normalize
from .store import SYNTHETIC_DB, connection, seed, save_run
from .analytics import comparisons, replay, WINDOW, THRESHOLD
from .pairs import PairRequest, load_pair, pair_history
from .backtest import BacktestRequest, simulate
from .ingestion import ingest


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset: str = "synthetic"
    csv_text: str = Field(max_length=5_000_000)
    as_of: str
    expected_dates: list[str] | None = None
    dry_run: bool = True
=======
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
from . import source_alerts
from .public_sources import catalog as source_catalog, ROOT as SOURCE_ROOT
from .source_workspace import snapshot as source_snapshot
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849


class IngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    csv_text: str = Field(max_length=5_000_000)
    manifest: ImportManifest
    registry: ReferenceRegistry
    dry_run: bool = True


def create_app(db_path: Path = SYNTHETIC_DB, real_db_path: Path = REAL_DB, alert_root: Path | None = None, *, real_only: bool = True, source_root: Path | None = None):
    paths = {"synthetic": Path(db_path), "real": Path(real_db_path)}
    notification_root = alert_root or Path(__file__).resolve().parents[1] / "data/notifications"
    source_root = source_root if source_root is not None else (SOURCE_ROOT if real_db_path == REAL_DB else Path(real_db_path).parent / "sources")
    if paths["synthetic"].resolve() == paths["real"].resolve():
        raise ValueError("Synthetic and real databases must be separate")

    @asynccontextmanager
    async def lifespan(app):
        if not real_only:
            seed(paths["synthetic"])
        yield

<<<<<<< HEAD
    app = FastAPI(title="GoldLens", version="0.3.0", lifespan=lifespan)
=======
    app = FastAPI(title="GoldLens", version="0.4.0", lifespan=lifespan)
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

    def dataset_path(dataset):
        if dataset not in paths:
            raise HTTPException(404, "Unknown dataset. No synthetic fallback.")
        if real_only and dataset != "real":
            raise HTTPException(422, "Only real market data is enabled. Synthetic data is restricted to tests.")
        return paths[dataset]

    def cutoff(value):
        return value or (datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if real_only else DEFAULT_AS_OF)

    def state(dataset, as_of):
        dataset_path(dataset)
        if dataset not in paths:
            raise HTTPException(404, "Unknown dataset. No synthetic fallback.")
        try:
            utc(as_of)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        try:
            if real_only and dataset == "real" and not paths["real"].exists():
                return source_snapshot(as_of, source_root)
            return research_snapshot(dataset_path(dataset), dataset, as_of)
        except ReferenceFailure as error:
            raise HTTPException(404 if error.code == "DATASET_UNAVAILABLE" else 409, f"{error.code}: {error}") from error
        except (ValueError, KeyError, sqlite3.DatabaseError) as error:
            raise HTTPException(409, "Stored dataset/reference validation failed; no substitute data") from error

    @app.get("/api/health")
    def health():
<<<<<<< HEAD
        with connection(db_path) as db:
            count = db.execute("SELECT count(*) FROM prices").fetchone()[0]
        return {"status": "ok", "app": "GoldLens", "version": "0.3.0", "storage": "SQLite", "datasets": {"synthetic": "ready", "real": "not configured"}, "observations": count}

    @app.post("/api/pair")
    def pair(request: PairRequest):
        dataset_check(request.dataset)
        try:
            with connection(db_path) as db:
                specs, histories = load_pair(db,request)
                result = pair_history(specs,histories,request)
                payload = json.dumps({"request":request.model_dump(),"result":result},sort_keys=True)
                key = sha256(payload.encode()).hexdigest()
                db.execute("INSERT OR IGNORE INTO signals VALUES (?,?,?)",(key,request.dataset,payload))
                return result
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

    @app.post("/backtest")
    @app.post("/api/backtest")
    def backtest(request: BacktestRequest):
        dataset_check(request.dataset)
        try:
            with connection(db_path) as db:
                specs, histories = load_pair(db,request)
                result = simulate(pair_history(specs,histories,request),request)
                save_run(db,result)
                return result
        except ValueError as error:
            raise HTTPException(422,str(error)) from error

    @app.post("/api/ingest")
    def csv_ingest(request: IngestRequest):
        dataset_check(request.dataset)
        cutoff(request.as_of)
        try:
            with connection(db_path) as db:
                specs = [dict(s) for s in db.execute("SELECT * FROM specs WHERE dataset=?",(request.dataset,))]
                return ingest(db,request.csv_text,specs,request.expected_dates,request.as_of,request.dry_run)
        except ValueError as error:
            raise HTTPException(422,str(error)) from error
=======
        if real_only:
            return {"status": "ok", "app": "GoldLens", "version": "0.4.0", "storage": "SQLite",
                    "datasets": {"real": "imported; validated on request" if paths["real"].exists() else "source quotes" if source_catalog(cutoff(None), source_root)["sources"] else "empty"}}
        current = state("synthetic", DEFAULT_AS_OF)
        return {"status": "ok", "app": "GoldLens", "version": "0.4.0", "dataset_version": "demo-v4", "storage": "SQLite",
                "datasets": {"synthetic": "ready", "real": "imported; validated on request" if paths["real"].exists() else "not configured"},
                "observations": sum(len(r) for r in current["histories"].values()), "blocked_observations": len(current["issues"])}

    @app.get("/api/sources")
    def sources(as_of: str | None = None):
        as_of = cutoff(as_of)
        try:
            utc(as_of)
            return source_catalog(as_of, source_root)
        except (ValueError, KeyError, OSError) as error:
            raise HTTPException(409, "Source archive unavailable or invalid") from error
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

    @app.get("/api/contracts")
    def contracts(dataset: str = "real" if real_only else "synthetic", as_of: str | None = None):
        as_of = cutoff(as_of)
        current = state(dataset, as_of)
        return {"dataset": dataset, "label": dataset.upper(), "as_of": as_of, "default_as_of": as_of,
                "contracts": current["contracts"], "issues": current["issues"], "disclaimer": disclaimer(dataset)}

    @app.get("/api/spec-evidence")
    def spec_evidence():
        return json.loads((Path(__file__).resolve().parents[1] / "docs/evidence/mcx-specs-2026-10-24.json").read_text())

    @app.get("/api/research")
    def research(contract_id: str, as_of: str, dataset: str = "real" if real_only else "synthetic"):
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
    def monitor(as_of: str, dataset: str = "real" if real_only else "synthetic", contract_id: str | None = None,
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
    def alert_catalog(dataset: str = Query(default="real" if real_only else "synthetic", pattern="^(synthetic|real)$"), as_of: str | None = None):
        as_of = cutoff(as_of)
<<<<<<< HEAD
        with connection(db_path) as db:
            result = db.execute("SELECT * FROM specs WHERE contract_id=? AND dataset=? AND available_at<=?", (contract_id, dataset, as_of)).fetchone()
            if result is None:
                raise HTTPException(404, "Contract specification not available at this cutoff")
            spec = dict(result)
            frame = pd.read_sql_query("SELECT * FROM prices WHERE contract_id=? AND dataset=? AND symbol=? AND expiry=? AND spec_version=? AND observed_at<=? AND available_at<=? AND trading_date<=? ORDER BY trading_date", db,
                                      params=(contract_id, dataset, spec["symbol"], spec["expiry"], spec["spec_version"], as_of, as_of, as_of[:10]))
        records = [{**r,"normalized_999_per_g":normalize(r["price"],spec)} for r in frame.to_dict(orient="records")]
        latest = records[-1] if records else None
        mean = round(float(frame.price.tail(5).mean()), 2) if records else None
        change = round((records[-1]["price"] / records[-2]["price"] - 1) * 100, 3) if len(records) >= 2 else None
        with connection(db_path) as db:
            compare, signals = comparisons(db, spec, as_of, latest)
        return {"dataset": dataset, "label": "SYNTHETIC", "as_of": as_of, "spec": spec,
                "prices": records, "latest": latest, "metrics": {"mean_5": mean, "change_pct": change, "count": len(records)},
                "compare": compare, "signals": signals, "signal_method": {"window": WINDOW, "threshold_pct": THRESHOLD},
                "backtest": replay(frame, spec), "disclaimer": DISCLAIMER}
=======
        if real_only and dataset == "real":
            return source_alerts.catalog(state(dataset, as_of))
        return alert_response(alerts.catalog, dataset_path(dataset), dataset, as_of)

    @app.get("/api/alerts/sessions")
    def alert_sessions(dataset: str = Query(default="real" if real_only else "synthetic", pattern="^(synthetic|real)$")):
        dataset_path(dataset)
        return alert_response(alerts.sessions, notification_root, dataset)

    @app.post("/api/alerts/sessions")
    def create_alert_session(request: alerts.NewSession):
        dataset_path(request.dataset)
        if real_only and request.dataset == "real":
            return alert_response(source_alerts.new_session, notification_root, request)
        return alert_response(alerts.new_session, dataset_path(request.dataset), notification_root, request)

    @app.post("/api/alerts/scan")
    def scan_alerts(request: alerts.ScanRequest):
        dataset_path(request.dataset)
        if real_only and request.dataset == "real":
            return alert_response(source_alerts.scan, notification_root, request, state(request.dataset, request.as_of))
        return alert_response(alerts.scan, dataset_path(request.dataset), notification_root, request)

    @app.get("/api/alerts/history")
    def alert_history(session_id: str, as_of: str,
                      dataset: str = Query(default="real" if real_only else "synthetic", pattern="^(synthetic|real)$")):
        dataset_path(dataset)
        return alert_response(alerts.history, notification_root, dataset, session_id, as_of)

    @app.post("/api/alerts/read")
    def read_alert(session_id: str, alert_id: str,
                   dataset: str = Query(default="real" if real_only else "synthetic", pattern="^(synthetic|real)$")):
        dataset_path(dataset)
        return alert_response(alerts.mark_read, notification_root, dataset, session_id, alert_id)

    def opportunity_response(operation, request):
        try:
            return operation(dataset_path(request.dataset), request)
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
        if any(s["normalization_status"] != "READY" for s in specs):
            raise HTTPException(422, "UNVERIFIED_TERMS: source quotes can be browsed, but this pair is not approved for normalized signals")
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
        dataset_path(request.manifest.dataset)
        try:
            if request.dry_run:
                return validate_csv(request.csv_text, request.manifest, request.registry)
            return import_csv(request.csv_text, request.manifest, request.registry, dataset_path(request.manifest.dataset))
        except (ValueError, sqlite3.DatabaseError) as error:
            raise HTTPException(422, f"{getattr(error, 'code', 'IMPORT_FAILED')}: {error}") from error

    @app.get("/api/spec-evidence")
    def spec_evidence():
        return json.loads((Path(__file__).resolve().parents[1] / "docs/evidence/mcx-specs-2026-10-24.json").read_text())
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

    return app


def disclaimer(dataset):
    return DISCLAIMER if dataset == "synthetic" else "Imported research data. Purity normalization does not remove delivery, location, costs, liquidity, execution or settlement uncertainty. No trade execution or guaranteed arbitrage."


app = create_app()
