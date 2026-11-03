// PERF-R5: the conditional (ETag) cache used to keep every URL's parsed body
// forever. Per-symbol endpoints (/api/chart/<symbol>, /api/fts/<symbol>) create
// a new key on each switch, so a long session accumulated parsed chart bodies.
// The cache is now LRU-bounded; an evicted URL must refetch, a hot URL must
// still get its 304 and reuse the parsed object.
import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { http } from '@shared/api/http';

const Schema = z.object({ v: z.number() });

describe('http conditional cache is LRU-bounded', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('evicts the oldest URL after the cap and still revalidates the newest', async () => {
    const seen: { url: string; inm: string | null }[] = [];
    const fetchMock = vi.fn(async (url: string | URL | Request, init?: RequestInit) => {
      const u = String(url);
      const inm = (init?.headers as Record<string, string> | undefined)?.['If-None-Match'] ?? null;
      seen.push({ url: u, inm });
      if (inm) {
        return new Response(null, { status: 304, headers: { etag: inm } });
      }
      const n = Number(u.split('/').pop() ?? 0);
      return new Response(JSON.stringify({ v: n }), {
        status: 200,
        headers: { 'content-type': 'application/json', etag: `"e-${n}"` },
      });
    });
    vi.stubGlobal('fetch', fetchMock);

    // 40 unique URLs > the 32-entry bound.
    for (let i = 0; i < 40; i++) {
      const got = await http<{ v: number }>(`/api/perf-lru/${i}`, { schema: Schema });
      expect(got.v).toBe(i);
    }

    // Oldest was evicted: the request must go out again without If-None-Match.
    const oldIndex = seen.length;
    await http<{ v: number }>('/api/perf-lru/0', { schema: Schema });
    expect(seen[oldIndex].inm).toBeNull();

    // Newest is still hot: a 304 reuses the parsed object and sends the tag.
    const hotIndex = seen.length;
    const hot = await http<{ v: number }>('/api/perf-lru/39', { schema: Schema });
    expect(hot.v).toBe(39);
    expect(seen[hotIndex].inm).toBe('"e-39"');
  });

  it('schema-less GET stores the ETag and reuses the parsed body on 304', async () => {
    const seen: (string | null)[] = [];
    const fetchMock = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      const inm = (init?.headers as Record<string, string> | undefined)?.['If-None-Match'] ?? null;
      seen.push(inm);
      if (inm) return new Response(null, { status: 304, headers: { etag: inm } });
      return new Response(JSON.stringify({ rows: [1, 2, 3] }), {
        status: 200, headers: { 'content-type': 'application/json', etag: '"plain-1"' },
      });
    });
    vi.stubGlobal('fetch', fetchMock);
    const a = await http<{ rows: number[] }>('/api/perf-lru-schemaless');
    const b = await http<{ rows: number[] }>('/api/perf-lru-schemaless');
    expect(a).toEqual({ rows: [1, 2, 3] });
    expect(b).toBe(a);                    // same parsed object, no second body
    expect(seen[1]).toBe('"plain-1"');
  });
});
