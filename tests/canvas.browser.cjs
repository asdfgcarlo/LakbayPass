// Requires Playwright: npm install --no-save playwright
// Or set PLAYWRIGHT_MODULE to an existing Playwright package directory.
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');

const root = path.resolve(__dirname, '..');
const python = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const session = execFileSync(python, ['-c', "from app import app; print(app.session_interface.get_signing_serializer(app).dumps({'loggedin':True,'id':0,'username':'Canvas tester'}))"], { cwd: root, encoding: 'utf8' }).trim();
const server = spawn(python, ['-c', "from app import app; from werkzeug.serving import make_server; server=make_server('127.0.0.1',0,app); print(server.server_port,flush=True); server.serve_forever()"], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });

async function settle(page) {
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
}
async function position(page, index = 7) {
  return page.locator('.photo-tile').nth(index).evaluate(tile => {
    const transform = new DOMMatrixReadOnly(getComputedStyle(tile).transform);
    return { x: transform.m41, y: transform.m42 };
  });
}
function near(actual, expected, tolerance = 1) {
  assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} should be within ${tolerance} of ${expected}`);
}
async function syntheticDrag(page, dx, dy) {
  await page.evaluate(({ dx, dy }) => {
    const canvas = document.querySelector('#photo-canvas');
    const options = { bubbles: true, pointerId: 42, pointerType: 'mouse', isPrimary: true, button: 0 };
    canvas.dispatchEvent(new PointerEvent('pointerdown', { ...options, clientX: 200, clientY: 200 }));
    // Begin a real drag past the click/tap threshold before measuring small
    // boundary movements. The final position still gives exactly dx/dy.
    canvas.dispatchEvent(new PointerEvent('pointermove', { ...options, clientX: 212, clientY: 212 }));
    canvas.dispatchEvent(new PointerEvent('pointermove', { ...options, clientX: 200 + dx, clientY: 200 + dy }));
    window.dispatchEvent(new PointerEvent('pointerup', options));
  }, { dx, dy });
  await settle(page);
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
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}/dashboard`);
    await page.waitForSelector('.canvas-ready');
    await settle(page);
    assert.equal(await page.locator('#photo-canvas').getAttribute('data-autoplay'), 'false');
    assert.equal(await page.locator('#destination-list li').count(), 6);

    // Mouse dragging works while paused, without enabling autoplay.
    let before = await position(page);
    await page.mouse.move(800, 450);
    await page.mouse.down();
    await page.mouse.move(940, 520, { steps: 8 });
    await page.mouse.up();
    await settle(page);
    let after = await position(page);
    near(after.x - before.x, 140);
    near(after.y - before.y, 70);
    assert.equal(await page.locator('#photo-canvas').getAttribute('data-autoplay'), 'false');

    // A complete repeat on both axes must produce identical pixels.
    await page.locator('#photo-canvas').focus();
    const periods = await page.evaluate(() => {
      const style = getComputedStyle(document.documentElement);
      const n = name => parseFloat(style.getPropertyValue(name));
      const strideX = n('--tile-width') + n('--column-gap');
      const strideY = n('--tile-height') + n('--caption-height') + n('--row-gap');
      const columns = Math.ceil((Math.ceil(innerWidth / strideX) + 2) / 3) * 3;
      const rows = Math.ceil((Math.ceil(innerHeight / strideY) + 2) / 2) * 2;
      return { x: columns * strideX, y: rows * strideY };
    });
    const originalPixels = await page.screenshot();
    await syntheticDrag(page, periods.x * 7, -periods.y * 9);
    assert.equal(Buffer.compare(originalPixels, await page.screenshot()), 0, 'Whole-loop pixels changed');

    // Crossing a wrap boundary moves every visible tile continuously.
    const origin = await position(page, 0);
    await syntheticDrag(page, -origin.x + 0.25, -origin.y + 0.25);
    const visible = await page.locator('.photo-tile').evaluateAll(nodes => nodes.map((node, index) => {
      const rect = node.getBoundingClientRect();
      return { index, x: rect.x, y: rect.y, visible: rect.right > 1 && rect.bottom > 1 && rect.x < innerWidth - 1 && rect.y < innerHeight - 1 };
    }).filter(tile => tile.visible));
    await syntheticDrag(page, -0.5, -0.5);
    for (const tile of visible) {
      const next = await position(page, tile.index);
      near(next.x - tile.x, -0.5, 0.01);
      near(next.y - tile.y, -0.5, 0.01);
    }

    // Direction buttons and arrow keys work independently of autoplay.
    before = await position(page);
    await page.getByRole('button', { name: 'Move canvas left', exact: true }).click();
    await settle(page);
    after = await position(page);
    assert.ok(after.x < before.x);
    await page.locator('#photo-canvas').focus();
    await page.keyboard.press('ArrowRight');
    await settle(page);
    near((await position(page)).x, before.x);

    // Verify real-time speed and that animation allocates no additional tiles.
    const tileCount = await page.locator('.photo-tile').count();
    await page.evaluate(() => {
      window.canvasNodeAdditions = 0;
      new MutationObserver(records => { window.canvasNodeAdditions += records.reduce((n, r) => n + r.addedNodes.length, 0); }).observe(document.querySelector('#canvas-tiles'), { childList: true });
    });
    await page.getByRole('button', { name: 'Play automatic canvas movement', exact: true }).click();
    await settle(page);
    before = await position(page);
    const started = Date.now();
    await page.waitForTimeout(1200);
    after = await position(page);
    const elapsed = (Date.now() - started) / 1000;
    near(after.x - before.x, -15 * elapsed, 2.5);
    near(after.y - before.y, -5 * elapsed, 1);
    assert.equal(await page.locator('.photo-tile').count(), tileCount);
    assert.equal(await page.evaluate(() => window.canvasNodeAdditions), 0);

    // Autoplay pauses during a held pointer, then resumes after release.
    const holdPoint = await page.evaluate(() => {
      for (let y = 150; y < innerHeight - 160; y += 40) {
        for (let x = 30; x < innerWidth - 30; x += 40) {
          const target = document.elementFromPoint(x, y);
          if (target?.closest('#photo-canvas') && !target.closest('.photo-tile')) return { x, y };
        }
      }
    });
    assert.ok(holdPoint, 'No canvas gap available for held-pointer test');
    await page.mouse.move(holdPoint.x, holdPoint.y);
    await page.mouse.down();
    await settle(page);
    before = await position(page);
    await page.waitForTimeout(250);
    assert.deepEqual(await position(page), before);
    await page.mouse.up();
    await page.waitForTimeout(400);
    assert.ok((await position(page)).x < before.x);
    await page.getByRole('button', { name: 'Pause automatic canvas movement', exact: true }).click();

    // Reachable tap controls at phone, tablet, and desktop sizes.
    for (const size of [{ width: 320, height: 568 }, { width: 390, height: 844 }, { width: 768, height: 1024 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(size);
      await settle(page);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
      for (const button of await page.locator('.canvas-controls button').all()) {
        const box = await button.boundingBox();
        assert.ok(box.width >= 44 && box.height >= 44 && box.x >= 0 && box.x + box.width <= size.width && box.y >= 0 && box.y + box.height <= size.height);
      }
    }

    // Native touch events exercise pointer capture and touch-action behavior.
    const touchContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
    await touchContext.addCookies([{ name: 'session', value: session, url: base }]);
    const touchPage = await touchContext.newPage();
    touchPage.on('pageerror', error => errors.push(error.message));
    await touchPage.goto(`${base}/dashboard`);
    await touchPage.waitForSelector('.canvas-ready');
    await settle(touchPage);
    const cdp = await touchContext.newCDPSession(touchPage);
    before = await position(touchPage, 0);
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchStart', touchPoints: [{ x: 190, y: 400, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchMove', touchPoints: [{ x: 100, y: 300, id: 1 }] });
    await cdp.send('Input.dispatchTouchEvent', { type: 'touchEnd', touchPoints: [] });
    await settle(touchPage);
    after = await position(touchPage, 0);
    near(after.x - before.x, -90);
    near(after.y - before.y, -100);
    assert.equal(await touchPage.locator('.is-dragging').count(), 0);
    assert.equal(await touchPage.locator('#photo-canvas').getAttribute('data-autoplay'), 'false');

    const playingContext = await browser.newContext({ reducedMotion: 'no-preference' });
    await playingContext.addCookies([{ name: 'session', value: session, url: base }]);
    const playingPage = await playingContext.newPage();
    await playingPage.goto(`${base}/dashboard`);
    await playingPage.waitForSelector('.canvas-ready');
    assert.equal(await playingPage.locator('#photo-canvas').getAttribute('data-autoplay'), 'true');
    await playingPage.emulateMedia({ reducedMotion: 'reduce' });
    await playingPage.waitForFunction(() => document.querySelector('#photo-canvas').dataset.autoplay === 'false');
    await playingPage.evaluate(() => {
      const canvas = document.querySelector('#photo-canvas');
      const options = { bubbles: true, pointerId: 42, pointerType: 'touch', isPrimary: true, clientX: 100, clientY: 100 };
      canvas.dispatchEvent(new PointerEvent('pointerdown', options));
      window.dispatchEvent(new PointerEvent('pointercancel', options));
    });
    assert.equal(await playingPage.locator('.is-dragging').count(), 0);

    const fallbackContext = await browser.newContext({ javaScriptEnabled: false });
    await fallbackContext.addCookies([{ name: 'session', value: session, url: base }]);
    const fallbackPage = await fallbackContext.newPage();
    await fallbackPage.goto(`${base}/dashboard`);
    assert.equal(await fallbackPage.locator('.photo-tile').count(), 6);
    assert.equal(await fallbackPage.locator('[data-canvas-toggle]').isVisible(), false);
    assert.deepEqual(errors, []);
    console.log('PASS: seamless two-axis loops, continuous boundary crossing, fixed tile count, 15/5 px/s drift, pause/resume, mouse drag, native touch swipe, keyboard controls, reduced motion, responsive controls, no-JavaScript fallback.');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
