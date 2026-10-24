# Simpler GoldLens navigation

## Observed public evidence

On 2026-10-24, REA `capture_browser_scenario` launched installed Edge headlessly with a fresh temporary profile at https://www.mcxindia.com/, waited 3 seconds, and captured DOM, accessibility and screenshot at 1440 x 1000. The page returned **Access Denied**, not the MCX interface. REA reported `terminated-owned-process` cleanup.

- Evidence: `ev_24275684ede67c0750e1d7a1743efee5054a53ac3aa266c8671c77b8e6de396d`
- DOM SHA-256: `dcedde2076b1a2b3f080803661c82c9e72a8344ce4c6f85fb5fb981205e24467`
- Screenshot SHA-256: `3a39b516fa2daae521b4db5f0eac77d3aebd781ef994c7e8b4f851cc62dbe812`

Public page text was available separately through the web reader:

- [MCX home](https://www.mcxindia.com/): separates market data, product information, education and operations. Its market-data navigation separates current prices, comparisons and historical reports.
- [Market Watch](https://www.mcxindia.com/market-data/market-watch)
- [Compare Commodities](https://www.mcxindia.com/market-data/compare-products)
- [Gold product information](https://www.mcxindia.com/products/bullion/gold)

This establishes the public information architecture only. MCX rendered appearance, interactive controls and browser behavior were not verified. No MCX code, branding or market data was copied into GoldLens.

## Design decisions

Use four task-based destinations, each with an explanation visible before opening it:

| Destination | Purpose |
| --- | --- |
| Prices | Follow one exact contract and its price history. |
| Compare prices | Compare normalized prices against the selected reference. |
| Price signals | Explain deviations from each contract's previous five prices. |
| Signal history | Replay past signals without implying simulated trades or profit. |

Replace the sidebar and separate mobile navigation with one responsive navigation grid. Keep contract choice prominent. Put historical time editing behind an expandable control while keeping the active cutoff visible. Use full contract names alongside symbols and exact expiry dates. Expand technical records, specification details and JSON only when requested. Add a glossary and increase table/control text sizes.

Existing routes, API contracts, data separation, point-in-time calculations and synthetic labels remain in force. The signals page explains that its cards cover all available contracts; the shared contract choice carries across pages.

## Remaining questions

Whether these labels improve comprehension for the user requires user feedback. MCX visual fidelity cannot be assessed from the blocked browser capture; this change uses public navigation structure and independently designed local UI.
