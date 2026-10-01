// __tests__/updater-install-reset-v1069.spec.ts -- پچِ که اعمال شد، «خطایِ اتصال» نیست
//
// گزارشِ مالک: «دلتا پچ فکر کنم یه باگی داره، اعمال نمیشه». سنجشِ زنده رویِ
// نصبیِ ۱٫۰٫۶۵ نشان داد پچ **درست** اعمال می‌شود (۱٫۴۵۹/۱٫۴۵۹ فایلِ manifest
// سرجا، user.db بدونِ تغییر) ولی POST /api/update/install هیچ پاسخی نمی‌داد،
// چون سرور وسطِ همان درخواست os._exit می‌کرد. درخواست با connection reset
// می‌مرد و فرانت‌اند آن را «اتصال به سرور برقرار نشد، اینترنت‌ات را چک کن»
// می‌خواند. یعنیِ یک آپدیتِ موفق در چِشمِ کاربر شکست خورده به‌نظر می‌آمد.
//
// این تست همان مسیر را بازنمایش می‌کند: نصب پاسخی نمی‌دهد (reset)، و هوک باید
// نسخهٔ تازه را بپاید و 'ready-to-restart' بدهد -- نه 'error'.
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const httpMock = vi.fn();
vi.mock('@shared/api/http', () => ({
  http: (...args: unknown[]) => httpMock(...args),
  HttpError: class extends Error {},
}));

import { useAppUpdater } from '../features/updater/useAppUpdater';

const CHECK = {
  status: 'success',
  current_version: '1.0.65',
  latest_version: '1.0.68',
  available: true,
  url: 'https://example/BorsTerminal_Patch_1.0.65_to_1.0.68.zip',
  signature: 'sig',
  delta: true,
  size: 12796095,
  notes: '',
  date: '',
};

function route(opts: { installThrows?: boolean; afterInstallVersion?: string }) {
  let installCalled = false;
  httpMock.mockImplementation((path: string) => {
    if (path === '/api/update/version') {
      return Promise.resolve({
        version: installCalled ? (opts.afterInstallVersion ?? '1.0.65') : '1.0.65',
        tauri: false,
      });
    }
    if (path === '/api/update/check') return Promise.resolve(CHECK);
    if (path === '/api/update/download') {
      return Promise.resolve({ status: 'started', path: 'C:/tmp/p.zip', delta: true });
    }
    if (path === '/api/update/progress') {
      return Promise.resolve({
        status: 'ready', downloaded: 12796095, total: 12796095,
        version: '1.0.68', path: 'C:/tmp/p.zip', signature: 'sig', message: '',
      });
    }
    if (path === '/api/update/install') {
      installCalled = true;
      if (opts.installThrows) {
        return Promise.reject(new Error('Network Error: connection reset by peer'));
      }
      return Promise.resolve({ status: 'installing', delta: true });
    }
    return Promise.reject(new Error('unmocked ' + path));
  });
}

describe('آپدیترِ درون‌برنامه‌ای: قطعِ ارتباط وسطِ نصب = شروعِ نصب، نه شکست', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    httpMock.mockReset();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it('وقتی سرور وسطِ install می‌میرد ولی نسخهٔ تازه بالا می‌آید، موفق گزارش می‌کند', async () => {
    route({ installThrows: true, afterInstallVersion: '1.0.68' });
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    await act(async () => { await result.current.checkForUpdates(); });
    expect(result.current.status).toBe('available');
    expect(result.current.isDelta).toBe(true);

    await act(async () => {
      const pending = result.current.startDownloadAndInstall();
      await vi.runAllTimersAsync();
      await pending;
    });

    expect(result.current.status).toBe('ready-to-restart');
    expect(result.current.errorMessage).toBeNull();
  });

  it('و اگر برنامه با نسخهٔ جدید بالا نیامد، صادقاً می‌گوید نصب کامل را بگیرید', async () => {
    route({ installThrows: true, afterInstallVersion: '1.0.65' });
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    await act(async () => { await result.current.checkForUpdates(); });
    await act(async () => {
      const pending = result.current.startDownloadAndInstall();
      await vi.runAllTimersAsync();
      await pending;
    });

    expect(result.current.status).toBe('error');
    expect(result.current.errorMessage).toContain('نصب‌کنندهٔ کامل');
  });

  it('پاسخِ عادیِ install هم همان موفقیت را می‌دهد (سرورِ تازه، بدونِ reset)', async () => {
    route({ installThrows: false });
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await vi.advanceTimersByTimeAsync(0); });

    await act(async () => { await result.current.checkForUpdates(); });
    await act(async () => {
      const pending = result.current.startDownloadAndInstall();
      await vi.runAllTimersAsync();
      await pending;
    });

    expect(result.current.status).toBe('ready-to-restart');
  });
});
