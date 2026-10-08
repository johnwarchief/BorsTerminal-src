// features/master/lib/funnelView.ts — نگاشتِ DTO ⇒ ViewModel؛ تنها پلِ قیف به UI
//
// قانونِ مأموریت: فرانت نباید FTS را دوباره داوری کند. این فایل هیچ `if`
// قاعده‌ای ندارد: فقط نام‌هایِ پاسخِ `/api/funnel` را به همان چیزی تبدیل می‌کند
// که جدول می‌خواند. جایی که پاسخ چیزی ندارد، `null` می‌ماند — نه حدس.
import type { MarketRow } from '@shared/types/marketRow';
import type { FtsScreenRow } from '@features/fundamental/api/useFtsScreen';
import type {
  Candidate,
  Funnel,
  FunnelMode,
  FunnelStageKey,
  StageStatus,
  StageSummary,
  TreePreset,
  UniverseExclusion,
} from './ftsFunnel';

export type ApiWhy = { code?: string; text?: string; stage?: string; seq?: number;
  label?: string; filter_id?: string; status?: StageStatus; reason_code?: string; human_reason?: string;
  input_count?: number | null; output_count?: number | null; source?: string;
  source_ref?: string; formula_version?: string; parameter_set?: Record<string, unknown> };

/** یک ردیفِ `entries.<stage>` درِ پاسخِ /api/funnel. */
export type ApiRow = {
  symbol: string; name?: string; sector?: string; last?: number | null;
  closing?: number | null; change_pct?: number | null; vol_ratio?: number | null;
  patterns?: string[]; status?: Partial<Record<FunnelStageKey, StageStatus>> | Record<string, StageStatus>;
  why?: Record<string, ApiWhy[]>; chain?: string[]; score?: number | null;
  primary_score?: number | null; weekly?: string | null; daily?: string | null;
  branch?: string | null; matrix?: string | null; tech_status?: string | null;
  tech_points?: number | null; evidence?: string[]; fib_zone?: string | null;
  hourglass?: boolean | null;
  inds?: Record<string, StageStatus | boolean | null>;
  ind_values?: Record<string, number | null>; pricing_mode?: string | null;
  excluded?: boolean; exclusion_reasons?: string; assembly_veto?: boolean;
  assembly_why?: string; as_of?: number | null; is_live?: boolean | null;
  /** رتبۀ رسمیِ بک‌اند (/api/screener) — حملِ عدد است، نه رتبۀ تازه */
  rank?: number | null;
};

export type ApiStep = {
  stage: string; seq?: number; filter_id?: string; label?: string; input_count: number;
  matched_count: number; removed_count: number; unmeasured_count?: number;
  parameter_set?: Record<string, unknown>; source_ref?: string; formula_version?: string;
  backend_impl?: string; status?: StageStatus;
};

export type ApiCell = {
  status?: StageStatus; reason_code?: string; human_reason?: string;
  stage_ref?: string; canonical?: StageStatus; display_rank?: number | null;
  exceptions?: string[];
};

