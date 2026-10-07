// گاردِ رونشانیِ زندۀ تابلو روی گوشی.
//
// تابلوی اندروید از دو سرچشمه می‌آید: ردیف‌های پخت‌شدۀ اسنپ‌شات + رونشانیِ زنده
// از `GetMarketWatch`. هر چیزی که همین‌جا از قلم بیفتد، رویِ گوشی یا کهنه
// می‌ماند یا جعلی «زنده» خوانده می‌شود — دقیقاً همان چیزهایی که مالک درِ
// «تابلوخوانیِ اندروید خیلی کمتر از دسکتاپ است» دید.
//
// قالبِ ردیف‌ها از فیکسچرِ خودِ دسکتاپ (`dev/market_hot_state_v1077.py::_mw`)
// گرفته شده، نه از حدس.
import { describe, expect, it } from 'vitest';
import { mwRowFromJson, overlayBoard, type MwRow } from '@shared/api/local/live';

const RAW = {
  insCode: 'A1', lva: 'فولاد', lvc: 'شرکت', csv: 'S1',
  dEven: 20261007, hEven: 110500,
  pcl: 1320, pdv: 1335, py: 1290, pf: 1300,
  pmn: 1300, pmx: 1350, pMin: 1161, pMax: 1419,
  qtj: 5_000_000, qtc: 6_650_000_000, ztt: 480, eps: 96, pe: 13.7,
  blDs: [
    { qmd: 300_000, pmd: 1335, zmd: 3, qmo: 120_000, pmo: 1340, zmo: 2 },
    { qmd: 200_000, pmd: 1334, zmd: 1, qmo: 90_000, pmo: 1341, zmo: 1 },
  ],
};

const bakedRow = (over: Record<string, unknown> = {}): Record<string, unknown> => ({
  symbol: 'فولاد', ins_code: 'A1', is_live: true, d_even: 20261004,
  p_last: 1290, p_closing: 1290, price_yesterday: 1280, tmin: 1152, tmax: 1408,
  q_tot_tran: 1_000, buy_q_vol: 0, sell_q_vol: 0, ...over,
});

describe('mwRowFromJson — خواندنِ کلیدهایِ زندهٔ TSETMC', () => {
  it('آستانه‌های مجاز و شمارۀ نشست از همان JSONِ مارکت‌واچ می‌آیند', () => {
    const m = mwRowFromJson(RAW);
    expect(m.pmin).toBe(1161);
    expect(m.pmax).toBe(1419);
    expect(m.den).toBe(20261007);
  });

  it('جمعِ پنج‌خطیِ صف و خطِ اول ساخته می‌شود', () => {
    const m = mwRowFromJson(RAW);
    expect(m.q?.bq).toBe(500_000);
    expect(m.q?.sq).toBe(210_000);
    expect(m.q?.b1p).toBe(1335);
    expect(m.q?.s1v).toBe(120_000);
  });

  it('بی‌blDs صف «بی‌داده» است نه صفر', () => {
    expect(mwRowFromJson({ ...RAW, blDs: undefined }).q).toBeNull();
  });

  it('پنج خطِ عمق از همان blDs درمی‌آید (همتا: book_lines دسکتاپ)', () => {
    const m = mwRowFromJson(RAW);
    expect(m.levels).toEqual([
      { buy_px: 1335, buy_vol: 300_000, buy_cnt: 3, sell_px: 1340, sell_vol: 120_000, sell_cnt: 2 },
      { buy_px: 1334, buy_vol: 200_000, buy_cnt: 1, sell_px: 1341, sell_vol: 90_000, sell_cnt: 1 },
    ]);
  });

  it('سطری که هیچ‌یک از دو طرفش قیمت ندارد نوشته نمی‌شود', () => {
    const m = mwRowFromJson({ ...RAW, blDs: [{ qmd: 5, zmd: 1 }, RAW.blDs[0]] });
    expect(m.levels).toHaveLength(1);
    expect(m.hen).toBe(110500);
  });
});

describe('overlayBoard — رونشانیِ زنده روی ردیف‌های اسنپ‌شات', () => {
  const mw = new Map<string, MwRow>([['A1', mwRowFromJson(RAW)]]);

  it('tmin/tmax و d_evenِ ردیفِ زنده تازه می‌شوند', () => {
    const rows = [bakedRow()];
    expect(overlayBoard(rows, mw, null)).toBe(1);
    expect(rows[0].tmin).toBe(1161);
    expect(rows[0].tmax).toBe(1419);
    expect(rows[0].d_even).toBe(20261007);
  });

  it('«زنده» بودن از آخرین نشستِ دیده‌شده خوانده می‌شود، نه از روزِ پخت', () => {
    const live = bakedRow();
    const stale = bakedRow({ symbol: 'همراه', ins_code: 'Z9', d_even: 20260930, is_live: true });
    overlayBoard([live, stale], mw, null);
    expect(live.is_live).toBe(true);
    // ردیفی که درِ زنده نیست و d_even‌اش کهنه است، نباید «زنده» بماند
    expect(stale.is_live).toBe(false);
  });

  it('کنترلِ منفی: بی‌pMinِ زنده، آستانۀ پخت‌شده دست‌نخورده می‌ماند', () => {
    const partial = mwRowFromJson({ ...RAW, pMin: undefined, pMax: undefined });
    const rows = [bakedRow()];
    overlayBoard(rows, new Map([['A1', partial]]), null);
    expect(rows[0].tmin).toBe(1152);
    expect(rows[0].tmax).toBe(1408);
  });

  it('درصدِ پایانی و درصدِ آخرین از پایهٔ دیروزِ زنده جدا حساب می‌شوند', () => {
    const rows = [bakedRow()];
    overlayBoard(rows, mw, null);
    // (pcl − py)/py = (1320−1290)/1290 و (pdv − py)/py = (1335−1290)/1290
    expect(rows[0].percent_change).toBeCloseTo(2.33, 2);
    expect(rows[0].percent_last).toBeCloseTo(3.49, 2);
  });
});
