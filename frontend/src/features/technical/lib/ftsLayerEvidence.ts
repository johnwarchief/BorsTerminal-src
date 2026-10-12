// features/technical/lib/ftsLayerEvidence.ts -- زنجیرۀ ردپای هر لایه (مرحلۀ ۶)
// FTS Rule → Algorithm Result → Chart Annotation، دقیقاً به همان شکلِ طرحِ
// مأموریت §۵: این فایل فقط *می‌خواند*. هیچ داوری از نو ساخته نمی‌شود، هیچ
// آستانه‌ای نمی‌آید و هیچ «فعال»ی بی‌پرچمِ سرور صادر نمی‌شود.
// سه‌حالتهایِ صادقانه همین‌جا نگه داشته می‌شوند: `null` (سرور نگفت) با `false`
// (سرور گفت نیست) یکی نیست، و «در حال تشکیل» با «دادهٔ ناکافی» هم‌معنی نمی‌شود.
// متنِ علت (`reason`/`desc`/`action`) عیناً از payloadِ همان لایه برداشته می‌شود؛
// بازنویسیِ آن، یعنی ساختنِ یک روایتِ دوم درِ فرانت.
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import type { Structure3Data } from '../api/useStructure3';
import { TREND_FA } from '../components/FtsBadgeStrip';
import type { FtsIndicatorEntry } from './ftsIndicatorCatalog';

/** حالتِ لایه، فقط از پرچم‌هایِ خودِ موتور */
export type LayerState = 'active' | 'forming' | 'inactive' | 'insufficient' | 'not-published';

export const LAYER_STATE_FA: Record<LayerState, string> = {
  active: 'فعال',
  forming: 'در حال تشکیل',
  inactive: 'فعال نیست',
  insufficient: 'دادهٔ ناکافی',
  'not-published': 'منتشر نشده',
};

export type EvidenceFact = { label: string; value: string };

export type LayerEvidence = {
  state: LayerState;
  /** خروجیِ الگوریتم — برچسب/عددِ منتشرشده؛ بی‌عدد، ردیفی نیست */
  facts: EvidenceFact[];
  /** «کِی رخ داد» (تاریخِ همان رویداد درِ payload) */
  occurredAt: string | null;
  /** «کِی فهمیدیم» (زمانِ تأیید)؛ null یعنی سرور آن را نگفته است */
  confirmedAt: string | null;
  /** متنِ علتِ خودِ موتور، دست‌نخورده */
  note: string | null;
};

/** دهانه‌هایی که از `/api/fts` نمی‌آیند (رویدادهایِ شرکتی از feedِ مبدأ،
 *  ساختارِ موتورِ سوم از `/api/structure3`) */
export type EvidenceFeed = {
  adjustmentEvents?: number | null;
  structure3?: Structure3Data | null;
};

const ev = (
  state: LayerState,
  facts: EvidenceFact[] = [],
  occurredAt: string | null = null,
  confirmedAt: string | null = null,
  note: string | null = null,
): LayerEvidence => ({ state, facts, occurredAt, confirmedAt, note });

const n = (v: unknown): number | null =>
  typeof v === 'number' && Number.isFinite(v) ? v : null;

/** عددِ منتشرشده ⇒ ردیف؛ منتشرنشده ⇒ هیچ (صفرِ جا‌نشین ساختگی است) */
const num = (facts: EvidenceFact[], label: string, v: unknown): void => {
  const x = n(v);
  if (x != null) facts.push({ label, value: fmtInt(x) });
};

/** متنِ منتشرشده ⇒ ردیف؛ رشتهٔ خالی و null «بی‌متن»اند نه «متنِ جعلی» */
const txt = (facts: EvidenceFact[], label: string, v: unknown): void => {
  if (typeof v === 'string' && v.trim()) facts.push({ label, value: v.trim() });
};

/** سه‌حالته: true/false خوانده می‌شود، null یعنی سرور نظر نداد */
const tri = (facts: EvidenceFact[], label: string, v: unknown): void => {
  if (v === true) facts.push({ label, value: 'هست' });
  else if (v === false) facts.push({ label, value: 'نیست' });
};

/** شمارۀ کندلِ موجود در برابرِ کفِ لازم — هر دو عدد از خودِ سرور (P0#1/#2).
 *  بی‌هر دو، «ناکافی» ادعا نمی‌شود؛ فقط ردیفِ تعداد می‌آید. */
