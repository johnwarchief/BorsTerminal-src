/**
 * tools/indicator_param_density.mts — شمارش الگوهای Double Tap روی نمادهای پرحجم
 *
 * این اسکریپت حلقۀ تشخیصِ advancedTradingIndicators.ts را عیناً ترجمه می‌کند تا
 * نشان دهد پارامترهای هاردکدِ اورلی (pivLeft=3, pivRight=2) در برابر پارامترهای
 * تبلیغ‌شده در رجیستری (pivLeft=6, pivRight=4) چند الگو می‌سازند.
 *
 * چرا این‌کار: defaultParams در هیچ کجای برنامه خوانده نمی‌شود، پس پنل تنظیمات
 * بدون وصل‌کردنِ پارامترها تزئین است. این عدد همان استدلال است.
 *
 * Run: node --no-warnings tools/indicator_param_density.mts [--top 40]
 */
import { writeFileSync, mkdirSync } from 'node:fs';

const BASE = process.env.BORS_API || 'http://127.0.0.1:8101';
const OUT = 'C:/Users/PCMOD/Desktop/BorsTerminal/_audit/indicator-density';

function arg(flag: string, dflt: string) {
  const i = process.argv.indexOf(flag);
  return i >= 0 ? process.argv[i + 1] : dflt;
}
const topN = Number(arg('--top', '40'));

type Candle = { high: number; low: number; close: number; open: number; timestamp: number };

function atrOf(candles: Candle[], period = 14): number[] {
  const out: number[] = new Array(candles.length).fill(NaN);
  let prevClose: number | null = null;
  const trs: number[] = [];
  for (let i = 0; i < candles.length; i++) {
    const c = candles[i];
    const tr = prevClose == null ? c.high - c.low : Math.max(c.high - c.low, Math.abs(c.high - prevClose), Math.abs(c.low - prevClose));
    trs.push(tr);
    prevClose = c.close;
    if (i >= period - 1) {
      if (i === period - 1) {
        out[i] = trs.slice(0, period).reduce((a, b) => a + b, 0) / period;
      } else {
        out[i] = (out[i - 1] * (period - 1) + tr) / period;
      }
    }
  }
  return out;
}

/** عینِ حلقۀ advancedTradingIndicators.ts:177-260 برای سقف دوقلو (M) */
function countDoubleTops(candles: Candle[], p: { pivLeft: number; pivRight: number; tolAtr: number; minSpan: number; maxSpan: number; minHeightAtr: number }) {
  const n = candles.length;
  if (n < 20) return { patterns: 0, pivotHighs: 0, figures: 0 };
  const atr = atrOf(candles, 14);

  const isPivotHigh = (idx: number) => {
    const h = candles[idx].high;
    for (let j = Math.max(0, idx - p.pivLeft); j <= Math.min(n - 1, idx + p.pivRight); j++) {
      if (j !== idx && candles[j].high > h) return false;
    }
    return true;
  };
  const highs: { index: number; price: number }[] = [];
  for (let i = p.pivLeft; i < n - p.pivRight; i++) if (isPivotHigh(i)) highs.push({ index: i, price: candles[i].high });

  let patterns = 0;
  let spans: number[] = [];
  for (let q = 0; q < highs.length - 1; q++) {
    const p1 = highs[q];
    const p2 = highs[q + 1];
    const span = p2.index - p1.index;
    if (span < p.minSpan || span > p.maxSpan) continue;
    const currentAtr = atr[p2.index] || 1;
    const diff = Math.abs(p1.price - p2.price);
    if (diff > p.tolAtr * currentAtr) continue;
    let neckLow = Infinity;
    let neckIdx = -1;
    for (let k = p1.index + 1; k < p2.index; k++) {
      if (candles[k].low < neckLow) { neckLow = candles[k].low; neckIdx = k; }
    }
    const height = Math.max(p1.price, p2.price) - neckLow;
    if (height >= p.minHeightAtr * currentAtr && neckIdx !== -1) { patterns++; spans.push(span); }
  }
  // هر الگو در کدِ فعلی ۵ شکل می‌سازد: ۳ خط + برچسبِ نام + برچسبِ TP1
  return { patterns, pivotHighs: highs.length, figures: patterns * 5, medianSpan: spans.length ? spans.sort((a, b) => a - b)[Math.floor(spans.length / 2)] : 0 };
}

