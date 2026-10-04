// __tests__/tape-badge-chip-parity.spec.ts -- چیپِ فیلتر == بجی که درِ ردیف می‌بینی
//
// سنجشِ زندهٔ ۱۴۰۵-۰۷-۰۷ (نسخۀ نصب‌شدۀ ۱٫۰٫۵۰، پنجرۀ ۱۸:۵۶): پنج فیلتر عینِ
// خودِ سایت بودند (ساعت ۲۵=۲۵، حجم مشکوک ۱۰۰ از ۱۰۰، جت ۸=۸، کف‌روبی ۳=۳،
// نقطه‌زنی ۱۲=۱۲) ولی ستونِ «الگو» درِ همان نما ۸ بجِ «ساعت» نشان می‌داد در
// برابرِ چیپِ (۶) — چون بج «فرمول یا پرچمِ بک‌اند یا ساعتِ قوی/طلایی» بود.
// این گارد همان شکاف را می‌بندد: هر پنج بجِ فیلتر باید دقیقاً آن‌وقت روشن
// شوند که خودِ داوریِ فیلتر درست است، و الگوهایِ محلیِ جزوه («ساعت قوی»،
// «طلایی»، «صف+/−») بجِ جدا و بی‌شمارش می‌گیرند.
import { describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { JET_LADDER } from '@features/market/lib/tapeMath';
import {
  DEFAULT_TAPE_FILTER_CONFIG,
  tapeFilterVerdict,
} from '@features/market/lib/tapeAlgorithms';
import { patternBadges, BADGE_FILTER_KEY } from '@features/market/lib/tapeBadges';

const FILTERS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh'];

/** ردیفی که هر پنج شرطِ فایل را با هم می‌گذراند (همان اعدادِ جزوه). */
const allPass = (over: Partial<MarketRow> = {}): MarketRow =>
  ({
    symbol: 'آزمون',
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

const filterBadges = (r: MarketRow) =>
  patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG)
    .filter((b) => b.filter)
    .map((b) => BADGE_FILTER_KEY[b.key])
    .sort();

const verdicts = (r: MarketRow) =>
  FILTERS.filter((f) => tapeFilterVerdict(r, f, DEFAULT_TAPE_FILTER_CONFIG)).sort();

describe('بج‌های پنج فیلتر با داوریِ خودشان یکی است', () => {
  // کف‌روبی سمتِ فروشِ تابلو است (آخرین رویِ آستانۀِ مجازِ پایین، زیرِ دو درصد)
  // و با سه‌تایِ سمتِ خریدِ همان ردیف نمی‌تواند باشد؛ پس دو ردیفِ جدا.
  it('ردیفِ سمتِ خرید: چهار بج، نه کم و نه زیاد', () => {
    const r = allPass();
    expect(verdicts(r)).toEqual(['f_clock', 'f_jet', 'f_noqteh', 'f_susp']);
    expect(filterBadges(r)).toEqual(verdicts(r));
  });

  it('ردیفِ کف‌روبی: بجِ «کف‌روب» فقط با همان داوری می‌آید', () => {
    const r = allPass({
      p_closing: 900, p_last: 900, tmin: 900, percent_last: -5, percent_change: -5,
      price_yesterday: 947,
    });
    // کف‌شکنی (پایانی زیرِ کفِ پنجره) درِ نقطه‌زنی قبول است — رأیِ عینِ فایل،
    // ویرایشِ ۱٫۰٫۴۸ — و حجمش هم سه‌برابرِ مبناءست؛ آن چه می‌سازد این است که
    // هر سه بج با همان سه داوری بیایند، نه کمتر و نه بیشتر.
    expect(verdicts(r)).toEqual(['f_noqteh', 'f_roobi', 'f_susp']);
    expect(filterBadges(r)).toEqual(verdicts(r));
  });

  it('ساعتِ قویِ تنها (دلتای ۱٫۵٪ از فایل کمتر) بجِ «ساعت» نمی‌گیرد', () => {
    // close < yesterday < last با دلتای ۱٫۵٪: الگویِ جزوه هست، فیلترِ سایت نیست
    const r = allPass({ p_closing: 1000, p_last: 1015, price_yesterday: 1008 });
    const badges = patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG);
    expect(badges.some((b) => b.key === 'strong-hour')).toBe(true);
    expect(badges.some((b) => b.key === 'clock')).toBe(false);
    expect(filterBadges(r)).toEqual(verdicts(r));
  });

  it('ساعتِ طلاییِ تنها هم شمارۀ چیپ را بالا نمی‌برد', () => {
    const r = allPass({ p_closing: 1000, p_last: 1004, price_yesterday: 1002 });
    const badges = patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG);
    expect(tapeFilterVerdict(r, 'f_clock', DEFAULT_TAPE_FILTER_CONFIG)).toBe(false);
    expect(badges.some((b) => b.key === 'golden-hour')).toBe(true);
    expect(badges.some((b) => b.key === 'clock')).toBe(false);
  });

  it('وقتی هر دو هستند فقط یک بجِ «ساعت» می‌آید — بی‌شمارشِ دوباره', () => {
    const r = allPass({ p_closing: 1000, p_last: 1030, price_yesterday: 1008 });
    expect(tapeFilterVerdict(r, 'f_clock', DEFAULT_TAPE_FILTER_CONFIG)).toBe(true);
    expect(patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG).filter((b) => b.key === 'clock')).toHaveLength(1);
    expect(patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG).some((b) => b.key === 'strong-hour')).toBe(false);
  });

  it('پنلِ بی‌ستونِ تاریخچه: پرچمِ بک‌اند هم چیپ را می‌گیرد هم بج را (#1.0.44)', () => {
    const legacy = {
      symbol: 'کهنه', p_closing: 1000, p_last: 1030, f_susp: true,
    } as unknown as MarketRow;
    expect(tapeFilterVerdict(legacy, 'f_susp', DEFAULT_TAPE_FILTER_CONFIG)).toBe(true);
    expect(filterBadges(legacy)).toEqual(['f_susp']);
    // همان ردیف با فیلتری که پرچمش نبوده نباید بجِ بی‌جای دیگری بگیرد
    expect(tapeFilterVerdict(legacy, 'f_jet', DEFAULT_TAPE_FILTER_CONFIG)).toBe(false);
  });

  it('هیچ بجِ بی‌پشتوانه‌ای رویِ ردیفِ مردود نمی‌نشیند', () => {
    const dead = { symbol: 'مردود', p_closing: 1000, p_last: 900, percent_change: -9 } as unknown as MarketRow;
    expect(verdicts(dead)).toEqual([]);
    expect(filterBadges(dead)).toEqual([]);
    // ولی الگوهایِ محلی (صف فروش) همان‌جا می‌مانند و بی‌شمارش‌اند
    const badges = patternBadges(dead, DEFAULT_TAPE_FILTER_CONFIG);
    expect(badges.map((b) => b.key)).toContain('ld');
    expect(badges.every((b) => !b.filter || verdicts(dead).includes(BADGE_FILTER_KEY[b.key]))).toBe(true);
  });
});

