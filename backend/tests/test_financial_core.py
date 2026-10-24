"""Financial invariants, independent arithmetic, chronology and reproducible scenarios."""
import copy
import csv
from io import StringIO
import math
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend.domain import DEFAULT_AS_OF, normalize, validate_price, Spec
from backend.store import fixtures, connection, seed
from backend.legacy_ingestion import COLUMNS, validate_csv
from backend.pairs import PairRequest, pair_history
from backend.backtest import BacktestRequest, simulate, lot_match
from backend.legacy_api import create_app


def example(anomaly=140, **options):
    specs, prices = fixtures(anomaly)
    pair_specs = [next(s for s in specs if s['symbol']==symbol and s['expiry'].startswith('2026-11')) for symbol in ('GOLDTEN','GOLDGUINEA')]
    histories = [[r for r in prices if r['contract_id']==s['contract_id']] for s in pair_specs]
    request = BacktestRequest(contract_a=pair_specs[0]['contract_id'],contract_b=pair_specs[1]['contract_id'],as_of=DEFAULT_AS_OF,allow_calendar=True,**options)
    return pair_specs,histories,request


def csv_text(rows):
    output=StringIO(); writer=csv.DictWriter(output,fieldnames=COLUMNS); writer.writeheader(); writer.writerows(rows)
    return output.getvalue()


def test_hand_calculations_quote_not_lot():
    specs,_=fixtures()
    mini=next(s for s in specs if s['symbol']=='GOLDM')
    ten=next(s for s in specs if s['symbol']=='GOLDTEN')
    guinea=next(s for s in specs if s['symbol']=='GOLDGUINEA')
    # 74,625 / 10 = 7,462.5; times 999/995 = 7,492.5.
    assert normalize(74625,mini)==pytest.approx(7492.5)
    assert mini['lot_grams']==100 and mini['quote_grams']==10
    assert 74625*mini['lot_grams']/mini['quote_grams']==746250
    assert normalize(75000,ten)==7500
    assert normalize(60080,guinea)==7510
    assert normalize(75000,ten)-normalize(60080,guinea)==-10
    assert lot_match(ten,guinea,100)==[4,5]  # 40g on each side.
    with pytest.raises(ValueError,match='Unmatchable'):
        lot_match(ten,guinea,3)


def test_real_unverified_fail_closed():
    specs,_=fixtures()
    spec={**specs[0],'dataset':'real','verification':'UNVERIFIED'}
    with pytest.raises(ValueError,match='UNVERIFIED'):
        normalize(75000,spec)


@pytest.mark.parametrize('change', [{'price':0},{'price':float('inf')},{'price':float('nan')},{'low':999999},{'volume':-1},{'unit':'gram'},{'currency':'USD'},{'expiry':'2026-11'},{'trading_date':'2026-02-30'},{'ingested_at':'2020-01-01T00:00:00Z'}])
def test_invalid_csv_values(change):
    specs,rows=fixtures(); result=validate_csv(csv_text([{**rows[0],**change}]),specs)
    assert not result['accepted'] and result['rows']==[] and result['errors']


def test_csv_duplicates_missing_calendar_and_schema():
    specs,rows=fixtures(); row=rows[0]
    assert not validate_csv(csv_text([row,row]),specs)['accepted']
    assert not validate_csv(csv_text([row]),specs,existing={(row['contract_id'],row['trading_date'])})['accepted']
    assert not validate_csv(csv_text([row]),specs,expected_dates=['2026-09-02'])['accepted']
    assert not validate_csv(csv_text([row]),specs,expected_dates=['2026-09-01','2026-09-02'])['accepted']
    assert validate_csv(csv_text(rows[:4]),specs,expected_dates=[r['trading_date'] for r in rows[:4]])['accepted']
    # A deliberately supplied calendar can include special sessions; weekdays are never assumed.
    holiday={**row,'trading_date':'2026-08-30'}
    assert validate_csv(csv_text([holiday]),specs,expected_dates=['2026-08-30'])['accepted']
    assert not validate_csv(csv_text([]),specs)['accepted']
    with pytest.raises(ValueError,match='schema'):
        validate_csv('symbol,month,price\nGOLDM,Nov,70000',specs)
    with pytest.raises(ValueError,match='schema'):
        validate_csv(csv_text([row]).replace('volume,','volume,volume,'),specs)


