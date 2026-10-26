# Real market source collection

The normal application uses real data only. Synthetic fixtures are available only
to isolated tests that explicitly pass `real_only=False` to the API factory.

Collect the four public Upstox gold pages from the project root:

```powershell
.venv/Scripts/python.exe -m backend.public_sources GOLDM GOLDTEN GOLDGUINEA GOLDPETAL
```

This downloads public HTML, extracts the embedded JSON without executing page
scripts, and archives immutable HTML and structured records in
`data/real/sources/<symbol>/`. Failures are reported per symbol and return a nonzero
exit code; no substitute prices are generated. No API key or account is required.
The actual collector is Python urllib; TinyFish was attempted but failed.

The Monitor shows collected quotes with exact expiry dates and source links.
When no validated real database exists, the contracts, monitor and research APIs
explicitly use the source archive for raw quotes, chart history and descriptive
changes. Selectors, watchlists, cutoffs and refresh remain usable. A corrupt
validated database is never replaced silently with source records.
`GET /api/sources?as_of=<UTC timestamp>` excludes snapshots collected after the
requested cutoff. Historical closes become known at collection time; historical
publication times are unknown. Displayed prices use the source's explicit price
divisor, but are not normalized per gram. A content hash identifies each immutable
unverified source specification snapshot.

These records are **not model-ready**. Verified official specifications, exact
listings, session calendars and observation timestamps are still required by the
existing importer. Once those are established, submit a reviewed CSV, manifest
and reference registry to `/api/ingest` with `dry_run: true`, resolve every issue,
then import with `dry_run: false`. Source snapshots never bypass that validation.
The research model and backtests remain unavailable until validated inputs exist.
Paper sessions can still be saved and scanned: scans persist an explicit
abstention reason and history without issuing unsupported opportunity alerts.

If the local API is offline, run `.venv/Scripts/python.exe scripts/start-local.py`
after stopping existing GoldLens services. It starts both services on loopback
and keeps them running until stopped. Check both services and the frontend proxy
with `.venv/Scripts/python.exe scripts/health-check.py`.

Refresh data in the UI rereads local archives. Rerun the collector explicitly to
download new snapshots; there is no background scraping or trade execution.
