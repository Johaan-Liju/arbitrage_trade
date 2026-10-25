"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Bell, Check, Clock3, FlaskConical, ShieldCheck } from "lucide-react";
import { api, post } from "@/lib/api";
import type { Dataset } from "@/lib/types";
import type { AlertCatalog, AlertHistory, AlertScan, AlertSettings, Package, PaperAlert, PaperSession } from "@/lib/alert-types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const stamp = (v: string) => v.replace("T", " ").replace("Z", " UTC");
const fmt = (v: string | number, digits = 2) => Number(v).toLocaleString("en-IN", { minimumFractionDigits: digits, maximumFractionDigits: digits });
const policyName = (p: string) => p === "model" ? "Cost-filtered model" : "Fixed-z baseline comparator";
const defaults: AlertSettings = { policy: "model", min_abs_z: "2.5", min_severe_net_bps: "10", max_age_hours: 24, cooldown_hours: 24, expires_hours: 12 };

export function AlertsScreen() {
  const [ready, setReady] = useState(false);
  const [dataset, setDataset] = useState<Dataset>("synthetic");
  const [cutoff, setCutoff] = useState("");
  const [draft, setDraft] = useState("");
  const [catalog, setCatalog] = useState<AlertCatalog | null>(null);
  const [sessions, setSessions] = useState<PaperSession[]>([]);
  const [session, setSession] = useState("");
  const [settings, setSettings] = useState<AlertSettings>(defaults);
  const [history, setHistory] = useState<AlertHistory | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [refresh, setRefresh] = useState(0);
  const generation = useRef(0);
  const action = useRef(false);

  useEffect(() => {
    const q = new URLSearchParams(window.location.search);
    setDataset(q.get("dataset") === "real" ? "real" : "synthetic");
    setCutoff(q.get("asOf") || ""); setDraft((q.get("asOf") || "").replace(/Z$/, ""));
    setSession(q.get("paperSession") || ""); setReady(true);
  }, []);

  useEffect(() => {
    if (!ready) return;
    const controller = new AbortController();
    const version = ++generation.current;
    setBusy(true); setError(""); setHistory(null); setCatalog(null);
    async function load() {
      try {
        const params = new URLSearchParams({ dataset, ...(cutoff ? { as_of: cutoff } : {}) });
        const [next, saved] = await Promise.all([
          api<AlertCatalog>(`alerts/catalog?${params}`, controller.signal),
          api<{ sessions: PaperSession[] }>(`alerts/sessions?dataset=${dataset}`, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        const asOf = cutoff || next.default_as_of;
        setCatalog(next); setSessions(saved.sessions); setDraft(asOf.replace(/Z$/, ""));
        // Never switch silently to another session when a shared session link is missing.
        const chosen = session || saved.sessions[0]?.id || "";
        if (chosen) {
          const result = await api<AlertHistory>(`alerts/history?${new URLSearchParams({ dataset, session_id: chosen, as_of: asOf })}`, controller.signal);
          if (controller.signal.aborted) return;
          setHistory(result); setSettings(result.session.settings);
        }
        const url = new URL(window.location.href);
        url.search = new URLSearchParams({ dataset, asOf, ...(chosen ? { paperSession: chosen } : {}) }).toString();
        window.history.replaceState(null, "", url);
      } catch (e) {
        if (!controller.signal.aborted) setError(e instanceof Error ? e.message : "Unable to load paper research");
      } finally { if (version === generation.current && !controller.signal.aborted) setBusy(false); }
    }
    void load();
    return () => controller.abort();
  }, [ready, dataset, cutoff, session, refresh]);

  const asOf = cutoff || catalog?.default_as_of || "";
  const selected = session || history?.session.id || "";
  const changed = !!history && JSON.stringify(settings) !== JSON.stringify(history.session.settings);
  const nav = new URLSearchParams({ dataset, ...(asOf ? { asOf } : {}) });

  async function run(create: boolean) {
    if (action.current || !asOf) return;
    action.current = true; setBusy(true); setError(""); setNotice(""); setHistory(null);
    const version = generation.current;
    try {
      let id = selected;
      if (create) {
        const created = await post<PaperSession>("alerts/sessions", { dataset, settings });
        id = created.id;
        setSessions(previous => [created, ...previous]);
      }
      const result = await post<AlertScan>("alerts/scan", { dataset, session_id: id, as_of: asOf });
      const next = await api<AlertHistory>(`alerts/history?${new URLSearchParams({ dataset, session_id: id, as_of: asOf })}`);
      if (version !== generation.current) return;
      setHistory(next);
      setSession(id);
      setNotice(result.new_alert_ids.length ? `${result.new_alert_ids.length} new paper alert. Review the evidence and uncertainty below.` : result.repeated_scan ? "This cutoff was already evaluated. No duplicate notifications." : `No new notifications. ${result.reason || "The model abstained."}`);
      // Preserve session selection without reloading and erasing the notification.
      const url = new URL(window.location.href);
      url.search = new URLSearchParams({ dataset, asOf, paperSession: id }).toString();
      window.history.replaceState(null, "", url);
    } catch (e) {
      if (version === generation.current) setError(e instanceof Error ? e.message : "Paper scan failed");
    } finally { action.current = false; if (version === generation.current) setBusy(false); }
  }

  async function readAlert(id: string) {
    try {
      await post(`alerts/read?${new URLSearchParams({ dataset, session_id: selected, alert_id: id })}`, {});
      setHistory(previous => previous ? { ...previous, unread_count: Math.max(0, previous.unread_count - 1), alerts: previous.alerts.map(a => a.id === id ? { ...a, read: true } : a) } : previous);
    } catch (e) { setError(e instanceof Error ? e.message : "Could not mark notification read"); }
  }

  return <div className="mx-auto max-w-7xl px-4 py-6 sm:px-8">
    <header className="mb-7 flex items-center justify-between gap-4"><Link href={`/?${nav}`} className="text-xl font-semibold text-primary">GoldLens</Link><nav aria-label="Main navigation" className="flex gap-5"><Link href={`/?${nav}`}>Monitor</Link><Link aria-current="page" href={`/alerts?${nav}`}>Alerts</Link></nav></header>
    <main className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4"><div><p className="mb-2 text-xs font-medium uppercase tracking-widest text-primary">Research / paper evaluation</p><h1 className="text-3xl font-semibold">Alerts</h1><p className="mt-2 text-muted-foreground">Evidence first. Follow exact contracts from signal to subsequent paper outcome.</p></div><span className="flex items-center gap-2 rounded-full border border-border px-3 py-2 text-xs"><FlaskConical size={15} /> In-app only</span></div>
      <div role="note" aria-label="Dataset disclosure" data-testid="dataset-banner" className="rounded-lg border border-primary/30 bg-card p-4 text-sm"><strong className="text-primary">{dataset === "synthetic" ? "SYNTHETIC DATA" : "IMPORTED REAL DATA"}</strong><p className="mt-1 text-muted-foreground">{dataset === "synthetic" ? "Invented prices, specifications and liquidity. Paper replay, with no live market feed." : "Only locally imported real records. An evaluated real-data model is required before alerts can be issued."}</p></div>
      <Card className="p-4"><div className="grid gap-4 sm:grid-cols-3">
        <label>Dataset<select aria-label="Dataset" className="field mt-2" value={dataset} disabled={busy} onChange={e => { generation.current++; setDataset(e.target.value as Dataset); setSession(""); setSessions([]); setHistory(null); setCatalog(null); setSettings(defaults); }}><option value="synthetic">Synthetic demo</option><option value="real">Imported real data</option></select></label>
        <form className="sm:col-span-2 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); const next = `${draft}${draft.length === 16 ? ":00" : ""}Z`; setHistory(null); setCutoff(next); setRefresh(n => n + 1); }}><label className="min-w-0 flex-1">Information cutoff (UTC)<input aria-label="Information cutoff (UTC)" type="datetime-local" step="1" className="field mt-2" value={draft} required onChange={e => setDraft(e.target.value)} /></label><Button disabled={busy || !draft}>View cutoff</Button></form>
      </div><p className="mt-3 text-xs text-muted-foreground">All freshness, expiry and outcomes use this explicit UTC cutoff. Viewing history does not issue notifications. Scan manually to evaluate newly imported records; no background polling.</p></Card>
      {error && <Card role="alert" className="border-warning/30 p-5"><h2 className="font-semibold">Research is paused</h2><p className="mt-2 text-sm">{error}</p><p className="mt-2 text-sm text-muted-foreground">Opportunity notifications are withheld when the required data or evaluated model is unavailable.</p><Button className="mt-3" variant="outline" onClick={() => setRefresh(n => n + 1)}>Retry</Button></Card>}
      {busy && <p role="status">Loading paper research…</p>}
      {catalog && <>
        <Card className="p-5" data-testid="model-evidence"><div className="flex items-center gap-2"><ShieldCheck className="text-primary" size={19} /><h2 className="text-lg font-semibold">What the evaluation supports</h2></div><p className="mt-2">{catalog.evaluation.scope}</p><div className="mt-4 grid gap-4 sm:grid-cols-3"><Metric title="Cost-filtered model" value={`${catalog.evaluation.metrics.model.alerts} held-out alerts`} detail={`Across ${catalog.evaluation.metrics.model.eligible_pair_decisions} eligible decisions`} /><Metric title="Fixed-z comparator" value={`${catalog.evaluation.metrics.baseline.alerts} held-out alert`} detail={`${catalog.evaluation.metrics.baseline.complete_alert_outcomes} completed paper outcome`} /><Metric title="Probability" value="Not available" detail="Calibration has not been evaluated" /></div><p className="mt-4 text-sm text-muted-foreground">Experimental evidence from one synthetic expiry is insufficient to establish market performance. The cost-filtered model abstained on the held-out sample. New thresholds and notification filters have no separately measured performance.</p><details className="mt-3 text-xs text-muted-foreground"><summary>Model version and evaluation provenance</summary><p className="mt-2">Version {catalog.model_version} · evaluation cutoff {stamp(catalog.evaluation.as_of)}</p><p>Protocol {catalog.protocol_hash}</p><p>Report {catalog.evaluation.report_id}</p>{catalog.evaluation.evidence.missing_or_insufficient.map(r => <p className="mt-2" key={r}>{r}</p>)}</details></Card>
        <Card className="p-5"><h2 className="text-lg font-semibold">Paper session & notification rules</h2><p className="mt-2 text-sm text-muted-foreground">Each session keeps its own immutable settings, deduplication and cooldown. New settings start a separate experiment and retain earlier history.</p>
          {!!sessions.length && <label className="mt-4 block">Saved session<select aria-label="Saved session" className="field mt-2" value={selected} disabled={busy} onChange={e => { setSession(e.target.value); setHistory(null); }} >{sessions.map(s => <option key={s.id} value={s.id}>{policyName(s.settings.policy)} · {s.id.slice(0, 8)} · {s.created_at}</option>)}</select></label>}
          <form className="mt-4" onSubmit={e => { e.preventDefault(); void run(true); }}>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <label>Policy<select aria-label="Policy" className="field mt-2" value={settings.policy} disabled={busy} onChange={e => setSettings({ ...settings, policy: e.target.value as AlertSettings["policy"] })}><option value="model">Cost-filtered model (evaluated)</option><option value="baseline">Fixed-z baseline (paper comparator)</option></select></label>
              <label>Minimum absolute z<input aria-label="Minimum absolute z" className="field mt-2" type="number" required min="2.5" max="100" step="0.1" value={settings.min_abs_z} onChange={e => setSettings({ ...settings, min_abs_z: e.target.value })} /></label>
              <label>Severe net return must exceed (bps)<input aria-label="Minimum severe net bps" className="field mt-2" type="number" required min="10" max="10000" step="1" disabled={settings.policy === "baseline"} value={settings.min_severe_net_bps} onChange={e => setSettings({ ...settings, min_severe_net_bps: e.target.value })} /></label>
              <label>Maximum input age (hours)<input aria-label="Maximum input age" className="field mt-2" type="number" required min="1" max="24" value={settings.max_age_hours} onChange={e => setSettings({ ...settings, max_age_hours: Number(e.target.value) })} /></label>
              <label>Cooldown (hours)<input aria-label="Cooldown" className="field mt-2" type="number" required min="0" max="720" value={settings.cooldown_hours} onChange={e => setSettings({ ...settings, cooldown_hours: Number(e.target.value) })} /></label>
              <label>Alert lifetime (hours)<input aria-label="Alert lifetime" className="field mt-2" type="number" required min="1" max="24" value={settings.expires_hours} onChange={e => setSettings({ ...settings, expires_hours: Number(e.target.value) })} /></label>
            </div>
            <p className="mt-3 text-xs text-muted-foreground">The model always requires |z| ≥ 2.5, ten prior common sessions, complete cost and settlement inputs, and usable volume/OI. Stricter settings can suppress more alerts. The baseline comparator omits the severe-cost filter. Notifications also expire at freshness, entry and safety boundaries.</p>
            <div className="mt-4 flex flex-wrap gap-3"><Button type="submit" disabled={busy}>Start new paper session</Button><Button type="button" variant="outline" disabled={busy || !selected || changed} onClick={() => void run(false)}>Scan at cutoff</Button></div>
            {changed && <p className="mt-3 text-xs text-warning">Rules changed. Start a new session to apply them; saved signals keep their original settings.</p>}
          </form>
        </Card>
      </>}
      {!!notice && <Card role="status" aria-live="polite" data-testid="notification" className="border-primary/40 p-4"><div className="flex items-start gap-3"><Bell size={19} className="mt-0.5 shrink-0 text-primary" /><p>{notice}</p></div></Card>}
      {history && <section aria-label="Paper alert history" className="space-y-4"><div className="flex flex-wrap items-center justify-between gap-3"><h2 className="text-xl font-semibold">Notifications & outcomes</h2><span className="text-sm text-muted-foreground">{history.unread_count} unread · {history.active_count} active at cutoff</span></div>
        {history.last_scan && <Card className="p-4" data-testid="scan-result"><p className="text-sm">Last scan {stamp(history.last_scan.as_of)} · Inputs {history.last_scan.input_status}</p><p className="mt-2 text-muted-foreground">{history.last_scan.reason || "Paper notification recorded."}</p>{history.last_scan.prediction?.features && <p className="mt-2 text-xs">Observed z-score {fmt(history.last_scan.prediction.features.z_score, 3)} · Ten prior sessions · Uncalibrated deterministic score</p>}</Card>}
        {!history.alerts.length && <Card className="p-8 text-center" data-testid="no-alerts"><Bell size={26} className="mx-auto text-muted-foreground" /><h3 className="mt-3 text-lg font-medium">No opportunity alerts at this cutoff</h3><p className="mx-auto mt-2 max-w-xl text-sm text-muted-foreground">Abstention is a valid model result. Advance the cutoff and scan to follow new observations. Missing or stale inputs cannot generate opportunity alerts.</p></Card>}
        {history.alerts.map(alert => <AlertCard key={alert.id} alert={alert} onRead={() => void readAlert(alert.id)} />)}
      </section>}
      {catalog && !history && !busy && !error && <Card className="p-6 text-center"><Clock3 size={24} className="mx-auto text-primary" /><h2 className="mt-3 font-semibold">Begin a paper evaluation</h2><p className="mt-2 text-sm text-muted-foreground">Choose rules and start a session. Every emitted signal stays in its history as later outcomes become available.</p></Card>}
      <footer className="pb-5 text-xs leading-6 text-muted-foreground">Research only. Daily prices are hypothetical execution proxies. Costs, liquidity, execution and settlement remain uncertain. No trade execution or guaranteed arbitrage.</footer>
    </main>
  </div>;
}

function Metric({ title, value, detail }: { title: string; value: string; detail: string }) {
  return <div className="rounded-lg border border-border bg-background p-4"><p className="text-xs text-muted-foreground">{title}</p><p className="mt-2 text-xl font-semibold">{value}</p><p className="mt-2 text-xs text-muted-foreground">{detail}</p></div>;
}

function Costs({ value, outcome = false }: { value: Package; outcome?: boolean }) {
  return <><div className="table-wrap mt-3"><table className="data-table"><caption className="sr-only">{outcome ? "Paper outcome scenarios" : "Estimated cost scenarios"}</caption><thead><tr><th>Scenario</th><th>Costs INR</th><th>{outcome ? "Paper net INR" : "Hypothesis net INR"}</th><th>Net return</th></tr></thead><tbody>{Object.entries(value.scenarios).map(([name, s]) => <tr key={name}><td>{name}</td><td className="number">{fmt(s.cost_inr)}</td><td className="number">{fmt(s.net_inr)}</td><td className="number">{fmt(s.net_return, 6)} × notional</td></tr>)}</tbody></table></div><p className="mt-2 text-xs text-muted-foreground">Gross package notional INR {fmt(value.initial_gross_notional_inr)}. {outcome ? "Subsequent daily source prices; no observed fills." : "Assumes reversion to the frozen prior mean; this is not a predicted success probability."}</p><details className="mt-3 text-xs text-muted-foreground"><summary>Four-sided cost breakdown</summary>{Object.entries(value.scenarios).map(([name, s]) => <div key={name} className="mt-3"><strong>{name}</strong>{s.items.map(i => <p key={`${i.leg}-${i.side}`} className="mt-1">Leg {i.leg + 1} {i.side}: brokerage INR {fmt(i.brokerage_inr)}, other INR {fmt(i.other_inr)}, slippage INR {fmt(i.slippage_inr)}, fixed INR {fmt(i.fixed_inr)}</p>)}</div>)}</details></>;
}

function AlertCard({ alert, onRead }: { alert: PaperAlert; onRead: () => void }) {
  const r = alert.record;
  return <Card className="min-w-0 overflow-hidden p-5" data-testid="paper-alert"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs uppercase tracking-wide text-primary">{alert.dataset} · {policyName(alert.policy)}</p><h3 className="mt-2 text-lg font-semibold">{alert.contracts.map(c => c.symbol).join(" / ")} <span className="text-muted-foreground">· {alert.contracts[0].expiry}</span></h3><p className="mt-2 text-sm">{alert.status} at selected cutoff · {alert.read ? "Read" : "Unread"}</p></div>{!alert.read && <Button variant="outline" size="sm" onClick={onRead}><Check size={14} className="mr-2" />Mark read</Button>}</div>
    <dl className="mt-5 grid gap-4 text-sm sm:grid-cols-2 lg:grid-cols-4"><div><dt className="text-muted-foreground">Signal time</dt><dd className="mt-1">{stamp(alert.signal_at)}</dd></div><div><dt className="text-muted-foreground">Prediction horizon</dt><dd className="mt-1">{alert.horizon.holding_sessions} common sessions after entry</dd><dd className="mt-1 text-xs">Entry {alert.horizon.entry} → Exit {alert.horizon.exit}</dd></div><div><dt className="text-muted-foreground">Model version</dt><dd className="mt-1">{alert.model_version}</dd><dd className="mt-1 text-xs">{policyName(alert.policy)}</dd></div><div><dt className="text-muted-foreground">Signal expires</dt><dd className="mt-1">{stamp(alert.expires_at)}</dd></div></dl>
    <div className="mt-5 grid gap-3 sm:grid-cols-2">{alert.contracts.map((c, i) => <div className="rounded-lg border border-border p-3 text-sm" key={c.contract_id}><strong>{c.symbol} · Exact expiry {c.expiry}</strong><p className="mt-1 text-xs text-muted-foreground">{c.spec_id} / {c.spec_version} · {r.lots?.[i]} lots · Paper {r.sides?.[i] === 1 ? "long" : "short"}</p><p className="mt-1 text-xs">{c.currency} per {c.quotation_grams} g · {c.unit}</p></div>)}</div>
    <h4 className="mt-5 font-medium">Supporting observations</h4><p className="mt-2 text-sm">z-score {fmt(r.features!.z_score, 3)} · spread {fmt(r.features!.spread, 4)} INR/g (999) · prior mean {fmt(r.features!.prior_mean, 4)} · prior standard deviation {fmt(r.features!.prior_std, 4)} · {r.features!.prior_count} prior common sessions</p><p className="mt-2 text-xs text-muted-foreground">No probability is shown: calibration has not been evaluated.</p>
    <details className="mt-3 text-sm"><summary>Source observations ({alert.observations.length}) and availability times</summary><div className="table-wrap mt-3"><table className="data-table"><thead><tr><th>Contract / specification</th><th>Trading date / price</th><th>Observed / available UTC</th><th>Volume / OI</th><th>Source</th></tr></thead><tbody>{alert.observations.map(o => <tr key={`${o.contract_id}-${o.trading_date}`}><td>{o.instrument} / {o.expiry}<span className="block text-xs">{o.spec_id} / {o.spec_version}</span></td><td>{o.trading_date}<span className="block text-xs">{fmt(o.price)} {o.currency} · {o.price_unit}</span></td><td>{stamp(o.observed_at)}<span className="block text-xs">{stamp(o.available_at)}</span></td><td>{o.volume ?? "Missing"} / {o.open_interest ?? "Missing"}</td><td><a className="text-primary underline" href={o.source_url} target="_blank" rel="noreferrer">Source record</a></td></tr>)}</tbody></table></div></details>
    <h4 className="mt-5 font-medium">Estimated costs at signal time</h4>{r.forecast && <Costs value={r.forecast.estimated_package} />}<p className="mt-3 text-xs text-muted-foreground">{alert.cost_uncertainty}</p>
    <div className="mt-5 grid gap-4 sm:grid-cols-2"><div><h4 className="font-medium">Liquidity & execution uncertainty</h4><p className="mt-2 text-sm text-muted-foreground">{alert.liquidity_uncertainty}</p></div><div><h4 className="font-medium">Settlement uncertainty</h4><p className="mt-2 text-sm text-muted-foreground">{alert.settlement_uncertainty}</p></div></div>
    <details className="mt-3 text-xs text-muted-foreground"><summary>Exact settlement references and frozen rules</summary>{alert.contracts.map(c => <p key={c.contract_id} className="mt-3">{c.symbol}: {c.settlement_method} · {c.settlement_terms} · {c.delivery_location} · {c.delivery_restrictions} · Safe exit {c.safe_exit_date}. <a className="text-primary underline" href={c.source} target="_blank" rel="noreferrer">Specification source</a></p>)}<p className="mt-3">Rules: |z| ≥ {alert.settings.min_abs_z}; {alert.policy === "model" ? `severe net > ${alert.settings.min_severe_net_bps} bps; ` : ""}age ≤ {alert.settings.max_age_hours}h; cooldown {alert.settings.cooldown_hours}h; lifetime ≤ {alert.settings.expires_hours}h.</p><p className="mt-2">Protocol {alert.protocol_hash}</p><p>Evaluation {alert.evaluation_report_id}</p></details>
    <div className="mt-5 border-t border-border pt-5" data-testid="paper-outcome"><h4 className="font-medium">Subsequent paper outcome</h4><p className="mt-2">{alert.outcome?.status || "PENDING"}{alert.outcome?.label ? ` · ${alert.outcome.label}` : ""}</p>{alert.outcome?.reason && <p className="mt-2 text-sm text-muted-foreground">{alert.outcome.reason}</p>}{alert.outcome?.label_available_at && <p className="mt-2 text-xs">Outcome available {stamp(alert.outcome.label_available_at)}</p>}{alert.outcome?.scenarios && <Costs value={alert.outcome as Package} outcome />}<details className="mt-3 text-xs text-muted-foreground"><summary>Outcome history ({alert.outcome_history.length} checks)</summary>{alert.outcome_history.map(o => <p key={o.as_of} className="mt-2">{stamp(o.as_of)} · {o.status}{o.label ? ` · ${o.label}` : ""}{o.reason ? ` · ${o.reason}` : ""}</p>)}</details><p className="mt-3 text-xs text-muted-foreground">Pending or missing endpoints are not losses. Fixed entry and exit dates are never replaced. Overlapping paper outcomes are not portfolio returns.</p></div>
  </Card>;
}
