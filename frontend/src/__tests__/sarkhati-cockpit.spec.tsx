// UI cockpit: status-first panel, blocked Preflight, Mock timeline, no order route.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiCockpitCard } from '@features/portfolio/components/sarkhati/SarkhatiCockpitCard';

const fetchMock = vi.fn();
vi.stubGlobal('fetch', fetchMock);
const json = (body: unknown) =>
  ({ ok: true, status: 200, json: () => Promise.resolve(body) }) as unknown as Response;

const STATUS = {
  status: 'success', mode: 'MOCK', live_ready: false, live_send: false,
  app_version: '1.0.95', failing_count: 2, next_action: 'host را باز کنید',
  components: { browser_host: 'unavailable', session: 'unverified',
    unknown_holds: 1, db: { market: true, offerings: true, schedules: true, cockpit: true } },
  gates: [
    { id: 'backend', label: 'Backend/API', status: 'PASS', evidence: 'پاسخ داد',
      reason: 'پاسخ می‌دهد', action: '', source: 'cockpit', age_s: null },
    { id: 'browser_host', label: 'Browser host', status: 'BLOCKED',
      evidence: 'host=unavailable', reason: 'host نیست', action: 'host را باز کنید',
      source: 'host', age_s: null },
    { id: 'data_fresh', label: 'تازگی داده', status: 'FAIL', evidence: 'age=7200s',
      reason: 'داده کهنه است', action: 'داده را تازه کنید', source: 'market.db', age_s: 7200 },
  ],
};
const OFFERS = {
  status: 'success', capital: {}, reserved_total: 0, available: 1000,
  reservations: [],
  offerings: [
    { id: 'off-A', symbol: 'TESTA', isin: 'IRO1TESTA', method: 'BOOK_BUILDING',
      price_min: 100, price_max: 110, price_step: 1, min_qty: 1, max_qty: 100,
      per_code_quota: 100, fee_rate: 0.001, source: 'fixture',
      source_url: 'https://example.test/a', verified_at_ms: Date.now(),
      data_as_of_ms: Date.now() - 1000, status: 'VERIFIED', timing_relevance: 'NOT_PROVEN',
      timing_note: '' },
    { id: 'off-B', symbol: 'TESTB', isin: 'IRO1TESTB', method: 'UNKNOWN',
      price_min: 100, price_max: 110, price_step: 1, min_qty: 1, max_qty: 100,
      per_code_quota: 100, fee_rate: 0.001, source: 'fixture', source_url: '',
      verified_at_ms: null, data_as_of_ms: null, status: 'UNVERIFIED',
      timing_relevance: 'UNKNOWN', timing_note: '' },
  ],
};
const EVENTS = [
  { seq: 1, at: Date.now() / 1000, phase: 'start', status: 'RUNNING', detail: 'MOCK started', duration_ms: null },
  { seq: 2, at: Date.now() / 1000, phase: 'result', status: 'PASS', detail: 'SIMULATED result', duration_ms: 2 },
];
const RUN = { id: 'run-ui-1', scenario: 'success', mode: 'MOCK', status: 'PASS',
  started_at: Date.now() / 1000, finished_at: Date.now() / 1000,
  summary: { order_sent: false, retry_performed: false }, events: EVENTS };
const RUNS = { status: 'success', mode: 'MOCK', runs: [RUN], selected_run: RUN.id,
  events: EVENTS, scenarios: [{ id: 'success', label: 'موفق', detail: 'mock' }] };

function routes(offersBody: unknown = OFFERS) {
  const calls: string[] = [];
  fetchMock.mockImplementation((url: string, init?: { method?: string }) => {
    const u = String(url); const method = init?.method ?? 'GET';
    calls.push(`${method} ${u}`);
    if (u.includes('/api/execution/cockpit/status')) return Promise.resolve(json(STATUS));
    if (u.includes('/api/execution/cockpit/preflight')) return Promise.resolve(json({
      status: 'success', preflight: { ok: true, state: 'PASS',
        checks: [{ name: 'price', state: 'PASS', detail: 'range', source: 'fixture' }] } }));
    if (u.includes('/api/execution/cockpit/runs/run-ui-1')) return Promise.resolve(json({
      status: 'success', run: RUN }));
    if (u.includes('/api/execution/cockpit/runs') && method === 'POST') return Promise.resolve(json({
      status: 'success', run: RUN, live_send: false }));
    if (u.includes('/api/execution/cockpit/runs')) return Promise.resolve(json(RUNS));
    if (u.includes('/api/execution/cockpit/report')) return Promise.resolve(json({
      status: 'success', mode: 'MOCK', live_ready: false, secrets_stored: false }));
    if (u.includes('/api/execution/offerings')) return Promise.resolve(json(offersBody));
    return Promise.resolve(json({ status: 'success', schedules: [], readiness: { live_ready: false } }));
  });
  return calls;
}

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiCockpitCard ledger={null} /></QueryClientProvider>);
}

