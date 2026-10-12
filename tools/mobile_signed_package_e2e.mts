// tools/mobile_signed_package_e2e.mts — زنجیرۀ کاملِ بستۀِ داده، درِ Chromiumِ واقعی
//
// چرا این ابزار و نه فقطِ jsdom: درِ jsdom هیچ‌کدام از این‌ها واقعی نیست —
// `Cache API` نیست، `crypto.subtle` نسخهٔ node است، `DecompressionStream` نبود،
// و WebViewِ اندروید اصلاً. این پروب همان بیلدِ `vite build` را درِ Chromium
// (همان موتورِ WebView) بالا می‌آورد و بایت‌هایِ **واقعیِ** ساخته‌شدۀ
// `scripts/build_mobile_snapshot.py` را سرو می‌کند، و بعدِ هر گام از خودِ رابط
// می‌پرسد چه شد: manifest ← امضا ← gz ← SHA ← بازگشایی ← بازکردنِ SQLite ←
// فعال‌سازی (pointer) ← reload ← مصرف از resolver (تابلو و پنلِ 🛠).
//
// پیش‌نیاز (مسیرها از arg، مقادیرِ پیش‌فرض = چیدمانِ کارِ this machine):
//   1) بیلدِ موبایل با کلیدِ عمومیِ امضا و آدرسِ بسته:
//      MSYS_NO_PATHCONV=1 VITE_LOCAL_DATA=1 VITE_APP_VERSION=<pkg.json> \
//      VITE_MOBILE_MANIFEST_PUBKEY=<base64 raw32> VITE_SNAPSHOT_URL=/probe_bundle.js \
//      VITE_SNAPSHOT_REMOTE=/release VITE_SNAPSHOT_STAMP=<قدیمی‌تر از بسته‌ها> npm run build
//   2) three+ signed packages in --release (خروجیِ سازنده + make_release_layout.py)
//   3) فایلِ gzِ بستۀ «همراهِ APK» در --bundle
//
//   JEV_CHROME='C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe' \
//   MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/mobile_signed_package_e2e.mts \
//     --out _audit/mobile_stage5_e2e.json
//
// محدودیتِ صریح: «اینکه Chromiumِ دسکتاپ پاسخِ بزرگِ `.gz` را دانلود می‌پندارد و
// fetch را ۲۰۴ می‌کند» یکِ واقعیتِ همینِ harness است (اندازه‌گیری‌شده؛ ببین
// _audit/tmp/stage5/gz_fetch_check.mts)؛ بایت‌ها درِ این پروب با page.route
// تحویل می‌شوند. رویِ گوشی، همان مسیر از CapacitorHttpِ بومی می‌رود و این پروب
// رفتارِ WebViewِ اندروید را اثبات **نمی‌کند** — فقط Chromium.
import { createServer } from 'node:http';
import { existsSync, mkdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};

const DIST = resolve(arg('dist', 'frontend/dist'));
const REL = resolve(arg('release', '_audit/tmp/stage5/release'));
const BUNDLE_GZ = resolve(arg('bundle', join(REL, 'pkg1/mobile_snapshot.db.gz')));
const SHOT_DIR = resolve(arg('shots', '_audit/tmp/stage5/shots'));
const OUT = resolve(arg('out', '_audit/mobile_stage5_e2e.json'));
const KEEP = process.argv.includes('--keep-open');
const NO_PUBKEY = process.argv.includes('--expect-no-pubkey');
const META_NAME = 'mobile_snapshot.db.meta.json';

for (const p of [[DIST, 'بیلدِ فرانت (vite build)'], [REL, 'چیدمانِ ریلیزِ بسته‌ها'],
                 [BUNDLE_GZ, 'بستۀ همراهِ برنامه']]) {
  if (!existsSync(p[0])) {
    console.error(`BLOCKED: ${p[1]} نیست → ${p[0]}`);
    process.exit(2);
  }
}
mkdirSync(SHOT_DIR, { recursive: true });
mkdirSync(dirname(OUT), { recursive: true });

