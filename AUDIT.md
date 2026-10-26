# GoldLens repository audit

**Date:** 2026-10-24 · **Commit audited:** `8ac8885` ("GoldLens runnable MVP"). The working tree had one uncommitted change, `docs/BUILD_LOG.md`.
**Scope:** frontend, backend, database, data pipeline, backtesting engine, tests, legacy code.
**Code changes made during this audit:** none. No critical runtime failure was found, so no fix was needed. This audit adds only `AUDIT.md` and two read-only probe scripts in `audit/`.

## Bottom line

GoldLens is a working **synthetic-data research demo**. Every test, build and startup check I ran passed. Independent probes found no look-ahead bias and no mixing of contract expiries. **No real MCX historical data is loaded.** The app has no path to load any: real-data requests are deliberately blocked. Every price, volume, open-interest figure, expiry, calendar and backtest result is invented. The single profitable demo trade (net ₹3,792.03) comes from a price spike the fixture generator injects on purpose.

## How results were obtained

| Item | Value |
|---|---|
| Where I ran it | Clean copy of the repository in a Linux container: fresh `pip install -r backend/requirements.lock.txt`, fresh `npm ci`, database deleted and re-seeded |
| Python / Node | 3.13.17 / 22.23.4. README validates 3.11.9 / 22.16.0 on Windows. |
| Browser test | Run with Playwright Chromium. The script defaults to installed Edge (`msedge`), which isn't available on Linux, so the channel was overridden in a temporary copy of the script only. |
| On your PC | Read-only checks: git log/status, file inventory and database contents. Your Windows `.venv` cannot run in the Linux shell, so the Windows commands below were not re-executed by me. |

Windows commands assume PowerShell at the repo root, after the README install steps. Wherever a command needs both services running, start them first with `npm.cmd run local`.

## Checklist

