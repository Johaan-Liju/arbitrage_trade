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

export function MonitorPrices({ data }: { data: Research }) {
  const latest = data.latest!;
  const [all, setAll] = useState(false);
  return <div className="space-y-5">
    <Card className="p-5"><p className="text-sm text-muted-foreground">INR per gram (999 purity)</p><p className="number mt-3 text-3xl text-primary" data-testid="normalized-price">{money(latest.normalized_999_per_g)}</p><details className="mt-3 text-xs text-muted-foreground"><summary>How the per-gram price is calculated</summary><p className="mt-3">Quote price / {data.spec.quotation_grams} g x 999 / {data.spec.quote_purity_per_mille} purity per mille. Lot weight: {data.spec.lot_size_grams} g (not the price denominator).</p></details><p className="mt-3 text-xs text-muted-foreground">Latest record: {latest.trading_date}. Historical snapshot, not a live quote.</p></Card>
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Latest quote price" value={money(latest.price)} detail={<><span className={data.metrics.change_pct !== null && data.metrics.change_pct < 0 ? "text-negative" : "text-success"}>{percent(data.metrics.change_pct)}</span><span className="ml-2">vs previous price</span></>} icon={<CircleDot size={16} />} primary />
      <Metric label="Average of latest 5 prices" value={money(data.metrics.mean_5)} detail="Includes the latest available price" icon={<Activity size={16} />} />
      <Metric label="Trading volume" value={number(latest.volume)} detail="Contracts traded in the latest record" icon={<BarChart3 size={16} />} />
      <Metric label="Open interest" value={number(latest.open_interest)} detail="Contracts still open in the latest record" icon={<Layers size={16} />} />
    </div>
    <div className="grid gap-5">
      <Card><CardHeader><div><CardTitle>Price history <span className="ml-2 text-muted-foreground">/ {data.spec.symbol}</span></CardTitle><p className="mt-2 text-xs text-muted-foreground">INR per quote · {data.spec.quote_grams} g</p></div></CardHeader><CardContent><PriceChart prices={data.prices} /><div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4 text-xs text-muted-foreground"><span className="flex items-center gap-2"><span className="h-1.5 w-1.5 rounded-full bg-primary" />Observed price / {data.label}</span><span>{data.metrics.count} available observations</span></div></CardContent></Card>
      <details className="self-start rounded-xl border border-border bg-card"><summary className="p-5 text-sm font-semibold">Contract details / expiry, weight and version</summary><CardHeader><CardTitle>About this contract</CardTitle><Boxes size={16} className="text-primary" /></CardHeader><CardContent><div className="mb-5 flex items-center gap-3"><div className="flex size-11 items-center justify-center rounded-lg border border-primary/20 bg-primary/5 font-serif text-xl text-primary">Au</div><div><p className="font-medium">{data.spec.symbol}</p><p className="mt-1 text-xs text-muted-foreground">{data.label} gold contract</p></div></div><dl className="space-y-4 text-xs"><Detail label="Exact expiry" value={data.spec.expiry} /><Detail label="Specification" value={data.spec.spec_version} /><Detail label="Quote weight" value={`${data.spec.quote_grams} g`} /><Detail label="Quoted purity" value={`${data.spec.quote_purity_per_mille} per mille`} /><Detail label="Lot weight" value={`${data.spec.lot_size_grams} g`} /><Detail label="Settlement" value={data.spec.settlement_method ?? "Unknown"} /><Detail label="Locations" value={data.spec.delivery_location} /><Detail label="Currency" value={data.spec.currency} /><Detail label="Trading date" value={latest.trading_date} /><Detail label="Spec available" value={data.spec.available_at.slice(0, 10)} /></dl><div className="mt-6 rounded-md border border-border bg-background px-3 py-3 text-xs leading-5 text-muted-foreground"><ShieldCheck size={13} className="mr-1.5 inline text-primary" />Versioned specification. Exact expiry.<br />{data.spec.description}.</div></CardContent></details>
    </div>
    <details className="overflow-hidden rounded-xl border border-border bg-card"><summary className="p-5 text-sm font-semibold">All recorded prices / dates and sources</summary><CardHeader><div><CardTitle>Recorded prices</CardTitle><p className="mt-2 text-xs text-muted-foreground">Open the records behind the chart, including when each price became available.</p></div><Button variant="ghost" size="sm" onClick={() => setAll(v => !v)}>{all ? "Recent 8" : "View all observations"}<ArrowUpRight size={13} /></Button></CardHeader><div className="table-wrap max-h-[430px]"><table className="data-table"><thead><tr><th>Trading date</th><th>Contract / exact expiry</th><th>Price · INR / quote</th><th>Volume</th><th>Open interest</th><th>Observed / available · UTC</th><th>Spec</th></tr></thead><tbody>{(all ? data.prices : data.prices.slice(-8)).toReversed().map(p => <tr key={p.trading_date}><td className="number text-muted-foreground">{p.trading_date}</td><td><span className="font-medium">{p.symbol}</span><span className="mt-1 block text-xs text-muted-foreground">{p.expiry}</span></td><td className="number">{money(p.price)}</td><td className="number text-muted-foreground">{number(p.volume)}</td><td className="number text-muted-foreground">{number(p.open_interest)}</td><td className="number text-xs text-muted-foreground">{p.observed_at}<br />{p.available_at}</td><td><Badge className="border-border bg-transparent text-muted-foreground">{p.spec_version}</Badge></td></tr>)}</tbody></table></div><div className="border-t border-border px-5 py-3 text-xs text-muted-foreground">Source: {latest.source} · Dataset: {data.label} · Unit: INR per quotation weight</div></details>
  </div>;
}

