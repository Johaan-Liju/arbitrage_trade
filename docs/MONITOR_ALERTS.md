# Monitor and Alerts

## Inspection and scope

Observed before refactoring: four routes shared `ResearchShell`. Prices used `Dashboard`; Compare, Signals and Backtest used one conditional `PairWorkspace`. FastAPI already supplied normalized prices, exact-expiry matches, prior-only spread statistics and quality gates. No alert notification service existed.

| Existing feature | Decision |
|---|---|
| Prices | Monitor at `/`; focused watchlist, selected chart, source provenance and specification details |
| Compare prices | Fold normalized comparison table into Monitor; remove separate navigation and route |
| Price signals | Alerts at `/alerts`; reuse pair selection, settings, status/reason, chart, provenance and quality checks |
| Paired backtest | Remove route, controls, trade/equity results, frontend types and active simulation endpoints |
| Shared shell | Reuse dataset selector, explicit UTC cutoff, loading/error/empty states, disclosure and UI primitives |

The old `/compare`, `/signals` and `/backtest` routes return 404. Offline simulation functions/tests and historical documents remain reference material, not active product capabilities. `frontend/scripts/monitor-check.mjs` is the current browser check invoked by `npm run test:browser`; earlier scripts target historical layouts.

## Required backend capabilities

| Capability | API / implementation |
|---|---|
| Dataset-scoped exact contract catalog | `GET /api/contracts` |
| Atomic Monitor watchlist, prices, changes, freshness and aligned spreads | `GET /api/monitor`, `monitor.py`, `research.py`, `normalization.py`; explicit as-of required |
| Alerts for selected exact-expiry pair | `POST /api/pair`, `pairs.py`; explicit dataset, contract IDs/spec versions and as-of timestamp |
| Validated ingestion, including dry run | `POST /api/ingest`, `ingestion.py` |
| Immutable references and separate SQLite paths | `reference.py`, `store.py`; synthetic and real paths cannot coincide |
| Health and specification evidence | `GET /api/health`, `GET /api/spec-evidence` |

No new financial calculations are implemented in the frontend. Both observation and availability times remain bounded by the cutoff; specification versions, symbols, exact expiries and datasets remain separate. Matching does not substitute nearby expiries. Missing real data remains an error, with no synthetic fallback. Real-data links now wait for URL dataset initialization before loading contracts, and keep the dataset when navigating without a selected contract.

## Decisions and limits

Monitor selections use symbol, exact expiry and specification version. The watchlist stores exact contract IDs in browser local storage under separate dataset keys, with a session-only fallback if storage is unavailable. All available contracts are watched initially; users can remove or re-add the selected contract. Removing a watchlist item does not delete source data.

Price changes compare the preceding available record within the identical dataset/symbol/expiry/specification partition, not necessarily the preceding calendar day. Cross-contract spreads are row minus selected contract in normalized INR/g at 999 purity. They require different symbols, identical exact expiries and latest trading dates, and fresh, unblocked legs. Missing, stale, blocked or mismatched legs produce no spread. No bid/ask spread is inferred from settlement observations.

Freshness is observation age at the explicit cutoff. The default 72-hour threshold is a research display policy, adjustable to 24 hours or 7 days; it is not a source SLA or a trading-calendar assertion. Expired contracts are stale. Historical observations remain visible with their status and timestamp, while missing observations have no chart. The connection status is checked separately from dataset availability. Requests clear previous results, and an aborted request cannot restore an older dataset or contract.

CSV v1 still requires its exact header; volume/open_interest cells may be blank when absent from the source. Blank values normalize to null, never zero. Supplied nonnegative integer values, including genuine zero, retain validation. Alerts fail closed on missing liquidity proxies. Monitor displays only supplied volume/open-interest metrics and discloses that these do not establish executable liquidity. Bid/ask and depth fields are not supported by the current import schema.

Alerts are in-app paper notifications from the evaluated deterministic `opportunity-v1` model (see OPPORTUNITY_EVALUATION.md), scanned manually at an explicit UTC cutoff. Backend: `backend/alerts.py`, `/api/alerts/{catalog,sessions,scan,history,read}`. A paper session freezes its settings (policy, minimum |z| of at least 2.5, severe-cost threshold, maximum input age, cooldown, lifetime) and keeps its own SQLite store under `data/notifications/<dataset>/`, separate for synthetic and real data. Each alert freezes contracts with exact expiry and specification versions, signal time, five-session horizon, model/protocol/report identifiers, the observations used with observed and available times, itemized BASE/STRESS/SEVERE costs, and liquidity, settlement and cost uncertainty text.

Suppression, in order: missing or invalid inputs, unevaluated dataset (real data has no registered model, so it never alerts), stale inputs, below-threshold z, missing costs, model abstention, deduplication (same pair, version, trading date, direction), cooldown, and expiry. Alerts expire at the earliest of the configured lifetime, input freshness limit, planned entry open and safety deadline. Probabilities are never shown because calibration has not been evaluated. Subsequent outcomes are an append-only journal per scan cutoff: pending endpoints are not losses, missing endpoints are censored, and outcomes use daily source prices, not observed fills. History at an earlier cutoff hides later signals and outcomes. Scan cutoffs must advance within a session.

Limits: the evaluation is one synthetic expiry with zero held-out model alerts; user-chosen thresholds have no separately measured performance. No external notification channel, scheduler or trade execution exists.

The existing loopback launcher and Next.js proxy remain unchanged. No deployment or trade execution is part of this refactor.
