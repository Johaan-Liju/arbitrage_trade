# GoldLens

Local-first gold contract research using Next.js / TypeScript / Tailwind / shadcn-style components and FastAPI / Pandas / SQLite. **SYNTHETIC DATA ONLY.** Exact contracts, calendars, prices, volume and OI are invented. Official quotation/lot/purity evidence is documented separately; real analytics remain blocked.

## Current contract research API (v4)

The active API uses `data/synthetic/goldlens-v4.sqlite3` and the new immutable `demo-v4` synthetic specifications. Earlier demo versions remain untouched. Invented purity, calendar, delivery and settlement terms are explicitly labelled SYNTHETIC. No real market records were fetched.

Python computes `quoted price / quotation grams ? 999 / quoted purity per mille` with Decimal. Lot weight is displayed separately. Compare prices shows normalized values, exact-expiry partners, unmatched reasons and delivery/location/settlement differences. Every request filters prices and reference versions against its explicit as-of cutoff. Missing or unverified required terms block normalization.

Real imports use a separate `data/real/imports-v4.sqlite3` file, with no synthetic fallback. `POST /api/ingest` accepts `{ "csv_text": "...", "manifest": {...}, "registry": {...}, "dry_run": true }`; set `dry_run` false only for a validated reviewed local import. The registry supplies immutable specification, explicit listing and calendar versions. CLI validation: `.\.venv\Scripts\python.exe -m backend.ingestion validate records.csv --manifest manifest.json --registry registry.json`. Existing database versions are not migrated silently. The preserved `backend.legacy_api` and its tests cover the earlier v3 behavior; production uses `backend.main`.

After updating source, rebuild and restart both local services so the API and frontend use the same version. `/api/health` should report `0.4.0` and `demo-v4`.

## Start locally (Windows PowerShell)

Use Node.js 22.13+ (validated 22.16.0) and Python 3.11+ (validated 3.11.9). From this repository root, install project-local dependencies once:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.lock.txt
npm.cmd --prefix frontend ci
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
