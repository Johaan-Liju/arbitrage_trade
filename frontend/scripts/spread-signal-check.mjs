import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';

const base = process.env.GOLDLENS_TEST_URL || 'http://127.0.0.1:3000';
const api = process.env.GOLDLENS_TEST_API;
const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  if (api) await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    await route.fulfill({ response: await route.fetch({ url: `${api}${url.pathname}${url.search}` }) });
  });
  const loaded = page.waitForResponse(r => r.url().endsWith('/api/pair') && r.status() === 200);
  await page.goto(`${base}/signals`);
  const initial = await (await loaded).json();
  await expect(page.getByText(/The price difference is A minus B/)).toBeVisible();
  await expect(page.getByText('Prior sample std / INR/g', { exact: true })).toBeVisible();
  await expect(page.getByText('Prior sample count', { exact: true })).toBeVisible();
  await expect(page.getByTestId('signal-reason')).toHaveText(initial.latest.reason);
  await page.getByText(/Signal settings/).click();
  for (const [label, value] of [['Lookback observations', '7'], ['Minimum prior observations', '3'], ['Investigate |z| threshold', '100']]) {
    const response = page.waitForResponse(r => r.url().endsWith('/api/pair') && r.status() === 200);
    await page.getByLabel(label, { exact: true }).fill(value);
    const body = await (await response).json();
    await expect(page.getByTestId('signal-reason')).toHaveText(body.latest.reason);
    assert.ok(['Investigate', 'No signal', 'Insufficient data'].includes(body.status));
    assert.ok(body.latest.sample_count <= body.method.lookback);
  }
  await expect(page.getByText('No signal', { exact: true }).first()).toBeVisible();
  assert.deepEqual(errors, []);
  console.log('PASS: left-minus-right direction, prior std/count, API-backed lookback/minimum/threshold controls, exact statuses, no browser errors');
} finally {
  await browser.close();
}
