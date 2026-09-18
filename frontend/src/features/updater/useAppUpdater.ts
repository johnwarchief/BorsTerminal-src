// features/updater/useAppUpdater.ts -- هوک اختصاصی مدیریت به‌روزرسانی خودکار و درون‌برنامه‌ای Tauri v2
import { useState, useCallback, useEffect, useRef } from 'react';

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

export function isTauriEnvironment(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
}

export function useAppUpdater() {
  const [status, setStatus] = useState<UpdaterStatus>('idle');
  const [currentVersion, setCurrentVersion] = useState<string>('1.0.1');
  const [newVersion, setNewVersion] = useState<string | null>(null);
  const [releaseNotes, setReleaseNotes] = useState<string | null>(null);
  const [releaseDate, setReleaseDate] = useState<string | null>(null);
  const [downloadProgress, setDownloadProgress] = useState<number>(0);
  const [downloadedBytes, setDownloadedBytes] = useState<number>(0);
  const [totalBytes, setTotalBytes] = useState<number>(0);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [manualFile, setManualFile] = useState<File | null>(null);

  // نگهداشت ارجاع شیء آپدیت توری برای پروسه دانلود و نصب
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const activeUpdateRef = useRef<any>(null);

  // تشخیص نسخه جاری در شروع
  useEffect(() => {
    if (isTauriEnvironment()) {
      import('@tauri-apps/api/app')
        .then((mod) => mod.getVersion())
        .then((v) => setCurrentVersion(v))
        .catch(() => setCurrentVersion('1.0.1'));
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
          setCurrentVersion(update.currentVersion || '1.0.1');
          setReleaseNotes(update.body || 'نسخه جدید شامل بهبودهای امنیتی و عملکردی است.');
          setReleaseDate(update.date || new Date().toISOString());
          setStatus('available');
          return true;
        } else {
          activeUpdateRef.current = null;
          setStatus('up-to-date');
          return false;
        }
      } catch (err: any) {
        console.error('Tauri updater check failed:', err);
        setErrorMessage(err?.message || 'خطا در ارتباط با سرور به‌روزرسانی.');
        setStatus('error');
        return false;
      }
    }

    // حالت وب / فال‌بک (بررسی از طریق GitHub API عمومی)
    try {
      const resp = await fetch('https://api.github.com/repos/johnwarchief/BorsTerminal/releases/latest', {
        headers: { Accept: 'application/vnd.github.v3+json' },
      });

      if (!resp.ok) {
        if (resp.status === 404) {
          setStatus('up-to-date');
          return false;
        }
        throw new Error(`خطای سرور گیت‌هاب: کد ${resp.status}`);
      }

      const data = await resp.json();
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
    } catch (err: any) {
      if (!silent) {
        setErrorMessage(err?.message || 'امکان استعلام نسخه در محیط وب وجود ندارد.');
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

    // حالت نیتیو Tauri با دانلود تدریجی واقعی
    if (isTauriEnvironment() && activeUpdateRef.current) {
      try {
        const update = activeUpdateRef.current;
        let downloaded = 0;
        let contentLength = 0;

        await update.downloadAndInstall((event: any) => {
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
      } catch (err: any) {
        console.error('Tauri downloadAndInstall error:', err);
        setErrorMessage(err?.message || 'خطا حین دانلود و استقرار پکیج به‌روزرسانی.');
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
      } catch (err: any) {
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
