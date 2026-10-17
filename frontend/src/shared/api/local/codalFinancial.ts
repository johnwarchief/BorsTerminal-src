import { nativeGetJsonResult, nativeGetTextResult, type NativeHttpResult } from './nativeHttp';
import {
  normalizeCodalReportUrl,
  runCodalRequest,
} from './codalMonthly';
import {
  codalStore,
  type CodalFinancialStatementRecord,
  type CodalProcessingStatus,
  type CodalSyncOutcome,
  type FinancialStatementValues,
} from './codalStore';

const SEARCH_API = 'https://search.codal.ir/api/search/v2/q';
const REPORT_TYPE = 'annual_financial_statement';
const MAX_REPORT_CHARS = 8_000_000;
const COOLDOWN_MS = 6 * 60 * 60_000;
const REPORT_HEADERS = {
  Accept: 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
  Origin: 'https://codal.ir',
  Referer: 'https://codal.ir/',
};

type TableCell = Record<string, unknown>;
type Datasource = Record<string, unknown> & {
  periodEndToDate?: unknown;
  period?: unknown;
  sheets?: Array<{ tables?: Array<{ description?: unknown; cells?: TableCell[] }> }>;
};

export type FinancialStatementParse = {
  status: CodalProcessingStatus;
  periodEnd: string | null;
  periodMonths: number | null;
  audited: boolean;
  consolidated: boolean | null;
  values: FinancialStatementValues | null;
  error: string | null;
};

export type CodalFinancialSyncResult = {
  symbol: string;
  status: string;
  httpStatus: number | null;
  retryAt: string | null;
  tracingNo?: string;
  periodEnd?: string | null;
  values?: FinancialStatementValues | null;
  sourceUrl?: string;
  error?: string;
};

type CodalStore = typeof codalStore;
type JsonResponse = NativeHttpResult<unknown>;
type TextResponse = NativeHttpResult<string>;
type SyncDependencies = {
  store: CodalStore;
  getJson: (url: string, headers: Record<string, string>) => Promise<JsonResponse>;
  getText: (url: string, headers: Record<string, string>) => Promise<TextResponse>;
  now: () => Date;
  sleep: (ms: number) => Promise<void>;
};

const defaults: SyncDependencies = {
  store: codalStore,
  getJson: nativeGetJsonResult,
  getText: nativeGetTextResult,
  now: () => new Date(),
  sleep: (ms) => new Promise((resolve) => setTimeout(resolve, ms)),
};

const BLANK_REVENUE_RANK = Number.MAX_SAFE_INTEGER;

const statementPatterns: Record<string, RegExp[]> = {
  revenue: [
    /^جمعدرآمدهایعملیاتی/, /^جمعدرآمدها$/, /^درآمدهایعملیاتی$/, /^درآمدعملیاتی/,
    /^فروشخالص/, /^مبلغفروش/, /^بهایفروش/, /^جمعفروش/, /^درآمدهعملیاتی/, /^فروش$/,
    /^درآمد(?!.*سودسهام)(?!.*سرمایهگذاری)/,
  ],
  grossProfit: [/سود\(?زیان\)?ناخالص/, /سودناخالص/, /سودوزيانناخالص/],
  operatingProfit: [/سود\(?زیان\)?عملیات/, /سودعملیاتی/, /سودوزيانعملياتي/],
  netProfit: [
    /^سود\(?زیان\)?خالص$/, /^سودخالص$/, /^زیانخالص$/,
    /سود\(?زیان\)?قابلتخصیصبهصاحبان/, /سود\(?زیان\)?خالص/, /سودخالص/,
    /سودوزيانخالص/, /^زیانخالص/,
  ],
  totalAssets: [
    /^جمعداراییها$/, /^جمع داراییها$/, /^جمع داراییها/, /کل داراییها/, /مجموع داراییها/,
    /^جمعدارایی(?!های)/, /^مجموعدارایی(?!های)/,
  ],
  totalLiabilities: [
    /^جمعبدهیها$/, /^جمع بدهیها$/, /^جمعبدیها/, /کل بدهیها/, /مجموع بدهیها/,
    /^جمعبدهی(?!های)/, /^مجموعبدهی(?!های)/,
  ],
  totalEquity: [
    /^جمعحقوقصاحبانسهام$/, /^جمع حقوق صاحبان سهام$/, /حقوقصاحبانسهام/, /کل حقوقصاحبانسهام/,
    /^جمعحقوقمالکانه/, /^حقوقمالکانه$/,
  ],
  capital: [/^سرمایه$/, /سرمایهپرداخته/, /محل تامینسرمایه/, /سرمایهثبتشده/],
  retainedEarnings: [
    /سود\(?زیان\)?انباشته/, /سودانباشته/, /سودوزيانانباشته/, /اندوختهسرمایه/, /زیانانباشته/,
  ],
  basicEps: [
    /سود\(?زیان\)?خالصهرسهم/, /سود\(?زیان\)?خالصهرسهمپایه/,
    /epsخالصهرسهم/, /سودخالصهرسهم/, /درآمدهرسهم/,
  ],
};

