// __tests__/market-session-phase.spec.tsx — بلوکِ «مرحلِ جلسه» (بند ۵ مأموریت)
// سه چیز باید رویِ صفحه خوانده شود: مرحل از وضعیتِ رسمی می‌آید یا از تقویم
// (و فرقشان صریح است)، درِ مرحلِ غیرقابلِ داوری هیچ حکمی داده نمی‌شود، و
// فهرستِ «چه چیزی معنا ندارد» با علتش می‌آید. هیچ حکمی درِ رابط ساخته نمی‌شود.
import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { MarketPhasePanel } from '@features/market/components/MarketStatusPanels';
import type { SessionPhaseFeed } from '@features/market/api/useMarketStatusFeed';

vi.stubGlobal('fetch', vi.fn(() => Promise.reject(new Error('شبکه خاموش'))));

const base = {
  status: 'ok', phase: 'pre_open', label: 'پیش از آغازِ معاملات',
  phase_source: 'tsetmc_marketState', official: true,
  official_state: 'F', official_state_title: 'بسته',
  session_day: 20261011, activity_h_even: 82000, is_live: false,
  verdict_allowed: false,
  computable: { realized_flow: false, order_pressure: true,
                session_vs_threshold: false, close_price_final: false },
  not_computable: ['realized_flow', 'session_vs_threshold', 'close_price_final'],
  why_not: {
    realized_flow: 'هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست',
    session_vs_threshold: 'جمعِ نشست کامل نشده، پس با آستانۀِ تمام‌روز سنجیده نمی‌شود',
    close_price_final: 'قیمت پایانیِ نهایی هنوز ساخته نشده',
    order_pressure: '',
  },
  clock_now: '2026-10-11 08:20:00', session_start: '09:00', session_end: '12:30',
  source: 'local:market.db',
} as unknown as SessionPhaseFeed;

const panel = (over: Partial<SessionPhaseFeed> = {}) =>
  render(<MarketPhasePanel data={{ ...base, ...over }} isLoading={false}
                           isError={false} onRetry={() => {}} />);

const text = () => screen.getByTestId('status-session-phase').textContent ?? '';

describe('بلوک مرحلِ جلسه', () => {
  it('پیش از آغاز: برچسبِ مرحل، «از وضعیتِ رسمی»، و هیچ حکمی', () => {
    panel();
    expect(screen.getByTestId('status-session-phase-label').getAttribute('data-phase'))
      .toBe('pre_open');
    expect(screen.getByTestId('status-session-phase-source').textContent)
      .toContain('از وضعیتِ رسمیِ بازار');
    expect(screen.getByTestId('status-session-phase-verdict').textContent)
      .toContain('هیچ حکمِ مساعد/نامساعدی صادر نمی‌شود');
    // نشستِ خودش با تاریخِ خودش، نه بی‌تاریخ
    expect(screen.getByTestId('status-session-phase-day').textContent).toContain('۱۴۰');
  });

  it('فهرستِ «معنا ندارد» با علتِ هر مورد می‌آید (و صفِ سفارش از آن جداست)', () => {
    panel();
    const missing = screen.getByTestId('status-session-phase-missing').textContent ?? '';
    expect(missing).toContain('جریانِ پولِ تحقق‌یافته');
    expect(missing).toContain('پولِ تحقق‌یافته یکی نیست');
    expect(missing).toContain('سنجشِ جمعِ نشست با آستانۀِ تمام‌روز');
    expect(missing).not.toContain('فشارِ سفارش‌ها');   // این درِ pre_open معنا دارد
  });

  it('معاملات جاری: داوری آزاد است و صفِ معنا‌ندارده نمایش داده نمی‌شود', () => {
    panel({
      phase: 'continuous', label: 'معاملات جاری', is_live: true, verdict_allowed: true,
      computable: { realized_flow: true, order_pressure: true,
                    session_vs_threshold: true, close_price_final: false },
      not_computable: ['close_price_final'],
      why_not: { close_price_final: 'قیمتِ پایانیِ نهایی هنوز ساخته نشده' },
    });
    expect(screen.getByTestId('status-session-phase-label').getAttribute('data-live')).toBe('1');
    expect(screen.getByTestId('status-session-phase-verdict').textContent)
      .toContain('قابلِ داوری است');
    expect(screen.getByTestId('status-session-phase-missing').textContent)
      .toContain('قیمتِ پایانیِ نهایی');
  });

  it('بی‌وضعیتِ رسمی ⇒ «از تقویم» و نه ادعایِ رسمی', () => {
    panel({ official: false, phase_source: 'calendar', official_state: null,
            official_state_title: null });
    expect(screen.getByTestId('status-session-phase-source').textContent)
      .toContain('از تقویم');
  });

  it('بی‌پاسخ ⇒ «مرحل ادعا نمی‌شود»، نه صفر و نه حکم', () => {
    render(<MarketPhasePanel data={undefined} isLoading={false} isError onRetry={() => {}} />);
    expect(screen.getByTestId('status-session-phase-error')).toBeInTheDocument();
    expect(text()).not.toContain('مساعد');
  });
});
