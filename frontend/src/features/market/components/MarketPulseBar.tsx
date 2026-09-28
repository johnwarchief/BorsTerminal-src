// features/market/components/MarketPulseBar.tsx -- مرکز فرماندهی نبض بازار (گرید ۴بخشی High-Density)
// بخش ۱: سنجه ارزش معاملات خرد | بخش ۲: مثلث جریان پول هوشمند |
// بخش ۳: تراز صف‌ها و پهنای باند | بخش ۴: برتری سرانه حقیقی.
// هر دادهٔ غایب «بدون داده» خاکستری است، نه عدد ساختگی (Circuit Breaker).
import { toFaDigits, fmtInt, fmtPct } from '@shared/lib/fmt';
import { FlashNum } from '@shared/components/FlashNum';
import {
  ALPHA_TRIO_LABEL,
  GOLD_WINDOW_LABEL,
  HEMAT_LABELS,
  computeAlphaTrio,
  powerTone,
  pulseMarketValueHemat,
  pulseTradeValueAllMarketHemat,
  pulseDepth,
  pulseEqAll,
  pulseGoldFlowB,
  pulseGroupRows,
  pulseHemat,
  pulseIndex,
  pulseVerdict,
  type DayVerdict,
  type HematState,
  type MarketPulseData,
} from '../api/useMarketPulse';

const fa = (x: number, digits = 1): string => toFaDigits(x.toFixed(digits));

function Section({
  testId,
  title,
  hint,
  children,
}: {
  testId: string;
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div
      data-testid={testId}
      className="glass-panel flex min-w-0 flex-col justify-start gap-2 rounded-2xl border border-border-c p-3 shadow-xs"
    >
      <div className="flex items-baseline justify-between gap-1.5 border-b border-border-c/40 pb-1.5">
        <h3 className="text-xs font-black text-text-primary">{title}</h3>
        {hint ? <span className="truncate text-3xs font-medium text-text-muted">{hint}</span> : null}
      </div>
      <div className="flex min-w-0 flex-col gap-1.5 text-xs">{children}</div>
    </div>
  );
}

/** یک خانهٔ شاخص: عددِ پایانی + تغییرِ عددی + درصد. هیچ‌کدام بازسازی نمی‌شود. */
function IndexCell({
  label,
  hint,
  last,
  change,
  pct,
}: {
  label: string;
  hint: string;
  last?: number | null;
  change?: number | null;
  pct?: number | null;
}) {
  const up = typeof pct === 'number' ? pct >= 0 : null;
  const tone = up == null ? 'text-text-secondary' : up ? 'text-accent-green' : 'text-accent-red';
  // جهت فقط وقتی که درصد هست؛ بی‌درصد هیچ فلشی نقاشی نمی‌شود.
  const delta = [
    up == null ? null : up ? '▲' : '▼',
    change != null ? fmtInt(Math.abs(change)) : null,
    typeof pct === 'number' ? fmtPct(pct, 2) : null,
  ].filter(Boolean);
  return (
    <div className="flex min-w-0 shrink-0 flex-col gap-0" title={hint}>
      <span className="text-3xs font-bold text-text-secondary">{label}</span>
      {last == null ? (
        <span className="text-xs">{MISSING}</span>
      ) : (
        <span className="flex flex-wrap items-baseline gap-x-1.5">
          {/* عددِ بزرگِ نبض هم مثلِ ستون‌هایِ تابلو فلاش می‌گیرد: ریتمِ این پنل
              خودش ۳۰ ثانیه است و تا پیش از این عدد بی‌خبر عوض می‌شد («کدام
              عدد همین حالا تاز شد؟» بی‌جواب می‌ماند). */}
          <FlashNum
            value={last}
            className="num text-sm font-black leading-5 text-text-primary"
            render={(v) => (v == null ? '—' : fmtInt(v))}
          />
          {delta.length ? <span className={`num text-3xs font-bold ${tone}`}>{delta.join(' ')}</span> : null}
        </span>
      )}
    </div>
  );
}