const balanceSideKeys = new Set(['totalLiabilities', 'totalEquity', 'capital', 'retainedEarnings']);

function normalizeLabel(value: unknown): string {
  return String(value ?? '').replace(/[يك]/g, (character) => character === 'ي' ? 'ی' : 'ک')
    .replace(/[\u200c\u200f\u064a]/g, '').replace(/\s+/g, '');
}

function normalizeDigits(value: unknown): string | null {
  if (value == null) return null;
  return String(value).replace(/[۰-۹٠-٩]/g, (character) => {
    const point = character.charCodeAt(0);
    return String(point >= 0x06f0 && point <= 0x06f9 ? point - 0x06f0 : point - 0x0660);
  }).trim() || null;
}

function numericValue(value: unknown): number | null {
  if (value == null) return null;
  const text = String(value).replace(/[۰-۹٠-٩]/g, (character) => {
    const point = character.charCodeAt(0);
    return String(point >= 0x06f0 && point <= 0x06f9 ? point - 0x06f0 : point - 0x0660);
  }).replace(/,/g, '').replace(/\u200c/g, '').trim();
  if (!text || text === '-' || text === '—') return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function parseDatasource(html: string): Datasource | null {
  const match = /var\s+datasource\s*=\s*(\{[\s\S]*?\});\s*\r?\n/.exec(html);
  if (!match?.[1]) return null;
  try {
    const value: unknown = JSON.parse(match[1]);
    return value && typeof value === 'object' && !Array.isArray(value)
      ? value as Datasource : null;
  } catch {
    return null;
  }
}

export type FinancialSheetSelection = {
  incomeSheetId: string | null;
  incomeConsolidated: boolean | null;
  balanceSheetId: string | null;
};

/** Same standalone-first sheet selection as desktop _sheet_options/_pick_sheets. */
export function selectFinancialSheets(html: string): FinancialSheetSelection {
  const options: Array<[string, string]> = [];
  for (const match of html.matchAll(/<option[^>]*value="(\d+)"[^>]*>(.*?)(?=<option|<\/select>)/gs)) {
    const label = (match[2] ?? '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
    if (label) options.push([match[1]!, label]);
  }
  let incomeStandalone: string | null = null;
  let incomeConsolidated: string | null = null;
  let balanceStandalone: string | null = null;
  let balanceConsolidated: string | null = null;
  for (const [id, rawName] of options) {
    const name = rawName.replace(/\u200c/g, ' ');
    const consolidated = name.includes('تلفیقی');
    if (name.includes('سود و زیان') && !name.includes('جامع')) {
      if (consolidated) incomeConsolidated ??= id;
      else incomeStandalone ??= id;
    } else if (name.includes('وضعیت مالی') || name.includes('ترازنامه')) {
      if (consolidated) balanceConsolidated ??= id;
      else balanceStandalone ??= id;
    }
  }
  const income = incomeStandalone ?? incomeConsolidated;
  const balance = balanceStandalone ?? balanceConsolidated;
  return { incomeSheetId: income, incomeConsolidated: income ? !incomeStandalone : null,
    balanceSheetId: balance };
}

function buildGrid(table: { cells?: TableCell[] }): { grid: Map<number, Map<number, unknown>>; rows: number[] } {
  const grid = new Map<number, Map<number, unknown>>();
  for (const cell of Array.isArray(table.cells) ? table.cells : []) {
    const row = Number(cell.rowSequence);
    const column = Number(cell.columnSequence);
    if (!Number.isFinite(row) || !Number.isFinite(column)) continue;
    let columns = grid.get(row);
    if (!columns) { columns = new Map(); grid.set(row, columns); }
    columns.set(column, cell.value);
  }
  return { grid, rows: [...grid.keys()].sort((a, b) => a - b) };
}

function parseStatementTables(datasource: Datasource, out: Record<string, number | null>,
                              ranks: Record<string, number>): string | null {
  let unit: string | null = null;
  for (const sheet of datasource.sheets ?? []) {
    for (const table of sheet.tables ?? []) {
      unit ??= String(table.description ?? '').trim() || null;
      const { grid, rows } = buildGrid(table);
      for (const row of rows) {
        const label = normalizeLabel(grid.get(row)?.get(1));
        const rightLabel = normalizeLabel(grid.get(row)?.get(5));
        if (!label && !rightLabel) continue;
        for (const [key, patterns] of Object.entries(statementPatterns)) {
          let best = label ? patterns.findIndex((pattern) => pattern.test(label)) : -1;
          let side = false;
          if (best < 0 && rightLabel && balanceSideKeys.has(key)) {
            best = patterns.findIndex((pattern) => pattern.test(rightLabel));
            side = best >= 0;
          }
          if (best < 0 || (out[key] != null && (ranks[key] ?? Number.MAX_SAFE_INTEGER) <= best)) continue;
          if ((ranks[`!${key}`] ?? Number.MAX_SAFE_INTEGER) <= best) continue;
          const columns = [...(grid.get(row)?.keys() ?? [])].filter((column) => column > 0).sort((a, b) => a - b)
            .filter((column) => !side || column > 5);
          const value = columns.map((column) => numericValue(grid.get(row)?.get(column)))
            .find((number) => number !== null && number !== 0) ?? null;
          if (value === null) {
            if (key === 'revenue' && best < (ranks[key] ?? BLANK_REVENUE_RANK)) {
              delete out[key];
              delete ranks[key];
              ranks[`!${key}`] = Math.min(ranks[`!${key}`] ?? BLANK_REVENUE_RANK, best);
            }
            continue;
          }
          out[key] = value;
          ranks[key] = best;
        }
      }
    }
  }
  return unit;
}

function canonicalPeriod(value: unknown): string | null {
  const normalized = normalizeDigits(value)?.replace(/-/g, '/');
  const match = /(?<!\d)(\d{4})\s*\/\s*(\d{1,2})\s*\/\s*(\d{1,2})(?!\d)/.exec(normalized ?? '');
  if (!match) return null;
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) return null;
  return `${match[1]}/${match[2]!.padStart(2, '0')}/${match[3]!.padStart(2, '0')}`;
}

function periodFromTitle(title: string): string | null {
  const normalized = normalizeDigits(title) ?? '';
  const endAnchor = /منتهی\s*به/.exec(normalized);
  return canonicalPeriod(endAnchor ? normalized.slice(endAnchor.index + endAnchor[0].length) : normalized);
}

function monthsFromTitle(title: string): number | null {
  const normalized = normalizeDigits(title) ?? '';
  const match = /(\d{1,2})\s*ماهه/.exec(normalized.replace(/[\u200c\u200f]/g, ' '));
  const months = match ? Number(match[1]) : null;
  return months != null && months >= 1 && months <= 12 ? months : null;
}

function reportMonths(datasource: Datasource | null, title: string, periodEnd: string | null): number | null {
  let columnMonths: number | null = null;
  const raw = normalizeDigits(datasource?.period);
  if (raw) {
    const parsed = Number(raw);
    if (Number.isInteger(parsed) && parsed >= 1 && parsed <= 12) columnMonths = parsed;
  }
  const titleMonths = monthsFromTitle(title);
  if (titleMonths === null) return columnMonths;
  const titlePeriod = periodFromTitle(title);
  if (titlePeriod && periodEnd && titlePeriod !== periodEnd) return columnMonths;
  return columnMonths === titleMonths ? columnMonths : titleMonths;
}

function titleIsAudited(title: string): boolean {
  const normalized = normalizeLabel(title);
  return normalized.includes('حسابرسیشده') && !normalized.includes('حسابرسینشده');
}

function fiscalYear(periodEnd: string | null): string | null {
  const match = /^(\d{4})\//.exec(periodEnd ?? '');
  return match?.[1] ?? null;
}

/** Mirrors desktop scrape_report/parse_tables for the selected income/balance sheets. */
export function parseFinancialStatementReport(
  title: string,
  incomeHtml: string,
  balanceHtml: string | null,
  incomeConsolidated: boolean | null,
): FinancialStatementParse {
  const income = parseDatasource(incomeHtml);
  const balance = balanceHtml ? parseDatasource(balanceHtml) : null;
  if (!income) {
    return { status: 'UNSUPPORTED', periodEnd: null, periodMonths: null, audited: titleIsAudited(title),
      consolidated: incomeConsolidated, values: null, error: 'income_datasource_missing_or_invalid' };
  }
  const out: Record<string, number | null> = {};
  const ranks: Record<string, number> = {};
  const incomeUnit = parseStatementTables(income, out, ranks);
  const balanceUnit = balance ? parseStatementTables(balance, out, ranks) : null;
  const unit = incomeUnit ?? balanceUnit;
  const rawPeriod = canonicalPeriod(income.periodEndToDate)
    ?? canonicalPeriod(balance?.periodEndToDate);
  const titlePeriod = periodFromTitle(title);
  const periodEnd = rawPeriod ?? titlePeriod;
  const periodMonths = reportMonths(income, title, periodEnd);
  const audited = titleIsAudited(title);
  const values: FinancialStatementValues = {
    periodMonths, revenue: out.revenue ?? null, grossProfit: out.grossProfit ?? null,
    operatingProfit: out.operatingProfit ?? null, netProfit: out.netProfit ?? null,
    basicEps: out.basicEps ?? null, totalAssets: out.totalAssets ?? null,
    totalLiabilities: out.totalLiabilities ?? null, totalEquity: out.totalEquity ?? null,
    capital: out.capital ?? null, retainedEarnings: out.retainedEarnings ?? null,
    unit, audited, consolidated: incomeConsolidated, fiscalYear: fiscalYear(periodEnd),
  };
  if (!periodEnd) return { status: 'INCOMPLETE', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: 'report_period_missing' };
  if (!audited) return { status: 'NOT_EVALUATED', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: 'report_not_audited' };
  if (incomeConsolidated !== false) return { status: 'NOT_EVALUATED', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: 'standalone_income_statement_missing' };
  if (periodMonths !== 12) return { status: 'NOT_EVALUATED', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: 'report_period_not_12_months' };
  if (values.revenue === null) return { status: 'INCOMPLETE', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: 'operating_revenue_missing' };
  return { status: 'PARSED', periodEnd, periodMonths, audited,
    consolidated: incomeConsolidated, values, error: null };
}

function buildSearchUrl(symbol: string, lastPublishedAt: string | null): string {
  const published = /^(\d{4})[/-](\d{2})[/-](\d{2})/.exec(normalizeDigits(lastPublishedAt) ?? '');
  const fromDate = published ? `${published[1]}/${published[2]}/${published[3]}` : '1400/01/01';
  const params = new URLSearchParams({
    Audited: 'true', AuditorRef: '-1', Category: '1', Childs: 'false',
    CompanyState: '-1', CompanyType: '-1', Consolidatable: 'true', IsNotAudited: 'false',
    Length: '-1', LetterType: '-1', Mains: 'true', NotAudited: 'true',
    NotConsolidatable: 'true', PageNumber: '1', Publisher: 'false', ReportingType: '-1',
    TracingNo: '-1', Symbol: symbol, Title: '', Type: '-1', search: 'true', FromDate: fromDate,
  });
  return `${SEARCH_API}?${params.toString()}`;
}

function responseLetters(data: unknown): Record<string, unknown>[] | null {
  if (!data || typeof data !== 'object' || !Array.isArray((data as Record<string, unknown>).Letters)) return null;
  return (data as { Letters: unknown[] }).Letters.filter((item): item is Record<string, unknown> =>
    Boolean(item) && typeof item === 'object' && !Array.isArray(item));
}

function isAnnualAuditedTitle(value: unknown): boolean {
  const title = normalizeLabel(value);
  return (title.includes('صورتمالی') || title.includes('صورتهایمالی'))
    && titleIsAudited(String(value ?? ''))
    && (title.includes('سالمالی') || title.includes('12ماهه'));
}

function financialFailureDelay(status: number, retryAfter: string | undefined, now: Date): number {
  if (status === 429) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds) && seconds >= 0) return Math.min(30 * 60_000, seconds * 1000);
    const date = Date.parse(retryAfter ?? '');
    if (Number.isFinite(date)) return Math.min(30 * 60_000, Math.max(0, date - now.getTime()));
  }
  if (status === 403) return 30 * 60_000;
  return status === 429 ? 30_000 : 5 * 60_000;
}

