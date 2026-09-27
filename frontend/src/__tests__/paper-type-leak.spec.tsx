// Regression test for the paper_type=8 misclassification bug.
//
// TSETMC's paperType filter is unstable: in a real sync (2026-09-22) the
// pt=8 (fund) response contained 1,168 ordinary operating companies —
// فولاد, وبملت, شستا, شپنا, فملي, خگستر — while the pt=1 response listed
// those same symbols as stocks. fetch_paper_types() keeps the most specific
// class (rank 8 > 1), so those companies were permanently stored as funds.
//
// The visible damage: the "پنجاه شرکت بزرگ" pulse card was always empty
// (zero stocks existed to rank), and the fund rows were inflated ~47x.
//
// The fix makes pt=8 advisory only: an instrument is a fund when its
// name/sector says so, otherwise pt=8 falls through to stock/right.
import { describe, it, expect } from 'vitest';

// Mirror of mstat_engine.classify() — the frontend assetType logic this
// must stay in step with.
const PAPER_STOCK = 'stock';
const PAPER_RIGHT = 'right';
const PAPER_FUND = 'fund';

function norm(s: string): string {
  return (s || '').replace(/ي/g, 'ی').replace(/ك/g, 'ک').replace(/\u200c/g, ' ');
}

function isFund(name: string, sector: string): boolean {
  const n = norm(name), s = norm(sector);
  return n.includes('صندوق') || s.includes('صندوق سرمايه گذاري')
      || s.includes('صندوق سرمایه گذاری');
}

// The contract the board relies on: never classify a real operating
// company as a fund just because TSETMC's pt=8 bucket leaked it in.
export function classify(paperType: number | null, name = '', symbol = '', sector = ''): [string, string] {
  const s18 = norm(symbol), s30 = norm(name);
  if (s18.toUpperCase().endsWith('ح') || s30.includes('حق تقدم')) return [PAPER_RIGHT, 'right'];
  if (paperType === 1 || paperType === 2) return [PAPER_STOCK, 'stock'];
  if (paperType === 4) return [PAPER_RIGHT, 'right'];
  if (paperType === 8) {
    if (isFund(name, sector)) return [PAPER_FUND, 'etf'];
    if (s18.toUpperCase().endsWith('ح') || s30.includes('حق تقدم')) return [PAPER_RIGHT, 'right'];
    return [PAPER_STOCK, 'stock'];
  }
  return ['other', 'other'];
}

describe('paper_type=8 leak — real companies must not become funds', () => {
  it('classifies an ordinary company stored as pt=8 as a stock', () => {
    // These were all stored paper_type=8 in market.db while TSETMC said pt=1.
    const leaked = [
      ['فولاد', 'فولاد مباركه اصفهان', 'فلزات اساسي'],
      ['وبملت', 'بانك ملت', 'بانك ها'],
      ['شستا', 'سرمايه گذاري تامين اجتماعي', 'بانك و موسسات اعتباري'],
      ['شپنا', 'پالايش نفت اصفهان', 'پالايش و پخش فرآورده هاي نفتي'],
      ['فملي', 'ملی صنایع مس ایران', 'فلزات اساسي'],
      ['خگستر', 'گسترش صنایع روی ایرانیان', 'فلزات اساسي'],
    ];
    for (const [sym, name, sector] of leaked) {
      const [cls] = classify(8, name, sym, sector);
      expect(cls, `${sym} must be a stock, not a fund`).toBe(PAPER_STOCK);
    }
  });

  it('still recognises a genuine fund stored as pt=8', () => {
    expect(classify(8, 'صندوق س.درآمد ثابت دينا-د', 'دينا', 'صندوق سرمايه گذاري قابل معامله')[0])
      .toBe(PAPER_FUND);
    expect(classify(8, 'صندوق س.سهام آواي معيار-س', 'آوا', 'صندوق سرمايه گذاري قابل معامله')[0])
      .toBe(PAPER_FUND);
  });

  it('keeps the plain paperType paths intact', () => {
    expect(classify(1, 'x', 'y')[0]).toBe(PAPER_STOCK);
    expect(classify(2, 'x', 'y')[0]).toBe(PAPER_STOCK);
    expect(classify(4, 'x', 'y')[0]).toBe(PAPER_RIGHT);
    expect(classify(null, 'a', 'b')[0]).toBe('other');
  });

  it('top50 has stocks to rank once the leak is sealed', () => {
    // Before the fix, zero rows had cls=='stock', so top50_codes() returned
    // an empty set and the card showed nothing.
    const universe: [string, string, string][] = [
      ['فولاد', 'فولاد مباركه اصفهان', 'فلزات اساسي'],
      ['دينا', 'صندوق س.درآمد ثابت دينا-د', 'صندوق سرمايه گذاري قابل معامله'],
    ];
    const stocks = universe.filter(
      ([s, n, sec]) => classify(8, n, s, sec)[0] === PAPER_STOCK);
    expect(stocks.length).toBeGreaterThan(0);
  });
});
