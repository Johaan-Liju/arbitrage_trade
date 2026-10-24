import { useState } from "react";
import { Activity, ArrowUpRight, BarChart3, Boxes, CircleDot, Layers, ShieldCheck } from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Price, Research } from "@/lib/types";

// Formatting and chart layout only. Financial metrics and signals come from FastAPI.
const number = (value: number | null, digits = 0) => value === null ? "—" : value.toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const money = (value: number | null) => value === null ? "—" : `₹${number(value, 2)}`;
const percent = (value: number | null) => value === null ? "—" : `${value > 0 ? "+" : ""}${number(value, 3)}%`;

export function Dashboard({ data }: { data: Research }) {
  const latest = data.latest!;
  const [all, setAll] = useState(false);
  return <div className="space-y-5">
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Latest observed price" value={money(latest.price)} detail={<><span className={data.metrics.change_pct !== null && data.metrics.change_pct < 0 ? "text-rose-300" : "text-emerald-400"}>{percent(data.metrics.change_pct)}</span><span className="ml-2">vs prior observation</span></>} icon={<CircleDot size={16} />} primary />
      <Metric label="5-observation mean" value={money(data.metrics.mean_5)} detail="Trailing available prices · includes latest" icon={<Activity size={16} />} />
      <Metric label="Trading volume" value={number(latest.volume)} detail="Synthetic contracts · latest observation" icon={<BarChart3 size={16} />} />
      <Metric label="Open interest" value={number(latest.open_interest)} detail="Synthetic contracts · latest observation" icon={<Layers size={16} />} />
    </div>
    <div className="grid gap-5 xl:grid-cols-[minmax(0,2.2fr)_minmax(260px,1fr)]">
      <Card><CardHeader><div><CardTitle>Price history <span className="ml-2 text-muted-foreground">/ {data.spec.symbol}</span></CardTitle><p className="mt-2 text-[11px] text-muted-foreground">INR per synthetic quote · {data.spec.quote_grams} g</p></div><Badge>AS-OF SERIES</Badge></CardHeader><CardContent><PriceChart prices={data.prices} /><div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-[10px] text-muted-foreground"><span className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-primary" />Observed price · synthetic</span><span>{data.metrics.count} available observations</span></div></CardContent></Card>
      <Card className="relative overflow-hidden"><CardHeader><CardTitle>Contract at a glance</CardTitle><Boxes size={16} className="text-primary" /></CardHeader><CardContent><div className="mb-5 flex items-center gap-3"><div className="flex size-11 items-center justify-center rounded-lg border border-primary/20 bg-primary/5 font-serif text-xl text-primary">Au</div><div><p className="font-medium">{data.spec.symbol}</p><p className="mt-1 text-[10px] text-muted-foreground">Synthetic gold contract</p></div></div><dl className="space-y-4 text-xs"><Detail label="Exact expiry" value={data.spec.expiry} /><Detail label="Specification" value={data.spec.spec_version} /><Detail label="Quote weight" value={`${data.spec.quote_grams} g (invented)`} /><Detail label="Lot weight" value={`${data.spec.lot_grams} g`} /><Detail label="Purity" value={String(data.spec.purity)} /><Detail label="Currency" value={data.spec.currency} /><Detail label="Trading date" value={latest.trading_date} /><Detail label="Spec available" value={data.spec.available_at.slice(0, 10)} /></dl><div className="mt-6 rounded-md border border-border bg-background px-3 py-3 text-[10px] leading-5 text-muted-foreground"><ShieldCheck size={13} className="mr-1.5 inline text-primary" />Versioned specification. Exact expiry.<br />{data.spec.description}.</div></CardContent></Card>
    </div>
    <Card className="overflow-hidden"><CardHeader><div><CardTitle>Observation ledger</CardTitle><p className="mt-2 text-[11px] text-muted-foreground">Trace each price to its contract, specification and information time.</p></div><Button variant="ghost" size="sm" onClick={() => setAll(v => !v)}>{all ? "Recent 8" : "View all observations"}<ArrowUpRight size={13} /></Button></CardHeader><div className="table-wrap max-h-[430px]"><table className="data-table"><thead><tr><th>Trading date</th><th>Contract / exact expiry</th><th>Price · INR / quote</th><th>Volume</th><th>Open interest</th><th>Observed / available · UTC</th><th>Spec</th></tr></thead><tbody>{(all ? data.prices : data.prices.slice(-8)).toReversed().map(p => <tr key={p.trading_date}><td className="number text-muted-foreground">{p.trading_date}</td><td><span className="font-medium">{p.symbol}</span><span className="mt-1 block text-[10px] text-muted-foreground">{p.expiry}</span></td><td className="number">{money(p.price)}</td><td className="number text-muted-foreground">{number(p.volume)}</td><td className="number text-muted-foreground">{number(p.open_interest)}</td><td className="number text-[10px] text-muted-foreground">{p.observed_at}<br />{p.available_at}</td><td><Badge className="border-border bg-transparent text-muted-foreground">{p.spec_version}</Badge></td></tr>)}</tbody></table></div><div className="border-t border-border px-5 py-3 text-[10px] text-muted-foreground">Source: {latest.source} · Dataset: SYNTHETIC · Unit: INR per invented quote</div></Card>
  </div>;
}

