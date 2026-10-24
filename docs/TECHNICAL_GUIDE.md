# GoldLens

Local-first gold contract research using Next.js / TypeScript / Tailwind / shadcn-style components and FastAPI / Pandas / SQLite. **Default dataset: SYNTHETIC.** Demo contracts, calendars, prices, volume and OI are invented. Official quotation/lot/purity evidence is documented separately; real analytics require separately imported, complete verified operational references and prices.

## Current contract research API (v4)

The active API uses `data/synthetic/goldlens-v4.sqlite3` and the new immutable `demo-v4` synthetic specifications. Earlier demo versions remain untouched. Invented purity, calendar, delivery and settlement terms are explicitly labelled SYNTHETIC. No real market records were fetched.

Python computes `quoted price / quotation grams * 999 / quoted purity per mille` with Decimal. Lot weight is displayed separately. Compare prices shows normalized values, exact-expiry partners, unmatched reasons and delivery/location/settlement differences. Every request filters prices and reference versions against its explicit as-of cutoff. Missing or unverified required terms block normalization.

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

1. Select GOLDTEN / **2026-11-20** / demo-v4 at UTC cutoff **2026-10-23T18:00:00Z**. The sticky SYNTHETIC banner remains visible while scrolling.
2. Compare with GOLDGUINEA / **2026-11-20**. Inspect quote grams, lot grams, quoted purity, normalized INR/gram at 999 purity, and delivery/settlement differences. Different exact expiries are listed as unsupported; no nearby-expiry substitution.
3. Price signals shows Investigate, No signal or Insufficient data with a reason. Change lookback, minimum prior observations and entry threshold; current spread is excluded from prior mean and sample standard deviation. A threshold of 100 demonstrates No signal; early cutoffs demonstrate warm-up.
4. Paired backtest uses the same spread z-scores. Configure exit threshold, maximum holding calendar days, whole-lot cap, adverse slippage and itemized per-leg assumed charges. Inspect later-observation fill times, whole lots, residual exposure, gross/net P&L and skipped orders. Open positions remain separate from realized results.
5. Apply `2026-09-01T16:00:00Z`: observed but not yet published records are excluded. Failed requests clear stale results. Hover either chart using the continuous plot area; its fixed readout stays stable between points.

See [DEMO_SCRIPT](DEMO_SCRIPT.md), [CONTRACT_MATRIX](CONTRACT_MATRIX.md), [ASSUMPTIONS](ASSUMPTIONS.md) and [paired-trade rules](PAIRED_BACKTEST.md). No machine learning, profitability guarantee or order execution is implemented.

## APIs

- `GET /api/health`: storage and dataset readiness.
- `GET /api/contracts?dataset=synthetic&as_of=2026-10-23T18:00:00Z`: exact contract/spec catalog.
- `GET /api/research?contract_id=GOLDTEN%3A2026-11-20%3Ademo-v4&as_of=2026-10-23T18%3A00%3A00Z`: dashboard prices and provenance. Single-contract signal events are retired; pair signals use the next endpoint.
- `GET /api/spec-evidence`: official-PDF research registry; numeric fields verified, operational chronology UNVERIFIED.
- `POST /api/pair`: paired normalized history, prior-only rolling spread z-scores, statuses, freshness, quality and exact-date caveats.
- `POST /backtest` or `POST /api/backtest`: hypothetical paired trades with persisted reproducible report and full ledger; open and realized results are separate.
- `POST /api/ingest`: strict CSV validator; `dry_run` defaults true. Entire invalid batches are rejected. Separate synthetic/real storage; real imports require complete verified references and calendars. No fallback.

Example pair request (JSON):

```json
{
  "contract_a": "GOLDTEN:2026-11-20:demo-v4",
  "contract_b": "GOLDGUINEA:2026-11-20:demo-v4",
  "dataset": "synthetic",
  "as_of": "2026-10-23T18:00:00Z",
  "lookback": 10,
  "min_observations": 5,
  "entry_z": 2.5
}
```

