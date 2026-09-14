// features/technical/lib/indicators.ts -- اندیکاتورهای FTS و ابزار سوینگ
// چهار مووینگ استاندارد FTS روی پن کندل: 14 تریلینگ استاپ و 52 و 100 مرجع روند.
// خالص و مستقل از DOM؛ null یعنی نقطه نامعتبر.
// مرجع هم‌ترازی متدولوژی: موتور ممیزی‌شدهٔ بک‌اند در api/chart.py (بخش FTS v10)
// و confidence_engine.py (_bearish_div/_rsi). این فایل فقط‌خواندنِ آن مرجع را
// به TS می‌آورد؛ بخش‌های «قرینهٔ …» به‌ازای هر تابع، شمارهٔ خط بک‌اند را می‌دهند.

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

/** آخرین مقدار معتبر */
export function lastValid(values: (number | null)[]): number | null {
  for (let i = values.length - 1; i >= 0; i--) {
    if (values[i] != null) return values[i];
  }
  return null;
}

/** میانگین متحرک نمایی؛ بذر با میانگین ساده اولین دوره کامل */
export function ema(values: (number | null)[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (period < 1) return out;
  const k = 2 / (period + 1);
  const window: number[] = [];
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    const v = num(values[i]);
    if (v == null) {
      out[i] = null;
      continue;
    }
    if (prev == null) {
      window.push(v);
      if (window.length === period) {
        prev = window.reduce((a, b) => a + b, 0) / period;
        out[i] = prev;
      }
      continue;
    }
    prev = v * k + prev * (1 - k);
    out[i] = prev;
  }
  return out;
}

/** میانگین متحرک ساده -- مبنای چهار مووینگ FTS */
export function sma(values: (number | null)[], period: number): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (period < 1) return out;
  const window: number[] = [];
  for (let i = 0; i < values.length; i++) {
    const v = num(values[i]);
    if (v == null) {
      out[i] = null;
      continue;
    }
    window.push(v);
    if (window.length > period) window.shift();
    if (window.length === period) out[i] = window.reduce((a, b) => a + b, 0) / period;
  }
  return out;
}

/** دوره های استاندارد FTS */
export const FTS_MA_PERIODS = [14, 21, 52, 100] as const;

/** نیم‌پنجرهٔ پیوت بک‌اند (_FTS_SWING_K در api/chart.py) */
export const FTS_SWING_K = 3;
/** اختلاف ≤ ۰٫۵٪ دو پیوت = «مساوی»/ساختار رنج (_FTS_EQUAL_TOL) */
export const FTS_EQUAL_TOL = 0.005;
/** آستانهٔ «قطعی» در CHoCH: ۰٫۳٪ فراتر از سطح، روی پایانی (نه wick) */
export const FTS_CHOCH_DECISIVE = 0.003;
/** دورهٔ RSI وایلدر و فاصلهٔ مقایسهٔ واگرایی (tech_rsi_daily / tech_div_back) */
export const FTS_RSI_PERIOD = 14;
export const FTS_DIV_BACK = 20;
/** کمربندهای فیبونانچی لگاریتمی FTS: [از، تا] نسبتِ اصلاح روی ln قیمت */
export const FTS_FIB_BANDS = [
  [0.33, 0.4],
  [0.618, 0.7],
] as const;

/** هر چهار مووینگ FTS روی سری بسته شدن */
export function ftsMAs(closes: (number | null)[]): Record<(typeof FTS_MA_PERIODS)[number], (number | null)[]> {
  return { 14: sma(closes, 14), 21: sma(closes, 21), 52: sma(closes, 52), 100: sma(closes, 100) };
}

export type MaStack = 'bull' | 'bear' | 'mixed' | 'unknown';

/** آرایش استک: 14 بالای 21 بالای 52 بالای 100 یعنی روند سالم.
    معنای عملیاتی MA14 در استک: «خروج تعقیبی» لایهٔ ۱ موتور خروج بک‌اند است
    (_fts_exit_layer1 در api/chart.py:913) — شرط خروج بدنهٔ کندل کاملاً زیر MA14
    به‌مدت دو کندل متوالی؛ برای آن سیگنال صریح از ma14TrailingExit استفاده کنید. */
