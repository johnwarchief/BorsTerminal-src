// features/master/api/useFtsFunnel.ts -- «Mode Resolver» + دو پاسِ کشفِ نماد FTS
//
// چرا هوکِ جدا: قیفِ چهارمرحله‌ای (`ui/FtsFunnelStages`)
// و سایدبارِ چپ، همه باید **همان** کاندیدها را ببینند.
// بی‌این، هر کامپوننت یک دورۀ خودش می‌ساخت — همان چیزی که `phaseMarksFor` درِ
// هاب می‌کرد (F همیشه «تایید»!). حالا هر سه از یک `Candidate[]` خوانده‌اند.
//
// جریان (#11):
//   خوراکِ تابلو + اسکرینرِ کدال + سبد
//     ➔ `funnelUniverse` (حالت: reverse = تابلو، review = کلِ اسکرینر)
//     ➔ `techQueryQueue` (بودجۀ `/api/fts` با رتبۀ رسمیِ بک‌اند، نه ترتیبِ تابلو)
//     ➔ `useFtsTechBoard` (رأیِ زنده)
//     ➔ `buildFunnel` (S ➔ T ➔ F ➔ M با واژگانِ چهارحالتي)
//
// کوئری‌ها درِ TanStack Query مشترک‌اند، پس صدازدنِ این هوک از دو کامپوننتِ
// هم‌زمان یک fetchِ دوباره نمی‌سازد؛ فقط شمارشِ خالصِ `buildFunnel` دو بار
// حساب می‌شود (O(universe)، بی‌هیچ کارِ شبکه‌ای).
import { useMemo } from 'react';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useFtsScreen } from '@features/fundamental/api/useFtsScreen';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { isMarketOpen } from '@shared/lib/marketHours';
import {
  buildFunnel,
  funnelUniverse,
  techQueryQueue,
  type Funnel,
  type FunnelMode,
  type FunnelOptions,
  type TapeFreshness,
  type TreePreset,
} from '../lib/ftsFunnel';
import { useFunnelPrefsStore } from '../stores/funnelPrefsStore';
import { TECH_QUERY_CAP, useFtsTechBoard } from './useFtsTechBoard';

export type FtsFunnelResult = {
  funnel: Funnel;
  mode: FunnelMode;
  tape: TapeFreshness;
  /** بودجۀ تکنیکال: چه کسی رأیِ زنده می‌گیرد و چند تا بیرونِ بودجه می‌مانند */
  queue: { symbols: string[]; beyondCap: number };
  tech: ReturnType<typeof useFtsTechBoard>;
  loading: boolean;
  /** سبدِ فعال — همان مجموعه‌ای که درِ `handover` توقف می‌دهد (#9) */
  basket: Set<string>;
  /** چیپ‌هایِ روشنِ تبِ تابلو — درِ reverse دربِ قیف را تعیین می‌کنند */
  quickFilters: string[];
  /** سه پیچِ دستِ مالک (کفِ بنیادی، سرنوشتِ سنجیده‌نشده، غربالگریِ تکنیکال) */
  opts: FunnelOptions;
};

// Phase پرفورمنس (N4-C): درِ /master دو مصرف‌کننده هم‌زمان این قیف را mount
// می‌کنند (سربرگِ مستر برایِ candidate + خودِ پنلِ قیف). useMemo هر instance
// جدا می‌شمارد، پس buildFunnel و funnelUniverse دو بار رویِ همان ورودیِ
// یکسان می‌دوند. این کشِ ماژول با برابریِ مرجعِ همان آرگومان‌ها، شمارش را
// به یک‌بار می‌رساند — بی‌هیچ تغییرِ خروجی. آرگومان‌ها همه از store/کوئری
// می‌آیند و مرجع‌شان تا تغییرِ واقعی پایدار است؛ گسترشِ [...quickFilters]
// حذف شد تا همین برابریِ مرجع برقرار بماند (تابلو همان آرایه را in-place
// عوض نمی‌کند — tapeRows فقط می‌خواند).
type BuildFunnelArgs = Parameters<typeof buildFunnel>;
let lastFunnelArgs: BuildFunnelArgs | null = null;
let lastFunnelResult: ReturnType<typeof buildFunnel> | null = null;