// اندازه‌گیریِ زنده: `TAPE_PAYLOAD=_audit/live_rows.json npx vitest run src/__tests__/tape-badge-chip-parity.spec.ts`
// با بدنهٔ خامِ /api/market. بی‌این لایه، ادعایِ «با سایت یکی است» دستی و
// تکرارناپذیر می‌ماند (لایۀ سایت‌محورش: tools/tse_live_filter_parity.py).
const PAYLOAD = process.env.TAPE_PAYLOAD ?? '';

describe.skipIf(!PAYLOAD)('برابریِ سه‌راه رویِ ردیف‌هایِ زندهٔ تابلو', () => {
  it('پرچمِ بک‌اند = فرمولِ فرانت = بجِ ردیف، برایِ هر پنج فیلتر', async () => {
    const { readFileSync } = await import('node:fs');
    const raw = JSON.parse(readFileSync(PAYLOAD, 'utf8'));
    const rows: MarketRow[] = Array.isArray(raw) ? raw : raw.data;
    const shown = rows.filter((r) => r.is_live !== false && !/[0-9۰-۹]$/.test(String(r.symbol ?? '')));
    const report: Record<string, unknown> = {};
    for (const f of FILTERS) {
      const back = rows.filter((r) => Boolean((r as unknown as Record<string, unknown>)[f])).length;
      const dyn = rows.filter((r) => tapeFilterVerdict(r, f, DEFAULT_TAPE_FILTER_CONFIG)).length;
      const badges = rows.filter((r) =>
        patternBadges(r, DEFAULT_TAPE_FILTER_CONFIG).some((b) => b.filter && BADGE_FILTER_KEY[b.key] === f)).length;
      report[f] = { all: [back, dyn, badges], shown: shown.filter((r) =>
        tapeFilterVerdict(r, f, DEFAULT_TAPE_FILTER_CONFIG)).length };
      expect(badges, `${f}: بج با فرمول نمی‌خواند`).toBe(dyn);
    }
    console.log(JSON.stringify(report));
  });
});
