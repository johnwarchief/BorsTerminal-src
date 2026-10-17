import type { Database } from 'sql.js';
import { getSql } from './localData';

export type MonthlySalesValues = {
  monthlyRevenue: number | null;
  ytdRevenue: number | null;
  monthlyRevenuePrev: number | null;
  ytdRevenuePrev: number | null;
  monthlyVolume: number | null;
  ytdVolume: number | null;
  volumeUnit: string | null;
};

export type FinancialStatementValues = {
  periodMonths: number | null;
  revenue: number | null;
  grossProfit: number | null;
  operatingProfit: number | null;
  netProfit: number | null;
  basicEps: number | null;
  totalAssets: number | null;
  totalLiabilities: number | null;
  totalEquity: number | null;
  capital: number | null;
  retainedEarnings: number | null;
  unit: string | null;
  audited: boolean;
  consolidated: boolean | null;
  fiscalYear: string | null;
};

export type CodalProcessingStatus = 'PARSED' | 'UNSUPPORTED' | 'INCOMPLETE' | 'NOT_EVALUATED';

export type CodalDocumentRecord = {
  tracingNo: string;
  symbol: string;
  companyName: string;
  title: string;
  sourceUrl: string;
  publishedAt: string | null;
  periodEnd: string | null;
  receivedAt: string;
  lastUpdatedAt: string;
  contentHash: string;
  rawHtml: string;
  reportType?: string;
  processingStatus: CodalProcessingStatus;
  processingError: string | null;
  values: MonthlySalesValues | null;
};

export type CodalFinancialStatementRecord = Omit<CodalDocumentRecord, 'values'> & {
  values: null;
  financialValues: FinancialStatementValues | null;
};

export type CodalSyncOutcome = {
  symbol: string;
  reportType?: string;
  attemptedAt: string;
  status: string;
  httpStatus: number | null;
  error: string | null;
  nextRetryAt: string | null;
  failureStreak: number;
  dataStored: boolean;
};

export type CodalSyncState = {
  symbol: string;
  reportType: string;
  lastAttemptAt: string;
  lastSuccessAt: string | null;
  lastStatus: string;
  lastHttpStatus: number | null;
  lastError: string | null;
  nextRetryAt: string | null;
  failureStreak: number;
};

export type CodalMonthlySalesRow = MonthlySalesValues & {
  tracingNo: string;
  symbol: string;
  periodEnd: string;
  source: string;
  sourceUrl: string;
  publishedAt: string | null;
  receivedAt: string;
  lastUpdatedAt: string;
  processingStatus: CodalProcessingStatus;
};

export type CodalFinancialStatementRow = FinancialStatementValues & {
  tracingNo: string;
  symbol: string;
  companyName: string;
  title: string;
  periodEnd: string;
  source: string;
  sourceUrl: string;
  publishedAt: string | null;
  receivedAt: string;
  lastUpdatedAt: string;
  processingStatus: CodalProcessingStatus;
};

export type CodalArtifactStorage = {
  read(): Promise<Uint8Array | null>;
  write(bytes: Uint8Array): Promise<void>;
};

type SqlRuntime = Awaited<ReturnType<typeof getSql>>;

const SCHEMA_VERSION = 2;
const REPORT_TYPE = 'monthly_activity';
const FINANCIAL_REPORT_TYPE = 'annual_financial_statement';
const CACHE_NAME = 'bors-mobile-codal-local-v1';
const DB_PATH = '/__bors_local/codal-delta-v1.sqlite';

function dbRequest(): Request {
  const origin = typeof location === 'undefined' ? 'https://localhost' : location.origin;
  return new Request(new URL(DB_PATH, origin).href);
}

const cacheStorage: CodalArtifactStorage = {
  async read() {
    if (typeof caches === 'undefined') throw new Error('Cache API unavailable');
    const cache = await caches.open(CACHE_NAME);
    const response = await cache.match(dbRequest());
    return response ? new Uint8Array(await response.arrayBuffer()) : null;
  },
  async write(bytes) {
    if (typeof caches === 'undefined') throw new Error('Cache API unavailable');
    const cache = await caches.open(CACHE_NAME);
    const copy = bytes.slice();
    await cache.put(dbRequest(), new Response(copy.buffer as ArrayBuffer, {
      headers: { 'Content-Type': 'application/vnd.sqlite3' },
    }));
  },
};

