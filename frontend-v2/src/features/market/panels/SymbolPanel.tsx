import { useState } from 'react';
import clsx from 'clsx';
import { faNum, fmtInt, fmtMcap, fmtVolume, toFaDigits } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { OrderBookFive } from '../components/OrderBookFive';
import { TapeHistoryPanel } from '../components/TapeHistoryPanel';
import { WatchlistButton } from '../components/WatchlistButton';

type LowerTab = 'book' | 'history' | 'fundamental';

function number(value: number | null | undefined, format: (n: number) => string): string {
  return value == null || !Number.isFinite(value) ? '—' : format(value);
}

export function SymbolPanel({ row, boardDay, chartOpen, onToggleChart }: {
  row: MarketRow | null;
  boardDay: number | null;
  chartOpen: boolean;
  onToggleChart: () => void;
}) {
  const [tab, setTab] = useState<LowerTab>('book');

  if (!row) {
    return (
      <div data-testid="symbol-empty" className="flex h-full flex-col items-center justify-center gap-1 text-text-3">
        <b className="t-115 text-text-2">نمادی انتخاب نشده</b>
        <span className="t-10">روی ردیفِ تابلو کلیک کن.</span>
      </div>
    );
  }

  const pct = row.percent_change;

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-baseline gap-2 border-b border-line px-2 py-1">
        <b data-testid="symbol-title" className="t-115 font-extrabold">{row.symbol}</b>
        <span className="min-w-0 truncate t-9 text-text-3">{row.name ?? ''}</span>
        <span className="num ms-auto t-11 font-bold">{number(row.p_last ?? row.p_closing, fmtInt)}</span>
        <span className={clsx('num t-10', pct == null ? 'text-text-3' : pct > 0 ? 'text-up' : pct < 0 ? 'text-down' : 'text-flat')}>
          {pct == null ? '—' : `${pct > 0 ? '▲' : pct < 0 ? '▼' : '•'} ${faNum(Math.abs(pct))}٪`}
        </span>
        <WatchlistButton symbol={row.symbol} name={row.name ?? undefined} />
      </div>

      <div className="flex flex-none items-center justify-between border-b border-line px-2 py-0.5 t-9 text-text-3">
        <span>چارت</span>
        <button type="button" data-testid="symbol-chart-toggle" onClick={onToggleChart}
          className="rounded-[var(--radius-xs)] px-1 hover:bg-panel-2">
          {chartOpen ? 'بستن' : 'باز کردن'}
        </button>
      </div>
      {chartOpen ? (
        <div className="h-[180px] flex-none border-b border-line">
          <ChartPanel symbol={row.symbol} />
        </div>
      ) : null}

      <div className="grid flex-none grid-cols-2 gap-x-3 gap-y-[2px] border-b border-line px-2 py-1 t-95">
        <span className="flex justify-between"><span className="text-text-3">پایانی</span><b className="num">{number(row.p_closing, fmtInt)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">حجم</span><b className="num">{number(row.q_tot_tran, fmtVolume)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">ارزش</span><b className="num">{number(row.q_tot_cap, (n) => `${fmtMcap(n)} همت`)}</b></span>
        <span className="flex justify-between"><span className="text-text-3">P/E</span><b data-testid="symbol-pe" className="num">{number(row.pe, (n) => toFaDigits(n.toFixed(1)))}</b></span>
        <span className="flex justify-between"><span className="text-text-3">مارکت‌کپ</span><b className="num">{number(row.mcap, (n) => fmtMcap(n))}</b></span>
        <span className="flex justify-between"><span className="text-text-3">کم/بیشترین</span><b className="num">{number(row.p_min, fmtInt)} / {number(row.p_max, fmtInt)}</b></span>
      </div>

      <div className="flex flex-none items-center gap-1 border-b border-line px-2 py-0.5" role="tablist">
        {([['book', 'عمق'], ['history', 'تاریخچه تابلو'], ['fundamental', 'بنیادی']] as const).map(([id, label]) => (
          <button key={id} type="button" role="tab" aria-selected={tab === id}
            data-testid={`symbol-tab-${id}`}
            onClick={() => setTab(id)}
            className={clsx('tape-btn', tab === id && 'is-on')}>
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {tab === 'book' ? <OrderBookFive symbol={row.symbol} insCode={row.ins_code} boardDay={boardDay} /> : null}
        {tab === 'history' ? <TapeHistoryPanel symbol={row.symbol} insCode={row.ins_code} /> : null}
        {tab === 'fundamental' ? (
          <p data-testid="symbol-fundamental-empty" className="p-2 t-95 text-text-3">
            دادهٔ بنیادی هنوز به این نسخه وصل نشده است.
          </p>
        ) : null}
      </div>
    </div>
  );
}
