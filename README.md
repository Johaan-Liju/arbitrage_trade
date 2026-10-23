# GoldLens

Local-first gold contract research with a Next.js/TypeScript/Tailwind/shadcn frontend and FastAPI/Pandas/SQLite backend. A dark workspace with Dashboard, Compare, Signals and Backtest. All business calculations come from the API.

**SYNTHETIC DATA ONLY.** GOLDM, GOLDTEN, GOLDGUINEA and GOLDPETAL use invented specifications, prices, volume and open interest. These are not verified exchange contracts or current market observations.

## Local setup (Windows PowerShell)

Requires Node.js 24 and Python 3.12. Commands below run from the repository root. Dependencies are installed locally; no global packages are required. Tested versions are recorded in `frontend/package-lock.json` and `backend/requirements.lock.txt`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
```

If npm reports `UNABLE_TO_VERIFY_LEAF_SIGNATURE` on this machine, set `$env:NODE_USE_SYSTEM_CA='1'` in that terminal and retry. Keep TLS verification enabled. Use `npm.cmd` to avoid PowerShell's `npm.ps1` execution-policy restriction; virtual-environment activation is unnecessary.

**Terminal 1 - backend:**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Startup creates `data/synthetic/goldlens-v1.sqlite3` if needed and verifies the deterministic fixtures on subsequent starts. SQLite or validation errors fail startup; there is no substitute dataset. API health: http://127.0.0.1:8000/api/health. Interactive API documentation: http://127.0.0.1:8000/docs (its Swagger assets may require internet).

**Terminal 2 - frontend:**

```powershell
npm.cmd --prefix frontend run dev
```

Open **http://127.0.0.1:3000**. Both services bind to IPv4 loopback. The browser calls `/api/*` on Next.js, which proxies to FastAPI at `127.0.0.1:8000`; no CORS or browser API-origin configuration is needed. Keep these ports together unless you also update `frontend/next.config.ts`. Stop each terminal with Ctrl+C.

For a production frontend build, stop the dev frontend and run:

```powershell
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend start
```

On macOS/Linux use `python3 -m venv .venv`, `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`, and `npm` instead of `npm.cmd`. Windows is the validated environment.

## Try the app

1. Select a contract and its exact expiry. Eight combinations are available, two for each symbol.
2. The default explicit UTC cutoff is `2026-10-23T18:00:00Z`. The API returns 39 observations for each contract.
3. Inspect the actual JSON with **Inspect API response** below the workspace.
4. Apply `2026-09-01T16:00:00Z`: the first price is observed but not yet available, so the page is empty. At `2026-09-01T16:05:00Z`, one observation becomes available.
5. Navigate to Compare for quote-weight normalization, Signals for prior-five-observation deviations, or Backtest for historical decision replay. Selection and cutoff carry across navigation.

The UI shows explicit loading, empty, API-error and retry states. API failures clear stale research results. Real data is never substituted with synthetic data.

## API and storage

- `GET /api/health`: SQLite readiness and dataset status.
- `GET /api/contracts?dataset=synthetic`: versioned contract catalog; accepts an optional `as_of` cutoff.
- `GET /api/research?contract_id=GOLDM%3A2026-11-20%3Ademo-v1&as_of=2026-10-23T18%3A00%3A00Z&dataset=synthetic`: prices, metrics, comparisons, signals and point-in-time replay. `as_of` is mandatory.
- Real/unknown datasets return 404; invalid timestamps return 422; unavailable specs return 404; valid cutoffs with no prices return 200 with empty results.

The generator in `backend/store.py` produces **8 specs and 312 observations**, covering 39 weekdays from 2026-09-01 through 2026-10-23. Weekdays are a demonstration convention, not a verified exchange calendar. Exact expiries are explicitly enumerated. There is no random seed or current-time dependency. You can recheck seeding with `.\.venv\Scripts\python.exe -m backend.store`.

Synthetic data lives only in `data/synthetic/goldlens-v1.sqlite3`; `data/real/goldlens.sqlite3` is reserved separately and is not opened or seeded. Databases are ignored by Git and regenerate from code. Specification updates/deletes are rejected by SQLite triggers; add a new version for changed terms. Price identity includes dataset, symbol, expiry and spec version, plus trading date, currency, unit, source, observed and available timestamps. Model validation and insert constraints enforce identity and chronology. This is a local read-only API, not tamper-proof storage against direct file edits.

Pandas filters both timestamps at the requested cutoff. Rolling means, changes, normalization and signals are calculated in Python. Each replay decision refilters its history at that observation's availability time and uses its referenced specification version. Frontend arithmetic is limited to chart positioning and numeric formatting.

## Validation

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm.cmd --prefix frontend run build
```

With both services running:

```powershell
.\.venv\Scripts\python.exe scripts/health-check.py
npm.cmd --prefix frontend run test:browser
```

Browser tests use installed Microsoft Edge with a fresh temporary profile, never a personal browser session. To use installed Chrome, set `$env:BROWSER_CHANNEL='chrome'`. No browser installation is required on the validated machine. Tests select each symbol, verify HTTP responses and rendered prices, navigate every view, exercise loading/empty/error/retry states, and check mobile overflow. Evidence is written to ignored `artifacts/` (screenshots and JSON). To rerun the initial integration gate, change into `frontend` and run `node scripts/selection-gate.mjs`.

The backend suite currently emits one upstream Starlette warning about future migration from httpx to httpx2; tests pass with the pinned dependencies.

## Scope and implementation

Backtest is a point-in-time **signal replay**, not a trading simulator. It reports no fills, P&L or profitability. Comparisons across expiries do not model carry, taxes, fees, delivery or settlement. Synthetic liquidity cannot establish executability. No real-data importer, exchange calendar validation, authentication, remote hosting or trade execution is implemented. Research results are never guaranteed arbitrage.

The app uses local assets and system fonts. UI source is owned locally under `frontend/components/ui`, following [shadcn manual installation](https://ui.shadcn.com/docs/installation/manual); routing and build follow [Next.js App Router](https://nextjs.org/docs/app/getting-started/installation). The original Node-only slice remains under `src`, `dist`, `test`, and the old JSON fixtures as legacy reference; it is not used by the new app. Legacy commands: `npm.cmd run start:legacy` (port 4310), `npm.cmd run test:legacy`.

See [project rules](AGENTS.md), [plan](docs/PLAN.md), and [actual build results](docs/BUILD_LOG.md).

REA tooling remains available through `.\rea.cmd --version`; it is independent of the app and depends on the previously installed npm cache entry. No REA setup changes are required to run GoldLens.
