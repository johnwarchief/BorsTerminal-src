// features/updater/useAppUpdater.ts -- هوکِ مدیریتِ به‌روزرسانیِ درون‌برنامه‌ای
// تنها آپدیترِ واقعی، هستهٔ پایتون (api/update.py) است. شاخه‌های Tauri حذف
// شدند: بیلدِ منتشرشده از bors_entry.py بالا می‌آید و هرگز __TAURI_INTERNALS__
// ندارد، پس آن مسیرها در عمل اجرا نمی‌شدند ولی در باندل می‌ماندند.
import { useState, useCallback, useEffect, useRef } from 'react';
import { http, HttpError } from '@shared/api/http';
// نسخهٔ واقعی برنامه — منبعِ واحدِ حقیقت package.json است و در زمان build درون
// باندل اینلاین می‌شود، تا placeholderهای فرانت‌اند هرگز استیل نشوند.
import { APP_VERSION } from '@shared/version';

export interface UpdateInfo {
  version: string;
  currentVersion: string;
  body?: string;
  date?: string;
}

export type UpdaterStatus =
  | 'idle'
  | 'checking'
  | 'available'
  | 'up-to-date'
  | 'downloading'
  | 'ready-to-restart'
  | 'error';

/**
 * قراردادِ فرانت‌اند با api/update.py — مسیرهای به‌روزرسانِ واقعیِ پایتون.
 * این‌ها شبیه‌سازی نیستند؛ هر فیلد دقیقاً خروجیِ همان اندپوینت است.
 */
interface CheckResponse {
  status: 'success' | 'error';
  current_version: string;
  latest_version?: string;
  available?: boolean;
  notes?: string;
  date?: string;
  url?: string;
  signature?: string;
  updater?: string;
  message?: string;
  /** v1.0.10: بستهٔ پیشنهادی، پچِ دلتاست (حجمِ بسیار کمتر) یا نصبِ کامل */
  delta?: boolean;
  /** حجمِ بایتِ بستهٔ انتخاب‌شده (پچ یا نصب‌کننده) */
  size?: number;
}

interface ProgressResponse {
  status: 'idle' | 'downloading' | 'verifying' | 'ready' | 'installing' | 'error';
  downloaded: number;
  total: number;
  version: string;
  path: string;
  signature: string;
  message: string;
}

interface InstallResponse {
  status: 'installing' | 'error';
  log?: string;
  flags?: string[];
  message?: string;
}

interface PendingUpdate {
  url: string;
  signature: string;
  version: string;
}

/** خروجیِ /api/update/version — نسخهٔ هستهٔ پایتون */
interface VersionResponse {
  version: string;
  tauri: boolean;
}

/**
 * پیامِ خطای کاربرپسند — متنِ خامِ استثناهای پایتون (مثلاً
 * "ValueError: signature verification failed") را به فارسیِ قابلِ فهم
 * تبدیل می‌کند. جزئیاتِ فنیِ پیام اصلی برای دیباگ در console لاگ می‌شود
 * ولی هرگز به کاربر نشان داده نمی‌شود.
 */
function friendlyErrorMessage(raw: string | null | undefined): string {
  const msg = (raw || '').trim();
  if (!msg) return 'عملیات ناموفق بود؛ لطفاً دوباره تلاش کنید.';
  const low = msg.toLowerCase();
  if (/signature verification failed|bad signature|tampered|minisign|key id|public key/.test(low)) {
    return 'راستی‌آزمایی امضای دیجیتال ناموفق بود. بستهٔ دریافت‌شده دستکاری شده یا ناقص است؛ دوباره تلاش کنید.';
  }
  if (/connection|timeout|timed out|failed to fetch|network|dns|reset by peer/.test(low)) {
    return 'اتصال به سرور برقرار نشد. اینترنت خود را بررسی کرده و دوباره تلاش کنید.';
  }
  if (/404|not found|یافت نشد/.test(low)) {
    return 'بستهٔ نصبِ این نسخه روی سرور یافت نشد.';
  }
  if (/403|401|forbidden|unauthorized|دسترسی/.test(low)) {
    return 'دسترسی به سرورِ به‌روزرسانی مجاز نیست.';
  }
  return msg;
}


