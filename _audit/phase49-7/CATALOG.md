# کاتالوگ کامل دارایی اطلاعاتی رهاورد (۳۴٫۴ گیگابایت) — Phase 4.9.7

این کاتالوگ از **محتوای واقعی** فایل‌ها و جداول ساخته شده (نه نام فایل یا حدس). منبع: `api-all/` + خروجی‌های Phase 4.9.5/4.9.6.

## ۱٫ نمای کلی آرشیو
- حجم کل آرشیو api-all: ۳۴,۳۸۴,۰۵۳,۲۸۱ بایت (≈۳۴٫۴ GB) شامل ۶۳ JSONL کندل + DB مرجع + متادیتا + خطاها.
- ۶۳ فایل کندل JSONL: ۱۹,۷۷۱,۹۲۵,۵۳۷ بایت (≈۱۹٫۸ GB)، ۴۵۷,۷۱۲ رکورد asset-mode، ۱۵۴,۶۳۲,۹۳۳ کندل.
- DB مرجع `reference_all.db`: ۱۴,۶۱۲,۱۲۷,۷۴۴ بایت (≈۱۴٫۶ GB)، ۱۵۴,۶۳۲,۹۳۳ ردیف کندل + ۴۵,۱۵۷ دارایی.
- **تطابق کامل**: مجموع کندل‌های JSONL = ردیف‌های DB = ۱۵۴,۶۳۲,۹۳۳؛ رکوردهای JSONL = seriesهای metadata.db = ۴۵۷,۷۱۲.

## ۲٫ فایل‌های کندل JSONL (۶۳ mode)
ساختار یکسان در هر ۶۳ فایل (تأییدشده: record_key_variants=1, bar_key_variants=1):
- هر خط = یک رکورد asset-mode: `{asset_id, trade_symbol, name, n, bars[]}`.
- هر کندل: `{time (ms epoch), utc (ISO-8601), open, high, low, close, volume}`.
- **اطلاعات منحصربه‌فرد نسبت به DB**: فیلد `utc` (رشتهٔ زمان خوانا) + `trade_symbol`/`name` به‌صورت denormalized در هر رکورد؛ DB فقط `t` عددی را نگه می‌دارد.
- نام فایل: `bars_{res}_{basis}_{adj}.jsonl`؛ res∈{D,W,M}، basis∈۷ پایه، adj∈{type0,type5,type7}.
- تکرار در DB: بله — کندل‌ها عیناً در `reference_all.db.candles` (بدون utc).
- بخش بازار: همهٔ ۱۷ نوع دارایی (سهام/صندوق/اختیار/آتی/ارز/رمزارز/کالا/اوراق/…) — موتور تکنیکال.

