// _audit/ws13_boot_page.mts — اثباتِ زندهٔ «صفحۀ لودینگِ اولین اجرا»
//
// دو پاس، هر دو با لانچرِ واقعی (`dev/boot_live_drill.py` که همان
// `_serve_with_boot`/`_bootstrap_worker` را اجرا می‌کند، فقط پنجره stub است):
//
//  ۱ synthetic: market.db.lzmaِ ~۳۰ مگابایتی واقعاً استخراج می‌شود؛ از مرورگر
//     *نوارِ پیشرفت* را نمونه‌برداری می‌کنیم (عرضِ واقعیِ پرشده، متنِ فارسی،
//     رقمِ فارسی، RTL، بی‌خطای کنسول) و می‌گوییم چند مقدارِ different دیده شد.
//  ۲ real: همان مسیرِ بالا ولی با اپِ واقعی روی ۸۰۲۱؛ اثباتِ این‌که صفحۀ بوت
//     خودش آدرس را عوض می‌کند و پوستۀ SPA بالا می‌آید.
//
// اجرا:  MSYS_NO_PATHCONV=1 node --experimental-strip-types _audit/ws13_boot_page.mts
import { mkdirSync, writeFileSync } from 'node:fs';
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';

const PKG = process.env.JEV_BROWSER_DIR
  ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
mkdirSync('_audit', { recursive: true });
const OUT = '_audit/ws13_boot_page.json';
const APP_PORT = 8031; // ۸۰۲۱ را سرورِ devِ خودمان اشغال دارد

type Drill = { proc: any; bootUrl: string; lines: string[]; kill: () => void };

function startDrill(mode: string): Promise<Drill> {
  return new Promise((resolve, reject) => {
    const proc = spawn('python', ['dev/boot_live_drill.py', '--mode', mode,
                                  '--app-port', String(APP_PORT)], {
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
    });
    const lines: string[] = [];
    let bootUrl = '';
    const timer = setTimeout(() => reject(new Error('drill did not print BOOT_URL\n'
      + lines.join('\n'))), mode === 'synthetic' ? 180_000 : 90_000);
    const onData = (buf: Buffer) => {
      for (const ln of String(buf).split(/\r?\n/)) {
        if (!ln.trim()) continue;
        lines.push(ln.trim());
        const m = /^BOOT_URL=(.+)$/.exec(ln.trim());
        if (m && !bootUrl) {
          bootUrl = m[1];
          clearTimeout(timer);
          resolve({ proc, bootUrl, lines, kill: () => { try { proc.kill('SIGTERM'); } catch {} } });
        }
      }
    };
    proc.stdout.on('data', onData);
    proc.stderr.on('data', (b) => lines.push('ERR:' + String(b).slice(0, 200)));
    proc.on('exit', (code) => { if (!bootUrl) { clearTimeout(timer); reject(new Error('drill exited ' + code + '\n' + lines.join('\n'))); } });
  });
}

const browser = await chromium.launch({ headless: true,
  executablePath: process.env.JEV_CHROME || undefined });
const report: any = { app_port: APP_PORT, passes: {} };
const drills: Drill[] = [];

