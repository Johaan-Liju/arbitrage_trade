"""Independent settlement-proxy execution and cash accounting examples."""
from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.backtest import BacktestRequest, simulate


def scenario(z=3, **settings):
    specs = [dict(contract_id=f'{symbol}:2026-09-20:v1', symbol=symbol, expiry='2026-09-20',
                  spec_version='v1', available_at='2026-08-01T00:00:00Z', valid_from='2026-09-01',
                  valid_to='2026-09-20', safe_exit_date='2026-09-15', tender_start='2026-09-17',
                  lot_grams=lot, quote_grams=quote, purity=purity)
             for symbol, lot, quote, purity in [('A',100,10,.995), ('B',8,8,.999)]]
    events = []
    for i, prices in enumerate([(100,80), (110,80), (105,82), (100,84)], 1):
        day = f'2026-09-{i:02d}'
        event = dict(trading_date=day, decision_at=day+'T16:05:00Z', z_score=z if i<3 else 0,
                     status='Investigate' if i==1 else 'No signal', reason='test threshold', quality_reasons=[])
        for key, price in zip(('a','b'), prices):
            event[key] = dict(price=price, volume=100000, open_interest=100000, currency='INR',
                              unit='quote', source='synthetic fixture', observed_at=day+'T16:00:00Z',
                              available_at=day+'T16:05:00Z')
        events.append(event)
    req = BacktestRequest(contract_a=specs[0]['contract_id'], contract_b=specs[1]['contract_id'],
                          as_of='2026-09-10T23:00:00Z', **settings)
    return dict(spec_a=specs[0], spec_b=specs[1], history=events, quality={'missing_dates':[]},
                alignment='EXACT_EXPIRY', cautions=[]), req


@pytest.mark.parametrize('z,sign', [(3,1), (-3,-1)])
def test_both_directions_whole_lots_raw_units_cost_items_and_reconciliation(z, sign):
    pair, req = scenario(z, costs_a={'exchange_bps':2,'tax_bps':3,'other_bps':4,'fixed_inr':7},
                         costs_b={'fixed_inr':11})
    result = simulate(pair, req)
    trade, = result['trades']
    a,b = trade['legs']
    assert [a['lots'],b['lots']] == [2,25]  # 200g per leg, no fractional contracts
    assert [a['direction'],b['direction']] == [-sign,sign]
    # 200/10 * 10 quote decline + 25 * 4 quote rise.
    assert trade['gross_pnl'] == sign*300
    expected_fees = (2200+2000)*.0014 + 14 + (2000+2100)*.0005 + 22
    expected_slippage = (2200+2000+2000+2100)*.001
    assert trade['fees'] == pytest.approx(expected_fees)
    assert trade['slippage'] == pytest.approx(expected_slippage)
    assert trade['net_pnl'] == pytest.approx(sign*300-expected_fees-expected_slippage)
    assert trade['residual_gross_grams'] == 0
    assert trade['residual_fine_gold_grams'] == pytest.approx(sign*.8)
    assert trade['directional_pnl_per_1_inr_999_g'] == pytest.approx(sign*.8/.999)
    assert trade['entry_fill_at'] > trade['signal_available_at']
    assert trade['exit_fill_at'] > trade['exit_signal_available_at']
    assert a['entry_observed_at'] > trade['signal_available_at']
    assert trade['entry_date']=='2026-09-02' and trade['exit_date']=='2026-09-04'
    assert result['realized_net_pnl'] == trade['net_pnl']
    assert result['equity_curve'][-1]['equity'] == pytest.approx(req.initial_capital+trade['net_pnl'])
    for leg in trade['legs']:
        assert leg['entry_fee'] == pytest.approx(sum(leg['entry_cost_items'].values()))
        assert leg['exit_fee'] == pytest.approx(sum(leg['exit_cost_items'].values()))


def test_holding_limit_requests_later_fill_and_open_entry_costs_stay_separate():
    pair, req = scenario(max_holding_days=1)
    for event in pair['history']:
        event['z_score'] = 3
    run = simulate(pair, req)
    assert run['trades'][0]['exit_reason'] == 'Maximum holding period'
    pair['history'] = pair['history'][:3]
    opened = simulate(pair, req)
    assert opened['open_position'] and not opened['trades']
    assert opened['realized_net_pnl'] == opened['realized_fees'] == opened['realized_slippage'] == 0
    assert opened['open_entry_costs'] > 0 and opened['net_pnl'] is None
    assert any('No eligible later' in r['reason'] for r in opened['rejections'])


def test_missing_entry_cancels_missing_exit_leaves_open_and_delayed_signal_cannot_fill():
    pair, req = scenario()
    missing = deepcopy(pair)
    missing['history'].pop(1)
    missing['quality']['missing_dates']=[{'trading_date':'2026-09-02'}]
    run = simulate(missing,req)
    assert not run['trades'] and not run['open_position']
    assert run['rejections'][0]['outcome']=='UNFILLED'
    assert 'Missing next dated' in run['rejections'][0]['reason']
    pair['history'][0]['decision_at']='2026-09-02T16:00:00Z'
    run=simulate(pair,req)
    assert not run['trades'] and any('strictly after' in r['reason'] for r in run['rejections'])
    pair,req=scenario()
    pair['history'].pop()
    pair['quality']['missing_dates']=[{'trading_date':'2026-09-04'}]
    run=simulate(pair,req)
    assert run['open_position'] and not run['trades'] and run['net_pnl'] is None


