// shared/api/local/resolvers.ts — نگاشت مسیرهای /api/* به دادهٔ روی دستگاه
//
// هر مسیری که React مصرف می‌کند قراردادِ خودش را همین‌جا دارد (نه در یک سندِ
// جدا؛ `docs/plans/MOBILE-APP-PLAN.md` که اینجا نام برده می‌شد هرگز نوشته نشد).
// برایِ بستۀ داده و امضایش: docs/MOBILE-DATA-PACKAGE-V2-2026-10-13.md
// و برایِ وضعیتِ انتشار: docs/android/ANDROID-RELEASE-REPORT-2026-10-15.md
// اینجا یک حل‌کننده دارد: یا از بسته‌های پخته (baked)، یا SQL روی جدول‌های خام،
// یا پیاده‌سازی محلی (سبد). مسیر ناشناخته ⇒ HttpError(404) — همان رفتاری که
// UI برای «بدون داده» می‌فهمد. هیچ دادهٔ ساختگی برنمی‌گردد.
import { HttpError } from '../http';
import { tehranOffsetMs } from '@shared/lib/marketHours';
import { baked, metaValue, normFa, query } from './localData';
import { deleteDecision, portfolioFeed, saveDecision, searchSymbols } from './selectionLocal';
import { liveChart, liveClientType, liveTedpix, liveTodayCandle, liveWatch, overlayBoard, tehranToday } from './live';
import { readLatestStoredMonthlySales, syncLatestMonthlySales, syncMonthlyHistory } from './codalMonthly';
import {
  readLatestStoredFinancialStatement,
  syncLatestAnnualFinancialStatement,
} from './codalFinancial';

const FTS_CONFIG_KEY = 'bors_mobile_fts_config_v1';

// تابلوی ۷مگابایتی را یک‌بار پارس نگه می‌داریم: پولینگ ۵ثانیه‌ای UI نباید هر
// بار JSON.parse سنگین بزند؛ لایهٔ زنده همین آبجکت را درجا به‌روز می‌کند.
let boardMemo: Record<string, unknown> | null = null;

/** مبنایِ rev_at وقتی هنوز هیچ رونشانیِ زنده‌ای عددی را عوض نکرده: مهرِ
 *  پختِ بسته. meta.last_sync (قالبِ «YYYY-MM-DD HH:MM:SS» خودِ بک‌اند) یا
 *  built_at. بی‌این، بی‌رونشانی rev_at یا صفر می‌ماند (badge «نامعلوم») یا
 *  — در نسخۀ خرابِ پیشین — هرگز. */
let boardBaselineMs = 0;

async function baselineMs(): Promise<number> {
  if (boardBaselineMs > 0) return boardBaselineMs;
  const meta = (boardMemo?.meta ?? {}) as Record<string, unknown>;
  const lastSync = typeof meta.last_sync === 'string' ? meta.last_sync : '';
  // مُهرِ «YYYY-MM-DD HH:MM:SS» بک‌اند ساعتِ دیواریِ تهران است؛ Date.parseی
  // صرف، آن را به TZِ گوشی می‌بندد و رویِ گوشیِ غیرتهرانی کج می‌شود.
  let ms = lastSync ? wallTehranToEpoch(lastSync) : NaN;
  if (!Number.isFinite(ms)) {
    const built = await metaValue('built_at').catch(() => null);
    ms = built ? Date.parse(built) : NaN; // built_at درِ CI با Z ساخته می‌شود (UTC)
  }
  boardBaselineMs = Number.isFinite(ms) ? ms : 0;
  return boardBaselineMs;
}

/** «YYYY-MM-DD HH:MM:SS»ِ تهران ← epoch. بی‌FALLBACK بهِ Date.parse که TZِ
 *  گوشی رأی می‌دهد. */
function wallTehranToEpoch(s: string): number {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})(?::(\d{2}))?$/.exec(s.trim());
  if (!m) return Date.parse(s);
  const asUtc = Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +(m[6] ?? 0));
  return asUtc - tehranOffsetMs(asUtc);
}

