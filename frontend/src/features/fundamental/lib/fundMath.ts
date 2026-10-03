// features/fundamental/lib/fundMath.ts -- تفکیک فصلی و میانهٔ صنعت (لایهٔ نمایش)
// این فایل هرگز داوری FTS نمی‌سازد: هیچ PASS/FAIL، امتیاز یا verdict اینجا محاسبه نمی‌شود.
// رأی پنج محور فقط از بک‌اند می‌آید (`/api/fundamental/{symbol}` و `/api/screener`).
// نسخۀ پیشین چهار تابعِ «ارزیابی پنج شاخص» با آستانه‌هایش داشت
// (`growth>=40`، `ratio>=1.0` و معافیتِ `passed: true`) که هیچ مصرف‌کننده‌ای نداشت
// و با موتور نمی‌خواند (`v10_monetary_growth_min=60` که *هدف* است نه کف،
// `sales_to_mcap_min=0.33`، و معافیت = «نظر نمی‌دهد» نه قبول). حذف شد تا منبع
// دومی رأی نماند.
import type { QuarterRow } from '../api/useQuarters';

export type FiscalQuarter = {
  key: string;
  yearLabel: string;
  quarter: 1 | 2 | 3 | 4;
  revenue: number | null;
  operatingProfit: number | null;
  netProfit: number | null;
  /**
   * سود ناخالصِ فصل (میلیون ریال). null یعنی صورتِ مالی سطر «بهای تمام‌شده»
   * را ندارد (صندوق، بعضی هلدینگ‌ها) — نه این‌که صفر بوده است.
   */
  grossProfit: number | null;
  /**
   * حاشیهٔ سود ناخالصِ فصلی به درصد = سود ناخالص ÷ درآمد × ۱۰۰.
   * #102 (رأیِ جزوه): مبنای مقایسه با درآمد، سود **ناخالص** است. سود ناخالص که
   * نباشد این عدد null می‌ماند — هرگز به سود خالص برنمی‌گردد و هرگز صفر نیست.
   */
  margin: number | null;
};

function num(v: unknown): number | null {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

function diff(cur: number | null, prev: number | null): number | null {
  if (cur == null || prev == null) return null;
  return cur - prev;
}

/** گروه‌بندی گزارش‌های تجمعی به سال مالی و تفکیک فصلی */
export function deCumulateQuarters(rows: QuarterRow[], keep = 8): FiscalQuarter[] {
  const asc = [...rows]
    .filter((r) => r.period_end)
    .sort((a, b) => (a.period_end < b.period_end ? -1 : a.period_end > b.period_end ? 1 : 0));
  const out: FiscalQuarter[] = [];
  let group: QuarterRow[] = [];
  const flush = () => {
    if (group.length === 0) return;
    const yearLabel = group[group.length - 1].period_end.slice(0, 4);
    let prevRev: number | null = null;
    let prevGross: number | null = null;
    let prevOp: number | null = null;
    let prevNet: number | null = null;
    for (const r of group) {
      const q = Math.round((r.period_months ?? 0) / 3);
      if (q < 1 || q > 4) continue;
      const rev = num(r.revenue);
      const gross = num(r.gross_profit);
      const op = num(r.operating_profit);
      const net = num(r.net_profit);
      const qRev = q === 1 ? rev : diff(rev, prevRev);
      const qGross = q === 1 ? gross : diff(gross, prevGross);
      const qOp = q === 1 ? op : diff(op, prevOp);
      const qNet = q === 1 ? net : diff(net, prevNet);
      out.push({
        key: `${yearLabel}-Q${q}`,
        yearLabel,
        quarter: q as 1 | 2 | 3 | 4,
        revenue: qRev,
        operatingProfit: qOp,
        netProfit: qNet,
        grossProfit: qGross,
        // #102: درآمد فقط با سود ناخالص سنجیده می‌شود. نبودِ سود ناخالص
        // «حاشیهٔ صفر» نیست و جایگزینِ سود خالص هم ندارد → null (N/A).
        margin: qRev != null && qRev > 0 && qGross != null ? (qGross / qRev) * 100 : null,
      });
      if (rev != null) prevRev = rev;
      // سود ناخالص برخلاف درآمد/سود خالص «تقریباً هیچ‌وقت ته‌نشین نمی‌شود»؛ نبودش
      // ساختاری است (صندوق سطر بهای تمام‌شده ندارد). اگر پایهٔ قدیمی نگه داشته
      // می‌شد، تفاضلِ فصلِ بعدی دو فصل را با هم می‌داد — پس پایه هم null می‌ماند
      // و آن فصل N/A می‌شود (نه عددِ غلط، نه صفر).
      prevGross = gross;
      if (op != null) prevOp = op;
      if (net != null) prevNet = net;
    }
    group = [];
  };
  let prevMonths = 0;
  for (const r of asc) {
    const m = r.period_months ?? 0;
    if (group.length > 0 && m <= prevMonths) flush();
    group.push(r);
    prevMonths = m;
  }
  flush();
  return out.slice(-keep);
}

/**
 * داوریِ روند فصلی: رشد سود **ناخالص** فصل آخر به فصل مشابه سال قبل (#102).
 * پیش از این مبنای مقایسه با درآمد، سود خالص بود؛ جزوه سود ناخالص را می‌خواهد.
 * null یعنی «داوری نداریم»: نه فصلِ مشابه سال قبل، نه سود ناخالصِ یکی از دو
 * فصل (صندوق/هلدینگ)، نه مبنای مثبت. هیچ‌وقت صفر و هیچ‌وقت سود خالص نیست.
 */
export function profitYoY(quarters: FiscalQuarter[]): number | null {
  if (quarters.length < 5) return null;
  const cur = quarters[quarters.length - 1];
  const base = quarters[quarters.length - 5];
  if (cur.quarter !== base.quarter) return null;
  if (cur.grossProfit == null || base.grossProfit == null) return null;
  if (base.grossProfit <= 0) return null;
  return ((cur.grossProfit - base.grossProfit) / base.grossProfit) * 100;
}

/** میانه P/E مثبت صنعت از تابلو زنده */
export function sectorMedianPE(rows: { sector_name?: string | null; pe?: number | null }[], sector: string): number | null {
  const vals = rows
    .filter((r) => (r.sector_name ?? '') === sector)
    .map((r) => num(r.pe))
    .filter((v): v is number => v != null && v > 0)
    .sort((a, b) => a - b);
  if (vals.length === 0) return null;
  const mid = Math.floor(vals.length / 2);
  return vals.length % 2 === 1 ? vals[mid] : (vals[mid - 1] + vals[mid]) / 2;
}

/** امتیاز تخفیف P/E به میانه صنعت: بازه 10- تا 15+ */
export function peBonus(pe: number | null | undefined, median: number | null | undefined): number {
  const p = num(pe);
  const m = num(median);
  if (p == null || m == null || m <= 0 || p <= 0) return 0;
  const ratio = p / m;
  const v = ratio >= 1 ? Math.max(-10, -12 * (ratio - 1)) : Math.min(15, 30 * (1 - ratio));
  return v === 0 ? 0 : v;
}

/** امتیاز رشد سود فصلی: بازه 15- تا 15+ */
export function yoyBonus(yoy: number | null | undefined): number {
  const y = num(yoy);
  if (y == null) return 0;
  if (y >= 0) return Math.min(15, 5 + y * 0.2);
  return Math.max(-15, y * 0.3);
}
