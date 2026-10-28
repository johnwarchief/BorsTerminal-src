import { useState } from 'react';
import clsx from 'clsx';
import { faNum, fmtInt, fmtPct } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import type { MarketRow } from '@shared/types/market';
import { ChartPanel } from '@features/chart/ui/ChartPanel';
import { FundamentalSummary } from '@features/fundamental/ui/FundamentalSummary';
import { useMa, technicalSummary, TREND_LABEL } from '@features/market/api/useMa';
import { OrderBookFive } from '@features/market/components/OrderBookFive';
import { TapeFilterChips } from '@features/market/components/TapeFilterChips';
import { TapeHistoryPanel } from '@features/market/components/TapeHistoryPanel';
import { WatchlistButton } from '@features/market/components/WatchlistButton';
import { SymbolGlance } from './SymbolGlance';

type SideTab = 'book' | 'history';

const TREND_TONE = { up: 'text-up', down: 'text-down', neutral: 'text-flat' } as const;

function faDate(value: string): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
  if (!match) return value;
  return jalaliFromYmd(Number(match[1]) * 10000 + Number(match[2]) * 100 + Number(match[3]));
}

function positionText(distancePct: number | null): string {
  if (distancePct == null) return '';
  if (distancePct > 0) return `بالای آن ${faNum(Math.abs(distancePct), 1)}٪`;
  if (distancePct < 0) return `زیرِ آن ${faNum(Math.abs(distancePct), 1)}٪`;
  return 'روی آن';
}

function levelTone(distancePct: number | null): string {
  if (distancePct == null || distancePct === 0) return 'text-text-3';
  return distancePct > 0 ? 'text-up' : 'text-down';
}

function TechnicalBlock({ row }: { row: MarketRow }) {
  const query = useMa(row.symbol);
  const price = row.p_last ?? row.p_closing ?? null;
  const ma = query.data?.status === 'ok' ? query.data.ma : null;
  const summary = ma ? technicalSummary(ma, price) : null;

  if (query.isLoading) {
    return <p data-testid="tech-loading" className="border-t border-line px-2 py-1 t-9 text-text-3">تکنیکال در حالِ خواندن…</p>;
  }
  if (!summary || (!summary.ma20 && !summary.ma50)) {
    return <p data-testid="tech-unavailable" className="border-t border-line px-2 py-1 t-9 text-text-3">تکنیکال در دسترس نیست.</p>;
  }

  return (
    <div data-testid="symbol-tech" className="flex flex-col gap-0.5 border-t border-line px-2 py-1 t-9">
      <div className="flex justify-between t-85 text-text-3">
        <span>تحلیل تکنیکال</span>
        <span title="میانگین‌ها از /api/ma؛ فاصله با آخرین قیمتِ ردیفِ تابلو">MA · یک نگاه</span>
      </div>
      {summary.ma20 ? (
        <span data-testid="tech-ma20" className="flex justify-between gap-1"
          title={`میانگینِ متحرکِ ۲۰روزه تا ${faDate(summary.ma20.date)}`}>
          <span className="text-text-3">MA20</span>
          <b className="num">{fmtInt(summary.ma20.value)}{' '}
            <span className={levelTone(summary.ma20.distancePct)}>{positionText(summary.ma20.distancePct)}</span>
          </b>
        </span>
      ) : null}
      {summary.ma50 ? (
        <span data-testid="tech-ma50" className="flex justify-between gap-1"
          title={`میانگینِ متحرکِ ۵۰روزه تا ${faDate(summary.ma50.date)}`}>
          <span className="text-text-3">MA50</span>
          <b className="num">{fmtInt(summary.ma50.value)}{' '}
            <span className={levelTone(summary.ma50.distancePct)}>{positionText(summary.ma50.distancePct)}</span>
          </b>
        </span>
      ) : null}
      {summary.slope5Pct != null ? (
        <span data-testid="tech-slope" className="flex justify-between gap-1"
          title="درصدِ تغییرِ MA20 در پنج نشستِ آخر">
          <span className="text-text-3">شیبِ MA20 (۵ روز)</span>
          <b className={clsx('num', TREND_TONE[
            summary.slope5Pct > 0 ? 'up' : summary.slope5Pct < 0 ? 'down' : 'neutral'
          ])}>{fmtPct(summary.slope5Pct, 1)}</b>
        </span>
      ) : null}
      <span data-testid="tech-range" className="flex justify-between gap-1"
        title="کمترین و بیشترین قیمتِ امروز (p_min / p_max)">
        <span className="text-text-3">کف/سقف امروز</span>
        <b className="num">
          {row.p_min == null ? '—' : fmtInt(row.p_min)} / {row.p_max == null ? '—' : fmtInt(row.p_max)}
        </b>
      </span>
      {summary.trend ? (
        <span data-testid="tech-trend" data-trend={summary.trend} className="flex justify-between gap-1">
          <span className="text-text-3">روندِ کوتاه</span>
          <b className={TREND_TONE[summary.trend]}>{TREND_LABEL[summary.trend]}</b>
        </span>
      ) : (
        <span data-testid="tech-trend-unknown" className="t-85 text-text-3">
          روندِ کوتاه سنجیده نشد: شیبِ پنج‌روزه یا قیمت در دسترس نیست.
        </span>
      )}
    </div>
  );
}

export interface SymbolSidebarProps {
  row: MarketRow | null;
  symbolKey: string | null;
  boardDay: number | null;
  variant?: 'wide' | 'narrow';
  chartOpen: boolean;
  fundamentalsOpen: boolean;
  collapsed?: boolean;
  onToggleChart: () => void;
  onToggleFundamentals: () => void;
  onToggleCollapsed?: () => void;
}

