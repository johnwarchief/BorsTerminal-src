#!/usr/bin/env node
/**
 * tools/android_webview_check.mts — آزمونِ زندهٔ WebView رویِ دستگاه/شبیه‌ساز
 *
 * چرا این فایل هست: تا پیش‌ازِ این، هر سنجشِ «اندروید» یا درِ jsdom (Vitest)
 * انجام می‌شد یا درِ Chromiumِ دسکتاپ با user-agent موبایل. هیچ‌کدام WebView
 * واقعیِ اندروید نیست: نه `env(safe-area-inset-*)` را مثلِ آن می‌دهد، نه
 * پلِ بومی/CapacitorHttp را صدا می‌زند، نه صفحه‌کلید و نه چرخۀِ عمرِ Activity.
 * این اسکریپت به DevToolsِ همان WebView وصل می‌شود (adb forward tcp:9222 →
 * localabstract:webview_devtools_remote_<pid>) و همان چیزهایی را می‌خواند که
 * درِ گوشیِ واقعی دیده می‌شود. بدونِ dependencyِ بیرونی: WebSocket درِ خودِ
 * Node 22 هست.
 *
 * پیش‌نیاز: بیلدِ **debuggable** (درِ buildِ release خودِ WebView
 * `setWebContentsDebuggingEnabled` نمی‌گیرد و این نقطۀ اتصال وجود ندارد).
 *
 *   node --experimental-strip-types tools/android_webview_check.mts \
 *        --base http://127.0.0.1:9222 --label 390x844 --out _audit/android_webview.json
 *
 * خروجی: JSON با هر ادعا + کدِ خروج. صفر فقط وقتی که همهٔ سنجه‌هایِ سخت پاس
 * باشند؛ نبودِ اتصال ⇒ exit 2 (نه PASS).
 */
import { writeFileSync, mkdirSync } from 'node:fs';
import { dirname } from 'node:path';

const args = process.argv.slice(2);
const arg = (name: string, dflt = ''): string => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] ? args[i + 1] : dflt;
};
const BASE = arg('base', 'http://127.0.0.1:9222');
const LABEL = arg('label', 'device');
const OUT = arg('out', `_audit/android_webview_${LABEL}.json`);
const WAIT_MS = Number(arg('wait', '1500'));

type Eval = { ok: boolean; value?: unknown; err?: string };

/** یک اتصالِ کوتاهِ CDP به یکِ target؛ بعد ازِ هرِ فرمان بسته می‌شود تا
 *  reconnectِ بعدی (پس ازِ تغییرِ wm size) با targetِ تازه کار کند. */
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
  const events: { method: string; params: Record<string, unknown> }[] = [];
  ws.onmessage = (ev) => {
    const msg = JSON.parse(String(ev.data));
    if (msg.id && pending.has(msg.id)) {
      const done = pending.get(msg.id)!;
      pending.delete(msg.id);
      done(msg);
    } else if (msg.method) {
      events.push({ method: msg.method, params: msg.params || {} });
    }
  };
  const send = (method: string, params: Record<string, unknown> = {}, ms = 25000): Promise<any> =>
    new Promise((res) => {
      const mid = ++id;
      // بی‌مهلت، یکِ CDPِ بی‌پاسخ (WebView که DevTools را نگه نداشته) پروسه را
      // معلق می‌کرد و Node با کدِ ۱۳ (top-level await ناتمام) خارج می‌شد —
      // یعنی «FAIL» بی‌هیچ سطرِ توضیح. حالا همان حالت یکِ خطایِ خوانا است.
      const t = setTimeout(() => {
        if (pending.has(mid)) { pending.delete(mid); res({ __timeout: method }); }
      }, ms);
      pending.set(mid, (v: unknown) => { clearTimeout(t); (res as (v: unknown) => void)(v); });
      ws.send(JSON.stringify({ id: mid, method, params }));
    });
  const evaluate = async (expr: string): Promise<Eval> => {
    const r = await send('Runtime.evaluate', {
      expression: expr, returnByValue: true, awaitPromise: true,
    });
    if (r?.__timeout) return { ok: false, err: `timeout: ${r.__timeout}` };
    if (r?.exceptionDetails) {
      return { ok: false, err: r.exceptionDetails.exception?.description || 'exception' };
    }
    return { ok: true, value: r?.result?.value };
  };
  return { send, evaluate, events };
}

