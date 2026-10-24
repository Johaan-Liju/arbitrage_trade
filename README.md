# GoldLens

Explore gold contract prices, compare contracts with the same expiry, and test hypothetical paired trades in a local research workspace.

**Starts with synthetic data.** Demo prices and contract terms are invented. Real imports live separately and never fall back to synthetic records. This app does not execute trades or promise arbitrage.

## Run locally

Requires Node.js 22.13+ and Python 3.11+. From the project root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
npm.cmd run build
npm.cmd run local
```

Open [GoldLens](http://127.0.0.1:3000). Both services bind to loopback only; Ctrl+C stops the services started by the launcher. Stop existing services before starting another instance. After changing source, rebuild and restart to see the update.

For development, use two terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm.cmd run dev
```

## Explore the app

1. **Prices:** choose a dataset and exact contract expiry. View the price and history.
2. **Compare prices:** compare prices per gram at a common purity; review delivery and settlement differences.
3. **Price signals:** inspect an unusual price difference. Open Signal settings to adjust the rule.
4. **Paired backtest:** review costs and run a hypothetical simulation. Expand a trade to inspect its fills.

Change research time to explore what was known at a specific UTC cutoff. Only records both observed and available by that cutoff are included. Data labels, costs and execution limitations remain relevant throughout.

## Where things live

| Path | Purpose |
|---|---|
| `frontend/app/` | Next.js pages and shared styling |
| `frontend/components/` | Research shell, price view, pair workspace and UI primitives |
| `frontend/lib/` | Shared API requests and response types |
| `backend/main.py` | Active FastAPI entry point |
| `backend/normalization.py`, `pairs.py`, `backtest.py` | Financial calculations, signals and simulation |
| `backend/reference.py`, `store.py`, `ingestion.py` | Immutable references, SQLite storage and validated imports |
| `backend/tests/`, `frontend/scripts/` | Financial regression tests and browser checks |
| `scripts/` | Local launcher and health checks |
| `data/synthetic/`, `data/real/` | Separate local datasets; never interchangeable |
| `docs/` | Technical reference, assumptions and validation history |

The frontend displays backend results; financial calculations stay in Python. API requests flow through the local Next.js proxy to FastAPI and the selected SQLite dataset.

**Legacy reference:** `src/`, `dist/`, `test/`, `backend/legacy_api.py` and `backend/legacy_ingestion.py` are retained for earlier slices. Start current work in `frontend/` and `backend/main.py`. Legacy Node commands use the `:legacy` suffix.

## Validate

```powershell
npm.cmd test
npm.cmd --prefix frontend run lint
npm.cmd run check
npm.cmd run build
```

With both services running: `npm.cmd run health` and `npm.cmd run test:browser`.

See the [technical guide](docs/TECHNICAL_GUIDE.md) for API requests, imports, storage and extended checks; [research assumptions](docs/ASSUMPTIONS.md) and [paired backtest rules](docs/PAIRED_BACKTEST.md) for limitations; and the [build log](docs/BUILD_LOG.md) for actual validation results.
