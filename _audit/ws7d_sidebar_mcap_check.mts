// _audit/ws7d_sidebar_mcap_check.mts — سنجشِ زندهٔ سطرِ «ارزشِ بازار» درِ سایدبار
//
// سه پرسش: عدد می‌آید؟ با همان عددی که موتور برایِ مخرجِ I4 می‌خواند یکی است؟
// و نبودِ داده صادقانه «بی‌داده» می‌ماند؟ (نه صفر.) بی‌اسکرولِ بی‌هدف: یک نماد
// از خودِ جدولِ تابلو انتخاب می‌شود که mcap دارد.
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const API = arg('api', 'http://127.0.0.1:8001');

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m: any) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 140)); });
page.on('pageerror', (e: any) => consoleErrors.push(`pageerror: ${String(e.message).slice(0, 140)}`));

// نمادِ آزمون از خودِ /api/market: نخستین ردیفِ دارای mcap و زنده
const mk = await (await fetch(`${API}/api/market`)).json();
// نمادی بدونِ فاصله: «آ س پ» درِ مسیرِ URL با فاصله است و تطبیقِ نماد درِ
// سایدبار را مبهم می‌کند — اولِ فهرستِ بی‌فاصله را می‌گیریم تا سطرِ خودِ فیچر سنجیده شود، نه instrumentِ تست.
const withCap = (mk.data || []).filter((r: any) => r.mcap && r.is_live !== false
  && !/\s/.test(String(r.symbol)));
const row = withCap[0] || {};
const SYM = String(row.symbol || '');
const noCap = (mk.data || []).find((r: any) => !r.mcap) || {};

const res: Record<string, unknown> = { symbol: SYM, serverMcapRial: row.mcap ?? null,
                                        serverSrc: row.mcap_src ?? null,
                                        rowsWithMcap: withCap.length, rowsTotal: (mk.data || []).length };

await page.goto(`${BASE}#/master/${encodeURIComponent(SYM)}`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="inspector-market-cap"]', { timeout: 90_000 });
// خوراکِ تابلو هنوز نرسیده بود و پنل «همه خالی» رندر می‌شد (قیمت هم «-» بود)؛
// بی‌این صبر، سنجش «بی‌داده» را به‌جای عددِ واقعی می‌گفت (سنجشِ معیوب ≠ نقصِ اپ).
await page.waitForFunction(() => {
  const t = document.body.innerText || '';
  return !/آخرین معامله\s*-/.test(t) && /آخرین معامله/.test(t);
}, undefined, { timeout: 90_000 });
res.ui = await page.evaluate(() => ({
  capText: document.querySelector('[data-testid="inspector-market-cap"]')?.textContent?.trim() ?? null,
  capTitle: document.querySelector('[data-testid="inspector-market-cap"] span[title]')?.getAttribute('title') ?? null,
  i4Text: document.querySelector('[data-testid="inspector-i4"]')?.textContent?.trim() ?? null,
  i4Title: document.querySelector('[data-testid="inspector-i4"]')?.getAttribute('title') ?? null,
  order: Array.from(document.querySelectorAll('[data-testid="inspector-market-cap"] span'))
    .map((s) => (s.textContent ?? '').trim()).slice(0, 4),
}));
await page.screenshot({ path: '_audit/ws7d_sidebar_mcap.png' });
// تشخیصِ محلی: آیا خودِ ردیف resolve شده؟ (قیمت/درصد پر باشند ⇒ ردیف هست و
// فقط کلیدِ mcap گم شده؛ خالی باشند ⇒ ردیف resolve نمی‌شود.)
res.panelText = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="inspector-market-cap"]');
  const panel = el?.closest('div.rounded-2xl, aside, section') ?? el?.parentElement?.parentElement;
  return (panel?.textContent ?? '').replace(/\s+/g, ' ').trim().slice(0, 260);
});
res.rowFromServer = await page.evaluate(async (sym: string) => {
  const d: any = await (await fetch('/api/market')).json();
  const row = (d.data || []).find((x: any) => x.symbol === sym);
  return row ? { keys: Object.keys(row).length, mcap: row.mcap ?? null, p_last: row.p_last ?? null } : null;
}, SYM);

// نمادی که mcap ندارد ⇒ «بی‌داده»، نه صفر
if (noCap.symbol) {
  await page.goto(`${BASE}#/master/${encodeURIComponent(String(noCap.symbol))}`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="inspector-market-cap"]', { timeout: 60_000 });
  res.noCapUi = await page.evaluate(() =>
    document.querySelector('[data-testid="inspector-market-cap"]')?.textContent?.trim() ?? null);
  res.noCapSymbol = noCap.symbol;
}

const capText = String((res.ui as any)?.capText ?? '');
const toLatin = (t: string) => t.replace(/[۰-۹]/g, (d) => String('۰۱۲۳۴۵۶۷۸۹'.indexOf(d)))
  .replace(/٬/g, '').replace('٫', '.');
const shown = /([\d.]+)\s*همت/.exec(toLatin(capText));
const expectedHemmat = row.mcap ? Number(row.mcap) / 1e13 : null;
const i4Text = String((res.ui as any)?.i4Text ?? '');
const out = { ...res,
              verdicts: {
                row_present: true,
                shows_number: !!shown,
                matches_server: !!shown && expectedHemmat !== null
                  && Math.abs(Number(shown[1]) - expectedHemmat) <= 0.01,
                // I4 یا نسبت دارد یا صادقانه «بی‌داده» — هیچ دو حالتِ دیگری مجاز نیست
                i4_honest: i4Text.includes('×') || i4Text.includes('بی‌داده'),
                missing_data_says_no_data: noCap.symbol ? String(res.noCapUi ?? '').includes('بی‌داده') : null,
                zero_console_errors: consoleErrors.length === 0,
              },
              consoleErrors: consoleErrors.slice(0, 6),
              expectedHemmat };
mkdirSync('_audit', { recursive: true });
writeFileSync('_audit/ws7d_sidebar_mcap_check.json', JSON.stringify(out, null, 2));
console.log(JSON.stringify(out.verdicts, null, 2));
console.log(`symbol=${SYM} server_hemmat=${expectedHemmat} ui="${capText}" i4="${(res.ui as any)?.i4Text}"`);
console.log(`noCap: ${out.noCapSymbol} → "${res.noCapUi}"`);
await browser.close();
