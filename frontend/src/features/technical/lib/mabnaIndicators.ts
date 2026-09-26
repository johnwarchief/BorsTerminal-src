// features/technical/lib/mabnaIndicators.ts — نُه مطالعه‌ای که rahavard365 در ویجتِ
// TradingView خودش ثبت می‌کند، عیناً از بدنهٔ کامپایل‌شدهٔ Pine→JS همان‌ها خوانده و
// به klinecharts v10 منتقل شده است.
//
// منبعِ فرمول (تنها منبع): خروجیِ read-only از باندلِ عمومیِ rahavard، فایل‌های
// Temp/rhv/js/study_*.js که برشی از _app-c5fd7f3021376609.js هستند. آفستِ بایتیِ هر
// مطالعه در همان باندل بالای هر بخش آمده؛ اگر فرمولی در آن برش خوانا نبود، این‌جا هم
// نوشته نشده یا صریحاً علامت‌گذاری شده که حدس نیست بلکه «تعریفِ مستندِ Pine» است:
//   DT 5406410 | Z 5408420 | SQZ 5411620 | HT 5414043 | SR 5418689
//   WT 5422874 | FIBB 5425907 | WTC 5429832 | VIX 5433623
//
// چرا این‌جا و نه tvIndicators.ts: آن فایل تمپلیت‌های پکیجِ react-klinecharts-ui را
// ثبت می‌کند و کاتالوگش با «هست یا نیست در پکیج» سنجیده می‌شود؛ این‌ها ساختِ خودمان
// است (کاتالوگِ موازی: MABNA_INDICATORS در tvIndicatorCatalog.ts).
//
// قراردادِ داده: undefined == na. هیچ‌جا صفر جانشین na نمی‌شود، و مقدارِ غیرمتناهی
// (تقسیم بر صفر و …) هم در finishRows دور ریخته می‌شود.
//
// هشدارِ باندل: چارتِ واقعیِ کاربر npm/klinecharts v10 است، نه window.klinechartsِ
// public/vendor (دو Chart API متفاوت — همان دامِ getCrosshair). ثبت روی همان api‌ای
// انجام می‌شود که registerTvIndicators هم مصرف می‌کند.

import { ema, rsi, sma } from './indicators';
import type { TvIndicator } from './tvIndicatorCatalog';
import { MABNA_INDICATORS } from './tvIndicatorCatalog';

// مثلِ tvIndicators: کاتالوگ از همین‌جا هم بیرون می‌رود تا منو یک import داشته باشد
export { MABNA_INDICATORS } from './tvIndicatorCatalog';

// ───────────────────────────────────────────────────────────── types ──────────

export type MabnaParam = number | string | boolean;
export type MabnaRow = Record<string, number | undefined>;
/** برشِ موردنیاز از کندلِ klinecharts (KLineData ساختاراً شاملِ این فیلدهاست) */
export type MabnaCandle = { open: number; high: number; low: number; close: number; volume?: number };

export interface MabnaFigure {
  key: string;
  title?: string;
  type?: 'line' | 'bar' | 'circle';
  /** مبنایِ میله (0 برای هیستوگرامِ مثبت/منفی) */
  baseValue?: number;
  /** رنگ از کدِ رنگِ همان سطر (paletteهای metainfo خودِ rahavard) */
  styles?: (params: { data: { prev?: MabnaRow; current?: MabnaRow; next?: MabnaRow } }) => { color: string };
}

export interface MabnaIndicator {
  name: string;
  shortName: string;
  /** 'price' = مطالعهٔ قیمتی (روی کندل)؛ 'normal' = پنلِ جدا. same as is_price_study */
  series: 'normal' | 'price';
  precision: number;
  /** به‌همان ترتیبِ defaults.inputs در metainfo خودِ rahavard */
  calcParams: MabnaParam[];
  figures: MabnaFigure[];
  calc: (dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }) => MabnaRow[];
}

// ─────────────────────────────────────────────────────── scalar helpers ───────

const fin = (v: number | null | undefined): number | undefined =>
  typeof v === 'number' && Number.isFinite(v) ? v : undefined;

const clean = (a: (number | null | undefined)[]): (number | undefined)[] => a.map(fin);

/** lib/indicators.ts na را null می‌نویسد؛ این‌جا undefined — پلِ بین دو قرارداد */
const toNull = (a: (number | undefined)[]): (number | null)[] => a.map((v) => v ?? null);

const num = (v: MabnaParam | undefined, fallback: number): number => {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN;
  return Number.isFinite(n) ? n : fallback;
};

const flag = (v: MabnaParam | undefined): boolean => v === true || v === 1 || v === 'true';

/** na نبودن، معادلِ `let r=e=>Number.isFinite(e)` در بدنهٔ SR */
const isF = (v: number | undefined): v is number => v !== undefined && Number.isFinite(v);

// ──────────────────────────────────────────────────────────── colours ─────────
// همه از defaults.styles / palettesِ خودِ metainfoهای rahavard برداشته شده‌اند؛ هیچ
// رنگی سلیقه‌ای نیست. کدِ رنگ (۰/۱/۲/…) در سطرِ نتیجه می‌نشیند و figure آن را به
// hex ترجمه می‌کند — همان کاری که colorer در TradingView می‌کند.

const solid = (color: string) => () => ({ color });
const byCode =
  (palette: string[], codeKey: string) =>
  ({ data }: { data: { current?: MabnaRow } }) => ({
    color: palette[fin(data.current?.[codeKey]) ?? 0] ?? palette[0],
  });

const PAL = {
  dtK: 'rgba(0, 0, 0, 0.65)',
  dtD: 'rgba(128,0,128, 0.65)',
  zLine: '#55FF55',
  zBand: '#FFFFFF',
  sqzMomentum: ['rgba(0,255,0, 0.65)', 'rgba(0,128,0, 0.65)', 'rgba(255,0,0, 0.65)', 'rgba(128,0,0, 0.65)'],
  sqzState: ['rgba(0,0,255, 0.65)', 'rgba(0,0,0, 0.65)', 'rgba(128,128,128, 0.65)'],
  htUp: 'rgba(41, 98, 255, 1)',
  htDown: 'rgba(242, 54, 69, 1)',
  srResistance: 'rgba(255, 0, 0, 1)',
  srSupport: 'rgba(35, 61, 238, 1)',
  srBearLabel: 'rgba(255, 82, 82, 1)',
  srBullLabel: 'rgba(76, 175, 80, 1)',
  wtZero: '#808080',
  wtLevelHigh: '#FF0000',
  wtLevelLow: '#008000',
  wtLine: '#008000',
  wtAvg: '#FF0000',
  wtHist: '#0000FF',
  wtcCross: ['#FF0000', '#00FF00'],
  vixRange: '#FF7F00',
  vixBand: '#00FFFF',
  vixBottom: ['#00FF00', '#808080'],
  fibBasis: '#FF00FF',
  fibOuterUp: '#FF0000',
  fibOuterDown: '#008000',
  fibInner: '#FFFFFF',
};

/** سراسری: هیچ نقطه‌ای با NaN/Infinity به چارت نمی‌رود (contract: na = absent) */
function finishRows(rows: MabnaRow[]): MabnaRow[] {
  return rows.map((row) => {
    const out: MabnaRow = {};
    for (const [key, value] of Object.entries(row)) {
      const f = fin(value);
      if (f !== undefined) out[key] = f;
    }
    return out;
  });
}