// وضعیتِ لایهٔ زنده: برایِ پنلِ 🛠 و برایِ داوریِ صادقانۀ «تازگی».
const overlayState = {
  patched: 0, at: '', fails: 0, lastFailAt: null as string | null,
  /** چکیدۀ عددیِ دورِ قبل (جمعِ حجم + جمعِ پایانی‌ها) — بی‌مقایسه، هر
   *  پاسخِ موفقِ TSETMC بی‌هیچ معاملۀِ جدید هم «داده عوض شد» می‌شد و badge
   *  سبزِ کاذب می‌ساخت. */
  fingerprint: '',
};

/** چکیدۀِ پایدار از اعدادِ زنده: اگر یکِ قیمت یا یکِ حجم تکان بخورد، عوض
 *  می‌شود؛ پاسخِ بی‌تغییریِ سرور، بیت‌به‌بیت همان چکیده را می‌دهد. */
function watchFingerprint(mw: Map<string, { pcl: number | null; qtj: number | null }>): string {
  let sumV = 0; let sumP = 0; let n = 0;
  for (const m of mw.values()) {
    sumV += m.qtj ?? 0;                    // جمعِ صحیح (سبدِ عددِ بزرگ بی‌خطایِ راندینگ)
    sumP += Math.round((m.pcl ?? 0) * 100); // پایانی ×۱۰۰ تا گردِ عددِ اعشاری گم نشود
    n += 1;
  }
  return `${n}:${sumV}:${sumP}`;
}

async function boardPayload(): Promise<Record<string, unknown>> {
  boardMemo ??= (await bakedOr404('market_board', '/api/market')) as Record<string, unknown>;
  const rows = boardMemo.data;
  if (Array.isArray(rows)) {
    const mw = await liveWatch();
    if (mw) {
      const ct = await liveClientType();
      const n = overlayBoard(rows as Record<string, unknown>[], mw, ct);
      overlayState.patched = n;
      overlayState.at = new Date().toISOString();
      // سه ستونِ تازگی که درِ بدنهٔ پخته‌شده مُرده‌اند (rev=0 از روزِ پخت،
      // live_count شمارشِ روزِ پخت، بی‌rev_at): با رونشانیِ زنده از نو
      // حساب می‌شوند. بی‌این، پولینگِ دلتا درِ marketFeed هرگز rev را عوض
      // ندیده و FreshnessBadge پنج دقیقه بعد از بالا آمدنِ اپ «ایستاده/کهنه»
      // می‌گفت درحالی‌که اعداد هر ۵ ثانیه از TSETMC عوض می‌شدند — دقیقاً همان
      // «درِ ساعاتِ معاملات درست کار نمی‌کند».
      const liveRows = n > 0
        ? (rows as Record<string, unknown>[]).filter((r) => r.is_live === true).length
        : typeof boardMemo.live_count === 'number' ? boardMemo.live_count : 0;
      if (n > 0) {
        boardMemo.live_count = liveRows;
        boardMemo.fossil_count = (rows as unknown[]).length - liveRows;
      }
      // rev فقط وقتی عوض می‌شود که یکِ عددِ واقعی جابه‌جا شده باشد: چکیدۀِ
      // حجم‌وپایانیِ مارکت‌واچ. سرورِ بی‌معاملۀِ جدید همان چکیده را می‌دهد،
      // پس «پاسخ رسید» با «داده عوض شد» خلط نمی‌شود — بازارِ ایستاده
      // صادقانه «ایستاده» می‌ماند. دورِ نخست فقط مُهر می‌کند (تبدیلِ ۰→۱ِ
      // بی‌مغزا ممنوع: rev درِ marketFeed سوپِ دلتا را گیت می‌کند).
      const fp = watchFingerprint(mw);
      if (n > 0 && overlayState.fingerprint && fp !== overlayState.fingerprint) {
        const prev = typeof boardMemo.rev === 'number' ? boardMemo.rev : 0;
        boardMemo.rev = prev + 1;
        boardMemo.rev_at = Date.now();
      }
      overlayState.fingerprint = fp;
    } else {
      // خطایِ شبکه درِ live.ts بلعیده می‌شود (null)؛ اینجا تنها نقطه‌ای است
      // که می‌فهمیم «زنده نبود» — درِ پنلِ 🛠 دیده می‌شود، نه پنهان.
      if (overlayState.at) {
        overlayState.fails += 1;
        overlayState.lastFailAt = new Date().toISOString();
      }
      // بی‌لایهٔ زنده *درِ کلِ این نشست*: شمارشِ live_countِ بدنهٔ پخت
      // «امروز» را اثبات نمی‌کند. اگر مهرِ نشستِ بسته با امروزِ تهران
      // نمی‌خواند، ردیفِ زندهٔ امروز درِ دسترس نیست — صفر صادقانه بهتر ازِ
      // ۳۶۱۴ فرسوده است. اگر همین نشست رونشانیِ موفقی داشته، ردیف‌ها همان
      // اعدادِ روزِ جاری‌اند و live_countِ شمارش‌شدۀ بالا درست می‌ماند؛
      // صفرکردنشان دروغِ جهۀِ مخالف می‌شد. بی‌مهرِ نشستِ معلوم هم
      // دست‌نخورده می‌ماند (ندانستن ≠ صفر کردن).
      const meta = (boardMemo.meta ?? {}) as Record<string, unknown>;
      const sess = Number(meta.d_even);
      if (!overlayState.at && Number.isFinite(sess) && sess > 0) {
        const today = Number(tehranToday().replaceAll('-', ''));
        if (Number.isFinite(today) && sess !== today) {
          boardMemo.live_count = 0;
          boardMemo.fossil_count = (rows as unknown[]).length;
        }
      }
    }
  }
  // rev_at هرگز مُهرِ روزِ پخت را «عوض‌شدنِ همین حالا» وانمود نمی‌کند؛
  // بی‌رونشانیِ زنده، مُهرِ پخت یعنی آخرین باری که *قطعاً* عددی عوض شده.
  if (boardMemo.rev_at == null) boardMemo.rev_at = await baselineMs();
  return boardMemo;
}

