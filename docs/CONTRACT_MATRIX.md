# Contract matrix — evidence reviewed 2026-10-24

## Observed facts from original MCX PDFs

| Symbol | Quotation grams | Trading lot grams | Base purity | Quotation location | PDF contract scope |
|---|---:|---:|---:|---|---|
| GOLDM | 10 | 100 | 0.995 | Ahmedabad | August 2026 expiry onwards |
| GOLDTEN | 10 | 10 | 0.999 | Ahmedabad | July 2026 expiry onwards |
| GOLDGUINEA | 8 | 8 | 0.999 | Ahmedabad | July 2026 expiry onwards |
| GOLDPETAL | 1 | 1 | 0.999 | Mumbai | July 2026 expiry onwards |

Sources (original documents, not broker summaries):

- [GOLDM PDF](https://www.mcxindia.com/docs/default-source/about-us/gold-mini-august-2026-contract-onwards8a79913a-e8de-4136-9f0b-25d31dc163c4.pdf), pages 1–2 and 5: 10 g quote differs from 100 g lot. Expiry rule is the fifth, adjusted to the preceding working day if necessary. August-2026-onward scope appears in the launch calendar. It references circulars dated January 27, April 6, and July 1, 2026.
- [GOLDTEN PDF](https://www.mcxindia.com/docs/default-source/about-us/gold-ten-july-2026-contract-onwards.pdf), pages 1–4: 10 g quote and lot; 999 purity. Calendar-month-end expiry adjusted to the preceding working day. July-2026-onward calendar references January 27 and July 1, 2026 circulars.
- [GOLDGUINEA PDF](https://www.mcxindia.com/docs/default-source/about-us/gold-guinea-july-2026-contract-onwards.pdf), pages 1–4: **8 g quote**, 8 g lot, 999 purity. Calendar-month-end expiry with holiday adjustment. Calendar scope starts July 2026, referencing January 27 and July 1, 2026 circulars.
- [GOLDPETAL PDF](https://www.mcxindia.com/docs/default-source/about-us/gold-petal-july-2026-contract-onwards.pdf), pages 1–4: 1 g quote and lot, 999 purity; Mumbai basis. Calendar-month-end expiry with holiday adjustment. Calendar scope starts July 2026, referencing January 27 and July 1, 2026 circulars. No trading after DDR declaration is specified.

All four describe a three-trading-day tender period including expiry and compulsory delivery of remaining expiry positions. Ahmedabad-based products list Mumbai/New Delhi additional centers; Petal lists Ahmedabad/New Delhi. Quotes include import-related taxes/customs but exclude GST and specified additional levies. These terms do not make different products interchangeable. Refer to the full PDFs for supplier, quality, margin, delivery and settlement provisions.

The official [product index](https://www.mcxindia.com/products/bullion/gold) lists multiple versions and advises checking subsequent circulars. Search-result snippets and conflicting secondary-source quotation tables were not used as authoritative specifications.

## Operational verification gate

**UNVERIFIED for real analytics.** The numeric fields above were verified in originals; this is not a verified historical specification timeline. PDF contract-month scope is not a publication timestamp or exact effective trading date. Exact `valid_from`, `valid_to`, original availability, listed expiry dates, tender dates, holiday/special-session calendars and superseding circular coverage remain unresolved. No month label is converted into an expiry date. Missing values are null in [the evidence registry](evidence/mcx-specs-2026-10-24.json); `/api/spec-evidence` exposes it with `live_analytics_enabled=false`.

No operational real specification or real price dataset has been fabricated. All real API requests fail closed. A future real-data adapter must populate a fully evidenced immutable version and exact dated contract before analytics can be enabled.

## Synthetic decision

`demo-v3` uses these quote/lot/purity numbers for arithmetic exercises, but its contracts, effective dates, delivery descriptions, safe exits, calendars and all observations are **invented**. Its source is `synthetic://goldlens/demo-v3`, not an MCX PDF. Exact synthetic expiries are enumerated in code, not inferred. Older fixture databases are retained separately; v3 never overwrites their specifications.

## Gate 3: independent hand checks

1. GOLDM example: ₹74,625 / 10 = ₹7,462.50/g. Multiply by 999/995 = **₹7,492.50 per 999-equivalent g**. One 100 g lot has raw quote notional ₹74,625 × 100/10 = **₹746,250**, not ₹74,625.
2. GOLDTEN example: ₹75,000 / 10 × 999/999 = **₹7,500/g**.
3. GOLDGUINEA example: ₹60,080 / 8 × 999/999 = **₹7,510/g**. A=TEN minus B=GUINEA raw comparison spread is **−₹10/g**.

These are comparison conventions. Expected basis is fitted only on prior available raw spreads. Residual equals raw spread minus that expected basis. A historical residual baseline is also prior-only. Neither purity conversion nor a statistical residual estimates executable profit.
