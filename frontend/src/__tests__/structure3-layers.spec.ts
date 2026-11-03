// تستِ نگاشتِ موتورِ سوم (lib/structure3Layers.ts) -- لایۀ مقایسه نباید رأی بسازد
// سه ادعایی که این فایل می‌سنجد: (۱) بی‌`status:success` هیچ لایه‌ای نیست، و
// «صفرِ ساختار» با «سنجیده نشد» یکی نمی‌شود؛ (۲) اعدادِ سرور عیناً به فضایِ رسم
// می‌آیند (یک ضریب، بی‌محاسبهٔ دوم) و `meta.pending` هرگز رسم نمی‌شود؛
// (۳) امضایِ موتورِ سوم (گروه + «م۳») درِ هر دو موتور یکی است تا خروجیِ این
// موتور با نقاطِ ساختاریِ موتورِ اول یکی خوانده نشود.
import { describe, expect, it } from 'vitest';
import {
  E3_GROUP,
  E3_MAX_DRAWN_POINTS,
  e3KlinechartsOverlay,
  e3MarkerLabel,
  structure3Layers,
} from '@features/technical/lib/structure3Layers';
import type { Structure3Data } from '@features/technical/api/useStructure3';

const DAY = 86_400_000;
const T0 = Date.UTC(2024, 0, 1);
const ts = (i: number) => T0 + i * DAY;
/** 'YYYY-MM-DD' از همان شاخکِ i که `ts(i)` می‌سازد */
const dateFor = (i: number) => new Date(ts(i)).toISOString().slice(0, 10);

const point = (
  i: number,
  kind: 'high' | 'low',
  price: number,
  label: 'HH' | 'HL' | 'LH' | 'LL' | null = null,
) => ({
  idx: i,
  time: dateFor(i),
  price,
  kind,
  confirm_idx: i + 3,
  confirm_time: dateFor(i + 3),
  threshold_pct: 3,
  atr_used: true,
  label,
});

const payload = (over: Partial<Structure3Data> = {}): Structure3Data => ({
  status: 'success',
  symbol: 'X',
  engine: 'structure3',
  official: false,
  voting: false,
  params: { atr_period: 14, atr_mult: 1, floor_pct: 3 },
  tf: 'D',
  basis: 'tsetmc-adjusted',
  bars: 10,
  ref_close: 100,
  points: [point(0, 'low', 100), point(4, 'high', 120, 'HH')],
  choch: [],
  meta: { bars: 10, confirmed_atr: 2, confirmed_floor_only: 0, atr_missing_bars: 0 },
  ...over,
});

const view = (e3: Structure3Data | null, cap?: number) =>
  structure3Layers({
    e3,
    startTs: ts(0),
    anchorTs: ts(9),
    toDisp: (rial) => rial,
    tsForDate: (d) => {
      const i = Math.round((Date.parse(`${d}T00:00:00Z`) - T0) / DAY);
      return i >= 0 && i <= 9 ? ts(i) : null;
    },
    maxPoints: cap,
  });

