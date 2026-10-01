// تستِ اتصالِ لایۀ «الگوهای FTS» — #193
// داورِ الگو فقط یک جاست: /api/fts. این‌جا two چیز می‌سنجیم:
//   ۱) patternInputsFromFts هر هشت داور را از دهانۀ درستِ payload برمی‌دارد
//      و هیچ عددِ ساختگی (صفرِ جا‌نشین، اندیسِ بی‌ربط) نمی‌سازد
//   ۲) buildPatternOverlays به ترجیحِ کاربر احترام می‌دهد و بی‌داده چیزی نمی‌کارد
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import {
  buildPatternOverlays,
  PATTERN_PREFS_DEFAULT,
  patternInputsFromFts,
  type PatternInputs,
  type PatternPrefs,
} from '@features/technical/lib/patternOverlays';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';
import { PatternToggles } from '@features/technical/components/PatternToggles';
import { usePatternPrefsStore } from '@features/technical/stores/patternPrefsStore';

const DAY = 86_400_000;
const t0 = Date.UTC(2026, 0, 1);
const rows = (n: number) => Array.from({ length: n }, (_, i) => ({ timestamp: t0 + i * DAY }));
const plain = { toDisp: (p: number) => p, tsForDate: (d: string) => Date.parse(d + 'T00:00:00Z') };

/** ورودیِ بی‌الگو — تست‌ها فقط چیزی که می‌خواهند را فعال می‌کنند */
function noPatterns(): PatternInputs {
  return {
    jet: { active: false, level: null },
    choch: { active: false, level: null },
    pointHunt: { active: false, floor: null, touches: null, ts: null },
    double: { active: false, level: null, breakout: false },
    doubleTop: { active: false, level: null },
    headShoulders: { active: false, neckline: null },
    thirdPeak: { active: false, level: null },
    ma14Exit: { active: false, level: null },
    hourglass: { active: false, ma52Weekly: null, rsi14: null },
  };
}

describe('نگاشتِ payloadِ سرور به ورودیِ الگوها (#193)', () => {
  const payload = {
    jet: { active: true, resistance: 2758 },
    choch: { bearish: false, bullish: true, level: 1900 },
    point_hunt: { active: true, touches: 4, floor_price: 1810, floor_idx: 77, floor_date: '2026-01-05' },
    double_bottom: { active: true, neckline: 2100, pct_above_neck: 3.1 },
    exit_engine: {
      verdict: 'hold',
      l1: { ma14_exit: true, ma14: 2450 },
      l3: { hs_break: true, neckline: 2210, third_peak: true, third_peak_level: 3050 },
    },
    hourglass: { active: true, ma52: 2980, weekly_rsi5: 24.6 },
  } as unknown as FtsAnalysisData;

  it('هر هشت داور از جایِ خودش برداشته می‌شود، نه از حدسِ چارت', () => {
    const i = patternInputsFromFts(payload, plain);
    expect(i.jet).toEqual({ active: true, level: 2758 });
    expect(i.choch).toEqual({ active: true, level: 1900 });
    expect(i.pointHunt.active).toBe(true);
    expect(i.pointHunt.floor).toBe(1810);
    expect(i.pointHunt.touches).toBe(4);
    expect(i.pointHunt.ts).toBe(Date.parse('2026-01-05T00:00:00Z'));
    expect(i.double).toEqual({ active: true, level: 2100, breakout: true });
    expect(i.headShoulders).toEqual({ active: true, neckline: 2210 });
    expect(i.thirdPeak).toEqual({ active: true, level: 3050 });
    expect(i.ma14Exit).toEqual({ active: true, level: 2450 });
    expect(i.hourglass).toEqual({ active: true, ma52Weekly: 2980, rsi14: 24.6 });
  });

  it('بی‌payload هیچ الگویی فعال نیست و هیچ قیمتی صفر نمی‌شود', () => {
    const i = patternInputsFromFts(null, plain);
    expect(i).toEqual(noPatterns());
  });

  it('قیمتِ صفر/منفی «بی‌داده» است نه سطحِ مجاز؛ تاریخِ بی‌اعتبار نشانگر نمی‌کارد', () => {
    const bad = {
      jet: { active: true, resistance: 0 },
      point_hunt: { active: true, floor_price: -5, touches: 3, floor_date: '' },
    } as unknown as FtsAnalysisData;
    const i = patternInputsFromFts(bad, { ...plain, tsForDate: () => null });
    expect(i.jet.level).toBeNull();
    expect(i.pointHunt.floor).toBeNull();
    expect(i.pointHunt.ts).toBeNull();
  });

  it('نمایِ بازدهی: همان داور با نسبتِ چارت به محور می‌آید (#193 × #187)', () => {
    const i = patternInputsFromFts(payload, { ...plain, toDisp: (p) => p * 0.5 });
    expect(i.jet.level).toBe(1379);
    expect(i.ma14Exit.level).toBe(1225);
  });

  it('سقف دوقلو از لایۀ ۳ برداشته و رسم می‌شود (قبلاً فقط کف رسم می‌شد)', () => {
    const top = {
      exit_engine: { verdict: 'exit', l3: { double_top: true, level: 4120, neckline: 4120 } },
    } as unknown as FtsAnalysisData;
    const i = patternInputsFromFts(top, plain);
    expect(i.doubleTop).toEqual({ active: true, level: 4120 });
    expect(i.double.active).toBe(false);
    const specs = buildPatternOverlays(i, PATTERN_PREFS_DEFAULT, rows(45));
    const line = specs.find((s) => s.label === 'خط گردن (سقف دوقلو)');
    expect(line).toBeTruthy();
    expect(line?.overlayName).toBe('ftsNeckline');
  });
});

