import { describe, expect, it, beforeEach, vi } from 'vitest';
import {
  normSymbol,
  symbolKey,
  resolveSymbolIdentity,
  __resetIdentityRegistryForTest,
  calculateIdentityStats,
} from '../shared/api/local/symbolIdentity';
import * as localData from '../shared/api/local/localData';

describe('symbolIdentity local module', () => {
  beforeEach(() => {
    __resetIdentityRegistryForTest();
    vi.restoreAllMocks();
  });

  it('normalizes arabic letters to persian correctly', () => {
    expect(normSymbol('شستاي')).toBe('شستای');
    expect(normSymbol('بانك')).toBe('بانک');
    expect(normSymbol('موسي')).toBe('موسی');
  });

  it('generates uniform identity keys ignoring spaces and invisible separators', () => {
    const raw1 = 'شهر فرش';
    const raw2 = 'شهر\u200cفرش'; // نیم‌فاصله
    const raw3 = 'شهر\u00a0فرش'; // non-breaking space
    const raw4 = 'شهر\u200f فرش'; // RLM + space

    const k1 = symbolKey(raw1);
    const k2 = symbolKey(raw2);
    const k3 = symbolKey(raw3);
    const k4 = symbolKey(raw4);

    expect(k1).toBe('شهرفرش');
    expect(k2).toBe('شهرفرش');
    expect(k3).toBe('شهرفرش');
    expect(k4).toBe('شهرفرش');
  });

  it('distinguishes single digit line suffixes and preserves multi-digit symbols', async () => {
    vi.spyOn(localData, 'query').mockResolvedValue([
      { l_val18: 'آباد', isin: 'IRO1ABAD0001' },
      { l_val18: 'آباد3', isin: 'IRO1ABAD0002' },
      { l_val18: 'اراد275', isin: 'IRO1ARAD2751' },
    ]);

    const resSingle = await resolveSymbolIdentity('آباد3');
    expect(resSingle.hasLineSuffix).toBe(true);
    expect(resSingle.baseKey).toBe('آباد');
    expect(resSingle.key).toBe('آباد3');
    // ISIN prefix matches (IRO1ABAD)
    expect(resSingle.evidence).toBe('isin-agree');
    expect(resSingle.resolved).toBe(true);

    const resMulti = await resolveSymbolIdentity('اراد275');
    expect(resMulti.hasLineSuffix).toBe(false);
    expect(resMulti.baseKey).toBe('اراد275');
    expect(resMulti.evidence).toBe('exact');
  });

  it('detects isin-clash when line and base have completely conflicting ISINs', async () => {
    vi.spyOn(localData, 'query').mockResolvedValue([
      { l_val18: 'كم ر', isin: 'IRO1KMR00001' },
      { l_val18: 'كم ر1', isin: 'IRO1DIFF0001' },
    ]);

    const res = await resolveSymbolIdentity('كم ر1');
    expect(res.hasLineSuffix).toBe(true);
    expect(res.evidence).toBe('isin-clash');
    expect(res.resolved).toBe(false);
  });

  it('handles no-isin when only one side has ISIN', async () => {
    vi.spyOn(localData, 'query').mockResolvedValue([
      { l_val18: 'خودرو', isin: 'IRO1IKCO0001' },
      { l_val18: 'خودرو2', isin: null },
    ]);

    const res = await resolveSymbolIdentity('خودرو2');
    expect(res.hasLineSuffix).toBe(true);
    expect(res.evidence).toBe('no-isin');
    expect(res.resolved).toBe(true);
  });

  it('calculates registry stats correctly', async () => {
    vi.spyOn(localData, 'query').mockResolvedValue([
      { l_val18: 'آباد', isin: 'IRO1ABAD0001' },
      { l_val18: 'آباد3', isin: 'IRO1ABAD0002' },
      { l_val18: 'خودرو', isin: 'IRO1IKCO0001' },
      { l_val18: 'خودرو2', isin: null },
      { l_val18: 'فولاد', isin: 'IRO1FOLD0001' },
    ]);

    const stats = await calculateIdentityStats();
    expect(stats.totalInstruments).toBe(5);
    expect(stats.uniqueSymbols).toBe(5);
    expect(stats.lineSymbols).toBe(2);
    expect(stats.isinAgree).toBe(1);
    expect(stats.noIsin).toBe(1);
    expect(stats.isinClash).toBe(0);
  });
});