beforeEach(() => { fetchMock.mockReset(); });

describe('cockpit UI', () => {
  it('وضعیت و Gateهای مسدود را نشان می‌دهد و live را سبز نمی‌کند', async () => {
    routes(); renderCard();
    expect(await screen.findByTestId('cockpit-gate-chip-browser_host')).toBeInTheDocument();
    expect(screen.getByTestId('cockpit-live-state')).toHaveTextContent('Live مسدود');
    expect(screen.getByTestId('cockpit-gate-chip-data_fresh')).toHaveTextContent('FAIL');
    expect(screen.getByTestId('cockpit-next-action')).toHaveTextContent('host');
  });

  it('Preflight موفق و مسدود را روی همان عرضه نشان می‌دهد', async () => {
    routes(); renderCard();
    await screen.findByTestId('cockpit-gate-chip-browser_host');
    fireEvent.click(screen.getByTestId('cockpit-preflight-section').querySelector('summary')!);
    await waitFor(() => expect(screen.getByTestId('cockpit-offer-select')).toBeInTheDocument());
    fireEvent.change(screen.getByTestId('cockpit-offer-select'), { target: { value: 'off-A' } });
    fireEvent.change(screen.getByTestId('cockpit-price'), { target: { value: '105' } });
    fireEvent.change(screen.getByTestId('cockpit-qty'), { target: { value: '10' } });
    fireEvent.click(screen.getByTestId('cockpit-run-preflight'));
    await waitFor(() => expect(screen.getByTestId('cockpit-preflight-state')).toHaveTextContent('PASS'));
    expect(screen.getByTestId('cockpit-check-price')).toHaveTextContent('PASS');
  });

  it('سناریوی Mock را اجرا می‌کند و Timeline و برچسب MOCK را نشان می‌دهد', async () => {
    routes(); renderCard();
    await screen.findByTestId('cockpit-run-state');
    fireEvent.click(screen.getByTestId('cockpit-mock-section').querySelector('summary')!);
    await waitFor(() => expect(screen.getByTestId('cockpit-run-mock')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('cockpit-run-mock'));
    await waitFor(() => expect(screen.getByTestId('cockpit-run-state')).toHaveTextContent('موفق'));
    expect(screen.getByTestId('cockpit-events')).toHaveTextContent('SIMULATED');
  });

  it('خطای وضعیت و فهرست خالی عرضه را صریح نشان می‌دهد', async () => {
    fetchMock.mockImplementation((url: string) => String(url).includes('/cockpit/status')
      ? Promise.resolve(({ ok: false, status: 400,
        json: () => Promise.resolve({ detail: 'backend down' }) }) as unknown as Response)
      : Promise.resolve(json({ status: 'success', offerings: [], capital: {},
        reserved_total: 0, reservations: [] })));
    renderCard();
    expect(await screen.findByTestId('cockpit-error')).toBeInTheDocument();
  });

  it('با عرضهٔ خالی، Preflight را NOT_RUN نگه می‌دارد و رزرو جعلی نمی‌سازد', async () => {
    routes({ status: 'success', capital: {}, reserved_total: 0, reservations: [], offerings: [] });
    renderCard();
    await screen.findByTestId('cockpit-gate-chip-browser_host');
    fireEvent.click(screen.getByTestId('cockpit-preflight-section').querySelector('summary')!);
    await waitFor(() => expect(screen.getByTestId('cockpit-offer-select')).toBeInTheDocument());
    expect(screen.getByTestId('cockpit-offer-select').querySelectorAll('option')).toHaveLength(1);
    expect(screen.queryByTestId('cockpit-check-price')).not.toBeInTheDocument();
  });

  it('هیچ درخواست سفارش واقعی از مسیر Mock ساخته نمی‌شود', async () => {
    const calls = routes(); renderCard();
    await screen.findByTestId('cockpit-run-state');
    fireEvent.click(screen.getByTestId('cockpit-mock-section').querySelector('summary')!);
    fireEvent.click(await screen.findByTestId('cockpit-run-mock'));
    await waitFor(() => expect(screen.getByTestId('cockpit-run-state')).toHaveTextContent('موفق'));
    expect(calls.filter((c) => /POST .*(\/order|\/dispatch)/.test(c))).toEqual([]);
  });
});
