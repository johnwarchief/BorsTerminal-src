/**
 * frontend-v2/src/features/technical/indicators/oscillatorIndicators.ts
 *
 * نیمۀ دومِ سه اندیکاتورِ hybrid.
 *
 * رجیستری این سه را `category: 'hybrid'` نامیده یعنی «نوسان‌گر در پنلِ خودش +
 * سیگنال روی چارتِ قیمت»، اما تا پیش از این فقط اورلیِ سیگنال نوشته شده بود؛
 * هیچ خطِ RSI‌ای در هیچ کجای برنامه رسم نمی‌شد و پنلِ دومِ وجود نداشت. این فایل
 * همان نیمۀ گمشده است: یک اندیکاتورِ بومیِ KLineCharts v10 برای هرکدام، که در
 * پنلِ اختصاصیِ خودِ نام (`osc_<name>`) می‌نشیند و محور Y اش همیشه ۰ تا ۱۰۰ است.
 *
 * محاسبه از همان calculateRSI/calculateEMA پیاده‌سازی‌شده در
 * overlays/userIndicators.ts می‌آید، پس عددِ پنل و برچسبِ روی چارت یکی است.
 */

import { registerIndicator } from 'klinecharts';
import type { IndicatorTemplate } from 'klinecharts';
import { calculateEMA, calculateRSI } from '../overlays/userIndicators';
import { useTechnicalStore } from '../model/technicalStore';

/** نام‌هایی که نوسان‌گرند و باید در پنلِ جدا رسم شوند، نه روی کندل‌ها */
export const OSCILLATOR_NAMES = ['FiboRSI8', 'RsiMaSmooth', 'MultiVariantRSI'] as const;

export function oscillatorPaneId(name: string): string {
  return `osc_${name}`;
}

type RsiRow = Record<string, number | undefined>;

/**
 * خانه‌های پیش از period را undefined می‌دهد تا خط از جایِ بی‌داده شروع نشود.
 * calculateRSI آن خانه‌ها را ۵۰ برمی‌گرداند و اگر نمایش داده شوند، یک خطِ دروغینِ
 * صاف روی ۵۰ از ابتدای چارت کشیده می‌شود.
 *
 * نکته: هموارسازی همیشه روی همان آرایۀ ۵۰پُر انجام می‌شود، نه روی نسخۀ ماسک‌شده —
 * دقیقاً مثل اورلی‌ها. وگرنه خطِ پنل با برچسبِ واگرایی/تقاطعِ روی چارت دو عددِ
 * متفاوت می‌گفت و کاربر همان را «غلط» می‌دید.
 */
function mask(values: number[], from: number): Array<number | undefined> {
  return values.map((v, i) => (i < from ? undefined : v));
}

/** همان حلقۀ میانگینِ اورلی MultiVariantRSI (پیش‌فرض ۵۰، از i=period به بعد) */
function smaRaw(values: number[], period: number): number[] {
  const out: number[] = new Array(values.length).fill(50);
  for (let i = period; i < values.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += values[i - j];
    out[i] = sum / period;
  }
  return out;
}

function bollingerRaw(values: number[], period: number, mult: number) {
  return values.map((_, i) => {
    if (i < period - 1) return { mid: 50, upper: 50, lower: 50 };
    let sum = 0;
    for (let j = i - period + 1; j <= i; j++) sum += values[j];
    const m = sum / period;
    let sq = 0;
    for (let j = i - period + 1; j <= i; j++) sq += Math.pow(values[j] - m, 2);
    const sd = Math.sqrt(sq / period);
    return { mid: m, upper: m + mult * sd, lower: m - mult * sd };
  });
}

const line = (key: string, title: string) => ({ key, title, type: 'line' });

/**
 * زبانِ بصریِ پنل‌ها، از تصویرِ مرجع و از TradingView:
 * خطِ اصلیِ قرمز، خطِ هموارِ آبی، ترازها خاکستریِ خط‌چین.
 *
 * پیش از این هیچ stylesی ست نبود، پس klinecharts پالتِ پیش‌فرضِ خودش را به ترتیبِ
 * figure می‌داد (زرد/بنفش/آبی/فیروزه‌ای) و ترازهای ۳۰ و ۰ هم مثل داده رنگِ پرشدت
 * می‌گرفتند؛ نتیجه همان چیزی است که «شبیه TradingView نیست» گفته شد.
 */
const INK = { rsi: '#ef5350', smooth: '#2962ff', level: '#787b86' };

const levelLine = { color: INK.level, size: 1, style: 'dashed' as const, dashedValue: [4, 4] };
const dataLine = (color: string) => ({ color, size: 1.5, style: 'solid' as const, smooth: true });

const paneStyles = (order: Array<'rsi' | 'smooth' | 'level'>) => ({
  lines: order.map((k) => (k === 'level' ? levelLine : dataLine(INK[k === 'smooth' ? 'smooth' : 'rsi']))),
  lastValueMark: { show: true },
});

/**
 * TradingView در legendِ پنل فقط سری‌های داده را می‌شمارد، نه ترازها را.
 * figures برای رسم لازم‌اند، پس ترازها را از legend بیرون می‌کشم.
 */
function legendWithoutLevels(labels: Array<{ key: string; title: string }>) {
  return (params: { indicator: { result: RsiRow[]; calcParams: number[] }; crosshair: { dataIndex?: number } }) => {
    const i = params.crosshair?.dataIndex ?? params.indicator.result.length - 1;
    const row = params.indicator.result[i] ?? {};
    return {
      name: '',
      calcParamsText: `(${params.indicator.calcParams[0]})`,
      features: [],
      legends: labels.map((l) => ({
        title: { text: l.title, color: INK.level },
        value: { text: row[l.key] === undefined ? '——' : String(Number(row[l.key]).toFixed(2)), color: l.title === 'هموار' ? INK.smooth : INK.rsi },
      })),
    };
  };
}

