/**
 * tools/ui_polish_probe.mts — اثباتِ زندهٔ دو اصلاحِ رابط (بندِ ۳ مأموریتِ رابط)
 *
 * دو پاس رویِ **همان باندلِ تازه** و همان دادهٔ زنده:
 *  پاس A — هیچ چیزی دست‌کاری نشده: ردیف‌های واقعی قیف اندازه گرفته می‌شوند
 *    (`clientWidth` در برابرِ `scrollWidth`ِ متنِ نام، اورفلوی افقیِ صفحه) و
 *    پنلِ چپ با کارتِ canonicalِ همان نماد سنجیده می‌شود (مقدارِ واقعی، «—»
 *    بی‌مقدار، اسکرولِ مستقل، کلیکِ کارت ⇒ `fts-drilldown-N` موجود).
 *  پاس B — حالتِ «برچسبِ بلند»: پاسخِ `/api/funnel` درِ لایۀ شبکه گیر می‌آید و
 *    رویِ چند ردیف `fund_caveat`/`assembly_veto` روشن می‌شود (همان «عبور با
 *    ملاحظات»ِ ۱۴ نویسه‌ای که باگِ گزارش‌شده نام را به «…» می‌کوبید). این
 *    **دست‌کاریِ ورودیِ رندر است، نه دادهٔ محصول**: بدنهٔ واقعی از همان
 *    بک‌اند می‌آید و فقط پرچمِ نمایشیِ همان ردیف‌ها عوض می‌شود تا رابط درِ
 *    بدترین حالتِ برچسب اندازه گرفته شود. شمارۀ نمادها و بقیۀ مقادیر عوض
 *    نمی‌شوند.
 *
 * usage:
 *   MSYS_NO_PATHCONV=1 JEV_CHROME=.../chrome.exe \
 *   node --experimental-strip-types tools/ui_polish_probe.mts \
 *     --url http://127.0.0.1:8013/ --w 1366 --h 768 --out _audit/live-ui/polish-1366.json
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const BASE = arg('url', 'http://127.0.0.1:8013/').replace(/\/$/, '');
const W = Number.parseInt(arg('w', '1366'), 10);
const H = Number.parseInt(arg('h', '768'), 10);
const OUT = resolve(arg('out', `_audit/live-ui/polish-${W}x${H}.json`));
/** چند ردیف اول درِ پاس B برچسبِ بلند می‌گیرند */
const MARK_FIRST = Number.parseInt(arg('mark-first', '6'), 10);

const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const context = await browser.newContext({ viewport: { width: W, height: H } });
await context.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
});
const page = await context.newPage();

const errors: string[] = [];
const api: { url: string; status: number }[] = [];
page.on('console', (m: any) => { if (m.type() === 'error') errors.push(String(m.text()).slice(0, 220)); });
page.on('pageerror', (e: any) => errors.push(`pageerror: ${String(e.message).slice(0, 220)}`));
page.on('response', (r: any) => {
  const u: string = r.url();
  if (u.includes('/api/fundamental/') || u.includes('/api/screener') || u.includes('/api/funnel')) {
    api.push({ url: u.replace(BASE, ''), status: r.status() });
  }
});

