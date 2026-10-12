// tools/mobile_old_client_compat_probe.mts — کلاینتِ **کهنهٔ منتشرشده** در برابرِ
// بستۀِ قراردادِ v2، درِ همان موتورِ واقعی
//
// چرا اجرایِ این و نه استنتاج از کد: پرسشِ مرحلۀ ۶ مأموریت این است که «کلاینتِ
// کهنه فقط gz را مصرف می‌کند یا بهِ formatِ متادیتا هم وابسته است؟». پاسخِ
// حدسی مجاز نیست، پس بیلدِ داخلِ همان APKِ منتشرشده (`mobile-latest`،
// sha256 61959eab…) از فایلِ APK بیرون کشیده می‌شود و **همان بایلدها** درِ
// Chromium اجرا می‌شوند؛ مسیرِ ریلیز با page.route به کاندیدای v2 این شاخه
// وصل می‌شود. هیچ فایلی رویِ `mobile-latest` دست نمی‌خورد — فقط خوانده می‌شود.
//
// what the shipped client does (از همان بایلد، نه از حدس):
//   • manifest را فقط برایِ `built_at` می‌خواند؛ schema_version/package_id/
//     gz_sha256 برایش معنایی ندارد و `.sig` را هرگز درخواست نمی‌کند؛
//   • بسته را درِ کشِ `bors-mobile-snapshot-v1` با کلیدِ `/mobile_snapshot.db.gz`
//     می‌گذارد و مُهرش را درِ `bors_snapshot_cached_stamp`؛
//   • کلیدهایِ pointerِ جدید (`bors_snapshot_active_v2`) را نمی‌نویسد ⇒ فضایِ
//     وضعیتِ دو نسل با هم نمی‌جنگند.
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/mobile_old_client_compat_probe.mts \
//     --www _audit/tmp/stage6/oldwww --pkg pkg3 --out _audit/mobile_stage6_old_client.json
import { createServer } from 'node:http';
import { existsSync, readFileSync, statSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const arg = (n: string, f = ''): string => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};

const WWW = resolve(arg('www', '_audit/tmp/stage6/oldwww'));
const REL = resolve(arg('release', '_audit/tmp/stage5/release'));
const PKG_NAME = arg('pkg', 'pkg3');
const OUT = resolve(arg('out', '_audit/mobile_stage6_old_client.json'));
const SHOTS = resolve(arg('shots', '_audit/tmp/stage6/shots'));
const META_NAME = 'mobile_snapshot.db.meta.json';
// آدرسِ واقعیِ موبایل‌لیتست که درِ بایلدِ کهنه مهر شده است — همان مسیر را
// می‌رباییم تا کلاینتِ کهنه «بی‌آنکه بداند» کاندیدای v2 را بخواند.
const LIVE_BASE =
  'https://github.com/johnwarchief/BorsTerminal-src/releases/download/mobile-latest';

for (const [p, what] of [[join(WWW, 'index.html'), 'بایلدِ بیرون‌کشیده‌شده از APK'],
                         [join(REL, PKG_NAME, META_NAME), `بستۀِ ${PKG_NAME} درِ چیدمانِ ریلیز`]] as string[][]) {
  if (!existsSync(p)) {
    console.error(`BLOCKED: ${what} نیست → ${p}
  APK را از mobile-latest بگیرید و assets/public/** را بیرون بکشید `
      + '(این پروب چیزی دانلود یا منتشر نمی‌کند).');
    process.exit(2);
  }
}
mkdirSync(dirname(OUT), { recursive: true });
mkdirSync(SHOTS, { recursive: true });

