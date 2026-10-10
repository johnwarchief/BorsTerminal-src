// TESTS — ترتیبِ نمایشِ ردیف‌هایِ هر گامِ قیف (باگِ P0: «تغییر Preset جدول را عوض
// نمی‌کند»). تابعِ خالصِ `orderStageRows` سنجیده می‌شود: نه داوری اینجا ساخته
// می‌شود و نه ردیفی حذف؛ فقط همان ردیف‌ها جابه‌جا می‌شوند.
import { describe, expect, it } from 'vitest';
import { orderStageRows } from '@features/master/ui/FtsFunnelAllStages';
import type { FunnelEntry, FunnelStageKey, StageStatus } from '@features/master/lib/ftsFunnel';

const STAGES: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

function cand(symbol: string, status: Partial<Record<FunnelStageKey, StageStatus>>,
             priority: number | null = null): FunnelEntry {
  const full = {} as Record<FunnelStageKey, StageStatus>;
  for (const k of STAGES) full[k] = status[k] ?? 'not_required';
  return {
    symbol, name: symbol, sector: '', kind: 'stock', row: null, screen: null,
    patterns: [], status: full, why: {} as Record<FunnelStageKey, string>,
    score: null, trendW: null, trendD: null, dailyStrategy: null, setups: '',
    technicalPoints: null, inds: [], techSource: null, jetEvidence: null,
    assemblyVeto: false, assemblyWhy: '', screenRank: null,
    universePriority: priority, universeStatus: null,
  } as unknown as FunnelEntry;
}

describe('orderStageRows — عبور_then_زنده، بی‌حذفِ هیچ ردیفی', () => {
  const rows = [
    cand('پ', { tape: 'reject' }),
    cand('ا', { tape: 'pass' }, 2),
    cand('ب', { tape: 'pass' }, 0),
    cand('ت', { tape: 'unavailable' }),
    cand('ث', { tape: 'pass' }, 1),
  ];

  it('ردیف‌هایِ عبور کرده رو‌به‌رو می‌آیند', () => {
    expect(orderStageRows('tape', rows).map((r) => r.symbol)).toEqual(['ب', 'ث', 'ا', 'ت', 'پ']);
  });

  it('درِ عبوری‌ها، نمادِ در حالِ معامله (priority کمتر) بالاتر است', () => {
    const out = orderStageRows('tape', rows).map((r) => r.symbol);
    expect(out.indexOf('ب')).toBeLessThan(out.indexOf('ا'));
    expect(out.indexOf('ث')).toBeLessThan(out.indexOf('ا'));
  });

  it('هیچ ردیفی حذف یا اضافه نمی‌شود و حکمِ هیچ ردیفی عوض نمی‌شود', () => {
    const out = orderStageRows('tape', rows);
    expect(out).toHaveLength(rows.length);
    expect(new Set(out.map((r) => r.symbol))).toEqual(new Set(rows.map((r) => r.symbol)));
    for (const r of out) {
      const src = rows.find((x) => x.symbol === r.symbol)!;
      expect(r.status).toEqual(src.status);
    }
  });

  it('بی‌دستۀِ ترتیبِ ثابتِ موتور حفظ می‌شود (پایدار، نه سوییِ تصادفی)', () => {
    const first = orderStageRows('tape', rows).map((r) => r.symbol).join('');
    for (let i = 0; i < 5; i++) {
      expect(orderStageRows('tape', rows).map((r) => r.symbol).join('')).toBe(first);
    }
  });

  it('دو preset با حکم‌هایِ متفاوت، ترتیبِ دیدنیِ متفاوت می‌دهند', () => {
    const swing = [cand('ا', { tape: 'pass' }), cand('ب', { tape: 'reject' })];
    const trend = [cand('ا', { tape: 'reject' }), cand('ب', { tape: 'pass' })];
    expect(orderStageRows('tape', swing).map((r) => r.symbol))
      .not.toEqual(orderStageRows('tape', trend).map((r) => r.symbol));
  });

  it('بی‌universe (بک‌اندِ قدیمی) فقط حکم ملاک است، نه اولویتِ اختراعی', () => {
    const out = orderStageRows('tape', [cand('ا', { tape: 'reject' }), cand('ب', { tape: 'pass' })]);
    expect(out.map((r) => r.symbol)).toEqual(['ب', 'ا']);
  });
});
