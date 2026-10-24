import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';

const browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || 'msedge', headless: true });
try {
  const page = await browser.newPage();
  const errors = [];
  const researchRequests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('request', r => { if (r.url().includes('/api/research?')) researchRequests.push(r.url()); });
  await page.goto('http://127.0.0.1:3000/compare?contract=GOLDM%3A2026-11-20%3Ademo-v1&asOf=2026-10-23T18%3A00%3A00Z&dataset=synthetic');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('older demo version');
  assert.equal(researchRequests.length, 0, 'Unavailable versions must not trigger repeated failing research requests');
  await expect(page.locator('#contract')).toHaveValue('GOLDM:2026-11-20:demo-v1');
  await page.getByRole('button', { name: 'Use an available contract' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'API snapshot' })).toBeVisible();
  await expect(page.locator('#contract')).toHaveValue('GOLDM:2026-11-20:demo-v4');
  assert.equal(new URL(page.url()).searchParams.get('contract'), 'GOLDM:2026-11-20:demo-v4');
  await expect(page.getByRole('heading', { name: 'Exact contract pair', exact: true })).toBeVisible();
  await expect(page.locator('#pair-contract option')).toHaveCount(3);
  await expect(page.getByRole('heading', { name: 'Quality checks', exact: true })).toBeVisible();
  await page.reload();
  await expect(page.getByRole('status').filter({ hasText: 'API snapshot' })).toBeVisible();
  await expect(page.getByRole('main').getByRole('alert')).toHaveCount(0);
  assert.deepEqual(errors, []);
  console.log('PASS old-version link explains unavailable selection without failing API requests; explicit selection updates URL; research and pair load; refresh preserves recovery; no browser errors');
} finally { await browser.close(); }
