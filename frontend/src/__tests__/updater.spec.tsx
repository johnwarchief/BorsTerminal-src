import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { UpdateManagerModal } from '../features/updater/UpdateManagerModal';
import { useAppUpdater, isTauriEnvironment } from '../features/updater/useAppUpdater';
import { renderHook, act } from '@testing-library/react';

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
    expect(result.current.currentVersion).toBe('1.0.1');
    expect(result.current.newVersion).toBeNull();
    expect(result.current.downloadProgress).toBe(0);
  });

  it('هوک useAppUpdater قابلیت بارگذاری دستی فایل زیپ آفلاین را دارد', async () => {
    const { result } = renderHook(() => useAppUpdater());

    const dummyFile = new File(['dummy content'], 'BorsTerminal_1.1.0_x64.zip', { type: 'application/zip' });

    act(() => {
      result.current.handleOfflineZipSelect(dummyFile);
    });

    expect(result.current.status).toBe('downloading');

    await waitFor(() => {
      expect(result.current.status).toBe('ready-to-restart');
    }, { timeout: 3000 });

    expect(result.current.newVersion).toBe('1.1.0');
  });

  it('کامپوننت UpdateManagerModal در صورت باز بودن به درستی رندر می‌شود', async () => {
    const handleClose = vi.fn();
    render(<UpdateManagerModal open={true} onClose={handleClose} />);

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getByText('مدیریت به‌روزرسانی سیستم')).toBeInTheDocument();
    expect(screen.getByText(/نسخه فعلی:/)).toBeInTheDocument();
    expect(screen.getByText(/محیط وب \/ ایزوله/)).toBeInTheDocument();
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
