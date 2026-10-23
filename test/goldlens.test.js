import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { snapshot, validatePrice } from '../src/domain.js';
import { createServer } from '../src/server.js';
const load = path => JSON.parse(readFileSync(new URL(path, import.meta.url)));
const specs = load('../data/synthetic/contracts.v1.json');
const rows = load('../data/synthetic/prices.json');
test('fixture has explicit identity and version', () => {
  rows.forEach(row => assert.equal(validatePrice(row, specs), row));
  for (const key of ['dataset', 'symbol', 'expiry', 'specVersion', 'tradingDate', 'source']) {
    const row = { ...rows[0] }; delete row[key];
    assert.throws(() => validatePrice(row, specs));
  }
});
test('reject invalid dates, specs, amounts and chronology', () => {
  for (const change of [{ expiry: '2026-12' }, { tradingDate: '2026-02-30' }, { specVersion: 'v999' }, { currency: 'INR' }, { price: -1 }, { price: Infinity }, { availableAt: '2026-10-19T00:00:00Z' }]) assert.throws(() => validatePrice({ ...rows[0], ...change }, specs));
});
test('as-of mean excludes future observations and late arrivals', () => {
  const late = { ...rows[0], price: 9999, availableAt: '2026-10-23T00:00:00Z' };
  const result = snapshot([...rows, late], specs, specs[0], '2026-10-21T16:01:00Z');
  assert.equal(result.indicator.count, 2); assert.equal(result.indicator.value, 2606);
  assert.equal(snapshot(rows, specs, specs[0], '2026-10-20T16:00:00Z').indicator.value, null);
  assert.throws(() => snapshot(rows, specs, specs[0], '2025-12-31T00:00:00Z'));
});
test('partition real data and other exact expiries from synthetic indicator', () => {
  const realSpec = { ...specs[0], dataset: 'real' };
  const otherSpec = { ...specs[0], expiry: '2026-12-19' };
  const mixed = [...rows, { ...rows[0], dataset: 'real', price: 5000 }, { ...rows[0], expiry: otherSpec.expiry, price: 6000 }];
  const result = snapshot(mixed, [...specs, realSpec, otherSpec], specs[0], '2026-10-22T16:01:00Z');
  assert.equal(result.indicator.count, 3); assert.equal(result.indicator.value, 2606);
});
test('HTTP health, dashboard, assets, cutoff and failure boundaries', async () => {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const base = `http://127.0.0.1:${server.address().port}`;
  try {
    const health = await fetch(`${base}/api/health`);
    assert.equal(health.status, 200); assert.equal((await health.json()).status, 'ok');
    const home = await fetch(base); assert.equal(home.status, 200); assert.match(await home.text(), /SYNTHETIC DATA ONLY/);
    for (const path of ['/app.js', '/style.css']) assert.equal((await fetch(base + path)).status, 200);
    const result = await (await fetch(`${base}/api/snapshot?asOf=2026-10-21T16:01:00Z`)).json();
    assert.equal(result.indicator.count, 2);
    assert.equal((await fetch(`${base}/api/snapshot?dataset=real`)).status, 404);
    assert.equal((await fetch(`${base}/api/snapshot?asOf=invalid`)).status, 400);
    assert.equal((await fetch(`${base}/unknown`)).status, 404);
    for (const path of ['/constructor', '/toString', '/__proto__']) assert.equal((await fetch(base + path)).status, 404);
    assert.equal((await fetch(`${base}/api/health`)).status, 200);
    assert.equal((await fetch(`${base}/api/health`, { method: 'POST' })).status, 405);
  } finally { await new Promise(resolve => server.close(resolve)); }
});