// ───────────────────────────────────────────────── Pine `Std` equivalents ─────
// پیاده‌سازیِ Std.* تریدینگ‌ویو (sma/ema از lib/indicators.ts دوباره‌استفاده شده).
// خودِ کتابخانهٔ PineJS در باندلِ rahavard نیست (از دامنهٔ TV بار می‌شود)، پس هرچه
// زیر «تعریفِ مستندِ Pine» است و در برشِ rahavard فقط *نامِ* تابع دیده می‌شود؛ آن
// موارد تک‌تک کامنت دارند.

/** پنجرهٔ کاملِ متناهی لازم است؛ na در پنجره = na در خروجی (رفتارِ Pine) */
function mapWindow(values: (number | undefined)[], period: number, fn: (win: number[]) => number): (number | undefined)[] {
  const out: (number | undefined)[] = new Array(values.length).fill(undefined);
  if (!(period > 0)) return out;
  for (let i = period - 1; i < values.length; i++) {
    const win: number[] = [];
    let ok = true;
    for (let j = i - period + 1; j <= i; j++) {
      const v = values[j];
      if (!isF(v)) {
        ok = false;
        break;
      }
      win.push(v);
    }
    if (ok) out[i] = fn(win);
  }
  return out;
}

/**
 * ta.stdev — «ambiguity/تنها انتخابِ بدونِ شاهد»: خودِ Std.stdev در باندلِ rahavard
 * نیست (از کتابخانهٔ TV بار می‌شود)، پس مخرجِ N یا N-1 را از منبع نمی‌شود خواند.
 * N (population) انتخاب شده چون BOLLِ همین چارت هم sqrt(sum/N) است
 * (node_modules/klinecharts/dist/index.esm.js:3456) — یعنی باندهای این پنل با هم
 * یک مقیاس می‌مانند. اگر ثابت شد TV نمونه‌ای می‌گیرد، فقط همین پرچم true می‌شود؛
 * باندهای Z/BB/Vix ضریبِ ثابتِ sqrt(N/(N-1)) می‌خورند و شکلِ نمودار عوض نمی‌شود.
 */
export const STDEV_SAMPLE = false;
function stdev(values: (number | undefined)[], period: number): (number | undefined)[] {
  return mapWindow(values, period, (win) => {
    const mean = win.reduce((a, b) => a + b, 0) / win.length;
    const sumSq = win.reduce((a, b) => a + (b - mean) * (b - mean), 0);
    const denom = STDEV_SAMPLE ? win.length - 1 : win.length;
    if (!(denom > 0)) return NaN;
    return Math.sqrt(sumSq / denom);
  });
}

/**
 * ta.rma (Wilder): بذر = میانگینِ سادهٔ اولین دورهٔ کامل، سپس alpha=1/period.
 * «ambiguity» همان seed: در Pine rma پیش از دورهٔ نخست na است (نه «آخرین مقدار»)،
 * و همین را lib/indicators.ts هم برای rsiِ وایلدر رعایت کرده — پس DT با بقیهٔ
 * FTS یک‌سان است.
 */
function rma(values: (number | undefined)[], period: number): (number | undefined)[] {
  const out: (number | undefined)[] = new Array(values.length).fill(undefined);
  if (!(period > 0)) return out;
  const alpha = 1 / period;
  let prev: number | undefined;
  let seedSum = 0;
  let seedN = 0;
  for (let i = 0; i < values.length; i++) {
    const v = values[i];
    if (!isF(v)) continue;
    if (prev === undefined) {
      seedSum += v;
      seedN += 1;
      if (seedN === period) {
        prev = seedSum / period;
        out[i] = prev;
      }
      continue;
    }
    prev = alpha * v + (1 - alpha) * prev;
    out[i] = prev;
  }
  return out;
}

const highest = (values: (number | undefined)[], period: number) =>
  mapWindow(values, period, (win) => Math.max(...win));
const lowest = (values: (number | undefined)[], period: number) =>
  mapWindow(values, period, (win) => Math.min(...win));

/** ta.tr: بیشینهٔ (high-low, |high-close[1]|, |low-close[1]|)؛ کندلِ اول high-low */
function trueRange(data: MabnaCandle[]): (number | undefined)[] {
  return data.map((d, i) => {
    const rangeHl = d.high - d.low;
    const prevClose = i > 0 ? data[i - 1].close : undefined;
    if (!isF(prevClose)) return fin(rangeHl);
    return fin(Math.max(rangeHl, Math.abs(d.high - prevClose), Math.abs(d.low - prevClose)));
  });
}

/** ta.atr = rma(tr) — تعریفِ مستندِ Pine؛ بدنهٔ Std.atr در باندل نیست */
function atr(data: MabnaCandle[], period: number): (number | undefined)[] {
  return rma(trueRange(data), period);
}

/** ta.vwma = sma(src*vol)/sma(vol) — تعریفِ مستندِ Pine */
function vwma(values: (number | undefined)[], volumes: number[], period: number): (number | undefined)[] {
  const out: (number | undefined)[] = new Array(values.length).fill(undefined);
  if (!(period > 0)) return out;
  for (let i = period - 1; i < values.length; i++) {
    let sv = 0;
    let svv = 0;
    let ok = true;
    for (let j = i - period + 1; j <= i; j++) {
      const v = values[j];
      const vol = volumes[j];
      if (!isF(v) || !isF(vol)) {
        ok = false;
        break;
      }
      sv += v * vol;
      svv += vol;
    }
    if (ok) out[i] = svv !== 0 ? sv / svv : NaN;
  }
  return out;
}

/**
 * ta.linreg(src, length, 0) — نقطهٔ انتهاییِ خطِ رگرسیونِ کمترین‌مربعات روی پنجره.
 * x=0..length-1؛ offset=0 یعنی ارزیابی در x=length-1 (کندلِ جاری). پنجرهٔ ناقص = na.
 */
function linreg(values: (number | undefined)[], period: number): (number | undefined)[] {
  const out: (number | undefined)[] = new Array(values.length).fill(undefined);
  if (!(period > 0)) return out;
  if (period === 1) return values.map((v) => v);
  const meanX = (period - 1) / 2;
  return mapWindow(values, period, (win) => {
    let sumY = 0;
    for (const v of win) sumY += v;
    const meanY = sumY / win.length;
    let cov = 0;
    let varX = 0;
    for (let j = 0; j < win.length; j++) {
      cov += (win[j] - meanY) * (j - meanX);
      varX += (j - meanX) * (j - meanX);
    }
    if (!(varX > 0)) return NaN;
    return meanY + (cov / varX) * (win.length - 1 - meanX);
  });
}

/**
 * ta.stoch(source, source, source, length) — همان کسری که rahavard با سه‌آرگومانِ
 * یکسان (سریِ RSI) صدا می‌زند: (src - lowest(src,len)) / (highest-len - lowest-len) * 100.
 * مخرجِ صفر (سریِ تخت) در Pine na می‌دهد؛ این‌جا هم undefined.
 */
