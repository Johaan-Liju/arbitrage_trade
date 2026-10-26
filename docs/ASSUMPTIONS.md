# GoldLens assumptions and limitations

## Data and chronology

<<<<<<< HEAD
- Local synthetic database: `data/synthetic/goldlens-v3.sqlite3`. Reserved real path: `data/real/goldlens.sqlite3`. No fallback or real seeding. Legacy Node files remain untouched.
- Canonical SQLite tables: instruments, contract_spec_versions, contracts, daily_prices, signals, backtest_runs, trades. `specs` and `prices` are compatibility read views. Spec, contract and price update/delete triggers enforce append-only publication. New terms require a new immutable version; existing validity bounds cannot be edited retroactively.
- Every observation carries dataset, instrument symbol, exact contract/expiry, spec version, trading date, INR/quote, source, OHLC, settlement (`price`), volume, OI, observation, availability and ingestion timestamps. `price` is settlement and may differ from OHLC. OHLC must be internally consistent. All positive prices must be finite and ≤₹1 trillion per quote (an input safety bound, not an exchange limit); unusual normalized values are flagged for review.
- CSV has one exact documented schema. No implicit units or monthly expiry parsing. Duplicate keys, including stored keys, reject the entire import. Missing fields reject. Explicit expected session lists detect absent rows/closed days. Without a supplied calendar, synthetic ingestion reports calendar UNVERIFIED; no holiday guessing. Source and archived ingestion timestamps are supplied in the CSV and validated, not independently authenticated.
- Real ingestion and analytics are disabled. Verified quotation fields do not establish the missing exact effective/availability chronology or calendars. See CONTRACT_MATRIX.md.
- The demo has 39 weekdays, eight contracts, 312 settlements. Weekdays are not an exchange calendar. TEN anomalies of +₹140 per normalized gram are injected at indices 24, 25 and 38. Fixtures are deterministic and labelled synthetic everywhere.
- Query filtering requires both observed and available timestamps ≤ explicit UTC as-of. Every pair/replay is partitioned by both exact contract identities and spec versions. Historical decisions also filter prior observations by their own availability. Ingestion time is preserved for auditing and is not substituted for source availability.

## Statistical convention

- Normalize: quote / quote grams × (0.999 / purity). Preserve originals. Compare A minus B. Exact expiry equality is shown; otherwise display CALENDAR_BASIS_DIFFERENCE and both dates. No silent rolling or forward fill.
- At each paired date, decision time is the later leg availability. Expected basis is the prior-only rolling raw-spread mean. Residual is current raw spread less expected basis. Its baseline and sample standard deviation use prior residual observations, computed at their original decision times and available by this decision. Window default 10, minimum 5: the two-stage warm-up needs additional data before z-scores exist. Low-quality prior events are excluded.
- Difference = residual − prior residual mean; z = difference / prior residual sample standard deviation (ddof=1). Absolute z ≥ entry threshold is INVESTIGATE, below is NO_SIGNAL. Zero deviation has undefined z and NO_SIGNAL. Too little history is INSUFFICIENT_DATA; stale/spec/liquidity failures are REJECTED. Every status includes a reason. The latest card additionally checks freshness at the requested cutoff and missing later legs.
- No carry, tax, location or delivery pricing model is claimed. A rolling historical baseline may be inappropriate for a structural break.

## Hypothetical execution and accounting