### جدول per-file (رکورد=دارایی، کندل=مجموع n)
| فایل | رکورد | کندل | حجم (بایت) | dup-asset |
|---|---|---|---|---|
| bars_D_close_type0.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۵۹ | ۵۷۶,۱۱۴,۴۷۵ | خیر |
| bars_D_close_type5.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۶۱ | ۵۷۶,۱۱۴,۶۸۷ | خیر |
| bars_D_close_type7.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۶۱ | ۶۹۶,۸۹۷,۲۷۴ | خیر |
| bars_D_close_usd_type0.jsonl | ۷,۴۲۵ | ۴,۶۹۵,۸۶۳ | ۷۰۳,۶۶۳,۱۹۴ | خیر |
| bars_D_close_usd_type5.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۷۰۳,۶۹۳,۵۲۰ | خیر |
| bars_D_close_usd_type7.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۷۱۹,۹۳۶,۶۳۵ | خیر |
| bars_D_last_type0.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۵۷۶,۰۷۰,۴۰۵ | خیر |
| bars_D_last_type5.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۵۷۶,۰۷۰,۴۱۶ | خیر |
| bars_D_last_type7.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۲۲۹ | ۶۹۶,۸۳۱,۳۱۵ | خیر |
| bars_D_last_usd_type0.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۴۲ | ۵۷۶,۱۰۹,۶۹۳ | خیر |
| bars_D_last_usd_type5.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۴۲ | ۵۷۶,۱۰۹,۷۵۶ | خیر |
| bars_D_last_usd_type7.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۴۴۴ | ۶۹۶,۸۵۷,۴۳۴ | خیر |
| bars_D_market_cap_type0.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۵۹ | ۶۳۲,۸۷۸,۴۶۹ | خیر |
| bars_D_market_cap_type5.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۶۳۲,۸۸۰,۰۷۶ | خیر |
| bars_D_market_cap_type7.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۶۳۲,۸۸۰,۱۰۵ | خیر |
| bars_D_market_cap_usd_type0.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۰۴ | خیر |
| bars_D_market_cap_usd_type5.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۳۵ | خیر |
| bars_D_market_cap_usd_type7.jsonl | ۷,۴۲۰ | ۴,۶۹۵,۹۷۳ | ۷۳۲,۶۸۱,۰۵۴ | خیر |
| bars_D_real_close_type0.jsonl | ۱۰,۷۱۵ | ۴,۹۳۹,۳۴۴ | ۶۰۵,۴۱۶,۷۹۳ | خیر |
| bars_D_real_close_type5.jsonl | ۷,۴۳۲ | ۴,۶۹۲,۱۷۷ | ۵۷۵,۵۶۹,۸۴۴ | خیر |
| bars_D_real_close_type7.jsonl | ۷,۴۳۶ | ۴,۶۹۶,۱۱۷ | ۶۹۶,۸۱۷,۸۰۸ | خیر |
| bars_M_close_type0.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۱۳۶ | ۱۰۴,۹۰۱,۵۰۹ | خیر |
| bars_M_close_type5.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۳۴۸ | خیر |
| bars_M_close_type7.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۲۲۱ | ۱۱۲,۰۵۸,۷۸۲ | خیر |
| bars_M_close_usd_type0.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۸۹۶,۰۵۴ | خیر |
| bars_M_close_usd_type5.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۲۱۷ | ۱۱۲,۸۹۵,۲۶۰ | خیر |
| bars_M_close_usd_type7.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۲۱۸ | ۱۱۳,۴۵۷,۵۲۲ | خیر |
| bars_M_last_type0.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | خیر |
| bars_M_last_type5.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | خیر |
| bars_M_last_type7.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۸ | خیر |
| bars_M_last_usd_type0.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۰۶۸ | ۱۰۴,۸۹۲,۵۱۴ | خیر |
| bars_M_last_usd_type5.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | خیر |
| bars_M_last_usd_type7.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۸ | خیر |
| bars_M_market_cap_type0.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۸ | خیر |
| bars_M_market_cap_type5.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۷ | خیر |
| bars_M_market_cap_type7.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۰۸۶,۶۹۷ | خیر |
| bars_M_market_cap_usd_type0.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۷ | خیر |
| bars_M_market_cap_usd_type5.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۹ | خیر |
| bars_M_market_cap_usd_type7.jsonl | ۶,۱۷۵ | ۹۳۴,۲۰۱ | ۸۷,۵۱۳,۸۵۹ | خیر |
| bars_M_real_close_type0.jsonl | ۷,۴۳۵ | ۱,۰۸۳,۲۲۰ | ۱۰۴,۹۱۱,۶۶۳ | خیر |
| bars_M_real_close_type5.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۰۴,۹۱۲,۱۵۳ | خیر |
| bars_M_real_close_type7.jsonl | ۷,۴۳۶ | ۱,۰۸۳,۲۲۳ | ۱۱۲,۰۵۷,۳۰۷ | خیر |
| bars_W_close_type0.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۸۴۹ | خیر |
| bars_W_close_type5.jsonl | ۷,۴۳۵ | ۱,۷۱۳,۷۲۳ | ۱۸۸,۰۹۰,۶۹۰ | خیر |
| bars_W_close_type7.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۹۵,۱۷۱ | خیر |
| bars_W_close_usd_type0.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۹,۱۳۰,۳۰۷ | خیر |
| bars_W_close_usd_type5.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۹,۱۳۰,۳۲۰ | خیر |
| bars_W_close_usd_type7.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۲۱,۷۱۳,۰۸۲ | خیر |
| bars_W_last_type0.jsonl | ۷,۴۳۵ | ۱,۷۱۳,۷۱۹ | ۱۸۸,۰۸۹,۸۴۱ | خیر |
| bars_W_last_type5.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۲۱ | خیر |
| bars_W_last_type7.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۸۶,۲۹۶ | خیر |
| bars_W_last_usd_type0.jsonl | ۷,۴۳۵ | ۱,۷۱۳,۷۳۰ | ۱۸۸,۰۹۱,۰۱۸ | خیر |
| bars_W_last_usd_type5.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۲۱ | خیر |
| bars_W_last_usd_type7.jsonl | ۷,۴۳۵ | ۱,۷۱۲,۸۲۵ | ۲۱۶,۱۲۶,۹۹۶ | خیر |
| bars_W_market_cap_type0.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۳ | خیر |
| bars_W_market_cap_type5.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۳ | خیر |
| bars_W_market_cap_type7.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۵۱,۷۸۰,۹۰۱ | خیر |
| bars_W_market_cap_usd_type0.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | خیر |
| bars_W_market_cap_usd_type5.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | خیر |
| bars_W_market_cap_usd_type7.jsonl | ۶,۳۷۸ | ۱,۳۶۹,۳۱۰ | ۱۶۲,۴۶۰,۸۳۰ | خیر |
| bars_W_real_close_type0.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۰۰ | خیر |
| bars_W_real_close_type5.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۱۸۸,۰۹۱,۴۰۲ | خیر |
| bars_W_real_close_type7.jsonl | ۷,۴۳۶ | ۱,۷۱۳,۷۳۲ | ۲۱۶,۲۸۶,۲۸۰ | خیر |

