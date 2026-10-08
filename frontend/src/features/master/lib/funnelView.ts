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
    TreePreset,
} from './ftsFunnel';

export type ApiWhy = { code?: string; text?: string; stage?: string; seq?: number;
  filter_id?: string; status?: StageStatus; reason_code?: string; human_reason?: string;
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

export type ApiPayload = {
  status: string; message?: string;
  engine_version?: string; ruleset_version?: string; as_of?: number;
  preset?: TreePreset; chain?: string[]; fund_mode?: string;
  universe?: { board: number; screened: number; joined: number };
  stages?: Record<FunnelStageKey, {
    steps?: ApiStep[]; input?: number; matched?: number; removed?: number;
    counts?: Partial<Record<StageStatus, number>>; mode?: string }>;
  entries?: Partial<Record<FunnelStageKey, ApiRow[]>>;
  timeline?: Record<string, ApiWhy[]>;
  handover?: Array<Record<string, unknown> & { symbol: string }>;
};

const STAGES: readonly FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];
const IND_KEYS = ['i1', 'i2', 'i3', 'i4', 'i5'] as const;

function markOf(v: StageStatus | boolean | null | undefined): StageStatus {
  if (v === true || v === 'pass') return 'pass';
  if (v === false || v === 'reject') return 'reject';
  if (v === 'pending') return 'pending';
  return 'unavailable';
}

function summaryOf(rows: Candidate[]): Record<StageStatus, number> {
  const out: Record<StageStatus, number> = { pass: 0, reject: 0, pending: 0, unavailable: 0 };
  for (const r of rows) for (const k of STAGES) if (r.status[k]) out[r.status[k]] += 1;
  return out;
}

/** یک ردیفِ API ⇒ همان چیزی که `Cell` می‌خواند. `row`/`screen` ساختگی‌اند
 *  ولی هیچ مقدارِ تازه‌ای نمی‌سازند: هر دو از ستون‌هایِ خودِ پاسخ پر می‌شوند. */
function toCandidate(r: ApiRow): Candidate {
  const status = {} as Record<FunnelStageKey, StageStatus>;
  const why = {} as Record<FunnelStageKey, string>;
  for (const k of STAGES) {
    const raw = (r.status as Record<string, StageStatus> | undefined)?.[k];
    status[k] = raw ?? 'unavailable';
    why[k] = (r.why?.[k] ?? []).map((w) => w.text || w.human_reason || '')
      .filter(Boolean)
      .join(' · ');
  }
  const row = {
    symbol: r.symbol, name: r.name ?? '', sector_name: r.sector ?? '',
    p_last: r.last ?? null, p_closing: r.closing ?? null,
    percent_change: r.change_pct ?? null, vol_ratio: r.vol_ratio ?? null,
    is_live: r.is_live ?? true,
  } as unknown as MarketRow;
  const screen = {
    symbol: r.symbol, name: r.name ?? '', sector_name: r.sector ?? '',
    score: r.score ?? null, pricing_mode: r.pricing_mode ?? null,
    excluded: !!r.excluded, exclusion_reasons: r.exclusion_reasons ?? '',
    rev_growth: r.ind_values?.i1 ?? null, eps_last: r.ind_values?.i2 ?? null,
    gross_margin: r.ind_values?.i3 ?? null, sales_to_mcap: r.ind_values?.i4 ?? null,
    tech_trend_w: r.weekly ?? null, tech_trend_d: r.daily ?? null,
    tech_matrix_decision: r.matrix ?? null, tech_status: r.tech_status ?? null,
    tech_fib_zone: r.fib_zone ?? null, tech_hourglass_active: r.hourglass ?? null,
    assembly_veto: !!r.assembly_veto,
  } as unknown as FtsScreenRow;
  return {
    symbol: r.symbol, name: r.name ?? '', sector: r.sector ?? '', kind: 'stock',
    row, screen, patterns: r.patterns ?? [],
    status, why,
    score: r.score ?? null,
    trendW: r.weekly ?? null, trendD: r.daily ?? null,
    dailyStrategy: r.branch ?? null,
    setups: (r.evidence ?? []).join(' + '),
    technicalPoints: r.tech_points ?? null,
    inds: IND_KEYS.map((k) => markOf(r.inds?.[k])),
    techSource: r.matrix || r.weekly ? 'screen' : null,
    jetEvidence: null,
    assemblyVeto: !!r.assembly_veto,
    assemblyWhy: r.assembly_why ?? '',
    screenRank: r.rank ?? null,
  };
}

export function funnelFromApi(payload: ApiPayload, fallbackMode: FunnelMode = 'reverse'): Funnel {
  const none: ApiRow[] = [];
  const stages = {} as Funnel['stages'];
  const counts = {} as Funnel['counts'];
  for (const key of STAGES) {
    const rows = (payload.entries?.[key] ?? none).map((r) => toCandidate(r));
    const sum = summaryOf(rows);
    const step = payload.stages?.[key];
    stages[key] = {
      key, entries: rows,
      dropped: key === 'tape' ? (step?.removed ?? 0) : Math.max(0, (step?.input ?? rows.length) - rows.length),
      rejected: sum.reject, unmeasured: sum.unavailable + sum.pending,
      pending: rows.filter((r) => r.status[key] === 'pending'),
      summary: sum,
    };
    counts[key] = sum;
  }
  const asOf = payload.universe?.joined ?? 0;
  return {
    mode: fallbackMode,
    tape: (payload.as_of && Date.now() / 1000 - payload.as_of < 900) ? 'live' : 'stale',
    techCoverage: { universe: asOf, live: 0, fromScreen: asOf, none: 0 },
    stages,
    boardScope: payload.universe?.board ?? 0,
    total: payload.universe?.joined ?? 0,
    counts,
    targets: { initial: 50, watchlist: 10, basketMin: 5, basketMax: 7 },
  };
}
