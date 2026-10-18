import { beforeEach, describe, expect, it } from 'vitest';
import { resolve } from 'node:path';
import initSqlJs from 'sql.js';
import {
  createCodalStore,
  migrateCodalDatabase,
  type CodalDocumentRecord,
  type CodalArtifactStorage,
  type CodalFinancialStatementRecord,
  type CodalSyncOutcome,
  type FinancialStatementValues,
} from '@shared/api/local/codalStore';
import {
  parseFinancialStatementReport,
  readLatestStoredFinancialStatement,
  selectFinancialSheets,
  syncLatestAnnualFinancialStatement,
} from '@shared/api/local/codalFinancial';
import { __resetCodalThrottleForTest, runCodalRequest } from '@shared/api/local/codalMonthly';

const cell = (rowSequence: number, columnSequence: number, value: string) =>
  ({ rowSequence, columnSequence, value });
const testSql = () => initSqlJs({ locateFile: () =>
  resolve(process.cwd(), 'node_modules/sql.js/dist/sql-wasm.wasm') });
const auditedTitle = 'صورت‌های مالی سال مالی منتهی به 1404/12/29 (حسابرسی شده)';

function sheetHtml(period: number | string, cells: Array<ReturnType<typeof cell>>): string {
  const datasource = { period, periodEndToDate: '1404/12/29',
    sheets: [{ tables: [{ description: 'میلیون ریال', cells }] }] };
  return `<html><script>\nvar datasource = ${JSON.stringify(datasource)};\n</script></html>`;
}

function incomeHtml(overrides: { period?: number | string; eps?: string | null } = {}): string {
  const cells = [
    cell(1, 1, 'جمع درآمدهای عملیاتی'), cell(1, 2, '250000'),
    cell(2, 1, 'سود (زیان) ناخالص'), cell(2, 2, '75000'),
    cell(3, 1, 'سود (زیان) عملیاتی'), cell(3, 2, '50000'),
    cell(4, 1, 'سود (زیان) خالص'), cell(4, 2, '40000'),
    ...(overrides.eps === null ? [] : [cell(5, 1, 'سود (زیان) خالص هر سهم'), cell(5, 2, overrides.eps ?? '125')]),
  ];
  return sheetHtml(overrides.period ?? 12, cells);
}

function balanceHtml(): string {
  return sheetHtml(12, [
    cell(1, 1, 'جمع داراییها'), cell(1, 2, '80000'),
    cell(1, 5, 'جمع بدهیها'), cell(1, 6, '30000'),
    cell(2, 5, 'جمع حقوق صاحبان سهام'), cell(2, 6, '50000'),
    cell(3, 5, 'سرمایه'), cell(3, 6, '10000'),
    cell(4, 5, 'سود (زیان) انباشته'), cell(4, 6, '12000'),
  ]);
}

function memoryStorage() {
  let bytes: Uint8Array | null = null;
  const storage: CodalArtifactStorage = {
    async read() { return bytes?.slice() ?? null; },
    async write(value) { bytes = value.slice(); },
  };
  return { storage, current: () => bytes?.slice() ?? null };
}

const values: FinancialStatementValues = {
  periodMonths: 12, revenue: 250000, grossProfit: 75000, operatingProfit: 50000,
  netProfit: 40000, basicEps: 125, totalAssets: 80000, totalLiabilities: 30000,
  totalEquity: 50000, capital: 10000, retainedEarnings: 12000, unit: 'میلیون ریال',
  audited: true, consolidated: false, fiscalYear: '1404',
};

function record(overrides: Partial<CodalFinancialStatementRecord> = {}): CodalFinancialStatementRecord {
  return {
    tracingNo: '1700001', symbol: 'خساپا', companyName: 'شرکت نمونه', title: auditedTitle,
    sourceUrl: 'https://codal.ir/Reports/Decision.aspx?LetterSerial=annual1',
    publishedAt: '1405/02/20 10:00:00', periodEnd: '1404/12/29',
    receivedAt: '2026-10-18T10:00:00.000Z', lastUpdatedAt: '2026-10-18T10:00:00.000Z',
    contentHash: 'a'.repeat(64), rawHtml: incomeHtml(), reportType: 'annual_financial_statement',
    processingStatus: 'PARSED', processingError: null, values: null, financialValues: values,
    ...overrides,
  };
}

