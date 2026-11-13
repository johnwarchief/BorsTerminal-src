# Data Dictionary نهایی — Phase 4.9.7

واژه‌نامهٔ همهٔ ساختارهای دادهٔ واقعی کشف‌شده. واحدها: قیمت‌ها **ریال** (مگر *_usd)، زمان **ms epoch**، market_cap **میلیون ریال**.

## A. کندل JSONL (`bars_*.jsonl`)
### رکورد asset-mode (هر خط)
| فیلد | نوع | معنا |
|---|---|---|
| asset_id | string | شناسهٔ دارایی رهاورد (= entity_id) |
| trade_symbol | string\|null | نماد معاملاتی (۳٬۷۲۸ دارایی null) |
| name | string\|null | نام کامل دارایی |
| n | int | تعداد کندل‌های این سری |
| bars | array | آرایهٔ کندل‌ها |
### کندل (هر عضو bars)
| فیلد | نوع | معنا | واحد |
|---|---|---|---|
| time | int | timestamp کندل | ms epoch (۰ = placeholder) |
| utc | string | زمان خوانا ISO-8601 (در DB حذف شده) | D: …Z، M: +04:30 |
| open/high/low/close | real | OHLC | ریال (یا USD در *_usd؛ میلیون ریال در market_cap) |
| volume | int | حجم معامله | سهم/واحد |

## B. DB مرجع `reference_all.db`
### assets
| فیلد | نوع | معنا |
|---|---|---|
| asset_id | INTEGER PK | شناسهٔ دارایی |
| trade_symbol | TEXT | نماد |
| name | TEXT | نام |
| exchange | TEXT | بازار (بورس تهران/فرابورس/…) |
| type_id | TEXT | کد نوع (۱=سهام، ۲=صندوق، …) |
| unlisted | INTEGER | ۱ اگر خارج از بورس/غیرفعال |
### candles (بدون PK؛ index: asset_id,res,basis,adj,t)
| فیلد | نوع | معنا |
|---|---|---|
| asset_id | INTEGER | شناسهٔ دارایی |
| res | TEXT | resolution: D/W/M |
| basis | TEXT | پایهٔ قیمت (۷ مقدار) |
| adj | TEXT | تعدیل: type0(خام)/type5(≡خام)/type7(عملکردی) |
| t | INTEGER | timestamp ms (۰=placeholder) |
| o/h/l/c | REAL | OHLC |
| v | INTEGER | حجم |

## C. `universe.json` (متادیتای دارایی)
| فیلد | نوع | معنا |
|---|---|---|
| entity_id | string | = asset_id |
| entity_type | string | همه exchange.asset |
| type_id / type | string | کد نوع / نام فارسی نوع |
| trade_symbol | string\|null | نماد |
| name / short_name | string | نام کامل / کوتاه |
| exchange | string | بازار |
| unlisted_item | bool | خارج از بورس؟ |

## D. `errors.jsonl`
| فیلد | نوع | معنا |
|---|---|---|
| asset_id, res, b, a | string | شناسهٔ task ناموفق (mode) |
| status | int/str | HTTP status (200=null-data، 422، 500، 503) یا err |

## E. pack تعدیل `factors.jsonl` (data/ra365_corrections)
| فیلد | نوع | معنا |
|---|---|---|
| asset_id / symbol / ins_code | string | شناسهٔ دارایی / نماد / کد ابزار TSETMC |
| effective_date / created_at | string | تاریخ مؤثر رویداد / ساخت |
| event_sig | string | نوع رویداد: dps/product/fund_dps/share/base_gap/pa/… |
| ratio / ref_ratio / prod_ratio | real | ضریب تعدیل pack / مرجع / تولید |
| cum_factor_after | real | ضریب تجمعی پس از رویداد |
| action / class | string | replace_step/… ؛ RATIO_DIFF/… |
| method / confidence / prov_kind | string | روش استنتاج / اطمینان / منشأ (pack) |
| validity / reason / fields_used | string | اعتبار / علت / فیلدهای استفاده‌شده |
| ref_bars_sha256 / correction_version | string | هش مرجع / نسخهٔ pack |

## F. pack `raw_ohlc.jsonl` (تصحیح per-field)
| فیلد | نوع | معنا |
|---|---|---|
| asset_id/symbol/ins_code/date/field | string | شناسه + تاریخ + فیلد (close/…) |
| value / product_value / abs_diff | real | مقدار مرجع / مقدار تولید / اختلاف |
| method/confidence/reason/source | string | روش/اطمینان/علت/منشأ |

## G. DB عملیاتی `market43.db` (مدل تکنیکال فعلی — کلید symbol+date)
| جدول | ردیف | نقش |
|---|---|---|
| adjusted_candles | ۱۲۲,۹۴۴ | OHLCV تعدیل‌شده + factor + revision |
| adjustment_factors | ۹۱۰ | ضرایب تعدیل (ratio/kind/source/method/confidence/status/q_before/q_after/prev_close) |
| adjustment_factor_audit | ۴۲۹ | audit مغایرت pack_ratio با ref_ratio |
| adjustment_verification | ۱۲۲,۹۴۴ | تأیید per-bar: reference_close vs adjusted_close + rel_error |
| corporate_actions | ۰ | رویدادهای شرکتی (kind/value/unit/fiscal_year) — خالی در این build |
| factor_action_links | ۵۰۵ | پیوند factor↔corporate_action (relation/delta_days/evidence) |
| reference_raw | ۱۲۲,۹۴۴ | OHLCV خام مرجع (parity target) |
| reference_adjusted | ۱۲۲,۹۴۴ | close تعدیل‌شدهٔ مرجع (parity target) |
| candle_build_revisions | ۴۳ | provenance ساخت per-symbol (raw/factor/adjusted_rows/max_rel_error) |
| candle_capture_runs | ۱ | متادیتای run ضبط (source/input_sha256/types/resolutions/symbols/bars) |
| candle_ingest_conflicts | ۰ | log تعارض ingest (old/new value+src) |

## H. `metadata.db` مشتق (Phase 4.9.6)
| جدول | نقش |
|---|---|
| asset | دارایی + asset_class + has_candles + modes_count + candle_rows + encoding_corrupt |
| mode | ۶۳ mode + timeframe/price_basis_category/adjustment_category + meaning |
| series | ۴۵۷٬۷۱۲ سری (asset_id, mode_key, rows, first_t, last_t) |
| coverage | per-mode: assets/rows/min_t/max_t |
| quality_flag | پرچم‌های کیفیت (scope/flag/severity/detail) |
| provenance | کلید-مقدار منشأ |
| dataset_split | تقسیم آموزشی (خالی — تصمیم مالک) |