For backtesting add `exit_z: 0.5`, `max_holding_days: 10`, `max_lots: 100`, `fee_bps: 5`, `slippage_bps: 10`, and optional `costs_a` / `costs_b` objects: `{ "exchange_bps": 0, "tax_bps": 0, "other_bps": 0, "fixed_inr": 0 }`. All charges and fills are hypothetical assumptions. Each component applies to each leg on entry and exit. Zero means omitted. The active API requires identical exact expiries even if legacy `allow_calendar` is supplied. Other guards: `max_age_days`, `min_volume`, `min_oi`, `max_participation`, `initial_capital`. Invalid values are rejected. [Local OpenAPI JSON](http://127.0.0.1:8000/openapi.json) documents request fields.

The v4 import request uses `csv_text`, `manifest`, `registry` and `dry_run`. Exact CSV columns in order:

```text
dataset,instrument,expiry,trading_date,spec_id,price,currency,price_unit,quotation_grams,quote_purity_per_mille,volume,open_interest,session,source_url,observed_at,available_at
```

The registry provides immutable specification, exact listing and explicit session calendar versions. Prices must reference those versions, use INR and their specified quotation unit/purity, and satisfy both observation and availability cutoffs. Unknown contracts, duplicate keys, missing dates against the manifest/calendar, wrong units and unusable specifications reject the entire import.

## Storage and verification

Canonical v4 records: reference_versions, observations and batches, with immutable compatibility views for specs/prices and persisted backtest_runs/trades. The schema supports explicit version-partitioned contracts; `specs` and `prices` are read compatibility views. Prices/specs/contracts are immutable. The deterministic seed creates 8 contracts, 4 spec versions (one per instrument) and 312 observations across 39 synthetic weekdays. Re-running verifies published fixtures and never updates them.

Current data: `data/synthetic/goldlens-v4.sqlite3`. Separate real imports: `data/real/imports-v4.sqlite3` (never seeded). Prior databases are retained; v4 does not mutate legacy terms. Databases are Git-ignored and regenerate locally. Real contract-month scope must never be treated as an exact expiry/effective date. All business calculations run in the backend; frontend arithmetic is chart geometry/formatting only.

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm.cmd --prefix frontend run lint
npm.cmd --prefix frontend run typecheck
npm.cmd --prefix frontend run build
```

With both services running:

```powershell
.\.venv\Scripts\python.exe scripts/health-check.py
npm.cmd --prefix frontend run test:browser
Push-Location frontend
node scripts/spread-signal-check.mjs
node scripts/paired-backtest-check.mjs
node scripts/audit-check.mjs
Pop-Location
```

For isolated test ports, set `GOLDLENS_TEST_URL` and `GOLDLENS_TEST_API` to loopback URLs before these checks. Browser QA uses installed Edge with a fresh test profile; set `BROWSER_CHANNEL=chrome` to use installed Chrome. It never inspects personal tabs or profiles. Screenshots and reports go to ignored `artifacts/`. The upstream Starlette httpx deprecation warning is recorded separately from failures.

## Verified scope versus unsupported claims

| Feature | Boundary |
|---|---|
| Quote/lot/purity normalization and exact contract provenance | Not an executable spread |
| Prior-only spread mean, sample standard deviation, z-score and explicit reasons | No predictive/profitability claim |
| Integer lot matching, later-observation replay, per-leg expenses | Hypothetical settlements, not actual fills |
| Mark-to-market, drawdown and reproducible ledger | No required margin, funding or tax completeness |
| Official original-PDF field evidence | Exact historical spec/calendar chronology remains unverified |
| Local offline synthetic workflow | No real feed, deployment or execution |

See [BUILD_LOG](BUILD_LOG.md) for exact commands and observed outcomes. Original Node-only code under `src`, `dist`, `test` remains legacy reference (`npm.cmd run test:legacy`). No deployment or push is performed.
