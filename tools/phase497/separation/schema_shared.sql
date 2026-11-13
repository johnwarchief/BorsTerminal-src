-- tools/phase497/separation/schema_shared.sql
CREATE TABLE IF NOT EXISTS asset(
  asset_id INTEGER PRIMARY KEY, trade_symbol TEXT, name TEXT, short_name TEXT,
  exchange TEXT, type_id TEXT, type_name TEXT, asset_class TEXT, ins_code TEXT,
  unlisted INTEGER, encoding_corrupt INTEGER DEFAULT 0, has_candles INTEGER DEFAULT 0,
  modes_count INTEGER DEFAULT 0, candle_rows INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS id_crosswalk(asset_id INTEGER PRIMARY KEY REFERENCES asset(asset_id),
  ins_code TEXT, codal_id TEXT, tsetmc_id TEXT);
CREATE TABLE IF NOT EXISTS mode_def(mode_key TEXT PRIMARY KEY, res TEXT, basis TEXT, adj TEXT,
  meaning TEXT, alias_of TEXT);
CREATE TABLE IF NOT EXISTS usd_rate(date TEXT PRIMARY KEY, rate_rial REAL, source_asset_id INTEGER DEFAULT 2);
CREATE TABLE IF NOT EXISTS provenance(key TEXT PRIMARY KEY, value TEXT);