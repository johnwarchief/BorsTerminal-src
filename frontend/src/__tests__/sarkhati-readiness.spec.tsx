// src/__tests__/sarkhati-readiness.spec.tsx — دروازهٔ آمادگی، بی‌ادعایِ Live
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SarkhatiReadinessCard } from '@features/portfolio/components/sarkhati/SarkhatiReadinessCard';
import { useSymbolStore } from '@shared/stores/symbolStore';

const DATA = {
  status: 'success',
  data_risk_ready: false,
  live_ready: false,
  live_enabled: false,
  contract_state: 'WRITE_CONTRACT_STATICALLY_RECONSTRUCTED',
  blocking_count: 4,
  next_action: 'آزمونِ مجازِ ثبت با تأییدِ مالک',
  gates: [
    { id: 'read_only_session', label: 'نشستِ فقط‌خواندنی', status: 'PASS', detail: '', source: '' },
    { id: 'buying_power', label: 'قدرت خرید', status: 'PASS', detail: '', source: '' },
    { id: 'data_risk', label: 'داده و ریسک', status: 'BLOCKED', detail: 'قیمت سنجیده نشده', source: 'preflight' },
    { id: 'write_contract', label: 'قرارداد نوشتن', status: 'UNVERIFIED', detail: 'بازسازی‌شده', source: 'client' },
    { id: 'owner_approval', label: 'مجوزِ مالک', status: 'REQUIRED', detail: '', source: 'owner' },
  ],
  contract: {
    method: 'POST', endpoint: '/core/api/v2/order',
    operationally_verified: false, provenance: 'main-XW5OZAYT.js → createOrder',
  },
  adapter: 'easytrader', symbol: 'فولاد', side: 'buy',
};

vi.mock('@features/portfolio/lib/orderClient', () => ({
  useExecutionReadiness: () => ({ data: DATA, isPending: false, isError: false, error: null }),
}));

function renderCard() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><SarkhatiReadinessCard /></QueryClientProvider>);
}

beforeEach(() => {
  useSymbolStore.setState({ symbol: 'فولاد' });
});

describe('کارتِ آمادگیِ اجرا', () => {
  it('سه وضعیتِ کلیدی را جدا می‌گوید و Live را آماده اعلام نمی‌کند', () => {
    renderCard();
    expect(screen.getByTestId('readiness-live').textContent).toContain('بسته');
    expect(screen.getByTestId('readiness-data').textContent).toContain('مسدود');
    expect(screen.getByTestId('readiness-write').textContent).toContain('تأییدنشده');
    expect(screen.getByTestId('readiness-owner').textContent).toContain('لازم');
    expect(screen.getByTestId('readiness-next').textContent).toContain('تأییدِ مالک');
    expect(screen.getByTestId('readiness-blocking').textContent).toContain('۴');
  });

  it('جزئیاتِ دروازه‌ها و قراردادِ بازسازی‌شده را باز می‌کند', () => {
    renderCard();
    const details = screen.getByTestId('readiness-details');
    fireEvent.click(details.querySelector('summary')!);
    expect(screen.getByTestId('readiness-gate-write_contract').textContent)
      .toContain('تأییدنشده');
    expect(screen.getByTestId('readiness-contract').textContent)
      .toContain('/core/api/v2/order');
    expect(screen.getByTestId('readiness-contract').textContent)
      .toContain('تأیید عملیاتی');
    expect(screen.getByTestId('readiness-contract').textContent).toContain('نه');
  });
});
