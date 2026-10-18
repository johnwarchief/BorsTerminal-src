// features/market/components/Sparkline.tsx -- خطِ کوچکِ تاریخچه، با اعلامِ دامنه
//
// چرا دستی و نه یک کتابخانۀ نمودار: کارت‌هایِ شاخص (صفحۀ ۶) سه تا هستند و
// نمودارِ صندوق‌های طلا (صفحۀ ۱۲) چندتا؛ همه یک چیز می‌خواهند — یک خطِ ۲۰
// پیکسلی. کشیدنِ یکبارِ Chart.js/lightweight-charts برایِ این کار هم bundle را
// بالا می‌برد هم دو منبعِ حقیقت برایِ «همان عدد» می‌سازد.
//
// دو قاعده که از نقص‌هایِ واقعیِ همین ریپو آمده:
// · بی‌داده صفر نیست. خانه‌یِ null خط را *می‌شکافد* (polyline جدا)، نه اینکه
//   آن را به کفِ نمودار می‌اندازد. تایم‌لاینِ قبلاً همین اشتباه را داشت: نقاطِ
//   بی‌سینک به صفر می‌رسیدند و «ریزشِ دروغین» می‌ساخت (توضیح درِ
//   `mstat_engine.timeline`).
// · کمتر از دو نقطه ⇒ خط نمی‌کشیم. یک نقطه هر شلیِ ممکن را «روند» نشان می‌دهد؛
//   به‌جای آن `note` می‌نشیند.
import { toFaDigits } from '@shared/lib/fmt';

export type SparkPoint = number | null | undefined;

export function sparkPath(values: SparkPoint[], w: number, h: number, pad = 1) {
  const pts = values.map((v, i) => ({ i, v: typeof v === 'number' && Number.isFinite(v) ? v : null }));
  const nums = pts.filter((p) => p.v !== null).map((p) => p.v as number);
  if (nums.length < 2) return { d: '', segments: [] as string[], min: 0, max: 0, count: nums.length };
  const min = Math.min(...nums);
  const max = Math.max(...nums);
  const span = max - min || 1;
  const n = pts.length;
  const x = (i: number) => pad + (i / Math.max(1, n - 1)) * (w - 2 * pad);
  const y = (v: number) => h - pad - ((v - min) / span) * (h - 2 * pad);
  // شکاف‌ها حفظ می‌شوند: هر بخشِ پیوسته یک polyline مستقل.
  const segments: string[] = [];
  let cur: string[] = [];
  for (const p of pts) {
    if (p.v === null) {
      if (cur.length > 1) segments.push(cur.join(' '));
      cur = [];
      continue;
    }
    cur.push(`${x(p.i).toFixed(1)},${y(p.v).toFixed(1)}`);
  }
  if (cur.length > 1) segments.push(cur.join(' '));
  return { d: segments.join(' '), segments, min, max, count: nums.length };
}

export function Sparkline({
  testId,
  values,
  width = 108,
  height = 26,
  tone = 'pos',
  label,
}: {
  testId: string;
  values?: SparkPoint[] | null;
  width?: number;
  height?: number;
  /** رنگ از همان کلیدِ tonِ سراسری می‌آید؛ اینجا فقط stroke/fill انتخاب می‌شود */
  tone?: 'pos' | 'neg' | 'zero' | 'nodata';
  label?: string;
}) {
  const { segments, count, min, max } = sparkPath(values ?? [], width, height);
  const stroke =
    tone === 'neg' ? 'var(--accent-red)' : tone === 'pos' ? 'var(--accent-green)' : 'var(--text-muted)';
  const real = values?.length ?? 0;
  return (
    <span
      data-testid={testId}
      className="inline-flex items-center gap-1"
      title={
        label
          ? `${label} · ${toFaDigits(count)} نقطۀ عددی از ${toFaDigits(real)} روز · کمینه ${toFaDigits(
              Number(min.toFixed(0)),
            )} بیشینه ${toFaDigits(Number(max.toFixed(0)))}`
          : undefined
      }
    >
      {segments.length ? (
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={label ? `نمودارِ کوچکِ ${label}` : 'نمودارِ کوچک'}
          data-testid={`${testId}-svg`}
        >
          {segments.map((s, i) => (
            <polyline
              key={i}
              points={s}
              fill="none"
              stroke={stroke}
              strokeWidth={1.4}
              strokeLinejoin="round"
              strokeLinecap="round"
            />
          ))}
        </svg>
      ) : (
        <span
          className="rounded border border-dashed border-border-c px-1.5 py-0.5 text-3xs text-text-muted"
          data-testid={`${testId}-flat`}
        >
          {real ? `${toFaDigits(real)} نقطه — خط نمی‌کشد` : 'تاریخچه نیست'}
        </span>
      )}
    </span>
  );
}