// ── حالتِ سروِ «ریلیز» — همان چیزی که سناریوها را عوض می‌کند ───────────────
type Mode = {
  pkg: string;                 // نامِ پوشه درِ --release
  offline: boolean;            // هیچ‌چیز ۲۰۰ نمی‌دهد
  noSig: boolean;              // .sig نیست
  otherKey: boolean;           // .sig با کلیدِ دیگری امضا شده
  flipSig: boolean;            // یکِ نویسهٔ base64ِ امضا عوض می‌شود
  flipManifest: boolean;       // یکِ بایتِ manifest عوض می‌شود
  truncateGz: boolean;         // فقط نصفِ بایت‌ها تحویل می‌شود
  corruptGz: boolean;          // یکِ بایتِ میانیِ gz عوض می‌شود
};
const mode: Mode = {
  pkg: 'pkg1', offline: false, noSig: false, otherKey: false, flipSig: false,
  flipManifest: false, truncateGz: false, corruptGz: false,
};
const reset = (pkg: string) => {
  Object.assign(mode, {
    pkg, offline: false, noSig: false, otherKey: false, flipSig: false,
    flipManifest: false, truncateGz: false, corruptGz: false,
  });
};

const fileAt = (rel: string): Buffer => readFileSync(join(REL, rel));
const flipByte = (b: Buffer, at: number): Buffer => {
  const c = Buffer.from(b);
  c[at] ^= 0x01;
  return c;
};
/** امضا: یکِ نویسهٔ **میانیِ** خطِ base64 را عوض می‌کنیم — نه آخرین، چون آخرین
 *  درِ امضایِ ۷۴بایتی «=` است و عوض‌کردنش طولِ decoded را عوض می‌کند؛ آن رأی
 *  «ساختارِ امضا خراب» می‌دهد نه «امضایِ نامعتبر». */
const flipSigChar = (text: string): string => {
  const lines = text.split('\n');
  const l2 = lines[1] ?? '';
  if (l2.length < 8) return text;
  const at = Math.floor(l2.length / 2);
  lines[1] = l2.slice(0, at) + (l2[at] === 'A' ? 'B' : 'A') + l2.slice(at + 1);
  return lines.join('\n');
};

/** بایت‌هایِ یکِ مسیرِ ریلیز، با تزریقِ حالتِ جاری. */
function releasePayload(url: string): { status: number; contentType: string; body: Buffer } | null {
  if (mode.offline) return { status: 500, contentType: 'text/plain', body: Buffer.from('offline') };
  const p = url.split('?')[0];
  const base = join(REL, mode.pkg);
  if (p.endsWith(`/${META_NAME}`)) {
    const f = join(base, META_NAME);
    if (!existsSync(f)) return { status: 404, contentType: 'text/plain', body: Buffer.from('no meta') };
    const raw = readFileSync(f);
    return { status: 200, contentType: 'application/json',
             body: mode.flipManifest ? flipByte(raw, Math.floor(raw.length / 2)) : raw };
  }
  if (p.endsWith(`${META_NAME}.sig`)) {
    if (mode.noSig) return { status: 404, contentType: 'text/plain', body: Buffer.from('no sig') };
    const f = mode.otherKey ? join(base, `${META_NAME}.otherkey.sig`) : join(base, `${META_NAME}.sig`);
    if (!existsSync(f)) return { status: 404, contentType: 'text/plain', body: Buffer.from('no sig') };
    const text = readFileSync(f, 'utf8');
    return { status: 200, contentType: 'text/plain; charset=utf-8',
             body: Buffer.from(mode.flipSig ? flipSigChar(text) : text, 'utf8') };
  }
  if (p.endsWith('mobile_snapshot.db.gz')) {
    const f = join(base, 'mobile_snapshot.db.gz');
    if (!existsSync(f)) return { status: 404, contentType: 'text/plain', body: Buffer.from('no gz') };
    let raw = readFileSync(f);
    if (mode.corruptGz) raw = flipByte(raw, Math.floor(raw.length * 0.4));
    if (mode.truncateGz) raw = raw.subarray(0, Math.floor(raw.length / 2));
    return { status: 200, contentType: 'application/octet-stream', body: raw };
  }
  return { status: 404, contentType: 'text/plain', body: Buffer.from('unknown') };
}