| # | Check | Result | Evidence (observed) | Reproduce (Windows) |
|---|---|---|---|---|
| 1 | Backend unit/integration tests | **PASS** | 61 passed, 0 failed (1 upstream Starlette/httpx deprecation warning) | `.\.venv\Scripts\python.exe -m pytest backend/tests -q` |
| 2 | Demo gates (anomaly, accepted, rejected, no-trade) | **PASS** | anomaly 0 → NO_SIGNAL (z 1.353); anomaly 140 → INVESTIGATE (z 10.391); accepted 1 trade, net 3792.03; calendar-rejected 0 trades; threshold 100 → 0 trades | `.\.venv\Scripts\python.exe -m backend.demo_gates` |
| 3 | Frontend lint | **PASS** | exit 0, zero warnings (`--max-warnings=0`) | `npm.cmd --prefix frontend run lint` |
| 4 | Frontend typecheck | **PASS** | `tsc --noEmit` exit 0 | `npm.cmd --prefix frontend run typecheck` |
| 5 | Frontend production build | **PASS** | exit 0. Routes `/`, `/compare`, `/signals`, `/backtest` prerendered. No build warnings. | `npm.cmd --prefix frontend run build` |
| 6 | Dependencies install from lockfiles | **PASS** | `npm ci` and `pip install -r backend/requirements.lock.txt` succeeded from scratch. Nothing missing at runtime. | README install block |
| 7 | Backend startup, fresh database | **PASS** | Database deleted → seeds 8 contracts / 4 spec versions / 312 rows. Health returns 200. | delete `data\synthetic\goldlens-v3.sqlite3`, then `npm.cmd run local` |
| 8 | Backend startup, your existing database | **PASS** | Your `goldlens-v3.sqlite3` passes the seed's verification on startup. Health returns 200, 312 rows. | `npm.cmd run local` |
| 9 | One-command launcher | **PASS** | `scripts/start-local.py` starts both services on 127.0.0.1. With ports busy it refuses (`Port 8000 is occupied… no process was killed`, exit 1). | `npm.cmd run local` (run twice to see the refusal) |
| 10 | Smoke health check | **PASS** | 4/4: backend 200, frontend proxy 200, proxied research 39 rows labelled SYNTHETIC, real dataset 404 | `.\.venv\Scripts\python.exe scripts/health-check.py` |
| 11 | Browser end-to-end workflow | **PASS** | 16/16 PASS (all four contracts, pages, calendar rejection then accepted trade, no-trade, empty/error/loading states, 390 px mobile, no JS errors) | `npm.cmd --prefix frontend run test:browser` |
| 12 | API contract and edge cases | **PASS** | 27/27: cutoffs, malformed timestamp 422, unknown expiry 404, real dataset 404 on every endpoint, invalid parameters 422, ingest dry-run/duplicate/future-availability, `/backtest` alias, proxy POST | `.\.venv\Scripts\python.exe audit\api_probe.py` |
| 13 | Frontend ↔ backend connections | **PASS** | The frontend calls exactly 5 endpoints (`health`, `contracts`, `research`, `pair`, `backtest`). All exist and answer through the `/api/*` proxy. | covered by #10–#12 |
| 14 | Runtime errors | **PASS** | No errors or tracebacks in the backend or Next.js logs during all runs. No uncaught browser errors. | inspect the terminal while running #11–#12 |
| 15 | Legacy Node slice | **PASS** | `node --test`: 5/5. Legacy server serves `/`, `/api/health`, `/api/snapshot`. | `npm.cmd run test:legacy` and `npm.cmd run start:legacy` |
| 16 | Charts use backend data | **PASS** | All 6 charts plot API fields only; the frontend does geometry and formatting, no financial arithmetic (see chart table) | code review of `frontend/components/*.tsx` |
| 17 | Synthetic data explicitly labelled | **PASS** | "SYNTHETIC DATA" banner on every page. Every API response carries `label`/`dataset`. Dashboard chart and ledger say synthetic. *Note:* the five pair/backtest charts rely on the page banner and have no per-chart badge. | open any page |
| 18 | Real MCX historical data loaded | **FAIL** | No `data/real/` directory on your PC. The database holds only `dataset=synthetic` (312 rows), source `GoldLens deterministic generator v3`, evidence URL `synthetic://goldlens/demo-v3`. No CSV, bhavcopy or other data files exist in the repo. | `.\.venv\Scripts\python.exe -c "import sqlite3;d=sqlite3.connect('data/synthetic/goldlens-v3.sqlite3');print(d.execute('select dataset,source,count(*) from daily_prices group by 1,2').fetchall())"` and `Test-Path data\real` |
| 19 | Real-data pipeline exists | **FAIL** (by design) | No MCX/bhavcopy adapter. Real dataset is rejected with 404 on every endpoint, including ingest. `normalize()` refuses UNVERIFIED real specs. | `audit\api_probe.py` (the "real … -> 404" lines) |
| 20 | No look-ahead: signals | **PASS** | 144 future-perturbation checks (24 same-month contract pairs × 6 cutoffs): changing every price and volume after the cutoff never changed any signal event on or before it. Late-arriving rows are invisible before their `available_at`. | `.\.venv\Scripts\python.exe audit\lookahead_probe.py` |
| 21 | No look-ahead: backtest | **PASS** | 144 backtest checks: equity, entries, rejections and entry/exit **decisions** on or before the cutoff are unchanged by future data. Across 488 trades over a 15-setting parameter grid, every fill is dated after its signal and observed after the signal became available, every exit is before the safe-exit date, and all four cost items are charged. | same as #20 |
| 22 | Probe sensitivity (does #20–#21 catch bias?) | **PASS** | Two deliberately planted bugs were both detected: (a) basis computed from the full series; (b) entering on the next day's signal. (A first version of the probe missed (b). It was fixed to compare decision dates before relying on it.) | see "Probe validation" below |
| 23 | No mixing of contract expiries | **PASS** | Each contract's rows carry one symbol/expiry/spec. The loader returns only the exact contract for all 56 ordered pairs. Pairs are joined on identical trading dates. Same-symbol different-expiry pairs (e.g. GOLDTEN Nov/Dec) are flagged `CALENDAR_BASIS_DIFFERENCE`. Injecting a Dec row into a Nov series raises an error. | same as #20 |
| 24 | Spec numbers match MCX PDFs | **PARTIAL** | Quote grams, lot and purity in `docs/CONTRACT_MATRIX.md` cite original MCX PDFs. Not re-checked against the PDFs in this audit. Exact effective dates, listed expiries, tender dates and holiday calendars are recorded as UNVERIFIED. | open the PDF links in `docs/CONTRACT_MATRIX.md` |
| 25 | Cross-platform scripts | **PARTIAL** | Root `npm` scripts `test`, `health` and `local` hard-code `.venv\Scripts\python.exe` (Windows only). The browser test defaults to Edge. `rea.cmd` points to a machine-specific npx cache path (dev tooling, not app runtime). | n/a |
| 26 | Cost / risk model | **PARTIAL** | Fees (5 bps) and slippage (10 bps) are charged per leg at entry and exit. GST, transaction taxes, margin, funding, delivery and tender are not modelled (documented). Fills use daily settlements as a proxy. | `docs/ASSUMPTIONS.md` |
| 27 | Data ingestion | **PARTIAL** | Strict CSV validator works through the API (dry-run by default, atomic, synthetic only). No UI. The `source` field is free text, not authenticated. | `audit\api_probe.py` (the ingest lines) |

## Completed features

| Area | Feature | Status |
|---|---|---|
| Database | SQLite schema: instruments, versioned specs, contracts, daily prices, signals, backtest runs, trades. Database triggers block any update or delete of published specs and prices; price rows must match an available spec. | Complete |
| Data | Deterministic synthetic seed: 4 instruments × 2 exact expiries = 8 contracts, 39 weekdays, 312 rows | Complete (synthetic) |
| Data pipeline | Strict CSV ingest `POST /api/ingest`: exact schema, duplicate/future/calendar checks, whole-batch rejection | Complete (API only, synthetic only) |
| Backend | `/api/health`, `/api/contracts`, `/api/research`, `/api/pair`, `/api/backtest` (+ `/backtest`), `/api/spec-evidence` | Complete |
| Normalization | quote ÷ quote grams × 0.999 ÷ purity, with originals and provenance kept | Complete |
| Signals | Rolling prior-only basis and z-score; statuses INVESTIGATE / NO_SIGNAL / INSUFFICIENT_DATA / REJECTED, each with a reason | Complete |
| Backtest | Two-leg integer-lot matching (e.g. 4 TEN × 10 g vs 5 GUINEA × 8 g), fills on later observations, per-leg costs, safe exit, mark-to-market equity and drawdown, trade ledger, rejection list, persisted reproducible run IDs | Complete (hypothetical fills) |
| Frontend | Dashboard, Compare, Signals and Backtest pages, as-of cutoff control, loading/empty/error/retry states, mobile layout | Complete |
| QA | pytest suite, demo gates, browser E2E, health check, launcher | Complete |

## Mocked, hardcoded or incomplete

| Item | Where | Detail |
|---|---|---|
| **All market data** | `backend/store.py` `fixtures()` | Prices are formula-generated (linear trend + sine + cosine). Open = close = settlement, high/low = ±0.2%. Volume and OI come from arithmetic formulas. |
| **Injected anomaly drives the demo result** | `store.py`: GOLDTEN `i in (24, 25, 38)`, +₹140/g | The only INVESTIGATE signals, and the single ₹3,792.03 trade, come from this planted spike. With anomaly 0 there is no signal. |
| Trading calendar | `store.py` | Plain weekdays from 2026-09-01. No MCX holidays or special sessions. |
| Expiry, tender and safe-exit dates | `store.py` | Invented (e.g. GOLDTEN 2026-11-24). Tender = expiry − 4 days, safe exit = expiry − 7 days. Real MCX rules (month-end or 5th) are not applied. |
| Timestamps | `store.py` | observed 16:00Z, available 16:05Z, every day |
| Default as-of cutoff | `backend/domain.py` `DEFAULT_AS_OF = 2026-10-23T18:00:00Z` | Hardcoded |
| Dataset selector | `frontend/components/research-shell.tsx` | Frontend always requests `dataset: "synthetic"`. There is no real/synthetic switch. |
| Default contract | `research-shell.tsx` | GOLDM is preselected |
| Cost and risk defaults | `backend/backtest.py`, `pairs.py` | fees 5 bps, slippage 10 bps, ₹10,00,000 reference capital, min volume/OI 100, 1% participation, 4-day max gap. Illustrative values, not real broker or exchange costs. |
| API-only controls | `BacktestRequest` | `max_age_days`, `min_volume`, `min_oi`, `max_lots`, `max_participation`, `initial_capital` have no UI |
| Unused legacy payload | `/api/research` → `compare`, `signals`, `backtest` (single-series replay in `analytics.py`) | Computed on every request but never rendered by the frontend |
| Legacy Node app | `src/`, `dist/`, `test/`, `data/synthetic/*.json` | Separate v0.1 demo (USD/troy ounce `DEMO-GOLD-202612`), unrelated to GoldLens v0.3 |
| Real data | `data/real/` (absent), `CONTRACT_MATRIX.md` | Not implemented; blocked on unverified chronology and calendars |
| Pair chart x-axis | `pair-workspace.tsx` `Chart` | Spaced by index, not by date. Days with one leg missing are left out of the chart (listed under quality instead). No effect on current data, which has no gaps. |

## Charts and their data source

| Chart | Component | Data plotted | Source | Synthetic label |
|---|---|---|---|---|
| Price history | `research-views.tsx` `PriceChart` | `prices[].price` | `GET /api/research` | Card text "Observed price · synthetic", aria-label "Synthetic price history", page banner |
| Normalized price history | `pair-workspace.tsx` `Chart` | `history[].normalized_a/_b` | `POST /api/pair` | page banner |
| Spread and expected basis | same | `raw_pair_spread`, `expected_basis`, `residual_spread` | `POST /api/pair` | page banner |
| Z-score and bands | same | `z_score`, `upper_z`, `lower_z` | `POST /api/pair` | page banner |
| Equity curve | same | `equity_curve[].equity` | `POST /api/backtest` | page banner + "SYNTHETIC SIMULATION" run label |

No chart uses hard-coded or client-generated series.

## Probe validation

To show that #20–#21 can detect bias, I planted two bugs in a throwaway copy of `backend/` and re-ran `audit/lookahead_probe.py`:

1. `pairs.py`: expected basis taken from the mean of the **whole** series. **Detected** (signal events changed when future data was perturbed).
2. `backtest.py`: entry decided from the **next** day's signal. **Detected** ("signal decisions <= cutoff changed by future prices").

A third change, removing the backtest's "fill must be later than signal" guard, was **not** detected. That is expected: the loop already creates an order only after that day's fill step, so same-day fills can't happen even without the guard. The guard is a backup check.

## Exact commands I ran (Linux container)

```bash
pip install --break-system-packages -r backend/requirements.lock.txt
rm -f data/synthetic/*.sqlite3*
python3 -m pytest backend/tests -q                 # 61 passed
python3 -m backend.demo_gates                       # output as in checklist #2
node --test                                         # 5 passed
cd frontend && npm ci && npm run lint && npm run typecheck && npm run build && cd ..
python3 scripts/start-local.py                      # both services up; second run refused (ports busy)
python3 scripts/health-check.py                     # 4/4 PASS
node frontend/scripts/browser-check.mjs             # 16/16 PASS (Chromium override, temporary copy)
python3 audit/api_probe.py                          # 27/27 passed
python3 audit/lookahead_probe.py                    # ALL PROBES PASSED (144 + 144 checks, 488 trades)
```

## Recommended next steps (not done; no features implemented)

1. Decide whether to build a real MCX data adapter (bhavcopy import plus a verified holiday calendar and dated spec versions). Until then, real analytics are correctly blocked.
2. Add a per-chart SYNTHETIC badge to the pair and backtest charts if screenshots may be shared outside the app.
3. Make the root `npm` scripts cross-platform, or document that they are Windows only.
4. Remove or render the unused legacy fields in `/api/research`.
5. Treat the backtest P&L as a test of the engine only: it is produced by an injected anomaly.