function sharedBuildFunnel(...args: BuildFunnelArgs): ReturnType<typeof buildFunnel> {
  if (lastFunnelArgs && lastFunnelArgs.length === args.length && lastFunnelArgs.every((v, i) => v === args[i])) {
    return lastFunnelResult as ReturnType<typeof buildFunnel>;
  }
  lastFunnelArgs = args;
  lastFunnelResult = buildFunnel(...args);
  return lastFunnelResult;
}

type UniverseArgs = Parameters<typeof funnelUniverse>;
let lastUniverseArgs: UniverseArgs | null = null;
let lastUniverseResult: ReturnType<typeof funnelUniverse> | null = null;

function sharedFunnelUniverse(...args: UniverseArgs): ReturnType<typeof funnelUniverse> {
  if (lastUniverseArgs && lastUniverseArgs.length === args.length && lastUniverseArgs.every((v, i) => v === args[i])) {
    return lastUniverseResult as ReturnType<typeof funnelUniverse>;
  }
  lastUniverseArgs = args;
  lastUniverseResult = funnelUniverse(...args);
  return lastUniverseResult;
}

export function useFtsFunnel(preset: TreePreset = 'custom'): FtsFunnelResult {  const feed = useMarketFeed();
  // یک درخواستِ مشترک با تبِ بنیادی (کلیدِ ۰ = کلِ universe). رویِ موبایل
  // resolverِ محلی `?limit` را جدی می‌گیرد، پس هر دو مصرف‌کننده باید «همه»
  // بخواهند وگرنه قیف از ۱۲۰ ردیفِ اول داوری می‌کند.
  const screen = useFtsScreen();
  const portfolio = usePortfolio();
  const cfg = useTapeStore((s) => s.tapeFilterConfig);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const fundFloor = useFunnelPrefsStore((s) => s.fundFloor);
  const unmeasured = useFunnelPrefsStore((s) => s.unmeasured);
  const techScreens = useFunnelPrefsStore((s) => s.techScreens);
  const mode = useFunnelPrefsStore((s) => s.mode);

  const opts = useMemo<FunnelOptions>(
    () => ({ fundFloor, unmeasured, techScreens }),
    [fundFloor, unmeasured, techScreens],
  );

  // تازگیِ خوراکِ تابلو (#16): بی‌ردیف یعنی «منبع نیست»، و بیرونِ ساعتِ بازار
  // یعنی داده از آخرینِ نشست است — هیچ‌کدام «رد» نیست.
  const boardRows = feed.data?.data ?? [];
  const tape: TapeFreshness = !boardRows.length ? 'unavailable' : isMarketOpen() ? 'live' : 'stale';

  // دو پاسِ عمدی: نخست جامعۀ ورود حساب می‌شود تا معلوم شود برایِ کدام نمادها
  // رأیِ تکنیکال لازم است، سپس `/api/fts` برایِ همان‌ها خوانده می‌شود. بی‌این،
  // درِ T هرگز بسته نمی‌شد چون اسکرینر فقط سقفِ واچ‌لیست را تحلیل کرده.
  // صف را `funnelUniverse` + `techQueryQueue` می‌چینند (رتبۀ رسمیِ بک‌اند) —
  // ترتیبِ تابلو با هر رفرش عوض می‌شود و «کی سنجیده شد» را قمار می‌کرد.
  const queue = useMemo(() => {
    const u = sharedFunnelUniverse(mode, boardRows, cfg, quickFilters, preset, screen.data?.data ?? []);
    return techQueryQueue(u.ordered, u.rank, TECH_QUERY_CAP);
  }, [mode, boardRows, cfg, quickFilters, preset, screen.data]);

  const tech = useFtsTechBoard(queue.symbols);

  const basket = useMemo(
    () => new Set((portfolio.data?.portfolio ?? []).map((h) => h.symbol)),
    [portfolio.data],
  );

  const funnelCtx = useMemo(
    () => ({
      mode,
      tape,
      screenAsOf: screen.data?.as_of ?? null,
      techAsOf: tech.asOf,
    }),
    [mode, tape, screen.data, tech.asOf],
  );

  const funnel = useMemo(
    () =>
      sharedBuildFunnel(boardRows, cfg, quickFilters, screen.data?.data ?? [], basket, preset, tech.map, opts, funnelCtx),
    [boardRows, screen.data, basket, cfg, quickFilters, preset, tech.map, opts, funnelCtx],
  );

  return {
    funnel,
    mode,
    tape,
    queue,
    tech,
    loading: feed.isLoading || screen.isLoading || tech.loading,
    basket,
    quickFilters: [...quickFilters],
    opts,
  };
}
