// features/technical/components/MarketOverview.tsx -- نمای «کل بورس» وقتی نمادی انتخاب نشده
// ارتقا یافته (فاز ۳): چارت کندل واقعی شاخص کل (TEDPIX) از /api/index/tedpix؛ اگر شاخص
// نرسد، fallback به سری کلان /api/mstat/timeline (چارت خطی). همه از لایهٔ دادهٔ واحد
// (useWholeMarket) می‌آید تا جایگزینی/افزودن منبع بدون refactor باشد. غایب ⇒ «بدون داده».
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { useUiStore } from '@shared/stores/uiStore';
import { MacroLineChart } from './MacroLineChart';
import { KLineChartWrapper } from './KLineChartWrapper';
import { paletteFor } from '../lib/chartPalette';
import { macroEqRow, macroHemat, useMarketMacro } from '../api/useMarketMacro';
import { useWholeMarket } from '../api/useMarketSeries';
import { firstScreenerSymbol, useFtsScreener } from '../api/useScreener';

function fmt(x: number | null | undefined, digits = 1): string {
  return x == null || !Number.isFinite(x) ? '—' : toFaDigits(x.toFixed(digits));
}

function fmtCount(x: number | null | undefined): string {
  return x == null || !Number.isFinite(x) ? '—' : toFaDigits(Math.round(x));
}

const MISSING = <span className="text-text-muted">بدون داده</span>;

function Stat({ label, hint, tone, children }: { label: string; hint?: string; tone?: 'green' | 'red' | 'yellow'; children: React.ReactNode }) {
  const color = tone === 'green' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : tone === 'yellow' ? 'text-accent-yellow' : 'text-text-primary';
  return (
    <div className="flex min-w-0 flex-col gap-0.5 rounded-xl border border-border-c bg-bg-card/40 p-2.5" title={hint}>
      <span className="truncate text-[10px] font-bold text-text-muted">{label}</span>
      <span className={`num text-base font-black leading-6 ${color}`}>{children}</span>
      {hint ? <span className="truncate text-[9px] text-text-muted">{hint}</span> : null}
    </div>
  );
}