const TONE_TEXT = { good: 'text-accent-green', mid: 'text-accent-yellow', bad: 'text-accent-red' } as const;
const TONE_BG = { good: 'bg-accent-green', mid: 'bg-accent-yellow', bad: 'bg-accent-red' } as const;
const MISSING = <span className="text-text-muted">بدون داده</span>;

/** رنگِ حکم؛ «بدون داده» بی‌رنگ است — نه سبزِ پیش‌فرض، نه قرمزِ تنبیهی */
const VERDICT_TONE: Record<'go' | 'watch' | 'wait' | 'avoid' | 'nodata', string> = {
  go: 'border-accent-green/60 bg-accent-green/10',
  watch: 'border-accent-yellow/60 bg-accent-yellow/10',
  wait: 'border-accent-yellow/60 bg-accent-yellow/10',
  avoid: 'border-accent-red/60 bg-accent-red/10',
  nodata: 'border-border-c bg-bg-card/60',
};
const VERDICT_TEXT: Record<'go' | 'watch' | 'wait' | 'avoid' | 'nodata', string> = {
  go: 'text-accent-green',
  watch: 'text-accent-yellow',
  wait: 'text-accent-yellow',
  avoid: 'text-accent-red',
  nodata: 'text-text-secondary',
};
const GATE_TONE: Record<'ok' | 'mid' | 'bad' | 'nodata', string> = {
  ok: 'text-accent-green',
  mid: 'text-accent-yellow',
  bad: 'text-accent-red',
  nodata: 'text-text-muted',
};

/** نشانِ حالتِ هر در — رنگ و رأی از موتور است، اینجا فقط نمادش نقاشی می‌شود. */
const GATE_MARK: Record<'ok' | 'mid' | 'bad' | 'nodata', string> = {
  ok: '✓',
  mid: '−',
  bad: '✕',
  nodata: '؟',
};

/**
 * حکمِ امروز — «آیا امروز برای ورود مناسب است یا نه». پنج شرطِ جزوه (ص۱۳ و ص۱۴)
 * همه از موتور می‌آیند (mstat_engine.day_verdict)؛ این‌جا فقط رنگ از state
 * خوانده می‌شود. رأیِ مالک (#170): شمارهٔ «قدمِ ۱/۲/۳» برداشته شد و شرط‌ها زیرِ
 * هم نوشته می‌شوند، هرکدام با یک جمله که می‌گوید رنگش دقیقاً چه معنی دارد —
 * «ارزش معاملات نوشتی سبزش کردی یعنی چی؟» دیگر نباید سؤال بماند.
 */
