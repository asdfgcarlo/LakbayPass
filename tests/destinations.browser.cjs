// Requires Playwright: npm install --no-save playwright
// Or set PLAYWRIGHT_MODULE to an existing Playwright package directory.
// Uses a synthetic signed session and an ephemeral Flask server. Mission tables
// must be installed; this suite only reads them and never writes a claim.
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const python = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const session = execFileSync(python, ['-c', "from app import app; print(app.session_interface.get_signing_serializer(app).dumps({'loggedin':True,'id':0,'username':'Destination tester'}))"], { cwd: root, encoding: 'utf8' }).trim();
const server = spawn(python, ['-c', "from app import app; from werkzeug.serving import make_server; server=make_server('127.0.0.1',0,app); print(server.server_port,flush=True); server.serve_forever()"], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
const places = [
  { slug: 'palawan', name: 'Palawan', photo: 'palawan-mitras-ranch.jpg' },
  { slug: 'vigan', name: 'Vigan', photo: 'vigan-calle-crisologo.jpg' },
  { slug: 'cebu', name: 'Cebu', photo: 'cebu-binalayan-hidden-falls.jpg' },
  { slug: 'siquijor', name: 'Siquijor', photo: 'siquijor-paliton-beach.jpg' },
  { slug: 'siargao', name: 'Siargao', photo: 'siargao-sugba-lagoon.jpg' },
  { slug: 'camiguin', name: 'Camiguin', photo: 'camiguin-mantigue-island.jpg' },
];

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}

// Move a particular recycled copy into view through the gallery's normal pan handler.
// Actual activation below always uses a native mouse, keyboard, or touch event.
async function showCopy(page, slug, copy = 0) {
  const tile = page.locator(`.photo-tile[data-destination="${slug}"]`).nth(copy);
  await tile.evaluate(node => {
    const rect = node.getBoundingClientRect();
    const dx = (innerWidth - rect.width) / 2 - rect.left;
    const dy = Math.max(120, (innerHeight - rect.height) / 2) - rect.top;
    if (Math.hypot(dx, dy) < 1) return;
    const canvas = document.querySelector('#photo-canvas');
    const common = { bubbles: true, pointerId: 42, pointerType: 'mouse', isPrimary: true, button: 0 };
    canvas.dispatchEvent(new PointerEvent('pointerdown', { ...common, clientX: 200, clientY: 200, buttons: 1 }));
    canvas.dispatchEvent(new PointerEvent('pointermove', { ...common, clientX: 200 + dx, clientY: 200 + dy, buttons: 1 }));
    window.dispatchEvent(new PointerEvent('pointerup', { ...common, clientX: 200 + dx, clientY: 200 + dy, buttons: 0 }));
  });
  await settle(page);
  return tile;
}

async function pointWithin(tile, selector) {
  const box = await tile.locator(selector).first().boundingBox();
  assert.ok(box && box.width > 0 && box.height > 0, `Missing visible ${selector}`);
  return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
}

async function visit(page, context, base, place, activate) {
  const tabs = context.pages().length;
  await Promise.all([page.waitForURL(`${base}/destinations/${place.slug}`), activate()]);
  assert.equal(context.pages().length, tabs, `${place.slug} must open in the same tab`);
  assert.equal(new URL(page.url()).pathname, `/destinations/${place.slug}`);
  assert.match(await page.locator('h1').innerText(), new RegExp(place.name, 'i'));
  const hero = page.locator('img.destination-hero, .destination-hero img').first();
  assert.equal(await hero.isVisible(), true);
  assert.equal(new URL(await hero.getAttribute('src'), base).pathname, `/static/destinations/${place.photo}`);
  assert.equal(await page.locator('.mission-list').isVisible(), true);
  assert.ok(await page.locator('.mission-list li').count() >= 3);
  const scanner = page.locator('#open-scanner');
  assert.equal(await scanner.isEnabled(), true);
  assert.match(await scanner.innerText(), /scan a qr/i);
  assert.equal(await scanner.getAttribute('aria-expanded'), 'false');
  assert.equal(await page.locator('.back-to-gallery').getAttribute('href'), '/dashboard');
  await Promise.all([page.waitForURL(`${base}/dashboard`), page.locator('.back-to-gallery').click()]);
  await page.waitForSelector('.canvas-ready');
  await settle(page);
  assert.equal(context.pages().length, tabs);
}

