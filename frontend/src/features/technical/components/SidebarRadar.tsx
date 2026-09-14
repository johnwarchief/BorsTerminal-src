// features/technical/components/SidebarRadar.tsx -- تب «رادار» سایدبار: رادار سلامت کلان بازار
// چهار محور (درصد مثبت · قدرت خرید · تراز صف · پهنای معامله) از /api/mstat/*.
// اگر هر محور غایب باشد، صادقانه «بدون داده» می‌شود (Circuit Breaker).
import { toFaDigits } from '@shared/lib/fmt';
import { macroEqRow, useMarketMacro } from '../api/useMarketMacro';
import { buildRadarAxes, radarComplete, radarLabelPositions, radarPolygon, type RadarAxis } from '../lib/radar';

const SIZE = 200;
const CX = SIZE / 2;
const CY = SIZE / 2;
const R = 66;

function fa(x: number, digits = 1): string {
  return x == null || !Number.isFinite(x) ? '—' : toFaDigits(x.toFixed(digits));
}

export function SidebarRadar() {
  const { data, isLoading } = useMarketMacro();
  const thermo = data?.thermometer ?? null;
  const depth = data?.depth ?? null;
  const sm = data?.smartMoney ?? null;
  const eq = macroEqRow(data?.summary);

  const tradedSharePct =
    eq?.traded != null && eq?.symbols != null && eq.symbols > 0 ? (eq.traded / eq.symbols) * 100 : null;

  const axes = buildRadarAxes({
    positivePct: thermo?.positive_pct ?? null,
    power: eq?.buy_power ?? null,
    queueRatio: depth?.depth_available === true ? (depth.ratio ?? null) : null,
    tradedSharePct,
  });
  const complete = radarComplete(axes);
  const polygon = complete ? radarPolygon(axes.map((a) => a.value as number), CX, CY, R) : null;
  const labels = radarLabelPositions(axes.length, CX, CY, R);
  const rings = [0.25, 0.5, 0.75, 1];

  const stress = sm?.flow?.eq_flow_b_toman ?? null;

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-radar">
      <span className="px-1 text-[11px] font-bold text-text-secondary">رادار سلامت کلان بازار</span>
      {isLoading ? <span className="px-1 text-[11px] text-text-muted">در حال دریافت دادهٔ رادار...</span> : null}

      {polygon ? (
        <svg viewBox={`0 0 ${SIZE} ${SIZE}`} className="mx-auto h-[210px] w-[210px]" role="img" aria-label="رادار سلامت کلان بازار" data-testid="radar-svg">
          {rings.map((f) => {
            const g = radarPolygon(axes.map(() => f * 100), CX, CY, R);
            return g ? <path key={f} d={g.path} fill="none" stroke="var(--border-color)" strokeWidth="1" /> : null;
          })}
          {axes.map((a, i) => {
            const ang = -Math.PI / 2 + (2 * Math.PI * i) / axes.length;
            return (
              <line key={a.label} x1={CX} y1={CY} x2={CX + R * Math.cos(ang)} y2={CY + R * Math.sin(ang)} stroke="var(--border-color)" strokeWidth="1" />
            );
          })}
          <path d={polygon.path} fill="rgba(56,189,248,0.22)" stroke="var(--accent-blue)" strokeWidth="2" />
          {labels.map((p, i) => (
            <text key={axes[i].label} x={p.x} y={p.y} textAnchor={p.anchor} fontSize="9" fill="var(--text-muted)">
              {axes[i].label}
            </text>
          ))}
        </svg>
      ) : (
        <div className="rounded-xl border border-dashed border-border-c p-4 text-center text-[11px] text-text-muted" data-testid="radar-empty">
          محورهای رادار کامل نیست؛ دادهٔ کافی از نبض کلان نرسیده
        </div>
      )}

      <dl className="rounded-xl border border-border-c bg-bg-card/40 px-2.5" data-testid="radar-values">
        {axes.map((a: RadarAxis) => (
          <div key={a.label} className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-1.5 last:border-b-0">
            <dt className="text-[11px] text-text-secondary">{a.label}</dt>
            <dd className="num text-xs font-bold text-text-primary">{a.value == null ? 'بدون داده' : `${fa(a.value)}٪`}</dd>
          </div>
        ))}
        <div className="flex items-center justify-between gap-2 py-1.5">
          <dt className="text-[11px] text-text-secondary">جریان پول حقیقی سهام</dt>
          <dd className={`num text-xs font-bold ${stress == null ? 'text-text-primary' : stress >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
            {stress == null ? 'بدون داده' : `${stress >= 0 ? '▲' : '▼'} ${fa(Math.abs(stress))} ب.ت`}
          </dd>
        </div>
      </dl>
      <span className="px-1 text-[10px] leading-4 text-text-muted">
        منبع: /api/mstat/* — محورها به بازهٔ ۰..۱۰۰ نرمال شده‌اند (قدرت خرید ÷۲، تراز صف ÷۳).
      </span>
    </div>
  );
}
