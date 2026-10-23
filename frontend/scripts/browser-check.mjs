import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const errors = [];
const reports = [];
try {
  const context = await browser.newContext({ viewport: { width: 1512, height: 1100 } });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  const loaded = () => page.getByRole('status').filter({ hasText: 'API snapshot' }).waitFor();
  await page.goto('http://127.0.0.1:3000');
  await loaded();
  await expect(page.getByText('SYNTHETIC DATA', { exact: true })).toBeVisible();
  assert.equal(await page.locator('#contract option').count(), 8);
  for (const [symbol, expiry] of [['GOLDTEN', '2026-11-24'], ['GOLDGUINEA', '2026-11-27'], ['GOLDPETAL', '2026-11-30'], ['GOLDM', '2026-11-20']]) {
    const id = `${symbol}:${expiry}:demo-v1`;
    const received = page.waitForResponse(r => r.url().includes('/api/research?') && r.url().includes(symbol) && r.status() === 200);
    await page.selectOption('#contract', id);
    const response = await received;
    const data = await response.json();
    await loaded();
    assert.equal(data.spec.contract_id, id);
    assert.equal(data.dataset, 'synthetic');
    assert.equal(data.prices.length, 39);
    await expect(page.getByRole('status')).toContainText(symbol);
    const price = `₹${data.latest.price.toLocaleString('en-IN', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    await expect(page.getByText(price, { exact: true }).first()).toBeVisible();
    reports.push(`${symbol}: HTTP 200, 39 observations, API latest price ${price} visible`);
  }
  await mkdir('../artifacts', { recursive: true });
  await page.screenshot({ path: '../artifacts/dashboard-desktop.png', fullPage: true });
  for (const [name, heading] of [['Compare', 'Contract comparison'], ['Signals', 'A transparent research rule'], ['Backtest', 'Replay ledger']]) {
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name }).click();
    await loaded();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    assert.equal(await page.locator('#contract').inputValue(), 'GOLDM:2026-11-20:demo-v1');
    await page.screenshot({ path: `../artifacts/${name.toLowerCase()}-desktop.png`, fullPage: true });
    reports.push(`${name}: navigation and API-backed view passed`);
  }
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Gold, in context.', exact: true })).toBeVisible();
  await loaded();
  await page.getByRole('button', { name: 'Apply cutoff' }).click();
  await expect(page.getByRole('heading', { name: 'Price history', exact: false })).toBeVisible();
  reports.push('Applying the unchanged cutoff preserves the current result');
  await page.fill('#asof', '2026-08-31T18:00');
  await page.getByRole('button', { name: 'Apply cutoff' }).click();
  await expect(page.getByRole('heading', { name: 'No observations at this cutoff' })).toBeVisible();
  reports.push('Empty state: no future records displayed at 2026-08-31 cutoff');
  await page.route('**/api/research?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Browser test: API unavailable' }) }));
  await page.fill('#asof', '2026-10-23T18:00');
  await page.getByRole('button', { name: 'Apply cutoff' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Browser test: API unavailable');
  await expect(page.getByRole('heading', { name: 'Price history', exact: false })).toHaveCount(0);
  await page.unroute('**/api/research?*');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await loaded();
  reports.push('Error state: failed API clears stale data; Retry restores actual response');
  await page.route('**/api/research?*', async route => { await new Promise(resolve => setTimeout(resolve, 900)); await route.continue(); });
  await page.selectOption('#contract', 'GOLDTEN:2026-12-22:demo-v1');
  await expect(page.getByLabel('Loading research', { exact: true })).toBeVisible();
  await loaded();
  await page.unroute('**/api/research?*');
  reports.push('Loading state visible while research request is pending');
  await page.locator('details > summary').click();
  await expect(page.getByTestId('api-response')).toContainText('GOLDTEN:2026-12-22:demo-v1');
  await page.locator('details > summary').click();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('navigation', { name: 'Mobile navigation' })).toBeVisible();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'Mobile page must not overflow horizontally');
  await page.screenshot({ path: '../artifacts/dashboard-mobile.png', fullPage: true });
  reports.push('Mobile 390px: navigation visible, no page-level horizontal overflow');
  assert.deepEqual(errors, [], 'Browser must have no uncaught JavaScript errors');
  reports.push('No uncaught browser JavaScript errors');
  await writeFile('../artifacts/browser-results.json', JSON.stringify(reports, null, 2));
  for (const report of reports) console.log(`PASS ${report}`);
} finally { await browser.close(); }
