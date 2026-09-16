// features/portfolio/model/sectorAllocation.ts -- ماتریس تخصیص صنایع سهام
// منبع بازه‌ها: سند FTS §۴ (مدیریت سرمایه و تخصیص پورتفوی) — «ساختار پورتفوی بهینه».
// اصل Circuit Breaker: غیب داده ⇒ بدون هشدار/«بدون داده»؛ هرگز عدد ساختگی.
import { toFaDigits } from '@shared/lib/fmt';

/** یک طبقهٔ صنعتی طبق سند FTS (بازهٔ درصدی سند، نه عدد ساختگی) */
export type SectorBand = {
  id: string;
  label: string;
  min: number;
  max: number;
  color: string;
  /** نمونه نمادهای سند — فقط راهنمای نمایش */
  examples: string[];
  /** کلیدواژه‌های نگاشت نام صنعت تابلو به این طبقه */
  keywords: string[];
};

/** هفت طبقهٔ سند FTS §۴ به‌ترتیب سند */
export const SECTOR_BANDS: SectorBand[] = [
  {
    id: 'metals',
    label: 'فلزات اساسی',
    min: 10,
    max: 15,
    color: '#f59e0b',
    examples: ['فملی', 'فسبزوار'],
    keywords: ['فلزات اساسي', 'فلزات اساسی', 'استخراج کانه', 'استخراج ساير معادن', 'فولاد'],
  },
  {
    id: 'cement',
    label: 'سیمان',
    min: 10,
    max: 15,
    color: '#94a3b8',
    examples: ['سصوفی', 'سآبیک', 'سقائن'],
    keywords: ['سيمان', 'سیمان'],
  },
  {
    id: 'petro',
    label: 'پتروپالایشی',
    min: 15,
    max: 20,
    color: '#22d3ee',
    examples: ['نوری', 'خراسان', 'شگویا'],
    keywords: ['پتروشيمي', 'پتروشیمی', 'فراورده هاي نفتي', 'پالایش', 'كك و سوخت', 'لاستيك و پلاستيك'],
  },
  {
    id: 'bank',
    label: 'بانکی',
    min: 10,
    max: 10,
    color: '#10b981',
    examples: ['وبملت', 'وپاسار'],
    keywords: ['بانك', 'بانک', 'واسطه گريهاي مالي'],
  },
  {
    id: 'pharma',
    label: 'دارویی منتخب',
    min: 10,
    max: 10,
    color: '#f43f5e',
    examples: ['دزاگرس'],
    keywords: ['دارو'],
  },
  {
    id: 'agri',
    label: 'زراعت',
    min: 10,
    max: 10,
    color: '#84cc16',
    examples: ['زنگا', 'زشگزا'],
    keywords: ['زراعت', 'كشت و دام', 'کشت و دام', 'نيشكر', 'نیشکر', 'قند و شكر'],
  },
  {
    id: 'defensive',
    label: 'ضدبحران / متفرقه',
    min: 5,
    max: 10,
    color: '#8b5cf6',
    examples: ['سیستم', 'کالا', 'غمهرا'],
    keywords: [],
  },
];

/** سقف سند برای یک طبقه */
export const DEFENSIVE_BAND_ID = 'defensive';

