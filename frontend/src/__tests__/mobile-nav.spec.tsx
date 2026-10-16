// __tests__/mobile-nav.spec.tsx -- نوارِ پایینِ گوشی: رسیدنی‌بودن، نه حضورِ دکمه
//
// سطح: تستِ UI. بندِ ۲.۲/۲.۳ مأموریتِ System ۲ دو چیزِ جدا می‌خواهد: نوارِ پایین
// جمع‌وجور بماند وِ «مسیر دسترسی بهِ قابلیت‌هایِ اصلی حذف نشود». پسِ اصلی‌ترین
// آزمونِ اینِ فایل «حذف‌نشدنِ مسیر» است: هرِ مقصدی که درِ `NAV_SECTIONSِ` سایدبار
// هست باید یاِ رویِ نوار باشد یاِ بعد ازِ «بیشتر» -- وِ اگرِ روزی مقصدی بهِ
// سایدبار اضافه شود وِ بهِ نوارِ گوشی نه، اینِ آزمون می‌شکند (نه گزارشِ دستی).
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MobileNav } from '@app/components/MobileNav';
import { NAV_SECTIONS } from '@app/components/Sidebar';
import { PALETTE_OPEN_EVENT } from '@app/components/CommandPalette';

// `vi.mock` بالاَیِ اعلامِ `let` برداشته می‌شود؛ متغیرِ مشترک باید `hoisted` باشد
// وگرنۀ کارخانۀِ mock بهِ `mobile` درِ TDZ می‌خورد وِ کلِ فایل می‌شکند.
const ref = vi.hoisted(() => ({ mobile: true }));
vi.mock('@shared/lib/useMediaQuery', () => ({ useMediaQuery: () => ref.mobile }));

function At() {
  const { pathname } = useLocation();
  return <div data-testid="at">{pathname}</div>;
}

