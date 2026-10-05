// __tests__/technical-corp-events.spec.ts — رویدادِ شرکتیِ مبدأ: نمایش، نه محاسبه
// دورِ مصرف‌کننده (docs/fts-notes/TSETMC-P0-CONSUMER-INTEGRATION.md): canonicalِ
// TSETMC به چارت وصل شد. سه چیز باید ثابت شود:
//   ۱) نگاشتِ نوع→حرف/رنگ/متن یک‌جا می‌شود و هر دو موتور همان را می‌خوانند؛
//   ۲) روزی که درِ سریِ کندل نیست نشانگر نمی‌گیرد (بی‌مکانِ حدسی)؛
//   ۳) هیچ‌کدام از این ردیف‌ها به زنجیرۀ تعدیل راه نمی‌یابد.
import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import {
  CORP_EVENT_GROUP,
  corpEventMarkers,
  corpEventText,
  corpEventType,
} from '@features/technical/lib/corpEvents';
import type { RawCorporateEvent } from '@features/technical/api/useCandleFeed';

const t = (s: string) => Date.parse(`${s}T00:00:00Z`);
const D1 = '2026-06-10';
const D2 = '2026-07-01';
const D3 = '2026-08-20';

const EVENTS: RawCorporateEvent[] = [
  { date: D1, type: 'priceAdjust', from: 22420, to: 17930, source: 'tsetmc_price_adjust_by_flow' },
  { date: D2, type: 'shareChange', from: 15800000000, to: 25800000000, source: 'tsetmc_share_change_by_flow' },
  // روزی که درِ این سریِ کندل نیست
  { date: D3, type: 'priceAdjust', from: 100, to: 90, source: 'tsetmc_price_adjust_by_flow' },
  // بی‌نوعِ شناخته‌شده: ساخته نمی‌شود، حدس نمی‌خورد
  { date: D1, type: 'mystery', from: 1, to: 2, source: 'x' },
];

const input = {
  events: EVENTS,
  tsForDate: (d: string) => (d === D3 ? null : t(d)),
  valueForDate: (d: string) => (d === D3 ? null : 1000 + Date.parse(`${d}T00:00:00Z`) / 86400000),
};

describe('نگاشتِ رویدادِ شرکتی → نشانگر', () => {
  it('دو نوع، دو نشانگر با دو حرفِ جدا و یک گروهِ مشترک', () => {
    const m = corpEventMarkers(input);
    expect(m).toHaveLength(2);
    expect(new Set(m.map((x) => x.letter)).size).toBe(2);
    expect(new Set(m.map((x) => x.color)).size).toBe(2);
    expect(m.every((x) => x.group === CORP_EVENT_GROUP && x.kind === 'marker')).toBe(true);
    expect(m.map((x) => x.id)).toEqual([`corp-priceAdjust-${D1}`, `corp-shareChange-${D2}`]);
  });

  it('روزی که درِ سری نیست نشانگر نمی‌گیرد (بی‌مکانِ حدسی)', () => {
    expect(corpEventMarkers(input).some((x) => x.id.includes(D3))).toBe(false);
    // و اگر فقط عمودیِ جایِ کندل را ندانیم هم نمی‌سازیم
    expect(corpEventMarkers({ ...input, valueForDate: () => null })).toEqual([]);
  });

  it('متنِ تولتیپ هر دو مقدارِ مبدأ را می‌گوید، نه چیزی جز آن‌ها', () => {
    const adj = corpEventText(EVENTS[0]);
    expect(adj).toContain('تعدیلِ پایانی');
    expect(adj).toContain('۲۲٬۴۲۰');
    expect(adj).toContain('۱۷٬۹۳۰');
    const sh = corpEventText(EVENTS[1]);
    expect(sh).toContain('تغییرِ سهام');
    expect(sh).toContain('۱۵.۸ میلیارد');
    expect(sh).toContain('۲۵.۸ میلیارد');
    expect(corpEventType(EVENTS[3])).toBeNull();
    expect(corpEventText(EVENTS[3])).toBe('');
  });

  it('مقدارِ نشانگر همان کفِ کندل است — بی‌هیچ بازمحاسبه‌ای', () => {
    const [first] = corpEventMarkers(input);
    expect(first.points[0].timestamp).toBe(t(D1));
    expect(first.points[0].value).toBe(input.valueForDate(D1));
  });

  it('رنگِ دو نوع با نشانگرِ زنجیرۀ تعدیل و پالتِ خودِ چارت قاطی نمی‌شود', () => {
    const colors = corpEventMarkers(input).map((m) => m.color);
    const COLLIDING = [
      '#f59e0b', // نشانگرِ زنجیرۀ تعدیل (A) درِ KLineChartWrapper
      '#22d3ee', '#fbbf24', // fib/jet درِ FTS_OVERLAY_COLORS
      '#10b981', '#ff3860', // pullback / chohRed
    ].map((c) => c.toLowerCase());
    for (const c of colors) {
      expect(COLLIDING).not.toContain(c.toLowerCase());
    }
    expect(new Set(colors).size).toBe(2);
  });
});

describe('سیمِ دو موتور به یک نگاشت', () => {
  const src = (p: string) => readFileSync(join(__dirname, '..', p), 'utf-8');
  const wrapper = src('features/technical/nahayatnegar/components/KLineChartWrapper.tsx');
  const ffc = src('features/technical/components/FtsEngineChart.tsx');
  const page = src('features/technical/routes/TechnicalPage.tsx');
  const feed = src('features/technical/api/useCandleFeed.ts');

  it('هر دو موتور lib/corpEvents را می‌خوانند (نگاشتِ دوم ساخته نشده)', () => {
    expect(wrapper).toContain("from '../../lib/corpEvents'");
    expect(ffc).toContain("from '../lib/corpEvents'");
    expect(wrapper.match(/corpEventMarkers/g)?.length).toBeGreaterThan(0);
    expect(ffc.match(/corpEventMarkers/g)?.length).toBeGreaterThan(0);
  });

  it('نشانگرِ مبدأ بی‌رویدادِ زنجیره هم رسم می‌شود (returnِ زودهنگامِ پیشین رفت)', () => {
    expect(wrapper).not.toContain('corporateActions.length === 0 || displayCandles.length === 0');
  });

  it('خوراکِ چارت همان پاسخِ `/api/chart` است، نه اندپوینتِ دوم', () => {
    expect(feed).toContain('corporateEvents: z.array(RawCorporateEvent).nullish()');
    expect(feed).toContain('corporateEvents: chart.corporateEvents ?? []');
    expect(wrapper).toContain('json?.corporateEvents');
    expect(ffc).not.toMatch(/fetch\(|http\(/);
  });

  it('سریِ تعدیل‌شده از همان `adjustEvents` می‌آید؛ رویدادِ مبدأ درِ آن نمی‌رود', () => {
    expect(page).toContain("applyAdjustmentToCandles(feed.candles, mapBackendAdjustEvents(adjustEvents ?? []), 'combined')");
    expect(page).not.toMatch(/applyAdjustmentToCandles\([^)]*corpEvents/);
    expect(wrapper).not.toMatch(/applyAdjustmentToCandles\([^)]*corpEvents/);
  });
});
