/** __tests__/tape-sort-bench.spec.ts — Stage 7: هزینهٔ هرِ دورِ دلتا درِ لایۀِ داده (BENCH)
 *
 *  ONLY-A-BENCH: با `BORS_BENCH=1` اجرا می‌شود و درِ CIِ معمول skip است، چون عددش
 *  شاهدِ مرورگر نیست. محیط = Node/V8 زیرِ jsdom، رویِ snapshotِ ثابتِ ۵٬۸۹۲ ردیفِ واقعی
 *  (`_audit/tmp/feed_after.json`). هیچِ مسیری ازِ برنامه تغییر نکرده و هیچِ دیتابیس/شبکه‌ای
 *  لمس نشده. تبدیلِ این اعداد به «هزینۀِ هر دلتا درِ بازارِ باز» جایز نیست — آن را فقط
 *  `tools/perf_raf_render_probe.mts` درِ پنجرۀِ معاملاتی می‌سنجد.
 *
 *  چه چیزی را ثابت می‌کند:
 *   ۱) وفاداری: مقایسه‌گرِ sortِ کپی‌شده درِ این فایل، ترتیبی *دقیقاً* مثلِ `TapeTable`
 *      می‌سازد (با رندرِ خودِ TapeTable و خواندنِ ترتیبِ DOM بررسی می‌شود). بی‌این، بنچ
 *      یکِ منطقِ دومی را می‌سنجد و سبزی‌اش هیچ معنایی ندارد.
 *   ۲) تفکیک: چه کسری ازِ کارِ هرِ دلتا به slice، sort، فیلترِ جهان، پنهان‌شمارش،
 *      چیپ‌شمارش، سیگنال و render تعلق دارد.
 *
 *  اجرا:  BORS_BENCH=1 npx vitest run src/__tests__/tape-sort-bench.spec.ts
 */
import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { render, cleanup } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import type { MarketRow } from '@shared/types/marketRow';
import { applyFilters } from '@features/market/routes/MarketPage';
import { TapeTable } from '@features/market/components/TapeTable';
import { dropNumericSuffixRows } from '@features/market/lib/tapeFts';
import { rowsToTapeSignals } from '@features/market/signals/tapeSignals';
import { countHiddenMatches, countQuickFilters } from '@features/market/components/MarketFilters';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { vi } from 'vitest';

const HERE = dirname(fileURLToPath(import.meta.url));
const FIXTURE = resolve(HERE, '../../../_audit/tmp/feed_after.json');
const ENABLED = process.env.BORS_BENCH === '1';

// jsdom اندازه نمی‌دهد ⇒ virtualizer را به رندرِ کامل وادار می‌کنیم (الگویِ market-components.spec.tsx)
vi.mock('@tanstack/react-virtual', async (orig) => {
  const mod = await orig<typeof import('@tanstack/react-virtual')>();
  return {
    ...mod,
    useVirtualizer: ({ count }: { count: number }) => ({
      getTotalSize: () => count * 40,
      getVirtualItems: () => Array.from({ length: count }, (_, i) => ({ key: i, index: i, start: i * 40 })),
    }),
  };
});

const NEG = Number.NEGATIVE_INFINITY;
/** کپیِ وفادارِ `sortVal`/comparator درِ `TapeTable.tsx:329-342` (پیش‌فرض: vol_ratio، نزولی).
 *  وفاداری‌اش درِ testِ ۱ با رندرِ خودِ TapeTable سنجیده می‌شود، نه با فرض. */
function replicatedSort(rows: MarketRow[]): MarketRow[] {
  const arr = [...rows];
  arr.sort((a, b) => {
    const va = (a.vol_ratio ?? NEG) as number;
    const vb = (b.vol_ratio ?? NEG) as number;
    return vb - va;
  });
  return arr;
}

const stats = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return { n: s.length, medianMs: +s[s.length >> 1].toFixed(3), p95Ms: +s[Math.min(s.length - 1, Math.floor(s.length * 0.95))].toFixed(3), minMs: +s[0].toFixed(3), maxMs: +s[s.length - 1].toFixed(3) };
};

function time(fn: () => unknown, runs: number, warm = 3) {
  for (let i = 0; i < warm; i++) fn();
  const xs: number[] = [];
  for (let i = 0; i < runs; i++) {
    const t = performance.now();
    fn();
    xs.push(performance.now() - t);
  }
  return stats(xs);
}

const RUNS = Number(process.env.BORS_BENCH_RUNS ?? 15);

