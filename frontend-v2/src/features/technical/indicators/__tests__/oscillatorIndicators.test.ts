/**
 * frontend-v2/src/features/technical/indicators/__tests__/oscillatorIndicators.test.ts
 *
 * نگهبان‌های نیمۀ گمشده: سه اندیکاتورِ hybrid باید نوسان‌گرِ واقعی در پنلِ خودش
 * داشته باشند، و عددِ آن نوسان‌گر باید دقیقاً همان عددی باشد که اورلیِ سیگنال روی
 * چارت برایش تصمیم می‌گیرد.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { calculateEMA, calculateRSI } from '../../overlays/userIndicators';
import { ADVANCED_INDICATORS_REGISTRY } from '../../overlays/advancedTradingIndicators';
import { USER_INDICATORS_REGISTRY } from '../../overlays/userIndicators';
import { useTechnicalStore } from '../../model/technicalStore';
import { OSCILLATOR_NAMES, OSCILLATOR_TEMPLATES, oscillatorPaneId, registerOscillatorIndicators } from '../oscillatorIndicators';

const captured = new Map<string, any>();

vi.mock('klinecharts', () => ({
  registerIndicator: vi.fn((template: any) => {
    captured.set(template.name, template);
  }),
  registerOverlay: vi.fn(),
}));

/** سریِ نوسانیِ ۷۰ کندلی؛ RSI در آن به اندازه کافی بالا و پایین می‌رود */
function buildCandles() {
  return Array.from({ length: 70 }, (_, i) => {
    const wave = Math.sin(i / 4.5) * 60 + Math.sin(i / 1.7) * 12;
    const mid = 1000 + wave;
    const high = mid + 14;
    const low = mid - 14;
    const close = mid + 5;
    return { timestamp: 1730000000000 + i * 86400000, open: mid - 5, high, low, close, volume: 100000 + i };
  });
}

function runCalc(name: (typeof OSCILLATOR_NAMES)[number], dataList = buildCandles()) {
  const template = OSCILLATOR_TEMPLATES[name];
  const indicator = { name, calcParams: [...(template.calcParams ?? [])], figures: template.figures };
  return template.calc?.(dataList as any, indicator as any) as Record<string, number | undefined>[];
}

function figureKeys(name: (typeof OSCILLATOR_NAMES)[number]) {
  return (OSCILLATOR_TEMPLATES[name].figures ?? []).map((f: any) => f.key as string);
}

