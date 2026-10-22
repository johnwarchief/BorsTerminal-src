// PERF-P2R3: identical concurrent GETs share one raw response, while each caller
// still applies its own Zod contract (no parsed-object bleed between schemas).
import { afterEach, describe, expect, it, vi } from 'vitest';
import { z } from 'zod';
import { http } from '@shared/api/http';

describe('http in-flight GET dedupe', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('merges the network call but not the schemas', async () => {
    let calls = 0;
    let release: (v: Response) => void = () => {};
    const gate = new Promise<Response>((res) => { release = res; });
    vi.stubGlobal('fetch', vi.fn(async () => {
      calls += 1;
      return gate;
    }));
    const A = z.object({ a: z.number() });
    const B = z.object({ b: z.number() });
    const p1 = http<{ a: number }>('/api/perf-dedupe', { schema: A });
    const p2 = http<{ b: number }>('/api/perf-dedupe', { schema: B });
    await Promise.resolve();
    release(new Response(JSON.stringify({ a: 1, b: 2, ignored: 3 }), {
      status: 200, headers: { 'content-type': 'application/json' },
    }));
    const [a, b] = await Promise.all([p1, p2]);
    expect(calls).toBe(1);
    expect(a).toEqual({ a: 1 });
    expect(b).toEqual({ b: 2 });
  });
});