@pytest.mark.parametrize('field,value', [('expiry','2026-09-03'),('valid_to','2026-09-03'),
                                         ('safe_exit_date','2026-09-03'),('tender_start','2026-09-04')])
def test_earliest_expiry_spec_safe_or_tender_boundary_blocks_entry(field,value):
    pair,req=scenario()
    pair['spec_a'][field]=value
    run=simulate(pair,req)
    assert run['safe_exit_date']=='2026-09-03'
    assert not run['trades'] and any('near safe exit' in r['reason'] for r in run['rejections'])


def test_cutoff_does_not_schedule_future_aware_exit_and_lot_cap_rejects():
    pair,req=scenario()
    early=simulate(pair,req.model_copy(update={'as_of':'2026-09-03T16:05:00Z'}))
    assert early['open_position'] and early['safe_exit_date']=='2026-09-15'
    capped=simulate(pair,req.model_copy(update={'max_lots':24}))
    assert not capped['trades'] and any('Unmatchable' in r['reason'] for r in capped['rejections'])


@pytest.mark.parametrize('setting', [{'max_holding_days':0},{'max_holding_days':1.5},
    {'max_lots':True},{'exit_z':2.5},{'slippage_bps':float('inf')},{'fee_bps':-1},
    {'costs_a':{'tax_bps':-1}},{'costs_b':{'fixed_inr':float('nan')}},{'costs_a':{'unknown':1}}])
def test_invalid_settings(setting):
    with pytest.raises(ValidationError):
        scenario(**setting)


def test_exit_cannot_fill_past_deadline_and_unavailable_fill_is_not_used():
    pair,req=scenario()
    pair['spec_a']['safe_exit_date']='2026-09-08'
    last=pair['history'][-1]
    last.update(trading_date='2026-09-09',decision_at='2026-09-09T16:05:00Z')
    for key in ('a','b'):
        last[key].update(observed_at='2026-09-09T16:00:00Z',available_at='2026-09-09T16:05:00Z')
    run=simulate(pair,req)
    assert run['open_position'] and not run['trades']
    assert any('Past safe exit' in r['reason'] for r in run['rejections'])
    pair,req=scenario()
    pair['history'][1]['b']['available_at']='2026-09-11T00:00:00Z'
    run=simulate(pair,req)
    assert not run['trades'] and any('unavailable at as-of' in r['reason'] for r in run['rejections'])


def test_simulation_removed_from_active_api(tmp_path):
    from fastapi.testclient import TestClient
    from backend.main import create_app
    with TestClient(create_app(tmp_path / 's.sqlite3', tmp_path / 'r.sqlite3', real_only=False)) as client:
        for route in ('/api/backtest', '/backtest'):
            assert client.post(route, json={}).status_code == 404
        assert '/api/ingest' in client.get('/openapi.json').json()['paths']


def test_no_trade_explains_threshold_without_fabricating_trades():
    pair, req = scenario(z=1)
    for event in pair["history"]:
        event["status"] = "No signal"
    result = simulate(pair, req)
    assert result["number_of_trades"] == 0
    assert result["diagnostics"] == dict(paired_observations=4, scored_observations=4,
        entry_signals=0, peak_abs_z=1, entry_threshold=2.5)
    assert "below your entry threshold of 2.5" in result["reason"]
    assert "not evidence of strategy performance" in result["reason"]


def test_no_trade_distinguishes_missing_history_and_blocked_fills():
    pair, req = scenario()
    for event in pair["history"]:
        event.update(status="Insufficient data", z_score=None)
    result = simulate(pair, req)
    assert result["diagnostics"]["scored_observations"] == 0
    assert "No usable signal history" in result["reason"]
    pair, req = scenario(max_lots=1)
    result = simulate(pair, req)
    assert result["diagnostics"]["entry_signals"] == 1
    assert "no entry filled" in result["reason"]
    assert "Unmatchable integer lots" in result["reason"]


def test_replay_diagnostics_exclude_observations_after_safe_exit():
    pair, req = scenario(z=1)
    for event in pair["history"]:
        event["status"] = "No signal"
    later = deepcopy(pair["history"][-1])
    later.update(trading_date="2026-09-16", decision_at="2026-09-16T16:05:00Z", z_score=99, status="Investigate")
    pair["history"].append(later)
    req = req.model_copy(update={"as_of":"2026-09-19T23:00:00Z"})
    result = simulate(pair, req)
    assert result["diagnostics"]["entry_signals"] == 0
    assert result["diagnostics"]["peak_abs_z"] == 1