describe('نگاشتِ `/api/structure3` به اورلی‌هایِ چارت', () => {
  it('بی‌پاسخِ موفق هیچ لایه‌ای ساخته نمی‌شود (سه حالت + بی‌پاسخ)', () => {
    for (const status of ['empty', 'insufficient', 'error'] as const) {
      expect(view(payload({ status }), undefined), status).toEqual([]);
    }
    expect(view(null)).toEqual([]);
  });

  it('پیوت‌هایِ دید ⇒ مارکر + پاره‌خطِ بینِ entriesِ متوالی، همه در گروهِ موتورِ سوم', () => {
    const specs = view(payload());
    const markers = specs.filter((s) => s.kind === 'marker');
    const segs = specs.filter((s) => s.kind === 'segment');
    expect(markers).toHaveLength(2);
    expect(segs).toHaveLength(1);
    expect(segs[0].points.map((p) => p.value)).toEqual([100, 120]);
    for (const s of specs) {
      expect(s.group).toBe(E3_GROUP);
      expect(s.id.startsWith('e3-')).toBe(true);
    }
  });

  it('امضایِ «م۳» رویِ برچسب می‌آید تا HHِ این لایه با HHِ موتورِ اول اشتباه نشود', () => {
    const specs = view(payload());
    const labels = specs.filter((s) => s.kind === 'marker').map((s) => s.label ?? '');
    expect(labels.some((l) => l.includes('HH') && l.includes('م'))).toBe(true);
    expect(e3MarkerLabel(point(1, 'low', 10, null))).toContain('م');
  });

  it('عددِ سرور عیناً با همان ضریبِ دید می‌آید (بی‌محاسبهٔ تعدیلِ دوم)', () => {
    const specs = structure3Layers({
      e3: payload(),
      startTs: ts(0),
      anchorTs: ts(9),
      toDisp: (rial) => rial * 1.5,
      tsForDate: (d) => {
        const i = Math.round((Date.parse(`${d}T00:00:00Z`) - T0) / DAY);
        return i >= 0 && i <= 9 ? ts(i) : null;
      },
    });
    expect(specs.filter((s) => s.kind === 'marker').map((s) => s.points[0].value)).toEqual([150, 180]);
  });

  it('پیوتِ بیرونِ دید و پیوتِ بی‌قیمتِ معتبر رسم نمی‌شوند (نه جای‌گذاریِ حدسی)', () => {
    const specs = structure3Layers({
      e3: payload({
        points: [point(0, 'low', 100), point(4, 'high', 0), point(20, 'low', 130)],
      }),
      startTs: ts(1),
      anchorTs: ts(9),
      toDisp: (r) => r,
      tsForDate: (d) => {
        const i = Math.round((Date.parse(`${d}T00:00:00Z`) - T0) / DAY);
        return i >= 1 && i <= 9 ? ts(i) : null;
      },
    });
    // idx0 بیرونِ دید، idx4 قیمتِ نامعتبر، idx20 بیرونِ سری ⇒ هیچ‌کدام
    expect(specs).toEqual([]);
  });

  it('`meta.pending` رسم نمی‌شود: حتی اگر تاریخش داخلِ دید باشد', () => {
    // pending درِ meta است و درِ points نیست؛ نگاشت هم فقط points را می‌خواند،
    // پس پیوتِ تأییدنشده هرگز رویِ بوم نمی‌آید (همان گاردِ ضدِ repaint).
    const withPending = payload({
      meta: {
        bars: 10,
        confirmed_atr: 2,
        confirmed_floor_only: 0,
        atr_missing_bars: 0,
        pending: { idx: 7, time: dateFor(7), price: 150, kind: 'high', confirmed: false },
      },
    });
    const specs = view(withPending);
    expect(specs.some((s) => s.points.some((p) => p.value === 150))).toBe(false);
  });

  it('سقفِ *رسم* تازه‌ترین‌ها را نگه می‌دارد و بی‌برشِ تحلیلی است', () => {
    const many = Array.from({ length: 12 }, (_, k) =>
      point(k * 30, k % 2 === 0 ? 'low' : 'high', 100 + k, k % 2 ? 'HH' : 'HL'),
    );
    const e3 = payload({
      points: many,
      bars: 400,
    });
    const specs = structure3Layers({
      e3,
      startTs: 0,
      anchorTs: Number.MAX_SAFE_INTEGER,
      toDisp: (r) => r,
      tsForDate: (d) => Date.parse(`${d}T00:00:00Z`),
      maxPoints: 4,
    });
    const drawn = specs.filter((s) => s.kind === 'marker');
    expect(drawn).toHaveLength(4);
    // چهار تایِ آخرِ فهرستِ سرور (قیمت ۱۰۸..۱۱۱)، نه چهار تایِ نخست
    expect(drawn.map((s) => s.points[0].value)).toEqual([108, 109, 110, 111]);
    expect(specs.filter((s) => s.kind === 'segment')).toHaveLength(3);
    expect(E3_MAX_DRAWN_POINTS).toBeGreaterThan(0);
  });

  it('رویدادهایِ CHoCH رویِ سطحِ خودِ موتور نشان می‌شوند، نه رویِ قیمتِ بستهٔ کندل', () => {
    const specs = view(payload({
      choch: [{
        kind: 'high', direction: 'bullish', idx: 4, time: dateFor(4),
        confirm_idx: 7, confirm_time: dateFor(7), level: 118.5,
      }],
    }));
    const ch = specs.find((s) => s.id.startsWith('e3-choch-'));
    expect(ch?.points[0].value).toBe(118.5);
    expect(ch?.label).toContain('CHoCH');
  });

  it('نگاشتِ klinecharts: segment و marker تنها حالت‌هایِ مجازِ این لایه‌اند', () => {
    const specs = view(payload({
      choch: [{
        kind: 'low', direction: 'bearish', idx: 4, time: dateFor(4),
        confirm_idx: 7, confirm_time: dateFor(7), level: 99,
      }],
    }));
    for (const s of specs) {
      const made = e3KlinechartsOverlay(s, 'fts_e3_overlays');
      expect(made, s.kind).toBeTruthy();
      expect(['segment', 'simpleAnnotation']).toContain((made as { name: string }).name);
      expect((made as { groupId: string }).groupId).toBe('fts_e3_overlays');
    }
    // حالتِ بی‌مصرفِ spec (که این موتور تولید نمی‌کند) نباید اورلی بسازد
    expect(e3KlinechartsOverlay({
      id: 'x', kind: 'level', group: E3_GROUP, points: [{ timestamp: ts(1), value: 1 }], color: '#fff',
    }, 'g')).toBeNull();
  });
});