/** یکدست‌سازی نام صنعت: ي/ك عربی، نیم‌فاصله و فاصله‌های اضافی */
export function normalizeSector(s: string): string {
  return s
    .replace(/ي/g, 'ی')
    .replace(/ك/g, 'ک')
    .replace(/[\u200c\u200e\u200f]/g, '')
    .replace(/[\u064b-\u065f\u0670\u0640]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

/** نگاشت نام صنعت تابلو به طبقهٔ سند؛ صنعت ناشناخته ⇒ «ضدبحران/متفرقه» */
export function matchSectorBand(sector: string | null | undefined): string | null {
  const s = normalizeSector(sector ?? '');
  if (!s) return null;
  for (const b of SECTOR_BANDS) {
    if (b.id === DEFENSIVE_BAND_ID) continue;
    if (b.keywords.some((k) => s.includes(normalizeSector(k)))) return b.id;
  }
  return DEFENSIVE_BAND_ID;
}

/** برچسب بازهٔ سند: «۱۰٪ تا ۱۵٪» یا «۱۰٪» برای بازهٔ تک‌نقطه‌ای */
export function bandRangeLabel(b: SectorBand): string {
  return b.min === b.max ? `${toFaDigits(b.min)}٪` : `${toFaDigits(b.min)}٪ تا ${toFaDigits(b.max)}٪`;
}

/** نگاشت صنعت تابلو → برچسب فارسی طبقه (برای لایه‌های دیگر) */
export function bandLabelById(id: string | null): string | null {
  return SECTOR_BANDS.find((b) => b.id === id)?.label ?? null;
}

export type SectorHolding = {
  symbol: string;
  status?: string | null;
  weight_eff_pct?: number | null;
  weight_pct?: number | null;
  sector?: string | null;
};

export type SectorRow = {
  band: SectorBand;
  /** وزن فعلی صنعت در سبد (درصد) */
  actualPct: number;
  /** نمادهای این صنعت در سبد (فقط تصمیم accept) */
  members: { symbol: string; weightPct: number }[];
  overweight: boolean;
  /** مقدار عبور از سقف سند (درصد) */
  overByPct: number;
};

export type SectorAllocation = {
  rows: SectorRow[];
  /** آیا سبد تصمیمی دارد؟ (وزن‌ها ممکن است صفر ثبت شده باشند) */
  hasData: boolean;
  /** مجموع وزن صنایع نگاشت‌شده */
  mappedTotalPct: number;
  /** تصمیم‌های accept بدون وزن ثبت‌شده */
  zeroWeightCount: number;
};

function holdingWeight(h: SectorHolding): number {
  if (typeof h.weight_eff_pct === 'number' && Number.isFinite(h.weight_eff_pct)) return Math.max(0, h.weight_eff_pct);
  if (typeof h.weight_pct === 'number' && Number.isFinite(h.weight_pct)) return Math.max(0, h.weight_pct);
  return 0;
}

/**
 * تخصیص فعلی صنایع از تصمیم‌های سبد (فقط accept وزن دارند) در برابر بازه‌های سند.
 * بدون داده ⇒ rows با actualPct صفر و hasData=false (UI باید «بدون داده» بزند).
 */
export function computeSectorAllocation(holdings: SectorHolding[]): SectorAllocation {
  const accepted = holdings.filter((h) => (h.status ?? '').trim().toLowerCase() === 'accept');
  const rows: SectorRow[] = SECTOR_BANDS.map((band) => ({ band, actualPct: 0, members: [], overweight: false, overByPct: 0 }));
  const byId = new Map(rows.map((r) => [r.band.id, r]));
  let mappedTotalPct = 0;
  let zeroWeightCount = 0;

  for (const h of accepted) {
    const bandId = matchSectorBand(h.sector);
    if (!bandId) continue;
    const w = holdingWeight(h);
    if (w <= 0) zeroWeightCount += 1;
    const row = byId.get(bandId);
    if (!row) continue;
    row.actualPct += w;
    row.members.push({ symbol: h.symbol, weightPct: w });
    mappedTotalPct += w;
  }

  for (const row of rows) {
    row.actualPct = Math.round(row.actualPct * 10) / 10;
    row.overweight = row.actualPct > row.band.max + 0.05;
    row.overByPct = row.overweight ? Math.round((row.actualPct - row.band.max) * 10) / 10 : 0;
  }

  return {
    rows,
    hasData: accepted.length > 0,
    mappedTotalPct: Math.round(mappedTotalPct * 10) / 10,
    zeroWeightCount,
  };
}

export type OverweightAlert = {
  bandId: string;
  label: string;
  actualPct: number;
  capPct: number;
  overByPct: number;
  symbols: string[];
  reason: string;
};

/** هشدارهای «نقض تنوع‌بخشی (Overweight)» — علت‌محور و بدون داده ساختگی */
export function overweightAlerts(rows: SectorRow[]): OverweightAlert[] {
  return rows
    .filter((r) => r.overweight)
    .map((r) => ({
      bandId: r.band.id,
      label: r.band.label,
      actualPct: r.actualPct,
      capPct: r.band.max,
      overByPct: r.overByPct,
      symbols: r.members.map((m) => m.symbol),
      reason: `وزن صنعت ${r.band.label} در سبد ${toFaDigits(r.actualPct)}٪ است و ${toFaDigits(r.overByPct)}٪ از سقف سند (${toFaDigits(r.band.max)}٪) فراتر رفته است.`,
    }));
}
