// widgets/SymbolInspector.tsx -- داک باریک نماد در لبه چپ (فاز 8)
// دید متمرکز روی تک‌سهم در کنار دید کلان همه تب‌ها.
import { Link } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtPct } from '@shared/lib/fmt';
import { FlashNum } from '@shared/components/FlashNum';
import { Badge } from '@shared/components/Badge';
import { aggregateSignals } from '@features/master/lib/masterMath';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { useInspectorBoard } from './useInspectorBoard';

const ACTION_FA = {
  strong_buy: 'خرید قوی',
  buy: 'خرید',
  hold: 'نگهداری',
  watch: 'زیر نظر',
  reduce: 'کاهش',
  sell: 'فروش',
  strong_sell: 'فروش قوی',
  no_data: 'بدون داده',
} as const;

const ACTION_TONE = {
  strong_buy: 'green',
  buy: 'green',
  hold: 'gray',
  watch: 'blue',
  reduce: 'yellow',
  sell: 'red',
  strong_sell: 'red',
  no_data: 'gray',
} as const;

function MiniGauge({ pct, color }: { pct: number; color: string }) {
  const r = 21;
  const circ = 2 * Math.PI * r;
  return (
    <svg width="48" height="48" viewBox="0 0 48 48" role="img" aria-label="گیج برآیند">
      <circle cx="24" cy="24" r={r} fill="none" stroke="var(--border-color)" strokeWidth="4.5" />
      <circle
        cx="24"
        cy="24"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="4.5"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={circ * (1 - pct / 100)}
        transform="rotate(-90 24 24)"
        style={{ transition: 'stroke-dashoffset 0.5s cubic-bezier(0.22, 1, 0.36, 1)' }}
      />
      <text x="24" y="28" textAnchor="middle" fontSize="12.5" fontWeight="900" fill="var(--text-primary)" className="num">
        {toFaDigits(Math.round(pct))}
      </text>
    </svg>
  );
}

/** یک چراغ وضعیت با مقدار و توضیح */
function StatusLight({
  label,
  value,
  tone,
  hint,
}: {
  label: string;
  value: string;
  tone: 'green' | 'red' | 'yellow' | 'gray' | 'blue' | 'orange';
  hint?: string;
}) {
  const on = tone === 'green' || tone === 'blue';
  const warn = tone === 'yellow' || tone === 'orange';
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-transparent px-2 py-1.5 transition-colors duration-200 hover:border-[var(--hairline)] hover:bg-bg-card/40">
      <span className="flex items-center gap-2 text-[11px] text-text-secondary">
        <span
          aria-hidden
          className={`inline-block h-2 w-2 shrink-0 rounded-full transition-all duration-300 ${
            on
              ? 'bg-accent-green shadow-[0_0_8px_var(--accent-green)]'
              : warn
                ? 'animate-pulse bg-accent-yellow shadow-[0_0_6px_var(--accent-yellow)]'
                : tone === 'red'
                  ? 'bg-accent-red shadow-[0_0_6px_var(--accent-red)]'
                  : 'bg-border-c'
          }`}
        />
        {label}
      </span>
      <span className={`num text-[11px] font-bold ${tone === 'green' || tone === 'blue' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : tone === 'yellow' || tone === 'orange' ? 'text-accent-yellow' : 'text-text-secondary'}`} title={hint}>
        {value}
      </span>
    </div>
  );
}

