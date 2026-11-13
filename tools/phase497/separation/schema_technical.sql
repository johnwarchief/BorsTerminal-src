-- tools/phase497/separation/schema_technical.sql
CREATE TABLE IF NOT EXISTS candle(
  candle_id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, res TEXT NOT NULL, basis TEXT NOT NULL,
  adj TEXT NOT NULL, t INTEGER NOT NULL, utc TEXT, o REAL, h REAL, l REAL, c REAL, v INTEGER,
  is_placeholder INTEGER DEFAULT 0, UNIQUE(asset_id,res,basis,adj,t));
CREATE INDEX IF NOT EXISTS idx_candle_asset_mode ON candle(asset_id,res,basis,adj,t);
CREATE TABLE IF NOT EXISTS adjustment_event(event_id INTEGER PRIMARY KEY, asset_id INTEGER, ins_code TEXT,
  effective_date TEXT, kind TEXT, event_sig TEXT, ratio REAL, cum_factor_after REAL, source TEXT,
  confidence TEXT, correction_version TEXT, ref_bars_sha256 TEXT);
CREATE TABLE IF NOT EXISTS adjustment_factor(asset_id INTEGER, date TEXT, factor REAL, revision TEXT,
  PRIMARY KEY(asset_id,date,revision));
CREATE TABLE IF NOT EXISTS tech_capture_run(run_id TEXT PRIMARY KEY, source TEXT, captured_at TEXT,
  input_sha256 TEXT, types TEXT, resolutions TEXT, symbols INTEGER, bars INTEGER);
CREATE TABLE IF NOT EXISTS candle_build(asset_id INTEGER, revision TEXT, raw_rows INTEGER,
  adjusted_rows INTEGER, max_rel_error REAL, built_at TEXT, PRIMARY KEY(asset_id,revision));