export function migrateCodalDatabase(db: Database): void {
  db.run('PRAGMA foreign_keys = ON');
  const versionRow = db.exec('PRAGMA user_version')[0]?.values?.[0]?.[0];
  const version = Number(versionRow ?? 0);
  if (!Number.isInteger(version) || version < 0) throw new Error('Invalid Codal schema version');
  if (version > SCHEMA_VERSION) throw new Error(`Unsupported Codal schema version ${version}`);
  if (version === SCHEMA_VERSION) return;

  db.run('BEGIN IMMEDIATE');
  try {
    if (version === 0) db.exec(`
      CREATE TABLE codal_documents (
        tracing_no TEXT PRIMARY KEY,
        symbol TEXT NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        report_type TEXT NOT NULL,
        source TEXT NOT NULL,
        source_url TEXT NOT NULL,
        published_at TEXT,
        report_period TEXT,
        received_at TEXT NOT NULL,
        last_updated_at TEXT NOT NULL,
        content_hash TEXT NOT NULL,
        raw_html TEXT NOT NULL,
        processing_status TEXT NOT NULL CHECK (processing_status IN
          ('PARSED', 'UNSUPPORTED', 'INCOMPLETE', 'NOT_EVALUATED')),
        processing_error TEXT
      );
      CREATE INDEX ix_codal_documents_symbol_period
        ON codal_documents(symbol, report_period DESC);
      CREATE TABLE monthly_sales (
        tracing_no TEXT PRIMARY KEY REFERENCES codal_documents(tracing_no) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        report_period TEXT NOT NULL,
        monthly_revenue REAL,
        ytd_revenue REAL,
        monthly_revenue_prev REAL,
        ytd_revenue_prev REAL,
        monthly_volume REAL,
        ytd_volume REAL,
        volume_unit TEXT,
        source TEXT NOT NULL,
        source_url TEXT NOT NULL,
        published_at TEXT,
        received_at TEXT NOT NULL,
        last_updated_at TEXT NOT NULL,
        processing_status TEXT NOT NULL CHECK (processing_status IN
          ('PARSED', 'UNSUPPORTED', 'INCOMPLETE', 'NOT_EVALUATED'))
      );
      CREATE INDEX ix_codal_monthly_sales_symbol_period
        ON monthly_sales(symbol, report_period DESC);
      CREATE TABLE codal_sync_state (
        symbol TEXT NOT NULL,
        report_type TEXT NOT NULL,
        last_attempt_at TEXT NOT NULL,
        last_success_at TEXT,
        last_status TEXT NOT NULL,
        last_http_status INTEGER,
        last_error TEXT,
        next_retry_at TEXT,
        failure_streak INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY(symbol, report_type)
      );
    `);
    if (version === 0 || version === 1) db.exec(`
      CREATE TABLE IF NOT EXISTS financial_statements (
        tracing_no TEXT PRIMARY KEY REFERENCES codal_documents(tracing_no) ON DELETE CASCADE,
        symbol TEXT NOT NULL,
        company_name TEXT NOT NULL DEFAULT '',
        title TEXT NOT NULL DEFAULT '',
        report_period TEXT,
        period_months INTEGER,
        revenue REAL,
        gross_profit REAL,
        operating_profit REAL,
        net_profit REAL,
        basic_eps REAL,
        total_assets REAL,
        total_liabilities REAL,
        total_equity REAL,
        capital REAL,
        retained_earnings REAL,
        unit TEXT,
        is_audited INTEGER,
        is_consolidated INTEGER,
        fiscal_year TEXT,
        source TEXT NOT NULL,
        source_url TEXT NOT NULL,
        published_at TEXT,
        received_at TEXT NOT NULL,
        last_updated_at TEXT NOT NULL,
        processing_status TEXT NOT NULL CHECK (processing_status IN
          ('PARSED', 'UNSUPPORTED', 'INCOMPLETE', 'NOT_EVALUATED'))
      );
      CREATE INDEX IF NOT EXISTS ix_codal_financial_statements_symbol_period
        ON financial_statements(symbol, report_period DESC, published_at DESC);
    `);
    db.run(`PRAGMA user_version = ${SCHEMA_VERSION}`);
    db.run('COMMIT');
  } catch (error) {
    try { db.run('ROLLBACK'); } catch { /* retain migration error */ }
    throw error;
  }
}

