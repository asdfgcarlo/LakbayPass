// Requires Playwright (or PLAYWRIGHT_MODULE) and local MySQL with CREATE DATABASE.
// The helper creates and removes a UUID-scoped test database; no app claims change.
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fixtures = require('./fixtures/mission-qr.json');
const root = path.resolve(__dirname, '..');
const python = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const server = spawn(python, ['tests/mission_browser_server.py'], { cwd: root, stdio: ['pipe', 'pipe', 'pipe'], windowsHide: true });
let serverErrors = '';
server.stderr.on('data', data => { serverErrors += data; });

// Real canvas MediaStreams carry actual QR pixels through video and jsQR. Only
// hardware acquisition is replaced; the decoder, fetch, Flask and MySQL are real.
function cameraHarness({ fixtures }) {
  const state = { mode: 'blank', code: 'LP-QG99QBYR', requests: [], streams: [] };
  window.testCamera = state;
  function makeStream() {
    const canvas = document.createElement('canvas');
    canvas.width = canvas.height = 512;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, 512, 512);
    if (state.mode === 'qr' || state.mode === 'late') {
      const matrix = fixtures[state.code];
      const unit = Math.floor(480 / matrix.length);
      const offset = Math.floor((512 - unit * matrix.length) / 2);
      ctx.fillStyle = '#000';
      matrix.forEach((row, y) => row.forEach((dark, x) => {
        if (dark) ctx.fillRect(offset + x * unit, offset + y * unit, unit, unit);
      }));
    }
    const stream = canvas.captureStream(10);
    state.streams.push(stream);
    return stream;
  }
  navigator.mediaDevices.getUserMedia = async constraints => {
    state.requests.push(constraints);
    if (state.mode === 'denied') throw new DOMException('Test denied', 'NotAllowedError');
    if (state.mode === 'missing') throw new DOMException('Test missing', 'NotFoundError');
    if (state.mode === 'busy') throw new DOMException('Test busy', 'NotReadableError');
    if (state.mode === 'late') return new Promise(resolve => { state.resolvePending = () => resolve(makeStream()); });
    return makeStream();
  };
}

async function login(page, base, account = 1) {
  await page.goto(`${base}/login`);
  await page.locator('#email').fill(`scanner-${account}@example.test`);
  await page.locator('#password').fill('scanner-test-password');
  await Promise.all([page.waitForURL(`${base}/dashboard`), page.getByRole('button', { name: 'Log in', exact: true }).click()]);
}
async function mode(page, mode, code = 'LP-QG99QBYR') {
  await page.evaluate(({ mode, code }) => Object.assign(window.testCamera, { mode, code }), { mode, code });
}
async function stopped(page) {
  assert.equal(await page.evaluate(() => window.testCamera.streams.every(stream => stream.getTracks().every(track => track.readyState === 'ended'))), true, 'All camera tracks must stop');
  assert.equal(await page.locator('#camera-preview').evaluate(video => video.srcObject === null), true);
}
async function scan(page, code, status) {
  await mode(page, 'qr', code);
  if (await page.locator('#mission-scanner').isVisible()) await page.locator('#retry-scanner').click();
  else await page.locator('#open-scanner').click();
  await page.waitForFunction(status => document.querySelector('#scanner-root').dataset.claimStatus === status && document.querySelector('#scanner-root').getAttribute('aria-busy') !== 'true', status);
  await stopped(page);
}
async function noOverflow(page) {
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  for (const name of ['#close-scanner', '#retry-scanner']) {
    if (await page.locator(name).isVisible()) {
      const box = await page.locator(name).boundingBox();
      assert.ok(box.height >= 44 && box.x >= 0 && box.x + box.width <= (await page.viewportSize()).width, `${name} reachable`);
    }
  }
}

