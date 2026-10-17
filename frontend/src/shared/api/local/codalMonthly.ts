import { nativeGetJsonResult, nativeGetTextResult, type NativeHttpResult } from './nativeHttp';
import {
  codalStore,
  type CodalDocumentRecord,
  type CodalProcessingStatus,
  type CodalSyncOutcome,
  type CodalSyncState,
  type MonthlySalesValues,
} from './codalStore';

const SEARCH_API = 'https://search.codal.ir/api/search/v2/q';
const MIN_REQUEST_GAP_MS = 1700;
const MAX_REPORT_CHARS = 8_000_000;
const REPORT_HEADERS = {
  Accept: 'text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8',
  Origin: 'https://codal.ir',
  Referer: 'https://codal.ir/',
};

export type MonthlyActivityParse = {
  status: CodalProcessingStatus;
  periodEnd: string | null;
  values: MonthlySalesValues | null;
  error: string | null;
};

export type CodalMonthlySyncResult = {
  symbol: string;
  status: string;
  httpStatus: number | null;
  retryAt: string | null;
  tracingNo?: string;
  periodEnd?: string | null;
  values?: MonthlySalesValues | null;
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

let lastCodalRequestAt = 0;
let codalRequestQueue: Promise<void> = Promise.resolve();

function normalizeLabel(value: unknown): string {
  return String(value ?? '').replace(/[يك]/g, (c) => c === 'ي' ? 'ی' : 'ک')
    .replace(/[\u200c\u200f]/g, '').replace(/\s+/g, '');
}

function normalizeDigits(value: unknown): string | null {
  if (value == null) return null;
  return String(value).replace(/[۰-۹٠-٩]/g, (c) => {
    const cp = c.charCodeAt(0);
    return String(cp >= 0x06f0 && cp <= 0x06f9 ? cp - 0x06f0 : cp - 0x0660);
  }).trim() || null;
}

function numericValue(value: unknown): number | null {
  if (value == null) return null;
  const text = String(value).replace(/,/g, '').replace(/\u200c/g, '').trim();
  if (!text || text === '-' || text === '—') return null;
  const number = Number(text);
  return Number.isFinite(number) ? number : null;
}

function parseDatasource(html: string): Record<string, unknown> | null {
  const match = /var\s+datasource\s*=\s*(\{[\s\S]*?\});\s*\r?\n/.exec(html);
  if (!match?.[1]) return null;
  try {
    const value: unknown = JSON.parse(match[1]);
    return value && typeof value === 'object' && !Array.isArray(value)
      ? value as Record<string, unknown> : null;
  } catch {
    return null;
  }
}

type CellTable = {
  description?: unknown;
  cells?: Array<Record<string, unknown>>;
};

function cellValue(grid: Map<number, Map<number, unknown>>, row: number, column: number): unknown {
  return grid.get(row)?.get(column);
}

function buildGrid(table: CellTable): { grid: Map<number, Map<number, unknown>>; rows: number[] } {
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

/** Mirrors desktop codal_fetcher.scrape_monthly_report sales-table selection. */
export function parseMonthlyActivityReportHtml(html: string): MonthlyActivityParse {
  const datasource = parseDatasource(html);
  if (!datasource) {
    return { status: 'UNSUPPORTED', periodEnd: null, values: null, error: 'datasource_missing_or_invalid' };
  }
  const periodEnd = normalizeDigits(datasource.periodEndToDate);
  const sheets = Array.isArray(datasource.sheets) ? datasource.sheets : [];
  let foundSalesTable = false;
  let foundTotal = false;

  for (const sheet of sheets) {
    const tables = sheet && typeof sheet === 'object'
      && Array.isArray((sheet as Record<string, unknown>).tables)
      ? (sheet as Record<string, unknown>).tables as CellTable[] : [];
    for (const table of tables) {
      const { grid, rows } = buildGrid(table);
      if (rows.length < 2) continue;
      let subRow: number | null = null;
      let groupRow: number | null = null;
      for (const headerRow of rows.slice(0, 2)) {
        const labels = [...(grid.get(headerRow)?.entries() ?? [])]
          .map(([, value]) => normalizeLabel(value));
        if (labels.some((label) => label.includes('مبلغفروش'))) subRow = headerRow;
        if (labels.some((label) => label.includes('دورهیکماهه')
          || label.includes('ازابتدایسالمالی'))) groupRow = headerRow;
      }
      if (subRow === null || groupRow === null) continue;
      foundSalesTable = true;

      const sub = new Map<number, string>();
      const groups = new Map<number, string>();
      for (const [column, value] of grid.get(subRow) ?? []) sub.set(column, normalizeLabel(value));
      for (const [column, value] of grid.get(groupRow) ?? []) groups.set(column, normalizeLabel(value));
      const groupColumns = [...groups.entries()].filter(([, label]) => Boolean(label))
        .map(([column]) => column).sort((a, b) => a - b);
      const groupOf = (column: number): string => {
        let group = '';
        for (const groupColumn of groupColumns) {
          if (groupColumn <= column) group = groups.get(groupColumn) ?? '';
          else break;
        }
        return group;
      };

      const subEntries = [...sub.entries()];
      const monthlyColumns = subEntries.filter(([column, label]) =>
        label.includes('مبلغفروش') && groupOf(column).includes('دورهیکماهه'))
        .map(([column]) => column).sort((a, b) => a - b);
      const ytdColumns = subEntries.filter(([column, label]) =>
        label.includes('مبلغفروش') && groupOf(column).includes('ازابتدایسالمالی')
          && (!monthlyColumns.length || column > monthlyColumns[0]))
        .map(([column]) => column).sort((a, b) => a - b);
      const monthlyVolumeColumns = subEntries.filter(([column, label]) =>
        (label.includes('تعدادفروش') || label.includes('مقدارفروش'))
          && groupOf(column).includes('دورهیکماهه'))
        .map(([column]) => column).sort((a, b) => a - b);
      const ytdVolumeColumns = subEntries.filter(([column, label]) =>
        (label.includes('تعدادفروش') || label.includes('مقدارفروش'))
          && groupOf(column).includes('ازابتدایسالمالی')
          && (!monthlyVolumeColumns.length || column > monthlyVolumeColumns[0]))
        .map(([column]) => column).sort((a, b) => a - b);
      const unitColumn = subEntries.find(([, label]) => label === 'واحد')?.[0] ?? null;

      let totalRow = rows.find((row) => ['جمع', 'جمعکل'].includes(normalizeLabel(cellValue(grid, row, 1))));
      totalRow ??= rows.find((row) => normalizeLabel(cellValue(grid, row, 1)).startsWith('جمع'));
      if (totalRow === undefined) continue;
      foundTotal = true;

      const monthlyRevenue = monthlyColumns.length ? numericValue(cellValue(grid, totalRow, monthlyColumns[0])) : null;
      const ytdRevenue = ytdColumns.length ? numericValue(cellValue(grid, totalRow, ytdColumns[0])) : null;
      const monthlyRevenuePrev = monthlyColumns.length > 1
        ? numericValue(cellValue(grid, totalRow, monthlyColumns[1])) : null;
      const ytdRevenuePrev = ytdColumns.length > 1
        ? numericValue(cellValue(grid, totalRow, ytdColumns[1])) : null;

      const volumeFrom = (column: number | undefined): number | null => {
        if (column === undefined) return null;
        const total = numericValue(cellValue(grid, totalRow!, column));
        if (total !== null) return total;
        let sum = 0;
        let hasValue = false;
        for (const row of rows) {
          if (row === totalRow) continue;
          const label = normalizeLabel(cellValue(grid, row, 1));
          if (!label || ['جمع', 'مجموع', 'سرفصل'].some((prefix) => label.startsWith(prefix))
            || label.endsWith(':')) continue;
          const value = numericValue(cellValue(grid, row, column));
          if (value !== null) { sum += value; hasValue = true; }
        }
        return hasValue && sum !== 0 ? sum : null;
      };

      let volumeUnit: string | null = null;
      if (unitColumn !== null) {
        for (const row of rows) {
          if (row === totalRow) continue;
          const unit = normalizeLabel(cellValue(grid, row, unitColumn));
          if (unit && unit !== 'واحد') { volumeUnit = unit; break; }
        }
      }

      if (monthlyRevenue === null && ytdRevenue === null) continue;
      const values: MonthlySalesValues = {
        monthlyRevenue, ytdRevenue, monthlyRevenuePrev, ytdRevenuePrev,
        monthlyVolume: volumeFrom(monthlyVolumeColumns[0]),
        ytdVolume: volumeFrom(ytdVolumeColumns[0]), volumeUnit,
      };
      if (!periodEnd) {
        return { status: 'INCOMPLETE', periodEnd: null, values, error: 'report_period_missing' };
      }
      return { status: 'PARSED', periodEnd, values, error: null };
    }
  }

  const error = !foundSalesTable ? 'sales_table_unsupported'
    : !foundTotal ? 'sales_total_row_missing' : 'sales_revenue_missing';
  return { status: foundSalesTable ? 'INCOMPLETE' : 'UNSUPPORTED', periodEnd,
    values: null, error };
}

function buildSearchUrl(symbol: string, lastPublishedAt: string | null): string {
  const published = /^(\d{4})[/-](\d{2})[/-](\d{2})/.exec(lastPublishedAt ?? '');
  const fromDate = published ? `${published[1]}/${published[2]}/${published[3]}` : '1400/01/01';
  const params = new URLSearchParams({
    Audited: 'true', AuditorRef: '-1', Category: '3', Childs: 'false',
    CompanyState: '-1', CompanyType: '-1', Consolidatable: 'true', IsNotAudited: 'false',
    Length: '-1', LetterType: '-1', Mains: 'true', NotAudited: 'true',
    NotConsolidatable: 'true', PageNumber: '1', Publisher: 'false', TracingNo: '-1',
    Symbol: symbol, Title: '', Type: '-1', search: 'true', FromDate: fromDate,
  });
  return `${SEARCH_API}?${params.toString()}`;
}

export function normalizeCodalReportUrl(path: unknown): string | null {
  if (typeof path !== 'string' || !path.trim()) return null;
  try {
    const url = new URL(path, 'https://codal.ir');
    if (!['codal.ir', 'www.codal.ir'].includes(url.hostname.toLowerCase())
      || !url.pathname.toLowerCase().startsWith('/reports/decision.aspx')
      || !url.searchParams.has('LetterSerial')) return null;
    return url.toString();
  } catch {
    return null;
  }
}

function responseLetters(data: unknown): Record<string, unknown>[] | null {
  if (!data || typeof data !== 'object' || !Array.isArray((data as Record<string, unknown>).Letters)) return null;
  return (data as { Letters: unknown[] }).Letters.filter((item): item is Record<string, unknown> =>
    Boolean(item) && typeof item === 'object' && !Array.isArray(item));
}

function secondsFromRetryAfter(value: string | undefined, now: Date): number | null {
  if (!value) return null;
  const seconds = Number(value);
  if (Number.isFinite(seconds) && seconds >= 0) return Math.min(30 * 60_000, seconds * 1000);
  const date = Date.parse(value);
  return Number.isFinite(date) ? Math.min(30 * 60_000, Math.max(0, date - now.getTime())) : null;
}

export function runCodalRequest<T>(
  request: () => Promise<T>, now: () => Date, sleep: (ms: number) => Promise<void>,
): Promise<T> {
  const operation = codalRequestQueue.then(async () => {
    const elapsed = now().getTime() - lastCodalRequestAt;
    if (lastCodalRequestAt > 0 && elapsed < MIN_REQUEST_GAP_MS) {
      await sleep(MIN_REQUEST_GAP_MS - elapsed);
    }
    lastCodalRequestAt = now().getTime();
    return request();
  });
  codalRequestQueue = operation.then(() => undefined, () => undefined);
  return operation;
}

function retryDelay(status: number, failureStreak: number, retryAfter?: string, now = new Date()): number {
  const provided = status === 429 ? secondsFromRetryAfter(retryAfter, now) : null;
  if (provided !== null) return provided;
  const base = status === 429 ? 30_000 : status === 403 ? 30 * 60_000 : 5 * 60_000;
  return Math.min(30 * 60_000, base * 2 ** Math.min(Math.max(0, failureStreak - 1), 6));
}

async function storeFailure(
  symbol: string,
  status: string,
  httpStatus: number | null,
  error: string,
  retryMs: number,
  deps: SyncDependencies,
): Promise<CodalMonthlySyncResult> {
  const now = deps.now();
  const previous = await deps.store.readSyncState(symbol);
  const failureStreak = (previous?.failureStreak ?? 0) + 1;
  const retryAt = new Date(now.getTime() + retryMs).toISOString();
  const outcome: CodalSyncOutcome = {
    symbol, attemptedAt: now.toISOString(), status, httpStatus, error,
    nextRetryAt: retryAt, failureStreak, dataStored: false,
  };
  await deps.store.recordSyncOutcome(outcome);
  return { symbol, status, httpStatus, retryAt, error };
}

export async function syncLatestMonthlySales(
  symbolValue: string,
  overrides: Partial<SyncDependencies> = {},
): Promise<CodalMonthlySyncResult> {
  const deps = { ...defaults, ...overrides };
  const symbol = symbolValue.trim();
  if (!symbol || symbol.length > 64) return { symbol, status: 'INVALID_SYMBOL', httpStatus: null, retryAt: null };

  let previous: CodalSyncState | null;
  let latestStored: Awaited<ReturnType<CodalStore['readLatestMonthlySales']>>;
  try {
    [previous, latestStored] = await Promise.all([
      deps.store.readSyncState(symbol), deps.store.readLatestMonthlySales(symbol),
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
    const retryMs = retryDelay(search.status, (previous?.failureStreak ?? 0) + 1,
      search.headers['retry-after'], deps.now());
    return storeFailure(symbol, status, search.status || null,
      search.error ?? `search_http_${search.status || 'unknown'}`, retryMs, deps);
  }

  const letters = responseLetters(search.data);
  if (!letters) {
    return storeFailure(symbol, 'UNSUPPORTED_SEARCH_RESPONSE', search.status,
      'letters_array_missing', 6 * 60 * 60_000, deps);
  }
  const letter = letters.find((item) => normalizeLabel(item.Title).includes('گزارشفعالیتماهانه'));
  if (!letter) {
    const now = deps.now();
    const outcome: CodalSyncOutcome = {
      symbol, attemptedAt: now.toISOString(), status: 'NO_REPORT', httpStatus: search.status,
      error: null, nextRetryAt: new Date(now.getTime() + 6 * 60 * 60_000).toISOString(),
      failureStreak: 0, dataStored: false,
    };
    await deps.store.recordSyncOutcome(outcome);
    return { symbol, status: 'NO_REPORT', httpStatus: search.status, retryAt: outcome.nextRetryAt };
  }

  const tracingNo = String(letter.TracingNo ?? '').trim();
  const sourceUrl = normalizeCodalReportUrl(letter.Url);
  if (!/^\d+$/.test(tracingNo) || !sourceUrl) {
    return storeFailure(symbol, 'INVALID_REPORT_REFERENCE', search.status,
      'invalid_tracing_number_or_report_url', 6 * 60 * 60_000, deps);
  }

  const report = await runCodalRequest(() => deps.getText(sourceUrl, REPORT_HEADERS), deps.now, deps.sleep);
  if (report.status < 200 || report.status >= 300 || report.data === null) {
    const status = report.status === 429 ? 'RATE_LIMITED' : report.status === 403 ? 'BLOCKED'
      : report.status === 0 ? 'NETWORK_ERROR' : 'HTTP_ERROR';
    const retryMs = retryDelay(report.status, (previous?.failureStreak ?? 0) + 1,
      report.headers['retry-after'], deps.now());
    return storeFailure(symbol, status, report.status || null,
      report.error ?? `report_http_${report.status || 'unknown'}`, retryMs, deps);
  }
  if (report.data.length > MAX_REPORT_CHARS) {
    return storeFailure(symbol, 'REPORT_TOO_LARGE', report.status,
      'report_html_exceeds_local_limit', 6 * 60 * 60_000, deps);
  }

  const parsed = parseMonthlyActivityReportHtml(report.data);
  const now = deps.now().toISOString();
  let contentHash: string;
  try {
    const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(report.data));
    contentHash = [...new Uint8Array(digest)].map((byte) => byte.toString(16).padStart(2, '0')).join('');
  } catch (error) {
    return storeFailure(symbol, 'HASH_UNAVAILABLE', report.status,
      error instanceof Error ? error.message : 'sha256_unavailable', 6 * 60 * 60_000, deps);
  }

  const title = typeof letter.Title === 'string' ? letter.Title : '';
  const record: CodalDocumentRecord = {
    tracingNo, symbol,
    companyName: typeof letter.CompanyName === 'string' ? letter.CompanyName : '',
    title, sourceUrl,
    publishedAt: normalizeDigits(letter.PublishDateTime), periodEnd: parsed.periodEnd,
    receivedAt: now, lastUpdatedAt: now, contentHash, rawHtml: report.data,
    processingStatus: parsed.status, processingError: parsed.error, values: parsed.values,
  };
  const isStoredData = parsed.status === 'PARSED' && Boolean(parsed.periodEnd) && Boolean(parsed.values);
  const retryAt = isStoredData ? null : new Date(deps.now().getTime() + 6 * 60 * 60_000).toISOString();
  const outcome: CodalSyncOutcome = {
    symbol, attemptedAt: now, status: parsed.status, httpStatus: report.status,
    error: parsed.error, nextRetryAt: retryAt,
    failureStreak: isStoredData ? 0 : (previous?.failureStreak ?? 0) + 1,
    dataStored: isStoredData,
  };
  try {
    await deps.store.recordReport(record, outcome);
  } catch (error) {
    return { symbol, status: 'STORAGE_ERROR', httpStatus: report.status, retryAt: null,
      tracingNo, periodEnd: parsed.periodEnd, error: error instanceof Error ? error.message : String(error) };
  }
  return { symbol, status: parsed.status, httpStatus: report.status, retryAt,
    tracingNo, periodEnd: parsed.periodEnd, values: parsed.values, sourceUrl,
    error: parsed.error ?? undefined };
}

export async function readLatestStoredMonthlySales(symbol: string) {
  const [data, sync] = await Promise.all([
    codalStore.readLatestMonthlySales(symbol), codalStore.readSyncState(symbol),
  ]);
  const stale = Boolean(sync?.lastError || (sync?.lastStatus && sync.lastStatus !== 'PARSED'));
  return {
    status: data?.processingStatus === 'PARSED' && !stale ? 'DATA_AVAILABLE' : 'NOT_EVALUATED',
    freshness: stale ? 'STALE' : data ? 'CACHED' : 'UNKNOWN',
    data: data?.processingStatus === 'PARSED' ? data : null,
    sync,
  };
}

export function __resetCodalThrottleForTest(): void {
  lastCodalRequestAt = 0;
  codalRequestQueue = Promise.resolve();
}