describe('buildPatternOverlays — احترام به انتخاب کاربر، بی‌داوریِ تازه', () => {
  const barRows = rows(45);

  it('جتِ فعالِ سرور ⇒ یک اورلی JET با هایلایتِ سه کندلی', () => {
    const specs = buildPatternOverlays(
      { ...noPatterns(), jet: { active: true, level: 2758 } },
      PATTERN_PREFS_DEFAULT,
      barRows,
    );
    const jetSpec = specs.find((s) => s.kind === 'jet');
    expect(jetSpec).toBeTruthy();
    expect(jetSpec!.label).toBe('JET');
    expect(jetSpec!.points[0].value).toBe(2758);
    expect(jetSpec!.extendData?.highlightBars).toBe(3);
    expect(String(jetSpec!.extendData?.highlightColor)).toContain('rgba');
  });

  it('خاموش‌کردن جت ⇒ هیچ اورلی جت ساخته نمی‌شود', () => {
    const prefs: PatternPrefs = { ...PATTERN_PREFS_DEFAULT, jet: { ...PATTERN_PREFS_DEFAULT.jet, enabled: false } };
    const specs = buildPatternOverlays({ ...noPatterns(), jet: { active: true, level: 2758 } }, prefs, barRows);
    expect(specs.find((s) => s.kind === 'jet')).toBeUndefined();
  });

  it('نقطه‌زنی بی‌تاریخِ لنگر رسم نمی‌شود — نشانگر روی کندلِ بی‌ربط بدتر از نبودن است', () => {
    const noTs = { ...noPatterns(), pointHunt: { active: true, floor: 1810, touches: 4, ts: null } };
    expect(buildPatternOverlays(noTs, PATTERN_PREFS_DEFAULT, barRows).find((s) => s.kind === 'pointhunt')).toBeUndefined();
    const withTs = { ...noPatterns(), pointHunt: { active: true, floor: 1810, touches: 4, ts: t0 + 3 * DAY } };
    const kept = buildPatternOverlays(withTs, PATTERN_PREFS_DEFAULT, barRows).find((s) => s.kind === 'pointhunt');
    expect(kept).toBeTruthy();
    expect(kept!.points[0].timestamp).toBe(t0 + 3 * DAY);
    expect(kept!.points[0].value).toBe(1810);
  });

  it('خروجِ MA14ِ سرور ⇒ ضربدر روی آخرین کندل، رویِ همان خطِ MA14', () => {
    const specs = buildPatternOverlays({ ...noPatterns(), ma14Exit: { active: true, level: 2450 } }, PATTERN_PREFS_DEFAULT, rows(30));
    const s = specs.find((x) => x.kind === 'ma14exit');
    expect(s).toBeTruthy();
    expect(s!.points[0].value).toBe(2450);
    // دیگر قیمتی از کندلِ هم‌زمان جانشین نمی‌شود (#193: بی‌داده = رسمِ نکردن)
    expect(s!.points[0].timestamp).toBe(t0 + 29 * DAY);
  });

  it('ساعت شنی بی‌MA52 باندِ تخت نمی‌سازد؛ با MA52 هم‌عرضِ ۳٪ می‌کشد', () => {
    const bare = buildPatternOverlays({ ...noPatterns(), hourglass: { active: true, ma52Weekly: null, rsi14: 24 } }, PATTERN_PREFS_DEFAULT, barRows);
    expect(bare.find((s) => s.kind === 'hourglass')).toBeUndefined();
    const full = buildPatternOverlays({ ...noPatterns(), hourglass: { active: true, ma52Weekly: 2980, rsi14: 24.6 } }, PATTERN_PREFS_DEFAULT, barRows);
    const band = full.find((s) => s.kind === 'hourglass')!;
    expect(band.points[0].value).toBeCloseTo(2980 * 1.03, 6);
    expect(band.points[1].value).toBeCloseTo(2980 * 0.97, 6);
  });

  // #193 داورِ jev-pilot «الف»: کمربندِ بلندتر از یک‌پنجمِ دید، پنل را پر می‌کرد
  // (سنجشِ زندهٔ «آكام»: ۲۶۶۲۳۳ پیکسل). حالا فقط دو خطِ سطح می‌ماند.
  describe('سقفِ ارتفاعِ بصریِ کمربند (#193)', () => {
    /** نمادِ تخت: کل دید ۱۰۰ تا ۱۰۳ (دامنهٔ ۳٪) — کمربندِ ±۲٪ نیمۀِ پنل را می‌پوشاند */
    const tightRows = Array.from({ length: 40 }, (_, i) => ({ timestamp: t0 + i * DAY, low: 100, high: 103 }));
    /** نمادِ پرنوسان: دید ۶۰ تا ۱۴۰ — همان کمربند یک‌هشتمِ پنل است و پر می‌ماند */
    const wideRows = Array.from({ length: 40 }, (_, i) => ({ timestamp: t0 + i * DAY, low: 60, high: 140 }));

    it('دیدِ تنگ ⇒ به‌جایِ مستطیلِ پر، دو خطِ سطحِ تمام‌عرض از همان دو سطحِ سرور', () => {
      const specs = buildPatternOverlays({ ...noPatterns(), thirdPeak: { active: true, level: 101 } }, PATTERN_PREFS_DEFAULT, tightRows);
      const tp = specs.filter((s) => s.kind === 'thirdpeak');
      expect(tp).toHaveLength(2);
      expect(tp.every((s) => s.points.length === 1)).toBe(true);
      expect(tp.map((s) => s.points[0].value).sort((a, b) => b - a)).toEqual([101 * 1.02, 101 * 0.98]);
      // سطح‌ها دست‌نخورده‌اند: فقط شکلِ رسم عوض شده، نه داوری
      expect(tp[0].kind).toBe('thirdpeak');
    });

    it('دیدِ باز ⇒ همان کمربند با پرکردنِ ملایم (یکِ اورلیِ دونقطه‌ای)', () => {
      const specs = buildPatternOverlays({ ...noPatterns(), thirdPeak: { active: true, level: 101 } }, PATTERN_PREFS_DEFAULT, wideRows);
      const tp = specs.filter((s) => s.kind === 'thirdpeak');
      expect(tp).toHaveLength(1);
      expect(tp[0].points).toHaveLength(2);
    });

    it('بی‌low/high (دامنۀ دید نامعلوم) کمربند حذف یا باریک نمی‌شود — حدس نمی‌زنیم', () => {
      const specs = buildPatternOverlays({ ...noPatterns(), thirdPeak: { active: true, level: 101 } }, PATTERN_PREFS_DEFAULT, rows(40));
      expect(specs.filter((s) => s.kind === 'thirdpeak')[0].points).toHaveLength(2);
    });

    it('ساعت شنی هم از همان سقفِ ارتفاعِ بصری عبور می‌کند', () => {
      const hg = { active: true, ma52Weekly: 101, rsi14: 22 };
      const tight = buildPatternOverlays({ ...noPatterns(), hourglass: hg }, PATTERN_PREFS_DEFAULT, tightRows).filter((s) => s.kind === 'hourglass');
      const wide = buildPatternOverlays({ ...noPatterns(), hourglass: hg }, PATTERN_PREFS_DEFAULT, wideRows).filter((s) => s.kind === 'hourglass');
      expect(tight).toHaveLength(2);
      expect(wide).toHaveLength(1);
    });
  });
});