const MEASURE_ROWS = `(() => {
  const rows = Array.from(document.querySelectorAll('tr[data-fkey]')).slice(0, 80);
  const out = [];
  for (const tr of rows) {
    const sym = tr.getAttribute('data-fkey') || '';
    const td = tr.querySelector('td');
    if (!td) continue;
    const btn = td.querySelector('button');
    const spans = btn ? Array.from(btn.querySelectorAll('span')) : [];
    const name = spans.find((s) => (s.textContent || '').trim() === sym.trim());
    const chips = Array.from(td.querySelectorAll('[data-testid^="funnel-fund-caveat-"], [data-testid^="funnel-assembly-veto-"]'));
    if (!name) { out.push({ sym, found: false }); continue; }
    const cs = getComputedStyle(name);
    const nr = name.getBoundingClientRect();
    out.push({
      sym,
      found: true,
      text: (name.textContent || '').trim(),
      clientWidth: name.clientWidth,
      scrollWidth: name.scrollWidth,
      clipped: name.scrollWidth > name.clientWidth + 1,
      overflow: cs.overflow + '/' + cs.textOverflow,
      whiteSpace: cs.whiteSpace,
      nameLines: Math.round(nr.height / (parseFloat(cs.lineHeight) || 14)),
      chipCount: chips.length,
      chipInsideNameButton: chips.some((ch) => btn.contains(ch)),
      marksLine: !!td.querySelector('[data-testid^="funnel-row-marks-"]'),
      rowHeight: Math.round(tr.getBoundingClientRect().height),
      nameRightOfCell: Math.round(nr.right - td.getBoundingClientRect().right),
    });
  }
  const de = document.documentElement;
  const sc = document.querySelector('[data-testid^="funnel-scroll-"]');
  return {
    tableScroll: sc ? { clientW: sc.clientWidth, scrollW: sc.scrollWidth,
                        canScrollX: sc.scrollWidth > sc.clientWidth + 1 } : null,
    rows: out,
    rowCount: out.length,
    pageScrollW: de.scrollWidth,
    innerW: window.innerWidth,
    pageOverflowX: de.scrollWidth > window.innerWidth + 2,
  };
})()`;

let report_stubPicked: string[] = [];
let report_stubMeta: Record<string, unknown> = {};
const report: Record<string, unknown> = {
  generated_at: new Date().toISOString(),
  base: BASE,
  viewport: { width: W, height: H },
  note_passB: 'پاس B فقط پرچمِ نمایشیِ همان ردیف‌ها را درِ لایۀ شبکه روشن می‌کند؛ دادهٔ محصول و باندل دست‌نخورده‌اند',
};

async function waitRows(timeoutMs: number): Promise<boolean> {
  try {
    await page.waitForSelector('tr[data-fkey]', { timeout: timeoutMs });
    return true;
  } catch {
    return false;
  }
}

// ── پاس A: همان‌طور که هست ─────────────────────────────────────────────── #
await page.goto(`${BASE}/#/master`, { waitUntil: 'domcontentloaded', timeout: 60000 });
report.rowsAppearedA = await waitRows(40000);
await page.waitForTimeout(1200);
report.passA = await page.evaluate(MEASURE_ROWS);

