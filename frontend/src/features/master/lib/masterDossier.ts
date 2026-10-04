// features/master/lib/masterDossier.ts -- مدلِ برآیندِ تک‌ناماد (Round L)
// ترجمهٔ محض است، نه داوری: هر حکمی که اینجا خوانده می‌شود یا از `Candidate`
// مدلِ قیف می‌آید («تنها جایِ داوریِ کاندید») یا از payloadِ `/api/fts/{symbol}`.
// هیچ آستانه، هیچ وزن و هیچ نمرۀ تازه‌ای در این فایل ساخته نمی‌شود — اگر چیزی
// در دو منبع نباشد، `null` می‌ماند و UI آن را «سنجیده نشد» می‌گوید، نه «رد».
import {
  STAGE_KEYS,
  trendLabel,
  type Candidate,
  type FunnelStageKey,
  type StageStatus,
} from './ftsFunnel';
import { toFaDigits } from '@shared/lib/fmt';
import { isoToJalali } from '@shared/lib/jalaali';
import type { FtsPlanFeed } from '../api/useFtsPlan';
import { STOP_BASIS_FA } from '@features/technical/lib/levels';

export type DossierVerdict = 'confirmed' | 'watch' | 'wait' | 'reject' | 'insufficient';

/** واژگانِ نمایش — همان پنج حالتِ مالک، بی‌واژۀ تازه */
export const VERDICT_LABEL: Record<DossierVerdict, string> = {
  confirmed: 'تأیید شده',
  watch: 'واچ‌لیست',
  wait: 'در انتظار',
  reject: 'رد شده',
  insufficient: 'سنجیده نشد',
};

export const STAGE_LABEL: Record<FunnelStageKey, string> = {
  tape: 'S — تابلوخوانی',
  technical: 'T — تکنیکال',
  fundamental: 'F — بنیادی',
  handover: 'M — تحویل',
};

/** ستاپ‌های trend.matrix از موتور خروجِ chart.py — ترجمۀ رشته‌ای، نه داوریِ دوم */
const MATRIX_SETUP_FA: Record<string, string> = {
  JET_OR_PULLBACK_HOLD: 'جت یا پولبک',
  FIB_CHOCH_STEP_ENTRY: 'ورود پله‌ای فیبو/CHoCH',
  SWING_DOUBLE_BOTTOM_OR_RANGE: 'کف دوقلو یا رنج',
};

/** کدهای verdict درِ exit_engine (api/chart.py) — همان واژگانِ VERDICT_META درِ نشان‌ها */
const EXIT_VERDICT_FA: Record<string, string> = {
  stop: 'حد ضرر',
  exit: 'خروج',
  caution: 'احتیاط',
  hold: 'نگهداری',
  unknown: 'سنجیده نشد',
};

const STATUS_ICON: Record<StageStatus, string> = {
  pass: '✅',
  reject: '❌',
  pending: '⏳',
  unavailable: '○',
};

export type DossierStage = {
  key: FunnelStageKey;
  label: string;
  status: StageStatus;
  icon: string;
  /** دلیلِ همان مرحله، عینِ متنِ مدلِ قیف */
  why: string;
};

export type DossierFlow = {
  weekly: string;
  daily: string;
  setup: string | null;
  /** گیتِ هفتگی بسته است ⇒ روزانه جایگزینِ وتو نمایش داده نمی‌شود */
  gated: boolean;
  reason: string | null;
};