- A signal dated t can fill only on a later dated observation, and both fill observations must occur strictly after signal availability. Daily settlement is a hypothetical proxy, not a quote or proof of a fill. Missing next-leg entry cancels the order. Failed exits can be reissued; unresolved positions remain explicit.
- Match integer lots to equal gross grams via LCM, cap default 100 lots per leg. GOLDTEN/GOLDGUINEA gives 4×10 g and 5×8 g. This does not necessarily match fine gold content or price sensitivity. A parallel +₹1/g normalized-price diagnostic reports signed grams × purity/.999; zero is not proof of neutrality.
- Compute raw notional = quoted price × lots × lot grams / quote grams. Leg P&L = direction × (exit − entry) quote × lots × lot grams / quote grams. Never use normalized comparison spread as executable P&L.
- Defaults: entry |z| 2.5, exit |z| ≤0.5; fees 5 bps and adverse slippage 10 bps of raw notional for each leg on each side. Slippage is a separate expense, not double-counted in quotes. These are intentionally illustrative assumptions, not an estimate of actual broker/exchange/tax costs. Fees/slippage configurable including zero for sensitivity checks.
- Daily volume and OI minimum 100 each; lots must be ≤1% of each proxy. Four calendar days is maximum order gap/age. This allows weekends but is not verified holiday logic. Users can configure these API guards. No order-book, partial-fill or intraday claims.
- Explicit synthetic safe exits precede tender/expiry. Effective replay end is the earlier of both safe exits and the request's known as-of date. Exit is requested at/after end minus the configured maximum-gap calendar-day buffer, then filled at the next eligible observation. Entries in that buffer are rejected. No liquidation past end and no last-close shortcut. End is known configuration, not inferred from future prices. Changing as-of changes the scheduled replay horizon.
- Mark-to-market uses raw quotes, deducting entry expenses when entered and exit expenses when closed. Equity is ₹1,000,000 reference capital plus realized/unrealized net P&L; drawdown is peak equity minus current equity, including initial capital. This capital is not required margin. Missing/invalid marks produce null equity and withheld drawdown; open positions produce INCOMPLETE and withheld total net P&L. Closed-trade realized P&L remains visible. No fabricated terminal exit.
- No margin funding, margin calls, GST, statutory transaction taxes, delivery premia, borrowing, storage, tender allocation, settlement default or executable two-leg liquidity modeling. Never guaranteed arbitrage; no trade execution.
=======
- Active v4 synthetic storage is `data/synthetic/goldlens-v4.sqlite3`; real imports are separate at `data/real/imports-v4.sqlite3`. No fallback, real seeding or silent migration. Earlier Node/v3 implementations remain legacy reference.
- Four immutable demo-v4 specifications, eight exact listings and 312 invented settlements across 39 explicit synthetic sessions. These are not a verified exchange calendar or real executable prices. Volume, open interest, delivery and settlement terms are synthetic too.
- Immutable reference_versions and observations retain explicit dataset, symbol, exact expiry, spec version, quote currency/unit/purity, source, observation and availability times. Every normalization validates exact listing and calendar versions. Real ingestion is supported only with complete verified operational references; a missing real dataset fails explicitly.
- Both observation and availability timestamps, including required references, must precede the explicit UTC cutoff. Ingestion time is audit metadata, not a replacement for source availability. No monthly expiry inference, nearest-expiry substitution or forward fill.

## Statistical convention

- Normalize using Decimal: quoted INR / quotation grams * 999 / quote purity per mille. Lot grams are separate. Preserve original quotes and reference provenance. This is a comparison convention, not economic interchangeability.
- Only different instruments with identical explicitly listed exact expiries can pair in the active API. Specification versions stay separate. Unsupported alternatives and delivery/settlement differences are explained.
- No machine learning or predictive accuracy claim. A historical baseline can fail after structural changes.

## Hypothetical execution and accounting

See [deterministic paired-trade rules](PAIRED_BACKTEST.md) for entry, exit, warm-up, sizing, timing, costs and expiry details. One paired position at a time; every fill requires later observations on BOTH legs, and missing prices remain explicitly unfilled.

- Defaults: entry |z| >= 2.5, exit |z| <= 0.5, maximum holding 10 calendar days, cap 100 whole lots per leg, assumed brokerage 5 bps and adverse slippage 10 bps per side. Per-leg exchange/clearing, tax, other bps and fixed INR default to zero (omitted, not exempt). These are user assumptions, never official charges.
- Use the smallest equal gross-weight package via integer LCM. Gross weight equality need not match fine gold or settlement exposure. Raw-quote notional uses lot grams / quote grams; normalized spreads never substitute for cash P&L.
- Deadline is earliest safe exit, exact expiry, spec valid-to or day before tender for either leg. The order-age calendar buffer requests exit before it. As-of truncates available observations and does not change this scheduled deadline. Holding limits request later exits; missing fills can leave a position open beyond the limit.
- Closed-trade realized P&L deducts both sides' itemized assumed charges and slippage. Open entry costs and unrealized marks appear separately. Reference equity defaults to INR 1,000,000, not required margin. Unknown marks withhold total performance; no invented terminal liquidation.
- Daily volume/OI participation is only a proxy. No order book, partial fills, legging risk, margin calls, funding, borrowing, delivery premia, storage, tender allocation or settlement default simulation. Configured tax items do not establish actual tax obligations or completeness. Never guaranteed arbitrage; no trade execution.
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