(async () => {
  let browser;
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
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    await context.addInitScript(cameraHarness, { fixtures });
    const page = await context.newPage();
    page.setDefaultTimeout(7000);
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await login(page, base);

    // Every destination connects to the shared scanner with no camera on load.
    for (const slug of ['palawan', 'vigan', 'cebu', 'siquijor', 'siargao', 'camiguin']) {
      await page.goto(`${base}/destinations/${slug}`);
      assert.equal(await page.evaluate(() => window.testCamera.requests.length), 0);
      assert.equal(await page.locator('#scanner-root').getAttribute('data-destination'), slug);
      await page.locator('#open-scanner').focus();
      await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelector('#camera-status').textContent.startsWith('Camera ready'));
      assert.equal(await page.evaluate(() => window.testCamera.requests[0].video.facingMode.ideal), 'environment');
      assert.equal(await page.evaluate(() => window.testCamera.requests[0].audio), false);
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('#mission-scanner').isVisible(), false);
      assert.equal(await page.locator('#open-scanner').evaluate(node => node === document.activeElement), true);
      await stopped(page);
    }

    await page.goto(`${base}/destinations/cebu`);
    let sentPayload;
    page.on('request', request => { if (request.url().endsWith('/api/claims')) sentPayload = request.postDataJSON(); });
    await scan(page, 'LP-QG99QBYR', 'claimed');
    assert.deepEqual(sentPayload, { qr_code: 'LP-QG99QBYR', destination_slug: 'cebu' });
    assert.match(await page.locator('#claim-feedback').innerText(), /Local Foods claimed.*15 points/);
    assert.equal(await page.locator('[data-mission-type="local_foods"] .mission-state').isVisible(), true);
    assert.equal(await page.locator('#player-total').innerText(), '15');
    await scan(page, 'LP-QG99QBYR', 'already_claimed');
    assert.match(await page.locator('#claim-feedback').innerText(), /already claimed.*No additional points/);
    assert.equal(await page.locator('#player-total').innerText(), '15');
    await scan(page, 'LP-BALJDMK4', 'wrong_destination');
    assert.match(await page.locator('#claim-feedback').innerText(), /belongs to Palawan/);
    await scan(page, 'LP-00000000', 'unknown_qr');
    assert.match(await page.locator('#claim-feedback').innerText(), /QR not recognized/);
    assert.equal(await page.locator('#player-total').innerText(), '15');

    // A failed request does not invent a claim or points; retry resolves safely.
    await page.route('**/api/claims', route => route.abort('failed'), { times: 1 });
    await scan(page, 'LP-2KK9Y69H', 'unavailable');
    assert.equal(await page.locator('[data-mission-type="activities"] .mission-state').isVisible(), false);
    assert.equal(await page.locator('#player-total').innerText(), '15');
    await scan(page, 'LP-2KK9Y69H', 'claimed');
    assert.equal(await page.locator('#player-total').innerText(), '35');
    await page.reload();
    assert.equal(await page.locator('#player-total').innerText(), '35');
    assert.equal(await page.locator('.is-claimed').count(), 2);
    assert.equal(await page.evaluate(() => window.testCamera.requests.length), 0);

    const review = path.join(root, '.impeccable/review');
    fs.mkdirSync(review, { recursive: true });
    await page.screenshot({ path: path.join(review, 'scanner-claimed-desktop.png'), fullPage: true });
    // Permission, missing hardware and busy-camera feedback are actionable.
    for (const [failure, text] of [['denied', 'Camera access was blocked'], ['missing', 'No camera was found'], ['busy', 'Close other apps']]) {
      await mode(page, failure);
      await page.locator('#open-scanner').click();
      await page.waitForFunction(text => document.querySelector('#camera-status').textContent.includes(text), text);
      assert.equal(await page.locator('#retry-scanner').isVisible(), true);
      await noOverflow(page);
      if (failure === 'denied') await page.screenshot({ path: path.join(review, 'scanner-denied-desktop.png'), fullPage: true });
      await page.locator('#close-scanner').click();
      await stopped(page);
    }
    // Closing before permission resolves still stops the late-acquired stream.
    await mode(page, 'late');
    await page.locator('#open-scanner').click();
    await page.waitForFunction(() => typeof window.testCamera.resolvePending === 'function');
    await page.locator('#close-scanner').click();
    await page.evaluate(() => window.testCamera.resolvePending());
    await page.waitForTimeout(100);
    await stopped(page);

    // Leaving/hiding the page closes the scanner and releases camera tracks.
    await mode(page, 'blank');
    await page.locator('#open-scanner').click();
    await page.waitForFunction(() => window.testCamera.streams.some(stream => stream.active));
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide')));
    await stopped(page);
    assert.equal(await page.locator('#mission-scanner').isVisible(), false);
    await page.locator('#open-scanner').click();
    await page.waitForFunction(() => window.testCamera.streams.some(stream => stream.active));
    await page.evaluate(() => {
      Object.defineProperty(document, 'hidden', { configurable: true, value: true });
      document.dispatchEvent(new Event('visibilitychange'));
      delete document.hidden;
    });
    await stopped(page);

    // A second signed-in account can claim the same physical QR once.
    const phoneContext = await browser.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, reducedMotion: 'reduce' });
    await phoneContext.addInitScript(cameraHarness, { fixtures });
    const phone = await phoneContext.newPage();
    phone.on('pageerror', error => errors.push(error.message));
    await login(phone, base, 2);
    await phone.goto(`${base}/destinations/cebu`);
    await mode(phone, 'qr');
    await phone.locator('#open-scanner').tap();
    await phone.waitForFunction(() => document.querySelector('#scanner-root').dataset.claimStatus === 'claimed');
    assert.equal(await phone.locator('#player-total').innerText(), '15');
    await stopped(phone);
    await noOverflow(phone);
    await phone.screenshot({ path: path.join(review, 'scanner-claimed-phone.png'), fullPage: true });
    await scan(phone, 'LP-QG99QBYR', 'already_claimed');
    assert.equal(await phone.locator('#player-total').innerText(), '15');
    await phone.locator('#close-scanner').tap();

    for (const width of [320, 390, 768, 1440]) {
      await phone.setViewportSize({ width, height: 900 });
      await mode(phone, 'blank');
      await phone.locator('#open-scanner').tap();
      await phone.waitForFunction(() => document.querySelector('#camera-status').textContent.startsWith('Camera ready'));
      await noOverflow(phone);
      if ([320, 390, 1440].includes(width)) await phone.screenshot({ path: path.join(review, `scanner-open-${width}.png`), fullPage: true });
      await phone.locator('#close-scanner').tap();
      await stopped(phone);
    }
    assert.deepEqual(errors, []);
    console.log('PASS: real QR pixel decoding and MySQL claims; all six scanner buttons; rear-camera preference; Cebu food +15, repeat +0 and second-account +15; unknown/wrong destination; saved reload; network and camera failures; late permission, Close, Escape, pagehide/visibility cleanup; 320/390/768/1440 layouts.');
  } finally {
    if (browser) await browser.close();
    server.stdin.end('stop\n');
    await new Promise(resolve => server.once('exit', resolve));
    if (server.exitCode !== 0) console.error(serverErrors);
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