function openDatabase(SQL: SqlRuntime, bytes: Uint8Array | null): Database {
  const db = bytes ? new SQL.Database(bytes) : new SQL.Database();
  try {
    migrateCodalDatabase(db);
    return db;
  } catch (error) {
    db.close();
    throw error;
  }
}

function readSyncState(db: Database, symbol: string, reportType = REPORT_TYPE): CodalSyncState | null {
  const stmt = db.prepare(`SELECT symbol, report_type, last_attempt_at, last_success_at,
    last_status, last_http_status, last_error, next_retry_at, failure_streak
    FROM codal_sync_state WHERE symbol = ? AND report_type = ?`);
  try {
    stmt.bind([symbol, reportType]);
    if (!stmt.step()) return null;
    const row = stmt.getAsObject();
    return {
      symbol: String(row.symbol),
      reportType: String(row.report_type),
      lastAttemptAt: String(row.last_attempt_at),
      lastSuccessAt: typeof row.last_success_at === 'string' ? row.last_success_at : null,
      lastStatus: String(row.last_status),
      lastHttpStatus: typeof row.last_http_status === 'number' ? row.last_http_status : null,
      lastError: typeof row.last_error === 'string' ? row.last_error : null,
      nextRetryAt: typeof row.next_retry_at === 'string' ? row.next_retry_at : null,
      failureStreak: Number(row.failure_streak ?? 0),
    };
  } finally {
    stmt.free();
  }
}

function upsertSyncState(db: Database, outcome: CodalSyncOutcome): void {
  const reportType = outcome.reportType ?? REPORT_TYPE;
  db.run(`INSERT INTO codal_sync_state
    (symbol, report_type, last_attempt_at, last_success_at, last_status,
     last_http_status, last_error, next_retry_at, failure_streak)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(symbol, report_type) DO UPDATE SET
      last_attempt_at = excluded.last_attempt_at,
      last_success_at = CASE WHEN ? = 1 THEN excluded.last_attempt_at
        ELSE codal_sync_state.last_success_at END,
      last_status = excluded.last_status,
      last_http_status = excluded.last_http_status,
      last_error = excluded.last_error,
      next_retry_at = excluded.next_retry_at,
      failure_streak = excluded.failure_streak`, [
    outcome.symbol, reportType, outcome.attemptedAt,
    outcome.dataStored ? outcome.attemptedAt : null, outcome.status,
    outcome.httpStatus, outcome.error, outcome.nextRetryAt, outcome.failureStreak,
    outcome.dataStored ? 1 : 0,
  ]);
}

function readLatestFinancialStatement(db: Database, symbol: string): CodalFinancialStatementRow | null {
  const stmt = db.prepare(`SELECT tracing_no, symbol, company_name, title, report_period,
    period_months, revenue, gross_profit, operating_profit, net_profit, basic_eps,
    total_assets, total_liabilities, total_equity, capital, retained_earnings, unit,
    is_audited, is_consolidated, fiscal_year, source, source_url, published_at,
    received_at, last_updated_at, processing_status FROM financial_statements
    WHERE symbol = ? ORDER BY report_period DESC, published_at DESC LIMIT 1`);
  try {
    stmt.bind([symbol]);
    if (!stmt.step()) return null;
    const row = stmt.getAsObject();
    const number = (key: string): number | null =>
      typeof row[key] === 'number' ? Number(row[key]) : null;
    return {
      tracingNo: String(row.tracing_no), symbol: String(row.symbol),
      companyName: String(row.company_name ?? ''), title: String(row.title ?? ''),
      periodEnd: typeof row.report_period === 'string' ? row.report_period : '',
      periodMonths: number('period_months'), revenue: number('revenue'),
      grossProfit: number('gross_profit'), operatingProfit: number('operating_profit'),
      netProfit: number('net_profit'), basicEps: number('basic_eps'),
      totalAssets: number('total_assets'), totalLiabilities: number('total_liabilities'),
      totalEquity: number('total_equity'), capital: number('capital'),
      retainedEarnings: number('retained_earnings'),
      unit: typeof row.unit === 'string' ? row.unit : null,
      audited: Number(row.is_audited) === 1,
      consolidated: row.is_consolidated == null ? null : Number(row.is_consolidated) === 1,
      fiscalYear: typeof row.fiscal_year === 'string' ? row.fiscal_year : null,
      source: String(row.source), sourceUrl: String(row.source_url),
      publishedAt: typeof row.published_at === 'string' ? row.published_at : null,
      receivedAt: String(row.received_at), lastUpdatedAt: String(row.last_updated_at),
      processingStatus: String(row.processing_status) as CodalProcessingStatus,
    };
  } finally {
    stmt.free();
  }
}