function outcome(overrides: Partial<CodalSyncOutcome> = {}): CodalSyncOutcome {
  return {
    symbol: 'خساپا', reportType: 'annual_financial_statement',
    attemptedAt: '2026-10-18T10:00:00.000Z', status: 'PARSED', httpStatus: 200,
    error: null, nextRetryAt: null, failureStreak: 0, dataStored: true, ...overrides,
  };
}

describe('Codal annual financial-statement parser', () => {
  it('selects the standalone income and balance sheets before consolidated sheets', () => {
    expect(selectFinancialSheets('<select><option value="2">صورت سود و زیان تلفیقی'
      + '<option value="1">صورت سود و زیان<option value="4">صورت وضعیت مالی</select>'))
      .toEqual({ incomeSheetId: '1', incomeConsolidated: false, balanceSheetId: '4' });
  });

  it('maps annual statement values and preserves missing EPS as null', () => {
    const parsed = parseFinancialStatementReport(auditedTitle, incomeHtml({ eps: null }), balanceHtml(), false);
    expect(parsed).toMatchObject({ status: 'PARSED', periodEnd: '1404/12/29', periodMonths: 12,
      audited: true, consolidated: false, error: null });
    expect(parsed.values).toMatchObject({ revenue: 250000, grossProfit: 75000,
      operatingProfit: 50000, netProfit: 40000, basicEps: null, totalAssets: 80000,
      totalLiabilities: 30000, totalEquity: 50000, capital: 10000,
      retainedEarnings: 12000, unit: 'میلیون ریال', fiscalYear: '1404' });
  });

  it('does not evaluate consolidated, unaudited or non-annual reports as FTS evidence', () => {
    expect(parseFinancialStatementReport(auditedTitle, incomeHtml(), null, true))
      .toMatchObject({ status: 'NOT_EVALUATED', error: 'standalone_income_statement_missing' });
    expect(parseFinancialStatementReport('صورت‌های مالی سال مالی منتهی به 1404/12/29 (حسابرسی نشده)',
      incomeHtml(), null, false)).toMatchObject({ status: 'NOT_EVALUATED', audited: false });
    expect(parseFinancialStatementReport(auditedTitle, incomeHtml({ period: 9 }), null, false))
      .toMatchObject({ status: 'NOT_EVALUATED', periodMonths: 9, error: 'report_period_not_12_months' });
  });

  it('does not replace a published blank operating-revenue total with a weaker component row', () => {
    const html = sheetHtml(12, [
      cell(1, 1, 'درآمد متفرقه'), cell(1, 2, '9000'),
      cell(2, 1, 'جمع درآمدهای عملیاتی'), cell(2, 2, '—'),
    ]);
    expect(parseFinancialStatementReport(auditedTitle, html, null, false))
      .toMatchObject({ status: 'INCOMPLETE', error: 'operating_revenue_missing', values: { revenue: null } });
  });
});

