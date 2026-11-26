// Real app/service flow on disposable SQL and photos; no hosted account writes.
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const review = path.join(root, '.impeccable/review/memories');
fs.mkdirSync(review, { recursive: true });
const server = spawn(path.join(root, 'venv/Scripts/python.exe'), ['tests/memories_browser_server.py'], {
  cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'],
});
let serverErrors = '';
server.stderr.on('data', (chunk) => { serverErrors += chunk; });
const photos = ['palawan-mitras-ranch.jpg', 'vigan-calle-crisologo.jpg', 'cebu-binalayan-hidden-falls.jpg']
  .map((name) => path.join(root, 'static/destinations', name));

(async () => {
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let output = '';
      server.stdout.on('data', (chunk) => {
        output += chunk;
        if (output.includes('\n')) resolve(JSON.parse(output.split('\n')[0]).port);
      });
      server.once('error', reject);
      server.once('exit', (code) => reject(new Error('Fixture exited: ' + code)));
    });
    const base = `http://127.0.0.1:${port}`;
    browser = await chromium.launch({ channel: 'chrome' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (error) => errors.push(error.message));
    await context.request.get(base + '/_preview/session/42');
    await page.goto(base + '/profile');
    async function capture(name) {
      await page.evaluate(async () => {
        document.querySelectorAll('img').forEach((image) => { image.loading = 'eager'; });
        await Promise.all([...document.images].filter((image) => image.hasAttribute('src'))
          .map((image) => image.decode().catch(() => {})));
        window.scrollTo(0, 0);
      });
      await page.screenshot({ path: path.join(review, name + '.png'), fullPage: true });
    }
    async function noOverflow() {
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    }
    assert.equal(await page.locator('#memories-empty').isVisible(), true);
    await capture('empty-desktop');
    await page.getByRole('button', { name: 'Add Memories', exact: true }).click();
    await page.getByRole('button', { name: 'Save Memories', exact: true }).click();
    await page.getByText('Please add at least 1 image to save your memories.', { exact: true }).waitFor();
    await page.locator('#memory-files').setInputFiles([...photos, photos[0]]);
    assert.equal(await page.locator('.memory-preview').count(), 3);
    await page.getByText('You can save up to 3 photos at a time.', { exact: true }).waitFor();
    while (await page.locator('.memory-preview').count()) {
      await page.locator('.memory-preview button').first().click();
    }
    await page.getByRole('button', { name: 'Save Memories', exact: true }).click();
    await page.getByText('Please add at least 1 image to save your memories.', { exact: true }).waitFor();
    await page.locator('#memory-files').setInputFiles(photos.slice(0, 2));
    await page.locator('#memory-files').setInputFiles(photos[2]);
    assert.equal(await page.locator('.memory-preview').count(), 3);
    await page.locator('.memory-preview textarea').nth(0).fill('A quiet afternoon at Mitra’s Ranch.');
    await page.locator('.memory-preview textarea').nth(1).fill('<script>Literal caption, safely displayed.</script>');
    await page.locator('.memory-preview textarea').nth(2).fill('A swim beneath the falls.');
    await capture('upload-desktop');
    await page.setViewportSize({ width: 390, height: 844 });
    await capture('upload-mobile');
    await noOverflow();
    await page.route('**/api/memories', (route) => route.fulfill({
      status: 503, contentType: 'application/json', body: JSON.stringify({ message: 'Synthetic save failure. Try again.' }),
    }), { times: 1 });
    await page.getByRole('button', { name: 'Save Memories', exact: true }).click();
    await page.getByText('Synthetic save failure. Try again.').waitFor();
    assert.equal(await page.locator('.memory-preview').count(), 3);
    assert.equal(await page.locator('#save-memories').isEnabled(), true);
    await page.getByRole('button', { name: 'Save Memories', exact: true }).click();
    await page.getByText('Your memories have been saved.', { exact: true }).waitFor();
    assert.equal(await page.locator('.memory-card').count(), 3);
    assert.equal(await page.locator('#memories-form').isVisible(), false);
    await capture('gallery-mobile');
    for (const width of [320, 390, 600, 768, 1024, 1440]) {
      await page.setViewportSize({ width, height: 900 });
      await noOverflow();
    }
    await capture('gallery-desktop');
    // Keyboard activation, focus trap, edit/save and Escape restore.
    await page.locator('.memory-open').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#memory-viewer').isVisible(), true);
    assert.equal(await page.locator('#close-memory').evaluate((node) => node === document.activeElement), true);
    await capture('viewer-desktop');
    await page.getByRole('button', { name: 'Edit description', exact: true }).click();
    await page.locator('#memory-edit-caption').fill('An afternoon I want to remember.');
    await page.getByRole('button', { name: 'Save description', exact: true }).click();
    await page.getByText('Description saved.', { exact: true }).waitFor();
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.memory-open').first().evaluate((node) => node === document.activeElement), true);
    await page.reload();
    assert.equal(await page.locator('.memory-card').count(), 3);
    await page.getByText('An afternoon I want to remember.', { exact: true }).waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('.memory-open').first().click();
    await capture('viewer-mobile');
    await page.getByRole('button', { name: 'Delete memory', exact: true }).click();
    await page.locator('#cancel-memory-delete').click();
    assert.equal(await page.locator('.memory-card').count(), 3);
    await page.getByRole('button', { name: 'Delete memory', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.getByText('Memory deleted.', { exact: true }).waitFor();
    assert.equal(await page.locator('.memory-card').count(), 2);
    await page.reload();
    assert.equal(await page.locator('.memory-card').count(), 2);
    await page.getByRole('button', { name: 'Add Memories', exact: true }).click();
    await page.locator('#memory-files').setInputFiles(photos[0]);
    await page.locator('#cancel-memories').click();
    assert.equal(await page.locator('.memory-preview').count(), 0);
    assert.equal(await page.locator('#add-memories').evaluate((node) => node === document.activeElement), true);
    // Deleting from the gallery while a new batch is open restores visible focus
    // and preserves the unsaved batch.
    await page.getByRole('button', { name: 'Add Memories', exact: true }).click();
    await page.locator('#memory-files').setInputFiles(photos[0]);
    await page.locator('.memory-open').first().click();
    await page.getByRole('button', { name: 'Delete memory', exact: true }).click();
    await page.getByRole('button', { name: 'Delete permanently', exact: true }).click();
    await page.getByText('Memory deleted.', { exact: true }).waitFor();
    assert.equal(await page.locator('#memory-files').evaluate((node) => node === document.activeElement), true);
    assert.equal(await page.locator('.memory-preview').count(), 1);
    await page.locator('#cancel-memories').click();
    await page.getByRole('button', { name: 'Add Memories', exact: true }).click();
    await page.locator('#memory-files').setInputFiles(photos[0]);
    await page.locator('.memory-preview textarea').fill('A single memory.');
    await page.getByRole('button', { name: 'Save Memories', exact: true }).click();
    await page.getByText('Your memories have been saved.', { exact: true }).waitFor();
    assert.equal(await page.locator('.memory-card').count(), 2);
    await page.reload();
    assert.equal(await page.locator('.memory-card').count(), 2);
    await page.getByText('A single memory.', { exact: true }).waitFor();
    const imageUrl = await page.locator('.memory-open').first().getAttribute('href');
    const other = await browser.newContext();
    assert.equal((await other.request.get(base + imageUrl)).status(), 401);
    await other.request.get(base + '/_preview/session/99');
    assert.equal((await other.request.get(base + imageUrl)).status(), 404);
    assert.deepEqual((await (await other.request.get(base + '/api/memories')).json()).memories, []);
    await other.close();
    assert.deepEqual(errors, []);
    console.log('Memories browser flow passed: one-to-three photo limits, single-photo save, captions, previews, failure recovery, persistence, viewer, edit/delete, privacy, keyboard, and six responsive widths.');
  } catch (error) {
    console.error(error);
    console.error(serverErrors.slice(-6000));
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    server.stdin.end('\n');
    await new Promise((resolve) => { if (server.exitCode !== null) resolve(); else server.once('exit', resolve); });
  }
})();