def test_stale_specs_and_unusual_price_review():
    specs,rows=fixtures()
    with pytest.raises(ValueError,match='Stale'):
        validate_price(rows[0],{**specs[0],'valid_to':'2026-08-31'})
    result=validate_csv(csv_text([{**rows[0],'price':1e12}]),specs)
    assert result['accepted'] and result['warnings']  # Extreme finite settlement is flagged, never silently clipped.


def test_pair_prior_only_future_late_and_reversed_sign():
    specs,rows,req=example(); pair=pair_history(specs,rows,req)
    changed=copy.deepcopy(rows); changed[0][-1]['price']*=10
    after=pair_history(specs,changed,req)
    assert pair['history'][:-1]==after['history'][:-1]
    assert pair['history'][-1]['baseline']==after['history'][-1]['baseline']
    late=copy.deepcopy(rows)
    for leg in late:
        leg[0]['available_at']='2026-10-23T17:00:00Z'
    late_result=pair_history(specs,late,req)
    # Late old observation cannot alter a decision preceding its availability.
    trimmed=pair_history(specs,[leg[1:] for leg in rows],req)
    assert late_result['history'][1:-1]==trimmed['history'][:-1]
    reverse=pair_history(specs[::-1],rows[::-1],req)
    for a,b in zip(pair['history'],reverse['history']):
        assert a['raw_pair_spread']==pytest.approx(-b['raw_pair_spread'])
        if a['z_score'] is not None:
            assert a['z_score']==pytest.approx(-b['z_score'])
            assert a['status']==b['status']


def test_signal_flat_insufficient_missing_stale_and_threshold():
    specs,rows,req=example()
    flat=copy.deepcopy(rows)
    for leg in flat:
        for row in leg:
            row['price']=75000 if row['symbol']=='GOLDTEN' else 60000
    pair=pair_history(specs,flat,req)
    assert pair['latest']['status']=='NO_SIGNAL' and pair['latest']['z_score'] is None
    assert pair_history(specs,[leg[:4] for leg in rows],req)['latest']['status']=='REJECTED'  # stale at final cutoff
    assert pair['history'][0]['status']=='INSUFFICIENT_DATA'
    missing=pair_history(specs,[rows[0],rows[1][:-1]],req)
    assert missing['quality']['missing_dates'] and missing['latest']['status']=='REJECTED'
    pair=pair_history(specs,rows,req); z=abs(pair['latest']['z_score'])
    boundary=pair_history(specs,rows,req.model_copy(update={'entry_z':z}))
    above=pair_history(specs,rows,req.model_copy(update={'entry_z':z+1e-6}))
    assert boundary['latest']['status']=='INVESTIGATE' and above['latest']['status']=='NO_SIGNAL'
    assert pair['alignment']=='CALENDAR_BASIS_DIFFERENCE'
    assert pair['spec_a']['expiry']!=pair['spec_b']['expiry']
    duplicate=[rows[0]+[rows[0][0]],rows[1]]
    with pytest.raises(ValueError,match='Duplicate'):
        pair_history(specs,duplicate,req)


def test_manual_anomaly_change_explanation_gate():
    specs,rows,req=example(0); normal=pair_history(specs,rows,req)['latest']
    specs,rows,req=example(140); anomaly=pair_history(specs,rows,req)['latest']
    assert normal['status']=='NO_SIGNAL'
    assert anomaly['status']=='INVESTIGATE'
    assert normal['reason']!=anomaly['reason']


