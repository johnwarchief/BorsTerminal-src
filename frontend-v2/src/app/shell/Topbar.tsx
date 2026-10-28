import clsx from 'clsx';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useBoard } from '@features/market/api/useBoard';
import { useMarketPrefs } from '@features/market/stores/prefs';

function SearchIcon() {
  return (
    <svg viewBox="0 0 24 24" width={13} height={13} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <circle cx="11" cy="11" r="7" />
      <path d="M20 20l-4-4" />
    </svg>
  );
}

/** نوارِ بالا: روزِ تابلو (واقعی)، فرمان، و تبِ بازار */
export function Topbar() {
  const pollMs = useMarketPrefs((state) => state.pollMs);
  const board = useBoard(pollMs);
  const day = jalaliFromYmd(board.data?.meta?.d_even);

  return (
    <header className="flex h-11 shrink-0 items-center gap-3 border-b border-line bg-panel px-3">
      <div className="flex items-center gap-1.5 t-10 whitespace-nowrap">
        <span
          className={clsx('h-1.5 w-1.5 rounded-full', board.isFetching ? 'animate-pulse bg-warn' : 'bg-accent')}
          aria-hidden
        />
        <span className="text-text-2">روزِ تابلو</span>
        <span className="num font-semibold">{day}</span>
      </div>

      <button
        type="button"
        onClick={() => window.dispatchEvent(new Event('bors:focus-search'))}
        title="جستجو یا فرمان — Ctrl K"
        className="flex h-7 w-[184px] items-center gap-2 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 t-10 text-text-3 hover:border-line-strong hover:text-text"
      >
        <SearchIcon />
        <span>جستجو یا فرمان</span>
        <kbd className="t-9 ms-auto rounded-[var(--radius-xs)] border border-line px-1" dir="ltr">
          Ctrl K
        </kbd>
      </button>

      <div className="ms-auto flex items-center gap-1" role="tablist" aria-label="تب‌ها">
        <span
          role="tab"
          aria-selected="true"
          className="flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] bg-panel-3 px-2 t-10 text-text"
        >
          بازار
        </span>
        <span
          className="grid h-7 w-7 cursor-not-allowed place-items-center rounded-[var(--radius-sm)] t-115 text-text-3/70"
          title="تبِ تازه — در مرحلهٔ بعد"
        >
          +
        </span>
      </div>
    </header>
  );
}
