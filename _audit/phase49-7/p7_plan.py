# -*- coding: utf-8 -*-
"""Phase 4.9.7 — MIGRATION-PLAN.md, schema_technical.sql, FINAL-REPORT.md."""
import os, json
P7 = r"D:/BorsTerminal-worktrees/phase49-7-discovery/_audit/phase49-7"
FA = str.maketrans('0123456789', '۰۱۲۳۴۵۶۷۸۹')
def fa(x):
    if isinstance(x, float): return f"{x:,.2f}".translate(FA)
    return f"{x:,}".translate(FA)
def gb(b): return f"{b/1e9:.2f}".translate(FA)
V = json.load(open(os.path.join(P7, 'arch_volumes.json'), encoding='utf-8'))
def w(name, text):
    with open(os.path.join(P7, name), 'w', encoding='utf-8', newline='\n') as f: f.write(text)
    print('wrote', name, len(text), flush=True)

# ===================== MIGRATION-PLAN.md =====================
L = []
L.append('# برنامهٔ انتقال به معماری جدید + اعتبارسنجی — Phase 4.9.7')
L.append('')
L.append('**این فقط برنامه است؛ اجرا منوط به تصمیم مالک.** در همهٔ مراحل: Reference Archive فقط‌خواندنی می‌ماند؛ منطق موتور تعدیل/FTS/Runtime تغییر نمی‌کند؛ هیچ merge/release بدون مجوز مالک.')
L.append('')
L.append('## ترتیب مراحل (وابستگی‌ها)')
L.append('```')
L.append('P0 تثبیت Archive → P1 Shared Metadata → P2 Technical candles → P3 adjustment events')
L.append('                                   → P4 Go wiring → P5 Other Market Data → P6 AI prep')
L.append('```')
L.append('')
L.append('## P0 — تثبیت Reference Archive (پیش‌نیاز، انجام‌شده)')
L.append('- manifest SHA-256 برای ۶۳ JSONL + DB (موجود: api_all_provenance.json). Archive immutable.')
L.append('- اعتبارسنجی: تطابق SHA + شمارش ردیف ' + fa(154632933) + ' ✓ (انجام شده در 4.9.5/4.9.6).')
L.append('')
L.append('## P1 — ساخت Shared Metadata')
L.append('- ورودی: universe.json + assets + pack تعدیل (ins_code) + taxonomy.')
L.append('- خروجی: asset/' + fa(45157) + '، mode_def/۶۳ + alias، usd_rate (از id=2)، id_crosswalk، provenance.')
L.append('- اعتبارسنجی: شمارش دارایی = ' + fa(45157) + '؛ یکگانگی asset_id؛ پوشش ins_code برای ' + fa(808) + ' دارایی pack؛ FK integrity؛ نرخ دلار مطابق نمونه‌های اندازه‌گیری‌شده.')
L.append('- بازگشت‌پذیر: DB جدید جداگانه؛ Archive دست‌نخورده.')
L.append('')
L.append('## P2 — ساخت Technical candles (متمایز، پاک‌سازی‌شده)')
L.append('- ورودی: reference_all.db (خواندن) یا JSONL (برای utc).')
L.append('- تبدیل: حذف modeهای افزونه (real_close→last، type5→type0) طبق mode_def؛ حذف/علامت t=0؛ dedup identical؛ حفظ utc.')
L.append(f'- خروجی: ≈{fa(V["operational_rows_est"])} ردیف، ≈{gb(V["technical_db_bytes_est_distinct_nopad"])} GB (برآورد).')
L.append('- اعتبارسنجی (حیاتی):')
L.append(f'  - reconciliation: ردیف متمایز = {fa(V["distinct_rows"])} منهای padding؛ تطابق با مبدأ per-mode.')
L.append('  - parity: روی cohort، close تعدیل‌شدهٔ Technical با reference type7 در تلورانس (معیار موجود 13-runtime).')
L.append('  - پاک‌سازی: هیچ t=0 در عملیاتی؛ هیچ dup-t identical؛ utc حفظ شده.')
L.append('  - alias: بازتولید real_close از last و type5 از type0 بیت‌به‌بیت.')
L.append('')
L.append('## P3 — رویدادها/ضرایب تعدیل')
L.append('- ورودی: pack تعدیل (factors.jsonl ' + fa(8280) + ' step) + raw_ohlc.')
L.append('- خروجی: adjustment_event + adjustment_factor + candle_build/tech_capture_run.')
L.append('- اعتبارسنجی: زنجیرهٔ factor، type7 را بازتولید کند (rel_error≈0 روی ' + fa(622) + ' verified step)؛ ' + fa(1358) + ' unverified علامت‌دار (بی‌جعل)؛ lineage هر factor به ref_bars_sha256.')
L.append('')
L.append('## P4 — اتصال Go Backend به Technical DB')
L.append('- نمای price_history + adjust_events از Technical DB سرو شود (بدون تغییر منطق موتور).')
L.append('- اعتبارسنجی: harness موجود 13-runtime parity + شواهد مرورگر ۳۰ نماد؛ مقایسهٔ خروجی چارت قبل/بعد (بیت‌به‌بیت در تلورانس).')
L.append('- **گیت مالک**: پیش از جایگزینی منبع دادهٔ عملیاتی.')
L.append('')
L.append('## P5 — Other Market Data DB (CODAL/TSETMC + top-lists آینده)')
L.append('- اتصال منابع موجود CODAL/TSETMC به schema پیشنهادی؛ استخراج آیندهٔ top-lists رهاورد (اختیاری، با login مالک).')
L.append('- اعتبارسنجی: خروجی موتورهای fundamental/mstat/confidence بدون تغییر؛ lineage با publish_date (بدون lookahead).')
L.append('')
L.append('## P6 — آماده‌سازی آموزش AI')
L.append('- corpus خام از Archive؛ ویژگی از Technical/Other؛ dataset_split (تصمیم مالک: split زمانی، حذف placeholder، پوشش کافی).')
L.append('- اعتبارسنجی: lineage خام→ویژگی→برچسب→خروجی مدل با revision/provenance؛ بدون نشت زمانی.')
L.append('')
L.append('## اصول اعتبارسنجی عمومی')
L.append('- هر مرحله read-only روی Archive؛ خروجی در DB جداگانه؛ قابل‌بازگشت.')
L.append('- هیچ PASS بدون شواهد واقعی (شمارش/parity/hash).')
L.append('- اعداد از artifacts خام تولید می‌شوند (نه دست‌نویس).')
L.append('- تصمیم اجرا/merge/release با مالک است.')
w('MIGRATION-PLAN.md', '\n'.join(L))

