import { describe, expect, it } from 'vitest';
import type { EngineCandle } from '../../doubleTapEngine';
import { EVENT_CONFIG } from '../config';
import { detectSrRetest } from '../zone';

const CFG = EVENT_CONFIG.srRetest;

interface PathPoint { index: number; price: number }

/** مسیر خطی با ویک ۰٫۳؛ پیوت‌ها با pivotLen=7 تأیید می‌شوند. */
function pathCandles(anchors: PathPoint[], lastPrice = anchors[anchors.length - 1].price, total = 160): EngineCandle[] {
  const bars: EngineCandle[] = [];
  for (let i = 0; i < total; i++) {
    let price = lastPrice;
    for (let a = 0; a < anchors.length - 1; a++) {
      const from = anchors[a];
      const to = anchors[a + 1];
      if (i >= from.index && i <= to.index) {
        const t = to.index === from.index ? 0 : (i - from.index) / (to.index - from.index);
        price = from.price + (to.price - from.price) * t;
        break;
      }
      if (i > anchors[anchors.length - 1].index) price = lastPrice;
      if (i > anchors[anchors.length - 1].index) break;
    }
    bars.push({
      timestamp: 1_700_000_000_000 + i * 86_400_000,
      open: price - 0.05,
      high: price + 0.3,
      low: price - 0.3,
      close: price,
      volume: 1_000,
    });
  }
  return bars;
}

/**
 * سناریوی پایه: سقف‌های ۱۰۰ در ۳۰ و ۷۰، کف‌های ۹۰ در ۵۰ و ۹۰، شکست بالا در ۱۰۰–۱۰۴،
 * ریتست در ۱۰۶ (لمس زون و بستهٔ بالای کف).
 */
function breakRetestFixture(): EngineCandle[] {
  const bars = pathCandles([
    { index: 0, price: 94 },
    { index: 30, price: 100 },
    { index: 50, price: 90 },
    { index: 70, price: 100 },
    { index: 90, price: 90 },
    { index: 100, price: 100.8 },
    { index: 104, price: 101.5 },
    { index: 106, price: 99.8 },
    { index: 115, price: 102 },
    { index: 130, price: 102 },
  ], 102, 131);
  // OHLC دقیق دو پیوت سقف برای ضخامت قابل‌انتظار.
  bars[30] = { ...bars[30], open: 99.8, high: 100.3, low: 99.6, close: 100 };
  bars[70] = { ...bars[70], open: 99.9, high: 100.3, low: 99.7, close: 100.1 };
  return bars;
}

describe('detectSrRetest — p21 zones', () => {
  it('builds the two-swing resistance zone with o/h/l/c thickness', () => {
    const zones = detectSrRetest(breakRetestFixture(), CFG);
    const resistance = zones.find((z) => z.fromIndex === 30);
    expect(resistance).toBeTruthy();
    // edge = max(h) = 100.3؛ ضخامت = max فاصلهٔ o/h/l/c دو پیوت (۰٫۷).
    expect(resistance!.upper).toBeCloseTo(100.3, 6);
    expect(resistance!.lower).toBeCloseTo(99.6, 6);
    expect(resistance!.volumeBalanceAvailable).toBe(false);
  });

  it('rejects a zone that overlaps an existing zone in both price and time', () => {
    const zones = detectSrRetest(breakRetestFixture(), CFG);
    // زون دوم از سقف ۷۰ به بعد در زمان و قیمت با زون اول هم‌پوشانی دارد.
    expect(zones.filter((z) => z.fromIndex === 70)).toHaveLength(0);
  });

  it('emits exactly one bullish retest at the expected bar after the clean break', () => {
    const zones = detectSrRetest(breakRetestFixture(), CFG);
    const retests = zones.filter((z) => z.state === 3 && z.direction === 'bullish');
    expect(retests).toHaveLength(1);
    expect(retests[0].retestIndex).toBe(106);
    // پاین: از حالت «کاملاً زیر زون» با اولین بستهٔ بالای زون وارد ±2 می‌شود.
    expect(retests[0].breakoutIndex).toBe(100);
    expect(retests[0].fromIndex).toBe(30);
  });

  it('expires an unfinished zone after expiryBars', () => {
    const zones = detectSrRetest(breakRetestFixture(), { ...CFG, expiryBars: 20 });
    expect(zones.some((z) => z.fromIndex === 30)).toBe(false);
  });

  it('reverts a failed break back to state 0 instead of firing a signal', () => {
    const bars = pathCandles([
      { index: 0, price: 94 },
      { index: 30, price: 100 },
      { index: 50, price: 90 },
      { index: 70, price: 100 },
      { index: 90, price: 90 },
      { index: 100, price: 100.8 },
      // تا ۱۰۳ کاملاً بالای زون می‌ماند تا ریتستِ زودهنگام رخ ندهد.
      { index: 101, price: 102.5 },
      { index: 103, price: 102.5 },
      { index: 104, price: 99 },
      { index: 110, price: 99.5 },
      { index: 130, price: 99.5 },
    ], 99.5, 131);
    bars[30] = { ...bars[30], open: 99.8, high: 100.3, low: 99.6, close: 100 };
    bars[70] = { ...bars[70], open: 99.9, high: 100.3, low: 99.7, close: 100.1 };
    const zones = detectSrRetest(bars, CFG);
    const resistance = zones.find((z) => z.fromIndex === 30);
    expect(resistance).toBeTruthy();
    expect([0, -1]).toContain(resistance!.state);
    expect(resistance!.retestIndex).toBeUndefined();
  });
});