describe('Codal financial-statements SQLite migrations', () => {
  it('upserts corrections once and keeps v1 data during the additive migration', async () => {
    const SQL = await testSql();
    const db = new SQL.Database();
    db.run('CREATE TABLE preserved_marker (value TEXT)');
    db.run("INSERT INTO preserved_marker VALUES ('kept')");
    migrateCodalDatabase(db);
    db.run(`INSERT INTO codal_documents
      (tracing_no, symbol, report_type, source, source_url, received_at, last_updated_at,
       content_hash, raw_html, processing_status)
      VALUES ('legacy-monthly', 'خساپا', 'monthly_activity', 'codal.ir',
        'https://codal.ir/Reports/Decision.aspx?LetterSerial=old',
        '2026-10-18T09:00:00.000Z', '2026-10-18T09:00:00.000Z', 'old-hash', '<html/>', 'PARSED')`);
    db.run(`INSERT INTO monthly_sales
      (tracing_no, symbol, report_period, source, source_url, received_at, last_updated_at, processing_status)
      VALUES ('legacy-monthly', 'خساپا', '1405/06/31', 'codal.ir',
        'https://codal.ir/Reports/Decision.aspx?LetterSerial=old',
        '2026-10-18T09:00:00.000Z', '2026-10-18T09:00:00.000Z', 'PARSED')`);
    db.run('DROP TABLE financial_statements');
    db.run('PRAGMA user_version = 1');
    migrateCodalDatabase(db);
    expect(Number(db.exec('PRAGMA user_version')[0]?.values[0]?.[0])).toBe(3);
    expect(db.exec('SELECT value FROM preserved_marker')[0]?.values).toEqual([['kept']]);
    expect(db.exec("SELECT name FROM sqlite_master WHERE name='financial_statements'")[0]?.values).toHaveLength(1);
    expect(db.exec("SELECT name FROM sqlite_master WHERE name='codal_monthly_history_checkpoint'")[0]?.values).toHaveLength(1);
    expect(db.exec('SELECT COUNT(*) FROM monthly_sales')[0]?.values[0]?.[0]).toBe(1);
    expect(db.exec('SELECT COUNT(*) FROM codal_documents')[0]?.values[0]?.[0]).toBe(1);
    db.close();

    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    await store.recordFinancialStatement(record(), outcome());
    await store.recordFinancialStatement(record({
      contentHash: 'b'.repeat(64), lastUpdatedAt: '2026-10-18T11:00:00.000Z',
      financialValues: { ...values, basicEps: 130 },
    }), outcome({ attemptedAt: '2026-10-18T11:00:00.000Z' }));
    expect((await store.readLatestFinancialStatement('خساپا'))?.basicEps).toBe(130);
    const saved = new SQL.Database(local.current()!);
    expect(saved.exec('SELECT COUNT(*) FROM codal_documents')[0]?.values[0]?.[0]).toBe(1);
    expect(saved.exec('SELECT COUNT(*) FROM financial_statements')[0]?.values[0]?.[0]).toBe(1);
    saved.close();

    await store.recordFinancialStatement(record({
      processingStatus: 'UNSUPPORTED', processingError: 'sheet_missing',
      financialValues: null, lastUpdatedAt: '2026-10-18T12:00:00.000Z',
    }), outcome({ status: 'UNSUPPORTED', error: 'sheet_missing', dataStored: false,
      attemptedAt: '2026-10-18T12:00:00.000Z' }));
    expect((await store.readLatestFinancialStatement('خساپا'))?.processingStatus).toBe('NOT_EVALUATED');
    expect((await store.readFinancialSyncState('خساپا'))?.reportType).toBe('annual_financial_statement');
    await expect(readLatestStoredFinancialStatement('خساپا', store))
      .resolves.toMatchObject({ status: 'NOT_EVALUATED', freshness: 'STALE', data: null });
    expect((await createCodalStore(local.storage, testSql)
      .readLatestFinancialStatement('خساپا'))?.processingStatus).toBe('NOT_EVALUATED');
  });

  it('serializes concurrent monthly and annual writes to the shared sidecar', async () => {
    let bytes: Uint8Array | null = null;
    const storage: CodalArtifactStorage = {
      async read() {
        const snapshot = bytes?.slice() ?? null;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return snapshot;
      },
      async write(next) {
        await new Promise((resolve) => setTimeout(resolve, 5));
        bytes = next.slice();
      },
    };
    const store = createCodalStore(storage, testSql);
    const monthly: CodalDocumentRecord = {
      tracingNo: '1599533', symbol: 'خساپا', companyName: 'شرکت نمونه',
      title: 'گزارش فعالیت ماهانه', sourceUrl: 'https://codal.ir/Reports/Decision.aspx?LetterSerial=monthly1',
      publishedAt: '1405/07/07 18:29:23', periodEnd: '1405/06/31',
      receivedAt: '2026-10-18T10:00:00.000Z', lastUpdatedAt: '2026-10-18T10:00:00.000Z',
      contentHash: 'c'.repeat(64), rawHtml: '<html/>', processingStatus: 'PARSED',
      processingError: null,
      values: { monthlyRevenue: 10, ytdRevenue: 20, monthlyRevenuePrev: null,
        ytdRevenuePrev: null, monthlyVolume: null, ytdVolume: null, volumeUnit: null },
    };
    await Promise.all([
      store.recordReport(monthly, outcome({ reportType: 'monthly_activity' })),
      store.recordFinancialStatement(record(), outcome()),
    ]);
    const SQL = await testSql();
    const db = new SQL.Database(bytes!);
    expect(db.exec('SELECT COUNT(*) FROM monthly_sales')[0]?.values[0]?.[0]).toBe(1);
    expect(db.exec('SELECT COUNT(*) FROM financial_statements')[0]?.values[0]?.[0]).toBe(1);
    expect(db.exec('SELECT COUNT(*) FROM codal_documents')[0]?.values[0]?.[0]).toBe(2);
    db.close();
  });
});