const HARD = { pivLeft: 3, pivRight: 2, tolAtr: 0.95, minSpan: 3, maxSpan: 120, minHeightAtr: 0.8 };
const REG = { pivLeft: 6, pivRight: 4, tolAtr: 0.85, minSpan: 3, maxSpan: 120, minHeightAtr: 1.0 };

const board = await (await fetch(`${BASE}/api/market`)).json();
const rows = (board.data ?? board).slice();
// نماد معروف = سهمِ بزرگِ اصلی. حق‌تقدم و اوراق با پسوندِ رقم کنار می‌روند،
// وگرنه «۴۰ نماد معروف» پر از حق‌تقدم می‌شود و سنجه بی‌معنی است.
const isMainEquity = (s: string) => !/\d+$/.test(s) && !/حق|تسهیم|اوراق|صندوق/.test(s);
const byCap = rows
  .filter((r: any) => typeof r.q_tot_cap === 'number' && r.q_tot_cap > 0 && r.p_last > 0 && isMainEquity(String(r.symbol)))
  .sort((a: any, b: any) => b.q_tot_cap - a.q_tot_cap)
  .slice(0, topN)
  .map((r: any) => String(r.symbol));
console.log(`symbols under test: ${byCap.length} -> ${byCap.slice(0, 12).join(', ')} …`);

const table: any[] = [];
let fail = 0;
for (const sym of byCap) {
  let candles: Candle[];
  try {
    const d = await (await fetch(`${BASE}/api/chart-db/${encodeURIComponent(sym)}?adjustment=3`)).json();
    candles = (d.candles ?? []).map((c: any) => ({ high: c.high, low: c.low, close: c.close, open: c.open, timestamp: c.time ?? c.timestamp }));
  } catch (e) { fail++; continue; }
  if (!candles || candles.length < 60) { fail++; continue; }
  const h = countDoubleTops(candles, HARD);
  const r = countDoubleTops(candles, REG);
  table.push({ symbol: sym, bars: candles.length, ...{ hardPatterns: h.patterns, hardPivots: h.pivotHighs, hardFigures: h.figures, hardSpan: h.medianSpan }, ...{ regPatterns: r.patterns, regPivots: r.pivotHighs, regFigures: r.figures, regSpan: r.medianSpan } });
}

const sum = (k: string) => table.reduce((a, b) => a + (b[k] as number), 0);
const mean = (k: string) => (table.length ? (sum(k) / table.length).toFixed(1) : '0');
console.log(`\nmeasured on ${table.length} symbols (${fail} skipped)`);
console.log('                                    hardcoded 3/2   registry 6/4');
console.log(`mean patterns per symbol            ${mean('hardPatterns').padStart(10)}   ${mean('regPatterns').padStart(10)}`);
console.log(`mean pivot highs per symbol         ${mean('hardPivots').padStart(10)}   ${mean('regPivots').padStart(10)}`);
console.log(`mean drawn figures (patterns x 5)   ${mean('hardFigures').padStart(10)}   ${mean('regFigures').padStart(10)}`);
console.log(`median pattern span (bars)          ${mean('hardSpan').padStart(10)}   ${mean('regSpan').padStart(10)}`);
console.log(`worst symbol by figures             ${Math.max(...table.map((t) => t.hardFigures))}   ${Math.max(...table.map((t) => t.regFigures))}`);

console.log('\ntop 12 by hardcoded figure count:');
for (const t of table.slice().sort((a, b) => b.hardFigures - a.hardFigures).slice(0, 12)) {
  console.log(`  ${String(t.symbol).padEnd(12)} bars ${String(t.bars).padStart(4)}  hard ${String(t.hardPatterns).padStart(3)} الگو / ${String(t.hardFigures).padStart(3)} شکل   registry ${String(t.regPatterns).padStart(3)} الگو / ${String(t.regFigures).padStart(3)} شکل`);
}

mkdirSync(OUT, { recursive: true });
writeFileSync(`${OUT}/density-${Date.now()}.json`, JSON.stringify({ base: BASE, topN, hardcoded: HARD, registry: REG, table }, null, 2));
console.log(`\nwrote ${OUT}`);