export function SymbolSidebar(props: SymbolSidebarProps) {
  const {
    row, symbolKey, boardDay, variant = 'wide', chartOpen, fundamentalsOpen,
    collapsed = false, onToggleChart, onToggleFundamentals, onToggleCollapsed,
  } = props;
  const [tab, setTab] = useState<SideTab>('book');

  if (collapsed) {
    return (
      <div data-testid="symbol-rail"
        className="flex h-full w-12 flex-none flex-col items-center gap-2 border-s border-line bg-panel py-2">
        <button type="button" data-testid="symbol-rail-open" aria-label="باز کردنِ سایدبارِ نماد"
          onClick={onToggleCollapsed}
          className="grid h-6 w-6 place-items-center rounded-[var(--radius-xs)] border border-line text-text-2 hover:border-accent hover:text-accent">
          ›
        </button>
        <span className="max-h-[60%] overflow-hidden text-ellipsis whitespace-nowrap t-95 font-bold text-text-2"
          style={{ writingMode: 'vertical-rl' }}>
          {row?.symbol ?? 'نماد'}
        </span>
      </div>
    );
  }

  if (!symbolKey) {
    return (
      <div data-testid="symbol-sidebar" data-variant={variant}
        className="flex h-full min-h-0 flex-col items-center justify-center gap-1 px-2 text-text-3">
        <b className="t-105 text-text-2">نمادی انتخاب نشده</b>
        <span className="t-9">روی ردیفِ تابلو کلیک کن.</span>
      </div>
    );
  }

  if (!row) {
    return (
      <div data-testid="symbol-sidebar" data-variant={variant} className="flex h-full min-h-0 flex-col">
        <div data-testid="symbol-not-in-board" className="grid flex-1 place-items-center px-2 text-center t-95 text-text-3">
          این نماد در تابلو نیست.
        </div>
      </div>
    );
  }

  return (
    <div data-testid="symbol-sidebar" data-variant={variant} className="flex h-full min-h-0 flex-col">
      <div className="flex flex-none items-center gap-1.5 border-b border-line px-2 py-1">
        <b data-testid="symbol-title" className="t-115 font-extrabold text-text">{row.symbol}</b>
        <span className="min-w-0 truncate t-9 text-text-3">{row.name ?? ''}</span>
        {variant === 'wide' && onToggleCollapsed ? (
          <button type="button" data-testid="symbol-collapse" aria-label="جمع کردنِ سایدبارِ نماد"
            onClick={onToggleCollapsed}
            className="ms-auto grid h-5 w-5 flex-none place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-3 hover:text-text">
            ‹
          </button>
        ) : null}
      </div>

      <div className="flex-none px-2 py-1">
        <WatchlistButton symbol={row.symbol} name={row.name ?? undefined} />
      </div>

      {variant === 'wide' ? (
        <div className="grid flex-none grid-cols-2 gap-1 border-y border-line px-2 py-1">
          <button type="button" data-testid="dock-toggle-chart" aria-expanded={chartOpen} onClick={onToggleChart}
            className={clsx('rounded-[var(--radius-sm)] border px-1.5 py-0.5 t-95',
              chartOpen ? 'border-accent/60 bg-accent/10 font-bold text-accent' : 'border-line text-text-3 hover:text-text-2')}>
            {chartOpen ? 'چارت روشن' : 'چارت خاموش'}
          </button>
          <button type="button" data-testid="dock-toggle-fundamental" aria-expanded={fundamentalsOpen} onClick={onToggleFundamentals}
            className={clsx('rounded-[var(--radius-sm)] border px-1.5 py-0.5 t-95',
              fundamentalsOpen ? 'border-accent/60 bg-accent/10 font-bold text-accent' : 'border-line text-text-3 hover:text-text-2')}>
            {fundamentalsOpen ? 'بنیادی روشن' : 'بنیادی خاموش'}
          </button>
        </div>
      ) : null}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <SymbolGlance row={row} />
        <TapeFilterChips row={row} />
        <TechnicalBlock row={row} />
        <FundamentalSummary
          symbol={row.symbol}
          expanded={fundamentalsOpen}
          onToggle={variant === 'wide' ? onToggleFundamentals : undefined}
        />

        {variant === 'narrow' ? (
          <div className="flex-none border-y border-line">
            <button type="button" data-testid="symbol-chart-toggle" aria-expanded={chartOpen} onClick={onToggleChart}
              className="flex w-full items-center justify-between px-2 py-0.5 t-9 text-text-2 hover:bg-panel-2">
              <span>چارت</span>
              <span className="text-text-3">{chartOpen ? 'بستن' : 'باز کردن'}</span>
            </button>
            {chartOpen ? <div className="h-[150px] border-t border-line"><ChartPanel symbol={row.symbol} /></div> : null}
          </div>
        ) : null}

        <div className="flex flex-none items-center gap-1 border-b border-line px-2 py-0.5" role="tablist">
          {(['book', 'history'] as const).map((id) => (
            <button key={id} type="button" role="tab" aria-selected={tab === id}
              data-testid={`symbol-tab-${id}`} onClick={() => setTab(id)}
              className={clsx('tape-btn', tab === id && 'is-on')}>
              {id === 'book' ? 'عمق' : 'تاریخچه تابلو'}
            </button>
          ))}
        </div>
        <div className="min-h-[160px] flex-none">
          {tab === 'book'
            ? <OrderBookFive symbol={row.symbol} insCode={row.ins_code} boardDay={boardDay} />
            : <TapeHistoryPanel symbol={row.symbol} insCode={row.ins_code} />}
        </div>
      </div>
    </div>
  );
}
