// Synthetic, read-only browser checks; never connects to the application database.
// PLAYWRIGHT_MODULE may point to an installed Playwright package directory.
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const python = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'data/hotel_recommendations.json'), 'utf8')).destinations;
const slugs = ['palawan', 'vigan', 'cebu', 'siquijor', 'siargao', 'camiguin'];
const sizes = [[320, 568], [390, 844], [768, 1024], [1440, 900]];
const edgeCasesOnly = process.argv.includes('--edge-cases');
const captureScreenshots = !process.argv.includes('--no-screenshots');
const artifacts = path.join(root, '.impeccable/review/hotels');
fs.mkdirSync(artifacts, { recursive: true });
const server = spawn(python, ['tests/responsive_browser_server.py'], {
  cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
});
let serverErrors = '';
server.stderr.on('data', chunk => { serverErrors = (serverErrors + chunk).slice(-12000); });

async function settle(page, { javaScript = true } = {}) {
  if (!javaScript) {
    // Chromium disables frame callbacks in a JavaScript-disabled context.
    // Trigger native image loading synchronously, then poll from the driver.
    await page.locator('.hotel-recommendations').scrollIntoViewIfNeeded();
    await page.locator('img.hotel-image').evaluateAll(images => {
      images.forEach(image => { image.loading = 'eager'; });
    });
    const deadline = Date.now() + 10000;
    while (!await page.locator('img.hotel-image').evaluateAll(images => images.every(image => image.complete))) {
      assert.ok(Date.now() < deadline, 'No-JavaScript hotel images finish loading');
      await page.waitForTimeout(50);
    }
    return;
  }
  await page.evaluate(async () => {
    await document.fonts.ready;
    [...document.images].forEach(image => { image.loading = 'eager'; });
    await Promise.all([...document.images].map(image => image.decode().catch(() => {})));
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  });
}

async function assertFits(page, label) {
  const state = await page.evaluate(() => ({
    viewport: innerWidth,
    scroll: document.documentElement.scrollWidth,
    offenders: [...document.querySelectorAll('body *')].filter(node => {
      const box = node.getBoundingClientRect();
      return box.width > 0 && box.right > innerWidth + 1 && getComputedStyle(node).position !== 'absolute';
    }).map(node => node.className || node.tagName).slice(0, 8),
  }));
  assert.ok(state.scroll <= state.viewport, `${label}: horizontal overflow ${JSON.stringify(state)}`);
}

// Hotel destinations are fulfilled locally: test native new-tab navigation
// without contacting the property or making any booking request.
async function interceptHotelNavigation(context) {
  const officialUrls = new Set(Object.values(catalog).flat().map(hotel => new URL(hotel.url).href));
  await context.route(url => officialUrls.has(url.href), route => route.fulfill({
    status: 200, contentType: 'text/html',
    body: '<!doctype html><html><title>Hotel navigation fixture</title><body>Official hotel URL intercepted by test.</body></html>',
  }));
}

async function assertPopup(page, link, expectedUrl, activate = () => link.click()) {
  const originalUrl = page.url();
  const [popup] = await Promise.all([page.waitForEvent('popup'), activate()]);
  await popup.waitForLoadState('domcontentloaded');
  assert.equal(new URL(popup.url()).href, new URL(expectedUrl).href, 'New tab retains the exact official hotel URL');
  assert.equal(page.url(), originalUrl, 'Hotel link preserves the destination page');
  assert.equal(await popup.title(), 'Hotel navigation fixture');
  assert.equal(await popup.evaluate(() => window.opener === null), true, 'External tab has no opener');
  await popup.close();
}

