import { render, screen, waitFor, within } from '@testing-library/react';
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
    // رأیِ واژگانِ مالک (۱۴۰۵-۰۷-۱۷): /master «استراتژی FTS» صدا می‌زند؛
    // «تابلوی غربالگری» و «مستر FTS» دیگر نامِ این مقصد نیستند. عنوانِ گروه
    // («غربالگری FTS») و عنوانِ درونِ صفحه سرِ جایشان می‌مانند، پس جستجو درِ
    // خودِ سایدبار قفل می‌شود وگرنه دو «غربالگری FTS» با هم قاطی می‌کنند.
    const sidebar = (await screen.findByLabelText('نوار کناری')) as HTMLElement;
    expect(within(sidebar).queryByText('تابلوی غربالگری')).not.toBeInTheDocument();
    expect(within(sidebar).queryByText('مستر FTS')).not.toBeInTheDocument();
    expect(within(sidebar).getByText('غربالگری FTS')).toBeInTheDocument();   // عنوانِ گروه
    expect(within(sidebar).getByText('درخت استراتژی')).toBeInTheDocument();
  });

  it('صفحۀ نخستِ برنامه غربالگری FTS است (رأیِ مالک)', async () => {
    await import('@features/master/routes/MasterPage');
    renderApp('/');
    // '/' دیگر تابلو نیست: باید قیف را بنشاند.
    await waitFor(() => {
      expect(screen.getByTestId('fts-funnel-workspace')).toBeInTheDocument();
    }, { timeout: 4000 });
    expect(screen.queryByTestId('tape-scroll')).not.toBeInTheDocument();
  });

  it('روت /master بدون نماد، قیفِ غربالگری را به‌جای پیامِ خالی نشان می دهد', async () => {
    await import('@features/master/routes/MasterPage');
    renderApp('/master');
    await waitFor(() => {
      // «نقشۀ راه قیف» حذف شده: /master باید مستقیم workspaceِ قیف باشد.
      expect(screen.getByTestId('fts-funnel-workspace')).toBeInTheDocument();
      expect(screen.queryByTestId('fts-funnel-overview')).not.toBeInTheDocument();
    });
    expect(screen.queryByText('نمادی انتخاب نشده')).not.toBeInTheDocument();
  });
});
