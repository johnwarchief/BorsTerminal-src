// features/technical/components/SidebarMacroPulse.tsx -- تب ۴ سایدبار: نبض کلان (فشرده)
// ارزش معاملات خرد، سرانهٔ خرید/فروش، تراز صف‌ها — از /api/mstat/* (همان هوک فیچر).
import { toFaDigits } from '@shared/lib/fmt';
import { macroEqRow, macroHemat, useMarketMacro } from '../api/useMarketMacro';

function f(x: number | null | undefined, digits = 1): string {
  return x == null || !Number.isFinite(x) ? '—' : toFaDigits(x.toFixed(digits));
}

function Line({ label, value, tone }: { label: string; value: React.ReactNode; tone?: 'green' | 'red' | 'yellow' }) {
  const color = tone === 'green' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : tone === 'yellow' ? 'text-accent-yellow' : 'text-text-primary';
  return (
    <div className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-1.5 last:border-b-0">
      <span className="text-[11px] text-text-secondary">{label}</span>
      <span className={`num text-xs font-bold ${color}`}>{value}</span>
    </div>
  );
}

export function SidebarMacroPulse() {
  const { data, isLoading } = useMarketMacro();
  const thermo = data?.thermometer ?? null;
  const depth = data?.depth ?? null;
  const sm = data?.smartMoney ?? null;
  const eq = macroEqRow(data?.summary);
  const hemat = macroHemat(sm);
  const flowEq = sm?.flow?.eq_flow_b_toman ?? null;
  const depthOk = depth?.depth_available === true;

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-macro">
      {isLoading ? <span className="px-1 text-[11px] text-text-secondary">در حال دریافت نبض کلان...</span> : null}
      <dl className="rounded-xl border border-border-c bg-bg-card/40 px-2.5" data-testid="sidebar-macro-list">
        <Line
          label="ارزش معاملات خرد"
          tone={hemat.state === 'good' ? 'green' : hemat.state === 'bad' ? 'red' : undefined}
          value={hemat.value == null ? 'بدون داده' : `${f(hemat.value)} همت`}
        />
        <Line
          label="سرانهٔ خرید حقیقی"
          value={eq?.pc_buy_m_toman == null ? 'بدون داده' : `${f(eq.pc_buy_m_toman)} م.ت`}
        />
        <Line
          label="سرانهٔ فروش حقیقی"
          value={eq?.pc_sell_m_toman == null ? 'بدون داده' : `${f(eq.pc_sell_m_toman)} م.ت`}
        />
        <Line
          label="قدرت خرید"
          tone={eq?.buy_power == null ? undefined : eq.buy_power >= 1.5 ? 'green' : eq.buy_power < 0.8 ? 'red' : 'yellow'}
          value={eq?.buy_power == null ? 'بدون داده' : `${f(eq.buy_power)}×`}
        />
        <Line
          label="جریان پول حقیقی سهام"
          tone={flowEq == null ? undefined : flowEq >= 0 ? 'green' : 'red'}
          value={flowEq == null ? 'بدون داده' : `${flowEq >= 0 ? '▲' : '▼'} ${f(Math.abs(flowEq))} ب.ت`}
        />
        <Line
          label="تراز صف‌ها (خرید÷فروش)"
          tone={depthOk && depth?.ratio != null ? (depth.ratio >= 1 ? 'green' : 'red') : undefined}
          value={depthOk && depth?.ratio != null ? `${f(depth.ratio)}×` : 'بدون داده'}
        />
        <Line
          label="صف خرید / فروش"
          value={
            depthOk && depth?.buy_queue_count != null && depth?.sell_queue_count != null
              ? `${toFaDigits(depth.buy_queue_count)} / ${toFaDigits(depth.sell_queue_count)}`
              : 'بدون داده'
          }
        />
        <Line
          label="نمادهای مثبت / منفی"
          value={
            thermo?.positive != null && thermo?.negative != null
              ? `${toFaDigits(Math.round(thermo.positive))} / ${toFaDigits(Math.round(thermo.negative))}`
              : 'بدون داده'
          }
        />
      </dl>
      <span className="px-1 text-[10px] leading-4 text-text-muted">منبع: /api/mstat/* — غایب یعنی «بدون داده»، نه صفر.</span>
    </div>
  );
}
