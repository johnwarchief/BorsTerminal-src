// آزمون‌های الزامیِ بند جِ مأموریتِ System 2 / UX فنی:
// ۱) /technical سایدبار اصلیِ اپ را «رندر نمی‌کند» (نه اینکه جمعش کند)؛
// ۲) /technical/:symbol هم همین‌طور؛
// ۳) مسیرهای دیگر سایدبار را برمی‌گردانند؛
// ۴) ترجیحِ جمع‌شدگیِ ذخیره‌شده در ورود/خروج دست‌نخورده می‌ماند؛
// ۵) در گوشی MobileNav روی مسیر تکنیکال سرِ جایش است.
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, afterEach } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { useAuthStore } from '@shared/stores/authStore';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';

function renderApp(initial: string) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: 0 } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initial]}>
        <Routes>
          <Route path="/" element={<AppShell />}>
            <Route path="technical" element={<div data-testid="technical-outlet" />} />
            <Route path="technical/:symbol" element={<div data-testid="technical-outlet" />} />
            <Route path="market" element={<div data-testid="market-outlet" />} />
            <Route path="master" element={<div data-testid="master-outlet" />} />
          </Route>
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const originalMatchMedia = window.matchMedia;

beforeEach(() => {
  localStorage.clear();
  useSymbolStore.getState().clearSymbol();
  useAuthStore.setState({ isAuthenticated: true });
  useUiStore.setState({ sidebarCollapsed: null });
});

afterEach(() => {
  window.matchMedia = originalMatchMedia;
});

describe('سایدبارِ اصلی در مسیر تکنیکال', () => {
  it('/technical: سایدبارِ اصلی کلاً رندر نمی‌شود', () => {
    renderApp('/technical');
    expect(screen.getByTestId('technical-outlet')).toBeInTheDocument();
    expect(screen.queryByLabelText('نوار کناری')).toBeNull();
    expect(screen.queryByTestId('nav-master')).toBeNull();
  });

  it('/technical/:symbol: همان رفتار، حتی وقتی نماد در آدرس است', () => {
    renderApp('/technical/فولاد');
    expect(screen.getByTestId('technical-outlet')).toBeInTheDocument();
    expect(screen.queryByLabelText('نوار کناری')).toBeNull();
  });

  it('مسیرهای دیگر سایدبار را برمی‌گردانند', () => {
    renderApp('/market');
    expect(screen.getByLabelText('نوار کناری')).toBeInTheDocument();
    expect(screen.getByTestId('nav-master')).toBeInTheDocument();
  });

  it('ترجیحِ جمع‌شدگی هنگام ورود و خروج از تکنیکال دست‌نخورده می‌ماند', () => {
    useUiStore.setState({ sidebarCollapsed: true });
    const { unmount } = renderApp('/technical');
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
    unmount();
    // افکتِ قدیمی در cleanup مقدار را null می‌کرد؛ این خط همان رگرسیون را می‌پاید.
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);

    renderApp('/market');
    expect(screen.getByLabelText('نوار کناری')).toHaveAttribute('data-collapsed', 'true');
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });

  it('در گوشی MobileNav روی مسیر تکنیکال می‌ماند (ناوبری حذف نمی‌شود)', () => {
    window.matchMedia = ((query: string) => ({
      matches: query.includes('max-width: 767.98px'),
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    })) as unknown as typeof window.matchMedia;

    renderApp('/technical');
    expect(screen.getByTestId('technical-outlet')).toBeInTheDocument();
    expect(screen.getByTestId('mobile-nav')).toBeInTheDocument();
    expect(screen.queryByLabelText('نوار کناری')).toBeNull();
  });
});