// ── سروِ ایستایِ بیلد (همان dist که رویِ گوشی است) ──────────────────────────
const MIME: Record<string, string> = {
  '.html': 'text/html; charset=utf-8', '.js': 'application/javascript',
  '.mjs': 'application/javascript', '.css': 'text/css', '.json': 'application/json',
  '.wasm': 'application/wasm', '.svg': 'image/svg+xml', '.png': 'image/png',
  '.woff2': 'font/woff2', '.ttf': 'font/ttf', '.ico': 'image/x-icon',
};
const BUNDLE_BYTES = readFileSync(BUNDLE_GZ);
const srv = createServer((req, res) => {
  const u = decodeURIComponent((req.url ?? '/').split('?')[0]);
  if (u === '/probe_bundle.js') {
    res.writeHead(200, { 'content-type': 'application/javascript',
                         'content-length': String(BUNDLE_BYTES.byteLength) });
    return res.end(BUNDLE_BYTES);
  }
  const f = join(DIST, u === '/' ? 'index.html' : u.replace(/^\/+/, ''));
  if (!existsSync(f) || !statSync(f).isFile()) { res.writeHead(404); return res.end('no'); }
  res.writeHead(200, { 'content-type': MIME[extname(f)] ?? 'application/octet-stream' });
  return res.end(readFileSync(f));
});
await new Promise<void>((r) => srv.listen(0, '127.0.0.1', r));
const BASE = `http://127.0.0.1:${(srv.address() as { port: number }).port}`;
console.log(`[e2e] origin=${BASE} · dist=${DIST} · release=${REL}`);

const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.JEV_CHROME ?? undefined,
  args: ['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage'],
});
const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
// دروازۀ ورودِ dev (همیشگی درِ probes): پروب باید اپ را آزمایش کند، نه لاگین را.
await ctx.addInitScript(() => { sessionStorage.setItem('bors_auth_session', 'true'); });
await ctx.route('**/release/**', (route) => {
  const p = releasePayload(route.request().url());
  if (!p) return route.abort();
  return route.fulfill({ status: p.status, contentType: p.contentType, body: p.body });
});
// بی‌شبکهٔ بیرونی: پنلِ 🛠 زندهٔ TSETMC را هم می‌پرسد. درِ این پروب باید فوراً
// شکست بخورد — نه اینکه جمع‌آوریِ وضعیت دقیقه‌ها معطل بماند یا دادۀِ زنده،
// رأیِ «بستۀِ آفلاین» را عوض کند.
await ctx.route(/tsetmc|codal/, (route) => route.abort());
const page = await ctx.newPage();
const consoleErrors: string[] = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 300)); });
page.on('pageerror', (e) => consoleErrors.push(String(e).slice(0, 300)));

// ── ثبتِ رأی‌ها ─────────────────────────────────────────────────────────────
type Check = { id: string; step: string; expect: string; observed: string; pass: boolean };
const checks: Check[] = [];
const say = (id: string, step: string, expect: string, observed: string, pass: boolean) => {
  checks.push({ id, step, expect, observed: observed.slice(0, 400), pass });
  console.log(`${pass ? 'PASS' : 'FAIL'} [${id}] ${step} · انتظار: ${expect} · دیدم: ${observed.slice(0, 200)}`);
  return pass;
};

/** rowsِ پنلِ 🛠 به‌شکلِ {برچسب: مقدار} — همان چیزی که کاربر رویِ گوشی می‌بیند.
 *  بی‌regex و بی‌cast درِ callback: `--experimental-strip-types` آن‌ها را نمی‌پذیرد. */