## ۳٫ جداول DB مرجع `reference_all.db`
| جدول | ساختار | ردیف | اطلاعات | منحصربه‌فرد؟ |
|---|---|---|---|---|
| assets | asset_id PK, trade_symbol, name, exchange, type_id, unlisted | ۴۵,۱۵۷ | متادیتای عمومی دارایی | نگاشت پایه؛ مشتق از universe.json |
| candles | asset_id, res, basis, adj, t, o, h, l, c, v (بدون PK؛ index روی asset_id,res,basis,adj,t) | ۱۵۴,۶۳۲,۹۳۳ | OHLCV خام/تعدیل‌شده در ۶۳ mode | کندل‌ها (همان JSONL منهای utc) |

## ۴٫ `universe.json` — متادیتای دارایی‌ها
- ساختار: `{total: ۴۵,۱۵۷, assets: [...]}`؛ هر دارایی: `{entity_id, entity_type, type_id, type, trade_symbol, name, short_name, exchange, unlisted_item}`.
- ۴۵,۱۵۷ دارایی؛ trade_symbol در ۴۱,۴۲۹ موجود (۳٬۷۲۸ فاقد نماد). entity_type همه `exchange.asset`.
- **اطلاعات منحصربه‌فرد**: short_name + unlisted_item + type فارسی (در DB مرجع نیست). منبع جدول assets.
- **هیچ دادهٔ بنیادی/صورت مالی/گروه/صنعت در آن نیست.** فقط مشخصات عمومی نماد.
- بخش بازار: همهٔ بازارها (بورس تهران/فرابورس/کالا/انرژی/نوبیتکس/والکس/بایننس/یاهو/…).

## ۵٫ `errors.jsonl` — خطاهای استخراج
- ۳۲۸,۹۰۸ رکورد؛ ساختار `{asset_id, res, b, a, status}`.
- توزیع وضعیت: HTTP 200 با data=null (بی‌تاریخچه)=۳۱۴,۹۳۷؛ 422=۷,۵۴۲؛ 500=۶,۲۹۷؛ 503=۱۰۵.
- اطلاعات منحصربه‌فرد: نگاشت asset/modeهایی که تاریخچه ندارند (پوشش منفی). مربوط به کیفیت استخراج.

## ۶٫ فایل `.orig` (پیش از پاک‌سازی)
- `bars_D_real_close_type0.jsonl.orig`: ۱۳,۰۳۶ رکورد، ۶,۴۰۲,۵۲۹ کندل — نسخهٔ آلودهٔ run اولِ لغوشده (پیش از dedupe). فقط برای provenance؛ در DB نهایی استفاده نشده.

## ۷٫ artefactهای کشف API (probeها)
- `_discover.json`, `_probe2.json`, `_plan.json`, `_universe_probe.json`, `_progress.json`: سطح API کشف‌شده.
- **مهم**: این‌ها endpointهای غیرکندل را نشان می‌دهند (`/api/v2/top-lists`, `/api/v2/search`, `/api/v2/search/companies`) اما **دادهٔ آن‌ها استخراج نشده**؛ top-lists فقط برای کشف asset_id استفاده شد.
- نمونهٔ probe از top-lists شامل: instrument_state، ask/bid price/count، volume/value، real_close_price، اثر در شاخص — **هیچ‌کدام در آرشیو bulk ذخیره نشده‌اند**.
- `_plan.json`: bases نهایی ۷تایی؛ alias_close_same=false (close≠real_close)، alias_real_last_same=true (real_last≡last، حذف شد).

## ۸٫ داده‌های مرتبطِ خارج از آرشیو ۳۴٫۴ GB
- `db/market43.db` (۹۶٫۵ MB): مدل عملیاتی تکنیکال (۱۱ جدول: adjusted_candles, adjustment_factors, corporate_actions, factor_action_links, adjustment_verification, reference_raw/adjusted, candle_build_revisions, candle_capture_runs, candle_ingest_conflicts, adjustment_factor_audit). کلید symbol+date.
- `db/api-payloads-13.json` (۳۰٫۵ MB): پاسخ موتور برای ۱۳ نماد (candles/factors/volumes/fts/adjustCapability/corporateEvents/priceBasis) — خروجی BorsTerminal، نه دادهٔ خام رهاورد.
- `data/ra365_corrections/*` (۳ pack): factors.jsonl + raw_ohlc.jsonl + manifest.json — ضرایب/رویدادهای تعدیل (DPS، base_gap، split) مشتق از type0/type7 + CODAL.
- `metadata.db` (Phase 4.9.6، ۴۹ MB): طبقه‌بندی مشتق (asset/mode/series/coverage/quality_flag/provenance/dataset_split).

## ۹٫ آنچه در آرشیو نیست (صادقانه)
**هیچ‌کدام از این‌ها استخراج نشده‌اند**: صورت‌های مالی، دادهٔ بنیادی (EPS/حاشیه سود)، ارزش‌گذاری، جریان پول، حقیقی/حقوقی، دفتر سفارش، وضعیت نماد، مقادیر شاخص، صنایع/گروه‌ها. API رهاورد برخی را ارائه می‌دهد (top-lists) اما فقط برای کشف شناسه استفاده شد. این دسته‌ها در صورت نیاز باید از منابع دیگر (CODAL برای بنیادی؛ استخراج آیندهٔ top-lists برای جریان پول) تأمین شوند.