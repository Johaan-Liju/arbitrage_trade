# Opportunity alert research specification

**Version:** opportunity-v1-draft, 2026-10-25. **Status:** ready for review; no training authorized by this document. This specifies research outcomes, not executable opportunities or guaranteed arbitrage. No models, outcome labels, orders or fills were produced in this task.

## 1. Decision and proposed first use case

Start with an **on-demand, exact-expiry contract-spread investigation alert**, using the existing deterministic prior-only z-score as the baseline. Use a fixed five-session outcome window for research. Do not train ML on the current dataset or report market predictive accuracy.

Initial demonstration pair, with fixed orientation:

- A: `GOLDTEN:2026-11-20:demo-v4`; specification `GOLDTEN:demo-v4`.
- B: `GOLDGUINEA:2026-11-20:demo-v4`; specification `GOLDGUINEA:demo-v4`.
- Both have 39 aligned dates, 999 quoted purity, invented Ahmedabad delivery basis and matching recorded settlement descriptions. Quote/lot weights are 10/10 g and 8/8 g respectively. The smallest equal gross-weight package is 4 lots A against 5 lots B, 40 g per leg. Equal purity reduces one comparison difference; it does not establish economic interchangeability.

This choice uses coverage, matching metadata, manageable integer sizing and the existing pair implementation. **It is not a performance-selected market pair.** GOLDTEN has deliberately inserted price anomalies in the generator, and this pair has already been used in earlier demos. Any apparent success is contaminated by generator design and prior inspection; it cannot serve as untouched validation.

Why this before directional prediction: the repository already supports spread normalization, same-date pairing, prior-only statistics and explicit quality gates. This pair has complete synthetic overlap for testing those mechanics. Directional data covers more exact contracts, but consists of the same 39 dates driven by a shared generator, not a larger independent market sample. Neither task has real evaluation coverage. If verified real exact-expiry overlap is absent, this choice must be reconsidered rather than substituting a nearby expiry.

## 2. Observed data audit

Reproduce with:

```powershell
.\.venv\Scripts\python.exe scripts/audit-opportunity-data.py --output docs/research/opportunity-data-audit.json
```

The script opens existing SQLite data read-only, uses the validated snapshot path, does not seed data, and records a file hash. [Audit artifact](research/opportunity-data-audit.json) uses cutoff `2026-10-23T18:00:00Z`. Counts describe this local snapshot, not promised future coverage.

| Observed repository fact | Consequence |
|---|---|
| Active `data/synthetic/goldlens-v4.sqlite3`: 312 stored/usable observations, zero blocked records; 1 batch, 4 specification references, 8 listings, 1 calendar | All observations and operational references are synthetic |
| Four symbols; two exact expiries each; 39 observations per contract partition, 2026-09-01 through 2026-10-23 | Only 39 distinct trading dates; 312 rows are not 312 independent opportunities |
| All four share invented expiry 2026-11-20; December expiries differ by symbol | Six unordered November pairs have 39 aligned dates each; no eligible December cross-symbol pair |
| One synthetic source URL; all 312 availability lags are 300 seconds | Does not test realistic vendor latency, revisions or outage distributions |
| Source price, currency/unit, quote purity/weight, volume, OI, observation/availability timestamps and immutable spec/listing/calendar references are present | Enough for deterministic arithmetic and point-in-time pipeline tests |
| Active import has one price per instrument/expiry/specification/trading date; no bid/ask, market depth, trade prints, order acknowledgements or actual fills | Cannot infer executable prices or fill probabilities; legacy generated OHLC is not observed market microstructure |
| `data/real/imports-v4.sqlite3` does not exist; there are zero real price rows available for this research | No real train/validation/test evaluation is currently possible |
| `docs/evidence/mcx-specs-2026-10-24.json` has `live_analytics_enabled=false`; operational terms remain UNVERIFIED | Original-document evidence is not an operational historical reference timeline or real price history |
| Legacy v1 SQLite/JSON files exist in the synthetic directory | Excluded from counts and evaluation; no pooling versions or treating demo copies as new evidence |

The generator in `backend/store.py::fixtures` combines a shared trend, sine/cosine functions and deterministic liquidity. It adds an explicit anomaly to GOLDTEN at indices 24, 25 and 38. `backend/synthetic_v4.py` republishes invented observations with explicit invented expiry listings. The synthetic calendar uses weekdays, not a verified exchange holiday/special-session history. Audited volume/OI is present on every row but is also invented.

