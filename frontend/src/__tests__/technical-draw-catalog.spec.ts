// تست کاتالوگ ابزارهای ترسیم به سبک TradingView (T-07): پوشش، پیشفرضها، فیبوی لگاریتمی
import { describe, expect, it } from 'vitest';
import type { OverlayFigureCtx, RegisterOverlayDef } from '@vendor/klinecharts';
import { DRAWING_CATALOG, buildDrawingGroups, toolDefaults, toolLabel } from '@features/technical/lib/drawingTools';
import { FTS_FIB_BANDS, FTS_FIB_LEVELS, fibZoneSpecs, registerFtsOverlays } from '@features/technical/lib/ftsOverlays';

/** ثبت اورلیها با api قلابی و برگرداندن تعریفها */
function captureRegistered(): RegisterOverlayDef[] {
  const defs: RegisterOverlayDef[] = [];
  registerFtsOverlays({
    registerOverlay: (def) => defs.push(def),
    getSupportedOverlays: () => [],
  });
  return defs;
}

function figuresOf(def: RegisterOverlayDef, ctx: OverlayFigureCtx) {
  const figs = def.createPointFigures?.(ctx) ?? [];
  return figs.filter((f) => f.type === 'text').map((f) => String((f.attrs as { text: string }).text));
}

describe('پوشش کاتالوگ ابزارهای رسم (TV)', () => {
  it('ابزارهای فهرست مأموریت همه در کاتالوگاند', () => {
    const names = DRAWING_CATALOG.flatMap((g) => g.tools.map((t) => t.name));
    for (const n of [
      'straightLine',
      'horizontalStraightLine',
      'verticalStraightLine',
      'rayLine',
      'parallelStraightLine',
      'ftsFib',
      'ftsFibLog',
      'ftsMeasure',
      'ftsPosition',
      'simpleAnnotation',
      'simpleTag',
    ]) {
      expect(names).toContain(n);
    }
  });

  it('فیبوی FTS سطوح ۰/۳۳/۴۰/۶۱.۸/۷۰/۱۰۰ را دارد', () => {
    expect([...FTS_FIB_LEVELS]).toEqual([0, 0.33, 0.4, 0.618, 0.7, 1]);
    expect(FTS_FIB_BANDS.map((b) => [...b])).toEqual([
      [0.33, 0.4],
      [0.618, 0.7],
    ]);
  });

  it('برچسب فارسی هر ابزار از کاتالوگ میآید', () => {
    expect(toolLabel('ftsFibLog')).toBe('فیبوی لگاریتمی FTS');
    expect(toolLabel('straightLine')).toBe('خط روند');
    expect(toolLabel('unknown-thing')).toBe('unknown-thing');
  });

  it('buildDrawingGroups سفارشیها را همیشه نگه میدارد', () => {
    const groups = buildDrawingGroups([]);
    const names = groups.flatMap((g) => g.tools.map((t) => t.name));
    expect(names).toContain('ftsFib');
    expect(names).toContain('ftsFibLog');
  });
});

describe('پیشفرض هر ابزار (رنگ/ضخامت/امتداد/متن)', () => {
  it('خط روند: رنگ و ضخامت و نوع خط', () => {
    expect(toolDefaults('straightLine')).toEqual({ styles: { color: '#38bdf8', size: 1.5, style: 'solid' } });
  });

  it('فیبوی لگاریتمی رنگ متمایز از فیبوی خطی دارد', () => {
    const lin = toolDefaults('ftsFib');
    const log = toolDefaults('ftsFibLog');
    expect((lin.styles as { color: string }).color).not.toBe((log.styles as { color: string }).color);
  });

  it('متن/یادداشت برچسب پیشفرض دارند', () => {
    expect(toolDefaults('simpleAnnotation').extendData).toEqual({ text: 'یادداشت' });
    expect(toolDefaults('simpleTag').extendData).toEqual({ text: 'برچسب' });
  });

  it('نام ناشناخته ⇒ پیشفرض خالی (بدون ساختگی)', () => {
    expect(toolDefaults('nope')).toEqual({});
  });
});

