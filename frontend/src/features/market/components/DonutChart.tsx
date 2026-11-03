// features/market/components/DonutChart.tsx -- حلقۀ سهمِ دسته‌ها (بی‌معنای پرتفوی)
//
// چرا نو و نه `features/portfolio/components/TargetDonut.tsx`: آن donut برایِ
// «هدفِ پرتفویِ کاربر» ساخته شده (درصدِ تارگت، رنگِ انحراف از هدف). نمودارِ
// «ارزش معاملات انواع دارایی» و «ترکیبِ ارزشِ بازارِ صندوق‌های طلا» درِ مرجع
// سهمِ *بازار* را نشان می‌دهند و هیچ هدفی ندارند. واگرداندنِ آن کامپوننت یعنی
// دو معنا درِ یک فایل — و تست‌هایِ موجودِ پرتفوی را هم زیرِ سؤال می‌برد.
//
// دو قاعده:
// · مجموعِ درِ مرکز چاپ می‌شود با یکا، چون مرجع همین کار را می‌کند («۹۴/۴۸۸ T»)؛
//   بی‌یکا عددِ مرکز بی‌معناست.
// · جمعِ سهم‌ها لزوماً ۱۰۰٪ نیست و گرد نمی‌شود: اگر دسته‌ها کل را نمی‌پوشانند،
//   حلقه هم کل را نمی‌پوشاند و `coverage_pct` نوشته می‌شود.

export type DonutSlice = { key: string; label: string; value: number; color: string };

const TAU = Math.PI * 2;

function arc(cx: number, cy: number, rOuter: number, rInner: number, a0: number, a1: number) {
  const p = (r: number, a: number) => [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [x0, y0] = p(rOuter, a0);
  const [x1, y1] = p(rOuter, a1);
  const [x2, y2] = p(rInner, a1);
  const [x3, y3] = p(rInner, a0);
  return `M${x0.toFixed(2)},${y0.toFixed(2)} A${rOuter},${rOuter} 0 ${large} 1 ${x1.toFixed(2)},${y1.toFixed(2)} L${x2.toFixed(2)},${y2.toFixed(2)} A${rInner},${rInner} 0 ${large} 0 ${x3.toFixed(2)},${y3.toFixed(2)} Z`;
}

export function DonutChart({
  testId,
  slices,
  size = 132,
  centerTop,
  centerBottom,
  unit,
  onPick,
  picked,
}: {
  testId: string;
  slices: DonutSlice[];
  size?: number;
  centerTop?: string;
  centerBottom?: string;
  unit?: string;
  onPick?: (key: string) => void;
  picked?: string | null;
}) {
  const usable = slices.filter((s) => Number.isFinite(s.value) && s.value > 0);
  const total = usable.reduce((a, s) => a + s.value, 0);
  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 3;
  const rInner = rOuter * 0.62;

  if (!usable.length || total <= 0) {
    return (
      <p
        data-testid={`${testId}-empty`}
        className="rounded border border-dashed border-border-c px-2 py-1.5 text-3xs text-text-muted"
      >
        دسته‌ای با مقدارِ مثبت نرسید — حلقه بی‌مقدار نمی‌کشیم.
      </p>
    );
  }

  let a = -Math.PI / 2;
  const paths = usable.map((s) => {
    const span = (s.value / total) * TAU;
    const d = arc(cx, cy, rOuter, rInner, a, a + span - 0.012);
    a += span;
    return { ...s, d };
  });

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid={testId}>
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        role="img"
        aria-label={`ترکیبِ ${usable.length} دسته`}
        data-testid={`${testId}-svg`}
      >
        {paths.map((p) => (
          <path
            key={p.key}
            data-testid={`${testId}-slice-${p.key}`}
            d={p.d}
            fill={p.color}
            opacity={picked && picked !== p.key ? 0.35 : 1}
            onClick={onPick ? () => onPick(p.key) : undefined}
            className={onPick ? 'cursor-pointer' : undefined}
          >
            <title>{`${p.label}: ${p.value.toFixed(1)} ${unit ?? ''}`}</title>
          </path>
        ))}
        <text x={cx} y={cy - 2} textAnchor="middle" className="fill-text-primary" style={{ fontSize: 12, fontWeight: 800 }}>
          {centerTop}
        </text>
        <text x={cx} y={cy + 11} textAnchor="middle" className="fill-text-muted" style={{ fontSize: 9 }}>
          {centerBottom}
        </text>
      </svg>
      <ul className="flex min-w-0 flex-col gap-0.5">
        {paths.map((p) => (
          <li key={p.key} className="flex items-baseline gap-1 text-3xs text-text-secondary">
            <span className="inline-block size-2 shrink-0 rounded-sm" style={{ background: p.color }} />
            <span className="truncate" title={p.label}>
              {p.label}
            </span>
            <span className="num-text shrink-0 font-bold">{p.value.toFixed(1)}</span>
            <span className="num-text shrink-0 text-text-muted">
              {((p.value / total) * 100).toFixed(1)}٪
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** رنگِ دسته‌ها — ثابتِ همین فایل تا دو بارِ رندر دو رنگ ندهد */
export const DONUT_COLORS = [
  'var(--accent-blue)',
  'var(--accent-green)',
  'var(--accent-yellow)',
  '#a78bfa',
  '#f472b6',
  '#34d399',
  '#60a5fa',
  '#fbbf24',
  '#fb7185',
  '#94a3b8',
] as const;

export function donutColor(i: number) {
  return DONUT_COLORS[i % DONUT_COLORS.length];
}
