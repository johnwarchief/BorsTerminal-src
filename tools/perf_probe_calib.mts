/** tools/perf_probe_calib.mts — Stage 7: کالیبراسیونِ ابزارِ Stage 6 (فقط مشاهده؛ بی‌تغییرِ رفتار)
 *
 *  دو پرسش:
 *   الف) سنسورِ DOM واقعاً چه چیزی را می‌بیند؟ — نُه آزمونِ fixture رویِ **همان**
 *      `installTapeSensor` که پروب درِ صفحۀِ واقعی نصب می‌کند (import شده، نه نسخهٔ دوم).
 *   ب) خودِ پروب چقدر به آنچه اندازه می‌گیرد اضافه می‌کند؟ — چهارِ حالت رویِ یکِ
 *      تحریکِ ثابت: بی‌سنسور / سنسور / سنسور+نمونۀِ ۱s / سنسور+نمونۀِ ۲۵۰ms.
 *
 *  هرچه اینِ ابزار می‌سازد `FIXTURE` یا `INDUCED` است؛ هیچ‌کدام شاهدِ بازارِ باز نیست.
 *  تازگیِ زنده و ریزشِ رندرِ هر دلتا همچنان `BLOCKED — نیازمندِ بازارِ باز`.
 *
 *  اجرا:
 *    JEV_CHROME='…/chromium-1234/chrome-win64/chrome.exe' node --experimental-strip-types \
 *      tools/perf_probe_calib.mts --url http://127.0.0.1:5173/ --out _audit/perf_probe_calib --window 8000
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';
import { installTapeSensor, readTapeSensor, installPageHooks, clockPrecision,
         induceSensorBurst, revertSensorBurst } from './perf_probe_sensors.mts';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (r: string) => import(pathToFileURL(`${PKG}/${r}`).href);
const arg = (n: string, f = ''): string => { const i = process.argv.indexOf(`--${n}`); return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f; };
const BASE = arg('url', 'http://127.0.0.1:5173/').replace(/\/+$/, '');
const OUT = arg('out', '_audit/perf_probe_calib');
const WINDOW_MS = Math.max(2000, Math.min(Number(arg('window', '8000')) || 8000, 30000));
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });

const KEYS = ['batches', 'records', 'ignored', 'addedElems', 'removedElems', 'addedText', 'removedText',
              'text', 'textReplaced', 'flash', 'title', 'otherAttr', 'sensorCalls', 'sensorMs'];
const num = (v: unknown) => (typeof v === 'number' ? v : 0);

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME || undefined,
                                        args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const results: Record<string, unknown> = { base: BASE, at: new Date().toISOString(),
  label: 'FIXTURE/INDUCED — هیچ‌کدام شاهدِ بازارِ باز نیست', fixture: null, overhead: null, precision: null };

// ── الف) fixture: ساختارِ واقعیِ grid، بی‌برنامه، بی‌داده، بی‌شبکه ───────────
{
  const fx = await browser.newPage();
  await fx.setContent('<!doctype html><html><body>'
    + '<div data-testid="tape-scroll">'
    + '<div><div data-testid="tape-row" title="t1"><button data-testid="select-box-SYM-A"></button>'
    + '<span class="num inline-block">100</span><span class="num inline-block">200</span><span class="num inline-block">300</span></div></div>'
    + '<div><div data-testid="tape-row" title="t2"><button data-testid="select-box-SYM-B"></button>'
    + '<span class="num inline-block">400</span></div></div>'
    + '</div>'
    + '<div data-testid="outside-the-grid"><div data-testid="tape-row"><button data-testid="select-box-SYM-OUT"></button>'
    + '<span class="num inline-block">900</span></div></div>'
    + '</body></html>');
  await fx.evaluate(installTapeSensor, 'tape-scroll');
  const install = await fx.evaluate(readTapeSensor, false) as Record<string, unknown>;

  /** یکِ آزمون: snippetِ JSِ خودمفتول →_delta_هایِ شمارنده، سپس بررسیِ انتظار.
   *  ترتیبی (نه Promise.all): آزمون‌ها یکِ DOM را دستکاری می‌کنند. */
  const tests: Record<string, unknown>[] = [];
  const run = async (name: string, snippet: string, expect: Record<string, number>) => {
    const before = await fx.evaluate(readTapeSensor, false) as Record<string, number>;
    await fx.evaluate(snippet);
    await fx.waitForTimeout(150);
    const after = await fx.evaluate(readTapeSensor, false) as Record<string, number>;
    const delta: Record<string, number> = {};
    for (const k of KEYS) delta[k] = +(after[k] ?? 0) - (before[k] ?? 0);
    const failed = Object.entries(expect).filter(([k, v]) => delta[k] !== v)
      .map(([k, v]) => `${k}: expected ${v} got ${delta[k]}`);
    tests.push({ name, expect, delta, pass: failed.length === 0, why: failed.join('; ') });
  };

  await run('added-elem', `(() => { const r = document.querySelector('[data-testid="tape-row"]');
    const s = document.createElement('span'); s.className = 'num inline-block'; s.textContent = 'x'; r.appendChild(s); })()`,
    { addedElems: 1, removedElems: 0 });
  await run('removed-elem', `(() => { const r = document.querySelector('[data-testid="tape-row"]');
    r.removeChild(r.lastElementChild); })()`, { removedElems: 1 });
  await run('charData-in-num-cell (= React text update)', `(() => { const c = document.querySelector('.num.inline-block');
    c.firstChild.nodeValue = '101'; })()`, { text: 1, textReplaced: 0 });
  await run('textContent-replace (should NOT count as row churn)', `(() => { const c = document.querySelectorAll('.num.inline-block')[1];
    c.textContent = '201'; })()`, { textReplaced: 1, removedElems: 0, addedElems: 0 });
  await run('flash-up-class', `(() => { const c = document.querySelector('.num.inline-block');
    c.classList.add('flash-up'); })()`, { flash: 1 });
  await run('neutral-flash-class', `(() => { const c = document.querySelector('.num.inline-block');
    c.classList.add('flash-neutral'); })()`, { flash: 1 });
  await run('non-flash-class-only', `(() => { const c = document.querySelectorAll('.num.inline-block')[2];
    c.classList.add('font-bold'); })()`, { flash: 0, otherAttr: 1 });
  await run('title-attr', `(() => { document.querySelector('[data-testid="tape-row"]').setAttribute('title', 't9'); })()`, { title: 1 });
  await run('OUTSIDE-container-must-be-ignored', `(() => { const c = document.querySelector('[data-testid="outside-the-grid"] .num.inline-block');
    c.firstChild.nodeValue = '999'; })()`, { text: 0, records: 0, batches: 0 });

  // هویتِ چندِ نماد + بی‌هویتِ بیرون: سه سلول در دو ردیفِ داخل + یکِ سلولِ بیرون
  await fx.evaluate(`(() => { const D = window.__dom; D.events.length = 0;
    const cs = document.querySelectorAll('.num.inline-block');
    for (const c of cs) c.firstChild.nodeValue = (c.firstChild.nodeValue || '') + '!'; })()`);
  await fx.waitForTimeout(200);
  const withEv = await fx.evaluate(readTapeSensor, true) as Record<string, unknown>;
  const idEv = (withEv.events as { kind: string; sym: string | null }[]).filter((e) => e.kind === 'text');
  const syms = [...new Set(idEv.map((e) => e.sym))];
  const fxRes: Record<string, unknown> = {
    install, tests,
    multiSymbol: {
      cellsEdited: 4, eventsSawText: idEv.length, distinctSymbols: syms,
      pass: syms.length === 2 && syms.includes('SYM-A') && syms.includes('SYM-B'),
      note: 'SYM-A و SYM-B باید جدا شناخته شوند؛ SYM-OUT هیچ‌وقت نباید بیاید (بیرونِ کانتینر)',
    },
  };
  const fails = tests.filter((t) => !t.pass).map((t) => t.name);
  fxRes.verdict = (fails.length === 0 && (fxRes.multiSymbol as Record<string, unknown>).pass)
    ? 'PASS' : `FAIL: ${fails.join(', ') || 'multiSymbol'}`;
  results.fixture = fxRes;
  console.log('FIXTURE:', (results.fixture as Record<string, unknown>).verdict);
  for (const t of tests) console.log(t.pass ? ' ok  ' : ' FAIL', t.name, t.pass ? '' : t.why, JSON.stringify(t.delta));
  console.log('MULTI-SYMBOL', JSON.stringify((results.fixture as Record<string, unknown>).multiSymbol));
  await fx.close();
}

