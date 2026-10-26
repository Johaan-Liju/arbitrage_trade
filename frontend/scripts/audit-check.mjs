import { chromium, expect } from '@playwright/test';
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const base = process.env.GOLDLENS_TEST_URL || 'http://127.0.0.1:3000';
const api = process.env.GOLDLENS_TEST_API || base;
const browser = await chromium.launch({channel:'msedge',headless:true});
const reports = [], errors = [];
try {
  const page = await browser.newPage({viewport:{width:1440,height:1000}});
  page.on('pageerror', error => errors.push(error.message));
  await page.route('**/api/**', async route => {
    const url = new URL(route.request().url());
    await route.fulfill({response:await route.fetch({url:`${api}${url.pathname}${url.search}`})});
  });
  const paired = () => page.waitForResponse(r => r.url().endsWith('/api/pair') && r.status()===200);
  let response = paired();
  await page.goto(`${base}/signals?contract=GOLDTEN%3A2026-11-20%3Ademo-v4`);
  let pair = await (await response).json();
  assert.equal(pair.status,'Investigate');
  await expect(page.getByTestId('signal-reason')).toHaveText(pair.latest.reason);
  await expect(page.getByText('Investigate',{exact:true}).first()).toBeVisible();
  const options = await page.locator('#pair-contract option').evaluateAll(nodes => nodes.map(n => n.value));
  assert.ok(options.length>=2 && options.every(id => id.includes(':2026-11-20:')));
  assert.ok(!options.some(id => id.startsWith('GOLDTEN:')));
  await page.getByText(/Unavailable comparisons/).click();
  await expect(page.getByRole('heading',{name:'Unsupported pair comparisons'})).toBeVisible();
  await page.getByText(/Signal settings/).click();
  for (const key of ['a','b']) {
    const spec=pair[`spec_${key}`], row=pair.latest[key];
    assert.ok(Math.abs(Number(row.normalized_999_inr_per_gram)-row.price/Number(spec.quotation_grams)*999/Number(spec.quote_purity_per_mille))<1e-8);
  }
  reports.push('Contract-aware 999 normalization agrees with independent arithmetic; B options have exact matching expiry and distinct symbols; unsupported alternatives explained');
  response=paired();
  await page.selectOption('#pair-contract','GOLDM:2026-11-20:demo-v4');
  pair=await (await response).json();
  assert.equal(pair.spec_b.symbol,'GOLDM');
  assert.equal(pair.spec_b.lot_grams,100);
  assert.equal(pair.spec_b.quote_grams,10);
  for (const [label,value] of [['Lookback observations','7'],['Minimum prior observations','3'],['Investigate |z| threshold','100']]) {
    response=paired(); await page.getByLabel(label,{exact:true}).fill(value);
    pair=await (await response).json();
    await expect(page.getByTestId('signal-reason')).toHaveText(pair.latest.reason);
  }
  assert.equal(pair.status,'No signal');
  await expect(page.getByText('No signal',{exact:true}).first()).toBeVisible();
  reports.push('Pair selection and lookback/minimum/entry settings reach API; No signal renders with backend reason');
  await page.getByText('Change research time',{exact:false}).click();
  response=paired();
  await page.fill('#asof','2026-09-02T18:00');
  await page.getByRole('button',{name:'Apply time'}).click();
  pair=await (await response).json();
  assert.equal(pair.status,'Insufficient data');
  assert.ok(pair.history.every(e => e.decision_at<=pair.as_of && e.a.observed_at<=pair.as_of && e.b.available_at<=pair.as_of));
  await expect(page.getByText('Insufficient data',{exact:true}).first()).toBeVisible();
  assert.equal(new URL(page.url()).searchParams.get('asOf'),'2026-09-02T18:00:00Z');
  response=paired(); await page.reload(); pair=await (await response).json();
  assert.equal(pair.as_of,'2026-09-02T18:00:00Z');
  await page.getByText('Change research time',{exact:false}).click();
  reports.push('Early cutoff excludes future observations/publications and renders Insufficient data warm-up');
  response=paired(); await page.fill('#asof','2026-10-23T18:00');
  await page.getByRole('button',{name:'Apply time'}).click(); pair=await (await response).json();

  async function stickyAndHover(width,height) {
    await page.setViewportSize({width,height});
    const hit=page.getByTestId('pair-chart-hit-area').first(), readout=page.getByTestId('pair-chart-readout').first();
    await hit.scrollIntoViewIfNeeded();
    const banner=page.getByTestId('dataset-banner');
    await expect(banner).toContainText('SYNTHETIC DATA');
    const bannerBox=await banner.boundingBox(), box=await hit.boundingBox();
    assert.ok(Math.abs(bannerBox.y)<1 && bannerBox.height < height/4);
    assert.ok(box.y >= bannerBox.y+bannerBox.height,'Chart hit area must clear sticky disclosure');
    assert.equal(await banner.evaluate(el => getComputedStyle(el).position),'sticky');
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth<=innerWidth),true);
    const index=Math.round((pair.history.length-1)*.25), fraction=index/(pair.history.length-1);
    const x=box.x+box.width*fraction;
    assert.ok(x<width,'Test point lies in visible part of horizontally scrollable chart');
    for (const offset of [.1,.9,.2,.8,.5]) {
      await page.mouse.move(x,box.y+box.height*offset);
      await expect(readout).toContainText(pair.history[index].trading_date);
      const after=await hit.boundingBox();
      assert.ok(Math.abs(after.y-box.y)<1,'Hover must not move chart');
    }
    await page.mouse.move(box.x,box.y+box.height+8);
    await expect(readout).toHaveText('Move across the chart to inspect paired values');
    await page.evaluate(() => scrollTo(0,document.body.scrollHeight));
    assert.ok(Math.abs((await banner.boundingBox()).y)<1);
    await page.screenshot({path:`../artifacts/audit-sticky-${width}.png`,fullPage:false});
    reports.push(`Sticky opaque banner, clear chart interaction, no horizontal overflow and stable paired-chart hover at ${width}px`);
  }
  await mkdir('../artifacts',{recursive:true});
  await stickyAndHover(1440,1000);
  await stickyAndHover(390,844);

  await page.setViewportSize({width:1440,height:1000});
  await page.getByText(/Signal settings/).click();
  await page.route('**/api/pair',route => route.fulfill({status:503,contentType:'application/json',body:JSON.stringify({detail:'Audit: paired API unavailable'})}));
  await page.getByLabel('Lookback observations',{exact:true}).fill('8');
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Audit: paired API unavailable');
  await expect(page.getByTestId('signal-reason')).toHaveCount(0);
  await page.unroute('**/api/pair');
  response=paired(); await page.getByRole('button',{name:'Retry pair'}).click(); await response;
  await expect(page.getByTestId('signal-reason')).toBeVisible();
  await page.route('**/api/pair',async route => {await new Promise(resolve => setTimeout(resolve,800)); await route.fallback();});
  response=paired(); await page.getByLabel('Lookback observations',{exact:true}).fill('9');
  await expect(page.getByRole('status').filter({hasText:'Loading paired observations'})).toBeVisible(); await response;
  await page.unroute('**/api/pair');
  reports.push('Pair failure clears stale signal; retry recovers; pending pair request shows loading');
  const invalid=page.waitForResponse(r => r.url().endsWith('/api/pair') && r.status()===422);
  await page.getByLabel('Minimum prior observations',{exact:true}).fill('250'); await invalid;
  await expect(page.getByRole('main').getByRole('alert')).toContainText('Minimum observations exceeds lookback');
  await expect(page.getByTestId('signal-reason')).toHaveCount(0);
  response=paired(); await page.getByLabel('Minimum prior observations',{exact:true}).fill('5'); await response;
  await expect(page.getByTestId('signal-reason')).toBeVisible();
  reports.push('Invalid settings show readable API validation and clear stale signals; valid settings recover');

  // An empty catalog is a supported API result, not an indefinite loading state.
  await page.route('**/api/contracts?*',route => route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({contracts:[],default_as_of:'2026-10-23T18:00:00Z'})}));
  await page.goto(base);
  await expect(page.getByRole('heading',{name:'No prices available at this time'})).toBeVisible();
  await expect(page.getByLabel('Loading research',{exact:true})).toHaveCount(0);
  await expect(page.getByTestId('dataset-banner')).toContainText('SYNTHETIC DATA');
  reports.push('Empty contract catalog ends loading and retains synthetic disclosure');
  assert.deepEqual(errors,[]);
  await writeFile('../artifacts/audit-results.json',JSON.stringify(reports,null,2));
  for (const report of reports) console.log(`PASS ${report}`);
} finally {await browser.close();}
