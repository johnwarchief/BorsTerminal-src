// PERF-P2R4: hovering a funnel row with intent warms the two protected
// endpoints (plan + key-levels) before the click; a quick pass does not.
import { fireEvent, render, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, afterEach } from 'vitest';
import { StageRow } from '@features/master/ui/FtsFunnelAllStages';
import { funnelFromApi } from '@features/master/lib/funnelView';
import { FUNNEL_FIXTURE } from './fixtures/funnelApi';

function entry() {
  const f = funnelFromApi(FUNNEL_FIXTURE as never, 'reverse');
  const e = f.stages.tape.entries[0] ?? f.stages.technical.entries[0] ?? f.stages.fundamental.entries[0];
  if (!e) throw new Error('fixture has no funnel entry');
  return e;
}

describe('funnel row hover prefetch', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it('a deliberate hover warms /api/fts and /api/chart key-levels', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request) => {
      calls.push(decodeURIComponent(String(url)));
      return new Response(JSON.stringify({ status: 'success', fts: {} }), {
        status: 200, headers: { 'content-type': 'application/json' },
      });
    }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const e = entry();
    const { container } = render(
      <QueryClientProvider client={qc}>
        <table><tbody>
          <StageRow entry={e} cols={['symbol']} showMark={null} stageKey="tape" onPick={() => {}} />
        </tbody></table>
      </QueryClientProvider>,
    );
    const row = container.querySelector('[data-fkey]')!;
    fireEvent.mouseEnter(row);
    await waitFor(() => {
      expect(calls.some((u) => u.includes('/api/fts/' + e.symbol))).toBe(true);
      expect(calls.some((u) => u.includes('/api/chart/' + e.symbol + '/key-levels'))).toBe(true);
    }, { timeout: 3000 });
  });

  it('a quick pass over the row does not prefetch', async () => {
    const calls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string | URL | Request) => {
      calls.push(decodeURIComponent(String(url)));
      return new Response(JSON.stringify({ status: 'success', fts: {} }), {
        status: 200, headers: { 'content-type': 'application/json' },
      });
    }));
    const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const e = entry();
    const { container } = render(
      <QueryClientProvider client={qc}>
        <table><tbody>
          <StageRow entry={e} cols={['symbol']} showMark={null} stageKey="tape" onPick={() => {}} />
        </tbody></table>
      </QueryClientProvider>,
    );
    const row = container.querySelector('[data-fkey]')!;
    fireEvent.mouseEnter(row);
    fireEvent.mouseLeave(row);
    // debounce is 300ms: after it has surely elapsed nothing was requested
    await new Promise((r) => setTimeout(r, 450));
    expect(calls.filter((u) => u.includes('/api/fts/') || u.includes('/key-levels'))).toEqual([]);
  });
});
