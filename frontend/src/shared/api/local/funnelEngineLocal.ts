// shared/api/local/funnelEngineLocal.ts — موتور کانونی داوری قیف FTS در کلاینت اندروید
//
// همتای دقیق، یک‌به‌یک و بدون انحرافِ funnel_engine.py در بک‌اند دسکتاپ.
// هیچ قاعده‌ای در کلاینت اختراع نشده و تمام ترتیب‌ها، وضعیت‌های هفت‌گانه،
// آستانه‌ها، شروط منطقی (AND/OR)، گیت‌های روند و ساعت شنی، استثناها،
// و رتبه‌بندی تحویل عیناً مطابق داور رسمی پیاده‌سازی شده‌اند.
//
import {
  FILTERS,
  FILTERS_BY_ID,
  PRESETS_BY_ID,
  TREND_GATE,
  HOURGLASS_GATE,
  RULESET_VERSION,
} from './funnelRegistryLocal';

export const PASS = 'pass' as const;
export const REJECT = 'reject' as const;
export const PENDING = 'pending' as const;
export const UNAVAILABLE = 'unavailable' as const;
export const NOT_REQUIRED = 'not_required' as const;
export const NOT_IN_UNIVERSE = 'not_in_universe' as const;
export const NOT_APPLICABLE = 'not_applicable' as const;

export type StageStatus =
  | typeof PASS
  | typeof REJECT
  | typeof PENDING
  | typeof UNAVAILABLE
  | typeof NOT_REQUIRED
  | typeof NOT_IN_UNIVERSE
  | typeof NOT_APPLICABLE;

export const STATUSES: StageStatus[] = [
  PASS,
  REJECT,
  PENDING,
  UNAVAILABLE,
  NOT_REQUIRED,
  NOT_IN_UNIVERSE,
  NOT_APPLICABLE,
];

const PERMITTED_TITLES = ['مجاز'];
const FORBIDDEN_TITLES = ['ممنوع'];
const STOPPED_MARK = 'متوقف';

type Row = Record<string, unknown>;

export function normSymbol(v: unknown): string {
  return String(v ?? '')
    .trim()
    .replace(/ك/g, 'ک')
    .replace(/ي/g, 'ی')
    .replace(/ى/g, 'ی');
}

const SUFFIX_RE = /[0-9۰-۹]$/;
export function hasNumericSuffix(symbol: unknown): boolean {
  return SUFFIX_RE.test(normSymbol(symbol));
}

export function _tri(v: unknown): boolean | null {
  if (v === null || v === undefined || v === '' || v === '—') return null;
  if (typeof v === 'boolean') return v;
  if (typeof v === 'number') return v !== 0;
  if (typeof v === 'string') {
    const s = v.trim().toLowerCase();
    if (['1', 'true', 'yes', 'آری', '✓'].includes(s)) return true;
    if (['0', 'false', 'no', 'خیر', '✗'].includes(s)) return false;
  }
  return null;
}

export function _num(v: unknown): number | null {
  const n = typeof v === 'string' ? Number(v) : typeof v === 'number' ? v : NaN;
  return Number.isFinite(n) ? n : null;
}

function _faDigits(v: unknown): string {
  return String(v).replace(/\d/g, (d) => String.fromCharCode(0x06f0 + Number(d)));
}

function _whyOf(row: Row): Array<Record<string, unknown>> {
  if (!Array.isArray(row._funnel_why)) {
    row._funnel_why = [];
  }
  return row._funnel_why as Array<Record<string, unknown>>;
}

/** تشخیص صلاحیت حضور نماد در جامعهٔ غربالگری */
export function screeningEligibility(
  row: Row,
  sessionDay: number | null = null,
): { ok: boolean; code: string; human: string } {
  const title = String(row.st_title ?? '').trim();
  const code = String(row.st_code ?? '').trim();

  if (row.is_live === false) {
    return { ok: false, code: 'NOT_LIVE_SESSION', human: 'درِ تازه‌ترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)' };
  }
  const dEven = _num(row.d_even);
  if (sessionDay != null && dEven != null && dEven < sessionDay) {
    return { ok: false, code: 'NOT_LIVE_SESSION', human: 'درِ تازه‌ترین نشستِ تابلو حاضر نیست (ردیفِ کهنه)' };
  }
  if (row.stop_state) {
    return { ok: false, code: 'STOPPED', human: `متوقف: ${String(row.stop_state)}` };
  }
  if (FORBIDDEN_TITLES.some((t) => title.startsWith(t))) {
    return { ok: false, code: 'FORBIDDEN_STATE', human: `وضعیتِ ثبت‌شدۀ نماد: ${title}` };
  }
  if (title.includes(STOPPED_MARK)) {
    return { ok: false, code: 'STOPPED', human: `وضعیتِ ثبت‌شدۀ نماد: ${title}` };
  }
  if (PERMITTED_TITLES.some((t) => title.startsWith(t))) {
    return { ok: true, code: 'PERMITTED_STATE', human: `وضعیتِ ثبت‌شدۀ نماد: ${title}` };
  }
  if (title || code) {
    return { ok: true, code: 'NO_BLOCKING_STATE', human: `وتوی معتبری ثبت نشده (وضعیت: ${title || code})` };
  }
  return { ok: true, code: 'NO_BLOCKING_STATE', human: 'وضعیتی برایِ این نماد ثبت نشده — وتویی نیست' };
}

function _tapePassText(r: Row, chain: string[]): { code: string; text: string } {
  const hits = chain
    .filter((f) => FILTERS_BY_ID.has(f) && _tri(r[f]) === true)
    .map((f) => FILTERS_BY_ID.get(f)!.name);
  if (hits.length > 0) {
    return { code: 'TAPE_PASSED', text: `خورده شده: ${hits.join(' · ')}` };
  }
  if (chain.length === 0) {
    return { code: 'TAPE_NO_FILTER_DEFINED', text: 'گامِ تابلو برایِ این شخص فیلتری ندارد' };
  }
  return { code: 'TAPE_PASSED_UNFLAGGED', text: 'پرچمِ هیچ فیلترِ انتخابی رویِ این ردیف True نیست' };
}