// ── پاس B: ردیف‌های عبوری با برچسبِ بلند ────────────────────────────────── #
// بازار بسته است و درِ «جدول فقط عبوری‌ها را نشان می‌دهد» (رأیِ مالک
// ۱۴۰۵-۰۷-۱۹) هیچ ردیفی نمی‌ماند (سنجشِ پاس A: matched=0، رد=1044). برایِ
// اندازه‌گیریِ رابط درِ حالتِ برچسب‌دار، پاسخِ واقعیِ /api/funnel گرفته می‌شود
// و رویِ چند ردیفِ اول فقط دو چیز عوض می‌شود: `status.* = 'pass'` (تا ردیف در
// جدول بنشیند) و پرچم‌هایِ نمایشی `fund_caveat`/`assembly_veto`.
// نامِ نماد و مقدارها عیناً همان است که بک‌اند فرستاده؛ هیچ نماد یا
// عددی از خودِ ساخته نشده.
await page.route('**/api/funnel', async (route: any) => {
  const res = await route.fetch();
  let body: any;
  try {
    body = await res.json();
  } catch {
    await route.fulfill({ response: res });
    return;
  }
  // حکمِ هر گام از `status_matrix[symbol][stage].status` خوانده می‌شود
  // (`funnelView.ts:253-290`)، نه از خودِ ردیف — پس همان‌جا عوض می‌شود.
  const ents = body?.entries || {};
  const matrix = body?.status_matrix || {};
  const pickedSyms: string[] = (ents.tape || [])
    .map((r: any) => r.symbol)
    .filter((s: string) => matrix[s])
    .slice(0, MARK_FIRST);
  pickedSyms.forEach((sym: string, i: number) => {
    for (const key of ['tape', 'technical', 'fundamental', 'handover']) {
      matrix[sym][key] = { ...matrix[sym][key], status: 'pass' };
    }
    for (const key of Object.keys(ents)) {
      const r = (ents[key] || []).find((x: any) => x.symbol === sym);
      if (!r) continue;
      r.fund_caveat = true;                        // «عبور با ملاحظات»
      if (i % 2 === 0) { r.assembly_veto = true; r.assembly_why = 'مجمع ۳ روز دیگر'; }
    }
  });
  report_stubPicked = pickedSyms;
  report_stubMeta = {
    bodyKeys: Object.keys(body || {}),
    tapeEntries: (ents.tape || []).length,
    matrixSize: Object.keys(matrix).length,
    firstMatrixKey: Object.keys(matrix)[0] || null,
    firstTapeSym: (ents.tape && ents.tape[0] && ents.tape[0].symbol) || null,
  };
  await route.fulfill({ status: res.status(), contentType: 'application/json', body: JSON.stringify(body) });
});
// با `goto`ی هم‌نشانی SPA دوباره بارگذاری نمی‌شد و درخواستِ `/api/funnel`
// تکرار نمی‌شد (پس stub هیچ‌وقت اجرا نمی‌شد). reload لازم است.
await page.evaluate(`(() => { const a = sessionStorage.getItem('bors_auth_session'); sessionStorage.clear(); if (a) sessionStorage.setItem('bors_auth_session', a); })()`);
await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
report.rowsAppearedB = await waitRows(40000);
await page.waitForTimeout(1500);
report.passB = await page.evaluate(MEASURE_ROWS);
report.stubMarkedSymbols = report_stubPicked;
report.stubMeta = report_stubMeta;
report.caveatChipsB = await page.$$eval('[data-testid^="funnel-fund-caveat-"]', (els: any[]) =>
  els.slice(0, 10).map((el) => {
    const td = el.closest('td');
    const btn = td ? td.querySelector('button') : null;
    const name = btn ? Array.from(btn.querySelectorAll('span')).find((s: any) => (s.textContent || '').trim() === (td!.parentElement!.getAttribute('data-fkey') || '').trim()) : null;
    return {
      testid: el.getAttribute('data-testid'),
      chipText: (el.textContent || '').trim(),
      chipWidthPx: Math.round(el.getBoundingClientRect().width),
      chipInsideNameButton: btn ? btn.contains(el) : false,
      onMarksLine: !!el.closest('[data-testid^="funnel-row-marks-"]'),
      nameStillThere: !!name,
    };
  })).catch(() => []);
await page.screenshot({ path: OUT.replace(/\.json$/, '-master-labeled.png'), fullPage: false });