export function maStack(m14: number | null, m21: number | null, m52: number | null, m100: number | null): MaStack {
  if (m14 == null || m21 == null || m52 == null || m100 == null) return 'unknown';
  if (m14 > m21 && m21 > m52 && m52 > m100) return 'bull';
  if (m14 < m21 && m21 < m52 && m52 < m100) return 'bear';
  return 'mixed';
}

export type Ma14Exit = { exit: boolean; pending: boolean; ma14: number | null };

/** خروج تعقیبی MA14 — قرینهٔ _fts_exit_layer1 (api/chart.py:947).
    شرط: «بدنه» یعنی max(open, close) < MA14 (نه سایه/wick) تا سکه‌های سایه‌دار
    یک‌روزه علامت اشتباه ندهند؛ کندل اول = pending (هشدار)، دوم = exit (تأیید).
    ma14Series اختیاری: پیش‌فرض SMA روی بسته‌ها با دورهٔ 14. */
export function ma14TrailingExit(
  opens: (number | null)[],
  closes: (number | null)[],
  ma14Series?: (number | null)[],
): Ma14Exit {
  const ma = ma14Series ?? sma(closes, 14);
  const n = Math.min(opens.length, closes.length, ma.length);
  let idx = -1;
  let bodyTop = 0;
  let m = 0;
  for (let i = n - 1; i >= 0; i--) {
    const o = num(opens[i]);
    const c = num(closes[i]);
    const v = num(ma[i]);
    if (o != null && c != null && v != null) {
      idx = i;
      bodyTop = Math.max(o, c);
      m = v;
      break;
    }
  }
  if (idx < 0) return { exit: false, pending: false, ma14: lastValid(ma) };
  const bodyBelow = bodyTop < m;
  let prevBelow = false;
  if (idx >= 1) {
    const po = num(opens[idx - 1]);
    const pc = num(closes[idx - 1]);
    const pm = num(ma[idx - 1]);
    if (po != null && pc != null && pm != null) prevBelow = Math.max(po, pc) < pm;
  }
  return { exit: bodyBelow && prevBelow, pending: bodyBelow && !prevBelow, ma14: m };
}

export type SwingPoint = { index: number; price: number };

/** فرکتال سقف: سقف بالاتر از order کندل دو طرف */
export function swingHighs(highs: (number | null)[], order = 3): SwingPoint[] {
  const out: SwingPoint[] = [];
  for (let i = order; i < highs.length - order; i++) {
    const h = num(highs[i]);
    if (h == null) continue;
    let ok = true;
    for (let j = i - order; j <= i + order; j++) {
      if (j === i) continue;
      const o = num(highs[j]);
      if (o == null || o >= h) {
        ok = false;
        break;
      }
    }
    if (ok) out.push({ index: i, price: h });
  }
  return out;
}

/** فرکتال کف */
export function swingLows(lows: (number | null)[], order = 3): SwingPoint[] {
  const out: SwingPoint[] = [];
  for (let i = order; i < lows.length - order; i++) {
    const l = num(lows[i]);
    if (l == null) continue;
    let ok = true;
    for (let j = i - order; j <= i + order; j++) {
      if (j === i) continue;
      const o = num(lows[j]);
      if (o == null || o <= l) {
        ok = false;
        break;
      }
    }
    if (ok) out.push({ index: i, price: l });
  }
  return out;
}

/** پیوت غیراکیدِ بک‌اند — قرینهٔ _fts_swings (api/chart.py:652).
    تفاوت با swingHighs/swingLows (اکید): سقف = high ≥ هر دو پنجره (پلتوهای
    مساوی هم پیوت می‌شوند)؛ یک کندل می‌تواند همزمان سقف و کف باشد. مبنای
    ftsChoch/fibZones برای هم‌خوانی عددی با موتور بک‌اند. کندل‌های دارای null
    در پنجره، پیوت‌زنی نمی‌شوند (بک‌اند کندلِ ناقص ندارد). */
export type FtsPivot = { idx: number; price: number; kind: 'high' | 'low' };

