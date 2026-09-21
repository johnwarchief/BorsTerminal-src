import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UpdateManagerModal } from '../features/updater/UpdateManagerModal';
import { useAppUpdater, isTauriEnvironment } from '../features/updater/useAppUpdater';
import { renderHook, act } from '@testing-library/react';
// منبعِ واحدِ حقیقتِ نسخه: همان فایلی که vite در زمان build می‌خواند.
import pkg from '../../package.json';

describe('سیستم مدیریت به‌روزرسانی (Tauri v2 / Web Fallback)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('تشخیص محیط غیر Tauri در تست یا مرورگر معمولی', () => {
    expect(isTauriEnvironment()).toBe(false);
  });

  it('هوک useAppUpdater وضعیت اولیه صحیح برمی‌گرداند', () => {
    const { result } = renderHook(() => useAppUpdater());
    expect(result.current.status).toBe('idle');
    expect(result.current.currentVersion).toBe(pkg.version);
    expect(result.current.newVersion).toBeNull();
    expect(result.current.downloadProgress).toBe(0);
  });

  // آپدیتِ آفلاین (useAppUpdater.handleOfflineZipSelect) فقط نصب‌کنندهٔ .exe
  // به همراهِ فایلِ امضایِ .sig را می‌پذیرد. این تست همان قرارداد را می‌سنجد:
  // بدونِ .sig باید خطایِ واضح بدهد. چون گاردِ .sig قبل از setStatus انجام
  // می‌شود، نتیجهٔ نهایی 'error' است (نه 'downloading').
  it('هوک useAppUpdater نصب‌کنندهٔ آفلاین بدون امضا را رد می‌کند', async () => {
    const { result } = renderHook(() => useAppUpdater());

    const dummyExe = new File(['dummy content'], 'BorsTerminal_1.1.0_x64_Setup.exe', { type: 'application/vnd.microsoft.portable-executable' });

    act(() => {
      result.current.handleOfflineZipSelect(dummyExe);
    });

    await waitFor(() => {
      expect(result.current.status).toBe('error');
    }, { timeout: 3000 });

    expect(result.current.errorMessage).toContain('.sig');
  });

  it('کامپوننت UpdateManagerModal در صورت باز بودن به درستی رندر می‌شود', async () => {
    const handleClose = vi.fn();
    render(<UpdateManagerModal open={true} onClose={handleClose} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('مدیریت به‌روزرسانی سیستم')).toBeInTheDocument();
    expect(screen.getByText(/نسخه فعلی:/)).toBeInTheDocument();
    // برچسبِ محیط در حالتِ غیرِ Tauri: «مرورگر · هستهٔ پایتون» (قبلاً
    // «محیط وب / ایزوله» بود). این تست را باِ کدِ واقعی هماهنگ کردیم.
    expect(screen.getByText(/مرورگر · هستهٔ پایتون/)).toBeInTheDocument();
    expect(screen.getByText(/بارگذاری دستی بسته آفلاین/)).toBeInTheDocument();

    const closeBtn = screen.getByLabelText('بستن پنجره');
    fireEvent.click(closeBtn);
    expect(handleClose).toHaveBeenCalled();
  });

  it('کامپوننت در صورت open=false چیزی رندر نمی‌کند', () => {
    const { container } = render(<UpdateManagerModal open={false} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