// ── پنلِ چپ با کارتِ واقعیِ همان نماد ──────────────────────────────────── #
const picked = await page.evaluate(`(() => {
  const tr = document.querySelector('tr[data-fkey]');
  const btn = tr && tr.querySelector('td button');
  if (btn) btn.click();
  return tr ? (tr.getAttribute('data-fkey') || '') : '';
})()`);
report.pickedSymbol = picked;
await page.waitForSelector('[data-testid="inspector-fts-cards"]', { timeout: 20000 });
await page.waitForTimeout(3000);   // کارتِ تک‌نمادی برسد
report.inspector = await page.evaluate(`(() => {
  const aside = document.querySelector('aside[data-shell="inspector"]');
  const rail = document.querySelector('[data-testid="inspector-fts-cards"]');
  if (!aside || !rail) return { missing: true };
  const cards = Array.from(rail.querySelectorAll('[data-testid^="inspector-card-i"]'));
  const before = aside.scrollTop;
  aside.scrollTop = 99999;
  const after = aside.scrollTop;
  aside.scrollTop = before;
  const de = document.documentElement;
  const y0 = window.scrollY;
  return {
    railCards: cards.length,
    panelScrollHeight: aside.scrollHeight,
    panelClientHeight: aside.clientHeight,
    panelScrollsIndependently: after > before,
    pageScrolledInstead: Math.abs(window.scrollY - y0) > 2,
    pageOverflowX: de.scrollWidth > window.innerWidth + 2,
    asideRect: (() => { const r = aside.getBoundingClientRect(); return { x: Math.round(r.x), w: Math.round(r.width), h: Math.round(r.height) }; })(),
    cards: cards.map((c) => {
      const t = c.querySelector('[data-testid^="inspector-card-verdict-"]');
      const v = c.querySelector('[data-testid^="inspector-ind-"]');
      const r = c.getBoundingClientRect();
      const txt = (c.textContent || '').trim();
      return {
        testid: c.getAttribute('data-testid'),
        href: c.getAttribute('href'),
        value: ((v && v.textContent) || '').trim(),
        verdict: ((t && t.textContent) || '').trim(),
        w: Math.round(r.width),
        h: Math.round(r.height),
        // علتِ بی‌داده یا آستانه، هرچه متنِ خطِ سوم باشد
        tail: txt.slice(((t && t.textContent) || '').length + ((v && v.textContent) || '').length).slice(0, 80),
        lineClamp: c.querySelectorAll('.line-clamp-2').length,
      };
    }),
  };
})()`);
await page.screenshot({ path: OUT.replace(/\.json$/, '-inspector.png'), fullPage: false });

// کلیک رویِ کارت ۳ ⇒ همان پنلِ جزئیات
report.clickedCard3 = await page.evaluate(`(() => {
  const c = document.querySelector('[data-testid="inspector-card-i3"]');
  if (!c) return false;
  c.click();
  return true;
})()`);
let drill3 = false;
try {
  await page.waitForSelector('[data-testid="fts-drilldown-3"]', { timeout: 20000 });
  drill3 = true;
} catch { /* گزارش */ }
report.drilldown3 = {
  opened: drill3,
  location: await page.evaluate('location.href'),
  panelTitle: await page.evaluate(`(() => { const h=document.querySelector('[data-testid="fts-drilldown-3"] h3'); return h?(h.textContent||'').trim():null; })()`),
  panelVisibleRect: await page.evaluate(`(() => { const p=document.querySelector('[data-testid="fts-drilldown-3"]'); if(!p) return null; const r=p.getBoundingClientRect(); return {w:Math.round(r.width),h:Math.round(r.height),top:Math.round(r.top)}; })()`),
};
// اسکرولِ پنل ممکن است یک دورِ رندر بعد از رسیدنِ داده اتفاق بیفتد؛ دوباره
// اندازه گرفته می‌شود تا «به چشم آمدن» با عدد ثابت شود.
await page.waitForTimeout(1500);
report.drilldown3AfterSettle = {
  rect: await page.evaluate(`(() => { const p=document.querySelector('[data-testid="fts-drilldown-3"]'); if(!p) return null; const r=p.getBoundingClientRect(); return {w:Math.round(r.width),h:Math.round(r.height),top:Math.round(r.top),bottom:Math.round(r.bottom)}; })()`),
  scrollY: await page.evaluate('window.scrollY'),
  inViewport: await page.evaluate(`(() => { const p=document.querySelector('[data-testid="fts-drilldown-3"]'); if(!p) return false; const r=p.getBoundingClientRect(); return r.top < window.innerHeight && r.bottom > 0; })()`),
};
await page.screenshot({ path: OUT.replace(/\.json$/, '-drill3.png'), fullPage: false });