async function listPages(): Promise<{ id: string; url: string; title: string; webSocketDebuggerUrl?: string }[]> {
  // مهلتِ سخت: adb forward می‌تواند سوکتی بدهد که هیچ‌وقت جواب نمی‌دهد (اپ درِ
  // حالتِ نیمه‌مرده). بی‌AbortSignal، `fetch` دقیقه‌ها بلوکه می‌ماند و کلِ job
  // را می‌خورد — همان چیزی که درِ رانِ 38668608986 دیدیم.
  const res = await fetch(`${BASE}/json/list`, { signal: AbortSignal.timeout(10000) });
  if (!res.ok) throw new Error(`CDP list ${res.status}`);
  const all = (await res.json()) as any[];
  return all.filter((p) => p.type === 'page' && p.webSocketDebuggerUrl);
}

const report: Record<string, unknown> = {
  label: LABEL, at: new Date().toISOString(), base: BASE, checks: {}, secrets: {}, console: {},
};
const set = (k: string, v: unknown) => { (report.checks as Record<string, unknown>)[k] = v; };

let pages: Awaited<ReturnType<typeof listPages>> = [];
try {
  pages = await listPages();
} catch (e) {
  report.fatal = `no CDP endpoint at ${BASE}: ${(e as Error).message}`;
  console.log(JSON.stringify(report, null, 2));
  process.exit(2);
}
if (!pages.length) {
  report.fatal = 'هیچ pageِ CDP نیست؛ WebView باز نشده (اپ اجرا نیست؟)';
  console.log(JSON.stringify(report, null, 2));
  process.exit(2);
}
const page = pages[0];
console.log(`CDP target: ${page.url} · title=${page.title}`);
set('page_url', page.url);
set('page_title', page.title);

const ws = await connect(page.webSocketDebuggerUrl!);
const c = makeClient(ws);
await c.send('Runtime.enable');
await c.send('Page.enable');
await c.send('Network.enable');
await c.send('Log.enable');
await new Promise((r) => setTimeout(r, WAIT_MS));

// ۰) دروازۀ ورودِ محلی: رویِ گوشی هم مثلِ کاربر، اگر صفحهٔ رمز آمد باز شود.
// بی‌این، «صفحه سفید نیست» با «برنامۀ واقعی باز شد» قاطی می‌شود: درِ صفحهٔ
// ورود هم گره و متن هست، ولی هیچ داده‌ای نمایش داده نشده. رمزِ پیش‌فرض درِ
// sourceِ عمومیِ همین مخزن است (authStore.ts: DEFAULT_USER/DEFAULT_PASS) —
// چیزی برایِ حدس‌زدن نیست و هیچ حسابِ واقعی درِ کار نیست.
await c.evaluate(
  '(()=>{const u=document.querySelector("input[type=text],input:not([type])");' +
  'const p=document.querySelector("input[type=password]");' +
  'if(!u||!p) return "no-gate";' +
  'const set=(el,v)=>{const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,"value").set;' +
  's.call(el,v);el.dispatchEvent(new Event("input",{bubbles:true}));};' +
  'set(u,"admin");set(p,"bors123");' +
  'const b=Array.from(document.querySelectorAll("button")).find(x=>/ورود/.test(x.textContent||""));' +
  'if(b) b.click(); return "submitted"})()');
await new Promise((r) => setTimeout(r, 6000));

// ۱) صفحه سفید نیست؟ — تعدادِ گره‌ها + همان چیزی که کاربر باید ببیند
set('dom_nodes', (await c.evaluate('document.querySelectorAll("*").length')).value);
set('testids', (await c.evaluate(
  'Array.from(document.querySelectorAll("[data-testid]")).slice(0,60).map(e=>e.getAttribute("data-testid"))')).value);
set('visible_text_len', (await c.evaluate(
  'document.body ? document.body.innerText.replace(/\\s+/g," ").trim().length : 0')).value);
// «سفید نیست» با «برنامۀ واقعی باز شده» یکی نیست: درِ صفحۀ ورود هم گره و متن
// هست. تنها چیزی که ادعا را اثبات می‌کند، متنِ خودِ تابلوست.
set('reached_content', (await c.evaluate(
  '(()=>{const t=document.body.innerText||"";' +
  'if(/نام کاربری|رمز عبور/.test(t)&&!/شاخص کل/.test(t)) return "login-gate";' +
  'if(/شاخص کل|ارزش معاملات بازار|نوسان‌گیر/.test(t)) return "board";' +
  'if(/پیدا نشد/.test(t)) return "not-found";return "other"})()')).value);
