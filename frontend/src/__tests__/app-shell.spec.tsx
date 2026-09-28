import { render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useAuthStore } from '@shared/stores/authStore';
import { mainRoutes } from '../routes';

function renderApp(initial = '/') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            {mainRoutes.map((r) => (
              <Route key={r.path} path={r.path || undefined} index={!r.path} element={r.element} />
            ))}
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('AppShell smoke', () => {
  beforeEach(() => {
    useSymbolStore.getState().clearSymbol();
    localStorage.clear();
    useAuthStore.setState({ isAuthenticated: true });
  });

  it('در غیاب احراز هویت، صفحه لاگین نمایش داده می‌شود', async () => {
    useAuthStore.setState({ isAuthenticated: false });
    renderApp('/');
    await waitFor(() => {
      expect(screen.getByText('ورود به ایستگاه معاملاتی ⏎')).toBeInTheDocument();
    });
  });

  it('سایدبار فارسی رندر می شود', async () => {
    renderApp('/');
    await waitFor(() => {
      expect(screen.getByText('تابلوخوانی/بازار')).toBeInTheDocument();
      expect(screen.getByText('استراتژی FTS')).toBeInTheDocument();
    });
  });

  it('روت /master بدون نماد، قیفِ غربالگری را به‌جای پیامِ خالی نشان می دهد', async () => {
    await import('@features/master/routes/MasterPage');
    renderApp('/master');
    await waitFor(() => {
      expect(screen.getByTestId('funnel-stage-tape')).toBeInTheDocument();
    });
    expect(screen.queryByText('نمادی انتخاب نشده')).not.toBeInTheDocument();
  });
});
