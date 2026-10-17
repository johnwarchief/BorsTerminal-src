import { beforeEach, describe, expect, it, vi } from 'vitest';
import { resolve } from 'node:path';
import initSqlJs from 'sql.js';
import {
  createCodalStore, migrateCodalDatabase,
  type CodalArtifactStorage, type CodalDocumentRecord, type CodalSyncOutcome,
} from '@shared/api/local/codalStore';
import {
  __resetCodalThrottleForTest, parseMonthlyActivityReportHtml, syncLatestMonthlySales,
} from '@shared/api/local/codalMonthly';

const cell = (rowSequence: number, columnSequence: number, value: string) =>
  ({ rowSequence, columnSequence, value });
const testSql = () => initSqlJs({ locateFile: () =>
  resolve(process.cwd(), 'node_modules/sql.js/dist/sql-wasm.wasm') });

function monthlyHtml(overrides: Record<string, unknown> = {}): string {
  const datasource = {
    periodEndToDate: '1405/06/31',
    sheets: [{ tables: [{ cells: [
      cell(1, 3, 'دوره یک ماهه منتهی به'), cell(1, 7, 'از ابتدای سال مالی تا'),
      cell(1, 11, 'دوره یک ماهه منتهی به'), cell(1, 15, 'از ابتدای سال مالی تا'),
      cell(2, 2, 'واحد'), cell(2, 4, 'تعداد فروش'), cell(2, 5, 'مبلغ فروش'),
      cell(2, 8, 'تعداد فروش'), cell(2, 9, 'مبلغ فروش'),
      cell(2, 12, 'تعداد فروش'), cell(2, 13, 'مبلغ فروش'),
      cell(2, 16, 'تعداد فروش'), cell(2, 17, 'مبلغ فروش'),
      cell(3, 1, 'محصول'), cell(3, 2, 'تن'), cell(3, 4, '60'), cell(3, 8, '240'),
      cell(4, 1, 'جمع'), cell(4, 4, '60'), cell(4, 5, '1200'),
      cell(4, 8, '240'), cell(4, 9, '5200'), cell(4, 12, '55'),
      cell(4, 13, '1000'), cell(4, 16, '210'), cell(4, 17, '4800'),
    ] }] }],
    ...overrides,
  };
  return `<html><script>\nvar datasource = ${JSON.stringify(datasource)};\n</script></html>`;
}

function memoryStorage(initial: Uint8Array | null = null) {
  let bytes = initial?.slice() ?? null;
  return {
    storage: {
      async read() { return bytes?.slice() ?? null; },
      async write(next: Uint8Array) { bytes = next.slice(); },
    } satisfies CodalArtifactStorage,
    current() { return bytes?.slice() ?? null; },
  };
}

function record(overrides: Partial<CodalDocumentRecord> = {}): CodalDocumentRecord {
  return {
    tracingNo: '1599533', symbol: 'خساپا', companyName: 'شرکت نمونه',
    title: 'گزارش فعالیت ماهانه', sourceUrl: 'https://codal.ir/Reports/Decision.aspx?LetterSerial=abc',
    publishedAt: '1405/07/07 18:29:23', periodEnd: '1405/06/31',
    receivedAt: '2026-10-18T08:00:00.000Z', lastUpdatedAt: '2026-10-18T08:00:00.000Z',
    contentHash: 'a'.repeat(64), rawHtml: monthlyHtml(), processingStatus: 'PARSED',
    processingError: null,
    values: { monthlyRevenue: 1200, ytdRevenue: 5200, monthlyRevenuePrev: 1000,
      ytdRevenuePrev: 4800, monthlyVolume: 60, ytdVolume: 240, volumeUnit: 'تن' },
    ...overrides,
  };
}

function outcome(overrides: Partial<CodalSyncOutcome> = {}): CodalSyncOutcome {
  return {
    symbol: 'خساپا', attemptedAt: '2026-10-18T08:00:00.000Z', status: 'PARSED',
    httpStatus: 200, error: null, nextRetryAt: null, failureStreak: 0, dataStored: true,
    ...overrides,
  };
}