function Metric({ label, value, detail, icon, primary = false }: { label: string; value: string; detail: React.ReactNode; icon: React.ReactNode; primary?: boolean }) {
  return <Card className={`p-5 ${primary ? "border-primary/25 bg-gradient-to-br from-primary/[.05] to-card" : ""}`}><div className="flex items-center justify-between gap-2 text-[11px] text-muted-foreground"><span>{label}</span><span className={primary ? "text-primary" : "text-muted-foreground/60"}>{icon}</span></div><p className={`number my-5 text-[27px] ${primary ? "text-primary" : ""}`}>{value}</p><div className="text-[10px] leading-5 text-muted-foreground">{detail}</div></Card>;
}
function Detail({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-3"><dt className="text-muted-foreground">{label}</dt><dd className="number text-right text-[11px]">{value}</dd></div>; }
function PriceChart({ prices }: { prices: Price[] }) {
  // These transforms place API price values on an SVG; they do not calculate indicators.
  const [hovered, setHovered] = useState<number | null>(null);
  const values = prices.map(p => p.price);
  const low = Math.min(...values), high = Math.max(...values);
  const span = high - low || high * .01;
  const y = (v: number) => 215 - ((v - low) / span) * 170;
  const x = (i: number) => 8 + i / Math.max(prices.length - 1, 1) * 682;
  const line = prices.map((p, i) => `${x(i)},${y(p.price)}`).join(" ");
  const focus = hovered !== null ? prices[hovered] : null;
  return <div><div className="mb-2 h-5 text-[11px] text-muted-foreground">{focus ? `${focus.trading_date} · ${money(focus.price)}` : "Hover over a point to inspect an observation"}</div><svg role="img" aria-label="Synthetic price history; exact values are in the observation ledger" viewBox="0 0 790 260" className="w-full overflow-visible"><defs><linearGradient id="gold-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#d9bd7d" stopOpacity=".17" /><stop offset="100%" stopColor="#d9bd7d" stopOpacity="0" /></linearGradient></defs>{[0,.25,.5,.75,1].map(t => <g key={t}><line x1="0" x2="700" y1={45 + t * 170} y2={45 + t * 170} stroke="#26303a" strokeDasharray="3 5" /><text x="714" y={49 + t * 170} fill="#778595" fontSize="10" fontFamily="monospace">{number(high - t * span)}</text></g>)}<polygon points={`8,230 ${line} ${x(prices.length - 1)},230`} fill="url(#gold-area)" /><polyline points={line} fill="none" stroke="#d9bd7d" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />{prices.map((p,i) => <circle key={p.trading_date} cx={x(i)} cy={y(p.price)} r={hovered === i ? 5 : 7} fill={hovered === i ? "#d9bd7d" : "transparent"} onMouseEnter={() => setHovered(i)} onMouseLeave={() => setHovered(null)}><title>{p.trading_date}: {money(p.price)}</title></circle>)}<text x="8" y="254" fill="#778595" fontSize="10">{prices[0]?.trading_date}</text><text x="690" y="254" textAnchor="end" fill="#778595" fontSize="10">{prices.at(-1)?.trading_date}</text></svg></div>;
}