describe('فیبوی FTS: خطی در برابر لگاریتمی', () => {
  const defs = captureRegistered();
  const lin = defs.find((d) => d.name === 'ftsFib');
  const log = defs.find((d) => d.name === 'ftsFibLog');
  const ctx = {
    chart: {},
    overlay: { points: [{ value: 200 }, { value: 100 }] },
    coordinates: [
      { x: 10, y: 50 },
      { x: 110, y: 150 },
    ],
    bounding: { width: 300, height: 200 },
    barSpace: { bar: 10, halfBar: 5, gapBar: 4, halfGapBar: 2 },
  } as unknown as OverlayFigureCtx;

  it('هر دو اورلی ثبت میشوند', () => {
    expect(lin).toBeTruthy();
    expect(log).toBeTruthy();
  });

  it('حالت خطی: سطح ۴۰٪ = ۱۴۰', () => {
    const texts = figuresOf(lin as RegisterOverlayDef, ctx);
    expect(texts.some((t) => t.includes('140') && t.includes('40.0%'))).toBe(true);
    expect(texts.some((t) => t.includes('132') && t.includes('40.0%'))).toBe(false);
  });

  it('حالت لگاریتمی: سطح ۴۰٪ = ۱۳۲ (۱۰۰×۲^۰٫۴)', () => {
    const texts = figuresOf(log as RegisterOverlayDef, ctx);
    expect(texts.some((t) => t.includes('132') && t.includes('40.0%'))).toBe(true);
    expect(texts.some((t) => t.includes('140') && t.includes('40.0%'))).toBe(false);
  });

  it('سطوح مبنا در هر دو حالت یکی است (۱۰۰٪ و ۰٪)', () => {
    for (const def of [lin, log] as RegisterOverlayDef[]) {
      const texts = figuresOf(def, ctx);
      expect(texts.some((t) => t.includes('200') && t.includes('100.0%'))).toBe(true);
      expect(texts.some((t) => t.includes('100') && t.includes('0.0%'))).toBe(true);
    }
  });
});

describe('اورلی رویدادهای شرکتی (FTS_CORP_ACTION_OVERLAY)', () => {
  const all = captureRegistered();
  const corp = all.find((d) => d.name === 'ftsCorpAction');

  it('اورلی با موفقیت ثبت می‌شود', () => {
    expect(corp).toBeTruthy();
  });

  it('نشانگر تکِ «تعدیل» با آفست +24px — نوعِ رویداد از سرور نمی‌آید، پس D/S ندارد', () => {
    const figs = corp?.createPointFigures?.({
      coordinates: [{ x: 100, y: 200 }],
      overlay: { extendData: { kind: 'A', text: 'تعدیل قیمت پایه · ×۰٫۷۴' } },
    } as unknown as OverlayFigureCtx) ?? [];
    const at = (i: number) => figs[i].attrs as { x?: number; y?: number; r?: number; text?: string };
    expect(figs.length).toBe(3);
    expect(at(0).y).toBe(224);
    expect(at(0).r).toBe(9);
    expect(at(1).text).toBe('A');
    expect((figs[1].styles as { color?: string }).color).toBe('#f59e0b');
    // خودِ نسبت هم کنارِ نشانگر خوانده می‌شود (وگرنه نقطه بی‌توضیح است)
    expect(at(2).text).toBe('تعدیل قیمت پایه · ×۰٫۷۴');
    expect(at(2).x).toBe(112);
  });
});

// از specِ رپرِ قدیمی به این‌جا آمد. fibZoneSpecs خالصِ کتابخانه‌ای است و
// چارتِ زنده همان را می‌سازد.
describe('fibZoneSpecs از داده بک اند', () => {
  it('هر دو کمربند معتبر می سازد', () => {
    const specs = fibZoneSpecs({
      zone_33_40: { lo: 2739.2, hi: 2839.93, in_zone: false },
      zone_618_70: { lo: 2346.44, hi: 2447.83, in_zone: true },
    });
    expect(specs).toHaveLength(2);
    expect(specs[0].lo).toBeCloseTo(2739.2);
    expect(specs[0].hi).toBeCloseTo(2839.93);
    expect(specs[1].label).toContain('طلایی');
  });

  it('null و کمربند ناقص هیچ نمی سازد', () => {
    expect(fibZoneSpecs(null)).toHaveLength(0);
    expect(fibZoneSpecs({ zone_33_40: null, zone_618_70: { lo: null, hi: null } })).toHaveLength(0);
    expect(fibZoneSpecs({ zone_33_40: { lo: 100, hi: 90 } })).toHaveLength(0); // hi<=lo
  });

  it('اعداد نامعتبر (نامنفی/NaN) رد می شوند', () => {
    expect(
      fibZoneSpecs({ zone_33_40: { lo: Number.NaN, hi: 100 } }),
    ).toHaveLength(0);
  });
});

