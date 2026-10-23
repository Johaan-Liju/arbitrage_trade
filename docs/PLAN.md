# GoldLens implementation plan

## Current stack migration

1. Set up a project-local Python virtual environment and Next.js/TypeScript/Tailwind frontend with shadcn components.
2. Build deterministic synthetic SQLite storage for GOLDM, GOLDTEN, GOLDGUINEA and GOLDPETAL. Use invented versioned specs, explicit exact expiries, immutable spec triggers, complete provenance and separate real-data paths.
3. Gate further UI work on a browser selecting a contract and rendering a response from the running FastAPI backend. All calculation and filtering stays in Python/Pandas.
4. Complete a dark workspace with Dashboard, Compare, Signals and Backtest views, as-of controls, synthetic banners and loading/empty/error states.
5. Run backend tests, frontend production build and browser checks; document actual results and local launch commands.

Scope: invented demonstration specifications, not verified exchange contracts. Compare uses explicit synthetic quote-weight normalization. Signals describe historical deviations, not actionable arbitrage. Backtest is a point-in-time signal replay without fills or profit claims. No trading, external market feeds, deployment or third-party private-data access.

## Original completed slice

1. Inspect the workspace and runtimes; identify REA separately. Write project rules and this log before code.
2. Scaffold a dependency-free Node HTTP app with a local dashboard, /api/health, and explicitly synthetic sample data.
3. Add immutable versioned synthetic contract specs, strict price identity validation, and an as-of mean that excludes future observations and late-arriving records.
4. Run domain tests and actual HTTP smoke checks. Document commands, results, startup instructions, and limits.

Later slices: user-authorized real-data import into separate local storage with provenance and exchange-calendar validation; cost-aware comparisons; point-in-time replay. These are not part of the initial scaffold.

Design choice: buildless HTML/CSS/JS served by Node 24, with no remote assets, analytics, dependencies, or market-data access. Prices are illustrative USD per troy ounce in an invented contract, not exchange specifications. Real data remains unavailable until an explicit import slice.
