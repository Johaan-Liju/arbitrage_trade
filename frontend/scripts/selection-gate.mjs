import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

// Uses an installed browser with an isolated temporary profile, never a personal session.
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
try {
  const page = await browser.newPage();
  await page.goto('http://127.0.0.1:3000');
  await page.locator('#contract option').nth(1).waitFor({ state: 'attached' });
<<<<<<< HEAD
  const id = 'GOLDPETAL:2026-11-30:demo-v3';
=======
  const id = 'GOLDPETAL:2026-11-20:demo-v4';
>>>>>>> 58455e0ad3016fd77becac210c1dd3a141d3a849
  const received = page.waitForResponse(r => r.url().includes('/api/research?') && r.url().includes('GOLDPETAL') && r.status() === 200);
  await page.selectOption('#contract', id);
  const response = await received;
  const data = await response.json();
  const inspector = page.getByText('Technical details / API response', { exact: true });
  if (await inspector.count()) await inspector.click();
  await page.getByTestId('api-response').filter({ hasText: id }).waitFor();
  assert.equal(data.spec.contract_id, id);
  assert.equal(data.dataset, 'synthetic');
  assert.equal(data.prices.length, 39);
  await mkdir('../artifacts', { recursive: true });
  await page.screenshot({ path: '../artifacts/selection-gate.png', fullPage: false });
  await writeFile('../artifacts/selection-gate-response.json', JSON.stringify(data, null, 2));
  console.log(`PASS browser selected ${id}; HTTP ${response.status()}; ${data.prices.length} API observations rendered`);
} finally { await browser.close(); }
