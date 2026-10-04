/**
 * tools/round78_live_probe.mts — اثباتِ زندهٔ سه رفتارِ Task #78
 *   الف) قیف: پیش از رفتن به Master جای اسکرول + مرحلۀ فعال ثبت می‌شود و پسِ goBack بازمی‌گردد
 *   ب) درخت: pan کریدوردار است (کل نقشه از دید بیرون نمی‌رود) و چرخِ ماوس هنوز زوم می‌کند
 *   ج) دراورِ تنظیمات FTS با Escape بسته می‌شود و اسکرولِ پشتِ آن قفل است
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=... node --experimental-strip-types tools/round78_live_probe.mts \
 *     --url http://127.0.0.1:8002/ --out _audit/round78_live.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/round78_live.json');
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) {
  const { ensureChromium } = await imp('src/browser-setup.ts');
  await ensureChromium();
}

const results: Record<string, unknown> = { base: BASE, checks: [] as Record<string, unknown>[] };
const push = (name: string, ok: boolean, detail: unknown) => {
  (results.checks as Record<string, unknown>[]).push({ name, ok, detail });
  console.log(`${ok ? 'OK  ' : 'FAIL'} ${name}${ok ? '' : ' :: ' + JSON.stringify(detail).slice(0, 240)}`);
};

const browser = await chromium.launch({
  executablePath: CHROME || undefined,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const page = await browser.newPage({ viewport: { width: 1366, height: 900 } });
await page.addInitScript(() => {
  try {
    sessionStorage.setItem('bors_auth_session', 'true');
  } catch {
    /* پوستهٔ بدونِ دروازه */
  }
});

const SNAP_KEY = 'bors.funnel.snapshot.v1';

// ── الف) قیف: ثبت و بازگردانیِ اسکرول ──
await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="funnel-stage-tape"] tbody tr button', { timeout: 40000 });