export type MasterDossier = {
  symbol: string;
  name: string;
  sector: string;
  /** آخرینِ تابلو — فقط وقتی ردیفِ زنده هست؛ بی‌ردیف `null` */
  last: number | null;
  percent: number | null;
  verdict: DossierVerdict;
  verdictText: string;
  /** مرحله‌ای که حکم را تعیین کرده، یا null وقتی نماد در جامعۀ قیف نیست */
  verdictStage: FunnelStageKey | null;
  stages: DossierStage[];
  flow: DossierFlow;
  technical: {
    /** حکمِ موتور، عینِ `status.text` — بی‌بازنویسی */
    engineText: string | null;
    code: string | null;
    trigger: { label: string | null; price: number | null; date: string | null } | null;
    basis: string | null;
    /** حکمِ موتورِ خروج، به واژگانِ مالک (`حد ضرر`/`خروج`/`احتیاط`/…) — کدِ خام ترجمه می‌شود، داوری نه */
    exitVerdict: string | null;
    exitConfirmed: boolean;
    stopBasis: string | null;
    matrixDesc: string | null;
    jetAth: boolean | null;
  };
  levels: { resistance: number | null; ceiling: number | null; hardStop: number | null; ma14: number | null };
  hourglass: { active: boolean | null; action: string | null; ma52: number | null;
    rsi5: number | null; desc: string | null };
  /** نماد در جامعۀ قیف بود؟ اگر نه، خطوطِ S/F «سنجیده نشد» می‌مانند */
  inFunnel: boolean;
};

/** نمادِ درجامعه؟ کاندید را از پهن‌ترین درِ قیف می‌خوانیم (`tape.entries = picked`). */
/** تاریخِ میلادیِ payload → «۱۴۰۵/۰۷/۱۲»؛ بی‌اعتبار ⇒ '—' (تبدیل درِ shared/lib/jalaali) */
export function jalaliText(iso: string | null | undefined): string {
  const j = isoToJalali(iso);
  return j ? toFaDigits(j) : '—';
}

export function findCandidate(candLists: Array<Candidate[] | undefined>, symbol: string): Candidate | null {
  for (const list of candLists) {
    const hit = list?.find((c) => c.symbol === symbol);
    if (hit) return hit;
  }
  return null;
}

/**
 * حکم از اولین دری می‌آید که بسته است؛ اگر هیچ دربندی نبود و تحویل باز است،
 * «تأیید» و اگر تحویل نگه داشته «واچ» — همان دلیلی که مدلِ قیف نوشته است.
 */
export function deriveVerdict(status: Record<FunnelStageKey, StageStatus>):
  { verdict: DossierVerdict; stage: FunnelStageKey } {
  for (const k of STAGE_KEYS) {
    if (status[k] === 'reject') return { verdict: 'reject', stage: k };
  }
  if (status.handover === 'pass') return { verdict: 'confirmed', stage: 'handover' };
  const upstream = (['tape', 'technical', 'fundamental'] as const).map((k) => status[k]);
  if (upstream.every((s) => s === 'pass')) return { verdict: 'watch', stage: 'handover' };
  if (upstream.some((s) => s === 'pending')) return { verdict: 'wait', stage: 'handover' };
  const unseen = (['tape', 'technical', 'fundamental'] as const).find((k) => status[k] === 'unavailable');
  return { verdict: 'insufficient', stage: unseen ?? 'handover' };
}