**Evaluation verdict: not credible for forecasting or profitability.** With ten prior observations, there are at most 29 decision dates per pair. Next-session entry plus five sessions held requires six future dates, leaving at most **23 complete fixed-horizon windows**, before z-score, liquidity and deadline gates. The final six post-warm-up decision dates have incomplete outcomes. Windows overlap; six pairs share legs and dates. Even those upper bounds are not independent trades, actual threshold crossings, observed outcomes, or evidence of generalization. No win rate, Sharpe ratio, accuracy or deployable probability should be reported from this dataset.

## 3. Separate prediction questions

Use separate datasets/label definitions, baselines and reports; never call a directional gold move a spread prediction.

| Definition | Directional task (deferred alternative) | Contract-spread task (initial research design) |
|---|---|---|
| Identity | One dataset/symbol/exact-expiry/specification partition | Ordered pair of those identities; identical exact expiry, different symbols |
| Economic question | Does that contract's quoted price rise or fall over five sessions after the entry proxy? | Does a contrarian two-leg package earn a positive return under an explicit cost scenario? |
| Continuous price target | `r_dir = (P_x - P_e) / P_e` | `delta_S = S_x - S_e`; retain independently from package P&L |
| Primary economic target | Hypothetical one-lot signed net return for LONG/SHORT separately | Hypothetical after-cost return on initial gross package notional, with sides frozen at decision |
| Direction | Forecast UP/DOWN/FLAT; no directional model or momentum threshold is specified for training now | At positive z: short A/long B; at negative z: long A/short B |
| Confounding risk | General gold trend, carry, expiry and changing regime | Residual directional/fine-weight exposure, delivery/settlement basis and two-leg timing |

For any later directional classification, use `UP` if the LONG scenario net return exceeds 10 bps, `DOWN` if the SHORT scenario net return exceeds 10 bps, otherwise `FLAT`, under the same fixed entry/exit schedule and declared costs. Missing outcomes are censored. These are price-proxy labels; shortability and actual execution remain unproven. Directional labels must not be pooled with spread labels or trained now.

## 4. Decision-time eligibility and features

For a recorded trading date d, decision timestamp **t** is the maximum of both legs' `observed_at`, `available_at`, normalized availability and every required specification/listing/calendar availability. Evaluate from a snapshot with cutoff exactly t. Do not use a later API snapshot as historical decision state. Manual current as-of refreshes do not create additional historical samples for d.

Required gates, fixed for opportunity-v1:

1. Exact dataset, symbol, expiry, `spec_id` and `spec_version` identities are retained on every leg. Real work requires operational VERIFIED references available at t. Synthetic work remains a separate labeled experiment. No month-derived dates, continuous/rolled prices or version concatenation.
2. Both prices describe the same trading date and compatible quote currency/unit. All timestamps and references must be <= t. At t, each observation is at most 24 hours old and observation timestamps differ by no more than 15 minutes. These are proposed research quality policies, not source guarantees. Missing or invalid timestamps block the alert.
3. Current spread `S_d = N_A,d - N_B,d`, where `N = quoted_INR / quotation_grams * 999 / quoted_purity_per_mille`. Use Decimal arithmetic. Normalized spread is not a traded price or cash P&L.
4. Require ten usable aligned observations strictly before d and available by t. Their historical eligibility is assessed at their own decision timestamps. No forward fill; an intervening known open session missing a required observation blocks this v1 window. This is stricter than the current pair engine, which can skip missing dates and permits minimum 5 by default.
5. `mu_t` is the mean of those ten preceding spreads; `sigma_t` is their sample standard deviation (ddof=1). Exclude the current spread. Zero variance or insufficient history is `INELIGIBLE`, never zero risk.
6. `z_t = (S_d - mu_t) / sigma_t`. Alert candidate when `abs(z_t) >= 2.5`. Freeze z sign and reference mean at t. Below threshold is `NO_ALERT`, not a failed opportunity label.
7. Liquidity/deadline/package gates below must pass at decision time. Calendar and expiry safety must be known at t.

Allowlisted future ML inputs, only after review and sufficient real data: current spread, z, prior mean/std, previous 1/5/10 aligned spread changes, prior leg returns, source-supplied volume/OI and missingness, ages/observation skew, and days/sessions to the exact safety deadline. No future label state, eventual P&L, future fill/exit quality, full-sample normalization, generator index or later revised specification may enter features. Any preprocessing must fit on training data only. Missing liquidity is a gate failure, not an imputed zero.