function stoch(values: (number | undefined)[], period: number): (number | undefined)[] {
  const hi = highest(values, period);
  const lo = lowest(values, period);
  return values.map((v, i) => {
    if (!isF(v) || !isF(hi[i]) || !isF(lo[i])) return undefined;
    const span = hi[i] - lo[i];
    if (!(span !== 0)) return undefined;
    return ((v - lo[i]!) / span) * 100;
  });
}

/** ta.cross(a,b) = تقاطع در دو جهت (crossover یا crossunder) */
function cross(a: (number | undefined)[], b: (number | undefined)[]): (boolean | undefined)[] {
  return a.map((_, i) => {
    if (i === 0) return undefined;
    const a0 = a[i - 1];
    const b0 = b[i - 1];
    const a1 = a[i];
    const b1 = b[i];
    if (!isF(a0) || !isF(b0) || !isF(a1) || !isF(b1)) return undefined;
    return (a0 < b0 && a1 > b1) || (a0 > b0 && a1 < b1);
  });
}

/** e.Std[src](ctx) با ورودیِ نوعِ منبع (open/high/…/hlcc4) */
function source(kind: MabnaParam | undefined, data: MabnaCandle[]): (number | undefined)[] {
  const key = typeof kind === 'string' ? kind : 'close';
  return data.map((d) => {
    switch (key) {
      case 'open':
        return fin(d.open);
      case 'high':
        return fin(d.high);
      case 'low':
        return fin(d.low);
      case 'hl2':
        return fin((d.high + d.low) / 2);
      case 'hlc3':
        // hlc3 = (H+L+C)/3 — شاهد: در FIBB خودِ بدنه hlcc4 را (h+l+c+c)/4 نوشته،
        // یعنی C یک‌بار در hlc3 و دوبار در hlcc4 می‌آید.
        return fin((d.high + d.low + d.close) / 3);
      case 'ohlc4':
        return fin((d.open + d.high + d.low + d.close) / 4);
      case 'hlcc4':
        return fin((d.high + d.low + d.close + d.close) / 4);
      default:
        return fin(d.close);
    }
  });
}

/** ابزارهایِ Std، بیرون‌زده برای تست (نه برای مصرفِ چارت) */
export const pineStd = { sma, ema, stdev, rma, highest, lowest, trueRange, atr, vwma, linreg, stoch, cross, source };

// ═══════════════════════════════════════════════════════════════ studies ═══════

// ── 1) DT Oscillator ─────────────────────────────── آفست 5406410 / study_DT.js 55-62
// بدنه: close → RSI(وایلدر؛ مدولِ ۶۳۷۳ همان باندل: change → rma(gain)/rma(loss) →
// 100-100/(1+rs)) → Std.stoch(rsi,rsi,rsi,lengthStoch) → sma(smoothK) → sma(smoothD).
// دو خروجیِ بدنه هر دو با id="plot_k" هستند (کویکِ خودِ rahavard؛ plot_d در metainfo
// بی‌مقدار می‌ماند) — خطِ دوم همان D است. plot_r در metainfo هست ولی بدنه هرگز
// مقدارش را نمی‌دهد، لذا در این پورت هم ندارد. بندهای ۷۵/۲۵ از نوع bands است (نه
// plot) پس در داده نمی‌آید. defaults.inputs: 8 / 5 / 3 / 3.
function calcDTOscillator(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const lengthRSI = Math.round(num(indicator.calcParams[0], 8));
  const lengthStoch = Math.round(num(indicator.calcParams[1], 5));
  const smoothK = Math.round(num(indicator.calcParams[2], 3));
  const smoothD = Math.round(num(indicator.calcParams[3], 3));
  const close = dataList.map((d) => d.close);
  const rsiSeries = clean(rsi(close, lengthRSI));
  const rawK = stoch(rsiSeries, lengthStoch);
  const k = clean(sma(toNull(rawK), smoothK));
  const d = clean(sma(toNull(k), smoothD));
  return finishRows(dataList.map((_, i) => ({ k: k[i], d: d[i] })));
}

const DT_OSCILLATOR: MabnaIndicator = {
  name: 'MabnaDT',
  shortName: 'DTOsc',
  series: 'normal', // is_price_study:!1
  precision: 2,
  calcParams: [8, 5, 3, 3],
  figures: [
    { key: 'k', title: 'K: ', type: 'line', styles: solid(PAL.dtK) },
    { key: 'd', title: 'D: ', type: 'line', styles: solid(PAL.dtD) },
  ],
  calc: calcDTOscillator,
};

// ── 2) Z Score ─────────────────────────────────────── آفست 5408420 / study_Z.js 113-127
// بدنه (سطر ۱۱۴): src = e.Std[this.src](ctx) → z = (src - sma(src,len)) / stdev(src,len)؛
// چهار خطِ ثابتِ باندها (+StdDevs، -StdDevs، +_StdDevs، -_StdDevs) و کدِ رنگِ میله.
// سطلِ رنگ (سطر ۱۱۵) یک index است نه داده (۱۰۰..۹۰۰)؛ در همان بدنه خوانده شده و
// کلیدِ barColor گذاشته می‌شود ولی figure ندارد تا مقیاسِ پنل را خراب نکند.
// defaults.inputs: length 20، StdDevs 2، _StdDevs 1، src "close".
function calcZScore(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const length = Math.round(num(indicator.calcParams[0], 20));
  const stdDevs = num(indicator.calcParams[1], 2);
  const underStdDevs = num(indicator.calcParams[2], 1);
  const srcKind = indicator.calcParams[3] ?? 'close';
  const src = source(srcKind, dataList);
  const mean = clean(sma(toNull(src), length));
  const sd = stdev(src, length);
  const z = src.map((v, i) => {
    if (!isF(v) || !isF(mean[i]) || !isF(sd[i]) || sd[i] === 0) return undefined;
    return (v - mean[i]!) / sd[i]!;
  });
  return finishRows(
    dataList.map((_, i) => ({
      z: z[i],
      // باندها در بدنه مقدارِ ثابت‌اند (trackPrice) و به z گره نخورده‌اند
      stdDevsBand: stdDevs,
      negStdDevsBand: -stdDevs,
      underStdDevsBand: underStdDevs,
      negUnderStdDevsBand: -underStdDevs,
      barColor: z[i] === undefined ? undefined : zBucket(z[i]!),
    })),
  );
}

/** شاخه‌های سطر ۱۱۵ study_Z.js — دقیقاً همان آستانه‌ها */
function zBucket(z: number): number {
  if (z < -1.5) return 600;
  if (z < -1) return 700;
  if (z < -0.5) return 800;
  if (z < 0) return 900;
  if (z < 0.5) return 100;
  if (z < 1) return 200;
  if (z < 1.5) return 300;
  if (z < 2) return 400;
  return 500;
}

const Z_SCORE: MabnaIndicator = {
  name: 'MabnaZScore',
  shortName: 'Z Score',
  series: 'normal',
  precision: 2,
  calcParams: [20, 2, 1, 'close'],
  figures: [
    { key: 'z', title: 'Z: ', type: 'line', styles: solid(PAL.zLine) },
    { key: 'stdDevsBand', title: '+StdDevs: ', type: 'line', styles: solid(PAL.zBand) },
    { key: 'negStdDevsBand', title: '-StdDevs: ', type: 'line', styles: solid(PAL.zBand) },
    { key: 'underStdDevsBand', title: '+StdDevs_: ', type: 'line', styles: solid(PAL.zBand) },
    { key: 'negUnderStdDevsBand', title: '-StdDevs_: ', type: 'line', styles: solid(PAL.zBand) },
  ],
  calc: calcZScore,
};

