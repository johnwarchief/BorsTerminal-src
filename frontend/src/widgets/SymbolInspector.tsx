// widgets/SymbolInspector.tsx -- داک باریک نماد در لبه چپ (فاز 8)
// دید متمرکز روی تک‌سهم در کنار دید کلان همه تب‌ها.
import { useMemo } from 'react';
import { Link } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtPct } from '@shared/lib/fmt';
import { ftsScoreOf } from '@contracts/fundamental';
import { FlashNum } from '@shared/components/FlashNum';
import { Badge } from '@shared/components/Badge';
import { aggregateSignals } from '@features/master/lib/masterMath';
import { runStrictGates, definiteDecision, weeklyTrendFromSignal } from '@features/master/lib/strictGates';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { AuditBadge } from '@features/fundamental/components/AuditBadge';
import { VolumeFlowMini } from '@features/market/components/VolumeFlowMini';
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

function MiniGauge({ pct, color, isVeto }: { pct: number; color: string; isVeto?: boolean }) {
  const r = 18;
  const circ = 2 * Math.PI * r;
  return (
    <svg width="42" height="42" viewBox="0 0 42 42" role="img" aria-label="گیج برآیند">
      <circle cx="21" cy="21" r={r} fill="none" stroke="var(--border-color)" strokeWidth="4" />
      <circle
        cx="21"
        cy="21"
        r={r}
        fill="none"
        stroke={isVeto ? 'var(--accent-red)' : color}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={isVeto ? circ : circ * (1 - pct / 100)}
        transform="rotate(-90 21 21)"
        style={{ transition: 'stroke-dashoffset 0.5s cubic-bezier(0.22, 1, 0.36, 1)' }}
      />
      <text
        x="21"
        y={isVeto ? '24' : '25'}
        textAnchor="middle"
        fontSize={isVeto ? '8.5' : '11'}
        fontWeight="900"
        fill={isVeto ? 'var(--accent-red)' : 'var(--text-primary)'}
        className="num"
      >
        {isVeto ? 'وتو' : toFaDigits(Math.round(pct))}
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
    <div className="flex items-center justify-between gap-1.5 rounded-md border border-transparent px-1.5 py-1 transition-colors duration-200 hover:border-[var(--hairline)] hover:bg-bg-card/40">
      <span className="flex items-center gap-1.5 text-[10px] text-text-secondary">
        <span
          aria-hidden
          className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full transition-all duration-300 ${
            on
              ? 'bg-accent-green shadow-[0_0_6px_var(--accent-green)]'
              : warn
                ? 'animate-pulse bg-accent-yellow shadow-[0_0_5px_var(--accent-yellow)]'
                : tone === 'red'
                  ? 'bg-accent-red shadow-[0_0_5px_var(--accent-red)]'
                  : 'bg-border-c'
          }`}
        />
        {label}
      </span>
      <span className={`num text-[10px] font-bold ${tone === 'green' || tone === 'blue' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : tone === 'yellow' || tone === 'orange' ? 'text-accent-yellow' : 'text-text-secondary'}`} title={hint}>
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

  const strictRes = useMemo(() => {
    if (!entry) return null;
    return runStrictGates(
      entry,
      {
        inBasket: Boolean(
          entry.portfolio?.payload &&
            (entry.portfolio.payload as { decision?: unknown }).decision === 'accept',
        ),
        industryUsedPct: null,
        industryCapPct: 20,
        warRegime: false,
        symbolWeightPct: null,
      },
      weeklyTrendFromSignal(entry.technical),
    );
  }, [entry]);

  const decision = useMemo(() => (strictRes ? definiteDecision(strictRes) : null), [strictRes]);
  const isVeto = Boolean(
    decision &&
      (decision.action === 'veto' ||
        decision.action === 'veto_gate1' ||
        decision.action === 'veto_gate2'),
  );

  const open = symbol.length > 0;
  const pct = isVeto ? 0 : verdict ? (verdict.compositeScore + 100) / 2 : 50;
  const gaugeColor = isVeto
    ? 'var(--accent-red)'
    : pct >= 60
      ? 'var(--accent-green)'
      : pct >= 40
        ? 'var(--neon-cyan)'
        : 'var(--neon-red)';

  const fund = entry?.fundamental;
  // امتیاز شمار شاخص‌های بنیادی ۰ تا ۵ (payload.score) — نه نمرهٔ ۰ تا ۱۰۰٬ اعتماد ترکیبی
  const fundFts = ftsScoreOf(fund);
  const tech = entry?.technical;
  const port = entry?.portfolio;

  return (
    <>
      {/* لایهی پشتزمینه؛ فقط در نمایشگرهای کوچک (<۱۰۲۴px) دیده میشود */}
      <div
        aria-hidden="true"
        onClick={clearSymbol}
        className={`fixed inset-0 z-40 bg-black/50 backdrop-blur-sm transition-opacity duration-200 lg:hidden ${
          open ? 'opacity-100' : 'pointer-events-none opacity-0'
        }`}
      />
      <aside
      aria-label={`بازرسی نماد ${symbol}`}
      className={`glass-panel fixed bottom-0 left-0 top-0 z-50 flex w-[var(--inspector-w)] max-w-[88vw] shrink-0 flex-col overflow-y-auto rounded-none border-y-0 border-l-0 p-0 transition-transform duration-200 ease-out shadow-2xl ${
        open ? 'translate-x-0' : '-translate-x-full'
      }`}
      style={{ borderRight: '1px solid var(--border-color)' }}
      aria-hidden={!open}
      {...{ inert: !open ? ('' as unknown as boolean) : undefined }}
    >
      {/* هدر: بستن + نماد */}
      <div className="sticky top-0 z-10 flex items-start justify-between gap-1.5 border-b border-[var(--hairline)] bg-bg-primary/85 px-2.5 py-2 backdrop-blur-md">
        <div className="min-w-0">
          <div className="truncate text-xs font-black text-text-primary">{symbol || '-'}</div>
          <div className="truncate text-[9.5px] text-text-muted">{row?.name || ''}</div>
          {row?.sector ? <div className="truncate text-[9.5px] text-text-muted">{row.sector}</div> : null}
        </div>
        <button
          type="button"
          onClick={clearSymbol}
          aria-label="بستن پنل نماد"
          className="shrink-0 rounded-md border border-transparent px-1.5 py-0.5 text-2xs text-text-muted transition-colors hover:border-[var(--hairline)] hover:text-accent-red"
        >
          ✕
        </button>
      </div>

      <div className="flex flex-col gap-2 p-2.5">
        {/* قیمت و درصد با فلاش */}
        <div className="flex items-end justify-between gap-2">
          <div>
            <div className="text-[8.5px] uppercase tracking-wider text-text-muted">آخرین معامله</div>
            <FlashNum value={row?.pLast} render={(v) => toFaDigits(v == null ? '-' : Number(v.toFixed(2)).toString())} className="text-sm font-black text-text-primary" />
          </div>
          <div className="text-end">
            <div className="text-[8.5px] uppercase tracking-wider text-text-muted">تغییر روز</div>
            <span className={row?.percentChange != null && row.percentChange >= 0 ? 'text-accent-green' : 'text-accent-red'}>
              <FlashNum value={row?.percentChange} render={(v) => (v == null ? '-' : fmtPct(v))} className="text-xs font-bold" />
            </span>
          </div>
        </div>

        {/* مینی کاکپیت مستر */}
        <div className="flex items-center gap-2.5 rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2">
          <MiniGauge pct={pct} color={gaugeColor} isVeto={isVeto} />
          <div className="flex min-w-0 flex-col gap-0.5">
            {isVeto ? (
              <Badge tone="red">ورود متوقف</Badge>
            ) : verdict ? (
              <Badge tone={ACTION_TONE[verdict.finalAction]}>{ACTION_FA[verdict.finalAction]}</Badge>
            ) : (
              <Badge tone="gray">بدون داده</Badge>
            )}
            <span className="num text-[9.5px] text-text-muted">
              {isVeto
                ? (decision?.action === 'veto_gate1' ? 'سد فیلتر ۱' : decision?.action === 'veto_gate2' ? 'سد فیلتر ۲' : 'توقف در فیلترها')
                : verdict
                  ? `${toFaDigits(verdict.usedSignalIds.length)}/۴ سیگنال`
                  : 'در انتظار سیگنال'}
            </span>
          </div>
        </div>

        {/* چهار چراغ وضعیت */}
        <div className="flex flex-col gap-0.5">
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

        {/* جریان حجم درون‌روزی با سقف ارتفاع ۶۰ پیکسل */}
        <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2">
          <div className="mb-1 text-[10px] font-bold text-text-secondary">جریان حجم (۰۸:۴۵ تا ۱۲:۳۰)</div>
          <div className="max-h-[60px] overflow-hidden">
            <VolumeFlowMini symbol={symbol} compact />
          </div>
        </div>

        {/* ممیزی وضعیت بنیادی (FTS) — بازشوی «چرا این وضعیت؟» */}
        <AuditBadge
          state={fund == null ? 'na' : fund.direction === 'bearish' ? 'fail' : 'pass'}
          evidence={{
            actualValue: fundFts,
            targetThreshold: 5,
            ruleRef: 'FTS',
            reason: fund?.rationale ?? null,
            direction: 'higher',
          }}
          compact
          title="چرا این وضعیت؟"
          label={`ممیزی بنیاد${fundFts == null ? '' : ': ' + toFaDigits(fundFts) + ' از ۵'}`}
          hintTitle="دلیل وضعیت شاخص بنیادی"
        />

        {/* دسترسی‌های سریع و اکشن‌ها در شبکه فشرده ۲×۲ */}
        <div className="grid grid-cols-2 gap-1.5 pt-1">
          <div className="flex items-center justify-center">
            <SymbolBasketAction symbol={symbol} compact />
          </div>
          <Link
            to={`/master/${encodeURIComponent(symbol)}`}
            className="flex items-center justify-center rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2 py-1 text-center text-[10px] font-bold text-accent-green transition-all duration-200 hover:border-accent-green hover:bg-accent-green/10"
            title="کاکپیت داوری مستر"
          >
            کاکپیت مستر ↗
          </Link>
          <Link
            to={`/technical/${encodeURIComponent(symbol)}`}
            className="flex items-center justify-center rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2 py-1 text-center text-[10px] font-bold text-accent-blue transition-all duration-200 hover:border-border-accent hover:text-neon-cyan"
            title="چارت تکنیکال"
          >
            چارت تکنیکال ↗
          </Link>
          <Link
            to={`/fundamental/${encodeURIComponent(symbol)}`}
            className="flex items-center justify-center rounded-lg border border-[var(--hairline)] bg-bg-card/60 px-2 py-1 text-center text-[10px] font-bold text-text-secondary transition-all duration-200 hover:border-border-accent hover:text-accent-blue"
            title="صورت‌های مالی و کدال"
          >
            بررسی کدال ↗
          </Link>
        </div>

        <div className="mt-auto pt-1 text-center text-[8.5px] uppercase tracking-widest text-text-muted">
          Symbol Inspector · FTS
        </div>
      </div>
    </aside>
    </>
  );
}