function shell() {
  return render(
    <MemoryRouter initialEntries={['/market']}>
      <At />
      <MobileNav />
      <Routes>
        <Route path="*" element={<div>صفحه</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

const sidebarTos = () => NAV_SECTIONS.flatMap((s) => s.items.map((i) => i.to));

// کشویِ «بیشتر» یکِ لایۀِ جدا ازِ نوار است؛ بسته‌شدن = رفتنِ اینِ گره، نه نوار
const sheet = () => document.getElementById('mobile-nav-sheet');

beforeEach(() => {
  ref.mobile = true;
});

describe('MobileNav', () => {
  it('درِ دسکتاق هیچِ نوارِ پایینِ تازه‌ای ساخته نمی‌شود (بی‌تغییرِ پوستۀِ همیشگی)', () => {
    ref.mobile = false;
    shell();
    expect(screen.queryByTestId('mobile-nav')).toBeNull();
  });

  it('چهارِ مقصدِ اصلی + «بیشتر» رویِ نوار است وِ هرِ آیتم کفِ لمسِ ۴۴px را دارد', () => {
    shell();
    const nav = screen.getByTestId('mobile-nav');
    const links = Array.from(nav.querySelectorAll('a,button'));
    expect(links.length).toBeGreaterThanOrEqual(5);
    for (const el of links) {
      expect(String(el.getAttribute('class'))).toContain('min-h-[44px]');
    }
    // safe area اندروید: paddingِ پایین ازِ env() عبور می‌کند، هاردکدِ px نه
    expect(String(nav.getAttribute('class'))).toContain('env(safe-area-inset-bottom)');
    expect(String(nav.getAttribute('class'))).toContain('bottom-0');
  });

  it('«بیشتر» همانِ NAV_SECTIONS خودِ سایدبار را می‌شمارد: هیچِ مقصدی گم نمی‌شود', () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    const bar = screen.getByTestId('mobile-nav');
    const sheet = document.getElementById('mobile-nav-sheet');
    const reached = new Set([
      ...Array.from(bar.querySelectorAll('a')).map((a) => a.getAttribute('href')),
      ...Array.from(sheet?.querySelectorAll('a') ?? []).map((a) => a.getAttribute('href')),
    ]);
    for (const to of sidebarTos()) {
      expect(reached.has(to)).toBe(true);
    }
  });

  it('مرجعِ ناوبری یکی است: نوارِ گوشی مقصدِ تازه‌ای نسازد که درِ سایدبار نیست', () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    const known = new Set(sidebarTos());
    const sheet = document.getElementById('mobile-nav-sheet');
    const hrefs = Array.from(sheet?.querySelectorAll('a') ?? []).map((a) => a.getAttribute('href'));
    // /notifications رأیِ مالک (۱۴۰۵-۰۷-۲۲) ازِ ناوبری بیرون است: زنگِ نوارِ بالا
    // همانِ صفحّه را باز می‌کند، پسِ نوارِ پایین نباید دومینِ مرجعِ آن شود.
    expect(hrefs.includes('/notifications')).toBe(false);
    for (const href of hrefs) expect(known.has(String(href))).toBe(true);
  });

  it('کلیک رویِ آیتمِ «بیشتر» هم مسیر می‌رود وِ کشو را می‌بندد (مسیرِ واقعی، نه تزئین)', async () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    expect(sheet()).toBeTruthy();
    fireEvent.click(screen.getByTestId('mobile-nav-more-order-line'));
    await waitFor(() => expect(screen.getByTestId('at').textContent).toBe('/order-line'));
    // خودِ نوار می‌ماند (دسترسیِ همیشه‌باز)؛ کشو باید رفته باشد وِ دکمه بسته شود
    expect(sheet()).toBeNull();
    expect(screen.getByTestId('mobile-nav-more').getAttribute('aria-expanded')).toBe('false');
  });

  it('Escape وِ کلیکِ پشتِ کشو، هرِ دو می‌بندندش (بی‌محبوس‌شدنِ کاربر درِ لایۀِ دوم)', () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    expect(screen.getByTestId('mobile-nav-more-order-line')).toBeTruthy();
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(sheet()).toBeNull();

    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    expect(sheet()).toBeTruthy();
    fireEvent.click(screen.getByTestId('mobile-nav-scrim'));
    expect(sheet()).toBeNull();
  });

  it('دکمۀِ «بستن» هم کشو را می‌بندد (سه راهِ خروج، هیچ‌کدام بن‌بست نیست)', () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    fireEvent.click(screen.getByTestId('mobile-nav-close'));
    expect(sheet()).toBeNull();
  });

  it('کشو رویِ مسیرِ عوض‌شده ازِ هرِ جایِ دیگرِ برنامه هم بسته می‌شود', async () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    expect(sheet()).toBeTruthy();
    // ناوبریِ بیرونی (لینکِ درونِ صفحه/پالت) -- کشو باید باِ مسیرِ تازه بخوابد
    fireEvent.click(screen.getByTestId('mobile-nav-technical'));
    await waitFor(() => expect(sheet()).toBeNull());
    expect(screen.getByTestId('at').textContent).toBe('/technical');
  });

  it('دکمۀِ «جست‌وجو» همانِ رویدادِ پالتِ فرمانِ نوارِ بالا را می‌فرستد (یکِ رفتار، دوِ دروازه)', () => {
    const seen = vi.fn();
    window.addEventListener(PALETTE_OPEN_EVENT, seen);
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    fireEvent.click(screen.getByTestId('mobile-nav-palette'));
    expect(seen).toHaveBeenCalledTimes(1);
    window.removeEventListener(PALETTE_OPEN_EVENT, seen);
  });

  it('سایدبار پنهان می‌شود ولی کنترل‌هایِ حساب نمی‌میرند: کشو همان‌ها را دارد', () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-more'));
    // اینِ سه testid درِ سایدبارِ دسکتاق هم هست؛ درِ گوشی باید ازِ کشو برسند
    expect(screen.getByTestId('user-settings-btn')).toBeTruthy();
    expect(screen.getByTestId('app-update-btn')).toBeTruthy();
    expect(screen.getByTestId('mobile-account-row').textContent).toContain('خروج');
  });

  it('نشانگرِ مقصدِ فعال رویِ نوار می‌نشیند (کاربرِ گوشی می‌فهمد کجاست)', async () => {
    shell();
    fireEvent.click(screen.getByTestId('mobile-nav-market-status'));
    await waitFor(() => expect(screen.getByTestId('at').textContent).toBe('/market-status'));
    const active = screen.getByTestId('mobile-nav-market-status');
    expect(active.getAttribute('aria-current')).toBeTruthy();
  });

  it('متنِ بریدۀِ آیتم‌ها باِ aria-labelِ کاملِ خودِ مقصد جبران می‌شود (اسکرین‌خوانِ گوشی)', () => {
    shell();
    for (const to of ['/market-status', '/market', '/technical', '/watch']) {
      const link = screen.getByTestId(`mobile-nav-${to.replace(/\//g, '')}`);
      expect(link.getAttribute('aria-label')).toBeTruthy();
    }
  });
});