const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript', '.css': 'text/css',
  '.json': 'application/json', '.wasm': 'application/wasm', '.svg': 'image/svg+xml',
  '.png': 'image/png', '.ttf': 'font/ttf', '.woff2': 'font/woff2', '.ico': 'image/x-icon',
  '.gz': 'application/octet-stream', '.map': 'application/json',
};
const srv = createServer((req, res) => {
  const u = decodeURIComponent((req.url ?? '/').split('?')[0]);
  const f = join(WWW, u === '/' ? 'index.html' : u.replace(/^\/+/, ''));
  if (!existsSync(f) || !statSync(f).isFile()) { res.writeHead(404); return res.end('no'); }
  res.writeHead(200, { 'content-type': MIME[extname(f)] ?? 'application/octet-stream' });
  return res.end(readFileSync(f));
});
await new Promise<void>((r) => srv.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${(srv.address() as { port: number }).port}`;

const metaOf = (name: string) =>
  JSON.parse(readFileSync(join(REL, name, META_NAME), 'utf8')) as Record<string, unknown>;
const FIRST = arg('first', 'pkg1');          // چیزی که کلاینتِ کهنه درِ بوت می‌گیرد
const SECOND = PKG_NAME;                       // کاندیدای تازه‌تر، برایِ دورۀِ بررسی
const meta = metaOf(SECOND);
const sigText = readFileSync(join(REL, SECOND, `${META_NAME}.sig`), 'utf8');
const secondGz = readFileSync(join(REL, SECOND, 'mobile_snapshot.db.gz'));
const firstBuilt = String(metaOf(FIRST).built_at ?? '');
const secondBuilt = String(meta.built_at ?? '');
if (!(secondBuilt > firstBuilt)) {
  console.error(`BLOCKED: بستۀ «${SECOND}» (built_at=${secondBuilt}) از «${FIRST}» `
    + `(built_at=${firstBuilt}) تازه‌تر نیست ⇒ دورۀِ بررسیِ کهنه دانلود نمی‌کند.`);
  process.exit(2);
}
const hits: string[] = [];
// «چه چیزی سرو می‌شود» درِ اجرا عوض می‌شود: راه‌اندازی با ${FIRST} و بعدِ
// بررسیِ پس‌زمینه با ${SECOND} — تا مسیرِ **دانلودِ** کاندیدا توسطِ کلاینتِ
// کهنه سنجیده شود، نه فقطِ خواندنش درِ بوت.
const served = { name: FIRST };
const servedBuf = (fn: string): Buffer => readFileSync(join(REL, served.name, fn));

const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME ?? undefined,
  args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
await ctx.route(`${LIVE_BASE}/**`, (route) => {
  const u = route.request().url();
  hits.push(u.replace(LIVE_BASE, ''));
  if (u.endsWith(META_NAME)) {
    return route.fulfill({ status: 200, contentType: 'application/json', body: servedBuf(META_NAME) });
  }
  if (u.endsWith(`${META_NAME}.sig`)) {
    return route.fulfill({ status: 200, contentType: 'text/plain', body: Buffer.from(sigText, 'utf8') });
  }
  if (u.endsWith('mobile_snapshot.db.gz')) {
    return route.fulfill({ status: 200, contentType: 'application/octet-stream',
                           body: servedBuf('mobile_snapshot.db.gz') });
  }
  return route.fulfill({ status: 404, contentType: 'text/plain', body: Buffer.from('no') });
});
// همان ردِ پروبِ مرحلۀ ۵: بی‌شبکهٔ بیرونی، تا سنجه‌ها معطلِ TSETMC نشوند.
await ctx.route(/tsetmc|codal/, (route) => route.abort());

const page = await ctx.newPage();
const errors: string[] = [];
page.on('pageerror', (e) => errors.push(String(e).slice(0, 200)));

const checks: { id: string; step: string; expect: string; observed: string; pass: boolean }[] = [];
const say = (id: string, step: string, expect: string, observed: string, pass: boolean) => {
  checks.push({ id, step, expect, observed: String(observed).slice(0, 300), pass });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${step} · انتظار: ${expect} · دیدم: ${String(observed).slice(0, 160)}`);
};

/** پنلِ 🛠 نسلِ کهنه (همان برچسبها: بستهٔ داده / تابلوی آفلاین / تاریخچۀ چارت /
 *  منبعِ بسته). این شاهدِ **مصرفِ داده** است؛ ردیف‌هایِ تابلو درِ آن نسل سنسورِ
 *  معتبری نیستند (صفحه در انتظارِ انتخابِ نماد است)، پس رأی از خودِ داده می‌آید. */
const oldPanel = async () => {
  if (await page.$('#bors-diag-panel')) { await page.click('#bors-diag-btn'); await page.waitForTimeout(250); }
  await page.click('#bors-diag-btn');
  await page.waitForSelector('#bors-diag-panel', { timeout: 30000 });
  let rows: Record<string, string> = {};
  for (let i = 0; i < 12; i++) {
    rows = await page.evaluate(() => {
      const panel = document.getElementById('bors-diag-panel');
      if (!panel) return {};
      const strip = (s: string) => {
        let v = s.trim();
        while (v.endsWith(':') || v.endsWith('\u061B')) v = v.slice(0, -1).trim();
        return v;
      };
      const out: Record<string, string> = {};
      panel.querySelectorAll('div').forEach((d) => {
        const b = d.querySelector('b');
        if (!b) return;
        const label = (b.textContent ?? '').trim();
        out[strip(label)] = strip((d.textContent ?? '').slice(label.length).trim());
      });
      return out;
    }) as Record<string, string>;
    if (rows['بستهٔ داده']) break;
    await page.waitForTimeout(1000);
  }
  await page.click('#bors-diag-btn');   // ببند تا دورِ بعدی تازه بخواند
  return rows;
};

/** اگر ردیفی ندیدیم، خودِ DOM بگوید کجا است — «سنسورِ نامنو» از «اپ نخاسته» جدا بماند. */
const domDump = () => page.evaluate(() => {
  const banner = document.getElementById('bors-fatal-banner');
  const ids = Array.from(document.querySelectorAll('[data-testid]'))
    .map((e) => e.getAttribute('data-testid') ?? '');
  const counts: Record<string, number> = {};
  ids.forEach((i) => { counts[i] = (counts[i] ?? 0) + 1; });
  return {
    boot: ids.includes('mobile-boot'),
    banner: banner ? (banner.textContent ?? '').slice(0, 200) : '',
    hash: location.hash,
    rootText: (document.getElementById('root')?.textContent ?? '').slice(0, 240),
    testids: Object.keys(counts).slice(0, 30),
  };
});

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
// راه‌اندازیِ کلاینتِ کهنه: بستۀِ همراهِ APK درِ این بایلد نیست ⇒ از همان
// مسیرِ ریلیزِ ربوده‌شده خوانده می‌شود.
await page.waitForFunction(() => !document.querySelector('[data-testid="mobile-boot"]'),
  null, { timeout: 180000 }).catch(() => { /* بنر/خطا: رأی‌هایِ بعدی می‌گویند */ });
const rowsBoot = await page.evaluate(() => document.querySelectorAll('[data-testid="tape-row"]').length);
const panelBoot = await oldPanel();
const dumpBoot = await domDump();
say('O1', 'کلاینتِ کهنه با بستۀِ v2 راه‌اندازی شد (پنلِ 🛠 همان بسته را می‌خواند)',
    metaOf(FIRST).built_at + ' و ردیفِ تابلو > 0',
    `بستهٔ داده=${panelBoot['بستهٔ داده'] ?? '—'} · تابلو=${panelBoot['تابلوی آفلاین'] ?? '—'} · منبع=${panelBoot['منبعِ بسته'] ?? '—'} · tape-row=${rowsBoot}`,
    String(panelBoot['بستهٔ داده'] ?? '').includes(String(metaOf(FIRST).built_at))
    && /[1-9]/.test(panelBoot['تابلوی آفلاین'] ?? '')
    && (panelBoot['تابلوی آفلاین'] ?? '').includes('ردیف'));
// حالا «ریلیز» تازه‌تر می‌شود: دورۀِ بررسیِ پس‌زمینه (۱۵ ثانیه) باید *خودِ*
// کلاینتِ کهنه کاندیدای SECOND را دانلود و کش کند.
served.name = SECOND;

let seenCheckAt = '';
let seenStamp = '';
let seenCached = -1;
let seenPointer: unknown = null;
for (let i = 0; i < 40; i++) {
  await page.waitForTimeout(2000);
  const s = await page.evaluate(async () => {
    let cached = -1;
    try {
      const c = await caches.open('bors-mobile-snapshot-v1');
      const r = await c.match('/mobile_snapshot.db.gz');
      cached = r ? (await r.arrayBuffer()).byteLength : -1;
    } catch { cached = -2; }
    return {
      checkAt: localStorage.getItem('bors_snapshot_check_at') ?? '',
      stamp: localStorage.getItem('bors_snapshot_cached_stamp') ?? '',
      cached,
      pointer: localStorage.getItem('bors_snapshot_active_v2'),
    };
  });
  seenCheckAt = s.checkAt; seenStamp = s.stamp; seenCached = s.cached; seenPointer = s.pointer;
  if (s.checkAt && s.cached > 0) break;
}
say('O2', 'درخواستِ manifest/بسته به همان مسیرِ موبایل‌لیتست رفت', '>= 2',
    JSON.stringify(hits.slice(0, 6)), hits.length >= 2);
say('O3', 'دورۀِ بررسیِ کهنه اجرا شد (bors_snapshot_check_at نوشته شد)', 'non-empty', seenCheckAt, !!seenCheckAt);
say('O4', 'بستۀِ v2 دانلود و درِ کشِ کهنه نشست', String(secondGz.byteLength), String(seenCached),
    seenCached === secondGz.byteLength);
say('O5', 'مُهرِ built_at از manifestِ v2 خوانده شد (فیلدهایِ افزوده بی‌ضرر)', secondBuilt,
    seenStamp, seenStamp === secondBuilt);
say('O6', 'کلیدهایِ وضعیتِ نسلِ جدید را نمی‌نویسد (بی‌تداخلِ فضایِ وضعیت)', 'null',
    JSON.stringify(seenPointer), seenPointer === null);

await page.reload({ waitUntil: 'domcontentloaded' });
await page.waitForFunction(() => !document.querySelector('[data-testid="mobile-boot"]'),
  null, { timeout: 180000 }).catch(() => {});
const rowsReload = await page.evaluate(() => document.querySelectorAll('[data-testid="tape-row"]').length);
const panelReload = await oldPanel();
const dumpReload = await domDump();
say('O7', 'پس ازِ reload، همان بستۀِ v2 از کشِ کهنه مصرف می‌شود',
    secondBuilt + ' · منبع=کش',
    `بستهٔ داده=${panelReload['بستهٔ داده'] ?? '—'} · منبع=${panelReload['منبعِ بسته'] ?? '—'} · tape-row=${rowsReload}`,
    String(panelReload['بستهٔ داده'] ?? '').includes(secondBuilt)
    && String(panelReload['منبعِ بسته'] ?? '').includes('کش'));
const realErrors = errors.filter((e) => !/Failed to load resource/.test(e));
say('O8', 'بی‌استثنایِ مدیریت‌نشده درِ کلاینتِ کهنه', '[]', JSON.stringify(realErrors.slice(0, 4)),
    realErrors.length === 0);

await page.screenshot({ path: join(SHOTS, 'old_client_with_v2_package.jpeg'), type: 'jpeg', quality: 60 })
  .catch(() => { /* تصویر شاهد است، نه رأی */ });

const passed = checks.filter((c) => c.pass).length;
const report = {
  generated_at: new Date().toISOString(),
  old_client: { source: 'APK از mobile-latest (فقط خواندنی)', www: WWW, live_base: LIVE_BASE },
  candidate: { first_served: FIRST, first_built_at: firstBuilt, pkg: SECOND,
               manifest: meta, gz_bytes: secondGz.byteLength,
               gz_sha256: meta.gz_sha256 },
  requests_seen: hits,
  dom: { at_boot: dumpBoot, after_reload: dumpReload },
  panels: { at_boot: panelBoot, after_reload: panelReload },
  counts: { checks: checks.length, passed, failed: checks.length - passed },
  verdict: passed === checks.length ? 'PASS' : 'FAIL',
  page_errors: realErrors.slice(0, 10),
  checks,
  note: 'این پروب هیچ چیزی رویِ mobile-latest منتشر نمی‌کند؛ مسیرِ ریلیز فقط '
    + 'ربوده (page.route) می‌شود تا بایلدِ کهنه کاندیدای v2 را بخواند.',
};
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
console.log(`\n[compat] ${report.verdict} · ${passed}/${checks.length} · گزارش: ${OUT}`);
await browser.close();
srv.close();
if (report.verdict !== 'PASS') process.exit(1);