async function assertDestination(page, slug, width, { javaScript = true } = {}) {
  const hotels = catalog[slug];
  const section = page.locator('.hotel-recommendations');
  assert.equal(await section.locator('h2').innerText(), 'Where to Stay');
  assert.equal(await section.locator('.hotels-heading > p').innerText(), 'Find a comfortable place to stay during your adventure.');
  const cards = section.locator('.hotel-card');
  assert.ok(hotels.length >= 1 && hotels.length <= 3, `${slug}: 1–3 curated cards`);
  assert.equal(await cards.count(), hotels.length);
  for (const [index, hotel] of hotels.entries()) {
    const card = cards.nth(index);
    assert.equal(await card.getAttribute('data-hotel'), hotel.id);
    assert.equal(await card.locator('h3').innerText(), hotel.name);
    assert.equal(await card.locator('.hotel-location').innerText(), hotel.location);
    assert.equal(await card.locator('.hotel-description').innerText(), hotel.description);
    const link = card.locator('a.hotel-link');
    assert.equal(await link.evaluate(node => node.tagName), 'A');
    assert.equal(await link.innerText(), 'View Hotel');
    assert.equal(await link.getAttribute('href'), hotel.url);
    assert.equal(new URL(hotel.url).protocol, 'https:');
    assert.equal(await link.getAttribute('target'), '_blank');
    const rel = (await link.getAttribute('rel')).split(/\s+/);
    assert.ok(rel.includes('noopener') && rel.includes('noreferrer'));
    assert.equal(await link.getAttribute('aria-label'), `View Hotel: ${hotel.name} (opens in a new tab)`);
    assert.ok((await link.boundingBox()).height >= 44, `${slug}/${width}: minimum touch target`);
    assert.ok(hotel.photo, `${slug}: every recommended hotel has a property photo`);
    if (hotel.photo) {
      const image = card.locator('img.hotel-image');
      assert.equal(await image.count(), 1);
      assert.equal(await image.getAttribute('alt'), hotel.photo.alt);
      assert.equal(await image.getAttribute('src'), `/static/hotels/${hotel.photo.asset_base}-640.webp`);
      assert.equal(await image.evaluate(node => node.complete && node.naturalWidth > 0), true, `${slug}/${width}: property image loads`);
      assert.equal(await image.isVisible(), true);
      assert.equal(await card.locator('.hotel-photo-fallback').isVisible(), false);
      const credit = card.locator('.hotel-photo-credit');
      assert.equal(await credit.isVisible(), true);
      assert.equal(await credit.getByRole('link', { name: hotel.photo.author, exact: true }).getAttribute('href'), hotel.photo.source_url);
      if (hotel.photo.license_url) {
        assert.equal(await credit.getByRole('link', { name: hotel.photo.license, exact: true }).getAttribute('href'), hotel.photo.license_url);
      } else {
        assert.equal(await credit.getByRole('link').count(), 1, 'Official-site credit has no invented license link');
        assert.ok((await credit.innerText()).includes(hotel.photo.license));
      }
      assert.match(await credit.innerText(), /resized\s*\/\s*cropped/);
    }
  }
  assert.equal(await page.locator('.mission-list > li').count(), 3, `${slug}: original missions retained`);
  assert.equal(await page.locator('.mission-list').isVisible(), true);
  const scanner = page.locator('#open-scanner');
  if (javaScript) {
    await page.locator('#open-scanner:not([disabled])').waitFor({ state: 'attached' });
    assert.equal(await scanner.isEnabled(), true, `${slug}: scanner remains enabled`);
  } else {
    assert.equal(await scanner.isDisabled(), true, 'No-JavaScript scanner retains its explanatory disabled state');
    assert.equal(await page.getByText('Enable JavaScript in your browser to scan mission cards.', { exact: true }).isVisible(), true);
  }
  assert.equal(await scanner.getAttribute('aria-expanded'), 'false');
  assert.equal(await scanner.innerText(), 'Scan a QR');
  assert.equal(await page.locator('.back-to-gallery').getAttribute('href'), '/dashboard');
  await assertFits(page, `${slug}/${width}${javaScript ? '' : '/no-js'}`);
}

async function assertKeyboardNavigation(page, hotel) {
  await page.locator('.skip-link').focus();
  let reached = false;
  for (let step = 0; step < 24; step++) {
    await page.keyboard.press('Tab');
    reached = await page.locator(`.hotel-card[data-hotel="${hotel.id}"] a.hotel-link`).evaluate(node => node === document.activeElement);
    if (reached) break;
  }
  assert.equal(reached, true, 'Native Tab reaches View Hotel');
  const link = page.locator(`.hotel-card[data-hotel="${hotel.id}"] a.hotel-link`);
  const focused = await link.evaluate(node => ({
    visible: node.matches(':focus-visible'),
    outline: getComputedStyle(node).outlineStyle,
    top: node.getBoundingClientRect().top,
    bottom: node.getBoundingClientRect().bottom,
  }));
  assert.equal(focused.visible, true);
  assert.notEqual(focused.outline, 'none', 'Keyboard focus has a visible outline');
  assert.ok(focused.top >= 0 && focused.bottom <= page.viewportSize().height, 'Browser scrolls focused hotel link into view');
  await assertPopup(page, link, hotel.url, () => page.keyboard.press('Enter'));
}

