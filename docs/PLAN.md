# GoldLens implementation plan

1. Inspect the workspace and runtimes; identify REA separately. Write project rules and this log before code.
2. Scaffold a dependency-free Node HTTP app with a local dashboard, /api/health, and explicitly synthetic sample data.
3. Add immutable versioned synthetic contract specs, strict price identity validation, and an as-of mean that excludes future observations and late-arriving records.
4. Run domain tests and actual HTTP smoke checks. Document commands, results, startup instructions, and limits.

Later slices: user-authorized real-data import into separate local storage with provenance and exchange-calendar validation; cost-aware comparisons; point-in-time replay. These are not part of the initial scaffold.

Design choice: buildless HTML/CSS/JS served by Node 24, with no remote assets, analytics, dependencies, or market-data access. Prices are illustrative USD per troy ounce in an invented contract, not exchange specifications. Real data remains unavailable until an explicit import slice.
