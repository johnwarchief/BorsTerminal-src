/** tools/perf_probe_sensors.mts — کدِ درونِ صفحۀِ پروب (Stage 7)
 *
 *  چرا فایلِ جدا: تا ابزارِ کالیبراسیون (`perf_probe_calib.mts`) **همان** تابعی را
 *  تست کند که پروب درِ صفحه نصب می‌کند. اگر نسخهٔ دومی از سنسور نوشته شود، سبز شدنِ
 *  تستِ سنسور هیچ چیزی دربارهٔ پروب ثابت نمی‌کند (سابقۀ این ریپو: گاردهایی که
 *  متنِ سورس را می‌خوانند نه رفتارِ واقعی را).
 *
 *  سه چیز را جدا می‌شمارد تا «زمانِ دریافت» با «زمانِ اجرای callback» قاطی نشود:
 *    • `sensorCalls` / `sensorMs` — وقتِ خودِ ناظر (خودسنجی با performance.now)
 *    • `batches` / `batchTimes`  — لحظۀِ flushِ mutation (نزدیک‌ترین معیارِ موجود به commitِ DOM)
 *    • `events[]`                — نوعِ تغییر + هویتِ ردیف، با مهرِ Date.now()
 *
 *  تفکیکِ «تغییرِ مقدار» از «تغییرِ ساختار» (درسِ کالیبراسیونِ Stage 7):
 *    گرهٔ متنی که جایگزین می‌شود تغییرِ داده است، نه کوه‌کشیِ ردیف. پس
 *    `addedElems/removedElems` (ساختار) از `text/textReplaced/flash` (مقدار) جداست.
 */

export type SensorKind = 'added' | 'removed' | 'addedText' | 'removedText'
  | 'text' | 'textReplaced' | 'flash' | 'title' | 'otherAttr';

/** ناظرِ تابلو. `rootTestId` کانتینرِ مجازی‌سازی است؛ بیرونِ آن هیچ چیزی شمارش نمی‌شود. */
export function installTapeSensor(rootTestId: string): void {
  const w = window as unknown as Record<string, any>;
  const host = document.querySelector(`[data-testid="${rootTestId}"]`);
  w.__dom = {
    installed: !!host,
    hostTag: host ? (host.getAttribute('data-testid') || host.tagName) : null,
    rootTestId,
    t0: Date.now(),
    batches: 0, addedElems: 0, removedElems: 0, addedText: 0, removedText: 0,
    text: 0, textReplaced: 0, flash: 0, otherAttr: 0, title: 0,
    sensorCalls: 0, sensorMs: 0, records: 0, ignored: 0,
    events: [] as { t: number; kind: string; sym: string | null }[],
    batchTimes: [] as number[],
    rowsSeen: 0,
  };
  const D = w.__dom;
  // خودسنجی: یک performance.now() در هر دسته. دقتِ اینِ Chromium ~۰.۱ms اندازه‌گیری
  // شده، پس sensorMs درِ دسته‌هایِ تک‌رکوردی صفر خوانده می‌شود — کفِ دقت، نه صفرِ واقعی.
  const symOf = (n: Element | null): string | null => {
    const row = n?.closest?.('[data-testid="tape-row"]');
    if (!row) return null;
    const box = row.querySelector('[data-testid^="select-box-"]');
    return box ? String(box.getAttribute('data-testid')).slice('select-box-'.length) : 'row#no-id';
  };
  const isNumCell = (el: Element | null): boolean =>
    !!el && typeof el.className === 'string' && el.className.includes('inline-block') && el.className.includes('num');
  const parentEl = (t: Node): Element | null =>
    ((t.nodeType === 1 ? t : t.parentElement) as Element) ?? null;

  const classify = (m: MutationRecord): { kind: SensorKind | null; el: Element | null } => {
    if (m.type === 'characterData') {
      const p = parentEl(m.target);
      return { kind: isNumCell(p) ? 'text' : 'otherAttr', el: p };
    }
    if (m.type === 'childList') {
      const el = parentEl(m.target);
      let addE = 0, addT = 0, remE = 0, remT = 0;
      m.addedNodes.forEach((n) => { if (n.nodeType === 3) addT++; else if (n.nodeType === 1) addE++; });
      m.removedNodes.forEach((n) => { if (n.nodeType === 3) remT++; else if (n.nodeType === 1) remE++; });
      // متنِ کهنه رفته + متنِ تازه آمده = جایگزینیِ مقدارِ همان سلول
      if (remT && addT) return { kind: 'textReplaced', el: isNumCell(el) ? el : parentEl(el) };
      if (addE) return { kind: 'added', el };
      if (remE) return { kind: 'removed', el };
      if (addT) return { kind: 'addedText', el };
      if (remT) return { kind: 'removedText', el };
      return { kind: null, el };
    }
    const el = parentEl(m.target);
    const cls = el && (el as Element).className;
    if (m.attributeName === 'class') {
      const k = isNumCell(el) && /(^| )flash-(up|down|neutral)( |$)/.test(cls as string) ? 'flash' : 'otherAttr';
      return { kind: k, el };
    }
    if (m.attributeName === 'title') return { kind: 'title', el };
    return { kind: 'otherAttr', el };
  };

  new MutationObserver((muts) => {
    const s0 = performance.now();
    D.batches++;
    D.records += muts.length;
    if (D.batchTimes.length < 8000) D.batchTimes.push(Date.now());
    for (const m of muts) {
      const c = classify(m);
      if (!c.kind) { D.ignored++; continue; }
      const k = c.kind;
      if (k === 'added') D.addedElems += m.addedNodes.length;
      else if (k === 'removed') D.removedElems += m.removedNodes.length;
      else if (k === 'addedText') D.addedText += m.addedNodes.length;
      else if (k === 'removedText') D.removedText += m.removedNodes.length;
      else if (k === 'text') D.text++;
      else if (k === 'textReplaced') D.textReplaced++;
      else if (k === 'flash') D.flash++;
      else if (k === 'title') D.title++;
      else D.otherAttr++;
      if (D.events.length < 60000) {
        D.events.push({ t: Date.now(), kind: k, sym: symOf(parentEl(m.target) ?? c.el) });
      }
    }
    D.sensorMs += performance.now() - s0;
    D.sensorCalls++;
  }).observe(host || document.body, {
    subtree: true, childList: true, characterData: true, attributes: true, attributeOldValue: false,
  });
  D.rowsSeen = document.querySelectorAll('[data-testid="tape-row"]').length;
}

