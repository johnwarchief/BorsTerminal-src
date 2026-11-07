/**
 * چرا در پنجرۀ ۹۰ ثانیه‌ای هر مسیر فقط یک بار پرسیده شد؟
 *
 * این اسکرپت فقط تشخیص است (نه ابزارِ مأموریت): زمانِ هر درخواست /api،
 * وضعیتِ visibility/focusِ صفحه، و شمارشِ ردیف با سلکتورهایِ مختلف.
 */
import { createRequire } from 'node:module';
import { writeFileSync } from 'node:fs';

const req = createRequire('C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-ui/frontend/index.js');
const { chromium } = req('playwright-core');

const BASE = (process.argv[2] || 'http://127.0.0.1:8020').replace(/\/$/, '');
const SECONDS = Number(process.argv[3] || '70');
const ROUTE = process.argv[4] || '/market';

const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
});
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();

const hits: Array<{ t: number; path: string; status: number; inm: boolean; xc: string }> = [];
const t0 = Date.now();
page.on('response', (res) => {
  const u = res.url();
  if (!u.includes('/api/')) return;
  hits.push({ t: Date.now() - t0, path: u.replace(BASE, '').split('?')[0],
    status: res.status(), inm: Boolean(res.request().headers()['if-none-match']),
    xc: res.headers()['x-cache'] ?? '' });
});

await page.goto(BASE + ROUTE, { waitUntil: 'networkidle' });
const marks: Array<{ t: number; visibility: string; focus: boolean; rows: Record<string, number> }> = [];
for (let i = 0; i < Math.ceil(SECONDS / 10); i++) {
  await page.waitForTimeout(10_000);
  marks.push(await page.evaluate(() => ({
    visibility: document.visibilityState, focus: document.hasFocus(),
    hidden: document.hidden,
    rows: {
      'tbody tr': document.querySelectorAll('tbody tr').length,
      '[role=row]': document.querySelectorAll('[role=row]').length,
      '.group.cursor-pointer': document.querySelectorAll('.group.cursor-pointer').length,
      a_href_asset: document.querySelectorAll('a[href*="/asset/"]').length,
    },
  })));
}
writeFileSync(process.argv[5] || 'poll-diag.json', JSON.stringify(
  { base: BASE, route: ROUTE, seconds: SECONDS, hits, marks }, null, 2), 'utf8');
console.log('requests:');
for (const h of hits) console.log(`  +${String(h.t).padStart(5)}ms ${h.path} ${h.status} inm=${h.inm} xc=${h.xc}`);
console.log('page state samples:');
for (const m of marks) console.log(' ', JSON.stringify(m));
await browser.close();