// ── 3) Squeeze Momentum [LazyBear] ─────────────────── آفست 5411620 / study_SQZ.js 94
// بدنه: BB(20,2) روی close؛ KC(20,1.5) با دامنه = useTrueRange ? ta.tr : (high-low)؛
// on = lowBB>upKC && upBB<loKC ، off = lowBB<upKC && upBB>loKC ، بقیه = هیچ؛
// avgHL = (highest(high,20)+lowest(low,20))/2 ، ji = (avgHL + sma(close,20))/2 ،
// momentum = linreg(close-ji, lengthKC, 0). چهار خروجیِ بدنه با ترتیبِ plotsِ
// metainfo (خط‌ها + colorerها) خوانده می‌شود: [momentum، رنگِ momentum، 0، state].
// state: 0=هیچ، 1=on، 2=off (عینِ `k?0:R?1:2`). رنگِ momentum هم کدِ ۰..۳ است
// (صعودی/نزولیِ مثبت/منفی نسبت به momentumِ کندلِ قبل) — index است نه داده.
// defaults.inputs: lengthBB 20، multBB 2، lengthKC 20، multKC 1.5، useTrueRange true.
function calcSqueezeMomentum(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const lengthBB = Math.round(num(indicator.calcParams[0], 20));
  const multBB = num(indicator.calcParams[1], 2);
  const lengthKC = Math.round(num(indicator.calcParams[2], 20));
  const multKC = num(indicator.calcParams[3], 1.5);
  const useTrueRange = flag(indicator.calcParams[4]) || indicator.calcParams[4] === undefined;

  const close = dataList.map((d) => d.close);
  const bbMid = clean(sma(close, lengthBB));
  const bbDev = stdev(close, lengthBB);
  const bbUpper = bbMid.map((m, i) => (isF(m) && isF(bbDev[i]) ? m + multBB * bbDev[i]! : undefined));
  const bbLower = bbMid.map((m, i) => (isF(m) && isF(bbDev[i]) ? m - multBB * bbDev[i]! : undefined));

  const kcMid = clean(sma(close, lengthKC));
  const range: (number | undefined)[] = useTrueRange ? trueRange(dataList) : dataList.map((d) => fin(d.high - d.low));
  const kcRange = clean(sma(toNull(range), lengthKC));
  const kcUpper = kcMid.map((m, i) => (isF(m) && isF(kcRange[i]) ? m + kcRange[i]! * multKC : undefined));
  const kcLower = kcMid.map((m, i) => (isF(m) && isF(kcRange[i]) ? m - kcRange[i]! * multKC : undefined));

  const onState = bbLower.map((lb, i) => {
    const ub = bbUpper[i];
    const ku = kcUpper[i];
    const kl = kcLower[i];
    if (!isF(lb) || !isF(ub) || !isF(ku) || !isF(kl)) return undefined;
    return lb > kl && ub < ku ? 1 : lb < kl && ub > ku ? 2 : 0; // هیچ → 0 (کدِ palette)
  });

  const hh = highest(dataList.map((d) => d.high), lengthKC);
  const ll = lowest(dataList.map((d) => d.low), lengthKC);
  const mom = close.map((_, i) => {
    if (!isF(hh[i]) || !isF(ll[i]) || !isF(kcMid[i])) return undefined;
    const avgHL = (hh[i]! + ll[i]!) / 2;
    const ji = (avgHL + kcMid[i]!) / 2;
    return fin(close[i] - ji);
  });
  const momentum = linreg(mom, lengthKC);
  const prevMomentum = [undefined, ...momentum.slice(0, -1)];
  return finishRows(
    dataList.map((_, i) => ({
      momentum: momentum[i],
      sqz: 0, // plot_1 در بدنه همیشه صفر است؛ وضعیت فقط با رنگ (sqzColor) نشان می‌دهد
      momColor: momentumColor(momentum[i], prevMomentum[i]),
      sqzColor: onState[i],
    })),
  );
}

/** `i=G>0?G>H?0:1:G<H?2:3` سطر ۹۵ study_SQZ.js؛ H مقدارِ کندلِ قبل است */
function momentumColor(cur: number | undefined, prev: number | undefined): number | undefined {
  if (!isF(cur)) return undefined;
  const h = isF(prev) ? prev : 0; // Std.nz در بدنه
  if (cur > 0) return cur > h ? 0 : 1;
  return cur < h ? 2 : 3;
}

const SQUEEZE_MOMENTUM: MabnaIndicator = {
  name: 'MabnaSQZMOM',
  shortName: 'SQZMOM_LB',
  series: 'normal',
  precision: 2,
  calcParams: [20, 2, 20, 1.5, true],
  figures: [
    { key: 'momentum', title: 'Momentum: ', type: 'bar', baseValue: 0, styles: byCode(PAL.sqzMomentum, 'momColor') },
    { key: 'sqz', title: 'SQZ: ', type: 'circle', baseValue: 0, styles: byCode(PAL.sqzState, 'sqzColor') },
  ],
  calc: calcSqueezeMomentum,
};

