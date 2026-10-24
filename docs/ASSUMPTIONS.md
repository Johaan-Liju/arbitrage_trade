# GoldLens assumptions and limitations

## Data and chronology

- Local synthetic database: `data/synthetic/goldlens-v3.sqlite3`. Reserved real path: `data/real/goldlens.sqlite3`. No fallback or real seeding. Legacy Node files remain untouched.
- Canonical SQLite tables: instruments, contract_spec_versions, contracts, daily_prices, signals, backtest_runs, trades. `specs` and `prices` are compatibility read views. Spec, contract and price update/delete triggers enforce append-only publication. New terms require a new immutable version; existing validity bounds cannot be edited retroactively.
- Every observation carries dataset, instrument symbol, exact contract/expiry, spec version, trading date, INR/quote, source, OHLC, settlement (`price`), volume, OI, observation, availability and ingestion timestamps. `price` is settlement and may differ from OHLC. OHLC must be internally consistent. All positive prices must be finite and ≤₹1 trillion per quote (an input safety bound, not an exchange limit); unusual normalized values are flagged for review.
- CSV has one exact documented schema. No implicit units or monthly expiry parsing. Duplicate keys, including stored keys, reject the entire import. Missing fields reject. Explicit expected session lists detect absent rows/closed days. Without a supplied calendar, synthetic ingestion reports calendar UNVERIFIED; no holiday guessing. Source and archived ingestion timestamps are supplied in the CSV and validated, not independently authenticated.
- Real ingestion and analytics are disabled. Verified quotation fields do not establish the missing exact effective/availability chronology or calendars. See CONTRACT_MATRIX.md.
- The demo has 39 weekdays, eight contracts, 312 settlements. Weekdays are not an exchange calendar. TEN anomalies of +₹140 per normalized gram are injected at indices 24, 25 and 38. Fixtures are deterministic and labelled synthetic everywhere.
- Query filtering requires both observed and available timestamps ≤ explicit UTC as-of. Every pair/replay is partitioned by both exact contract identities and spec versions. Historical decisions also filter prior observations by their own availability. Ingestion time is preserved for auditing and is not substituted for source availability.

## Statistical convention

- Normalize: quote / quote grams × (0.999 / purity). Preserve originals. Compare A minus B. The active API requires identical exact expiries; the legacy reference API can display calendar differences. No silent rolling or forward fill.
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

## Verified features versus unsupported claims

| Implemented and tested | Unsupported |
|---|---|
| Immutable specs and exact expiry/version identity | Complete historical MCX spec/calendar timeline |
| Strict CSV validation and atomic imports | Automatic bhavcopy schema detection or real feed |
| 999-equivalent normalization with provenance | Economic interchangeability or executable spread |
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
