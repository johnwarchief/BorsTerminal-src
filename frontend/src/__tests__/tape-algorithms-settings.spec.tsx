// __tests__/tape-algorithms-settings.spec.tsx -- پنج فیلترِ تابلو، آینهٔ فرمول‌هایِ جزوه
//
// سه چیز اینجا تست می‌شود و هر سه قبلاً می‌سوختند:
//   ۱) عددِ پیش‌فرضِ هر فیلتر = عددِ جزوه (دلتای ۲٪، حجم ۳×، پلکانِ [ih][2..59]).
//   ۲) «داده نداشتن» هیچ‌وقت قبول نیست — حلقهٔ خاموشی که ۶۷۱ ردیف را جت می‌زد.
//   ۳) آستانه‌ای که کاربر عوض می‌کند واقعاً رویِ نتیجه اثر می‌گذارد.
import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import type { MarketRow } from '@shared/types/marketRow';
import {
  DEFAULT_TAPE_FILTER_CONFIG,
  TAPE_PRESETS,
  coerceLookback,
  isConfigCustomized,
  matchClockPattern,
  matchJetFilter,
  matchNoqtehFilter,
  matchRoobiFilter,
  matchSmartFlowFilter,
  matchSuspiciousVolume,
  evaluateDynamicQuickFilter,
} from '@features/market/lib/tapeAlgorithms';
import { JET_LADDER, resistanceLadderHigh } from '@features/market/lib/tapeMath';
import { TapeFilterSettingsModal } from '@features/market/components/TapeFilterSettingsModal';
import { useTapeStore } from '@features/market/stores/tapeStore';

/** ردیفی که همهٔ شروطِ فایلِ پنج فیلتر را با هم دارد. */
const passingRow = (overrides: Partial<MarketRow> = {}): MarketRow => ({
  symbol: 'تست',
  p_closing: 1000,
  p_last: 1025,          // +۲٫۵٪ → دلتای ساعتِ فایل
  price_yesterday: 1000,
  percent_change: 2.5,
  percent_last: 2.5,          // (plp) درِ فایل = درصدِ «آخرین» — جت با این داوری می‌کند
  q_tot_tran: 4_000_000,
  tvol: 4_000_000,
  month_avg_vol: 1_000_000,   // ستونِ نمایش «نسبت حجم ماه» → ۴×
  vol_ratio: 4,
  vol_ratio_file: 4,          // قیدِ حجمیِ پنج فیلتر (Σ[ih][0..29]/۳۰)
  prior30_vol: 30_000_000,    // سی نشستِ آخر × ۱M میانگین
  hist_sessions: 60,          // عمرِ نماد از پنجره بیشتر → هر دو درِ ۳۰ و ۵۹ باز است
  min_low_29: 995,            // کمینۀِ [ih][0..28].PriceMin
  // (zd1)/(qd1) = سطرِ اولِ صفِ خرید؛ کف‌روبی با این دو داوری می‌کند.
  buy_q1_cnt: 6,
  buy_q1_vol: 250_000,
  tmin: 900,                  // (tmin) = آستانۀِ مجاز پایین
  vol_dod: 2,
  prev_day_vol: 2_000_000,
  z_tot_tran: 120,
  buyer_power: 2,
  buyer_power_raw: 2,
  buy_i_vol: 2_000_000,
  buy_count_i: 100,
  sell_i_vol: 1_000_000,
  sell_count_i: 100,
  p_min: 1025,
  min30_low: 995,
  ...Object.fromEntries(JET_LADDER.map((k) => [`h${k}_max`, 900])),
  ...overrides,
});