describe('Codal annual financial sync', () => {
  beforeEach(() => __resetCodalThrottleForTest());

  it('serializes Codal requests and keeps the configured start-to-start gap', async () => {
    let clock = new Date('2026-10-18T10:00:00.000Z');
    let releaseFirst!: () => void;
    let markFirstStarted!: () => void;
    const firstStarted = new Promise<void>((resolve) => { markFirstStarted = resolve; });
    const firstGate = new Promise<void>((resolve) => { releaseFirst = resolve; });
    const starts: string[] = [];
    const sleeps: number[] = [];
    const now = () => clock;
    const sleep = async (ms: number) => {
      sleeps.push(ms);
      clock = new Date(clock.getTime() + ms);
    };
    const first = runCodalRequest(async () => {
      starts.push('first');
      markFirstStarted();
      await firstGate;
      return 1;
    }, now, sleep);
    await firstStarted;
    const second = runCodalRequest(async () => { starts.push('second'); return 2; }, now, sleep);
    await Promise.resolve();
    expect(starts).toEqual(['first']);
    releaseFirst();
    await expect(Promise.all([first, second])).resolves.toEqual([1, 2]);
    expect(starts).toEqual(['first', 'second']);
    expect(sleeps).toEqual([1700]);
  });

  it('fetches a category-1 annual audited notice and stores its standalone statements', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    const getJson = async (url: string) => {
      expect(url).toContain('Category=1');
      expect(url).toContain('Symbol=%D8%AE%D8%B3%D8%A7%D9%BE%D8%A7');
      return { status: 200, headers: {}, data: { Letters: [{
        TracingNo: 1700001, Symbol: 'خساپا', CompanyName: 'شرکت نمونه', Title: auditedTitle,
        Url: '/Reports/Decision.aspx?LetterSerial=annual1', PublishDateTime: '1405/02/20 10:00:00',
      }] } };
    };
    const getText = async (url: string) => {
      const parsedUrl = new URL(url);
      const sheetId = parsedUrl.searchParams.get('sheetId');
      const data = sheetId === null
        ? '<select><option value="2">صورت سود و زیان تلفیقی<option value="1">صورت سود و زیان'
          + '<option value="4">صورت وضعیت مالی</select>'
        : sheetId === '1' ? incomeHtml() : balanceHtml();
      return { status: 200, headers: {}, data };
    };
    const result = await syncLatestAnnualFinancialStatement('خساپا', {
      store, getJson, getText, now: () => new Date('2026-10-18T10:00:00.000Z'), sleep: async () => {},
    });
    expect(result).toMatchObject({ status: 'PARSED', tracingNo: '1700001', periodEnd: '1404/12/29' });
    expect((await store.readLatestFinancialStatement('خساپا'))?.basicEps).toBe(125);
    expect((await store.readFinancialSyncState('خساپا'))?.lastSuccessAt).toBe('2026-10-18T10:00:00.000Z');
  });

  it('stores a 429 cooldown instead of retrying or claiming fresh data', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    let requests = 0;
    const getJson = async () => { requests += 1; return { status: 429, headers: {}, data: null }; };
    const deps = { store, getJson, getText: async () => ({ status: 0, headers: {}, data: null }),
      now: () => new Date('2026-10-18T10:00:00.000Z'), sleep: async () => {} };
    expect((await syncLatestAnnualFinancialStatement('خساپا', deps)).status).toBe('RATE_LIMITED');
    expect((await syncLatestAnnualFinancialStatement('خساپا', deps)).status).toBe('COOLDOWN');
    expect(requests).toBe(1);
  });
});
