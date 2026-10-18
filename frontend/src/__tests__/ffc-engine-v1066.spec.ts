// __tests__/ffc-engine-v1066.spec.ts -- موتورِ دوم باید همان تحلیلِ سرور را بگوید
// FFC از رابطِ موتور (engine/) اورلی می‌گیرد: level/band/segment/marker. این سنجش‌ها
// می‌گویند (۱) نگاشتِ `/api/fts` → لایه‌ها هیچ عددی از خودش نمی‌سازد و هیچ لایه‌ای
// را دو بار نمی‌کارد، (۲) انتخابِ موتور در تنظیمات می‌نشیند و مقدارِ ناشناخته (یا
// موتورِ حذف‌شده از رجیستری) چارت را نمی‌اندازد، (۳) هر سوییچِ کاتالوگ درِ همین
// موتور هم مسیرِ رسم دارد (مرحلۀ ۶: دکمه به تنهایی آزمون نیست).
import { describe, expect, it } from 'vitest';
import { engineFtsLayers } from '@features/technical/lib/engineFtsLayers';
import { ENGINE_REGISTRY } from '@features/technical/engine';
import { FTS_INDICATOR_CATALOG } from '@features/technical/lib/ftsIndicatorCatalog';
import {
  PATTERN_PREFS_DEFAULT,
  type PatternKind,
  type PatternPrefs,
} from '@features/technical/lib/patternOverlays';
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

  it('موتورِ دوم درِ رجیستری می‌ماند ولی ازِ انتخابِ کاربر بیرون است (#186، رأیِ ۱۴۰۵-۷-۲۷)', () => {
    const ffc = ENGINE_REGISTRY.find((e) => e.id === 'ffc');
    // کدِ موتور و آزمایشگاهِ موتور سرجای خوداند؛ فقط چارتِ اصلی آن را انتخاب‌پذیر
    // نمی‌کند. این سطر پیش از این `production: true` را قفل کرده بود — همان
    // انتخابی که مالک ازِ رابط بیرون کرد، پس اصلاح می‌شود نه حذف.
    expect(ffc).toBeTruthy();
    expect(ffc?.production).toBe(false);
    expect(ENGINE_REGISTRY.filter((e) => e.production).map((e) => e.id)).toEqual(['klinecharts']);
  });
});

