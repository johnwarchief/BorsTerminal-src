// __tests__/technical-drawing-registry.spec.ts
// گاردِ ابزار ترسیم: هر overlayType که تولبار به چارت می‌فرستد باید واقعاً ثبت‌شده
// باشد. تا v1.0.25 ابزارهای «الگو/گن/اندازه‌گیری» در منو بودند ولی تمپلیت‌شان هرگز
// در چارتِ فعال ثبت نمی‌شد — کلیک کاربر بی‌صدا هیچی می‌ساخت.

import { describe, expect, it } from 'vitest';

import { indicators as pkgIndicatorList, overlays as pkgOverlays } from 'react-klinecharts-ui/extensions';

import { registerFtsOverlays } from '@features/technical/lib/ftsOverlays';
import { TV_INDICATORS } from '@features/technical/lib/tvIndicatorCatalog';
import { registerTvIndicators } from '@features/technical/lib/tvIndicators';
import { registerTvOverlays, TV_OVERLAY_TOOLS } from '@features/technical/lib/tvTools';

const pkgNames = new Set((pkgOverlays as { name: string }[]).map((o) => o.name));
const pkgIndNames = new Set((pkgIndicatorList as { name: string }[]).map((i) => i.name));

describe('drawing tool registry', () => {
  it('every tool the toolbar offers has a template in the installed extension package', () => {
    const missing = TV_OVERLAY_TOOLS.filter((t) => !pkgNames.has(t.name)).map((t) => t.name);
    expect(missing, `no template for: ${missing.join(', ')}`).toEqual([]);
  });

  it('registerTvOverlays registers all of them on the chart api', () => {
    const registered: string[] = [];
    const n = registerTvOverlays({
      registerOverlay: (o) => registered.push((o as { name: string }).name),
      getSupportedOverlays: () => [],
    });
    expect(n).toBe(TV_OVERLAY_TOOLS.length);
    expect(registered.sort()).toEqual(TV_OVERLAY_TOOLS.map((t) => t.name).sort());
  });

  it('is idempotent: already-registered overlays are not re-registered', () => {
    const again: string[] = [];
    const n = registerTvOverlays({
      registerOverlay: (o) => again.push((o as { name: string }).name),
      getSupportedOverlays: () => TV_OVERLAY_TOOLS.map((t) => t.name),
    });
    expect(n).toBe(0);
    expect(again).toEqual([]);
  });

  it('FTS overlays register too (fib zones, measure, positions, corp actions)', () => {
    const registered: string[] = [];
    registerFtsOverlays({ registerOverlay: (o) => registered.push((o as { name: string }).name) });
    expect(registered.length).toBeGreaterThan(5);
    for (const name of ['ftsMeasure', 'ftsPosition', 'ftsFibLog']) {
      expect(registered, `missing ${name}`).toContain(name);
    }
  });

  it('every indicator the menu offers has a template in the installed package', () => {
    const missing = TV_INDICATORS.filter((i) => !pkgIndNames.has(i.name)).map((i) => i.name);
    expect(missing, `no indicator template for: ${missing.join(', ')}`).toEqual([]);
  });

  it('registerTvIndicators registers them once and skips supported ones', () => {
    const first: string[] = [];
    expect(registerTvIndicators({
      registerIndicator: (i) => first.push((i as { name: string }).name),
      getSupportedIndicators: () => [],
    })).toBe(TV_INDICATORS.length);
    expect(registerTvIndicators({
      registerIndicator: () => { throw new Error('must not re-register'); },
      getSupportedIndicators: () => TV_INDICATORS.map((i) => i.name),
    })).toBe(0);
  });

  it('اندیکاتورهای TV با شش موردِ درونیِ چارت نامِ یکی ندارند', () => {
    // منو = این شش + TV_INDICATORS؛ اگر نامی یکی باشد دو چک‌باکس یک id و یک
    // state می‌گیرند (کلید تکراری در React + روشن/خاموشِ اشتباه).
    const builtin = ['VOL', 'MA', 'EMA', 'RSI', 'MACD', 'BOLL'];
    const clash = TV_INDICATORS.map((i) => i.name).filter((n) => builtin.includes(n));
    expect(clash, `indicator id collision: ${clash.join(', ')}`).toEqual([]);
  });

  it('نام‌هایِ درونیِ که تولبار به کار می‌برد در موتورِ نصب‌شده هست', async () => {
    // باندلِ npm تنها منبعِ چارتِ برنامه است (باندلِ دومِ public/vendor بیرون
    // رفت)؛ اگر نسخه‌ای این نام‌ها را بردارد، createOverlay بی‌صدا هیچی می‌سازد.
    // از خودِ API می‌پرسیم، نه از grepِ باندل — grep به شکلِ فشرده‌سازی حساس است.
    const { getSupportedFigures, getSupportedOverlays } = await import('klinecharts');
    const overlays = new Set(getSupportedOverlays());
    const figures = new Set(getSupportedFigures());
    // اورلیِ آماده — این‌ها را createOverlay با نامِ خودش می‌شناسد
    const wantOverlays = ['segment', 'rayLine', 'straightLine', 'verticalStraightLine',
                          'priceChannelLine', 'fibonacciLine', 'brush', 'simpleAnnotation',
                          'horizontalStraightLine'];
    // شکلِ داخلِ اورلیِ سفارشی — rect/circle اورلی *نیستند*؛ همین تفاوت باعث شد
    // آداپترِ کمربند اول «rect» را به createOverlay بدهد و بی‌صدا هیچی نشود.
    const wantFigures = ['rect', 'circle', 'text', 'line', 'polygon'];
    const missingOverlays = wantOverlays.filter((n) => !overlays.has(n));
    const missingFigures = wantFigures.filter((n) => !figures.has(n));
    expect(missingOverlays, `klinecharts lost overlays: ${missingOverlays.join(', ')}`).toEqual([]);
    expect(missingFigures, `klinecharts lost figures: ${missingFigures.join(', ')}`).toEqual([]);
  });
});