export type ApiPayload = {
  status: string; message?: string;
  engine_version?: string; ruleset_version?: string; as_of?: number;
  preset?: TreePreset; chain?: string[]; fund_mode?: string;
  /** `board` ردیف خامِ تابلو است (با تکراری)، `market` جامعۀ نمادها (یک‌شده)،
   *  `screening` فقط زنده‌ها/واجدِ شرایط، `excluded` باقیِ نمادها. همیشۀ
   *  `market = screening + excluded` درِ گاردِ بک‌اند بسته شده. */
  universe?: { board: number; screened: number; joined: number; duplicate_rows?: number;
    market?: number; screening?: number; excluded?: number;
    exclusion_counts?: Record<string, number>; exclusion_labels?: Record<string, string> };
  /** علتِ خروجِ تک‌تکِ نمادهایِ بیرون از جامعۀ غربالگری (پاسخِ موتور) */
  exclusions?: Array<{ symbol: string; name?: string; sector?: string;
    last?: number | null; reason_code?: string; human_reason?: string;
    st_code?: string | null; st_title?: string | null;
    stop_state?: string | null; is_live?: boolean | null }>;
  stages?: Record<FunnelStageKey, {
    steps?: ApiStep[]; input?: number; matched?: number; removed?: number;
    counts?: Partial<Record<StageStatus, number>>; mode?: string }>;
  entries?: Partial<Record<FunnelStageKey, ApiRow[]>>;
  /** وضعیتِ هر چهار گام برایِ تک‌تکِ نمادهایِ جامعۀ ورودی — منبعِ canonicalِ
   *  «این نماد درِ این گام چه حکمی دارد». خطِ زمانِ خودِ نماد با
   *  `GET /api/funnel/trace?symbol=` می‌آید و درِ این پاسخ نیست. */
  status_matrix?: Record<string, Partial<Record<FunnelStageKey, ApiCell>>>;
  /** شمارشِ وضعیت‌هایِ هر گام رویِ کلِ جامعۀ ورودی — جمعش با `universe.joined`
   *  باید بخواند (گاردِ مالک: هیچ نمادی بی‌حکم نمی‌ماند). */
  coverage?: Record<FunnelStageKey, Partial<Record<StageStatus, number>>>;
  /** وضعیتِ اسکنِ پس‌زمینۀ تکنیکال: نمادهایی که به گام رسیده‌اند ولی داوری‌شان
   *  هنوز ساخته نشده. نبودش یعنی همه ساخته شده، نه اینکه چیزی پنهان است. */
  tech_scan?: { pending_symbols?: number; running?: boolean; queued?: number;
    done?: number; failed?: number; in_flight?: number; error?: string | null };
  timeline?: Record<string, ApiWhy[]>;
  handover?: Array<Record<string, unknown> & { symbol: string }>;
};

const STAGES: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];
const IND_KEYS = ['i1', 'i2', 'i3', 'i4', 'i5'] as const;

function markOf(v: StageStatus | boolean | null | undefined): StageStatus {
  if (v === true || v === 'pass') return 'pass';
  if (v === false || v === 'reject') return 'reject';
  if (v === 'pending') return 'pending';
  if (v === 'not_required') return 'not_required';
  return 'unavailable';
}

function summaryOf(v: Partial<Record<StageStatus, number>> | undefined): StageSummary {
  return {
    pass: v?.pass ?? 0, reject: v?.reject ?? 0, pending: v?.pending ?? 0,
    unavailable: v?.unavailable ?? 0, not_required: v?.not_required ?? 0,
  };
}

/** جمعِ پنج شمارش — همان چیزی که باید با جامعۀ ورودی بخواند. */
export function sumSummary(s: StageSummary): number {
  return s.pass + s.reject + s.pending + s.unavailable + s.not_required;
}

/** یک نماد ⇒ ردیفِ نمایشیِ یک گام.
 *
 *  `own` ردیفِ غنیِ *همین* گام است (ستون‌هایش مالِ همین مرحله‌اند) و `base`
 *  ردیفِ غنیِ هر گامِ دیگرِ همان نماد (نام، قیمت، …). `cells` سطرِ همان نماد درِ
 *  `status_matrix` است و حکمِ هر چهار گام را می‌دهد.
 *
 *  هیچ عددِ تازه‌ای ساخته نمی‌شود: ردیفی که پاسخ ندارد ⇒ `row`/`screen` برابر
 *  `null` و سلول‌ها «—» می‌شوند. حکم هم اول از matrix خوانده می‌شود؛ آنجا
 *  canonical است و ردیفِ غنی فقط عدد می‌آورد، نه داوری. */