function _tapePassWhy(r: Row, chain: string[]): void {
  const { code, text } = _tapePassText(r, chain);
  _whyOf(r).push({
    stage: 'tape',
    seq: 0,
    filter_id: chain.join(','),
    status: PASS,
    reason_code: code,
    human_reason: text,
  });
}

/** گام تابلو — حالت اجتماع (OR) */
function _tapeStageUnion(
  rows: Row[],
  chain: string[],
  params: Record<string, Record<string, unknown>>,
): { survivors: Row[]; steps: Array<Record<string, unknown>>; dropped: Record<string, string[]>; logic: 'or' } {
  const steps: Array<Record<string, unknown>> = [];
  const matchedSyms = new Set<string>();

  for (const fid of chain) {
    const f = FILTERS_BY_ID.get(fid);
    if (!f) throw new Error(`فیلترِ ناشناخته درِ زنجیره: ${fid}`);

    const yes = rows.filter((r) => _tri(r[fid]) === true);
    const no = rows.filter((r) => _tri(r[fid]) === false);
    const unknown = rows.filter((r) => _tri(r[fid]) === null);

    for (const r of yes) matchedSyms.add(String(r.symbol ?? ''));

    steps.push({
      stage: 'tape',
      seq: steps.length + 1,
      filter_id: fid,
      label: f.name,
      input_count: rows.length,
      matched_count: yes.length,
      removed_count: no.length,
      unmeasured_count: unknown.length,
      not_forwarded_count: 0,
      parameter_set: params[fid] ?? {},
      source_ref: `${f.source_file}#${f.source_hash}`,
      formula_version: f.formula_version,
      backend_impl: f.backend_impl,
      status: matchedSyms.size === 0 && no.length > 0 ? REJECT : PASS,
      logic: 'or',
    });
  }

  const survivors: Row[] = [];
  const dropped: Record<string, string[]> = Object.fromEntries(chain.map((fid) => [fid, []]));

  for (const r of rows) {
    const sym = String(r.symbol ?? '');
    if (matchedSyms.has(sym)) {
      survivors.push(r);
      _tapePassWhy(r, chain);
      continue;
    }
    const falses = chain.filter((fid) => _tri(r[fid]) === false);
    const unknowns = chain.filter((fid) => _tri(r[fid]) === null);

    for (const fid of falses) dropped[fid].push(sym);

    if (falses.length > 0) {
      const parts = falses.slice(0, 3).map((fid) => FILTERS_BY_ID.get(fid)!.name);
      if (falses.length > 3) parts.push(`و ${_faDigits(falses.length - 3)} قیدِ دیگر`);
      r._tape_why_text = `هیچ‌یک از فیلترهایِ انتخابی نخورد: ${parts.join(' · ')}`;
      _whyOf(r).push({
        stage: 'tape',
        seq: 0,
        filter_id: falses.join(','),
        status: REJECT,
        reason_code: 'TAPE_UNION_NO_MATCH',
        human_reason: r._tape_why_text,
      });
    } else if (unknowns.length > 0) {
      const fids = unknowns[0];
      r._tape_why_text = `${FILTERS_BY_ID.get(fids)!.name} — مبنایِ تاریخچه را ندارد، پس رد نشده`;
      _whyOf(r).push({
        stage: 'tape',
        seq: 0,
        filter_id: unknowns.join(','),
        status: UNAVAILABLE,
        reason_code: `TAPE_${fids.toUpperCase()}_UNMEASURED`,
        human_reason: r._tape_why_text,
      });
    }
  }

  return { survivors, steps, dropped, logic: 'or' };
}

/** گام ۱: تابلوخوانی — اشتراک ترتیبی (AND) یا اجتماع (OR) */
export function tapeStage(
  rows: Row[],
  chain: string[],
  params: Record<string, Record<string, unknown>> = {},
  logic: 'and' | 'or' = 'and',
): { survivors: Row[]; steps: Array<Record<string, unknown>>; dropped: Record<string, string[]>; logic: 'and' | 'or' } {
  if (logic === 'or' && chain.length > 0) {
    return _tapeStageUnion(rows, chain, params);
  }

  let survivors = [...rows];
  const steps: Array<Record<string, unknown>> = [];
  const dropped: Record<string, string[]> = {};

  for (const fid of chain) {
    const f = FILTERS_BY_ID.get(fid);
    if (!f) throw new Error(`فیلترِ ناشناخته درِ زنجیره: ${fid}`);

    const before = survivors.length;
    const matched: Row[] = [];
    const removed: string[] = [];
    const unmeasured: string[] = [];

    for (const r of survivors) {
      const sym = String(r.symbol ?? '');
      const v = _tri(r[fid]);
      if (v === false) {
        removed.push(sym);
      } else {
        matched.push(r);
        if (v === null) unmeasured.push(sym);
      }
    }

    dropped[fid] = removed;

    for (const r of survivors) {
      const fv = _tri(r[fid]);
      if (fv === false) {
        r._tape_why_text = `${f.name} — نشانه در این نماد نیست`;
        _whyOf(r).push({
          stage: 'tape',
          seq: steps.length + 1,
          filter_id: fid,
          status: REJECT,
          reason_code: `TAPE_${fid.toUpperCase()}_NO_MATCH`,
          human_reason: r._tape_why_text,
          input_count: before,
          output_count: matched.length,
          source: f.source_file,
          formula_version: f.formula_version,
        });
      } else if (fv === null) {
        _whyOf(r).push({
          stage: 'tape',
          seq: steps.length + 1,
          filter_id: fid,
          status: UNAVAILABLE,
          reason_code: `TAPE_${fid.toUpperCase()}_UNMEASURED`,
          human_reason: `${f.name} — پرچم این نماد ساخته نشده`,
          input_count: before,
          output_count: matched.length,
          source: f.source_file,
          formula_version: f.formula_version,
        });
      }
    }

    steps.push({
      stage: 'tape',
      seq: steps.length + 1,
      filter_id: fid,
      label: f.name,
      input_count: before,
      matched_count: matched.length,
      removed_count: removed.length,
      unmeasured_count: unmeasured.length,
      not_forwarded_count: before - matched.length,
      parameter_set: params[fid] ?? {},
      source_ref: `${f.source_file}#${f.source_hash}`,
      formula_version: f.formula_version,
      backend_impl: f.backend_impl,
      status: removed.length > 0 ? REJECT : unmeasured.length > 0 ? PENDING : PASS,
    });

    survivors = matched;
  }

  for (const r of survivors) {
    _tapePassWhy(r, chain);
  }

  return { survivors, steps, dropped, logic: 'and' };
}

