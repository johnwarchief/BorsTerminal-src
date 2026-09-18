import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { UserSettingsModal } from '../widgets/UserSettingsModal';
import { useAuthStore } from '../shared/stores/authStore';
import { nahayatNegarLightTheme, nahayatNegarDarkTheme } from '../features/technical/nahayatnegar/lib/chartTheme';

describe('پنجره تنظیمات کاربر و امنیت (UserSettingsModal)', () => {
  beforeEach(() => {
    useAuthStore.getState().resetCredentials();
    useAuthStore.getState().login('admin', 'bors123');
  });

  it('در حالت open=false چیزی رندر نمی‌شود', () => {
    const { container } = render(<UserSettingsModal open={false} onClose={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it('در حالت open=true فیلدهای نام کاربری و رمز عبور نمایش می‌یابند', () => {
    render(<UserSettingsModal open={true} onClose={vi.fn()} />);
    expect(screen.getByText('تنظیمات حساب کاربری و امنیت')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('admin')).toHaveValue('admin');
  });

  it('ثبت بدون رمز عبور فعلی پیام خطا می‌دهد', async () => {
    render(<UserSettingsModal open={true} onClose={vi.fn()} />);
    const submitBtn = screen.getByText('ذخیره تغییرات');
    const form = submitBtn.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('رمز عبور فعلی');
    });
  });

  it('عدم تطابق رمز عبور جدید و تکرار آن خطای متناظر را نشان می‌دهد', async () => {
    render(<UserSettingsModal open={true} onClose={vi.fn()} />);

    const currentPassInput = screen.getByPlaceholderText('جهت تایید هویت، رمز عبور فعلی را وارد کنید');
    const newPassInput = screen.getByPlaceholderText('اگر قصد تغییر رمز را دارید، رمز جدید را وارد کنید');

    fireEvent.change(currentPassInput, { target: { value: 'bors123' } });
    fireEvent.change(newPassInput, { target: { value: 'newpass123' } });

    const confirmPassInput = screen.getByPlaceholderText('تکرار رمز عبور جدید');
    fireEvent.change(confirmPassInput, { target: { value: 'different' } });

    const submitBtn = screen.getByText('ذخیره تغییرات');
    const form = submitBtn.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('همخوانی');
    });
  });

  it('به‌روزرسانی موفق نام کاربری و پیام تایید', async () => {
    render(<UserSettingsModal open={true} onClose={vi.fn()} />);

    const userInput = screen.getByPlaceholderText('admin');
    const currentPassInput = screen.getByPlaceholderText('جهت تایید هویت، رمز عبور فعلی را وارد کنید');

    fireEvent.change(userInput, { target: { value: 'super_admin' } });
    fireEvent.change(currentPassInput, { target: { value: 'bors123' } });

    const submitBtn = screen.getByText('ذخیره تغییرات');
    const form = submitBtn.closest('form')!;
    fireEvent.submit(form);

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('با موفقیت به‌روزرسانی شد');
    });

    expect(useAuthStore.getState().username).toBe('super_admin');
  });
});

describe('سازگاری تم روشنایی چارت تکنیکال (nahayatNegarLightTheme)', () => {
  it('تم روشنایی دارای خطوط گرید روشن و کنتراست مناسب است', () => {
    expect(nahayatNegarLightTheme.grid.horizontal.color).toBe('#eef2f8');
    expect(nahayatNegarLightTheme.grid.vertical.color).toBe('#eef2f8');
    expect(nahayatNegarLightTheme.xAxis.axisLine.color).toBe('#e2e8f0');
    expect(nahayatNegarLightTheme.xAxis.tickText.color).toBe('#64748b');
    expect(nahayatNegarLightTheme.overlay.text.color).toBe('#0f172a');
  });

  it('تم تاریک پیشین کماکان با رنگ‌های اصیل TradingView موجود است', () => {
    expect(nahayatNegarDarkTheme.grid.horizontal.color).toBe('#242832');
    expect(nahayatNegarDarkTheme.xAxis.axisLine.color).toBe('#2a2e39');
  });
});
