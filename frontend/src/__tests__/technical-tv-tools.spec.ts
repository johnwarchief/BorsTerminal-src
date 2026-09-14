// تست ابزارهای پیشرفتهٔ TV (T-09): تمپلیت‌های واقعی بستهٔ react-klinecharts-ui + ادغام در کاتالوگ
import { describe, expect, it, vi } from 'vitest';
import { overlays } from 'react-klinecharts-ui/extensions';
import { TV_OVERLAY_TOOLS, TV_TOOL_NAMES, registerTvOverlays, tvOverlayTemplates } from '@features/technical/lib/tvTools';
import { DRAWING_CATALOG, toolDefaults, toolLabel } from '@features/technical/lib/drawingTools';

describe('تمپلیت‌های بستهٔ react-klinecharts-ui', () => {
  it('بسته واقعاً تمپلیت ارائه می‌دهد', () => {
    expect(Array.isArray(overlays)).toBe(true);
    expect(overlays.length).toBeGreaterThan(10);
  });

  it('همهٔ ابزارهای منتخب ما در بسته موجودند', () => {
    const resolved = tvOverlayTemplates();
    expect(resolved).toHaveLength(TV_OVERLAY_TOOLS.length);
    for (const r of resolved) {
      const tpl = r.template as { name?: string; createPointFigures?: unknown };
      expect(tpl.name).toBe(r.name);
      expect(typeof tpl.createPointFigures).toBe('function');
    }
  });

  it('ثبت روی نمونهٔ klinecharts ما کار می‌کند (mock api)', () => {
    const registerOverlay = vi.fn();
    const n = registerTvOverlays({ registerOverlay, getSupportedOverlays: () => [] });
    expect(n).toBe(TV_OVERLAY_TOOLS.length);
    expect(registerOverlay).toHaveBeenCalledTimes(TV_OVERLAY_TOOLS.length);
  });

  it('تمپلیت‌های از قبل ثبت‌شده دوباره ثبت نمی‌شوند', () => {
    const registerOverlay = vi.fn();
    const n = registerTvOverlays({ registerOverlay, getSupportedOverlays: () => ['measure', 'gannBox'] });
    expect(n).toBe(TV_OVERLAY_TOOLS.length - 2);
  });
});

describe('کاتالوگ ما شامل گروه ابزارهای پیشرفتهٔ TV است', () => {
  it('همهٔ نام‌ها در کاتالوگ هستند', () => {
    const names = DRAWING_CATALOG.flatMap((g) => g.tools.map((t) => t.name));
    for (const n of TV_TOOL_NAMES) expect(names).toContain(n);
  });

  it('گروه «پیشرفته (TV)» ساخته شده و برچسب فارسی دارد', () => {
    const group = DRAWING_CATALOG.find((g) => g.label === 'پیشرفته (TV)');
    expect(group).toBeTruthy();
    expect(group!.tools).toHaveLength(TV_OVERLAY_TOOLS.length);
    expect(toolLabel('gannBox')).toBe('جعبهٔ گن');
    expect(toolLabel('longPosition')).toBe('پوزیشن لانگ');
  });

  it('پیشفرض رنگ برای ابزارهای TV تعریف شده است', () => {
    const d = toolDefaults('gannFan');
    expect((d.styles as { color?: string }).color).toBe('#22d3ee');
  });
});
