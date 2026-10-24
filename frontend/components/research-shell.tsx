"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Activity, ArrowDownUp, CircleHelp, Database, FlaskConical, LayoutDashboard, RefreshCw, Timer, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Contract, Dataset, Research, View } from "@/lib/types";
import { Dashboard } from "@/components/research-views";
import { PairWorkspace } from "@/components/pair-workspace";

const navigation = [
  { view: "dashboard", label: "Prices", hint: "Follow one contract", href: "/", icon: LayoutDashboard },
  { view: "compare", label: "Compare prices", hint: "See contracts side by side", href: "/compare", icon: ArrowDownUp },
  { view: "signals", label: "Price signals", hint: "Compare matched pair spreads", href: "/signals", icon: Activity },
  { view: "backtest", label: "Paired backtest", hint: "Hypothetical trades after assumed costs", href: "/backtest", icon: Timer },
] as const;
const headings: Record<View, [string, string]> = {
  dashboard: ["Follow a gold contract", "Choose a contract below to see its price, recent movement and trading activity."],
  compare: ["Compare gold prices", "See prices per gram across contracts. The contract you choose below is the reference for each price difference."],
  signals: ["Is the matched pair spread unusual?", "Choose two contracts with the same expiry to see whether their price difference is unusual."],
  backtest: ["Test hypothetical paired trades", "Choose a pair, review the assumed costs, then run a hypothetical simulation."],
};

