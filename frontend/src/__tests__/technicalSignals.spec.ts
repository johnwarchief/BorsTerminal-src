// تست سیگنال FTS: استک مووینگ و تریگر جت و گیت ریسک
import { describe, expect, it } from 'vitest';
import { BaseSignal, TechnicalPayload } from '@contracts/index';
import { TECH_VALID_MS, technicalSignal, type TechInput } from '@features/technical/signals/technicalSignals';

function input(patch: Partial<TechInput> = {}): TechInput {
  const n = 120;
  const closes = Array.from({ length: n }, (_, i) => 100 + i);
  return {
    symbol: 'فولاد',
    opens: closes.map((c) => c - 0.5),
    closes,
    highs: closes.map((c) => c + 1),
    lows: closes.map((c) => c - 1),
    volumes: new Array(n).fill(1000),
    riskGatePass: true,
    enforceRiskGates: true,
    ...patch,
  };
}

describe('سیگنال FTS', () => {
  it('روند صعودی با استک سالم صعودی می دهد', () => {
    const s = technicalSignal(input(), 1726000000000);
    expect(s.direction).toBe('bullish');
    expect(s.payload.setups).toContain('trend');
    expect(s.payload.stopLossRef).toBe('ma14');
    expect(s.payload.stopLossPrice).not.toBeNull();
    expect(s.validForMs).toBe(TECH_VALID_MS);
    expect(BaseSignal.safeParse(s).success).toBe(true);
    expect(TechnicalPayload.safeParse(s.payload).success).toBe(true);
  });

  it('شکست خط آبی با حجم تریگر پرواز می دهد', () => {
    const n = 103;
    const closes = [...new Array(n - 3).fill(100), 105, 108, 112];
    const s = technicalSignal(
      input({
        opens: [...new Array(n - 3).fill(99.5), 104, 107, 110],
        closes,
        highs: [...new Array(n - 3).fill(101), 105, 108, 112],
        lows: [...new Array(n - 3).fill(99), 103, 106, 109],
        volumes: [...new Array(n - 3).fill(1000), 1000, 1000, 5000],
      }),
      1726000000000,
    );
    expect(s.direction).toBe('bullish');
    expect(s.payload.setups).toContain('breakout');
    expect(s.score as number).toBeGreaterThanOrEqual(70);
  });

  it('گیت ریسک مردود جلوی پرواز را می گیرد', () => {
    const n = 103;
    const jetPatch = {
      opens: [...new Array(n - 3).fill(99.5), 104, 107, 110],
      closes: [...new Array(n - 3).fill(100), 105, 108, 112],
      highs: [...new Array(n - 3).fill(101), 105, 108, 112],
      lows: [...new Array(n - 3).fill(99), 103, 106, 109],
      volumes: [...new Array(n - 3).fill(1000), 1000, 1000, 5000],
    };
    const blocked = technicalSignal(input({ ...jetPatch, riskGatePass: false }), 1726000000000);
    expect(blocked.direction).toBe('neutral');
    expect(blocked.payload.setups).toEqual([]);
    expect(blocked.score).toBe(50);
    expect(blocked.confidence).toBe('low');
    expect(blocked.rationale).toContain('گیت ریسک');

    const unknown = technicalSignal(input({ ...jetPatch, riskGatePass: null }), 1726000000000);
    expect(unknown.direction).toBe('bullish');
  });

  it('خط چین قرمز نزولی هشدار خروج می دهد', () => {
    const n = 48;
    const closes = new Array(n).fill(100);
    const highs = new Array(n).fill(101);
    const lows = new Array(n).fill(99);
    highs[20] = 105;
    highs[30] = 110;
    const tailCloses = [100, 99, 98, 97, 98, 99, 100, 96, 94, 92, 90, 86];
    const tailLows = [91, 90, 89, 88, 89, 90, 91, 87, 87, 87, 87, 86];
    for (let i = 0; i < 12; i++) {
      closes[n - 12 + i] = tailCloses[i];
      lows[n - 12 + i] = tailLows[i];
      highs[n - 12 + i] = tailCloses[i] + 1;
    }
    const s = technicalSignal(
      input({ opens: closes.map((c) => c + 0.2), closes, highs, lows, volumes: new Array(n).fill(1000) }),
      1726000000000,
    );
    expect(s.payload.setups).toContain('choch');
    expect(s.direction).toBe('bearish');
  });

  it('تاریخچه کوتاه اعتماد پایین و کیفیت جزئی می گیرد', () => {
    const s = technicalSignal(
      input({ opens: new Array(20).fill(99.5), closes: new Array(20).fill(100), highs: new Array(20).fill(101), lows: new Array(20).fill(99), volumes: new Array(20).fill(500) }),
      1726000000000,
    );
    expect(s.confidence).toBe('low');
    expect(s.payload.dataQuality).toBe('partial');
    expect(BaseSignal.safeParse(s).success).toBe(true);
  });

  it('تاریخچه خالی خنثی ناقص می دهد', () => {
    const s = technicalSignal(
      { symbol: 'فولاد', opens: [], closes: [], highs: [], lows: [], volumes: [], riskGatePass: null, enforceRiskGates: true },
      1726000000000,
    );
    expect(s.direction).toBe('neutral');
    expect(s.confidence).toBe('nodata');
    expect(s.score).toBeNull();
    expect(s.payload.dataQuality).toBe('incomplete');
  });
});