## 5. Horizon and hypothetical entry/exit protocol

**Fixed horizon:** next scheduled common open session is entry session e; exit x is the fifth common open session **after e**. Thus x is the sixth subsequent session after decision date d. Use the verified point-in-time session calendar for real data; synthetic weekdays only support demo tests. No calendar-day/session-day substitution.

Entry is a **hypothetical daily price proxy**: both legs' source-recorded prices on e, with observations strictly later than t. Those prices are only known when their later publications arrive. They are not orders, actual fills or evidence that either price could have been obtained. If either prescribed entry record is missing, stale, invalid or fails liquidity/skew gates, label entry unavailable; do not seek a more favorable later date.

Exit is both source-recorded prices on scheduled x, with the same provenance/quality checks. Exit uses a fixed horizon to keep outcomes comparable. There is **no early z-score convergence exit, intraday stop-loss, take-profit or terminal forced liquidation** in this v1 label. A price crossing that disappears between daily observations is unobservable. Record convergence toward the frozen `mu_t` as a secondary descriptive measure, not as proof of a completed trade.

The safety deadline is the earliest of explicit safe-exit dates, last-trade dates, exact expiries, specification valid-through dates and the last verified open session before tender/delivery restrictions for either leg. Planned entry and exit must both be strictly before that deadline; require at least one further common open session before it as a buffer. If known dates/calendar coverage cannot establish this at t, outcome is `INELIGIBLE` with reason. No delivery or roll is assumed. Invalid references encountered later censor the result; never replace them with today's spec.

The legacy offline simulator uses a dynamic exit threshold and maximum calendar-day hold; it does **not** implement this fixed-session protocol. Do not reuse its trade records as these labels. Its replay fills are hypothetical too. No simulator/API/UI changes are part of this specification.

## 6. Sizing, costs, slippage and liquidity

Use the smallest whole-lot equal gross-weight package: LCM of integer lot grams, with no more than 100 lots per leg. For the selected synthetic pair this is 4 A / 5 B. Keep equal fine-weight and settlement exposure checks separate; real spec changes can invalidate this package. No volatility-based resizing, leverage, margin return or automatic scaling.

For leg i, signed quantity `q_i = side_i * lots_i * lot_grams_i / quote_grams_i`. Gross P&L in INR is `sum(q_i * (P_i,x - P_i,e))`. Initial gross notional `G_e = sum(abs(q_i) * P_i,e)`; this is exposure, **not required capital or margin**.

Costs are charged on absolute raw-quote notional at entry AND exit on BOTH legs. Slippage is a separate adverse cash deduction, not a rewritten source price or double-counted fee. For fixed per-leg/side cash charges f: `C = sum_over_legs_and_sides(notional * (brokerage_bps + other_charge_bps + slippage_bps)/10000 + f)`. `R_net = (gross_PnL - C) / G_e`. Retain gross P&L and every cost component beside the net figure.

The following are **invented sensitivity budgets**, not verified exchange/broker/tax charges or measured slippage:

| Scenario | Brokerage, bps/leg/side | Aggregate other charges budget, bps/leg/side | Adverse slippage, bps/leg/side | Fixed INR/leg/side |
|---|---:|---:|---:|---:|
| BASE | 5 | 5 | 10 | 0 |
| STRESS | 5 | 10 | 25 | 0 |
| SEVERE | 5 | 15 | 50 | 0 |

BASE therefore deducts 20 bps of each transaction's notional; for roughly unchanged prices, a full package round trip costs roughly 40 bps of initial gross notional, not 20. These differ from the older simulator's omitted-charge defaults. The aggregate budget does not establish completeness or applicability of taxes, exchange/clearing charges, funding, margin, borrowing, delivery, custody or settlement costs. Store unknown actual costs as unknown, never silently zero. Report sensitivity outcomes as `HYPOTHETICAL_COST_SCENARIO`; live economic eligibility remains unresolved until cost evidence is complete.

At decision, entry and exit, require source-supplied daily volume >=100 contracts and open interest >=100 for each leg. Additionally, each leg's package lots must be <=1% of that leg's daily volume AND <=1% of open interest. For 4/5 lots the participation gate needs volume and OI >=400/500 respectively; the 100-floor alone is insufficient. Decision gates may only use data available at t; entry/exit values validate a later scenario outcome, never a feature or a claim of known future eligibility.

