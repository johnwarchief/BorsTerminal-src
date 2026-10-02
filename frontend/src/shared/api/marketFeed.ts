// shared/api/marketFeed.ts — تنها خوانندۀ /api/market در کل برنامه
//
// چرا این فایل هست: شش مصرف‌کننده (تابلو، واچ‌لیستِ تکنیکال، میانهٔ صنعت،
// حد ضررِ پورتفوی، پالتوی دستور، جستجوی نماد) هر کدام URL خودشان را می‌زدند.
// آن‌ها کلیدِ کوئریِ جدا داشتند، پس هر کدام یک *درخواستِ مستقل* می‌فرستادند و
// بدنهٔ ۴ مگابایتی چند بار رویِ سیمِ localhost و چند بار در JSON.parse/zdِ
// دستگاهِ کاربر می‌نشست. این فایل یک کوئری با یک کلید می‌سازد؛ بقیه با `select`
// از همان داده می‌خوانند.
//
// و مهم‌تر: پولینگِ پس از اولین بار **دلتا** است. سرور در `market_state` می‌داند
// کدام نماد از کدام ویرایش تکان خورده، پس پنجره فقط همان ردیف‌ها را می‌گیرد و
// اینجا در جای خودشان جا می‌نشینند. اندازه‌گیری ۱۴۰۵-۰۷-۱۴ رویِ بانکِ کاری:
// بدنهٔ کامل ۴٫۱MB (gzip ۵۶۴KB) در برابرِ دلتایِ ۲۰۰ نماد = ۱۴۲KB
// (gzip ۱۷KB) و در سیکلِ بی‌تغییری ۱۵۸ بایت.
//
// سه درِ ایمنی که «سریع‌تر» را به «غلط‌تر» تبدیل نمی‌کند:
//   ۱) اگر `count` سرور با تعدادِ ردیفِ ما نخورد، merge رها می‌شود و بدنۀ
//      کامل گرفته می‌شود (ردیفِ کم‌یا‌زیاده از دلتا قابل اثبات نیست).
//   ۲) هر پاسخِ غیرمنتظره (۴۰۴ روی نسخهٔ قدیمیِ سرور، zod fail، خطای شبکه)
//      یک‌بار به مسیرِ کامل برمی‌گردد؛ بی‌دلتا بهتر از دلتایِ ناقص.
//   ۳) در حالتِ `unchanged` همان آرایۀ قبلی برگردانده می‌شود — ارجاعِ یکسان
//      یعنی TanStack هیچ رندرِ تازه‌ای نمی‌سازد.
import { useQuery, type QueryObserverOptions } from '@tanstack/react-query';
import { http, HttpError } from '@shared/api/http';
import {
  MarketFeedSchema,
  MarketDeltaSchema,
  type MarketDelta,
  type MarketFeed,
  type MarketRow,
} from '@shared/types/marketRow';
import { effectivePollMs } from '@shared/lib/marketHours';

export const MARKET_FEED_KEY = ['market-feed'] as const;

let rows: MarketRow[] = [];
let indexBy = new Map<string, number>();
let rev = -1;
let meta: MarketFeed['meta'] = null;
let counts = { count: 0, live_count: 0, fossil_count: 0 };
/** سرورِ بی‌/api/market/delta (نسخۀ قدیمیِ نصب‌شده) ⇒ تا پایانِ عمرِ تب کامل می‌گیریم. */
let deltaUnsupported = false;

function snapshot(): MarketFeed {
  return { status: 'success', data: rows, meta, ...counts };
}

function adopt(f: MarketFeed): MarketFeed {
  rows = f.data ?? [];
  indexBy = new Map(rows.map((r, i) => [r.ins_code ?? `#${i}`, i]));
  counts = {
    count: f.count ?? rows.length,
    live_count: f.live_count ?? 0,
    fossil_count: f.fossil_count ?? 0,
  };
  meta = f.meta ?? null;
  // بدنهٔ کامل **همراه rev خودش** می‌آید (سرور آن را پیش از ساختن می‌خواند)،
  // پس پولینگِ بعدی دقیقاً از همین نقطه دلتا می‌خواهد. بی‌rev هر دور یک
  // بدنۀ ۴ مگابایتی می‌شد — یعنی همان وضعیتِ پیش از حالتِ داغ.
  rev = typeof f.rev === 'number' ? f.rev : -1;
  return f;
}

