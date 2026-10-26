# GoldLens

<<<<<<< HEAD
Local-first gold contract research using Next.js / TypeScript / Tailwind / shadcn-style components and FastAPI / Pandas / SQLite. **SYNTHETIC DATA ONLY.** Exact contracts, calendars, prices, volume and OI are invented. Official quotation/lot/purity evidence is documented separately; real analytics remain blocked.

## Start locally (Windows PowerShell)

Use Node.js 22.13+ (validated 22.16.0) and Python 3.11+ (validated 3.11.9). From this repository root, install project-local dependencies once:
=======
Monitor gold contract prices and inspect matched-pair research alerts in a local workspace.

**Starts with synthetic data.** Demo prices and contract terms are invented. Real imports live separately and never fall back to synthetic records. This app does not execute trades or promise arbitrage.

## Run locally

Requires Node.js 22.13+ and Python 3.11+. From the project root in PowerShell:
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
<<<<<<< HEAD
npm.cmd --prefix frontend run build
```

Then start both services with one command:

```powershell
npm.cmd run local
```

Open [GoldLens](http://127.0.0.1:3000). Both processes bind only to `127.0.0.1`; the frontend proxies `/api/*` to port 8000. Ctrl+C stops owned services. The launcher refuses occupied ports. Installation needs internet; the built app, seeded workflow and tests need no market connection. No credentials are used.

For development, run these in two terminals:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
npm.cmd --prefix frontend run dev
```

Stop development before building/starting production on the same ports. `npm.cmd` avoids the PowerShell npm.ps1 execution-policy restriction. No global installation is needed. On other systems use `.venv/bin/python` and `npm`; only Windows was validated.

## Three-minute workflow

For hosted service configuration, see [Render setup](docs/RENDER_SETUP.md). Local startup remains loopback-only. The optional server-side `BACKEND_URL` sets the frontend proxy origin and requires a frontend rebuild when changed.

1. Select GOLDTEN · **2026-11-24** · demo-v3; default UTC cutoff **2026-10-23T18:00:00Z**.
2. Compare with GOLDGUINEA · **2026-11-27**. Inspect normalized prices, spread, prior-only expected basis and z-score bands. Read the calendar mismatch caveat.
3. Signals explains INVESTIGATE with an explicit reason, prior statistics, volume/OI and freshness. Expand the observation ledger and Quality checks.
4. Backtest first rejects a calendar mismatch by default. Explicitly acknowledge different expiries to run the hypothetical settlement simulation. Inspect both legs, subsequent fill dates, notional, costs, net P&L and equity/drawdown. A 100 entry threshold demonstrates no trades.
5. Apply an early cutoff such as `2026-09-01T16:00:00Z`: observed but not yet available records are excluded. Errors clear stale results.

See [DEMO_SCRIPT](docs/DEMO_SCRIPT.md), [CONTRACT_MATRIX](docs/CONTRACT_MATRIX.md) and [ASSUMPTIONS](docs/ASSUMPTIONS.md). Normalization is a comparison convention, not an executable arbitrage price. No orders are sent.

## APIs

- `GET /api/health`: storage and dataset readiness.
- `GET /api/contracts?dataset=synthetic&as_of=2026-10-23T18:00:00Z`: exact contract/spec catalog.
- `GET /api/research?contract_id=GOLDTEN%3A2026-11-24%3Ademo-v3&as_of=2026-10-23T18%3A00%3A00Z`: dashboard prices and provenance. Legacy descriptive single-series replay remains in this response for compatibility; paired financial analysis uses the next endpoints.
- `GET /api/spec-evidence`: official-PDF research registry; numeric fields verified, operational chronology UNVERIFIED.
- `POST /api/pair`: paired normalized history, residual statistics, statuses, freshness, quality and exact-date caveats.
- `POST /backtest` or `POST /api/backtest`: replay with persisted reproducible report and trade ledger.
- `POST /api/ingest`: strict CSV validator; `dry_run` defaults true. Entire invalid batches are rejected. Synthetic imports only; real requests return 404. No fallback.

Example pair request (JSON):

```json
{
  "contract_a": "GOLDTEN:2026-11-24:demo-v3",
  "contract_b": "GOLDGUINEA:2026-11-27:demo-v3",
  "dataset": "synthetic",
  "as_of": "2026-10-23T18:00:00Z",
  "lookback": 10,
  "min_observations": 5,
  "entry_z": 2.5
}
```

For backtesting add `exit_z: 0.5`, `fee_bps: 5`, `slippage_bps: 10` and `allow_calendar: true` only when consciously accepting the calendar difference. Other API controls: `max_age_days`, `min_volume`, `min_oi`, `max_lots`, `max_participation`, `initial_capital`. Invalid values are rejected. [Local OpenAPI JSON](http://127.0.0.1:8000/openapi.json) is offline; Swagger `/docs` may load external assets.

CSV request has `csv_text`, `dataset`, explicit `as_of`, optional `expected_dates` (exact session list), and `dry_run`. Exact columns, with no extras or aliases:

```text
contract_id,dataset,symbol,expiry,spec_version,trading_date,price,open,high,low,close,volume,open_interest,currency,unit,source,observed_at,available_at,ingested_at
```

`price` is settlement, `currency=INR`, `unit=quote`, timestamps are `YYYY-MM-DDTHH:MM:SSZ`. Unknown contracts, duplicate keys, missing data, impossible dates/ranges, wrong units and stale specs reject. Large finite values are flagged; they are not silently corrected. Without an explicit session list, missing dates cannot be distinguished from holidays and the validator says so.

## Storage and verification

Canonical tables: instruments, contract_spec_versions, contracts, daily_prices, signals, backtest_runs, trades. The schema supports explicit version-partitioned contracts; `specs` and `prices` are read compatibility views. Prices/specs/contracts are immutable. The deterministic seed creates 8 contracts, 4 spec versions (one per instrument) and 312 observations across 39 synthetic weekdays. Re-running verifies published fixtures and never updates them.

Current data: `data/synthetic/goldlens-v3.sqlite3`. Reserved real data: `data/real/goldlens.sqlite3` (never seeded). Prior databases are retained; v3 does not mutate legacy terms. Databases are Git-ignored and regenerate locally. Real contract-month scope must never be treated as an exact expiry/effective date. All business calculations run in the backend; frontend arithmetic is chart geometry/formatting only.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
.\.venv\Scripts\python.exe -m backend.demo_gates
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

With both services running:

```powershell
.\.venv\Scripts\python.exe scripts/health-check.py
npm.cmd --prefix frontend run test:browser
```

Browser QA uses installed Edge with a fresh test profile; set `BROWSER_CHANNEL=chrome` to use installed Chrome. It never inspects personal tabs or profiles. Screenshots and reports go to ignored `artifacts/`. The upstream Starlette httpx deprecation warning is recorded separately from failures.

## Verified scope versus unsupported claims

| Feature | Boundary |
|---|---|
| Quote/lot/purity normalization and exact contract provenance | Not an executable spread |
| Prior-only expected basis, residual z-score and explicit reasons | No predictive/profitability claim |
| Integer lot matching, later-observation replay, per-leg expenses | Hypothetical settlements, not actual fills |
| Mark-to-market, drawdown and reproducible ledger | No required margin, funding or tax completeness |
| Official original-PDF field evidence | Exact historical spec/calendar chronology remains unverified |
| Local offline synthetic workflow | No real feed, deployment or execution |

See [BUILD_LOG](docs/BUILD_LOG.md) for exact commands and observed outcomes. Original Node-only code under `src`, `dist`, `test` remains legacy reference (`npm.cmd run test:legacy`). No deployment or push is performed.
=======
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

1. **Monitor** (`/`): select a symbol, exact expiry and specification version. Maintain a dataset-specific watchlist; inspect prices, changes, aligned spreads, source timestamps, freshness and the selected contract chart. Freshness is measured at the explicit cutoff with a configurable threshold. Volume and open interest appear only when supplied by the source.
2. **Alerts** (`/alerts`): in-app paper notifications from the evaluated `opportunity-v1` model for one exact-expiry pair. Each alert shows contracts, exact expiry, signal time, horizon, model version, supporting observations, estimated costs, and liquidity and settlement uncertainty, with a history of later paper outcomes. Thresholds, freshness, cooldown and lifetime are configurable per paper session.

Alerts are scanned manually at an explicit cutoff; there is no background polling, no probability display (calibration is unevaluated) and no trade execution. Compare, Signals and Backtest routes have been removed. The active API no longer exposes simulations. Offline simulation code and its regression tests remain as historical research reference.

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

See [Monitor and Alerts scope](docs/MONITOR_ALERTS.md) for the inspection, component reuse, backend requirements and retained safeguards.

Before predictive work, review the [opportunity research specification](docs/OPPORTUNITY_RESEARCH_SPEC.md) and its repository data audit. Current history is synthetic and does not support credible market forecast evaluation.

The [deterministic opportunity evaluation](docs/OPPORTUNITY_EVALUATION.md) documents the backend prediction/evaluation endpoints, leakage safeguards, estimated costs and experimental held-out results.

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
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
