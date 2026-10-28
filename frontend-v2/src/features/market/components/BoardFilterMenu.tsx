import { useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { faNum } from '@shared/lib/fa';
import type { BoardFilterValues, DirectionFilter } from '../lib/boardFilters';

const POLL_OPTIONS = [
  { ms: 5_000, label: '۵ ثانیه' },
  { ms: 15_000, label: '۱۵ ثانیه' },
  { ms: 60_000, label: '۱ دقیقه' },
  { ms: 300_000, label: '۵ دقیقه' },
];

const DIRECTIONS: { key: DirectionFilter; label: string }[] = [
  { key: 'all', label: 'همه' },
  { key: 'pos', label: 'مثبت' },
  { key: 'neg', label: 'منفی' },
  { key: 'limitUp', label: 'صف خرید' },
  { key: 'limitDown', label: 'صف فروش' },
];

interface Props {
  filters: BoardFilterValues;
  onChange: (patch: Partial<BoardFilterValues>) => void;
  sectors: readonly string[];
  pollMs: number;
  onPollMs: (ms: number) => void;
}

function FilterToggle({ testid, label, pressed, onClick, title }: {
  testid: string;
  label: string;
  pressed: boolean;
  onClick: () => void;
  title?: string;
}) {
  return (
    <button
      type="button"
      data-testid={testid}
      aria-pressed={pressed}
      title={title}
      onClick={onClick}
      className={clsx(
        'flex h-7 items-center justify-between rounded-[var(--radius-xs)] border px-2 t-10',
        pressed ? 'border-accent/40 bg-accent-soft font-bold text-accent' : 'border-line text-text-3 hover:text-text-2',
      )}
    >
      <span>{label}</span>
      <span className="t-85">{pressed ? 'روشن' : 'خاموش'}</span>
    </button>
  );
}

export function BoardFilterMenu({ filters, onChange, sectors, pollMs, onPollMs }: Props) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const activeCount = Number(Boolean(filters.sector)) + Number(!filters.liveOnly)
    + Number(filters.direction !== 'all') + Number(filters.volRatioOn)
    + Number(filters.exitAccum) + Number(filters.showNumericSuffix);

  useEffect(() => {
    if (!open) return;
    function onDown(event: MouseEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === 'Escape') setOpen(false);
    }
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div className="relative flex-none" ref={rootRef}>
      <button
        type="button"
        data-testid="filters-btn"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className={clsx(
          'h-[24px] rounded-[var(--radius-sm)] border px-2 t-10 font-semibold whitespace-nowrap',
          open || activeCount > 0
            ? 'border-accent/40 bg-accent-soft text-accent'
            : 'border-line text-text-3 hover:border-line-strong hover:text-text-2',
        )}
      >
        فیلترها{activeCount > 0 ? ` · ${faNum(activeCount)}` : ''}
      </button>
      {open && (
        <div className="absolute end-0 top-full z-30 mt-1 grid w-[286px] grid-cols-2 gap-2 rounded-[var(--radius-sm)] border border-line bg-panel-2 p-2.5 shadow-2xl">
          <label className="col-span-2 flex items-center gap-2 t-10 text-text-3">
            <span className="w-[62px] flex-none">صنعت</span>
            <select
              aria-label="فیلتر صنعت"
              value={filters.sector}
              onChange={(event) => onChange({ sector: event.target.value })}
              className="h-7 min-w-0 flex-1 rounded-[var(--radius-xs)] border border-line bg-panel px-1.5 text-text outline-none focus:border-line-strong"
            >
              <option value="">همه صنایع</option>
              {sectors.map((sector) => <option key={sector} value={sector}>{sector}</option>)}
            </select>
          </label>
          <label className="col-span-2 flex items-center gap-2 t-10 text-text-3">
            <span className="w-[62px] flex-none">جهت</span>
            <select
              aria-label="جهت تغییر"
              value={filters.direction}
              onChange={(event) => onChange({ direction: event.target.value as DirectionFilter })}
              className="h-7 min-w-0 flex-1 rounded-[var(--radius-xs)] border border-line bg-panel px-1.5 text-text outline-none focus:border-line-strong"
            >
              {DIRECTIONS.map((direction) => <option key={direction.key} value={direction.key}>{direction.label}</option>)}
            </select>
          </label>
          <FilterToggle
            testid="live-only-toggle"
            label="فقط زنده"
            pressed={filters.liveOnly}
            onClick={() => onChange({ liveOnly: !filters.liveOnly })}
            title="جستجوی صریح، نمادِ خاموش را هم پیدا می‌کند."
          />
          <FilterToggle
            testid="numeric-suffix-toggle"
            label="حذفِ پسوندِ عددی"
            pressed={!filters.showNumericSuffix}
            onClick={() => onChange({ showNumericSuffix: !filters.showNumericSuffix })}
          />
          <FilterToggle
            testid="vol-ratio-toggle"
            label="ضریب حجم"
            pressed={filters.volRatioOn}
            onClick={() => onChange({ volRatioOn: !filters.volRatioOn })}
          />
          <FilterToggle
            testid="exit-accum-toggle"
            label="خروج از انباشت"
            pressed={filters.exitAccum}
            onClick={() => onChange({ exitAccum: !filters.exitAccum })}
            title="الگوی ساعت و حجم مشکوک، هر دو با هم."
          />
          {filters.volRatioOn && (
            <label className="col-span-2 flex items-center gap-2 t-10 text-text-3">
              <span className="w-[62px] flex-none">کمینه</span>
              <input
                aria-label="کمینه ضریب حجم"
                type="range"
                min={1.5}
                max={5}
                step={0.5}
                value={filters.volRatioMin}
                onChange={(event) => onChange({ volRatioMin: Number(event.target.value) })}
                className="min-w-0 flex-1 accent-[var(--accent)]"
              />
              <span className="num w-7 text-end text-text-2">{faNum(filters.volRatioMin, 1)}×</span>
            </label>
          )}
          <label className="col-span-2 flex items-center gap-2 border-t border-line pt-2 t-10 text-text-3">
            <span className="w-[62px] flex-none">بازه</span>
            <select
              aria-label="بازه به‌روزرسانی"
              value={pollMs}
              onChange={(event) => onPollMs(Number(event.target.value))}
              className="h-7 min-w-0 flex-1 rounded-[var(--radius-xs)] border border-line bg-panel px-1.5 text-text outline-none focus:border-line-strong"
            >
              {POLL_OPTIONS.map((option) => <option key={option.ms} value={option.ms}>{option.label}</option>)}
            </select>
          </label>
        </div>
      )}
    </div>
  );
}
