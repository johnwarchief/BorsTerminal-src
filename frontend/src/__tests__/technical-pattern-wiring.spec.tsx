// تست اتصال موتور الگوها (T-26): نگاشت به اورلی + ترجیحات مستقل + fixture واقع‌گرا
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { detectJet, detectMa14Exit } from '@features/technical/lib/ftsPatterns';
import { PATTERN_PREFS_DEFAULT, buildPatternOverlays, type PatternPrefs } from '@features/technical/lib/patternOverlays';
import { PatternToggles } from '@features/technical/components/PatternToggles';
import { usePatternPrefsStore } from '@features/technical/stores/patternPrefsStore';

const DAY = 86_400_000;
const t0 = Date.UTC(2026, 0, 1);
const rows = (n: number) => Array.from({ length: n }, (_, i) => ({ timestamp: t0 + i * DAY }));

describe('نقشهٔ راه: پیش‌فرض‌های ترجیحات', () => {
  it('۹ الگو، همه روشن، شفافیت در بازهٔ ۰٫۱–۰٫۲ برای نواحی', () => {
    const kinds = Object.keys(PATTERN_PREFS_DEFAULT);
    expect(kinds).toHaveLength(9);
    expect(kinds.every((k) => PATTERN_PREFS_DEFAULT[k as keyof PatternPrefs].enabled)).toBe(true);
    expect(PATTERN_PREFS_DEFAULT.jet.opacity).toBeLessThanOrEqual(0.2);
    expect(PATTERN_PREFS_DEFAULT.fib.opacity).toBeLessThanOrEqual(0.2);
  });
});

describe('buildPatternOverlays — احترام به انتخاب کاربر و anti-clutter', () => {
  // fixture واقع‌گرا: ۴۵ کندل زیر مقاومت ۱۰۰ (۹۸)، سپس شکست با کلوز ۱۰۳ ⇒ جت فعال
  const highs = [...new Array(43).fill(100), 101, 103];
  const closes = [...new Array(43).fill(98), 102, 103];
  const barRows = rows(45);

  it('جت فعال + روشن ⇒ یک اورلی با لیبل JET و هایلایت ۳ کندلی', () => {
    const jet = detectJet(highs, closes, 30);
    expect(jet.active).toBe(true);
    const specs = buildPatternOverlays({ jet }, PATTERN_PREFS_DEFAULT, barRows);
    const jetSpec = specs.find((s) => s.kind === 'jet');
    expect(jetSpec).toBeTruthy();
    expect(jetSpec!.label).toBe('JET');
    expect(jetSpec!.extendData?.highlightBars).toBe(3);
    expect(String(jetSpec!.extendData?.highlightColor)).toContain('rgba');
  });

  it('خاموش‌کردن جت ⇒ هیچ اورلی جت ساخته نمی‌شود', () => {
    const jet = detectJet(highs, closes, 30);
    const prefs: PatternPrefs = { ...PATTERN_PREFS_DEFAULT, jet: { ...PATTERN_PREFS_DEFAULT.jet, enabled: false } };
    const specs = buildPatternOverlays({ jet }, prefs, barRows);
    expect(specs.find((s) => s.kind === 'jet')).toBeUndefined();
  });

  it('الگوی نقطه‌زنی کهنه (بیش از ۵۰ کندل قبل) حذف می‌شود — anti-clutter', () => {
    const oldRows = rows(120);
    // برخورد کف در ایندکس ۳ ⇒ ۱۱۶ کندل از انتها ⇒ کهنه ⇒ باید حذف شود
    const oldHit = { active: true, slopePct: -1, hits: [3], floor: 3 as const };
    expect(buildPatternOverlays({ pointHunt: oldHit }, PATTERN_PREFS_DEFAULT, oldRows).find((s) => s.kind === 'pointhunt')).toBeUndefined();
    // همان الگو ولی با برخورد تازه (ایندکس ۱۱۸) ⇒ باید بماند
    const freshHit = { active: true, slopePct: -1, hits: [118], floor: 3 as const };
    const kept = buildPatternOverlays({ pointHunt: freshHit }, PATTERN_PREFS_DEFAULT, oldRows);
    expect(kept.find((s) => s.kind === 'pointhunt')).toBeTruthy();
  });

  it('خروج MA14 فعال ⇒ ضربدر روی آخرین کندل (تازه)', () => {
    const ma = new Array(20).fill(100);
    const ma14 = detectMa14Exit(new Array(20).fill(95), new Array(20).fill(96), new Array(20).fill(94), new Array(20).fill(95), ma);
    expect(ma14.active).toBe(true);
    const specs = buildPatternOverlays({ ma14Exit: ma14 }, PATTERN_PREFS_DEFAULT, rows(30));
    expect(specs.find((s) => s.kind === 'ma14exit')).toBeTruthy();
  });

  it('فیبوی فعال ⇒ دو باکس با لیبل‌های استاندارد', () => {
    const fib = { active: true, low: 100, high: 400, entry1: { from: 220, to: 240 }, entry2: { from: 130, to: 150 } };
    const specs = buildPatternOverlays({ fib }, PATTERN_PREFS_DEFAULT, barRows);
    const labels = specs.filter((s) => s.kind === 'fib').map((s) => s.label);
    expect(labels).toEqual(['Fibo Entry 1 (33-40%)', 'Fibo Entry 2 (61.8-70%)']);
  });
});

describe('سوییچ‌های UI (PatternToggles) + پایداری', () => {
  beforeEach(() => {
    localStorage.clear();
    usePatternPrefsStore.getState().reset();
  });

  it('۹ توسل روشن/خاموش/رنگ/شفافیت رندر می‌شوند', () => {
    render(<PatternToggles />);
    expect(screen.getByTestId('pattern-toggles')).toBeInTheDocument();
    for (const k of ['jet', 'fib', 'choch', 'pointhunt', 'double', 'headshoulders', 'thirdpeak', 'ma14exit', 'hourglass']) {
      expect(screen.getByTestId(`pattern-toggle-${k}`)).toBeInTheDocument();
      expect(screen.getByTestId(`pattern-color-${k}`)).toBeInTheDocument();
      expect(screen.getByTestId(`pattern-opacity-${k}`)).toBeInTheDocument();
    }
  });

  it('خاموش‌کردن یک الگو در استور و localStorage ذخیره می‌شود', () => {
    render(<PatternToggles />);
    fireEvent.click(screen.getByTestId('pattern-toggle-choch'));
    expect(usePatternPrefsStore.getState().prefs.choch.enabled).toBe(false);
    const raw = localStorage.getItem('fts-pattern-prefs');
    expect(raw).toBeTruthy();
    expect(JSON.parse(raw as string).choch.enabled).toBe(false);
  });

  it('تغییر رنگ و شفافیت اعمال می‌شود', () => {
    render(<PatternToggles />);
    fireEvent.change(screen.getByTestId('pattern-color-jet'), { target: { value: '#ff00aa' } });
    fireEvent.change(screen.getByTestId('pattern-opacity-jet'), { target: { value: '55' } });
    expect(usePatternPrefsStore.getState().prefs.jet.color).toBe('#ff00aa');
    expect(usePatternPrefsStore.getState().prefs.jet.opacity).toBeCloseTo(0.55, 6);
  });
});
