// __tests__/ffc-engine-v1066.spec.ts -- موتورِ دوم باید همان تحلیلِ سرور را بگوید
// FFC از رابطِ موتور (engine/) اورلی می‌گیرد: level/band/segment/marker. این دو
// سنجش می‌گویند (۱) نگاشتِ `/api/fts` → لایه‌ها هیچ عددی از خودش نمی‌سازد و هیچ
// لایه‌ای را دو بار نمی‌کارد، (۲) انتخابِ موتور در تنظیمات می‌نشیند و مقدارِ
// ناشناخته (یا موتورِ حذف‌شده از رجیستری) چارت را نمی‌اندازد.
import { describe, expect, it } from 'vitest';
import { engineFtsLayers } from '@features/technical/lib/engineFtsLayers';
import { ENGINE_REGISTRY } from '@features/technical/engine';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

const T0 = Date.UTC(2026, 0, 5);
const DAY = 86_400_000;
const plain = {
  anchorTs: T0 + 10 * DAY,
  startTs: T0,
  toDisp: (p: number) => p,
  tsForDate: (d: string) => Date.parse(d + 'T00:00:00Z'),
};

const payload = {
  fib: {
    zone_33_40: { lo: 1200, hi: 1260, in_zone: true },
    zone_618_70: { lo: 1400, hi: 1450, in_zone: false },
    levels: [
      { ratio: 0, price: 1500 },
      { ratio: 0.5, price: 1300 },
      { ratio: 1, price: 1100 },
    ],
    leg: { direction: 'up' },
  },
  jet: { active: true, resistance: 1500 },
  choch: { bearish: true, level: 1180 },
  double_bottom: { active: true, neckline: 1290 },
  point_hunt: { active: true, floor_price: 1105, touches: 4, floor_date: '2026-01-08',
                 trigger_date: '2026-01-08' },
  exit_engine: { verdict: 'caution', l1: { hard_stop: 1049, ma14: 1270, ma14_exit: true }, l3: { third_peak: true, third_peak_level: 1500 } },
  hourglass: { active: true, ma52: 1250, weekly_rsi5: 24 },
} as unknown as FtsAnalysisData;

