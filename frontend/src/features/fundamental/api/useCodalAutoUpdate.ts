// features/fundamental/api/useCodalAutoUpdate.ts -- یک هوکِ واحد برای وضعیتِ
// به‌روزرسانیِ دیتابیسِ کدال (GET /api/sync/codal/db-status).
//
// پیش از این صفحه دو افکتِ جدا داشت: یکی برای pollingِ ۲ثانیه‌ای فقط وقتی
// اجرا در جریان بود و یکی برای «کاوشِ یک‌بارهٔ» شروع. نتیجه این بود که پس از
// پایان، صفحه دیگر وضعیت را نمی‌دید و کاربری که وسطِ دانلود وارد می‌شد تا
// تیکِ بعدی از آن بی‌خبر می‌ماند. اینجا یک هوک:
//   • یک کاوشِ فوری در mount (وضعیتِ همین حالا، از جمله meta/freshness)؛
//   • یک تایمر: ۲ ثانیه وقتی running است، ۳۰ ثانیه وقتی بی‌کار است؛
//   • نگهبانِ `alive` (پس از unmount نوشتن در stateِ رهاشده ممنوع) و
//     شمارهٔ ترتیبِ سراسری (پاسخِ درخواستِ کهنه جایِ پاسخِ تازه را نگیرد)؛
//   • گذارِ running→done فقط یک‌بار `onDone` را صدا می‌زند تا صاحبِ صفحه
//     غربالگری را یک‌بار تازه کند؛ ورود به صفحه وقتی کارِ قبلی done است
//     «موفقیتِ تازه» ساخته نمی‌شود.
//   • «اجرا دیده شد» فقط با شاهدِ سرور لچ می‌شود: پولینگی که running:true
//     برمی‌گرداند یا POSTی که status:"success" تأیید می‌کند. کلیکِ دستی به‌تنهایی
//     هیچ موفقیتی نمی‌سازد؛ ردشدنِ سرور (already_running/error) هشدار می‌دهد.
//   • خطایِ ماندگارِ فایلِ وضعیت فقط وقتی «خطایِ همین حالا» خوانده می‌شود که از
//     همین نشست باشد یا `ts`ش تازه باشد؛ خطایِ چندروزه در هر ورود تکرار نمی‌شود.
// هیچ شبکه‌ای در تست لازم نیست: فقط `http` ماک می‌شود.
import { useCallback, useEffect, useRef, useState } from 'react';
import { http } from '@shared/api/http';

/** ریتمِ پولینگ وقتی دانلود/ادغام در جریان است */
export const CODAL_DB_POLL_RUNNING_MS = 2_000;
/** ریتمِ پولینگِ بی‌کار — برایِ دیدنِ شروعِ اجرایِ خودکارِ روزانه */
export const CODAL_DB_POLL_IDLE_MS = 30_000;
/** سنِ مجازِ خطایِ ماندگارِ db-status — قدیمی‌تر از این «همین حالا» خوانده نمی‌شود */
export const CODAL_DB_ERROR_MAX_AGE_MS = 6 * 60 * 60 * 1000;

/** آیا `ts`ِ وضعیت به‌قدرِ کافی تازه است که خطایش خطایِ کنونی خوانده شود؟
 *  `ts` را بک‌اند با `datetime.now().isoformat()` می‌نویسد (بی‌افست، وقتِ محلی)؛
 *  هر ISO دیگری هم با Date.parse خوانده می‌شود. بی‌تاریخ/نامعتبر ⇒ نه. */
export function isRecentDbStatusTs(
  ts: string | null | undefined,
  now: number = Date.now(),
): boolean {
  const raw = String(ts ?? '').trim();
  if (!raw) return false;
  const at = Date.parse(raw);
  if (!Number.isFinite(at)) return false;
  return Math.abs(now - at) <= CODAL_DB_ERROR_MAX_AGE_MS;
}

/** متایِ آخرین snapshotِ منتشرشده (از tag دادهٔ گیت‌هاب) — فقط فیلدهایِ خوانده‌شده */
export type CodalDbMeta = {
  latest_financial_period?: string | null;
  latest_monthly_period?: string | null;
  published_at?: string | null;
  checked_at?: string | null;
  tag?: string | null;
  [key: string]: unknown;
};

/** تازگیِ دادهٔ محلی — دوره‌ها + آخرین اجرایِ موفقِ خودکار (ISO) */
export type CodalFreshness = {
  latest_financial_period?: string | null;
  latest_monthly_period?: string | null;
  source?: string | null;
  last_success?: string | null;
};

/** قراردادِ `db`ِ پاسخِ /api/sync/codal/db-status — meta/freshness اختیاری‌اند */
export type DbStatus = {
  running: boolean;
  stage: string;
  percent?: number;
  detail?: string;
  error?: string;
  ts?: string;
  meta?: CodalDbMeta | null;
  freshness?: CodalFreshness | null;
};

export type CodalAutoUpdateOptions = {
  /** یک‌بار در گذارِ running→done — مثلاً refetchِ غربالگری */
  onDone?: () => void;
};

/** قراردادِ پاسخِ POST /api/sync/codal/db-download — `success` تنها تأییدِ شروع است */
export type CodalDbDownloadResult = {
  status?: string;
  message?: string;
  started?: boolean;
  url?: string;
};

export type CodalAutoUpdateState = {
  status: DbStatus | null;
  running: boolean;
  /** true فقط پس از گذارِ running→done؛ با شروعِ اجرایِ تازه پاک می‌شود */
  completed: boolean;
  /** شروعِ دستی — همان دکمهٔ «دیتابیس کدال» (POST + انتظار برای polling) */
  start: () => Promise<void>;
};

