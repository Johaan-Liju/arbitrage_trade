"use client";

import Link from "next/link";
<<<<<<< HEAD
import { useEffect, useState } from "react";
import { Activity, ArrowDownUp, ChevronRight, CircleHelp, Database, FlaskConical, LayoutDashboard, RefreshCw, ScanLine, ShieldCheck, SlidersHorizontal, Timer, TriangleAlert, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Contract, Research, View } from "@/lib/types";
import { Dashboard } from "@/components/research-views";
import { PairWorkspace } from "@/components/pair-workspace";
=======
import { useEffect, useRef, useState } from "react";
import { Bell, CircleHelp, Database, FlaskConical, LayoutDashboard, RefreshCw, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Contract, Dataset, Research, View } from "@/lib/types";
import { MonitorPrices, NormalizedComparison } from "@/components/research-views";
import { AlertsWorkspace } from "@/components/pair-workspace";
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849

const navigation = [
  { view: "monitor", label: "Monitor", hint: "Prices and normalized comparisons", href: "/", icon: LayoutDashboard },
  { view: "alerts", label: "Alerts", hint: "Matched-pair research flags", href: "/alerts", icon: Bell },
] as const;
const headings: Record<View, [string, string]> = {
  monitor: ["Monitor", "Review gold prices, exact expiries and normalized contract comparisons at your selected cutoff."],
  alerts: ["Alerts", "Inspect matched-pair research flags at the selected cutoff. Refresh to re-evaluate; no background notifications or trade execution."],
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
  const [dataset, setDataset] = useState<Dataset>("real");
  const [initialized, setInitialized] = useState(false);
  useEffect(() => { if (new URLSearchParams(window.location.search).get("dataset") === "real") setDataset("real"); setInitialized(true); }, []);
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
    if (!initialized) return;
    const controller = new AbortController();
<<<<<<< HEAD
=======
    setBooting(true); setData(null); setError("");
    const queryCutoff = asOf || new URLSearchParams(window.location.search).get("asOf");
    const params = new URLSearchParams({dataset});
    if (queryCutoff) params.set("as_of", queryCutoff);
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
    Promise.all([
      api<{ contracts: Contract[]; default_as_of: string }>(`contracts?${params}`, controller.signal),
      api<{ status: string }>("health", controller.signal),
    ]).then(([catalog, health]) => {
      if (controller.signal.aborted) return;
      const query = new URLSearchParams(window.location.search);
      const requested = (query.get("dataset") || "real") === dataset ? query.get("contract") : null;
      setContracts(catalog.contracts);
      setSelected(previous => previous || requested || catalog.contracts.find(c => c.symbol === "GOLDM")?.contract_id || catalog.contracts[0]?.contract_id || "");
      const cutoff = query.get("asOf") || catalog.default_as_of;
      setAsOf(previous => previous || cutoff); setDraft(previous => previous || cutoff.replace(/Z$/, ""));
<<<<<<< HEAD
      setHealthy(health.status === "ok"); setLoading(true); setBooting(false);
=======
      setHealthy(health.status === "ok"); setLoading(false); setBooting(false);
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setHealthy(false); setBooting(false); } });
    return () => controller.abort();
  }, [retry, dataset, asOf, initialized]);

  useEffect(() => {
    if (booting || !selected || !asOf) return;
    if (unavailableSelection) {
      setLoading(false); setData(null);
      setError(`The selected contract (${selected}) is not in this dataset at the chosen cutoff. This may be a link to an older demo version. Choose an available contract below; Retry cannot restore a missing version.`);
      return;
    }
    const controller = new AbortController();
<<<<<<< HEAD
    api<Research>(`research?${new URLSearchParams({ contract_id: selected, as_of: asOf, dataset: "synthetic" })}`, controller.signal)
=======
    setLoading(true); setError(""); setData(null);
    api<Research>(`research?${new URLSearchParams({ contract_id: selected, as_of: asOf, dataset })}`, controller.signal)
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
      .then(result => { if (!controller.signal.aborted) { setData(result); setLoading(false); setHealthy(true); } })
      .catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false); setHealthy(false); } });
    return () => controller.abort();
  }, [selected, asOf, booting, retry, dataset, unavailableSelection]);

