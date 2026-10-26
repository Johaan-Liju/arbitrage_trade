"""Hypothetical two-leg replay using raw quote P&L, not normalized-price P&L."""
from datetime import date, timedelta
from hashlib import sha256
import json
import math
from pydantic import BaseModel, ConfigDict, Field, model_validator
from .pairs import PairRequest, seconds


class LegCosts(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    exchange_bps: float = Field(default=0, ge=0, le=1000)
    tax_bps: float = Field(default=0, ge=0, le=1000)
    other_bps: float = Field(default=0, ge=0, le=1000)
    fixed_inr: float = Field(default=0, ge=0, le=1_000_000)


class BacktestRequest(PairRequest):
    exit_z: float = Field(default=.5, ge=0, le=100)
    fee_bps: float = Field(default=5, ge=0, le=1000)
    slippage_bps: float = Field(default=10, ge=0, le=1000)
    max_lots: int = Field(default=100, ge=1, le=10000, strict=True)
    max_holding_days: int = Field(default=10, ge=1, le=365, strict=True)
    costs_a: LegCosts = Field(default_factory=LegCosts)
    costs_b: LegCosts = Field(default_factory=LegCosts)
    max_participation: float = Field(default=.01, gt=0, le=.1)
    initial_capital: float = Field(default=1_000_000, gt=0, le=1e12)
    allow_calendar: bool = False

    @model_validator(mode="after")
    def exit_threshold(self):
        if self.exit_z >= self.entry_z:
            raise ValueError("Exit threshold must be less than entry threshold")
        return self


def lot_match(a,b,max_lots):
    grams = math.lcm(a["lot_grams"],b["lot_grams"])
    lots = [grams//s["lot_grams"] for s in (a,b)]
    if max(lots)>max_lots:
        raise ValueError("Unmatchable integer lots within configured lot cap")
    return lots


def simulate(pair, request):
    specs = [pair["spec_a"],pair["spec_b"]]
    deadlines = [s[k] for s in specs for k in ("safe_exit_date", "expiry", "valid_to") if s.get(k)]
    deadlines += [(date.fromisoformat(s["tender_start"])-timedelta(days=1)).isoformat() for s in specs if s.get("tender_start")]
    cutoff = min(deadlines)
    exit_trigger = (date.fromisoformat(cutoff)-timedelta(days=request.max_age_days)).isoformat()
    blocked = []
    try:
        lots = lot_match(*specs,request.max_lots)
    except ValueError as error:
        lots,blocked = [0,0],[str(error)]
    if pair["alignment"]=="CALENDAR_BASIS_DIFFERENCE" and not request.allow_calendar:
        blocked.append("Calendar mismatch requires explicit allow_calendar acknowledgement")
    events = {e["trading_date"]:e for e in pair["history"] if e["decision_at"]<=request.as_of and e["trading_date"]<=request.as_of[:10]}
    dates = sorted(set(events)|{r["trading_date"] for r in pair["quality"]["missing_dates"] if r["trading_date"]<=request.as_of[:10]})
    trades, rejections, curve = [], [], []
    position = pending = None
    realized = total_fees = total_slippage = 0.0
    peak = request.initial_capital
    max_drawdown = 0.0
    invalid_marks = False

    def reject(day, action, reason):
        rejections.append({"trading_date":day,"action":action,"outcome":"UNFILLED" if action in ("ENTRY", "EXIT") else "SKIPPED","reason":reason,
                           "signal_date":pending["date"] if pending else day,
                           "decision_at":pending["decision_at"] if pending else events.get(day, {}).get("decision_at")})

    def costs(value, config):
        return {"brokerage":value*request.fee_bps/10000, "exchange_clearing":value*config.exchange_bps/10000,
                "tax":value*config.tax_bps/10000, "other":value*config.other_bps/10000, "fixed":config.fixed_inr}

    def leg_values(event):
        return [event[k]["price"] * s["lot_grams"]/s["quote_grams"]*n for k,s,n in zip(('a','b'),specs,lots)]

    def fill_problem(event, order):
        if event["decision_at"] > request.as_of or any(event[k]["available_at"] > request.as_of for k in ('a','b')):
            return "Fill unavailable at as-of cutoff"
        if any(not s["valid_from"] <= event["trading_date"] <= s["valid_to"] or s["available_at"] > event["decision_at"] for s in specs):
            return "Specification unavailable or invalid at fill"
        if event["trading_date"]>cutoff:
            return "No liquidation or entry past safe exit/end date"
        if event["quality_reasons"]:
            return "; ".join(event["quality_reasons"])
        if event["trading_date"]<=order["date"] or any(event[k]["observed_at"]<=order["decision_at"] for k in ('a','b')):
            return "Fill must be dated later and observed strictly after signal availability"
        if (date.fromisoformat(event["trading_date"])-date.fromisoformat(order["date"])).days>request.max_age_days:
            return "Next observation is stale relative to order"
        if any(n>event[k]["volume"]*request.max_participation or n>event[k]["open_interest"]*request.max_participation for k,n in zip(('a','b'),lots)):
            return "Integer lots exceed volume/OI participation proxy"
        if order["action"]=="ENTRY" and event["trading_date"]>=exit_trigger:
            return "Entry too near safe exit/end date to allow later liquidation"
        return None

    for day in dates:
        event = events.get(day)
        if not event:
            if pending:
                reject(day,pending["action"],"Missing next dated observation for one leg; no fill")
                if pending["action"]=="ENTRY":
                    pending = None
            if position:
                position.update(last_mark_date=day, unrealized_gross_pnl=None, unrealized_net_pnl=None)
                invalid_marks = True
                curve.append({"trading_date":day,"equity":None,"net_pnl":None,"drawdown":None,"reason":"Missing one-leg mark; equity unknown"})
            continue
        if day>cutoff:
            if pending:
                reject(day,pending["action"],"Past safe exit/end date; no synthetic liquidation")
                pending = None
            break
        values = leg_values(event)
        filled_exit = False
        if pending:
            problem = fill_problem(event,pending)
            if problem:
                reject(day,pending["action"],problem)
                # Reissue an exit at this event's decision time; never backdate a failed fill.
                pending = {**pending,"original_signal_date":pending.get("original_signal_date", pending["date"]),
                           "original_decision_at":pending.get("original_decision_at", pending["decision_at"]),
                           "date":day,"decision_at":max(event["decision_at"], pending["decision_at"])} if position else None
            elif pending["action"]=="ENTRY":
                sides = [-1,1] if pending["z"]>0 else [1,-1]
                legs = [{"contract_id":s["contract_id"],"symbol":s["symbol"],"expiry":s["expiry"],"spec_version":s["spec_version"],
                         "side":"LONG" if side>0 else "SHORT","direction":side,"lots":n,"grams":n*s["lot_grams"],
                         "entry_quote":event[k]["price"],"entry_notional":v,
                         "quote_grams":s["quote_grams"],"lot_grams":s["lot_grams"],"currency":event[k].get("currency", "INR"),
                         "unit":event[k].get("unit"),"source":event[k].get("source"),
                         "entry_observed_at":event[k]["observed_at"],"entry_available_at":event[k]["available_at"],
                         "entry_cost_items":costs(v, request.costs_a if k=='a' else request.costs_b),
                         "entry_fee":sum(costs(v, request.costs_a if k=='a' else request.costs_b).values()),"entry_slippage":v*request.slippage_bps/10000}
                        for s,n,side,v,k in zip(specs,lots,sides,values,('a','b'))]
                fees = sum(l["entry_fee"] for l in legs)
                slip = sum(l["entry_slippage"] for l in legs)
                total_fees += fees
                total_slippage += slip
                position = {"signal_date":pending["date"],"signal_available_at":pending["decision_at"],"entry_date":day,
                            "signal_observed_at":pending["signal_observed_at"],
                            "entry_signal_z":pending["z"],"entry_fill_at":event["decision_at"],"fill_assumption":"Paired raw settlement proxy; costs assumed",
                            "entry_reason":pending["reason"],"legs":legs,"entry_costs":fees+slip,
                            "residual_gross_grams":sum(side*n*s["lot_grams"] for side,n,s in zip(sides,lots,specs)),
                            "residual_fine_gold_grams":sum(side*n*s["lot_grams"]*s["purity"] for side,n,s in zip(sides,lots,specs)),
                            "directional_pnl_per_1_inr_999_g":sum(side*n*s["lot_grams"]*s["purity"]/.999 for side,n,s in zip(sides,lots,specs))}
                pending = None
            else:
                gross = 0.0
                for leg,v,k in zip(position["legs"],values,('a','b')):
                    items = costs(v, request.costs_a if k=='a' else request.costs_b)
                    leg.update(exit_quote=event[k]["price"],exit_notional=v,exit_fee=sum(items.values()),exit_cost_items=items,
                               exit_observed_at=event[k]["observed_at"],exit_available_at=event[k]["available_at"],
                               exit_slippage=v*request.slippage_bps/10000,gross_pnl=leg["direction"]*(v-leg["entry_notional"]))
                    gross += leg["gross_pnl"]
                fees = sum(l["entry_fee"]+l["exit_fee"] for l in position["legs"])
                slip = sum(l["entry_slippage"]+l["exit_slippage"] for l in position["legs"])
                total_fees += sum(l["exit_fee"] for l in position["legs"])
                total_slippage += sum(l["exit_slippage"] for l in position["legs"])
                realized += gross-fees-slip
                trades.append({**position,"exit_date":day,"exit_signal_date":pending["date"],"exit_signal_available_at":pending["decision_at"],
                               "original_exit_signal_date":pending.get("original_signal_date", pending["date"]),
                               "original_exit_decision_at":pending.get("original_decision_at", pending["decision_at"]),
                               "exit_fill_at":event["decision_at"],
                               "exit_reason":pending["reason"],"gross_pnl":gross,"fees":fees,"slippage":slip,"net_pnl":gross-fees-slip})
                position = pending = None
                filled_exit = True
        mark_ok = not event["quality_reasons"]
        if position and not mark_ok:
            position.update(last_mark_date=day, unrealized_gross_pnl=None, unrealized_net_pnl=None)
            invalid_marks = True
            curve.append({"trading_date":day,"equity":None,"net_pnl":None,"drawdown":None,"reason":"Rejected/stale mark"})
        else:
            unrealized = sum(l["direction"]*(v-l["entry_notional"]) for l,v in zip(position["legs"],values))-position["entry_costs"] if position else 0
            if position:
                position.update(last_mark_date=day, unrealized_gross_pnl=unrealized+position["entry_costs"], unrealized_net_pnl=unrealized)
            net = realized+unrealized
            equity = request.initial_capital+net
            peak = max(peak,equity)
            dd = peak-equity
            max_drawdown = max(max_drawdown,dd)
            curve.append({"trading_date":day,"equity":equity,"net_pnl":net,"drawdown":dd,"reason":"Raw-quote mark to market; costs deducted"})
        holding_limit = position and (date.fromisoformat(day)-date.fromisoformat(position["entry_date"])).days >= request.max_holding_days
        if position and pending is None and (day>=exit_trigger or holding_limit or (event["z_score"] is not None and abs(event["z_score"])<=request.exit_z)):
            if event["status"]=="Investigate":
                reject(day,"SIGNAL","Position occupied; exit requested instead of new entry")
            pending = {"action":"EXIT","date":day,"decision_at":event["decision_at"],"reason":"Scheduled safe exit" if day>=exit_trigger else "Maximum holding period" if holding_limit else "Z-score converged within exit threshold"}
        elif not position and not pending and not filled_exit and event["status"]=="Investigate":
            reasons = blocked + (["Entry too near safe exit/end date"] if day>=exit_trigger else [])
            if reasons:
                reject(day,"ENTRY","; ".join(reasons))
            else:
                pending = {"action":"ENTRY","date":day,"decision_at":event["decision_at"],"reason":event["reason"],"z":event["z_score"],
                           "signal_observed_at":{k:event[k]["observed_at"] for k in ('a','b')}}
        elif event["status"]=="Insufficient data":
            reject(day,"SIGNAL",event["reason"])
        elif event["status"]=="Investigate":
            reject(day,"SIGNAL","Position or order occupied; no pyramiding or same-observation reversal")
    if pending:
        reject(pending["date"],pending["action"],"No eligible later observation to fill pending order")
    complete = position is None and not invalid_marks
    # Explain the actual replay window, not later observations beyond the safe exit.
    replay = [event for day, event in events.items() if day <= cutoff]
    scored = [event for event in replay if event["status"] != "Insufficient data" and event["z_score"] is not None]
    signals = sum(event["status"] == "Investigate" for event in replay)
    peak_z = max((abs(event["z_score"]) for event in scored), default=None)
    diagnostics = {"paired_observations": len(replay), "scored_observations": len(scored),
                   "entry_signals": signals, "peak_abs_z": peak_z, "entry_threshold": request.entry_z}
    if not complete:
        reason = "Unpriced marks or unresolved open position; total performance withheld"
    elif trades:
        reason = "Completed hypothetical round trips"
    elif not scored:
        reason = "No usable signal history in this replay window. Review the warm-up and data checks below."
    elif not signals:
        reason = (f"No entry signal: the largest eligible absolute z-score was {peak_z:.3f}, "
                  f"below your entry threshold of {request.entry_z:g}, across {len(scored)} scored observations. "
                  "No trades were opened; zero P&L is not evidence of strategy performance.")
    else:
        entry_reasons = list(dict.fromkeys(r["reason"] for r in rejections if r["action"] == "ENTRY"))
        reason = f"{signals} entry signal(s), but no entry filled. " + " ".join(entry_reasons)
    result = {"dataset":request.dataset,"label":request.dataset.upper()+" HYPOTHETICAL SIMULATION","as_of":request.as_of,"config":request.model_dump(),
              "spec_a":specs[0],"spec_b":specs[1],"alignment":pair["alignment"],"safe_exit_date":cutoff,"lots_a":lots[0],"lots_b":lots[1],
              "status":"COMPLETE" if complete else "INCOMPLETE","number_of_trades":len(trades),"trades":trades,"rejections":rejections,
              "open_position":position,"equity_curve":curve,"gross_pnl":sum(t["gross_pnl"] for t in trades),
              "fees":total_fees,"slippage":total_slippage,"realized_net_pnl":realized,"net_pnl":realized if complete else None,
              "realized_fees":sum(t["fees"] for t in trades),"realized_slippage":sum(t["slippage"] for t in trades),
              "open_entry_costs":position["entry_costs"] if position else 0,
              "max_drawdown":max_drawdown if not invalid_marks else None,
              "reason":reason, "diagnostics":diagnostics,
              "assumptions":["Next dated observation settlement proxy only; signal availability must precede both fill observations.",
                  "Same grams per leg via integer lots; purity and price sensitivity may differ. No perfect market neutrality.",
                  "All fills, brokerage, exchange/clearing, tax, other/fixed costs and adverse slippage are configurable assumptions, not official charges. Zero cost means omitted. Funding/delivery costs are not modeled.",
                  "Daily volume/OI participation is a proxy. No bids, asks, intraday execution, partial fills or margin calls modeled.",
                  "Initial capital is an equity reference, not required margin. Margin funding and settlement can invalidate results.",
                  "Exit requested before known cutoff with a calendar-day buffer; missing fills can leave an unresolved position."]+pair["cautions"]}
    result["run_id"] = sha256(json.dumps({"result":result,"input":pair},sort_keys=True).encode()).hexdigest()[:24]
    return result
