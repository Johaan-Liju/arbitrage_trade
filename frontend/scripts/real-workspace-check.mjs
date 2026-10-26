import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto('http://127.0.0.1:3000/');
  await expect(page.getByText('API: Connected', { exact: false })).toBeVisible();
  await expect(page.getByTestId('watchlist').locator('tbody tr')).toHaveCount(4);
  for (const symbol of ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']) {
    await page.getByLabel('Symbol', { exact: true }).selectOption(symbol);
    await expect(page.getByTestId('selected-contract').getByRole('heading', { level: 2 })).toContainText(symbol);
    await expect(page.getByRole('img', { name: /price history/ })).toBeVisible();
    await expect(page.getByTestId('selected-contract')).not.toContainText('NaN');
  }
  const remove = page.getByRole('button', { name: /^Remove GOLDPETAL/ });
  await remove.click();
  await expect(page.getByTestId('watchlist').locator('tbody tr')).toHaveCount(3);
  await page.getByRole('button', { name: 'Add selected contract' }).click();
  await expect(page.getByTestId('watchlist').locator('tbody tr')).toHaveCount(4);
  await page.getByRole('button', { name: 'Refresh data', exact: true }).click();
  await expect(page.getByTestId('selected-contract')).toBeVisible();
  await page.goto('http://127.0.0.1:3000/?asOf=2026-10-23T18:00:00Z');
  await expect(page.getByText('No contracts are available in this dataset at the cutoff.', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Use current time' }).click();
  await expect(page.getByTestId('selected-contract')).toBeVisible();
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  await page.getByRole('navigation').getByRole('link', { name: 'Alerts' }).click();
  await expect(page.getByTestId('model-evidence')).toContainText('4 real contracts available');
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  await expect(page.getByTestId('scan-result')).toContainText('UNVERIFIED');
  await expect(page.getByTestId('no-alerts')).toBeVisible();
  await page.getByRole('button', { name: 'Scan at cutoff', exact: true }).click();
  await expect(page.getByTestId('notification')).toContainText('already evaluated');
  await page.reload();
  await expect(page.getByTestId('scan-result')).toContainText('UNVERIFIED');
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  assert.deepEqual(errors, []);
  console.log('PASS: API/proxy, four selectors/charts, watchlist remove/add, refresh, historical cutoff/current recovery, persisted alert session/scan/dedup/history, mobile, no page errors');
} finally { await browser.close(); }