// مرحلۀ ۶: «صرفاً کلیک رویِ دکمهٔ ابزار آزمونِ موفق نیست». سنجشِ زندهٔ بوم نشان داد
// سوییچ‌هایِ کاتالوگ درِ موتورِ دوم هیچ پیکسلی را تکان نمی‌دهند (`prefs` به نگاشت
// نمی‌رسید) — این‌ها همان مسیر را از درِ تابعِ نگاشت می‌بندند.
describe('سوییچ‌هایِ کاتالوگ درِ موتورِ دوم (#227)', () => {
  /** هر سوییچِ کاتالوگ لا‌اقلِ یک لایه دارد — بی‌این، آزمونِ «خاموش شد» بی‌معناست */
  const ALL = {
    ...payload,
    choch: { bullish: true, bearish: false, level: 1180 },
    pullback: { active: true, touching: true, level: 1420 },
    range_box: { active: true, top: 1500, bottom: 1300, start_date: '2026-01-06', end_date: '2026-01-08' },
    structure_points: {
      D: [{ time: '2026-01-07', price: 1250, label: 'HL', confirm_time: '2026-01-09' }],
      W: [{ time: '2026-01-05', price: 1210, label: 'LH', confirm_time: '2026-01-12' }],
    },
    exit_engine: {
      verdict: 'caution',
      l1: { hard_stop: 1049, ma14: 1270, ma14_exit: true },
      l3: { third_peak: true, third_peak_level: 1500, third_peak_band_pct: 2,
            double_top: true, level: 1470, hs_break: true, neckline: 1440 },
    },
  } as unknown as FtsAnalysisData;

  /** سوییچ → لایه‌هایی که فقط زیرِ همان سوییچ رسم می‌شوند (جدولِ صریح، تا
   *  «همه‌چیز کم شد» به جایِ «لایۀِ درست کم شد» سبز نشود) */
  const LAYERS_OF: Record<PatternKind, (id: string) => boolean> = {
    jet: (id) => id === 'jet',
    choch: (id) => id === 'choch',
    pointhunt: (id) => id === 'point-hunt',
    double: (id) => id === 'double-bottom' || id === 'double-top',
    headshoulders: (id) => id === 'head-shoulders',
    thirdpeak: (id) => id === 'third-peak',
    ma14exit: (id) => id === 'ma14-exit',
    hourglass: (id) => id === 'hourglass',
    pullback: (id) => id === 'pullback',
    structure: (id) => id.startsWith('structure-'),
    rangebox: (id) => id === 'range-box',
  };

  const prefsOf = (off: PatternKind[]): PatternPrefs =>
    Object.fromEntries(
      Object.entries(PATTERN_PREFS_DEFAULT).map(([k, v]) => [k, { ...v, enabled: !off.includes(k as PatternKind) }]),
    ) as PatternPrefs;

  const idsOf = (prefs?: PatternPrefs) => engineFtsLayers({ ...plain, fts: ALL, prefs }).map((l) => l.id);

  it('هر سوییچی که کاتالوگ اعلام می‌کند درِ این موتور هم لایۀ خودش را دارد', () => {
    const declared = new Set(
      FTS_INDICATOR_CATALOG.map((e) => e.toggle).filter((t) => t !== null && t in PATTERN_PREFS_DEFAULT),
    );
    const gated = Object.keys(LAYERS_OF) as PatternKind[];
    expect(declared.size, 'رجیستری و جدولِ سوییچ‌ها هم‌اندازه‌اند').toBe(gated.length);
    for (const k of gated) expect(declared.has(k), `سوییچِ ${k} درِ کاتالوگ ثبت شده`).toBe(true);
    const ids = idsOf();
    for (const k of gated) expect(ids.some(LAYERS_OF[k]), `سوییچِ ${k} لایه می‌سازد`).toBe(true);
  });

  it('خاموش‌کردنِ هر سوییچ دقیقاً لایه‌هایِ خودش را برمی‌دارد', () => {
    const all = idsOf();
    for (const k of Object.keys(LAYERS_OF) as PatternKind[]) {
      const hit = LAYERS_OF[k];
      const after = idsOf(prefsOf([k]));
      const gone = all.filter((id) => !after.includes(id));
      expect(gone.sort(), `سوییچِ ${k} فقط لایه‌هایِ خودش را حذف می‌کند`)
        .toEqual(all.filter(hit).sort());
      // و لایه‌هایِ بقیه سرِ جایشان می‌مانند
      expect(after.length).toBe(all.length - all.filter(hit).length);
    }
  });

  it('بی‌prefs همان رفتارِ پیشین: همه روشن (پیش‌فرضِ enabled !== false)', () => {
    expect(idsOf()).toEqual(idsOf(PATTERN_PREFS_DEFAULT));
    expect(idsOf()).toContain('double-top');
    expect(idsOf()).toContain('head-shoulders');
  });

  it('رنگِ لایه از همان prefs می‌آید، نه از ثابتِ این فایل (تفاتِ CHoCH)', () => {
    const base = engineFtsLayers({ ...plain, fts: ALL });
    // با پیش‌فرض‌ها دو موتور یک رنگ دارند: `col(kind)` درِ کهنه == اینجا
    expect(base.find((l) => l.id === 'choch')!.color).toBe(PATTERN_PREFS_DEFAULT.choch.color);
    const box = base.find((l) => l.id === 'range-box')!;
    expect(box.color).toBe(PATTERN_PREFS_DEFAULT.rangebox.color);
    expect(box.fill).toBe('rgba(251, 191, 36, 0.12)');
    const custom = engineFtsLayers({
      ...plain, fts: ALL,
      prefs: { ...PATTERN_PREFS_DEFAULT, choch: { ...PATTERN_PREFS_DEFAULT.choch, color: '#ff0000' } },
    });
    expect(custom.find((l) => l.id === 'choch')!.color).toBe('#ff0000');
  });
});
