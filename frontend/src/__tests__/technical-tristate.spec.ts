/** سه‌حالۀ سیگنالِ تکنیکال در فرانت (دورِ «موتور تکنیکال»).
 *
 *  قاعدۀ مالک: «null یا عدم‌محاسبه را هرگز به false تبدیل نکن». سه جا این
 *  تبدیل اتفاق می‌افتاد و اینجا قفل می‌شود:
 *    ۱) `technicalSignals` — پرچم‌هایِ ستاپ
 *    ۲) `patternInputsFromFts` — ورودیِ نگاشتِ چارت
 *    ۳) `ftsPipelineEvaluator` — گامِ Tِ قیف
 *  و در مقابلش: «موتور چیزی نگفت» با «موتور گفت نیست» باید در UI فرق داشته
 *  باشد، پس هیچ‌جا صفرِ جانشین یا برچسبِ «مردود» ساخته نمی‌شود.
 */
import { describe, expect, it } from 'vitest';
import { technicalSignal } from '@features/technical/signals/technicalSignals';
import { patternInputsFromFts } from '@features/technical/lib/patternOverlays';
import type { FtsAnalysisData } from '@features/technical/api/useFtsAnalysis';

const closes = Array.from({ length: 80 }, (_, i) => 100 + i);

function input(fts: unknown) {
  return {
    symbol: 'شپنا',
    opens: closes, closes, highs: closes.map((c) => c + 1),
    lows: closes.map((c) => c - 1), volumes: closes.map(() => 10),
    riskGatePass: null, enforceRiskGates: false,
    fts: fts as FtsAnalysisData | null | undefined,
  };
}

/** موتور می‌گوید «سنجیده نشد» — هیچ‌کدام از ستاپ‌ها رأی ندارند */
const PENDING: Record<string, unknown> = {
  trend: { D: { trend: 'na' }, W: { trend: 'na' }, M: { trend: 'na' }, alignment: 'na' },
  jet: { active: null, resistance: null, ceiling: null, static_broke: null, tier: null,
         reason: 'تاریخچه به ۶۰ نشست نمی‌رسد' },
  choch: { bearish: null, bullish: null, level: null },
  point_hunt: { active: null, touches: null, floor_price: null },
  double_bottom: { active: null, neckline: null },
  range_box: { active: null, top: null },
  hourglass: { active: null, action: 'UNKNOWN' },
  fib: null,
  setups: [],
};

describe('پرچم‌هایِ ستاپ سه‌حالۀ می‌مانند', () => {
  it('موتور «سنجیده نشد» گفت ⇒ null منتشر می‌شود، نه false', () => {
    const p = technicalSignal(input(PENDING)).payload as Record<string, unknown>;
    for (const k of ['jet_active', 'choch_bullish', 'point_hunt_active',
                     'double_bottom_active', 'range_break_active', 'hourglass_active']) {
      expect(p[k], k).toBeNull();
    }
  });

  it('موتور «نیست» گفت ⇒ همان false می‌ماند (با null قاطی نمی‌شود)', () => {
    const p = technicalSignal(input({
      ...PENDING,
      jet: { active: false, resistance: 120, static_broke: false, tier: 'none' },
      choch: { bearish: false, bullish: false, level: 118 },
      point_hunt: { active: false, touches: 4, floor_price: 101 },
      hourglass: { active: false, action: 'NORMAL' },
    })).payload as Record<string, unknown>;
    expect(p.jet_active).toBe(false);
    expect(p.point_hunt_active).toBe(false);
    expect(p.hourglass_active).toBe(false);
  });

  it('پاسخِ تکنیکال اصلاً نیامده ⇒ پرچم منتشر **نمی‌شود** (undefined)', () => {
    const p = technicalSignal(input(null)).payload as Record<string, unknown>;
    expect('jet_active' in p).toBe(false);
    expect('hourglass_active' in p).toBe(false);
  });

  it('موتور «هست» گفت ⇒ true', () => {
    const p = technicalSignal(input({
      ...PENDING, jet: { active: true, resistance: 118, ceiling: 120,
                         static_broke: true, tier: 'strong' },
    })).payload as Record<string, unknown>;
    expect(p.jet_active).toBe(true);
  });
});

describe('نگاشتِ چارت از رأیِ تهی عدد نمی‌سازد', () => {
  const view = {
    toDisp: (p: number) => p,
    tsForDate: (d: string) => new Date(d + 'T12:00:00Z').getTime(),
  };

  it('موتور چیزی نگفت ⇒ هیچ سطحی نمی‌خواند و هیچ مارکری نمی‌نشیند', () => {
    const inp = patternInputsFromFts(PENDING as unknown as FtsAnalysisData, view);
    expect(inp.jet.active).toBe(false);
    expect(inp.jet.level).toBeNull();
    expect(inp.pointHunt.floor).toBeNull();
    expect(inp.pointHunt.ts).toBeNull();
    expect(inp.choch.level).toBeNull();
  });

  it('سطحِ جت از همان `resistance`ِ سرور می‌آید (بدونِ دست‌کاری)', () => {
    const inp = patternInputsFromFts({
      ...PENDING, jet: { active: true, resistance: 118, ceiling: 140,
                         static_broke: true, tier: 'strong' },
    } as unknown as FtsAnalysisData, view);
    expect(inp.jet.active).toBe(true);
    expect(inp.jet.level).toBe(118);
  });
});
