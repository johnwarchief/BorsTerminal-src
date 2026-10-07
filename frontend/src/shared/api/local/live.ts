// shared/api/local/live.ts — لایهٔ زندهٔ TSETMC روی خود دستگاه (فاز ۳ب)
//
// گوشی IP ایرانی دارد و مستقیم از cdn.tsetmc.com می‌خواند — همان اندپوینت‌ها و
// همان نگاشت فیلدهایی که test_tsetmc.py (مرجع دسکتاپ) استفاده می‌کند:
//   GetMarketWatch  → pcl/pdv/py/pf/pmn/pmx/qtj/qtc/ztt/eps + blDs(qmd,pmd,zmd,qmo,pmo,zmo)
//   GetClientTypeAll→ buy_I_Volume/… (حقیقی/حقوقی)
//   GetIndexB2History→ xNivInuClMresIbs/Ph/Pb (شاخص کل، همتای api/market_index.py)
//
// اصل صداقت داده: اگر شبکه/CORS نگذاشت (مثلاً پیش‌نمایش مرورگری)، null
// برمی‌گردد و مصرف‌کننده دادهٔ اسنپ‌شات را دست‌نخورده نشان می‌دهد — هیچ عدد
// ساختگی، هیچ خطای مزاحم. داخل اپ Capacitor (CapacitorHttp)، fetch بومی است
// و CORS ندارد.

import { nativeGetJson, nativeGetText } from './nativeHttp';

const LIVE_BASE = 'https://cdn.tsetmc.com/api';
const PT = Array.from({ length: 9 }, (_, i) => `paperTypes[${i}]=${i + 1}`).join('&');
const MW_URL = `${LIVE_BASE}/ClosingPrice/GetMarketWatch?market=0&${PT}&showTraded=false&withBestLimits=true&hEven=0`;
const CT_URL = `${LIVE_BASE}/ClientType/GetClientTypeAll`;
const TEDPIX_URL = `${LIVE_BASE}/Index/GetIndexB2History/32097828799138957`;

const HDRS: Record<string, string> = {
  Accept: 'application/json',
  // مرورگر این دو را بی‌صدا نادیده می‌گیرد (هدر ممنوعه)؛ CapacitorHttp بومی می‌فرستد
  Referer: 'https://tsetmc.com/',
  Origin: 'https://tsetmc.com',
};

type Json = Record<string, unknown>;
const num = (v: unknown): number | null => {
  const n = typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : NaN;
  return Number.isFinite(n) ? n : null;
};

// ---- کش TTL دار: پولینگ ۵ثانیه‌ای تابلو نباید هر بار ۲–۳MB تازه بکشد -------
const cache = new Map<string, { at: number; data: unknown }>();
async function cachedJson(url: string, ttlMs: number): Promise<Json | null> {
  const hit = cache.get(url);
  if (hit && Date.now() - hit.at < ttlMs) return hit.data as Json | null;
  try {
    const data = (await nativeGetJson(url, HDRS)) as Json | null;
    cache.set(url, { at: Date.now(), data });
    return data;
  } catch {
    // خطا هم برای مدت کوتاه کش می‌شود تا در نبود شبکه، هر پول ۵ثانیه‌ای
    // دوباره سراغ یک fetch محکوم‌به‌شکست نرود.
    cache.set(url, { at: Date.now(), data: null });
    return null;
  }
}

async function cachedText(url: string, ttlMs: number): Promise<string | null> {
  const hit = cache.get(url);
  if (hit && Date.now() - hit.at < ttlMs) return hit.data as string | null;
  try {
    const text = await nativeGetText(url, HDRS);
    cache.set(url, { at: Date.now(), data: text });
    return text;
  } catch {
    cache.set(url, { at: Date.now(), data: null });
    return null;
  }
}

export type MwRow = {
  lva: string;
  pcl: number | null; pdv: number | null; py: number | null; pf: number | null;
  pmn: number | null; pmx: number | null;
  /** آستانه‌های مجاز (pMin/pMax) — همان tmin/tmax دسکتاپ؛ کفِ نشست نیستند */
  pmin: number | null; pmax: number | null;
  /** شمارهٔ نشستِ آخرین رویداد (dEven) — همان ستونی که `is_live` از آن می‌خواند */
  den: number | null;
  /** ساعتِ همان نشست (hEven) — برای `session` پاسخِ عمق */
  hen: number | null;
  /** پنج خطِ واقعیِ عمق از blDs — همتای `book_lines` دسکتاپ (بی‌قیمت نوشته نمی‌شود) */
  levels: { buy_px: number; buy_vol: number; buy_cnt: number;
            sell_px: number; sell_vol: number; sell_cnt: number }[];
  qtj: number | null; qtc: number | null; ztt: number | null; eps: number | null;
  q: null | {
    bq: number; bqv: number; bc: number; sq: number; sqv: number; sc: number;
    b1v: number | null; b1p: number | null; s1v: number | null; s1p: number | null; b1c: number | null;
  };
};

