import { useLocation, useNavigate, Link } from 'react-router';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PALETTE_OPEN_EVENT } from './CommandPalette';
import { SearchIcon } from '@shared/components/Icons';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';
import { useSymbolStore } from '@shared/stores/symbolStore';

const TITLES: Record<string, string> = {
  '/market': 'تابلوخوانی / بازار',
  '/technical': 'تحلیل تکنیکال',
  '/fundamental': 'تحلیل بنیادی',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'استراتژی FTS',
  '/strategy-tree': 'درخت استراتژی FTS',
};

type FeedSnap = { status: string; dataUpdatedAt: number };
const NO_FEED: FeedSnap = { status: 'idle', dataUpdatedAt: 0 };

function readFeedSnap(qc: ReturnType<typeof useQueryClient>): FeedSnap {
  const q = qc.getQueryCache().find({ queryKey: MARKET_FEED_KEY });
  if (!q) return NO_FEED;
  return { status: q.state.status, dataUpdatedAt: q.state.dataUpdatedAt };
}

function useFeedSnapshot(): FeedSnap {
  const qc = useQueryClient();
  const [snap, setSnap] = useState<FeedSnap>(() => readFeedSnap(qc));
  useEffect(() => {
    setSnap(readFeedSnap(qc));
    const unsub = qc.getQueryCache().subscribe(() => {
      // چرا defer: خودِ notify شدنِ cache هم‌زمان درِ render-phaseِ کامپوننتِ
      // دیگری اتفاق می‌افتد (مثلاً وقتی قیف mount می‌شود و observer تازه‌اش را
      // به cache وصل می‌کند). setSnap درِ همان لحظه یعنی «به‌هنگامِ رندرِ
      // کامپوننتِ دیگر state را عوض کردی» — هشدارِ Reactِ همان است. یک
      // microtask بعد، همان عدد خوانده می‌شود و پیام می‌رود.
      queueMicrotask(() => {
        const next = readFeedSnap(qc);
        setSnap((prev) => (prev.status === next.status && prev.dataUpdatedAt === next.dataUpdatedAt ? prev : next));
      });
    });
    return unsub;
  }, [qc]);
  return snap;
}

function feedStatus(state: FeedSnap) {
  if (state.status === 'idle' && !state.dataUpdatedAt) {
    return { tone: 'bg-text-muted', label: 'در انتظارِ رسیدنِ دادهٔ تابلو' };
  }
  if (state.status === 'error') {
    return { tone: 'bg-accent-red', label: 'دادهٔ تابلو نمی‌رسد — اتصال بک‌اند را بررسی کن' };
  }
  if (state.status === 'success') {
    return { tone: 'bg-accent-green animate-pulse', label: 'سیستم آنلاین و متصل' };
  }
  return { tone: 'bg-accent-yellow', label: 'در حالِ دریافتِ داده' };
}

export function Topbar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';

  const symbol = useSymbolStore((s) => s.symbol);
  const pinned = useSymbolStore((s) => s.pinned);
  const setSymbol = useSymbolStore((s) => s.setSymbol);

  const showSearch = base !== '/technical';
  const feedState = useFeedSnapshot();
  const feed = feedStatus(feedState);

  const handlePinnedClick = (s: string) => {
    setSymbol(s);
    if (base === '/technical' || base === '/fundamental' || base === '/master' || base === '/strategy-tree') {
      navigate(`${base}/${encodeURIComponent(s)}`);
    }
  };

  return (
    <header className="glass-strip sticky top-0 z-40 flex h-9 items-center justify-between px-3 sm:px-4">
      {/* سمت راست: نشان وضعیت + Breadcrumb ناوبری */}
      <div className="flex items-center gap-2 overflow-hidden">
        <span
          role="status"
          aria-label={feed.label}
          className={`inline-block h-2 w-2 shrink-0 rounded-full ${feed.tone}`}
          title={feed.label}
        />

        <nav aria-label="موقعیت در برنامه" className="flex items-center gap-1.5 text-xs">
          <Link
            to={base || '/market'}
            className="font-black text-text-primary hover:text-accent-blue transition-colors truncate"
          >
            {title}
          </Link>
          {symbol ? (
            <>
              <span className="text-text-muted select-none">/</span>
              <span className="font-bold text-accent-blue truncate">{symbol}</span>
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
        {showSearch && (
          <button
            type="button"
            onClick={() => window.dispatchEvent(new Event(PALETTE_OPEN_EVENT))}
            className="flex items-center gap-2 rounded-lg border border-border-c bg-bg-card/70 px-2.5 py-1 text-2xs text-text-secondary transition-all hover:border-border-accent hover:text-accent-blue hover:bg-bg-card shadow-2xs"
            aria-label="باز کردن پالت فرمان"
          >
            <SearchIcon size={12} className="text-neon-cyan" />
            <span className="hidden sm:inline">جستجوی سریع نماد...</span>
            <span className="sm:hidden">جستجو</span>
            <kbd className="rounded border border-border-c/80 bg-bg-secondary px-1 py-0.2 text-[10px] text-text-muted">
              Ctrl+K
            </kbd>
          </button>
        )}
      </div>
    </header>
  );
}