// مسیرِ اصلیِ تب بنیادی بی‌پارامتر ⇒ هیچ پنلی باز نیست
await page.goto(`${BASE}/#/fundamental/${encodeURIComponent(String(picked || 'فولاد'))}`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForTimeout(3000);
report.noParamNoPanel = await page.evaluate(
  `document.querySelectorAll('[data-testid^="fts-drilldown-"]').length === 0`);
report.fundamentalPageCards = await page.evaluate(`(() => {
  const cells = Array.from(document.querySelectorAll('[data-testid^="fts-card-cell-"]'));
  return { count: cells.length, text: cells.slice(0, 5).map((c) => (c.textContent || '').replace(/\\s+/g, ' ').trim().slice(0, 70)) };
})()`);

// ── کنترلِ سنسور: همان ردیف با چیدمانِ *پیشین* باید بریده شود ───────────── #
// بی‌این بند، «هیچ ردیفی بریده نشد» می‌تواند یعنیِ پروب کور است. اینجا دقیقاً
// قراردادِ قبلی (نام و برچسب‌ها درِ یک خط با سقفِ 15ch و ellipsis) بازسازی
// می‌شود و اندازه دوباره گرفته می‌شود؛ اگر clipped نشود، سنجشِ بالا بی‌معناست.
await page.goto(`${BASE}/#/master`, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.reload({ waitUntil: 'domcontentloaded', timeout: 60000 });
if (await waitRows(40000)) await page.waitForTimeout(1200);
report.sensorControl = await page.evaluate(`(() => {
  const tr = document.querySelector('tr[data-fkey]');
  if (!tr) return { skipped: 'ردیفی نیست' };
  const td = tr.querySelector('td');
  const btn = td.querySelector('button');
  const sym = tr.getAttribute('data-fkey') || '';
  const name = Array.from(btn.querySelectorAll('span')).find((s) => (s.textContent || '').trim() === sym.trim());
  const marks = td.querySelector('[data-testid^="funnel-row-marks-"]');
  const chips = marks ? Array.from(marks.children) : [];
  const afterNew = name ? { client: name.clientWidth, scroll: name.scrollWidth, clipped: name.scrollWidth > name.clientWidth + 1 } : null;
  btn.style.cssText += ';max-width:15ch;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  if (name) name.style.cssText += ';overflow:hidden;text-overflow:ellipsis;white-space:nowrap';
  chips.forEach((ch) => btn.appendChild(ch));
  const afterOld = name ? { client: name.clientWidth, scroll: name.scrollWidth, clipped: name.scrollWidth > name.clientWidth + 1 } : null;
  return { sym, withNewLayout: afterNew, withOldLayoutRebuilt: afterOld, chipsMoved: chips.length };
})()`);

report.api = api.slice(0, 24);
report.consoleErrors = errors;

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf-8');

const rowsOf = (p: any) => (p && p.rows) || [];
const clippedOf = (p: any) => rowsOf(p).filter((r: any) => r.clipped).map((r: any) => r.sym);
console.log(JSON.stringify({
  viewport: [W, H],
  rowsA: rowsOf(report.passA).length,
  rowsB: rowsOf(report.passB).length,
  clippedA: clippedOf(report.passA),
  clippedB: clippedOf(report.passB),
  chipsInsideNameButtonB: (report.caveatChipsB as any[]).filter((c) => c.chipInsideNameButton).length,
  chipsOnMarksLineB: (report.caveatChipsB as any[]).filter((c) => c.onMarksLine).length,
  pageOverflowX: (report.passB as any)?.pageOverflowX,
  railCards: (report.inspector as any)?.railCards,
  panelScrollsIndependently: (report.inspector as any)?.panelScrollsIndependently,
  cardValues: ((report.inspector as any)?.cards || []).map((c: any) => `${c.testid}=${c.value}/${c.verdict}`),
  drilldown3: (report.drilldown3 as any)?.opened,
  drillTitle: (report.drilldown3 as any)?.panelTitle,
  noParamNoPanel: report.noParamNoPanel,
  consoleErrors: errors.length,
  out: OUT,
}, null, 1));
await browser.close();
