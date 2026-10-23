from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
import pandas as pd

from .domain import DEFAULT_AS_OF, DISCLAIMER, utc
from .store import SYNTHETIC_DB, connection, seed
from .analytics import comparisons, replay, WINDOW, THRESHOLD


def create_app(db_path: Path = SYNTHETIC_DB):
    @asynccontextmanager
    async def lifespan(app):
        seed(db_path)
        yield

    app = FastAPI(title="GoldLens", version="0.2.0", lifespan=lifespan)

    def dataset_check(dataset):
        if dataset != "synthetic":
            raise HTTPException(404, "Real data is not configured. No synthetic fallback.")

    def cutoff(value):
        try:
            return utc(value)
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.get("/api/health")
    def health():
        with connection(db_path) as db:
            count = db.execute("SELECT count(*) FROM prices").fetchone()[0]
        return {"status": "ok", "app": "GoldLens", "version": "0.2.0", "storage": "SQLite", "datasets": {"synthetic": "ready", "real": "not configured"}, "observations": count}

    @app.get("/api/contracts")
    def contracts(dataset: str = "synthetic", as_of: str = DEFAULT_AS_OF):
        dataset_check(dataset)
        as_of = cutoff(as_of)
        with connection(db_path) as db:
            specs = [dict(s) for s in db.execute("SELECT * FROM specs WHERE dataset=? AND available_at<=? ORDER BY symbol,expiry", (dataset, as_of))]
        return {"dataset": dataset, "label": "SYNTHETIC", "as_of": as_of, "default_as_of": DEFAULT_AS_OF, "contracts": specs, "disclaimer": DISCLAIMER}

    @app.get("/api/research")
    def research(contract_id: str, as_of: str, dataset: str = "synthetic"):
        dataset_check(dataset)
        as_of = cutoff(as_of)
        with connection(db_path) as db:
            result = db.execute("SELECT * FROM specs WHERE contract_id=? AND dataset=? AND available_at<=?", (contract_id, dataset, as_of)).fetchone()
            if result is None:
                raise HTTPException(404, "Contract specification not available at this cutoff")
            spec = dict(result)
            frame = pd.read_sql_query("SELECT * FROM prices WHERE contract_id=? AND dataset=? AND symbol=? AND expiry=? AND spec_version=? AND observed_at<=? AND available_at<=? AND trading_date<=? ORDER BY trading_date", db,
                                      params=(contract_id, dataset, spec["symbol"], spec["expiry"], spec["spec_version"], as_of, as_of, as_of[:10]))
        records = frame.to_dict(orient="records")
        latest = records[-1] if records else None
        mean = round(float(frame.price.tail(5).mean()), 2) if records else None
        change = round((records[-1]["price"] / records[-2]["price"] - 1) * 100, 3) if len(records) >= 2 else None
        with connection(db_path) as db:
            compare, signals = comparisons(db, spec, as_of, latest)
        return {"dataset": dataset, "label": "SYNTHETIC", "as_of": as_of, "spec": spec,
                "prices": records, "latest": latest, "metrics": {"mean_5": mean, "change_pct": change, "count": len(records)},
                "compare": compare, "signals": signals, "signal_method": {"window": WINDOW, "threshold_pct": THRESHOLD},
                "backtest": replay(frame, spec), "disclaimer": DISCLAIMER}

    return app


app = create_app()