/** شمارنده‌ها را بیرون می‌گیرد (events فقط وقتی لازم است — پنجره‌هایِ بلند سنگین‌اند). */
export function readTapeSensor(withEvents: boolean): Record<string, unknown> {
  const D = (window as unknown as Record<string, any>).__dom;
  if (!D) return { missing: true };
  const out: Record<string, unknown> = {
    installed: D.installed, hostTag: D.hostTag, batches: D.batches, records: D.records, ignored: D.ignored,
    addedElems: D.addedElems, removedElems: D.removedElems, addedText: D.addedText, removedText: D.removedText,
    text: D.text, textReplaced: D.textReplaced, flash: D.flash, title: D.title, otherAttr: D.otherAttr,
    sensorCalls: D.sensorCalls, sensorMs: +D.sensorMs.toFixed(2),
    rowsSeen: document.querySelectorAll('[data-testid="tape-row"]').length,
    batchTimes: D.batchTimes,
  };
  if (withEvents) out.events = D.events;
  return out;
}

/** قلاب‌هایِ پیش‌ازِ کدِ برنامه: rAF + fetch. بی‌خواندنِ بدنه درِ صفحه. */
export function installPageHooks(): void {
  const w = window as unknown as Record<string, any>;
  try { sessionStorage.setItem('bors_auth_session', 'true'); } catch { /* دروازۀ UI */ }
  w.__p = {
    raf: { requested: 0, executed: 0, frames: [] as number[], stacks: {} as Record<string, number> },
    fetch: [] as { url: string; t0: number; t1: number; p0: number; p1: number; status: number; bytes: number }[],
    navStart: Date.now(),
  };
  const P = w.__p;
  const origRaf = w.requestAnimationFrame.bind(w);
  w.requestAnimationFrame = function (cb: FrameRequestCallback) {
    P.raf.requested++;
    const st = (new Error().stack || '').split('\n').slice(2, 5)
      .map((s) => (s.trim().match(/at ([\w.$<>]+)/) || [0, '?'])[1]).join(' < ');
    P.raf.stacks[st] = (P.raf.stacks[st] || 0) + 1;
    return origRaf((ts) => { P.raf.executed++; if (P.raf.frames.length < 20000) P.raf.frames.push(Math.round(ts)); return cb(ts); });
  };
  const origFetch = w.fetch.bind(w);
  w.fetch = async function (input: RequestInfo | URL, init?: RequestInit) {
    const url = typeof input === 'string' ? input : input instanceof URL ? input.href : (input as Request)?.url || '';
    const track = /\/api\/market(\/delta)?\?|\/api\/market$/.test(url);
    const t0 = Date.now(); const p0 = performance.now();
    const res = await origFetch(input as RequestInfo, init);
    if (track) {
      P.fetch.push({
        url: url.replace(/^https?:\/\/[^/]+/, ''), t0, t1: Date.now(), p0, p1: performance.now(),
        status: res.status, bytes: Number(res.headers.get('content-length') || 0),
      });
      if (P.fetch.length > 4000) P.fetch.splice(0, 2000);
    }
    return res;
  };
}