/** برای پنل عیب‌یابی: آخرین رونشانیِ زندهٔ تابلو (چند ردیف، کِی، چند شکست) */
export function overlayStatus() {
  if (!overlayState.at && !overlayState.lastFailAt) return null;
  return { patched: overlayState.patched, at: overlayState.at,
           fails: overlayState.fails, lastFailAt: overlayState.lastFailAt };
}

/** فقط برایِ تست — وضعیتِ ماژولِ تابلو را به حالتِ نخستِ فرآیند برمی‌گرداند
 *  (boardMemo ممو سراسری است و تست‌ها باید از هم مستقل باشند). */
export function __resetBoardForTest(): void {
  boardMemo = null;
  boardBaselineMs = 0;
  overlayState.patched = 0;
  overlayState.at = '';
  overlayState.fails = 0;
  overlayState.lastFailAt = null;
  overlayState.fingerprint = '';
}

/** قیمت پایانی نمادها از تابلوی حافظه — برای وزن‌دهی ارزشی سبد */
export async function boardCloses(): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  try {
    const b = await boardPayload();
    for (const r of (b.data as Record<string, unknown>[] | undefined) ?? []) {
      const sym = normFa(String(r.symbol ?? ''));
      const px = Number(r.p_closing ?? r.p_last);
      if (sym && Number.isFinite(px) && px > 0) out.set(sym, px);
    }
  } catch { /* تابلو در اسنپ‌شات نبود — وزن‌دهی ارزشی غیرفعال می‌ماند */ }
  return out;
}

