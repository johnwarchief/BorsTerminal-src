// __tests__/updater-portable-v1083.spec.ts -- پرتابیل نصاب اجرا نمی‌کند، لینکِ ZIP می‌دهد
//
// بندِ ۴ مأموریتِ انتشار: «Updater نصب‌شده نباید در حالت Portable به‌طور
// ناخواسته Inno Setup را اجرا یا فایل‌های پوشهٔ Portable را خراب کند».
// بک‌اند درِ `/api/update/check` می‌گوید `portable: true` و `installable: false`
// و `signature` را خالی می‌فرستد. اگر هوک همان مسیرِ همیشگی را برود، دو چیز
// غلط می‌شود: یا «تا‌به‌روز» می‌خواند (چون امضا نیست و آپدیتِ واقعی پنهان
// می‌ماند) یا download را بدونِ امضا صدا می‌زند. این تست هر دو را می‌بندد.
import { renderHook, act, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

const httpMock = vi.fn();
vi.mock('@shared/api/http', () => ({
  http: (...args: unknown[]) => httpMock(...args),
  HttpError: class extends Error {},
}));

import { useAppUpdater } from '../features/updater/useAppUpdater';

const PORTABLE_CHECK = {
  status: 'success',
  current_version: '1.0.83',
  latest_version: '1.0.84',
  available: true,
  url: 'https://github.com/johnwarchief/BorsTerminal/releases/latest/download/' +
       'BorsTerminal_Ultimate_Portable_v1.0.84.zip',
  signature: '',
  updater: 'portable',
  delta: false,
  portable: true,
  installable: false,
  message: 'این نسخۀ Portable است؛ نصب‌کنندهٔ ویندوز اجرا نمی‌شود.',
  notes: 'تازه',
  date: '2026-10-12T09:00:00Z',
  size: 71000000,
};

beforeEach(() => {
  httpMock.mockReset();
  httpMock.mockImplementation((path: string) => {
    if (path === '/api/update/version') {
      return Promise.resolve({ version: '1.0.83', tauri: false, mode: 'portable', instance: 'abc' });
    }
    if (path === '/api/update/check') return Promise.resolve(PORTABLE_CHECK);
    return Promise.reject(new Error(`اندپوینتِ غیرمنتظره: ${path}`));
  });
});

describe('به‌روزرسانی در حالت Portable', () => {
  it('آپدیت را می‌بیند و لینکِ ZIP را نگه می‌دارد (بی‌آن «تا‌به‌روز» بگوید)', async () => {
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await result.current.checkForUpdates(); });
    await waitFor(() => expect(result.current.status).toBe('available'));
    expect(result.current.newVersion).toBe('1.0.84');
    expect(result.current.portableUpdate?.url).toBe(PORTABLE_CHECK.url);
    expect(result.current.portableUpdate?.message).toBe(PORTABLE_CHECK.message);
    expect(result.current.isDelta).toBe(false);
  });

  it('هیچ درخواستِ download/install نمی‌زند — حتی اگر کاربر دکمه را بزند', async () => {
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await result.current.checkForUpdates(); });
    await act(async () => { await result.current.startDownloadAndInstall(); });
    const paths = httpMock.mock.calls.map((c) => String(c[0]));
    expect(paths).not.toContain('/api/update/download');
    expect(paths).not.toContain('/api/update/install');
    expect(paths).not.toContain('/api/update/progress');
  });

  it('بی‌آپدیتِ تازه لینکِ پرتابیل ساخته نمی‌شود (پیامِ کاذب نداریم)', async () => {
    httpMock.mockImplementation((path: string) => {
      if (path === '/api/update/version') {
        return Promise.resolve({ version: '1.0.83', tauri: false, mode: 'portable' });
      }
      return Promise.resolve({ ...PORTABLE_CHECK, available: false, latest_version: '1.0.83' });
    });
    const { result } = renderHook(() => useAppUpdater());
    await act(async () => { await result.current.checkForUpdates(); });
    expect(result.current.status).toBe('up-to-date');
    expect(result.current.portableUpdate).toBeNull();
  });
});
