import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { MarketFeed } from '@shared/types/market';
import {
  adoptBoard,
  applyBoardDelta,
  fetchBoard,
  getBoardSnapshot,
  resetBoardMirror,
} from '@features/market/api/boardFeed';
import { computeFeedStatus } from '@shared/lib/feedFreshness';

function feed(): MarketFeed {
  return {
    status: 'success',
    data: [
      { ins_code: '1', symbol: 'فولاد', p_last: 100, is_live: true },
      { ins_code: '2', symbol: 'خساپا', p_last: 200, is_live: true },
    ],
    count: 2,
    live_count: 2,
    fossil_count: 0,
    rev: 7,
    rev_at: null,
    meta: null,
  };
}

beforeEach(() => resetBoardMirror());
afterEach(() => vi.unstubAllGlobals());

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('board feed mirror', () => {
  it('merges changed rows by instrument identity and advances data-change time', () => {
    adoptBoard(feed(), 1_000);
    const previous = getBoardSnapshot();
    const result = applyBoardDelta({
      status: 'delta', rev: 8, count: 2, live_count: 2, fossil_count: 0, meta: null,
      rows: [{ ins_code: '2', symbol: 'خساپا', p_last: 210, is_live: true }],
    }, 2_000);
    const next = getBoardSnapshot();
    expect(result).toBe('merged');
    expect(next.data.map((row) => row.p_last)).toEqual([100, 210]);
    expect(next.rev).toBe(8);
    expect(next.rev_at).toBe(2_000);
    expect(next).not.toBe(previous);
  });

  it('keeps the same snapshot and data-change time for an unchanged revision', () => {
    adoptBoard(feed(), 1_000);
    const previous = getBoardSnapshot();
    const result = applyBoardDelta({
      status: 'unchanged', rev: 7, count: 2, live_count: 2, fossil_count: 0, meta: null,
    }, 9_000);
    expect(result).toBe('unchanged');
    expect(getBoardSnapshot()).toBe(previous);
    expect(getBoardSnapshot().rev_at).toBe(1_000);
  });

  it('rejects an unkeyed delta without partially changing the mirror', () => {
    adoptBoard(feed(), 1_000);
    const previous = getBoardSnapshot();
    const result = applyBoardDelta({
      status: 'delta', rev: 8, count: 2, live_count: 2, fossil_count: 0, meta: null,
      rows: [
        { ins_code: '2', symbol: 'خساپا', p_last: 210, is_live: true },
        { symbol: 'بی‌کلید', p_last: 1 },
      ],
    }, 2_000);
    expect(result).toBe('full');
    expect(getBoardSnapshot()).toBe(previous);
  });

  it('requests a full refresh on count mismatch or an explicit full response', () => {
    adoptBoard(feed(), 1_000);
    const previous = getBoardSnapshot();
    expect(applyBoardDelta({
      status: 'delta', rev: 8, count: 3, live_count: 3, fossil_count: 0, meta: null,
      rows: [{ ins_code: '2', symbol: 'خساپا', p_last: 210, is_live: true }],
    }, 2_000)).toBe('full');
    expect(getBoardSnapshot()).toBe(previous);
    expect(applyBoardDelta({ status: 'full', rev: null, reason: 'journal rotated' }, 3_000)).toBe('full');
    expect(getBoardSnapshot()).toBe(previous);
  });
});

describe('feed freshness', () => {
  it('reports a transport error independently from missing market data', () => {
    expect(computeFeedStatus({
      status: 'error', dataUpdatedAt: 10_000, dataChangedAt: 9_000,
      liveCount: 10, totalCount: 100, now: 20_000, marketOpen: true,
    }).connection).toBe('error');
  });

  it('marks a live feed stale when requests arrive but values stop changing', () => {
    const status = computeFeedStatus({
      status: 'success', dataUpdatedAt: 400_000, dataChangedAt: 1_000,
      liveCount: 10, totalCount: 100, now: 400_000, marketOpen: true,
    });
    expect(status.freshness).toBe('stale');
    expect(status.pulse).toBe(false);
  });

  it('does not call a closed board live or stale merely because nothing changes', () => {
    const status = computeFeedStatus({
      status: 'success', dataUpdatedAt: 400_000, dataChangedAt: 100_000,
      liveCount: 0, totalCount: 100, now: 400_000, marketOpen: false,
    });
    expect(status.freshness).toBe('closed');
    expect(status.pulse).toBe(false);
  });
});

describe('board HTTP fallback', () => {
  it('refetches the full board when a delta cannot be merged safely', async () => {
    const initial = feed();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(initial))
      .mockResolvedValueOnce(jsonResponse({
        status: 'delta', rev: 8, count: 3, live_count: 2, fossil_count: 0, meta: null, rows: [],
      }))
      .mockResolvedValueOnce(jsonResponse({ ...initial, rev: 8 }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchBoard();
    const result = await fetchBoard();

    expect(result.rev).toBe(8);
    expect(fetchMock.mock.calls.map((call) => String(call[0]))).toEqual([
      '/api/market', '/api/market/delta?since=7', '/api/market',
    ]);
  });

  it('disables delta for this tab after the server answers 404', async () => {
    const initial = feed();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(jsonResponse(initial))
      .mockResolvedValueOnce(new Response(null, { status: 404 }))
      .mockResolvedValueOnce(jsonResponse(initial))
      .mockResolvedValueOnce(jsonResponse(initial));
    vi.stubGlobal('fetch', fetchMock);

    await fetchBoard();
    await fetchBoard();
    await fetchBoard();

    const urls = fetchMock.mock.calls.map((call) => String(call[0]));
    expect(urls.filter((url) => url.includes('/delta'))).toHaveLength(1);
    expect(urls.at(-1)).toBe('/api/market');
  });
});
