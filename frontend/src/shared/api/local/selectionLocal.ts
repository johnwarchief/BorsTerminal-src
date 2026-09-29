// shared/api/local/selectionLocal.ts — سبد/تصمیم‌ها روی خود دستگاه (localStorage)
//
// روی دسکتاپ این‌ها در user.db سرور می‌نشینند؛ روی گوشی دستگاهِ کاربر خودش
// مرجع است. شکل خروجی همان قرارداد /api/selection/* است (PortfolioFeedSchema)
// تا UI هیچ تفاوتی نبیند. وزن‌دهی ارزشی/کلاس دارایی نسخهٔ ۱ ساده است:
// weight_eff_pct = وزن دستی کاربر؛ محاسبات پیشرفتهٔ دسکتاپ (قیمت×تعداد،
// طبقهٔ دارایی از تابلو) در فاز بعد به آداپتور اضافه می‌شود.
import { query, normFa } from './localData';

const KEY = 'bors_mobile_decisions_v1';

type Decision = {
  symbol: string;
  status?: string | null;
  weight_pct?: number | null;
  weight_eff_pct?: number | null;
  stop_loss?: number | string | null;
  reason?: string | null;
  note?: string | null;
  sector?: string | null;
  price?: number | null;
  name?: string | null;
  qty?: number | null;
  value_toman?: number | null;
  updated_at?: string | null;
};

function load(): Decision[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return [];
    const arr = JSON.parse(raw) as unknown;
    return Array.isArray(arr) ? (arr as Decision[]) : [];
  } catch {
    return [];
  }
}

function save(list: Decision[]): void {
  localStorage.setItem(KEY, JSON.stringify(list));
}

export function portfolioFeed(closes?: Map<string, number>): Record<string, unknown> {
  const decisions = load();
  const counts: Record<string, number> = { accept: 0, reject: 0, monitor: 0, pending: 0 };
  for (const d of decisions) {
    const s = d.status ?? '';
    if (s in counts) counts[s] += 1;
    // قیمت جاری از تابلوی اسنپ‌شات/زنده؛ ارزش ردیف = قیمت × تعداد (ریال→تومان ÷۱۰)
    const px = closes?.get(normFa(d.symbol));
    if (px != null && px > 0) {
      d.price = px;
      if (d.qty != null && d.qty > 0) d.value_toman = Math.round((px * d.qty) / 10);
    }
  }
  const accepted = decisions.filter((d) => d.status === 'accept');
  // منطق وزن، همتای _weights دسکتاپ: ارزشی اگر برای همه معلوم است؛ وگرنه
  // دستی؛ وگرنه پیشنهاد وزن مساوی. (منشأ وزن به UI اعلام می‌شود)
  const allValued = accepted.length > 0 && accepted.every((d) => (d.value_toman ?? 0) > 0);
  const totalValue = accepted.reduce((a, d) => a + (d.value_toman ?? 0), 0);
  const anyManual = accepted.some((d) => (d.weight_pct ?? 0) > 0);
  const eq = accepted.length ? Math.round((100 / accepted.length) * 10) / 10 : null;
  let source: 'value' | 'manual' | 'equal' = 'equal';
  if (allValued && totalValue > 0) {
    source = 'value';
    for (const d of accepted) {
      d.weight_eff_pct = Math.round(((d.value_toman ?? 0) / totalValue) * 1000) / 10;
    }
  } else if (anyManual) {
    source = 'manual';
    for (const d of accepted) d.weight_eff_pct = d.weight_pct ?? 0;
  } else {
    for (const d of accepted) d.weight_eff_pct = eq ?? 0;
  }
  const sumW = Math.round(accepted.reduce((a, d) => a + (d.weight_eff_pct ?? 0), 0) * 10) / 10;
  const missing = accepted.filter((d) => !((d.value_toman ?? 0) > 0)).length;
  return {
    status: 'success',
    decisions,
    portfolio: accepted,
    monitor: decisions.filter((d) => d.status === 'monitor'),
    counts,
    limits: {
      equal_weight_pct: eq,
      sum_weight_pct: sumW,
      weight_source: source,
      portfolio_value_toman: allValued && totalValue > 0 ? totalValue : null,
      value_missing_count: missing,
    },
  };
}

export function saveDecision(body: unknown): Record<string, unknown> {
  const b = (body ?? {}) as Decision & { weight_pct?: number | null };
  if (!b.symbol) return { status: 'error', message: 'نماد نامشخص است' };
  let list = load().filter((d) => d.symbol !== b.symbol);
  if (b.status && b.status !== 'pending') {
    list = [
      {
        ...b,
        weight_eff_pct: b.weight_pct ?? null,
        updated_at: new Date().toISOString(),
      },
      ...list,
    ];
  }
  save(list);
  return { status: 'success', symbol: b.symbol, saved_status: b.status ?? 'pending' };
}

export function deleteDecision(symbol: string): Record<string, unknown> {
  const target = normFa(symbol);
  save(load().filter((d) => normFa(d.symbol) !== target));
  return { status: 'success', symbol };
}

/** جستجوی نماد از جدول instruments اسنپ‌شات + قیمت پایانی تابلو */
export async function searchSymbols(q: string): Promise<Record<string, unknown>> {
  const needle = `%${normFa(q)}%`;
  const rows = await query(
    `SELECT replace(replace(trim(i.l_val18),'ي','ی'),'ك','ک') AS symbol,
            trim(i.l_val30) AS name,
            coalesce(i.sector_name,'') AS sector_name,
            m.p_closing AS price
       FROM instruments i
       LEFT JOIN market_watch m ON m.ins_code = i.ins_code
      WHERE replace(replace(trim(i.l_val18),'ي','ی'),'ك','ک') LIKE ?
         OR replace(replace(trim(i.l_val30),'ي','ی'),'ك','ک') LIKE ?
      ORDER BY length(trim(i.l_val18)) ASC
      LIMIT 20`,
    [needle, needle],
  );
  const data = rows.map((r) => ({
    symbol: String(r.symbol ?? ''),
    name: String(r.name ?? ''),
    sector_name: String(r.sector_name ?? ''),
    cls: '',
    kind: '',
    price: typeof r.price === 'number' && r.price > 0 ? r.price : null,
  }));
  return { status: 'success', count: data.length, data };
}
