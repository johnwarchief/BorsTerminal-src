// shared/api/local/resolvers.ts — نگاشت مسیرهای /api/* به دادهٔ روی دستگاه
//
// هر مسیری که React مصرف می‌کند (قرارداد کامل در docs/plans/MOBILE-APP-PLAN.md)
// اینجا یک حل‌کننده دارد: یا از بسته‌های پخته (baked)، یا SQL روی جدول‌های خام،
// یا پیاده‌سازی محلی (سبد). مسیر ناشناخته ⇒ HttpError(404) — همان رفتاری که
// UI برای «بدون داده» می‌فهمد. هیچ دادهٔ ساختگی برنمی‌گردد.
import { HttpError } from '../http';
import { baked, metaValue, normFa, query } from './localData';
import { deleteDecision, portfolioFeed, saveDecision, searchSymbols } from './selectionLocal';
import { liveChart, liveClientType, liveTedpix, liveTodayCandle, liveWatch, overlayBoard, tehranToday } from './live';

const FTS_CONFIG_KEY = 'bors_mobile_fts_config_v1';

// تابلوی ۷مگابایتی را یک‌بار پارس نگه می‌داریم: پولینگ ۵ثانیه‌ای UI نباید هر
// بار JSON.parse سنگین بزند؛ لایهٔ زنده همین آبجکت را درجا به‌روز می‌کند.
let boardMemo: Record<string, unknown> | null = null;

async function boardPayload(): Promise<Record<string, unknown>> {
  boardMemo ??= (await bakedOr404('market_board', '/api/market')) as Record<string, unknown>;
  const rows = boardMemo.data;
  if (Array.isArray(rows)) {
    const mw = await liveWatch();
    if (mw) {
      const ct = await liveClientType();
      const n = overlayBoard(rows as Record<string, unknown>[], mw, ct);
      if (n > 0) boardMemo.live_overlay = { patched: n, at: new Date().toISOString() };
    }
  }
  return boardMemo;
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

/** کندل/حجم از price_history — همتای /api/history بک‌اند (فیلتر و dedupe یکسان) */
async function historyPayload(symbol: string): Promise<{
  status: string;
  candles: { time: string; open: number; high: number; low: number; close: number }[];
  volumes: { time: string; value: number; color: string }[];
}> {
  const rows = await query(
    `SELECT date, open, high, low, close, volume FROM price_history
      WHERE replace(replace(trim(symbol),'ي','ی'),'ك','ک') = ?
      ORDER BY date ASC`,
    [normFa(symbol)],
  );
  // حذف تکراریِ روز (کلید دسکتاپ: symbol,date — املای دوگانه ⇒ رکورد پرحجم‌تر می‌ماند)
  const byDate = new Map<string, { o: number; h: number; l: number; c: number; v: number }>();
  for (const r of rows) {
    const t = String(r.date ?? '');
    const o = Number(r.open), h = Number(r.high), l = Number(r.low), c = Number(r.close);
    const v = Number(r.volume ?? 0) || 0;
    if (!t || !Number.isFinite(o) || !Number.isFinite(h) || !Number.isFinite(l) || !Number.isFinite(c)) continue;
    if (c <= 0 || h <= 0) continue;
    const prev = byDate.get(t);
    if (!prev || v > prev.v) byDate.set(t, { o, h, l, c, v });
  }
  const dates = [...byDate.keys()].sort();
  const upC = 'rgba(34, 197, 94, 0.4)', dnC = 'rgba(239, 68, 68, 0.4)';
  const candles = dates.map((t) => {
    const k = byDate.get(t)!;
    return { time: t, open: k.o, high: k.h, low: k.l, close: k.c };
  });
  const volumes = dates.map((t) => {
    const k = byDate.get(t)!;
    return { time: t, value: k.v, color: k.c >= k.o ? upC : dnC };
  });
  return { status: candles.length ? 'success' : 'empty', candles, volumes };
}

type HistoryOut = Awaited<ReturnType<typeof historyPayload>>;

/**
 * چارت کامل از CSV زندهٔ TSETMC (کندل خام + رویدادهای تعدیل + factors) —
 * همان مسیر /api/chart دسکتاپ. null یعنی زنده در دسترس نیست ⇒ پختِ محلی.
 */
async function liveChartPayload(symbol: string): Promise<Record<string, unknown> | null> {
  try {
    // همان lookup دسکتاپ: نمادِ نرمال‌شده → ins_code (جدیدترین سری نماد)
    const rows = await query(
      `SELECT ins_code FROM instruments
        WHERE replace(replace(replace(trim(l_val18),'ي','ی'),'ك','ک'),'ى','ی') = ?
        ORDER BY updated_at DESC LIMIT 1`,
      [normFa(symbol)],
    );
    const insCode = rows.length ? String(rows[0].ins_code ?? '') : '';
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
                       close: live.close, last: live.close };
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
    const candle = { time: live.time, open: live.open, high: live.high, low: live.low, close: live.close };
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
    const data = await baked(`orderbook/${p(2)}`);
    return data ?? { status: 'no_data', symbol: p(2), levels: [] };
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
