// تست زنجیرهٔ منبع کندل: /api/chart (سالم) ← در صورت خطا، /api/history (محلی)
// ریشهٔ باگ: /api/history تطبیق نماد را دقیق می‌کند و برای نماد ذخیره‌شده با «ك» عربی
// خالی برمی‌گرداند؛ /api/chart سالم است (نمونهٔ تأییدشده: کانسار).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fetchCandleFeed } from '@features/technical/api/useCandleFeed';

function resp(body: unknown): Response {
  return { ok: true, status: 200, json: async () => body } as unknown as Response;
}

function stub(bodies: { chart?: unknown; history?: unknown }) {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      if (url.includes('/api/chart/')) return Promise.resolve(resp(bodies.chart));
      if (url.includes('/api/history/')) return Promise.resolve(resp(bodies.history));
      return Promise.resolve(resp({ status: 'error' }));
    }),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe('زنجیرهٔ منبع کندل', () => {
  it('خارج از قلمرو: /api/chart سالم ⇒ منبع chart', async () => {
    stub({
      chart: {
        status: 'success',
        candles: [{ time: '2026-09-14', open: 10, high: 12, low: 9, close: 11 }],
        volumes: [{ time: '2026-09-14', value: 500 }],
        count: 1,
      },
    });
    const out = await fetchCandleFeed('کانسار');
    expect(out.source).toBe('chart');
    expect(out.status).toBe('success');
    expect(out.candles).toHaveLength(1);
    expect(out.volumes[0].value).toBe(500);
  });

  it('/api/chart خطا ⇒ fallback به /api/history', async () => {
    stub({
      chart: { status: 'error', message: 'CDN down' },
      history: {
        status: 'success',
        candles: [
          { time: '2026-09-13', open: 1, high: 2, low: 0.5, close: 1.5 },
          { time: '2026-09-14', open: 1.5, high: 2.5, low: 1, close: 2 },
        ],
        volumes: [],
      },
    });
    const out = await fetchCandleFeed('نماد');
    expect(out.source).toBe('history');
    expect(out.candles).toHaveLength(2);
  });

  it('/api/chart خالی (بدون کندل) ⇒ fallback', async () => {
    stub({
      chart: { status: 'success', candles: [], volumes: [] },
      history: { status: 'empty', candles: [], volumes: [] },
    });
    const out = await fetchCandleFeed('خالی');
    expect(out.source).toBe('history');
    expect(out.status).toBe('empty');
    expect(out.candles).toHaveLength(0);
  });
});
