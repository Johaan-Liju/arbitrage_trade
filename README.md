# GoldLens

Local-first gold contract research scaffold. Requires Node.js 24 or newer; no dependencies or installation step.

```powershell
npm.cmd run check
npm.cmd test
npm.cmd run health
npm.cmd start
```

Open http://127.0.0.1:4310. Stop with Ctrl+C. Set `PORT` to choose another port. The service binds only to IPv4 loopback.

The dashboard lets you move a UTC information cutoff through three explicitly synthetic prices. The mean uses only observations available at that cutoff. The demo defaults to 2026-10-22T16:01:00Z, not the current time.

- `GET /api/health`: readiness and dataset status.
- `GET /api/snapshot?dataset=synthetic&asOf=2026-10-21T16:01:00Z`: point-in-time demonstration.
- `dataset=real`: explicit 404; never substituted with synthetic data.

Fixtures are local JSON under `data/synthetic`. Contract specs are append-only versions: create a new version and reference it from new records instead of modifying an existing published version. Real-data storage is reserved under ignored `data/real`; no importer is implemented. There is no database, authentication, market feed, trading, or external network dependency. Exchange timezone/session validation, cost modeling and real-data provenance verification are future slices. The current synthetic trading dates are UTC calendar dates.

Research results are not guaranteed arbitrage. Costs, liquidity, execution and settlement uncertainty matter.

See [project rules](AGENTS.md), [plan](docs/PLAN.md), and [actual build results](docs/BUILD_LOG.md).

REA tooling is available from this workspace with `.\rea.cmd --version` or `.\rea.cmd --help`. The launcher uses the verified REA 6.7.0 package in the local npm cache (retain that cache entry). Codex's REA MCP registration is enabled; restart Codex to attach its tools. No native analysis engines were installed.
