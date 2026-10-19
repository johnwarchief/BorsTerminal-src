// shared/lib/tapeFlags.ts — نامِ yک‌جایِ هفت فیلترِ تابلوخوانی
//
// چرا درِ `shared`: پروندۀ نماد درِ سه سطح خوانده می‌شود (تبِّ تابلو، غربالگری،
// دیدهبان/برآیند). نامِ فیلتر اگر درِ هر فیچر جدا نوشته شود، روزی دوتا می‌شود —
// و «دو منبعِ حقیقت» همان چیزی است که مالک درِ بندِ پنجم مأموریت منع کرده است.
// `QUICK_LABELS` درِ `features/market/stores/tapeStore.ts` از همین جدول می‌خواند.
export const TAPE_FLAGS = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal'] as const;

export type TapeFlag = (typeof TAPE_FLAGS)[number];

/** نام‌ها عینِ دو فایلِ جزوه؛ داوری درِ `tape_flags.py` است و رابط فقط پرچم را
 *  می‌خواند. */
export const TAPE_FLAG_LABELS: Record<TapeFlag, string> = {
  f_clock: 'الگوی ساعت',
  f_susp: 'حجم مشکوک',
  f_jet: 'فیلتر جت',
  f_roobi: 'کف‌روبی',
  f_noqteh: 'نقطه زنی',
  f_smart: 'ورود پول هوشمند',
  f_legal: 'پول هوشمند و کد به کد حقوقی به حقیقی',
};

/** ستونِ شواهد: نامِ فیلدِ ثبت‌شده درِ `tape_flag_history.EVIDENCE_COLS`. */
export const EVIDENCE_LABELS: Record<string, string> = {
  tvol: 'حجم امروز',
  p_closing: 'قیمت پایانی',
  p_last: 'آخرین قیمت',
  percent_last: '٪ آخرین',
  z_tot_tran: 'تعداد معامله',
  vol_ratio_file: 'مبنایِ حجم (Σ۳۰÷۳۰)',
  buyer_power_raw: 'قدرت خریدار',
  resistance_59: 'سقفِ ۵۹ نشست',
  is6: 'مبنایِ [is6]',
};