function shortage(
  facts: EvidenceFact[],
  avail: unknown,
  req: unknown,
): boolean {
  const a = n(avail);
  const r = n(req);
  if (a != null) facts.push({ label: 'سابقهٔ موجود', value: `${toFaDigits(a)} کندل` });
  if (r != null) facts.push({ label: 'حداقلِ لازم', value: `${toFaDigits(r)} کندل` });
  return a != null && r != null && a < r;
}

/** رأیِ ماتریسِ هفتگی — همان دو واژه‌ای که پنلِ تحلیل ساختاری می‌گوید */
const MATRIX_FA: Record<string, string> = {
  PERMITTED: 'ورود مجاز',
  REJECT: 'ممنوعیت ورود',
};

type Reader = (fts: FtsAnalysisData | null | undefined, feed: EvidenceFeed) => LayerEvidence;

const READERS: Record<string, Reader> = {
  'trend-daily': (fts) => {
    const leg = fts?.trend?.D;
    if (!leg) return ev('not-published');
    const facts: EvidenceFact[] = [{ label: 'رأیِ موتور', value: TREND_FA[leg.trend] ?? leg.trend }];
    txt(facts, 'مبنایِ سنجش', leg.basis);
    num(facts, 'تازگیِ پیوت (کندلِ عقب)', leg.stale_bars);
    return ev(leg.trend === 'na' ? 'inactive' : 'active', facts, leg.last_pivot_time ?? null);
  },

  'trend-weekly-gate': (fts) => {
    const m = fts?.trend?.matrix;
    if (!m?.decision) return ev('not-published');
    const facts: EvidenceFact[] = [{ label: 'رأی', value: MATRIX_FA[m.decision] ?? m.decision }];
    txt(facts, 'ستاپ', m.setup);
    txt(facts, 'مبنایِ هفتگی', m.basis?.weekly);
    txt(facts, 'مبنایِ روزانه', m.basis?.daily);
    return ev(m.decision === 'REJECT' ? 'inactive' : 'active', facts, null, null, m.desc ?? null);
  },

  'structure-points': (fts) => {
    const pts = fts?.structure_points?.D ?? [];
    if (pts.length === 0) return ev('inactive', [], null, null, 'پیوتِ تأییدشده‌ای درِ این تاریخچه نیست');
    const last = pts[pts.length - 1];
    const facts: EvidenceFact[] = [
      { label: 'نقاطِ تأییدشده', value: `${toFaDigits(pts.length)} پیوت` },
      { label: 'آخرین برچسب', value: last.label },
    ];
    num(facts, 'قیمتِ تأییدشده', last.price);
    // زمانِ وقوع و زمانِ تأیید جدا می‌مانند (مرحلۀ ۱۰): «کِی فهمیدیم» نباید
    // جایِ «کِی رخ داد» را بگیرد، وگرنه خواننده فکر می‌کند مارکر زودتر دیده می‌شد.
    return ev('active', facts, last.time ?? null, last.confirm_time ?? null);
  },

  'fib-belt-33-40': (fts) => fibBelt(fts, 'zone_33_40'),
  'fib-belt-618-70': (fts) => fibBelt(fts, 'zone_618_70'),

  'fib-levels': (fts) => {
    const levels = fts?.fib?.levels ?? [];
    if (levels.length === 0) return ev('not-published');
    const facts: EvidenceFact[] = [{ label: 'سطح‌ها', value: `${toFaDigits(levels.length)} عدد` }];
    txt(facts, 'مبنایِ موج', fts?.fib?.leg?.direction);
    const provisional = fts?.fib?.leg?.provisional === true;
    return ev(provisional ? 'forming' : 'active', facts, fts?.fib?.leg?.end ?? null, null,
      provisional ? 'موجِ فیبو هنوز بی‌پیوتِ تأییدشده است (پیش‌نویس)' : null);
  },

  'jet': (fts) => {
    const j = fts?.jet;
    if (!j) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'مقاومت', j.resistance);
    tri(facts, 'ایستگاهِ سقفِ ایستاده شکسته', j.static_broke);
    txt(facts, 'طبقه', j.tier);
    const short = shortage(facts, j.bars_available, j.bars_required);
    if (j.active === true) return ev('active', facts, j.resistance_date ?? null);
    return ev(short ? 'insufficient' : 'inactive', facts, j.resistance_date ?? null, null, j.reason ?? null);
  },

  'pullback': (fts) => {
    const p = fts?.pullback;
    if (!p) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'سطحِ آخرین سقف', p.level);
    num(facts, 'قدمتِ سطح (کندل)', p.level_age_bars);
    tri(facts, 'لمس', p.touching);
    tri(facts, 'تأییدِ هفتگی', p.weekly_confirms);
    if (p.active === true) return ev('active', facts, p.level_date ?? null);
    // لمسِ بی‌بازگشت = درِ حالِ تشکیل، نه ردِ ستاپ و نه بی‌داده (P0 §۳)
    if (p.touching === true) return ev('forming', facts, p.level_date ?? null);
    return ev('inactive', facts, p.level_date ?? null, null, p.reason ?? null);
  },

  'choch': (fts) => {
    const c = fts?.choch;
    if (!c) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'سطح', c.level);
    tri(facts, 'تغییرِ صعودی', c.bullish);
    tri(facts, 'تغییرِ نزولی', c.bearish);
    txt(facts, 'برچسب', c.label);
    num(facts, 'روزهایِ تأیید', c.confirm_days);
    const on = c.bullish === true || c.bearish === true;
    return ev(on ? 'active' : 'inactive', facts, null, null, on ? null : c.reason ?? null);
  },

  'double-bottom': (fts) => {
    const d = fts?.double_bottom;
    if (!d) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'خطِ گردن', d.neckline);
    if (d.active === true) return ev('active', facts);
    return ev('inactive', facts, null, null, d.reason ?? null);
  },

  'range-box': (fts) => {
    const b = fts?.range_box;
    if (!b) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'سقفِ باکس', b.top);
    num(facts, 'کفِ باکس', b.bottom);
    num(facts, 'درصدِ بالایِ سقف', b.pct_above_top);
    if (b.active === true) {
      return ev('active', facts, b.end_date ?? null, null, b.start_date ? `بازۀ باکس از ${toFaDigits(b.start_date)}` : null);
    }
    return ev(b.top == null ? 'insufficient' : 'inactive', facts, b.end_date ?? null, null, b.reason ?? null);
  },

  'structure-points-weekly': (fts) => {
    const pts = fts?.structure_points?.W ?? [];
    if (pts.length === 0) return ev('inactive', [], null, null, 'پیوتِ هفتگیِ تأییدشده‌ای درِ این تاریخچه نیست');
    const last = pts[pts.length - 1];
    const facts: EvidenceFact[] = [
      { label: 'پیوت‌هایِ هفتگی', value: `${toFaDigits(pts.length)} نقطه` },
      { label: 'آخرین برچسب', value: last.label },
    ];
    num(facts, 'قیمتِ تأییدشده', last.price);
    return ev('active', facts, last.time ?? null, last.confirm_time ?? null);
  },

  'point-hunt': (fts) => {
    const p = fts?.point_hunt;
    if (!p) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'لمس‌ها', p.touches);
    num(facts, 'کف', p.floor_price);
    tri(facts, 'ریباند', p.bounced);
    // تریگر = کندلِ لمس+ریباند؛ لنگر = کفِ کانال. این دو یکی نیستند (#221).
    if (p.active === true) return ev('active', facts, p.trigger_date ?? null, null, p.floor_date ? `لنگرِ کف: ${p.floor_date}` : null);
    return ev('inactive', facts, p.trigger_date ?? null, null, p.reason ?? null);
  },

  'current-trigger': (fts) => {
    const t = fts?.status?.trigger;
    if (!t || typeof t.price !== 'number' || !(t.price > 0)) return ev('not-published');
    const facts: EvidenceFact[] = [];
    txt(facts, 'نوع', t.kind);
    txt(facts, 'برچسب', t.label);
    txt(facts, 'نقش', t.role);
    num(facts, 'قیمتِ تریگر', t.price);
    return ev('active', facts, t.date ?? null);
  },

  'third-peak': (fts) => {
    const l3 = fts?.exit_engine?.l3;
    if (!l3) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'سطحِ سقفِ سوم', l3.third_peak_level);
    num(facts, 'پهنایِ باند (٪ از سرور)', l3.third_peak_band_pct);
    if (l3.third_peak === true) return ev('active', facts);
    return ev('inactive', facts, null, null, l3.reason ?? null);
  },

  'hourglass': (fts) => {
    const h = fts?.hourglass;
    if (!h) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'MA52 هفتگی', h.ma52);
    num(facts, 'کندلِ هفتگیِ واقعی', h.weekly_bars);
    num(facts, 'RSI هفتگی', h.weekly_rsi);
    num(facts, 'پهنایِ سایه (٪ از سرور)', h.ma52_band_pct);
    tri(facts, 'تطبیقِ جایگاهِ MA52', h.ma52_position_match);
    if (h.active === true) return ev('active', facts);
    return ev('inactive', facts, null, null, h.desc ?? h.action ?? null);
  },

  'ma14-exit': (fts) => {
    const l1 = fts?.exit_engine?.l1;
    if (!l1) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'MA14', l1.ma14);
    num(facts, 'بستِ امروز', l1.close);
    if (l1.ma14_exit === true) return ev('active', facts);
    // pending یعنی «هنوز بسته نشده» — نه رد و نه بی‌داده (§۳)
    if (l1.ma14_exit_pending === true) return ev('forming', facts);
    return ev('inactive', facts, null, null, l1.stop_reason ?? null);
  },

  'hard-stop': (fts) => {
    const l1 = fts?.exit_engine?.l1;
    if (!l1) return ev('not-published');
    const facts: EvidenceFact[] = [];
    num(facts, 'حدِ ضرر', l1.hard_stop);
    txt(facts, 'مبنایِ حد', l1.stop_basis);
    tri(facts, 'خوردِ حد', l1.stop_hit);
    if (n(l1.hard_stop) != null) return ev('active', facts);
    return ev('inactive', facts, null, null, l1.stop_reason ?? null);
  },

  'setup-history': (fts) => {
    const list = fts?.setups ?? [];
    const facts: EvidenceFact[] = [{ label: 'رویدادهایِ تاریخ‌دار', value: `${toFaDigits(list.length)} ستاپ` }];
    txt(facts, 'وضعیتِ فهرست', fts?.setups_state);
    const short = shortage(facts, fts?.setups_bars_available, fts?.setups_bars_required);
    if (short) return ev('insufficient', facts);
    // فهرستِ خالیِ بی‌کوتاهیِ تاریخچه یعنی «ستاپی نبود»، نه «سنجیده نشد»
    return ev(list.length > 0 ? 'active' : 'inactive', facts,
      list.length > 0 ? list[list.length - 1].date : null);
  },

  // لایۀ خارجِ قواعدِ جزوه: مبدأاش feedِ TSETMC است، نه `/api/fts`
  'corp-actions': (_fts, feed) => {
    const c = n(feed.adjustmentEvents);
    if (c == null) return ev('not-published');
    return ev(c > 0 ? 'active' : 'inactive', [{ label: 'رویدادهایِ تعدیل', value: `${toFaDigits(c)} رویداد` }]);
  },

  // لایۀ موتورِ سوم: دهانۀ `/api/structure3` است نه `/api/fts` (مثلِ
  // `corp-actions`). بی‌پاسخ «منتشر نشده» است، «صفر پیوت» نه؛ پاسخِ ناکافی هم
  // حالتِ جدای خودش را دارد -- سه‌حالتهایِ این فایل درِ موتورِ سوم هم رعایت می‌شود.
  'e3-zigzag': (_fts, feed) => {
    const e3 = feed.structure3;
    if (!e3) return ev('not-published');
    if (e3.status === 'error') return ev('not-published', [], null, null, e3.message ?? null);
    const facts: EvidenceFact[] = [];
    const pr = e3.params;
    txt(facts, 'آستانه‌ها (از خودِ موتور)',
      pr ? `ATR ${toFaDigits(pr.atr_period)} · ×${toFaDigits(pr.atr_mult)} · کفِ ${toFaDigits(pr.floor_pct)}٪` : null);
    txt(facts, 'مبنایِ سری', e3.basis);
    num(facts, 'کندلِ تحلیل', e3.bars);
    const meta = e3.meta;
    // دو شمارِ meta معنایِ خودِ `_threshold` را دارند: `atr_used` یعنی «ATRِ معتبر
    // درِ آستانه حساب شد» -- وگرنه فقطِ کفِ٪ جاری بوده. پس «ATR» با «آستانه‌ای که
    // ATR ساخت» یکی نیست و برچسب هم همین را می‌گوید.
    num(facts, 'تأیید با ATRِ معتبر', meta?.confirmed_atr);
    num(facts, 'تأیید بی‌ATR (کف‌محور)', meta?.confirmed_floor_only);
    num(facts, 'کندل بی‌ATR', meta?.atr_missing_bars);
    if (meta?.pending) {
      facts.push({
        label: 'ساختارِ تأییدنشده (بی‌رسم)',
        value: `${meta.pending.kind === 'high' ? 'سقف' : meta.pending.kind === 'low' ? 'کف' : '—'} ${
          typeof meta.pending.price === 'number' ? fmtInt(meta.pending.price) : '—'
        }`,
      });
    }
    if (e3.status !== 'success') {
      return ev('insufficient', facts, null, null, e3.message ?? 'تاریخچه برای زیگزاگ ناکافی است');
    }
    const pts = e3.points ?? [];
    num(facts, 'پیوتِ تأییدشده', pts.length);
    if (pts.length === 0) {
      return ev('inactive', facts, null, null, e3.rule_source ?? null);
    }
    const last = pts[pts.length - 1];
    return ev('active', facts, last.time, last.confirm_time ?? null, e3.rule_source ?? null);
  },

  'e3-choch': (_fts, feed) => {
    const e3 = feed.structure3;
    if (!e3 || e3.status !== 'success') {
      return ev(e3 ? 'insufficient' : 'not-published', [], null, null, e3?.message ?? null);
    }
    const list = e3.choch ?? [];
    const facts: EvidenceFact[] = [{ label: 'واژگونیِ ساختاری', value: `${toFaDigits(list.length)} رویداد` }];
    if (list.length === 0) {
      return ev('inactive', facts, null, null, 'هیچ پیوتِ هم‌سمتی الگویِ دو جفتِ پیشین را نشکسته است');
    }
    const last = list[list.length - 1];
    num(facts, 'سطحِ واژگونی', last.level);
    facts.push({ label: 'جهت', value: last.direction === 'bullish' ? 'صعودی' : 'نزولی' });
    return ev('active', facts, last.time, last.confirm_time ?? null, e3.rule_source ?? null);
  },
};

