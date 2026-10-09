// widgets/SymbolInspector.tsx -- داک باریک نماد در لبه چپ (فاز 8)
// دید متمرکز روی تک‌سهم در کنار دید کلان همه تب‌ها.
import { useEffect, useMemo, useState } from 'react';
import { Link, useLocation } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSignalStore, getActiveSignals } from '@shared/stores/signalStore';
import { billionRialText, fmtHemmat, fmtInt, toBillionRial, toFaDigits } from '@shared/lib/fmt';
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
import { BuySellCell } from '@features/market/components/BuySellCell';
import { buyPerCapitaMt, sellPerCapitaMt } from '@features/market/lib/tapeFts';
import { useCalendarEvents } from '@features/fundamental/api/useCalendarEvents';
import { jalaliOf } from '@features/fundamental/lib/assemblyEvent';
import { SidebarOrderBook } from '@features/technical/components/SidebarOrderBook';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { INSPECTOR_STAGES, stageHref, stageIndexForPath } from './inspectorStage';
import { useInspectorBoard, useInspectorRawRow } from './useInspectorBoard';
import { useSymbolVeto } from './useSymbolVeto';
import { useFtsFunnel } from '@features/master/api/useFtsFunnel';
import { useActiveFunnelPreset } from '@features/master/lib/useActiveFunnelPreset';
import { useFunnelTrace } from '@features/master/api/useFunnelTrace';
import { FunnelTraceList } from '@features/master/ui/FunnelTraceList';
import { stageProgressFor } from '@features/master/lib/funnelView';
import { IND_COLUMNS, STATUS_LABEL, trendLabel } from '@features/master/lib/ftsFunnel';

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

/** چیپِ روندِ یک تایم‌فریم — واژگانِ موتور (`up`/`down`/`range`/`na`) به زبانِ
 *  چارت ۳؛ `na`/نبود ⇒ «بی‌ساختار» و بی‌رنگ، که «نزولی» نیست. هیچ روندِ ساختگی
 *  از نبودِ داده ساخته نمی‌شود. */
function TrendChip({ side, value }: { side: string; value: string | null }) {
  const tone = value === 'up' ? 'text-accent-green'
    : value === 'down' ? 'text-accent-red'
    : value === 'range' ? 'text-accent-yellow'
    : 'text-text-muted';
  return (
    <span className="flex items-baseline gap-1">
      <span className="text-[9px] text-text-muted">{side}</span>
      <span className={`num font-bold ${tone}`} data-testid={`inspector-trend-${side}`}>
        {trendLabel(value)}
      </span>
    </span>
  );
}