const BRANCH_OF: Record<string, string> = {
  up: 'جت / پولبک',
  down: 'فیبوناچی / CHoCH',
  range: 'کف دوقلو / آخرین ساختار حمایت-مقاومت',
};

/** گام ۲: تکنیکال */
export function technicalStage(
  rows: Row[],
  gate: string = TREND_GATE,
): { survivors: Row[]; decisions: Array<Record<string, unknown>>; counts: Record<string, number>; dropped: string[] } {
  const kept: Row[] = [];
  const decisions: Array<Record<string, unknown>> = [];
  const dropped: string[] = [];
  const counts = { [PASS]: 0, [REJECT]: 0, [PENDING]: 0, [UNAVAILABLE]: 0 };

  for (const r of rows) {
    const sym = String(r.symbol ?? '');
    const w = String(r.tech_trend_w ?? '').trim() || null;
    const d = String(r.tech_trend_d ?? '').trim() || null;
    const mat = String(r.tech_matrix_decision ?? '').trim() || null;
    const why: Array<{ code: string; text: string }> = [];

    let status: StageStatus = PENDING;

    if (gate === HOURGLASS_GATE) {
      const hg = _tri(r.tech_hourglass_active);
      if (hg === true) {
        status = PASS;
        why.push({ code: 'HOURGLASS_WEEKLY_ACTIVE', text: 'ساعتِ شنیِ هفتگی فعال — زیرِ MA=۵۲ هفتگی با RSI(۵)ِ اشباعِ کف' });
      } else if (hg === false) {
        status = REJECT;
        why.push({ code: 'HOURGLASS_INACTIVE', text: 'ساعتِ شنیِ هفتگی فعال نیست — شرطِ MA=۵۲ و RSI(۵)ِ هفتگی ندارد' });
      } else {
        status = UNAVAILABLE;
        why.push({ code: 'TECH_UNMEASURED', text: 'تکنیکال این نماد سنجیده نشده' });
      }
    } else if (!w && !d && !mat) {
      status = UNAVAILABLE;
      why.push({ code: 'TECH_UNMEASURED', text: 'تکنیکال این نماد سنجیده نشده' });
    } else if (mat === 'UNKNOWN') {
      status = PENDING;
      why.push({ code: 'WEEKLY_UNMEASURED', text: 'هفتگی به اندازهٔ کافی پیوت ندارد' });
    } else if (w === 'down') {
      status = REJECT;
      why.push({ code: 'WEEKLY_TREND_DOWN', text: 'روند هفتگی نزولی — وتوی قطعی' });
    } else if (w === 'range') {
      status = REJECT;
      why.push({ code: 'WEEKLY_TREND_NEUTRAL', text: 'روند هفتگی خنثی — وتوی قطعی' });
    } else if (w === 'up') {
      status = PASS;
      why.push({ code: 'WEEKLY_TREND_UP', text: 'روند هفتگی صعودی' });
      why.push({ code: 'DAILY_BRANCH', text: `روزانه ${d ?? '—'} ⇒ شاخهٔ ${BRANCH_OF[d ?? ''] ?? '—'}` });
    } else {
      status = PENDING;
      why.push({ code: 'WEEKLY_UNCLASSIFIED', text: 'هفتگی دسته‌بندی نشده' });
    }

    const evidence = ['tech_jet', 'tech_choch_bull', 'tech_double_bottom', 'tech_range_break']
      .filter((k) => _tri(r[k]) === true);

    counts[status] = (counts[status] ?? 0) + 1;
    if (status === PASS) {
      kept.push(r);
    } else {
      dropped.push(sym);
    }

    decisions.push({
      stage: 'technical',
      symbol: sym,
      status,
      weekly: w,
      daily: d,
      branch: BRANCH_OF[d ?? ''] ?? null,
      matrix: mat,
      evidence,
      points: _num(r.tech_points),
      why,
    });
  }

  return { survivors: kept, decisions, counts, dropped };
}

const IND_KEYS = ['i1', 'i2', 'i3', 'i4', 'i5'] as const;
const IND_LABEL: Record<string, string> = {
  i1: 'I1 رشد فروش',
  i2: 'I2 EPS سه‌ساله',
  i3: 'I3 حاشیه سود ناخالص',
  i4: 'I4 فروش ۱۲ماه ÷ ارزش بازار',
  i5: 'I5 نرخ‌گذاری',
};
const FUND_MIN_PASS = 3;
const NA_SIGNALS: Record<string, string> = { i2: 'i2_na', i3: 'i3_na', i4: 'i4_na' };