describe.skipIf(!ENABLED)('بنچِ هزینۀِ هرِ دورِ دلتا (Node/jsdom — نه مرورگر، نه بازارِ باز)', () => {
  afterEach(cleanup);
  const have = existsSync(FIXTURE);
  it.skipIf(!have)('وفاداریِ کپیِ sort + تفکیکِ هزینهٔ مراحل', () => {
    const body = JSON.parse(readFileSync(FIXTURE, 'utf8')) as { data: MarketRow[]; count: number };
    const all = body.data;
    const st = useTapeStore.getState();

    // ۱) وفاداری: ترتیبِ خودِ TapeTable == ترتیبِ کپیِ این فایل
    const sub = all.slice(0, 400);
    render(<TapeTable rows={sub} selected="" onSelect={() => {}} isLoading={false} isError={false} />);
    const domOrder = [...document.querySelectorAll('[data-testid="tape-row"]')]
      .map((r) => r.querySelector('[data-testid^="select-box-"]')?.getAttribute('data-testid')?.slice('select-box-'.length));
    const mine = replicatedSort(sub).map((r) => r.symbol);
    expect(domOrder.length).toBe(sub.length);
    expect(mine.length).toBe(domOrder.length);
    // مقایسه تا عمقِ ۴۰۰ — اگر الگوریتمِ sortِ ما باِ جدول فرق داشت اینجا می‌شکست
    expect(mine.slice(0, 400)).toEqual(domOrder);

    // همان حالتی که MarketPage درِ هرِ دلتایِ *دارایِ تغییر* از سرِ نو می‌گذراند
    const cfg = st.tapeFilterConfig;
    const stages: Record<string, unknown> = {
      fixture: { rows: all.length, file: FIXTURE.replace(/\\/g, '/'), runs: RUNS,
                 env: 'node ' + process.version + ' / jsdom / BORS_BENCH=1',
                 caveat: 'مرتب‌سازی درِ TapeTable رویِ `filtered` است، نه رویِ کلِ جهان؛ پس sortِ کلِ جهان اینجا نیست' },
      slice_copy_universe: time(() => [...all], RUNS),
      slice_copy_plus_sort_400: time(() => replicatedSort(sub), RUNS),
      boardBase_applyFilters_universe: time(
        () => applyFilters(all, st.query, st.assetTypes, [], st.sector, st.liveOnly, st.direction, st.volRatioOn, st.volRatioMin, st.exitAccum, cfg), RUNS),
      dropNumericSuffix: time(() => dropNumericSuffixRows(sub), RUNS),
      hiddenRows_set_and_filter: time(() => {
        const base = applyFilters(all, st.query, st.assetTypes, [], st.sector, st.liveOnly, st.direction, st.volRatioOn, st.volRatioMin, st.exitAccum, cfg);
        const shown = new Set(base);
        return all.filter((r) => !shown.has(r));
      }, RUNS),
      countHiddenMatches: time(() => countHiddenMatches(sub, { assetTypes: st.assetTypes, liveOnly: st.liveOnly, query: st.query, sector: st.sector, dropSuffix: !st.showNumericSuffix }, cfg), RUNS),
      rowsToTapeSignals_filtered: time(() => rowsToTapeSignals(sub), RUNS),
    };
    // چیپ‌هایِ روشن: همان قیف ولی با tapeFilterVerdict درِ هرِ ردیف (۷ فیلتر)
    const withChips = time(
      () => applyFilters(all, st.query, st.assetTypes, ['f_susp', 'f_jet'] as never, st.sector, st.liveOnly, st.direction, st.volRatioOn, st.volRatioMin, st.exitAccum, cfg), RUNS);
    stages['applyFilters_universe_WITH_2_chips'] = withChips;
    stages['countQuickFilters_universe'] = time(() => countQuickFilters(all as never, cfg, ['f_susp', 'f_jet'] as never, 'and'), RUNS);

    const summary: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(stages)) {
      const isStat = v && typeof v === 'object' && 'medianMs' in (v as object);
      summary[k] = isStat
        ? `${(v as unknown as { medianMs: number }).medianMs}ms (n=${(v as unknown as { n: number }).n}, p95=${(v as unknown as { p95Ms: number }).p95Ms}ms)`
        : v;
    }
    console.log('BEN result:', JSON.stringify(summary, null, 1));
    expect(all.length).toBeGreaterThan(4000);
  });
  it.skipIf(have)('fixtureِ snapshot موجود نیست — بنچ اجرا نمی‌شود', () => {
    console.log('BENCH SKIPPED: بی‌' + FIXTURE);
  });
});
