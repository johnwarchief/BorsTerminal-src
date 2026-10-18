// __tests__/connect-broker-row.spec.tsx -- «اتصال به EasyTrader» در رابط
//
// سه چیزی که باید درِ DOM دیده شود، نه درِ متنِ ثابت:
//  • حالتِ نشست از پاسخِ `/connect` می‌آید؛ «متصل» بی‌پرسشِ واقعی ساخته نمی‌شود؛
//  • بی‌دامنۀ تأییدشده، علتِ BLOCKED نشان داده می‌شود (نه دکمۀ بی‌عمل، نه ادعا)؛
//  • هیچ ورودیِ نشانی/رمزی درِ این ردیف نیست — نشانی فقط درِ پنلِ موجود و
//    فقط به `POST /api/execution/session` می‌رود.
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConnectBrokerRow } from '@features/portfolio/components/ConnectBrokerRow';

const fetchMock = vi.fn();
beforeEach(() => { fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock); });

function respond(body: unknown, status = 200) {
  fetchMock.mockImplementation(async () => new Response(JSON.stringify(body), {
    status, headers: { 'Content-Type': 'application/json' },
  }));
}

function render_() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}><ConnectBrokerRow /></QueryClientProvider>);
}

describe('ردیفِ اتصالِ کارگزاری', () => {
  it('بی‌پرسشِ موفق، برچسب «نامعلوم» است — نه «متصل»', async () => {
    respond({ status: 'success', last_verify: {}, browser: { open: false, profile_kept: false },
              login_hosts_configured: [], login_host_blocked_reason: 'بی‌دامنه' });
    render_();
    await waitFor(() => expect(screen.getByTestId('connect-broker-row')).toBeTruthy());
    expect(screen.getByTestId('connect-broker-row').textContent).toContain('نامعلوم');
    expect(screen.getByTestId('connect-broker-row').textContent).not.toContain('متصل');
  });

  it('علتِ BLOCKED درِ رابط خوانده می‌شود', async () => {
    respond({ status: 'success', last_verify: { state: 'UNKNOWN' }, browser: { open: false },
              login_hosts_configured: [],
              login_host_blocked_reason: 'هیچ دامنه‌ای برایِ ورودِ کاربر تأیید نشده' });
    render_();
    await waitFor(() => expect(screen.getByTestId('connect-blocked')).toBeTruthy());
    expect(screen.getByTestId('connect-blocked').textContent).toContain('تأیید نشده');
  });

  it('CONNECTED فقط وقتی سرور بگوید', async () => {
    respond({ status: 'success', last_verify: { state: 'CONNECTED', reason: 'از پرسشِ صریح' },
              browser: { open: true, profile_kept: false }, login_hosts_configured: ['mts.example'] });
    render_();
    await waitFor(() => expect(screen.getByTestId('connect-broker-row').textContent).toContain('متصل'));
  });

  it('هیچ ورودیِ رمز/نشانی درِ این ردیف نیست و کنش‌ها به مسیرهایِ واقعی‌اند', async () => {
    respond({ status: 'success', last_verify: {}, browser: { open: false }, login_hosts_configured: [] });
    render_();
    await waitFor(() => expect(screen.getByTestId('connect-verify')).toBeTruthy());
    expect(document.querySelectorAll('input[type="password"]').length).toBe(0);
    fetchMock.mockClear();
    respond({ status: 'success', verify: { state: 'EXPIRED' } });
    fireEvent.click(screen.getByTestId('connect-verify'));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.endsWith('/api/execution/connect/verify'))).toBe(true);
  });

  // تازگیِ ادعا درِ لایۀ canonical ساخته می‌شود (`effective_verify`)؛ رابط فقط
  // همان را نشان می‌دهد — پس چیپِ سبز بی‌پرسشِ تازه نمی‌ماند.
  it('پرسشِ کهنه «متصل» نیست و سنِ پرسش درِ جزئیات خوانده می‌شود', async () => {
    respond({ status: 'success',
              last_verify: { state: 'UNKNOWN', verified_state: 'CONNECTED', stale: true,
                             age_s: 7200, reason: 'پرسشِ اتصال قدیمی است' },
              browser: { open: false }, login_hosts_configured: ['mts.example'] });
    render_();
    // خطِ سنِ پرسش حتی بی‌داده هم رندر می‌شود؛ پس شاهدِ واقعی باید خودِ عدد باشد،
    // وگرنه آزمون بی‌ رسیدنِ پاسخ هم سبز می‌ماند (سنجشِ خودِ سنجه).
    await waitFor(() => expect(screen.getByTestId('connect-verify-age').textContent)
      .toContain('کهنه'));
    expect(screen.getByTestId('connect-verify-age').textContent).toContain('۱۲۰');
    expect(screen.getByTestId('connect-broker-row').textContent).not.toContain('متصل');
    expect(screen.getByTestId('connect-broker-row').textContent).toContain('نامعلوم');
  });
});