export function SymbolInspector() {
  const storedSymbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const togglePin = useSymbolStore((s) => s.togglePin);
  const pinned = useSymbolStore((s) => s.pinned);
  const row = useInspectorBoard();
  const feed = useMarketFeed();
  const { pathname } = useLocation();
  const stageIdx = stageIndexForPath(pathname);
  // نشانی منبعِ نماد هم هست. پیش‌تر این پنل فقط استور را می‌خواند، پس هر
  // پیوندِ مستقیمِ ‎#/master/فولاد (لینک، «عقب» مرورگر، بازکردنِ دوباره پس از
  // ری‌استارت) سایدبار را خالی می‌گذاشت — نه فقط عددِ تازه، حتی «آخرین معامله»
  // هم «-» می‌ماند چون ردیفِ تابلو هرگز resolve نمی‌شد.
  const routeSymbol = useMemo(() => {
    const m = /^\/master\/([^/?#]+)/.exec(pathname ?? '');
    if (!m) return null;
    try { return decodeURIComponent(m[1]); } catch { return m[1]; }
  }, [pathname]);
  const symbol = routeSymbol ?? storedSymbol;
  useEffect(() => {
    if (routeSymbol && routeSymbol !== storedSymbol) setSymbol(routeSymbol);
  }, [routeSymbol, storedSymbol, setSymbol]);

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
  /** جایِ خودِ نماد در قیف — از همان پاسخِ /api/funnel که جدول می‌خواند: یکیِ
   *  presetِ فعال (URL > انتخابِ کاربر > افق)، نه `'custom'`ِ ثابت. بی‌این سه سطح
   *  (جدول، dossier، سایدبار) سه مدلِ متفاوت از یک universe را می‌سنجیدند. */
  const { funnel, request: funnelRequest } = useFtsFunnel(useActiveFunnelPreset());
  // ردیفِ غنیِ همین نماد از همان پاسخِ غربالگری (یک findsِ اضافی به‌جای پنج تا):
  // مخرجِ I4 و شمارۀِ sales از همین‌جا خوانده می‌شود، نه از یک پرس‌وجویِ تازه.
  const cand = useMemo(() => {
    for (const k of ['fundamental', 'technical', 'handover', 'tape'] as const) {
      const hit = funnel.stages[k].entries.find((e) => e.symbol === symbol);
      if (hit) return hit;
    }
    return null;
  }, [funnel, symbol]);
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

  // ── ۱۵.۲۰ دو صفحۀ محلی (رأیِ مالک ۱۴۰۵-۰۷-۱۷) ──────────────────────────────
  // جابه‌جاییِ صفحّه فقط «دیدن» است: نه درخواستِ تازه می‌زند نه refetchِ صفحۀ
  // دیگر. `detailSeen` نگهبانِ mount است: تا بارِ اول باز نشود پنج مظنه پرسیده
  // نمی‌شود (query درِ خودش enabled-gated است)، و بعد از آن mount می‌ماند تا
  // حالتِ بازشوِ پنل‌هایش با هر تبِ دیگر گم نشود.
  const [page, setPage] = useState<'glance' | 'detail'>('glance');
  const [detailSeen, setDetailSeen] = useState(false);
  const [quotesOpen, setQuotesOpen] = useState(false);
  const goPage = (k: 'glance' | 'detail') => {
    setPage(k);
    if (k === 'detail') setDetailSeen(true);
  };
  // رویدادها از همان تقویمِ خودِ بک‌اند (`/api/calendar/<symbol>`) خوانده می‌شوند
  // با همان کشِ شش‌ساعته‌اش — نه از یک منبعِ دومِ اختراعیِ درِ فرانت.
  // ردپایِ فیلتر‌به‌فیلتر از همان درخواستِ جدولِ غربالگری — تا سایدبار و جدول
  // یک حکم داشته باشند، نه دو تا.
  const trace = useFunnelTrace(symbol, funnelRequest);
  const calEvents = useCalendarEvents(symbol);
  const events = useMemo(() => (calEvents.data?.events ?? []).slice(0, 3), [calEvents.data]);

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
        {/* ── ۱۵.۲۰ دو صفحۀ محلیِ بازرسی نماد (رأیِ مالک ۱۴۰۵-۰۷-۱۷) ────────
            «در یک نگاه» = همان سطرهایِ خودش به همان ترتیبِ رأیِ داده‌شده،
            «جزئیات بازار» = ردیف‌هایِ پُر جزئیات. جابه‌جایی فقط دیدن است: نه
            درخواستِ تازه‌ای می‌زند نه refetch. صفحۀ دوم تا باز نشده mount نمی‌شود
            تا پرسشِ پنج مظنه بی‌مصرف نرود، و بعد از باز شدن سرِ جایش می‌ماند تا
            حالتِ بازشوِ خودش گم نشود. */}
        <nav aria-label="صفحه‌هایِ بازرسی" data-testid="inspector-tabs" className="grid grid-cols-2 gap-1">
          {([['glance', 'در یک نگاه'], ['detail', 'جزئیات بازار']] as const).map(([k, lbl]) => (
            <button key={k} type="button" aria-current={page === k ? 'page' : undefined}
                    data-testid={`inspector-tab-${k}`} onClick={() => goPage(k)}
                    className={`rounded-md border px-2 py-1 text-[10px] font-bold transition-colors ${
                      page === k
                        ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue'
                        : 'border-border-c/60 bg-bg-primary text-text-muted hover:text-text-primary'
                    }`}>
              {lbl}
            </button>
          ))}
        </nav>

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

        <div data-testid="inspector-page-glance"
             className={page === 'glance' ? 'flex flex-col gap-2' : 'hidden'}>
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

          {/* ── بخش ۲ («در یک نگاه»): وضعیتِ قیمت — همان ستون‌هایِ تابلو، بی‌محاسبه
              درِ رابط. «٪ آخرین» (p_last به دیروز) از «٪ پایانی» (percent_change،
              p_closing به دیروز) جدا می‌ماند؛ یکی جای دیگری نمی‌نشیند. اولین/
              بیشترین/کمترین از `p_first`/`p_max`/`p_min` خوانده می‌شوند و صفرِ
              واقعیِ این سه «مبادله‌ای در این سطح نبود» است، نه قیمتِ صفر ⇒ «—» با
              منشأ درِ title. نبودِ کلید ⇒ «—» (بی‌داده)، نه پرشدن با آخرین/پایانی. */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9.5px]"
               data-testid="inspector-price-grid">
            <span className="flex items-baseline gap-1 text-text-muted">
              پایانی
              <span className="num font-bold text-text-primary" data-testid="inspector-p-closing"
                    title={rawRow?.p_closing != null ? fmtInt(rawRow.p_closing) : 'قیمتِ پایانی درِ پاسخ نیست'}>
                {rawRow?.p_closing != null ? fmtInt(rawRow.p_closing) : '—'}
              </span>
            </span>
            <span className="flex items-baseline gap-1 text-text-muted">
              ٪آخرین
              <span className={`num font-bold ${rawRow?.percent_last != null && rawRow.percent_last >= 0 ? 'text-accent-green' : 'text-accent-red'}`}
                    data-testid="inspector-percent-last"
                    title="درصدِ آخرین به دیروز (p_last÷price_yesterday) — با ٪پایانی یکی نیست">
                {fmtPct(rawRow?.percent_last)}
              </span>
            </span>
            <span className="flex items-baseline gap-1 text-text-muted">
              اولین
              <span className="num font-bold text-text-secondary" data-testid="inspector-p-first"
                    title={rawRow?.p_first ? fmtInt(rawRow.p_first) : 'اولینِ مبادله هنوز ثبت نشده یا درِ پاسخ نیست'}>
                {rawRow?.p_first ? fmtInt(rawRow.p_first) : '—'}
              </span>
            </span>
            <span className="flex items-baseline gap-1 text-text-muted">
              بیشینه
              <span className="num font-bold text-text-secondary" data-testid="inspector-p-max"
                    title={rawRow?.p_max ? fmtInt(rawRow.p_max) : 'بیشترینِ همین نشست ثبت نشده یا درِ پاسخ نیست'}>
                {rawRow?.p_max ? fmtInt(rawRow.p_max) : '—'}
              </span>
            </span>
            <span className="flex items-baseline gap-1 text-text-muted">
              کمینه
              <span className="num font-bold text-text-secondary" data-testid="inspector-p-min"
                    title={rawRow?.p_min ? fmtInt(rawRow.p_min) : 'کمترینِ همین نشست ثبت نشده یا درِ پاسخ نیست'}>
                {rawRow?.p_min ? fmtInt(rawRow.p_min) : '—'}
              </span>
            </span>
          </div>

          {/* ── ۱۵.۲۰ حجم/تعداد و ارزشِ معاملات — دو مقدارِ همان ستون‌هایِ تابلو
              با همان واحد. اینجا عددِ تازه‌ای محاسبه نمی‌شود؛ فقط همان‌ها خوانده
              می‌شود (تک‌تعریفِ واحد درِ `shared/lib/fmt`). */}
          <div className="grid grid-cols-3 items-end gap-1 rounded-lg border border-[var(--hairline)] bg-bg-card/40 px-2 py-1"
               data-testid="inspector-volume">
            <div className="min-w-0">
              <div className="text-[8.5px] text-text-muted">حجم</div>
              <div className="num truncate text-[10.5px] font-bold text-text-primary"
                   data-testid="inspector-volume-num"
                   title={rawRow?.tvol != null ? fmtInt(rawRow.tvol) : undefined}>
                {rawRow?.tvol != null ? fmtInt(rawRow.tvol) : 'بی‌داده'}
              </div>
            </div>
            <div className="min-w-0">
              <div className="text-[8.5px] text-text-muted">تعداد</div>
              <div className="num truncate text-[10.5px] font-bold text-text-primary"
                   data-testid="inspector-trades-num"
                   title={rawRow?.z_tot_tran != null ? fmtInt(rawRow.z_tot_tran) : undefined}>
                {rawRow?.z_tot_tran != null ? fmtInt(rawRow.z_tot_tran) : 'بی‌داده'}
              </div>
            </div>
            <div className="min-w-0">
              <div className="truncate text-[8.5px] text-text-muted">ارزش (م.ریال)</div>
              <div className="num truncate text-[10.5px] font-bold text-text-primary"
                   data-testid="inspector-value-num"
                   title={rawRow?.q_tot_cap != null ? `${fmtInt(rawRow.q_tot_cap)} ریال` : undefined}>
                {rawRow?.q_tot_cap != null ? billionRialText(toBillionRial(rawRow.q_tot_cap)) : 'بی‌داده'}
              </div>
            </div>
          </div>

          {/* ارزشِ بازار و I4 از یک مبنایِ واحد (رأیِ مالک ۱۴۰۵-۰۷-۱۷): همان
              `market_watch.market_cap` که مخرجِ I4 درِ موتور است، اینجا می‌نشیند —
              پس «two market cap» درِ رابط نداریم. TSETMC برایِ هر نماد `marketValue`
              ساختاریاره نمی‌فرستد (سنجشِ زنده: فقط سطحِ بازار)، لذا مبنا همان
              ستونِ تابلو با برچسبِ منشأ است. نبودِ عدد ⇒ «بی‌داده»، هرگز صفر. */}
          <div className="flex items-center justify-between gap-2 rounded-lg border border-[var(--hairline)] bg-bg-card/40 px-2 py-1"
               data-testid="inspector-market-cap">
            <span className="text-[9px] text-text-muted">ارزشِ بازار</span>
            <span className="num text-[11px] font-bold text-text-primary"
                  title={`مبنایِ TSETMC: ${rawRow?.mcap_src || 'بی‌منبع'} — `
                         + `${rawRow?.is_live === false ? 'آخرینِ نشستِ تابلو' : 'نشستِ جاریِ تابلو'}`}>
              {rawRow?.mcap ? fmtHemmat(rawRow.mcap) : 'بی‌داده'}
            </span>
            <span className="text-[9px] text-text-muted">I4</span>
            {(() => {
              // رأیِ I4ِ موتور دست‌نخورده است؛ آنچه اینجا نشان داده می‌شود
              // «نسبتِ با ارزشِ بازارِ همین ردیفِ تابلو» است:
              //   فروشِ ۱۲ ماهه (برآورد، میلیارد تومان) × ۱e10 ÷ mcap(ریال)
              // و اگر با نسبتِ ثبت‌شدۀ موتور نمی‌خواند، **هر دو** عدد دیده
              // می‌شوند — نه بازنویسیِ بی‌صدایِ حکم، نه داورِ دوم درِ فرانت.
              const salesBt = cand?.screen?.annual_sales_bt ?? null;
              const cached = cand?.screen?.sales_to_mcap ?? null;
              const mcap = rawRow?.mcap ?? null;
              const live = salesBt != null && mcap ? (salesBt * 1e10) / mcap : null;
              const shown = live ?? cached;
              if (shown == null) {
                return <span className="num text-[11px] text-text-muted" data-testid="inspector-i4"
                             title="I4 = فروشِ ۱۲ ماهه ÷ ارزشِ بازار؛ نه فروش داریم نه مبنایِ معتبر">بی‌داده</span>;
              }
              const differs = live != null && cached != null && Math.abs(live - cached) > 0.005;
              return (
                <Link to={`/fundamental?symbol=${encodeURIComponent(symbol)}`}
                      data-testid="inspector-i4"
                      title={`فروشِ ۱۲ ماهه (برآورد): ${salesBt != null ? toFaDigits(Math.round(salesBt)) : '—'} میلیارد تومان`
                        + ` ÷ ارزشِ بازارِ همین ردیف: ${mcap != null ? fmtHemmat(mcap) : '—'}`
                        + ` ⇒ ${toFaDigits(shown.toFixed(2))}×`
                        + (differs ? ` — نسبتِ ثبت‌شدۀ موتور: ${toFaDigits(cached!.toFixed(2))}×`
                                   : ' — با نسبتِ ثبت‌شدۀ موتور می‌خواند')
                        + '\nمبنایِ ارزشِ بازار: TSETMC (' + (rawRow?.mcap_src || 'بی‌منبع') + ')؛'
                        + ' حکمِ پذیرش/رد را همان موتورِ بنیادی می‌دهد، این عدد فقط نسبتِ زنده است.'}
                      className="num flex items-baseline gap-1 text-[11px] font-bold text-accent-blue hover:underline">
                  {toFaDigits(shown.toFixed(2))}×
                  {differs ? (
                    <span className="text-[8.5px] font-normal text-accent-amber"
                          data-testid="inspector-i4-diverges">
                      (موتور: {toFaDigits((cached as number).toFixed(2))}×)
                    </span>
                  ) : null}
                </Link>
              );
            })()}
          </div>

          {/* ── ۱۵.۲۰ قدرت خرید/فروش — همان خانۀ ستونِ «خرید/فروش»ِ تابلو
              (دو سرانه + نوارِ سهم + نسبت)، بی‌اوراقِ دوباره‌نویسی: یک
              implementation درِ `BuySellCell`. پرچمِ الگو همین‌جا می‌ماند، چون
              همان دو سرانه را داوری می‌کند؛ پیش‌تر درِ چراغِ «سرانۀ خریدار» بود. */}
          <div className="flex flex-col gap-0.5 rounded-lg border border-[var(--hairline)] bg-bg-card/40 px-2 py-1"
               data-testid="inspector-power">
            <div className="flex items-center justify-between gap-1">
              <span className="text-[8.5px] text-text-muted">قدرت خرید/فروش</span>
              {rawRow?.f_clock || rawRow?.f_susp ? (
                <span className="text-[8.5px] text-accent-amber" data-testid="inspector-power-pattern">
                  {rawRow?.f_clock ? 'الگوی ساعت' : 'حجم مشکوک'}
                </span>
              ) : null}
            </div>
            {/* خانۀ تمام‌عرض: پنل ۲۴۰ پیکسل است و برچسبِ کنارِ سلول، خودِ سلول را
                می‌شکست (سرریزِ ۱۰۸→۷۴ پیکسل درِ سنجشِ زنده دیده شد). */}
            <BuySellCell testId="inspector-buy-sell"
                         buyPc={rawRow ? buyPerCapitaMt(rawRow) : null}
                         sellPc={rawRow ? sellPerCapitaMt(rawRow) : null}
                         power={rawRow?.buyer_power} />
          </div>

          {/* وضعیتِ ناظر (TSETMC): کفِ سلسله‌مراتبِ همین پنل — «الان می‌شود-trade کرد
              یا نه» پیش از هر عددی خوانده می‌شود. متنِ کامل درِ بازشو. */}
          <RegulatoryState row={rawRow} feedFailed={feed.isError} />

          <div className="flex flex-col gap-0.5">
              <StatusLight
                label="تکنیکال FTS"
                value={tech == null ? '-' : tech.direction === 'bullish' ? 'صعودی' : tech.direction === 'bearish' ? 'نزولی' : 'خنثی'}
                tone={tech == null ? 'gray' : tech.direction === 'bullish' ? 'green' : tech.direction === 'bearish' ? 'red' : 'yellow'}
                hint={tech?.rationale}
              />
              <StatusLight
                label="نمره بنیادی"
                value={fund?.score == null ? '-' : toFaDigits(fund.score)}
                tone={fund == null ? 'gray' : fund.direction === 'bullish' ? 'green' : fund.direction === 'bearish' ? 'red' : 'yellow'}
                hint={fund?.rationale}
              />
          </div>

          {/* ── بخش ۷ («در یک نگاه»): نمای فشردهٔ تکنیکال — روندِ روزانه و هفتگی از
              همان خروجیِ canonicalِ قیف (`cand.trendD`/`cand.trendW` ← `trend.matrix`)
              و جت از پرچمِ canonicalِ تابلو (`f_jet` درِ tape_flags). بی‌نامزدِ رسیدن
              به این گام ⇒ «—»، که با «نزولی» یکی نیست؛ هیچ روندِ ساختگی ساخته نمی‌شود. */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[9.5px]"
               data-testid="inspector-trend">
            <span className="text-[9px] text-text-muted">روند</span>
            <TrendChip side="روزانۀ" value={cand?.trendD ?? null} />
            <TrendChip side="هفتگی" value={cand?.trendW ?? null} />
            <span className="flex items-center gap-1" data-testid="inspector-jet">
              <span className="text-[9px] text-text-muted">جت</span>
              <span className={`rounded px-1 font-bold ${
                rawRow?.f_jet ? 'bg-accent-amber/15 text-accent-amber' : 'text-text-muted'
              }`} title={rawRow?.f_jet ? 'پرچمِ جت از داوریِ canonicalِ تابلو (f_jet)' : 'جتِ canonical روشن نیست'}>
                {rawRow?.f_jet ? '✓' : '—'}
              </span>
            </span>
          </div>

          {/* ── بخش ۸ («در یک نگاه»): پنج شاخصِ بنیادی از همان پاسخِ غربالگری —
              مقدار از `cand.screen`، حکم از `cand.inds`؛ هیچ محاسبهٔ دومی درِ رابط
              نیست و هیچ شاخصِ ناقص به صفر بدل نمی‌شود. نبودِ مقدار ⇒ «—» با علتِ
              «داده نیست» یا «لازم نبود» (حکمِ خودِ گام)، نه نتیجهٔ تأییدشده. */}
          <div className="flex flex-wrap items-center gap-1 text-[9.5px]"
               data-testid="inspector-i1-i5">
            {IND_COLUMNS.map((col, i) => {
              const st = cand?.inds?.[i] ?? null;
              const val = i === 0 ? cand?.screen?.rev_growth
                : i === 1 ? cand?.screen?.eps_last
                : i === 2 ? cand?.screen?.gross_margin
                : i === 3 ? cand?.screen?.sales_to_mcap
                : cand?.screen?.pricing_mode;
              const txt = i === 0 || i === 2
                ? (val == null ? '—' : fmtPct(val as number))
                : i === 3
                  ? (val == null ? '—' : toFaDigits((val as number).toFixed(2)) + '×')
                  : i === 1
                    ? (val == null ? '—' : fmtInt(val as number))
                    : (val == null || val === '' ? '—' : String(val));
              const tone = st === 'pass' ? 'border-accent-green/40 bg-accent-green/10 text-accent-green'
                : st === 'reject' ? 'border-accent-red/40 bg-accent-red/10 text-accent-red'
                : st === 'pending' || st === 'unavailable' ? 'border-accent-yellow/40 bg-accent-yellow/10 text-accent-yellow'
                : 'border-border-c/60 text-text-muted';
              return (
                <span key={col.key} data-testid={`inspector-ind-${col.key}`}
                      title={`${col.full}${st ? ` — وضعیت: ${STATUS_LABEL[st]}` : ' — هنوز داوری‌ای برای این شاخص نیست'}`}
                      className={`flex items-center gap-1 rounded-md border px-1.5 py-0.5 ${tone}`}>
                  <span className="opacity-70">{col.label}</span>
                  <span className="num font-bold">{txt}</span>
                </span>
              );
            })}
          </div>

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

          {/* ── ۱۵.۲۰ رویدادها — عنوانِ خودِ اطلاعیه از تقویمِ نماد
              (`/api/calendar/<symbol>`)، نه برچسبِ اختراعی. سه رویدادِ نخستِ
              پیشِ رو؛ «همه» به صفحۀ بنیادی می‌رود. */}
          <div className="flex flex-col gap-0.5 rounded-lg border border-[var(--hairline)] bg-bg-card/40 px-2 py-1"
               data-testid="inspector-events">
            <div className="flex items-center justify-between gap-2">
              <span className="text-[9px] text-text-muted">رویدادها</span>
              <Link to={`/fundamental?symbol=${encodeURIComponent(symbol)}`}
                    data-testid="inspector-events-all"
                    className="text-[9px] text-accent-blue hover:underline">همه ↗</Link>
            </div>
            {events.length === 0 ? (
              <span className="text-[10px] text-text-muted" data-testid="inspector-events-none">
                {calEvents.isError ? 'تقویم نمی‌رسد'
                 : calEvents.isPending ? 'در حالِ خواندنِ تقویم'
                 : 'رویدادی ثبت نشده'}
              </span>
            ) : (
              <ul className="flex flex-col gap-0.5">
                {events.map((e, i) => (
                  <li key={`${e.date}-${i}`} className="truncate text-[10px] text-text-secondary"
                      title={`${e.date} — ${e.title ?? ''}`}>
                    <span className="num text-text-muted">{jalaliOf(e.date)}</span>
                    {' '}{e.title ?? '—'}
                    {/* رأیِ §۲۴: اگر عنوانِ اطلاعیه تاریخِ جلسه را نمی‌گفت، این عدد
                        فقط تاریخِ انتشار است — بی‌علامت گذاشتنش «X روز تا مجمع»
                        به کاربر می‌فروشد. */}
                    {e.date_source === 'title' ? null : (
                      <span className="text-text-muted" data-testid="inspector-event-published"> (انتشار)</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </div>

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
        </div>

        {detailSeen ? (
          <div data-testid="inspector-page-detail"
               className={page === 'detail' ? 'flex flex-col gap-2' : 'hidden'}>
          {/* ── ۱۵.۲۰ پنج مظنه، بسته به‌پیش‌فرض — «بسته» یعنی «نپرسیده نشده»،
              نه «حذف شده»: اجزایِ عمق فقط وقتی پرسیده می‌شوند که بازشده باشد، و
              کلِ پنل هم درِ صفحۀ دوم سرِ جایش است. */}
          <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 p-1.5"
               data-testid="inspector-quotes">
            <button type="button" onClick={() => setQuotesOpen((v) => !v)} aria-expanded={quotesOpen}
                    data-testid="inspector-quotes-toggle"
                    className="flex w-full items-center justify-between gap-2 text-[10px] font-bold text-text-secondary">
              <span>پنج مظنه</span>
              <span className="text-[9px] font-normal text-accent-blue">
                {quotesOpen ? 'بستن' : 'نمایش'}
              </span>
            </button>
            {quotesOpen ? (
              <div className="mt-1">
                <SidebarOrderBook symbol={symbol} compact />
              </div>
            ) : null}
          </div>

          {/* جریان حجم درون‌روز — کارتِ خودکفا (عنوان و محورِ خودش را دارد) */}
          <VolumeFlowMini symbol={symbol} compact />

          {/* ردپا — همان `timeline`ِ موتور برایِ همین نماد: کدام فیلتر، با چه
              دلیلی، با چه ورودی/خروجی‌ای رد یا قبولش کرد. بی‌این، سایدبار فقط
              «ایستاده در مرحلۀ X» را می‌گفت. */}
          <div className="rounded-lg border border-[var(--hairline)] bg-bg-card/40 px-2 py-1.5"
               data-testid="inspector-trace">
            <div className="mb-1 text-[10px] font-bold text-text-secondary">ردپایِ غربالگری</div>
            {trace.isError ? (
              <span className="text-[10px] text-accent-red" data-testid="funnel-trace-error">
                ردپا نمی‌رسد
              </span>
            ) : trace.isPending ? (
              <span className="text-[10px] text-text-muted" data-testid="funnel-trace-loading">
                در حالِ خواندنِ ردپا
              </span>
            ) : (
              <FunnelTraceList steps={trace.data?.timeline ?? []}
                               rulesetVersion={trace.data?.ruleset_version ?? null}
                               asOf={trace.data?.as_of ?? null} />
            )}
          </div>

          <div className="flex flex-col gap-0.5">
              <StatusLight
                label="پرتفوی"
                value={basketValue}
                tone={basketTone}
                hint={port?.rationale}
              />
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
          </div>
        ) : null}

        <div className="mt-auto pt-1 text-center text-[8.5px] uppercase tracking-widest text-text-muted">
          Symbol Inspector · FTS
        </div>

      </div>
    </aside>
    </>
  );
}
