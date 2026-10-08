// widgets/SymbolInspector.tsx -- داک باریک نماد در لبه چپ (فاز 8)
// دید متمرکز روی تک‌سهم در کنار دید کلان همه تب‌ها.
import { useMemo } from 'react';
import { Link, useLocation } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSignalStore, getActiveSignals } from '@shared/stores/signalStore';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtPct } from '@shared/lib/fmt';
import { ftsScoreOf } from '@contracts/fundamental';
import { LiveNumber } from '@shared/components/ui/live-number';
import { Badge } from '@shared/components/Badge';
import { RetryAction } from '@shared/components/RetryAction';
import { aggregateSignals } from '@features/master/lib/masterMath';
import {
  definiteDecision,
  runStrictGates,
  weeklyTrendFromSignal,
  type DefiniteAction,
} from '@features/master/lib/strictGates';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { basketRegimeFor } from '@features/portfolio/lib/basketRegime';
import { useCapitalStore } from '@features/master/stores/capitalStore';
import { AuditBadge } from '@features/fundamental/components/AuditBadge';
import { VolumeFlowMini } from '@features/market/components/VolumeFlowMini';
import { RegulatoryState } from '@features/market/components/RegulatoryState';
import { SidebarOrderBook } from '@features/technical/components/SidebarOrderBook';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { INSPECTOR_STAGES, stageHref, stageIndexForPath } from './inspectorStage';
import { useInspectorBoard, useInspectorRawRow } from './useInspectorBoard';
import { useSymbolVeto } from './useSymbolVeto';
import { useFtsFunnel } from '@features/master/api/useFtsFunnel';
import { stageProgressFor } from '@features/master/lib/funnelView';

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

/** رنگِ تصمیمِ قطعیِ گیت‌ها — همان داورِ کاکپیتِ مستر، نه میانگینِ وزنیِ آرا */
const DECISION_TONE: Record<DefiniteAction, 'green' | 'yellow' | 'red' | 'blue' | 'gray'> = {
  ladder_buy: 'green',
  high_risk_swing: 'yellow',
  watch: 'blue',
  veto: 'red',
  veto_gate1: 'yellow',
  veto_gate2: 'yellow',
};

