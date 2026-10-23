import assert from 'node:assert/strict';
import { createServer } from '../src/server.js';

const server = createServer();
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const base = `http://127.0.0.1:${server.address().port}`;
try {
  const response = await fetch(`${base}/api/health`);
  assert.equal(response.status, 200);
  const health = await response.json();
  assert.equal(health.status, 'ok');
  console.log(`GET /api/health -> ${response.status} ${JSON.stringify(health)}`);
  const page = await fetch(base);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /SYNTHETIC DATA ONLY/);
  console.log('GET / -> 200; synthetic label present');
  const snapshot = await fetch(`${base}/api/snapshot?asOf=2026-10-21T16:01:00Z`);
  assert.equal(snapshot.status, 200);
  const data = await snapshot.json();
  assert.equal(data.indicator.count, 2);
  assert.equal(data.indicator.value, 2606);
  console.log(`GET /api/snapshot (historical cutoff) -> 200 ${JSON.stringify(data.indicator)}`);
  const real = await fetch(`${base}/api/snapshot?dataset=real`);
  assert.equal(real.status, 404);
  console.log('GET /api/snapshot?dataset=real -> 404; no synthetic fallback');
} finally {
  await new Promise(resolve => server.close(resolve));
}
