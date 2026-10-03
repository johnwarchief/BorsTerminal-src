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


/** خروج تعقیبی MA14 — مطابق FTS_SPEC بخش اول بند ۵.
    شرط: «یک کندل کامل» یعنی همهٔ اجزای OHLC (Open/High/Low/Close) زیر خط MA14
    (چون high بیشینه است، high < MA14 کل کندل را زیر خط می‌گذارد).
    pending = بدنه زیر خط ولی سایهٔ بالا بالای خط (کندل کامل نیست).
    ma14Series اختیاری: پیش‌فرض SMA روی بسته‌ها با دورهٔ 14. */
export type SwingPoint = { index: number; price: number };

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
export function highestHigh(highs: (number | null)[], n: number): number | null {
  if (!(n > 0)) return null;
  const vals = highs.slice(-n).filter((v): v is number => v != null);
  return vals.length > 0 ? Math.max(...vals) : null;
}

/** کف n کندل آخر */
export function lowestLow(lows: (number | null)[], n: number): number | null {
  if (!(n > 0)) return null;
  const vals = lows.slice(-n).filter((v): v is number => v != null);
  return vals.length > 0 ? Math.min(...vals) : null;
}

/** میانگین حجم n جلسه آخر */
export function avgVolume(volumes: (number | null)[], n: number): number | null {
  if (!(n > 0)) return null;
  const vals = volumes.slice(-n).filter((v): v is number => v != null && v >= 0);
  if (vals.length === 0) return null;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

/**
 * RSI وایلدر با هموارسازی Wilder (نه میانگین ساده) — FTS_SPEC بخش اول بند ۲ و ۵.
 * بذر: میانگین سادهٔ دورهٔ نخست؛ سپس هموارسازی (n-1)/n. null یعنی دادهٔ ناکافی.
 */
export function rsi(values: (number | null)[], period = FTS_RSI_PERIOD): (number | null)[] {
  const out: (number | null)[] = new Array(values.length).fill(null);
  if (period < 1) return out;
  const fromRs = (g: number, l: number): number => (l === 0 ? 100 : 100 - 100 / (1 + g / l));
  let avgGain = 0;
  let avgLoss = 0;
  let seed = 0;
  let prev: number | null = null;
  for (let i = 0; i < values.length; i++) {
    const v = num(values[i]);
    if (v == null) {
      out[i] = null;
      continue;
    }
    if (prev == null) {
      prev = v;
      continue;
    }
    const change = v - prev;
    prev = v;
    const gain = Math.max(0, change);
    const loss = Math.max(0, -change);
    if (seed < period) {
      avgGain += gain;
      avgLoss += loss;
      seed += 1;
      if (seed === period) {
        avgGain /= period;
        avgLoss /= period;
        out[i] = fromRs(avgGain, avgLoss);
      }
      continue;
    }
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    out[i] = fromRs(avgGain, avgLoss);
  }
  return out;
}
