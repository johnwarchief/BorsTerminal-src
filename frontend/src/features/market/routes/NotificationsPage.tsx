// features/market/routes/NotificationsPage.tsx -- مرکزِ اعلانِ درون‌برنامه
//
// بند ۶ مأموریت (رأیِ مالک 1405-07-20). سه چیز را صریح نگه می‌دارد:
//  • منبع: اطلاعیه‌هایِ کدالِ خودِ برنامه (`codal_notices`)، با لینکِ اصلی،
//    زمانِ انتشارِ کدال و زمانِ دریافتِ خودِ برنامه — دو زمانِ جدا.
//  • اهمیت: از `notifications.py` می‌آید و دلیلِ هر سطح درِ tooltip نوشته
//    شده است؛ رابط هیچ امتیازِ دومی نمی‌سازد.
//  • بی‌منبع: «نرسیده» با «چیزی نیست» یکی نمی‌شود؛ نوارِ سلامتِ منبع همین
//    را جدا می‌گوید و خطایِ شبکه صفحه را نمی‌خواباند.
//
// اعلانِ بومیِ ویندوز: کلیدش همین‌جاست و پیش‌فرض خاموش. مسیرِ ارسال درِ این
// دور ساخته نشده (بندِ «چه نشد»ِ گزارش) — پس برچسبِ کلید صادقانه است و
// هیچ پیامِ سیستمی‌ای پشتِ آن نمی‌رود.
import { useMemo } from 'react';
import { Badge } from '@shared/components/Badge';
import { RetryAction } from '@shared/components/RetryAction';
import { EmptyState } from '@shared/components/EmptyState';
import { toFaDigits } from '@shared/lib/fmt';
import { useNoticeFeed, useNoticeSources, type NoticeItem } from '../api/useNotifications';
import { useNoticePrefsStore } from '../stores/noticePrefsStore';

const LEVEL_FA: Record<string, string> = {
  high: 'بالا', medium: 'متوسط', low: 'پایین', unclassified: 'بی‌طبقه',
};
const LEVEL_TONE: Record<string, string> = {
  high: 'border-accent-red/50 bg-accent-red/10 text-accent-red',
  medium: 'border-accent-yellow/50 bg-accent-yellow/10 text-accent-yellow',
  low: 'border-border-c bg-bg-card text-text-secondary',
  unclassified: 'border-dashed border-border-c bg-bg-primary text-text-muted',
};
const KIND_FA: Record<string, string> = {
  statements: 'صورتهایِ مالی', assembly: 'مجمع', capital: 'افزایش سرمایه',
  dividend: 'تقسیم سود', ipo: 'عرضه اولیه', maturity: 'سررسید اوراق',
  monthly: 'فعالیت ماهانه', production: 'گزارش تولید', governance: 'مدیریت/افشا',
  other: 'بی‌طبقه',
};

/** «۱۴۰۵/۰۷/۰۹ ۱۵:۳۸» — رابط رقمِ فارسی می‌دهد، حتی وقتی پاسخ canonicalِ لاتین است */
function stamp(iso: string | null | undefined): string {
  const s = String(iso || '').trim();
  if (!s) return '—';
  // `sources()` از دور ۳ نمایشِ canonicalِ لاتین برمی‌گرداند (تا رقمِ مخلوط
  // «تازۀترین» را عوض نکند)، پس رابط رقمِ فارسی می‌سازد — تبدیل درِ نمایش است،
  // نه درِ داده.
  return toFaDigits(s.replace('T', ' ').slice(0, 16));
}

/** زمانِ *خودِ برنامه* (میلادی، ASCII) — همان‌طور که درِ بانک نوشته شده می‌ماند؛
 *  قاعدۀ رابط فقط تاریخِ جلالیِ کدال را فارسی رقم می‌کند. */
function stampApp(iso: string | null | undefined): string {
  const s = String(iso || '').trim();
  return s ? s.replace('T', ' ').slice(0, 16) : '—';
}