function toCandidate(sym: string, own: ApiRow | undefined, base: ApiRow | undefined,
                    cells: Partial<Record<FunnelStageKey, ApiCell>>): Candidate {
  const r = own ?? base;
  const status = {} as Record<FunnelStageKey, StageStatus>;
  const why = {} as Record<FunnelStageKey, string>;
  const textOf = (row: ApiRow | undefined, k: FunnelStageKey) =>
    (row?.why?.[k] ?? []).map((w) => w.text || w.human_reason || '').filter(Boolean).join(' · ');
  for (const k of STAGES) {
    status[k] = cells[k]?.status ?? own?.status?.[k] ?? base?.status?.[k] ?? 'unavailable';
    why[k] = textOf(own, k) || textOf(base, k) || cells[k]?.human_reason || '';
  }
  const row: MarketRow | null = r ? {
    symbol: sym, name: r.name ?? '', sector_name: r.sector ?? '',
    p_last: r.last ?? null, p_closing: r.closing ?? null,
    percent_change: r.change_pct ?? null, vol_ratio: r.vol_ratio ?? null,
    is_live: r.is_live ?? true,
  } as unknown as MarketRow : null;
  const screen: FtsScreenRow | null = r ? {
    symbol: sym, name: r.name ?? '', sector_name: r.sector ?? '',
    score: r.score ?? null, pricing_mode: r.pricing_mode ?? null,
    excluded: !!r.excluded, exclusion_reasons: r.exclusion_reasons ?? '',
    rev_growth: r.ind_values?.i1 ?? null, eps_last: r.ind_values?.i2 ?? null,
    gross_margin: r.ind_values?.i3 ?? null, sales_to_mcap: r.ind_values?.i4 ?? null,
    tech_trend_w: r.weekly ?? null, tech_trend_d: r.daily ?? null,
    tech_matrix_decision: r.matrix ?? null, tech_status: r.tech_status ?? null,
    tech_fib_zone: r.fib_zone ?? null, tech_hourglass_active: r.hourglass ?? null,
    assembly_veto: !!r.assembly_veto,
  } as unknown as FtsScreenRow : null;
  // پنج شاخص: اگر بک‌اند مقدارش را داد همان است؛ اگر نداشت، وضعیتِ خودِ گامِ
  // بنیادی بر هر پنج نشسته (not_required یعنی «به این گام نرسید»، نه «رد»).
  const inds = IND_KEYS.map((k) => (r?.inds
    ? markOf(r.inds[k])
    : markOf(cells.fundamental?.status ?? 'unavailable')));
  return {
    symbol: sym, name: r?.name ?? '', sector: r?.sector ?? '', kind: 'stock',
    row, screen, patterns: r?.patterns ?? [],
    status, why,
    score: r?.score ?? null,
    trendW: r?.weekly ?? null, trendD: r?.daily ?? null,
    dailyStrategy: r?.branch ?? null,
    setups: (r?.evidence ?? []).join(' + '),
    technicalPoints: r?.tech_points ?? null,
    inds,
    techSource: r && (r.matrix || r.weekly) ? 'screen' : null,
    jetEvidence: null,
    assemblyVeto: !!r?.assembly_veto,
    assemblyWhy: r?.assembly_why ?? '',
    screenRank: r?.rank ?? null,
  };
}

/** ردیف‌هایِ هر گام = **کلِ جامعۀ ورودی**، نه فقط رسیدگان. قاعدۀ مالک: هیچ
 *  نمادی بی‌حکم نمی‌ماند؛ آنکه به این گام نرسیده `not_required` می‌خورد و
 *  دلیلش (گامِ بازدارنده) درِ متنِ خودِ بک‌اند نوشته شده.
 *  `pending` از جدولِ اصلی جدا می‌نشیند تا با «رد» یکی خوانده نشود. */
export function funnelFromApi(payload: ApiPayload, fallbackMode: FunnelMode = 'reverse'): Funnel {
  const cached = BUILD_CACHE.get(payload);
  if (cached && cached.mode === fallbackMode) return cached.funnel;
  const funnel = build(payload, fallbackMode);
  // یک پاسخِ ۱۰مگابایتی را سه مصرف‌کننده می‌خواند (صفحهٔ گام، جدولِ چهارگام،
  // نشانگرِ سایدبار). بی‌این کش، نگاشتِ ۵٫۸ هزار نماد سه بار تکرار می‌شد.
  BUILD_CACHE.set(payload, { mode: fallbackMode, funnel });
  return funnel;
}

const BUILD_CACHE = new WeakMap<ApiPayload, { mode: FunnelMode; funnel: Funnel }>();

