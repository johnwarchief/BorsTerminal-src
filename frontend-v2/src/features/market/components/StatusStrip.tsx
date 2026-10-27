import { fmtInt, toFaDigits } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import type { MarketFeed } from '@shared/types/market';

export function StatusStrip({ feed, isLoading }: { feed?: MarketFeed; isLoading: boolean }) {
  const meta = feed?.meta;
  return (
    <div data-testid="board-status" className="flex h-9 shrink-0 items-center gap-4 border-b border-line bg-panel px-3 text-[11px] text-text-2">
      <span className="font-semibold text-text">بورس‌ترمینال</span>
      <span className="text-text-3">|</span>
      <span>روزِ تابلو: {jalaliFromYmd(meta?.d_even)}</span>
      <span>آخرین همگام‌سازی: {meta?.last_sync ? toFaDigits(meta.last_sync) : '—'}</span>
      <span className="ms-auto flex items-center gap-3">
        <span>نمادها: {isLoading ? '…' : fmtInt(feed?.count)}</span>
        <span className="text-up">زنده: {isLoading ? '…' : fmtInt(feed?.live_count)}</span>
        <span className="text-text-3">کهنه: {isLoading ? '…' : fmtInt(feed?.fossil_count)}</span>
      </span>
    </div>
  );
}