function _indState(k: string, mark: boolean | null, row: Row): StageStatus {
  if (row[NA_SIGNALS[k] ?? '_'] === true) return NOT_APPLICABLE;
  if (mark === null) return PENDING;
  return mark ? PASS : REJECT;
}

function indicatorStates(row: Row): Record<string, StageStatus> {
  const out: Record<string, StageStatus> = {};
  for (const k of IND_KEYS) {
    out[k] = _indState(k, _tri(row[`${k}_pass`]), row);
  }
  return out;
}

function _fundCounts(states: Record<string, StageStatus>): [number, number, number, number] {
  let p = 0, f = 0, u = 0, na = 0;
  for (const s of Object.values(states)) {
    if (s === PASS) p++;
    else if (s === REJECT) f++;
    else if (s === PENDING) u++;
    else if (s === NOT_APPLICABLE) na++;
  }
  return [p, f, u, na];
}

/** گام ۳: بنیادی */
export function fundamentalStage(
  rows: Row[],
  mode: 'standard' | 'hard' | 'exception' = 'standard',
  exceptions: Record<string, string[]> = {},
): { survivors: Row[]; decisions: Array<Record<string, unknown>>; counts: Record<string, number>; dropped: string[] } {
  const kept: Row[] = [];
  const decisions: Array<Record<string, unknown>> = [];
  const dropped: string[] = [];
  const counts: Record<StageStatus, number> = {
    [PASS]: 0,
    [REJECT]: 0,
    [PENDING]: 0,
    [UNAVAILABLE]: 0,
    [NOT_REQUIRED]: 0,
    [NOT_IN_UNIVERSE]: 0,
    [NOT_APPLICABLE]: 0,
  };

  for (const r of rows) {
    const sym = String(r.symbol ?? '');
    const states = indicatorStates(r);
    const [nPass, nFail, nUnknown, nNa] = _fundCounts(states);
    const failed = IND_KEYS.filter((k) => states[k] === REJECT);
    const unknown = IND_KEYS.filter((k) => states[k] === PENDING);
    const why: Array<{ code: string; text: string }> = [];

    const granted = (exceptions[sym] ?? [])
      .map((k) => k.toUpperCase())
      .filter((k) => ['I1', 'I2', 'I3'].includes(k));
    const grantKeys = ['i1', 'i2', 'i3'].filter((k) => granted.includes(k.toUpperCase()) && states[k] !== PASS);
    const counted = nPass + (mode === 'exception' ? grantKeys.length : 0);

    const verdict = (n: number): StageStatus => {
      if (mode === 'hard') {
        return failed.length > 0 ? REJECT : unknown.length > 0 ? PENDING : PASS;
      }
      if (n >= FUND_MIN_PASS) return PASS;
      return unknown.length > 0 ? PENDING : REJECT;
    };

    const canonical = verdict(nPass);
    const effective = verdict(counted);
    const caveat = Boolean(nFail || nUnknown || nNa);

    if (mode === 'hard') {
      if (failed.length > 0) {
        for (const k of failed) why.push({ code: `FUND_${k.toUpperCase()}_REJECT`, text: `${IND_LABEL[k]} تأیید نشده` });
      } else if (unknown.length > 0) {
        for (const k of unknown) why.push({ code: `FUND_${k.toUpperCase()}_MISSING`, text: `${IND_LABEL[k]} سنجیده نشده` });
      }
    } else {
      if (canonical === PENDING) {
        for (const k of unknown) why.push({ code: `FUND_${k.toUpperCase()}_MISSING`, text: `${IND_LABEL[k]} گزارشش نرسیده — رد نیست، سنجیده نشده` });
      } else if (canonical === REJECT) {
        why.push({ code: 'FUND_BELOW_MIN_PASS', text: `${_faDigits(nPass)} شاخص از ${_faDigits(FUND_MIN_PASS)} تأیید لازم` });
      }
      for (const k of failed) why.push({ code: `FUND_${k.toUpperCase()}_REJECT`, text: `${IND_LABEL[k]} زیرِ کف` });
    }

    if (effective === PASS && canonical !== PASS) {
      why.push({ code: 'EXCEPTION_APPLIED', text: `استثنای بنیادی: ${[...granted].sort().join('، ')}` });
    }
    if (effective === PASS && caveat) {
      const parts = [`${_faDigits(nPass)} شاخص تأیید شد`];
      if (nFail) parts.push(`${_faDigits(nFail)} شاخص رد شد`);
      if (nUnknown) parts.push(`اطلاعات ${_faDigits(nUnknown)} شاخص موجود نیست`);
      why.push({ code: 'FUND_PASSED_WITH_CAVEATS', text: `عبور با ملاحظات: ${parts.join('؛ ')}` });
    }

    counts[canonical] = (counts[canonical] ?? 0) + 1;

    const rowOut: Row = {
      ...r,
      _fund_canonical: canonical,
      _fund_effective: effective,
      _fund_caveat: Boolean(effective === PASS && caveat),
      _fund_exceptions: effective === PASS && granted.length > 0 ? [...granted].sort() : [],
    };

    if (effective === PASS) {
      kept.push(rowOut);
    } else {
      dropped.push(sym);
    }

    decisions.push({
      stage: 'fundamental',
      symbol: sym,
      mode,
      canonical,
      effective,
      caveat: rowOut._fund_caveat,
      exceptions: rowOut._fund_exceptions,
      indicators_passed: nPass,
      indicators_failed: nFail,
      indicators_unknown: nUnknown,
      indicators_na: nNa,
      min_pass_required: FUND_MIN_PASS,
      score: _num(r.score),
      primary_score: _num(r.primary_score),
      why,
    });
  }

  return { survivors: kept, decisions, counts, dropped };
}

