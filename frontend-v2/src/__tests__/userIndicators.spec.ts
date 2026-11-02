import { describe, it, expect } from 'vitest';
import {
  USER_INDICATORS_REGISTRY,
  registerAllUserIndicators,
  registerBreakoutRetestProOverlay,
  registerSuperTrendHeikinAshiOverlay,
  registerFiboRSI8Overlay,
  registerRsiMaSmoothOverlay,
} from '../features/technical/overlays/userIndicators';

describe('userIndicators registry and overlays', () => {
  it('exports registry with all 4 user indicators', () => {
    expect(USER_INDICATORS_REGISTRY).toHaveLength(4);
    const ids = USER_INDICATORS_REGISTRY.map((i) => i.id);
    expect(ids).toContain('BreakoutRetestPro');
    expect(ids).toContain('SuperTrendHeikinAshi');
    expect(ids).toContain('FiboRSI8');
    expect(ids).toContain('RsiMaSmooth');
  });

  it('contains valid Persian descriptions and metadata', () => {
    for (const item of USER_INDICATORS_REGISTRY) {
      expect(item.id.length).toBeGreaterThan(0);
      expect(item.nameFa.length).toBeGreaterThan(0);
      expect(item.descriptionFa.length).toBeGreaterThan(0);
      expect(Object.keys(item.defaultParams).length).toBeGreaterThan(0);
      expect(typeof item.registerFn).toBe('function');
    }
  });

  it('registers all user overlays without throwing', () => {
    expect(() => registerBreakoutRetestProOverlay()).not.toThrow();
    expect(() => registerSuperTrendHeikinAshiOverlay()).not.toThrow();
    expect(() => registerFiboRSI8Overlay()).not.toThrow();
    expect(() => registerRsiMaSmoothOverlay()).not.toThrow();
    expect(() => registerAllUserIndicators()).not.toThrow();
  });
});
