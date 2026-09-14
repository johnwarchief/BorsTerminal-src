import { render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
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
  it('سایدبار فارسی رندر می شود', async () => {
    renderApp('/');
    await waitFor(() => {
      expect(screen.getByText('تابلو بازار')).toBeInTheDocument();
      expect(screen.getByText('ایجنت ارشد')).toBeInTheDocument();
    });
  });

  it('روت /master بدون نماد حالت خالی را نشان می دهد', async () => {
    renderApp('/master');
    await waitFor(() => {
      expect(screen.getByText('نمادی انتخاب نشده')).toBeInTheDocument();
    });
  });
});