describe('پیش‌فرض‌ها باید خودِ فرمولِ جزوه باشند', () => {
  it('الگوی ساعت: pl >= pc*1.02 و tno > 30', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.clock.minDeltaPct).toBe(2.0);
    expect(DEFAULT_TAPE_FILTER_CONFIG.clock.minTradeCount).toBe(30);
    expect(DEFAULT_TAPE_FILTER_CONFIG.clock.minVolRatio).toBe(1.0);
  });

  it('حجم مشکوک: tvol > 3*avg30 و tno > 50', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume.minRatio).toBe(3.0);
    expect(DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume.minTradeCount).toBe(50);
  });

  it('جت: حجم ۳×، قدرت خریدار ۱٫۵×، آخرین بالای پایانی، پلکانِ کامل، tno > 100', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.jet).toEqual({
      lookbackDays: 59, minBuyerPower: 1.5, minVolRatio: 3.0,
      requireLastAboveClose: true, minChangePct: 0.0, minTradeCount: 100,
    });
    // پلکانِ فایل دقیقاً همین هشت نقطه است — [ih][1] درِ فرمول نیست.
    expect([...JET_LADDER]).toEqual([2, 5, 9, 19, 29, 39, 49, 59]);
  });

  it('کف‌روبی: plp < -1 و qd1 > 100، و گیت‌هایی که جزوه ندارد خاموش‌اند', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.roobi.maxChangePct).toBe(-1.0);
    expect(DEFAULT_TAPE_FILTER_CONFIG.roobi.minTradeCount).toBe(100);
    expect(DEFAULT_TAPE_FILTER_CONFIG.roobi.minVolRatio).toBe(0);
    expect(DEFAULT_TAPE_FILTER_CONFIG.roobi.minBuyerPower).toBe(0);
  });

  it('نقطه‌زنی: فاصله از کف < 3٪ و tno > 5', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.noqteh).toEqual({
      maxDistPct: 3.0, minTradeCount: 5, minVolRatio: 1.0,
    });
  });
});