describe('سوییچ‌های UI (PatternToggles) + پایداری', () => {
  beforeEach(() => {
    localStorage.clear();
    usePatternPrefsStore.getState().reset();
  });

  it('هشت الگو، همه روشن؛ فیبو حذف شده چون لایۀ ۴ِ سرور خودش را می‌کشد (#193)', () => {
    const kinds = Object.keys(PATTERN_PREFS_DEFAULT);
    expect(kinds).toHaveLength(8);
    expect(kinds).not.toContain('fib');
    expect(kinds.every((k) => PATTERN_PREFS_DEFAULT[k as keyof PatternPrefs].enabled)).toBe(true);
    expect(PATTERN_PREFS_DEFAULT.jet.opacity).toBeLessThanOrEqual(0.2);
  });

  it('هشت توسلِ روشن/خاموش/رنگ/شفافیت رندر می‌شوند', () => {
    render(<PatternToggles />);
    expect(screen.getByTestId('pattern-toggles')).toBeInTheDocument();
    for (const k of ['jet', 'choch', 'pointhunt', 'double', 'headshoulders', 'thirdpeak', 'ma14exit', 'hourglass']) {
      expect(screen.getByTestId(`pattern-toggle-${k}`)).toBeInTheDocument();
      expect(screen.getByTestId(`pattern-color-${k}`)).toBeInTheDocument();
      expect(screen.getByTestId(`pattern-opacity-${k}`)).toBeInTheDocument();
    }
    expect(screen.queryByTestId('pattern-toggle-fib')).toBeNull();
  });

  it('خاموش‌کردن یک الگو در استور و localStorage ذخیره می‌شود', () => {
    render(<PatternToggles />);
    fireEvent.click(screen.getByTestId('pattern-toggle-choch'));
    expect(usePatternPrefsStore.getState().prefs.choch.enabled).toBe(false);
    const raw = localStorage.getItem('fts-pattern-prefs');
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw as string).choch.enabled).toBe(false);
  });

  it('رجوع‌به‌پیش‌فرض، ترجیحِ پاک‌شدهٔ قدیمی (fib) را زنده نمی‌کند', () => {
    localStorage.setItem('fts-pattern-prefs', JSON.stringify({ fib: { enabled: true }, jet: { enabled: false } }));
    // store ماژول-سطحی یک‌بار ساخته می‌شود؛ بازخوانیِ صریحِ load را با reset می‌سنجیم
    usePatternPrefsStore.getState().reset();
    const prefs = usePatternPrefsStore.getState().prefs as unknown as Record<string, unknown>;
    expect(Object.keys(prefs)).toHaveLength(8);
    expect(prefs.fib).toBeUndefined();
  });

  it('تغییر رنگ و شفافیت اعمال می‌شود', () => {
    render(<PatternToggles />);
    fireEvent.change(screen.getByTestId('pattern-color-jet'), { target: { value: '#ff00aa' } });
    fireEvent.change(screen.getByTestId('pattern-opacity-jet'), { target: { value: '55' } });
    expect(usePatternPrefsStore.getState().prefs.jet.color).toBe('#ff00aa');
    expect(usePatternPrefsStore.getState().prefs.jet.opacity).toBeCloseTo(0.55, 6);
  });
});