export function ftsSwings(highs: (number | null)[], lows: (number | null)[], k = FTS_SWING_K): FtsPivot[] {
  const n = Math.min(highs.length, lows.length);
  if (k < 1 || n < 2 * k + 2) return [];
  const out: FtsPivot[] = [];
  for (let i = k; i < n - k; i++) {
    const hi = num(highs[i]);
    const lo = num(lows[i]);
    if (hi == null || lo == null) continue;
    let maxLH = -Infinity;
    let maxRH = -Infinity;
    let minLL = Infinity;
    let minRL = Infinity;
    let gap = false;
    for (let j = i - k; j <= i + k; j++) {
      if (j === i) continue;
      const h = num(highs[j]);
      const l = num(lows[j]);
      if (h == null || l == null) {
        gap = true;
        break;
      }
      if (j < i) {
        if (h > maxLH) maxLH = h;
        if (l < minLL) minLL = l;
      } else {
        if (h > maxRH) maxRH = h;
        if (l < minRL) minRL = l;
      }
    }
    if (gap) continue;
    if (hi >= maxLH && hi >= maxRH) out.push({ idx: i, price: hi, kind: 'high' });
    if (lo <= minLL && lo <= minRL) out.push({ idx: i, price: lo, kind: 'low' });
  }
  return out;
}

export type FtsTrend = 'up' | 'down' | 'range' | 'na';

/** طبقه‌بندی ساختار روند — قرینهٔ _fts_classify_trend (api/chart.py:677):
    دو سقف و دو کفِ پیوتِ آخر: HH+HL=up، LH+LL=down، هر اختلاف ≤tol یا بقیهٔ
    حالت‌ها=range؛ کمتر از دو پیوت در یک سمت=na. */
export function classifyTrend(swings: FtsPivot[], tol = FTS_EQUAL_TOL): FtsTrend {
  const hs = swings.filter((s) => s.kind === 'high').slice(-2);
  const ls = swings.filter((s) => s.kind === 'low').slice(-2);
  if (hs.length < 2 || ls.length < 2) return 'na';
  const h2 = hs[0].price;
  const h1 = hs[1].price;
  const l2 = ls[0].price;
  const l1 = ls[1].price;
  const hh = h1 > h2 * (1 + tol);
  const hl = l1 > l2 * (1 + tol);
  const lh = h1 < h2 * (1 - tol);
  const ll = l1 < l2 * (1 - tol);
  if (hh && hl) return 'up';
  if (lh && ll) return 'down';
  return 'range';
}

/** خط آبی پرواز: بالاترین سوینگ ماژور در پنجره نگاه */
export function majorResistance(highs: (number | null)[], lookback = 120): SwingPoint | null {
  const swings = swingHighs(highs.slice(-lookback), 3);
  if (swings.length > 0) return swings.reduce((a, b) => (b.price > a.price ? b : a));
  const vals = highs.slice(-lookback).filter((v): v is number => v != null);
  if (vals.length === 0) return null;
  return { index: highs.length - 1, price: Math.max(...vals) };
}

/** حمایت ماژور متناظر */
export function majorSupport(lows: (number | null)[], lookback = 120): SwingPoint | null {
  const swings = swingLows(lows.slice(-lookback), 3);
  if (swings.length > 0) return swings.reduce((a, b) => (b.price < a.price ? b : a));
  const vals = lows.slice(-lookback).filter((v): v is number => v != null);
  if (vals.length === 0) return null;
  return { index: lows.length - 1, price: Math.min(...vals) };
}

export type FibBand = { lo: number; hi: number; inZone: boolean };
export type FibZones = {
  baseHigh: number;
  baseLow: number;
  zone3340: FibBand;
  zone61870: FibBand;
};

/** کمربندهای فیبوناچی در مقیاس لگاریتمی — قرینهٔ _fts_fib_zones (api/chart.py:742).
    چرا لگاریتم: حرکت ×۴ و اصلاح ۵۰٪ آن در مقیاس خطی «کف» درست نمی‌دهد؛ نسبت
    اصلاح روی ln قیمت سنجیده می‌شود. بازهٔ اندازه‌گیری: آخرین سقف پیوتِ مهم ←
    پایین‌ترین کفِ «پس از آن سقف» (کفی بعد از سقف نبود: مینِ کل پنجره؛ همان
    fallback بک‌اند). دو کمربند: zone3340 (ادامهٔ روند) و zone61870 (طلایی
    اصلاحی). in_zone = پایانیِ آخرین کندل داخل کمربند.
    انحراف مستند از کد بک‌اند: بک‌اند نقطهٔ شروع را argmax سقف کل پنجره
    (candles) می‌گیرد، نه idx خودِ پیوت؛ وقتی آخرین سقف پیوت همان قلهٔ پنجره
    است (حالت عادی) دو خروجی یکی می‌شود — اینجا قاعدهٔ مستندِ متدولوژی (idx پیوت)
    پیاده شده. بک‌اند قیمت‌ها را round(…,2) می‌کند؛ اینجا عدد خام (گردکردن به
    نمایش سپرده شد). */