function readLatestMonthlySales(db: Database, symbol: string): CodalMonthlySalesRow | null {
  const stmt = db.prepare(`SELECT tracing_no, symbol, report_period, monthly_revenue,
    ytd_revenue, monthly_revenue_prev, ytd_revenue_prev, monthly_volume, ytd_volume,
    volume_unit, source, source_url, published_at, received_at, last_updated_at,
    processing_status FROM monthly_sales WHERE symbol = ?
    ORDER BY report_period DESC, last_updated_at DESC LIMIT 1`);
  try {
    stmt.bind([symbol]);
    if (!stmt.step()) return null;
    const row = stmt.getAsObject();
    const nullableNumber = (key: string): number | null =>
      typeof row[key] === 'number' ? Number(row[key]) : null;
    return {
      tracingNo: String(row.tracing_no),
      symbol: String(row.symbol),
      periodEnd: String(row.report_period),
      monthlyRevenue: nullableNumber('monthly_revenue'),
      ytdRevenue: nullableNumber('ytd_revenue'),
      monthlyRevenuePrev: nullableNumber('monthly_revenue_prev'),
      ytdRevenuePrev: nullableNumber('ytd_revenue_prev'),
      monthlyVolume: nullableNumber('monthly_volume'),
      ytdVolume: nullableNumber('ytd_volume'),
      volumeUnit: typeof row.volume_unit === 'string' ? row.volume_unit : null,
      source: String(row.source),
      sourceUrl: String(row.source_url),
      publishedAt: typeof row.published_at === 'string' ? row.published_at : null,
      receivedAt: String(row.received_at),
      lastUpdatedAt: String(row.last_updated_at),
      processingStatus: String(row.processing_status) as CodalProcessingStatus,
    };
  } finally {
    stmt.free();
  }
}