async function bakedOr404(key: string, url: string): Promise<unknown> {
  const data = await baked(key);
  if (data === null) throw new HttpError(404, url, `دادهٔ آفلاین برای ${key} در اسنپ‌شات نیست`);
  return data;
}

/** کلیدِ بستۀ قیف. باید با `funnel_key()` درِ `scripts/build_mobile_snapshot.py`
 *  بیت‌به‌بیت یکی باشد — `dev/mobile_funnel_offline_v1116.py` همین را با هم
 *  خواندنِ هر دو طرف می‌سنجد، چون رانشِ همین یکِ رشته صفحۀ غربالگریِ گوشی را
 *  بی‌خطایِ قابل‌فهم خالی می‌کند. */
export function funnelKey(preset: string, logic: string, fundMode: string,
                          dropSuffix: boolean): string {
  return `funnel/${preset}/${logic}/${fundMode}/${dropSuffix ? 'ds1' : 'ds0'}`;
}

const FUNNEL_FUND_DEFAULT = 'standard';

/** آنچه آفلاین سرو می‌شود: زنجیرۀ پیش‌فرضِ هر اشخاص × منطقِ and/or × بنیادیِ
 *  standard × حذفِ پسوندِ عددیِ روشن. هر چیزِ دیگری صریح رد می‌شود. */
async function funnelOffline(u: URL, body: unknown, url: string): Promise<unknown> {
  const b = (body && typeof body === 'object' ? body : {}) as Record<string, unknown>;
  const preset = String(b.preset ?? u.searchParams.get('preset') ?? 'trend');
  const logic = String(b.logic ?? u.searchParams.get('logic') ?? 'and');
  const fundMode = String(b.fund_mode ?? u.searchParams.get('fund_mode') ?? FUNNEL_FUND_DEFAULT);
  const dropRaw = b.drop_suffix ?? u.searchParams.get('drop_suffix');
  const dropSuffix = dropRaw === undefined || dropRaw === null
    ? true : (dropRaw === true || dropRaw === 'true');
  const chain = Array.isArray(b.chain) ? b.chain.map(String)
    : String(u.searchParams.get('chain') ?? '').split(',').map((s) => s.trim()).filter(Boolean);
  const has = (v: unknown) => !!v && typeof v === 'object' && Object.keys(v as object).length > 0;
  const exceptions = has(b.exceptions);
  const params = has(b.params);

  if (fundMode !== FUNNEL_FUND_DEFAULT || !dropSuffix || chain.length || exceptions || params) {
    const asked = [preset, `منطقِ ${logic}`, `بنیادیِ ${fundMode}`,
      dropSuffix ? 'با پسوندِ عددی' : 'بی‌پسوندِ عددی'];
    if (chain.length) asked.push(`زنجیرۀ دستِ خودِ شما (${chain.length} فیلتر)`);
    if (exceptions) asked.push('استثنا');
    if (params) asked.push('پارامترِ دلخواه');
    throw new HttpError(404, url,
      `ترکیبِ خواستۀ غربالگری درِ بستۀ آفلاین پخته نشده: ${asked.join(' / ')}. `
      + 'رویِ گوشی فقط زنجیرۀ پیش‌فرضِ هر اشخاص با منطقِ AND یا OR و بنیادیِ standard سرو '
      + 'می‌شود؛ برایِ همین ترکیب نسخهٔ دسکتاپ را باز کنید.');
  }
  return bakedOr404(funnelKey(preset, logic, fundMode, dropSuffix), url);
}