/** گام ۴: تحویل و رتبه‌بندی نهایی */
export function handoverStage(
  rows: Row[],
  tape: { steps: Array<Record<string, unknown>> },
  tech: { decisions: Array<Record<string, unknown>> },
  fund: { decisions: Array<Record<string, unknown>> },
  assemblyVetoed: Set<string> = new Set(),
): { entries: Array<Record<string, unknown>>; counts: Record<string, number> } {
  const techBy = new Map(tech.decisions.map((d) => [String(d.symbol), d]));
  const fundBy = new Map(fund.decisions.map((d) => [String(d.symbol), d]));
  const out: Array<Record<string, unknown>> = [];

  for (let i = 0; i < rows.length; i++) {
    const r = rows[i];
    const sym = String(r.symbol ?? '');
    const f = fundBy.get(sym) ?? {};
    const t = techBy.get(sym) ?? {};
    const exc = (f.exceptions as string[]) ?? [];
    const isVeto = assemblyVetoed.has(sym);

    out.push({
      symbol: sym,
      name: r.name ?? '',
      final: isVeto ? REJECT : PASS,
      exception: exc.length > 0,
      fund_caveat: Boolean(f.caveat),
      fund_passed: _num(f.indicators_passed),
      fund_score: _num(r.score),
      tech_points: _num(r.tech_points),
      backend_rank: i,
      weekly: t.weekly,
      daily: t.daily,
      branch: t.branch,
      exceptions: exc,
      assembly_veto: isVeto,
      why: isVeto
        ? [{ code: 'ASSEMBLY_VETO', text: 'وتوی مجمع — زمان‌بندیِ ورود' }]
        : [...((t.why as Array<Record<string, unknown>>) ?? []), ...((f.why as Array<Record<string, unknown>>) ?? [])],
      chain: tape.steps.map((s) => s.filter_id),
    });
  }

  out.sort((a, b) => {
    if (a.final !== b.final) return a.final === PASS ? -1 : 1;
    if (a.exception !== b.exception) return a.exception ? 1 : -1;
    const aFund = _num(a.fund_score) ?? -1;
    const bFund = _num(b.fund_score) ?? -1;
    if (aFund !== bFund) return bFund - aFund;
    const aTech = _num(a.tech_points) ?? -1;
    const bTech = _num(b.tech_points) ?? -1;
    if (aTech !== bTech) return bTech - aTech;
    return String(a.symbol).localeCompare(String(b.symbol));
  });

  out.forEach((e, idx) => {
    e.display_rank = idx + 1;
  });

  return {
    entries: out,
    counts: {
      [PASS]: out.filter((e) => e.final === PASS).length,
      [REJECT]: out.filter((e) => e.final === REJECT).length,
      exception: out.filter((e) => e.exception).length,
    },
  };
}