function MiniGauge({ pct, color, mode }: { pct: number; color: string; mode: 'score' | 'veto' | 'wait' }) {
  const r = 18;
  const circ = 2 * Math.PI * r;
  const closed = mode !== 'score';
  return (
    <svg width="42" height="42" viewBox="0 0 42 42" role="img" aria-label="گیج برآیند">
      <circle cx="21" cy="21" r={r} fill="none" stroke="var(--border-color)" strokeWidth="4" />
      <circle
        cx="21"
        cy="21"
        r={r}
        fill="none"
        stroke={mode === 'veto' ? 'var(--accent-red)' : mode === 'wait' ? 'var(--accent-yellow)' : color}
        strokeWidth="4"
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={closed ? circ : circ * (1 - pct / 100)}
        transform="rotate(-90 21 21)"
        style={{ transition: 'stroke-dashoffset 0.5s cubic-bezier(0.22, 1, 0.36, 1)' }}
      />
      <text
        x="21"
        y={closed ? '24' : '25'}
        textAnchor="middle"
        fontSize={closed ? '8.5' : '11'}
        fontWeight="900"
        fill={
          mode === 'veto'
            ? 'var(--accent-red)'
            : mode === 'wait'
              ? 'var(--accent-yellow)'
              : 'var(--text-primary)'
        }
        className="num"
      >
        {mode === 'veto' ? 'وتو' : mode === 'wait' ? '…' : toFaDigits(Math.round(pct))}
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
  const togglePin = useSymbolStore((s) => s.togglePin);
  const pinned = useSymbolStore((s) => s.pinned);
  const row = useInspectorBoard();
  const feed = useMarketFeed();
  const { pathname } = useLocation();
  const stageIdx = stageIndexForPath(pathname);

  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const inputs = useMemo(() => (symbol ? getActiveSignals(symbol) : {}), [symbol, entry]);
  const verdict = symbol ? aggregateSignals(symbol, getActiveSignals(symbol)) : null;

  // رژیمِ سبد از همان تصمیم‌هایِ واقعیِ مستر خوانده می‌شود، نه از ثابت‌ها:
  // پیش‌تر این‌جا `industryCapPct: 20` و `warRegime: false` نوشته شده بود و
  // سایدبار برایِ نمادی که مستر آن را می‌بندد «خرید» می‌گفت.
  const basket = usePortfolio();
  const warRegime = useCapitalStore((s) => s.warRegime);
  const regime = useMemo(() => basketRegimeFor(symbol, basket.data?.decisions), [symbol, basket.data]);

  const strictRes = useMemo(() => {
    if (!entry) return null;
    return runStrictGates(
      // سیگنالِ غیرمنقضی، نه خامِ باس: با سیگنالِ منقضی، چراغ‌ها سبز می‌ماندند
      // و گیج قرمز «وتو» — دو جوابِ متناقض برایِ یک نماد در یک پنل.
      inputs,
      {
        inBasket: regime.inBasket,
        industryUsedPct: regime.industryUsedPct,
        industryCapPct: regime.industryCapPct,
        warRegime,
        symbolWeightPct: regime.symbolWeightPct,
      },
      weeklyTrendFromSignal(inputs.technical),
    );
  }, [entry, inputs, regime, warRegime]);

  const decision = useMemo(() => (strictRes ? definiteDecision(strictRes) : null), [strictRes]);

  // سه حالت، نه دو تا: وتویِ واقعی (مجمع/هفتگی) قرمز است؛ «هنوز سنجیده نشده»
  // زردِ درانتظار است و نباید واژۀ «وتو» را قرض بگیرد (رأیِ pilot گزینهٔ a،
  // همان قاعدۀ «بی‌داده وتو نیست» که بک‌اند هم به آن گارد دارد).
  const veto = useSymbolVeto(symbol);
  const rawRow = useInspectorRawRow();
  /** جایِ خودِ نماد در قیف — از همان پاسخِ /api/funnel که جدول می‌خواند.
   *  پیشِ این `symbolStageProgress` قواعدِ چهار در را رویِ تک‌ناماد درِ مرورگر
   *  دوباره اجرا می‌کرد (داورِ دوم). حالا وضعیت‌ها خوانده می‌شوند؛ اگر نماد درِ
   *  پاسخ نبود، هر چهار گام unknown است، نه رد. */
  const { funnel } = useFtsFunnel('custom');
  const progress = useMemo(() => stageProgressFor(funnel, symbol), [funnel, symbol]);
  /** اولین دری که رویِ این نماد بسته است — منفی یعنی هیچ‌جا وتو نشده */
  const stoppedAt = progress.findIndex((p) => p.state === 'blocked');

  const hardVeto = veto.assembly.veto || veto.weekly.veto || decision?.action === 'veto';
  const awaiting =
    !hardVeto && (decision?.action === 'veto_gate1' || decision?.action === 'veto_gate2');
  const gaugeMode: 'score' | 'veto' | 'wait' = hardVeto ? 'veto' : awaiting ? 'wait' : 'score';
  const isVeto = hardVeto;
  /** نامِ گیت‌هایی که سبز نیستند — خطِ دومِ کاکپیت، تا «چرا نه» مبهم نماند */
  const blockers = (strictRes?.gates ?? [])
    .filter((g) => g.state !== 'passed')
    .map((g) => g.label)
    .join('، ');
  const whyLine = veto.assembly.veto
    ? veto.assembly.label || 'مجمع عمومیِ پیش‌رو'
    : veto.weekly.veto || decision?.action === 'veto'
      ? `وتوی هفتگی${veto.weekly.desc ? ` — ${veto.weekly.desc}` : ' — روند هفتگی صعودی نیست'}`
      : awaiting
        ? decision?.action === 'veto_gate1'
          ? 'بنیادی هنوز سنجیده نشده'
          : 'تکنیکال هنوز سنجیده نشده'
        : blockers
          ? `سد: ${blockers}`
          : verdict && symbol
            ? `${toFaDigits(verdict.usedSignalIds.length)}/۴ سیگنال`
            : 'در انتظار سیگنال';

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

  // وضعیت سبد: رأیِ سیگنال اگر باشد، وگرنه تصمیمِ واقعیِ سبد. نبودِ سیگنال
  // «در سبد نیست» نبود (ادعای بی‌داده)؛ آن را از خودِ اندپوینتِ سبد می‌خوانیم و
  // اگر آن هم نخوانده بود، صادقانه «بی‌خبر».
  const portDecision = (port?.payload as { decision?: unknown } | null | undefined)?.decision;
  const basketIn = regime.inBasket === true || portDecision === 'accept';
  const basketOut = regime.inBasket === false && portDecision !== 'monitor' && portDecision !== 'reject';
  const basketValue =
    portDecision === 'reject'
      ? 'حذف‌شده'
      : portDecision === 'monitor'
        ? 'زیر نظر'
        : basketIn
          ? 'نگهداری'
          : basketOut
            ? 'در سبد نیست'
            : portDecision === 'pending'
              ? 'ظرفیت‌سنجی'
              : 'بی‌خبر';
  const basketTone: 'green' | 'red' | 'yellow' | 'gray' = portDecision === 'reject'
    ? 'red'
    : portDecision === 'monitor'
      ? 'yellow'
      : basketIn
        ? 'green'
        : 'gray';

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
      data-shell="inspector"
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
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={() => togglePin(symbol)}
            aria-pressed={pinned.includes(symbol)}
            aria-label="سنجاق کردن نماد برای دسترسی سریع"
            title={pinned.includes(symbol) ? 'از سنجاق برداشته می‌شود' : 'به سنجاق‌ها اضافه می‌شود — در Ctrl+K صدر می‌آید'}
            className={`rounded-md border px-1.5 py-0.5 text-2xs transition-colors ${
              pinned.includes(symbol)
                ? 'border-accent-amber/50 bg-accent-amber/15 text-accent-amber'
                : 'border-transparent text-text-muted hover:border-[var(--hairline)] hover:text-text-primary'
            }`}
          >
            سنجاق
          </button>
          <button
            type="button"
            onClick={clearSymbol}
            aria-label="بستن پنل نماد"
            className="rounded-md border border-transparent px-1.5 py-0.5 text-2xs text-text-muted transition-colors hover:border-[var(--hairline)] hover:text-accent-red"
          >
            ✕
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-2 p-2.5">
        {/* خطای خوراک با «ردیف نیست» یکی نیست: بی‌این، بیست '-' بی‌صدا معنای
            «داده نیست» به کاربر می‌فروشد وقتی مشکل، رسیدنِ داده است. */}
        {!row && feed.isError ? (
          <div
            data-testid="inspector-feed-error"
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-dashed border-accent-red/40 bg-accent-red/10 px-2 py-1.5 text-3xs text-accent-red"
          >
            <span>تابلو نمی‌رسد — اعداد این نماد تازه نیست</span>
            <RetryAction onRetry={() => void feed.refetch()} testId="inspector-feed-retry" />
          </div>
        ) : null}
        {/* نشانگر مرحلۀ قیف: تبِ فعال («الان کجاییم») + جای خودِ نماد در قیف
            («این سهم کجا ایستاده»). حلقه‌ها از همان `symbolStageProgress`ِ قیف
            می‌آیند — سایدبار قواعدِ دومی نمی‌سازد. */}
        {stageIdx != null ? (
          <nav
            aria-label="مراحل غربالگری FTS"
            data-testid="inspector-stage"
            className="flex flex-wrap items-center gap-1 text-[10px] font-bold"
          >
            {INSPECTOR_STAGES.map((s, i) => {
              const p = progress[i];
              const st = p?.state ?? 'unknown';
              return (
                <Link
                  key={s.key}
                  to={stageHref(i, symbol)}
                  aria-current={i === stageIdx ? 'step' : undefined}
                  data-testid={`inspector-stage-${s.key}`}
                  data-stage-state={st}
                  title={p?.why || `${s.label}: هنوز منبعی برای داوری این مرحله نیست`}
                  className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 transition-colors ${
                    i === stageIdx
                      ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                      : 'border-border-c/60 bg-bg-primary text-text-muted hover:text-text-primary'
                  }`}
                >
                  <span
                    aria-hidden
                    data-testid={`inspector-stage-dot-${s.key}`}
                    className={`inline-block h-1.5 w-1.5 shrink-0 rounded-full ${
                      st === 'passed'
                        ? 'bg-accent-green'
                        : st === 'blocked'
                          ? 'bg-accent-red'
                          : st === 'waiting'
                            ? 'bg-accent-yellow'
                            : st === 'not_required'
                              ? 'bg-border-c/40 ring-1 ring-border-c/60'
                              : st === 'not_in_universe'
                                ? 'bg-bg-secondary ring-1 ring-border-c'
                                : 'bg-border-c'
                    }`}
                  />
                  {s.label}
                  {st === 'not_required' ? (
                    <span className="text-[9px] font-normal opacity-70" data-testid={`inspector-stage-note-${s.key}`}>
                      · لازم نبود
                    </span>
                  ) : null}
                  {st === 'not_in_universe' ? (
                    <span className="text-[9px] font-normal opacity-70" data-testid="inspector-stage-out">
                      · خارج از جامعه
                    </span>
                  ) : null}
                </Link>
              );
            })}
            <span className="w-full text-[9.5px] font-normal text-text-muted" data-testid="inspector-stage-next">
              {progress[0]?.state === 'not_in_universe'
                ? `خارج از جامعۀ غربالگری — ${progress[0].why}`
                : stoppedAt >= 0
                ? `ایستاده در «${INSPECTOR_STAGES[stoppedAt].label}» — ${progress[stoppedAt].why}`
                : stageIdx < INSPECTOR_STAGES.length - 1
                  ? `مرحلۀ فعلی: ${INSPECTOR_STAGES[stageIdx].label} · بعدی: ${INSPECTOR_STAGES[stageIdx + 1].label}`
                  : `مرحلۀ فعلی: ${INSPECTOR_STAGES[stageIdx].label} — پایِ غربالگری`}
            </span>
          </nav>
        ) : null}

        {/* قیمت و درصد با انیمیشن زنده و فلاش مارکت */}
        <div className="flex items-end justify-between gap-2">
          <div>
            <div className="text-[8.5px] uppercase tracking-wider text-text-muted">آخرین معامله</div>
            <LiveNumber
              value={row?.pLast}
              format={(v) => toFaDigits(Number(v.toFixed(2)).toString())}
              className="text-sm font-black text-text-primary"
            />
          </div>
          <div className="text-end">
            <div className="text-[8.5px] uppercase tracking-wider text-text-muted">تغییر روز</div>
            <span className={row?.percentChange != null && row.percentChange >= 0 ? 'text-accent-green' : 'text-accent-red'}>
              <LiveNumber
                value={row?.percentChange}
                format={(v) => fmtPct(v)}
                className="text-xs font-bold"
              />
            </span>
          </div>
        </div>

        {/* وضعیتِ ناظر (TSETMC): کفِ سلسله‌مراتبِ همین پنل — «الان می‌شود-trade کرد
            یا نه» پیش از هر عددی خوانده می‌شود. متنِ کامل درِ بازشو. */}
        <RegulatoryState row={rawRow} feedFailed={feed.isError} />

        {/* مینی کاکپیت مستر
            بج از «تصمیمِ قطعیِ گیت‌ها» می‌آید، نه از میانگینِ وزنیِ آرا: میانگین
            می‌توانست «خرید قوی» بگوید در حالی که گیتِ سبد (رژیم جنگی/سقفِ صنعت)
            همان نماد را بسته است — دو پنل، دو جواب. */}
        <div className="flex items-center gap-2.5 rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-2">
          <MiniGauge pct={pct} color={gaugeColor} mode={gaugeMode} />
          <div className="flex min-w-0 flex-col gap-0.5">
            {hardVeto ? (
              <Badge tone="red">ورود متوقف</Badge>
            ) : awaiting ? (
              <Badge tone="yellow">در انتظارِ سنجش</Badge>
            ) : decision ? (
              <Badge tone={DECISION_TONE[decision.action]}>{decision.label}</Badge>
            ) : verdict ? (
              <Badge tone={ACTION_TONE[verdict.finalAction]}>{ACTION_FA[verdict.finalAction]}</Badge>
            ) : (
              <Badge tone="gray">بدون داده</Badge>
            )}
            <span className="num text-[9.5px] text-text-muted" data-testid="inspector-veto-why">
              {whyLine}
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
            value={basketValue}
            tone={basketTone}
            hint={port?.rationale}
          />
        </div>

        {/* پنج مظنه — همان عمقی که در تب تکنیکال است، این‌جا برایِ همان نماد */}
        <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-1.5">
          <div className="mb-1 text-[10px] font-bold text-text-secondary">پنج مظنه</div>
          <SidebarOrderBook symbol={symbol} compact />
        </div>

        {/* جریان حجم درون‌روز — کارتِ خودکفا (عنوان و محورِ خودش را دارد) */}
        <VolumeFlowMini symbol={symbol} compact />

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
          label={`ممیزی بنیادی${fundFts == null ? '' : ': ' + toFaDigits(fundFts) + ' از ۵'}`}
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