/** کندل/حجم از price_history — همتای /api/history بک‌اند (فیلتر و dedupe یکسان) */
async function historyPayload(symbol: string): Promise<{
  status: string;
  candles: { time: string; open: number; high: number; low: number; close: number;
             closing?: number; last?: number | null }[];
  volumes: { time: string; value: number; color: string }[];
}> {
  // `last` درِ اسنپ‌شات‌هایِ تازه هست (price_history از v10.7.0 این ستون را
  // کپی می‌کند) و درِ بسته‌هایِ کهنه نیست — بی‌ستون، پایانی همان مبنایِ نمایش
  // می‌ماند، نه جعلِ `last := close`.
  let rows: Record<string, unknown>[];
  let hasLast = true;
  try {
    rows = await query(
      `SELECT date, open, high, low, close, volume, last FROM price_history
        WHERE replace(replace(trim(symbol),'ي','ی'),'ك','ک') = ?
        ORDER BY date ASC`,
      [normFa(symbol)],
    );
  } catch {
    hasLast = false;
    rows = await query(
      `SELECT date, open, high, low, close, volume FROM price_history
        WHERE replace(replace(trim(symbol),'ي','ی'),'ك','ک') = ?
        ORDER BY date ASC`,
      [normFa(symbol)],
    );
  }
  // حذف تکراریِ روز (کلید دسکتاپ: symbol,date — املای دوگانه ⇒ رکورد پرحجم‌تر می‌ماند)
  const byDate = new Map<string, { o: number; h: number; l: number; c: number; v: number; last: number | null }>();
  for (const r of rows) {
    const t = String(r.date ?? '');
    const o = Number(r.open), h = Number(r.high), l = Number(r.low), c = Number(r.close);
    const v = Number(r.volume ?? 0) || 0;
    const ls = hasLast ? Number(r.last) : NaN;
    const last = Number.isFinite(ls) && ls > 0 ? ls : null;
    if (!t || !Number.isFinite(o) || !Number.isFinite(h) || !Number.isFinite(l) || !Number.isFinite(c)) continue;
    if (c <= 0 || h <= 0) continue;
    const prev = byDate.get(t);
    if (!prev || v > prev.v) byDate.set(t, { o, h, l, c, v, last });
  }
  const dates = [...byDate.keys()].sort();
  const upC = 'rgba(34, 197, 94, 0.4)', dnC = 'rgba(239, 68, 68, 0.4)';
  const candles = dates.map((t) => {
    const k = byDate.get(t)!;
    // مبنایِ نمایش = آخرین (همان پیش‌فرضِ price_basis دسکتاپ)، لنگرِ تعدیل = پایانی
    return { time: t, open: k.o, high: k.h, low: k.l, close: k.last ?? k.c, closing: k.c, last: k.last };
  });
  const volumes = dates.map((t) => {
    const k = byDate.get(t)!;
    return { time: t, value: k.v, color: k.c >= k.o ? upC : dnC };
  });
  return { status: candles.length ? 'success' : 'empty', candles, volumes };
}

type HistoryOut = Awaited<ReturnType<typeof historyPayload>>;

/** نماد → ins_code (جدیدترین سریِ نماد) — همان lookupِ دسکتاپ */
async function insCodeFor(symbol: string): Promise<string> {
  const rows = await query(
    `SELECT ins_code FROM instruments
      WHERE replace(replace(replace(trim(l_val18),'ي','ی'),'ك','ک'),'ى','ی') = ?
      ORDER BY updated_at DESC LIMIT 1`,
    [normFa(symbol)],
  );
  return rows.length ? String(rows[0].ins_code ?? '') : '';
}

/**
 * چارت کامل از CSV زندهٔ TSETMC (کندل خام + رویدادهای تعدیل + factors) —
 * همان مسیر /api/chart دسکتاپ. null یعنی زنده در دسترس نیست ⇒ پختِ محلی.
 */