<<<<<<< HEAD
  const refresh = () => { setBooting(true); setError(""); setData(null); setRetry(r => r + 1); };
  const current = navigation.find(n => n.view === view)!;
  const query = selected && asOf ? `?${new URLSearchParams({ contract: selected, asOf })}` : "";
  const busy = booting || loading;
  return <div className="min-h-screen lg:pl-56">
    <aside className="fixed inset-y-0 left-0 z-20 hidden w-56 flex-col border-r border-border bg-[#10151b] lg:flex">
      <Link href="/" className="flex items-center gap-3 px-6 py-8" aria-label="GoldLens home"><Logo /><span className="text-xl font-semibold tracking-tight">Gold<span className="text-primary">Lens</span><span className="mt-1 block text-[9px] font-normal tracking-[.23em] text-muted-foreground">PRECIOUS METAL RESEARCH</span></span></Link>
      <p className="eyebrow px-6 pb-4 pt-6">Workspace</p>
      <nav aria-label="Main navigation" className="space-y-1 px-3">{navigation.map(n => <Link key={n.view} href={n.href + query} aria-current={view === n.view ? "page" : undefined} className={`flex items-center gap-3 rounded-lg px-4 py-3 text-[13px] transition-colors ${view === n.view ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground"}`}><n.icon size={17} />{n.label}{view === n.view && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary" />}</Link>)}</nav>
      <div className="mx-5 mt-10 border-t border-border pt-6"><p className="eyebrow mb-4">Data environment</p><div className="flex items-center gap-2 text-xs"><span className="h-1.5 w-1.5 rounded-full bg-primary" />Synthetic sandbox</div><p className="mt-2 pl-3.5 text-[11px] leading-5 text-muted-foreground">Deterministic. Local. Reproducible.</p></div>
      <div className="mt-auto p-5"><div className="rounded-lg border border-border bg-background p-4"><ShieldCheck size={18} className="mb-2 text-primary" /><p className="text-xs font-medium">Your research stays local.</p><p className="mt-2 text-[11px] leading-5 text-muted-foreground">No live feed. No trade execution.<br />A workspace for understanding.</p></div><div className="mt-5 flex justify-between text-[10px] text-muted-foreground"><span>GOLDLENS / 0.3</span><span>LOCAL FIRST</span></div></div>
    </aside>

    <header className="flex h-[72px] items-center justify-between border-b border-border px-5 md:px-9"><div className="flex items-center gap-3 text-xs text-muted-foreground"><span className="lg:hidden"><Logo /></span><span className="hidden sm:inline">Workspace</span><ChevronRight size={13} className="hidden sm:block" /><span className="text-foreground">{current.label}</span></div><div className="flex items-center gap-5"><span className={`flex items-center gap-2 text-[11px] ${healthy ? "text-emerald-400" : "text-muted-foreground"}`}>{healthy ? <Wifi size={13} /> : <WifiOff size={13} />}{healthy ? "Local API connected" : busy ? "Connecting to API" : "API needs attention"}</span><span className="rounded-full border border-border bg-card px-2.5 py-1.5 text-[10px] text-muted-foreground">GL</span></div></header>
    <nav aria-label="Mobile navigation" className="flex overflow-x-auto border-b border-border px-3 lg:hidden">{navigation.map(n => <Link key={n.view} href={n.href + query} className={`flex items-center gap-2 px-3 py-4 text-xs ${view === n.view ? "text-primary" : "text-muted-foreground"}`}><n.icon size={14} />{n.label}</Link>)}</nav>
    <main id="main-content" className="mx-auto max-w-[1600px] px-5 py-7 md:px-9 md:py-9">
      <div className="mb-7 flex flex-wrap items-start justify-between gap-4"><div><p className="eyebrow mb-3">{current.label} / Research workspace</p><h1 className="text-[28px] font-medium tracking-tight md:text-[32px]">{headings[view][0]}</h1><p className="mt-2 text-xs leading-6 text-muted-foreground">{headings[view][1]}</p></div><Button variant="outline" size="sm" onClick={refresh} disabled={busy}><RefreshCw size={13} className={busy ? "animate-spin" : ""} />Refresh data</Button></div>
      <div className="mb-6 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-lg border border-primary/20 bg-primary/[.045] px-4 py-3 text-xs"><FlaskConical size={16} className="text-primary" /><span className="font-semibold tracking-wider text-primary">SYNTHETIC DATA</span><span className="text-[#a9a28f]">All specifications, prices, volume and open interest are invented. Not a live market feed.</span></div>
      <form className="mb-6 grid items-end gap-4 rounded-xl border border-border bg-card p-4 sm:grid-cols-[1.2fr_1fr_auto]" onSubmit={e => { e.preventDefault(); const next = draft.length === 16 ? `${draft}:00Z` : `${draft}Z`; if (next !== asOf) { setData(null); setError(""); setLoading(true); setAsOf(next); } }}>
        <div><label htmlFor="contract" className="mb-2 flex items-center gap-2 text-[11px] text-muted-foreground"><ScanLine size={13} />Contract & exact expiry</label><select id="contract" className="field" value={selected} disabled={booting || !contracts.length} onChange={e => {setData(null); setError(""); setLoading(true); setSelected(e.target.value);}}>{!contracts.length && <option value="">{booting ? "Loading contracts…" : "No contracts available"}</option>}{contracts.map(c => <option key={c.contract_id} value={c.contract_id}>{c.symbol} · {c.expiry} · {c.spec_version}</option>)}</select></div>
        <div><label htmlFor="asof" className="mb-2 flex items-center gap-2 text-[11px] text-muted-foreground"><Timer size={13} />Information cutoff (UTC)</label><input id="asof" className="field number" type="datetime-local" step="1" value={draft} onChange={e => setDraft(e.target.value)} required disabled={booting} /></div>
        <Button type="submit" disabled={booting || !selected}><SlidersHorizontal size={14} />Apply cutoff</Button>
      </form>
      <div role="status" aria-live="polite" className="mb-5 flex flex-wrap items-center justify-between gap-2 text-[10px] text-muted-foreground"><span className="flex items-center gap-2"><span className={`h-1.5 w-1.5 rounded-full ${data ? "bg-emerald-400" : "bg-slate-500"}`} />{data ? `API snapshot · ${data.spec.symbol} · ${data.as_of}` : busy ? "Loading point-in-time research…" : "No snapshot displayed"}</span><span>Observed AND available at cutoff</span></div>
      {error ? <Card className="p-8" role="alert"><TriangleAlert className="mb-3 text-amber-300" /><h2 className="font-medium">Unable to load research</h2><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{error}</p><Button className="mt-5" variant="outline" onClick={refresh}>Retry connection</Button></Card> : busy ? <Loading /> : !data || !data.latest ? <Card className="grid-pattern p-12 text-center"><Database className="mx-auto mb-4 text-muted-foreground" /><h2 className="text-lg">No observations at this cutoff</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">Choose a later information cutoff. No future observations or substitute datasets are displayed.</p></Card> : <>
        {view === "dashboard" && <Dashboard data={data} />}{view !== "dashboard" && <PairWorkspace key={data.spec.contract_id + data.as_of} data={data} contracts={contracts} view={view} />}
      </>}
      {data && <details className="mt-6 rounded-lg border border-border px-4 py-3 text-xs"><summary className="text-muted-foreground">Inspect API response <span className="ml-2 text-[10px] text-emerald-400">HTTP 200 · {data.dataset}</span></summary><pre data-testid="api-response" className="mt-4 max-h-80 overflow-auto text-[11px] leading-5 text-muted-foreground">{JSON.stringify(data, null, 2)}</pre></details>}
      <footer className="mt-8 flex flex-col justify-between gap-4 border-t border-border py-5 text-[10px] leading-5 text-muted-foreground sm:flex-row"><p className="max-w-3xl"><CircleHelp className="mr-1.5 inline size-3" />{data?.disclaimer ?? "Synthetic research only. No guaranteed arbitrage. Fees, taxes, slippage, liquidity, execution and settlement uncertainty matter. No trade execution."}</p><span className="shrink-0 tracking-widest">BUILT FOR PERSPECTIVE</span></footer>
    </main>
=======
  const query = `?${new URLSearchParams({ dataset, ...(selected ? { contract: selected } : {}), ...(asOf ? { asOf } : {}) })}`;
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
      <nav aria-label="Main navigation" className="mb-7 grid grid-cols-2 gap-1 rounded-lg bg-card p-1 ">{navigation.map(n => <Link key={n.view} href={n.href + query} aria-current={view === n.view ? "page" : undefined} className={`rounded-md px-3 py-3 ${view === n.view ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted hover:text-foreground"}`}><span className="flex items-center gap-2 text-sm font-semibold"><n.icon size={17} className="shrink-0" />{n.label}</span><span className="sr-only">{n.hint}</span></Link>)}</nav>
      <main id="main-content">
        <div className="mb-6"><h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{headings[view][0]}</h1><p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">{headings[view][1]}</p></div>
        <Card className="mb-6 p-4 sm:p-5"><label className="mb-4 block max-w-sm text-sm">Dataset<select aria-label="Dataset" className="field mt-2" value={dataset} onChange={e => { setData(null); setContracts([]); setSelected(""); setBooting(true); setError(""); setDataset(e.target.value as Dataset); const url = new URL(window.location.href); url.searchParams.set("dataset", e.target.value); url.searchParams.delete("contract"); window.history.replaceState(null, "", url); }}><option value="real">Imported real data</option></select></label>
          <div className="flex flex-wrap items-end gap-4">
            <div className="min-w-0 flex-1 basis-64"><label htmlFor="contract" className="mb-2 block text-sm font-medium">{view === "alerts" ? "First contract (A)" : "Choose a gold contract"}</label><select id="contract" className="field" value={selected} disabled={booting || !contracts.length} onChange={e => chooseContract(e.target.value)}>{unavailableSelection && <option value={selected} disabled>Unavailable: {selected}</option>}{!contracts.length && <option value="">{booting ? "Loading contracts..." : "No contracts available"}</option>}{contracts.map(c => <option key={c.contract_id} value={c.contract_id}>{contractName(c.symbol)} ({c.symbol}) / expires {c.expiry}</option>)}</select><p className="mt-2 text-xs leading-5 text-muted-foreground">Expiry is the exact date the contract ends. Each expiry is a separate contract.</p></div>
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
        {error ? <Card className="p-8" role="alert"><TriangleAlert className="mb-3 text-warning" /><h2 className="font-medium">Unable to load research</h2><p className="mt-2 max-w-2xl text-sm text-muted-foreground">{error}</p><Button className="mt-5" variant="outline" onClick={() => unavailableSelection && contracts.length ? chooseContract(contracts.find(c => c.symbol === "GOLDM")?.contract_id || contracts[0].contract_id) : setRetry(r => r + 1)}>{unavailableSelection && contracts.length ? "Use an available contract" : "Retry connection"}</Button></Card> : busy ? <Loading /> : !data || (!data.latest && view === "monitor") ? <Card className="p-10 text-center"><Database className="mx-auto mb-4 text-muted-foreground" /><h2 className="text-lg">No prices available at this time</h2><p className="mx-auto mt-3 max-w-md text-sm leading-6 text-muted-foreground">{data?.spec.normalization_reason || (dataset === "real" && !contracts.length ? "No imported contracts are available at this cutoff. Import validated real records collected from public sources to enable research." : "Open Change research time and choose a later time. No future prices or substitute datasets are shown.")}</p></Card> : <>
          {view === "monitor" && data.latest && <><MonitorPrices data={data} /><NormalizedComparison data={data} /></>}{view === "alerts" && <AlertsWorkspace key={data.dataset + data.spec.contract_id + data.as_of} data={data} contracts={contracts} />}
        </>}
        {data && data.issues.length > 0 && <Card className="mt-5 p-5"><h2 className="font-medium">Blocked price records</h2>{data.issues.map((issue, i) => <p className="mt-2 text-xs" key={i}>{issue.contract_id} / {issue.trading_date}: {issue.code} - {issue.reason}</p>)}</Card>}
        <details className="mt-6 rounded-lg border border-border bg-card p-4 text-sm"><summary>Terms explained</summary><dl className="mt-4 grid gap-4 text-sm leading-6 sm:grid-cols-2"><div><dt className="font-medium">Quote price</dt><dd className="text-muted-foreground">The price for the contract&apos;s stated weight of gold. The Monitor comparison uses a common price per gram.</dd></div><div><dt className="font-medium">Trading volume</dt><dd className="text-muted-foreground">The number of contracts traded during the recorded period.</dd></div><div><dt className="font-medium">Open interest</dt><dd className="text-muted-foreground">The number of contracts still open, rather than closed or settled.</dd></div><div><dt className="font-medium">Baseline and signals</dt><dd className="text-muted-foreground">Spread is left minus right in 999-purity INR/gram. A z-score measures its distance from the prior spread mean in sample standard deviations (ddof=1), excluding the current spread.</dd></div></dl></details>
        {data && <details className="mt-3 rounded-lg border border-border p-4 text-sm"><summary className="text-muted-foreground">Technical details / API response</summary><pre data-testid="api-response" className="mt-4 max-h-80 overflow-auto text-xs leading-5 text-muted-foreground">{JSON.stringify(data, null, 2)}</pre></details>}
        <footer className="mt-8 border-t border-border py-5 text-xs leading-6 text-muted-foreground"><CircleHelp className="mr-1.5 inline size-3" />{data?.disclaimer ?? "Research only. No guaranteed arbitrage. Fees, taxes, slippage, liquidity, execution and settlement uncertainty matter. No trade execution."}</footer>
      </main>
    </div>
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
  </div>;
}

function contractName(symbol: string) { return ({ GOLDM: "Gold Mini", GOLDTEN: "Gold Ten", GOLDGUINEA: "Gold Guinea", GOLDPETAL: "Gold Petal" } as Record<string, string>)[symbol] ?? symbol; }

function Logo() { return <svg width="29" height="34" viewBox="0 0 29 34" aria-hidden="true"><path d="M14.5 1 28 9v16l-13.5 8L1 25V9Z" fill="none" stroke="var(--primary)" strokeWidth="1.6" /><path d="m7 21 7.5-13L22 21H7Zm7.5-7v13" fill="none" stroke="var(--primary)" strokeWidth="1.4" /></svg>; }
function Loading() { return <div aria-label="Loading research" className="space-y-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0,1,2,3].map(i => <Card key={i} className="space-y-5 p-5"><div className="skeleton h-3 w-24" /><div className="skeleton h-8 w-32" /><div className="skeleton h-2 w-28" /></Card>)}</div><Card className="h-80 p-6"><div className="skeleton mb-8 h-4 w-40" /><div className="skeleton h-52 w-full" /></Card></div>; }
