// features/fundamental/lib/fundMath.ts -- ریاضیات خالص ۵ شاخص استراتژی FTS
import type { QuarterRow } from '../api/useQuarters';

export type FiscalQuarter = {
  key: string;
  yearLabel: string;
  quarter: 1 | 2 | 3 | 4;
  revenue: number | null;
  operatingProfit: number | null;
  netProfit: number | null;
  /** حاشیه سود ناخالص یا خالص فصلی به درصد */
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
    let prevOp: number | null = null;
    let prevNet: number | null = null;
    for (const r of group) {
      const q = Math.round((r.period_months ?? 0) / 3);
      if (q < 1 || q > 4) continue;
      const rev = num(r.revenue);
      const op = num(r.operating_profit);
      const net = num(r.net_profit);
      const qRev = q === 1 ? rev : diff(rev, prevRev);
      const qOp = q === 1 ? op : diff(op, prevOp);
      const qNet = q === 1 ? net : diff(net, prevNet);
      out.push({
        key: `${yearLabel}-Q${q}`,
        yearLabel,
        quarter: q as 1 | 2 | 3 | 4,
        revenue: qRev,
        operatingProfit: qOp,
        netProfit: qNet,
        margin: qRev != null && qRev > 0 && qNet != null ? (qNet / qRev) * 100 : null,
      });
      if (rev != null) prevRev = rev;
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

/** رشد سود خالص فصل آخر به فصل مشابه سال قبل */
export function profitYoY(quarters: FiscalQuarter[]): number | null {
  if (quarters.length < 5) return null;
  const cur = quarters[quarters.length - 1];
  const base = quarters[quarters.length - 5];
  if (cur.quarter !== base.quarter) return null;
  if (cur.netProfit == null || base.netProfit == null || base.netProfit <= 0) return null;
  return ((cur.netProfit - base.netProfit) / base.netProfit) * 100;
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

// ═══════════════════════════════════════════════════════════════════════════
//  توابع داوری ۵ شاخص اصلی FTS (اسپک v2.1)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * شاخص ۱: نرخ رشد فروش و درآمد نسبت به دوره مشابه سال قبل
 * فرمول: ((فروش امسال - فروش پارسال) / فروش پارسال) * ۱۰۰
 * آستانه: حداقل ۴۰٪ و امتیاز کامل بالای ۶۰٪
 */
export function evalSalesGrowth(curr: number, prev: number, minGrowth = 40.0) {
  if (prev <= 0 || curr == null) return { growth: null, passed: false, fullScore: false };
  const growth = ((curr - prev) / prev) * 100;
  const rounded = Number(growth.toFixed(1));
  return {
    growth: rounded,
    passed: rounded >= minGrowth,
    fullScore: rounded >= 60.0,
  };
}

/**
 * شاخص ۲: سابقه ۳ ساله روند سود خالص هر سهم (EPS) از ۱۲/۲۹ حسابرسی‌شده
 * شرط: اکیداً صعودی و تمام سال‌ها مثبت (EPS_y > EPS_y-1 > EPS_y-2 > 0)
 * هرگونه افت یا زیان = رد قطعی
 */
export function evalEpsTrajectory(history: number[]) {
  if (!history || history.length < 3) return { trajectory: 'INSUFFICIENT_DATA', passed: false };
  const [y1, y2, y3] = history.slice(-3);
  if (y1 == null || y2 == null || y3 == null) {
    return { trajectory: 'INSUFFICIENT_DATA', passed: false };
  }
  // شرط سخت‌گیرانه FTS: اکیداً صعودی و تماماً سودده
  if (y3 > y2 && y2 > y1 && y1 > 0) {
    return { trajectory: 'ASCENDING_STRICT', passed: true };
  }
  if (y3 <= 0 || y2 <= 0 || y1 <= 0) {
    return { trajectory: 'LOSS_OR_NEGATIVE', passed: false };
  }
  return { trajectory: 'DECLINING_OR_FLAT', passed: false };
}

/**
 * شاخص ۳: حاشیه سود ناخالص (Gross Profit Margin)
 * فرمول: (سود ناخالص / درآمد عملیاتی) * ۱۰۰
 * استاندارد >= ۳۰٪، مرزی >= ۲۰٪، زیر ۲۰٪ وتو و رد قطعی
 */
export function evalGrossMargin(grossProfit: number, revenue: number, minMargin = 20.0, optimalMargin = 30.0) {
  if (revenue <= 0 || grossProfit == null) return { margin: null, passed: false, optimal: false };
  const margin = (grossProfit / revenue) * 100;
  const rounded = Number(margin.toFixed(1));
  return {
    margin: rounded,
    passed: rounded >= minMargin,
    optimal: rounded >= optimalMargin,
  };
}

/**
 * شاخص ۴: نسبت فروش سالانه و پتانسیل سود ناخالص به ارزش بازار
 * شرط قبولی (OR Gate):
 * ۱) فروش سالانه‌شده / ارزش بازار >= ۱.۰
 * یا
 * ۲) سود ناخالص سالانه تخمینی / ارزش بازار >= ۴۰٪
 * استثنا: هلدینگ‌ها و سرمایه‌گذاری‌ها N/A معاف هستند
 */
export function evalSalesToMarketCap(
  annualSales: number,
  marketCap: number,
  grossMarginPct: number | null = null,
  isHolding = false,
) {
  if (isHolding) {
    return {
      ratio: null,
      potential: null,
      passed: true,
      isExempt: true,
      reason: 'معافیت هلدینگ/سرمایه‌گذاری (مبنای P/NAV)',
    };
  }
  if (marketCap <= 0 || annualSales <= 0) {
    return { ratio: null, potential: null, passed: false, isExempt: false, reason: 'داده ارزش بازار یا فروش ناموجود' };
  }

  const ratio = Number((annualSales / marketCap).toFixed(2));
  let potential: number | null = null;
  if (grossMarginPct != null && grossMarginPct > 0) {
    potential = Number(((annualSales * (grossMarginPct / 100) / marketCap) * 100).toFixed(1));
  }

  const salesPass = ratio >= 1.0;
  const potentialPass = potential != null && potential >= 40.0;
  const passed = salesPass || potentialPass;

  return {
    ratio,
    potential,
    passed,
    salesPass,
    potentialPass,
    isExempt: false,
    reason: salesPass
      ? 'پاس با نسبت فروش سالانه به ارزش بازار >= ۱.۰'
      : potentialPass
      ? 'پاس با پوشش سود ناخالص سالانه تخمینی >= ۴۰٪ ارزش بازار'
      : 'عدم دستیابی به حد نصاب نسبت فروش یا پتانسیل سود',
  };
}
