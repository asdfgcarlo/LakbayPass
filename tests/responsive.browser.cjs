// Synthetic read-only fixtures; does not connect to the app database.
// PLAYWRIGHT_MODULE may point to an existing Playwright package.
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const root = path.resolve(__dirname, '..');
const python = path.join(root, 'venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const baseline = process.argv.includes('--baseline');
const interactionsOnly = process.argv.includes('--interactions');
const artifacts = path.join(root, '.impeccable/review/responsive' + (baseline ? '-before' : ''));
fs.mkdirSync(artifacts, { recursive: true });
const server = spawn(python, ['tests/responsive_browser_server.py'], { cwd: root, windowsHide: true, stdio: ['pipe', 'pipe', 'pipe'] });
let serverErrors = '';
server.stderr.on('data', chunk => { serverErrors = (serverErrors + chunk).slice(-12000); });

(async () => {
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let output = '';
      server.stdout.on('data', chunk => { output += chunk; if (output.includes('\n')) resolve(JSON.parse(output.split('\n')[0]).port); });
      server.once('error', reject);
      server.once('exit', code => reject(new Error('Fixture server exited: ' + code)));
    });
    const base = `http://127.0.0.1:${port}`;
    browser = await chromium.launch({ channel: 'chrome' });
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce', hasTouch: true });
    context.setDefaultTimeout(10000);
    context.setDefaultNavigationTimeout(15000);
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await context.request.get(base + '/_preview/session/1');
    const routes = interactionsOnly ? [] : ['/login', '/register', '/dashboard', '/profile', '/redeem',
      ...['palawan', 'vigan', 'cebu', 'siquijor', 'siargao', 'camiguin'].map(slug => '/destinations/' + slug), '/admin'];
    const overflows = [];
    for (const route of routes) {
      if (route === '/admin') await context.request.get(base + '/_preview/session/3');
      for (const [width, height] of [[320,568],[390,844],[600,320],[700,900],[767,800],[768,1024],[844,390],[1024,768],[1440,900]]) {
        await page.setViewportSize({ width, height });
        const response = await page.goto(base + route);
        assert.equal(response.status(), 200, route);
        await page.evaluate(() => document.fonts.ready);
        if (route === '/dashboard') await page.waitForSelector('.canvas-ready');
        await page.evaluate(async () => {
          const images = [...document.images];
          images.forEach(image => { image.loading = 'eager'; });
          await Promise.all(images.map(image => image.decode().catch(() => {})));
        });
        const overflow = await page.evaluate(() => ({ width: innerWidth, scroll: document.documentElement.scrollWidth,
          offenders: [...document.querySelectorAll('body *')].filter(node => {
            const r = node.getBoundingClientRect(), css = getComputedStyle(node);
            return r.width && r.right > innerWidth + 1 && css.position !== 'absolute' && !node.closest('#photo-canvas,.canvas-brand') && !node.closest('.sr-only,.visually-hidden');
          }).map(node => node.className || node.tagName).slice(0,6) }));
        if (overflow.scroll > width) overflows.push({ route, width, ...overflow });
        if ([390,1440].includes(width) && (!route.startsWith('/destinations/') || route === '/destinations/palawan' || width === 390)) {
          await page.screenshot({ path: path.join(artifacts, route.slice(1).replaceAll('/','-') + `-${width}.png`), fullPage: true });
        }
        if (!baseline && !['/login','/register'].includes(route)) {
          const menu = page.locator('[data-account-menu]');
          assert.equal(await menu.isVisible(), width <= 767, `${route} menu breakpoint at ${width}`);
          if (width <= 767) {
            await menu.locator('summary').click();
            assert.equal(await menu.getAttribute('open'), '');
            for (const name of ['Profile','Redeem Points','Log Out']) assert.ok(await menu.getByRole('link',{name,exact:true}).isVisible());
            assert.ok(await menu.getByText('Current Points',{exact:true}).isVisible());
            const panel = await menu.locator('.account-menu-panel').boundingBox();
            assert.ok(panel.x >= 0 && panel.x + panel.width <= width && panel.y + panel.height <= height, `${route} menu panel fits ${width}x${height}`);
            await page.keyboard.press('Escape');
            assert.equal(await menu.getAttribute('open'), null);
          }
        }
      }
    }
    if (baseline) console.log('Baseline overflow findings:', JSON.stringify(overflows));
    else {
      assert.deepEqual(overflows, [], 'All routes fit the viewport');
      assert.deepEqual(errors, [], 'No browser runtime errors');
      await context.request.get(base + '/_preview/session/1');
      await page.setViewportSize({width:390,height:844});
      await page.goto(base+'/dashboard');
      const menu = page.locator('[data-account-menu]');
      const summary = menu.locator('summary');
      await summary.tap();
      assert.equal(await menu.locator('[data-current-points]').innerText(),'180');
      await page.waitForTimeout(400); // Let Chrome's native tap highlight settle.
      assert.ok(await menu.locator('.menu-close-icon').isVisible());
      await page.screenshot({path:path.join(artifacts,'menu-open-390.png'),fullPage:true});
      await Promise.all([page.waitForURL(base+'/profile'),menu.getByRole('link',{name:'Profile',exact:true}).tap()]);
      await menu.locator('summary').focus();
      await page.keyboard.press('Enter');
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.textContent.trim()),'Profile');
      await page.keyboard.press('Escape');
      assert.ok(await menu.locator('summary').evaluate(node=>node===document.activeElement));
      await menu.locator('summary').tap();
      await page.locator('h1').click({position:{x:5,y:10}});
      assert.equal(await menu.getAttribute('open'),null,'Outside click closes menu');
      await menu.locator('summary').tap();
      await Promise.all([page.waitForURL(base+'/redeem'),menu.getByRole('link',{name:'Redeem Points',exact:true}).tap()]);
      await menu.locator('summary').tap();
      await Promise.all([page.waitForURL(base+'/login'),menu.getByRole('link',{name:'Log Out',exact:true}).tap()]);

      await context.request.get(base+'/_preview/session/1');
      await page.route('**/api/destinations/palawan/missions', async route=>{
        const response=await route.fetch();
        const data=await response.json();data.total_points=165;
        await route.fulfill({json:data});
      });
      await page.goto(base+'/destinations/palawan');
      await page.evaluate(()=>window.dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
      await page.waitForFunction(()=>document.querySelector('[data-current-points]').textContent==='165');
      assert.equal(await page.locator('#player-total').innerText(),'165','Scanner refresh updates both balances');
      await page.unroute('**/api/destinations/palawan/missions');

      await page.emulateMedia({reducedMotion:'no-preference'});
      await page.goto(base+'/dashboard');
      await page.waitForSelector('.canvas-ready');
      await menu.locator('summary').tap();
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      const transform=()=>page.locator('.photo-tile').first().evaluate(node=>getComputedStyle(node).transform);
      const frozen=await transform();await page.waitForTimeout(150);
      assert.equal(await transform(),frozen,'Gallery pauses behind open menu');
      await page.keyboard.press('Escape');await page.waitForTimeout(150);
      assert.notEqual(await transform(),frozen,'Gallery resumes when menu closes');
      await page.locator('.playback-button').click();
      await menu.locator('summary').tap();await page.keyboard.press('Escape');
      assert.equal(await page.locator('#photo-canvas').getAttribute('data-autoplay'),'false','Menu preserves chosen pause');
      await menu.locator('summary').tap();
      await page.setViewportSize({width:1024,height:768});
      await page.waitForFunction(()=>!document.querySelector('[data-account-menu]').open);

      for(const user of [2,4]) {
        await context.request.get(base+'/_preview/session/'+user);
        await page.setViewportSize({width:320,height:568});
        for(const route of ['/dashboard','/profile','/redeem']) {
          const response=await page.goto(base+route);
          assert.equal(response.status(),user===4&&route!='/dashboard'?503:200);
          await menu.locator('summary').tap();
          assert.equal(await menu.locator('[data-current-points]').innerText(),user===2?'0':'Unavailable');
          await page.keyboard.press('Escape');
        }
      }
      const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:320,height:568}});
      await nojs.request.get(base+'/_preview/session/2');
      const fallback=await nojs.newPage();await fallback.goto(base+'/dashboard');
      await fallback.locator('[data-account-menu] summary').click();
      await Promise.all([fallback.waitForURL(base+'/profile'),fallback.locator('.account-menu-panel').getByRole('link',{name:'Profile',exact:true}).click()]);
      assert.equal(await fallback.locator('.profile-empty').isVisible(),true);
      await nojs.close();
      assert.deepEqual(errors, [], 'No browser runtime errors');
      console.log((interactionsOnly ? 'Menu checks passed.' : 'Responsive layouts passed: all 12 routes at 9 phone, tablet, short landscape and desktop sizes.') + ' Menu links, keyboard/touch, Escape/outside close, balance refresh, gallery pause, resize, zero/error states and no-JavaScript navigation passed.');
    }
  } finally {
    if (browser) await browser.close();
    server.stdin.write('stop\n');
    await new Promise(resolve => { if (server.exitCode !== null) return resolve(); server.once('exit', resolve); setTimeout(() => { server.kill(); resolve(); }, 3000).unref(); });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
