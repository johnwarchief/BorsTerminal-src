/**
 * tools/tape_five_filters_matrix_probe.mts — ماتریسِ «هر کنترلِ پنج فیلتر ← اثرِ واقعی»
 *
 * برای هر یک از پنج فیلترِ جزوه: چیپ روشن، شمارۀ وعدۀ چیپ و شمارندۀ جدول ثبت می‌شود؛
 * سپس هر کنترلِ داخلِ پاپ‌اور ⚙ (اسلایدر / چک‌باکس / دکمۀ حالت) یک‌بار operated و
 * یک‌بار برگردانده می‌شود و همان دو عدد دوباره خوانده می‌شوند. کنترلی که هیچ‌کدام را
 * تکان ندهد در `dead` فهرست می‌شود. هیچ داوری‌ای از کد نمی‌شود — فقط از DOM.
 *
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types \
 *     tools/tape_five_filters_matrix_probe.mts --url http://127.0.0.1:8002/ --out _audit/tmp/five_matrix.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const BASE = arg('url', 'http://127.0.0.1:8002/').replace(/\/$/, '');
const OUT = arg('out', '_audit/tmp/five_matrix.json');
const WAIT = Number.parseInt(arg('wait', '13000'), 10);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 900 } });
await ctx.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* noop */
  }
});
const page = await ctx.newPage();
const errors: string[] = [];
page.on('console', (m: any) => {
  if (m.type() === 'error') errors.push(String(m.text()).slice(0, 200));
});

const FILTERS: Array<{ key: string; label: string }> = [
  { key: 'f_clock', label: 'الگوی ساعت' },
  { key: 'f_susp', label: 'حجم مشکوک' },
  { key: 'f_jet', label: 'فیلتر جت' },
  { key: 'f_roobi', label: 'کف‌روبی' },
  { key: 'f_noqteh', label: 'نقطه زنی' },
];

const STATE = (label: string) => {
  const counter = document.querySelector('[title="تعداد نمادهای فعال در جدول"]');
  const chipBtns = Array.from(
    document.querySelectorAll('[data-testid="quick-filters-bar"] button[aria-pressed]'),
  ) as HTMLElement[];
  const chip = chipBtns.find((b) => (b.textContent || '').startsWith(label));
  const promised = chip ? (chip.textContent || '').match(/\(\s*([\d\u06F0-\u06F9٬]+)\s*\)/) : null;
  return {
    shown: counter ? (counter.textContent || '').replace(/\s+/g, ' ').trim() : null,
    promised: promised ? promised[1] : null,
    pressed: chip ? chip.getAttribute('aria-pressed') : null,
    rendered: document.querySelectorAll('[data-testid="tape-row"]').length,
  };
};
const read = (label: string) => page.evaluate(STATE, label);

const chipLocator = (label: string) =>
  page.locator(`[data-testid="quick-filters-bar"] button[aria-pressed]:has-text("${label}")`).first();
const gearLocator = (label: string) =>
  page.locator(`[data-testid="quick-filters-bar"] button[aria-label="تنظیمات ${label}"]`).first();

const out: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), filters: {}, dead: [] };

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT);
out.baseline = await read('الگوی ساعت');

for (const { key, label } of FILTERS) {
  const entry: Record<string, unknown> = { key, controls: [] };

  await chipLocator(label).click();
  await page.waitForTimeout(1100);
  entry.withChip = await read(label);

  await gearLocator(label).click();
  await page.waitForTimeout(700);
  entry.dialogOpen = await page.locator('[role="dialog"]').count();

  const sliders = await page.locator('[role="dialog"] input[type="range"]').all();
  const checks = await page.locator('[role="dialog"] input[type="checkbox"]').all();
  const modeButtons = await page
    .locator('[role="dialog"] button')
    .filter({ hasNotText: /بازنشانی|✕|فعال|خاموش/ })
    .all();
  entry.counts = {
    sliders: sliders.length,
    checkboxes: checks.length,
    modeButtons: modeButtons.length,
  };

  const step = async (kind: string, idx: number, name: string, operate: () => Promise<void>, revert: () => Promise<void>) => {
    const rec: Record<string, unknown> = { kind, idx, name };
    try {
      const before = await read(label);
      await operate();
      await page.waitForTimeout(1100);
      const after = await read(label);
      rec.before = { promised: before.promised, shown: before.shown };
      rec.after = { promised: after.promised, shown: after.shown };
      rec.effective = before.promised !== after.promised || before.shown !== after.shown;
      await revert();
      await page.waitForTimeout(800);
      const back = await read(label);
      rec.reverted = { promised: back.promised, shown: back.shown };
      rec.revertOk = back.promised === before.promised && back.shown === before.shown;
    } catch (e) {
      rec.error = String(e).slice(0, 160);
    }
    (entry.controls as unknown[]).push(rec);
  };

  const nameOf = async (el: any) => {
    const info = await el.evaluate((n: any) => {
      const label =
        n.getAttribute('aria-label') ||
        n.closest('label')?.textContent ||
        n.parentElement?.querySelector('span')?.textContent ||
        n.nextElementSibling?.textContent ||
        '';
      return {
        label: (label || '').replace(/\s+/g, ' ').trim().slice(0, 46),
        value: n.value ?? n.textContent ?? '',
        min: n.min ?? null,
        max: n.max ?? null,
        type: n.type ?? '',
      };
    });
    return info;
  };

  for (let i = 0; i < sliders.length; i += 1) {
    const s = sliders[i];
    const meta = await nameOf(s);
    await step('slider', i, String(meta.label), async () => {
      await s.evaluate((el: any) => {
        const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        const min = Number(el.min || '0');
        const max = Number(el.max || '10');
        const cur = Number(el.value || '0');
        const next = cur > (min + max) / 2 ? min : max;
        set?.call(el, String(next));
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
    }, async () => {
      await s.evaluate((el: any) => {
        const set = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value')?.set;
        const min = Number(el.min || '0');
        const max = Number(el.max || '10');
        const cur = Number(el.value || '0');
        const back = cur === Number(el.min || '0') ? max : min;
        set?.call(el, String(back === cur ? cur : back));
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
      });
    });
  }

  for (let i = 0; i < checks.length; i += 1) {
    const c = checks[i];
    const meta = await nameOf(c);
    await step('checkbox', i, String(meta.label), () => c.click({ force: true }), () =>
      c.click({ force: true }),
    );
  }

  for (let i = 0; i < Math.min(modeButtons.length, 8); i += 1) {
    const b = modeButtons[i];
    const meta = await nameOf(b);
    const txt = String(meta.label || '').trim();
    if (!txt) continue;
    await step('button', i, txt, () => b.click({ timeout: 3000 }), () => b.click({ timeout: 3000 }));
  }

  // بستنِ پاپ‌اور و خاموش‌کردنِ چیپ تا فیلتر بعدی تمیز سنجیده شود
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const stillOn = (await read(label)).pressed;
  if (stillOn === 'true') await chipLocator(label).click();
  await page.waitForTimeout(700);
  entry.afterCleanup = await read(label);

  (out.filters as Record<string, unknown>)[key] = entry;
  for (const c of entry.controls as Array<Record<string, unknown>>) {
    if (c.effective === false) {
      (out.dead as Array<unknown>).push({ filter: label, kind: c.kind, idx: c.idx, name: c.name });
    }
  }
}

out.errors = errors.slice(0, 8);
mkdirSync('_audit/tmp', { recursive: true });
writeFileSync(OUT, JSON.stringify(out, null, 2), 'utf-8');
console.log('WROTE', OUT, 'dead:', JSON.stringify(out.dead));
await browser.close();