Missing liquidity gives no eligible economic outcome; zero source volume is not missing and fails the threshold. Daily volume/OI cannot establish book depth, simultaneous execution, absence of partial fills or true participation at the quote. There is no spread-crossing/legging/fill probability estimate in this design. Without order-book/trade/execution evidence, feasibility remains `UNKNOWN` even when all proxies pass.

## 7. Targets, outcome labels and provenance

For spread candidates, the continuous primary target is `R_net_BASE` under the prescribed package and horizon. Also retain `R_net_STRESS`, `R_net_SEVERE`, raw `delta_S`, gross P&L, and `sign(z_t)*(S_e - S_x)` as a descriptive convergence value. The eventual prediction question, if later approved, is **P(ROBUST_POSITIVE | information available at t)**; it is not a fill probability or probability of risk-free profit.

Use a 10-bps materiality buffer on G_e; compare unrounded values. Every record has an eligibility state, economic scenario label and execution-evidence flag, rather than conflating missing outcomes with losses:

| State / label | Exact meaning |
|---|---|
| `INELIGIBLE` | A gate already fails at t; store all reasons, no economic label |
| `NO_ALERT` | Eligible but abs(z)<2.5; not a negative training example for candidate success |
| `CENSORED_ENTRY` | Scheduled entry unavailable/invalid or fails later quality/liquidity checks; economic label null |
| `CENSORED_EXIT` | Entry proxy exists but scheduled exit is missing/invalid, beyond available data or lacks required reference/liquidity; label null |
| `ROBUST_POSITIVE` | Complete candidate: net return > +0.001 under BASE, STRESS AND SEVERE |
| `COST_SENSITIVE_POSITIVE` | BASE net return > +0.001, but at least one stress scenario does not exceed +0.001 |
| `NEAR_ZERO` | BASE net return in [-0.001, +0.001], inclusive |
| `NEGATIVE` | BASE net return < -0.001 |

All complete economic labels have `execution_evidence=NONE` and `outcome_basis=HYPOTHETICAL_DAILY_PRICE_PROXY`, including synthetic outputs. Also store `price_data_kind=SYNTHETIC` or `IMPORTED_REAL`; real source prices alone do not turn hypothetical execution into observed fills. A later sample can only have observed execution with a separately linked immutable execution record, outside this scope. Censoring reason and its detection time must be retained; do not relabel missing exits as zero P&L, loss or a fabricated closing trade.

No actual label distribution has been measured here. The target and thresholds are design choices for review, not fitted conclusions. If eligible alerts or complete outcomes are too rare, report that fact; do not adjust thresholds until a new protocol version is registered.

Future label records must include: protocol/version hash; dataset and snapshot/reference hashes; ordered contract IDs, both exact expiries/spec IDs/versions; d/t; feature cutoff; entry/exit planned sessions; actual source observation/publication timestamps; label availability time = maximum of all outcome inputs' availabilities; side/lot package; original quotes and units; normalization version; all quality/liquidity flags; each cost scenario; outcome/censor state; execution-evidence flag. Features stop at t; label availability can be later. Do not expose an immature label in a replay at an earlier as-of.

## 8. Evaluation design and training gate

Current permitted validation: point-in-time/identity arithmetic tests, source/missing-data handling, deterministic baseline behavior, label timestamp maturation and censoring tests, and hand reconciliation of hypothetical package P&L. The checked-in audit reports coverage bounds only. No labels or forecasts were generated by the audit.

Before credible real evaluation, collect operational verified specs/listings/calendars and point-in-time source history, including original availability and revision vintages. As a **proposed minimum collection gate**, require at least 24 consecutive months and 12 distinct eligible exact-expiry cycles for the chosen real pair, with >=90% same-session coverage over their jointly listed periods; audit missingness and delayed/revised records. This is not a statistical sufficiency guarantee. If exact-expiry overlap fails, stop or preregister a different task; never fabricate matching dates.

Only after sufficient data and a separate approval to train:

- Freeze protocol and cost evidence before examining held-out outcomes. Run the deterministic |z|>=2.5 baseline and an always-abstain baseline first; compare any ML alert to them on the same eligible population and cost scenarios.
- Use chronological walk-forward folds and a final untouched period containing complete expiry cycles. Keep all contracts/pairs for a trading date in the same split, to prevent shared-leg/date leakage. Never random-split rows or pool synthetic data into real validation.
- Purge training decisions whose decision-through-exit/label-availability interval overlaps validation/test. Apply at least a six-common-session embargo around fold boundaries and extend it for delayed label availability. Fit scalers/features/calibration on prior training data only. Never train on unmatured labels.
- For an eventual 24-month minimum collection, reserve the last six months and at least three full expiry cycles as untouched test; train/validate on earlier data with expanding windows. If those periods do not contain the required cycles, extend collection. Fix the calendar boundary before seeing performance.
- Report decision/gate counts, threshold crossings, complete/censored outcome counts, label prevalence, source/spec coverage and liquidity failures BEFORE accuracy. Report spread target error; robust-positive precision/recall and PR-AUC; Brier score/calibration if probabilities exist; alert rate/abstention and incremental performance over the deterministic baseline. Include uncertainty clustered by date/expiry, not a row-i.i.d. confidence interval.
- Censoring can be informative: outages and low liquidity may coincide with large moves. Complete-outcome metrics are conditional on observable eligible endpoints, not unbiased performance over all alerts. Report censoring by time, source, z-score and regime; disclose sensitivity bounds rather than silently discarding difficult outcomes.
- Economic reports must be scenario P&L and costs on raw quotes, not normalized-price gains masquerading as cash returns. Overlapping candidate labels are permitted for prediction analysis but cannot be summed as independently funded trades. A portfolio report requires a separately specified non-overlapping position policy, margin/funding constraints and execution model. None is specified or evaluated here.
- Proposed reporting gate: at least 100 complete held-out candidate outcomes across >=3 expiry cycles, with at least 30 robust positives and 30 non-robust outcomes for classification. Even then inspect dependence and interval width; if gates are unmet or confidence intervals remain broad, report evaluation as inconclusive and collect more data. Do not force classes or tune on the holdout.

## 9. Missing data and review decisions

Blocking for real research: real historical source prices; original publication/revision chronology; verified point-in-time operational spec timelines, exact listings, tender/safety dates and exchange session calendars; enough genuinely matching expiries. Blocking for executable-profit claims: bid/ask/depth/trades, actual fills and partial/failed/legged execution records; historical costs/tax treatment; margin/funding/borrowing constraints; delivery/location/settlement basis and operational restrictions. Historical daily volume/OI coverage also needs verification; Monitor's optional fields are not a license to invent liquidity.

The current immutable observation key admits one record per dataset/instrument/expiry/specification/trading date. It prevents overwrite, but does not by itself represent multiple corrected source vintages under the same identity. A revision-aware import/storage extension is needed before claiming authentic as-published revision replay; do not simulate it by overwriting prices or inventing new contract specs. Import audit provenance is not proof that a historically asserted source-availability timestamp is authentic.

Review these concrete choices before any label implementation or training: initial pair/task, full ten-session warm-up, |z|2.5 candidate threshold, fixed five-session hold, strict next-session/no-date-substitution policy, one-session pre-deadline buffer, 24-hour/15-minute quality limits, package and participation limits, cost budgets, 10-bps label buffer, censoring policy, real-data collection/split/reporting gates. Cost budgets and data minimums are research proposals, not externally verified market requirements.

After review, the next authorized implementation would be a versioned label builder plus leakage/chronology and cash-reconciliation tests on synthetic fixtures. Approval of this specification alone does not supply real data, authorize training or validate investment use. No deployment or trade execution is proposed.

## Repository evidence

- `scripts/audit-opportunity-data.py`, [audit JSON](research/opportunity-data-audit.json): read-only observed coverage and dataset hash.
- `backend/research.py`, `normalization.py`, `reference.py`, `ingestion.py`: available fields, immutable identities, validation, publication and reference cutoffs.
- `backend/pairs.py`: existing prior-only spread baseline and volume/OI gates; differs from the stricter proposed research window.
- `backend/backtest.py`: legacy hypothetical accounting and fill assumptions, not this fixed-session labeling protocol.
- `backend/store.py::fixtures`, `backend/synthetic_v4.py`: synthetic generator, disclosed anomalies and invented calendars/listings.
- [Contract evidence and operational limitations](CONTRACT_MATRIX.md), [evidence registry](evidence/mcx-specs-2026-10-24.json), [current Monitor scope](MONITOR_ALERTS.md): repository evidence only; no new external verification performed.