// ── پاس ۱: نوارِ پیشرفتِ واقعی ────────────────────────────────────────────
const d1 = await startDrill('synthetic');
drills.push(d1);
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 140)); });
  const t0 = Date.now();
  await page.goto(d1.bootUrl, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  const dir = await page.evaluate(() => document.documentElement.dir + '/' + document.documentElement.lang);
  const samples: { ms: number; pct: number; phase: string; detail: string }[] = [];
  let shotDone = false;
  while (Date.now() - t0 < 150_000) {
    const s = await page.evaluate(() => {
      const fill = document.getElementById('fill');
      const bar = document.getElementById('bar');
      const w = fill ? fill.getBoundingClientRect().width : 0;
      const bw = bar ? bar.getBoundingClientRect().width : 1;
      return {
        pct: Math.round((w / Math.max(1, bw)) * 100),
        indet: (bar?.className || '').includes('indet'),
        phase: (document.getElementById('phase')?.textContent || '').trim(),
        detail: (document.getElementById('detail')?.textContent || '').trim(),
      };
    });
    samples.push({ ms: Date.now() - t0, pct: s.indet ? -1 : s.pct, phase: s.phase, detail: s.detail });
    if (!shotDone && s.pct > 12 && s.pct < 92) {
      await page.screenshot({ path: '_audit/ws13_boot_progress.png' });
      shotDone = true;
    }
    if (s.pct >= 100) break;
    await page.waitForTimeout(300);
  }
  const last = samples[samples.length - 1];
  const seen = samples.filter((s) => s.pct >= 0);
  const distinct = Array.from(new Set(seen.map((s) => s.pct))).sort((a, b) => a - b);
  const persianDigits = /[۰-۹]/.test(seen.map((s) => s.detail).join(''));
  report.passes.progress = {
    rtl: dir, samples: samples.length, distinct_pcts: distinct.length,
    pct_track: distinct.slice(0, 20), reached_100: last.pct >= 100,
    phase_texts: Array.from(new Set(samples.map((s) => s.phase).filter(Boolean))),
    detail_sample: seen.find((s) => s.detail)?.detail ?? '',
    persian_digits_rendered: persianDigits,
    screenshot_midway: shotDone ? '_audit/ws13_boot_progress.png' : null,
    console_errors: errs,
  };
  await ctx.close();
  d1.kill();
}

// ── پاس ۲: تسلیمِ آدرس به اپِ واقعی ──────────────────────────────────────
const d2 = await startDrill('real');
drills.push(d2);
{
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  // اپ احرازِ هویت می‌خواهد؛ بی‌این، بعد از redirect به صفحۀ ورود می‌رسیم و
  // سایدبار هرگز رندر نمی‌شود (همان الگویِ ws9).
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  const page = await ctx.newPage();
  const errs: string[] = [];
  page.on('pageerror', (e) => errs.push(String(e.message).slice(0, 160)));
  await page.goto(d2.bootUrl, { waitUntil: 'domcontentloaded', timeout: 20_000 });
  const bootPhase = await page.evaluate(() => (document.getElementById('phase')?.textContent || '').trim());
  await page.screenshot({ path: '_audit/ws13_boot_page.png' });
  const t0 = Date.now();
  let handedOff = false;
  try {
    await page.waitForURL(`http://127.0.0.1:${APP_PORT}/**`, { timeout: 180_000 });
    handedOff = true;
  } catch { /* در گزارش می‌آید */ }
  let shell = false;
  let funnel = false;
  if (handedOff) {
    try {
      await page.waitForSelector('[data-shell="sidebar"]', { timeout: 60_000 });
      shell = true;
    } catch { /* می‌ماند false */ }
    funnel = await page.locator('[data-testid="fts-funnel-workspace"]').count() > 0;
  }
  report.passes.handoff = {
    boot_phase_text: bootPhase,
    handed_off_ms: handedOff ? Date.now() - t0 : null,
    spa_shell_rendered: shell,
    funnel_workspace_on_landing: funnel,
    final_url: page.url(),
    page_errors: errs,
    screenshot_boot: '_audit/ws13_boot_page.png',
  };
  await page.screenshot({ path: '_audit/ws13_after_boot.png' });
  await ctx.close();
  d2.kill();
}

await browser.close();
writeFileSync(OUT, JSON.stringify(report, null, 2));
const p = report.passes;
const ok1 = p.progress.reached_100 && p.progress.distinct_pcts >= 3
  && p.progress.console_errors.length === 0 && p.progress.rtl === 'rtl/fa'
  && p.progress.persian_digits_rendered && p.progress.screenshot_midway;
const ok2 = p.handoff.handed_off_ms !== null && p.handoff.spa_shell_rendered
  && p.handoff.page_errors.length === 0;
console.log(JSON.stringify({ pass_progress: ok1, pass_handoff: ok2 }, null, 0));
console.log(JSON.stringify(report, null, 2));
if (!(ok1 && ok2)) {
  console.log('WS13 RED');
  for (const d of drills) { try { d.kill(); } catch {} }
  process.exit(1);
}
console.log('WS13 GREEN');
