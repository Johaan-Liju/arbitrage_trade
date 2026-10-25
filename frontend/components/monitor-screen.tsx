"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Contract, Dataset, Monitor, MonitorRow } from "@/lib/types";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { PriceChart } from "@/components/research-views";

const fmt = (value: string | number | null, digits = 2): string => value === null ? "Not supplied" : Number(value).toLocaleString("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
const stamp = (value: string) => value.replace("T", " ").replace("Z", " UTC");
const key = (dataset: Dataset) => `goldlens.monitor.watchlist.${dataset}`;
function saved(dataset: Dataset): string[] | null {
  try { const value = JSON.parse(localStorage.getItem(key(dataset)) || "null"); return Array.isArray(value) && value.every(v => typeof v === "string") ? value : null; } catch { return null; }
}

export function MonitorScreen() {
  const [ready, setReady] = useState(false);
  const [dataset, setDataset] = useState<Dataset>("synthetic");
  const [selected, setSelected] = useState("");
  const [cutoff, setCutoff] = useState("");
  const [draft, setDraft] = useState("");
  const [limit, setLimit] = useState(72);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [watched, setWatched] = useState<string[] | null>(null);
  const [data, setData] = useState<Monitor | null>(null);
  const [error, setError] = useState("");
  const [connected, setConnected] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(true);
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    const query = new URLSearchParams(window.location.search);
    const owner = query.get("dataset") === "real" ? "real" : "synthetic";
    setDataset(owner); setWatched(saved(owner)); setSelected(query.get("contract") || "");
    setCutoff(query.get("asOf") || ""); setDraft((query.get("asOf") || "").replace(/Z$/, "")); setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    setBusy(true); setData(null); setError(""); setConnected(null);
    api<{ status: string }>("health", controller.signal).then(r => { if (!controller.signal.aborted) setConnected(r.status === "ok"); }).catch(() => { if (!controller.signal.aborted) setConnected(false); });
    async function load() {
      try {
        const params = new URLSearchParams({ dataset });
        if (cutoff) params.set("as_of", cutoff);
        const catalog = await api<{ contracts: Contract[]; default_as_of: string }>(`contracts?${params}`, controller.signal);
        if (controller.signal.aborted) return;
        setContracts(catalog.contracts);
        const asOf = cutoff || catalog.default_as_of;
        params.set("as_of", asOf); params.set("stale_after_hours", String(limit));
        if (selected) params.set("contract_id", selected);
        const result = await api<Monitor>(`monitor?${params}`, controller.signal);
        if (controller.signal.aborted) return;
        setData(result); setDraft(asOf.replace(/Z$/, "")); setBusy(false);
        const url = new URL(window.location.href);
        url.search = new URLSearchParams({ dataset, asOf, ...(result.selected ? { contract: result.selected.contract.contract_id } : {}) }).toString();
        window.history.replaceState(null, "", url);
      } catch (e) {
        if (!controller.signal.aborted) { setError(e instanceof Error ? e.message : "Unable to load data"); setBusy(false); }
      }
    }
    void load();
    return () => controller.abort();
  }, [ready, dataset, selected, cutoff, limit, retry]);

  const active = contracts.find(c => c.contract_id === selected) || data?.selected?.contract;
  const symbols = [...new Set(contracts.map(c => c.symbol))];
  const symbolContracts = contracts.filter(c => c.symbol === active?.symbol);
  const expiries = [...new Set(symbolContracts.map(c => c.expiry))];
  const versions = symbolContracts.filter(c => c.expiry === active?.expiry);
  const ids = watched ?? contracts.map(c => c.contract_id);
  function saveWatchlist(next: string[]) {
    setWatched(next);
    try { localStorage.setItem(key(dataset), JSON.stringify(next)); } catch { /* Session watchlist remains usable without storage. */ }
  }
  function choose(id: string) {
    if (id === selected) return;
    setData(null); setSelected(id); setError("");
    const url = new URL(window.location.href);
    if (id) url.searchParams.set("contract", id); else url.searchParams.delete("contract");
    window.history.replaceState(null, "", url);
  }
  function changeDataset(next: Dataset) {
    const asOf = data?.as_of || cutoff;
    setData(null); setContracts([]); setSelected(""); setError(""); setWatched(saved(next)); setDataset(next);
    if (asOf) setCutoff(asOf);
    const url = new URL(window.location.href);
    url.searchParams.set("dataset", next); url.searchParams.delete("contract");
    if (asOf) url.searchParams.set("asOf", asOf);
    window.history.replaceState(null, "", url);
  }
  const query = new URLSearchParams({ dataset, ...(data ? { asOf: data.as_of } : cutoff ? { asOf: cutoff } : {}), ...(active ? { contract: active.contract_id } : {}) });

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-8">
    <header className="mb-6 flex items-center justify-between gap-4"><Link href={`/?${query}`} className="text-xl font-semibold text-primary">GoldLens</Link><nav aria-label="Main navigation" className="flex gap-5"><Link href={`/?${query}`} aria-current="page">Monitor</Link><Link href={`/alerts?${query}`}>Alerts</Link></nav></header>
    <main>
      <h1 className="text-3xl font-semibold">Monitor</h1>
      <p className="mt-2 text-sm text-muted-foreground">Watch exact contracts and compare prices known at your UTC cutoff.</p>
      <div role="note" aria-label="Dataset disclosure" data-testid="dataset-banner" className="my-5 rounded-lg border border-primary/30 bg-card p-4 text-sm"><strong className="text-primary">{dataset === "synthetic" ? "SYNTHETIC DATA" : "IMPORTED REAL DATA"}</strong><p className="mt-1 text-muted-foreground">{dataset === "synthetic" ? "Invented prices, specifications and liquidity. No live market data." : "Locally imported source records. No live feed or synthetic fallback."}</p></div>
      <Card className="mb-5 p-4">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <label>Dataset<select aria-label="Dataset" className="field mt-2" value={dataset} onChange={e => changeDataset(e.target.value as Dataset)}><option value="synthetic">Synthetic demo</option><option value="real">Imported real data</option></select></label>
          <label>Symbol<select aria-label="Symbol" className="field mt-2" value={active?.symbol || ""} disabled={busy || !contracts.length} onChange={e => choose(contracts.find(c => c.symbol === e.target.value)!.contract_id)}><option value="" disabled>Choose symbol</option>{symbols.map(s => <option key={s}>{s}</option>)}</select></label>
          <label>Exact expiry<select aria-label="Exact expiry" className="field mt-2" value={active?.expiry || ""} disabled={busy || !active} onChange={e => choose(symbolContracts.find(c => c.expiry === e.target.value)!.contract_id)}><option value="" disabled>Choose exact date</option>{expiries.map(s => <option key={s}>{s}</option>)}</select></label>
          <label>Specification version<select aria-label="Specification version" className="field mt-2" value={active?.contract_id || ""} disabled={busy || !active} onChange={e => choose(e.target.value)}><option value="" disabled>Choose version</option>{versions.map(c => <option key={c.contract_id} value={c.contract_id}>{c.spec_version} / {c.spec_id}</option>)}</select></label>
        </div>
        <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); const next = `${draft}${draft.length === 16 ? ":00" : ""}Z`; if (next === cutoff) setRetry(n => n + 1); else setCutoff(next); }}>
          <label className="min-w-0 flex-1 basis-64">Information cutoff (UTC)<input aria-label="Information cutoff (UTC)" className="field mt-2" type="datetime-local" step="1" value={draft} onChange={e => setDraft(e.target.value)} required /></label>
          <Button type="submit" disabled={busy || !draft}>Apply time</Button><Button type="button" variant="outline" disabled={busy} onClick={() => setRetry(n => n + 1)}>Refresh data</Button>
          <label className="w-40">Stale after<select aria-label="Stale after" className="field mt-2" value={limit} onChange={e => setLimit(Number(e.target.value))}><option value={24}>24 hours</option><option value={72}>72 hours</option><option value={168}>7 days</option></select></label>
        </form>
      </Card>
      <Card className="mb-5 p-4" role="status" aria-live="polite"><p>API: {connected === null ? "Checking connection" : connected ? "Connected" : "Unavailable"} · Data: {busy ? "Loading" : error ? "Unavailable" : data?.selected?.freshness.status || "MISSING"}</p><p className="mt-2 text-xs text-muted-foreground">{data ? `Cutoff ${stamp(data.as_of)}. Freshness uses observation age at this cutoff, not the current clock. Limit: ${data.stale_after_hours} hours. Historical snapshot; refresh reads local imports.` : "Only the selected dataset is requested. Results clear while loading or after failure."}</p></Card>
      {error && <Card role="alert" className="mb-5 p-5"><h2 className="font-semibold">Your research workspace is waiting for data</h2><p className="mt-2 text-sm text-muted-foreground">{error === "Not Found" ? "The local API needs a restart to load Monitor. Restart the GoldLens backend, then try again." : "We could not load this snapshot. Try again, or choose another contract from the selected dataset."}</p><p className="mt-3 text-sm">Once connected, this space shows your contract watchlist, price history and freshness at the chosen cutoff.</p><details className="mt-3 text-xs text-muted-foreground"><summary>Connection details</summary><p className="mt-2">{error}</p></details><Button className="mt-3" onClick={() => setRetry(n => n + 1)}>Retry data</Button>{selected && <Button className="ml-3 mt-3" variant="outline" onClick={() => choose("")}>Choose an available contract</Button>}</Card>}
      {busy && <p role="status" className="p-5">Loading Monitor…</p>}
      {data && <div className="space-y-5">
        <Card className="min-w-0 overflow-hidden"><div className="flex flex-wrap items-center justify-between gap-3 p-5"><h2 className="text-lg font-semibold">Watchlist</h2>{active && !ids.includes(active.contract_id) && <Button onClick={() => saveWatchlist([...ids, active.contract_id])}>Add selected contract</Button>}</div>
          <p className="px-5 pb-4 text-xs text-muted-foreground">Changes compare the preceding available record in the same specification partition. Spreads are row minus selected contract in INR/g (999 purity), for fresh legs with identical exact expiries and trading dates. These are research comparisons; costs and delivery terms differ.</p>
          <div className="table-wrap"><table className="data-table" data-testid="watchlist"><thead><tr><th>Symbol / exact expiry / spec</th><th>Price / change</th><th>Spread INR/g (999)</th><th>Freshness</th><th>Source / observed / available</th><th>Watch</th></tr></thead><tbody>{data.watchlist.filter(r => ids.includes(r.contract.contract_id)).map(row => <tr key={row.contract.contract_id} className={row.contract.contract_id === active?.contract_id ? "selected-row" : ""}>
            <td><button className="text-left text-primary underline-offset-4 hover:underline" onClick={() => choose(row.contract.contract_id)}>{row.contract.symbol} / {row.contract.expiry}</button><span className="mt-1 block text-xs text-muted-foreground">{row.contract.spec_version} · {row.contract.spec_id}</span></td>
            <td>{row.latest ? <><span className="number">{fmt(row.latest.price)} {row.latest.currency}</span><span className="block text-xs text-muted-foreground">per {row.contract.quotation_grams} g · {row.latest.unit}</span><span className="mt-1 block number">{row.change === null ? "Change unavailable" : `${fmt(row.change)} (${fmt(row.change_pct)}%)`}</span>{row.previous_trading_date && <span className="block text-xs text-muted-foreground">vs {row.previous_trading_date}</span>}</> : "Missing price"}</td>
            <td className="max-w-60 whitespace-normal"><span className="number">{row.spread === null ? "Unavailable" : fmt(row.spread, 4)}</span><p className="mt-1 text-xs text-muted-foreground">{row.spread_reason}</p></td>
            <td className="max-w-56 whitespace-normal"><Freshness row={row} /></td>
            <td>{row.latest ? <><a className="text-primary underline" href={row.latest.source} target="_blank" rel="noreferrer">Price source</a><span className="block text-xs">{row.latest.source}</span><span className="block text-xs">Observed {stamp(row.latest.observed_at)}</span><span className="block text-xs">Available {stamp(row.latest.available_at)}</span></> : "No source observation at cutoff"}</td>
            <td><Button variant="ghost" size="sm" aria-label={`Remove ${row.contract.symbol} ${row.contract.expiry} ${row.contract.spec_version}`} onClick={() => saveWatchlist(ids.filter(id => id !== row.contract.contract_id))}>Remove</Button></td>
          </tr>)}</tbody></table></div>
          {!data.watchlist.some(r => ids.includes(r.contract.contract_id)) && <p className="p-5">Your watchlist is empty. Select a symbol and exact expiry above, then add it.</p>}
        </Card>
        {data.selected ? <Selected row={data.selected} prices={data.prices} /> : <Card className="p-5">No contracts are available in this dataset at the cutoff.</Card>}
        {!!data.issues.length && <details className="disclosure"><summary>Blocked observations ({data.issues.length})</summary>{data.issues.map((issue, i) => <p className="mt-2 text-xs" key={i}>{issue.contract_id} / {issue.trading_date}: {issue.code} — {issue.reason}</p>)}</details>}
      </div>}
      <footer className="mt-6 text-xs leading-6 text-muted-foreground">{data?.disclaimer || "Research only. Costs, liquidity, execution and settlement remain uncertain. No trade execution or guaranteed arbitrage."}</footer>
    </main>
  </div>;
}