def test_replay_accepted_rejected_and_no_trade():
    specs,rows,req=example(); pair=pair_history(specs,rows,req)
    run=simulate(pair,req)
    assert run==simulate(pair,req)
    assert run['status']=='COMPLETE' and run['number_of_trades']>=1
    assert run['lots_a']==4 and run['lots_b']==5
    for trade in run['trades']:
        assert trade['entry_date']>trade['signal_date']
        assert trade['exit_date']>trade['exit_signal_date']
        assert trade['exit_date']<=run['safe_exit_date']
        gross=sum(l['direction']*(l['exit_quote']-l['entry_quote'])*l['grams']/s['quote_grams'] for l,s in zip(trade['legs'],specs))
        notionals=sum(l['entry_notional']+l['exit_notional'] for l in trade['legs'])
        assert trade['gross_pnl']==pytest.approx(gross)
        assert trade['fees']==pytest.approx(notionals*req.fee_bps/10000)
        assert trade['slippage']==pytest.approx(notionals*req.slippage_bps/10000)
        assert trade['net_pnl']==pytest.approx(gross-trade['fees']-trade['slippage'])
    assert run['equity_curve'][-1]['equity']==pytest.approx(req.initial_capital+run['net_pnl'])
    rejected=simulate(pair,req.model_copy(update={'allow_calendar':False}))
    assert rejected['number_of_trades']==0 and any('Calendar mismatch' in r['reason'] for r in rejected['rejections'])
    no_req=req.model_copy(update={'entry_z':100})
    no=simulate(pair_history(specs,rows,no_req),no_req)
    assert no['number_of_trades']==0 and no['net_pnl']==0


def test_replay_missing_fill_liquidity_and_no_same_close():
    specs,rows,req=example(); pair=pair_history(specs,rows,req); run=simulate(pair,req)
    entry=run['trades'][0]['entry_date']
    missing=copy.deepcopy(rows); missing[1]=[r for r in missing[1] if r['trading_date']!=entry]
    result=simulate(pair_history(specs,missing,req),req)
    assert any('Missing next dated' in r['reason'] for r in result['rejections'])
    illiquid=req.model_copy(update={'max_participation':.00001})
    rejected=simulate(pair,illiquid)
    assert not rejected['trades'] and any('participation' in r['reason'] for r in rejected['rejections'])
    # Delayed publication means the next day's close already happened: no historical fill.
    delayed=copy.deepcopy(pair)
    signal_date=run['trades'][0]['signal_date']
    for event in delayed['history']:
        if event['trading_date']==signal_date:
            event['decision_at']=entry+'T18:00:00Z'
    rejected=simulate(delayed,req)
    assert any('strictly after' in r['reason'] for r in rejected['rejections'])


def test_safe_exit_missing_marks_and_unresolved_position():
    specs,rows,req=example(); pair=pair_history(specs,rows,req); run=simulate(pair,req)
    first=run['trades'][0]
    # Remove every potential exit mark after entry. No forced end-of-series same-close liquidation.
    truncated=copy.deepcopy(pair)
    truncated['history']=[e for e in pair['history'] if e['trading_date']<=first['entry_date']]
    result=simulate(truncated,req)
    assert result['open_position'] and result['net_pnl'] is None and result['status']=='INCOMPLETE'
    early=copy.deepcopy(pair)
    early['spec_a']['safe_exit_date']=first['entry_date']
    early['spec_b']['safe_exit_date']=first['entry_date']
    result=simulate(early,req)
    assert not result['trades'] and result['rejections']


def test_backtest_api_storage_validation_and_real_block(tmp_path):
    with TestClient(create_app(tmp_path/'demo.sqlite3')) as client:
        specs,rows,req=example()
        response=client.post('/backtest',json=req.model_dump())
        assert response.status_code==200
        result=response.json()
        assert result['number_of_trades']>0
        assert client.post('/api/backtest',json=req.model_dump()).json()==result
        with connection(tmp_path/'demo.sqlite3') as db:
            assert db.execute('SELECT count(*) FROM backtest_runs').fetchone()[0]==1
            assert db.execute('SELECT count(*) FROM trades').fetchone()[0]==result['number_of_trades']
        assert client.post('/api/pair',json=PairRequest(**{k:v for k,v in req.model_dump().items() if k in PairRequest.model_fields}).model_dump()).status_code==200
        assert client.post('/backtest',json={**req.model_dump(),'dataset':'real'}).status_code==404
        assert client.post('/backtest',json={**req.model_dump(),'exit_z':5}).status_code==422
        assert client.post('/backtest',json={**req.model_dump(),'fee_bps':-1}).status_code==422
        invalid=client.post('/api/ingest',json={'csv_text':csv_text([rows[0][0]]),'as_of':DEFAULT_AS_OF}).json()
        assert not invalid['accepted'] and invalid['inserted']==0