export function createCodalStore(
  storage: CodalArtifactStorage = cacheStorage,
  runtime: () => Promise<SqlRuntime> = () => getSql(),
) {
  let writeQueue: Promise<void> = Promise.resolve();

  async function withRead<T>(read: (db: Database) => T): Promise<T> {
    const SQL = await runtime();
    const db = openDatabase(SQL, await storage.read());
    try { return read(db); } finally { db.close(); }
  }

  async function persistWrite<T>(write: (db: Database) => T): Promise<T> {
    const SQL = await runtime();
    const db = openDatabase(SQL, await storage.read());
    let inTransaction = false;
    try {
      db.run('BEGIN IMMEDIATE');
      inTransaction = true;
      const result = write(db);
      db.run('COMMIT');
      inTransaction = false;
      const bytes = db.export();
      const checkDb = new SQL.Database(bytes);
      try {
        const integrity = checkDb.exec('PRAGMA integrity_check')[0]?.values?.[0]?.[0];
        const version = checkDb.exec('PRAGMA user_version')[0]?.values?.[0]?.[0];
        if (integrity !== 'ok' || Number(version) !== SCHEMA_VERSION) {
          throw new Error('Codal database validation failed');
        }
      } finally {
        checkDb.close();
      }
      await storage.write(bytes);
      return result;
    } catch (error) {
      if (inTransaction) {
        try { db.run('ROLLBACK'); } catch { /* retain operation error */ }
      }
      throw error;
    } finally {
      db.close();
    }
  }

  function withWrite<T>(write: (db: Database) => T): Promise<T> {
    const operation = writeQueue.then(() => persistWrite(write));
    writeQueue = operation.then(() => undefined, () => undefined);
    return operation;
  }

  return {
    readSyncState(symbol: string): Promise<CodalSyncState | null> {
      return withRead((db) => readSyncState(db, symbol));
    },
    readFinancialSyncState(symbol: string): Promise<CodalSyncState | null> {
      return withRead((db) => readSyncState(db, symbol, FINANCIAL_REPORT_TYPE));
    },
    readLatestMonthlySales(symbol: string): Promise<CodalMonthlySalesRow | null> {
      return withRead((db) => readLatestMonthlySales(db, symbol));
    },
    readLatestFinancialStatement(symbol: string): Promise<CodalFinancialStatementRow | null> {
      return withRead((db) => readLatestFinancialStatement(db, symbol));
    },
    recordSyncOutcome(outcome: CodalSyncOutcome): Promise<void> {
      return withWrite((db) => { upsertSyncState(db, outcome); });
    },
    recordReport(record: CodalDocumentRecord, outcome: CodalSyncOutcome): Promise<void> {
      return withWrite((db) => {
        db.run(`INSERT INTO codal_documents
          (tracing_no, symbol, company_name, title, report_type, source, source_url,
           published_at, report_period, received_at, last_updated_at, content_hash,
           raw_html, processing_status, processing_error)
          VALUES (?, ?, ?, ?, ?, 'codal.ir', ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(tracing_no) DO UPDATE SET
            symbol = excluded.symbol, company_name = excluded.company_name,
            title = excluded.title, report_type = excluded.report_type,
            source = excluded.source, source_url = excluded.source_url,
            published_at = excluded.published_at, report_period = excluded.report_period,
            last_updated_at = excluded.last_updated_at, content_hash = excluded.content_hash,
            raw_html = excluded.raw_html, processing_status = excluded.processing_status,
            processing_error = excluded.processing_error`, [
          record.tracingNo, record.symbol, record.companyName, record.title, REPORT_TYPE,
          record.sourceUrl, record.publishedAt, record.periodEnd, record.receivedAt,
          record.lastUpdatedAt, record.contentHash, record.rawHtml,
          record.processingStatus, record.processingError,
        ]);

        if (record.processingStatus === 'PARSED' && record.periodEnd && record.values) {
          const v = record.values;
          db.run(`INSERT INTO monthly_sales
            (tracing_no, symbol, report_period, monthly_revenue, ytd_revenue,
             monthly_revenue_prev, ytd_revenue_prev, monthly_volume, ytd_volume,
             volume_unit, source, source_url, published_at, received_at,
             last_updated_at, processing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'codal.ir', ?, ?, ?, ?, 'PARSED')
            ON CONFLICT(tracing_no) DO UPDATE SET
              symbol = excluded.symbol, report_period = excluded.report_period,
              monthly_revenue = excluded.monthly_revenue, ytd_revenue = excluded.ytd_revenue,
              monthly_revenue_prev = excluded.monthly_revenue_prev,
              ytd_revenue_prev = excluded.ytd_revenue_prev,
              monthly_volume = excluded.monthly_volume, ytd_volume = excluded.ytd_volume,
              volume_unit = excluded.volume_unit, source = excluded.source,
              source_url = excluded.source_url, published_at = excluded.published_at,
              last_updated_at = excluded.last_updated_at,
              processing_status = 'PARSED'`, [
            record.tracingNo, record.symbol, record.periodEnd, v.monthlyRevenue,
            v.ytdRevenue, v.monthlyRevenuePrev, v.ytdRevenuePrev, v.monthlyVolume,
            v.ytdVolume, v.volumeUnit, record.sourceUrl, record.publishedAt,
            record.receivedAt, record.lastUpdatedAt,
          ]);
        } else {
          db.run(`UPDATE monthly_sales SET processing_status = 'NOT_EVALUATED',
            last_updated_at = ? WHERE tracing_no = ?`, [record.lastUpdatedAt, record.tracingNo]);
        }
        upsertSyncState(db, outcome);
      });
    },
    recordFinancialStatement(
      record: CodalFinancialStatementRecord,
      outcome: CodalSyncOutcome,
    ): Promise<void> {
      return withWrite((db) => {
        const reportType = record.reportType ?? FINANCIAL_REPORT_TYPE;
        db.run(`INSERT INTO codal_documents
          (tracing_no, symbol, company_name, title, report_type, source, source_url,
           published_at, report_period, received_at, last_updated_at, content_hash,
           raw_html, processing_status, processing_error)
          VALUES (?, ?, ?, ?, ?, 'codal.ir', ?, ?, ?, ?, ?, ?, ?, ?, ?)
          ON CONFLICT(tracing_no) DO UPDATE SET
            symbol = excluded.symbol, company_name = excluded.company_name,
            title = excluded.title, report_type = excluded.report_type,
            source = excluded.source, source_url = excluded.source_url,
            published_at = excluded.published_at, report_period = excluded.report_period,
            last_updated_at = excluded.last_updated_at, content_hash = excluded.content_hash,
            raw_html = excluded.raw_html, processing_status = excluded.processing_status,
            processing_error = excluded.processing_error`, [
          record.tracingNo, record.symbol, record.companyName, record.title, reportType,
          record.sourceUrl, record.publishedAt, record.periodEnd, record.receivedAt,
          record.lastUpdatedAt, record.contentHash, record.rawHtml,
          record.processingStatus, record.processingError,
        ]);

        const v = record.financialValues;
        if (v && record.periodEnd) {
          db.run(`INSERT INTO financial_statements
            (tracing_no, symbol, company_name, title, report_period, period_months,
             revenue, gross_profit, operating_profit, net_profit, basic_eps, total_assets,
             total_liabilities, total_equity, capital, retained_earnings, unit,
             is_audited, is_consolidated, fiscal_year, source, source_url, published_at,
             received_at, last_updated_at, processing_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    'codal.ir', ?, ?, ?, ?, ?)
            ON CONFLICT(tracing_no) DO UPDATE SET
              symbol = excluded.symbol, company_name = excluded.company_name,
              title = excluded.title, report_period = excluded.report_period,
              period_months = excluded.period_months, revenue = excluded.revenue,
              gross_profit = excluded.gross_profit, operating_profit = excluded.operating_profit,
              net_profit = excluded.net_profit, basic_eps = excluded.basic_eps,
              total_assets = excluded.total_assets, total_liabilities = excluded.total_liabilities,
              total_equity = excluded.total_equity, capital = excluded.capital,
              retained_earnings = excluded.retained_earnings, unit = excluded.unit,
              is_audited = excluded.is_audited, is_consolidated = excluded.is_consolidated,
              fiscal_year = excluded.fiscal_year, source_url = excluded.source_url,
              published_at = excluded.published_at, last_updated_at = excluded.last_updated_at,
              processing_status = excluded.processing_status`, [
            record.tracingNo, record.symbol, record.companyName, record.title,
            record.periodEnd, v.periodMonths, v.revenue, v.grossProfit,
            v.operatingProfit, v.netProfit, v.basicEps, v.totalAssets,
            v.totalLiabilities, v.totalEquity, v.capital, v.retainedEarnings,
            v.unit, v.audited ? 1 : 0,
            v.consolidated === null ? null : v.consolidated ? 1 : 0, v.fiscalYear,
            record.sourceUrl, record.publishedAt, record.receivedAt,
            record.lastUpdatedAt, record.processingStatus,
          ]);
        } else {
          db.run(`UPDATE financial_statements SET processing_status = 'NOT_EVALUATED',
            last_updated_at = ? WHERE tracing_no = ?`, [record.lastUpdatedAt, record.tracingNo]);
        }
        upsertSyncState(db, { ...outcome, reportType });
      });
    },
  };
}

export const codalStore = createCodalStore();