/** گروه‌بندیِ روزانه. کلید، همانِ تاریخِ جلالیِ خودِ کدال است (نه تبدیلِ ساعتِ
 *  کلاینت): «امروز/دیروز» گفتن بهِ یکِ رشتهٔ بی‌منطقِ منطقه‌زمانی نیاز دارد وِ
 *  آنِ دروغ است. ترتیبِ خودِ فید نگه داشته می‌شود. */
export type NoticeDay = { day: string; items: NoticeItem[]; unread: number };

export function groupByDay(items: NoticeItem[], isRead: (id: string) => boolean): NoticeDay[] {
  const out: NoticeDay[] = [];
  for (const n of items) {
    const day = stamp(n.publish_date).slice(0, 10);
    let g = out.find((x) => x.day === day);
    if (!g) {
      g = { day, items: [], unread: 0 };
      out.push(g);
    }
    g.items.push(n);
    if (!isRead(String(n.id))) g.unread += 1;
  }
  return out;
}

function NoticeRow({ n, read, onOpen }: { n: NoticeItem; read: boolean; onOpen: () => void }) {
  return (
    <li
      data-testid="notice-row"
      data-read={read ? '1' : '0'}
      data-level={n.level}
      className={`flex min-w-0 flex-col gap-1 rounded-xl border px-2.5 py-2 ${
        read ? 'border-border-c/50 bg-bg-primary' : 'border-accent-blue/40 bg-accent-blue/5'
      }`}
    >
      <div className="flex flex-wrap items-center gap-1.5">
        <span className={`shrink-0 rounded-full border px-1.5 py-0.5 text-3xs font-bold ${LEVEL_TONE[n.level] ?? LEVEL_TONE.low}`}
              title={n.reason} data-testid="notice-level">
          {LEVEL_FA[n.level] ?? n.level}
        </span>
        <span className="text-3xs text-text-muted" data-testid="notice-kind">{KIND_FA[n.kind] ?? n.kind}</span>
        {n.symbol ? (
          <span className="num text-2xs font-black text-text-primary" data-testid="notice-symbol">
            {n.symbol}
          </span>
        ) : null}
        {(n.occurrences ?? 1) > 1 ? (
          <span className="text-3xs text-text-muted" title="چند ردیفِ هم‌متن از چند واکشی ادغام شد"
                data-testid="notice-occurrences">
            +{toFaDigits((n.occurrences ?? 1) - 1)} تکراری
          </span>
        ) : null}
        <span className="ms-auto flex items-center gap-1.5">
          <a
            href={n.url ?? '#'}
            target="_blank"
            rel="noreferrer noopener"
            onClick={onOpen}
            data-testid="notice-open"
            className="min-h-[24px] rounded-md border border-border-c px-1.5 py-0.5 text-3xs font-bold text-accent-blue hover:border-accent-blue max-md:inline-flex max-md:min-h-[40px] max-md:min-w-[44px] max-md:items-center max-md:justify-center"
            title="درِ خودِ کدال باز می‌شود (لینکِ اصلیِ اطلاعیه)"
          >
            منبع ↗
          </a>
          {read ? (
            <span className="text-3xs text-text-muted" data-testid="notice-read-mark">خوانده شد</span>
          ) : (
            <button type="button" onClick={onOpen} data-testid="notice-mark"
                    className="min-h-[24px] rounded-md border border-border-c px-1.5 py-0.5 text-3xs text-text-muted hover:text-text-primary max-md:min-h-[40px] max-md:min-w-[44px]">
              خوانده شد
            </button>
          )}
        </span>
      </div>
      <p className="line-clamp-2 text-2xs leading-5 text-text-primary" title={n.title}>{n.title}</p>
      <p className="num-text text-3xs text-text-muted">
        انتشار: {stamp(n.publish_date)} · دریافتِ برنامه: {stampApp(n.received_at)}
        {n.company ? ` · ${n.company}` : ''}
      </p>
    </li>
  );
}