function build(payload: ApiPayload, fallbackMode: FunnelMode): Funnel {
  const matrix = payload.status_matrix ?? {};
  const richBy = {} as Record<FunnelStageKey, Map<string, ApiRow>>;
  for (const k of STAGES) {
    richBy[k] = new Map((payload.entries?.[k] ?? []).map((r) => [r.symbol, r]));
  }
  // ترتیبِ جامعۀ غربالگری از خودِ `status_matrix` می‌آید (همان ترتیبِ `joined`
  // درِ موتور)، **بیرون‌زدۀ نمادهایِ خارج از جامعه**: رأیِ مالک ۱۴۰۵-۰۷-۱۶ این
  // است که جدولِ گام‌ها با آنها شلوغ نشود؛ علتشان درِ `funnel.exclusions` و
  // بخشِ بازشوندهٔ خودش می‌نشیند. اگر پاسخی matrix نداشته باشد (پاسخِ قدیمی)،
  // نمادها از ردیف‌هایِ خودِ stages جمع می‌شوند — هیچ‌کدام جا نمی‌مانند.
  const excludedSyms = new Set((payload.exclusions ?? []).map((e) => e.symbol));
  const syms: string[] = [];
  const seen = new Set<string>();
  for (const sym of Object.keys(matrix)) {
    if (seen.has(sym) || excludedSyms.has(sym)) continue;
    seen.add(sym); syms.push(sym);
  }
  for (const k of STAGES) {
    for (const r of payload.entries?.[k] ?? []) {
      if (!seen.has(r.symbol) && !excludedSyms.has(r.symbol)) { seen.add(r.symbol); syms.push(r.symbol); }
    }
  }
  const baseOf = (sym: string) => richBy.tape.get(sym) ?? richBy.technical.get(sym)
    ?? richBy.fundamental.get(sym) ?? richBy.handover.get(sym);

  const stages = {} as Funnel['stages'];
  const counts = {} as Funnel['counts'];
  for (const key of STAGES) {
    // هر گام جدولِ **کلِ جامعۀ ورودی** را می‌گیرد، با ردیفِ غنیِ خودش اگر باشد.
    const rows = syms.map((sym) => toCandidate(sym, richBy[key].get(sym), baseOf(sym), matrix[sym] ?? {}));
    // شمارش از `coverage`ِ بک‌اند است. اگر پاسخِ قدیمی coverage نداشت، همین
    // ردیف‌ها شمرده می‌شوند — جمعِ ردیف‌ها، نه داوریِ تازه.
    const given = payload.coverage?.[key];
    const sum = given
      ? summaryOf(given)
      : (() => {
          const s: StageSummary = { pass: 0, reject: 0, pending: 0, unavailable: 0, not_required: 0 };
          // خارج از جامعه درِ پنج عددِ گام نیست (جدولِ گام فقط جامعۀ غربالگری
          // است)؛ بی‌این شرط، شمارشِ محلی با `coverage` نمی‌خواند.
          for (const c of rows) {
            const st = c.status[key];
            if (st !== 'not_in_universe') s[st] += 1;
          }
          return s;
        })();
    stages[key] = {
      key,
      // حملِ بی‌داوریِ گام‌هایِ درونیِ تابلو (شمارشِ ترتیب‌محور از موتور)
      steps: (payload.stages?.[key]?.steps ?? []).map((s) => ({
        seq: s.seq ?? 0, filter_id: s.filter_id ?? '', label: s.label ?? s.filter_id ?? '',
        input_count: s.input_count, matched_count: s.matched_count,
        removed_count: s.removed_count, unmeasured_count: s.unmeasured_count,
        source_ref: s.source_ref, formula_version: s.formula_version,
        parameter_set: s.parameter_set, status: s.status,
      })),
      entries: rows.filter((c) => c.status[key] !== 'pending'),
      dropped: sum.reject,
      rejected: sum.reject,
      unmeasured: sum.unavailable,
      notRequired: sum.not_required,
      ruled: sumSummary(sum),
      pending: rows.filter((c) => c.status[key] === 'pending'),
      summary: sum,
    };
    counts[key] = sum;
  }
  const screening = payload.universe?.screening ?? syms.length;
  const exclusions: UniverseExclusion[] = (payload.exclusions ?? []).map((e) => ({
    symbol: e.symbol, name: e.name ?? '', sector: e.sector ?? '', last: e.last ?? null,
    reasonCode: e.reason_code ?? '', humanReason: e.human_reason ?? '',
    stateCode: e.st_code ?? null, stateTitle: e.st_title ?? null,
    stopState: e.stop_state ?? null, isLive: e.is_live ?? null,
  }));
  const excludedCount = payload.universe?.excluded ?? exclusions.length;
  return {
    mode: fallbackMode,
    tape: (payload.as_of && Date.now() / 1000 - payload.as_of < 900) ? 'live' : 'stale',
    techCoverage: {
      universe: screening,
      live: Math.max(0, sumSummary(counts.technical) - counts.technical.not_required),
      fromScreen: 0,
      none: counts.technical.unavailable,
    },
    stages,
    boardScope: payload.universe?.board ?? 0,
    total: screening,
    marketUniverse: payload.universe?.market
      ?? payload.universe?.joined ?? screening + excludedCount,
    excludedCount,
    exclusions,
    exclusionCounts: payload.universe?.exclusion_counts ?? {},
    exclusionLabels: payload.universe?.exclusion_labels ?? {},
    counts,
    targets: { initial: 50, watchlist: 10, basketMin: 5, basketMax: 7 },
  };
}