/** یک ردیفِ خامِ GetMarketWatch → `MwRow` (از liveWatch جدا تا قابلِ آزمون باشد) */
export function mwRowFromJson(r: Json): MwRow {
  // همتای queue_agg دسکتاپ: جمع ۵ خط + خط اول؛ نبودِ blDs یعنی null نه صفر
  let q: MwRow['q'] = null;
  const lines = r.blDs;
  if (Array.isArray(lines) && lines.length) {
    let bq = 0, bqv = 0, bc = 0, sq = 0, sqv = 0, sc = 0;
    for (const ln of lines as Json[]) {
      const bv = num(ln.qmd) ?? 0, bp = num(ln.pmd) ?? 0;
      const sv = num(ln.qmo) ?? 0, sp = num(ln.pmo) ?? 0;
      bq += bv; bqv += bv * bp; bc += num(ln.zmd) ?? 0;
      sq += sv; sqv += sv * sp; sc += num(ln.zmo) ?? 0;
    }
    const f = lines[0] as Json;
    q = { bq, bqv, bc, sq, sqv, sc,
          b1v: num(f.qmd), b1p: num(f.pmd), s1v: num(f.qmo), s1p: num(f.pmo), b1c: num(f.zmd) };
  }
  // همتای `book_lines` دسکتاپ (test_tsetmc.py:492): پنج خط، و سطری که هیچ‌یک از
  // دو طرفش قیمت ندارد نوشته نمی‌شود.
  const levels = ((Array.isArray(lines) ? lines : []).slice(0, 5) as Json[])
    .filter((ln) => ln && typeof ln === 'object')
    .map((ln) => ({
      buy_px: num(ln.pmd) ?? 0, buy_vol: num(ln.qmd) ?? 0, buy_cnt: num(ln.zmd) ?? 0,
      sell_px: num(ln.pmo) ?? 0, sell_vol: num(ln.qmo) ?? 0, sell_cnt: num(ln.zmo) ?? 0,
    }))
    .filter((l) => l.buy_px || l.sell_px);
  return {
    lva: String(r.lva ?? ''),
    pcl: num(r.pcl), pdv: num(r.pdv), py: num(r.py), pf: num(r.pf),
    pmn: num(r.pmn), pmx: num(r.pmx),
    pmin: num(r.pMin), pmax: num(r.pMax),
    den: num(r.dEven), hen: num(r.hEven),
    levels,
    qtj: num(r.qtj), qtc: num(r.qtc), ztt: num(r.ztt), eps: num(r.eps),
    q,
  };
}

/** مارکت‌واچ زنده — Map با کلید ins_code؛ null یعنی «زنده در دسترس نیست» */
export async function liveWatch(ttlMs = 5000): Promise<Map<string, MwRow> | null> {
  const j = await cachedJson(MW_URL, ttlMs);
  const rows = j?.marketwatch;
  if (!Array.isArray(rows) || !rows.length) return null;
  const out = new Map<string, MwRow>();
  for (const r of rows as Json[]) {
    const ins = String(r.insCode ?? '');
    if (!ins) continue;
    out.set(ins, mwRowFromJson(r));
  }
  return out.size ? out : null;
}

/** حقیقی/حقوقی زنده — Map با کلید ins_code */
export async function liveClientType(ttlMs = 30000): Promise<Map<string, Json> | null> {
  const j = await cachedJson(CT_URL, ttlMs);
  const rows = j?.clientTypeAllDto;
  if (!Array.isArray(rows) || !rows.length) return null;
  const out = new Map<string, Json>();
  for (const r of rows as Json[]) {
    const ins = String(r.insCode ?? '');
    if (ins) out.set(ins, r);
  }
  return out;
}