describe('نگاشتِ FTS → لایه‌های رابطِ موتور', () => {
  it('بی‌payload هیچ لایه‌ای نیست (موتورِ دوم هم بی‌داده رأی نمی‌دهد)', () => {
    expect(engineFtsLayers({ ...plain, fts: null })).toEqual([]);
    expect(engineFtsLayers({ ...plain, fts: undefined })).toEqual([]);
  });

  it('کمربندها، سطوح، خطِ گردن، جت، CHoCH، حدِ ضرر و ساعت شنی همگی می‌آیند', () => {
    const layers = engineFtsLayers({ ...plain, fts: payload });
    const ids = layers.map((l) => l.id);
    for (const want of ['fib-zone_33_40', 'fib-zone_618_70', 'jet', 'choch',
                       'double-bottom', 'point-hunt', 'hard-stop', 'ma14-exit', 'third-peak', 'hourglass']) {
      expect(ids, `لایۀ ${want} رسم می‌شود`).toContain(want);
    }
    expect(new Set(ids).size, 'هیچ لایه‌ای دوبار کاشته نمی‌شود').toBe(ids.length);
    const belt = layers.find((l) => l.id === 'fib-zone_33_40')!;
    expect(belt.kind).toBe('band');
    expect(belt.points.map((p) => p.value)).toEqual([1200, 1260]);
    expect(layers.find((l) => l.id === 'point-hunt')!.points[0].timestamp).toBe(Date.parse('2026-01-08T00:00:00Z'));
    // سلسله‌مراتبِ دورِ J: سطح‌های فیبو پیش‌فرض رسم نمی‌شوند
    expect(ids.filter((s) => String(s).startsWith('fib-level-'))).toEqual([]);
    const withLevels = engineFtsLayers({ ...plain, fts: payload, showFibLevels: true });
    expect(withLevels.map((l) => l.id)).toContain('fib-level-0.5');
  });

  it('عددِ سرور در فضایِ قیمتِ چارت می‌نشیند و بی‌سطحِ معتبر لایه نمی‌سازد', () => {
    const half = engineFtsLayers({ ...plain, fts: payload, toDisp: (p) => p * 0.5 });
    expect(half.find((l) => l.id === 'jet')!.points[0].value).toBe(750);
    const broken = engineFtsLayers({
      ...plain,
      fts: { jet: { active: true, resistance: 0 }, fib: { zone_33_40: { lo: 500, hi: 400 } } } as unknown as FtsAnalysisData,
    });
    expect(broken.find((l) => l.id === 'jet')).toBeUndefined();
    expect(broken.find((l) => l.id === 'fib-zone_33_40')).toBeUndefined();
  });

  it('جعبۀ رنج با کرانِ بازۀ خودش رسم می‌شود؛ بی‌تاریخِ سرور اصلاً رسم نمی‌شود (ب-۳)', () => {
    const withBox = (box: Record<string, unknown>) =>
      engineFtsLayers({ ...plain, fts: { range_box: box } as unknown as FtsAnalysisData })
        .find((l) => l.id === 'range-box');
    const drawn = withBox({ top: 1500, bottom: 1300, active: true, start_date: '2026-01-06', end_date: '2026-01-26' })!;
    expect(drawn.kind).toBe('band');
    expect(drawn.points.map((p) => p.timestamp))
      .toEqual([Date.parse('2026-01-06T00:00:00Z'), Date.parse('2026-01-26T00:00:00Z')]);
    expect(drawn.points.map((p) => p.value)).toEqual([1300, 1500]);
    expect(drawn.label).toBe('شکست جعبه رنج');
    expect(withBox({ top: 1500, bottom: 1300, active: false, start_date: '2026-01-06', end_date: '2026-01-26' })!.label)
      .toBe('جعبه رنج');
    // extentِ باکس از خودِ قاعدۀ سرور است؛ بی‌کرانِ زمانی، رسمِ تمام‌عرض دروغ می‌گفت
    expect(withBox({ top: 1500, bottom: 1300, active: true })).toBeUndefined();
    expect(withBox({ top: 1500, bottom: 1300, active: true, start_date: '2026-01-06' })).toBeUndefined();
    expect(withBox({ top: null, bottom: 1300, start_date: '2026-01-06', end_date: '2026-01-26' })).toBeUndefined();
    const scaled = engineFtsLayers({
      ...plain,
      toDisp: (p) => p * 0.5,
      fts: { range_box: { top: 1500, bottom: 1300, start_date: '2026-01-06', end_date: '2026-01-26' } } as unknown as FtsAnalysisData,
    }).find((l) => l.id === 'range-box')!;
    expect(scaled.points.map((p) => p.value)).toEqual([650, 750]);
  });

  it('پیوت‌هایِ ساختار از هر دو TF می‌آیند و هفتگی با پسوندِ (W) خوانده می‌شود (ب-۱)', () => {
    const layers = engineFtsLayers({
      ...plain,
      fts: {
        structure_points: {
          D: [{ time: '2026-01-06', price: 1400, label: 'HL', confirm_time: '2026-01-08' }],
          W: [{ time: '2026-01-05', price: 1200, label: 'LL', confirm_time: '2026-01-12' }],
        },
      } as unknown as FtsAnalysisData,
    }).filter((l) => l.group === 'fts-structure');
    expect(layers.map((l) => `${l.id}:${l.label}`))
      .toEqual(['structure-D-2026-01-06:HL', 'structure-W-2026-01-05:LL (W)']);
    expect(layers.find((l) => l.id === 'structure-W-2026-01-05')!.color).toBe('#f87171');
    const broken = engineFtsLayers({
      ...plain,
      fts: { structure_points: { D: [{ time: '2026-01-07', price: 0, label: 'HH', confirm_time: null }] } } as unknown as FtsAnalysisData,
    }).filter((l) => l.group === 'fts-structure');
    expect(broken).toEqual([]);
  });

  it('موتورِ دوم در رجیستری «تولیدی» است و klinecharts همان پیش‌فرضِ ساخت است', () => {
    const ffc = ENGINE_REGISTRY.find((e) => e.id === 'ffc');
    expect(ffc?.production).toBe(true);
    expect(ENGINE_REGISTRY.filter((e) => e.production).map((e) => e.id)).toEqual(['klinecharts', 'ffc']);
  });
});