describe('oscillator indicators (the missing hybrid half)', () => {
  beforeEach(() => {
    captured.clear();
    useTechnicalStore.getState().reset();
  });

  it('registers one native indicator per hybrid name', () => {
    registerOscillatorIndicators();
    for (const name of OSCILLATOR_NAMES) {
      expect(captured.has(name)).toBe(true);
    }
  });

  it('the oscillator list matches exactly the registries declared hybrids', () => {
    const declaredHybrids = [...ADVANCED_INDICATORS_REGISTRY, ...USER_INDICATORS_REGISTRY]
      .filter((i) => i.category === 'hybrid')
      .map((i) => i.id)
      .sort();
    expect([...OSCILLATOR_NAMES].sort()).toEqual(declaredHybrids);
  });

  it('every pane gets its own stable pane id', () => {
    expect(oscillatorPaneId('RsiMaSmooth')).toBe('osc_RsiMaSmooth');
    expect(new Set(OSCILLATOR_NAMES.map(oscillatorPaneId)).size).toBe(OSCILLATOR_NAMES.length);
  });

  it('the y axis of every oscillator is fixed 0..100', () => {
    for (const name of OSCILLATOR_NAMES) {
      const t = OSCILLATOR_TEMPLATES[name];
      expect(t.minValue).toBe(0);
      expect(t.maxValue).toBe(100);
    }
  });

  it('every declared figure actually receives data', () => {
    // این تست همان باگِ کلیدِ اشتباه را می‌گیرد: calc یک نام می‌نوشت و figures
    // نامِ دیگر، پس آن خط هرگز رسم نمی‌شد و تستِ عددی هم چیزی نمی‌دید.
    for (const name of OSCILLATOR_NAMES) {
      const rows = runCalc(name);
      for (const key of figureKeys(name)) {
        const defined = rows.filter((r) => r[key] !== undefined && Number.isFinite(r[key])).length;
        expect(defined, `${name}.${key} هیچ مقداری تولید نکرد`).toBeGreaterThan(0);
      }
    }
  });

  it('RsiMaSmooth shows the very EMA the divergence overlay decides on', () => {
    const candles = buildCandles();
    const closes = candles.map((c) => c.close);
    const expectedRsi = calculateRSI(closes, 14);
    const expectedMa = calculateEMA(expectedRsi, 9);

    const rows = runCalc('RsiMaSmooth', candles);
    expect(rows).toHaveLength(candles.length);

    // قبل از دورۀ گرمایش هیچ خطی نباید باشد، وگرنه ۵۰ِ پیش‌فرض صاف کشیده می‌شود
    for (let i = 0; i < 14; i++) {
      expect(rows[i].rsi).toBeUndefined();
      expect(rows[i].mid ?? rows[i].ma).toBeUndefined();
    }

    for (let i = 14; i < candles.length; i++) {
      expect(rows[i].rsi).toBeCloseTo(expectedRsi[i], 10);
      expect(rows[i].ma).toBeCloseTo(expectedMa[i], 10);
    }
  });

  it('RsiMaSmooth never leaves the 0..100 band', () => {
    for (const name of OSCILLATOR_NAMES) {
      for (const row of runCalc(name)) {
        for (const v of Object.values(row)) {
          if (v === undefined) continue;
          expect(v).toBeGreaterThanOrEqual(0);
          expect(v).toBeLessThanOrEqual(100);
        }
      }
    }
  });

  it('MultiVariantRSI follows the dropdown: period, levels and bands', () => {
    const store = useTechnicalStore.getState();

    store.setRsiVariant('fibo');
    const fibo = runCalc('MultiVariantRSI');
    expect(fibo[7].rsi).toBeUndefined();
    expect(fibo[8].rsi).toBeDefined();
    expect(fibo[40].lo).toBe(23.6);
    expect(fibo[40].hi).toBe(78.6);

    store.setRsiVariant('standard');
    const std = runCalc('MultiVariantRSI');
    expect(std[8].rsi).toBeUndefined();
    expect(std[40].rsi).toBeDefined();
    expect(std[40].lo).toBe(30);
    expect(std[40].hi).toBe(70);

    store.setRsiVariant('bb');
    const bb = runCalc('MultiVariantRSI');
    expect(bb[19].rsi).toBeUndefined();
    expect(bb[20].rsi).toBeDefined();
    expect(bb[40].upper ?? bb[40].hi).toBeGreaterThan(bb[40].mid as number);
    expect(bb[40].lower ?? bb[40].lo).toBeLessThan(bb[40].mid as number);

    store.setRsiVariant('smooth_ma');
    const sm = runCalc('MultiVariantRSI');
    expect(sm[40].mid).toBeDefined();
    // همان SMA(9) روی آرایۀ خام که اورلیِ تقاطع استفاده می‌کند
    const raw = calculateRSI(buildCandles().map((c) => c.close), 14);
    let sum = 0;
    for (let j = 0; j < 9; j++) sum += raw[40 - j];
    expect(sm[40].mid).toBeCloseTo(sum / 9, 10);
  });

  it('the panes speak the TradingView palette, not klinecharts defaults', () => {
    // بی‌styles، klinecharts پالتِ پیش‌فرضش را به ترتیبِ figure می‌دهد
    // (#FF9600 #935EBD #1677FF #E11D74 #01C5C4) و پنل به همان رنگی می‌شد که
    // «شبیه TradingView نیست» گفته شد. این نگهبانِ همان است.
    const KL_DEFAULTS = ['#ff9600', '#935ebd', '#1677ff', '#e11d74', '#01c5c4'];
    for (const name of OSCILLATOR_NAMES) {
      const lines = (OSCILLATOR_TEMPLATES[name].styles as any)?.lines ?? [];
      expect(lines.length, `${name} هیچ styles.lines ندارد`).toBeGreaterThan(0);
      const colors = lines.map((l: any) => String(l.color).toLowerCase());
      for (const c of colors) expect(KL_DEFAULTS).not.toContain(c);
      expect(colors).toContain('#ef5350');
      expect(colors).toContain('#787b86');
    }
  });

  it('the legend lists data series only, never the threshold levels', () => {
    for (const name of OSCILLATOR_NAMES) {
      const source = OSCILLATOR_TEMPLATES[name].createTooltipDataSource as any;
      expect(typeof source, `${name} createTooltipDataSource ندارد`).toBe('function');
      const rows = runCalc(name);
      const data = source({
        indicator: { result: rows, calcParams: OSCILLATOR_TEMPLATES[name].calcParams },
        crosshair: { dataIndex: 60 },
      });
      const titles = data.legends.map((l: any) => l.title.text);
      expect(titles).toContain('RSI');
      for (const t of titles) expect(['۳۰', '۷۰', 'کف', 'سقف', 'پایین', 'بالا']).not.toContain(t);
    }
  });
});
