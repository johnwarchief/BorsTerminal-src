/* _audit/card_jev.mts — سنجشِ زندهٔ کارت‌های پنج‌شاخص درِ مرورگر (#200/#201/#203/#204/#205)
 *
 * چرا این پروب هست: ویتست منطق و کلاس‌ها را ثابت می‌کند، ولی نمی‌گوید رویِ
 * ۱۹۲۰×۱۰۸۰ واقعی کارت‌ها چند پیکسل عرض دارند، متن جایی بریده می‌شود یا نه،
 * نمودارک پیکسل می‌گیرد یا نه، و بنرِ رد چه متنی می‌نویسد. همهٔ این‌ها فقط درِ
 * پیکسل دیده می‌شوند. هیچ متنی به سرویسِ بیرونی نمی‌رود — فقط Playwright.
 *
 *   JEV_CHROME=... node --experimental-strip-types _audit/card_jev.mts
 */
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const require = createRequire(pathToFileURL(PKG + '/index.js').href);
const { chromium } = require('playwright');

const BASE = process.env.BORS_URL ?? 'http://127.0.0.1:8001/';
const CARDS = ['1_growth', '2_eps_trend', '3_gross_margin', '4_sales_to_mcap', '5_industry'];

const browser = await chromium.launch({
  executablePath: process.env.JEV_CHROME || undefined,
  args: ['--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* دروازه فقط UI است */
  }
});
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m) => {
  if (m.type() === 'error') errors.push(m.text().slice(0, 200));
});
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`.slice(0, 200)));

/** یک نمادِ مردود از خودِ سرور پیدا می‌شود تا بنرِ «علتِ رد» هم سنجیده شود */
await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(14000);
const probe = await page.evaluate(async (sample: number) => {
  const r = await fetch('/api/market', { headers: { Accept: 'application/json' } });
  const j = await r.json();
  const rows: { symbol?: string }[] =
    (j as { rows?: { symbol?: string }[] }).rows ??
    (Object.values(j as Record<string, unknown>).find(
      (v) => Array.isArray(v) && v.length && (v[0] as Record<string, unknown>).symbol,
    ) as { symbol?: string }[]);
  const picked: string[] = [];
  for (let i = 0; i < rows.length && picked.length < sample; i += 137) {
    const s = rows[i]?.symbol;
    if (s) picked.push(s);
  }
  const found: { symbol: string; score: number | null; verdict: string | null }[] = [];
  for (const s of picked) {
    try {
      const c = await (await fetch(`/api/fundamental/${encodeURIComponent(s)}`)).json();
      // مردودِ «عدددار»: هم حاشیه دارد هم سابقۀ EPS، تا علتِ رد با رقم و
      // نمودارک هر دو رویِ یک نمادِ واقعی سنجیده شوند
      if (
        c && typeof c.score === 'number' && c.score < 3 && !c.excluded &&
        c.indicators?.['3']?.margin_pct != null && (c.indicators?.['2']?.eps_series ?? []).length >= 2
      )
        found.push({ symbol: s, score: c.score, verdict: c.verdict ?? null });
      if (found.length >= 2) break;
    } catch {
      /* یک نمادِ بی‌کارت نباید پروب را بخواباند */
    }
  }
  return { candidates: picked.length, found };
}, 60);

const report: Record<string, unknown> = { base: BASE, probe, cards: {}, banners: {}, shots: [] };

for (const sym of probe.found.length
  ? probe.found.slice(0, 1).map((f: { symbol: string }) => f.symbol)
  : ['شفارس']) {
  await page.goto(`${BASE}#/fundamental/${encodeURIComponent(sym)}`, {
    waitUntil: 'domcontentloaded',
    timeout: 60000,
  });
  await page.waitForTimeout(9000);
  const one = await page.evaluate((keys: string[]) => {
    const box = (el: Element | null) => {
      const b = el?.getBoundingClientRect();
      return b ? { w: Math.round(b.width), h: Math.round(b.height), top: Math.round(b.top) } : null;
    };
    const clipped = (el: Element | null) =>
      el ? Array.from(el.querySelectorAll<HTMLElement>('*')).filter((n) => n.scrollWidth - n.clientWidth > 2).length : -1;
    const cards: Record<string, unknown> = {};
    for (const k of keys) {
      const el = document.querySelector(`[data-testid="fts-card-cell-${k}"]`);
      cards[k] = { box: box(el), clippedDescendants: clipped(el) };
    }
    return {
      cards,
      sparks: {
        eps: !!document.querySelector('[data-testid="fts-spark-eps"]'),
        margin: !!document.querySelector('[data-testid="fts-spark-margin"]'),
        epsBars: document.querySelectorAll('[data-testid="fts-spark-eps"] rect').length,
        marginPts: document.querySelectorAll('[data-testid="fts-spark-margin"] circle').length,
        heights: Array.from(document.querySelectorAll('[data-testid^="fts-spark-"] svg')).map((s) => s.getAttribute('height')),
      },
      badges: {
        audit: document.querySelectorAll('[data-testid^="fts-cell-audit-"]').length,
        drill: document.querySelectorAll('[data-testid="fts-drill-affordance"]').length,
        infoGlyph: (document.querySelector('[data-testid="fts-card-cell-2_eps_trend"]')?.textContent ?? '').includes('ⓘ'),
      },
      banner: {
        text: (document.querySelector('[data-testid="fts-strategy-summary"]')?.textContent ?? '').replace(/\s+/g, ' ').slice(0, 700),
        reasons: (document.querySelector('[data-testid="fts-reject-reasons"]')?.textContent ?? '').replace(/\s+/g, ' ').slice(0, 700),
      },
    };
  }, CARDS);
  report.cards[sym] = one;
  const shot = `_audit/card_jev_${sym}.png`;
  await page.screenshot({ path: shot, fullPage: false });
  report.shots = [...(report.shots as string[]), shot];
}

report.errors = errors.slice(0, 10);
writeFileSync('_audit/card_jev.json', JSON.stringify(report, null, 1), 'utf8');
console.log(JSON.stringify(report, null, 1));
await browser.close();