export function MarketOverview({ onSelect }: { onSelect?: (s: string) => void }) {
  const { data: macro, isLoading } = useMarketMacro();
  const { data: market } = useWholeMarket();
  const { data: screener } = useFtsScreener();
  const theme = useUiStore((s) => s.theme);

  const thermo = macro?.thermometer ?? null;
  const depth = macro?.depth ?? null;
  const sm = macro?.smartMoney ?? null;
  const eq = macroEqRow(macro?.summary);
  const hemat = macroHemat(sm);
  const allMarket = sm?.macro?.value_hemat_all_market ?? null;
  const flowEq = sm?.flow?.eq_flow_b_toman ?? null;
  const flowFixed = sm?.flow?.fixed_flow_b_toman ?? null;

  const fallbackSymbol = firstScreenerSymbol(screener?.data ?? []);
  const day = macro?.summary?.asof?.d_even ?? null;
  const negPct = thermo?.negative_pct ?? null;
  const breadthWarn = typeof negPct === 'number' && thermo?.entry_rule_pct != null ? negPct >= thermo.entry_rule_pct : false;

  return (
    <div className="flex flex-col gap-3" data-testid="market-overview">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-black text-text-primary">کل بورس</h2>
        {day != null ? <Badge tone="blue">روز {toFaDigits(String(day))}</Badge> : null}
        {market?.source ? <Badge tone="gray">{market.source}</Badge> : null}
        <Badge tone="gray">نمای کلان بازار</Badge>
        {isLoading ? <span className="text-xs text-text-secondary">در حال دریافت نبض بازار...</span> : null}
      </div>

      <p className="text-[11px] leading-5 text-text-muted">
        چارت کل بازار از سری واقعی شاخص کل (<span className="num">TEDPIX</span>) می‌آید؛ اگر شاخص در دسترس نباشد،
        به سری کلان <span className="num">/api/mstat/timeline</span> برمی‌گردد. برای انتخاب نماد از سایدبار «دیده‌بان» استفاده کن.
      </p>

      {fallbackSymbol && onSelect ? (
        <button
          type="button"
          onClick={() => onSelect(fallbackSymbol)}
          data-testid="market-fallback-symbol"
          className="self-start rounded-full border border-border-accent bg-accent-blue/10 px-3 py-1 text-xs font-bold text-accent-blue transition-colors hover:bg-accent-blue/20"
        >
          تحلیل نماد پیشنهادی (اولین screener): {fallbackSymbol}
        </button>
      ) : null}

      <div className="glass-panel rounded-2xl p-3">
        {market?.kind === 'candles' ? (
          <>
            <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-[11px] font-bold text-text-secondary">{market.title}</span>
              <span className="num text-[10px] text-text-muted">{toFaDigits(market.candles.length)} کندل روزانه · بدون حجم</span>
            </div>
            <KLineChartWrapper data={market.candles} palette={paletteFor(theme)} height={380} />
          </>
        ) : market?.kind === 'macro' ? (
          <>
            <MacroLineChart
              values={market.points.map((p) => p.value)}
              labels={market.points.map((p) => p.label)}
              title={market.title}
              unit={market.unit}
              testId="macro-val"
            />
            {market.note ? (
              <span className="mt-1 block text-[10px] text-text-muted" data-testid="macro-note">
                {market.note}
              </span>
            ) : null}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-border-c bg-bg-secondary p-6 text-center" data-testid="market-chart-empty">
            <span className="text-xs font-bold text-text-secondary">سری کل بازار در دسترس نیست</span>
            <span className="text-[11px] text-text-muted">نه شاخص کل برگشت و نه سری کلان؛ بدون دادهٔ ساختگی.</span>
          </div>
        )}
      </div>

      <div className="grid grid-cols-2 gap-2 md:grid-cols-3 xl:grid-cols-4" data-testid="macro-stats">
        <Stat label="ارزش معاملات خرد" hint="سهام + حق تقدم + ص.سهامی (همت)" tone={hemat.state === 'good' ? 'green' : hemat.state === 'bad' ? 'red' : undefined}>
          {hemat.value == null ? MISSING : <>{fmt(hemat.value)} <span className="text-[10px] font-bold text-text-muted">همت</span></>}
        </Stat>
        <Stat label="ارزش کل بازار" hint="macro.value_hemat_all_market (همت)">
          {allMarket == null ? MISSING : <>{fmt(allMarket)} <span className="text-[10px] font-bold text-text-muted">همت</span></>}
        </Stat>
        <Stat
          label="پهنای بازار"
          hint={`مثبت ${fmtCount(thermo?.positive)} / منفی ${fmtCount(thermo?.negative)}`}
          tone={breadthWarn ? 'red' : undefined}
        >
          {negPct == null ? MISSING : <>{fmt(negPct)}<span className="text-[10px] font-bold text-text-muted">٪ منفی</span></>}
        </Stat>
        <Stat
          label="تعادل صف‌ها"
          hint="نسبت ارزش صف خرید به فروش"
          tone={depth?.depth_available !== true || depth?.ratio == null ? undefined : depth.ratio >= 1 ? 'green' : 'red'}
        >
          {depth?.depth_available !== true || depth.ratio == null ? MISSING : <>{fmt(depth.ratio)}<span className="text-[10px] font-bold text-text-muted">×</span></>}
        </Stat>
        <Stat
          label="جریان پول حقیقی سهام"
          hint="جریان خالص سهام و صندوق‌های سهامی (میلیارد تومان)"
          tone={flowEq == null ? undefined : flowEq >= 0 ? 'green' : 'red'}
        >
          {flowEq == null ? MISSING : <>{flowEq >= 0 ? '▲' : '▼'} {fmt(Math.abs(flowEq))} <span className="text-[10px] font-bold text-text-muted">ب.ت</span></>}
        </Stat>
        <Stat
          label="درآمد ثابت"
          hint="خروج از درآمد ثابت (منفی) نشانهٔ ورود نوسانی است"
          tone={flowFixed == null ? undefined : flowFixed < 0 ? 'green' : 'red'}
        >
          {flowFixed == null ? MISSING : <>{flowFixed < 0 ? '▼ ' : '▲ '}{fmt(Math.abs(flowFixed))} <span className="text-[10px] font-bold text-text-muted">ب.ت</span></>}
        </Stat>
        <Stat label="قدرت خرید حقیقی" hint="خرید ÷ فروش سرانهٔ حقیقی" tone={eq?.buy_power == null ? undefined : eq.buy_power >= 1.5 ? 'green' : eq.buy_power < 0.8 ? 'red' : 'yellow'}>
          {eq?.buy_power == null ? MISSING : <>{fmt(eq.buy_power)}<span className="text-[10px] font-bold text-text-muted">×</span></>}
        </Stat>
        <Stat label="نمادهای معامله‌شده" hint="سهام، حق تقدم و ص.سهامی">
          {eq?.traded == null ? MISSING : <>{fmtCount(eq.traded)} <span className="text-[10px] font-bold text-text-muted">از {fmtCount(eq.symbols)}</span></>}
        </Stat>
      </div>
    </div>
  );
}
