# GoldLens working rules

- Build a local-first gold contract research app in small, testable vertical slices.
- Keep synthetic and real data in separate datasets and storage paths. Label synthetic data in APIs and UI. Never silently fall back to synthetic data when real data fails.
- Version contract specifications immutably. Every price must reference a specific specification version, trading date, contract symbol, and exact expiry date. Require currency, unit, source, observation time, and availability time. Never infer an expiry from a month label.
- Indicators must use only records observed AND available at or before an explicit as-of time. Partition by dataset, symbol, expiry, and specification version. Backtests must use point-in-time spec versions too.
- Never claim guaranteed arbitrage. Research signals must disclose relevant costs, liquidity, execution, and settlement uncertainty; do not execute trades.
- Ask before deploying, pushing, installing invasive system software, or inspecting third-party private data. Do not read credentials or unrelated personal files.
- Run relevant validation and record exact commands and actual results in docs/BUILD_LOG.md. Distinguish observed facts, design decisions, and unresolved questions.
- The initial Node-only slice is retained as legacy reference. The current user-authorized stack is Next.js/TypeScript/Tailwind/shadcn with FastAPI/Pandas/SQLite. Keep dependencies project-local and bind both services only to loopback. The frontend displays API results; business calculations belong in the backend.