async function liveChartPayload(symbol: string): Promise<Record<string, unknown> | null> {
  try {
    const insCode = await insCodeFor(symbol);
    if (!insCode) return null;
    const res = await liveChart(insCode, symbol);
    if (!res || typeof res !== 'object') return null;
    const out = res as Record<string, unknown>;
    // کندل زندهٔ امروز از مارکت‌واچ — همتای _attach_live_bar دسکتاپ
    const live = await liveTodayCandle(normFa(symbol), normFa);
    if (live) {
      const candles = out.candles as { time: string; last?: number }[];
      const volumes = out.volumes as { time: string }[];
      const factors = out.factors as { time: string; factor: number }[];
      const candle = { time: live.time, open: live.open, high: live.high, low: live.low,
                       close: live.last ?? live.close, last: live.last ?? undefined };
      const vol = { time: live.time, value: live.volume,
                    color: live.close >= live.open ? '#10b981' : '#f43f5e' };
      const last = candles[candles.length - 1];
      if (last && last.time === live.time) {
        candles[candles.length - 1] = candle;
        volumes[volumes.length - 1] = vol;
        factors[factors.length - 1] = { time: live.time, factor: 1.0 };
      } else if (!last || last.time < live.time) {
        candles.push(candle);
        volumes.push(vol);
        factors.push({ time: live.time, factor: 1.0 });
        out.count = candles.length;
      }
    }
    return out;
  } catch { /* زنده در دسترس نبود — پختِ محلی جایگزین می‌شود */ }
  return null;
}

/** کندل زندهٔ امروز را به انتهای سری تاریخی می‌چسباند (جایگزین اگر امروز از قبل هست) */
async function withTodayCandle(h: HistoryOut, symbol: string): Promise<HistoryOut> {
  try {
    const live = await liveTodayCandle(normFa(symbol), normFa);
    if (!live) return h;
    const today = tehranToday();
    const last = h.candles[h.candles.length - 1];
    const candle = { time: live.time, open: live.open, high: live.high, low: live.low,
                     close: live.last ?? live.close, last: live.last };
    const vol = { time: live.time, value: live.volume,
                  color: live.close >= live.open ? 'rgba(34, 197, 94, 0.4)' : 'rgba(239, 68, 68, 0.4)' };
    if (last && last.time === today) {
      h.candles[h.candles.length - 1] = candle;
      h.volumes[h.volumes.length - 1] = vol;
    } else {
      h.candles.push(candle);
      h.volumes.push(vol);
    }
    if (h.status === 'empty' && h.candles.length) h.status = 'success';
  } catch { /* زنده در دسترس نبود — سری تاریخی دست‌نخورده برمی‌گردد */ }
  return h;
}

/** نزدیک‌ترین بازهٔ پخته‌شدهٔ تقویم به days درخواستی */
function nearestUpcomingKey(days: number): string {
  const buckets = [7, 14, 30, 60, 90];
  const pick = buckets.find((b) => b >= days) ?? 90;
  return `calendar/upcoming/${pick}`;
}

