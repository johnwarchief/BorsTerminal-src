// __tests__/tape-unevaluated-display.spec.ts -- «سنجیده نشد» نباید با «رد» یکی شود
//
// سنجشِ زندهٔ ۱۴۰۵-۰۷-۱۹ رویِ همان /api/market: پرچمِ هر هفت فیلتر برایِ همهٔ
// ۵٬۹۴۱ ردیف boolean است (هیچ nullی نمی‌آید)، ولی `vol_ratio_file` در ۴٬۱۰۹ ردیف
// و `hist_sessions`/`min_low_29`/`prior30_vol` در ۲٬۹۸۱ ردیف اصلاً نمی‌آید. یعنی
// نیمیِ «رد»ها در واقع «اندازه‌گیری نشد» بودند. این گارد دو چیز را قفل می‌کند:
//   ۱) علتِ نبودِ ورودی از «زیرِ آستانه بودن» جدا شود،
//   ۲) هیچ حکمی جابه‌جا نشود — ردیفِ سنجیده‌نشده هرگز واجدِ شمارشِ چیپ نیست و
//      هیچ «قبول»ی به «سنجیده نشد» تبدیل نمی‌شود.
import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { JET_LADDER } from '@features/market/lib/tapeMath';
import {
  DEFAULT_TAPE_FILTER_CONFIG as CFG,
  tapeFilterState,
  tapeFilterUnmeasured,
  tapeFilterVerdict,
} from '@features/market/lib/tapeAlgorithms';

/** ردیفی که همه‌چیز دارد و هر پنج شرطِ فایل را می‌گذراند. */
const full = (over: Partial<MarketRow> = {}): MarketRow =>
  ({
    symbol: 'آزمون',
    is_live: true,
    p_closing: 1000,
    p_last: 1025,
    price_yesterday: 1000,
    percent_change: 2.5,
    percent_last: 2.5,
    tvol: 4_000_000,
    q_tot_tran: 4_000_000,
    vol_ratio: 4,
    vol_ratio_file: 4,
    prior30_vol: 30_000_000,
    hist_sessions: 60,
    min_low_29: 995,
    min30_low: 995,
    buy_q1_cnt: 6,
    buy_q1_vol: 250_000,
    tmin: 900,
    p_min: 1025,
    vol_dod: 2,
    prev_day_vol: 2_000_000,
    z_tot_tran: 120,
    buyer_power: 2,
    buyer_power_raw: 2,
    buy_i_vol: 2_000_000,
    buy_count_i: 100,
    sell_i_vol: 1_000_000,
    sell_count_i: 100,
    ...Object.fromEntries(JET_LADDER.map((k) => [`h${k}_max`, 900])),
    ...over,
  }) as unknown as MarketRow;

const FILE_FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart'];

describe('علتِ «نبودِ ورودی» از «زیرِ آستانه» جدا می‌ماند', () => {
  it('مبنایِ حجمِ سی‌نشست نیامد ⇒ سنجیده نشد، نه رد', () => {
    const r = full({ vol_ratio_file: null });
    expect(tapeFilterUnmeasured(r, 'f_clock', CFG)).toBe(true);
    expect(tapeFilterState(r, 'f_clock', CFG)).toBe('unevaluated');
  });

  it('مبناء آمد ولی حجم زیرِ آستانه است ⇒ رد (سنجیده شد)', () => {
    const r = full({ vol_ratio_file: 1.5 });
    expect(tapeFilterUnmeasured(r, 'f_susp', CFG)).toBe(false);
    expect(tapeFilterState(r, 'f_susp', CFG)).toBe('fail');
  });

  it('تعدادِ معاملات نیامد ⇒ سنجیده نشد؛ صفرِ واقعی رد است', () => {
    expect(tapeFilterState(full({ z_tot_tran: null }), 'f_clock', CFG)).toBe('unevaluated');
    expect(tapeFilterState(full({ z_tot_tran: 0 }), 'f_clock', CFG)).toBe('fail');
  });

  it('پلکانِ جت کامل نیست ⇒ سنجیده نشد (نه «مقاومتش زیرِ آخرین بود»)', () => {
    const r = full({ hist_sessions: 10, prior30_vol: null, min_low_29: null, vol_ratio_file: 4 });
    expect(tapeFilterState(r, 'f_jet', CFG)).toBe('unevaluated');
  });

  it('کفِ بیست‌ونُه‌نشستیِ نقطه‌زنی نیامد ⇒ سنجیده نشد', () => {
    const r = full({ min_low_29: null });
    expect(tapeFilterState(r, 'f_noqteh', CFG)).toBe('unevaluated');
  });
});