/** رونشانی اعداد زنده روی ردیف‌های تابلوی اسنپ‌شات (جهش درجا؛ فقط فیلد معلوم) */
export function overlayBoard(rows: Json[], mw: Map<string, MwRow>, ct: Map<string, Json> | null): number {
  let patched = 0;
  let maxDEven = -1;
  for (const row of rows) {
    const ins = String(row.ins_code ?? '');
    const m = ins ? mw.get(ins) : undefined;
    if (!m) continue;
    patched += 1;
    const set = (k: string, v: number | null) => { if (v != null) row[k] = v; };
    set('p_closing', m.pcl); set('p_last', m.pdv); set('price_yesterday', m.py);
    set('p_min', m.pmn); set('p_max', m.pmx);
    set('tmin', m.pmin); set('tmax', m.pmax);
    set('q_tot_tran', m.qtj); set('q_tot_cap', m.qtc); set('z_tot_tran', m.ztt);
    set('tvol', m.qtj); set('eps', m.eps);
    if (m.den != null) { row.d_even = m.den; if (m.den > maxDEven) maxDEven = m.den; }
    if (m.py && m.pcl != null) row.percent_change = Math.round(((m.pcl - m.py) / m.py) * 10000) / 100;
    if (m.py && m.pdv != null) row.percent_last = Math.round(((m.pdv - m.py) / m.py) * 10000) / 100;
    if (m.q) {
      set('buy_q_vol', m.q.bq); set('buy_q_val', m.q.bqv); set('buy_q_cnt', m.q.bc);
      set('sell_q_vol', m.q.sq); set('sell_q_val', m.q.sqv); set('sell_q_cnt', m.q.sc);
      set('buy_q1_vol', m.q.b1v); set('buy_q1_px', m.q.b1p); set('buy_q1_cnt', m.q.b1c);
      set('sell_q1_vol', m.q.s1v); set('sell_q1_px', m.q.s1p);
    }
    const c = ins && ct ? ct.get(ins) : undefined;
    if (c) {
      set('buy_i_vol', num(c.buy_I_Volume)); set('buy_n_vol', num(c.buy_N_Volume));
      set('sell_i_vol', num(c.sell_I_Volume)); set('sell_n_vol', num(c.sell_N_Volume));
      set('buy_count_i', num(c.buy_CountI)); set('sell_count_i', num(c.sell_CountI));
    }
  }
  // `is_live` همان قاعدۀ دسکتاپ (api/market.py:552): ردیفی که d_even‌اش به
  // آخرین نشستِ دیده‌شده نمی‌رسد، زنده نیست — وگرنه رویِ گوشی ردیف‌هایِ
  // نشست‌هایِ قبل هم زنده نشان داده می‌شدند.
  if (maxDEven >= 0) {
    for (const row of rows) row.is_live = Number(row.d_even ?? -1) === maxDEven;
  }
  return patched;
}

/** تاریخ امروز به وقت تهران (کندل زندهٔ امروز باید با date دیتابیس هم‌قالب باشد) */
export function tehranToday(): string {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Tehran' }).format(new Date());
}

/** کندل زندهٔ امروزِ یک نماد از مارکت‌واچ؛ null اگر زنده/نماد در دسترس نیست.
 *  پایانی (`pcl`) و آخرین (`pdv`) جدا می‌مانند — جعلِ `last := close` همان کاری
 *  است که قرارداد §۱-ث دسکتاپ (api/chart.py:87) لغوش کرد. */
export async function liveTodayCandle(
  normSymbol: string,
  norm: (s: string) => string,
): Promise<{ time: string; open: number; high: number; low: number; close: number; last: number | null; volume: number } | null> {
  const mw = await liveWatch();
  if (!mw) return null;
  for (const m of mw.values()) {
    if (norm(m.lva) !== normSymbol) continue;
    const close = m.pcl ?? m.pdv;
    if (close == null || close <= 0) return null;
    const last = m.pdv ?? null;
    const open = m.pf && m.pf > 0 ? m.pf : close;
    const high = Math.max(m.pmx ?? close, close, open);
    const low = Math.min(m.pmn ?? close, close, open);
    return { time: tehranToday(), open, high, low, close, last, volume: m.qtj ?? 0 };
  }
  return null;
}

