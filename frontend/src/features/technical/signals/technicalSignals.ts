// features/technical/signals/technicalSignals.ts -- سیگنال FTS با وزن 3
// تاییدیه روند از آرایش چهار مووینگ و تریگر ورود از خط آبی پرواز.
// گیت ریسک بنیادی در صورت فعال بودن شرط، جلوی سیگنال پرواز را می گیرد.
import type { AgentSignal, Confidence, Direction } from '@contracts/signal';
import type { DataQuality } from '@contracts/signal';
import type { SetupKind, TechnicalPayload, WeeklyTrend } from '@contracts/technical';
import { toFaDigits } from '@shared/lib/fmt';
import {
  avgVolume,
  bearishDivergence,
  detectChoch,
  fibZones,
  FTS_RSI_PERIOD,
  ftsMAs,
  lastValid,
  majorResistance,
  majorSupport,
  ma14TrailingExit,
  maStack,
  rsi,
  swingLows,
} from '../lib/indicators';

/** کمینه کندل معتبر برای داوری کامل */
export const MIN_CANDLES = 50;
/** ماندگاری سیگنال روزانه: 48 ساعت */
export const TECH_VALID_MS = 48 * 3600_000;
const NODATA_VALID_MS = 7 * 24 * 3600_000;
/** تایید حجم شکست: 1.5 برابر میانگین 20 جلسه */
export const JET_VOL_MULT = 1.5;

export type TechInput = {
  symbol: string;
  opens: (number | null)[];
  closes: (number | null)[];
  highs: (number | null)[];
  lows: (number | null)[];
  volumes: (number | null)[];
  /** نتیجه گیت ریسک بنیادی؛ null یعنی بررسی نشده */
  riskGatePass: boolean | null;
  /** اعمال شرط گیت از استور تنظیمات */
  enforceRiskGates: boolean;
  /** رأیِ هفتگیِ موتورِ FTSِ سرور — گیتِ وتوی هفتگی فقط از همین می‌خواند */
  weekly?: WeeklyTrend | null;
};

function faNum(x: number, digits = 1): string {
  return toFaDigits(x.toFixed(digits));
}

function nodata(symbol: string, ts: number): AgentSignal<TechnicalPayload> {
  return {
    id: `technical:${symbol}:nodata:${ts}`,
    agentId: 'technical',
    symbol,
    ts,
    direction: 'neutral',
    confidence: 'nodata',
    weight: 'major',
    title: `داده تکنیکال ${symbol} نیست`,
    rationale: 'تاریخچه قیمت معتبری برای این نماد نیست؛ داوری تکنیکال ممکن نیست.',
    score: null,
    evidence: ['tech:no_history'],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: NODATA_VALID_MS,
    payload: { kind: 'setup', timeframe: 'daily', setups: [], stopLossRef: null, stopLossPrice: null, keyLevels: [], dataQuality: 'incomplete', weekly: null },
  };
}