// ── 4) HalfTrend ────────────────────────────────────── آفست 5414043 / study_HT.js 103-123
// حالت‌محورِ واقعی (this.trend/nextTrend/maxLowPrice/minHighPrice…). ارجاعِ اصلی:
// d = ta.atr(100)/2 (دورهٔ ۱۰۰ در بدنه hardcode است، نه ورودی) و p = channelDeviation*d؛
// y = بالاترین highِ پنجرهٔ amplitude (بجز na → high)، b = پایین‌ترین lowِ پنجره؛
// در حالتِ بعدی (nextTrend==1): maxLowPrice=max(b,…) و اگر sma(high,amp)<maxLowPrice و
// close<low[1] → روند نزولی (trend=1). در غیر این صورت: minHighPrice=min(y,…) و اگر
// sma(low,amp)>minHighPrice و close>high[1] → trend=0/nextTrend=1.
// ترتیبِ بازگشت با plotsِ metainfo (خط‌ها + colorer) خوانده شد:
//   [C, T, l, u, arrowUp, arrowDown, buy, sell] → plot_0=C، plot_0_colors=T،
//   plot_1=«ATR High»=l، plot_2=«ATR Low»=u، plot_3..6 = shapeها. (T فقط ۰/۱ است و
//   palette_0 دقیقاً دو رنگ دارد؛ پس T کدِ رنگ است نه مقدارِ خط.)
// defaults.inputs: amplitude 2، channelDeviation 2، showArrows/showChannels/showBuySellLabels true.
function calcHalfTrend(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const amplitude = Math.max(1, Math.round(num(indicator.calcParams[0], 2)));
  const channelDeviation = num(indicator.calcParams[1], 2);
  const showArrows = indicator.calcParams[2] === undefined || flag(indicator.calcParams[2]);
  const showChannels = indicator.calcParams[3] === undefined || flag(indicator.calcParams[3]);
  const showBuySellLabels = indicator.calcParams[4] === undefined || flag(indicator.calcParams[4]);

  const highs = dataList.map((d) => d.high);
  const lows = dataList.map((d) => d.low);
  const closes = dataList.map((d) => d.close);
  // NaN == na در همین حلقه نگه داشته می‌شود تا بدنهٔrahavard کلمه‌به‌کلمه ترجمه شود؛
  // finishRows در انتها همهٔ naها را حذف می‌کند (قرار: na = نقطه نباشد، نه صفر).
  const asNaN = (v: number | undefined): number => (isF(v) ? v : NaN);
  const dSeries = atr(dataList, 100).map((a) => (isF(a) ? a / 2 : NaN)); // d = Std.atr(100)/2
  const pSeries = dSeries.map((d) => (isF(d) ? channelDeviation * d : NaN)); // p = channelDeviation*d
  const smaHigh = clean(sma(highs, amplitude)).map(asNaN); // _
  const smaLow = clean(sma(lows, amplitude)).map(asNaN); // x
  const winHigh = clean(highest(highs, amplitude)).map(asNaN); // m → y
  const winLow = clean(lowest(lows, amplitude)).map(asNaN); // g → b
  const na = (v: number) => !Number.isFinite(v);
  const nz = (v: number, fallback: number) => (na(v) ? fallback : v);

  let trend = 0;
  let nextTrend = 0;
  let maxLowPrice = NaN;
  let minHighPrice = NaN;
  let up = 0;
  let down = 0;
  let arrowUp = NaN;
  let arrowDown = NaN;
  let prevTrend: number | null = null;
  let prevUp = NaN;
  let prevDown = NaN;

  const rows: MabnaRow[] = [];
  for (let i = 0; i < dataList.length; i++) {
    const high = highs[i];
    const low = lows[i];
    const close = closes[i];
    if (na(maxLowPrice)) maxLowPrice = low;
    if (na(minHighPrice)) minHighPrice = high;

    const d = dSeries[i];
    const p = pSeries[i];
    // highestbars/lowestbars در بدنه فقط برای رسیدن به *مقدارِ* آن آفست استفاده
    // می‌شوند، پس بیشینه/کمینهٔ پنجره همان چیز است و tie-break فرق نمی‌کند.
    const y = na(winHigh[i]) ? high : winHigh[i];
    const b = na(winLow[i]) ? low : winLow[i];
    const prevLow = i > 0 ? lows[i - 1] : NaN;
    const prevHigh = i > 0 ? highs[i - 1] : NaN;

    if (nextTrend === 1) {
      maxLowPrice = Math.max(b, maxLowPrice);
      if (smaHigh[i] < maxLowPrice && close < nz(prevLow, low)) {
        trend = 1;
        nextTrend = 0;
        minHighPrice = y;
      }
    } else {
      minHighPrice = Math.min(y, minHighPrice);
      if (smaLow[i] > minHighPrice && close > nz(prevHigh, high)) {
        trend = 0;
        nextTrend = 1;
        maxLowPrice = b;
      }
    }

    let l = NaN;
    let u = NaN;
    if (trend === 0) {
      if (prevTrend !== null && prevTrend !== 0) {
        up = na(prevDown) ? down : prevDown;
        arrowUp = up - d;
      } else {
        up = na(prevUp) ? maxLowPrice : Math.max(maxLowPrice, prevUp);
      }
      l = up + p;
      u = up - p;
    } else {
      if (prevTrend !== null && prevTrend !== 1) {
        down = na(prevUp) ? up : prevUp;
        arrowDown = down + d;
      } else {
        down = na(prevDown) ? minHighPrice : Math.min(minHighPrice, prevDown);
      }
      l = down + p;
      u = down - p;
    }

    const line = trend === 0 ? up : down;
    const dir = trend === 0 ? 0 : 1; // کدِ رنگِ palette_0 (۰ آبی، ۱ قرمز)
    const E = !na(arrowUp) && trend === 0 && prevTrend === 1;
    const P = !na(arrowDown) && trend === 1 && prevTrend === 0;

    rows.push({
      halfTrend: line,
      trend: dir,
      atrHigh: showChannels ? l : NaN,
      atrLow: showChannels ? u : NaN,
      arrowUp: showArrows && E ? u : NaN,
      arrowDown: showArrows && P ? l : NaN,
      buyLabel: showBuySellLabels && E ? u : NaN,
      sellLabel: showBuySellLabels && P ? l : NaN,
    });

    prevTrend = trend;
    prevUp = up;
    prevDown = down;
  }
  return finishRows(rows);
}

const HALF_TREND: MabnaIndicator = {
  name: 'MabnaHalfTrend',
  shortName: 'HalfTrend',
  series: 'price', // is_price_study:!0
  precision: 2,
  calcParams: [2, 2, true, true, true],
  figures: [
    // `trend` در بدنه کدِ رنگِ plot_0 است (palette_0 دو رنگ دارد) نه خطِ جدا — پس
    // figure ندارد و فقط در سطر می‌ماند.
    { key: 'halfTrend', title: 'HalfTrend: ', type: 'line', styles: byCode([PAL.htUp, PAL.htDown], 'trend') },
    { key: 'atrHigh', title: 'ATR High: ', type: 'line', styles: solid(PAL.htUp) },
    { key: 'atrLow', title: 'ATR Low: ', type: 'line', styles: solid(PAL.htDown) },
    { key: 'arrowUp', title: 'Arrow Up: ', type: 'circle', styles: solid(PAL.htUp) },
    { key: 'arrowDown', title: 'Arrow Down: ', type: 'circle', styles: solid(PAL.htDown) },
  ],
  calc: calcHalfTrend,
};

