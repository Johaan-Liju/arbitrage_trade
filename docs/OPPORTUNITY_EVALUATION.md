# Deterministic opportunity model — experimental

Implemented in `backend/opportunity.py` and `backend/opportunity_evaluation.py`. No learned parameters or calibrated probabilities are claimed.

## Policies and accounting

- **Baseline:** exact-expiry matched spread, ten consecutive preceding common sessions, prior-only sample standard deviation, alert at |z| >= 2.5.
- **Model:** the baseline plus a fixed cost filter. Assume the spread returns to its frozen prior mean through equal and opposite normalized moves in the two legs. Use current quotes to estimate entry and projected raw quotes for exit. Alert only if estimated SEVERE net return exceeds 10 bps of gross package notional. This reversion hypothesis is uncalibrated; it uses no future outcomes.
- **Control:** always abstain. No alerts means undefined precision and outcome estimates, not proven zero-risk performance.
- Labels use next scheduled common-session entry and exit five common sessions after entry, with immutable exact specification/calendar references. Missing prescribed endpoints are censored; dates are never substituted. Raw quote P&L deducts brokerage, other-charge budgets and adverse slippage on both legs at both endpoints. BASE/STRESS/SEVERE budgets are 20/40/70 bps per leg per side, respectively.
- All results are `HYPOTHETICAL_DAILY_PRICE_PROXY`, with `execution_evidence=NONE`. Costs are assumed sensitivity budgets, not verified fees or measured slippage.

## Point-in-time and evaluation safeguards

Both observation and availability times, including specification/listing/calendar availability, must be known at each prediction. Prior records must also pass their own publication-time quality gates. Exact versions are never merged. Current inference rechecks freshness at the requested as-of; it returns no outcome labels.

Chronological expanding-history folds group all pairs on each trading date. Training manifests purge overlapping outcomes and labels unavailable at the fold boundary, then enforce a six-session embargo on outcome end/publication times. Test blocks have at least six excluded sessions between them, extended if needed so planned outcomes do not cross the next test block. Parameters remain frozen; training manifests are audited inputs for a future learner, not fitted examples for this deterministic model.

Dependent outcomes within blocks remain explicit. Uncertainty groups complete alerts by expiry, merging overlapping time envelopes across expiries. Cluster-bootstrap intervals require at least 100 complete alerts, ten resulting blocks and 30 outcomes in each class. Otherwise intervals are null with an explanation. Censoring bounds are separate missing-outcome bounds, not confidence intervals. Overlapping hypothetical outcomes are never summed into portfolio returns.

## Held-out synthetic experiment

Request: [opportunity-synthetic-request.json](research/opportunity-synthetic-request.json).
Final immutable report: [328f3862…json](research/evaluations/synthetic/328f38620dca811605488161635a4c3bfd9ffb89e4072caf2655cbaab42ac4b1.json).

GOLDTEN/GOLDGUINEA, exact expiry 2026-11-20, demo-v4, 4/5 lots. Cutoff 2026-10-23 18:00 UTC. There are 39 scheduled dates and 29 eligible decisions after warm-up. Held-out blocks are 2026-09-29–2026-10-05 and 2026-10-14–2026-10-20, totaling ten eligible decisions. Purging/embargo leaves **zero completed candidate training examples** in either fold; no supervised model was fitted.

| Held-out measure | Fixed-z baseline | Cost-filtered model |
|---|---:|---:|
| Alerts / eligible decisions | 1 / 10 (10%) | 0 / 10 (0%) |
| Complete alerted outcomes | 1 | 0 |
| Censored alerted outcomes | 0 | 0 |
| Precision: positive by >10 bps under BASE costs | 1 / 1 | Undefined |
| Precision: positive by >10 bps under ALL cost scenarios | 0 / 1 | Undefined |
| Mean BASE hypothetical net return | +57.32 bps / +INR 3,535.97 | Undefined |
| Mean STRESS hypothetical net return | +17.18 bps / +INR 1,059.84 | Undefined |
| Mean SEVERE hypothetical net return | -43.03 bps / -INR 2,654.34 | Undefined |
| Statistical confidence interval | Withheld: one outcome, one expiry block | Withheld: no outcomes |

The baseline's one alert has label `COST_SENSITIVE_POSITIVE`. The model abstains. On that completed baseline candidate, model-minus-baseline return is -57.32 bps under BASE and +43.03 bps under SEVERE, assigning abstention zero exposure. This is a conditional scenario comparison, not a portfolio result or evidence that the filter is better.

**Evidence is insufficient.** History spans 52 calendar days, one matched expiry, and contains deliberate synthetic GOLDTEN anomalies previously inspected during development. Held-out here means a chronological replay partition, not untouched real market validation. Real storage is absent; real requests fail explicitly without synthetic substitution. Missing evidence includes verified real price/reference history across regimes and expiry cycles, source revision vintages, authentic publication timing, cost evidence and actual execution/liquidity data. Reports remain `EXPERIMENTAL`; no market-performance or probability claim is supported.

The earlier `f3bdf00e…` JSON is a retained intermediate run. Use the final report linked above, which includes protocol, implementation and point-in-time input hashes.

## Use locally

Both endpoints accept the same explicit dataset/as-of/pair/calendar request shape:

- `POST /api/opportunities/predict`: current deterministic predictions and reasons; freshness checked at as-of; no outcome labels.
- `POST /api/opportunities/evaluate`: historical features, hypothetical labels, purged fold manifests, held-out policy metrics, uncertainty and evidence limitations.

Reproduce the report without starting services or modifying data:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate-opportunity.py --request docs/research/opportunity-synthetic-request.json --output-root docs/research/evaluations
```

The CLI reads the selected existing database only and writes content-addressed reports beneath separate `synthetic/` and `real/` directories. It refuses to overwrite different contents. Real requests must specify real exact contract and calendar versions; no demo identifiers or data are substituted.

Validation: 148 backend tests passed, including future-price perturbation invariance, future/late references, label maturity, exact endpoints, missing liquidity, raw-cash hand reconciliation, dataset failures, overlap purging, delayed-label embargo, date grouping, current freshness and deterministic report reproduction. One existing Starlette/httpx deprecation warning remains. See BUILD_LOG.md for exact commands.