function Freshness({ row }: { row: MonitorRow }) {
  return <><strong className={row.freshness.status === "FRESH" ? "text-success" : "text-warning"}>{row.freshness.status}</strong>{row.freshness.age_hours !== null && <span className="block text-xs">{fmt(row.freshness.age_hours, 1)} hours old at cutoff</span>}<p className="mt-1 text-xs text-muted-foreground">{row.freshness.reason}</p></>;
}
function Selected({ row, prices }: { row: MonitorRow; prices: Monitor["prices"] }) {
  const latest = row.latest;
  return <Card className="p-5" data-testid="selected-contract"><h2 className="text-lg font-semibold">{row.contract.symbol} / {row.contract.expiry}</h2><p className="mt-2 text-xs text-muted-foreground">Specification {row.contract.spec_id} / {row.contract.spec_version} · {row.contract.currency} per {row.contract.quotation_grams} g · {row.contract.unit}</p>
    <div className="my-4"><Freshness row={row} /></div>
    {latest ? <><p className="number text-3xl text-primary">{fmt(latest.price)} {latest.currency}</p><p className="mt-2 text-sm">Change {row.change === null ? "unavailable: no preceding record" : `${fmt(row.change)} (${fmt(row.change_pct)}%) vs ${row.previous_trading_date}`}</p>
      <p className="mt-2 text-xs text-muted-foreground">Trading date {latest.trading_date} · Normalized {fmt(latest.normalized_999_per_g, 4)} INR/g (999 purity)</p>
      <div className="my-5"><h3 className="mb-3 font-medium">Price history</h3><PriceChart prices={prices} /></div>
      <dl className="grid gap-3 text-xs sm:grid-cols-2"><div><dt>Source</dt><dd><a className="break-all text-primary underline" href={latest.source} target="_blank" rel="noreferrer">{latest.source}</a></dd></div><div><dt>Observed / available (UTC)</dt><dd>{stamp(latest.observed_at)}<br />{stamp(latest.available_at)}</dd></div>
        {latest.volume !== null && <div data-testid="source-volume"><dt>Source trading volume</dt><dd>{fmt(latest.volume, 0)} contracts</dd></div>}{latest.open_interest !== null && <div data-testid="source-oi"><dt>Source open interest</dt><dd>{fmt(latest.open_interest, 0)} contracts</dd></div>}
      </dl><p className="mt-3 text-xs text-muted-foreground">{latest.volume === null && latest.open_interest === null ? "Source did not supply liquidity information. " : "Volume and open interest are source proxies, not executable liquidity. "}Bid/ask quotes and market depth are not supplied; no bid/ask spread is inferred.</p>
    </> : <p>No prices available at this time. No future records or substitute datasets are displayed.</p>}
    <details className="mt-5 text-xs"><summary>Specification and settlement references</summary><p className="mt-2">Version available {stamp(row.contract.available_at)} · exact expiry {row.contract.expiry}</p><p className="mt-2">{row.contract.settlement_method} · {row.contract.settlement_terms} · {row.contract.delivery_location}</p><a className="mt-2 block break-all text-primary underline" href={row.contract.source} target="_blank" rel="noreferrer">Specification source: {row.contract.source}</a></details>
  </Card>;
}
