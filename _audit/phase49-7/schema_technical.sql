-- Phase 4.9.7 PROPOSED schema (design only; NOT executed).
-- C. Shared Metadata (single source of truth; FK target for both operational DBs)
CREATE TABLE asset(
  asset_id INTEGER PRIMARY KEY, trade_symbol TEXT, name TEXT, short_name TEXT,
  exchange TEXT, type_id TEXT, type_name TEXT, asset_class TEXT, ins_code TEXT,
  unlisted INTEGER, encoding_corrupt INTEGER, has_candles INTEGER,
  modes_count INTEGER, candle_rows INTEGER);
CREATE TABLE asset_alias(asset_id INTEGER REFERENCES asset(asset_id), alias_symbol TEXT, kind TEXT,
  PRIMARY KEY(asset_id, alias_symbol));
CREATE TABLE mode_def(mode_key TEXT PRIMARY KEY, res TEXT, basis TEXT, adj TEXT,
  meaning TEXT, alias_of TEXT);            -- real_close->last, type5->type0
CREATE TABLE usd_rate(date TEXT PRIMARY KEY, rate_rial REAL, source_asset_id INTEGER DEFAULT 2);
CREATE TABLE id_crosswalk(asset_id INTEGER REFERENCES asset(asset_id), ins_code TEXT,
  codal_id TEXT, tsetmc_id TEXT, PRIMARY KEY(asset_id));
CREATE TABLE provenance(key TEXT PRIMARY KEY, value TEXT);

-- A. Technical Market Database (operational, cleaned)
CREATE TABLE candle(
  candle_id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL REFERENCES asset(asset_id),
  res TEXT NOT NULL, basis TEXT NOT NULL, adj TEXT NOT NULL,
  t INTEGER NOT NULL, utc TEXT,
  o REAL, h REAL, l REAL, c REAL, v INTEGER,
  is_placeholder INTEGER DEFAULT 0,
  UNIQUE(asset_id, res, basis, adj, t));   -- holds after identical-dup dedup + t=0 removal
CREATE INDEX idx_candle_asset_mode ON candle(asset_id, res, basis, adj, t);
CREATE TABLE adjustment_event(
  event_id INTEGER PRIMARY KEY,
  asset_id INTEGER NOT NULL REFERENCES asset(asset_id),
  ins_code TEXT, effective_date TEXT, kind TEXT, event_sig TEXT,
  ratio REAL, cum_factor_after REAL, source TEXT, confidence TEXT,
  correction_version TEXT, ref_bars_sha256 TEXT);
CREATE TABLE adjustment_factor(
  asset_id INTEGER REFERENCES asset(asset_id), date TEXT, factor REAL, revision TEXT,
  PRIMARY KEY(asset_id, date, revision));
CREATE TABLE trading_calendar(date TEXT PRIMARY KEY, is_trading_day INTEGER, session_phase TEXT);
CREATE TABLE tech_capture_run(run_id TEXT PRIMARY KEY, source TEXT, captured_at TEXT,
  input_sha256 TEXT, types TEXT, resolutions TEXT, symbols INTEGER, bars INTEGER);
CREATE TABLE candle_build(asset_id INTEGER REFERENCES asset(asset_id), revision TEXT,
  raw_rows INTEGER, adjusted_rows INTEGER, max_rel_error REAL, built_at TEXT,
  PRIMARY KEY(asset_id, revision));
CREATE TABLE derived_feature(asset_id INTEGER REFERENCES asset(asset_id), date TEXT,
  feature_key TEXT, value REAL, model_revision TEXT,
  PRIMARY KEY(asset_id, date, feature_key, model_revision));

-- B. Other Market Data DB (fed by CODAL/TSETMC/future top-lists; NOT from Rahavard bulk)
-- instrument, financial_statement, monthly_sales, codal_notice, market_watch,
-- client_type, order_book_depth, index_value, industry, top_list_snapshot
-- (all keyed by asset_id FK -> Shared.asset; external join via ins_code/codal_id).
