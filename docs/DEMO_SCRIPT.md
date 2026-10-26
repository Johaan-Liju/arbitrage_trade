<<<<<<< HEAD
# Three-minute offline demo

Before starting: install dependencies once, `npm.cmd --prefix frontend run build`, then `npm.cmd run local`. Open http://127.0.0.1:3000. Default cutoff is 2026-10-23T18:00:00Z. No internet/feed is required after setup.

**0:00–0:30 — Overview.** Point to SYNTHETIC DATA. Select GOLDTEN · 2026-11-24 · demo-v3. Explain that contracts and observations are invented; quotation/lot/purity arithmetic exercises use explicit terms. Inspect exact expiry, quote unit, lot and observation ledger.

**0:30–1:15 — Compare.** Select B GOLDGUINEA · 2026-11-27 · demo-v3. Read the CALENDAR_BASIS_DIFFERENCE warning aloud. Trace both normalized series, raw spread and expected basis. Explain that 999-equivalent INR/g compares gold content but does not estimate executable arbitrage. Hover a chart point or expand the paired ledger for originals/source/time.

**1:15–1:45 — Signals and quality.** Open Signals and keep the same pair. Latest TEN spike should be INVESTIGATE, with a threshold reason, prior baseline, difference, z-score, volume/OI and freshness. Show the warm-up at the start of the history and the quality checks. Explain that no observation trains on itself and real analytics remain blocked pending chronology/calendar verification.

**1:45–2:40 — Backtest.** With calendar acknowledgement unchecked, Run simulation: no accepted calendar entries; inspect rejection reasons. Check the visible acknowledgement and run again. Inspect an accepted trade, its signal date, strictly later entry, later exit, four TEN lots versus five GUINEA lots, raw-quote leg notionals, entry/exit fees and slippage. Read the actual net P&L from the backend report; do not imply profit is guaranteed. Show the equity curve, drawdown and directional sensitivity disclaimer.

**2:40–3:00 — No-trade and limits.** Set entry threshold 100 and run: zero trades, explicit explanation, zero net P&L. State that daily settlements are not fills, calendars are synthetic, taxes/margins/delivery are incomplete and nothing executes orders.

## Reproducible gates

- Gate 3 hand checks: CONTRACT_MATRIX.md, tested by `test_hand_calculations_quote_not_lot`.
- Gate 4 anomaly change: `python -m backend.demo_gates` compares fixtures with injected anomaly 0 and 140 without modifying published observations; status and explanation change.
- Gate 5: same command prints accepted, calendar-rejected and high-threshold no-trade reports; tests verify per-leg costs and missing-fill handling.
- Browser QA uses a fresh automated Edge profile, never personal browser data. Screenshots go to ignored `artifacts/`.
=======
# GoldLens demo (active v4)

1. Prices: select GOLDTEN / 2026-11-20 / demo-v4. Read the sticky SYNTHETIC disclosure. Hover across the chart; date/price stays in a fixed readout. Inspect quote source, observation time and availability.
2. Compare prices: choose GOLDGUINEA / 2026-11-20 as B. Trace quoted INR / quotation grams * 999 / purity per mille. GOLDM has a 10g quote and 100g lot; they are different concepts. Read unsupported exact-expiry alternatives and delivery/settlement differences. Matching expiry does not imply interchangeable contracts.
3. Price signals: inspect Investigate and its reason. Set entry threshold 100 for No signal. Use cutoff 2026-09-02T18:00:00Z for Insufficient data during warm-up. Return to 2026-10-23T18:00:00Z. Prior mean and sample standard deviation exclude the current spread; no machine learning is claimed.
4. Paired backtest: retain GOLDTEN/GOLDGUINEA and set holding limit 3. Run with hypothetical brokerage/slippage and optional per-leg costs. Check 4 ten-gram versus 5 eight-gram whole lots, later entry/exit observations, itemized costs, residual exposure and gross minus costs minus slippage equals net. Open positions and skipped/unfilled orders remain separate.
5. Prices: change cutoff to 2026-09-01T16:00:00Z, before publication. No future prices appear. Scroll desktop/mobile and confirm the banner remains visible without blocking chart interaction. No orders are sent; these results do not establish executable arbitrage.
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