export function SymbolInspector() {
  const symbol = useSymbolStore((s) => s.symbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const row = useInspectorBoard();

  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const verdict = symbol ? aggregateSignals(symbol, getActiveSignals(symbol)) : null;

  const open = symbol.length > 0;
  const pct = verdict ? (verdict.compositeScore + 100) / 2 : 50;
  const gaugeColor = pct >= 60 ? 'var(--accent-green)' : pct >= 40 ? 'var(--neon-cyan)' : 'var(--neon-red)';

  const fund = entry?.fundamental;
  const tech = entry?.technical;
  const port = entry?.portfolio;

  return (
    <aside
      aria-label={`بازرسی نماد ${symbol}`}
      className={`glass-panel fixed bottom-0 left-0 top-0 z-50 flex w-[264px] shrink-0 flex-col overflow-y-auto rounded-none border-y-0 border-l-0 p-0 transition-transform duration-200 ease-out ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
      style={{ borderRight: '1px solid var(--hairline)' }}
      aria-hidden={!open}
      {...{ inert: !open ? ('' as unknown as boolean) : undefined }}
    >
      {/* هدر: بستن + نماد */}
      <div className="sticky top-0 z-10 flex items-start justify-between gap-2 border-b border-[var(--hairline)] bg-bg-primary/85 px-3 py-2.5 backdrop-blur-md">
        <div className="min-w-0">
          <div className="truncate text-sm font-black text-text-primary">{symbol || '-'}</div>
          <div className="truncate text-[10px] text-text-muted">{row?.name || ''}</div>
          {row?.sector ? <div className="truncate text-[10px] text-text-muted">{row.sector}</div> : null}
        </div>
        <button
          type="button"
          onClick={clearSymbol}
          aria-label="بستن پنل نماد"
          className="shrink-0 rounded-md border border-transparent px-1.5 py-0.5 text-xs text-text-muted transition-colors hover:border-[var(--hairline)] hover:text-accent-red"
        >
          ✕
        </button>
      </div>

      <div className="flex flex-col gap-3 p-3">
        {/* قیمت و درصد با فلاش */}
        <div className="flex items-end justify-between gap-2">
          <div>
            <div className="text-[9px] uppercase tracking-wider text-text-muted">آخرین معامله</div>
            <FlashNum value={row?.pLast} render={(v) => toFaDigits(v == null ? '-' : Number(v.toFixed(2)).toString())} className="text-base font-black text-text-primary" />
          </div>
          <div className="text-left">
            <div className="text-[9px] uppercase tracking-wider text-text-muted">تغییر روز</div>
            <span className={row?.percentChange != null && row.percentChange >= 0 ? 'text-accent-green' : 'text-accent-red'}>
              <FlashNum value={row?.percentChange} render={(v) => (v == null ? '-' : fmtPct(v))} className="text-sm font-bold" />
            </span>
          </div>
        </div>

        {/* مینی کاکپیت مستر */}
        <div className="flex items-center gap-3 rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-2.5">
          <MiniGauge pct={pct} color={gaugeColor} />
          <div className="flex min-w-0 flex-col gap-1">
            {verdict ? (
              <Badge tone={ACTION_TONE[verdict.finalAction]}>{ACTION_FA[verdict.finalAction]}</Badge>
            ) : (
              <Badge tone="gray">بدون داده</Badge>
            )}
            <span className="num text-[10px] text-text-muted">
              {verdict ? `${toFaDigits(verdict.usedSignalIds.length)}/۴ سیگنال` : 'در انتظار سیگنال'}
            </span>
          </div>
        </div>

        {/* چهار چراغ وضعیت */}
        <div className="flex flex-col gap-1">
          <StatusLight
            label="نمره بنیادی"
            value={fund?.score == null ? '-' : toFaDigits(fund.score)}
            tone={fund == null ? 'gray' : fund.direction === 'bullish' ? 'green' : fund.direction === 'bearish' ? 'red' : 'yellow'}
            hint={fund?.rationale}
          />
          <StatusLight
            label="تکنیکال FTS"
            value={tech == null ? '-' : tech.direction === 'bullish' ? 'صعودی' : tech.direction === 'bearish' ? 'نزولی' : 'خنثی'}
            tone={tech == null ? 'gray' : tech.direction === 'bullish' ? 'green' : tech.direction === 'bearish' ? 'red' : 'yellow'}
            hint={tech?.rationale}
          />
          <StatusLight
            label="سرانه خریدار"
            value={row?.buyerPower == null ? '-' : toFaDigits(row.buyerPower.toFixed(1))}
            tone={row?.buyerPower != null && row.buyerPower >= 1.5 ? 'green' : row?.fClock || row?.fSusp ? 'orange' : 'gray'}
            hint={row?.fClock ? 'الگوی ساعت فعال' : row?.fSusp ? 'حجم مشکوک' : undefined}
          />
          <StatusLight
            label="پرتفوی"
            value={
              port == null
                ? 'در سبد نیست'
                : port.payload && (port.payload as { decision?: unknown }).decision === 'accept'
                  ? 'نگهداری'
                  : (port.payload as { decision?: unknown }).decision === 'monitor'
                    ? 'زیر نظر'
                    : (port.payload as { decision?: unknown }).decision === 'reject'
                      ? 'حذف‌شده'
                      : 'بدون تصمیم'
            }
            tone={
              port == null
                ? 'gray'
                : (port.payload as { decision?: unknown }).decision === 'accept'
                  ? 'green'
                  : (port.payload as { decision?: unknown }).decision === 'reject'
                    ? 'red'
                    : 'yellow'
            }
            hint={port?.rationale}
          />
        </div>

        {/* دسترسی مستقیم */}
        <div className="mt-1 flex flex-col gap-2">
          <SymbolBasketAction symbol={symbol} compact />
          <Link
            to={`/technical/${encodeURIComponent(symbol)}`}
            className="rounded-full border border-[var(--hairline)] bg-bg-card/60 px-3 py-1.5 text-center text-[11px] font-bold text-accent-blue transition-all duration-200 hover:border-border-accent hover:text-neon-cyan"
          >
            پرش به چارت تکنیکال ↗
          </Link>
          <Link
            to={`/fundamental/${encodeURIComponent(symbol)}`}
            className="rounded-full border border-[var(--hairline)] bg-bg-card/60 px-3 py-1.5 text-center text-[11px] font-bold text-text-secondary transition-all duration-200 hover:border-border-accent hover:text-accent-blue"
          >
            بررسی کدال ↗
          </Link>
        </div>

        <div className="mt-auto pt-2 text-center text-[9px] uppercase tracking-widest text-text-muted">
          Symbol Inspector · FTS
        </div>
      </div>
    </aside>
  );
}
