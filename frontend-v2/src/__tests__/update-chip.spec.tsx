import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { UpdateChip } from '@features/updater/ui/UpdateChip';

function client(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
}

function withClient(ui: ReactElement): ReactElement {
  return <QueryClientProvider client={client()}>{ui}</QueryClientProvider>;
}

function json(body: unknown): Response {
  return new Response(JSON.stringify(body), { status: 200, headers: { 'Content-Type': 'application/json' } });
}

type Route = (url: string, init?: RequestInit) => unknown;
let calls: Array<{ url: string; method: string; csrf: string | null }> = [];

function mockFetch(routes: Record<string, Route>) {
  vi.stubGlobal('fetch', vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = (init?.method ?? 'GET').toUpperCase();
    const headers = new Headers(init?.headers ?? {});
    calls.push({ url, method, csrf: headers.get('X-OC-CSRF') });
    const route = routes[`${method} ${url.split('?')[0]}`];
    if (!route) throw new Error(`unexpected fetch ${method} ${url}`);
    return json(route(url, init));
  }));
}

beforeEach(() => {
  calls = [];
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('UpdateChip', () => {
  it('shows the current version, last update and offers rollback', async () => {
    mockFetch({
      'GET /api/update/version': () => ({
        version: '1.0.96', mode: 'installed', rollback_available: true, rollback_version: '1.0.95',
        last_update: { status: 'applied', from: '1.0.95', to: '1.0.96' },
      }),
      'GET /api/update/check': () => ({
        status: 'success', current_version: '1.0.96', latest_version: '1.0.96', available: false,
      }),
      'POST /api/update/rollback': () => ({ status: 'rolling_back' }),
    });
    render(withClient(<UpdateChip />));
    await waitFor(() => expect(screen.getByTestId('update-chip').textContent).toContain('1.0.96'));
    fireEvent.click(screen.getByTestId('update-chip'));
    await waitFor(() => expect(screen.getByText('برنامه به‌روز است.')).toBeTruthy());
    expect(screen.getByTestId('update-last').textContent).toContain('موفق');
    fireEvent.click(screen.getByTestId('update-rollback'));
    fireEvent.click(screen.getByTestId('update-rollback-confirm'));
    await waitFor(() => expect(calls.some((c) => c.url === '/api/update/rollback' && c.method === 'POST')).toBe(true));
    const post = calls.find((c) => c.url === '/api/update/rollback');
    expect(post?.csrf).toBe('1');
  });

  it('downloads, shows progress, then installs a new version', async () => {
    mockFetch({
      'GET /api/update/version': () => ({ version: '1.0.95', mode: 'installed', rollback_available: false }),
      'GET /api/update/check': () => ({
        status: 'success', current_version: '1.0.95', latest_version: '1.0.96',
        available: true, installable: true, size: 104857600, notes: 'رفع اشکال',
      }),
      'POST /api/update/download': () => ({ status: 'started' }),
      'GET /api/update/progress': () => ({ status: 'ready', downloaded: 104857600, total: 104857600, version: '1.0.96' }),
      'POST /api/update/install': () => ({ status: 'installing' }),
    });
    render(withClient(<UpdateChip />));
    await waitFor(() => expect(screen.getByTestId('update-chip').textContent).toContain('1.0.95'));
    fireEvent.click(screen.getByTestId('update-chip'));
    await waitFor(() => expect(screen.getByText('1.0.96')).toBeTruthy());
    expect(screen.getByText('۱۰۰ مگابایت')).toBeTruthy();
    fireEvent.click(screen.getByTestId('update-download'));
    await waitFor(() => expect(screen.getByTestId('update-install')).toBeTruthy());
    fireEvent.click(screen.getByTestId('update-install'));
    await waitFor(() => expect(calls.some((c) => c.url === '/api/update/install' && c.method === 'POST')).toBe(true));
  });
});