const readPanel = () => page.evaluate(() => {
  const panel = document.getElementById('bors-diag-panel');
  if (!panel) return null;
  const strip = (s: string) => {
    let v = s.trim();
    while (v.endsWith(':') || v.endsWith('\u061B')) v = v.slice(0, -1).trim();   // «برچسب:» درِ <b> است
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
});
/** وضعیتِ ذخیره‌گاهِ بسته: pointerها و شمارِ بسته‌هایِ staging. */
const readStorage = () => page.evaluate(async () => {
  const ptr = (k: string) => {
    try { return JSON.parse(localStorage.getItem(k) ?? 'null'); } catch { return null; }
  };
  let staging: string[] = [];
  let cachesOk = true;
  try {
    const c = await caches.open('bors-mobile-snapshot-staging-v2');
    staging = (await c.keys()).map((r) => r.url);
  } catch { cachesOk = false; }
  let legacy: string[] = [];
  try {
    const c2 = await caches.open('bors-mobile-snapshot-v1');
    legacy = (await c2.keys()).map((r) => r.url);
  } catch { /* نبود کشِ کهنه یعنی پاک‌سازی درست */ }
  return {
    active: ptr('bors_snapshot_active_v2'),
    previous: ptr('bors_snapshot_previous_v2'),
    stamp: localStorage.getItem('bors_snapshot_cached_stamp') ?? '',
    staging, legacy, cachesOk,
    failStreak: localStorage.getItem('bors_snapshot_fail_streak') ?? '0',
  };
});
const openPanel = async () => {
  if (await page.$('#bors-diag-panel')) { await page.click('#bors-diag-btn'); await page.waitForTimeout(300); }
  await page.click('#bors-diag-btn');
  await page.waitForSelector('#bors-diag-check button', { timeout: 30000 });
  return readPanel();
};
/** دکمۀ «بررسی دستی» را می‌زند و تا نتیجه صبر می‌کند (فعال‌سازی = بازکردنِ SQLite، ثانیه‌ها طول می‌کشد). */
const clickCheck = async () => {
  const sel = '#bors-diag-check button';
  await page.waitForSelector(sel, { timeout: 30000 });
  const before = await page.textContent(sel);
  await page.click(sel);
  const t0 = Date.now();
  while (Date.now() - t0 < 180000) {
    await page.waitForTimeout(500);
    const now = await page.textContent(sel);
    if (now && now !== before && !now.includes('در حال بررسی')) return (now ?? '').trim();
  }
  return 'TIMEOUT';
};
const waitForBoot = async () => {
  await page.waitForSelector('#bors-diag-btn', { timeout: 180000 });
  await page.waitForFunction(() => !document.querySelector('[data-testid="mobile-boot"]'),
    null, { timeout: 180000 }).catch(() => { /* بنر مرگبار =Boot screen باقی می‌ماند؛ رأیِ خودش گرفته می‌شود */ });
};
const boardRows = () => page.evaluate(() => document.querySelectorAll('[data-testid="tape-row"]').length);

const shot = async (name: string) => {
  const path = join(SHOT_DIR, `${name}.jpeg`);
  await page.screenshot({ path, type: 'jpeg', quality: 60 }).catch(() => { /* تصویر شاهد است، نه رأی */ });
  return path;
};

/** گزارشِ ماشین‌خواندنی — هم مسیرِ کامل و هم مسیرِ بی‌کلید به همین نیاز دارد. */
const writeReport = async (): Promise<{ verdict: string; passed: number; checks: number }> => {
  const passed = checks.filter((c) => c.pass).length;
  const report = {
    generated_at: new Date().toISOString(),
    origin: BASE,
    mode: NO_PUBKEY ? 'expect-no-pubkey' : 'full-chain',
    engine: { chromium: await browser.version(), executable: process.env.JEV_CHROME ?? 'bundled' },
    artifacts: {
      dist: DIST, release_dir: REL, bundle_gz: BUNDLE_GZ,
      bundle_gz_bytes: BUNDLE_BYTES.byteLength,
      packages: { pkg1: metaOf('pkg1'), pkg2: metaOf('pkg2'), pkg3: metaOf('pkg3'),
                  baddb: metaOf('baddb') },
    },
    counts: { checks: checks.length, passed, failed: checks.length - passed },
    verdict: passed === checks.length ? 'PASS' : 'FAIL',
    console_errors: consoleErrors.slice(0, 20),
    checks,
    results,
    limitation: 'Chromiumِ دسکتاپ؛ Cache API و crypto.subtle واقعی‌اند، ولی Android WebView اثبات نشده است. '
      + 'بایت‌هایِ gz با page.route تحویل می‌شود چون همین harness پاسخِ بزرگِ `.gz` را ۲۰۴ می‌کند '
      + '(شاهد: _audit/tmp/stage5/gz_fetch_check.mts).',
  };
  writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
  console.log(`\n[e2e] ${report.verdict} · ${passed}/${checks.length} · گزارش: ${OUT}`);
  return { verdict: report.verdict, passed, checks: checks.length };
};

// ── اجرایِ سناریوها ────────────────────────────────────────────────────────
const results: Record<string, unknown> = {};
const metaOf = (pkg: string) => JSON.parse(readFileSync(join(REL, pkg, META_NAME), 'utf8'));

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await waitForBoot();

// S0 — راه‌اندازی با بستۀ «همراهِ APK»، بی‌ریلیزِ دست‌رس
mode.offline = true;
let panel = await openPanel();
let st = await readStorage();
const src0 = panel?.['منبعِ بسته'] ?? '';
const candles0 = panel?.['تاریخچۀ چارت'] ?? '';
say('S0a', 'منبعِ بسته درِ راه‌اندازیِ اول', 'همراهِ APK', src0, src0.includes('همراهِ APK'));
say('S0b', 'داده از resolver خوانده می‌شود', '> 0 کندل', candles0, /کندل/.test(candles0));
say('S0c', 'بی‌فعال‌سازی، pointer نوشته نمی‌شود', 'null', JSON.stringify(st.active), st.active === null);
const rows0 = await boardRows();
say('S0d', 'ردیف‌های تابلو از بسته', '> 0', String(rows0), rows0 > 0);
results.S0 = { panel, storage: st, boardRows: rows0 };
await shot('S0_bundle_boot');

// NP — بیلدی که کلیدِ عمومی درِ آن نیست (VITE_MOBILE_MANIFEST_PUBKEY خالی):
// درِ همان موتورِ واقعی هم باید **fail-closed** باشد، نه پذیرندۀِ manifestِ بی‌امضا.
if (NO_PUBKEY) {
  mode.offline = false;
  reset('pkg1');
  panel = await openPanel();
  const npc = await clickCheck();
  st = await readStorage();
  say('NP1', 'بیلدِ بی‌کلید ⇒ manifest خوانده نمی‌شود', 'signing-key-unconfigured', npc,
      npc.includes('signing-key-unconfigured'));
  say('NP2', 'هیچ pointerی نوشته نمی‌شود', 'null', JSON.stringify(st.active), st.active === null);
  say('NP3', 'دادۀِ همراهِ برنامه همچنان خوانده می‌شود', 'همراهِ APK',
      String(panel?.['منبعِ بسته'] ?? ''), String(panel?.['منبعِ بسته'] ?? '').includes('همراهِ APK'));
  await shot('NP_no_pubkey');
  const npRep = await writeReport();
  if (!KEEP) await browser.close();
  srv.close();
  process.exit(npRep.verdict === 'PASS' ? 0 : 1);
}

// S1 — فعال‌سازیِ نخست از ریلیز (manifest امضاشده ← … ← pointer)
mode.offline = false;
reset('pkg1');
const p1 = metaOf('pkg1');
panel = await openPanel();
const c1 = await clickCheck();
st = await readStorage();
say('S1a', 'دکمۀ بررسی پس ازِ فعال‌سازی', 'نسخۀ تازه فعال شد', c1, c1.includes('فعال شد'));
say('S1b', 'pointer = package_idِ بستۀ امضاشده', p1.package_id,
    JSON.stringify(st.active?.packageId ?? null), st.active?.packageId === p1.package_id);
say('S1c', 'یکِ بسته در staging', '1', String(st.staging.length), st.staging.length === 1);
say('S1d', 'مُهرِ built_at نوشته شد', p1.built_at, st.stamp, st.stamp === p1.built_at);
results.S1 = { outcome: c1, storage: st, manifest: p1 };
await shot('S1_activated_pkg1');

// S2 — فعال‌سازیِ دوم: بستۀ پیشین می‌ماند و دو بسته نگه داشته می‌شود
reset('pkg2');
const p2 = metaOf('pkg2');
panel = await openPanel();
const c2 = await clickCheck();
st = await readStorage();
const prev2 = Array.isArray(st.previous) ? st.previous : [];
say('S2a', 'فعال‌سازیِ دوم', 'فعال شد', c2, c2.includes('فعال شد'));
say('S2b', 'pointer = pkg2', p2.package_id, String(st.active?.packageId ?? ''),
    st.active?.packageId === p2.package_id);
say('S2c', 'pkg1 به‌عنوانِ نامزدِ بازگشت ماند', p1.package_id,
    String(prev2.map((x: { packageId?: string }) => x?.packageId).join(',')),
    prev2.length === 1 && prev2[0]?.packageId === p1.package_id);
say('S2d', 'دو بسته در staging', '2', String(st.staging.length), st.staging.length === 2);
results.S2 = { outcome: c2, storage: st };
await shot('S2_activated_pkg2');

// S3 — فعال‌سازیِ سوم: نگهداشت «حداکثرِ دو» و حذفِ سومی
reset('pkg3');
const p3 = metaOf('pkg3');
panel = await openPanel();
const c3 = await clickCheck();
st = await readStorage();
const prev3 = Array.isArray(st.previous) ? st.previous : [];
const ids3 = st.staging.map((u: string) => u.replace(/^.*\//, '').replace(/\.gz$/, ''));
say('S3a', 'فعال‌سازیِ سوم', 'فعال شد', c3, c3.includes('فعال شد'));
say('S3b', 'pointer = pkg3', p3.package_id, String(st.active?.packageId ?? ''),
    st.active?.packageId === p3.package_id);
say('S3c', 'نامزدِ بازگشت = pkg2 (نه pkg1)', p2.package_id,
    String(prev3.map((x: { packageId?: string }) => x?.packageId).join(',')),
    prev3.length === 1 && prev3[0]?.packageId === p2.package_id);
say('S3d', 'سومِ بسته‌ها پاک شد؛ فقط دو تا می‌ماند', '2', String(st.staging.length),
    st.staging.length === 2);
say('S3e', 'بستۀِ pkg1 از staging رفت', 'absent', ids3.join(','),
    !ids3.some((x: string) => x.includes(p1.package_id)));
results.S3 = { outcome: c3, storage: st, stagingIds: ids3 };
await shot('S3_retention_two_packages');

// S4 — reload: همان بستهٔ فعال از کش خوانده می‌شود و مصرف‌کننده داده را می‌بیند
await page.reload({ waitUntil: 'domcontentloaded' });
await waitForBoot();
panel = await openPanel();
const src4 = panel?.['منبعِ بسته'] ?? '';
const candles4 = panel?.['تاریخچۀ چارت'] ?? '';
say('S4a', 'منبع پس ازِ reload', 'کشِ دستگاه', src4, src4.includes('کش'));
say('S4b', 'دادۀِ pkg3 در حافظه باز شد (۴٧٤۰ کندل)', 'pkg3 candles', candles4,
    /۴\s?۷\s?۴\s?۰|4740/.test(candles4.replace(/[٬]/g, '')));
const rows4 = await boardRows();
say('S4c', 'تابلو پس ازِ reload ردیف دارد', '> 0', String(rows4), rows4 > 0);
results.S4 = { panel, boardRows: rows4 };
await shot('S4_reload_from_cache');

// S5…S12 — تزریقِ شکست در هر گام؛ در همه، pkg3 فعال می‌ماند و داده خوانده می‌شود
const bad = metaOf('baddb');
type Failure = { id: string; label: string; expect: string; setup: () => void };
const failures: Failure[] = [
  { id: 'S5', label: 'امضا نیست', expect: 'signature-missing', setup: () => { mode.noSig = true; } },
  { id: 'S6', label: 'امضا دست‌خورده', expect: 'signature-invalid', setup: () => { mode.flipSig = true; } },
  { id: 'S7', label: 'امضا با کلیدِ دیگر', expect: 'signature-key-mismatch', setup: () => { mode.otherKey = true; } },
  { id: 'S8', label: 'manifest دست‌خورده', expect: 'signature-invalid', setup: () => { mode.flipManifest = true; } },
  { id: 'S9', label: 'gz نصفه', expect: 'size-mismatch', setup: () => { mode.truncateGz = true; } },
  { id: 'S10', label: 'gz دست‌خورده', expect: 'digest-mismatch', setup: () => { mode.corruptGz = true; } },
  { id: 'S11', label: 'دیتابیسِ بسته خراب (امضا/SHA سالم)', expect: 'db-', setup: () => { /* بایت‌هایِ pkg_bad_db، بی‌هیچ دست‌زدنی */ } },
  { id: 'S12', label: 'ریلیز در دسترس نیست', expect: 'manifest-missing', setup: () => { mode.offline = true; } },
];
for (const f of failures) {
  reset('baddb');            // همیشه بستۀِ **تازه‌تر** از pkg3، وگرنه بررسی «تازه است» می‌گوید و رد می‌شود
  f.setup();
  panel = await openPanel();
  const outcome = await clickCheck();
  st = await readStorage();
  say(`${f.id}a`, `${f.label}: رأیِ کلاینت`, f.expect, outcome, outcome.includes(f.expect));
  say(`${f.id}b`, `${f.label}: بستۀ فعال عوض نشد`, p3.package_id, String(st.active?.packageId ?? ''),
      st.active?.packageId === p3.package_id);
  const pv = Array.isArray(st.previous) ? st.previous : [];
  say(`${f.id}c`, `${f.label}: نامزدِ بازگشت سالم ماند`, p2.package_id,
      String(pv.map((x: { packageId?: string }) => x?.packageId).join(',')),
      pv.length === 1 && pv[0]?.packageId === p2.package_id);
  say(`${f.id}d`, `${f.label}: دو بستهٔ سالم در staging`, '2', String(st.staging.length),
      st.staging.length === 2);
  results[f.id] = { outcome, storage: st };
  await shot(`${f.id}_${f.id === 'S11' ? 'broken_db' : 'failure'}`);
}

// S13 — reload پس ازِ همه‌یِ شکست‌ها: همان pkg3 خوانده و مصرف می‌شود
mode.offline = false;
reset('pkg3');
await page.reload({ waitUntil: 'domcontentloaded' });
await waitForBoot();
panel = await openPanel();
const candles13 = panel?.['تاریخچۀ چارت'] ?? '';
const rows13 = await boardRows();
say('S13a', 'پس ازِ ۸ شکست، دادۀ pkg3 خوانده می‌شود', 'pkg3 candles', candles13,
    /۴\s?۷\s?۴\s?۰|4740/.test(candles13.replace(/[٬]/g, '')));
say('S13b', 'تابلو پس ازِ شکست‌ها ردیف دارد', '> 0', String(rows13), rows13 > 0);
results.S13 = { panel, boardRows: rows13 };
await shot('S13_still_readable_after_failures');

// S14 — بازگشتِ صریح به نسخۀِ پیشینِ معتبر (دکمۀ پنلِ 🛠)
mode.offline = true;
panel = await openPanel();
const rbSel = '#bors-diag-rollback button';
const hasRb = Boolean(await page.$(rbSel));
say('S14a', 'دکمۀ بازگشت فقط با نامزدِ معتبر دیده می‌شود', 'present', String(hasRb), hasRb);
let rbText = '—';
if (hasRb) {
  const before = await page.textContent(rbSel);
  await page.click(rbSel);
  const t0 = Date.now();
  while (Date.now() - t0 < 60000) {
    await page.waitForTimeout(400);
    const now = await page.textContent(rbSel);
    if (now && now !== before && !now.includes('در حال بازگشت')) { rbText = (now ?? '').trim(); break; }
  }
}
st = await readStorage();
const pv14 = Array.isArray(st.previous) ? st.previous : [];
say('S14b', 'نتیجهٔ بازگشت', p2.package_id, rbText, rbText.includes('بازگشت شد'));
say('S14c', 'pointer = pkg2', p2.package_id, String(st.active?.packageId ?? ''),
    st.active?.packageId === p2.package_id);
say('S14d', 'pkg3 شد نامزدِ بازگشت', p3.package_id,
    String(pv14.map((x: { packageId?: string }) => x?.packageId).join(',')),
    pv14.length === 1 && pv14[0]?.packageId === p3.package_id);
results.S14 = { rbText, storage: st };
await shot('S14_rollback');

// S15 — reload پس ازِ بازگشت: دیتابیسِ pkg2 باز می‌شود (۶٨٧۴ کندل)
mode.offline = false;
reset('pkg2');
await page.reload({ waitUntil: 'domcontentloaded' });
await waitForBoot();
panel = await openPanel();
const candles15 = panel?.['تاریخچۀ چارت'] ?? '';
say('S15a', 'پس ازِ بازگشت، دادۀ pkg2 مصرف می‌شود', 'pkg2 candles', candles15,
    /۶\s?۸\s?۷\s?۴|6874/.test(candles15.replace(/[٬]/g, '')));
results.S15 = { panel };
await shot('S15_after_reload_rolled_back');

// S16 — بازیابیِ pointerِ بی‌بسته: ردیفِ staging را پاک می‌کنیم و reload می‌گیریم
const delKey = await page.evaluate(() => {
  try { return JSON.parse(localStorage.getItem('bors_snapshot_active_v2') ?? 'null')?.cacheKey ?? ''; }
  catch { return ''; }
});
const gone = await page.evaluate(async (key: string) => {
  const c = await caches.open('bors-mobile-snapshot-staging-v2');
  const ok = await c.delete(key);
  return { ok, left: (await c.keys()).map((r) => r.url) };
}, delKey);
await page.reload({ waitUntil: 'domcontentloaded' });
await waitForBoot();
panel = await openPanel();
st = await readStorage();
const src16 = panel?.['منبعِ بسته'] ?? '';
const rows16 = await boardRows();
say('S16a', 'بستۀ فعالِ pointer پاک شد', 'deleted', JSON.stringify(gone), gone.ok === true);
say('S16b', 'pointerِ بی‌بسته بازنشسته شد', 'null', JSON.stringify(st.active), st.active === null);
say('S16c', 'برنامه به بستۀِ همراهِ APK برگشت', 'همراهِ APK', src16, src16.includes('همراهِ APK'));
say('S16d', 'تابلو بی‌کرش داده دارد', '> 0', String(rows16), rows16 > 0);
results.S16 = { gone, panel, boardRows: rows16, deletedKey: delKey };
await shot('S16_pointer_recovery');

// S17 — بستۀِ **کهنه** همان چیزی که امروز رویِ `mobile-latest` است (manifestِ
// چهارکلیدیِ ۱۱۱بایتی، بایت‌به‌بایت از ریلیزِ زنده، این‌جا با کلیدِ نمایشی امضا
// شده تا رأی «ساختارِ manifest» سنجیده شود نه «امضا»): کلاینتِ همین شاخه باید
// آن را **رد** کند و بهِ بستۀِ همراهِِ برنامه برگردد، نه اینکه بی‌آزمون بپذیرد.
reset('v1_legacy');
panel = await openPanel();
const legacy = await clickCheck();
st = await readStorage();
const rows17 = await boardRows();
say('S17a', 'manifestِ کهنه (schema_version/package_id نیست) رد شد', 'manifest-field-missing', legacy,
    legacy.includes('manifest-field-missing') || legacy.includes('manifest-schema-unknown'));
say('S17b', 'هیچ pointerی ساخته نشد', 'null', JSON.stringify(st.active), st.active === null);
say('S17c', 'دادۀِ همراهِ برنامه همچنان مصرف می‌شود', '> 0', String(rows17), rows17 > 0);
results.S17 = { legacy, storage: st, boardRows: rows17 };
await shot('S17_legacy_manifest_rejected');

// ── گزارش ──────────────────────────────────────────────────────────────────
const rep = await writeReport();
if (!KEEP) await browser.close();
srv.close();
if (!KEEP && rep.verdict !== 'PASS') process.exit(1);