/** جایِ یک نماد در چهار گام — از همان entriesِ پاسخِ سرور.
 *
 *  جایگزینِ `symbolStageProgress` است که قواعدِ قیف را رویِ تک‌ناماد درِ مرورگر
 *  دوباره اجرا می‌کرد. اینجا فقط وضعیت‌هایِ ثبت‌شدۀ سرور خوانده می‌شوند؛ اگر
 *  نماد درِ پاسخ نبود، هر چهار گام `unknown` است (نه رد، نه قبول). */
export function stageProgressFor(
  funnel: Funnel, symbol: string,
): { key: FunnelStageKey; state: 'passed' | 'blocked' | 'waiting' | 'not_required'
                | 'not_in_universe' | 'unknown'; why: string }[] {
  // نمادِ خارج از جامعۀ غربالگری درِ هیچ جدولِ گامی نیست (رأیِ مالک)؛ اگر اینجا
  // بی‌کار می‌ماند، سایدبار او را «سنجیده نشده» می‌خواند — دقیقاً همان چیزی که
  // ممنوع است. علتش را از `exclusionsِ` خودِ سرور می‌گیرد.
  const out = funnel.exclusions.find((e) => e.symbol === symbol);
  if (out) {
    const why = out.humanReason || out.reasonCode || '';
    return STAGES.map((key) => ({ key, state: 'not_in_universe' as const, why }));
  }
  // هر گام ردیفِ خودش را دارد و status همان گام را می‌گوید؛ پس وضعیت‌ها از
  // همهٔ ردیف‌هایِ همین نماد جمع می‌شوند (نخستِ یافت‌شده کافی نبود: ردیفِ گامِ
  // تابلو فقط status.tape را دارد و چراغِ تکنیکال unknown می‌ماند).
  let found: Candidate | null = null;
  const merged: Record<FunnelStageKey, StageStatus> = {
    tape: 'unavailable', technical: 'unavailable', fundamental: 'unavailable', handover: 'unavailable',
  };
  for (const key of STAGES) {
    const hit = funnel.stages[key].entries.find((e) => e.symbol === symbol);
    if (!hit) continue;
    found = found ?? hit;
    if (hit.status[key]) merged[key] = hit.status[key];
  }
  return STAGES.map((key) => {
    const st = merged[key] === 'unavailable' ? found?.status[key] : merged[key];
    // «لازم نبود» یک حکمِ صریح است (گامِ پیشین جلوش را گرفته) و با «بی‌حکم/unknown»
    // یکی نیست — قاعدۀ مالک: هیچ نمادی با «سنجیده نشده» از قیف بیرون نمی‌ماند.
    const state: 'passed' | 'blocked' | 'waiting' | 'not_required' | 'not_in_universe' | 'unknown' =
      st === 'pass' ? 'passed'
        : st === 'reject' ? 'blocked'
        : st === 'pending' ? 'waiting'
        : st === 'not_required' ? 'not_required'
        : st === 'not_in_universe' ? 'not_in_universe' : 'unknown';
    const hit = funnel.stages[key].entries.find((e) => e.symbol === symbol);
    return { key, state, why: hit?.why[key] || found?.why[key] || '' };
  });
}