export function fibZones(
  highs: (number | null)[],
  lows: (number | null)[],
  closes: (number | null)[],
  order = FTS_SWING_K,
): FibZones | null {
  const pivots = ftsSwings(highs, lows, order);
  const highPivots = pivots.filter((p) => p.kind === 'high');
  if (highPivots.length === 0) return null;
  const topPivot = highPivots[highPivots.length - 1];
  const top = topPivot.price;
  const nLow = Math.min(lows.length, highs.length);
  let bot: number | null = null;
  for (let i = topPivot.idx; i < nLow; i++) {
    const l = num(lows[i]);
    if (l != null && (bot == null || l < bot)) bot = l;
  }
  if (bot == null) {
    for (let i = 0; i < nLow; i++) {
      const l = num(lows[i]);
      if (l != null && (bot == null || l < bot)) bot = l;
    }
  }
  if (bot == null || top <= 0 || bot <= 0 || top <= bot) return null;
  const last = lastValid(closes);
  const lnTop = Math.log(top);
  const lnBot = Math.log(bot);
  const band = ([p1, p2]: readonly [number, number]): FibBand => {
    const hi = Math.exp(lnTop + (lnBot - lnTop) * p1);
    const lo = Math.exp(lnTop + (lnBot - lnTop) * p2);
    return { lo, hi, inZone: last != null && last >= lo && last <= hi };
  };
  return {
    baseHigh: top,
    baseLow: bot,
    zone3340: band(FTS_FIB_BANDS[0]),
    zone61870: band(FTS_FIB_BANDS[1]),
  };
}

export type Choch = { type: 'bearish' | 'bullish' | null; level: number | null };

/** خط چین قرمز: شکست ساختار پس از توالی کف و سقف.
    در سه سوینگ آخر اگر یک جفت صعودی باشد و قیمت زیر آخرین کف برود یعنی
    تغییر ماهیت نزولی؛ قرینه آن برای صعودی. */
export function detectChoch(
  highs: (number | null)[],
  lows: (number | null)[],
  closes: (number | null)[],
  order = 3,
): Choch {
  const sh = swingHighs(highs, order);
  const sl = swingLows(lows, order);
  const last = lastValid(closes);
  if (last == null) return { type: null, level: null };
  const recentH = sh.slice(-3);
  const recentL = sl.slice(-3);
  const hasHigherHigh = recentH.some((s, i) => i > 0 && s.price > recentH[i - 1].price);
  const hasLowerLow = recentL.some((s, i) => i > 0 && s.price < recentL[i - 1].price);
  if (recentH.length >= 2 && sl.length >= 1 && hasHigherHigh) {
    const l = sl[sl.length - 1];
    if (last < l.price) return { type: 'bearish', level: l.price };
  }
  if (recentL.length >= 2 && sh.length >= 1 && hasLowerLow) {
    const h = sh[sh.length - 1];
    if (last > h.price) return { type: 'bullish', level: h.price };
  }
  return { type: null, level: null };
}

/** سقف n کندل آخر */
export function highestHigh(highs: (number | null)[], n: number): number | null {
  const vals = highs.slice(-n).filter((v): v is number => v != null);
  return vals.length > 0 ? Math.max(...vals) : null;
}

/** کف n کندل آخر */
export function lowestLow(lows: (number | null)[], n: number): number | null {
  const vals = lows.slice(-n).filter((v): v is number => v != null);
  return vals.length > 0 ? Math.min(...vals) : null;
}

/** میانگین حجم n جلسه آخر */
export function avgVolume(volumes: (number | null)[], n: number): number | null {
  const vals = volumes.slice(-n).filter((v): v is number => v != null && v >= 0);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}
