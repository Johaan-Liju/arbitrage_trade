"""Manual gate printout without mutating immutable fixtures or published databases."""
from .store import fixtures
from .pairs import pair_history
from .backtest import BacktestRequest, simulate
from .domain import DEFAULT_AS_OF


def run():
    for anomaly in (0,140):
        specs,prices=fixtures(anomaly)
        selected=[next(s for s in specs if s['symbol']==symbol and s['expiry'].startswith('2026-11')) for symbol in ('GOLDTEN','GOLDGUINEA')]
        rows=[[r for r in prices if r['contract_id']==s['contract_id']] for s in selected]
        request=BacktestRequest(contract_a=selected[0]['contract_id'],contract_b=selected[1]['contract_id'],as_of=DEFAULT_AS_OF,allow_calendar=True)
        pair=pair_history(selected,rows,request)
        print(f"SYNTHETIC anomaly={anomaly}: {pair['latest']['status']} — {pair['latest']['reason']}")
        if anomaly:
            for label,changes in [('accepted',{}),('rejected',{'allow_calendar':False}),('no-trade',{'entry_z':100})]:
                config=request.model_copy(update=changes)
                result=simulate(pair_history(selected,rows,config),config)
                print(f"{label}: {result['status']}; trades={result['number_of_trades']}; net={result['net_pnl']:.2f}; rejections={len(result['rejections'])}")
                for trade in result['trades']:
                    print(f"  signal={trade['signal_date']} entry={trade['entry_date']} exit={trade['exit_date']} gross={trade['gross_pnl']:.2f} fees={trade['fees']:.2f} slippage={trade['slippage']:.2f}")

if __name__=='__main__':
    run()
