// _audit/funnel_toggle_roundtrip.mts -- «خودم چک می‌کنم» → «رد می‌کند» در یک پنجرۀ کوتاه
//   عددهایِ قبلِ کلید و بعدِ برگشت باید عیناً یکی باشند؛ پنجره کوتاه است تا
//   لغزشِ خودِ تابلو (فیدِ زنده) با رفتارِ کلید اشتباه نشود.
import { writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR!;
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
const errs: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') errs.push(m.text().slice(0, 140)); });
await page.goto('http://127.0.0.1:8001/#/master', { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-technical"]', { timeout: 60_000 });
await page.waitForTimeout(11_000);

const snap = () => page.evaluate(() => {
  const one = (k: string) => {
    const el = document.querySelector(`[data-testid="funnel-stage-${k}"]`);
    return {
      n: el ? el.querySelectorAll('tbody tr[data-fkey]').length : -1,
      chip: el?.querySelector('[data-testid^="funnel-rejected-"]')?.textContent?.trim() ?? null,
      pend: el?.querySelector('[data-testid^="funnel-pending-"]')?.querySelectorAll('tbody tr[data-fkey]').length ?? 0,
    };
  };
  return {
    tape: one('tape'), tech: one('technical'), fund: one('fundamental'), hand: one('handover'),
    screens: document.querySelector('[data-testid="funnel-tech-screens"]')?.getAttribute('aria-pressed'),
    self: document.querySelector('[data-testid="funnel-tech-selfcheck"]')?.getAttribute('aria-pressed'),
    clock: new Date().toLocaleTimeString('en-GB'),
  };
});

const t0 = await snap();
await page.click('[data-testid="funnel-tech-selfcheck"]'); await page.waitForTimeout(900);
const t1 = await snap();
await page.click('[data-testid="funnel-tech-screens"]');  // برگشت به «رد می‌کند»
await page.waitForTimeout(900);
const t2 = await snap();

const rowsWithMark = await page.evaluate(() => {
  const trs = [...document.querySelectorAll('[data-testid="funnel-stage-technical"] tbody tr[data-fkey]')];
  return trs.map((t) => ({ s: t.getAttribute('data-fkey'), mark: t.children[4]?.textContent?.trim() })).filter((r) => r.mark === 'رد').length;
});

writeFileSync('_audit/funnel_toggle_roundtrip.json', JSON.stringify({ t0, t1, t2, rowsRejectedNow: rowsWithMark, errors: errs }, null, 1), 'utf-8');
const fmt = (n: string, s: any) => `${n} ${s.clock} | تابلو ${s.tape.n} | تکنیکال ${s.tech.n} (چیپ ${s.tech.chip ?? '-'}) | بنیادی ${s.fund.n} (انتظار ${s.fund.pend}) | تحویل ${s.hand.n} | screens=${s.screens} selfcheck=${s.self}`;
console.log(fmt('قبل   ', t0));
console.log(fmt('خودم  ', t1));
console.log(fmt('برگشت ', t2));
console.log('ردِ صریح درِ مرحلۀ تکنیکال (با «رد می‌کند»):', rowsWithMark);
console.log('برگشت = حالتِ اول؟', JSON.stringify({ ...t0, clock: 0 }) === JSON.stringify({ ...t2, clock: 0 }) ? 'بله' : 'خیر');
console.log('console errors:', errs.length);
await browser.close();