// ── 5) Support And Resistance Levels With Breaks ───── آفست 5418689 / study_SR.js 98-129
// بدنه: پیوتِ سقف در اندیس p=i-rightBars اگر all(left ≤ v) و all(right < v) باشد
// (مقایسه‌ها عینِ `i>e` و `i>=e` در حلقه‌ها) و پیوتِ کف قرینه با (left ≥ v) و (right > v).
// سطحِ «در حالِ استفاده» = پیوتِ خامِ کندلِ قبل، وگرنه سطحِ چسبندهٔ قبلی.
// volume momentum: k = 100*(ema(vol,5)-ema(vol,10))/ema(vol,10)؛
// break صعودی: close[1] ≤ سطح_قبلی و close > سطح_جدید (و نزولی قرینه)؛ با «بدنه بر
// سایه» و k>volumeTreshold → لیبلِ Break، وگرنه Wick.
// ترتیبِ بازگشت با plots (خطوط + colorerها): [res, resThick, sup, supThick, G, W, V, H].
// defaults.inputs: showBreaks true، leftBars 15، rightBars 15، volumeTreshold 20.
function calcSrLevels(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const showBreaks = indicator.calcParams[0] === undefined || flag(indicator.calcParams[0]);
  const leftBars = Math.max(0, Math.round(num(indicator.calcParams[1], 15)));
  const rightBars = Math.max(0, Math.round(num(indicator.calcParams[2], 15)));
  const volumeTreshold = num(indicator.calcParams[3], 20);

  const highs = dataList.map((d) => d.high);
  const lows = dataList.map((d) => d.low);
  const closes = dataList.map((d) => d.close);
  const volumes = dataList.map((d) => d.volume);
  const ema5 = clean(ema(toNull(volumes), 5));
  const ema10 = clean(ema(toNull(volumes), 10));
  const at = (arr: number[], i: number) => (i >= 0 && i < arr.length ? arr[i] : undefined);

  const x = rightBars + 1;
  let prevRawPH: number | undefined;
  let prevRawPL: number | undefined;
  let prevHighUse: number | undefined;
  let prevLowUse: number | undefined;
  let highUse: number | undefined;
  let lowUse: number | undefined;

  const rows: MabnaRow[] = [];
  for (let i = 0; i < dataList.length; i++) {
    const barCount = i + 1;
    const h = highs[i];
    const l = lows[i];
    const o = dataList[i].open;
    const c = closes[i];
    let rawPH: number | undefined;
    let rawPL: number | undefined;

    if (barCount > x) {
      const p = i - rightBars;
      const candH = at(highs, p);
      if (isF(candH)) {
        let ok = true;
        for (let n = 1; n <= leftBars && ok; n++) {
          const v = at(highs, p - n);
          if (!isF(v) || v > candH) ok = false;
        }
        for (let n = 1; n <= rightBars && ok; n++) {
          const v = at(highs, p + n);
          if (!isF(v) || v >= candH) ok = false;
        }
        if (ok) rawPH = candH;
      }
      const candL = at(lows, p);
      if (isF(candL)) {
        let ok = true;
        for (let n = 1; n <= leftBars && ok; n++) {
          const v = at(lows, p - n);
          if (!isF(v) || v < candL) ok = false;
        }
        for (let n = 1; n <= rightBars && ok; n++) {
          const v = at(lows, p + n);
          if (!isF(v) || v <= candL) ok = false;
        }
        if (ok) rawPL = candL;
      }
    }

    const E = isF(prevRawPH) ? prevRawPH : isF(highUse) ? highUse : undefined;
    const P = isF(prevRawPL) ? prevRawPL : isF(lowUse) ? lowUse : undefined;
    const changedH = isF(E) && isF(prevHighUse) ? E !== prevHighUse : false;
    const changedL = isF(P) && isF(prevLowUse) ? P !== prevLowUse : false;
    const volMom = isF(ema10[i]) && ema10[i] !== 0 && isF(ema5[i]) ? (100 * (ema5[i]! - ema10[i]!)) / ema10[i]! : 0;
    const prevClose = at(closes, i - 1);

    const bullBreak = showBreaks && isF(prevClose) && isF(prevHighUse) && isF(c) && isF(E) && prevClose <= prevHighUse && c > E;
    const bearBreak = showBreaks && isF(prevClose) && isF(prevLowUse) && isF(c) && isF(P) && prevClose >= prevLowUse && c < P;
    const bearVolume = bearBreak && !(o - c < h - o) && volMom > volumeTreshold; // G
    const bullVolume = bullBreak && !(o - l > c - o) && volMom > volumeTreshold; // W
    const bullWick = bullBreak && o - l > c - o; // V
    const bearWick = bearBreak && o - c < h - o; // H
    const resHold = !changedH && isF(E) ? 0 : undefined; // plot_0_colors
    const supHold = !changedL && isF(P) ? 0 : undefined; // plot_1_colors

    const row: MabnaRow = {
      resistance: isF(E) ? E : undefined,
      support: isF(P) ? P : undefined,
      // shapeها در rahavard value=1 دارند و مکانشان AboveBar/BelowBar است؛ آن value
      // داده نیست، پس این‌جا روی خودِ سطح نشان داده می‌شوند (انحرافِ نمایشی، نه محاسباتی).
      bearBreak: bearVolume ? E : undefined,
      bullBreak: bullVolume ? E : undefined,
      bullWick: bullWick ? E : undefined,
      bearWick: bearWick ? P : undefined,
      resHold,
      supHold,
    };
    rows.push(row);

    // paint-on-pivot: معادلِ offset:-x در بدنه — پیوت روی کندلِ خودش نشان داده می‌شود
    if (isF(rawPH) && rows[i - rightBars]) rows[i - rightBars]!.pivotHigh = rawPH;
    if (isF(rawPL) && rows[i - rightBars]) rows[i - rightBars]!.pivotLow = rawPL;

    prevRawPH = rawPH;
    prevRawPL = rawPL;
    prevHighUse = E;
    prevLowUse = P;
    highUse = isF(E) ? E : isF(highUse) ? highUse : undefined;
    lowUse = isF(P) ? P : isF(lowUse) ? lowUse : undefined;
  }
  return finishRows(rows);
}

const SR_LEVELS: MabnaIndicator = {
  name: 'MabnaSRLevels',
  shortName: 'SR Levels',
  series: 'price', // is_price_study:!0
  precision: 2,
  calcParams: [true, 15, 15, 20],
  figures: [
    { key: 'resistance', title: 'Resistance: ', type: 'line', styles: solid(PAL.srResistance) },
    { key: 'support', title: 'Support: ', type: 'line', styles: solid(PAL.srSupport) },
    { key: 'pivotHigh', title: 'Pivot H: ', type: 'circle', styles: solid(PAL.srResistance) },
    { key: 'pivotLow', title: 'Pivot L: ', type: 'circle', styles: solid(PAL.srSupport) },
    { key: 'bullBreak', title: 'Bull Break: ', type: 'circle', styles: solid(PAL.srBullLabel) },
    { key: 'bearBreak', title: 'Bear Break: ', type: 'circle', styles: solid(PAL.srBearLabel) },
    { key: 'bullWick', title: 'Bull Wick: ', type: 'circle', styles: solid(PAL.srBullLabel) },
    { key: 'bearWick', title: 'Bear Wick: ', type: 'circle', styles: solid(PAL.srBearLabel) },
  ],
  calc: calcSrLevels,
};

// ── 6) WaveTrend Oscillator [WT] ───────────────────── آفست 5422874 / study_WT.js 81
// بدنه: esa=ema(hlc3,n1) ؛ d=ema(|hlc3-esa|,n1) ؛ ci=(hlc3-esa)/(0.015*d) ؛
// wt=ema(ci,n2) ؛ avg=sma(wt,4) (عددِ ۴ در بدنه hardcode است) ؛ hist=wt-avg.
// شش خطِ اولِ خروجیِ بدنه مقدارِ ثابت است: 0 و ترازهای 60/53/-60/-53.
// defaults.inputs: n1 10، n2 21، ob1 60، ob2 53، os1 -60، os2 -53.
function waveTrendCore(dataList: MabnaCandle[], n1: number, n2: number) {
  const hlc3 = source('hlc3', dataList);
  const esa = clean(ema(toNull(hlc3), n1));
  const absDiff = hlc3.map((v, i) => (isF(v) && isF(esa[i]) ? Math.abs(v - esa[i]!) : undefined));
  const d = clean(ema(toNull(absDiff), n1));
  const ci = hlc3.map((v, i) => {
    if (!isF(v) || !isF(esa[i]) || !isF(d[i]) || d[i] === 0) return undefined; // 0.015*0 → na
    return (v - esa[i]!) / (0.015 * d[i]!);
  });
  const wt = clean(ema(toNull(ci), n2));
  const avg = clean(sma(toNull(wt), 4));
  const hist = wt.map((v, i) => (isF(v) && isF(avg[i]) ? v - avg[i]! : undefined));
  return { wt, avg, hist };
}