export function useCodalAutoUpdate({ onDone }: CodalAutoUpdateOptions = {}): CodalAutoUpdateState {
  const [status, setStatus] = useState<DbStatus | null>(null);
  const [completed, setCompleted] = useState(false);
  const onDoneRef = useRef(onDone);
  /** آیا از آخرین «پایان»، اجرایی در جریان دیده/شروع کرده؟ */
  const sawRunningRef = useRef(false);
  /** شمارهٔ ترتیبِ سراسریِ درخواست‌ها — پاسخِ قدیمی‌تر هرگز نمی‌نشیند */
  const requestSeqRef = useRef(0);
  /** نسلِ اجرایِ دستی — پاسخِ کاوشِ mount را پس از شروعِ دستی بی‌اعتبار می‌کند */
  const epochRef = useRef(0);

  useEffect(() => {
    onDoneRef.current = onDone;
  }, [onDone]);

  const applyStatus = useCallback((db: DbStatus) => {
    let next = db;
    if (db.running) {
      sawRunningRef.current = true;
      setCompleted(false);
    } else if (db.stage === 'done') {
      // فقط گذارِ running→done؛ doneِ کهنه در mount بنر/refetch نمی‌سازد
      if (sawRunningRef.current) {
        sawRunningRef.current = false;
        setCompleted(true);
        onDoneRef.current?.();
      }
    } else if (db.stage === 'error' && String(db.error ?? '').trim()) {
      // خطایِ نوشته‌شده در فایلِ وضعیت با شروعِ بعدی پاک نمی‌شود؛ اگر از همین
      // نشست نباشد و `ts`ش هم کهنه باشد، اعلانِ «همین حالا» ساخته نمی‌شود.
      const fromSession = sawRunningRef.current;
      sawRunningRef.current = false;
      setCompleted(false);
      if (!fromSession && !isRecentDbStatusTs(db.ts)) {
        next = { ...db, error: '' };
      }
    } else {
      // idle/error — اجرایِ در جریان پایان یافته؛ doneِ بعدی «تازه» نیست
      sawRunningRef.current = false;
    }
    setStatus(next);
  }, []);

  const start = useCallback(async () => {
    // پاسخِ کاوشِ mount یا تیکِ در راه نباید بعد از این کلیک بنشیند
    requestSeqRef.current += 1;
    const epoch = ++epochRef.current;
    // کلیک به‌تنهایی «اجرا دیده شد» نیست: فقط running:trueِ پولینگ یا
    // status:"success"ِ خودِ POST این لچ را می‌بندد.
    sawRunningRef.current = false;
    setCompleted(false);
    setStatus((prev) => ({
      ...(prev ?? {}),
      running: true,
      stage: 'starting',
      percent: 0,
      detail: '',
      error: '',
    }));
    const reject = (message: string) => {
      if (epoch !== epochRef.current) return;   // کلیکِ تازه‌تر حاکم است
      sawRunningRef.current = false;
      setStatus((prev) => ({
        ...(prev ?? {}),
        running: false,
        stage: 'error',
        percent: 0,
        error: message,
        ts: new Date().toISOString(),
      }));
    };
    try {
      const res = await http<CodalDbDownloadResult>('/api/sync/codal/db-download', {
        method: 'POST',
      });
      if (String(res?.status ?? '') === 'success') {
        // تنها تأییدِ سرور اجازهٔ بنرِ پایان می‌دهد (HTTP 200 به‌تنهایی کافی نیست)
        if (epoch === epochRef.current) sawRunningRef.current = true;
        return;
      }
      // already_running یا error: همان پیامِ سرور به‌صورتِ role=alert دیده می‌شود
      reject(
        String(res?.message ?? '').trim()
          || 'شروعِ به‌روزرسانیِ دادهٔ بنیادی ممکن نشد.',
      );
    } catch {
      // POSTِ شکست‌خورده هم موفقیت نیست — بنر/refetchِ ساختگی ممنوع
      reject('شروعِ به‌روزرسانیِ دادهٔ بنیادی ممکن نشد — ارتباط با سرور برقرار نشد.');
    }
  }, []);

  // کاوشِ فوریِ mount: کاربری که وسطِ دانلود صفحه را عوض کرده، وضعیتِ زنده
  // و meta/freshness را از همان ابتدا می‌بیند. پاسخِ کهنه پس از شروعِ دستی
  // (epoch) یا پس از یک درخواستِ تازه‌تر (seq) دور ریخته می‌شود.
  useEffect(() => {
    let alive = true;
    const epoch = epochRef.current;
    const mine = ++requestSeqRef.current;
    http<{ db: DbStatus }>('/api/sync/codal/db-status')
      .then((r) => {
        if (!alive || epoch !== epochRef.current || mine !== requestSeqRef.current) return;
        applyStatus(r.db);
      })
      .catch(() => { /* تیکِ بعدی دوباره تلاش می‌کند */ });
    return () => {
      alive = false;
    };
  }, [applyStatus]);

  // تنها تایمرِ پولینگ. ریتم از خودِ `running` می‌آید، نه از آبجکتِ وضعیت —
  // وگرنه هر پاسخ تایمر را از نو می‌ساخت.
  const running = status?.running === true;
  useEffect(() => {
    let alive = true;
    let issued = 0;
    const tick = () => {
      const mine = ++issued;
      const seq = ++requestSeqRef.current;
      http<{ db: DbStatus }>('/api/sync/codal/db-status')
        .then((r) => {
          if (!alive || mine !== issued || seq !== requestSeqRef.current) return;
          applyStatus(r.db);
        })
        .catch(() => { /* سرور مشغول است — تیکِ بعدی */ });
    };
    const id = setInterval(tick, running ? CODAL_DB_POLL_RUNNING_MS : CODAL_DB_POLL_IDLE_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [running, applyStatus]);

  return { status, running, completed, start };
}