# ===================== schema_technical.sql =====================
SQL = """-- Phase 4.9.7 PROPOSED schema (design only; NOT executed).
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
"""
w('schema_technical.sql', SQL)

# ===================== FINAL-REPORT.md =====================
L = []
L.append('# گزارش نهایی Phase 4.9.7 — کشف کامل دادهٔ رهاورد + طراحی جداسازی')
L.append('')
L.append('## یافته‌های قطعی (شواهد read-only)')
L.append(f'- آرشیو ۳۴٫۴ GB = **فقط کندل + متادیتای عمومی دارایی + خطاها**. ۶۳ JSONL = {fa(457712)} رکورد = {fa(154632933)} کندل (تطابق کامل با DB). بنیادی/صورت مالی/جریان پول/دفتر سفارش/شاخص **استخراج نشده** (تأیید از کد استخراج + PROVENANCE).')
L.append('- ۷ پایه: real_close≡last (۱۰۰٪)؛ close=پایانی رسمی؛ type0≡type5 (۵۲/۵۲ دارایی)؛ type7=عملکردی. گرید ۶۳ mode در عمل ' + fa(V['distinct_modes']) + ' سری متمایز دارد.')
L.append('- فرمول USD: close_usd = close / نرخ دلار (دارایی id=2)؛ market_cap_usd = market_cap×1e6/نرخ؛ last_usd تبدیل‌نشده.')
L.append('- صفرهای W/M و dup-t آن‌ها = **placeholder با t=0** (صندوق‌ها)؛ dup-t در D = bar تکراری identical مبدأ (۱۱ دارایی). ناهنجاری OHLC = source-level (در type7 دست‌نخورده).')
L.append(f'- پوشش: {fa(10715)} دارایی دارای کندل از {fa(45157)}؛ صندوق {fa(686)}/{fa(60361963)} ردیف، سهام {fa(910)}/{fa(56405237)}، رمزارز {fa(618)}، اختیار {fa(5337)} (کم‌تاریخچه).')
L.append('')
L.append('## ابهام‌های حل‌نشده (نیازمند مستندات رهاورد / تصمیم مالک)')
L.append('- نام‌گذاری رسمی real_close و intent دقیق type5 (چرا ≡type0) — شواهد داده‌ای قطعی، تسمیهٔ رسمی UNKNOWN.')
L.append('- واحد مطلق market_cap (میلیون ریال از فرمول استنباط شد) و انطباق دقیق روز نرخ دلار — PARTIALLY_CONFIRMED.')
L.append('- تقویم معاملاتی TSE در آرشیو نیست (شکاف Technical DB).')
L.append('- dataset_split و scope نهایی دیتاست آموزش — تصمیم مالک.')
L.append('')
L.append('## اطلاعات ارزشمند کشف‌شده')
L.append(f'- **افزونگی ' + fa(V['redundant_pct_rows']) + '٪**: real_close≡last و type0≡type5 → انبار عملیاتی می‌تواند از ' + gb(V['ref_db_bytes']) + ' GB به ≈' + gb(V['technical_db_bytes_est_distinct_nopad']) + ' GB کاهش یابد (حذف alias + padding t=0).')
L.append('- **دارایی دلار id=2** کلید تبدیل USD است (باید در Shared Metadata بماند).')
L.append('- **فیلد utc** در JSONL هست ولی DB مرجع حذف کرده — در Technical DB حفظ می‌شود.')
L.append('- **pack تعدیل** ' + fa(8280) + ' step (' + fa(808) + ' دارایی) منبع رویداد/ضریب برای بازتولید عملکردی.')
L.append('- API رهاورد top-lists (instrument_state/ask-bid/value/اثر شاخص) را ارائه می‌دهد ولی استخراج نشده — هدف استخراج آینده برای Market Intelligence.')
L.append('')
L.append('## پیشنهاد نهایی معماری (برای تصمیم مالک)')
L.append('- **Reference Archive** (سرد، immutable): ۳۴٫۴ GB faithful — منبع parity/بازتولید/corpus خام.')
L.append('- **A. Technical Market DB** (گرم): کندل متمایز پاک‌سازی‌شده + utc + رویداد/ضریب تعدیل + تقویم + منشأ ≈' + gb(V['technical_db_bytes_est_distinct_nopad']) + ' GB. همهٔ موتورهای قیمت‌محور (Technical/FTS-setup/Forecasting/Regime/Volatility) را تغذیه می‌کند.')
L.append('- **B. Other Market Data DB**: بنیادی/جریان/دفتر سفارش/شاخص از CODAL/TSETMC (موجود) + top-lists آیندهٔ رهاورد. سهم آرشیو فعلی رهاورد = ۰ فراتر از متادیتا.')
L.append('- **C. Shared Metadata**: asset/mode_def/usd_rate/id_crosswalk — کلید مشترک asset_id، بی‌تکرار متادیتا.')
L.append('- برنامهٔ انتقال P0…P6 با اعتبارسنجی per-phase (MIGRATION-PLAN.md)؛ اجرا منوط به مالک.')
L.append('')
L.append('## خروجی‌ها')
L.append('CATALOG / JSONL-REPORT / AMBIGUITIES / DATA-DICTIONARY / DATA-MAP / ARCHITECTURE / ENGINE-USABILITY / MIGRATION-PLAN / schema_technical.sql / FINAL-REPORT + اسکریپت‌های بازتولیدپذیر p7_*.py + artifacts (catalog_jsonl/ambiguity_evidence*/arch_volumes).')
L.append('')
L.append('**هیچ DB/موتوری تغییر نکرد؛ هیچ merge/release/push انجام نشد. تصمیم اجرای جداسازی با مالک است.**')
w('FINAL-REPORT.md', '\n'.join(L))
print('PLAN_DONE', flush=True)