// ── ب) سربارِ خودِ ابزار رویِ برنامۀِ واقعی ────────────────────────────────
{
  const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
  await ctx.addInitScript(installPageHooks);
  const page = await ctx.newPage();
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Performance.enable');
  const metrics = async () => {
    const { metrics: m } = await cdp.send('Performance.getMetrics');
    const g = (n: string) => (m.find((x) => x.name === n)?.value ?? 0) as number;
    return { task: g('TaskDuration'), script: g('ScriptDuration'), layout: g('LayoutDuration'), style: g('RecalcStyleDuration') };
  };
  const ms = (a: number, b: number) => +((b - a) * 1000).toFixed(2);
  await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="tape-row"] .num.inline-block', { timeout: 60000 });
  await page.waitForTimeout(4000);
  results.precision = await page.evaluate(clockPrecision);

  // هزینهٔ خودِ فراخوانیِ CDP — همین، دورۀِ نمونۀِ ۲۵۰ms را تعریف می‌کند
  const rt: number[] = [];
  for (let i = 0; i < 40; i++) { const t = performance.now(); await metrics(); rt.push(+(performance.now() - t).toFixed(2)); }
  rt.sort((a, b) => a - b);
  const cdpRt = { n: rt.length, medianMs: rt[rt.length >> 1], p95Ms: rt[Math.floor(rt.length * 0.95)], maxMs: rt[rt.length - 1] };

  const med = (a: number[]) => { const s = [...a].sort((x, y) => x - y); return +(s[s.length >> 1]).toFixed(2); };
  const mode = async (name: string, o: { sensor: boolean; cadence: number; reps: number }) => {
    // هرِ حالت با صفحۀِ تازه: ناظرِ دوم رویِ اولی سوار نشود (وگرنه records دو برابر خوانده می‌شود)
    await page.reload({ waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="tape-row"] .num.inline-block', { timeout: 60000 });
    await page.waitForTimeout(3500);
    if (o.sensor) await page.evaluate(installTapeSensor, 'tape-scroll');
    await page.waitForTimeout(1500);
    const reps: Record<string, unknown>[] = [];
    for (let r = 0; r < o.reps; r++) {
      const idleA = await metrics();
      let samples = 0;
      if (o.cadence) {
        const until = Date.now() + WINDOW_MS;
        while (Date.now() < until) { await page.waitForTimeout(o.cadence); await metrics(); samples++; }
      } else { await page.waitForTimeout(WINDOW_MS); }
      const idleB = await metrics();
      // تحریکِ ثابت و برگردانده‌شدنی: ۱۲ کلاسِ فلاش + ۱۲ تغییرِ nodeValue (۲۴ رکورد)
      const sensorBefore = await page.evaluate(readTapeSensor, false) as Record<string, number>;
      const burstA = await metrics();
      const inj1 = await page.evaluate(induceSensorBurst, { n: 12, mode: 'class' });
      await page.evaluate(induceSensorBurst, { n: 12, mode: 'nodeValue' });
      await page.waitForTimeout(800);
      const burstB = await metrics();
      const rev = await page.evaluate(revertSensorBurst);
      const sensorAfter = await page.evaluate(readTapeSensor, false) as Record<string, number>;
      const d = (k: string) => num(sensorAfter[k]) - num(sensorBefore[k]);
      reps.push({
        r, windowSamples: samples,
        idleMs: { task: ms(idleA.task, idleB.task), script: ms(idleA.script, idleB.script),
                  layout: ms(idleA.layout, idleB.layout), style: ms(idleA.style, idleB.style) },
        burstMs: { task: ms(burstA.task, burstB.task), script: ms(burstA.script, burstB.script),
                   layout: ms(burstA.layout, burstB.layout), style: ms(burstA.style, burstB.style) },
        injected: inj1, reverted: rev,
        sensorSelf: o.sensor ? { batches: d('batches'), records: d('records'), flash: d('flash'),
                                  text: d('text'), ms: +d('sensorMs').toFixed(2) } : null,
      });
      await page.waitForTimeout(1200);
    }
    return {
      name, sensor: o.sensor, cadenceMs: o.cadence, reps,
      medianIdleScriptMs: med(reps.map((x) => (x.idleMs as Record<string, number>).script)),
      medianBurstScriptMs: med(reps.map((x) => (x.burstMs as Record<string, number>).script)),
      medianBurstTaskMs: med(reps.map((x) => (x.burstMs as Record<string, number>).task)),
      medianBurstStyleMs: med(reps.map((x) => (x.burstMs as Record<string, number>).style)),
      medianSensorSelfMs: o.sensor ? med(reps.map((x) => (x.sensorSelf as Record<string, number>).ms)) : 0,
      totalSamples: reps.reduce((a, x) => a + (x.windowSamples as number), 0),
    };
  };

  const REPS = Math.max(1, Math.min(Number(arg('reps', '3')) || 3, 6));
  const m0 = await mode('A-be-Sensor', { sensor: false, cadence: 0, reps: REPS });
  const m1 = await mode('B-Sensor', { sensor: true, cadence: 0, reps: REPS });
  const m2 = await mode('C-Sensor-1s', { sensor: true, cadence: 1000, reps: REPS });
  const m3 = await mode('D-Sensor-250ms', { sensor: true, cadence: 250, reps: REPS });

  results.overhead = {
    windowMs: WINDOW_MS, burstRecords: 24, reps: REPS, cdpGetMetricsRoundtrip: cdpRt, modes: [m0, m1, m2, m3],
    probeOverheadVsA: {
      idleScriptMs: [m1, m2, m3].map((x) => +(x.medianIdleScriptMs - m0.medianIdleScriptMs).toFixed(2)),
      burstScriptMs: [m1, m2, m3].map((x) => +(x.medianBurstScriptMs - m0.medianBurstScriptMs).toFixed(2)),
      burstTaskMs: [m1, m2, m3].map((x) => +(x.medianBurstTaskMs - m0.medianBurstTaskMs).toFixed(2)),
      burstStyleMs: [m1, m2, m3].map((x) => +(x.medianBurstStyleMs - m0.medianBurstStyleMs).toFixed(2)),
    },
    samplerExtraPerSampleMs: +(
      (m3.medianIdleScriptMs - m2.medianIdleScriptMs) /
      Math.max(1, (m3.totalSamples / REPS) - (m2.totalSamples / REPS))).toFixed(4),
    note: 'A هیچِ ناظری ندارد، پس اختلافِ B/C/D با A سربارِ خودِ ابزار است نه کارِ برنامه. هرِ حالت رویِ صفحۀِ تازه و با reps=' + REPS + ' (میانه) — یکِ نمونه برایِ تفکیکِ سربارِ ~۰.۲ms کافی نیست. تحریکِ ۲۴رکوردی INDUCED است، نه دلتایِ بازار، و کامل برگردانده می‌شود.',
  };
  console.log('PRECISION', JSON.stringify(results.precision));
  console.log('CDP roundtrip', JSON.stringify(cdpRt));
  for (const x of [m0, m1, m2, m3]) {
    console.log(x.name, '| idle script', x.medianIdleScriptMs, '| burst script', x.medianBurstScriptMs,
                '| burst task', x.medianBurstTaskMs, '| burst style', x.medianBurstStyleMs,
                '| sensor self', x.medianSensorSelfMs, '| samples', x.totalSamples);
  }
  console.log('OVERHEAD vs A', JSON.stringify((results.overhead as Record<string, unknown>).probeOverheadVsA));

  // ── E) بازیابیِ نسبت‌دهی: آیا فرمولِ پنجره‌ایِ پروب (s0=نمونۀِ پیش از رویداد،
  //      s1=نمونۀِ پس از +۲.۵s) هزینهٔ *معروفِ* یکِ رویداد را برمی‌گرداند؟
  //      بی‌این، عددِ scriptMsAfterِ هر دلتا درِ بازارِ باز فقط یکِ ادعاست.
  await page.reload({ waitUntil: 'domcontentloaded' });
  await page.waitForSelector('[data-testid="tape-row"] .num.inline-block', { timeout: 60000 });
  await page.waitForTimeout(3500);
  await page.evaluate(installTapeSensor, 'tape-scroll');
  const trials: Record<string, unknown>[] = [];
  for (let tr = 0; tr < 4; tr++) {
    for (const cad of [1000, 250]) {
      await page.waitForTimeout(2000);
      const series: { t: number; task: number; script: number; style: number }[] = [];
      const until = Date.now() + 6000;
      while (Date.now() < until) {
        await page.waitForTimeout(cad);
        const m = await metrics();
        series.push({ t: Date.now(), task: m.task, script: m.script, style: m.style });
      }
      // رویدادِ معروف: همان تحریکِ ۲۴رکوردی، با سنجشِ مستقیمِ دورِ خودش
      await page.waitForTimeout(1500);
      const directA = await metrics();
      const tEvent = Date.now();
      await page.evaluate(induceSensorBurst, { n: 12, mode: 'class' });
      await page.evaluate(induceSensorBurst, { n: 12, mode: 'nodeValue' });
      await page.waitForTimeout(1200);
      const directB = await metrics();
      await page.evaluate(revertSensorBurst);
      await page.waitForTimeout(1500);
      const tail = await metrics();
      series.push({ t: Date.now(), task: tail.task, script: tail.script, style: tail.style });
      // فرمولِ پروب رویِ همین series
      const beforeS = series.filter((s) => s.t <= tEvent);
      const s0 = beforeS[beforeS.length - 1] ?? series[0];
      const s1 = series.filter((s) => s.t > tEvent + 2500)[0] ?? series[series.length - 1];
      trials.push({
        cadenceMs: cad, trial: tr,
        directTaskMs: ms(directA.task, directB.task), directScriptMs: ms(directA.script, directB.script),
        attributedTaskMs: +(((s1?.task ?? 0) - (s0?.task ?? 0)) * 1000).toFixed(2),
        attributedScriptMs: +(((s1?.script ?? 0) - (s0?.script ?? 0)) * 1000).toFixed(2),
        attributionWindowMs: (s1?.t ?? 0) - (s0?.t ?? 0),
      });
    }
  }
  const recov = (k: string, cad: number) => {
    const a = trials.filter((x) => x.cadenceMs === cad) as Record<string, number>[];
    return { n: a.length, directMed: med(a.map((x) => x['direct' + k + 'Ms'] as number)),
             attributedMed: med(a.map((x) => x['attributed' + k + 'Ms'] as number)) };
  };
  results.attributionRecovery = {
    trials,
    summary: {
      task_1000ms: recov('Task', 1000), task_250ms: recov('Task', 250),
      script_1000ms: recov('Script', 1000), script_250ms: recov('Script', 250),
    },
    verdict: 'رویدادِ معروف = تحریکِ ۲۴رکوردیِ INDUCED؛ direct = سنجشِ چسبیده به خودِ رویداد؛ attributed = فرمولِ پنجره‌ایِ پروب',
  };
  console.log('ATTRIBUTION RECOVERY', JSON.stringify(results.attributionRecovery.summary));
  for (const t of trials as Record<string, unknown>[]) console.log(' cad', t.cadenceMs, 'direct task', t.directTaskMs, '→ attributed', t.attributedTaskMs, '| direct script', t.directScriptMs, '→ attributed', t.attributedScriptMs);
}

writeFileSync(`${OUT}.json`, JSON.stringify(results, null, 1), 'utf8');
console.log('OUT →', `${OUT}.json`);
await browser.close();
