// features/master/api/useFtsFunnel.ts — مصرف‌کنندۀ /api/funnel
//
// پیش از این همین فایل خوراکِ تابلو و اسکرینر را می‌گرفت، بودجۀ «۶۰ نماد» را
// می‌چید، برای هر کدام /api/fts می‌زد و درِ آخر `buildFunnel` حکمِ نهایی را درِ
// مرورگر می‌ساخت. یعنی دومین داور. حالا تنها کاری که می‌کند این است:
//   درخواستِ زنجیره + حالتِ بنیادی  ➔  /api/funnel  ➔  funnelFromApi()
// و هر آنچه جدول می‌خواند از پاسخِ سرور می‌آید. هیچ شمارشِ FTS درِ کلاینت
// حساب نمی‌شود؛ نگاشتِ نام‌ها درِ `lib/funnelView.ts` است و بس.
import { useMemo } from 'react';
import { useSearchParams } from 'react-router';
import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';
import { sessionPollMs } from '@shared/lib/marketHours';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { useTapeStore } from '@features/market/stores/tapeStore';
import {
  DEFAULT_FUNNEL_OPTIONS,
  type Funnel,
  type FunnelMode,
  type FunnelOptions,
  type FunnelStage,
  type FunnelStageKey,
  type StageSummary,
  type TapeFreshness,
  type TreePreset,
} from '../lib/ftsFunnel';
import { funnelFromApi, type ApiPayload } from '../lib/funnelView';
import { useFunnelPrefsStore, type FundStrictness } from '../stores/funnelPrefsStore';

export type FunnelRequest = {
  preset: TreePreset;
  chain: string[];
  fundMode: FundStrictness;
  exceptions: Record<string, string[]>;
};

const EMPTY_SUM: StageSummary = { pass: 0, reject: 0, pending: 0, unavailable: 0, not_required: 0 };
const emptyStage = (key: FunnelStageKey): FunnelStage => ({
  key, entries: [], steps: [], dropped: 0, rejected: 0, unmeasured: 0, notRequired: 0,
  ruled: 0, pending: [], summary: { ...EMPTY_SUM },
});

const EMPTY: Funnel = {
  mode: 'reverse', tape: 'unavailable',
  techCoverage: { universe: 0, live: 0, fromScreen: 0, none: 0 },
  stages: {
    tape: emptyStage('tape'),
    technical: emptyStage('technical'),
    fundamental: emptyStage('fundamental'),
    handover: emptyStage('handover'),
  },
  boardScope: 0, total: 0, asOf: null,
  marketUniverse: 0, excludedCount: 0, exclusions: [], exclusionCounts: {},
  exclusionLabels: {},
  counts: {
    tape: { ...EMPTY_SUM },
    technical: { ...EMPTY_SUM },
    fundamental: { ...EMPTY_SUM },
    handover: { ...EMPTY_SUM },
  },
  targets: { initial: 50, watchlist: 10, basketMin: 5, basketMax: 7 },
};

export function funnelQueryKey(req: FunnelRequest): string[] {
  return ['funnel', req.preset, req.chain.join(','), req.fundMode,
          JSON.stringify(req.exceptions)];
}

/** درخواستِ قیف از سرور. `mode` فقط نمایشِ ریتمِ کشف است (معکوس/مرور) و داوری
 *  نیست؛ همان را prefs نگه می‌دارد. */