describe('Codal monthly activity parser', () => {
  it('selects the total row and maps monthly/YTD and prior-year columns', () => {
    const parsed = parseMonthlyActivityReportHtml(monthlyHtml());
    expect(parsed).toEqual({
      status: 'PARSED', periodEnd: '1405/06/31', error: null,
      values: { monthlyRevenue: 1200, ytdRevenue: 5200, monthlyRevenuePrev: 1000,
        ytdRevenuePrev: 4800, monthlyVolume: 60, ytdVolume: 240, volumeUnit: 'تن' },
    });
  });

  it('keeps an unsupported page unevaluated instead of inventing zeroes', () => {
    expect(parseMonthlyActivityReportHtml('<html>challenge page</html>')).toMatchObject({
      status: 'UNSUPPORTED', values: null, error: 'datasource_missing_or_invalid',
    });
  });

  it('does not promote a recognized sales table without a total amount', () => {
    const html = monthlyHtml({ periodEndToDate: '1405/06/31', sheets: [{ tables: [{ cells: [
      cell(1, 3, 'دوره یک ماهه منتهی به'), cell(2, 5, 'مبلغ فروش'),
      cell(3, 1, 'محصول'), cell(3, 5, '100'),
    ] }] }] });
    expect(parseMonthlyActivityReportHtml(html)).toMatchObject({ status: 'INCOMPLETE', values: null });
  });
});

