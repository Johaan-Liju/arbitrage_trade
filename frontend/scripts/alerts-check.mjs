import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const base = process.env.GOLDLENS_TEST_URL || 'http://127.0.0.1:3000';
const backend = process.env.GOLDLENS_TEST_API || base;
const signalAt = '2026-10-05T18:00:00Z';
const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
const reports = [], errors = [], mutations = [];
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (r.method() === 'POST') mutations.push(new URL(r.url()).pathname); });
  if (process.env.GOLDLENS_TEST_API) await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    await route.fulfill({ response: await route.fetch({ url: `${backend}${url.pathname}${url.search}` }) });
  });
  const main = page.getByRole('main');
  const notice = page.getByTestId('notification');
  await page.goto(`${base}/alerts?dataset=synthetic&asOf=${signalAt}`);
  await expect(page.getByTestId('model-evidence')).toBeVisible();
  await expect(page.getByTestId('dataset-banner')).toContainText('SYNTHETIC DATA');
  await expect(page.getByTestId('model-evidence')).toContainText('Calibration has not been evaluated');
  await expect(page.getByTestId('model-evidence')).toContainText('opportunity-v1');
  await expect(page.getByTestId('paper-alert')).toHaveCount(0);
  reports.push('Evaluation scope, version and uncalibrated probability disclosure shown before any session; no alerts invented');

  // The evaluated cost-filtered model abstains at this cutoff.
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  await expect(notice).toContainText('COST_FILTER');
  await expect(page.getByTestId('no-alerts')).toBeVisible();
  await expect(page.getByTestId('paper-alert')).toHaveCount(0);
  reports.push('Default evaluated model abstains with a stated reason and no notification');

  // Stricter threshold suppresses even the baseline comparator.
  await page.getByLabel('Policy', { exact: true }).selectOption('baseline');
  await page.getByLabel('Minimum absolute z').fill('100');
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  await expect(notice).toContainText('THRESHOLD');
  await expect(page.getByTestId('paper-alert')).toHaveCount(0);
  reports.push('Configurable minimum |z| suppresses a signal; new settings create a separate session');

  // Baseline comparator emits one paper alert with the full evidence set.
  await page.getByLabel('Minimum absolute z').fill('2.5');
  await page.getByLabel('Cooldown').fill('720');
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  await expect(notice).toContainText('1 new paper alert');
  const alert = page.getByTestId('paper-alert');
  await expect(alert).toHaveCount(1);
  await expect(alert).toContainText('GOLDTEN / GOLDGUINEA');
  await expect(alert).toContainText('2026-11-20');
  await expect(alert).toContainText(`${signalAt.replace('T', ' ').replace('Z', ' UTC')}`);
  await expect(alert).toContainText('5 common sessions after entry');
  await expect(alert).toContainText('Entry 2026-10-06 → Exit 2026-10-13');
  await expect(alert).toContainText('opportunity-v1');
  await expect(alert).toContainText('Source observations (22)');
  await expect(alert).toContainText('Estimated costs at signal time');
  for (const scenario of ['BASE', 'STRESS', 'SEVERE']) await expect(alert.getByRole('cell', { name: scenario, exact: true }).first()).toBeVisible();
  await expect(alert).toContainText('Liquidity & execution uncertainty');
  await expect(alert).toContainText('Settlement uncertainty');
  await expect(alert).toContainText('No probability is shown: calibration has not been evaluated');
  await expect(alert.getByTestId('paper-outcome')).toContainText('PENDING_ENTRY');
  const text = await main.innerText();
  assert.ok(!/\d\s?%\s*(probability|chance|likely)/i.test(text), 'no probability percentage may be displayed');
  assert.ok(!/guaranteed arbitrage/i.test(text.replace(/no [^.]*guaranteed arbitrage/ig, '')), 'must not describe signals as guaranteed arbitrage');
  reports.push('Alert shows contracts, exact expiry, signal time, horizon, model version, 22 observations, costs, liquidity/settlement uncertainty and pending outcome; no probability');

  // Read receipts.
  await expect(page.getByText('1 unread')).toBeVisible();
  await alert.getByRole('button', { name: 'Mark read' }).click();
  await expect(page.getByText('0 unread')).toBeVisible();

  // Repeating the same cutoff cannot duplicate the notification.
  await page.getByRole('button', { name: 'Scan at cutoff' }).click();
  await expect(notice).toContainText('already evaluated');
  await expect(alert).toHaveCount(1);
  reports.push('Read receipt persists; rescanning the same cutoff is idempotent');

  // A new cutoff with the same pair, direction and trading date is deduplicated.
  await page.getByLabel('Information cutoff (UTC)').fill('2026-10-05T18:01');
  await page.getByRole('button', { name: 'View cutoff' }).click();
  await expect(page.getByTestId('paper-alert')).toHaveCount(1);
  await page.getByRole('button', { name: 'Scan at cutoff' }).click();
  await expect(notice).toContainText('DEDUPLICATED');
  await expect(page.getByTestId('paper-alert')).toHaveCount(1);
  reports.push('Same pair, version, trading date and direction at a new cutoff is deduplicated');

  // Later cutoff matures the outcome without altering the frozen signal.
  const frozen = await alert.getByText('Source observations').innerText();
  await page.getByLabel('Information cutoff (UTC)').fill('2026-10-13T16:05');
  await page.getByRole('button', { name: 'View cutoff' }).click();
  await expect(page.getByTestId('paper-alert')).toHaveCount(1);
  await expect(page.getByTestId('paper-outcome')).toContainText('PENDING_ENTRY');
  await page.getByRole('button', { name: 'Scan at cutoff' }).click();
  await expect(notice).toContainText('No new notifications');
  await expect(page.getByTestId('paper-alert')).toHaveCount(1);
  await expect(page.getByTestId('paper-outcome')).toContainText('COMPLETE');
  await expect(page.getByTestId('paper-outcome')).toContainText('COST_SENSITIVE_POSITIVE');
  await expect(page.getByTestId('paper-outcome')).toContainText('no observed fills');
  assert.equal(await page.getByTestId('paper-alert').getByText('Source observations').innerText(), frozen);
  await page.getByTestId('paper-outcome').getByText(/Outcome history/).click();
  await expect(page.getByTestId('paper-outcome')).toContainText('PENDING_ENTRY');
  await expect(page.getByTestId('paper-outcome')).toContainText('COMPLETE');
  reports.push('Later scan records a completed paper outcome and keeps the earlier pending check; no repeat notification; frozen evidence unchanged');

  // Stale inputs suppress opportunity alerts.
  await page.getByLabel('Policy', { exact: true }).selectOption('baseline');
  await page.getByLabel('Information cutoff (UTC)').fill('2026-10-27T18:00');
  await page.getByRole('button', { name: 'View cutoff' }).click();
  await expect(page.getByTestId('model-evidence')).toBeVisible();
  await page.getByRole('button', { name: 'Start new paper session' }).click();
  await expect(notice).toContainText('STALE');
  await expect(page.getByTestId('scan-result')).toContainText('Inputs BLOCKED');
  reports.push('Stale inputs at a late cutoff are suppressed and shown as blocked');

  // Mobile layout.
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(`${base}/alerts?dataset=synthetic&asOf=2026-10-13T16:05:00Z`);
  await expect(page.getByTestId('model-evidence')).toBeVisible();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  assert.ok(overflow <= 1, `page overflows horizontally by ${overflow}px`);
  await mkdir('../artifacts', { recursive: true });
  await page.screenshot({ path: '../artifacts/alerts-mobile.png', fullPage: true });
  reports.push('Mobile 390px: no horizontal page overflow');

  // Real data: failure stays a failure, with no session creation or synthetic substitution.
  await page.setViewportSize({ width: 1440, height: 1000 });
  mutations.length = 0;
  const datasets = [];
  page.on('request', r => { if (/\/api\/alerts\//.test(r.url())) datasets.push(new URL(r.url()).searchParams.get('dataset')); });
  await page.goto(`${base}/alerts?dataset=real&asOf=${signalAt}`);
  await expect(main.getByRole('alert')).toContainText('DATASET_UNAVAILABLE');
  await expect(page.getByTestId('dataset-banner')).toContainText('IMPORTED REAL DATA');
  await expect(page.getByTestId('model-evidence')).toHaveCount(0);
  await expect(page.getByTestId('paper-alert')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Start new paper session' })).toHaveCount(0);
  assert.ok(datasets.length > 0 && datasets.every(d => d === 'real'));
  assert.deepEqual(mutations, []);
  reports.push('Missing real data blocks alerts with no synthetic request, session creation or notification');

  assert.deepEqual(errors, []);
  await page.unrouteAll({ behavior: 'wait' });
  await writeFile('../artifacts/alerts-results.json', JSON.stringify(reports, null, 2));
  for (const report of reports) console.log(`PASS ${report}`);
} finally { await browser.close(); }