export function useFtsFunnel(
  preset: TreePreset = 'trend',
  overrides: Partial<FunnelRequest> = {},
): {
  funnel: Funnel;
  mode: FunnelMode;
  tape: TapeFreshness;
  queue: { symbols: string[]; beyondCap: number };
  tech: { wanted: number; resolved: number; loading: boolean };
  /** پیشرفتِ اسکنِ تکنیکال درِ پاسخِ سرور — برایِ خطِ «چرا بعضی در انتظارند» */
  scan: { pending: number; running: boolean; queued: number; done: number };
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  hasData: boolean;
  retry: () => void;
  basket: Set<string>;
  quickFilters: string[];
  opts: FunnelOptions;
  request: FunnelRequest;
} {
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const mode = useFunnelPrefsStore((s) => s.mode);
  const fundMode = useFunnelPrefsStore((s) => s.fundMode);
  const chainPref = useFunnelPrefsStore((s) => s.chain);
  const exceptions = useFunnelPrefsStore((s) => s.exceptions);
  const opts: FunnelOptions = {
    ...DEFAULT_FUNNEL_OPTIONS,
    ...useFunnelPrefsStore.getState(),
  };
  const portfolio = usePortfolio();
  // `?chain=` درِ URL باید بر انتخابِ ذخیره‌شده بردگی کند، وگرنه لینکِ
  // «برو به این زنجیره» (stepper/StrategyTree/کاوشِ مرورگر) همان جدولِ خالیِ
  // custom را می‌دهد. سنجشِ ۱۴۰۵-۰۷-۱۸: `?preset=custom&chain=f_clock` رویِ API
  // عبورِ ۵۴ نماد می‌داد و جدولِ UI ۲۸۱۲ — یعنی زنجیرۀِ URL هرگز خوانده نمی‌شد.
  // بی‌`chain` درِ URL، همان رفتارِ پیشین (زنجیرۀِ کاربر درِ builder).
  const [searchParams] = useSearchParams();
  const urlChain = useMemo(() => {
    const raw = searchParams.get('chain');
    if (!raw) return null;
    const ids = raw.split(',').map((s) => s.trim()).filter(Boolean);
    return ids.length ? ids : null;
  }, [searchParams]);

  const request = useMemo<FunnelRequest>(() => ({
    preset,
    chain: overrides.chain ?? (preset === 'custom' ? (urlChain ?? chainPref) : []),
    fundMode: overrides.fundMode ?? fundMode,
    exceptions: overrides.exceptions ?? exceptions,
    ...overrides,
  }), [preset, overrides, urlChain, chainPref, fundMode, exceptions]);

  const q = useQuery({
    queryKey: funnelQueryKey(request),
    queryFn: (ctx) => http<ApiPayload>('/api/funnel', {
      method: 'POST',
      // لغوِ درخواستِ کهنه: هر پاسخِ قیف چندِ مگابایت است (سنجشِ زنده: ۷٫۷ تا
      // ۱۰٫۹ مگابایت درِ هر کلیک). بی‌`signal`، با عوض‌کردنِ سریعِ preset آن
      // بدنه‌ها تا آخر دانلود می‌مانند و می‌توانند *بعدِ* پاسخِ تازه بنشینند.
      signal: ctx.signal,
      body: { preset: request.preset, chain: request.chain, fund_mode: request.fundMode,
              exceptions: request.exceptions },
    }),
    // کلیدِ تازه = پاسخِ تازه، و بی‌این خط جدولِ مسلطِ قیف برایِ چند صدمیلی‌ثانیه
    // به صفر می‌افتاد («universe: ۰») و کاربر فکر می‌کرد بازار خالی است. پاسخِ
    // قبلی رویِ صفحه می‌ماند تا جدید بنشیند؛ markerِ loading هم همین‌جا دیده
    // می‌شود، پس «کهنه» با «تازه» قاطی نمی‌شود.
    placeholderData: keepPreviousData,
    // ریتمِ تازه‌سازی دیگر ثابتِ ۶۰ ثانیه نیست: درِ ساعتِ بازار ۲۰ ثانیه و
    // بیرونِ آن ریتمِ آرامِ تابلو (`sessionPollMs`) — و تا اسکنِ تکنیکال صف
    // داشته باشد ۵ ثانیه، وگرنه «در حال محاسبه» فقط یک نوشته می‌ماند و نمادها
    // جلویِ چشمِ کاربر جابه‌جا نمی‌شوند.
    refetchInterval: (query) => {
      const ts = query.state.data?.tech_scan;
      if (ts?.running || (ts?.pending_symbols ?? 0) > 0) return 5_000;
      return sessionPollMs(20_000);
    },
    staleTime: 5_000,
  });

  const funnel = useMemo<Funnel>(() => (q.data ? funnelFromApi(q.data, mode) : EMPTY),
                                 [q.data, mode]);
  const universe = q.data?.universe?.joined ?? 0;
  // «سنجیده شده» = هر نمادی که گامِ تکنیکال درباره‌اش حکمی نوشته است. آنکه
  // تابلو ردش کرده به این گام نرسیده (`not_required`) و درِ شمار حساب نمی‌آید؛
  // این تقسیمِ شمارش است، نه داوریِ تازه.
  const tc = funnel.counts.technical;
  const resolved = tc.pass + tc.reject + tc.pending + tc.unavailable;

  return {
    funnel,
    mode,
    tape: funnel.tape,
    // بودجۀ /api/fts دیگر معنا ندارد: تکنیکالِ هر نماد درِ همان پاسخِ قیف است.
    queue: { symbols: [], beyondCap: 0 },
    tech: { wanted: universe, resolved, loading: q.isFetching },
    scan: {
      pending: q.data?.tech_scan?.pending_symbols ?? 0,
      running: !!q.data?.tech_scan?.running,
      queued: q.data?.tech_scan?.queued ?? 0,
      done: q.data?.tech_scan?.done ?? 0,
    },
    loading: q.isPending,
    /** پاسخِ رویِ صفحه پاسخِ *قبلی* است و تازه‌اش در راه است — باید دیده شود،
     *  وگرنه keepPreviousData یعنی «کهنه» بی‌برچسب. */
    refreshing: !!q.isPlaceholderData || q.isFetching,
    error: q.error ? String((q.error as Error).message ?? q.error) : null,
    /** آیا همین حالا دادهٔ معتبری رویِ صفحه هست؟ مصرف‌کننده با این، «خطا» را از
     *  «خالی» جدا می‌کند: خطا با دادهٔ قبلی ⇒ بنرِ کنارِ جدول، نه empty-state. */
    hasData: !!q.data,
    /** Retryِ همان query — دکمهٔ بی‌اثر نه؛ همان fetchِ واقعی را دوباره می‌زند. */
    retry: () => void q.refetch(),
    // سبد از همان پاسخِ /api/selection/portfolio خوانده می‌شود (decisions)،
    // نه از فرضِ آرایه — آن ساختار { status, decisions, counts, limits } است.
    basket: new Set(((portfolio.data as { decisions?: Array<{ symbol: string }> } | undefined)
      ?.decisions ?? []).map((d) => d.symbol)),
    quickFilters,
    opts,
    request,
  };
}
