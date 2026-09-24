// features/market/components/MarketPulseBar.tsx -- مرکز فرماندهی نبض بازار (گرید ۴بخشی High-Density)
// بخش ۱: سنجه ارزش معاملات خرد | بخش ۲: مثلث جریان پول هوشمند |
// بخش ۳: تراز صف‌ها و پهنای باند | بخش ۴: برتری سرانه حقیقی.
// هر دادهٔ غایب «بدون داده» خاکستری است، نه عدد ساختگی (Circuit Breaker).
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import {
  ALPHA_TRIO_LABEL,
  GOLD_WINDOW_LABEL,
  computeAlphaTrio,
  powerTone,
  pulseMarketValueHemat,
  pulseTradeValueAllMarketHemat,
  pulseDepth,
  pulseEqAll,
  pulseGoldFlowB,
  pulseHemat,
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
      className="glass-panel flex min-w-0 flex-col gap-2 rounded-xl border border-border-c p-3"
    >
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-bold text-text-muted">{title}</h3>
        {hint ? <span className="truncate text-2xs text-text-muted">{hint}</span> : null}
      </div>
      <div className="flex min-w-0 flex-col gap-1.5 text-xs">{children}</div>
    </div>
  );
}

const TONE_TEXT = { good: 'text-accent-green', mid: 'text-accent-yellow', bad: 'text-accent-red' } as const;
const TONE_BG = { good: 'bg-accent-green', mid: 'bg-accent-yellow', bad: 'bg-accent-red' } as const;
const MISSING = <span className="text-text-muted">بدون داده</span>;

/** آستانه هشدار پهنای باند: عبور منفی‌ها از قاعده ۸۰٪ */
export const WATCH_ENTRY_PCT = 80;

function hematText(state: HematState | null): string {
  if (state === 'good') return 'مساعد';
  if (state === 'mid') return 'متوسط';
  if (state === 'bad') return 'نامساعد';
  return '';
}