function VerdictStrip({ v }: { v: DayVerdict | null }) {
  const kind = v?.verdict ?? 'nodata';
  return (
    <div
      data-testid="pulse-verdict"
      className={`flex min-w-0 flex-1 flex-col justify-center gap-y-1 rounded-2xl border px-3 py-1.5 shadow-xs ${VERDICT_TONE[kind]}`}
    >
      <div className="flex min-w-0 flex-wrap items-baseline gap-x-2.5">
        <span className="text-3xs font-bold text-text-secondary">ورود به بازار</span>
        <span data-testid="pulse-verdict-label" className={`text-lg font-black leading-6 ${VERDICT_TEXT[kind]}`}>
          {v ? v.label : 'بدون داده'}
        </span>
      </div>
      <span data-testid="pulse-verdict-reason" className="text-2xs font-medium text-text-secondary">
        {v ? v.reason : 'هنوز پولِ هوشمند نرسیده تا حکمی باشد'}
      </span>
      <ul className="flex min-w-0 flex-col gap-y-1 border-t border-border-c/40 pt-1">
        {(v?.gates ?? []).map((g) => (
          <li
            key={g.key}
            data-testid={`pulse-verdict-gate-${g.key}`}
            title={`${g.label_state}${g.detail ? ` — ${g.detail}` : ''}\n${g.rule ?? ''}`}
            className="flex min-w-0 flex-wrap items-baseline gap-x-1.5"
          >
            <span
              aria-hidden
              data-testid={`pulse-verdict-mark-${g.key}`}
              className={`shrink-0 text-2xs font-black ${GATE_TONE[g.state]}`}
            >
              {GATE_MARK[g.state]}
            </span>
            <span className="text-2xs font-bold text-text-primary">{g.label}</span>
            <span className={`text-2xs font-black ${GATE_TONE[g.state]}`}>{g.label_state}</span>
            {g.detail ? <span className="num min-w-0 text-2xs text-text-secondary">{g.detail}</span> : null}
            {g.why ? (
              <span data-testid={`pulse-verdict-why-${g.key}`} className="min-w-0 text-3xs leading-snug text-text-muted">
                — {g.why}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** آستانه هشدار پهنای باند: عبور منفی‌ها از قاعده ۸۰٪ */
export const WATCH_ENTRY_PCT = 80;

function hematText(state: HematState | null): string {
  // برچسب‌ها در لایۀِ داده‌اند (HEMAT_LABELS)؛ اینجا فقط خوانده می‌شوند.
  return state ? HEMAT_LABELS[state] : '';
}

/** رنگِ دماسنج: «nodata» داوری ندارد، پس بی‌رنگ (همان زردِ خنثیِ نبودِ عدد) */
function hematTone(state: HematState | null): 'good' | 'mid' | 'bad' {
  return state === 'good' || state === 'mid' || state === 'bad' ? state : 'mid';
}

export function MarketPulseBar({ pulse, isLoading = false }: { pulse: MarketPulseData | null; isLoading?: boolean }) {
  const hemat = pulseHemat(pulse);
  const smart = pulse?.smartMoney ?? null;
  const flow = smart?.flow ?? null;
  const watch = smart?.watch_entry ?? null;
  const thermo = pulse?.thermometer ?? null;
  const depth = pulseDepth(pulse);
  const eq = pulseEqAll(pulse);
  // چهار گروهِ دارایی که جدول خلاصه می‌فرستد — برای ردیف‌های مقایسهٔ قدرت
  const groups = pulseGroupRows(pulse, ['stock_right', 'eq_fund', 'fixed_fund', 'gold_fund']);
  const gold = pulseGoldFlowB(pulse);
  const trio = computeAlphaTrio(pulse);
  const allMarket = pulseTradeValueAllMarketHemat(pulse);
  const ix = pulseIndex(pulse);
  const verdict = pulseVerdict(pulse);
  const marketValue = pulseMarketValueHemat(pulse);
  // آستانه‌هایِ همین دماسنج از payload خوانده می‌شوند؛ عددِ دستی در لایهٔ نمایش ممنوع.
  const hematGood = pulse?.smartMoney?.macro?.good_min ?? null;
  const hematBad = pulse?.smartMoney?.macro?.bad_max ?? null;

  const thermoTotal =
    thermo != null &&
    [thermo.positive, thermo.negative, thermo.zero].every((v) => typeof v === 'number') &&
    (thermo.positive as number) + (thermo.negative as number) + (thermo.zero as number) > 0
      ? ((thermo.positive as number) + (thermo.negative as number) + (thermo.zero as number))
      : null;
  const rulePct = typeof thermo?.entry_rule_pct === 'number' ? thermo.entry_rule_pct : WATCH_ENTRY_PCT;
  // جزوه ص۱۳: «۸۰٪ منفی یعنی بازار هنوز فرصت‌های ورود دارد» — این فرصت است،
  // نه هشدار. داورِ خودش موتور است (watch_entry.active)؛ نمایش دوباره عدد را
  // با آستانه مقایسه نمی‌کند.
  const entryOpportunity = watch?.active === true;

  const sellSharePct =
    depth && depth.buyBt != null && depth.sellBt != null && depth.buyBt + depth.sellBt > 0
      ? (depth.sellBt / (depth.buyBt + depth.sellBt)) * 100
      : null;

  const eqTone = powerTone(eq?.power) ?? 'mid';
  const powerClass = TONE_TEXT[eqTone];
  const powerBarClass = TONE_BG[eqTone];

  return (
    <div
      dir="rtl"
      className="grid w-full max-w-none grid-cols-1 items-stretch gap-2.5 sm:grid-cols-2 xl:grid-cols-4"
      aria-label="مرکز فرماندهی نبض بازار"
      data-testid="market-pulse-bar"
    >
      {isLoading && !pulse ? <span className="text-xs text-text-secondary">در حال دریافت نبض بازار...</span> : null}

      {/* نوارِ شاخص + حکمِ امروز — دو شاخصِ جمع‌وجور روی هم در ستونِ راستِ
          RTL، و حکمِ بازار کنارِ آن‌ها. عددِ شاخص خامِ TSETMC است (سازندهٔ
          عدد: save_market_index در سینک)؛ داوری هم فقط موتور می‌کند. */}
      <div className="col-span-full flex flex-wrap items-stretch gap-2.5">
        <div
          data-testid="pulse-index"
          className="flex w-44 shrink-0 flex-col justify-center gap-1.5 rounded-2xl border border-border-c bg-bg-card/60 px-3 py-1.5 shadow-xs"
        >
          <IndexCell
            label="شاخص کل"
            hint="میانگین وزنِ ارزش بازاری"
            last={ix?.last}
            change={ix?.change}
            pct={ix?.pct}
          />
          <IndexCell
            label="شاخص هموزن"
            hint="هر نماد یک وزن — نبضِ واقعیِ بازار"
            last={ix?.ewLast}
            change={ix?.ewChange}
            pct={ix?.ewPct}
          />
        </div>

        {/* حکمِ امروز — «آیا امروز برای ورود مناسب است؟». همان سه قدمِ جزوه +
            تداوم و پنجرهٔ ساعت. تنها داوری‌کننده موتور است. */}
        <VerdictStrip v={verdict} />
      </div>

      {/* بخش ۱ -- ارزش معاملات خرد (سهام، حق تقدم و ص.سهامی) */}
      <Section
        testId="pulse-hemat"
        title="ارزش معاملات خرد"
        hint="سهام، حق تقدم و ص.سهامی"
      >
        {hemat && hemat.value != null ? (
          <>
            <div className="flex items-baseline justify-center gap-2 py-0.5">
              <span className={`text-3xl font-black leading-8 ${TONE_TEXT[hematTone(hemat.state)]}`}>
                <span className="num">{fa(hemat.value)}</span>
                <span className="ms-1 text-sm font-bold">همت</span>
              </span>
              <span className="text-sm font-black">{hematText(hemat.state ?? null)}</span>
            </div>
            <div
              data-testid="pulse-market-cap"
              className="flex items-baseline justify-between rounded-lg border border-border-c/70 bg-bg-card/60 px-2.5 py-1 text-2xs"
              title="همان «ارزش بازار» صفحهٔ TSETMC — مبنای «سهم از کل بازار» در شاخص ۵"
            >
              <span className="font-bold text-text-secondary">ارزش کل بازار</span>
              {marketValue != null ? (
                <span className="num text-sm font-black text-text-primary">
                  {fa(marketValue)} <span className="text-3xs font-bold text-text-muted">همت</span>
                </span>
              ) : (
                MISSING
              )}
            </div>
            <div
              data-testid="pulse-trade-value"
              className="flex items-baseline justify-between rounded-lg border border-border-c/40 bg-bg-card/30 px-2.5 py-0.5 text-2xs"
              title="گردشِ امروزِ تمامِ تابلو (سهام + حق تقدم + ص.سهامی + صندوق‌ها) — این ارزشِ بازار نیست"
            >
              <span className="font-bold text-text-secondary">گردش امروزِ کل بازار</span>
              {allMarket != null ? (
                <span className="num text-xs font-black text-text-primary">
                  {fa(allMarket)} <span className="text-3xs font-bold text-text-muted">همت</span>
                </span>
              ) : (
                MISSING
              )}
            </div>
            {/* آستانه‌هایِ واقعیِ همین دماسنج (از payload) — پیش‌تر این خط
                «روند ۳-۴ روزه: بدون داده» نوشته می‌شد و در هر دو شاخه یکی
                بود: ادّعایی که هیچ‌وقت راست نمی‌شد. */}
            {hematGood != null || hematBad != null ? (
              <span className="text-center text-3xs font-medium text-text-muted">
                <span>مساعد از </span>
                <span className="num font-bold text-accent-green">{hematGood != null ? fa(hematGood) : '—'}</span>
                <span> همت · رکود زیر </span>
                <span className="num font-bold text-accent-red">{hematBad != null ? fa(hematBad) : '—'}</span>
                <span> همت</span>
              </span>
            ) : null}
          </>
        ) : (
          <div data-testid="pulse-market-cap">
            {MISSING}
            {marketValue == null ? <span className="sr-only">ارزش کل بازار بدون داده</span> : null}
          </div>
        )}
      </Section>

      {/* بخش ۲ -- جریان پول حقیقی سه بازارِ دارایی */}
      <Section
        testId="pulse-smart"
        title="جریان پول هوشمند"
        hint="سهام / درآمد ثابت / طلا"
      >
        {!flow ? (
          MISSING
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <span
                title="جریان پول حقیقی سهام و صندوق‌های سهامی (میلیارد تومان)"
                className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 ${
                  flow.eq_flow_b_toman != null && flow.eq_flow_b_toman >= 0
                    ? 'border-emerald-300/80 bg-emerald-50 text-emerald-950 dark:border-accent-green/40 dark:bg-accent-green/10 dark:text-accent-green'
                    : 'border-rose-300/80 bg-rose-50 text-rose-950 dark:border-accent-red/40 dark:bg-accent-red/10 dark:text-accent-red'
                }`}
              >
                <span className="text-2xs font-bold text-text-secondary">سهام</span>
                {flow.eq_flow_b_toman != null ? (
                  <span className={`text-xs font-black inline-flex items-center gap-1 ${flow.eq_flow_b_toman >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    <span>{flow.eq_flow_b_toman >= 0 ? '▲' : '▼'}</span>
                    <span className="num">{fa(Math.abs(flow.eq_flow_b_toman))}</span>
                    <span className="text-3xs font-bold text-text-muted">ب.ت</span>
                  </span>
                ) : (
                  MISSING
                )}
              </span>
              <span
                title="خروج از درآمد ثابت = عدد منفی؛ نشانهٔ ورود نوسانی، پس سبز بولد"
                className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 ${
                  flow.fixed_flow_b_toman != null && flow.fixed_flow_b_toman < 0
                    ? 'border-emerald-300/80 bg-emerald-50 text-emerald-950 dark:border-accent-green/40 dark:bg-accent-green/10 dark:text-accent-green'
                    : 'border-rose-300/80 bg-rose-50 text-rose-950 dark:border-accent-red/40 dark:bg-accent-red/10 dark:text-accent-red'
                }`}
              >
                <span className="text-2xs font-bold text-text-secondary">درآمد ثابت</span>
                {flow.fixed_flow_b_toman != null ? (
                  flow.fixed_flow_b_toman < 0 ? (
                    <span className="text-xs font-black text-accent-green">▼ {fa(Math.abs(flow.fixed_flow_b_toman))} ب.ت خروج</span>
                  ) : (
                    <span className="text-xs font-black text-accent-red">▲ {fa(flow.fixed_flow_b_toman)} ب.ت</span>
                  )
                ) : (
                  MISSING
                )}
              </span>
              <span
                title={`${GOLD_WINDOW_LABEL} -- داده طلا از ردیف gold_fund خلاصه بازار`}
                className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 ${
                  gold == null
                    ? 'border-border-c bg-bg-card/60 text-text-secondary'
                    : gold < 0
                      ? 'border-emerald-300/80 bg-emerald-50 text-emerald-950 dark:border-accent-green/40 dark:bg-accent-green/10 dark:text-accent-green'
                      : 'border-amber-300/80 bg-amber-50 text-amber-950 dark:border-accent-yellow/40 dark:bg-accent-yellow/10 dark:text-accent-yellow'
                }`}
              >
                <span className="text-2xs font-bold text-text-secondary">طلا (پنجرهٔ ۱۲:۰۰–۱۲:۳۰)</span>
                {gold != null ? (
                  <span className={`text-xs font-black inline-flex items-center gap-1 ${gold < 0 ? 'text-accent-green' : 'text-accent-yellow'}`}>
                    <span>{gold < 0 ? '▼ خروج' : '▲ ورود'}</span>
                    <span className="num">{fa(Math.abs(gold))}</span>
                    <span className="text-3xs font-bold text-text-muted">ب.ت</span>
                  </span>
                ) : (
                  <span className="text-text-muted text-2xs">تا ۱۲:۳۰</span>
                )}
              </span>
            </div>
            {trio?.active ? (
              <span
                data-testid="pulse-alpha-trio"
                className="self-start rounded-full border border-amber-400/80 bg-amber-100 text-amber-950 px-2 py-0.5 text-3xs font-black dark:border-accent-yellow/60 dark:bg-accent-yellow/15 dark:text-accent-yellow"
                title="خروج درآمد ثابت + خروج طلا + ورود سهام"
              >
                ✨ {ALPHA_TRIO_LABEL}
              </span>
            ) : null}
            {/* سه شرطِ همان چیپ، تک‌تک — فضایِ خالیِ پایینِ کارت را «وضعیتِ
                واقعیِ هر شرط» پر می‌کند، نه متنِ تزئینی. بولین‌ها از لایهٔ
                داده (computeAlphaTrio) خوانده می‌شوند و اینجا فقط نمایش‌اند. */}
            {trio ? (
              <div
                data-testid="pulse-alpha-conditions"
                className="flex flex-wrap items-center gap-x-2 gap-y-0.5 border-t border-border-c/40 pt-1 text-3xs font-bold text-text-muted"
                title="هر تیک یکی از سه شرطِ ایده‌آلِ ورود نوسانی است"
              >
                {[
                  { t: 'ورود سهام', v: trio.eqInflow },
                  { t: 'خروج درآمد ثابت', v: trio.fixedOutflow },
                  { t: 'خروج طلا', v: trio.goldOutflow },
                ].map((c) => (
                  <span key={c.t} className="inline-flex items-center gap-0.5">
                    <span className={c.v == null ? 'text-text-muted' : c.v ? 'text-accent-green' : 'text-accent-red'}>
                      {c.v == null ? '؟' : c.v ? '✓' : '✗'}
                    </span>
                    <span>{c.t}</span>
                  </span>
                ))}
              </div>
            ) : null}
          </>
        )}
      </Section>

      {/* بخش ۳ -- ارزش سفارش های خرید و فروش سهام، حق تقدم و ص.سهامی */}
      <Section
        testId="pulse-queues"
        title="ارزش سفارش های خرید و فروش"
        hint="سهام، حق تقدم و ص.سهامی"
      >
        {thermoTotal != null && thermo ? (
          <>
            <div className="flex h-3 w-full overflow-hidden rounded-full border border-border-c/80" title="تعداد مثبت/خنثی/منفی">
              <span className="h-full bg-accent-green" style={{ width: `${((thermo.positive as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-slate-400/40" style={{ width: `${((thermo.zero as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-accent-red" style={{ width: `${((thermo.negative as number) / thermoTotal) * 100}%` }} />
            </div>
            <div className="flex items-center justify-between gap-1 text-[11px] font-bold">
              <span className="inline-flex items-center gap-1 text-accent-green" title="نمادهای مثبت">
                <span className="text-[10px]">▲</span>
                <span className="num">{fa(thermo.positive as number, 0)}</span>
                <span className="text-3xs font-medium text-text-muted">مثبت</span>
              </span>
              <span className="inline-flex items-center gap-1 text-text-secondary" title="نمادهای بدون تغییر">
                <span className="text-[10px]">■</span>
                <span className="num">{fa(thermo.zero as number, 0)}</span>
                <span className="text-3xs font-medium text-text-muted">خنثی</span>
              </span>
              <span className="inline-flex items-center gap-1 text-accent-red" title="نمادهای منفی">
                <span className="text-[10px]">▼</span>
                <span className="num">{fa(thermo.negative as number, 0)}</span>
                <span className="text-3xs font-medium text-text-muted">منفی</span>
              </span>
            </div>
            {entryOpportunity ? (
              <span
                data-testid="pulse-breadth-warn"
                className="text-2xs font-black text-accent-green"
                title="عبور منفی‌ها از آستانهٔ ۸۰٪ — طبقِ جزوه «بازار هنوز فرصتِ ورود دارد»، نه هشدار"
              >
                🟢 فرصتِ ورود — منفی‌ها از <span className="num">{fa(rulePct, 0)}</span>٪ گذشته
              </span>
            ) : null}
          </>
        ) : (
          MISSING
        )}
        {depth ? (
          <>
            <div className="grid grid-cols-2 gap-1.5 pt-0.5" title="ارزش ۵ خط اول صف‌ها (میلیارد تومان)">
              <div className="flex flex-col rounded-lg border border-emerald-300/80 bg-emerald-50/70 p-1.5 text-center dark:border-accent-green/30 dark:bg-accent-green/10">
                <span className="text-3xs font-bold text-text-secondary">صف خرید</span>
                <span className="text-base font-black text-accent-green inline-flex items-baseline justify-center gap-1">
                  <span className="num">{depth.buyBt != null ? fmtInt(depth.buyBt) : '—'}</span>
                  <span className="text-3xs font-normal text-text-muted">ب.ت</span>
                </span>
                {depth.buyCount != null && (
                  <span className="text-3xs text-text-muted mt-0.5 font-bold">
                    <span className="num text-accent-green">{fa(depth.buyCount, 0)}</span> نماد
                  </span>
                )}
              </div>

              <div className="flex flex-col rounded-lg border border-rose-300/80 bg-rose-50/70 p-1.5 text-center dark:border-accent-red/30 dark:bg-accent-red/10">
                <span className="text-3xs font-bold text-text-secondary">صف فروش</span>
                <span className="text-base font-black text-accent-red inline-flex items-baseline justify-center gap-1">
                  <span className="num">{depth.sellBt != null ? fmtInt(depth.sellBt) : '—'}</span>
                  <span className="text-3xs font-normal text-text-muted">ب.ت</span>
                </span>
                {depth.sellCount != null && (
                  <span className="text-3xs text-text-muted mt-0.5 font-bold">
                    <span className="num text-accent-red">{fa(depth.sellCount, 0)}</span> نماد
                  </span>
                )}
              </div>
            </div>
            {sellSharePct != null ? (
              <span className="text-3xs text-text-muted inline-flex items-center gap-1 justify-center pt-0.5 font-medium" title="سهم ارزش صف‌های فروش از کل ارزش صف‌ها">
                <span>سهم فروش:</span>
                <span className="inline-flex items-center gap-0.5 font-bold text-accent-red">
                  <span className="num">{fa(sellSharePct)}</span>
                  <span>٪</span>
                </span>
                <span>از کل صف‌ها</span>
              </span>
            ) : null}
          </>
        ) : (
          <span className="text-3xs text-text-muted">تعادل صف‌ها: بدون داده</span>
        )}
      </Section>

      {/* بخش ۴ -- درصد و سرانه خرید و فروش حقیقی */}
      <Section
        testId="pulse-percapita"
        title="درصد و سرانه خرید و فروش حقیقی"
        hint="خرید ÷ فروش"
      >
        {eq && (eq.pcBuy != null || eq.pcSell != null) ? (
          <>
            <div className="flex items-center justify-between gap-2">
              <span className={`num text-2xl font-black leading-7 ${powerClass}`} title="≥۱.۵× سبز / <۰.۸× قرمز">
                {eq.power != null ? `${fa(eq.power)}×` : '—'}
              </span>
              <span className="min-w-0 flex-1 text-2xs text-text-secondary inline-flex items-center justify-end gap-1">
                <span>خرید</span>
                <span className="num font-bold text-text-primary">{eq.pcBuy != null ? fa(eq.pcBuy) : '—'}</span>
                <span>/ فروش</span>
                <span className="num font-bold text-text-primary">{eq.pcSell != null ? fa(eq.pcSell) : '—'}</span>
                <span className="text-3xs font-bold text-text-muted">م.ت</span>
              </span>
            </div>
            {eq.pcBuy != null && eq.pcSell != null && eq.pcBuy + eq.pcSell > 0 ? (
              <div
                className="flex h-3 w-full overflow-hidden rounded-full border border-border-c/80"
                title={`سهم سرانه خرید ٪${fa((eq.pcBuy / (eq.pcBuy + eq.pcSell)) * 100)}`}
              >
                <span className={`h-full ${powerBarClass}`} style={{ width: `${(eq.pcBuy / (eq.pcBuy + eq.pcSell)) * 100}%` }} />
                <span className="h-full flex-1 bg-accent-red" />
              </div>
            ) : null}
            {eq.symbols != null || eq.traded != null ? (
              <div className="flex items-center justify-between gap-2 text-3xs text-text-muted font-medium pt-1">
                <span className="inline-flex items-center gap-1" title="تعداد نمادهای گروه سهام، حق تقدم و ص.سهامی">
                  <span>کل نمادها:</span>
                  <span className="num font-bold text-text-primary">{eq.symbols != null ? fa(eq.symbols, 0) : '—'}</span>
                </span>
                <span className="inline-flex items-center gap-1" title="نمادهای دارای معامله امروز">
                  <span>معامله‌شده:</span>
                  <span className="num font-bold text-text-primary">{eq.traded != null ? fa(eq.traded, 0) : '—'}</span>
                </span>
              </div>
            ) : null}
            {/* قدرت خریدار به تفکیکِ گروه — همان ردیف‌هایی که جدول خلاصه
                می‌فرستد؛ پیش‌تر این پایینِ کارت خالی می‌ماند. */}
            {groups.length ? (
              <div data-testid="pulse-groups" className="mt-1 flex flex-col gap-0.5 border-t border-border-c/40 pt-1">
                {groups.map((g) => (
                  <span
                    key={g.key}
                    className="flex items-baseline justify-between gap-2 text-3xs"
                    title={`${g.label} — سرانه خرید ${g.pcBuy != null ? fa(g.pcBuy) : '—'} / فروش ${g.pcSell != null ? fa(g.pcSell) : '—'} م.ت`}
                  >
                    <span className="truncate text-text-muted">{g.label}</span>
                    <span className={`num shrink-0 font-black ${powerTone(g.power) ? TONE_TEXT[powerTone(g.power) as 'good' | 'mid' | 'bad'] : 'text-text-muted'}`}>
                      {g.power != null ? `${fa(g.power)}×` : '—'}
                    </span>
                  </span>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          MISSING
        )}
      </Section>
    </div>
  );
}
