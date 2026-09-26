// features/technical/lib/compareSeries.ts -- همسنجیِ دو نماد روی یک مقیاسِ بازدهی
// خالص و بی‌DOM. مبنا نخستین میله‌ای است که هر دو نماد در آن بسته شده‌اند؛ هر دو
// سری به پایهٔ ۱۰۰ در همان میله می‌نشینند، پس فاصلهٔ دو خط یعنی اختلافِ بازدهی،
// نه اختلافِ قیمت. میله‌ای که نمادِ دوم در آن معامله نشده undefined می‌ماند:
// خط پرش نمی‌کند و عددِ ساختگی هم نمی‌شود.
import type { KLineData } from '../../../vendor/klinecharts';
import { toFaDigits } from '../../../shared/lib/fmt';
import { COMPARE_BASE } from './compare';

export type CompareRow = { self: number | undefined; other: number | undefined };

export type CompareOutcome = {
  /** یک ردیف به ازای هر میلهٔ نمادِ اصلی — همان ترتیبِ dataListِ چارت */
  rows: CompareRow[];
  /** میله‌های مشترک؛ زیر ۲ یعنی مقایسه معنا ندارد */
  commonBars: number;
  /** میله‌ای که هر دو خط از آن ۱۰۰ می‌شوند */
  anchorTimestamp: number | null;
  selfChangePct: number | null;
  otherChangePct: number | null;
  /** نسبتِ بازدهیِ همسنج به این نماد از همان مبنا — نه تفاضلِ دو درصدِ بی‌سابقه */
  relativePct: number | null;
};

const EMPTY: CompareOutcome = {
  rows: [],
  commonBars: 0,
  anchorTimestamp: null,
  selfChangePct: null,
  otherChangePct: null,
  relativePct: null,
};

/** بستهٔ معتبر: قیمتِ مثبت و زمانِ عددی؛ بقیه کندل نیست */
function closeMap(candles: readonly KLineData[]): Map<number, number> {
  const m = new Map<number, number>();
  for (const c of candles) {
    if (!Number.isFinite(c.timestamp) || c.timestamp <= 0) continue;
    if (!Number.isFinite(c.close) || c.close <= 0) continue;
    m.set(c.timestamp, c.close);
  }
  return m;
}

/**
 * مبنا نخستین میلهٔ مشترک است، مگر anchorTs داده شود؛ آن‌گاه نخستین میلهٔ
 * مشترکِ از آن زمان به بعد. چارت این‌جا میلهٔ ابتدایِ دید را می‌دهد تا «نسبتِ
 * بازدهی» به همان بازه‌ای که کاربر می‌بیند برگردد، نه به اولِ تاریخچه.
 */
export function compareRows(
  main: readonly KLineData[],
  other: readonly KLineData[],
  anchorTs?: number | null,
): CompareOutcome {
  if (main.length === 0 || other.length === 0) return EMPTY;
  const otherCloses = closeMap(other);
  const mainCloses = closeMap(main);
  if (otherCloses.size === 0 || mainCloses.size === 0) return EMPTY;

  const isCommon = (c: KLineData): boolean => mainCloses.has(c.timestamp) && otherCloses.has(c.timestamp);
  const wanted = typeof anchorTs === 'number' && Number.isFinite(anchorTs) ? anchorTs : null;
  const anchor =
    main.find((c) => isCommon(c) && (wanted == null || c.timestamp >= wanted)) ?? main.find(isCommon);
  if (!anchor) return EMPTY;
  const selfBase = mainCloses.get(anchor.timestamp) as number;
  const otherBase = otherCloses.get(anchor.timestamp) as number;
  if (!(selfBase > 0) || !(otherBase > 0)) return EMPTY;

  let commonBars = 0;
  let lastSelf: number | null = null;
  let lastOther: number | null = null;
  const rows: CompareRow[] = main.map((c) => {
    const mc = mainCloses.get(c.timestamp);
    const oc = otherCloses.get(c.timestamp);
    const self = mc == null ? undefined : (mc / selfBase) * COMPARE_BASE;
    const otherValue = oc == null ? undefined : (oc / otherBase) * COMPARE_BASE;
    if (self != null && otherValue != null) {
      commonBars += 1;
      lastSelf = self;
      lastOther = otherValue;
    }
    return { self, other: otherValue };
  });

  const base: CompareOutcome = {
    rows,
    commonBars,
    anchorTimestamp: anchor.timestamp,
    selfChangePct: null,
    otherChangePct: null,
    relativePct: null,
  };
  if (commonBars < 2) return base;
  return {
    ...base,
    selfChangePct: lastSelf == null ? null : lastSelf - COMPARE_BASE,
    otherChangePct: lastOther == null ? null : lastOther - COMPARE_BASE,
    relativePct:
      lastSelf != null && lastSelf > 0 && lastOther != null ? (lastOther / lastSelf - 1) * 100 : null,
  };
}

/** برچسبِ یک درصدِ بازدهی با رقمِ فارسی و علامتِ صریح */
export function comparePctLabel(pct: number | null): string {
  if (pct == null || !Number.isFinite(pct)) return '—';
  const sign = pct > 0 ? '+' : pct < 0 ? '−' : '';
  return `${sign}${toFaDigits(Math.abs(pct).toFixed(1))}٪`;
}
