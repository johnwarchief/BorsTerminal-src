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
  pulseAllMarketHemat,
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
        {hint ? <span className="truncate text-[10px] text-text-muted">{hint}</span> : null}
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
  const allMarket = pulseAllMarketHemat(pulse);

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
                {fa(hemat.value)}
                <span className="mr-1 text-sm font-bold">همت</span>
              </span>
              <span className="text-sm font-black">{hematText(hemat.state ?? null)}</span>
            </div>
            <div
              data-testid="pulse-market-cap"
              className="flex items-baseline justify-center gap-2 rounded-lg border border-border-c/60 bg-bg-card/40 px-2 py-1"
              title="ارزش کل بازار از macro.value_hemat_all_market (سهام + حق تقدم + ص.سهامی)"
            >
              <span className="text-[10px] font-bold text-text-muted">ارزش کل بازار</span>
              {allMarket != null ? (
                <span className="num text-lg font-black text-text-primary">
                  {fa(allMarket)} <span className="text-[10px] font-bold text-text-muted">همت</span>
                </span>
              ) : (
                MISSING
              )}
            </div>
            <span className="text-center text-[10px] text-text-muted">
              {hemat.state === 'bad' ? 'رکود روز — روند ۳-۴ روزه: بدون داده' : 'روند ۳-۴ روزه: بدون داده'}
            </span>
          </>
        ) : (
          <div data-testid="pulse-market-cap">
            {MISSING}
            {allMarket == null ? <span className="sr-only">ارزش کل بازار بدون داده</span> : null}
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
                <span className="text-[11px] font-bold text-text-secondary">سهام</span>
                {flow.eq_flow_b_toman != null ? (
                  <span className={`num text-xs font-black ${flow.eq_flow_b_toman >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                    {flow.eq_flow_b_toman >= 0 ? '▲' : '▼'} {fa(Math.abs(flow.eq_flow_b_toman))} ب.ت
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
                <span className="text-[11px] font-bold text-text-secondary">درآمد ثابت</span>
                {flow.fixed_flow_b_toman != null ? (
                  flow.fixed_flow_b_toman < 0 ? (
                    <span className="num text-xs font-black text-accent-green">▼ {fa(Math.abs(flow.fixed_flow_b_toman))} ب.ت خروج</span>
                  ) : (
                    <span className="num text-xs font-black text-accent-red">▲ {fa(flow.fixed_flow_b_toman)} ب.ت</span>
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
                <span className="text-[11px] font-bold text-text-secondary">طلا (پنجرهٔ ۱۲:۰۰–۱۲:۳۰)</span>
                {gold != null ? (
                  <span className={`num text-xs font-black ${gold < 0 ? 'text-accent-green' : 'text-accent-yellow'}`}>
                    {gold < 0 ? '▼ خروج ' : '▲ ورود '}
                    {fa(Math.abs(gold))} ب.ت
                  </span>
                ) : (
                  <span className="text-text-muted">تا ۱۲:۳۰</span>
                )}
              </span>
            </div>
            {trio?.active ? (
              <span
                data-testid="pulse-alpha-trio"
                className="mt-0.5 self-start rounded-full border border-accent-yellow/60 bg-accent-yellow/15 px-2 py-0.5 text-[10px] font-black text-accent-yellow"
                title="خروج درآمد ثابت + خروج طلا + ورود سهام"
              >
                ✨ {ALPHA_TRIO_LABEL}
              </span>
            ) : null}
          </>
        )}
      </Section>

      {/* بخش ۳ -- تراز صف‌ها و پهنای باند */}
      <Section testId="pulse-queues" title="تراز صف‌ها و پهنای باند" hint="دماسنج + اردر‌بوک">
        {thermoTotal != null && thermo ? (
          <>
            <div className="flex h-2.5 w-full overflow-hidden rounded-full border border-border-c" title="تعداد مثبت/خنثی/منفی">
              <span className="h-full bg-accent-green" style={{ width: `${((thermo.positive as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-text-muted/30" style={{ width: `${((thermo.zero as number) / thermoTotal) * 100}%` }} />
              <span className="h-full bg-accent-red" style={{ width: `${((thermo.negative as number) / thermoTotal) * 100}%` }} />
            </div>
            <span className="num text-[10px] text-text-secondary">
              +{fa(thermo.positive as number, 0)} / −{fa(thermo.negative as number, 0)} / ص{fa(thermo.zero as number, 0)}
            </span>
            {breadthWarn ? (
              <span data-testid="pulse-breadth-warn" className="text-[10px] font-black text-accent-red" title="بیش از ۸۰٪ معاملات منفی — فرصت/هشدار ورود FTS">
                ⚠ عبور منفی از {fa(rulePct, 0)}٪
              </span>
            ) : null}
          </>
        ) : (
          MISSING
        )}
        {depth ? (
          <>
            <div className="flex items-baseline justify-between gap-2" title="ارزش ۵ خط اول صف‌ها (میلیارد تومان)">
              <span className="num text-xl font-black text-accent-green">
                {depth.buyBt != null ? fmtInt(depth.buyBt) : '—'}
                <span className="mr-1 text-[9px] font-bold text-text-muted">ب.ت خرید</span>
              </span>
              {depth.buyCount != null && depth.sellCount != null ? (
                <span className="num text-[10px] text-text-secondary" title="تعداد نمادهای دارای صف خرید در برابر صف فروش">
                  {fa(depth.buyCount, 0)} / {fa(depth.sellCount, 0)}
                </span>
              ) : null}
              <span className="num text-xl font-black text-accent-red">
                <span className="ml-1 text-[9px] font-bold text-text-muted">فروش ب.ت</span>
                {depth.sellBt != null ? fmtInt(depth.sellBt) : '—'}
              </span>
            </div>
            {sellSharePct != null ? (
              <span className="num text-[10px] text-text-muted" title="سهم ارزش صف‌های فروش از کل ارزش صف‌ها">
                فروش ٪{fa(sellSharePct)} از کل صف‌ها
              </span>
            ) : null}
          </>
        ) : (
          <span className="text-[10px] text-text-muted">تعادل صف‌ها: بدون داده</span>
        )}
      </Section>

      {/* بخش ۴ -- برتری سرانه حقیقی: نوار گرافیکی خرید/فروش */}
      <Section testId="pulse-percapita" title="برتری سرانه حقیقی" hint="خرید ÷ فروش">
        {eq && (eq.pcBuy != null || eq.pcSell != null) ? (
          <>
            <div className="flex items-center gap-3">
              <span className={`text-2xl font-black leading-7 ${powerClass}`} title="≥۱.۵× سبز / <۰.۸× قرمز">
                {eq.power != null ? `${fa(eq.power)}×` : '—'}
              </span>
              <span className="num min-w-0 flex-1 text-[10px] text-text-secondary">
                خرید {eq.pcBuy != null ? fa(eq.pcBuy) : '—'} / فروش {eq.pcSell != null ? fa(eq.pcSell) : '—'} م.ت
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
              <div className="flex items-center justify-between gap-2 text-[10px] text-text-muted">
                <span className="num" title="تعداد نمادهای گروه سهام، حق تقدم و ص.سهامی">
                  نمادها {eq.symbols != null ? fa(eq.symbols, 0) : '—'}
                </span>
                <span className="num" title="نمادهای دارای معامله امروز">
                  معامله‌شده {eq.traded != null ? fa(eq.traded, 0) : '—'}
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
