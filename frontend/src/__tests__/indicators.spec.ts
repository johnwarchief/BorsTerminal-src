// تست شاخص های FTS: چهار مووینگ و سوینگ و خط آبی و قرمز
import { describe, expect, it } from 'vitest';
import {
  avgVolume,
  detectChoch,
  ema,
  ftsMAs,
  majorResistance,
  majorSupport,
  maStack,
  sma,
  swingHighs,
  swingLows,
} from '@features/technical/lib/indicators';

describe('میانگین ها و استک', () => {
  it('SMA پنج تایی', () => {
    expect(sma([1, 2, 3, 4, 5, 6], 5)).toEqual([null, null, null, null, 3, 4]);
  });

  it('EMA با بذر میانگین ساده', () => {
    expect(ema([10, 11, 12, 13, 14], 3)).toEqual([null, null, 11, 12, 13]);
  });

  it('چهار مووینگ FTS ساخته می شود', () => {
    const closes = Array.from({ length: 110 }, (_, i) => 100 + i);
    const mas = ftsMAs(closes);
    expect(mas[14][109]).toBeCloseTo(209 - 6.5, 4);
    expect(mas[100][109]).toBeCloseTo(209 - 49.5, 4);
    expect(maStack(mas[14][109], mas[21][109], mas[52][109], mas[100][109])).toBe('bull');
  });

  it('استک نزولی و درهم و نامشخص', () => {
    expect(maStack(90, 100, 110, 120)).toBe('bear');
    expect(maStack(100, 90, 110, 120)).toBe('mixed');
    expect(maStack(null, 90, 110, 120)).toBe('unknown');
  });
});

describe('سوینگ و خطوط', () => {
  const highs = [5, 6, 8, 7, 6, 7, 9, 12, 10, 9, 8, 9, 10, 9, 8];
  const lows = [6, 5, 3, 5, 6, 7, 6, 4, 6, 7, 8, 8, 8, 2, 8, 8, 8, 8, 8];

  it('فرکتال سقف و کف', () => {
    expect(swingHighs(highs, 2).map((s) => s.index)).toEqual([2, 7, 12]);
    expect(swingLows(lows, 2).map((s) => s.index)).toEqual([2, 7, 13]);
  });

  it('خط آبی بالاترین سوینگ ماژور است', () => {
    expect(majorResistance(highs, 120)?.price).toBe(12);
    expect(majorSupport(lows, 120)?.price).toBe(2);
    expect(majorResistance([], 120)).toBeNull();
  });

  it('میانگین حجم و تهی', () => {
    expect(avgVolume([10, 20, 30], 3)).toBe(20);
    expect(avgVolume([null, null], 5)).toBeNull();
  });
});

describe('خط چین قرمز', () => {
  it('شکست کف پس از سقف های صعودی هشدار نزولی می دهد', () => {
    const highs = [100, 100, 100, 100, 100, 105, 100, 100, 100, 100, 100, 110, 100, 100, 100, 100, 100];
    const lows = [98, 98, 98, 98, 98, 98, 98, 98, 96, 98, 98, 98, 98, 98, 97, 98, 98];
    const closes = [99, 99, 99, 99, 99, 100, 99, 99, 98, 99, 99, 100, 99, 99, 98, 97, 95];
    const c = detectChoch(highs, lows, closes, 2);
    expect(c.type).toBe('bearish');
    expect(c.level).toBe(97);
  });

  it('شکست سقف پس از کف های نزولی هشدار صعودی می دهد', () => {
    const lows = [100, 100, 100, 100, 100, 95, 100, 100, 100, 100, 100, 90, 100, 100, 100, 100, 100];
    const highs = [102, 102, 102, 102, 102, 102, 102, 102, 104, 102, 102, 102, 102, 102, 103, 102, 102];
    const closes = [101, 101, 101, 101, 101, 100, 101, 101, 102, 101, 101, 100, 101, 101, 102, 103, 105];
    const c = detectChoch(highs, lows, closes, 2);
    expect(c.type).toBe('bullish');
    expect(c.level).toBe(103);
  });

  it('بدون ساختار هشدار نیست', () => {
    const flat = new Array(20).fill(100);
    expect(detectChoch(flat, flat, flat, 2).type).toBeNull();
  });
});