/** دقتِ ساعت‌ها با بارِ واقعی (حلقۀِ ~۵۰ms) — نه حلقه‌ای که درِ یکِ تیکِ ساعت می‌گذرد. */
export function clockPrecision(): Record<string, unknown> {
  const spinUntil = performance.now() + 50;
  const ds: number[] = []; const ps: number[] = [];
  do { ds.push(Date.now()); ps.push(performance.now()); } while (performance.now() < spinUntil);
  const step = (a: number[]) => {
    const diffs: number[] = [];
    for (let i = 1; i < a.length; i++) { const d = a[i] - a[0]; if (d > 0) { diffs.push(d); break; } }
    return diffs;
  };
  const uniq = (a: number[]) => new Set(a.map((x) => Math.round(x * 1000))).size;
  return {
    callsIn50ms: ds.length,
    dateNowDistinct: uniq(ds), perfNowDistinct: uniq(ps),
    // کمترینِ گامِ غیرصفرِ دیده‌شده = کفِ دقتِ همان ساعت
    dateNowFirstNonzeroStepMs: step(ds).length ? step(ds)[0] : null,
    perfNowFirstNonzeroStepMs: step(ps).length ? +(step(ps)[0]).toFixed(4) : null,
    wallVsPerf: { dateNow: ds[0], perfNow: +ps[0].toFixed(3), timeOrigin: +performance.timeOrigin.toFixed(3) },
  };
}

/** تحریکِ کنترل‌شدهٔ سنسور (INDUCED — هرگز شاهدِ بازارِ واقعی نیست).
 *  `mode`: 'class' → کلاسِ فلاش، 'nodeValue' → تغییرِ characterData (همان کاری که React
 *  درِ به‌روزرسانیِ عدد می‌کند)، 'textContent' → جایگزینیِ گرهٔ متنی (باید textReplaced
 *  شود نه «گرهٔ حذف‌شده»). هیچ ردیفِ واقعی حذف/افزوده نمی‌شود؛ همه‌چیز برمی‌گردد. */
export function induceSensorBurst(spec: { n: number; mode: string }): Record<string, unknown> {
  const cells = [...document.querySelectorAll('[data-testid="tape-row"] .num.inline-block')] as HTMLElement[];
  if (!cells.length) return { error: 'no cells' };
  const n = Math.min(spec.n, cells.length);
  const W = window as unknown as Record<string, any>;
  const snapCls = new Map<HTMLElement, string>();
  const snapNode = new Map<HTMLElement, string | null>();
  const t0 = performance.now();
  for (let i = 0; i < n; i++) {
    const c = cells[i];
    if (spec.mode === 'class') {
      snapCls.set(c, c.className);
      c.classList.add(i % 2 ? 'flash-down' : 'flash-up');
    } else if (spec.mode === 'nodeValue') {
      if (!c.firstChild) c.appendChild(document.createTextNode('0'));
      const tn = c.firstChild as Text;
      snapNode.set(c, tn.nodeValue);
      tn.nodeValue = (tn.nodeValue || '') + ' ';
    } else {
      snapNode.set(c, c.textContent);
      c.textContent = (c.textContent || '') + ' ';
    }
  }
  const injectMs = +(performance.now() - t0).toFixed(3);
  const syms = new Set(cells.slice(0, n).map((c) => {
    const box = c.closest('[data-testid="tape-row"]')?.querySelector('[data-testid^="select-box-"]');
    return box ? String(box.getAttribute('data-testid')).slice('select-box-'.length) : null;
  }).filter(Boolean) as string[]);
  W.__burst = { snapCls, snapNode };
  return { mode: spec.mode, injected: n, distinctRowsOfInjected: syms.size,
           injectedSymbols: [...syms].slice(0, 8), injectMs };
}

/** بازگردانیِ کاملِ تحریک؛ اگر چیزی برنگردد `restored:false` می‌دهد. */
export function revertSensorBurst(): Record<string, unknown> {
  const W = window as unknown as Record<string, any>;
  const h = W.__burst;
  if (!h) return { restored: false, note: 'nothing to revert' };
  let mismatch = 0;
  (h.snapCls as Map<HTMLElement, string>).forEach((v: string, k: HTMLElement) => {
    k.className = v; if (k.className !== v) mismatch++;
  });
  (h.snapNode as Map<HTMLElement, string | null>).forEach((v: string | null, k: HTMLElement) => {
    k.textContent = v; if (k.textContent !== v) mismatch++;
  });
  W.__burst = null;
  return { restored: mismatch === 0, mismatches: mismatch };
}