/** اجرای ارزیابی کامل قیف به شیوهٔ رسمی و همگام با دسکتاپ */
export function evaluateFunnelLocal(
  boardRows: Row[],
  screenRows: Row[],
  options: {
    preset?: string;
    customChain?: string[];
    fundMode?: 'standard' | 'hard' | 'exception';
    params?: Record<string, Record<string, unknown>>;
    exceptions?: Record<string, string[]>;
    dropNumericSuffix?: boolean;
    tapeLogic?: 'and' | 'or';
    sessionDay?: number | null;
    asOf?: number;
    marketDataAt?: number;
    dataSource?: 'live_overlay' | 'snapshot_db';
  } = {},
): Record<string, unknown> {
  const asOf = options.asOf ?? Math.floor(Date.now() / 1000);
  const preset = options.preset ?? 'trend';
  const fundMode = options.fundMode ?? 'standard';
  const dropNumericSuffix = options.dropNumericSuffix ?? true;
  const tapeLogic = options.tapeLogic ?? 'and';
  const customChain = options.customChain ?? [];
  const params = options.params ?? {};
  const exceptions = options.exceptions ?? {};
  const sessionDay = options.sessionDay ?? null;

  const pObj = PRESETS_BY_ID.get(preset as any);
  if (!pObj) {
    return { status: 'error', message: `presetِ ناشناخته: ${preset}` };
  }

  const chain = customChain.length > 0 ? customChain : pObj.chain;

  // تلفیق ردیف‌های تابلو و اسکرینر بر اساس کلید نماد
  const screenBy = new Map<string, Row>();
  for (let i = 0; i < screenRows.length; i++) {
    const orig = screenRows[i];
    const r: Row = { ...orig, _backend_rank: i };
    screenBy.set(normSymbol(orig.symbol), r);
  }

  const seen = new Map<string, Row>();
  for (const bRow of boardRows) {
    const sym = normSymbol(bRow.symbol);
    if (!sym || seen.has(sym)) continue;
    const scr = screenBy.get(sym) ?? {};
    seen.set(sym, { ...scr, ...bRow, symbol: sym });
  }

  const joined = Array.from(seen.values());

  // جداسازی نمادهای واجد شرایط غربالگری از خارج از جامعه
  const screening: Row[] = [];
  const excluded: Row[] = [];

  for (const r of joined) {
    if (dropNumericSuffix && hasNumericSuffix(r.symbol)) {
      r._screening_eligible = false;
      r._exclusion_code = 'NUMERIC_SUFFIX';
      r._exclusion_reason = 'پسوندِ عددی دارد — نسخۀ افزودۀ همان برند، نه نمادِ اصلی';
      excluded.push(r);
    } else {
      const el = screeningEligibility(r, sessionDay);
      r._screening_eligible = el.ok;
      r._exclusion_code = el.code;
      r._exclusion_reason = el.human;
      if (el.ok) screening.push(r);
      else excluded.push(r);
    }
  }

  // اجرای چهار گام
  const tape = tapeStage(screening, chain, params, tapeLogic);
  const gate = pObj.technical_gate ?? TREND_GATE;
  const tech = technicalStage(tape.survivors, gate);
  const fund = fundamentalStage(tech.survivors, fundMode, exceptions);
  const hand = handoverStage(fund.survivors, tape, tech, fund);

  // تولید ساختار entries و timeline برای رندر در رابط کاربری
  const entries: Record<string, Row[]> = { tape: [], technical: [], fundamental: [], handover: [] };
  const timeline: Record<string, Array<Record<string, unknown>>> = {};

  const techBy = new Map(tech.decisions.map((d) => [String(d.symbol), d]));
  const fundBy = new Map(fund.decisions.map((d) => [String(d.symbol), d]));
  const handBy = new Map(hand.entries.map((e) => [String(e.symbol), e]));
  const tapeSurv = new Set(tape.survivors.map((r) => String(r.symbol)));

  for (const r of screening) {
    const sym = String(r.symbol);
    const t = techBy.get(sym);
    const f = fundBy.get(sym);
    const h = handBy.get(sym);

    const tapeStatus: StageStatus = tapeSurv.has(sym) ? PASS : REJECT;
    const techStatus: StageStatus = t ? (t.status as StageStatus) : tapeStatus === PASS ? UNAVAILABLE : PENDING;
    const fundStatus: StageStatus = f ? (f.effective as StageStatus) : techStatus === PASS ? UNAVAILABLE : PENDING;
    const handStatus: StageStatus = h ? (h.final as StageStatus) : fundStatus === PASS ? UNAVAILABLE : PENDING;

    const rowDisplay: Row = {
      symbol: sym,
      name: r.name ?? '',
      sector: r.sector_name ?? r.sector ?? '',
      last: _num(r.p_last),
      closing: _num(r.p_closing),
      change_pct: _num(r.percent_change),
      vol_ratio: _num(r.vol_ratio),
      tvol: _num(r.tvol ?? r.q_tot_tran),
      is_live: r.is_live,
      status: {
        tape: tapeStatus,
        technical: techStatus,
        fundamental: fundStatus,
        handover: handStatus,
      },
      chain,
      score: _num(r.score),
      tech_points: _num(r.tech_points),
    };

    if (tapeStatus === PASS) entries.tape.push(rowDisplay);
    if (techStatus === PASS) entries.technical.push(rowDisplay);
    if (fundStatus === PASS) entries.fundamental.push(rowDisplay);
    if (handStatus === PASS) entries.handover.push(rowDisplay);

    timeline[sym] = [
      {
        stage: 'universe',
        status: PASS,
        reason_code: 'IN_SCREENING_UNIVERSE',
        human_reason: 'در جامعۀ غربالگریِ این نشست',
        input_count: joined.length,
        output_count: screening.length,
      },
      ...tape.steps.map((sp) => ({
        stage: `tape:${sp.filter_id}`,
        seq: sp.seq,
        status: tapeSurv.has(sym) ? PASS : REJECT,
        label: sp.label,
        filter_id: sp.filter_id,
        reason_code: tapeSurv.has(sym) ? 'TAPE_PASSED' : 'TAPE_NO_MATCH',
        human_reason: tapeSurv.has(sym) ? `${sp.label} — خورده شد` : `${sp.label} — نشانه در این نماد نیست`,
      })),
      ...(t
        ? [{
            stage: 'technical',
            status: t.status,
            reason_code: (t.why as any[])?.[0]?.code ?? '',
            human_reason: (t.why as any[])?.[0]?.text ?? '',
          }]
        : []),
      ...(f
        ? [{
            stage: 'fundamental',
            status: f.effective,
            reason_code: (f.why as any[])?.[0]?.code ?? '',
            human_reason: (f.why as any[])?.[0]?.text ?? '',
          }]
        : []),
    ];
  }

  for (const r of excluded) {
    const sym = String(r.symbol);
    timeline[sym] = [
      {
        stage: 'universe',
        status: NOT_IN_UNIVERSE,
        reason_code: r._exclusion_code,
        human_reason: r._exclusion_reason,
      },
    ];
  }

  const { matrix, coverage } = statusMatrix(joined, tape, tech, fund, hand, chain);

  const exclusions = excluded.map((r) => ({
    symbol: String(r.symbol ?? ''),
    name: String(r.name ?? ''),
    sector: String(r.sector_name ?? r.sector ?? ''),
    last: _num(r.p_last),
    reason_code: String(r._exclusion_code ?? ''),
    human_reason: String(r._exclusion_reason ?? ''),
    st_code: r.st_code as string | undefined,
    st_title: r.st_title as string | undefined,
    stop_state: r.stop_state as string | undefined,
    is_live: r.is_live as boolean | undefined,
  }));

  const exclusionCounts: Record<string, number> = {};
  for (const r of excluded) {
    const c = String(r._exclusion_code ?? '');
    exclusionCounts[c] = (exclusionCounts[c] ?? 0) + 1;
  }
  const exclusionLabels: Record<string, string> = {};
  for (const k of Object.keys(exclusionCounts)) {
    exclusionLabels[k] = EXCLUSION_LABEL[k] ?? k;
  }

  // اثر انگشت ورودی و خروجی جهت ممیزی و اثبات تازگی
  const inputFp = `${joined.length}:${screening.length}:${chain.join(',')}:${tapeLogic}:${fundMode}:${options.marketDataAt ?? 0}`;
  const outputFp = `${hand.entries.length}:${entries.tape.length}:${entries.technical.length}:${entries.fundamental.length}`;

  return {
    status: 'success',
    engine_version: 'local_canonical_v1',
    ruleset_version: RULESET_VERSION,
    as_of: asOf,
    preset,
    chain,
    tape_logic: tapeLogic,
    fund_mode: fundMode,
    metadata: {
      engine_mode: 'local_canonical',
      market_data_at: options.marketDataAt ?? asOf * 1000,
      evaluated_at: new Date().toISOString(),
      data_source: options.dataSource ?? 'snapshot_db',
      input_fingerprint: inputFp,
      output_fingerprint: outputFp,
    },
    universe: {
      board: boardRows.length,
      joined: joined.length,
      market: joined.length,
      screening: screening.length,
      excluded: excluded.length,
      screened: screenRows.length,
      drop_numeric_suffix: dropNumericSuffix,
      exclusion_counts: exclusionCounts,
      exclusion_labels: exclusionLabels,
    },
    stages: {
      tape: {
        steps: tape.steps,
        logic: tapeLogic,
        input: screening.length,
        matched: tape.survivors.length,
        removed: screening.length - tape.survivors.length,
        filter_counts: filterCounts(screening, chain, tapeLogic),
        survivors: tape.survivors.map((r) => String(r.symbol ?? '')),
      },
      technical: {
        counts: tech.counts,
        matched: tech.survivors.length,
        input: tape.survivors.length,
        survivors: tech.survivors.map((r) => String(r.symbol ?? '')),
      },
      fundamental: {
        counts: fund.counts,
        matched: fund.survivors.length,
        input: tech.survivors.length,
        mode: fundMode,
        survivors: fund.survivors.map((r) => String(r.symbol ?? '')),
      },
      handover: {
        counts: hand.counts,
        matched: hand.entries.length,
        input: fund.survivors.length,
        survivors: hand.entries.map((e) => String(e.symbol ?? '')),
      },
    },
    entries,
    handover: hand.entries,
    exclusions,
    timeline,
    status_matrix: matrix,
    coverage,
    trace: {
      tape_dropped: tape.dropped,
      technical: tech.decisions,
      fundamental: fund.decisions,
    },
  };
}

