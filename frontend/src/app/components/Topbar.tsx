import { useLocation, useNavigate, Link } from 'react-router';
import { PALETTE_OPEN_EVENT } from './CommandPalette';
import { NavHistoryControls } from './NavHistoryControls';
import { SearchIcon, BellIcon } from '@shared/components/Icons';
import { toFaDigits } from '@shared/lib/fmt';
import { useNoticeFeed } from '@features/market/api/useNotifications';
import { useNoticePrefsStore } from '@features/market/stores/noticePrefsStore';
import { FreshnessBadge } from '@shared/components/FreshnessBadge';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { resolveSymbolParam } from '@shared/lib/symbolParam';

// صادر شد تاِ نگهبانِ «هرِ route عنوانِ معنادار دارد» (route-title-guard) همانِ
// یکِ جدول را بخواند، نه نسخۀِ دومِ آن را درِ متنِ آزمون.
export const TITLES: Record<string, string> = {
  '/market': 'تابلوخوانی',
  '/market-status': 'وضعیت بازار',
  '/watch': 'دیده‌بان بازار',
  '/technical': 'تحلیل تکنیکال',
  '/fundamental': 'تحلیل بنیادی',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'غربالگری FTS',
  '/strategy-tree': 'درخت استراتژی FTS',
  // سه مقصد بی‌عنوان بود: نوارِ بالا رویِ «ترمینال بورس» می‌ماند وِ کاربر
  // نمی‌فهمید کدامِ صفحه باز است (سنجشِ عنوانِ هر route درِ فاز ۷.۱).
  '/sarkhati': 'سرخطی',
  '/autoclicker': 'اتوکلیکر',
  '/notifications': 'مرکزِ اعلان',
  '/engine-lab': 'آزمایشگاهِ موتور',
};

export function Topbar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';

  const symbol = useSymbolStore((s) => s.symbol);
  const pinned = useSymbolStore((s) => s.pinned);
  const setSymbol = useSymbolStore((s) => s.setSymbol);

  const showSearch = base !== '/technical';

  // فاز D: نشانیِ خودِ آدرس برنده است — `/technical/فولاد` باید درِ نوارِ بالا هم
  // «فولاد» بگوید، نه نمادی که ازِ نشستِ قبلی درِ استور مانده است.
  const shownSymbol = resolveSymbolParam({ path: pathname.split('/')[2], stored: symbol });

  const handlePinnedClick = (s: string) => {
    setSymbol(s);
    if (base === '/technical' || base === '/fundamental' || base === '/master' || base === '/strategy-tree') {
      navigate(`${base}/${encodeURIComponent(s)}`);
    }
  };

  return (
    <header data-pinned="topbar" className="glass-strip sticky top-0 z-40 flex h-11 items-center justify-between px-3 sm:px-4 md:h-9">
      {/* سمت راست: نشانِ وضعیت (اتصال ≠ تازگی) + Breadcrumb ناوبری */}
      <div className="flex items-center gap-2 overflow-hidden">
        {/* یکِ h1 درِ هرِ صفحه: «کجا هستم» برایِ تکنولوژیِ کمکی هم نوشته می‌شود،
            نه فقطِ دیده می‌شود. */}
        <h1 className="sr-only">{title}</h1>
        <FreshnessBadge />

        {/* بندِ A مأموریتِ UI/UX: دو کنترلِ بازگشت/بعدی درست کنارِ «موقعیت در
            برنامه» می‌نشینند — بیِ ردیفِ تازه وِ بیِ افزایشِ ارتفاعِ `h-11 md:h-9`.
            درِ RTL اینِ گروه سمتِ راستِ عنوانِ مسیر می‌آید («قبلی» راست، «بعدی» چپ). */}
        <NavHistoryControls />

        <nav aria-label="موقعیت در برنامه" className="flex items-center gap-1.5 text-xs">
          <Link
            to={base || '/market'}
            className="font-black text-text-primary hover:text-accent-blue transition-colors truncate"
          >
            {title}
          </Link>
          {shownSymbol ? (
            <>
              <span className="text-text-muted select-none">/</span>
              <span className="font-bold text-accent-blue truncate">{shownSymbol}</span>
            </>
          ) : null}
        </nav>
      </div>

      {/* بخش میانی: نوار نمادهای نشان‌شده (Pinned Symbols Quick Switcher) */}
      {pinned.length > 0 ? (
        <div className="hidden items-center gap-1 overflow-x-auto md:flex max-w-[40%] scrollbar-none px-2">
          <span className="text-3xs text-text-muted select-none">نشان‌شده‌ها:</span>
          {pinned.slice(0, 6).map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => handlePinnedClick(p)}
              className={`rounded-md px-1.5 py-0.5 text-2xs font-bold transition-all ${
                symbol === p
                  ? 'bg-accent-blue/20 text-accent-blue border border-accent-blue/40 shadow-xs'
                  : 'text-text-secondary hover:bg-bg-card hover:text-text-primary border border-transparent'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      ) : null}

      {/* سمت چپ: دکمه جستجو و پالت فرمان */}
      <div className="flex items-center gap-2 shrink-0">
        <NoticeBell />
        {showSearch && (
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
            className="flex items-center gap-2 rounded-lg border border-border-c bg-bg-card/70 px-2.5 py-1 text-2xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue hover:bg-bg-card shadow-2xs max-md:min-h-[40px]"
            aria-label="باز کردن پالت فرمان"
          >
            <SearchIcon size={12} className="text-neon-cyan" />
            <span className="hidden sm:inline">جستجوی سریع نماد...</span>
            <span className="sm:hidden">جستجو</span>
            <kbd className="rounded border border-border-c/80 bg-bg-secondary px-1 py-0.2 text-3xs text-text-muted">
              Ctrl+K
            </kbd>
          </button>
        )}
      </div>
    </header>
  );
}

/** زنگولۀِ مرکزِ اعلان — شمارۀِ خوانده‌نشده از همان فیدِ خودِ صفحه می‌آید؛ خودِ
 *  آیکون هیچ منطقِ خبری‌ای ندارد (رأیِ مالک، بند ۶: «زنگوله بی‌منبع کافی نیست»).
 *  بی‌پاسخ/خطا ⇒ بی‌شماره، نه «صفر خوانده‌نشده» و نه انیمیشنِ هشدار. */
function NoticeBell() {
  const feed = useNoticeFeed([], 60);
  const read = useNoticePrefsStore((st) => st.read);
  const items = feed.data?.items ?? [];
  const unread = items.filter((n) => !read.includes(String(n.id))).length;
  const known = feed.data != null;
  return (
    <Link
      to="/notifications"
      aria-label={known ? `اعلان‌ها — ${unread} خوانده‌نشده` : 'اعلان‌ها'}
      title="اعلان‌ها: اطلاعیه‌های کدال همراه با پیوند اصلی و توضیح اهمیت هر مورد"
      data-testid="topbar-notifications"
      data-state={known ? 'ok' : 'unknown'}
      className="relative flex items-center gap-1 rounded-lg border border-border-c bg-bg-card/70 px-2 py-1 text-2xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue"
    >
      <BellIcon size={13} className="text-accent-yellow" />
      {known && unread > 0 ? (
        <span className="num rounded-full bg-accent-red/20 px-1 text-3xs font-black text-accent-red"
              data-testid="topbar-notifications-count">
          {toFaDigits(unread)}
        </span>
      ) : null}
    </Link>
  );
}