set('route', (await c.evaluate('location.hash || location.pathname')).value);

// ۲) دیتابیسِ بسته واقعاً باز شده؟ bootTiming را خودِ localData رویِ window می‌گذارد
set('boot_timing', (await c.evaluate(
  'JSON.stringify(window.bootTiming||null)')).value);

// ۳) پلِ بومی و حالتِ اجرا
set('is_native', (await c.evaluate(
  'String(!!(window.Capacitor && typeof window.Capacitor.isNativePlatform==="function" && window.Capacitor.isNativePlatform()))')).value);
set('webview_chrome', (await c.evaluate('(navigator.userAgent.match(/Chrome\\/[\\d.]+/)||[""])[0]')).value);

// ۴) safe-area: env() رویِ این دستگاه چقدر است و viewport-fit نشسته؟
set('viewport_meta', (await c.evaluate(
  '(document.querySelector("meta[name=viewport]")||{}).content||null')).value);
const probe = await c.evaluate(
  '(()=>{const d=document.createElement("div");' +
  'd.style.cssText="position:fixed;left:0;bottom:0;padding-bottom:env(safe-area-inset-bottom,0px);' +
  'padding-top:env(safe-area-inset-top,0px);visibility:hidden";' +
  'document.body.appendChild(d);const cs=getComputedStyle(d);' +
  'const r={top:cs.paddingTop,bottom:cs.paddingBottom};d.remove();return JSON.stringify(r)})()');
set('safe_area_probe', probe.value ?? probe.err);
set('nav_bar_box', (await c.evaluate(
  '(()=>{const el=document.querySelector("[data-testid=mobile-nav],nav.bors-bottom,.bors-bottom");' +
  'if(!el)return null;const b=el.getBoundingClientRect();' +
  'return JSON.stringify({x:Math.round(b.x),y:Math.round(b.y),w:Math.round(b.width),h:Math.round(b.height),bottom:Math.round(b.bottom)})})()')).value);
set('body_overflow_x', (await c.evaluate(
  'JSON.stringify({scroll:document.documentElement.scrollWidth-clientWidth,client:clientWidth,innerH:window.innerHeight,innerW:window.innerWidth,dpr:devicePixelRatio})')).value);

// ۵) شبکه: هر درخواستی که تا اینجا رد شده، با وضعیتِ واقعی
const netEvents = c.events.filter((e) => e.method === 'Network.responseReceived' || e.method === 'Network.loadingFailed');
set('network', netEvents.slice(0, 80).map((e) => {
  const p = e.params as any;
  return e.method === 'Network.responseReceived'
    ? { url: p.response.url, status: p.response.status, type: p.type }
    : { url: (p.request && p.request.url) || 'unknown', failed: p.errorText || p.type };
}));

// ۶) هر چیزی که WebView به console فرستاده + هر رشتهٔ شبیه رمز
const consoleEvents = c.events.filter((e) => e.method === 'Runtime.consoleAPICalled' || e.method === 'Log.entryAdded');
const lines = consoleEvents.map((e) => {
  const p = e.params as any;
  if (e.method === 'Log.entryAdded') return `[${p.entry.level}] ${p.entry.source||''} ${String(p.entry.text||'').slice(0,200)}`;
  const txt = (p.args || []).map((a: any) => String(a.value ?? a.description ?? a.type ?? '')).join(' ');
  return `[${p.type}] ${txt.slice(0, 300)}`;
});
const secretish = lines.filter((l) => /(authorization|bearer|token|passwo?rd|api[-_ ]?key|secret)/i.test(l));
report.secrets = { scanned_lines: lines.length, hits: secretish.length, sample: secretish.slice(0, 5) };
report.console = { errors: lines.filter((l) => l.startsWith('[error]') || l.startsWith('[warning]')).slice(0, 25) };

ws.close();

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 2), 'utf8');
console.log(JSON.stringify(report, null, 2));

// حکم: سفیدیبودن، نبودِ داده، موندن پشتِ دروازۀ ورود، و نشتِ رمز، چهار «رد»ِ
// سخت‌اند. بی‌این سه اول، «اپ باز شد» از رویِ هر صفحۀ غیرخالی ادعا می‌شد.
const nodes = Number(report.checks.dom_nodes || 0);
const textLen = Number(report.checks.visible_text_len || 0);
const reached = String(report.checks.reached_content || 'other');
const fail = nodes < 150 || textLen < 40 || secretish.length > 0 || reached !== 'board';
process.exit(fail ? 1 : 0);