const EXCLUSION_LABEL: Record<string, string> = {
  NOT_LIVE_SESSION: 'ردیفِ نشستِ کهنه',
  STOPPED: 'متوقف',
  FORBIDDEN_STATE: 'ممنوع',
  NUMERIC_SUFFIX: 'پسوندِ عددی',
};

export function filterCounts(
  rows: Row[],
  chain: string[] = [],
  logic: 'and' | 'or' = 'and',
): Record<string, { name: string; matched: number; removed: number; unmeasured: number; input: number; universe: number }> {
  const ids = FILTERS.map((f) => f.filter_id);
  const bits: Array<[number, number]> = [];
  for (const r of rows) {
    let p = 0;
    let u = 0;
    for (let j = 0; j < ids.length; j++) {
      const t = _tri(r[ids[j]]);
      if (t === true) p |= 1 << j;
      else if (t === null) u |= 1 << j;
    }
    bits.push([p, u]);
  }
  const sel = new Set(chain);
  const universe = rows.length;
  const out: Record<string, { name: string; matched: number; removed: number; unmeasured: number; input: number; universe: number }> = {};
  for (let j = 0; j < ids.length; j++) {
    const fid = ids[j];
    const others = ids.map((g, idx) => ({ g, idx })).filter(({ g }) => sel.has(g) && g !== fid).map(({ idx }) => idx);
    let mask = 0;
    for (const k of others) mask |= 1 << k;
    let yes = 0;
    let no = 0;
    let un = 0;
    let base = 0;
    for (const [p, u] of bits) {
      if (others.length > 0) {
        const cond = logic === 'or' ? (p & mask) !== 0 : (p & mask) === mask;
        if (!cond) continue;
      }
      base += 1;
      if ((p >> j) & 1) yes += 1;
      else if ((u >> j) & 1) un += 1;
      else no += 1;
    }
    out[fid] = {
      name: FILTERS_BY_ID.get(fid)?.name ?? fid,
      matched: yes,
      removed: no,
      unmeasured: un,
      input: base,
      universe,
    };
  }
  return out;
}

