"use client";
import { useEffect, useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Contract, Research, View } from "@/lib/types";
import type { BacktestResult, PairResult } from "@/lib/financial-types";

const fmt = (n: number | null, digits = 2) => n === null ? "—" : n.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
async function post<T>(endpoint: string, body: object, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`/api/${endpoint}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal });
  const result = await response.json();
  if (!response.ok) throw new Error(typeof result.detail === "string" ? result.detail : JSON.stringify(result.detail));
  return result;
}

export function PairWorkspace({ data, contracts, view }: { data: Research; contracts: Contract[]; view: View }) {
  const alternatives = contracts.filter(c => data.pairing.matches.some(m => m.contract_b === c.contract_id));
  const [other, setOther] = useState(alternatives.find(c => c.symbol === "GOLDGUINEA")?.contract_id || alternatives[0]?.contract_id || "");
  const [lookback, setLookback] = useState(10), [minimum, setMinimum] = useState(5), [entry, setEntry] = useState(2.5);
  const [exit, setExit] = useState(.5), [fees, setFees] = useState(5), [slippage, setSlippage] = useState(10);
  const [pair, setPair] = useState<PairResult | null>(null), [run, setRun] = useState<BacktestResult | null>(null);
  const [error, setError] = useState(""), [running, setRunning] = useState(false);
  const [retry, setRetry] = useState(0);
  const [simulation, setSimulation] = useState(0);
  const selection = { contract_a: data.spec.contract_id, contract_b: other, as_of: data.as_of, dataset: data.dataset, lookback, min_observations: minimum, entry_z: entry };
  const signature = JSON.stringify(selection);
  useEffect(() => {
    if (!other) return;
    const controller = new AbortController();
    post<PairResult>("pair", JSON.parse(signature), controller.signal).then(result => { if (!controller.signal.aborted) setPair(result); })
      .catch(e => { if (!controller.signal.aborted) setError(e.message); });
    return () => controller.abort();
  }, [signature, retry]);
  useEffect(() => {
    if (simulation === 0) return;
    const controller = new AbortController();
    post<BacktestResult>("backtest", { ...JSON.parse(signature), exit_z: exit, fee_bps: fees, slippage_bps: slippage, allow_calendar: false }, controller.signal)
      .then(result => { if (!controller.signal.aborted) { setRun(result); setRunning(false); } })
      .catch(e => { if (!controller.signal.aborted) { setError(e.message); setRunning(false); } });
    return () => controller.abort();
  }, [simulation, signature, exit, fees, slippage]);
  const resetSimulation = () => { setSimulation(0); setRun(null); setError(""); setRunning(false); };
  const resetPair = () => { resetSimulation(); setPair(null); };
  return <div className="space-y-5">
    {view === "compare" && <Card><CardHeader><CardTitle>Prices side by side</CardTitle><Badge>{data.label} / 999 purity</Badge></CardHeader><CardContent><p className="mb-4 text-sm leading-6 text-muted-foreground">Quoted INR / quotation grams x 999 / quoted purity per mille. Lot weight is shown separately. Only identical exact expiries can form a pair.</p><div className="table-wrap"><table className="data-table"><thead><tr><th>Contract / exact expiry</th><th>Quote INR</th><th>Quote / lot grams</th><th>Quoted purity per mille</th><th>INR / gram (999)</th><th>Trading date / availability</th></tr></thead><tbody>{data.pairing.normalization.map(({contract:c,latest:r,reason}) => <tr key={c.contract_id} className={c.contract_id === data.spec.contract_id ? "selected-row" : ""}><td>{c.symbol}<br/>{c.expiry}<br/>{c.spec_version}</td><td>{r ? fmt(r.price) : "Unavailable"}</td><td>{c.quotation_grams ?? "Unknown"} / {c.lot_size_grams ?? "Unknown"}</td><td>{c.quote_purity_per_mille ?? "Unknown"}</td><td>{r ? fmt(Number(r.normalized_999_inr_per_gram), 4) : reason}</td><td>{r?.trading_date}<br/>{r?.normalized_available_at}</td></tr>)}</tbody></table></div></CardContent></Card>}
    <Card className="p-5"><h2 className="font-medium">Unmatched contracts</h2><p className="mt-2 text-sm text-muted-foreground">Relative to {data.spec.symbol} / {data.spec.expiry}. Exact dates are never merged or replaced with the nearest expiry.</p>{data.pairing.unmatched.map(({contract:c,reason}) => <p key={c.contract_id} className="mt-3 text-sm"><b>{c.symbol} / {c.expiry} / {c.spec_version}</b><br/><span className="text-muted-foreground">{reason}</span></p>)}{!data.pairing.unmatched.length && <p className="mt-3 text-sm">No unmatched alternatives.</p>}</Card>
    {!other && <Card className="p-5" role="status">Insufficient data: no eligible exact-expiry partner at this cutoff. Choose another contract or import an explicitly listed matching expiry.</Card>}

    <Card className="p-5"><h2 className="text-sm font-medium">Exact contract pair</h2><p className="mt-2 text-xs text-muted-foreground">A: {data.spec.symbol} · {data.spec.expiry} · {data.spec.spec_version}. Left: A. Right: B. Spread = left minus right, in 999-purity INR/gram.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <label className="text-xs">Right (B): contract & exact expiry<select disabled={!alternatives.length} id="pair-contract" className="field mt-2" value={other} onChange={e => { resetPair(); setOther(e.target.value); }}>{!alternatives.length && <option value="">No exact-expiry match</option>}{alternatives.map(c => <option key={c.contract_id} value={c.contract_id}>{c.symbol} · {c.expiry} · {c.spec_version}</option>)}</select></label>
        <Field label="Lookback observations" value={lookback} min={2} max={250} onChange={n => { resetPair(); setLookback(n); }} />
        <Field label="Minimum prior observations" value={minimum} min={2} max={250} onChange={n => { resetPair(); setMinimum(n); }} />
        <Field label="Investigate |z| threshold" value={entry} min={.1} max={100} step={.1} onChange={n => { resetPair(); setEntry(n); }} />
      </div></Card>
    {error && <Card role="alert" className="p-5 text-sm"><p>{error}</p><Button className="mt-3" onClick={() => { setPair(null); setError(""); setRetry(n => n + 1); }}>Retry pair</Button></Card>}
    {other && !pair && !error && <p role="status" className="text-sm text-muted-foreground">Loading paired observations…</p>}
    {pair && <>
      <Card className="border-primary/25 p-5"><Badge>{pair.alignment}</Badge><p className="mt-3 text-sm">{pair.spec_a.symbol} · {pair.spec_a.expiry} ↔ {pair.spec_b.symbol} · {pair.spec_b.expiry}</p><p className="mt-2 text-xs leading-6 text-muted-foreground">{pair.cautions.join(" ")}</p><p className="mt-3 text-sm">{pair.basis_differences.length ? "Delivery or settlement differences remain:" : "Recorded delivery and settlement terms match; costs and execution are still uncertain."}</p>{pair.basis_differences.map(d => <p key={d.field} className="mt-2 text-xs"><b>{d.field.replaceAll("_", " ")}</b>: A {JSON.stringify(d.left)} / B {JSON.stringify(d.right)}</p>)}{pair.normalization_issues.map((issue,i) => <p key={i} className="mt-2 text-xs text-warning">{issue.trading_date}: {issue.code} / {issue.reason}</p>)}</Card>
      {view === "compare" && <>
        <Card><CardHeader><CardTitle>Contract comparison</CardTitle><Badge>999 PURITY · INR/g</Badge></CardHeader><CardContent><div className="grid gap-4 md:grid-cols-2">{[pair.spec_a,pair.spec_b].map(s => <div key={s.contract_id} className="rounded border border-border p-4 text-xs leading-6"><b>{s.symbol} · {s.expiry}</b><p>{s.spec_version} · {s.verification}</p><p>Quote {s.quote_grams} g · lot {s.lot_grams} g · quoted purity {s.quote_purity_per_mille} per mille</p><p>Settlement: {s.settlement_method} / {s.settlement_terms}</p><p>Delivery restrictions: {s.delivery_restrictions}</p><p>{s.delivery_location} · {s.delivery_basis}</p><p>Safe exit {s.safe_exit_date} · tender {s.tender_start}</p></div>)}</div><p className="mt-4 text-xs text-muted-foreground">Quoted price / quotation grams x 999 / quoted purity per mille. Original quotes and provenance remain in the ledger.</p></CardContent></Card>
        <Chart title="Normalized price history" dates={pair.history.map(e => e.trading_date)} series={[{name:`A · ${pair.spec_a.symbol}`, values:pair.history.map(e => e.normalized_a), color:"#d9bd7d"},{name:`B · ${pair.spec_b.symbol}`,values:pair.history.map(e => e.normalized_b),color:"#7dd3fc"}]} />
        <Chart title="Spread and prior mean · INR/g" dates={pair.history.map(e => e.trading_date)} series={[{name:"Raw A − B",values:pair.history.map(e => e.raw_pair_spread),color:"#d9bd7d"},{name:"Prior mean",values:pair.history.map(e => e.expected_basis),color:"#7dd3fc"}]} />
      </>}
      {view !== "backtest" && <>
        <Card><CardHeader><CardTitle>A transparent research rule</CardTitle><Badge>{pair.status}</Badge></CardHeader><CardContent><p className="text-xs leading-6 text-muted-foreground">{pair.method.basis} Window {pair.method.lookback}; minimum {pair.method.min_observations}. Defaults: lookback 10, minimum 5 prior spreads, threshold 2.5. Investigate is a research flag; costs, liquidity, execution and settlement remain uncertain.</p>{pair.latest ? <><p className="mt-4 text-sm text-primary" data-testid="signal-reason">{pair.latest.reason}</p><div className="mt-5 grid grid-cols-2 gap-4 lg:grid-cols-4">{[["Observed spread",pair.latest.raw_pair_spread],["Prior mean / INR/g",pair.latest.prior_mean],["Prior sample std / INR/g",pair.latest.prior_std],["Z-score",pair.latest.z_score],["Prior sample count",pair.latest.sample_count],["Freshness · hours",pair.latest.age_hours]].map(([label,value]) => <div key={String(label)}><p className="text-[10px] text-muted-foreground">{label}</p><p className="mt-2 number text-lg">{fmt(value as number | null, label === "Prior sample count" ? 0 : 2)}</p></div>)}</div><p className="mt-5 text-xs text-muted-foreground">A volume / OI {fmt(pair.latest.a.volume,0)} / {fmt(pair.latest.a.open_interest,0)} · B {fmt(pair.latest.b.volume,0)} / {fmt(pair.latest.b.open_interest,0)}. Cutoff {pair.latest.cutoff} · observation {pair.latest.trading_date}.</p></> : <p className="mt-4 text-sm">{pair.reason}</p>}</CardContent></Card>
        <Chart title="Z-score and investigation bands" dates={pair.history.map(e => e.trading_date)} series={[{name:"Prior-only z-score",values:pair.history.map(e => e.z_score),color:"#d9bd7d"},{name:"Upper band",values:pair.history.map(e => e.upper_z),color:"#fda4af"},{name:"Lower band",values:pair.history.map(e => e.lower_z),color:"#fda4af"}]} />
        <details className="rounded border border-border p-4 text-xs"><summary>Paired observation ledger · original values and provenance</summary><div className="table-wrap mt-4"><table className="data-table"><thead><tr><th>Date</th><th>A quote / source / available</th><th>B quote / source / available</th><th>Spread</th><th>Prior mean / sample std / count / cutoff</th><th>Z</th><th>Status & reason</th></tr></thead><tbody>{pair.history.toReversed().map(e => <tr key={e.trading_date}><td>{e.trading_date}</td><td>{fmt(e.a.price)}<br/>{e.a.source}<br/>{e.a.available_at}</td><td>{fmt(e.b.price)}<br/>{e.b.source}<br/>{e.b.available_at}</td><td>{fmt(e.raw_pair_spread)}</td><td>{fmt(e.prior_mean)} / {fmt(e.prior_std)} / {e.sample_count}<br/>{e.cutoff}</td><td>{fmt(e.z_score)}</td><td>{e.status}<br/>{e.reason}</td></tr>)}</tbody></table></div></details>
      </>}
      <Card className="p-5"><h2 className="text-sm font-medium">Quality checks</h2><p className="mt-3 text-xs leading-6 text-muted-foreground">{pair.quality.calendar}. Both timestamps must be at or before {pair.as_of}. No forward filling. {pair.quality.missing_dates.length} dates are missing one leg. Only records with usable point-in-time references are included.</p>{pair.quality.missing_dates.map(d => <p key={d.trading_date} className="mt-2 text-xs text-amber-300">{d.trading_date}: {d.reason}</p>)}</Card>
      {view === "backtest" && <>
        <Card className="p-5"><h2 className="text-sm font-medium">Hypothetical paired settlement replay</h2><p className="mt-2 text-xs leading-6 text-muted-foreground">Daily settlements are not executable fills. Orders use a later dated observation. Costs apply to both legs on entry and exit. Taxes, margin funding, delivery and actual liquidity remain unresolved.</p><div className="mt-4 grid gap-4 sm:grid-cols-3"><Field label="Exit |z| threshold" value={exit} min={0} step={.1} onChange={n => { resetSimulation(); setExit(n); }}/><Field label="Fee bps per leg per side" value={fees} min={0} onChange={n => { resetSimulation(); setFees(n); }}/><Field label="Slippage bps per leg per side" value={slippage} min={0} onChange={n => { resetSimulation(); setSlippage(n); }}/></div><p className="my-5 text-xs">Simulation is restricted to identical exact expiries. Delivery and settlement differences remain visible above.</p><Button disabled={running} onClick={() => { setRunning(true); setRun(null); setError(""); setSimulation(n => n+1); }}>{running ? "Simulating…" : "Run simulation"}</Button></Card>
        {run && <><Card className="p-5"><Badge>{run.label} · {run.status}</Badge><p className="mt-3 text-sm">{run.reason}</p><p className="mt-2 text-xs text-muted-foreground">{run.lots_a} lots A / {run.lots_b} lots B · no fills after {run.safe_exit_date} · run {run.run_id}</p><div className="mt-5 grid grid-cols-2 gap-5 md:grid-cols-4">{[["Closed trades",run.number_of_trades],["Gross P&L · INR",run.gross_pnl],["Fees · INR",run.fees],["Slippage · INR",run.slippage],["Net P&L · INR",run.net_pnl],["Max drawdown · INR",run.max_drawdown]].map(([label,value]) => <div key={String(label)}><p className="text-[10px] text-muted-foreground">{label}</p><p className="number mt-2 text-xl">{fmt(value as number | null)}</p></div>)}</div>{run.open_position && <p className="mt-4 text-amber-300">Unresolved open position: total performance is withheld.</p>}</Card>
          <Chart title="Equity curve · INR (₹10,00,000 reference capital)" dates={run.equity_curve.map(e => e.trading_date)} series={[{name:"Marked equity after costs",values:run.equity_curve.map(e => e.equity),color:"#d9bd7d"}]} />
          <Card><CardHeader><CardTitle>Trade ledger</CardTitle></CardHeader><CardContent>{!run.trades.length && <p className="text-sm text-muted-foreground">No completed trades. Inspect the reasons below.</p>}{run.trades.map((trade,i) => <details key={i} className="mb-4 rounded border border-border p-4 text-xs" open><summary>Trade {i+1} · {trade.entry_date} → {trade.exit_date} · net ₹{fmt(trade.net_pnl)}</summary><p className="mt-3 leading-6">Signal {trade.signal_date}, available {trade.signal_available_at}. {trade.entry_reason}<br/>Exit signal {trade.exit_signal_date}: {trade.exit_reason}</p><div className="table-wrap mt-3"><table className="data-table"><thead><tr><th>Exact leg / spec</th><th>Side / lots</th><th>Entry → exit quote</th><th>Entry → exit notional</th><th>Entry / exit fees</th><th>Entry / exit slippage</th><th>Gross P&L</th></tr></thead><tbody>{trade.legs.map(l => <tr key={l.symbol+l.expiry}><td>{l.symbol} · {l.expiry}<br/>{l.spec_version}</td><td>{l.side} · {l.lots}</td><td>{fmt(l.entry_quote)} → {fmt(l.exit_quote)}</td><td>{fmt(l.entry_notional)} → {fmt(l.exit_notional)}</td><td>{fmt(l.entry_fee)} / {fmt(l.exit_fee)}</td><td>{fmt(l.entry_slippage)} / {fmt(l.exit_slippage)}</td><td>{fmt(l.gross_pnl)}</td></tr>)}</tbody></table></div><p className="mt-3 text-muted-foreground">Directional sensitivity: ₹{fmt(trade.directional_pnl_per_1_inr_999_g,4)} P&L per +₹1/g parallel move in 999-equivalent price. This diagnostic does not establish market neutrality.</p></details>)}</CardContent></Card>
          <Card><CardHeader><CardTitle>Rejected orders and decisions</CardTitle></CardHeader><CardContent>{run.rejections.length ? run.rejections.map((r,i) => <p key={i} className="mb-3 text-xs leading-6"><span className="text-primary">{r.trading_date} · {r.action}</span> — {r.reason}</p>) : <p className="text-xs text-muted-foreground">No rejected orders.</p>}</CardContent></Card>
          <details className="rounded border border-border p-4 text-xs"><summary>Simulation assumptions and full report</summary>{run.assumptions.map(a => <p className="mt-3 leading-5 text-muted-foreground" key={a}>{a}</p>)}<pre className="mt-4 max-h-80 overflow-auto">{JSON.stringify(run,null,2)}</pre></details>
        </>}
      </>}
    </>}
  </div>;
}

function Field({ label,value,onChange,min,max,step=1 }: { label:string;value:number;onChange:(n:number)=>void;min:number;max?:number;step?:number }) {
  return <label className="text-xs">{label}<input className="field mt-2 number" type="number" value={value} min={min} max={max} step={step} onChange={e => onChange(Number(e.target.value))}/></label>;
}
function Chart({ title,dates,series }: { title:string;dates:string[];series:{name:string;values:(number|null)[];color:string}[] }) {
  // Chart geometry only: all financial series and bands are API values.
  const values=series.flatMap(s => s.values.filter((v):v is number => v!==null));
  if (!values.length) return <Card className="p-5"><h3 className="text-sm">{title}</h3><p className="mt-3 text-xs text-muted-foreground">Insufficient observations to plot.</p></Card>;
  const lo=Math.min(...values), hi=Math.max(...values), span=hi-lo||1;
  const x=(i:number)=>45+i/Math.max(dates.length-1,1)*680, y=(v:number)=>185-(v-lo)/span*145;
  return <Card><CardHeader><CardTitle>{title}</CardTitle></CardHeader><CardContent><div className="mb-3 flex flex-wrap gap-4 text-xs">{series.map(s=><span key={s.name} style={{color:s.color}}>{s.name}</span>)}</div><div className="overflow-x-auto"><svg role="img" aria-label={title} viewBox="0 0 810 225" className="min-w-[640px] w-full">{[0,.5,1].map(t=><g key={t}><line x1="45" x2="725" y1={40+t*145} y2={40+t*145} stroke="#26303a"/><text x="735" y={44+t*145} fill="#778595" fontSize="10">{fmt(hi-t*span)}</text></g>)}{series.map(s=><g key={s.name}><path d={s.values.map((v,i)=>v===null?"":`${i===0||s.values[i-1]===null?"M":"L"}${x(i)},${y(v)}`).join(" ")} fill="none" stroke={s.color} strokeWidth="2"/>{s.values.map((v,i)=>v===null?null:<circle key={i} cx={x(i)} cy={y(v)} r="4" fill="transparent"><title>{dates[i]} · {s.name}: {fmt(v,4)}</title></circle>)}</g>)}<text x="45" y="215" fill="#778595" fontSize="10">{dates[0]}</text><text x="725" y="215" textAnchor="end" fill="#778595" fontSize="10">{dates.at(-1)}</text></svg></div></CardContent></Card>;
}
