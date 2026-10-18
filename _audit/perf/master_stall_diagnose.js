// _audit/perf/master_stall_diagnose.js — چرا #/master روی «در حال…» می‌ماند؟
//
// master_landing_check.js نشان داد درِ t=121s هیچِ درخواستِ in-flight نیست، صفحه سفید نیست
// (۳۳۷ عنصر، ۱۶۹۵ کاراکترِ ناوبری) ولی نشانک‌هایِ محتوایِ استراتژی هرگز نمی‌آیند. اینِ اسنیپ
// همانِ حالتِ بن‌بست را باز می‌کند: متنِ کاملِ ناحیۀِ محتوا، کلاسِ هرِ کانتینرِ بارگزاری،
// وضعیتِ queryهایِ TanStack اگر جایی قابلِ خواندن است، و پیام‌هایِ کنسول.
//
// usage: node _audit/perf/master_stall_diagnose.js
const os = require('os');
const fs = require('fs');
const path = require('path');
const REPO = path.join(__dirname, '..', '..');
const { chromium } = require(path.join(REPO, 'frontend', 'node_modules', 'playwright-core'));

const BASE = process.env.BORS_UI_BASE || 'http://127.0.0.1:8000';
const EXE = process.env.RA_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';

(async () => {
  const browser = await chromium.launch({
    executablePath: EXE,
    args: ['--no-first-run', '--disable-sync', '--remote-debugging-port=0'],
  });
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  const page = await ctx.newPage();
  const logs = [];
  page.on('console', (m) => logs.push(m.type() + ': ' + m.text().slice(0, 240)));
  page.on('pageerror', (e) => logs.push('pageerror: ' + String(e).slice(0, 240)));
  const reqs = [];
  page.on('request', (r) => { if (r.url().includes('/api/')) reqs.push(r.method() + ' ' + decodeURIComponent(r.url().replace(/^https?:\/\/[^/]+/, ''))); });
  const resps = [];
  page.on('response', (r) => { if (r.url().includes('/api/')) resps.push(r.status() + ' ' + decodeURIComponent(r.url().replace(/^https?:\/\/[^/]+/, ''))); });

  await page.goto(BASE + '/', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1200);
  if (await page.evaluate(() => !!document.querySelector('input[type="password"]'))) {
    const src = fs.readFileSync(path.join(REPO, 'frontend', 'src', 'shared', 'stores', 'authStore.ts'), 'utf8');
    const du = (src.match(/DEFAULT_USER\s*=\s*'([^']+)'/) || [])[1];
    const dp = (src.match(/DEFAULT_PASS\s*=\s*'([^']+)'/) || [])[1];
    await page.locator('input[type="text"]').first().fill(du);
    await page.locator('input[type="password"]').first().fill(dp);
    await page.locator('button[type="submit"]').first().click();
  }
  await page.waitForTimeout(30000);

  const snap = await page.evaluate(() => {
    const main = document.querySelector('main') || document.body;
    const loaders = [...document.querySelectorAll('[class*="animate-spin"],[role="status"],[aria-busy="true"]')].map((el) => ({
      cls: (el.className || '').toString().slice(0, 120),
      parentCls: (el.parentElement && el.parentElement.className || '').toString().slice(0, 120),
      box: el.parentElement ? el.parentElement.getBoundingClientRect().height : null,
    }));
    const bigText = [...document.querySelectorAll('div,section')]
      .filter((d) => d.children.length <= 3 && (d.innerText || '').length > 40)
      .slice(0, 6).map((d) => (d.innerText || '').replace(/\s+/g, ' ').slice(0, 220));
    return {
      hash: location.hash,
      mainText: (main.innerText || '').replace(/\s+/g, ' ').slice(0, 900),
      mainHtmlLen: main.innerHTML.length,
      loaders, bigText,
      workers: typeof window.Worker,
      testids: [...document.querySelectorAll('[data-testid]')].map((e) => e.getAttribute('data-testid')).slice(0, 40),
    };
  });
  console.log(JSON.stringify(snap, null, 1));
  console.log('\n--- requests (/api/) ---\n' + reqs.join('\n'));
  console.log('\n--- responses ---\n' + resps.join('\n'));
  console.log('\n--- console ---\n' + logs.slice(0, 30).join('\n'));
  await page.screenshot({ path: path.join(__dirname, 'shots', 'master_stall.png'), fullPage: false });
  await browser.close();
  return 0;
})().then((rc) => process.exit(rc)).catch((e) => { console.error('HARNESS ERROR', e); process.exit(1); });
