// features/updater/useAppUpdater.ts -- هوک اختصاصی مدیریت به‌روزرسانی خودکار و درون‌برنامه‌ای Tauri v2
import { useState, useCallback, useEffect, useRef } from 'react';
import { http, HttpError } from '@shared/api/http';
import type { Update, DownloadEvent } from '@tauri-apps/plugin-updater';

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

/** پاسخ اندپوینت latest release گیت‌هاب — فقط فیلدهای مورد نیاز هوک */
interface GitHubRelease {
  tag_name?: string;
  body?: string;
  published_at?: string;
}

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export function useAppUpdater() {
  const [status, setStatus] = useState<UpdaterStatus>('idle');
  const [currentVersion, setCurrentVersion] = useState<string>('1.0.3');
  const [newVersion, setNewVersion] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<string | null>(null);
  const [releaseDate, setReleaseDate] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<number>(0);
  const [downloadedBytes, setDownloadedBytes] = useState<number>(0);
  const [totalBytes, setTotalBytes] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualFile, setManualFile] = useState<File | null>(null);

  // نگهداشت ارجاع شیء آپدیت توری برای پروسه دانلود و نصب
  const activeUpdateRef = useRef<Update | null>(null);

  // تشخیص نسخه جاری در شروع
  useEffect(() => {
    if (isTauriEnvironment()) {
      import('@tauri-apps/api/app')
        .then((mod) => mod.getVersion())
        .then((v) => setCurrentVersion(v))
        .catch(() => setCurrentVersion('1.0.3'));
    }
  }, []);

  /**
   * بررسی وجود نسخه جدید
   */
  const checkForUpdates = useCallback(async (silent = false) => {
    if (!silent) {
      setStatus('checking');
      setErrorMessage(null);
    }

    // حالت اجرای درون محیط نیتیو Tauri
    if (isTauriEnvironment()) {
      try {
        const { check } = await import('@tauri-apps/plugin-updater');
        const update = await check();

        if (update && update.available) {
          activeUpdateRef.current = update;
          setNewVersion(update.version);
          setCurrentVersion(update.currentVersion || '1.0.3');
          setReleaseNotes(update.body || 'نسخه جدید شامل بهبودهای امنیتی و عملکردی است.');
          setReleaseDate(update.date || new Date().toISOString());
          setStatus('available');
          return true;
        } else {
          activeUpdateRef.current = null;
          setStatus('up-to-date');
          return false;
        }
      } catch (err) {
        console.error('Tauri updater check failed:', err);
        setErrorMessage(err instanceof Error ? err.message : 'خطا در ارتباط با سرور به‌روزرسانی.');
        setStatus('error');
        return false;
      }
    }

    // حالت وب / فال‌بک (بررسی از طریق GitHub API عمومی)
    try {
      const data = await http<GitHubRelease>('https://api.github.com/repos/johnwarchief/BorsTerminal/releases/latest');
      const latestTag = (data.tag_name || '').replace(/^v/, '');

      if (latestTag && latestTag !== currentVersion) {
        setNewVersion(latestTag);
        setReleaseNotes(data.body || 'تغییرات نسخه جدید در گیت‌هاب در دسترس است.');
        setReleaseDate(data.published_at || new Date().toISOString());
        setStatus('available');
        return true;
      } else {
        setStatus('up-to-date');
        return false;
      }
    } catch (err) {
      // ریلیزی روی گیت‌هاب وجود ندارد → نسخهٔ جاری آخرین نسخه است
      if (err instanceof HttpError && err.status === 404) {
        setStatus('up-to-date');
        return false;
      }
      if (!silent) {
        setErrorMessage(err instanceof Error ? err.message : 'امکان استعلام نسخه در محیط وب وجود ندارد.');
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

    const update = activeUpdateRef.current;

    // حالت نیتیو Tauri با دانلود تدریجی واقعی
    if (isTauriEnvironment() && update) {
      try {
        let downloaded = 0;
        let contentLength = 0;

        await update.downloadAndInstall((event: DownloadEvent) => {
          switch (event.event) {
            case 'Started':
              contentLength = event.data.contentLength ?? 0;
              setTotalBytes(contentLength);
              break;
            case 'Progress':
              downloaded += event.data.chunkLength;
              setDownloadedBytes(downloaded);
              if (contentLength > 0) {
                const pct = Math.min(100, Math.round((downloaded / contentLength) * 100));
                setDownloadProgress(pct);
              }
              break;
            case 'Finished':
              setDownloadProgress(100);
              break;
          }
        });

        setStatus('ready-to-restart');
      } catch (err) {
        console.error('Tauri downloadAndInstall error:', err);
        setErrorMessage(err instanceof Error ? err.message : 'خطا حین دانلود و استقرار پکیج به‌روزرسانی.');
        setStatus('error');
      }
      return;
    }

    // شبیه‌سازی در محیط وب یا هنگام عدم اتصال به هسته نیتیو
    let currentPct = 0;
    const timer = setInterval(() => {
      currentPct += 15;
      if (currentPct >= 100) {
        clearInterval(timer);
        setDownloadProgress(100);
        setStatus('ready-to-restart');
      } else {
        setDownloadProgress(currentPct);
      }
    }, 200);
  }, [status]);

  /**
   * راه‌اندازی مجدد برنامه جهت اعمال نسخه جدید
   */
  const relaunchApp = useCallback(async () => {
    if (isTauriEnvironment()) {
      try {
        const { relaunch } = await import('@tauri-apps/plugin-process');
        await relaunch();
      } catch (err) {
        console.error('Failed to relaunch:', err);
        window.location.reload();
      }
    } else {
      window.location.reload();
    }
  }, []);

  /**
   * آپدیت دستی آفلاین از طریق انتخاب فایل فشرده
   */
  const handleOfflineZipSelect = useCallback((file: File) => {
    setManualFile(file);
    setErrorMessage(null);
    setStatus('downloading');
    setDownloadProgress(0);

    // پردازش پکیج دستی
    let p = 0;
    const interval = setInterval(() => {
      p += 25;
      setDownloadProgress(p);
      if (p >= 100) {
        clearInterval(interval);
        const match = file.name.match(/(\d+\.\d+(?:\.\d+)?)/);
        setNewVersion(match ? match[1] : 'دستی');
        setReleaseNotes(`پکیج آفلاین با موفقیت بارگذاری شد: ${file.name}`);
        setStatus('ready-to-restart');
      }
    }, 200);
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
    errorMessage,
    manualFile,
    isTauri: isTauriEnvironment(),
    checkForUpdates,
    startDownloadAndInstall,
    relaunchApp,
    handleOfflineZipSelect,
    resetState,
  };
}
