// shared/api/local/tapeFlagsLocal.ts — محاسبه و به‌روزرسانی پرچم‌های تابلوخوانی بر اساس داده‌های زنده
//
// همتای مستقیم tape_flags.py در دسکتاپ:
// هفت فرمول کانونی بر اساس ردیف زندهٔ تابلوی TSETMC + میانگین‌های تاریخیِ ردیف
//
type Row = Record<string, unknown>;

const num = (v: unknown): number | null => {
  const n = typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : NaN;
  return Number.isFinite(n) ? n : null;
};

/** محاسبهٔ مجدد پرچم‌های تابلو روی ردیف در صورت وجود داده‌های زنده */
export function refreshTapeFlags(r: Row): void {
  const pl = num(r.p_last ?? r.p_closing);
  const pc = num(r.p_closing);
  const py = num(r.price_yesterday);
  const tmin = num(r.tmin);
  const tvol = num(r.tvol ?? r.q_tot_tran);
  const ztt = num(r.z_tot_tran);
  const plp = num(r.percent_last ?? (py && pl != null && py > 0 ? ((pl - py) / py) * 100 : null));

  // میانگین حجم سی نشست
  const prior30 = num(r.prior30_vol);
  const monthAvg = num(r.month_avg_vol);
  const avg30 = prior30 != null && prior30 > 0 ? prior30 / 30 : monthAvg != null && monthAvg > 0 ? monthAvg : null;

  // اطلاعات حقیقی / حقوقی
  const bIv = num(r.buy_i_vol);
  const bIc = num(r.buy_count_i);
  const sIv = num(r.sell_i_vol);
  const sIc = num(r.sell_count_i);
  const sNv = num(r.sell_n_vol);
  const bp = bIv != null && bIc != null && bIc > 0 && sIv != null && sIc != null && sIc > 0 && sIv > 0
    ? (bIv / bIc) / (sIv / sIc)
    : null;

  // ۱) الگوی ساعت (f_clock): pl >= pc * 1.02 && tvol > 1.0 * avg30 && ztt > 30
  if (pl != null && pc != null && avg30 != null) {
    const isClock = pl >= pc * 1.02 && (tvol != null && tvol > avg30) && (ztt == null || ztt > 30);
    r.f_clock = isClock;
  }

  // ۲) حجم مشکوک (f_susp): tvol > 3.0 * avg30 && ztt > 50
  if (tvol != null && avg30 != null) {
    const isSusp = tvol > 3.0 * avg30 && (ztt == null || ztt > 50);
    r.f_susp = isSusp;
  }

  // ۳) فیلتر جت (f_jet): tvol > 3.0 * avg30 && bp >= 1.5 && ztt > 100 && pl > resistance
  if (tvol != null && avg30 != null) {
    const res = num(r.resistance_max);
    const hasRes = res != null ? (pl != null && pl > res) : true;
    const isJet = tvol > 3.0 * avg30 && (bp != null && bp >= 1.5) && (ztt == null || ztt > 100) && hasRes;
    r.f_jet = isJet;
  }

  // ۴) کف‌روبی صف فروش (f_roobi): pl == tmin && plp < -1.0 && buy_q1_cnt > 1 && buy_q1_vol > 100
  if (pl != null && tmin != null) {
    const bq1c = num(r.buy_q1_cnt);
    const bq1v = num(r.buy_q1_vol);
    const isRoobi = pl === tmin && (plp != null && plp < -1.0) && (bq1c != null && bq1c > 1) && (bq1v != null && bq1v > 100);
    r.f_roobi = isRoobi;
  }

  // ۵) نقطه زنی (f_noqteh): (pc - low_min) / pc * 100 < 3.0 && tvol > 1.0 * avg30 && ztt > 5
  if (pc != null && avg30 != null) {
    const lowMin = num(r.low_base_min ?? r.p_min);
    const dist = lowMin != null && pc > 0 ? ((pc - lowMin) / pc) * 100 : null;
    const isNoqteh = dist != null && dist < 3.0 && dist >= 0 && (tvol != null && tvol > avg30) && (ztt == null || ztt > 5);
    r.f_noqteh = isNoqteh;
  }

  // ۶) ورود پول هوشمند (f_smart): tvol > 1.5 * avg30 && bp >= 1.0 && pl >= pc && plp > 0
  if (tvol != null && avg30 != null && pl != null && pc != null) {
    const isSmart = tvol > 1.5 * avg30 && (bp != null && bp >= 1.0) && pl >= pc && (plp != null && plp > 0);
    r.f_smart = isSmart;

    // ۷) کد به کد حقوقی به حقیقی (f_legal): f_smart && bIv > 0.5 * tvol && sNv > 0.5 * tvol
    if (isSmart && bIv != null && sNv != null) {
      r.f_legal = bIv > 0.5 * tvol && sNv > 0.5 * tvol;
    }
  }
}