async function tilePosition(tile) {
  return tile.evaluate(node => {
    const matrix = new DOMMatrixReadOnly(getComputedStyle(node).transform);
    return { x: matrix.m41, y: matrix.m42 };
  });
}

(async () => {
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let output = '';
      server.stdout.on('data', chunk => { output += chunk; if (/^\d+\r?\n/.test(output)) resolve(Number(output.split('\n')[0])); });
      server.once('error', reject);
      server.once('exit', code => reject(new Error(`Test server exited: ${code}`)));
    });
    const base = `http://127.0.0.1:${port}`;
    browser = await chromium.launch(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, reducedMotion: 'reduce' });
    await context.addCookies([{ name: 'session', value: session, url: base }]);
    const page = await context.newPage();
    page.setDefaultTimeout(5000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/dashboard`);
    await page.waitForSelector('.canvas-ready');
    await settle(page);

    // Every generated repeat retains its source destination and a native same-tab link.
    const tiles = await page.locator('.photo-tile').evaluateAll(nodes => nodes.map(node => ({
      tag: node.tagName, slug: node.dataset.destination, href: node.getAttribute('href'),
      target: node.getAttribute('target'), pointerEvents: getComputedStyle(node).pointerEvents,
      tabIndex: node.tabIndex, hidden: node.getAttribute('aria-hidden'),
    })));
    const repeatCounts = places.map(place => tiles.filter(tile => tile.slug === place.slug).length);
    assert.ok(repeatCounts.every(count => count >= 2), 'Every destination must have repeated copies');
    assert.equal(new Set(repeatCounts).size, 1, 'All six destinations repeat equally');
    for (const tile of tiles) {
      assert.equal(tile.tag, 'A');
      assert.ok(places.some(place => place.slug === tile.slug));
      assert.equal(tile.href, `/destinations/${tile.slug}`);
      assert.ok(!tile.target || tile.target === '_self');
      assert.equal(tile.pointerEvents, 'auto');
    }
    assert.equal(await page.locator('#destination-list li').count(), 6);
    for (const place of places) {
      const representatives = tiles.filter(tile => tile.slug === place.slug && tile.tabIndex === 0 && tile.hidden !== 'true');
      assert.equal(representatives.length, 1, `${place.slug} needs one accessible keyboard link`);
    }

    // Image and caption both activate each of the six destinations on different repeats.
    for (const place of places) {
      for (const [copy, selector] of [[0, 'img'], [1, '.caption, figcaption']]) {
        const tile = await showCopy(page, place.slug, copy);
        const point = await pointWithin(tile, selector);
        await visit(page, context, base, place, () => page.mouse.click(point.x, point.y));
      }
    }

    // Native Enter activation works for all six accessible tile links, including offscreen representatives.
    for (const place of places) {
      const tile = page.locator(`.photo-tile[data-destination="${place.slug}"][tabindex="0"]`);
      await tile.focus();
      await settle(page);
      assert.equal(await tile.evaluate(node => document.activeElement === node), true);
      assert.equal(await tile.evaluate(node => {
        const rect = node.getBoundingClientRect();
        return rect.left >= 0 && rect.right <= innerWidth && rect.top >= 0 && rect.bottom <= innerHeight;
      }), true, `${place.slug} keyboard focus must be visible`);
      await visit(page, context, base, place, () => page.keyboard.press('Enter'));
    }

    // Small hand jitter still clicks; a deliberate diagonal drag on an image pans without following its link.
    let tile = await showCopy(page, places[0].slug);
    let point = await pointWithin(tile, 'img');
    await visit(page, context, base, places[0], async () => {
      await page.mouse.move(point.x, point.y);
      await page.mouse.down();
      await page.mouse.move(point.x + 2, point.y + 2);
      await page.mouse.up();
    });
    tile = await showCopy(page, places[1].slug, 1);
    point = await pointWithin(tile, 'img');
    let before = await tilePosition(tile);
    await page.mouse.move(point.x, point.y);
    await page.mouse.down();
    await page.mouse.move(point.x + 85, point.y + 64, { steps: 8 });
    await page.mouse.up();
    await settle(page);
    let after = await tilePosition(tile);
    assert.equal(new URL(page.url()).pathname, '/dashboard', 'Dragging a tile must not navigate');
    assert.ok(after.x - before.x > 60 && after.y - before.y > 40, 'Dragging a tile must pan both axes');
    assert.equal(await page.locator('.is-dragging').count(), 0);
    assert.equal(await page.locator('#photo-canvas').getAttribute('data-autoplay'), 'false');

    // Real touch taps follow all six links, while a real touch swipe starting on a link only pans.
    const touchContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
    await touchContext.addCookies([{ name: 'session', value: session, url: base }]);
    const touchPage = await touchContext.newPage();
    touchPage.setDefaultTimeout(5000);
    touchPage.on('pageerror', error => errors.push(error.message));
    await touchPage.goto(`${base}/dashboard`);
    await touchPage.waitForSelector('.canvas-ready');
    await settle(touchPage);
    for (const place of places) {
      tile = await showCopy(touchPage, place.slug, 1);
      point = await pointWithin(tile, 'img');
      await visit(touchPage, touchContext, base, place, () => touchPage.touchscreen.tap(point.x, point.y));
    }
    tile = await showCopy(touchPage, places[2].slug, 1);
    point = await pointWithin(tile, 'img');
    before = await tilePosition(tile);
    const cdp = await touchContext.newCDPSession(touchPage);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ ...point, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: point.x - 90, y: point.y - 70, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await settle(touchPage);
    await touchPage.waitForTimeout(180);
    after = await tilePosition(tile);
    assert.equal(new URL(touchPage.url()).pathname, '/dashboard', 'Swiping a tile must not navigate');
    assert.ok(after.x - before.x < -60 && after.y - before.y < -40, 'Swiping a tile must pan both axes');
    assert.equal(await touchPage.locator('.is-dragging').count(), 0);
    assert.equal(await touchPage.locator('#photo-canvas').getAttribute('data-autoplay'), 'false');
    tile = await showCopy(touchPage, places[2].slug, 1);
    point = await pointWithin(tile, 'img');
    await visit(touchPage, touchContext, base, places[2], () => touchPage.touchscreen.tap(point.x, point.y));

    // The six source links still work when JavaScript is disabled.
    const fallbackContext = await browser.newContext({ javaScriptEnabled: false });
    await fallbackContext.addCookies([{ name: 'session', value: session, url: base }]);
    const fallbackPage = await fallbackContext.newPage();
    await fallbackPage.goto(`${base}/dashboard`);
    assert.equal(await fallbackPage.locator('a.photo-tile').count(), 6);
    for (const place of places) {
      assert.equal(await fallbackPage.locator(`.photo-tile[data-destination="${place.slug}"]`).getAttribute('href'), `/destinations/${place.slug}`);
    }
    await Promise.all([
      fallbackPage.waitForURL(`${base}/destinations/${places[0].slug}`),
      fallbackPage.locator(`.photo-tile[data-destination="${places[0].slug}"]`).click(),
    ]);
    assert.deepEqual(errors, []);
    console.log('PASS: same-tab destination links on every repeat; all six image/caption clicks, Enter links and native touch taps; small-jitter activation; mouse/touch drag cancellation; destination hero, missions, Scan a QR, Back to gallery and no-JavaScript links.');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
