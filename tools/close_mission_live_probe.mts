// tools/close_mission_live_probe.mts — شاهدِ زندهٔ بستنِ مأموریتِ ۱۴۰۵-۰۷-۲۳
//
// چرا این پروب لازم است: گاردهای پایتون و vitest هر دو درِ فرایندِ خودشان
// می‌دوند. سه چیزی که بیِ مرورگرِ واقعی باورکردنی نمی‌ماند:
//   ۱ دروازۀ `/api/execution/*` درِ بیلدِ در حال اجرا واقعاً ۲۰۰ می‌دهد
//      (پیش از امروز ۴۰۴ بود، در حالی که UI همان را صدا می‌زد)
//   ۲ پنلِ سلامتِ کدال با پاسخِ *واقعیِ* بانکِ همین ماشین رندر می‌شود و
//      «بی‌سابقه» را با صفر قاطی نمی‌کند
//   ۳ قفلِ توقفِ اضطراری از مسیرِ HTTP بسته/باز می‌شود و رویِ دیسک می‌ماند
// و یک بازگشتِ لازم: دکمۀ خروجیِ دیدهبان هنوز فایلِ واقعی می‌دهد (پنل جدید
// بالای همان صفحه اضافه شد، پس باید مطمئن شویم چیزی را جابه‌جا یا خفه نکرده).
//
// اجرا (از ریشۀ ریپو، با بک‌اندی که رابطِ buildشده را خودش سرو می‌کند):
//   MSYS_NO_PATHCONV=1 \
//   JEV_CHROME=C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe \
//   node tools/close_mission_live_probe.mts --url http://127.0.0.1:8002/
import { existsSync, mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const BASE = arg('url', 'http://127.0.0.1:8002/');
const OUT = arg('out', '_audit/close_mission_20261014');
const CHROME = process.env.JEV_CHROME ?? '';
if (!CHROME) throw new Error('JEV_CHROME لازم است');
if (!existsSync(CHROME)) throw new Error(`JEV_CHROME وجود ندارد: ${CHROME}`);
mkdirSync(OUT, { recursive: true });

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({
  executablePath: CHROME,
  args: ['--no-sandbox', '--disable-dev-shm-usage'],
});
const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1366, height: 768 } });
await context.addInitScript(() => {
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* بی‌دروازه */ }
});
const page = await context.newPage();
const consoleErrors: string[] = [];
const failedRequests: string[] = [];
page.on('console', (m) => {
  if (m.type() === 'error') {
    const loc = m.location?.() ?? {};
    consoleErrors.push(`${m.text().slice(0, 140)} @ ${String(loc.url ?? '?').slice(0, 70)}:${loc.lineNumber ?? '?'}`);
  }
});
page.on('requestfailed', (r) => failedRequests.push(`${r.method()} ${r.url().slice(0, 80)} ⇒ ${r.failure()?.errorText ?? '?'}`));

const report: Record<string, unknown> = { base: BASE, at: new Date().toISOString() };
const out = (k: string, v: unknown) => { report[k] = v; console.log(`  ${k}: ${JSON.stringify(v)}`); };

// ── ۱) دروازۀ اجرا از همان مبدأِ رابط ──────────────────────────────────────
// `fetch` از صفحهٔ خالی (about:blank) با مبدأی مخصوب مجاز نیست;
// اول خودٔ رابط باز می‌شود تا همان مبدأ داشته باشيم.
await page.goto(BASE, { waitUntil: 'domcontentloaded', timeout: 45_000 });

const door = await page.evaluate(async (base: string) => {
  const r = await fetch(base.replace(/\/$/, '') + '/api/execution/status', { headers: { Accept: 'application/json' } });
  const j = await r.json().catch(() => null);
  return { status: r.status, dryRun: j?.dry_run, live: j?.live_enabled, adapter: j?.adapter,
           kill: j?.kill_switch, auditDb: j?.audit_db ?? j?.audit_db_name ?? null,
           blocked: j?.blocked_on ?? null, recovered: j?.recovered_after_restart };
}, BASE);
out('execution_door', door);

// ── ۲) رفت‌وبرگشتِ قفلِ توقف رویِ HTTP ─────────────────────────────────────
const halt = await page.evaluate(async (base: string) => {
  const post = async (p: string, body: unknown) => {
    const r = await fetch(base.replace(/\/$/, '') + p, {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
    });
    return { code: r.status, json: await r.json().catch(() => null) };
  };
  const h = await post('/api/execution/halt', { reason: 'probe', actor: 'live-probe' });
  const s1 = await (await fetch(base.replace(/\/$/, '') + '/api/execution/status')).json();
  const d = await post('/api/execution/dispatch', { symbol: 'فولاد', side: 'buy', price: 100, quantity: 2, mock_instrument: true });
  const r1 = await post('/api/execution/resume', { reason: 'probe-undo' });
  const s2 = await (await fetch(base.replace(/\/$/, '') + '/api/execution/status')).json();
  return { haltCode: h.code, stateHalted: s1.kill_switch, halted: s1.halted,
           dispatchWhileHalted: { code: d.code, status: d.json?.status, err: d.json?.code },
           resumeCode: r1.code, stateAfter: s2.kill_switch };
}, BASE);
out('kill_switch_roundtrip', halt);

