# یکپارچگیِ معماریِ داده و سرویس — فاز ۴٫۵

مأموریت §۸: جداسازیِ ingestion از computation، جداییِ خام از تعدیل‌شده، ردیابیِ
رویدادِ شرکتی، مسیرِ استانداردِ داده برایِ همهٔ محاسبات، یکسانیِ چارت و آکوپیشن‌لب،
اعلامِ صریحِ زمان/منبع/اعتبار، stale به‌جایِ live، و نبودِ موتورِ موازی با منطقِ متفاوت.
این فایل فقط یافته‌هایِ **راستی‌آزمایی‌شده** را می‌آورد؛ هر یافته شاهدِ عددی دارد.

## نقشهٔ مسیرِ داده

```
ingestion                        computation (read-only)                     consumers
price_history  ─┐
market_watch   ─┤   chartDBBody / get_chart_db
adjust_events  ─┼─► _canonical_adjustment ──► candles + factors + events ──► /api/chart-db, /api/chart
price_adjust_events  ─┤        (effective dates → merge official → share legs →
share_change_events  ─┤         correction pack → engine → chain → coverage)
ra365 packs (calendar/corrections) ─┘                    │
                                                          ├─► /api/ma            (پس از S8: همان factors)
                                                          ├─► /api/patterns      (پس از S8: همان factors)
                                                          ├─► /api/chart/{sym}/key-levels (خام، بدونِ ضریب)
                                                          ├─► forecast/edge/indicators
                                                          └─► FTS analysis (chartSnapshot)
```

## یافته‌ها

| # | یافته | وضعیت | شاهد |
| --- | --- | --- | --- |
| 1 | MA و الگوها ضریب را از زنجیرهٔ دومِ ساده‌تر می‌گرفتند (رویدادِ رسمیِ تازه جا می‌افتاد) | **FAIL — اصلاح شد** | شستا: ۴۵۷ روز، ضریب 0.747069 در برابرِ 0.703611 چارت؛ MA5 آخری 3380.00 در برابرِ 3337.19 |
| 2 | چارت، MA، الگوها، forecast/edge/indicators و FTS همگی از خروجیِ کانونیک می‌خوانند | **PASS** | `analysisSeries` → `chartSnapshot` → `chartDBBody`؛ مسیرهایِ handlers |
| 3 | خام و تعدیل‌شده جدا و قابلِ تفکیک‌اند | **PASS** | `candles` خام دست‌نخورده + `factors` جدا + `_literal_display_candles` فقط برایِ نمایش |
| 4 | ردیابیِ رویدادِ شرکتی | **PASS** | ۲۷۲ اعمال/۴۹۳ رد؛ هر رویداد `source`/`factor_status`/`correction.version` دارد |
| 5 | زمان/منبع/اعتبار صریح | **PASS** | `lastDataTime`، `payloadAgeS`، `liveInjected`، `liveError`، `live_forming`، `adjustSource`، `adjustCapability.availability.stale` |
| 6 | stale هرگز live نشان داده نمی‌شود | **PASS** | تزریقِ کندلِ زنده فقط با `d_even > last_db_date` و حجمِ مثبت؛ `stale` فقط وقتی live نیست و سری کهنه است |
| 7 | موتورِ قدیمیِ مرده هنوز در کد است | **DEFERRED** | `ComputeAdjustmentFactors`/`LoadAutonomousAdjustmentEvents`/`factorsFromEvents` فقط تعریف‌اند، بدونِ مصرف‌کننده؛ حذف نشد تا خروجیِ هیچ مسیری عوض نشود |
| 8 | `key-levels` رویِ قیمتِ خام است (بدونِ ضریب) | مشاهده | هر دو موتور یکسان؛ مصرف‌کننده‌ای در frontend-v2 ندارد؛ تغییر نکرد |
| 9 | `_stored_adjust_events` رویِ مسیرِ خواندن `CREATE TABLE IF NOT EXISTS` اجرا می‌کند | مشاهده | اثرِ جانبیِ DDL، نه نوشتنِ داده؛ `run_all_tests` را دست‌نخورده گذاشت |
| 10 | ردیف‌هایِ قدیمی برچسبِ provenance دارند | **PASS** | DB: `src` تهی ۳۶۹٬۳۵۹ / `board` ۹۷٬۶۵۶ / `published` ۱۳؛ در payload تهی → `published` |

## اصلاحِ یافتهٔ ۱ (S8)

پیش: `/api/ma` و `/api/patterns` از `_factors_from_events` (Python) و
`factorsFromStoredEvents` (Go) می‌خواندند — فقط `adjust_events` + بستهٔ تصحیح،
بدونِ mergeِ رویدادِ رسمی (`_official_price_adjust_events`)، سهام و گام‌هایِ بلند.
نتیجه: برایِ شستا رویدادِ رسمیِ ۲۰۲۶-۱۰-۲۵ (ratio 0.9418282548) از زنجیرهٔ MA جا
می‌افتاد، در حالی که چارت آن را داشت.

پس:

| فایل | تغییر |
| --- | --- |
| `api/chart.py` | `_canonical_factors(symbol, times, closings)` اضافه شد: همان فیلترِ اثبات‌نشده + داوریِ منبع + `_canonical_adjustment`ِ چارت. `/api/ma` و `/api/patterns` از آن می‌خوانند؛ `_adjust_events_for` (فالبکِ CDN) حذف شد |
| `backend-go/internal/chart/canonical.go` | `canonicalFactors` اضافه شد (همان `storedCanonicalEvents` + `filterUnproven` + `adjKnownSources` + `canonicalAdjustment`)؛ `factorsFromStoredEvents`ِ مرده حذف شد |
| `backend-go/internal/chart/ma.go` | factors از `canonicalFactors` با `closings` همان کندل‌ها |
| `backend-go/internal/chart/patterns.go` | factors از `canonicalFactors` با `closings` همان کندل‌ها |

شاهدِ پس از اصلاح:

| قلم | نتیجه |
| --- | --- |
| ضریبِ MA/الگوها در برابرِ چارت (۳۰ نماد) | 0 اختلاف |
| خروجیِ `ma` + `patterns` Python ↔ Go | ۳۰/۳۰ یکسان (عدد، تاریخ، overlay) |
| خروجیِ چارت | بدونِ تغییر؛ Python↔Go 0 اختلاف (با بستهٔ تقویمِ یکسان) |
| GO test | `go test ./...` سبز |
| B3 | 50 passed / 0 failed |
| اثرِ کاربری | فقط شستا: MA5 آخری 3380.00 → 3337.19 (ضریبِ درست) |

## حکمِ S8

| محور | وضعیت |
| --- | --- |
| جداسازیِ ingestion/computation | PASS |
| جداییِ خام/تعدیل‌شده | PASS |
| ردیابیِ رویدادِ شرکتی | PASS |
| مسیرِ استانداردِ واحد برایِ همهٔ محاسبات | **PASS پس از اصلاح** (پیش: FAIL) |
| یکسانیِ چارت و آکوپیشن‌لب | PASS (هر دو از `chartSnapshot`) |
| زمان/منبع/اعتبار | PASS |
| stale به‌جایِ live | PASS |
| موتورِ موازیِ دیگر | هیچ موتورِ فعالی نماند؛ موتورِ مردهٔ Go در ردیفِ ۷ ثبت شد |