describe('Codal local SQLite schema and writes', () => {
  it('migrates idempotently and refuses a future schema without overwriting it', async () => {
    const SQL = await testSql();
    const db = new SQL.Database();
    db.run('CREATE TABLE legacy_marker (value TEXT)');
    migrateCodalDatabase(db);
    migrateCodalDatabase(db);
    expect(Number(db.exec('PRAGMA user_version')[0]?.values[0]?.[0])).toBe(2);
    expect(db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='codal_documents'")[0]?.values).toHaveLength(1);
    expect(db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='legacy_marker'")[0]?.values).toHaveLength(1);
    db.run('DROP TABLE financial_statements');
    db.run('PRAGMA user_version = 1');
    migrateCodalDatabase(db);
    expect(Number(db.exec('PRAGMA user_version')[0]?.values[0]?.[0])).toBe(2);
    expect(db.exec("SELECT name FROM sqlite_master WHERE type='table' AND name='financial_statements'")[0]?.values).toHaveLength(1);
    expect(db.exec('SELECT COUNT(*) FROM legacy_marker')[0]?.values[0]?.[0]).toBe(0);
    db.run('PRAGMA user_version = 99');
    expect(() => migrateCodalDatabase(db)).toThrow('Unsupported Codal schema version 99');
    expect(Number(db.exec('PRAGMA user_version')[0]?.values[0]?.[0])).toBe(99);
    const futureBytes = db.export();
    db.close();
    const futureStorage = memoryStorage(futureBytes);
    const futureStore = createCodalStore(futureStorage.storage, testSql);
    await expect(futureStore.readSyncState('خساپا')).rejects.toThrow('Unsupported Codal schema version 99');
    expect(futureStorage.current()).toEqual(futureBytes);
  });

  it('upserts a correction by tracing number and preserves the last durable copy on write failure', async () => {
    const durable = memoryStorage();
    const store = createCodalStore(durable.storage, testSql);
    await store.recordReport(record(), outcome());
    await store.recordReport(record({
      contentHash: 'b'.repeat(64), lastUpdatedAt: '2026-10-18T09:00:00.000Z',
      values: { monthlyRevenue: 1250, ytdRevenue: 5250, monthlyRevenuePrev: 1000,
        ytdRevenuePrev: 4800, monthlyVolume: 60, ytdVolume: 240, volumeUnit: 'تن' },
    }), outcome({ attemptedAt: '2026-10-18T09:00:00.000Z' }));
    expect((await store.readLatestMonthlySales('خساپا'))?.monthlyRevenue).toBe(1250);
    const SQL = await testSql();
    const savedDb = new SQL.Database(durable.current()!);
    expect(savedDb.exec('SELECT COUNT(*) FROM codal_documents')[0]?.values[0]?.[0]).toBe(1);
    expect(savedDb.exec('SELECT content_hash FROM codal_documents')[0]?.values[0]?.[0]).toBe('b'.repeat(64));
    savedDb.close();

    const beforeFailure = durable.current();
    const failingStorage: CodalArtifactStorage = {
      read: durable.storage.read,
      async write() { throw new Error('disk full'); },
    };
    const failingStore = createCodalStore(failingStorage, testSql);
    await expect(failingStore.recordReport(record({
      lastUpdatedAt: '2026-10-18T10:00:00.000Z',
      values: { monthlyRevenue: 9999, ytdRevenue: 9999, monthlyRevenuePrev: null,
        ytdRevenuePrev: null, monthlyVolume: null, ytdVolume: null, volumeUnit: null },
    }), outcome())).rejects.toThrow('disk full');
    expect(durable.current()).toEqual(beforeFailure);
    expect((await store.readLatestMonthlySales('خساپا'))?.monthlyRevenue).toBe(1250);
  });

  it('marks a previously stored period unevaluated when a correction has an unknown shape', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    await store.recordReport(record(), outcome());
    await store.recordReport(record({
      processingStatus: 'UNSUPPORTED', processingError: 'datasource_missing_or_invalid',
      values: null, lastUpdatedAt: '2026-10-18T09:00:00.000Z',
    }), outcome({ status: 'UNSUPPORTED', dataStored: false, error: 'datasource_missing_or_invalid' }));
    expect((await store.readLatestMonthlySales('خساپا'))?.processingStatus).toBe('NOT_EVALUATED');
  });

  it('builds a bounded desktop-shaped monthly series and excludes reports for another entity', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    await store.recordReport(record({ tracingNo: '100', periodEnd: '1404/06/31',
      values: { monthlyRevenue: 300, ytdRevenue: 2100, monthlyRevenuePrev: null,
        ytdRevenuePrev: null, monthlyVolume: null, ytdVolume: null, volumeUnit: null } }), outcome());
    await store.recordReport(record({ tracingNo: '101', periodEnd: '1405/06/31',
      values: { monthlyRevenue: 400, ytdRevenue: 3600, monthlyRevenuePrev: null,
        ytdRevenuePrev: 2100, monthlyVolume: null, ytdVolume: null, volumeUnit: null } }), outcome());
    await store.recordReport(record({ tracingNo: '102', title: 'گزارش فعالیت ماهانه (شرکت هلپاک)',
      periodEnd: '1405/07/30', values: { monthlyRevenue: 9000, ytdRevenue: 99000,
        monthlyRevenuePrev: null, ytdRevenuePrev: null, monthlyVolume: null,
        ytdVolume: null, volumeUnit: null } }), outcome());

    const series = await store.readMonthlyRevenueSeries('خساپا', 60);
    expect(series).toMatchObject({ coverage: 'INCOMPLETE',
      reason: 'identity_or_history_coverage_unverified' });
    expect(series.rows.map(({ periodEnd, ytdRevenue, ytdRevenuePrev }) =>
      ({ periodEnd, ytdRevenue, ytdRevenuePrev }))).toEqual([
      { periodEnd: '1405/06/31', ytdRevenue: 3600, ytdRevenuePrev: 2100 },
      { periodEnd: '1404/06/31', ytdRevenue: 2100, ytdRevenuePrev: null },
    ]);
  });

  it('keeps desktop scope exemptions and only returns rows with positive YTD revenue', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    await store.recordReport(record({ tracingNo: '200', title: 'گزارش فعالیت ماهانه (حسابرسی شده)',
      values: { monthlyRevenue: 100, ytdRevenue: 100, monthlyRevenuePrev: null,
        ytdRevenuePrev: null, monthlyVolume: null, ytdVolume: null, volumeUnit: null } }), outcome());
    await store.recordReport(record({ tracingNo: '201', periodEnd: '1405/07/30',
      values: { monthlyRevenue: -1, ytdRevenue: -1, monthlyRevenuePrev: null,
        ytdRevenuePrev: null, monthlyVolume: null, ytdVolume: null, volumeUnit: null } }), outcome());

    const series = await store.readMonthlyRevenueSeries('خساپا', 1);
    expect(series.rows).toHaveLength(1);
    expect(series.rows[0]).toMatchObject({ tracingNo: '200', periodEnd: '1405/06/31',
      source: 'codal.ir', processingStatus: 'PARSED' });
  });
});