export async function resolveLocal(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'DELETE',
  body?: unknown,
): Promise<unknown> {
  const u = new URL(url, 'http://local');
  const path = decodeURIComponent(u.pathname).replace(/\/+$/, '');
  const seg = path.split('/').filter(Boolean); // ['api', ...]
  const p = (i: number) => seg[i] ?? '';

  if (path === '/api/codal/monthly-sales/sync') {
    if (method !== 'POST') throw new HttpError(405, url, 'POST required');
    return syncLatestMonthlySales(u.searchParams.get('symbol') ?? '');
  }
  if (path === '/api/codal/monthly-sales/history-sync') {
    if (method !== 'POST') throw new HttpError(405, url, 'POST required');
    const maxPages = Number(u.searchParams.get('max_pages') ?? 1);
    const maxReports = Number(u.searchParams.get('max_reports') ?? 5);
    return syncMonthlyHistory(u.searchParams.get('symbol') ?? '', { maxPages, maxReports });
  }
  if (path === '/api/codal/monthly-sales') {
    if (method !== 'GET') throw new HttpError(405, url, 'GET required');
    return readLatestStoredMonthlySales(u.searchParams.get('symbol') ?? '');
  }
  if (path === '/api/codal/annual-financial-statements/sync') {
    if (method !== 'POST') throw new HttpError(405, url, 'POST required');
    return syncLatestAnnualFinancialStatement(u.searchParams.get('symbol') ?? '');
  }
  if (path === '/api/codal/annual-financial-statements') {
    if (method !== 'GET') throw new HttpError(405, url, 'GET required');
    return readLatestStoredFinancialStatement(u.searchParams.get('symbol') ?? '');
  }

  // --- تابلو و اسکرینر --------------------------------------------------
  if (path === '/api/market') return boardPayload();
  if (path === '/api/screener') {
    const data = (await bakedOr404('screener', url)) as Record<string, unknown>;
    const limit = Number(u.searchParams.get('limit') ?? 0);
    if (limit > 0 && Array.isArray(data.data)) {
      return { ...data, data: data.data.slice(0, limit), count: Math.min(limit, data.data.length) };
    }
    return data;
  }

  // --- FTS و بنیادی -----------------------------------------------------
  if (path === '/api/fts/config') {
    if (method === 'GET') {
      try {
        const local = localStorage.getItem(FTS_CONFIG_KEY);
        if (local) return JSON.parse(local) as unknown;
      } catch { /* localStorage خراب — از اسنپ‌شات بخوان */ }
      return bakedOr404('fts_config', url);
    }
    // POST: آستانه‌ها فقط روی دستگاه ذخیره می‌شوند؛ محاسبهٔ مجدد در پخت بعدی PC
    localStorage.setItem(FTS_CONFIG_KEY, JSON.stringify(body ?? {}));
    return { status: 'success' };
  }
  if (path === '/api/fts') return bakedOr404('fts', url);
  if (p(1) === 'fts' && seg.length === 3) return bakedOr404(`fts/${p(2)}`, url);
  if (path === '/api/fundamental/screen') return bakedOr404('screener', url);
  if (path === '/api/fundamental/sectors') return bakedOr404('sectors', url);
  if (p(1) === 'fundamental' && seg.length === 3) return bakedOr404(`fundamental/${p(2)}`, url);
  if (p(1) === 'fundamental' && seg.length === 4 && p(3) === 'quarters') {
    return bakedOr404(`quarters/${p(2)}`, url);
  }

  // --- غربالگری (قیف FTS) ------------------------------------------------
  // داورِ رسمی درِ `api/funnel.py` است و گوشی هیچ سروری ندارد، پس تنها چیزی که
  // آفلاین سرو می‌شود **خروجیِ پختۀ همان موتور** است. هیچ داوریِ تازه درِ
  // کلاینت ساخته نمی‌شود — همان قاعدۀ «یک داور» که با حذفِ `buildFunnel` بسته شد.
  // ترکیبی که پخته نشده ⇒ HttpError با علتِ روشن؛ نه جدولِ خالی (که «بازار خالی»
  // خوانده می‌شود) و نه حدس.
  if (path === '/api/funnel') {
    return funnelOffline(u, body, url);
  }
  if (path === '/api/funnel/registry') {
    return bakedOr404('funnel_registry', url);
  }
  if (path === '/api/funnel/trace') {
    throw new HttpError(404, url,
      'ردپایِ یکِ نماد درِ بستۀ آفلاین پخته نمی‌شود؛ وضعیتِ هر نماد درِ هر گام از '
      + 'خودِ پاسخِ قیف رویِ دستگاه است، اما خطِ زمانِ رویدادها فقط درِ دسکتاپ ساخته می‌شود');
  }

  // --- نبض بازار و شاخص ---------------------------------------------------
  if (p(1) === 'mstat') {
    if (p(2) === 'timeline' && u.searchParams.get('mode') === 'cum') {
      return bakedOr404('mstat/timeline_cum', url);
    }
    return bakedOr404(`mstat/${p(2)}`, url);
  }
  if (path === '/api/index/tedpix') {
    // اول زنده از CDN خود TSETMC (روی گوشی همیشه کار می‌کند)؛ وگرنه پختِ PC
    const limit = Number(u.searchParams.get('limit') ?? 0) || 0;
    const live = await liveTedpix(limit);
    if (live) return live;
    return bakedOr404('index/tedpix', url);
  }

  // --- چارت -----------------------------------------------------------
  if (p(1) === 'history' && seg.length === 3) return withTodayCandle(await historyPayload(p(2)), p(2));
  if (p(1) === 'chart' && seg.length === 3) {
    // اول CSV زندهٔ TSETMC (کندل کامل + رویدادهای تعدیل واقعی — همان /api/chart دسکتاپ)
    const liveRes = await liveChartPayload(p(2));
    if (liveRes) return liveRes;
    // آفلاین: پختِ محلی؛ adjustEvents خالی یعنی «تعدیلی نداریم»، نه دادهٔ ساختگی.
    const h = await withTodayCandle(await historyPayload(p(2)), p(2));
    return { ...h, count: h.candles.length, adjustEvents: [] };
  }
  if (p(1) === 'chart-db' && seg.length === 3) return withTodayCandle(await historyPayload(p(2)), p(2));
  if (p(1) === 'order-book' && seg.length === 3) {
    const sym = p(2);
    // عمقِ زنده از همان blDs که دسکتاپ درِ `order_book` می‌نویسد — صفِ دیدنیِ
    // گوشی نباید به اسنپ‌شاتِ روزِ پخت گیر کند («سرخطی» از همین پنج خط خوانده می‌شود).
    const ins = await insCodeFor(sym);
    const mw = ins ? (await liveWatch())?.get(ins) : undefined;
    if (mw?.levels.length) {
      return {
        status: 'ok', symbol: sym, levels: mw.levels,
        session: { d_even: mw.den, h_even: mw.hen, updated_at: new Date().toISOString() },
        totals: mw.q
          ? { buy_vol: mw.q.bq, buy_cnt: mw.q.bc, sell_vol: mw.q.sq, sell_cnt: mw.q.sc }
          : null,
      };
    }
    const data = await baked(`orderbook/${sym}`);
    return data ?? { status: 'no_data', symbol: sym, levels: [] };
  }
  if (p(1) === 'market' && p(2) === 'intraday') {
    // سری درون‌روزی از تیک‌های زندهٔ سرور ساخته می‌شود؛ در اسنپ‌شات معنا ندارد
    return { status: 'no_data', buckets: [] };
  }

  // --- تقویم -----------------------------------------------------------
  if (p(1) === 'calendar' && p(2) === 'upcoming') {
    const days = Number(u.searchParams.get('days') ?? 14) || 14;
    return bakedOr404(nearestUpcomingKey(days), url);
  }
  if (p(1) === 'calendar' && seg.length === 3) {
    const data = await baked(`calendar/${p(2)}`);
    return data ?? { status: 'success', symbol: p(2), events: [] };
  }

  // --- سبد و تصمیم (روی خود دستگاه) ------------------------------------
  if (path === '/api/selection/portfolio') return portfolioFeed(await boardCloses());
  if (path === '/api/selection/decision' && method === 'POST') return saveDecision(body);
  if (p(1) === 'selection' && p(2) === 'decision' && seg.length === 4) {
    return deleteDecision(p(3));
  }
  if (path === '/api/selection/symbols') {
    return searchSymbols(u.searchParams.get('q') ?? '');
  }

  // --- بروزرسانی/عملیات دسکتاپ — روی گوشی معنی ندارند -------------------
  if (path === '/api/update/version') {
    return {
      status: 'success',
      version: (await metaValue('app_version')) ?? '0.0.0',
      built_at: await metaValue('built_at'),
    };
  }
  if (p(1) === 'update' || (p(1) === 'sync')) {
    return { status: 'unsupported', message: 'این عملیات مخصوص نسخهٔ دسکتاپ است' };
  }
  if (path === '/api/diagnostics/log/open') {
    return { status: 'unsupported', message: 'لاگ سرور در نسخهٔ موبایل وجود ندارد' };
  }

  throw new HttpError(404, url, `مسیر ${path} در حالت آفلاین پشتیبانی نمی‌شود`);
}