describe('هیچ حکمی جابه‌جا نمی‌شود', () => {
  it('ردیفِ سنجیده‌نشده هرگز واجدِ شمارشِ چیپ نیست', () => {
    for (const f of FILE_FILTERS) {
      for (const r of [full({ vol_ratio_file: null }), full({ z_tot_tran: null }), full({ percent_last: null })]) {
        if (tapeFilterState(r, f, CFG) === 'unevaluated') {
          expect(tapeFilterVerdict(r, f, CFG), `${f} نباید با نسنجیده واجد شود`).toBe(false);
        }
      }
    }
  });

  it('ردیفِ واجد هیچ‌وقت «سنجیده نشد» نمی‌شود', () => {
    // چهار فیلترِ سمتِ خرید با یک ردیف سنجیده می‌شوند؛ کف‌روبی ردیفِ خودش را
    // می‌خواهد (آخرین رویِ آستانۀ مجازِ پایین) و پولِ هوشمند پرچمِ بک‌اند.
    for (const f of ['f_clock', 'f_susp', 'f_jet', 'f_noqteh']) {
      const r = full();
      expect(tapeFilterVerdict(r, f, CFG), `پیش‌فرض: ${f} باید بگذرد`).toBe(true);
      expect(tapeFilterState(r, f, CFG)).toBe('pass');
    }
    const roobi = full({ p_closing: 900, p_last: 900, tmin: 900, percent_last: -5, percent_change: -5 });
    expect(tapeFilterState(roobi, 'f_roobi', CFG)).toBe('pass');
    expect(tapeFilterState(full({ f_smart: true }), 'f_smart', CFG)).toBe('pass');
  });

  it('پولِ هوشمند با پرچمِ true و مبنایِ نیامده باز هم pass است', () => {
    // داوریِ این چیپ پرچمِ بک‌اند است؛ «سنجیده نشد» حقِ پاکردنِ یک قبول را ندارد.
    const r = full({ vol_ratio_file: null, f_smart: true });
    expect(tapeFilterUnmeasured(r, 'f_smart', CFG)).toBe(false);
    expect(tapeFilterState(r, 'f_smart', CFG)).toBe('pass');
  });

  it('کد به کد بی‌[is6] «سنجیده نشد» می‌گیرد؛ با مبناءِ سایت همان «رد» است', () => {
    // خطِ سومِ فایل `(tvol) > 1.5*[is6]` است و سایت کلید ۶ را برایِ بیشترِ
    // نمادها منتشر نمی‌کند ⇒ آنجا `undefined` و ردیف بیرون می‌افتد. پس نبودِ
    // عدد «رد» نیست؛ و آمدنش هم حقِ داوری می‌دهد، نه صفرِ ساختگی.
    const noBase = full({ f_legal: false, is5: null, is6: null });
    expect(tapeFilterUnmeasured(noBase, 'f_legal', CFG)).toBe(true);
    expect(tapeFilterState(noBase, 'f_legal', CFG)).toBe('unevaluated');
    const withBase = full({ f_legal: false, is5: 1_000_000, is6: 900_000 });
    expect(tapeFilterUnmeasured(withBase, 'f_legal', CFG)).toBe(false);
    expect(tapeFilterState(withBase, 'f_legal', CFG)).toBe('fail');
    // [is5] دروازه نیست: خطِ دوم اجرا می‌شود ولی ارزشش درِ `eval` دور ریخته
    // می‌شود و مقایسه با `undefined` استثنای هم نمی‌دهد (۱۳۱ موجودِ InstValue
    // کلید ۶ دارند و کلید ۵ نه — سایت ایشان را می‌سنجد، پس رابط هم باید بزند).
    const only6 = full({ f_legal: false, is5: null, is6: 900_000 });
    expect(tapeFilterUnmeasured(only6, 'f_legal', CFG)).toBe(false);
    expect(tapeFilterState(only6, 'f_legal', CFG)).toBe('fail');
    // پول هوشمند هم از همان مبناء می‌گذرد، نه از حجمِ تقریبی
    expect(tapeFilterState(full({ f_smart: false, is5: null, is6: null }), 'f_smart', CFG))
      .toBe('unevaluated');
    expect(tapeFilterState(full({ f_smart: true, is5: null, is6: null }), 'f_smart', CFG))
      .toBe('pass');
    expect(tapeFilterState(full({ f_smart: false, is5: null, is6: 900_000 }), 'f_smart', CFG))
      .toBe('fail');
  });
});

describe('پنل‌هایِ قدیمی و ردیف‌هایِ خاموش دست‌نخورده‌اند', () => {
  it('بی‌ستون‌هایِ تاریخچه: داوری همان پرچمِ بک‌اند است', () => {
    const bare = { symbol: 'قدیمی', f_clock: true };
    expect(tapeFilterState(bare as unknown as MarketRow, 'f_clock', CFG)).toBe('pass');
    expect(tapeFilterState({ symbol: 'قدیمی', f_clock: false } as unknown as MarketRow, 'f_clock', CFG)).toBe('fail');
    expect(tapeFilterState({ symbol: 'قدیمی' } as unknown as MarketRow, 'f_clock', CFG)).toBe('unevaluated');
  });

  it('ردیفِ خاموش (بیرونِ تابلویِ امروز) «رد» نمی‌شود — وضعیتش جدا خوانده می‌شود', () => {
    // رأیِ مالک ۱۴۰۵-۰۷-۲۱، بند ۱: سایت چنین ردیفی را اصلاً نمی‌سنجد، پس
    // «✗ رد» برچسبِ ساختگی است. نمایش «سنجیده نشد» است و داوریِ فیلترکردن
    // عوض نمی‌شود: ردیفِ خاموش همچنان قبول نیست.
    const r = full({ is_live: false, vol_ratio_file: null });
    expect(tapeFilterState(r, 'f_clock', CFG)).toBe('unevaluated');
    expect(tapeFilterVerdict(r, 'f_clock', CFG)).toBe(false);
    // جریانِ پولِ نخبگان پنلِ خودی است و از این قید آزاد ماند.
    expect(tapeFilterState(full({ is_live: false }), 'f_smart_flow', CFG)).not.toBe('unevaluated');
  });
});
