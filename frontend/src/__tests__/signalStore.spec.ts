// تست تخته اعلانات مشترک
import { beforeEach, describe, expect, it } from 'vitest';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import type { AgentSignal } from '@contracts/signal';

function sig(patch: Partial<AgentSignal> = {}): AgentSignal {
  return {
    id: 'tape:شپنا:clock:1726000000000',
    agentId: 'tape',
    symbol: 'شپنا',
    ts: 1726000000000,
    direction: 'bullish',
    confidence: 'high',
    weight: 'major',
    title: 'الگوی ساعت در شپنا',
    rationale: 'قیمت پایانی بالاتر از آخرین است.',
    score: 80,
    evidence: [],
    sourceView: 'market',
    sourceRef: ['API'],
    validForMs: 3600_000,
    payload: { kind: 'tape_pattern', pattern: 'closing_auction_pop', lastVsClose: -0.02, volumeMultiple: 2 },
    ...patch,
  };
}

const NOW = 1726000000000;

describe('تخته سیگنال', () => {
  beforeEach(() => useSignalStore.getState().clearSignals());

  it('انتشار و خواندن سیگنال فعال', () => {
    useSignalStore.getState().publishSignal(sig());
    const active = getActiveSignals('شپنا', NOW);
    expect(active.tape?.id).toBe('tape:شپنا:clock:1726000000000');
  });

  it('انتشار دوباره همان ایجنت جایگزین می شود', () => {
    useSignalStore.getState().publishSignal(sig());
    useSignalStore.getState().publishSignal(sig({ id: 'tape:شپنا:susp_vol:1726000001000', score: 60 }));
    const active = getActiveSignals('شپنا', NOW);
    expect(active.tape?.score).toBe(60);
  });

  it('سیگنال منقضی از فعال ها حذف می شود', () => {
    useSignalStore.getState().publishSignal(sig({ validForMs: 1000 }));
    expect(getActiveSignals('شپنا', NOW + 2000).tape).toBeUndefined();
    expect(getActiveSignals('شپنا', NOW).tape).not.toBeUndefined();
  });

  it('سیگنال خراب منتشر نمی شود', () => {
    useSignalStore.getState().publishSignal(sig({ title: 'x' }));
    expect(getActiveSignals('شپنا', NOW).tape).toBeUndefined();
  });

  it('پاک سازی یک نماد بقیه را نگه می دارد', () => {
    useSignalStore.getState().publishSignal(sig());
    useSignalStore.getState().publishSignal(sig({ symbol: 'فولاد', id: 'tape:فولاد:clock:1726000000000' }));
    useSignalStore.getState().clearSignals('شپنا');
    expect(getActiveSignals('شپنا', NOW).tape).toBeUndefined();
    expect(getActiveSignals('فولاد', NOW).tape).not.toBeUndefined();
    useSignalStore.getState().clearSignals();
    expect(getActiveSignals('فولاد', NOW).tape).toBeUndefined();
  });
});