function calcWaveTrend(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const n1 = Math.round(num(indicator.calcParams[0], 10));
  const n2 = Math.round(num(indicator.calcParams[1], 21));
  const ob1 = num(indicator.calcParams[2], 60);
  const ob2 = num(indicator.calcParams[3], 53);
  const os1 = num(indicator.calcParams[4], -60);
  const os2 = num(indicator.calcParams[5], -53);
  const { wt, avg, hist } = waveTrendCore(dataList, n1, n2);
  return finishRows(
    dataList.map((_, i) => ({
      // پنج خطِ اولِ خروجیِ بدنه ثابت‌اند (۰ و ترازها) — مثلِ TV از کندلِ اول کشیده می‌شوند
      zero: 0,
      ob1,
      os1,
      ob2,
      os2,
      wt: wt[i],
      avg: avg[i],
      hist: hist[i],
    })),
  );
}

const WAVE_TREND: MabnaIndicator = {
  name: 'MabnaWaveTrend',
  shortName: 'WT_LB',
  series: 'normal',
  precision: 2,
  calcParams: [10, 21, 60, 53, -60, -53],
  figures: [
    { key: 'zero', title: 'Zero: ', type: 'line', styles: solid(PAL.wtZero) },
    { key: 'ob1', title: 'OB1: ', type: 'line', styles: solid(PAL.wtLevelHigh) },
    { key: 'os1', title: 'OS1: ', type: 'line', styles: solid(PAL.wtLevelLow) },
    { key: 'ob2', title: 'OB2: ', type: 'line', styles: solid(PAL.wtLevelHigh) },
    { key: 'os2', title: 'OS2: ', type: 'line', styles: solid(PAL.wtLevelLow) },
    { key: 'wt', title: 'WT: ', type: 'line', styles: solid(PAL.wtLine) },
    { key: 'avg', title: 'AVG: ', type: 'line', styles: solid(PAL.wtAvg) },
    { key: 'hist', title: 'WT-AVG: ', type: 'bar', baseValue: 0, styles: solid(PAL.wtHist) },
  ],
  calc: calcWaveTrend,
};

// ── 7) Fibonacci Bollinger Bands ───────────────────── آفست 5425907 / study_FIBB.js 106-125
// بدنه: basis = vwma(src, length)؛ dev = mult*stdev(src, length)؛ سطرهای فیبوناچی
// ±0.236/±0.382/±0.5/±0.618/±0.764/±1 × dev (علامتِ ضرب *first* در `l=this.mult*stdev`
// و سپس `.236*l` — یعنی ضریبِ استندرِوی پیش از کسرِ فیبو اعمال می‌شود).
// defaults.inputs: length 200، Source "hlc3"، mult 3.
const FIB_FRACTIONS = [0.236, 0.382, 0.5, 0.618, 0.764, 1] as const;

function calcFibBollinger(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const length = Math.round(num(indicator.calcParams[0], 200));
  const srcKind = indicator.calcParams[1] ?? 'hlc3';
  const mult = num(indicator.calcParams[2], 3);
  const src = source(srcKind, dataList);
  const volumes = dataList.map((d) => d.volume ?? 0);
  const basis = vwma(src, volumes, length);
  const dev = stdev(src, length).map((s) => (isF(s) ? mult * s : undefined));
  return finishRows(
    dataList.map((_, i) => {
      const row: MabnaRow = { basis: basis[i] };
      if (!isF(basis[i]) || !isF(dev[i])) return row;
      FIB_FRACTIONS.forEach((f) => {
        row[`up${f}`] = basis[i]! + f * dev[i]!;
        row[`dn${f}`] = basis[i]! - f * dev[i]!;
      });
      return row;
    }),
  );
}

