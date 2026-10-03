// features/technical/signals/technicalSignals.ts -- سیگنال تکنیکال برایِ مستر، از رأیِ موتورِ FTSِ سرور
//
// این فایل «موتور» نیست: هیچ آستانه، هیچ پنجرۀ پیوت و هیچ فرمولِ تشخیصی
// نمی‌سازد. هر تشخیص (جت، CHoCH، کمربند فیبو، خروجِ MA14، واگرایی RSI، حد ضرر،
// هم‌راستاییِ سه‌زمانه) از `fts` همانی خوانده می‌شود که چارت و پنل «وضعیت FTS»
// می‌خوانند (`/api/fts/{symbol}` ← `api/chart.py::_fts_analyze_candles`).
// پیش از این همین‌جا چهار تشخیصِ دوم با فرمولِ دیگری اجرا می‌شد: جت = عبور از
// مقاومتِ ۱۲۰ کندله با حجمِ ۱٫۵× (`JET_VOL_MULT`) در حالی که موتورِ جزوه نردبانِ
// مقاومت را بی‌شرطِ حجم می‌سنجد؛ CHoCH/فیبو/MA14/واگرایی هم از lib/indicators.ts
// (بازنویسیِ TS از پایتون) می‌آمدند. شاهدِ زنده (۱۴۰۵-۰۷-۱۱، فولاد): موتور
// `jet.active=false` («بدنهٔ نزولی») می‌گفت و سیگنالِ همین‌جا «شکست خط آبی» می‌داد.
//
// وزن‌ها (۲/۳/۱/۲/۳) و نگاشتِ نمره `50 + 8*total` عمداً دست‌نخورده‌اند: این‌ها
// ریتمِ هم‌سنجیِ ایجت‌ها درِ مسترند، نه قواعدِ جزوۀ تکنیکال. چیزی که از جزوه
// نمی‌آید اینجا اختراع نشده؛ اگر موتور چیزی نگوید، سیگنال هم می‌گوید «نظر نداریم».
import type { AgentSignal, Confidence, DataQuality, Direction } from '@contracts/signal';
import type { SetupKind, TechnicalPayload, WeeklyTrend } from '@contracts/technical';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';