def test_replay_prefix_does_not_use_future_quotes_or_liquidity():
    specs,rows,req=example()
    pair=pair_history(specs,rows,req); original=simulate(pair,req)
    first=original['trades'][0]
    changed=copy.deepcopy(rows)
    for leg in changed:
        for row in leg:
            if row['trading_date']>first['exit_date']:
                row['price']*=2; row['volume']=0
    later=simulate(pair_history(specs,changed,req),req)
    assert later['trades'][0]==first
    assert [e for e in later['equity_curve'] if e['trading_date']<=first['exit_date']]==[e for e in original['equity_curve'] if e['trading_date']<=first['exit_date']]


def test_independent_two_leg_pnl_cost_and_sensitivity_arithmetic():
    specs,rows,req=example()
    pair=pair_history(specs,rows,req)
    events=copy.deepcopy(pair['history'][:3])
    for i,e in enumerate(events):
        e.update(status='INVESTIGATE' if i==0 else 'NO_SIGNAL',z_score=3 if i==0 else 0,quality_reasons=[])
        e['a']['price']=[75000,75100,75000][i]
        e['b']['price']=[60000,60000,60080][i]
    pair['history']=events
    result=simulate(pair,req)
    trade=result['trades'][0]
    # Short 4 ten-gram lots earns 4*100=400; long 5 eight-gram lots earns 5*80=400.
    # Turnover: 300400 + 300000 + 300000 + 300400 = 1,200,800 INR.
    assert trade['gross_pnl']==800
    assert trade['fees']==pytest.approx(600.4)
    assert trade['slippage']==pytest.approx(1200.8)
    assert trade['net_pnl']==pytest.approx(-1001.2)
    assert trade['directional_pnl_per_1_inr_999_g']==0


def test_no_entry_after_tender_or_unavailable_spec():
    specs,rows,req=example()
    specs[0]['valid_to']='2026-09-15'
    pair=pair_history(specs,rows,req)
    assert pair['latest']['status']=='REJECTED'
    assert 'Stale' in pair['latest']['reason']
    result=simulate(pair,req)
    assert not result['trades']


def test_ingestion_atomicity_and_derived_provenance(tmp_path):
    specs,prices=fixtures()
    row={**prices[0],'trading_date':'2026-08-31','observed_at':'2026-08-31T16:00:00Z',
         'available_at':'2026-08-31T16:05:00Z','ingested_at':'2026-08-31T16:06:00Z'}
    with TestClient(create_app(tmp_path/'demo.sqlite3')) as client:
        bad={**row,'contract_id':'unknown'}
        response=client.post('/api/ingest',json={'csv_text':csv_text([row,bad]),'as_of':DEFAULT_AS_OF,'dry_run':False}).json()
        assert not response['accepted'] and response['inserted']==0
        assert client.get('/api/health').json()['observations']==312
        response=client.post('/api/ingest',json={'csv_text':csv_text([row]),'as_of':DEFAULT_AS_OF,'dry_run':False}).json()
        assert response['inserted']==1
        derived=response['normalized_observations'][0]
        assert derived['original_quote']==row['price']
        assert derived['normalized_999_per_g']==normalize(row['price'],specs[0])
        assert derived['spec_version']==row['spec_version'] and derived['source']==row['source']
        assert client.get('/api/health').json()['observations']==313
        evidence=client.get('/api/spec-evidence').json()
        assert not evidence['live_analytics_enabled']
        assert all(s['operational_status']=='UNVERIFIED' for s in evidence['specifications'])