const FIB_BOLLINGER: MabnaIndicator = {
  name: 'MabnaFibBB',
  shortName: 'FBB',
  series: 'price', // is_price_study:!0
  precision: 2,
  calcParams: [200, 'hlc3', 3],
  figures: [
    { key: 'basis', title: 'Basis: ', type: 'line', styles: solid(PAL.fibBasis) },
    { key: 'up0.236', title: '+0.236: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'up0.382', title: '+0.382: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'up0.5', title: '+0.5: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'up0.618', title: '+0.618: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'up0.764', title: '+0.764: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'up1', title: '+1.0: ', type: 'line', styles: solid(PAL.fibOuterUp) },
    { key: 'dn0.236', title: '-0.236: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'dn0.382', title: '-0.382: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'dn0.5', title: '-0.5: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'dn0.618', title: '-0.618: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'dn0.764', title: '-0.764: ', type: 'line', styles: solid(PAL.fibInner) },
    { key: 'dn1', title: '-1.0: ', type: 'line', styles: solid(PAL.fibOuterDown) },
  ],
  calc: calcFibBollinger,
};

// ── 8) WaveTrend with Crosses ──────────────────────── آفست 5429832 / study_WTC.js 135
// همانِ هستهٔ WT ( esa/d/ci با n1، wt=ema(ci,n2)، avg=sma(wt,4) ) + `_ = cross(wt,avg)`؛
// خروجی: [0,60,-60,53,-53, wt, avg, wt-avg, cross?avg, cross?avg, cross?code, cross?code]
// و code = `b-y>0?0:1` یعنی ۰=تقاطعِ نزولی (قرمز) و ۱=صعودی (سبز).
// defaults.inputs مثل WT: 10 / 21 / 60 / 53 / -60 / -53.
function calcWaveTrendCross(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const n1 = Math.round(num(indicator.calcParams[0], 10));
  const n2 = Math.round(num(indicator.calcParams[1], 21));
  const ob1 = num(indicator.calcParams[2], 60);
  const ob2 = num(indicator.calcParams[3], 53);
  const os1 = num(indicator.calcParams[4], -60);
  const os2 = num(indicator.calcParams[5], -53);
  const { wt, avg, hist } = waveTrendCore(dataList, n1, n2);
  const crossed = cross(wt, avg);
  return finishRows(
    dataList.map((_, i) => ({
      zero: 0,
      ob1,
      os1,
      ob2,
      os2,
      wt: wt[i],
      avg: avg[i],
      hist: hist[i],
      // مقدارِ shape در بدنه خودِ avg است (تقاطع روی خطِ میانگین)؛ کدِ رنگ:
      // `b-y>0?0:1` → ۰ = تقاطع نزولی (قرمز)، ۱ = صعودی (سبز)
      cross: crossed[i] ? avg[i] : undefined,
      crossColor: crossed[i] && isF(wt[i]) && isF(avg[i]) ? (avg[i]! - wt[i]! > 0 ? 0 : 1) : undefined,
    })),
  );
}

const WAVE_TREND_CROSS: MabnaIndicator = {
  name: 'MabnaWaveTrendCross',
  shortName: 'WT_CROSS_LB',
  series: 'normal',
  precision: 2,
  calcParams: [10, 21, 60, 53, -60, -53],
  figures: [
    { key: 'zero', title: 'Zero: ', type: 'line', styles: solid(PAL.wtZero) },
    { key: 'ob1', title: 'OB1: ', type: 'line', styles: solid(PAL.wtLevelHigh) },
    { key: 'os1', title: 'OS1: ', type: 'line', styles: solid(PAL.wtLevelLow) },
    { key: 'ob2', title: 'OB2: ', type: 'line', styles: solid(PAL.wtLevelHigh) },
    { key: 'os2', title: 'OS2: ', type: 'line', styles: solid(PAL.wtLevelLow) },
    { key: 'wt', title: 'WT: ', type: 'line', styles: solid(PAL.wtLine) },
    { key: 'avg', title: 'AVG: ', type: 'line', styles: solid(PAL.wtAvg) },
    { key: 'hist', title: 'WT-AVG: ', type: 'bar', baseValue: 0, styles: solid(PAL.wtHist) },
    { key: 'cross', title: 'Cross: ', type: 'circle', styles: byCode(PAL.wtcCross, 'crossColor') },
  ],
  calc: calcWaveTrendCross,
};

// ── 9) CM_Williams_Vix_Fix Finds Market Bottoms ────── آفست 5433623 / study_VIX.js 81
// بدنه: hnif = highest(close, pd)؛ vixFix = (hnif-low)/hnif*100؛
// bblUp = sma(vixFix,bbl) + mult*stdev(vixFix,bbl)؛
// rhi = highest(vixFix,lb)*ph و rlo = lowest(vixFix,lb)*pl (pl=1.01 یعنی *بالای* کف)؛
// bottom = (vixFix>=bblUp || vixFix>=rhi) ? 0 : 1 — در بدنه هیچ na-guard ندارد، پس
// پیش از پُرشدنِ پنجره‌ها شرط false و نتیجه ۱ است؛ عیناً همان نگه داشته شده.
// دو خطِ rhi/rlo فقط با hp=true و خطِ bblUp فقط با sd=true plotted می‌شوند.
// defaults.inputs: pd 22، bbl 20، mult 2، lb 50، ph 0.85، pl 1.01، hp false، sd false.
function calcVixFix(dataList: MabnaCandle[], indicator: { calcParams: MabnaParam[] }): MabnaRow[] {
  const pd = Math.round(num(indicator.calcParams[0], 22));
  const bbl = Math.round(num(indicator.calcParams[1], 20));
  const mult = num(indicator.calcParams[2], 2);
  const lb = Math.round(num(indicator.calcParams[3], 50));
  const ph = num(indicator.calcParams[4], 0.85);
  const pl = num(indicator.calcParams[5], 1.01);
  const showHighRange = flag(indicator.calcParams[6]);
  const showSdLine = flag(indicator.calcParams[7]);

  const hnif = highest(dataList.map((d) => d.close), pd);
  const vix = dataList.map((d, i) => {
    if (!isF(hnif[i]) || hnif[i] === 0) return undefined;
    return ((hnif[i]! - d.low) / hnif[i]!) * 100;
  });
  const mid = clean(sma(toNull(vix), bbl));
  const dev = stdev(vix, bbl).map((s) => (isF(s) ? mult * s : undefined));
  const upperBand = vix.map((_, i) => (isF(mid[i]) && isF(dev[i]) ? mid[i]! + dev[i]! : undefined));
  const rangeHigh = highest(vix, lb).map((v) => (isF(v) ? v * ph : undefined));
  const rangeLow = lowest(vix, lb).map((v) => (isF(v) ? v * pl : undefined));
  const bottom = vix.map((v, i) => {
    const overBand = isF(v) && isF(upperBand[i]) && v >= upperBand[i]!;
    const overRange = isF(v) && isF(rangeHigh[i]) && v >= rangeHigh[i]!;
    return overBand || overRange ? 0 : 1;
  });
  return finishRows(
    dataList.map((_, i) => ({
      rangeHigh: showHighRange ? rangeHigh[i] : undefined,
      rangeLow: showHighRange ? rangeLow[i] : undefined,
      vix: vix[i],
      bottom: bottom[i],
      upperBand: showSdLine ? upperBand[i] : undefined,
    })),
  );
}

const VIX_FIX: MabnaIndicator = {
  name: 'MabnaVixFix',
  shortName: 'CM_Williams_Vix_Fix',
  series: 'normal',
  precision: 2,
  calcParams: [22, 20, 2, 50, 0.85, 1.01, false, false],
  figures: [
    { key: 'rangeHigh', title: 'Range High: ', type: 'line', styles: solid(PAL.vixRange) },
    { key: 'rangeLow', title: 'Range Low: ', type: 'line', styles: solid(PAL.vixRange) },
    // در metainfo، `bottom` خط نیست؛ colorerِ هیستوگرامِ vix است (۰ سبز = کف، ۱ خاکستری)
    { key: 'vix', title: 'Vix Fix: ', type: 'bar', baseValue: 0, styles: byCode(PAL.vixBottom, 'bottom') },
    { key: 'upperBand', title: 'Upper Band: ', type: 'line', styles: solid(PAL.vixBand) },
  ],
  calc: calcVixFix,
};

// ═══════════════════════════════════════════════════════════ registry ══════════

/** نام → تعریف. نام‌ها باید با کاتالوگِ منو یکی باشد (تست همین را می‌گیرد). */
export const MABNA_TEMPLATES: Record<string, MabnaIndicator> = {
  [DT_OSCILLATOR.name]: DT_OSCILLATOR,
  [Z_SCORE.name]: Z_SCORE,
  [SQUEEZE_MOMENTUM.name]: SQUEEZE_MOMENTUM,
  [HALF_TREND.name]: HALF_TREND,
  [SR_LEVELS.name]: SR_LEVELS,
  [WAVE_TREND.name]: WAVE_TREND,
  [FIB_BOLLINGER.name]: FIB_BOLLINGER,
  [WAVE_TREND_CROSS.name]: WAVE_TREND_CROSS,
  [VIX_FIX.name]: VIX_FIX,
};

export const MABNA_INDICATOR_LIST: MabnaIndicator[] = Object.values(MABNA_TEMPLATES);

/** نام‌هایی که تعریفشان واقعاً هست — مابقی در منو نشان داده نمی‌شوند */
export function availableMabnaIndicators(): TvIndicator[] {
  return MABNA_INDICATORS.filter((i) => MABNA_TEMPLATES[i.name] != null);
}

/**
 * ثبت روی apiِ klinecharts؛ idempotent بر پایهٔ getSupportedIndicators و مثل
 * registerTvIndicators: یک مطالعهٔ ناسازگار نباید بقیه را متوقف کند.
 * خروجی: تعدادِ ثبت‌شده.
 */
export function registerMabnaIndicators(api: {
  registerIndicator: (indicator: unknown) => void;
  getSupportedIndicators?: () => string[];
}): number {
  const have = new Set(api.getSupportedIndicators?.() ?? []);
  let n = 0;
  for (const entry of availableMabnaIndicators()) {
    if (have.has(entry.name)) continue;
    const tpl = MABNA_TEMPLATES[entry.name];
    try {
      api.registerIndicator(tpl);
      n += 1;
    } catch {
      // مطالعهٔ شکست‌خورده فقط همین یکی است؛ بقیه ثبت می‌مانند
    }
  }
  return n;
}