export function statusMatrix(
  market: Row[],
  tape: { survivors: Row[]; steps: Array<Record<string, unknown>>; dropped: Record<string, string[]> },
  tech: { decisions: Array<Record<string, unknown>> },
  fund: { decisions: Array<Record<string, unknown>> },
  hand: { entries: Array<Record<string, unknown>> },
  chain: string[],
): {
  matrix: Record<string, Record<string, Record<string, unknown>>>;
  coverage: Record<string, Record<StageStatus, number>>;
} {
  const survivors = new Set(tape.survivors.map((r) => String(r.symbol ?? '')));
  const droppedFirst: Record<string, Record<string, unknown>> = {};
  for (const step of tape.steps) {
    const fid = String(step.filter_id ?? '');
    for (const sym of tape.dropped[fid] ?? []) {
      if (!droppedFirst[sym]) droppedFirst[sym] = step;
    }
  }
  const techBy = new Map(tech.decisions.map((d) => [String(d.symbol), d]));
  const fundBy = new Map(fund.decisions.map((d) => [String(d.symbol), d]));
  const handBy = new Map(hand.entries.map((e) => [String(e.symbol), e]));

  const matrix: Record<string, Record<string, Record<string, unknown>>> = {};
  const emptyCov = (): Record<StageStatus, number> => ({
    pass: 0,
    reject: 0,
    pending: 0,
    unavailable: 0,
    not_required: 0,
    not_in_universe: 0,
    not_applicable: 0,
  });
  const coverage: Record<string, Record<StageStatus, number>> = {
    tape: emptyCov(),
    technical: emptyCov(),
    fundamental: emptyCov(),
    handover: emptyCov(),
  };

  const codeOf = (dec: Record<string, unknown> | undefined): string => {
    const w = (dec?.why as Array<Record<string, unknown>>) ?? [];
    return String(w[0]?.code ?? '');
  };

  const stopText = (stageName: string, st: string, nextName: string): string => {
    if (st === REJECT) return `${stageName} نماد را رد کرده؛ ${nextName} اجرا نمی‌شود`;
    if (st === PENDING) return `${stageName} هنوز حکم نداده؛ ${nextName} اجرا نمی‌شود`;
    return `${stageName} داوری‌پذیر نبود؛ ${nextName} اجرا نمی‌شود`;
  };

  for (const r of market) {
    const sym = String(r.symbol ?? '');
    if (!r._screening_eligible) {
      const outCell = {
        status: NOT_IN_UNIVERSE,
        reason_code: r._exclusion_code || 'STATE_NOT_RECORDED',
        human_reason: r._exclusion_reason || 'وضعیتِ رسمیِ نماد اجازهٔ غربال نمی‌دهد',
      };
      const row: Record<string, Record<string, unknown>> = {
        tape: { ...outCell },
        technical: { ...outCell },
        fundamental: { ...outCell },
        handover: { ...outCell },
      };
      matrix[sym] = row;
      for (const stage of ['tape', 'technical', 'fundamental', 'handover']) {
        coverage[stage][NOT_IN_UNIVERSE] = (coverage[stage][NOT_IN_UNIVERSE] ?? 0) + 1;
      }
      continue;
    }

    const t = techBy.get(sym);
    const f = fundBy.get(sym);
    const h = handBy.get(sym);
    const step = droppedFirst[sym];

    let tapeSt: Record<string, unknown>;
    if (step) {
      tapeSt = {
        status: REJECT,
        reason_code: `TAPE_${String(step.filter_id).toUpperCase()}_NO_MATCH`,
        human_reason: r._tape_why_text || `${step.label} — نشانه در این نماد نیست`,
        stage_ref: step.source_ref,
      };
    } else if (survivors.has(sym)) {
      const { code, text } = _tapePassText(r, chain);
      tapeSt = { status: PASS, reason_code: code, human_reason: text };
    } else if (r._tape_why_text) {
      tapeSt = { status: UNAVAILABLE, reason_code: 'TAPE_UNMEASURED', human_reason: r._tape_why_text };
    } else {
      tapeSt = { status: UNAVAILABLE, reason_code: 'TAPE_NO_FLAG', human_reason: 'پرچم این نماد در این نشست ساخته نشده' };
    }

    let techSt: Record<string, unknown>;
    if (tapeSt.status !== PASS) {
      techSt = {
        status: NOT_REQUIRED,
        reason_code: tapeSt.status === REJECT ? 'NOT_REQUIRED_AFTER_TAPE_REJECT' : 'NOT_REQUIRED_AFTER_TAPE_STOP',
        human_reason: stopText('تابلو', String(tapeSt.status), 'تکنیکال'),
      };
    } else if (!t) {
      techSt = { status: UNAVAILABLE, reason_code: 'TECH_NO_VERDICT', human_reason: 'سریِ تکنیکال برای این نماد ساخته نشد' };
    } else {
      const tWhy = (t.why as Array<Record<string, unknown>>) ?? [];
      techSt = {
        status: t.status,
        reason_code: codeOf(t) || 'TECH_PASSED',
        human_reason: tWhy.map((w) => w.text).join(' · '),
      };
    }

    let fundSt: Record<string, unknown>;
    if (techSt.status !== PASS) {
      const gate = tapeSt.status !== PASS ? 'TAPE' : 'TECHNICAL';
      const whyStage = gate === 'TAPE' ? 'تابلو' : 'تکنیکال';
      const whySt = String(gate === 'TAPE' ? tapeSt.status : techSt.status);
      fundSt = {
        status: NOT_REQUIRED,
        reason_code: `NOT_REQUIRED_AFTER_${gate}_${whySt === REJECT ? 'REJECT' : 'STOP'}`,
        human_reason: stopText(whyStage, whySt, 'بنیادی'),
      };
    } else if (!f) {
      fundSt = { status: UNAVAILABLE, reason_code: 'FUND_NO_CODAL_COVERAGE', human_reason: 'پوشش کدال این نماد در اسکرینر نیست' };
    } else {
      const fWhy = (f.why as Array<Record<string, unknown>>) ?? [];
      fundSt = {
        status: f.effective,
        reason_code: codeOf(f) || 'FUND_PASSED',
        human_reason: fWhy.map((w) => w.text).join(' · '),
        canonical: f.canonical,
        exceptions: f.exceptions ?? [],
      };
    }

    let handSt: Record<string, unknown>;
    if (h) {
      const hWhy = (h.why as Array<Record<string, unknown>>) ?? [];
      handSt = {
        status: h.final,
        reason_code: hWhy[0]?.code || (h.assembly_veto ? 'ASSEMBLY_VETO' : 'FINAL_PASS'),
        human_reason: hWhy.map((w) => w.text).join(' · '),
        display_rank: h.display_rank,
      };
    } else {
      const prior = [tapeSt.status, techSt.status, fundSt.status];
      if (prior.includes(REJECT)) {
        handSt = { status: REJECT, reason_code: 'NOT_ELIGIBLE_AFTER_PRIOR_REJECT', human_reason: 'در گامِ پیشین رد شده' };
      } else if (prior.includes(PENDING)) {
        handSt = { status: PENDING, reason_code: 'WAITING_FOR_DATA', human_reason: 'در انتظارِ داده/گزارش' };
      } else {
        handSt = { status: UNAVAILABLE, reason_code: 'NO_FINAL_SOURCE', human_reason: 'منبعی برای حکم نهایی نبود' };
      }
    }

    const row = { tape: tapeSt, technical: techSt, fundamental: fundSt, handover: handSt };
    matrix[sym] = row;
    for (const [stg, cl] of Object.entries(row)) {
      const st = cl.status as StageStatus;
      coverage[stg][st] = (coverage[stg][st] ?? 0) + 1;
    }
  }

  return { matrix, coverage };
}