// ── ۳) پنلِ سلامتِ کدال با پاسخِ واقعی ─────────────────────────────────────
await page.goto(BASE.replace(/\/$/, '') + '/#/fundamental', { waitUntil: 'networkidle', timeout: 45_000 });
const strip = await page.evaluate(() => {
  const t = (sel: string) => document.querySelector(`[data-testid="${sel}"]`)?.textContent?.trim() ?? null;
  const el = (sel: string) => document.querySelector(`[data-testid="${sel}"]`);
  const node = el('codal-health-strip');
  return {
    present: !!node,
    state: node?.getAttribute('data-state') ?? null,
    stateText: t('codal-health-state'),
    stateTitle: el('codal-health-state')?.getAttribute('title') ?? null,
    queued: t('codal-health-count-queued'),
    failed: t('codal-health-count-failed'),
    incomplete: t('codal-health-count-incomplete'),
    gap: t('codal-health-count-gap'),
    dirty: t('codal-health-count-dirty'),
    lastSync: t('codal-health-last-sync'),
    lastSyncTitle: el('codal-health-last-sync')?.getAttribute('title') ?? null,
    latinDigitsInCounters: ['codal-health-count-queued', 'codal-health-count-failed',
      'codal-health-count-incomplete', 'codal-health-count-gap', 'codal-health-count-dirty']
      .map((id) => `${id}=${t(id)}`).filter((s) => /[0-9]/.test(s)),
    stripHeightPx: node ? Math.round(node.getBoundingClientRect().height) : null,
  };
});
out('codal_strip', strip);
await page.screenshot({ path: path.join(OUT, 'fundamental_strip_1366.png'), fullPage: false });

// ── ۴) بازگشتِ دیدهبان: دکمۀ خروجی هنوز فایلِ واقعی می‌دهد ────────────────
// اگر فهرستِ رصد خالی باشد دکمه *باید* غیرفعال باشد (count=0 ⇒ دانلود معنی
// ندارد)، پس «نبودِ فایل» چیزی را ثابت نمی‌کند. ردیف‌ها از رابطِ خودِ برنامه
// پر می‌شوند، نه با نوشتنِ مستقیمِ localStorage.
await page.goto(BASE.replace(/\/$/, '') + '/#/watch', { waitUntil: 'networkidle', timeout: 60_000 });
await page.waitForSelector('[data-testid="watch-export"]', { timeout: 30_000 }).catch(() => {});
let watchRows = await page.locator('[data-testid^="watch-row-"]').count();
if (watchRows === 0) {
  for (const sym of ['فولاد', 'وپارس']) {
    await page.fill('[data-testid="watch-add-input"]', sym).catch(() => {});
    await page.click('[data-testid="watch-add-btn"]').catch(() => {});
    await page.waitForTimeout(500);
  }
  await page.reload({ waitUntil: 'networkidle' });
  watchRows = await page.locator('[data-testid^="watch-row-"]').count();
}
out('watchRows', watchRows);
const exportDisabled = await page.locator('[data-testid="watch-export-csv"]').isDisabled().catch(() => null);
const dl = page.waitForEvent('download', { timeout: 25_000 }).catch(() => null);
await page.click('[data-testid="watch-export-csv"]').catch(() => {});
const download = await dl;
let csv: Record<string, unknown> = { taken: false, reason: '', name: '', rows: 0,
                                     bom: false, sep: false, metaLines: 0 };
if (download) {
  const fp = path.join(OUT, 'watch.csv');
  await download.saveAs(fp);
  const buf = await import('node:fs').then((m) => m.readFileSync(fp));
  const text = buf.toString('utf8').replace(/^/, '');
  const rowsTxt = text.split(/\r?\n/).filter((x: string) => x.length > 0);
  csv = { taken: true, reason: '', name: download.suggestedFilename(),
          rows: Math.max(0, rowsTxt.length - 2),
          bom: buf[0] === 0xef && buf[1] === 0xbb && buf[2] === 0xbf,
          sep: rowsTxt[0]?.startsWith('sep=;') === true,
          metaLines: rowsTxt.filter((x: string) => x.startsWith('#')).length,
          dataCount: await page.locator('[data-testid="watch-export"]').getAttribute('data-count') };
} else {
  csv.reason = exportDisabled ? 'button disabled (count=0)' : 'enabled but no download event';
  csv.dataCount = await page.locator('[data-testid="watch-export"]').getAttribute('data-count').catch(() => null);
}
out('watch_download', csv);

// ── ۵) سرریزِ افقی در دو عرض ───────────────────────────────────────────────
const viewports: Record<string, unknown> = {};
for (const [w, h, tag] of [[1366, 768, 'desktop'], [390, 844, 'phone']] as const) {
  await page.setViewportSize({ width: w, height: h });
  await page.goto(BASE.replace(/\/$/, '') + '/#/fundamental', { waitUntil: 'networkidle', timeout: 45_000 });
  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForSelector('[data-testid="codal-health-strip"]', { timeout: 25_000 }).catch(() => {});
  const m = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    stripVisible: !!document.querySelector('[data-testid="codal-health-strip"]'),
    stripHeight: (function () { const n = document.querySelector('[data-testid="codal-health-strip"]'); return n ? Math.round(n.getBoundingClientRect().height) : 0; })(),
  }));
  viewports[tag] = m;
  await page.screenshot({ path: path.join(OUT, `fundamental_strip_${tag}.png`) });
}
out('viewports', viewports);
out('consoleErrors', consoleErrors.slice(0, 12));
out('failedRequests', failedRequests.slice(0, 12));

writeFileSync(path.join(OUT, 'live_probe.json'), JSON.stringify(report, null, 2), 'utf8');
console.log('saved:', path.join(OUT, 'live_probe.json'));
await browser.close();