export function technicalSignal(input: TechInput, ts = Date.now()): AgentSignal<TechnicalPayload> {
  const { symbol } = input;
  const valid = input.closes.filter((c) => c != null).length;
  if (!symbol || valid === 0) return nodata(symbol || 'unknown', ts);

  const short = valid < MIN_CANDLES;
  const last = lastValid(input.closes) ?? 0;
  const lastOpen = lastValid(input.opens);
  const lastVol = lastValid(input.volumes);
  const avgVol = avgVolume(input.volumes, 20);

  const mas = ftsMAs(input.closes);
  const m14 = lastValid(mas[14]);
  const m21 = lastValid(mas[21]);
  const m52 = lastValid(mas[52]);
  const m100 = lastValid(mas[100]);
  const stack = maStack(m14, m21, m52, m100);

  const jet = majorResistance(input.highs.slice(0, -1), 120);
  const support = majorSupport(input.lows, 120);
  const jetTrigger =
    jet != null &&
    last >= jet.price &&
    lastOpen != null &&
    last > lastOpen &&
    avgVol != null &&
    lastVol != null &&
    lastVol > JET_VOL_MULT * avgVol;

  const choch = detectChoch(input.highs, input.lows, input.closes, 3);

  const setups = new Set<SetupKind>();
  let total = 0;
  const bits: string[] = [];

  if (stack === 'bull') {
    total += 2;
    setups.add('trend');
    bits.push('آرایش صعودی مووینگ ها (14 بالای 21 بالای 52 بالای 100)');
  } else if (stack === 'bear') {
    total -= 2;
    setups.add('trend');
    bits.push('آرایش نزولی مووینگ ها');
  }

  if (jetTrigger && jet) {
    total += 3;
    setups.add('breakout');
    bits.push(`شکست خط آبی ${faNum(jet.price, 0)} با کندل تثبیت و حجم ${faNum((lastVol ?? 0) / (avgVol ?? 1))} برابری`);
  }

  if (choch.type === 'bearish') {
    total -= 3;
    setups.add('choch');
    bits.push(`خط چین قرمز نزولی در ${choch.level != null ? faNum(choch.level, 0) : '-'}؛ حد خروج`);
  } else if (choch.type === 'bullish') {
    total += 2;
    setups.add('choch');
    bits.push(`خط چین قرمز صعودی در ${choch.level != null ? faNum(choch.level, 0) : '-'}؛ بازگشت روند`);
  }

  // RSI(14) وایلدر + واگرایی منفی (RD−) — FTS_SPEC بخش اول بند ۵
  const rsiSeries = rsi(input.closes, FTS_RSI_PERIOD);
  const divBear = bearishDivergence(input.highs, rsiSeries);
  if (divBear) {
    total -= 2;
    setups.add('bearish_div');
    bits.push('واگرایی منفی RSI (سقف قیمتی بالاتر با سقف RSI پایین‌تر)');
  }

  // کمربند فیبوی لگاریتمی — FTS_SPEC بخش اول بند ۳: داخل زون = کاندید ورود پله‌ای
  const fib = fibZones(input.highs, input.lows, input.closes);
  const inFibZone = fib != null && (fib.zone3340.inZone || fib.zone61870.inZone);
  if (fib && inFibZone) {
    total += 1;
    setups.add('fibonacci');
    bits.push(fib.zone61870.inZone ? 'قیمت داخل کمربند طلایی ۶۱.۸-۷۰٪' : 'قیمت داخل کمربند ۳۳-۴۰٪');
  }

  // خروج با «کندل کامل زیر MA(14)» — FTS_SPEC بخش اول بند ۵
  const ma14Exit = ma14TrailingExit(input.opens, input.highs, input.lows, input.closes, mas[14]);
  if (ma14Exit.exit) {
    total -= 3;
    bits.push('کندل کامل زیر MA(14) — سیگنال خروج');
  }

  const score = Math.max(0, Math.min(100, Math.round(50 + 8 * total)));
  let direction: Direction = total >= 2 ? 'bullish' : total <= -2 ? 'bearish' : 'neutral';
  if (ma14Exit.exit && direction === 'bullish') direction = 'neutral';
  if (direction === 'neutral' && !short) setups.add('range');

  // دروازه ریسک: سهم مردود یعنی پرواز صادر نمی شود
  const gateBlocked = input.enforceRiskGates && input.riskGatePass === false;
  if (gateBlocked) {
    direction = 'neutral';
    setups.clear();
  }

  const dataQuality: DataQuality = short ? 'partial' : 'complete';
  const confidence: Confidence = gateBlocked ? 'low' : short ? 'low' : score >= 70 ? 'high' : score >= 45 ? 'medium' : 'low';
  if (short) bits.push(`فقط ${faNum(valid, 0)} کندل معتبر؛ داوری احتیاطی است`);
  if (gateBlocked) bits.push('سهم در گیت ریسک بنیادی مردود است؛ سیگنال پرواز صادر نشد');

  // حد ضرر نوسان‌گیر: ۵٪ زیر آخرین کف سوینگ روند صعودی (FTS_SPEC بند ۵)؛
  // در نبود کف سوینگ، مرجع به MA(14) تنزل می‌کند.
  const swingArr = swingLows(input.lows, 3);
  const swingLow = swingArr.length > 0 ? swingArr[swingArr.length - 1].price : null;
  const risingLowStop = swingLow != null ? swingLow * 0.95 : null;
  const bullStopRef = risingLowStop != null ? 'rising_low' : 'ma14';
  const bullStopPrice = risingLowStop ?? m14;

  return {
    id: `technical:${symbol}:setup:${ts}`,
    agentId: 'technical',
    symbol,
    ts,
    direction,
    confidence,
    weight: 'major',
    title: gateBlocked
      ? `تکنیکال ${symbol} پشت گیت ریسک ماند`
      : direction === 'bullish'
        ? `پرواز ${symbol} تایید شد`
        : direction === 'bearish'
          ? `تکنیکال ${symbol} نزولی است`
          : `تکنیکال ${symbol} در انتظار شکست خط آبی است`,
    rationale: bits.length > 0 ? bits.join('؛ ') + '.' : 'همگرایی مشخصی دیده نشد.',
    score: gateBlocked ? 50 : score,
    evidence: gateBlocked
      ? ['tech:risk_gate_block']
      : [
          'tech:ma_stack',
          'tech:jet_trigger',
          'tech:choch',
          ...(divBear ? ['tech:rsi_div'] : []),
          ...(inFibZone ? ['tech:fib_zone'] : []),
          ...(ma14Exit.exit ? ['tech:ma14_exit'] : []),
        ],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: TECH_VALID_MS,
    payload: {
      kind: 'setup',
      timeframe: 'daily',
      setups: [...setups],
      stopLossRef: direction === 'neutral' ? null : direction === 'bullish' ? bullStopRef : 'swing_stop',
      stopLossPrice: direction === 'bullish' ? bullStopPrice : direction === 'bearish' ? (support?.price ?? null) : null,
      keyLevels: [
        ...(jet != null ? [{ type: 'resistance', price: jet.price }] : []),
        ...(support != null ? [{ type: 'support', price: support.price }] : []),
      ],
      dataQuality,
      weekly: input.weekly ?? null,
    },
  };
}
