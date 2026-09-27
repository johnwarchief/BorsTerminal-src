// features/fundamental/components/QuarterlyTrend.tsx -- روند ۸ فصل درآمد و سود ناخالص
// #102 (رأیِ جزوه): روند فصلیِ درآمد باید با سود **ناخالص** سنجیده شود نه سود
// خالص — پس سری دومِ همین نمودار سود ناخالص است. نبودِ سود ناخالص (صندوق/بعضی
// هلدینگ‌ها) «صفر» نیست: آن فصل میله‌ای نمی‌گیرد و تغییر فصل هم نمایش داده
// نمی‌شود. اعداد منفی درست رندر می‌شوند (میله به پایین خط صفر)، محور Y با
// مقیاس همت/میلیارد تومان برچسب‌خورده و فصل‌ها با نام فارسی‌اند.
import { useMemo, useState } from 'react';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import { CollapseBody, CollapseToggle } from '@shared/components/Collapse';
import { useElementWidth } from '@shared/hooks/useElementWidth';
import type { FiscalQuarter } from '../lib/fundMath';

/** ارتفاعِ ثابت (#169 → #217): viewBox کشیده نمی‌شود تا واحدِ SVG = پیکسلِ CSS
 *  بماند و نوشته‌ها بی‌نسبت درشت/ریز نشوند. #169 از ≈۳۷۵px به ۱۶۸px نشست
 *  («زیادی بزرگ»)، ولی در عرضِ کاملِ پنل همان ۱۶۸ نوارِ باریک و بی‌قراشی شد —
 *  رأیِ #217: «خیلی کوچیکه، محسوس بزرگترش کن». ارتفاعِ CSS ثابت می‌ماند و
 *  فقط بلندتر می‌شود؛ عرض همچنان از ظرف خوانده می‌شود. */
const CHART_H = 262;
const PAD = 42;

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
  const [boxRef, boxW] = useElementWidth<HTMLDivElement>(560);
  const geom = useMemo(() => {
    const W = Math.max(280, boxW);
    const H = CHART_H;
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
    return { y, zeroY, slot, top, bottom, guides, W, H };
  }, [quarters, boxW]);
  /** #156 — پنلِ بسته با بازشوندهٔ روشن: نمودار پایینِ کارت بنیادی بود و
      کاربر کلیک‌پذیری‌اش را حدس نمی‌زد. */
  const [open, setOpen] = useState(false);

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
      <CollapseToggle
        open={open}
        onToggle={() => setOpen((o) => !o)}
        testId="qtrend-toggle"
        openLabel="نمودار فصلی"
        label={
          <span className="flex min-w-0 items-baseline gap-2">
            <span className="truncate text-sm font-black">روند فصلی درآمد و سود ناخالص</span>
            <span className="num shrink-0 text-3xs text-text-muted">«<span className="num">{toFaDigits(quarters.length)}</span> فصل، میلیارد تومان»</span>
          </span>
        }
      />
      <CollapseBody open={open} testId="qtrend-body">
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-2xs text-text-muted">
          <span className="flex items-center gap-3">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm bg-accent-blue" /> درآمد
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded-sm bg-accent-green" /> سود ناخالص
            </span>
          </span>
          {yoy != null ? (
            <span>
              تغییر فصل: <span className="num">{fmtInt(yoy * MRL_TO_BT)}</span> میلیارد تومان
            </span>
          ) : null}
        </div>
          {!hasGross ? (
            <p className="mb-2 text-2xs leading-relaxed text-text-muted" data-testid="qtrend-gross-na">
              سود ناخالص در صورت‌های مالی این نماد گزارش نمی‌شود — مقایسهٔ روند درآمد با آن ممکن نیست
              (نبودِ داده، صفر نیست).
            </p>
          ) : null}
          <div ref={boxRef} className="w-full">
            <svg
              viewBox={`0 0 ${geom.W} ${geom.H}`}
              width={geom.W}
              height={geom.H}
              style={{ width: '100%', height: `${geom.H}px` }}
              className="block"
              role="img"
              aria-label="نمودار روند فصلی"
              data-testid="quarterly-trend-chart"
            >
              {/* خطوط راهنمای محور Y با برچسب مقیاس */}
              {geom.guides.map((v) => (
                <g key={v}>
                  <line
                    x1={PAD}
                    x2={geom.W - PAD}
                    y1={geom.y(v)}
                    y2={geom.y(v)}
                    stroke="var(--border-color)"
                    strokeWidth="0.8"
                    opacity="0.6"
                  />
                  <text x={PAD - 4} y={geom.y(v) + 4} textAnchor="end" fontSize="12.5" fill="var(--text-muted)">
                    {fmtAxisBt(v * MRL_TO_BT)}
                  </text>
                </g>
              ))}
              <line x1={PAD} x2={geom.W - PAD} y1={geom.zeroY} y2={geom.zeroY} stroke="var(--border-color)" strokeWidth="1.2" />
              {quarters.map((q, i) => {
                const x = PAD + i * geom.slot;
                const rev = q.revenue ?? 0;
                const gross = q.grossProfit;
                const bw = Math.max(6, Math.min(38, geom.slot / 3.2));
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
                    <text x={x + geom.slot / 2} y={geom.H - 10} textAnchor="middle" fontSize="13" fill="var(--text-muted)">
                      {faQuarter(q)}
                    </text>
                  </g>
                );
              })}
            </svg>
          </div>
      </CollapseBody>
    </div>
  );
}
