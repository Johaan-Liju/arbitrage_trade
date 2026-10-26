"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Card } from "@/components/ui/card";

type Source = {
  symbol: string; source_url: string; retrieved_at: string; spec_id: string;
  blockers: string[];
  rows: { expiry: string; trading_date: string; price: string; unit: string }[];
};

export function SourceRecords({ asOf, refresh }: { asOf: string; refresh: number }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    setSources([]); setError("");
    api<{ sources: Source[] }>(`sources${asOf ? `?${new URLSearchParams({ as_of: asOf })}` : ""}`, controller.signal)
      .then(value => { if (!controller.signal.aborted) setSources(value.sources); })
      .catch(reason => { if (!controller.signal.aborted) setError(reason.message); });
    return () => controller.abort();
  }, [asOf, refresh]);
  return <Card className="mb-5 min-w-0 overflow-hidden p-5" data-testid="real-source-records">
    <h2 className="text-lg font-semibold">Collected market records</h2>
    <p className="mt-2 text-sm text-muted-foreground">Public Upstox pages collected with a direct Python scraper. These are source quotes awaiting specification verification. Normalized spreads, predictions and backtests remain unavailable.</p>
    {error && <p role="alert" className="mt-3 text-sm">Source archive unavailable: {error}</p>}
    {!sources.length && !error && <p className="mt-3 text-sm">No collected source records available at this cutoff.</p>}
    <div className="mt-4 grid gap-4 md:grid-cols-2">{sources.map(source => <div key={source.spec_id} className="min-w-0 rounded-lg border p-4">
      <div className="flex items-center justify-between gap-3"><h3 className="font-semibold">{source.symbol}</h3><span className="text-xs text-warning">Terms unverified</span></div>
      <p className="mt-2 text-xs text-muted-foreground">{source.rows.length} daily closes · collected {source.retrieved_at.replace("T", " ").replace("Z", " UTC")}</p>
      <div className="table-wrap mt-3"><table className="data-table"><thead><tr><th>Trading date</th><th>Exact expiry</th><th>Close (INR / source quote)</th></tr></thead><tbody>{source.rows.slice(0, 5).map(row => <tr key={`${row.trading_date}:${row.expiry}`}><td>{row.trading_date}</td><td>{row.expiry}</td><td>{Number(row.price).toLocaleString("en-IN", { minimumFractionDigits: 2 })}</td></tr>)}</tbody></table></div>
      <p className="mt-3 text-xs text-muted-foreground">The source labels its unit “{source.rows[0]?.unit}”; quotation weight is not verified. These values are not normalized INR per gram.</p>
      <a className="mt-3 inline-block text-sm text-primary underline" href={source.source_url} target="_blank" rel="noreferrer">View source</a>
      <details className="mt-3 text-xs text-muted-foreground"><summary>Why model calculations are blocked</summary>{source.blockers.map(reason => <p className="mt-2" key={reason}>{reason}</p>)}</details>
    </div>)}</div>
  </Card>;
}
