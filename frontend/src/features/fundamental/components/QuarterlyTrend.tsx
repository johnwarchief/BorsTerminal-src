// features/fundamental/components/QuarterlyTrend.tsx -- روند ۸ فصل درآمد و سود ناخالص
// #102 (رأیِ جزوه): روند فصلیِ درآمد باید با سود **ناخالص** سنجیده شود نه سود
// خالص — پس سری دومِ همین نمودار سود ناخالص است. نبودِ سود ناخالص (صندوق/بعضی
// هلدینگ‌ها) «صفر» نیست: آن فصل میله‌ای نمی‌گیرد و تغییر فصل هم نمایش داده
// نمی‌شود. اعداد منفی درست رندر می‌شوند (میله به پایین خط صفر)، محور Y با
// مقیاس همت/میلیارد تومان برچسب‌خورده و فصل‌ها با نام فارسی‌اند.
import { useMemo } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import type { FiscalQuarter } from '../lib/fundMath';

const W = 640;
const H = 200;
const PAD = 34;

const Q_LABEL = ['بهار', 'تابستان', 'پاییز', 'زمستان'];

/** برچسب فارسی فصل از کلید «1404-Q3» یا سال+فصل */
function faQuarter(q: FiscalQuarter): string {
  return `${Q_LABEL[q.quarter - 1]} ${toFaDigits(q.yearLabel.slice(2))}`;
}

function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return Math.ceil(v / p) * p;
}

/** قالب مقادیر محور: میلیارد تومان (ب.ت) یا همت */
function fmtAxisBt(bt: number): string {
  const abs = Math.abs(bt);
    if (abs >= 1000) return `${toFaDigits((bt / 1000).toFixed(1))} همت`;
    if (abs >= 1) return `${toFaDigits(bt.toFixed(0))} ب.ت`;
  return toFaDigits(bt.toFixed(2));
}

/** واحد سری: میلیون ریال از بک‌اند — به ریال برای مقیاس‌بندی محور */
const MRL_TO_BT = 1e6 / 1e10;

export function QuarterlyTrend({ quarters }: { quarters: FiscalQuarter[] }) {
  const geom = useMemo(() => {
    // null یعنی «گزارش نشده» و در مقیاس محور صفر حساب نمی‌شود
    const vals = quarters.flatMap((q) =>
      [q.revenue, q.grossProfit].filter((v): v is number => typeof v === 'number' && Number.isFinite(v)),
    );
    const top = niceMax(Math.max(1, ...vals));
    const bottom = Math.min(0, ...vals);
    const span = top - bottom || 1;
    const y = (v: number) => PAD + (1 - (v - bottom) / span) * (H - PAD * 2);
    const zeroY = y(0);
    const n = Math.max(1, quarters.length);
    const slot = (W - PAD * 2) / n;
    // خطوط راهنمای محور Y: صفر + سقف + میانه مثبت
    const guides = [bottom, 0, top].filter((v, i, a) => a.indexOf(v) === i && v <= top && v >= bottom);
    return { y, zeroY, slot, top, bottom, guides };
  }, [quarters]);

  if (quarters.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border-c bg-bg-secondary p-6 text-center text-xs text-text-muted">
        سری فصلی برای این نماد نیست
      </div>
    );
  }

  /** سود ناخالص هیچ فصلی نیامده (صندوق/سرمایه‌گذاری/نبودِ سطر بهای تمام‌شده) —
   *  نمودار با میله‌های صفر جعل نمی‌شود؛ N/A صریح اعلام می‌شود. */
  const hasGross = quarters.some((q) => q.grossProfit != null);
  const last = quarters[quarters.length - 1];
  const prev = quarters[quarters.length - 2];
  const yoy = last?.grossProfit != null && prev?.grossProfit != null ? last.grossProfit - prev.grossProfit : null;

  return (
    <div className="glass-panel panel-in p-4">
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">روند فصلی درآمد و سود ناخالص</h3>
        <span className="flex items-center gap-3 text-2xs text-text-muted">
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-accent-blue" /> درآمد
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-sm bg-accent-green" /> سود ناخالص
          </span>
          {yoy != null ? <span>تغییر فصل: <span className="num">{fmtInt(yoy * MRL_TO_BT)}</span> میلیارد تومان</span> : null}
        </span>
      </div>
      {!hasGross ? (
        <p className="mb-2 text-2xs leading-relaxed text-text-muted" data-testid="qtrend-gross-na">
          سود ناخالص در صورت‌های مالی این نماد گزارش نمی‌شود — مقایسهٔ روند درآمد با آن ممکن نیست
          (نبودِ داده، صفر نیست).
        </p>
      ) : null}
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="نمودار روند فصلی" data-testid="quarterly-trend-chart">
        {/* خطوط راهنمای محور Y با برچسب مقیاس */}
        {geom.guides.map((v) => (
          <g key={v}>
            <line x1={PAD} x2={W - PAD} y1={geom.y(v)} y2={geom.y(v)} stroke="var(--border-color)" strokeWidth="0.8" opacity="0.6" />
            <text x={PAD - 4} y={geom.y(v) + 3} textAnchor="end" fontSize="8.5" fill="var(--text-muted)">
              {fmtAxisBt(v * MRL_TO_BT)}
            </text>
          </g>
        ))}
        <line x1={PAD} x2={W - PAD} y1={geom.zeroY} y2={geom.zeroY} stroke="var(--border-color)" strokeWidth="1.2" />
        {quarters.map((q, i) => {
          const x = PAD + i * geom.slot;
          const rev = q.revenue ?? 0;
          const gross = q.grossProfit;
          const bw = Math.max(3, geom.slot / 4);
          // میله از خط صفر به بالا/پایین — منفی درست رندر می‌شود
          const revTop = geom.y(Math.max(0, rev));
          const revH = Math.max(1, Math.abs(geom.y(rev) - geom.zeroY));
          const grossTop = gross == null ? 0 : geom.y(Math.max(0, gross));
          const grossH = gross == null ? 0 : Math.max(1, Math.abs(geom.y(gross) - geom.zeroY));
          return (
            <g key={q.key}>
              <title>{`${q.key}: درآمد ${fmtInt((q.revenue ?? 0) * MRL_TO_BT)} -- سود ناخالص ${gross == null ? 'گزارش نشده' : fmtInt(gross * MRL_TO_BT)}`}</title>
              <rect
                x={x + geom.slot / 2 - bw - 1}
                y={rev >= 0 ? revTop : geom.zeroY}
                width={bw}
                height={revH}
                fill={rev >= 0 ? 'var(--accent-blue)' : 'var(--accent-red)'}
                opacity="0.75"
              />
              {/* بدونِ سود ناخالص هیچ میله‌ای کشیده نمی‌شود — میلهٔ صفر یعنی «زیان صفر» */}
              {gross == null ? null : (
                <rect
                  x={x + geom.slot / 2 + 1}
                  y={gross >= 0 ? grossTop : geom.zeroY}
                  width={bw}
                  height={grossH}
                  fill={gross >= 0 ? 'var(--accent-green)' : 'var(--accent-red)'}
                  opacity="0.9"
                />
              )}
              <text x={x + geom.slot / 2} y={H - 6} textAnchor="middle" fontSize="9.5" fill="var(--text-muted)">
                {faQuarter(q)}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="mt-1 text-2xs text-text-muted"><span className="num">{toFaDigits(quarters.length)}</span> فصل آخر (ارقام میلیارد تومان)</div>
    </div>
  );
}
