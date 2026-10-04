import { useLocation } from 'react-router';
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { PALETTE_OPEN_EVENT } from './CommandPalette';
import { SearchIcon } from '@shared/components/Icons';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';

const TITLES: Record<string, string> = {
  '/market': 'تابلوخوانی / بازار',
  '/technical': 'تحلیل تکنیکال',
  '/fundamental': 'تحلیل بنیادی',
  '/portfolio': 'مدیریت پرتفوی',
  '/master': 'استراتژی FTS',
  '/strategy-tree': 'درخت استراتژی FTS',
};

/** وضعیت اتصال از کشِ کوئریِ تابلو خوانده می‌شود؛ ادعای «آنلاین» بی‌سیگنال ممنوع.
    فقط status/dataUpdatedAtِ کوئری خوانده می‌شود — رندرِ دادهٔ تابلو اینجا لازم نیست. */
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
      const next = readFeedSnap(qc);
      setSnap((prev) => (prev.status === next.status && prev.dataUpdatedAt === next.dataUpdatedAt ? prev : next));
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
  const base = '/' + (pathname.split('/')[1] ?? '');
  const title = TITLES[base] ?? 'ترمینال بورس';
  // در تب تکنیکال خودِ نوارِ چارت بجِ نماد و جستجو را دارد؛ دکمهٔ تکراری حذف است
  const showSearch = base !== '/technical';
  const feedState = useFeedSnapshot();
  const feed = feedStatus(feedState);

  return (
    <header className="glass-strip sticky top-0 z-40 mb-1 flex h-9 items-center justify-between px-3 sm:px-4">
      <div className="flex items-center gap-2">
        <h1 className="text-xs font-black text-text-primary sm:text-sm">
          {title}
        </h1>
        <span
          role="status"
          aria-label={feed.label}
          className={`inline-block h-1.5 w-1.5 rounded-full ${feed.tone}`}
          title={feed.label}
        />
      </div>

      <div className="flex items-center gap-2">
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
