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
    const id = `${symbol}:${expiry}:demo-v3`;
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
  await expect(page.getByRole('heading', { name: 'Recorded prices', exact: true })).not.toBeVisible();
  await page.getByText('All recorded prices / dates and sources', { exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Recorded prices', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'View all observations' }).click();
  assert.equal(await page.locator('tbody tr').count(), 39);
  await page.getByText('All recorded prices / dates and sources', { exact: true }).click();
  await page.getByText('Terms explained', { exact: true }).click();
  await expect(page.getByText('The number of contracts still open, rather than closed or settled.', { exact: true })).toBeVisible();
  await page.getByText('Terms explained', { exact: true }).click();
  reports.push('Plain-language navigation, expandable records and glossary work');
  const chartPrices = (await (await page.request.get('http://127.0.0.1:3000/api/research?contract_id=GOLDM%3A2026-11-20%3Ademo-v1&as_of=2026-10-23T18%3A00%3A00Z&dataset=synthetic')).json()).prices;
  async function checkChartHover() {
    const hitArea = page.getByTestId('price-chart-hit-area');
    await hitArea.scrollIntoViewIfNeeded();
    const box = await hitArea.boundingBox();
    const readout = page.getByTestId('price-chart-readout');
    // Sweep away from the line: the plot must stay interactive between markers.
    for (let i = 0; i < chartPrices.length; i++) {
      const px = box.x + Math.max(0.5, Math.min(box.width - 0.5, box.width * i / (chartPrices.length - 1)));
      await page.mouse.move(px, box.y + 4);
      await expect(readout).toContainText(chartPrices[i].trading_date);
      await expect(readout).toContainText(chartPrices[i].price.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
    }
    // Repeated vertical movement at one date must not clear or change selection.
    const middle = Math.floor(chartPrices.length / 2);
    for (const offset of [0.1, 0.9, 0.2, 0.8]) {
      await page.mouse.move(box.x + box.width * middle / (chartPrices.length - 1), box.y + box.height * offset);
      await expect(readout).toContainText(chartPrices[middle].trading_date);
    }
    await page.mouse.move(box.x + box.width + 10, box.y + 4);
    await expect(readout).toHaveText('Move across the chart to inspect a price');
  }
  await checkChartHover();
  await page.setViewportSize({ width: 390, height: 844 });
  await checkChartHover();
  await page.setViewportSize({ width: 1512, height: 1100 });
  reports.push('Chart hover: all 39 dates/prices, stable vertical tracking and leave reset at desktop and mobile widths');
  await mkdir('../artifacts', { recursive: true });
  await page.screenshot({ path: '../artifacts/dashboard-desktop.png', fullPage: true });
<<<<<<< HEAD
  for (const [name, heading] of [['Compare prices', 'Prices side by side'], ['Price signals', 'How to read these signals'], ['Signal history', 'Past signals']]) {
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name }).click();
    await loaded();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    assert.equal(await page.locator('#contract').inputValue(), 'GOLDM:2026-11-20:demo-v1');
    await page.screenshot({ path: `../artifacts/${name.toLowerCase().replaceAll(' ', '-')}-desktop.png`, fullPage: true });
    reports.push(`${name}: navigation and API-backed view passed`);
  }
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Prices Follow one contract' }).click();
  await expect(page.getByRole('heading', { name: 'Follow a gold contract', exact: true })).toBeVisible();
=======
  for (const [name, heading] of [['Compare', 'Contract comparison'], ['Signals', 'A transparent research rule'], ['Backtest', 'Hypothetical paired settlement replay']]) {
    await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name }).click();
    await loaded();
    await expect(page.getByRole('heading', { name: heading, exact: true })).toBeVisible();
    assert.equal(await page.locator('#contract').inputValue(), 'GOLDM:2026-11-20:demo-v3');
    await page.screenshot({ path: `../artifacts/${name.toLowerCase()}-desktop.png`, fullPage: true });
    reports.push(`${name}: navigation and API-backed view passed`);
  }
  await page.selectOption('#contract', 'GOLDTEN:2026-11-24:demo-v3');
  await loaded();
  await expect(page.getByText('CALENDAR_BASIS_DIFFERENCE', { exact: true })).toBeVisible();
  await expect(page.locator('#pair-contract')).toHaveValue('GOLDGUINEA:2026-11-27:demo-v3');
  let replayResponse = page.waitForResponse(r => r.url().endsWith('/api/backtest') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  let replay = await (await replayResponse).json();
  assert.equal(replay.number_of_trades, 0);
  assert.ok(replay.rejections.some(r => r.reason.includes('Calendar mismatch')));
  await expect(page.getByRole('heading', { name: 'Rejected orders and decisions' })).toBeVisible();
  await page.getByRole('checkbox').check();
  replayResponse = page.waitForResponse(r => r.url().endsWith('/api/backtest') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  replay = await (await replayResponse).json();
  assert.equal(replay.number_of_trades, 1);
  assert.equal(replay.status, 'COMPLETE');
  await expect(page.getByRole('heading', { name: 'Trade ledger' })).toBeVisible();
  await expect(page.getByText('Trade 1', { exact: false }).first()).toBeVisible();
  await page.screenshot({ path: '../artifacts/backtest-accepted-desktop.png', fullPage: true });
  reports.push(`Paired replay: calendar rejection then accepted trade; backend net INR ${replay.net_pnl.toFixed(2)}`);
  await page.getByLabel('Entry |z| threshold').fill('100');
  await expect(page.getByRole('button', { name: 'Run simulation', exact: true })).toBeVisible();
  replayResponse = page.waitForResponse(r => r.url().endsWith('/api/backtest') && r.request().method() === 'POST');
  await page.getByRole('button', { name: 'Run simulation', exact: true }).click();
  replay = await (await replayResponse).json();
  assert.equal(replay.number_of_trades, 0);
  assert.equal(replay.net_pnl, 0);
  reports.push('High-threshold no-trade simulation: zero trades, zero net P&L');
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Compare', exact: true }).click();
  await loaded();
  await expect(page.getByRole('img', { name: 'Normalized price history', exact: true })).toBeVisible();
  await expect(page.getByText('INVESTIGATE', { exact: true }).first()).toBeVisible();
  await page.screenshot({ path: '../artifacts/compare-pair-desktop.png', fullPage: true });
  await page.setViewportSize({ width: 390, height: 844 });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  await page.screenshot({ path: '../artifacts/compare-pair-mobile.png', fullPage: true });
  await page.setViewportSize({ width: 1512, height: 1100 });
  reports.push('Pair charts, anomaly explanation and mobile comparison layout visible');
  await page.getByRole('navigation', { name: 'Main navigation', exact: true }).getByRole('link', { name: 'Dashboard' }).click();
  await expect(page.getByRole('heading', { name: 'Gold, in context.', exact: true })).toBeVisible();
>>>>>>> 8ac8885badf893791b51a2b0017f2f2352f8c0e1
  await loaded();
  await page.getByText('Change research time', { exact: false }).click();
  await page.getByRole('button', { name: 'Apply time' }).click();
  await expect(page.getByRole('heading', { name: 'Price history', exact: false })).toBeVisible();
  reports.push('Applying the unchanged cutoff preserves the current result');
  await page.fill('#asof', '2026-08-31T18:00');
  await page.getByRole('button', { name: 'Apply time' }).click();
  await expect(page.getByRole('heading', { name: 'No prices available at this time' })).toBeVisible();
  reports.push('Empty state: no future records displayed at 2026-08-31 cutoff');
  await page.route('**/api/research?*', route => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'Browser test: API unavailable' }) }));
  await page.fill('#asof', '2026-10-23T18:00');
  await page.getByRole('button', { name: 'Apply time' }).click();
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Browser test: API unavailable');
  await expect(page.getByRole('heading', { name: 'Price history', exact: false })).toHaveCount(0);
  await page.unroute('**/api/research?*');
  await page.getByRole('button', { name: 'Retry connection' }).click();
  await loaded();
  reports.push('Error state: failed API clears stale data; Retry restores actual response');
  await page.route('**/api/research?*', async route => { await new Promise(resolve => setTimeout(resolve, 900)); await route.continue(); });
  await page.selectOption('#contract', 'GOLDTEN:2026-12-22:demo-v3');
  await expect(page.getByLabel('Loading research', { exact: true })).toBeVisible();
  await loaded();
  await page.unroute('**/api/research?*');
  reports.push('Loading state visible while research request is pending');
<<<<<<< HEAD
  await page.getByText('Technical details / API response', { exact: true }).click();
  await expect(page.getByTestId('api-response')).toContainText('GOLDTEN:2026-12-22:demo-v1');
  await page.getByText('Technical details / API response', { exact: true }).click();
=======
  await page.locator('details > summary').click();
  await expect(page.getByTestId('api-response')).toContainText('GOLDTEN:2026-12-22:demo-v3');
  await page.locator('details > summary').click();
>>>>>>> 8ac8885badf893791b51a2b0017f2f2352f8c0e1
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.getByRole('navigation', { name: 'Main navigation' })).toBeVisible();
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true, 'Mobile page must not overflow horizontally');
  await page.screenshot({ path: '../artifacts/dashboard-mobile.png', fullPage: true });
  reports.push('Mobile 390px: navigation visible, no page-level horizontal overflow');
  assert.deepEqual(errors, [], 'Browser must have no uncaught JavaScript errors');
  reports.push('No uncaught browser JavaScript errors');
  await writeFile('../artifacts/browser-results.json', JSON.stringify(reports, null, 2));
  for (const report of reports) console.log(`PASS ${report}`);
} finally { await browser.close(); }