/** کمینه کندل معتبر برای داوری کامل */
export const MIN_CANDLES = 50;
/** ماندگاری سیگنال روزانه: 48 ساعت */
export const TECH_VALID_MS = 48 * 3600_000;
const NODATA_VALID_MS = 7 * 24 * 3600_000;

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
  /** پاسخِ کاملِ `/api/fts/{symbol}`؛ تنها منبعِ تشخیص در این فایل */
  fts?: FtsAnalysisData | null;
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

  const fts = input.fts ?? null;
  const l1 = fts?.exit_engine?.l1;
  const l4 = fts?.exit_engine?.l4;
  const jet = fts?.jet;
  const choch = fts?.choch;
  const fib = fts?.fib;
  const alignment = fts?.trend?.alignment ?? 'na';
  const vetoed = (fts?.trend?.matrix?.decision ?? '') === 'REJECT';
  /** موتور هنوز رأیی نداده (تحلیل در جریان است یا بی‌نتیجه بوده) */
  const noVerdict = fts == null;

  const short = valid < MIN_CANDLES;
  const setups = new Set<SetupKind>();
  let total = 0;
  const bits: string[] = [];

  // هم‌راستاییِ سه‌زمانه (روز/هفته/ماه) — `trend.alignment` درِ خودِ موتور
  if (alignment === 'up') {
    total += 2;
    setups.add('trend');
    bits.push('سه تایمِ روز/هفته/ماه صعودی‌اند (رأیِ موتور)');
  } else if (alignment === 'down') {
    total -= 2;
    setups.add('trend');
    bits.push('سه تایمِ روز/هفته/ماه نزولی‌اند (رأیِ موتور)');
  }

  // جت: عبور از نردبانِ مقاومت با بدنهٔ صعودی — همان تعریفِ `_fts_jet_setup`
  if (jet?.active === true) {
    total += 3;
    setups.add('breakout');
    bits.push(
      `جت: عبور از مقاومت${jet.resistance != null ? ` ${faNum(jet.resistance, 0)}` : ''}` +
        (jet.ath ? ' (سقف تاریخی)' : '') +
        (jet.pct_above_res != null ? `، ${faNum(jet.pct_above_res)}٪ بالاتر` : ''),
    );
  } else if (jet?.reason) {
    bits.push(`جت نیست: ${jet.reason}`);
  }

  // CHoCH: شکست آخرینِ سقف در روند نزولی یا آخرینِ کف در روند صعودی
  if (choch?.bearish === true) {
    total -= 3;
    setups.add('choch');
    bits.push(`CHoCH نزولی${choch.level != null ? ` در ${faNum(choch.level, 0)}` : ''} — حد خروج`);
  } else if (choch?.bullish === true) {
    total += 2;
    setups.add('choch');
    bits.push(`CHoCH صعودی${choch.level != null ? ` در ${faNum(choch.level, 0)}` : ''} — بازگشت روند`);
  }

  // واگرایی منفی RSI — لایۀ ۴ موتورِ خروج
  if (l4?.rsi_divergence === true) {
    total -= 2;
    setups.add('bearish_div');
    bits.push('واگرایی منفی RSI (سقفِ قیمتیِ بالاتر با سقفِ RSIِ پایین‌تر)');
  }

  // کمربندهای فیبو (۳۳–۴۰ و ۶۱٫۸–۷۰) — از موتور، با همان مبنایِ موج
  const in3340 = fib?.zone_33_40?.in_zone === true;
  const in61870 = fib?.zone_618_70?.in_zone === true;
  if (in3340 || in61870) {
    total += 1;
    setups.add('fibonacci');
    bits.push(in61870 ? 'قیمت داخل کمربند طلایی ۶۱.۸–۷۰٪' : 'قیمت داخل کمربند ۳۳–۴۰٪');
  }

  // خروج با MA(14) — لایۀ ۱ موتورِ خروج (دو کندلِ کامل زیر میانگین)
  const ma14Exit = l1?.ma14_exit === true;
  if (ma14Exit) {
    total -= 3;
    bits.push('کندلِ کامل زیر MA(14) — سیگنال خروج');
  }

  const score = Math.max(0, Math.min(100, Math.round(50 + 8 * total)));
  let direction: Direction = total >= 2 ? 'bullish' : total <= -2 ? 'bearish' : 'neutral';
  if (ma14Exit && direction === 'bullish') direction = 'neutral';
  // رأیِ درختِ FTS: وتوی هفتگی «فرصت ورود» نمی‌دهد (چارت ۳، بخش ۲). سیگنالِ
  // مستر نباید جایش «پرواز تأیید شد» بنویسد وقتی موتور می‌گوید REJECT.
  if (vetoed && direction === 'bullish') direction = 'neutral';
  if (direction === 'neutral' && !short) setups.add('range');

  // دروازه ریسک: سهم مردود یعنی پرواز صادر نمی شود
  const gateBlocked = input.enforceRiskGates && input.riskGatePass === false;
  if (gateBlocked) {
    direction = 'neutral';
    setups.clear();
  }

  const dataQuality: DataQuality = noVerdict || short ? 'partial' : 'complete';
  const confidence: Confidence = gateBlocked || noVerdict
    ? 'low'
    : short ? 'low' : score >= 70 ? 'high' : score >= 45 ? 'medium' : 'low';
  if (short) bits.push(`فقط ${faNum(valid, 0)} کندل معتبر؛ داوری احتیاطی است`);
  if (noVerdict) bits.push('موتور FTS هنوز برای این نماد رأی منتشر نکرده؛ تشخیصی از این فایل ساخته نمی‌شود');
  if (vetoed) bits.push('درخت FTS: وتوی تایم هفتگی — ورود ندارد');
  if (gateBlocked) bits.push('سهم در گیت ریسک بنیادی مردود است؛ سیگنال پرواز صادر نشد');

  // حد ضرر: همان عددِ موتورِ خروج (لایۀ ۱) با همان مبنایِ اعلام‌شده؛ برایِ
  // نمادِ نزولی کفِ کانال/پایۀ نقطه‌زنیِ خودِ موتور مرجع است، نه محاسبۀ دوم.
  // مبنارا «ترجمه» نمی‌کنیم: رشتهٔ خامِ `stop_basis` می‌رود و اگر موتور مبنایی
  // نگفت، null می‌ماند (نه واژۀ سه‌تاییِ قدیمیِ فرانت).
  const bullStopPrice = l1?.hard_stop ?? null;
  const bullStopRef = l1?.stop_basis ?? null;
  const bearRef = fts?.point_hunt?.floor_price ?? fts?.range_box?.bottom ?? null;

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
      : noVerdict
        ? `تکنیکال ${symbol} در انتظار رأیِ موتور`
        : direction === 'bullish'
          ? `پرواز ${symbol} تایید شد`
          : direction === 'bearish'
            ? `تکنیکال ${symbol} نزولی است`
            : vetoed
              ? `تکنیکال ${symbol}: وتوی تایم هفتگی`
              : `تکنیکال ${symbol} در انتظار شکست خط آبی است`,
    rationale: bits.length > 0 ? bits.join('؛ ') + '.' : 'همگرایی مشخصی دیده نشد.',
    score: gateBlocked ? 50 : score,
    evidence: gateBlocked
      ? ['tech:risk_gate_block']
      : noVerdict
        ? ['tech:awaiting_engine']
        : [
            'tech:trend_alignment',
            ...(jet?.active === true ? ['tech:jet_trigger'] : []),
            ...(choch?.bullish === true || choch?.bearish === true ? ['tech:choch'] : []),
            ...(l4?.rsi_divergence === true ? ['tech:rsi_div'] : []),
            ...(in3340 || in61870 ? ['tech:fib_zone'] : []),
            ...(ma14Exit ? ['tech:ma14_exit'] : []),
            ...(vetoed ? ['tech:weekly_veto'] : []),
          ],
    sourceView: 'technical',
    sourceRef: ['API'],
    validForMs: TECH_VALID_MS,
    payload: {
      kind: 'setup',
      timeframe: 'daily',
      setups: [...setups],
      stopLossRef: direction === 'bullish' ? bullStopRef : null,
      stopLossPrice: direction === 'bullish' ? bullStopPrice : direction === 'bearish' ? bearRef : null,
      keyLevels: [
        ...(jet?.resistance != null ? [{ type: 'resistance' as const, price: jet.resistance }] : []),
        ...(bearRef != null ? [{ type: 'support' as const, price: bearRef }] : []),
      ],
      dataQuality,
      weekly: input.weekly ?? null,
    },
  };
}
