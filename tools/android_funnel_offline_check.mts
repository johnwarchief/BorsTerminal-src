#!/usr/bin/env node
/**
 * tools/android_funnel_offline_check.mts — قیفِ آفلاین رویِ WebViewِ واقعی
 *
 * چرا این فایل هست: گاردهایِ M1..M7 و vitest قراردادِ کلید و پاسخِ موتور را
 * می‌سنجند، اما هیچ‌کدام «APKِ نصب‌شده رویِ دستگاه» نیست. تنها چیزی که
 * ادعایِ بندِ ۵ مأموریت را ثابت می‌کند: همان resolveLocalِ خودِ APK، رویِ همان
 * SQLite و SQLite-wasmِ خودِ بسته، هر هشتِ کلیدِ canonical را با بارِ واقعی
 * بدهد؛ پاسخِ status:error «بازارِ خالی» نشود؛ و کلیدِ پشتیبانی‌نشده پیامِ
 * روشن بدهد نه جدولِ خالی.
 *
 * چگونه: به همان DevToolsِ android_webview_check.mts وصل می‌شود (adb forward
 * 9222) و window.__borsProbe.ask را صدا می‌زند — پرسش از خودِ رزولوورِ بیلد،
 * بی‌هرگزِ دوباره‌سازیِ کلید درِ این فایل. بیلدی که پرچمِ probe را ندارد ⇒
 * exit 3 (PARTIAL/NOT_PROVEN، نه سبزِ جعلی؛ نه FAILِ اپ).
 *
 *   node --experimental-strip-types tools/android_funnel_offline_check.mts \
 *        --base http://127.0.0.1:9222 --out _audit/android_funnel/funnel.json
 *
 * خروجِ exit: 0 هر هشت سبز + تله‌ها درست · 1 رأیِ رد ازِ خودِ برنامه ·
 * 2 بی‌CDP · 3 بیلد بی‌قلابِ probe است.
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const args = process.argv.slice(2);
const arg = (name: string, dflt = ''): string => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const BASE = arg('base', 'http://127.0.0.1:9222');
const OUT = arg('out', '_audit/android_funnel/funnel.json');
const WAIT_MS = Number(arg('wait', '1500'));

// فهرستِ کلیدها ازِ همان شبکه‌ای که resolvers.ts و build_mobile_snapshot.py
// می‌سازند — اینجا فقط preset×logic، چون دو جزءِ دیگرِ رشته درِ رزولوور
// ثابت‌اند (standard/ds1) و dev/mobile_funnel_offline_v1116.py بیت‌به‌بیت
// قفلشان کرده. اگر روزی شبکه عوض شود، آن گارد قرمز می‌شود، نه این سنجه.
const PRESETS = ['trend', 'swing', 'hourglass', 'custom'];
const LOGICS = ['and', 'or'];

async function connect(wsUrl: string): Promise<WebSocket> {
  const ws = new WebSocket(wsUrl);
  await new Promise<void>((res, rej) => {
    ws.onopen = () => res();
    ws.onerror = () => rej(new Error(`CDP open failed: ${wsUrl}`));
    setTimeout(() => rej(new Error('CDP open timeout')), 8000);
  });
  return ws;
}

function makeClient(ws: WebSocket) {
  let id = 0;
  const pending = new Map<number, (v: unknown) => void>();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(String(ev.data));
    if (msg.id && pending.has(msg.id)) {
      const done = pending.get(msg.id)!;
      pending.delete(msg.id);
      done(msg);
    }
  };
  const evaluate = (expr: string, ms = 30000): Promise<{ ok: boolean; value?: unknown; err?: string }> =>
    new Promise((res) => {
      const mid = ++id;
      const t = setTimeout(() => {
        if (pending.has(mid)) { pending.delete(mid); res({ ok: false, err: `timeout ${ms}ms` }); }
      }, ms);
      pending.set(mid, (v: unknown) => {
        clearTimeout(t);
        const r = v as { result?: { value?: unknown }; exceptionDetails?: { exception?: { description?: string } } };
        if (r?.exceptionDetails) {
          res({ ok: false, err: r.exceptionDetails.exception?.description || 'exception' });
        } else res({ ok: true, value: r?.result?.value });
      });
      ws.send(JSON.stringify({ id: mid, method: 'Runtime.evaluate',
        params: { expression: expr, returnByValue: true, awaitPromise: true } }));
    });
  const send = (method: string): Promise<void> =>
    new Promise((res) => {
      const mid = ++id;
      pending.set(mid, () => res());
      ws.send(JSON.stringify({ id: mid, method, params: {} }));
      setTimeout(res, 4000);
    });
  return { evaluate, send };
}

const report: Record<string, unknown> = { at: new Date().toISOString(), base: BASE, keys: {}, guard: {} };

let pages: { url: string; webSocketDebuggerUrl?: string }[] = [];
try {
  const res = await fetch(`${BASE}/json/list`, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`CDP list ${res.status}`);
  pages = ((await res.json()) as any[]).filter((p) => p.type === 'page' && p.webSocketDebuggerUrl);
} catch (e) {
  report.fatal = `no CDP endpoint: ${(e as Error).message}`;
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify(report));
  process.exit(2);
}
if (!pages.length) {
  report.fatal = 'هیچ pageِ CDP نیست؛ WebView باز نشده';
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
  process.exit(2);
}

const ws = await connect(pages[0].webSocketDebuggerUrl!);
const c = makeClient(ws);
await c.send('Runtime.enable');
await new Promise((r) => setTimeout(r, WAIT_MS));

// قلابِ probe درِ main.tsx داینامیک ایمپورت می‌شود؛ پیش ازِ پاسخِ بانک ممکن
// است هنوز ننشسته باشد — پنج تلاشِ رشدیافته بی‌دروغ‌گویی.
let haveProbe = false;
for (let i = 1; i <= 5; i++) {
  const r = await c.evaluate('typeof window.__borsProbe==="object"&&__borsProbe.version===1? "yes":"no"');
  if (r.ok && r.value === 'yes') { haveProbe = true; break; }
  await new Promise((r2) => setTimeout(r2, 4000 * i));
}
if (!haveProbe) {
  report.fatal = 'window.__borsProbe نیست ⇒ این بیلد با VITE_ANDROID_PROBE ساخته نشده؛ سنجشِ قیفِ آفلاین ازِ این artifact ممکن نیست (NOT_PROVEN، نه FAILِ اپ)';
  mkdirSync(dirname(OUT), { recursive: true });
  writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
  console.log(JSON.stringify(report));
  ws.close();
  process.exit(3);
}

report.boot_timing = (await c.evaluate('JSON.stringify(window.bootTiming||null)')).value;

type KeyResult = { key: string; verdict: string; detail?: unknown };
const keys: KeyResult[] = [];
for (const preset of PRESETS) {
  for (const logic of LOGICS) {
    const expr = `__borsProbe.ask('/api/funnel?preset=${preset}&logic=${logic}&fund_mode=standard&drop_suffix=true&chain=')`
      + `.then(r=>JSON.stringify(r))`;
    const r = await c.evaluate(expr);
    const key = `funnel/${preset}/${logic}/standard/ds1`;
    if (!r.ok) { keys.push({ key, verdict: 'EVAL-ERROR', detail: r.err }); continue; }
    const v = JSON.parse(String(r.value));
    // قراردادِ «بارِ واقعی» همان چیزی است که CI درِ گامِ bundle می‌سنجد:
    // status∈{null,success} + entries + status_matrix + universe.joined>0.
    const good = v.ok && (v.status === null || v.status === 'success')
      && (v.entries ?? 0) > 0 && (v.matrixCells ?? 0) > 0 && (v.joined ?? 0) > 0;
    keys.push({ key, verdict: good ? 'REAL-PAYLOAD' : 'BAD', detail: v });
  }
}
report.keys = keys;

// تلهٔ M7 رویِ دستگاه: پاسخِ ۲۰۰ِ بی‌status_matrix ازِ موتورِ زنده نیست، اما
// قراردادِ آفلاین باید پاسخِ status=error را هم «خطا» ببیند نه جدولِ صفر.
// مسیرِ پشتیبانی‌نشده (chain دستی) هم باید پیامِ روشن بدهد، نه ردِ بی‌صدا.
const guardUnsup = await c.evaluate(
  `__borsProbe.ask('/api/funnel?preset=trend&logic=and&fund_mode=standard&drop_suffix=true&chain=f_clock')`
  + `.then(r=>JSON.stringify(r))`);
const guardDs = await c.evaluate(
  `__borsProbe.ask('/api/funnel?preset=trend&logic=and&fund_mode=standard&drop_suffix=false&chain=')`
  + `.then(r=>JSON.stringify(r))`);
report.guard.unsupported_chain = guardUnsup.value ?? guardUnsup.err;
report.guard.drop_suffix_off = guardDs.value ?? guardDs.err;

ws.close();
mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');

const bad = keys.filter((k) => k.verdict !== 'REAL-PAYLOAD');
const uns = (() => { try { return JSON.parse(String(guardUnsup.value)); } catch { return null; } })();
const dsOff = (() => { try { return JSON.parse(String(guardDs.value)); } catch { return null; } })();
// سنجه‌هایِ رأی: (۱) هر هشت کلید با بارِ واقعی (۲) ترکیبِ پشتیبانی‌نشده خطایِ
// روشنِ ۴۰۴ با پیامِ فارسی، نه داده (۳) ds0 هم ردِ روشن — پخته نشده.
const okG1 = bad.length === 0;
const okG2 = !!uns && uns.ok === false && uns.http === 404 && typeof uns.message === 'string'
  && uns.message.includes('پخته نشده');
const okG3 = !!dsOff && dsOff.ok === false && dsOff.http === 404;
const fail = !okG1 || !okG2 || !okG3;
console.log(JSON.stringify({ keys_total: keys.length, keys_ok: keys.length - bad.length,
  guard_unsupported: okG2, guard_ds0: okG3, boot: report.boot_timing }, null, 2));
process.exit(fail ? 1 : 0);