export function buildDossier(
  candidate: Candidate | null,
  feed: FtsPlanFeed | null | undefined,
  symbol: string,
): MasterDossier {
  const fts = feed?.fts ?? null;
  const status = fts?.status ?? null;
  const matrix = fts?.trend?.matrix ?? null;
  const ftsW = fts?.trend?.W?.trend ?? null;
  const ftsD = fts?.trend?.D?.trend ?? null;
  const gated = matrix?.decision === 'REJECT' || status?.vetoed === true;

  const flow: DossierFlow = {
    // واژگانِ روند از خودِ payload است؛ `trendLabel` تنها ترجمهٔ رشته‌ای است
    weekly: trendLabel(candidate?.trendW ?? ftsW ?? undefined),
    daily: gated ? '—' : trendLabel(candidate?.trendD ?? ftsD ?? undefined),
    setup:
      status?.trigger?.label ??
      (matrix?.setup && matrix.setup !== 'NONE' ? (MATRIX_SETUP_FA[matrix.setup] ?? matrix.setup) : null),
    gated,
    reason: gated ? (matrix?.desc ?? candidate?.why?.technical ?? null) : null,
  };

  // سه بلوکِ مشترک یک‌بار ساخته می‌شوند تا هر دو شاخه (با کاندید و بی‌کاندید)
  // دقیقاً همان عددِ payload را ببینند — نه دو نسخۀ هم‌نام.
  const tech = {
    engineText: status?.text ?? null,
    code: status?.code ?? null,
    trigger: status?.trigger
      ? {
          label: status.trigger.label ?? null,
          price: status.trigger.price ?? null,
          date: status.trigger.date ?? null,
        }
      : null,
    basis: feed?.analysis_basis ?? null,
    exitVerdict: fts?.exit_engine?.verdict ? (EXIT_VERDICT_FA[fts.exit_engine.verdict] ?? fts.exit_engine.verdict) : null,
    /** موتور خروج صریحاً روی «حد ضرر» یا «خروج» ایستاده — منطقِ همین از کدِ خامِ verdict حساب می‌شود، نه از متنِ ترجمه‌شده */
    exitConfirmed: fts?.exit_engine?.verdict === 'stop' || fts?.exit_engine?.verdict === 'exit',
    stopBasis: fts?.exit_engine?.l1?.stop_basis
      ? (STOP_BASIS_FA[fts.exit_engine.l1.stop_basis] ?? fts.exit_engine.l1.stop_basis)
      : null,
    matrixDesc: matrix?.desc ?? null,
    jetAth: fts?.jet?.ath ?? null,
  };
  const levels = {
    resistance: fts?.jet?.resistance ?? null,
    ceiling: fts?.jet?.ceiling ?? null,
    hardStop: fts?.exit_engine?.l1?.hard_stop ?? null,
    ma14: fts?.exit_engine?.l1?.ma14 ?? null,
  };
  const hg = {
    active: fts?.hourglass?.active ?? null,
    action: fts?.hourglass?.action ?? null,
    ma52: fts?.hourglass?.ma52 ?? null,
    rsi5: fts?.hourglass?.weekly_rsi5 ?? null,
    desc: fts?.hourglass?.desc ?? null,
  };

  if (!candidate) {
    // بی‌کاندید یعنی نماد در جامعۀ قیف نیست: نه رد، نه قبول — فقط تکنیکالِ زنده
    const v = deriveVerdict({ tape: 'unavailable', technical: gated ? 'reject' : 'unavailable',
                              fundamental: 'unavailable', handover: 'unavailable' });
    return {
      symbol,
      name: '',
      sector: '',
      last: null,
      percent: null,
      verdict: v.verdict,
      verdictText: status?.text ?? VERDICT_LABEL[v.verdict],
      // «تعیین‌کننده» فقط وقتی معنا دارد که یک در واقع بسته باشد؛ بی‌کاندید
      // هیچ دری رأی نداده، پس این فیلد خالی می‌ماند (مگر گیتِ هفتگی بسته باشد)
      verdictStage: gated ? 'technical' : null,
      stages: STAGE_KEYS.map((k) => ({
        key: k, label: STAGE_LABEL[k], status: k === 'technical' && gated ? 'reject' : 'unavailable',
        icon: STATUS_ICON[k === 'technical' && gated ? 'reject' : 'unavailable'],
        why: k === 'technical'
          ? (flow.reason ?? status?.text ?? 'رأیِ زندهٔ موتور خوانده شد؛ دلیلِ در ثبت نشده')
          : 'در جامعۀ قیف نیست — سنجیده نشد، وتو نیست',
      })),
      flow,
      technical: tech,
      levels,
      hourglass: hg,
      inFunnel: false,
    };
  }

  const v = deriveVerdict(candidate.status);
  return {
    symbol: candidate.symbol,
    name: candidate.name,
    sector: candidate.sector,
    last: candidate.row?.p_last ?? null,
    percent: candidate.row?.percent_change ?? null,
    verdict: v.verdict,
    // متنِ موتور مقدم است؛ اگر موتور چیزی نگفت، برچسبِ خنثیِ همان حکم
    verdictText: (v.verdict === 'reject' ? candidate.why[v.stage] : '') || status?.text || VERDICT_LABEL[v.verdict],
    verdictStage: v.stage,
    stages: STAGE_KEYS.map((k) => ({
      key: k,
      label: STAGE_LABEL[k],
      status: candidate.status[k],
      icon: STATUS_ICON[candidate.status[k]],
      why: candidate.why[k] ?? '',
    })),
    flow,
    technical: tech,
    levels,
    hourglass: hg,
    inFunnel: true,
  };
}