type Delta = Extract<MarketDelta, { status: 'delta' }>;

function applyDelta(r: Delta): boolean {
  const next = rows.slice();
  for (const row of r.rows) {
    const code = row.ins_code;
    if (!code) return false;                 // بی‌کلید ⇒ merge ممکن نیست
    const i = indexBy.get(code);
    if (i === undefined) {
      indexBy.set(code, next.length);
      next.push(row);
    } else {
      next[i] = row;
    }
  }
  // «درِcount»: سرور می‌گوید تابلو چند ردیف است. اگر با ما فرق داشت، ردیفی
  // آمده یا رفته که دلتا آن را ندارد — merge را ول می‌کنیم و کامل می‌خواهیم.
  if (r.count != null && r.count !== next.length) return false;
  rows = next;
  rev = r.rev;
  if (r.meta) meta = r.meta;
  counts = {
    count: r.count ?? counts.count,
    live_count: r.live_count ?? counts.live_count,
    fossil_count: r.fossil_count ?? counts.fossil_count,
  };
  return true;
}

async function fetchFull(signal?: AbortSignal): Promise<MarketFeed> {
  return adopt(await http<MarketFeed>('/api/market', { schema: MarketFeedSchema, signal }));
}

async function fetchFeed(signal?: AbortSignal): Promise<MarketFeed> {
  if (rev < 0 || deltaUnsupported) return fetchFull(signal);
  let d: MarketDelta;
  try {
    d = await http<MarketDelta>(`/api/market/delta?since=${rev}`, {
      schema: MarketDeltaSchema,
      signal,
    });
  } catch (e) {
    if (e instanceof HttpError && e.status === 404) deltaUnsupported = true;
    // هر خطایِ دیگر (۵xx، zod، قطعیِ نخ) هم باید تابلو را زنده نگه دارد:
    // یک دورِ کامل، و اگر آن هم شکست خطا بالا می‌رود تا UI صادقانه بخواند.
    return fetchFull(signal);
  }
  if (d.status === 'unchanged') {
    return snapshot();
  }
  if (d.status === 'delta' && applyDelta(d)) {
    return snapshot();
  }
  return fetchFull(signal);
}

/** گزینه‌هایِ کوئریِ مشترکِ تابلو. فقط پولینگ و `select` از مصرف‌کننده فرق می‌کند. */
export function marketFeedOptions<T = MarketFeed>(
  pollMs: number,
  paused: boolean,
  extra?: Partial<QueryObserverOptions<MarketFeed, Error, T>>,
): QueryObserverOptions<MarketFeed, Error, T> {
  return {
    queryKey: MARKET_FEED_KEY,
    queryFn: (ctx: { signal?: AbortSignal }) => fetchFeed(ctx.signal),
    refetchInterval: paused ? false : () => effectivePollMs(pollMs),
    staleTime: Math.min(Math.max(pollMs - 1_000, 1_000), 4_000),
    gcTime: 5 * 60_000,
    refetchOnWindowFocus: false,
    ...extra,
  } as unknown as QueryObserverOptions<MarketFeed, Error, T>;
}

/** همان تابلو، بی‌درخواستِ دوم: مصرف‌کننده‌هایِ فرعی با select از این می‌خوانند. */
export function useMarketFeedShared<T>(select: (f: MarketFeed) => T, pollMs = 5_000) {
  return useQuery<MarketFeed, Error, T>(
    marketFeedOptions<T>(pollMs, false, {
      select,
      // پولینگِ این مشاهده‌گر نه؛ صاحبِ ریتم، تابلو است. بیرونِ ساعتِ بازار
      // که هیچ ناظرِ فعالی نیست، خودِ همین کوئری با ریتمِ آرام تازه می‌شود.
      refetchInterval: () => effectivePollMs(Math.max(pollMs, 60_000)),
    }),
  );
}

/** تست‌ها/حالتِ سخت: آینه‌یِ RAMِ کلاینت را خالی می‌کند تا دورۀ بعد بدنۀ کامل بیاید. */
export function resetMarketFeedMirror() {
  rows = [];
  indexBy = new Map();
  rev = -1;
  meta = null;
  counts = { count: 0, live_count: 0, fossil_count: 0 };
  deltaUnsupported = false;
}

export function marketFeedMirrorSize() {
  return { rows: rows.length, rev };
}
