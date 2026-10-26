import { chromium, expect } from '@playwright/test';
import { mkdir } from 'node:fs/promises';
const base = process.env.GOLDLENS_TEST_URL, backend = process.env.GOLDLENS_TEST_API;
const out = '../artifacts/deck';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    await route.fulfill({ response: await route.fetch({ url: `${backend}${url.pathname}${url.search}` }) });
  });
  await page.goto(`${base}/?dataset=synthetic&asOf=2026-10-23T18:00:00Z`);
  await expect(page.getByTestId('selected-contract')).toBeVisible();
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}/monitor.png` });
  await page.goto(`${base}/alerts?dataset=synthetic&asOf=2026-10-05T18:00:00Z`);
  await expect(page.getByTestId('model-evidence')).toBeVisible();
  await page.screenshot({ path: `${out}/alerts-evidence.png` });
  await page.getByLabel('Policy', { exact: true }).selectOption('baseline');
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  const alert = page.getByTestId('paper-alert');
  await expect(alert).toHaveCount(1);
  await alert.scrollIntoViewIfNeeded();
  await alert.screenshot({ path: `${out}/alert-card.png` });
  console.log('captured');
} finally { await browser.close(); }