function fibBelt(fts: FtsAnalysisData | null | undefined, key: 'zone_33_40' | 'zone_618_70'): LayerEvidence {
  const z = fts?.fib?.[key];
  if (!z) return ev('not-published');
  const facts: EvidenceFact[] = [];
  num(facts, 'کفِ کمربند', z.lo);
  num(facts, 'سقفِ کمربند', z.hi);
  tri(facts, 'قیمتِ امروز داخلِ کمربند', z.in_zone);
  const provisional = fts?.fib?.leg?.provisional === true;
  const state = n(z.lo) == null || n(z.hi) == null ? 'not-published' : provisional ? 'forming' : 'active';
  return ev(state, facts, fts?.fib?.leg?.end ?? null, null,
    provisional ? 'موجِ بی‌پیوتِ تأییدشده؛ کمربند پیش‌نویس است (P0#4)' : null);
}

/** شواهدِ یک لایه از رجیستری — شناسۀ ناشناخته «بی‌شاهد» است نه «صفر» */
export function layerEvidence(
  entry: FtsIndicatorEntry,
  fts: FtsAnalysisData | null | undefined,
  feed: EvidenceFeed = {},
): LayerEvidence {
  const reader = READERS[entry.id];
  if (!reader) return ev('not-published');
  return reader(fts, feed);
}

/** دهانۀ payloadِ رجیستری واقعاً درِ همان مسیر وجود دارد؟ (تستِ زنده‌بودنِ دهانه‌ها) */
export function sourceExists(fts: FtsAnalysisData | null | undefined, path: string): boolean {
  if (!fts || !path || path.startsWith('(')) return false;
  let cur: unknown = fts;
  for (const part of path.split('.')) {
    if (cur == null || typeof cur !== 'object') return false;
    cur = (cur as Record<string, unknown>)[part];
  }
  return cur != null;
}