function Metric({ label, value, detail, icon, primary = false }: { label: string; value: string; detail: React.ReactNode; icon: React.ReactNode; primary?: boolean }) {
  return <Card className={`p-5 ${primary ? "border-primary/25 bg-gradient-to-br from-primary/[.05] to-card" : ""}`}><div className="flex items-center justify-between gap-2 text-xs text-muted-foreground"><span>{label}</span><span className={primary ? "text-primary" : "text-muted-foreground/60"}>{icon}</span></div><p className={`number my-5 text-[27px] ${primary ? "text-primary" : ""}`}>{value}</p><div className="text-xs leading-5 text-muted-foreground">{detail}</div></Card>;
}
function Detail({ label, value }: { label: string; value: string }) { return <div className="flex justify-between gap-3"><dt className="text-muted-foreground">{label}</dt><dd className="number text-right text-xs">{value}</dd></div>; }
export function PriceChart({ prices }: { prices: Price[] }) {
  // These transforms place API price values on an SVG; they do not calculate indicators.
  const [hovered, setHovered] = useState<number | null>(null);
  const values = prices.map(p => p.price);
  const low = Math.min(...values), high = Math.max(...values);
  const span = high - low || high * .01;
  const y = (v: number) => 215 - ((v - low) / span) * 170;
  const x = (i: number) => 8 + i / Math.max(prices.length - 1, 1) * 682;
  const line = prices.map((p, i) => `${x(i)},${y(p.price)}`).join(" ");
  const focus = hovered !== null ? prices[hovered] : null;
  return <div>
    <div data-testid="price-chart-readout" className="mb-2 min-h-5 text-xs text-muted-foreground">{focus ? `${focus.trading_date} / ${money(focus.price)}` : "Move across the chart to inspect a price"}</div>
    <svg role="img" aria-label={`${prices[0]?.dataset === "synthetic" ? "Synthetic" : "Imported"} price history; exact values are in the observation ledger`} viewBox="0 0 790 260" className="w-full overflow-visible">
      <defs><linearGradient id="gold-area" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="var(--primary)" stopOpacity=".17" /><stop offset="100%" stopColor="var(--primary)" stopOpacity="0" /></linearGradient></defs>
      {[0,.25,.5,.75,1].map(t => <g key={t}><line x1="0" x2="700" y1={45 + t * 170} y2={45 + t * 170} stroke="#26303a" strokeDasharray="3 5" /><text x="714" y={49 + t * 170} fill="#778595" fontSize="10" fontFamily="monospace">{number(high - t * span)}</text></g>)}
      <polygon points={`8,230 ${line} ${x(prices.length - 1)},230`} fill="url(#gold-area)" />
      <polyline points={line} fill="none" stroke="var(--primary)" strokeWidth="2.4" strokeLinejoin="round" strokeLinecap="round" />
      {focus && hovered !== null && <g pointerEvents="none">
        <line x1={x(hovered)} x2={x(hovered)} y1="30" y2="230" stroke="var(--primary)" strokeOpacity=".4" strokeDasharray="3 5" />
        <circle cx={x(hovered)} cy={y(focus.price)} r="5" fill="var(--primary)" stroke="var(--card)" strokeWidth="2" />
      </g>}
      <rect data-testid="price-chart-hit-area" x="8" y="30" width="682" height="200" fill="transparent" pointerEvents="all"
        onPointerMove={event => {
          const svg = event.currentTarget.ownerSVGElement;
          const matrix = svg?.getScreenCTM();
          if (!svg || !matrix || !prices.length) return;
          // Convert screen pixels into SVG coordinates, including responsive scaling.
          const point = svg.createSVGPoint();
          point.x = event.clientX;
          point.y = event.clientY;
          const plotX = point.matrixTransform(matrix.inverse()).x;
          const index = Math.max(0, Math.min(prices.length - 1, Math.round((plotX - 8) / 682 * (prices.length - 1))));
          setHovered(index);
        }}
        onPointerLeave={() => setHovered(null)} onPointerCancel={() => setHovered(null)} />
      <text x="8" y="254" fill="#778595" fontSize="10">{prices[0]?.trading_date}</text><text x="690" y="254" textAnchor="end" fill="#778595" fontSize="10">{prices.at(-1)?.trading_date}</text>
    </svg>
  </div>;
}

export function NormalizedComparison({ data }: { data: Research }) {
  const fmt = number;
  return <Card><CardHeader><CardTitle>Prices side by side</CardTitle></CardHeader><CardContent><p className="mb-4 text-sm leading-6 text-muted-foreground">Compare the INR per gram (999) column for a common weight and purity. Pairs must share the exact expiry date.</p><div className="table-wrap"><table className="data-table"><thead><tr><th>Contract / exact expiry</th><th>Quote INR</th><th>Quote / lot grams</th><th>Quoted purity per mille</th><th>INR / gram (999)</th><th>Trading date / availability</th></tr></thead><tbody>{data.pairing.normalization.map(({contract:c,latest:r,reason}) => <tr key={c.contract_id} className={c.contract_id === data.spec.contract_id ? "selected-row" : ""}><td>{c.symbol}<br/>{c.expiry}<br/>{c.spec_version}</td><td>{r ? fmt(r.price) : "Unavailable"}</td><td>{c.quotation_grams ?? "Unknown"} / {c.lot_size_grams ?? "Unknown"}</td><td>{c.quote_purity_per_mille ?? "Unknown"}</td><td>{r ? fmt(Number(r.normalized_999_inr_per_gram), 4) : reason}</td><td>{r?.trading_date}<br/>{r?.normalized_available_at}</td></tr>)}</tbody></table></div></CardContent></Card>;
}
