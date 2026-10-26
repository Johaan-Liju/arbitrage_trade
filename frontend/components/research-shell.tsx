"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Activity, ArrowDownUp, ChevronRight, CircleHelp, Database, FlaskConical, LayoutDashboard, RefreshCw, ScanLine, ShieldCheck, SlidersHorizontal, Timer, TriangleAlert, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import type { Contract, Research, View } from "@/lib/types";
import { Dashboard } from "@/components/research-views";
import { PairWorkspace } from "@/components/pair-workspace";

const navigation = [
  { view: "dashboard", label: "Dashboard", href: "/", icon: LayoutDashboard },
  { view: "compare", label: "Compare", href: "/compare", icon: ArrowDownUp },
  { view: "signals", label: "Signals", href: "/signals", icon: Activity },
  { view: "backtest", label: "Backtest", href: "/backtest", icon: Timer },
] as const;
const headings: Record<View, [string, string]> = {
  dashboard: ["Gold, in context.", "A precise view of your contracts. Every observation in its proper time."],
  compare: ["See the differences.", "Explore quote-normalized prices across synthetic contracts and exact expiries."],
  signals: ["Patterns, with perspective.", "Historical deviations from a rolling baseline. Research, never a promise."],
  backtest: ["Rewind. Observe. Understand.", "Replay signals using only the information available at each decision time."],
};

export function ResearchShell({ view }: { view: View }) {
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

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<{ contracts: Contract[]; default_as_of: string }>("contracts", controller.signal),
      api<{ status: string }>("health", controller.signal),
    ]).then(([catalog, health]) => {
      const query = new URLSearchParams(window.location.search);
      const requested = query.get("contract");
      setContracts(catalog.contracts);
      setSelected(previous => previous || catalog.contracts.find(c => c.contract_id === requested)?.contract_id || catalog.contracts.find(c => c.symbol === "GOLDM")?.contract_id || catalog.contracts[0]?.contract_id || "");
      const cutoff = query.get("asOf") || catalog.default_as_of;
      setAsOf(previous => previous || cutoff); setDraft(previous => previous || cutoff.replace(/Z$/, ""));
      setHealthy(health.status === "ok"); setLoading(true); setBooting(false);
    }).catch(e => { if (!controller.signal.aborted) { setError(e.message); setHealthy(false); setBooting(false); } });
    return () => controller.abort();
  }, [retry]);

  useEffect(() => {
    if (booting || !selected || !asOf) return;
    const controller = new AbortController();
    api<Research>(`research?${new URLSearchParams({ contract_id: selected, as_of: asOf, dataset: "synthetic" })}`, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setData(result); setLoading(false); setHealthy(true); } })
      .catch(e => { if (!controller.signal.aborted) { setError(e.message); setLoading(false); setHealthy(false); } });
    return () => controller.abort();
  }, [selected, asOf, booting, retry]);

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
  </div>;
}

function Logo() { return <svg width="29" height="34" viewBox="0 0 29 34" aria-hidden="true"><path d="M14.5 1 28 9v16l-13.5 8L1 25V9Z" fill="none" stroke="#d9bd7d" strokeWidth="1.6" /><path d="m7 21 7.5-13L22 21H7Zm7.5-7v13" fill="none" stroke="#d9bd7d" strokeWidth="1.4" /></svg>; }
function Loading() { return <div aria-label="Loading research" className="space-y-5"><div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{[0,1,2,3].map(i => <Card key={i} className="space-y-5 p-5"><div className="skeleton h-3 w-24" /><div className="skeleton h-8 w-32" /><div className="skeleton h-2 w-28" /></Card>)}</div><Card className="h-80 p-6"><div className="skeleton mb-8 h-4 w-40" /><div className="skeleton h-52 w-full" /></Card></div>; }