const preScroll = await page.evaluate(() => {
  const el = document.querySelector('.app-content') as HTMLElement | null;
  const doc = document.scrollingElement as HTMLElement | null;
  const scroller = el && el.scrollHeight > el.clientHeight + 2 ? el : doc;
  if (!scroller) return null;
  scroller.scrollTop = 620;
  return { top: scroller.scrollTop, height: scroller.scrollHeight, client: scroller.clientHeight };
});
const symbolClicked = await page.evaluate(() => {
  // کلیکِ Playwright عنصر را به دید می‌آورد و اسکرولِ تست را صفر می‌کند؛
  // اینجا همان سطرِ قابل‌دید را درِ DOM کلیک می‌کنیم.
  const els = [document.querySelector('.app-content'), document.scrollingElement].filter(Boolean) as HTMLElement[];
  const top = Math.max(0, ...els.map((e) => e.scrollTop));
  const btns = Array.from(document.querySelectorAll('[data-testid="funnel-stage-tape"] tbody tr button')) as HTMLElement[];
  const visible = btns.find((b) => {
    const r = b.getBoundingClientRect();
    return r.top >= 0 && r.bottom <= innerHeight && b.closest('tr') && top > 0;
  });
  const target = visible ?? btns[0];
  if (!target) return null;
  const sym = (target.textContent ?? '').trim();
  target.click();
  return sym;
});
if (!preScroll || preScroll.top < 300 || !symbolClicked) {
  push('قیف: بستری برای اسکرولِ ۶۲۰px فراهم نشد', false, preScroll);
} else {
  // کلیک درِ evaluate انجام شد (بدون scroll-into-viewِ Playwright)
  await page.waitForSelector('[data-testid="master-dossier"], [data-testid="master-fts-details"]', { timeout: 40000 });
  const snap = await page.evaluate((k) => sessionStorage.getItem(k), SNAP_KEY);
  const snapObj = snap ? JSON.parse(snap) : null;
  push(
    'قیف: پیش از رفتن، مرحلۀ فعال و scroll ثبت شد',
    !!snapObj && snapObj.stage === 'tape' && snapObj.scroll >= 300,
    snapObj,
  );
  await page.goBack({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="funnel-stage-tape"] tbody tr', { timeout: 40000 });
  let restored: number | null = null;
  for (let i = 0; i < 60 && restored === null; i++) {
    restored = await page.evaluate(() => {
      const els = [document.querySelector('.app-content'), document.scrollingElement].filter(Boolean) as HTMLElement[];
      const top = Math.max(0, ...els.map((e) => e.scrollTop));
      return top >= 300 ? top : -1;
    });
    if (restored !== null && restored >= 0 && restored >= 300) break;
    restored = null;
    await page.waitForTimeout(200);
  }
  push('قیف: پس از Back اسکرولِ همان‌جا بازمی‌گردد', restored !== null && restored >= 300, { restored });
  const snapAfter = await page.evaluate((k) => sessionStorage.getItem(k), SNAP_KEY);
  push('قیف: snapshot مصرف‌شده پاک می‌شود', snapAfter === null, snapAfter);
}

// ── ب) درخت: کریدورِ pan و زومِ چرخ ──
await page.goto(`${BASE}#/strategy-tree`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="obsidian-strategy-canvas"]', { timeout: 40000 });
const box = await page.evaluate(() => {
  const el = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
  if (!el) return null;
  const r = el.getBoundingClientRect();
  return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height };
});
if (!box) {
  push('درخت: بوم پیدا نشد', false, null);
} else {
  const gBox = () =>
    page.evaluate(() => {
      const g = document.querySelector('[data-testid="obsidian-strategy-canvas"] g[transform]');
      const c = document.querySelector('[data-testid="obsidian-strategy-canvas"]');
      if (!g || !c) return null;
      const gb = g.getBoundingClientRect();
      const cb = c.getBoundingClientRect();
      const ix = Math.min(gb.right, cb.right) - Math.max(gb.left, cb.left);
      const iy = Math.min(gb.bottom, cb.bottom) - Math.max(gb.top, cb.top);
      return { ix: Math.round(ix), iy: Math.round(iy), transform: g.getAttribute('transform') };
    });
  // drag بسیار بلند: باید داخل کریدور بایستد، نه اینکه نقشه غیب شود
  await page.mouse.move(box.x, box.y);
  await page.mouse.down();
  for (let i = 1; i <= 8; i++) {
    await page.mouse.move(box.x + i * 900, box.y + i * 600);
  }
  await page.mouse.up();
  await page.waitForTimeout(150);
  const afterDrag = await gBox();
  push(
    'درخت: pan تا بی‌نهایت کشیده شود، باز هم ۱۰۰pxِ نقشه در دید می‌ماند',
    !!afterDrag && afterDrag.ix >= 100 && afterDrag.iy >= 100,
    afterDrag,
  );
  // چرخ = زوم (باید مقیاسِ transform تکان بخورد)
  const beforeZoom = await gBox();
  await page.mouse.move(box.x, box.y);
  for (let i = 0; i < 4; i++) {
    await page.mouse.wheel(0, -240);
    await page.waitForTimeout(60);
  }
  await page.waitForTimeout(200);
  const afterZoom = await gBox();
  const scaleOf = (t: string | null) => {
    const m = /scale\(([-0-9.]+)\)/.exec(t ?? '');
    return m ? Number.parseFloat(m[1]) : 1;
  };
  const z0 = scaleOf(beforeZoom?.transform ?? '');
  const z1 = scaleOf(afterZoom?.transform ?? '');
  push('درخت: چرخِ ماوس همچنان زوم می‌کند', z1 > z0 + 0.05, { z0, z1 });
  const stillVisible = afterZoom && afterZoom.ix >= 100 && afterZoom.iy >= 100;
  push('درخت: پسِ زوم هم محتوا از کریدور بیرون نیست', !!stillVisible, afterZoom);
}

// ── ج) Escape و قفلِ اسکرول درِ دراورِ بنیادی ──
await page.goto(`${BASE}#/fundamental`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="fts-settings-trigger"]', { timeout: 40000 });
await page.click('[data-testid="fts-settings-trigger"] button');
await page.waitForTimeout(350);
const drawerOpen = await page.evaluate(() => {
  const p = document.querySelector('[data-testid="fts-settings-panel"]');
  return {
    open: !!p && p.getAttribute('aria-hidden') !== 'true',
    bodyLocked: document.body.style.overflow === 'hidden',
    focusInside: !!p && p.contains(document.activeElement),
  };
});
push('دراور: با کلیک باز می‌شود، focus داخلش و اسکرول قفل', drawerOpen.open && drawerOpen.bodyLocked && drawerOpen.focusInside, drawerOpen);
await page.keyboard.press('Escape');
await page.waitForTimeout(350);
const drawerClosed = await page.evaluate(() => {
  const p = document.querySelector('[data-testid="fts-settings-panel"]');
  return {
    closed: !!p && p.getAttribute('aria-hidden') === 'true',
    bodyUnlocked: document.body.style.overflow !== 'hidden',
  };
});
push('دراور: Escape می‌بندد و قفلِ اسکرول آزاد می‌شود', drawerClosed.closed && drawerClosed.bodyUnlocked, drawerClosed);

await browser.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(results, null, 1), 'utf8');
const failed = (results.checks as { ok: boolean }[]).filter((c) => !c.ok).length;
console.log(`\n${(results.checks as unknown[]).length} سنجش — ${failed} ناکام`);
process.exit(failed ? 1 : 0);
