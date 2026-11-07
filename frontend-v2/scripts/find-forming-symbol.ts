import {
  DEFAULT_PRECISION_PARAMS,
  calculateAtr,
  detectDoubleTapPatterns,
  estimateFormation,
  selectLastFormingPattern,
} from '../src/features/technical/model/doubleTapEngine';
import { getMarketCohort } from '../src/features/technical/model/doubletapCohort';

const BASE = 'http://127.0.0.1:8101';

async function main() {
  const board = await (await fetch(`${BASE}/api/market`)).json();
  const rows = Array.isArray(board?.data) ? board.data : [];
  const symbols = rows
    .map((r: any) => r.symbol)
    .filter((s: any) => typeof s === 'string')
    .slice(0, 120);

  const hits: Array<Record<string, unknown>> = [];
  for (const symbol of symbols) {
    try {
      const res = await fetch(`${BASE}/api/chart-db/${encodeURIComponent(symbol)}`);
      if (!res.ok) continue;
      const payload = await res.json();
      const candles = (payload?.candles ?? []).map((c: any) => ({
        timestamp: Date.parse(c.time),
        open: c.open,
        high: c.high,
        low: c.low,
        close: c.close,
        volume: c.volume ?? 0,
      }));
      if (candles.length < 30) continue;
      const patterns = detectDoubleTapPatterns(candles, DEFAULT_PRECISION_PARAMS);
      const forming = selectLastFormingPattern(patterns);
      if (!forming) continue;
      const atr = calculateAtr(candles, DEFAULT_PRECISION_PARAMS.atrPeriod);
      const cohort = getMarketCohort('1D', forming.quality);
      const estimate = estimateFormation(
        patterns,
        candles,
        atr[forming.peak2.index] ?? atr[atr.length - 1] ?? 1,
        forming.id,
        10,
        cohort ?? undefined
      );
      hits.push({
        symbol,
        candles: candles.length,
        quality: forming.quality,
        probability: estimate?.probability ?? null,
        method: estimate?.method ?? null,
        resolved: estimate?.resolved ?? null,
        confidence: estimate?.confidence ?? null,
      });
      if (hits.length >= 12) break;
    } catch {
      // نماد بعدی
    }
  }
  process.stdout.write(JSON.stringify(hits, null, 2) + '\n');
}

main().catch((e) => {
  process.stderr.write(String(e) + '\n');
  process.exit(1);
});