export function ResearchShell({ view }: { view: View }) {
  const banner = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const observer = new ResizeObserver(() => {
      document.documentElement.style.setProperty("--dataset-banner-height", `${banner.current?.offsetHeight ?? 0}px`);
    });
    if (banner.current) observer.observe(banner.current);
    return () => { observer.disconnect(); document.documentElement.style.removeProperty("--dataset-banner-height"); };
  }, []);
  const [dataset, setDataset] = useState<Dataset>("synthetic");
  useEffect(() => { if (new URLSearchParams(window.location.search).get("dataset") === "real") setDataset("real"); }, []);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [selected, setSelected] = useState("");
  const [asOf, setAsOf] = useState("");
  const [draft, setDraft] = useState("");
  const [data, setData] = useState<Research | null>(null);
  const [error, setError] = useState("");
  const [booting, setBooting] = useState(true);
  const [loading, setLoading] = useState(false);
  const [healthy, setHealthy] = useState(false);
  const [retry, setRetry] = useState(0);
  const unavailableSelection = !!selected && !contracts.some(c => c.contract_id === selected);
  function chooseContract(id: string) {
    setData(null); setSelected(id); setError("");
    const url = new URL(window.location.href);
    url.searchParams.set("contract", id);
    url.searchParams.set("dataset", dataset);
    window.history.replaceState(null, "", url);
  }

  useEffect(() => {
    const controller = new AbortController();
    setBooting(true); setData(null); setError("");
    const queryCutoff = asOf || new URLSearchParams(window.location.search).get("asOf");
    const params = new URLSearchParams({dataset});
    if (queryCutoff) params.set("as_of", queryCutoff);
    Promise.all([
      api<{ contracts: Contract[]; default_as_of: string }>(`contracts?${params}`, controller.signal),
      api<{ status: string }>("health", controller.signal),
    ]).then(([catalog, health]) => {
      if (controller.signal.aborted) return;
      const query = new URLSearchParams(window.location.search);
      const requested = (query.get("dataset") || "synthetic") === dataset ? query.get("contract") : null;
      setContracts(catalog.contracts);
      setSelected(previous => previous || requested || catalog.contracts.find(c => c.symbol === "GOLDM")?.contract_id || catalog.contracts[0]?.contract_id || "");
      const cutoff = query.get("asOf") || catalog.default_as_of;
      setAsOf(previous => previous || cutoff); setDraft(previous => previous || cutoff.replace(/Z$/, ""));
      setHealthy(health.status === "ok"); setLoading(false); setBooting(false);
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setHealthy(false); setBooting(false); } });
    return () => controller.abort();
  }, [retry, dataset, asOf]);

  useEffect(() => {
    if (booting || !selected || !asOf) return;
    if (unavailableSelection) {
      setLoading(false); setData(null);
      setError(`The selected contract (${selected}) is not in this dataset at the chosen cutoff. This may be a link to an older demo version. Choose an available contract below; Retry cannot restore a missing version.`);
      return;
    }
    const controller = new AbortController();
    setLoading(true); setError(""); setData(null);
    api<Research>(`research?${new URLSearchParams({ contract_id: selected, as_of: asOf, dataset })}`, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setData(result); setLoading(false); setHealthy(true); } })
      .catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false); setHealthy(false); } });
    return () => controller.abort();
  }, [selected, asOf, booting, retry, dataset, unavailableSelection]);

  const query = selected && asOf ? `?${new URLSearchParams({ contract: selected, asOf, dataset })}` : "";
  const busy = booting || loading;
  return <div className="min-h-screen">
    <header className="border-b border-border bg-card">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-5 sm:px-8">
        <Link href={"/" + query} className="flex items-center gap-3" aria-label="GoldLens home"><Logo /><span className="text-xl font-semibold">GoldLens<span className="mt-0.5 block text-xs font-normal text-muted-foreground">Gold contract research</span></span></Link>
        <span className="text-right text-xs text-muted-foreground">Local workspace<br /><span className={healthy ? "text-success" : "text-muted-foreground"}>{healthy ? "API connected" : busy ? "Connecting..." : "Connection needs attention"}</span></span>
      </div>
    </header>
    <div ref={banner} data-testid="dataset-banner" role="note" aria-label="Dataset disclosure" className="sticky top-0 z-50 border-y border-primary/25 bg-card">
      <div className="mx-auto flex max-w-6xl items-start gap-3 px-5 py-3 text-xs leading-5 sm:px-8 sm:text-sm"><FlaskConical size={18} className="mt-0.5 shrink-0 text-primary" /><p><strong className="text-primary">{dataset === "synthetic" ? "SYNTHETIC DATA" : "IMPORTED REAL DATA"}</strong><span className="ml-2 text-muted-foreground">{dataset === "synthetic" ? "Invented prices and contract terms. No live market data." : "Locally imported records. No live feed or synthetic fallback."}</span></p></div>
    </div>
    <div className="mx-auto max-w-6xl px-5 py-6 sm:px-8">
      <nav aria-label="Main navigation" className="mb-7 grid grid-cols-2 gap-1 rounded-lg bg-card p-1 sm:grid-cols-4">{navigation.map(n => <Link key={n.view} href={n.href + query} aria-current={view === n.view ? "page" : undefined} className={`rounded-md px-3 py-3 ${view === n.view ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><span className="flex items-center gap-2 text-sm font-semibold"><n.icon size={17} className="shrink-0" />{n.label}</span><span className="sr-only">{n.hint}</span></Link>)}</nav>
      <main id="main-content">
        <div className="mb-6"><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{headings[view][0]}</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">{headings[view][1]}</p></div>
        <Card className="mb-6 p-4 sm:p-5"><label className="mb-4 block max-w-sm text-sm">Dataset<select aria-label="Dataset" className="field mt-2" value={dataset} onChange={e => { setData(null); setSelected(""); setDataset(e.target.value as Dataset); }}><option value="synthetic">Synthetic demo v4</option><option value="real">Imported real data</option></select></label>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-0 flex-1 basis-64"><label htmlFor="contract" className="mb-2 block text-sm font-medium">{view === "compare" ? "Compare against this contract" : view !== "dashboard" ? "First contract (A)" : "Choose a gold contract"}</label><select id="contract" className="field" value={selected} disabled={booting || !contracts.length} onChange={e => chooseContract(e.target.value)}>{unavailableSelection && <option value={selected} disabled>Unavailable: {selected}</option>}{!contracts.length && <option value="">{booting ? "Loading contracts..." : "No contracts available"}</option>}{contracts.map(c => <option key={c.contract_id} value={c.contract_id}>{contractName(c.symbol)} ({c.symbol}) / expires {c.expiry}</option>)}</select><p className="mt-2 text-xs leading-5 text-muted-foreground">Expiry is the exact date the contract ends. Each expiry is a separate contract.</p></div>
            <Button variant="outline" onClick={() => setRetry(r => r + 1)} disabled={busy}><RefreshCw size={14} className={busy ? "animate-spin" : ""} />Reload data</Button>
          </div>
          <details className="mt-4 border-t border-border pt-4"><summary className="text-sm text-muted-foreground">Change research time <span className="mt-1 block text-xs">Using information available by {asOf ? asOf.replace("T", " ").replace("Z", " UTC") : "?"}</span></summary>
            <p className="mt-4 max-w-2xl text-sm leading-6 text-muted-foreground">Look back at what was known at a specific time. A price is included only when it had been both observed and made available by this time.</p>
            <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); const next = draft.length === 16 ? `${draft}:00Z` : `${draft}Z`; if (next !== asOf) { setData(null); setAsOf(next); const url = new URL(window.location.href); url.searchParams.set("asOf", next); url.searchParams.set("dataset", dataset); url.searchParams.set("contract", selected); window.history.replaceState(null, "", url); } }}>
              <div className="min-w-0 flex-1 basis-60"><label htmlFor="asof" className="mb-2 block text-sm">Information cutoff (UTC)</label><input id="asof" className="field number" type="datetime-local" step="1" value={draft} onChange={e => setDraft(e.target.value)} required disabled={booting} /></div>
              <Button type="submit" disabled={booting || !selected}>Apply time</Button>
            </form>
          </details>
        </Card>
        <div role="status" aria-live="polite" className="mb-5 text-xs leading-5 text-muted-foreground">{data ? `${data.spec.symbol} ? ${data.metrics.count} available prices ? As of ${data.as_of.replace("T", " ").replace("Z", " UTC")}` : busy ? "Loading research..." : "No results displayed"}</div>
        {error ? <Card className="p-8" role="alert"><TriangleAlert className="mb-3 text-warning" /><h2 className="font-medium">Unable to load research</h2><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{error}</p><Button className="mt-5" variant="outline" onClick={() => unavailableSelection && contracts.length ? chooseContract(contracts.find(c => c.symbol === "GOLDM")?.contract_id || contracts[0].contract_id) : setRetry(r => r + 1)}>{unavailableSelection && contracts.length ? "Use an available contract" : "Retry connection"}</Button></Card> : busy ? <Loading /> : !data || (!data.latest && view === "dashboard") ? <Card className="p-10 text-center"><Database className="mx-auto mb-4 text-muted-foreground" /><h2 className="text-lg">No prices available at this time</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">{data?.spec.normalization_reason || (dataset === "real" && !contracts.length ? "No imported contracts are available at this cutoff. Import validated real records or choose Synthetic demo to explore the app." : "Open Change research time and choose a later time. No future prices or substitute datasets are shown.")}</p></Card> : <>
          {view === "dashboard" && data.latest && <Dashboard data={data} />}{view !== "dashboard" && <PairWorkspace key={data.dataset + data.spec.contract_id + data.as_of} data={data} contracts={contracts} view={view} />}
        </>}
        {data && data.issues.length > 0 && <Card className="mt-5 p-5"><h2 className="font-medium">Blocked price records</h2>{data.issues.map((issue, i) => <p className="mt-2 text-xs" key={i}>{issue.contract_id} / {issue.trading_date}: {issue.code} - {issue.reason}</p>)}</Card>}
        <details className="mt-6 rounded-lg border border-border bg-card p-4 text-sm"><summary>Terms explained</summary><dl className="mt-4 grid gap-4 text-sm leading-6 sm:grid-cols-2"><div><dt className="font-medium">Quote price</dt><dd className="text-muted-foreground">The price for the contract&apos;s stated weight of gold. Use Compare prices to see a common price per gram.</dd></div><div><dt className="font-medium">Trading volume</dt><dd className="text-muted-foreground">The number of contracts traded during the recorded period.</dd></div><div><dt className="font-medium">Open interest</dt><dd className="text-muted-foreground">The number of contracts still open, rather than closed or settled.</dd></div><div><dt className="font-medium">Baseline and signals</dt><dd className="text-muted-foreground">Spread is left minus right in 999-purity INR/gram. A z-score measures its distance from the prior spread mean in sample standard deviations (ddof=1), excluding the current spread.</dd></div></dl></details>
        {data && <details className="mt-3 rounded-lg border border-border p-4 text-sm"><summary className="text-muted-foreground">Technical details / API response</summary><pre data-testid="api-response" className="mt-4 max-h-80 overflow-auto text-xs leading-5 text-muted-foreground">{JSON.stringify(data, null, 2)}</pre></details>}
        <footer className="mt-8 border-t border-border py-5 text-xs leading-6 text-muted-foreground"><CircleHelp className="mr-1.5 inline size-3" />{data?.disclaimer ?? "Synthetic research only. No guaranteed arbitrage. Fees, taxes, slippage, liquidity, execution and settlement uncertainty matter. No trade execution."}</footer>
      </main>
    </div>
  </div>;
}

function contractName(symbol: string) { return ({ GOLDM: "Gold Mini", GOLDTEN: "Gold Ten", GOLDGUINEA: "Gold Guinea", GOLDPETAL: "Gold Petal" } as Record<string, string>)[symbol] ?? symbol; }

function Logo() { return <svg width="29" height="34" viewBox="0 0 29 34" aria-hidden="true"><path d="M14.5 1 28 9v16l-13.5 8L1 25V9Z" fill="none" stroke="var(--primary)" strokeWidth="1.6" /><path d="m7 21 7.5-13L22 21H7Zm7.5-7v13" fill="none" stroke="var(--primary)" strokeWidth="1.4" /></svg>; }
function Loading() { return <div aria-label="Loading research" className="space-y-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0,1,2,3].map(i => <Card key={i} className="space-y-5 p-5"><div className="skeleton h-3 w-24" /><div className="skeleton h-8 w-32" /><div className="skeleton h-2 w-28" /></Card>)}</div><Card className="h-80 p-6"><div className="skeleton mb-8 h-4 w-40" /><div className="skeleton h-52 w-full" /></Card></div>; }