/** فیبو تک‌شلیک: RSI(8) با دو ترازِ ۲۳٫۶ و ۷۸٫۶ */
const fiboRsi8: IndicatorTemplate<RsiRow, number> = {
  name: 'FiboRSI8',
  shortName: 'فیبو RSI',
  precision: 2,
  calcParams: [8, 23.6, 78.6],
  shouldOhlc: false,
  minValue: 0,
  maxValue: 100,
  figures: [line('rsi', 'RSI'), line('lo', 'کف'), line('hi', 'سقف')],
  styles: paneStyles(['rsi', 'level', 'level']),
  createTooltipDataSource: legendWithoutLevels([{ key: 'rsi', title: 'RSI' }]) as never,
  calc: (dataList, indicator) => {
    const [period, lo, hi] = indicator.calcParams;
    const closes = dataList.map((d) => d.close);
    const rsi = mask(calculateRSI(closes, period), period);
    return dataList.map((_, i) => ({ rsi: rsi[i], lo, hi }));
  },
};

/** آراس‌آی هموار: RSI(14) + میانگینِ ۹ دورۀ آن + ترازهای ۳۰ و ۷۰ */
const rsiMaSmooth: IndicatorTemplate<RsiRow, number> = {
  name: 'RsiMaSmooth',
  shortName: 'RSI هموار',
  precision: 2,
  calcParams: [14, 9, 30, 70],
  shouldOhlc: false,
  minValue: 0,
  maxValue: 100,
  figures: [line('rsi', 'RSI'), line('ma', 'هموار'), line('lo', '۳۰'), line('hi', '۷۰')],
  styles: paneStyles(['rsi', 'smooth', 'level', 'level']),
  createTooltipDataSource: legendWithoutLevels([
    { key: 'rsi', title: 'RSI' },
    { key: 'ma', title: 'هموار' },
  ]) as never,
  calc: (dataList, indicator) => {
    const [period, maPeriod, lo, hi] = indicator.calcParams;
    const closes = dataList.map((d) => d.close);
    const rawRsi = calculateRSI(closes, period);
    // همان calculateEMA و همان آرایۀ ۵۰پُر که اورلیِ واگرایی برایش تصمیم می‌گیرد
    const smoothRsi = calculateEMA(rawRsi, maPeriod);
    const rsi = mask(rawRsi, period);
    const ma = mask(smoothRsi, period);
    return dataList.map((_, i) => ({ rsi: rsi[i], ma: ma[i], lo, hi }));
  },
};

/**
 * خانوادۀ RSI: همان منحنی، ولی دورۀش و باندها از انتخابِ دراپ‌داون می‌آیند.
 * تغییر دراپ‌داون در-wrapper با remove/createِ دوباره اعمال می‌شود.
 */
const multiVariantRsi: IndicatorTemplate<RsiRow, number> = {
  name: 'MultiVariantRSI',
  shortName: 'RSI',
  precision: 2,
  calcParams: [14, 30, 70],
  shouldOhlc: false,
  minValue: 0,
  maxValue: 100,
  figures: [line('rsi', 'RSI'), line('mid', 'میانه'), line('lo', 'پایین'), line('hi', 'بالا')],
  styles: paneStyles(['rsi', 'smooth', 'level', 'level']),
  createTooltipDataSource: legendWithoutLevels([
    { key: 'rsi', title: 'RSI' },
    { key: 'mid', title: 'هموار' },
  ]) as never,
  calc: (dataList) => {
    const variant = useTechnicalStore.getState().rsiVariant;
    const closes = dataList.map((d) => d.close);
    const period = variant === 'fibo' ? 8 : 14;
    const rawRsi = calculateRSI(closes, period);

    if (variant === 'bb') {
      const bands = bollingerRaw(rawRsi, 20, 2);
      return dataList.map((_, i) =>
        i < 20 ? { rsi: undefined } : { rsi: rawRsi[i], mid: bands[i].mid, lo: bands[i].lower, hi: bands[i].upper }
      );
    }

    if (variant === 'smooth_ma') {
      // همان حلقۀ SMA(9) روی آرایۀ ۵۰پُر که اورلیِ تقاطع برایش تصمیم می‌گیرد
      const ma = mask(smaRaw(rawRsi, 9), period);
      const rsi = mask(rawRsi, period);
      return dataList.map((_, i) => ({ rsi: rsi[i], mid: ma[i], lo: 30, hi: 70 }));
    }

    const levels = variant === 'fibo' ? { lo: 23.6, hi: 78.6 } : { lo: 30, hi: 70 };
    const rsi = mask(rawRsi, period);
    return dataList.map((_, i) => ({ rsi: rsi[i], lo: levels.lo, hi: levels.hi }));
  },
};

export const OSCILLATOR_TEMPLATES: Record<'FiboRSI8' | 'RsiMaSmooth' | 'MultiVariantRSI', IndicatorTemplate<RsiRow, number>> = {
  FiboRSI8: fiboRsi8,
  RsiMaSmooth: rsiMaSmooth,
  MultiVariantRSI: multiVariantRsi,
};

export function registerOscillatorIndicators(): void {
  for (const template of Object.values(OSCILLATOR_TEMPLATES)) {
    try {
      registerIndicator(template);
    } catch {
      // Idempotent: فراخوانیِ مکرر در HMR و تست
    }
  }
}
