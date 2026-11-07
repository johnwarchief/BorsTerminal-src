// lib/ftsMatrixLabels.ts -- واژگانِ فارسیِ ستون‌هایِ ماتریس FTS، یک منبع
// دامنه از خودِ سرور می‌آید: `trend.matrix.decision` در api/chart.py و
// `tech_matrix_decision`/`tech_matrix_setup` در api/screener.py. هر مقدارِ
// تازه باید همین‌جا نام بگیرد؛ نامِ ناشناس بی‌تغییر نمایش داده می‌شود، نه
// معادلِ «مجاز».

/** حکمِ ماتریس: PERMITTED / REJECT / UNKNOWN (سرور) */
export const MATRIX_DECISION_FA: Record<string, string> = {
  PERMITTED: 'ورود مجاز',
  REJECT: 'ممنوعیت ورود',
  UNKNOWN: 'بدون رأی',
};

/** ستاپِ حکمِ ماتریس: NONE + سه شاخهٔ api/chart.py */
export const MATRIX_SETUP_FA: Record<string, string> = {
  NONE: 'بدون ستاپ',
  JET_OR_PULLBACK_HOLD: 'جت یا پولبک',
  FIB_CHOCH_STEP_ENTRY: 'ورود پله‌ای فیبو/CHoCH',
  DOUBLE_BOTTOM_OR_LAST_STRUCTURE: 'کف دوقلو یا آخرین ساختار',
};

/** `null`/غایب «نامشخص» است؛ `UNKNOWN` خودِ سرور «بدون رأی» — دو چیزِ جدا،
 *  هیچ‌کدام معادلِ اجازهٔ ورود نیست. */
export function matrixDecisionFa(decision: string | null | undefined): string {
  if (!decision) return 'نامشخص';
  return MATRIX_DECISION_FA[decision] ?? decision;
}

/** ستاپِ اعلام‌نشده `null` می‌ماند تا رابط «گزارش نشده» بنویسد، نه نامی ساختگی */
export function matrixSetupFa(setup: string | null | undefined): string | null {
  if (!setup) return null;
  return MATRIX_SETUP_FA[setup] ?? setup;
}