(async () => {
  let browser;
  const errors = [];
  try {
    const port = await new Promise((resolve, reject) => {
      let output = '';
      server.stdout.on('data', chunk => {
        output += chunk;
        if (output.includes('\n')) resolve(JSON.parse(output.split('\n')[0]).port);
      });
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Fixture server exited ${code}: ${serverErrors}`)));
    });
    const base = `http://127.0.0.1:${port}`;
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' });
    const context = await browser.newContext({ reducedMotion: 'reduce' });
    context.setDefaultTimeout(10000);
    await interceptHotelNavigation(context);
    await context.request.get(`${base}/_preview/session/2`);
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    for (const slug of edgeCasesOnly ? [] : slugs) {
      for (const [width, height] of sizes) {
        await page.setViewportSize({ width, height });
        const response = await page.goto(`${base}/destinations/${slug}`);
        assert.equal(response.status(), 200);
        await settle(page);
        await assertDestination(page, slug, width);
        if (captureScreenshots && [390, 1440].includes(width)) {
          await page.screenshot({ path: path.join(artifacts, `${slug}-${width}.png`), fullPage: true });
        }
        await assertKeyboardNavigation(page, catalog[slug][0]);
      }
      console.log(`PASS ${slug}: 320, 390, 768 and 1440; content, photo/fallback, focus and native hotel tab.`);
    }
    await context.close();

    // A real failed image request must reveal the labelled placeholder, hide
    // the broken image and its credit, and preserve the independent hotel link.
    const broken = await browser.newContext({ reducedMotion: 'reduce' });
    broken.setDefaultTimeout(10000);
    await interceptHotelNavigation(broken);
    await broken.route('**/static/hotels/**', route => route.abort('failed'));
    await broken.request.get(`${base}/_preview/session/2`);
    const failedPage = await broken.newPage();
    failedPage.on('pageerror', error => errors.push(error.message));
    for (const width of [390, 1440]) {
      await failedPage.setViewportSize({ width, height: width === 390 ? 844 : 900 });
      for (const slug of slugs.filter(value => catalog[value].some(hotel => hotel.photo))) {
        await failedPage.goto(`${base}/destinations/${slug}`);
        await settle(failedPage);
        const card = failedPage.locator('.hotel-card').first();
        assert.equal(await card.locator('.hotel-photo-fallback').isVisible(), true, `${slug}: forced image failure shows fallback`);
        assert.equal(await card.locator('.hotel-image').isVisible(), false);
        assert.equal(await card.locator('.hotel-photo-credit').isVisible(), false);
        await assertPopup(failedPage, card.locator('a.hotel-link'), catalog[slug][0].url);
        await assertFits(failedPage, `${slug}/${width}/forced-fallback`);
        if (captureScreenshots && slug === 'palawan') {
          await failedPage.screenshot({ path: path.join(artifacts, `forced-fallback-${width}.png`), fullPage: true });
        }
      }
    }
    console.log('PASS forced image failures: all six properties at 390 and 1440; hidden image/credit, labelled fallback, preserved hotel links.');
    await broken.close();

    const nojs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 320, height: 568 } });
    nojs.setDefaultTimeout(10000);
    await interceptHotelNavigation(nojs);
    await nojs.request.get(`${base}/_preview/session/2`);
    const fallbackPage = await nojs.newPage();
    for (const slug of slugs) {
      await fallbackPage.goto(`${base}/destinations/${slug}`);
      await settle(fallbackPage, { javaScript: false });
      await assertDestination(fallbackPage, slug, 320, { javaScript: false });
      await assertPopup(fallbackPage, fallbackPage.locator('.hotel-link').first(), catalog[slug][0].url);
      console.log(`PASS ${slug}: no-JavaScript content, property photo and native hotel link.`);
    }
    await nojs.close();
    assert.deepEqual(errors, [], 'No browser runtime errors');
    console.log('PASS: all six hotel routes at four sizes; six local property photos with source/rights credits; real image errors; no-JavaScript content and links; original missions, scanner and gallery backlink; no horizontal overflow.');
  } finally {
    if (browser) await browser.close();
    if (server.exitCode === null) {
      server.stdin.write('stop\n');
      await new Promise(resolve => {
        server.once('exit', resolve);
        setTimeout(() => { server.kill(); resolve(); }, 3000).unref();
      });
    }
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