export function MarketPulseBar({ pulse, isLoading = false }: { pulse: MarketPulseData | null; isLoading?: boolean }) {
  const hemat = pulseHemat(pulse);
  const smart = pulse?.smartMoney ?? null;
  const flow = smart?.flow ?? null;
  const watch = smart?.watch_entry ?? null;
  const thermo = pulse?.thermometer ?? null;
  const depth = pulseDepth(pulse);
  const eq = pulseEqAll(pulse);
  const gold = pulseGoldFlowB(pulse);
  const trio = computeAlphaTrio(pulse);
  const allMarket = pulseTradeValueAllMarketHemat(pulse);
  const marketValue = pulseMarketValueHemat(pulse);

  const thermoTotal =
    thermo != null &&
    [thermo.positive, thermo.negative, thermo.zero].every((v) => typeof v === 'number') &&
    (thermo.positive as number) + (thermo.negative as number) + (thermo.zero as number) > 0
      ? ((thermo.positive as number) + (thermo.negative as number) + (thermo.zero as number))
      : null;
  const negativePct = typeof thermo?.negative_pct === 'number' ? thermo.negative_pct : null;
  const rulePct = typeof thermo?.entry_rule_pct === 'number' ? thermo.entry_rule_pct : WATCH_ENTRY_PCT;
  const breadthWarn = negativePct != null ? negativePct >= rulePct : watch?.active === true;

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
      className="grid w-full max-w-none grid-cols-1 items-stretch gap-3 md:grid-cols-2 xl:grid-cols-4"
      aria-label="مرکز فرماندهی نبض بازار"
      data-testid="market-pulse-bar"
    >
      {isLoading && !pulse ? <span className="text-xs text-text-secondary">در حال دریافت نبض بازار...</span> : null}

      {/* بخش ۱ -- ارزش معاملات خرد + ارزش کل بازار (macro همان fetch پول هوشمند) */}
      <Section
        testId="pulse-hemat"
        title="ارزش معاملات خرد"
        hint="سهام + حق تقدم + ص.سهامی"
      >
        {hemat && hemat.value != null ? (
          <>
            <div className="flex items-baseline justify-center gap-2">
              <span className={`text-3xl font-black leading-8 ${TONE_TEXT[hemat.state ?? 'mid']}`}>
                <span className="num">{fa(hemat.value)}</span>
                <span className="ms-1 text-sm font-bold">همت</span>
              </span>
              <span className="text-sm font-black">{hematText(hemat.state ?? null)}</span>
            </div>
            <div
              data-testid="pulse-market-cap"
              className="flex items-baseline justify-center gap-2 rounded-lg border border-border-c/60 bg-bg-card/40 px-2 py-1"
              title="همان «ارزش بازار» صفحهٔ TSETMC — مبنای «سهم از کل بازار» در شاخص ۵"
            >
              <span className="text-2xs font-bold text-text-muted">ارزش کل بازار</span>
              {marketValue != null ? (
                <span className="num text-lg font-black text-text-primary">
                  {fa(marketValue)} <span className="text-2xs font-bold text-text-muted">همت</span>
                </span>
              ) : (
                MISSING
              )}
            </div>
            <div
              data-testid="pulse-trade-value"
              className="flex items-baseline justify-center gap-2"
              title="گردشِ امروزِ تمامِ تابلو (سهام + حق تقدم + ص.سهامی + صندوق‌ها) — این ارزشِ بازار نیست"
            >
              <span className="text-2xs font-bold text-text-muted">گردش امروزِ کل بازار</span>
              {allMarket != null ? (
                <span className="num text-sm font-black text-text-secondary">
                  {fa(allMarket)} <span className="text-2xs font-bold text-text-muted">همت</span>
                </span>
              ) : (
                MISSING
              )}
            </div>
            <span className="text-center text-2xs text-text-muted">
              {hemat.state === 'bad' ? 'رکود روز — روند ۳-۴ روزه: بدون داده' : 'روند ۳-۴ روزه: بدون داده'}
            </span>
          </>
        ) : (
          <div data-testid="pulse-market-cap">
            {MISSING}
            {marketValue == null ? <span className="sr-only">ارزش کل بازار بدون داده</span> : null}
          </div>
        )}
      </Section>

      {/* بخش ۲ -- مثلث جریان پول هوشمند: سه بردار منظم با تگ سبز/قرمز */}
      <Section testId="pulse-smart" title="جریان پول هوشمند" hint="سهام / درآمد ثابت / طلا">
        {!flow ? (
          MISSING
        ) : (
          <>
            <div className="flex flex-col gap-1.5">
              <span
                title="جریان پول حقیقی سهام و صندوق‌های سهامی (میلیارد تومان)"
                className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 ${
                  flow.eq_flow_b_toman != null && flow.eq_flow_b_toman >= 0
                    ? 'border-accent-green/40 bg-accent-green/5'
                    : 'border-accent-red/40 bg-accent-red/5'
                }`}
              >
                <span className="text-2xs font-bold text-text-secondary">سهام</span>
                {flow.eq_flow_b_toman != null ? (
                  <span className={`text-xs font-black inline-flex items-center gap-1 ${flow.eq_flow_b_toman >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    <span>{flow.eq_flow_b_toman >= 0 ? '▲' : '▼'}</span>
                    <span className="num">{fa(Math.abs(flow.eq_flow_b_toman))}</span>
                    <span className="text-2xs font-bold text-text-muted">ب.ت</span>
                  </span>
                ) : (
                  MISSING
                )}
              </span>
              <span
                title="خروج از درآمد ثابت = عدد منفی؛ نشانهٔ ورود نوسانی، پس سبز بولد"
                className={`flex items-center justify-between gap-2 rounded-lg border px-2.5 py-1 ${
                  flow.fixed_flow_b_toman != null && flow.fixed_flow_b_toman < 0
                    ? 'border-accent-green/40 bg-accent-green/5'
                    : 'border-accent-red/40 bg-accent-red/5'
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
                    ? 'border-border-c bg-bg-card'
                    : gold < 0
                      ? 'border-accent-green/40 bg-accent-green/5'
                      : 'border-accent-yellow/40 bg-accent-yellow/5'
                }`}
              >
                <span className="text-2xs font-bold text-text-secondary">طلا (پنجرهٔ ۱۲:۰۰–۱۲:۳۰)</span>
                {gold != null ? (
                  <span className={`text-xs font-black inline-flex items-center gap-1 ${gold < 0 ? 'text-accent-green' : 'text-accent-yellow'}`}>
                    <span>{gold < 0 ? '▼ خروج' : '▲ ورود'}</span>
                    <span className="num">{fa(Math.abs(gold))}</span>
                    <span className="text-2xs font-bold text-text-muted">ب.ت</span>
                  </span>
                ) : (
                  <span className="text-text-muted">تا ۱۲:۳۰</span>
                )}
              </span>
            </div>
            {trio?.active ? (
              <span
                data-testid="pulse-alpha-trio"
                className="mt-0.5 self-start rounded-full border border-accent-yellow/60 bg-accent-yellow/15 px-2 py-0.5 text-2xs font-black text-accent-yellow"
                title="خروج درآمد ثابت + خروج طلا + ورود سهام"
              >
                ✨ {ALPHA_TRIO_LABEL}
              </span>
            ) : null}
          </>
        )}
      </Section>

      {/* بخش ۳ -- جو بازار و ارزش صف‌ها */}
      <Section testId="pulse-queues" title="جو بازار و ارزش صف‌ها" hint="نسبت مثبت/منفی + ارزش صف‌ها">
        {thermoTotal != null && thermo ? (
          <>
            <div className="flex h-2 w-full overflow-hidden rounded-full border border-border-c/70" title="تعداد مثبت/خنثی/منفی">
              <span className="h-full bg-accent-green" style={{ width: `${((thermo.positive as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-text-muted/30" style={{ width: `${((thermo.zero as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-accent-red" style={{ width: `${((thermo.negative as number) / thermoTotal) * 100}%` }} />
            </div>
            <div className="flex items-center justify-between gap-1 text-[11px] font-bold pt-0.5">
              <span className="inline-flex items-center gap-1 text-accent-green" title="نمادهای مثبت">
                <span className="text-[10px]">▲</span>
                <span className="num">{fa(thermo.positive as number, 0)}</span>
                <span className="text-3xs font-normal text-text-muted">مثبت</span>
              </span>
              <span className="inline-flex items-center gap-1 text-text-secondary" title="نمادهای بدون تغییر">
                <span className="text-[10px]">■</span>
                <span className="num">{fa(thermo.zero as number, 0)}</span>
                <span className="text-3xs font-normal text-text-muted">خنثی</span>
              </span>
              <span className="inline-flex items-center gap-1 text-accent-red" title="نمادهای منفی">
                <span className="text-[10px]">▼</span>
                <span className="num">{fa(thermo.negative as number, 0)}</span>
                <span className="text-3xs font-normal text-text-muted">منفی</span>
              </span>
            </div>
            {breadthWarn ? (
              <span data-testid="pulse-breadth-warn" className="text-2xs font-black text-accent-red" title="بیش از ۸۰٪ معاملات منفی — فرصت/هشدار ورود FTS">
                ⚠ عبور منفی از <span className="num">{fa(rulePct, 0)}</span>٪
              </span>
            ) : null}
          </>
        ) : (
          MISSING
        )}
        {depth ? (
          <>
            <div className="grid grid-cols-2 gap-2 pt-1" title="ارزش ۵ خط اول صف‌ها (میلیارد تومان)">
              <div className="flex flex-col rounded-lg border border-accent-green/30 bg-accent-green/5 p-1.5 text-center">
                <span className="text-3xs font-bold text-text-muted">صف خرید (ارزش)</span>
                <span className="text-base font-black text-accent-green inline-flex items-baseline justify-center gap-1">
                  <span className="num">{depth.buyBt != null ? fmtInt(depth.buyBt) : '—'}</span>
                  <span className="text-3xs font-normal text-text-muted">ب.ت</span>
                </span>
                {depth.buyCount != null && (
                  <span className="text-3xs text-text-muted mt-0.5">
                    <span className="num font-bold text-accent-green">{fa(depth.buyCount, 0)}</span> نماد
                  </span>
                )}
              </div>

              <div className="flex flex-col rounded-lg border border-accent-red/30 bg-accent-red/5 p-1.5 text-center">
                <span className="text-3xs font-bold text-text-muted">صف فروش (ارزش)</span>
                <span className="text-base font-black text-accent-red inline-flex items-baseline justify-center gap-1">
                  <span className="num">{depth.sellBt != null ? fmtInt(depth.sellBt) : '—'}</span>
                  <span className="text-3xs font-normal text-text-muted">ب.ت</span>
                </span>
                {depth.sellCount != null && (
                  <span className="text-3xs text-text-muted mt-0.5">
                    <span className="num font-bold text-accent-red">{fa(depth.sellCount, 0)}</span> نماد
                  </span>
                )}
              </div>
            </div>
            {sellSharePct != null ? (
              <span className="text-2xs text-text-muted inline-flex items-center gap-1 justify-center pt-0.5" title="سهم ارزش صف‌های فروش از کل ارزش صف‌ها">
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
          <span className="text-2xs text-text-muted">تعادل صف‌ها: بدون داده</span>
        )}
      </Section>

      {/* بخش ۴ -- برتری سرانه حقیقی: نوار گرافیکی خرید/فروش */}
      <Section testId="pulse-percapita" title="برتری سرانه حقیقی" hint="خرید ÷ فروش">
        {eq && (eq.pcBuy != null || eq.pcSell != null) ? (
          <>
            <div className="flex items-center gap-3">
              <span className={`num text-2xl font-black leading-7 ${powerClass}`} title="≥۱.۵× سبز / <۰.۸× قرمز">
                {eq.power != null ? `${fa(eq.power)}×` : '—'}
              </span>
              <span className="min-w-0 flex-1 text-2xs text-text-secondary inline-flex items-center gap-1">
                <span>خرید</span>
                <span className="num font-bold text-text-primary">{eq.pcBuy != null ? fa(eq.pcBuy) : '—'}</span>
                <span>/ فروش</span>
                <span className="num font-bold text-text-primary">{eq.pcSell != null ? fa(eq.pcSell) : '—'}</span>
                <span className="text-text-muted">م.ت</span>
              </span>
            </div>
            {eq.pcBuy != null && eq.pcSell != null && eq.pcBuy + eq.pcSell > 0 ? (
              <div
                className="flex h-2.5 w-full overflow-hidden rounded-full border border-border-c"
                title={`سهم سرانه خرید ٪${fa((eq.pcBuy / (eq.pcBuy + eq.pcSell)) * 100)}`}
              >
                <span className={`h-full ${powerBarClass}`} style={{ width: `${(eq.pcBuy / (eq.pcBuy + eq.pcSell)) * 100}%` }} />
                <span className="h-full flex-1 bg-accent-red/70" />
              </div>
            ) : null}
            {eq.symbols != null || eq.traded != null ? (
              <div className="flex items-center justify-between gap-2 text-2xs text-text-muted">
                <span className="inline-flex items-center gap-1" title="تعداد نمادهای گروه سهام، حق تقدم و ص.سهامی">
                  <span>نمادها</span>
                  <span className="num font-bold text-text-secondary">{eq.symbols != null ? fa(eq.symbols, 0) : '—'}</span>
                </span>
                <span className="inline-flex items-center gap-1" title="نمادهای دارای معامله امروز">
                  <span>معامله‌شده</span>
                  <span className="num font-bold text-text-secondary">{eq.traded != null ? fa(eq.traded, 0) : '—'}</span>
                </span>
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
