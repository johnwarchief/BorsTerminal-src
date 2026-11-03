// features/technical/api/useScreener.ts -- سیگنال‌های FTS سایدبار راست (تب ۲)
// از اندپوینت /api/screener؛ فقط ستون‌های tech_* لازم است. اسکیمای بومیِ فیچر
// (مرز B1): هیچ importی از فیچر fundamental. ردیف بی‌سیگنال حذف می‌شود.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';
import { matchFa } from '@shared/lib/normalizeFa';
import { FTS_SIGNAL_LABEL } from '@shared/lib/ftsSignals';

const flag = z.boolean().nullish();

export const ScreenerRowSchema = z.object({
  symbol: z.string().min(1),
  name: z.string().nullish(),
  symbol_norm: z.string().nullish(),
  sector_name: z.string().nullish(),
  score: z.number().nullish(),
  excluded: z.boolean().nullish(),
  watchlist: z.boolean().nullish(),
  weekly_veto: z.boolean().nullish(),
  tech_trend_d: z.string().nullish(),
  tech_trend_w: z.string().nullish(),
  tech_trend_m: z.string().nullish(),
  tech_alignment: z.string().nullish(),
  tech_jet: flag,
  tech_choch_bull: flag,
  tech_choch_bear: flag,
  tech_double_bottom: flag,
  tech_range_break: flag,
  tech_fib_zone: z.string().nullish(),
  tech_exit_verdict: z.string().nullish(),
  tech_exit_signals: z.array(z.string()).nullish(),
  tech_matrix_decision: z.string().nullish(),
  tech_matrix_setup: z.string().nullish(),
  tech_hourglass_active: flag,
  tech_hourglass_action: z.string().nullish(),
});
export type ScreenerRow = z.infer<typeof ScreenerRowSchema>;

export const ScreenerResponseSchema = z.object({
  status: z.string(),
  count: z.number().nullish(),
  data: z.array(ScreenerRowSchema),
});
export type ScreenerResponse = z.infer<typeof ScreenerResponseSchema>;

/** سقفِ فهرستِ سایدبار — از پاسخِ کامل فیلتر می‌شود، پس «نمایش X از Y» صادق است */
export const FTS_SIGNAL_LIMIT = 60;