/** سری شاخص کل — همان نگاشت build_tedpix_payload دسکتاپ (بدون دادهٔ ساختگی) */
export async function liveTedpix(limit: number): Promise<Json | null> {
  const j = await cachedJson(TEDPIX_URL, 300000);
  const raw = j?.indexB2;
  if (!Array.isArray(raw) || !raw.length) return null;
  const rows: { time: string; close: number; high: number; low: number }[] = [];
  for (const x of raw as Json[]) {
    const d = String(num(x.dEven) ?? '');
    if (d.length !== 8) continue;
    const iso = `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
    const close = num(x.xNivInuClMresIbs) ?? 0;
    if (close <= 0) continue;
    rows.push({ time: iso, close,
                high: num(x.xNivInuPhMresIbs) ?? 0, low: num(x.xNivInuPbMresIbs) ?? 0 });
  }
  if (!rows.length) return null;
  rows.sort((a, b) => (a.time < b.time ? -1 : 1));
  const candles: Json[] = [];
  let prev: number | null = null;
  for (const r of rows) {
    const c = r.close;
    let h = r.high > 0 ? r.high : c;
    let l = r.low > 0 ? r.low : c;
    if (h < c) h = c;
    if (l > c) l = c;
    const open = prev ?? c; // شاخص «تیک بازگشایی» ندارد؛ open = close روز قبل
    candles.push({ time: r.time, open, high: Math.max(h, open), low: Math.min(l, open), close: c });
    prev = c;
  }
  const sliced = limit > 0 ? candles.slice(-limit) : candles;
  return { status: 'success', symbol: 'شاخص کل', count: sliced.length, candles: sliced };
}

// ---------------------------------------------------------------------------
// چارت زندهٔ روزانه از CSV رسمی TSETMC — هم‌ارزِ get_chart در api/chart.py
// (پارس هدرمحور v9.7 + ترمیم هندسه + رویدادهای تعدیل با درِ لنگر ANCHOR_MIN)
// ---------------------------------------------------------------------------
const ADJ_TOL = 0.001;    // آستانهٔ نسبی تشخیص تعدیل (همان api/chart.py)
const ANCHOR_MIN = 0.9;   // حداقل نسبت لنگر base==close(t-1)؛ کمتر ⇒ صندوق NAVمحور

type CsvCandle = { time: string; open: number; high: number; low: number; close: number; last: number | null };
type CsvVolume = { time: string; value: number; color: string };
type CsvRow = { time: string; base: number; close: number; vol: number };

/** پارس CSV روزانهٔ TSETMC → کندل/حجم/همهٔ ردیف‌های base-close (خالص، بدون شبکه) */
export function parseTsetmcCsv(text: string): { candles: CsvCandle[]; volumes: CsvVolume[]; allRows: CsvRow[] } {
  const candles: CsvCandle[] = [];
  const volumes: CsvVolume[] = [];
  const allRows: CsvRow[] = [];
  const lines = text.split(/\r?\n/);
  // ایندکس ستون‌ها از خود هدر — نه عدد ثابت (v9.7 دسکتاپ)
  let iLast = 11;
  if (lines.length && lines[0].trim().startsWith('<')) {
    const hdr = lines[0].split(',').map((s) => s.trim().toUpperCase());
    const k = hdr.indexOf('<LAST>');
    if (k >= 0) iLast = k;
  }
  for (let li = 1; li < lines.length; li++) {
    const ln = lines[li];
    if (!ln.trim()) continue;
    const p = ln.split(',').map((s) => s.trim());
    if (p.length < 11) continue;
    const d = p[1];
    if (!d || d.length < 8) continue;
    const dt = `${d.slice(0, 4)}-${d.slice(4, 6)}-${d.slice(6, 8)}`;
    const first = Number(p[2] || 0);
    const hi0 = Number(p[3]);
    const lo0 = Number(p[4]);
    const c = Number(p[5]);
    const base = Number(p[10] || 0);   // <OPEN> = قیمت پایه (= پایانی دیروز، یا پس از تعدیل)
    const v = p[7] ? Number(p[7]) : 0;
    const rawLast = p.length > iLast && p[iLast] ? Number(p[iLast]) : NaN;
    if ([first, hi0, lo0, c, base, v].some((x) => Number.isNaN(x)) || (p.length > iLast && p[iLast] && Number.isNaN(rawLast))) continue;
    // بدنهٔ کندل = اولین معامله؛ اگر نبود پایهٔ clampشده و سپس پایانی (FIX-1/1b)
    const o = first > 0 ? first : base > 0 ? Math.min(Math.max(base, lo0), hi0) : c;
    if (c > 0 && base > 0) allRows.push({ time: dt, base, close: c, vol: v });
    if (hi0 <= 0 || c <= 0 || o <= 0 || lo0 <= 0) continue;
    // ترمیم هندسه (candle_contract.widen دسکتاپ): high فقط سقف را باز می‌کند و
    // low فقط کف را — هیچ‌کدام کاندیدِ طرفِ دیگر نیستند؛ اصلِ «هیچ قیمتِ
    // منتشرشده‌ای خُرد نمی‌شود».
    const hi = Math.max(hi0, o, c);
    const lo = Math.min(lo0, o, c);
    // v10.7.0: «آخرین» نه به پایانی fallback می‌شود نه clamp — دو جعلِ قبلی
    // همان چیزی بود که قرارداد §۱-ث شرطِ ۳ بست (همان خط در api/chart.py).
    const last = Number.isNaN(rawLast) ? null : rawLast;
    candles.push({ time: dt, open: o, high: hi, low: lo, close: c, last });
    volumes.push({ time: dt, value: v, color: c >= o ? '#10b981' : '#f43f5e' });
  }
  return { candles, volumes, allRows };
}

/** رویدادهای تعدیل از دو نشانۀ خامِ CSV — همان `_adjust_events_from_rows` دسکتاپ
 *  (a) گسستِ «قیمت پایه»: base(t) != close(t-1)
 *  (b) بازنویسیِ «قیمت پایانی» روی سطرِ بی‌معامله (VOL=0) — بدونِ این، زنجیرِ
 *      تعدیلِ نمادهایی مثلِ وبملت (۱۳۹۰–۱۳۹۳) کامل از دست می‌رفت. */
export function adjustEventsFromRows(allRows: CsvRow[]): { date: string; ratio: number }[] {
  const rows = allRows
    .filter((r) => r.close > 0 && r.base > 0)
    .sort((a, b) => (a.time < b.time ? -1 : 1));
  if (rows.length < 2) return [];
  // درِ لنگر: اگر base غالباً به پایانیِ دیروز زنجیر نیست (صندوق NAVمحور)،
  // رویداد ساختگی بدتر از هیچ است.
  let pairs = 0;
  let anchored = 0;
  for (let i = 1; i < rows.length; i++) {
    pairs++;
    if (rows[i].base === rows[i - 1].close) anchored++;
  }
  if (pairs >= 20 && anchored / pairs < ANCHOR_MIN) return [];
  const byDate = new Map<string, { date: string; ratio: number }>();
  const push = (date: string, ratio: number) => {
    if (!byDate.has(date)) byDate.set(date, { date, ratio: Number(ratio.toFixed(6)) });
  };
  for (let i = 1; i < rows.length; i++) {
    const prevClose = rows[i - 1].close;
    const base = rows[i].base;
    // آستانه دوتایی: هم ≥ یک واحد قیمت، هم > ADJ_TOL نسبی (همان دسکتاپ)
    if (Math.abs(base - prevClose) >= 1.0 && Math.abs(base / prevClose - 1) > ADJ_TOL) {
      push(rows[i].time, base / prevClose);
    }
    if (rows[i].vol === 0) {
      const r2 = rows[i].close / base;
      if (Math.abs(r2 - 1) > ADJ_TOL) push(rows[i].time, r2);
    }
  }
  return [...byDate.values()].sort((a, b) => (a.date < b.date ? -1 : 1));
}

/**
 * چارت کامل یک نماد از CSV زندهٔ TSETMC: کندل خام + factors تعدیل + رویدادها.
 * خروجی هم‌شکلِ /api/chart دسکتاپ؛ null اگر شبکه/داده در دسترس نیست.
 */
export async function liveChart(insCode: string, symbol: string): Promise<Json | null> {
  const url = `${LIVE_BASE}/ClosingPrice/GetClosingPriceDailyListCSV/${insCode}/19900101`;
  const text = await cachedText(url, 3600000); // TTL یک ساعت، مثل CHART_CACHE_TTL
  if (!text) return null;
  const parsed = parseTsetmcCsv(text);
  if (!parsed.candles.length) return null;
  // CSV تی‌اس‌ای گاهی نزولی است؛ سری همیشه صعودی برمی‌گردد (هم‌قالب /api/history)
  const candles = [...parsed.candles].sort((a, b) => (a.time < b.time ? -1 : 1));
  const volumes = [...parsed.volumes].sort((a, b) => (a.time < b.time ? -1 : 1));
  const adjustEvents = adjustEventsFromRows(parsed.allRows);
  // فاکتور back-adjust هر کندل: حاصل‌ضرب ratio رویدادهای بعد از آن؛ آخرین کندل = ۱
  const factors: { time: string; factor: number }[] = new Array(candles.length);
  const evDates = adjustEvents.map((e) => e.date);
  const evRatios = adjustEvents.map((e) => e.ratio);
  let f = 1.0;
  let j = evDates.length - 1;
  for (let i = candles.length - 1; i >= 0; i--) {
    const t = candles[i].time;
    while (j >= 0 && evDates[j] > t) {
      f *= evRatios[j];
      j--;
    }
    factors[i] = { time: t, factor: Number(f.toFixed(10)) };
  }
  return {
    status: 'success',
    symbol,
    candles: candles as unknown as Json[],
    volumes: volumes as unknown as Json[],
    factors: factors as unknown as Json[],
    adjustEvents: adjustEvents as unknown as Json[],
    adjustSource: 'base-close-chain',
    count: candles.length,
  };
}