export default function NotificationsPage() {
  const prefs = useNoticePrefsStore();
  const sources = useNoticeSources();
  const feed = useNoticeFeed(prefs.levels);

  const items = feed.data?.items ?? [];
  const visible = useMemo(
    () => (prefs.kinds.length ? items.filter((n) => prefs.kinds.includes(n.kind)) : items),
    [items, prefs.kinds],
  );
  const unread = visible.filter((n) => !prefs.read.includes(String(n.id))).length;
  const days = useMemo(
    () => groupByDay(visible, (id) => prefs.read.includes(id)),
    [visible, prefs.read],
  );

  const src = sources.data?.sources?.[0] ?? null;
  const srcState = src?.state ?? 'unknown';

  return (
    <div className="flex w-full max-w-none flex-col gap-2" data-testid="notifications-page">
      {/* ── سلامتِ منبع: «چیزی نیست» با «نرسیده» یکی نیست ─────────────────── */}
      <section className="glass-panel flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border-c px-2.5 py-2"
               data-testid="notice-sources" data-state={srcState}>
        <span className="text-2xs font-black text-text-primary">اعلان‌ها</span>
        <span className="text-3xs text-text-muted" data-testid="notice-source-name">
          منبع: {src?.label ?? 'کدال (سازمانِ بورس)'}
        </span>
        {srcState === 'ok' ? (
          <span className="num text-3xs text-text-muted" data-testid="notice-source-fresh">
            {toFaDigits(src?.rows ?? 0)} اطلاعیه درِ بانک · تازه‌ترینِ انتشار {stamp(src?.newest_publish)} ·
            آخرینِ واکشی {stampApp(src?.last_fetch)}
          </span>
        ) : srcState === 'empty' ? (
          <span className="text-3xs text-accent-yellow" data-testid="notice-source-empty">
            هیچ اطلاعیه‌ای درِ بانک نیست — این «خبری نیست» نیست، «واکشی نشده» است.
          </span>
        ) : (
          <span className="text-3xs text-accent-red" data-testid="notice-source-bad">
            جدولِ اطلاعیه‌ها نمی‌رسد: {src?.message ?? sources.data?.status ?? '—'}
          </span>
        )}
        <span className="ms-auto flex items-center gap-2">
          <label className="flex items-center gap-1 text-3xs text-text-muted"
                 title="اعلانِ بومیِ ویندوز — پیش‌فرض خاموش و تا روشن نشود هیچ پیامِ سیستمی‌ای فرستاده نمی‌شود">
            <input type="checkbox" data-testid="notice-native" checked={prefs.native}
                   onChange={(e) => prefs.setNative(e.target.checked)} />
            اعلانِ ویندوز
          </label>
          <button type="button" data-testid="notice-mark-all"
                  onClick={() => prefs.markAllRead(visible.map((n) => String(n.id)))}
                  className="min-h-[24px] rounded-md border border-border-c px-1.5 py-0.5 text-3xs font-bold text-text-secondary hover:text-text-primary">
            خوانده‌شدنِ همه
          </button>
        </span>
      </section>

      {/* ── فیلترها: سطحِ اهمیت و نوع، هر دو درِ همین دستگاه می‌مانند ──────── */}
      <div className="flex flex-wrap items-center gap-1.5 text-3xs" data-testid="notice-filters">
        <span className="font-bold text-text-muted">سطحِ اهمیت:</span>
        {Object.entries(LEVEL_FA).map(([k, lbl]) => (
          <button key={k} type="button" data-testid={`notice-level-${k}`} aria-pressed={prefs.levels.includes(k)}
                  onClick={() => prefs.toggleLevel(k)}
                  className={`min-h-[24px] rounded-full border px-2 py-0.5 font-bold transition-colors ${
                    prefs.levels.includes(k) ? LEVEL_TONE[k] : 'border-border-c bg-bg-primary text-text-muted'
                  }`}>
            {lbl}
          </button>
        ))}
        <span className="ms-2 font-bold text-text-muted">نوع:</span>
        {Object.entries(KIND_FA).map(([k, lbl]) => (
          <button key={k} type="button" data-testid={`notice-kind-${k}`} aria-pressed={prefs.kinds.includes(k)}
                  onClick={() => prefs.toggleKind(k)}
                  className={`min-h-[24px] rounded-full border px-2 py-0.5 font-bold transition-colors ${
                    prefs.kinds.includes(k) ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue'
                                            : 'border-border-c bg-bg-primary text-text-muted'
                  }`}>
            {lbl}
          </button>
        ))}
        <Badge tone="gray">
          خوانده‌نشده: <span className="num">{toFaDigits(unread)}</span> از {toFaDigits(visible.length)}
        </Badge>
      </div>

      {/* ── فهرست ───────────────────────────────────────────────────────── */}
      {/* «status: error» با HTTP 4xx یکی نیست: بک‌اند پاسخِ ۲۰۰ با پیامِ خطا
          می‌دهد (جدولِ نبودِ codal_notices درِ بانکِ کهنه). هر دو حالت یکی
          خوانده می‌شوند و هیچ خبری جایگزین ساخته نمی‌شود. */}
      {feed.isError || feed.data?.status === 'error' ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-dashed border-accent-red/50 bg-accent-red/5 px-2.5 py-2 text-2xs text-accent-red"
             data-testid="notice-error">
          <span>
            اطلاعیه‌ها نمی‌رسند{feed.data?.message ? `: ${feed.data.message}` : ''} —
            بقیۀ برنامه کار می‌کند و هیچ خبری جایگزین ساخته نمی‌شود
          </span>
          <RetryAction onRetry={() => void feed.refetch()} testId="notice-retry" />
        </div>
      ) : feed.isLoading && items.length === 0 ? (
        <p className="text-2xs text-text-muted" data-testid="notice-loading">در حالِ خواندنِ اطلاعیه‌ها…</p>
      ) : visible.length === 0 ? (
        <EmptyState title="چیزی درِ این فیلتر نیست"
                    hint="فیلترها را بردارید؛ خالی بودنِ این فهرست به معنای بی‌خبریِ بازار نیست." />
      ) : (
        // بندِ بازطراحی: ۲۷۰ اطلاعیه درِ یکِ <ul> بی‌تیتر، ستونی ۱۰٬۴۴۶pxِ بی‌نقطهٔ
        // اتّصال بود (سنجشِ زنده: heads=0). هرِ روز یکِ <section> باِ <h2> چسبان است،
        // پس «کجایِ تاریخچهم؟» بدونِ اسکرولِ کور خوانده می‌شود.
        <div className="flex min-w-0 flex-col gap-3" data-testid="notice-list">
          {days.map((g) => (
            <section key={g.day} data-testid={`notice-day-${g.day}`} className="flex min-w-0 flex-col gap-1.5">
              <h2
                data-testid={`notice-day-title-${g.day}`}
                className="sticky top-0 z-10 -mx-1 flex flex-wrap items-center gap-x-2 rounded-md bg-bg-primary/95 px-1 py-1 text-2xs font-black text-text-primary backdrop-blur"
              >
                <span className="num">{g.day}</span>
                <span className="num-text text-3xs font-medium text-text-muted">
                  {toFaDigits(g.items.length)} اطلاعیه
                </span>
                {g.unread > 0 ? (
                  <span
                    data-testid={`notice-day-unread-${g.day}`}
                    className="num-text rounded-full bg-accent-blue/15 px-1.5 py-px text-3xs font-bold text-accent-blue"
                  >
                    {toFaDigits(g.unread)} ناخوانده
                  </span>
                ) : null}
              </h2>
              <ul className="flex min-w-0 flex-col gap-1.5">
                {g.items.map((n) => (
                  <NoticeRow key={String(n.id)} n={n} read={prefs.read.includes(String(n.id))}
                             onOpen={() => prefs.markRead(String(n.id))} />
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      <p className="text-3xs leading-5 text-text-muted" data-testid="notice-note">
        {feed.data?.merged_duplicates
          ? `${toFaDigits(feed.data.merged_duplicates)} ردیفِ هم‌متن از چند واکشی ادغام شد (حذفِ بی‌صدا نیست). `
          : ''}
        {sources.data?.note ?? ''}
        {' '}تاریخچۀِ خوانده‌شده‌ها درِ همین دستگاه می‌ماند.
        <button type="button" data-testid="notice-clear-history"
                onClick={() => prefs.clearHistory()}
                className="ms-1 rounded border border-border-c px-1 py-0.5 text-3xs text-text-muted hover:text-text-primary">
          پاک‌کردنِ تاریخچۀِ خوانده‌شده‌ها
        </button>
      </p>
    </div>
  );
}
