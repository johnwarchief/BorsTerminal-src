// پنجرۀ «نام و قفلِ صفحه» + سازگاریِ تم چارت (بلوکِ آخر دست‌نخورده مانده است)
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { UserSettingsModal } from '../widgets/UserSettingsModal';
import { useAuthStore } from '../shared/stores/authStore';
import { nahayatNegarLightTheme, nahayatNegarDarkTheme } from '../features/technical/nahayatnegar/lib/chartTheme';

if (!globalThis.crypto?.subtle) {
  Object.defineProperty(globalThis, 'crypto', { value: webcrypto, configurable: true });
}

async function armLock(code = '۴۴۵۵') {
  await useAuthStore.getState().setLock(code);
  useAuthStore.setState({ isAuthenticated: false });
}

describe('پنجرهٔ نام و قفلِ صفحه (UserSettingsModal)', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useAuthStore.getState().logout();
    // نامِ ازِ پیش پرشده: فرم، «نام نمایشی» را required دارد و بی‌آن،
    // مرورگر/jsbedom اصلاً submit نمی‌کند (تستِ بی‌نام، تستِ قفل نیست).
    useAuthStore.setState({ locked: false, failedAttempts: 0, lockoutUntil: null, username: 'trader' });
  });

  it('در حالت open=false چیزی رندر نمی‌شود', () => {
    const { container } = render(<UserSettingsModal open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('عنوانِ صادق است و وضعیتِ قفل «غیرفعال» نشان داده می‌شود', async () => {
    render(<UserSettingsModal open onClose={vi.fn()} />);
    expect(await screen.findByText('نام و قفلِ صفحه')).toBeInTheDocument();
    expect(screen.getByTestId('settings-lock-state').textContent).toContain('غیرفعال');
    // ادعایِ «احراز هویت امن» حذف شده است:
    expect(screen.getByText(/قفلِ نمایشیِ محلی/)).toBeInTheDocument();
  });

  it('کدِ کوتاه قفل نمی‌شود و پیامش می‌آید', async () => {
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-username'), { target: { value: 'trader' } });
    fireEvent.change(screen.getByTestId('settings-new-code'), { target: { value: '123' } });
    fireEvent.change(screen.getByTestId('settings-confirm-code'), { target: { value: '123' } });
    fireEvent.click(screen.getByTestId('settings-submit'));
    await waitFor(() => expect(screen.getByTestId('settings-error')).toHaveTextContent('۴ رقم'));
    expect(useAuthStore.getState().locked).toBe(false);
  });

  it('کدِ درست قفل را فعال می‌کند و رویِ دیسک هش می‌ماند', async () => {
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-username'), { target: { value: 'trader' } });
    fireEvent.change(screen.getByTestId('settings-new-code'), { target: { value: '۴۴۵۵' } });
    fireEvent.change(screen.getByTestId('settings-confirm-code'), { target: { value: '4455' } });
    fireEvent.click(screen.getByTestId('settings-submit'));

    await waitFor(() => expect(screen.getByTestId('settings-success')).toBeInTheDocument());
    expect(useAuthStore.getState().locked).toBe(true);
    expect((screen.getByTestId('settings-lock-state').textContent || '')).toContain('فعال');
    const blob = localStorage.getItem('bors_screen_lock') || '';
    expect(blob).toContain('PBKDF2-SHA256');
    expect(blob).not.toContain('4455');
    expect(useAuthStore.getState().username).toBe('trader');
  });

  it('بی‌کدِ فعلی، تغییرِ کد رد می‌شود', async () => {
    await armLock();
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-new-code'), { target: { value: '9999' } });
    fireEvent.change(screen.getByTestId('settings-confirm-code'), { target: { value: '9999' } });
    fireEvent.click(screen.getByTestId('settings-submit'));
    await waitFor(() => expect(screen.getByTestId('settings-error')).toHaveTextContent('کدِ فعلی'));
    expect(useAuthStore.getState().locked).toBe(true);
  });

  it('کدِ فعلیِ غلط قفل را برندارد', async () => {
    await armLock();
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-current-code'), { target: { value: '0000' } });
    fireEvent.click(screen.getByTestId('settings-submit'));
    await waitFor(() => expect(screen.getByTestId('settings-error')).toBeInTheDocument());
    expect(useAuthStore.getState().locked).toBe(true);
  });

  it('کدِ فعلیِ درست، قفل را برمی‌دارد (و نام ذخیره می‌ماند)', async () => {
    await armLock();
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-username'), { target: { value: 'analyst' } });
    fireEvent.change(screen.getByTestId('settings-current-code'), { target: { value: '4455' } });
    fireEvent.click(screen.getByTestId('settings-submit'));
    await waitFor(() => expect(screen.getByTestId('settings-success')).toHaveTextContent('برداشته شد'));
    expect(useAuthStore.getState().locked).toBe(false);
    expect(localStorage.getItem('bors_screen_lock')).toBeNull();
  });

  it('تغییرِ کد با کدِ فعلیِ درست انجام می‌شود و کدِ قدیمی دیگر نمی‌گشاید', async () => {
    await armLock();
    render(<UserSettingsModal open onClose={vi.fn()} />);
    fireEvent.change(screen.getByTestId('settings-current-code'), { target: { value: '4455' } });
    fireEvent.change(screen.getByTestId('settings-new-code'), { target: { value: '۷۷۸۸' } });
    fireEvent.change(screen.getByTestId('settings-confirm-code'), { target: { value: '7788' } });
    fireEvent.click(screen.getByTestId('settings-submit'));
    await waitFor(() => expect(screen.getByTestId('settings-success')).toHaveTextContent('عوض شد'));

    useAuthStore.setState({ isAuthenticated: false });
    expect((await useAuthStore.getState().unlock('4455')).success).toBe(false);
    expect((await useAuthStore.getState().unlock('۷۷۸۸')).success).toBe(true);
  });
});

describe('سازگاری تم روشنایی چارت تکنیکال (nahayatNegarLightTheme)', () => {
  // بازطراحیِ AntiGravity (c12f88e6): پالتِ تم تغییر کرد — گریدِ روشن
  // #eef2f8 → #f0f3fa و گریدِ تاریک #242832 → #242731. مقادیرِ زیر باید
  // دقیقاً همانِ chartTheme.ts باشند، وگرنی این تست بهجایِ چک کردنِ کنتراست،
  // فقط قدیمی بودنِ خودش را ثابت می‌کند.
  it('تم روشنایی دارای خطوط گرید روشن و کنتراست مناسب است', () => {
    expect(nahayatNegarLightTheme.grid.horizontal.color).toBe('#f0f3fa');
    expect(nahayatNegarLightTheme.grid.vertical.color).toBe('#f0f3fa');
    expect(nahayatNegarLightTheme.xAxis.axisLine.color).toBe('#e2e8f0');
    expect(nahayatNegarLightTheme.xAxis.tickText.color).toBe('#434651');
    expect(nahayatNegarLightTheme.overlay.text.color).toBe('#0f172a');
  });

  it('تم تاریک پیشین کماکان با رنگ‌های اصیل TradingView موجود است', () => {
    expect(nahayatNegarDarkTheme.grid.horizontal.color).toBe('#242731');
    expect(nahayatNegarDarkTheme.xAxis.axisLine.color).toBe('#2a2e39');
  });
});