describe('نبودنِ داده هیچ‌وقت «قبول» نیست', () => {
  it('جت بدونِ مبنایِ حجمِ فایل رد می‌شود، نه اینکه گیتِ حجم بی‌صدا بخورد', () => {
    expect(matchJetFilter(passingRow({ vol_ratio_file: null }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
    // میانگینِ ماه عدد دارد ولی مبناءِ فایل null است: دو مبناء، دو مصرف.
    expect(matchJetFilter(passingRow({ vol_ratio_file: null, month_avg_vol: 1_000_000 }),
                           DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
    // نبودنِ ستونِ نمایشیِ tvol فیلتر را خاموش نمی‌کند: قید، خودِ نسبت است.
    expect(matchJetFilter(passingRow({ tvol: null }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(true);
  });

  it('پلکان: پلۀِ بی‌معامله سقف را نمی‌شکند؛ پنجرۀِ کوتاه سنجش را می‌بندد', () => {
    // سایت برایِ هر نشستِ تقویمی ردیف دارد و نشستِ بی‌معامله PriceMax = صفر
    // می‌گیرد؛ «pl > آن پله» همان‌جا خودبه‌خود برقرار است، پس صفر سقفِ بقیه
    // را پایین نمی‌آورد (و نبودنِ ستون هم از حساب بیرون است).
    expect(resistanceLadderHigh(passingRow({ h9_max: 0 }), 59)).toBe(900);
    expect(resistanceLadderHigh(passingRow({ h9_max: null }), 59)).toBe(900);
    expect(resistanceLadderHigh(passingRow({ h2_max: null, h5_max: null }), 59)).toBe(900);
    // پنجره: lookback=59 یعنی هشت پله → شصت نشستِ تاریخچه لازم است
    expect(resistanceLadderHigh(passingRow({ hist_sessions: 59 }), 59)).toBeNull();
    expect(resistanceLadderHigh(passingRow({ hist_sessions: 60 }), 59)).toBe(900);
    expect(resistanceLadderHigh(passingRow({ hist_sessions: 30 }), 29)).toBe(900);
    expect(resistanceLadderHigh(passingRow({ hist_sessions: 29 }), 29)).toBeNull();
    expect(resistanceLadderHigh(passingRow(), 2)).toBe(900);
  });

  it('جت نقاطِ پلکانِ بلندتر از تایم‌فریمِ انتخابی را لازم ندارد', () => {
    // سقفِ واقعیِ نوزده نشستِ پیش بالاست؛ با lookback=9 آن پله خوانده نمی‌شود
    // و ردیف قبول، با lookback=19 همان ردیف رد می‌شود.
    const row = passingRow({ h19_max: 2000, h29_max: 2000, h39_max: 2000, h49_max: 2000, h59_max: 2000 });
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 9 })).toBe(true);
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 19 })).toBe(false);
    // lookback کوتاه پنجرهٔ نشست هم کوتاه‌تر می‌کند: دَه نشست برایِ پلهٔ ۹ بس است
    expect(matchJetFilter(passingRow({ hist_sessions: 10 }),
                           { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 9 })).toBe(true);
    expect(matchJetFilter(passingRow({ hist_sessions: 9 }),
                           { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 9 })).toBe(false);
  });

  it('قدرت خریدارِ قابل‌محاسبه = رد، حتی اگر آستانه صفر باشد', () => {
    expect(matchJetFilter(passingRow({ buyer_power_raw: null, buyer_power: null,
                                       buy_i_vol: null, sell_i_vol: null }),
                           { ...DEFAULT_TAPE_FILTER_CONFIG.jet, minBuyerPower: 0 })).toBe(false);
  });

  it('ساعت، کف‌روبی، نقطه‌زنی و پول هوشمند هم با دادهٔ غایب رد می‌شوند', () => {
    expect(matchClockPattern(passingRow({ z_tot_tran: null }), DEFAULT_TAPE_FILTER_CONFIG.clock)).toBe(false);
    expect(matchSuspiciousVolume(passingRow({ vol_ratio_file: null }), DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume)).toBe(false);
    expect(matchRoobiFilter(passingRow({ buy_q1_cnt: null }), DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    expect(matchNoqtehFilter(passingRow({ min_low_29: null }), DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
    expect(matchSmartFlowFilter(passingRow({ buyer_power: null }), DEFAULT_TAPE_FILTER_CONFIG.smartFlow)).toBe(false);
  });

  it('پنجرۀِ نشست‌محور: بیست‌ونهشت نشست کفِ فایل نیست، بیست‌ونُه کافی است', () => {
    // نسبتِ حجم را بک‌اند با همان کف می‌سازد، پس سمتِ او «نبودنِ مبناء» همان
    // vol_ratio_file = null است (تستِ پایین). اینجا کفِ پنجره درِ نقطه‌زنی است:
    // فایل [ih][0..28] را می‌خواهد و کمبودش را صفرِ کف می‌بیند، نه میانگینِ کم.
    expect(matchNoqtehFilter(passingRow({ hist_sessions: 28 }), DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
    expect(matchNoqtehFilter(passingRow({ hist_sessions: 29 }), DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(true);
    expect(matchNoqtehFilter(passingRow({ hist_sessions: null }), DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
    expect(matchClockPattern(passingRow({ vol_ratio_file: null }), DEFAULT_TAPE_FILTER_CONFIG.clock)).toBe(false);
  });

  it('نشستِ بی‌معامله پلکان را نمی‌شکند: پلکانِ غایب صفر است، کم‌سابقه نه', () => {
    // سایت برایِ هر نشست ردیف دارد و نشستِ بی‌معامله PriceMax=0 می‌گیرد؛ پس
    // نبودنِ یک پله «سقفِ غایب» نیست. آنچه سنجش را متوقف می‌کند کم بودنِ
    // `hist_sessions` است — همان استثنایی که ExecFilter می‌دهد و ردیف را
    // بیرون می‌اندازد.
    expect(matchJetFilter(passingRow({ h49_max: null, h59_max: null }),
                          DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(true);
    expect(matchJetFilter(passingRow({ hist_sessions: 59 }),
                          DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
  });

  it('NaN و بی‌نهایت هم «داده» حساب نمی‌شوند', () => {
    expect(matchJetFilter(passingRow({ vol_ratio_file: NaN, tvol: Number.POSITIVE_INFINITY }),
                           DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
  });
});

describe('جت: مقایسه با «آخرین» است، نه «پایانی»', () => {
  it('پایانی زیر مقاومت ولی آخرین بالای مقاومت → جت', () => {
    const row = passingRow({ p_closing: 850, p_last: 950 });   // همه سقف‌ها ۹۰۰
    expect(resistanceLadderHigh(row, 59)).toBe(900);
    expect(matchJetFilter(row, DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(true);
  });

  it('آخرینِ دقیقاً روی مقاومت رد می‌شود (جزوه: > نه >=)', () => {
    expect(matchJetFilter(passingRow({ p_last: 900 }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
  });

  it('آخرینِ پایین‌تر از پایانی با وجود شکستِ مقاومت رد می‌شود', () => {
    expect(matchJetFilter(passingRow({ p_last: 700, percent_last: -2.5 }),
                           DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
  });

  it('جت: (plp) درصدِ «آخرین» است، نه درصدِ پایانی', () => {
    // پایانی بالا رفته ولی آخرین پایین‌تر از دیروز است → فایل مردود می‌کند؛
    // خواندنِ plp به‌عنوانِ percent_change همین را «قبول» می‌شمرد.
    expect(matchJetFilter(passingRow({ percent_change: 3.0, percent_last: -1.5 }),
                           DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
    expect(matchJetFilter(passingRow({ percent_change: -3.0, percent_last: 1.5 }),
                           DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(true);
  });
});

describe('شخصی‌سازی آستانه‌ها واقعاً اعمال می‌شود', () => {
  it('دلتای ساعت: آستانهٔ بالاتر همان ردیف را مردود می‌کند', () => {
    const row = passingRow({ p_last: 1025 });
    expect(matchClockPattern(row, { ...DEFAULT_TAPE_FILTER_CONFIG.clock, minDeltaPct: 2.0 })).toBe(true);
    expect(matchClockPattern(row, { ...DEFAULT_TAPE_FILTER_CONFIG.clock, minDeltaPct: 3.0 })).toBe(false);
  });

  it('ضریب حجم جت: آستانهٔ زیر ۳× نتیجه را شل می‌کند، بالای آن سفت', () => {
    const row = passingRow({ h59_max: 1000, p_last: 1025 });   // مقاومت ۱۰۰۰ < آخرین ۱۰۲۵
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, minVolRatio: 4.5 })).toBe(false);
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, minVolRatio: 3.0 })).toBe(true);
  });

  it('تایم‌فریم جت: نقطۀِ بلندترِ پلکان که نشکسته، رد می‌کند', () => {
    const row = passingRow({ h19_max: 1100 });
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 9 })).toBe(true);
    expect(matchJetFilter(row, { ...DEFAULT_TAPE_FILTER_CONFIG.jet, lookbackDays: 19 })).toBe(false);
  });

  it('کف‌روبی: آخرین باید دقیقاً روی آستانۀِ مجازِ پایین باشد (tmin، نه کفِ روز)', () => {
    // (tmin) درِ ExecFilter خودِ سایت = element.pMin = آستانۀِ مجاز. کفِ همین
    // نشست (p_min) چیزِ دیگری است و پیش از این اشتباه خوانده می‌شد.
    const onFloor = passingRow({ p_last: 900, tmin: 900, p_min: 940, percent_last: -2.0 });
    expect(matchRoobiFilter(onFloor, DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(true);
    // یک ریال بالاتر از آستانه → دیگر «رویِ کف» نیست.
    expect(matchRoobiFilter(passingRow({ ...onFloor, p_last: 901 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // رویِ کفِ *روز* نشستن کافی نیست؛ باید آستانه باشد.
    expect(matchRoobiFilter(passingRow({ p_last: 940, tmin: 900, p_min: 940, percent_last: -2.0 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // plp = -۱ اکیداً رد است (فایل: < -1)
    expect(matchRoobiFilter(passingRow({ ...onFloor, percent_last: -1.0 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // درصدِ «پایانی» منفی بودن به تنهائی کافی نیست؛ فایل درصدِ «آخرین» را می‌خواهد.
    expect(matchRoobiFilter(passingRow({ ...onFloor, percent_last: 2.5, percent_change: -2.0 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
  });

  it('کف‌روبی: zd1/qd1 سطرِ اولِ صفِ خریداند، نه حجم و تعدادِ نشستِ پیش', () => {
    // تعدادِ سفارشِ سطرِ اول = ۱ → شرطِ «> ۱» رد می‌کند، هر چقدر هم حجمِ صف زیاد باشد.
    expect(matchRoobiFilter(passingRow({ p_last: 900, tmin: 900, percent_last: -2.0,
                                         buy_q1_cnt: 1, buy_q1_vol: 9_000_000 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // حجمِ سطرِ اول زیرِ ۱۰۰ سهم → رد، با وجودِ صفِ شلوغ.
    expect(matchRoobiFilter(passingRow({ p_last: 900, tmin: 900, percent_last: -2.0,
                                         buy_q1_cnt: 40, buy_q1_vol: 100 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // صفِ خریدِ سطرِ اول ندارد (عمق تهی) → «داده نبود» رد است، نه قبول.
    expect(matchRoobiFilter(passingRow({ p_last: 900, tmin: 900, percent_last: -2.0,
                                         buy_q1_cnt: null, buy_q1_vol: null }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(false);
    // دو سفارشِ ۱۰۰ سهمی رویِ کف = دقیقاً همان چیزی که فایل می‌خواهد.
    expect(matchRoobiFilter(passingRow({ p_last: 900, tmin: 900, percent_last: -2.0,
                                         buy_q1_cnt: 2, buy_q1_vol: 101 }),
                            DEFAULT_TAPE_FILTER_CONFIG.roobi)).toBe(true);
  });

  it('نقطه‌زنی: فاصلۀِ ۳٪ و بالاتر رد می‌شود (فایل: < 3)', () => {
    const at3 = passingRow({ p_closing: 1000, min_low_29: 970 });
    expect(matchNoqtehFilter(at3, { ...DEFAULT_TAPE_FILTER_CONFIG.noqteh, maxDistPct: 3.5 })).toBe(true);
    expect(matchNoqtehFilter(at3, { ...DEFAULT_TAPE_FILTER_CONFIG.noqteh, maxDistPct: 3.0 })).toBe(false);
  });

  it('نقطه‌زنی: کفِ فایل کفِ [ih][0..28] است، نه ستونِ نمایشیِ min30_low', () => {
    // min30_low (کفِ سی نشستِ *معامله‌شده*) ۹۹۵ است و کفِ خامِ پنجره ۸۰۰ →
    // فاصله از کفِ فایل ۲۰٪، یعنی رد. با min30_low می‌شد ۰٫۵٪ و قبول.
    const row = passingRow({ p_closing: 1000, p_min: 800, min30_low: 995, min_low_29: 800 });
    expect(matchNoqtehFilter(row, DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
  });

  it('نقطه‌زنی: کفِ صفرِ پنجره کل ردیف را رد می‌کند (MinPriceOfMonth() != 0)', () => {
    // نشستِ بی‌معامله low=۰ می‌گیرد و فایل خودِ صفر را دلیلِ رد می‌داند؛
    // «صفر را حذف کن و با باقیِ پنجره داوری کن» دو ردیفِ جعلی می‌ساخت که
    // مرجعِ TSETMC هیچ‌کدام را نمی‌داد.
    const row = passingRow({ p_closing: 1000, min_low_29: 0 });
    expect(matchNoqtehFilter(row, DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
  });

  it('نقطه‌زنی: کف‌شکنی (فاصلۀِ منفی) قبول است — فایل فقط سقف می‌گذارد', () => {
    // سنجشِ زندۀِ ۱۴۰۵-۰۷-۰۷ رویِ تابلویِ خودِ سایت: طملي7072 با پایانیِ ۲ و
    // کفِ پنجرۀِ ۳ (فاصله ‎−۵۰٪) درِ «نقطه‌زنی» می‌نشست و درِ ما رد می‌شد.
    // متنِ فایل هیچ کرانِ پایینِ برایِ cfield2 ندارد، و کف‌شکنی خودش
    // قوی‌ترینِ مصداقِ «چسبیده به کف» است.
    const row = passingRow({ p_closing: 1000, min_low_29: 1100 });
    expect(matchNoqtehFilter(row, DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(true);
  });
});

describe('نشانِ «شخصی‌سازی شده» به آستانه‌ها نگاه می‌کند، نه به شیءِ کانفیگ', () => {
  it('کانفیگِ پیش‌فرض شخصی‌سازی‌شده نیست و هر تغییرِ عددی هست', () => {
    expect(isConfigCustomized(DEFAULT_TAPE_FILTER_CONFIG)).toBe(false);
    expect(isConfigCustomized({
      ...DEFAULT_TAPE_FILTER_CONFIG,
      jet: { ...DEFAULT_TAPE_FILTER_CONFIG.jet, minVolRatio: 4 },
    })).toBe(true);
    // یک شیءِ تازه با همان مقدارها نباید «شخصی‌سازی» نشان دهد
    expect(isConfigCustomized(JSON.parse(JSON.stringify(DEFAULT_TAPE_FILTER_CONFIG)))).toBe(false);
  });
});

describe('کانفیگ ذخیره‌شده از نسخهٔ قبل نباید فیلتر را بی‌صدا بخواباند', () => {
  it('«۱ روزه» که دیگر نقطۀِ پلکان نیست به نزدیک‌ترین نقطهٔ معتبر می‌رود', () => {
    expect(coerceLookback(1)).toBe(2);
    expect(coerceLookback(7)).toBe(9);
    expect(coerceLookback(59)).toBe(59);
    expect(coerceLookback(900)).toBe(59);
    expect(coerceLookback(undefined)).toBe(59);
    expect(coerceLookback('abc')).toBe(59);
  });

  it('کانفیگِ ذخیره‌شده با فیلدِ جاافتاده، همان فیلد را از پیش‌فرض می‌گیرد', () => {    // همان چیزی که loadInitialTapeConfig در tapeStore انجام می‌دهد:
    // ادغامِ «ذخیره‌شده روی پیش‌فرض» به‌ازای هر بلوک. اگر روزی بلوکی
    // سرِ خودش جایگزین شود، گیتِ جاافتاده undefined و فیلتر خاموش می‌شود.
    const saved = { jet: { minBuyerPower: 2 }, clock: { minDeltaPct: 1.5 } };
    const merged = Object.fromEntries(
      Object.keys(DEFAULT_TAPE_FILTER_CONFIG).map((k) => [
        k, { ...(DEFAULT_TAPE_FILTER_CONFIG as Record<string, object>)[k],
             ...((saved as Record<string, object>)[k] ?? {}) },
      ]),
    ) as unknown as typeof DEFAULT_TAPE_FILTER_CONFIG;
    expect(merged.jet.minVolRatio).toBe(3.0);          // از پیش‌فرضِ جزوه
    expect(merged.jet.minBuyerPower).toBe(2);          // از کاربر
    expect(merged.clock.minTradeCount).toBe(30);
    expect(Object.values(merged.jet).every((v) => v !== undefined)).toBe(true);
  });
});

describe('مدال تنظیمات شخصی‌سازی فیلترها (TapeFilterSettingsModal)', () => {
  beforeEach(() => {
    useTapeStore.getState().resetTapeFilterConfig();
  });

  it('اعمال پریست استراتژی آماده از مدال', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    expect(screen.getByText('⚙️ تنظیمات فیلترها')).toBeInTheDocument();
    fireEvent.click(screen.getByText('نوسان‌گیری سریع و ساعت قوی'));
    const current = useTapeStore.getState().tapeFilterConfig;
    expect(current.jet.lookbackDays).toBe(5);
    // پریست‌ها هم مثل بقیهٔ کانفیگ باید همهٔ گیت‌ها را داشته باشند
    expect(current.clock.minVolRatio).toBeGreaterThan(0);
  });

  it('تغییر مستقیم پارامتر ساعت در تب ساعت', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: /الگوی ساعت/ }));
    const goldenBox = screen.getByRole('checkbox', { name: /فقط ساعت طلایی/ });
    fireEvent.click(goldenBox);
    expect(useTapeStore.getState().tapeFilterConfig.clock.requireGoldenHour).toBe(true);
  });

  it('تغییر تایم‌فریم شکست سقف جت به نقاطِ پلکانِ جزوه', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: /فیلتر جت/ }));
    expect(screen.getByText('تایم‌فریم شکست سقف قیمتی (Lookback High)')).toBeInTheDocument();
    expect(screen.getByText('۲ روزه')).toBeInTheDocument();
    fireEvent.click(screen.getByText('۲۹ روزه'));
    expect(useTapeStore.getState().tapeFilterConfig.jet.lookbackDays).toBe(29);
    fireEvent.click(screen.getByText('۵۹ روزه'));
    expect(useTapeStore.getState().tapeFilterConfig.jet.lookbackDays).toBe(59);
  });

  it('فیلدِ عددیِ خالی آستانه را صفر نمی‌کند (صفر = گیتِ خاموش)', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: /الگوی ساعت/ }));
    const trades = screen.getByRole('textbox', { name: /حداقل تعداد معاملات/ });
    const before = useTapeStore.getState().tapeFilterConfig.clock.minTradeCount;
    fireEvent.change(trades, { target: { value: '' } });
    expect(useTapeStore.getState().tapeFilterConfig.clock.minTradeCount).toBe(before);
  });

  it('ارقامِ فارسی در فیلدِ عددی خوانده می‌شوند', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: /الگوی ساعت/ }));
    const trades = screen.getByRole('textbox', { name: /حداقل تعداد معاملات/ });
    fireEvent.change(trades, { target: { value: '۷۵' } });
    expect(useTapeStore.getState().tapeFilterConfig.clock.minTradeCount).toBe(75);
  });

  // ── رأیِ ۱۸ (۱۴۰۵-۰۷-۰۴): فیلترِ تابلو عینِ فایل است، پس ``tno > 100`` ─────
  it('جتِ تابلو تعدادِ معاملات را شرط می‌کند، چون خودِ فایل می‌نویسد tno>100', () => {
    expect(DEFAULT_TAPE_FILTER_CONFIG.jet.minTradeCount).toBe(100);
    for (const preset of Object.values(TAPE_PRESETS)) {
      expect(preset.config.jet.minTradeCount).toBeGreaterThan(0);
    }
    // فایل دو قید دارد: tno > 1 و tno > 100. هر دو باید رد کنند.
    expect(matchJetFilter(passingRow({ z_tot_tran: 5 }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
    expect(matchJetFilter(passingRow({ z_tot_tran: 100 }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
    expect(matchJetFilter(passingRow({ z_tot_tran: 101 }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(true);
    // آستانه‌ای که کاربر پایین می‌آورد قیدِ «> ۱» را نمی‌شکند.
    expect(matchJetFilter(passingRow({ z_tot_tran: 1 }),
                          { ...DEFAULT_TAPE_FILTER_CONFIG.jet, minTradeCount: 0 })).toBe(false);
  });

  it('جت با تعدادِ معاملاتِ ندارد (null) رد می‌شود، نه بی‌صدا قبول', () => {
    expect(matchJetFilter(passingRow({ z_tot_tran: null }), DEFAULT_TAPE_FILTER_CONFIG.jet)).toBe(false);
  });

  // ── ریشهٔ TAPE-1: کلیدِ نیامده در literal یعنی undefined، یعنی گیتِ خاموش ─
  it('هیچ پرستیژی گیتِ فیلتری را با جاانداختنِ فیلد بی‌صدا خاموش نمی‌کند', () => {
    const defaults = DEFAULT_TAPE_FILTER_CONFIG as unknown as
      Record<string, Record<string, unknown>>;
    for (const [name, preset] of Object.entries(TAPE_PRESETS)) {
      const cfg = preset.config as unknown as Record<string, Record<string, unknown>>;
      for (const block of Object.keys(defaults)) {
        const missing = Object.keys(defaults[block])
          .filter((field) => cfg[block]?.[field] === undefined);
        expect(missing, name + '.' + block + ' فیلدِ از‌دست‌رفته دارد: '
               + missing.join(',')).toEqual([]);
      }
    }
  });
});

describe('دستگیره‌های ۲۲۶ — مبنایِ داوری', () => {
  // دو دستگیره، هر کدام یک تابع: (الف) درِ volumeGate، (ب) درِ کمینۀِ ۲۹-نشست.
  const basisToday = { ...DEFAULT_TAPE_FILTER_CONFIG.basis, includeTodayInVolumeBase: true };
  const noHistGate = { ...DEFAULT_TAPE_FILTER_CONFIG.basis, requireLowBaseHistory: false };

  it('پیش‌فرض‌ها = رفتارِ فعلی: هیچ‌کدام از پنج فیلتر با کانفیگِ تازه عوض نمی‌شود', () => {
    const row = passingRow();
    for (const key of ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh']) {
      expect(evaluateDynamicQuickFilter(row, key, DEFAULT_TAPE_FILTER_CONFIG))
        .toBe(evaluateDynamicQuickFilter(row, key, {
          ...DEFAULT_TAPE_FILTER_CONFIG,
          basis: { includeTodayInVolumeBase: false, requireLowBaseHistory: true },
        }));
    }
    expect(DEFAULT_TAPE_FILTER_CONFIG.basis).toEqual({
      includeTodayInVolumeBase: false, requireLowBaseHistory: true,
    });
  });

  it('(الف) امروز داخلِ مبناء: نسبت از ۴ به ۳۱×۴÷۳۴ (≈۳.۶۴۷) می‌آید و آستانۀ مرزی می‌شکند', () => {
    const row = passingRow();  // tvol=۴۰۰۰۰۰۰، Σ=۳۰۰۰۰۰۰۰ → vrf=۴
    const cfg = {
      ...DEFAULT_TAPE_FILTER_CONFIG,
      suspiciousVolume: { ...DEFAULT_TAPE_FILTER_CONFIG.suspiciousVolume, minRatio: 3.7 },
    };
    expect(evaluateDynamicQuickFilter(row, 'f_susp', cfg)).toBe(true);        // ۴ > ۳.۷
    expect(evaluateDynamicQuickFilter(row, 'f_susp', { ...cfg, basis: basisToday })).toBe(false);
  });

  it('(الف) دربِ سی‌نشستِ کامل جا نمی‌زند: بی‌مبناءِ کامل همچنان رد است', () => {
    const thin = passingRow({ vol_ratio_file: null, prior30_vol: 5_000_000, hist_sessions: 12 });
    const cfg = { ...DEFAULT_TAPE_FILTER_CONFIG, basis: basisToday };
    expect(evaluateDynamicQuickFilter(thin, 'f_clock', cfg)).toBe(false);
  });

  it('(الف) جت بی‌تأثیر می‌ماند — قیدِ حجمش همان مبناءِ خالصِ فایل است', () => {
    const row = passingRow();
    expect(evaluateDynamicQuickFilter(row, 'f_jet', DEFAULT_TAPE_FILTER_CONFIG)).toBe(true);
    expect(evaluateDynamicQuickFilter(row, 'f_jet',
      { ...DEFAULT_TAPE_FILTER_CONFIG, basis: basisToday })).toBe(true);
  });

  it('(ب) دربِ ۲۹-نشست خاموش: نمادِ کم‌سابقه با کمینۀِ موجود سنجیده می‌شود', () => {
    const young = passingRow({ hist_sessions: 28, min_low_29: 0, min30_low: 995 });
    expect(matchNoqtehFilter(young, DEFAULT_TAPE_FILTER_CONFIG.noqteh)).toBe(false);
    expect(matchNoqtehFilter(young, DEFAULT_TAPE_FILTER_CONFIG.noqteh, noHistGate)).toBe(true);
  });

  it('(ب) با دربِ خاموش هم «هیچ کفی نبودن» یعنی رد، نه قبولِ بی‌صدا', () => {
    const noLow = passingRow({ hist_sessions: 28, min_low_29: 0, min30_low: null });
    expect(matchNoqtehFilter(noLow, DEFAULT_TAPE_FILTER_CONFIG.noqteh, noHistGate)).toBe(false);
  });

  it('تب «مبنای داوری» در مودال هر دو دستگیره را در استور می‌نویسد', () => {
    render(<TapeFilterSettingsModal open={true} onClose={() => {}} />);
    fireEvent.click(screen.getByRole('tab', { name: /مبنای داوری/ }));
    const todayBox = screen.getByRole('checkbox', { name: /امروز داخلِ مبنایِ میانگین/ });
    const histBox = screen.getByRole('checkbox', { name: /دروازۀ ۲۹-نشستِ تاریخچه/ });
    expect(todayBox).not.toBeChecked();
    expect(histBox).toBeChecked();
    fireEvent.click(todayBox);
    expect(useTapeStore.getState().tapeFilterConfig.basis.includeTodayInVolumeBase).toBe(true);
    fireEvent.click(histBox);
    expect(useTapeStore.getState().tapeFilterConfig.basis.requireLowBaseHistory).toBe(false);
  });
});
