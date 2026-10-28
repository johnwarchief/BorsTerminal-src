import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import clsx from 'clsx';
import { changePct, fmtInt, fmtMcap, fmtPct, fmtPe, fmtPrice, fmtValue, fmtVolume, tone } from '@shared/lib/fa';
import type { MarketRow } from '@shared/types/market';
import { ASSET_LABELS, classifyAssetType } from '../lib/assetType';
import type { TapeFilterConfig } from '../lib/tapeAlgorithms';
import { patternBadges } from '../lib/tapeBadges';
import { WatchlistButton } from './WatchlistButton';

const OrderBookFive = lazy(() => import('./OrderBookFive').then((module) => ({ default: module.OrderBookFive })));
const TapeHistoryPanel = lazy(() => import('./TapeHistoryPanel').then((module) => ({ default: module.TapeHistoryPanel })));

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" width={15} height={15} fill="none" stroke="currentColor" strokeWidth="1.6" aria-hidden>
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

interface Props {
  row: MarketRow;
  filterConfig: TapeFilterConfig;
  boardDay?: number | null;
  onClose: () => void;
}

export function QuickDrawer({ row, filterConfig, boardDay, onClose }: Props) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const pct = changePct(row.percent_change, row.price_change, row.price_yesterday);
  const pctTone = tone(pct);
  const badges = patternBadges(row, filterConfig);
  const type = classifyAssetType(row);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  async function copySymbol() {
    try {
      await navigator.clipboard.writeText(row.symbol);
    } catch {
      const area = document.createElement('textarea');
      area.value = row.symbol;
      area.style.position = 'fixed';
      area.style.opacity = '0';
      document.body.appendChild(area);
      area.select();
      document.execCommand('copy');
      area.remove();
    }
    setCopied(true);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setCopied(false), 1200);
  }

  const stats: [string, string][] = [
    ['آخرین', fmtPrice(row.p_last)],
    ['پایانی', fmtPrice(row.p_closing)],
    ['تغییر', fmtPct(pct)],
    ['دیروز', fmtPrice(row.price_yesterday)],
    ['حجم', fmtVolume(row.q_tot_tran)],
    ['ارزش (میلیارد ریال)', fmtValue(row.q_tot_cap)],
    ['معاملات', fmtInt(row.z_tot_tran)],
    ['P/E', fmtPe(row.pe)],
    ['ارزش بازار (همت)', fmtMcap(row.mcap)],
    ['صنعت', row.sector_name ?? '—'],
  ];

  return (
    <aside
      role="dialog"
      aria-modal="false"
      className="quick-drawer flex h-full w-[356px] min-w-0 flex-col border-s border-line-strong bg-panel"
      aria-label="جزئیات سریع نماد"
    >
      <div className="flex h-[44px] flex-none items-center gap-2 border-b border-line px-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-baseline gap-1.5">
            <b className="t-145 font-extrabold text-text">{row.symbol}</b>
            <span className="t-9 text-text-3">{ASSET_LABELS[type]}</span>
          </div>
          <div className="overflow-hidden text-ellipsis whitespace-nowrap t-95 text-text-3" title={row.name ?? ''}>
            {row.name ?? '—'}
          </div>
        </div>
        <button
          autoFocus
          type="button"
          onClick={onClose}
          aria-label="بستن جزئیات"
          title="بستن (Esc)"
          className="grid h-6 w-6 place-items-center rounded-[var(--radius-sm)] text-text-3 hover:bg-panel-2 hover:text-text"
        >
          <CloseIcon />
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col gap-[13px] overflow-y-auto p-3">
        <div className="flex flex-wrap items-end gap-2">
          <span className="num text-[23.5px] font-black leading-none tracking-tight text-text">{fmtPrice(row.p_last ?? row.p_closing)}</span>
          <span className="t-9 pb-0.5 text-text-3">ریال</span>
          <span
            className={clsx(
              'num pb-0.5 t-115 font-bold',
              pctTone === 'up' ? 'text-up' : pctTone === 'down' ? 'text-down' : 'text-flat',
            )}
          >
            {fmtPct(pct)}
          </span>
        </div>

        <section>
          <div className="flex items-center justify-between border-b border-line pb-1 t-9 font-bold tracking-[0.05em] text-text-3">
            <span>مشخصات بازار</span>
            <span className="font-normal">‎/api/market</span>
          </div>
          <div className="grid grid-cols-2">
            {stats.map(([label, value]) => (
              <div key={label} className="qd-stat">
                <span className="t-95 text-text-3">{label}</span>
                <b className="num max-w-[68%] overflow-hidden text-ellipsis whitespace-nowrap t-10 text-text-2" title={value}>
                  {value}
                </b>
              </div>
            ))}
          </div>
        </section>

        <section>
          <div className="flex items-center justify-between border-b border-line pb-1 t-9 font-bold tracking-[0.05em] text-text-3">
            <span>تابلوخوانی</span>
            <span className="font-normal">نشان‌های همین تابلو</span>
          </div>
          <div className="pt-1">
            {badges.length > 0 ? (
              <div className="flex flex-wrap gap-1">
                {badges.map((badge) => (
                  <span key={badge.key} data-testid={`badge-${badge.key}`} className="sym-badge" title={badge.title}>
                    {badge.label}
                  </span>
                ))}
              </div>
            ) : (
              <div className="qd-row">
                <span>فیلترهای تابلوخوانی</span>
                <b>دیده نشده</b>
              </div>
            )}
            <p className="mt-1.5 t-85 leading-relaxed text-text-3">نبودِ برچسب یعنی دیده‌نشده، نه ردِ فیلتر.</p>
          </div>
        </section>

        <WatchlistButton symbol={row.symbol} name={row.name ?? ''} />

        <section data-testid="drawer-orderbook-section">
          <div className="flex items-center justify-between border-b border-line pb-1 t-9 font-bold tracking-[0.05em] text-text-3">
            <span>عمق بازار</span>
            <span className="font-normal">پنج مظنه</span>
          </div>
          <div className="pt-2">
            <Suspense fallback={<p className="t-95 text-text-3" role="status">دفتر سفارش در حال آماده‌سازی…</p>}>
              <OrderBookFive symbol={row.symbol} insCode={row.ins_code} boardDay={boardDay} />
            </Suspense>
          </div>
        </section>

        <section data-testid="drawer-history-section">
          <div className="flex items-center justify-between border-b border-line pb-1 t-9 font-bold tracking-[0.05em] text-text-3">
            <span>سابقهٔ فیلترها</span>
            <span className="font-normal">روزهای رصدشده</span>
          </div>
          <div className="pt-2">
            <Suspense fallback={<p className="t-95 text-text-3" role="status">سابقه در حال آماده‌سازی…</p>}>
              <TapeHistoryPanel insCode={row.ins_code} symbol={row.symbol} />
            </Suspense>
          </div>
        </section>

        <section aria-label="ادامهٔ بررسی" className="grid grid-cols-2 gap-1.5">
          <button
            type="button"
            data-testid="drawer-technical-link"
            disabled
            title="تحلیل تکنیکال در نسخهٔ تازه هنوز وصل نیست"
            className="h-7 rounded-[var(--radius-sm)] border border-line t-10 text-text-3 disabled:cursor-not-allowed disabled:opacity-50"
          >
            تکنیکال · وصل نیست
          </button>
          <button
            type="button"
            data-testid="drawer-fundamental-link"
            disabled
            title="تحلیل بنیادی در نسخهٔ تازه هنوز وصل نیست"
            className="h-7 rounded-[var(--radius-sm)] border border-line t-10 text-text-3 disabled:cursor-not-allowed disabled:opacity-50"
          >
            بنیادی · وصل نیست
          </button>
        </section>
      </div>

      <div className="flex flex-none gap-1.5 border-t border-line p-2.5">
        <button
          type="button"
          onClick={() => void copySymbol()}
          className="flex h-7 flex-1 items-center justify-center gap-1.5 rounded-[var(--radius-sm)] border border-accent/60 bg-accent t-10 font-bold text-accent-ink hover:brightness-110"
        >
          {copied ? 'کپی شد' : 'کپی نماد'}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="flex h-7 items-center gap-1.5 rounded-[var(--radius-sm)] border border-line px-2.5 t-10 text-text-2 hover:border-line-strong hover:text-text"
        >
          بستن
        </button>
      </div>
    </aside>
  );
}
