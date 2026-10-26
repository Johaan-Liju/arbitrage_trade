import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: 'msedge', headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:3000/');
  const panel = page.getByTestId('real-source-records');
  for (const symbol of ['GOLDM', 'GOLDTEN', 'GOLDGUINEA', 'GOLDPETAL']) {
    await expect(panel.getByRole('heading', { name: symbol, exact: true })).toBeVisible();
  }
  await expect(page.getByLabel('Dataset', { exact: true }).locator('option')).toHaveCount(1);
  await expect(panel.getByText('Terms unverified', { exact: true })).toHaveCount(4);
  await expect(panel).toContainText('predictions and backtests remain unavailable');
  const response = await page.request.get('http://127.0.0.1:8000/api/sources');
  const data = await response.json();
  assert.equal(data.sources.reduce((count, s) => count + s.rows.length, 0), 80);
  assert.equal(data.model_ready, false);
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await page.goto('http://127.0.0.1:3000/?asOf=2026-10-23T18:00:00Z');
  await expect(panel).toContainText('No collected source records available at this cutoff');
  await expect(panel.getByRole('heading', { name: 'GOLDM', exact: true })).toHaveCount(0);
  assert.deepEqual(errors, []);
  console.log('PASS: four real sources, 80 records, real-only selector, blocked model disclosure, mobile width, point-in-time source exclusion, no page errors');
} finally {
  await browser.close();
}