describe('Codal monthly sync vertical slice', () => {
  beforeEach(() => {
    __resetCodalThrottleForTest();
    vi.restoreAllMocks();
  });

  it('fetches a bounded symbol query, parses a report, and stores it locally', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    const now = new Date('2026-10-18T08:00:00.000Z');
    const getJson = vi.fn(async (_url: string, _headers: Record<string, string>) => {
      void [_url, _headers];
      return { status: 200, headers: {}, data: { Letters: [{
      TracingNo: 1599533, Symbol: 'خساپا', CompanyName: 'شرکت نمونه',
      Title: 'گزارش فعالیت ماهانه دوره یک ماهه',
      Url: '/Reports/Decision.aspx?LetterSerial=abc123', PublishDateTime: '1405/07/07 18:29:23',
      }] } };
    });
    const getText = vi.fn(async (_url: string, _headers: Record<string, string>) => {
      void [_url, _headers];
      return { status: 200, headers: {}, data: monthlyHtml() };
    });
    const result = await syncLatestMonthlySales('خساپا', {
      store, getJson, getText, now: () => now, sleep: async () => {},
    });
    expect(result.status).toBe('PARSED');
    expect(result.httpStatus).toBe(200);
    expect(getJson).toHaveBeenCalledTimes(1);
    expect(getText).toHaveBeenCalledTimes(1);
    expect(getJson.mock.calls[0]?.[0]).toContain('Category=3');
    expect(getJson.mock.calls[0]?.[0]).toContain('Symbol=%D8%AE%D8%B3%D8%A7%D9%BE%D8%A7');
    expect(getJson.mock.calls[0]?.[0]).toContain('FromDate=1400%2F01%2F01');
    expect((await store.readLatestMonthlySales('خساپا'))?.monthlyRevenue).toBe(1200);
  });

  it('starts the next symbol query from the latest stored Codal publication date', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    await store.recordReport(record(), outcome());
    const getJson = vi.fn(async (_url: string, _headers: Record<string, string>) => {
      void [_url, _headers];
      return { status: 200, headers: {}, data: { Letters: [] } };
    });
    await syncLatestMonthlySales('خساپا', {
      store, getJson, getText: vi.fn(), now: () => new Date('2026-10-18T10:00:00.000Z'),
      sleep: async () => {},
    });
    expect(getJson.mock.calls[0]?.[0]).toContain('FromDate=1405%2F07%2F07');
  });

  it('records a 429 and enforces cooldown without a retry loop', async () => {
    const local = memoryStorage();
    const store = createCodalStore(local.storage, testSql);
    const now = new Date('2026-10-18T08:00:00.000Z');
    const getJson = vi.fn(async () => ({ status: 429, headers: {}, data: null }));
    const deps = { store, getJson, getText: vi.fn(), now: () => now, sleep: async () => {} };
    const first = await syncLatestMonthlySales('خساپا', deps);
    const second = await syncLatestMonthlySales('خساپا', deps);
    expect(first.status).toBe('RATE_LIMITED');
    expect(second.status).toBe('COOLDOWN');
    expect(getJson).toHaveBeenCalledTimes(1);
  });
});