export function useFtsScreener() {
  return useQuery({
    queryKey: ['technical-fts-screener'],
    queryFn: ({ signal }) => http<ScreenerResponse>('/api/screener', { schema: ScreenerResponseSchema, signal }),
    staleTime: 5 * 60_000,
    gcTime: 30 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export type FtsSignalTag = { label: string; tone: 'green' | 'red' | 'blue' | 'gray'; role: 'signal' | 'context' };

/** برچسب ستاپ‌های فعال از ستون‌های tech_* پاسخ اسکرینر.
 *  taxonomyِ دورِ J: `role: 'context'` هیچ‌وقت «ستاپ» حساب نمی‌شود — کمربندِ فیبو
 *  جایِ ایستادن را می‌گوید، نه اینکه بخر (سنجش: داخلِ باند edge ندارد). */
export function ftsSignalTags(r: ScreenerRow): FtsSignalTag[] {
  const t: FtsSignalTag[] = [];
  if (r.tech_hourglass_active) t.push({ label: FTS_SIGNAL_LABEL.tech_hourglass_active, tone: 'green', role: 'signal' });
  if (r.tech_jet) t.push({ label: FTS_SIGNAL_LABEL.tech_jet, tone: 'green', role: 'signal' });
  if (r.tech_choch_bull) t.push({ label: FTS_SIGNAL_LABEL.tech_choch_bull, tone: 'green', role: 'signal' });
  if (r.tech_choch_bear) t.push({ label: FTS_SIGNAL_LABEL.tech_choch_bear, tone: 'red', role: 'signal' });
  if (r.tech_double_bottom) t.push({ label: FTS_SIGNAL_LABEL.tech_double_bottom, tone: 'green', role: 'signal' });
  if (r.tech_range_break) t.push({ label: FTS_SIGNAL_LABEL.tech_range_break, tone: 'green', role: 'signal' });
  if (r.tech_fib_zone) t.push({ label: `موقعیت فیبو ${r.tech_fib_zone}`, tone: 'gray', role: 'context' });
  if (r.tech_matrix_decision === 'REJECT') t.push({ label: 'وتوی هفتگی', tone: 'red', role: 'signal' });
  return t;
}

/** فقط نمادهای دارای دست‌کم یک ستاپ/الگو (زمینهٔ فیبو به‌تنهایی سیگنال نیست) */
export function hasFtsSignal(r: ScreenerRow): boolean {
  return ftsSignalTags(r).some((tag) => tag.role === 'signal');
}

/** هشدار/سیگنالِ موتور خروج: فقط آرایهٔ غیرخالیِ `tech_exit_signals` معیار است؛
 *  `tech_exit_verdict = hold` بدون سیگنال، خروج نیست. */
export function hasExitSignal(r: ScreenerRow): boolean {
  return (r.tech_exit_signals?.length ?? 0) > 0;
}

/** جهانِ فهرست: ستاپ/الگو، وتوی هفتگی، یا هشدارِ موتور خروج. */
export function isFtsSignalRow(r: ScreenerRow): boolean {
  return hasFtsSignal(r) || hasExitSignal(r);
}

/**
 * فیلترهای کشویی — هر گزینه یک ستونِ واقعیِ همان `/api/screener` است.
 * `weekly_veto` همان `tech_matrix_decision === 'REJECT'` است (داورِ انحصاریِ
 * وتو در سرور)؛ `exit_signal` همان آرایهٔ `tech_exit_signals`.
 * `not_reported` برایِ حالتِ null/غایب است؛ تهی هرگز با `false` یا رأیِ منفی
 * یکی گرفته نمی‌شود.
 */
export type FtsKindFilter =
  | 'all'
  | 'hourglass'
  | 'jet'
  | 'choch_bull'
  | 'choch_bear'
  | 'double_bottom'
  | 'range_break'
  | 'weekly_veto'
  | 'exit_signal';
export type FtsWeeklyFilter = 'all' | 'up' | 'down' | 'range' | 'na' | 'not_reported';
export type FtsVerdictFilter = 'all' | 'PERMITTED' | 'REJECT' | 'UNKNOWN' | 'not_reported';
export type FtsSignalFilters = { kind: FtsKindFilter; weekly: FtsWeeklyFilter; verdict: FtsVerdictFilter };

export const FTS_FILTERS_DEFAULT: FtsSignalFilters = { kind: 'all', weekly: 'all', verdict: 'all' };

type FlagKind = Exclude<FtsKindFilter, 'all' | 'weekly_veto' | 'exit_signal'>;

const KIND_FLAG: Record<FlagKind, keyof ScreenerRow> = {
  hourglass: 'tech_hourglass_active',
  jet: 'tech_jet',
  choch_bull: 'tech_choch_bull',
  choch_bear: 'tech_choch_bear',
  double_bottom: 'tech_double_bottom',
  range_break: 'tech_range_break',
};

function matchesKind(r: ScreenerRow, kind: FtsKindFilter): boolean {
  if (kind === 'all') return true;
  if (kind === 'weekly_veto') return r.tech_matrix_decision === 'REJECT';
  if (kind === 'exit_signal') return hasExitSignal(r);
  return r[KIND_FLAG[kind]] === true;
}

function matchesFtsFilters(r: ScreenerRow, f: FtsSignalFilters): boolean {
  if (!matchesKind(r, f.kind)) return false;
  if (f.weekly === 'not_reported') {
    if (r.tech_trend_w != null) return false;
  } else if (f.weekly !== 'all' && r.tech_trend_w !== f.weekly) {
    return false;
  }
  if (f.verdict === 'not_reported') {
    if (r.tech_matrix_decision != null) return false;
  } else if (f.verdict !== 'all' && r.tech_matrix_decision !== f.verdict) {
    return false;
  }
  return true;
}

export type FtsSignalsResult = { rows: ScreenerRow[]; total: number; limit: number; truncated: boolean };

/** فیلترِ کامل (سیگنال + سه کشویی + جستجو) با شمارشِ پیش از سقفِ نمایش */
export function filterFtsSignalRows(
  rows: ScreenerRow[],
  q: string,
  filters: FtsSignalFilters = FTS_FILTERS_DEFAULT,
  limit = FTS_SIGNAL_LIMIT,
): FtsSignalsResult {
  const term = q.trim();
  const matched = rows.filter((r) => {
    if (!isFtsSignalRow(r)) return false;
    if (!matchesFtsFilters(r, filters)) return false;
    if (!term) return true;
    return matchFa(r.symbol, term) || matchFa(r.name, term);
  });
  return { rows: matched.slice(0, limit), total: matched.length, limit, truncated: matched.length > limit };
}

/** ردیف‌های دارای ستاپ/الگو، وتوی هفتگی، یا هشدارِ خروج؛ جستجو روی نماد و نام */
export function filterFtsSignals(
  rows: ScreenerRow[],
  q: string,
  filters: FtsSignalFilters = FTS_FILTERS_DEFAULT,
  limit = FTS_SIGNAL_LIMIT,
): ScreenerRow[] {
  return filterFtsSignalRows(rows, q, filters, limit).rows;
}

/**
 * نماد پیش‌فرض (fallback) وقتی نمادی انتخاب نشده: اولین ردیف واچ‌لیست اسکرینر،
 * وگرنه اولین ردیف غیرمردود. null یعنی اسکرینر خالی است.
 */
export function firstScreenerSymbol(rows: ScreenerRow[]): string | null {
  const wl = rows.find((r) => r.watchlist && !r.excluded && r.symbol);
  if (wl) return wl.symbol;
  const any = rows.find((r) => !r.excluded && r.symbol);
  return any ? any.symbol : null;
}