## Verified features versus unsupported claims

| Implemented and tested | Unsupported |
|---|---|
| Immutable specs and exact expiry/version identity | Complete historical MCX spec/calendar timeline |
| Strict CSV validation and atomic imports | Automatic bhavcopy schema detection or real feed |
| 999-equivalent normalization with provenance | Economic interchangeability or executable spread |
<<<<<<< HEAD
| Prior-only residual statistics, explicit statuses | Forecast accuracy or profitable strategy |
| Next-observation paired hypothetical replay | Actual fills, market neutrality or margin sufficiency |
| Leg notional, gross/net attribution, equity and drawdown | Complete taxes, funding, delivery or settlement model |
| Loopback app and offline seeded workflow | Remote hosting, authentication or trade execution |
=======
| Prior-only spread statistics, explicit statuses | Forecast accuracy or profitable strategy |
| Next-observation paired hypothetical replay | Actual fills, market neutrality or margin sufficiency |
| Leg notional, gross/net attribution, equity and drawdown | Complete taxes, funding, delivery or settlement model |
| Loopback app and offline seeded workflow | Remote hosting, authentication or trade execution |

### Rolling matched-pair spread signals

- Spread = left normalized price minus right normalized price, in 999-purity INR/gram. The active API accepts only explicitly listed, identical exact expiries and distinct instruments. Normalization uses quotation grams and quoted purity; lot weight is separate.
- At decision cutoff t, both observed_at and available_at of both legs must be <= t. Pair availability is the maximum of both observations, publications, and required specification, exact listing and calendar availability. Replay uses that availability as its decision cutoff. Latest is evaluated at the explicitly requested as_of; later arrivals may change latest without rewriting earlier replay decisions.
- Align only identical trading dates. No forward filling, nearby expiry substitution or merging of specification versions. Partitions include dataset and both exact contract/symbol/expiry/specification identities. Unusable reference/price records are excluded and reported. An unusable or missing latest leg blocks a current signal rather than reusing a stale spread.
- For current date d, take up to lookback preceding eligible aligned dates strictly before d and available by t. z = (current spread - prior mean) / prior sample standard deviation. Sample variance divides squared deviations by n-1 (ddof=1). Current spread is excluded from both mean and standard deviation. Decimal normalization and spread arithmetic precede numeric response values.
- Defaults: lookback=10 preceding eligible spreads (integer 2..250), min_observations=5 (integer 2..lookback), entry_z=2.5 (finite number >0 and <=100). POST /api/pair and /api/backtest validate these settings. UI controls expose all three. A partial window is permitted once the minimum is met; missing dates do not consume samples.
- Exactly three signal statuses: Investigate when abs(z) >= threshold (inclusive boundary); No signal below it; Insufficient data for inadequate history, zero variance, missing legs, unusable references or quality failures. Each includes a specific reason. Investigate is a research flag, never guaranteed arbitrage: costs, liquidity, execution and settlement uncertainty remain.
- Existing quality gates remain: max_age_days=4, min_volume=100, min_oi=100, known spec validity and safe exit. Prior eligibility checks these gates at each spread's own availability; historical records do not age out of the rolling window as the current decision advances. Current freshness is checked at the decision cutoff. Daily volume/OI is only a proxy.
- API history and latest expose raw_pair_spread, prior_mean, prior_std, z_score, sample_count and cutoff. Latest metrics are null when its legs are missing/unusable. Previous single-contract percentage-deviation signals are retired in the active API; the legacy reference API remains separate. Historical replay consumes these raw-spread z-score signals.
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