export function useAppUpdater() {
  const [status, setStatus] = useState<UpdaterStatus>('idle');
  const [currentVersion, setCurrentVersion] = useState<string>(APP_VERSION);
  const [newVersion, setNewVersion] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<string | null>(null);
  const [releaseDate, setReleaseDate] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<number>(0);
  const [downloadedBytes, setDownloadedBytes] = useState<number>(0);
  const [totalBytes, setTotalBytes] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualFile, setManualFile] = useState<File | null>(null);
  // v1.0.10: این به‌روزرسانی پچِ دلتاست (فقط تغییرات) یا نصبِ کامل؟
  const [isDelta, setIsDelta] = useState<boolean>(false);
  const [packageSize, setPackageSize] = useState<number>(0);

  // مانیفستِ دریافت‌شده از /api/update/check (url + signature) برای مرحلهٔ download
  const pendingUpdateRef = useRef<PendingUpdate | null>(null);
  // جلوگیری از نشتِ حلقهٔ نظرسنجیِ progress بعد از unmount
  const pollingRef = useRef<AbortController | null>(null);

  // تشخیص نسخه جاری در شروع
  useEffect(() => {
    let alive = true;
    const settle = (v: string) => { if (alive) setCurrentVersion(v); };
    // نسخهٔ واقعیِ هستهٔ پایتون (bors_config.APP_VERSION) — منبعِ واحد حقیقت
    http<VersionResponse>('/api/update/version', { retries: 1 })
      .then((v) => settle(v.version || APP_VERSION))
      .catch(() => settle(APP_VERSION));
    return () => { alive = false; };
  }, []);

  // توقفِ نظرسنجیِ پس‌زمینه هنگام unmount
  useEffect(() => () => pollingRef.current?.abort(), []);

  /**
   * بررسی وجود نسخه جدید
   */
  const checkForUpdates = useCallback(async (silent = false) => {
    if (!silent) {
      setStatus('checking');
      setErrorMessage(null);
    }

    // مانیفست + مقایسهٔ semver سمتِ سرور (api/update.py)
    try {
      const data = await http<CheckResponse>('/api/update/check');
      if (data.status === 'error') {
        throw new HttpError(0, '/api/update/check', data.message || 'خطا در دریافت مانیفست به‌روزرسانی.');
      }
      setCurrentVersion(data.current_version || currentVersion);

      if (data.available && data.url && data.signature) {
        pendingUpdateRef.current = {
          url: data.url,
          signature: data.signature,
          version: data.latest_version || '',
        };
        setNewVersion(data.latest_version || null);
        setReleaseNotes(data.notes || 'نسخهٔ جدید شامل بهبودهای امنیتی و عملکردی است.');
        setReleaseDate(data.date || new Date().toISOString());
        setIsDelta(Boolean(data.delta));
        setPackageSize(Number(data.size || 0));
        setStatus('available');
        return true;
      }

      pendingUpdateRef.current = null;
      setStatus('up-to-date');
      return false;
    } catch (err) {
      if (!silent) {
        console.error('[updater] check failed:', err);
        setErrorMessage(
          friendlyErrorMessage(err instanceof Error ? err.message : 'امکان استعلام نسخه وجود ندارد.'),
        );
        setStatus('error');
      }
      return false;
    }
  }, [currentVersion]);

  /**
   * دانلود و آماده‌سازی پکیج آپدیت
   */
  const startDownloadAndInstall = useCallback(async () => {
    if (status === 'downloading') return;

    setStatus('downloading');
    setDownloadProgress(0);
    setDownloadedBytes(0);
    setTotalBytes(0);
    setErrorMessage(null);

    // download واقعی → نظرسنجیِ progress → install سایلنت (api/update.py)
    const pending = pendingUpdateRef.current;
    if (!pending) {
      setErrorMessage('ابتدا بررسی به‌روزرسانی را انجام دهید (check).');
      setStatus('error');
      return;
    }

    try {
      // ۱) شروعِ دانلود در پس‌زمینهٔ سرور
      await http<{ status: string; path: string }>('/api/update/download', {
        method: 'POST',
        body: pending,
        retries: 1,
      });

      // ۲) نظرسنجیِ پیشرفت تا رسیدن به ready (یا error)
      pollingRef.current?.abort();
      const pollCtl = new AbortController();
      pollingRef.current = pollCtl;
      let final: ProgressResponse | null = null;
      while (!pollCtl.signal.aborted) {
        const p = await http<ProgressResponse>('/api/update/progress', {
          retries: 1,
          signal: pollCtl.signal,
        });
        setDownloadedBytes(p.downloaded || 0);
        setTotalBytes(p.total || 0);
        if (p.total > 0) {
          setDownloadProgress(Math.min(99, Math.round((p.downloaded / p.total) * 100)));
        }
        if (p.status === 'verifying') {
          setDownloadProgress(100);
        }
        if (p.status === 'ready' || p.status === 'error') {
          final = p;
          break;
        }
        await new Promise((r) => setTimeout(r, 400));
        if (pollCtl.signal.aborted) return;
      }
      if (!final) return;

      if (final.status === 'error') {
        console.error('[updater] download/verify failed:', final.message);
        setErrorMessage(friendlyErrorMessage(final.message));
        setStatus('error');
        return;
      }

      // ۳) راستی‌آزماییِ نهایی + اجرای نصبِ سایلنت (پاسخ، رمز را لو نمی‌دهد)
      const install = await http<InstallResponse>('/api/update/install', {
        method: 'POST',
        retries: 0, // سرور کمتر از ۲ ثانیه بعد خارج می‌شود؛ تلاشِ مجدد بی‌معنی است
      });
      if (install.status === 'error') {
        console.error('[updater] install failed:', install.message);
        setErrorMessage(friendlyErrorMessage(install.message));
        setStatus('error');
        return;
      }
      // نصب‌کننده در یک پروسهٔ مستقل اجرا می‌شود و نسخهٔ جدید را دوباره
      // بالا می‌آورد؛ کاربر می‌تواند همین الان صفحه را تازه کند.
      setStatus('ready-to-restart');
    } catch (err) {
      // سرور بعد از شروعِ نصب می‌میرد → قطعِ ارتباط طبیعی است، نصب ادامه دارد.
      const aborted = err instanceof DOMException && err.name === 'AbortError';
      if (aborted) return;
      console.error('[updater] download/install failed:', err);
      setErrorMessage(
        friendlyErrorMessage(err instanceof Error ? err.message : 'خطا در دانلود یا نصب بسته.'),
      );
      setStatus('error');
    }
  }, [status]);

  /**
   * راه‌اندازی مجددِ صفحه — نصبِ واقعی در پروسهٔ مستقلِ نصب‌کننده انجام می‌شود
   * و همان پروسه نسخهٔ تازه را دوباره بالا می‌آورد.
   */
  const relaunchApp = useCallback(async () => {
    window.location.reload();
  }, []);

  /**
   * آپدیت دستی آفلاین: کاربر setup.exe و امضای همان‌نام (.sig) را می‌دهد.
   * بدنهٔ خامِ باینری مستقیماً روی /api/update/install-local می‌رود (بدون
   * multipart) و سرور قبل از هر کاری امضای minisign را راستی‌آزمایی می‌کند.
   */
  const handleOfflineZipSelect = useCallback(async (file: File, sigFile?: File) => {
    setManualFile(file);
    setErrorMessage(null);
    setStatus('downloading');
    setDownloadProgress(0);
    setDownloadedBytes(0);
    setTotalBytes(file.size);

    if (!file.name.toLowerCase().endsWith('.exe')) {
      setErrorMessage('فقط نصب‌کنندهٔ .exe برای آپدیتِ آفلاین پذیرفته می‌شود.');
      setStatus('error');
      return;
    }
    if (!sigFile) {
      setErrorMessage('فایل امضا (.sig) را هم کنار نصب‌کننده انتخاب کنید.');
      setStatus('error');
      return;
    }

    try {
      const signature = (await sigFile.text()).trim();
      const res = await http<InstallResponse>(
        '/api/update/install-local?signature=' + encodeURIComponent(signature) +
          '&name=' + encodeURIComponent(file.name),
        {
          method: 'POST',
          rawBody: file,
          headers: { 'Content-Type': 'application/octet-stream' },
          retries: 0,
        },
      );
      if (res.status === 'error') {
        console.error('[updater] offline install failed:', res.message);
        setErrorMessage(friendlyErrorMessage(res.message));
        setStatus('error');
        return;
      }
      const match = file.name.match(/(\d+\.\d+(?:\.\d+)?)/);
      setNewVersion(match ? match[1] : 'دستی');
      setReleaseNotes(`پکیج آفلاین تأیید و در حال نصب است: ${file.name}`);
      setStatus('ready-to-restart');
    } catch (err) {
      const aborted = err instanceof DOMException && err.name === 'AbortError';
      if (aborted) return;
      console.error('[updater] offline upload failed:', err);
      setErrorMessage(
        friendlyErrorMessage(err instanceof Error ? err.message : 'بارگذاری بستهٔ آفلاین ناموفق بود.'),
      );
      setStatus('error');
    }
  }, []);

  const resetState = useCallback(() => {
    setStatus('idle');
    setErrorMessage(null);
    setDownloadProgress(0);
    setManualFile(null);
  }, []);

  return {
    status,
    currentVersion,
    newVersion,
    releaseNotes,
    releaseDate,
    downloadProgress,
    downloadedBytes,
    totalBytes,
    isDelta,
    packageSize,
    errorMessage,
    manualFile,
    checkForUpdates,
    startDownloadAndInstall,
    relaunchApp,
    handleOfflineZipSelect,
    resetState,
  };
}