async function storeSyncFailure(
  symbol: string, status: string, httpStatus: number | null, error: string,
  retryMs: number, deps: SyncDependencies,
): Promise<CodalFinancialSyncResult> {
  const previous = await deps.store.readFinancialSyncState(symbol);
  const now = deps.now();
  const retryAt = new Date(now.getTime() + retryMs).toISOString();
  const outcome: CodalSyncOutcome = {
    symbol, reportType: REPORT_TYPE, attemptedAt: now.toISOString(), status,
    httpStatus, error, nextRetryAt: retryAt, failureStreak: (previous?.failureStreak ?? 0) + 1,
    dataStored: false,
  };
  await deps.store.recordSyncOutcome(outcome);
  return { symbol, status, httpStatus, retryAt, error };
}

function sheetUrl(sourceUrl: string, sheetId: string): string {
  const url = new URL(sourceUrl);
  url.searchParams.set('sheetId', sheetId);
  return url.toString();
}

async function readSheet(
  sourceUrl: string, sheetId: string, deps: SyncDependencies,
): Promise<TextResponse> {
  return runCodalRequest(() => deps.getText(sheetUrl(sourceUrl, sheetId), REPORT_HEADERS),
    deps.now, deps.sleep);
}

export async function syncLatestAnnualFinancialStatement(
  symbolValue: string,
  overrides: Partial<SyncDependencies> = {},
): Promise<CodalFinancialSyncResult> {
  const deps = { ...defaults, ...overrides };
  const symbol = symbolValue.trim();
  if (!symbol || symbol.length > 64) return { symbol, status: 'INVALID_SYMBOL', httpStatus: null, retryAt: null };

  let previous;
  let latestStored;
  try {
    [previous, latestStored] = await Promise.all([
      deps.store.readFinancialSyncState(symbol), deps.store.readLatestFinancialStatement(symbol),
    ]);
  } catch (error) {
    return { symbol, status: 'STORAGE_UNAVAILABLE', httpStatus: null, retryAt: null,
      error: error instanceof Error ? error.message : String(error) };
  }
  if (previous?.nextRetryAt && Date.parse(previous.nextRetryAt) > deps.now().getTime()) {
    return { symbol, status: 'COOLDOWN', httpStatus: previous.lastHttpStatus,
      retryAt: previous.nextRetryAt, error: previous.lastError ?? undefined };
  }

  const search = await runCodalRequest(
    () => deps.getJson(buildSearchUrl(symbol, latestStored?.publishedAt ?? null), REPORT_HEADERS),
    deps.now, deps.sleep);
  if (search.status < 200 || search.status >= 300 || !search.data) {
    const status = search.status === 429 ? 'RATE_LIMITED' : search.status === 403 ? 'BLOCKED'
      : search.status === 0 ? 'NETWORK_ERROR' : 'HTTP_ERROR';
    return storeSyncFailure(symbol, status, search.status || null,
      search.error ?? `search_http_${search.status || 'unknown'}`,
      financialFailureDelay(search.status, search.headers['retry-after'], deps.now()), deps);
  }
  const letters = responseLetters(search.data);
  if (!letters) return storeSyncFailure(symbol, 'UNSUPPORTED_SEARCH_RESPONSE', search.status,
    'letters_array_missing', COOLDOWN_MS, deps);
  const letter = letters.filter((item) => isAnnualAuditedTitle(item.Title))
    .sort((left, right) => (normalizeDigits(String(right.PublishDateTime ?? '')) ?? '')
      .localeCompare(normalizeDigits(String(left.PublishDateTime ?? '')) ?? ''))[0];
  if (!letter) {
    const now = deps.now();
    const retryAt = new Date(now.getTime() + COOLDOWN_MS).toISOString();
    await deps.store.recordSyncOutcome({ symbol, reportType: REPORT_TYPE,
      attemptedAt: now.toISOString(), status: 'NO_ANNUAL_AUDITED_REPORT', httpStatus: search.status,
      error: null, nextRetryAt: retryAt, failureStreak: 0, dataStored: false });
    return { symbol, status: 'NO_ANNUAL_AUDITED_REPORT', httpStatus: search.status, retryAt };
  }

  const tracingNo = String(letter.TracingNo ?? '').trim();
  const sourceUrl = normalizeCodalReportUrl(letter.Url);
  if (!/^\d+$/.test(tracingNo) || !sourceUrl) {
    return storeSyncFailure(symbol, 'INVALID_REPORT_REFERENCE', search.status,
      'invalid_tracing_number_or_report_url', COOLDOWN_MS, deps);
  }

  const base = await runCodalRequest(() => deps.getText(sourceUrl, REPORT_HEADERS), deps.now, deps.sleep);
  if (base.status < 200 || base.status >= 300 || base.data === null) {
    const status = base.status === 429 ? 'RATE_LIMITED' : base.status === 403 ? 'BLOCKED'
      : base.status === 0 ? 'NETWORK_ERROR' : 'HTTP_ERROR';
    return storeSyncFailure(symbol, status, base.status || null,
      base.error ?? `report_http_${base.status || 'unknown'}`,
      financialFailureDelay(base.status, base.headers['retry-after'], deps.now()), deps);
  }
  if (base.data.length > MAX_REPORT_CHARS) return storeSyncFailure(symbol,
    'REPORT_TOO_LARGE', base.status, 'report_html_exceeds_local_limit', COOLDOWN_MS, deps);

  const sheets = selectFinancialSheets(base.data);
  const pieces: string[] = [base.data];
  let incomeHtml = '';
  let balanceHtml: string | null = null;
  let failedSheet: TextResponse | null = null;
  if (sheets.incomeSheetId) {
    const income = await readSheet(sourceUrl, sheets.incomeSheetId, deps);
    if (income.status < 200 || income.status >= 300 || income.data === null) failedSheet = income;
    else { incomeHtml = income.data; pieces.push(`<!-- sheetId=${sheets.incomeSheetId} -->`, income.data); }
  }
  if (!failedSheet && sheets.balanceSheetId) {
    const balance = await readSheet(sourceUrl, sheets.balanceSheetId, deps);
    if (balance.status < 200 || balance.status >= 300 || balance.data === null) failedSheet = balance;
    else { balanceHtml = balance.data; pieces.push(`<!-- sheetId=${sheets.balanceSheetId} -->`, balance.data); }
  }
  if (failedSheet) {
    const status = failedSheet.status === 429 ? 'RATE_LIMITED' : failedSheet.status === 403 ? 'BLOCKED'
      : failedSheet.status === 0 ? 'NETWORK_ERROR' : 'HTTP_ERROR';
    return storeSyncFailure(symbol, status, failedSheet.status || null,
      failedSheet.error ?? `sheet_http_${failedSheet.status || 'unknown'}`,
      financialFailureDelay(failedSheet.status, failedSheet.headers['retry-after'], deps.now()), deps);
  }
  if (pieces.some((piece) => piece.length > MAX_REPORT_CHARS) || pieces.join('').length > MAX_REPORT_CHARS) {
    return storeSyncFailure(symbol, 'REPORT_TOO_LARGE', base.status,
      'report_bundle_exceeds_local_limit', COOLDOWN_MS, deps);
  }
  const parsed = sheets.incomeSheetId && incomeHtml
    ? parseFinancialStatementReport(String(letter.Title ?? ''), incomeHtml, balanceHtml,
      sheets.incomeConsolidated)
    : { status: 'UNSUPPORTED' as const, periodEnd: null, periodMonths: null,
      audited: titleIsAudited(String(letter.Title ?? '')), consolidated: sheets.incomeConsolidated,
      values: null, error: 'income_statement_sheet_missing' };
  const now = deps.now().toISOString();
  let contentHash: string;
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(pieces.join('\n')));
    contentHash = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  } catch (error) {
    return storeSyncFailure(symbol, 'HASH_UNAVAILABLE', base.status,
      error instanceof Error ? error.message : 'sha256_unavailable', COOLDOWN_MS, deps);
  }
  const record: CodalFinancialStatementRecord = {
    tracingNo, symbol, companyName: typeof letter.CompanyName === 'string' ? letter.CompanyName : '',
    title: typeof letter.Title === 'string' ? letter.Title : '', sourceUrl,
    publishedAt: normalizeDigits(letter.PublishDateTime), periodEnd: parsed.periodEnd,
    receivedAt: now, lastUpdatedAt: now, contentHash, rawHtml: pieces.join('\n'),
    reportType: REPORT_TYPE, processingStatus: parsed.status, processingError: parsed.error,
    values: null, financialValues: parsed.values,
  };
  const dataStored = parsed.status === 'PARSED' && Boolean(parsed.periodEnd) && Boolean(parsed.values);
  const retryAt = dataStored ? null : new Date(deps.now().getTime() + COOLDOWN_MS).toISOString();
  const outcome: CodalSyncOutcome = {
    symbol, reportType: REPORT_TYPE, attemptedAt: now, status: parsed.status,
    httpStatus: base.status, error: parsed.error, nextRetryAt: retryAt,
    failureStreak: dataStored ? 0 : (previous?.failureStreak ?? 0) + 1, dataStored,
  };
  try {
    await deps.store.recordFinancialStatement(record, outcome);
  } catch (error) {
    return { symbol, status: 'STORAGE_ERROR', httpStatus: base.status, retryAt: null,
      tracingNo, periodEnd: parsed.periodEnd,
      error: error instanceof Error ? error.message : String(error) };
  }
  return { symbol, status: parsed.status, httpStatus: base.status, retryAt,
    tracingNo, periodEnd: parsed.periodEnd, values: parsed.values, sourceUrl,
    error: parsed.error ?? undefined };
}

export async function readLatestStoredFinancialStatement(
  symbol: string, store: CodalStore = codalStore,
) {
  const [data, sync] = await Promise.all([
    store.readLatestFinancialStatement(symbol), store.readFinancialSyncState(symbol),
  ]);
  const stale = Boolean(sync?.lastError || (sync?.lastStatus && sync.lastStatus !== 'PARSED'));
  const valid = data?.processingStatus === 'PARSED' && data.audited && data.consolidated === false
    && data.periodMonths === 12;
  return {
    status: valid && !stale ? 'DATA_AVAILABLE' : 'NOT_EVALUATED',
    freshness: stale ? 'STALE' : data ? 'CACHED' : 'UNKNOWN',
    data: valid && !stale ? data : null, sync,
  };
}
