# parity نبض بازار با Traders Arena — جدولِ ممیزی (کار #73، ۱۴۰۵-۰۷-۱۴)

این فایل **ممیزی** است، نه ادعایِ parity. مرجعِ سمتِ ما خودِ کد است (سطرِ
ارجاع‌دار) و مرجعِ سمتِ او فیدهایِ بایگانی‌شدۀ `_audit/ta/` (هفت فایل، GETِ
عمومیِ tradersarena.ir). فرمولِ درونِ فیدهایِ او از نامِ فیلدِ کوتاهِ خودش
(`m`, `s1…s60`, `bpcx`…) بیرون نمی‌آید؛ تا کدِ باندلِ او سطر‌به‌سطر رمزگشایی
نشود، هر «فرمولِ تریدرزآرنا» در این جدول حدس است و مالک گفته حدس نزنیم.

**نتیجۀ اجرای این دور: صفر تغییرِ رفتار درِ نبض بازار.** دو دلیلِ صریح:

۱. هیچ‌کدام از واگرایی‌هایِ عددیِ این دور *قابلِ اثبات* نبود (باید باندلِ او
   رمزگشایی شود؛ `_audit/ra_technicalChart.js` و `ra_bundle_decode.js` شروعش‌اند
   و کارِ دورِ بعد هستند).
۲. سه موردی که «باگ» به‌نظر می‌رسیدند، رأیِ مالک‌اند نه خطایِ من (پایین‌تر).

## جدولِ پنل‌ها

| پنل | source (اندپوینت ← جدول) | فیلد خام | فرمولِ اجراشده (file:line) | بازۀ زمانی | تازه‌سازی | خروجِ BorsTerminal | خروجِ Traders Arena | طبقه‌بندی |
|---|---|---|---|---|---|---|---|---|
| خلاصۀ جریان پول | `/api/mstat/summary` ← `market_watch`+`instruments`+`client_type` | `buy_I_Volume`, `buy_N_Volume`, `sell_*`, `q_tot_*`, `z_tot_tran` | VWAP=`val/vol`؛ `pc_buy_m = (buy_i/vol)/…`؛ `power = pc_buy/pc_sell`؛ `flow = (rb−rs)/B` (`mstat_engine.py:747,761,842-850`) | همین نشست (`MAX(d_even)`) | پولینگِ ۳۰s/۵m، نوشتنِ نقطه هر ۳۰۰s | ۱۰ ردیفِ `CATEGORY_ROWS` + `health` | `market0.json` → `m[13]` + `d` (ساختار: ۱۴ عددِ فشرده، برچسبِ بی‌متن) | **نیازمندِ پژوهش** (واحد/ترتیبِ آرایه ثابت نشده) |
| پولِ هوشمند | `/api/mstat/smart-money` ← `client_type`+`market_totals`+`market_index` |同上 + `paperType`, `pct`, `qstate` | bearish: `(p<0) or qstate==ST_SELLQ` بر `known`؛ `ideal = eq_in>0 and fx_in<0`؛ trio: `core and gold_out is not False` (`:1048-1060,1241`) | همین نشست + پنجرۀ `h_even` | ۳۰s | `macro/watch_entry/flow/verdict` | بی‌فیدِ متناظرِ بایگانی‌شده | **نیازمندِ پژوهش** |
| دما/پوشش | `/api/mstat/thermometer` ← `market_watch` | `pct`, `vol` | فقطِ *معامله‌شده* (`vol>0`)؛ `pos_pct = 100*pos/known` (`:1532-1553`) | همین نشست | ۳۰s | positive/negative/zero/nodata + `entry_opportunity` | `histo-status.json` → `s1,s5,s10,s20,s60` هر کدام ۱۴ سطل | **parity ممکن است** — سطل‌هایِ او (HISTO12/HISTO7 در `:135-160`) دقیقاً همین شکل‌اند؛ باید مرزِ سطل‌ها را از باندل بخوانیم |
| عمقِ صف | `/api/mstat/depth` ← `market_watch` | `buy_q_val`, `sell_q_val`, `qstate`, `q_tot_tran` | `ratio = round(buy/sell,2)`؛ سه‌شاخۀ one-sided (`no_trade`/`below_base`/`base_unknown`) (`:1570-1599`) | همین نشست | ۳۰s | `depth_available` (نه صفرِ جعلی) | `chart/totals0.json` → `bq`,`sq`,`bo`,`so` | **parity ممکن است** — دو ستونِ هم‌نام در فیدِ او هست؛ مقایسهٔ عددی نیازمندِ نشستِ زنده |
| صنایع | `/api/mstat/industries` ← `market_watch`+`instruments` | `sector_name`, `pct`, `q_tot_cap`, `buy/sell` | میانگینِ درصد بی‌nullها؛ `flow=None` اگر `val<=0`؛ leader = رتبۀ ≤۵ در هر دو (`:1736-1809`) | همین نشست | ۳۰s/۵m (staleTime 120s) | ۶۱ صنعت + دو داغ | `data_industries-csv.fz` → ۶۱ سطرِ ۲۲ ستونه | **parity ممکن است** — پوشش (۶۱=۶۱) یکی است؛ معنایِ ۱۹ ستونِ او رمزگشایی‌نشده |
| خطِ زمانِ درون‌روز | `/api/mstat/timeline?mode=cum` ← `mstat_snap` | نقاطِ ۱۰ سری (`val_bt, flow_eq_bt, pos, neg, bq_bt…`) | `limit=240`، `stale` با `MAX(d_even)`، `ready` با ≥۲ نقطه (`:1901-1982`) | یک نشست (`h_even` ۰۸:۵۵–۱۳:۰۰) | ۳۰s | نمودارِ چندسری | `chart/totals0.json` → `time[]`,`transfer[]`,`plus[]`,`minus[]`,`bpc[]`… (هر ۶۰ ثانیه) | **نیازمندِ دادهٔ تازه** — او هر دقیقه نقطه می‌گذارد، ما هر ۵ دقیقه (`app.py:306`); برایِ هم‌شکلی باید ریتمِ نوشتنِ `mstat_snap` عوض شود، که یعنی بارِ نوشتنِ بیشتر: رأیِ مالک |
| تابلویِ نمادهایِ اصلی | `/api/mstat/mainwatch` | `p_closing`, `pct`, `z_tot_tran`, `h_even` | `clock_ok = pct>=1.0 and trades>=30 and price>=500` (`:1702-1704`) | همین نشست | بی‌مصرف‌کننده | محاسبه می‌شود، در UI نیست | `data_mainwatch_symbols.fz` → ۲۰ سطرِ ۲۰ ستونه | **نیازمندِ UI** — فرمول درِ ما هست و پوششِ او هم (۲۰ سطر)؛ وصل‌کردنش کارت، یک تصمیمِ محصولی است |
|Client split / phases | `/api/mstat/client-split`, `/phases` | `client_type` / دو نقطۀ مجاور | `_TRANS` شش‌جفتی (`:1989-2012`) | همین نشست | بی‌مصرف‌کننده | محاسبه، بی‌UI | بی‌متناظرِ بایگانی | **نیازمندِ UI** |

## سه موردِ «باگ‌نما» که رأیِ مالک است، نه خطایِ من

* `POWER_GOOD=1.5` / `POWER_BAD=0.8` در `useMarketPulse.ts:271-272` **فقط درِ
  فرانت** هستند و هیچ معادلِ پشت‌صحنه‌ای ندارند — تنها آستانهٔ این دور که درِ
  جزوه نیافتم. طبقِ قاعدۀ «هیچ threshold جدیدی اضافه نکن» حذفش کردم **نمی‌کنم**؛
  رنگِ قدرتِ خریدار را عوض می‌کند و باید مالک بگوید مبناءی درِ جزوه دارد یا نه.
* `HEMAT_GOOD=20/HEMAT_BAD=10` در `useMarketPulse.ts:22-23` دوباره‌نویسیِ
  `mstat_engine.py:47-48` است (تک‌منبع نیست) — بی‌خطرِ رفتاری، ولی همان درزِ
  «دو کد برایِ یک قاعده» که دورِ بنیادی بسته شد. اصلاحش یک commitِ جدا می‌خواهد.
* `mstat_snap` هیچ retention/DELETE ندارد (`mstat_engine` سطرِ پاک‌سازی ندارد؛
  فقط خواندن `limit=240`) — بزرگ‌شدنِ بی‌سقف. حذفِ ردیف = تصمیمِ از‌دست‌رفتنِ
  داده، پس دست نزدم.

## آنچه این دور *شد*

حلقۀ اسنپ‌شاتِ نبض بازار تا پیش از این بیرونِ پنجرۀ بازار هم هر ۳۰۰ ثانیه
بیدار می‌شد، اتصالِ SQLite می‌گشود و `ensure_schema` می‌زد؛ حالا درِ
`in_trading_session` است (`app.py:290-311`) — همان چیزی که مالک خواست:
«همهٔ pollingها فقط درِ trading session فعال باشند». رفتارِ درونِ نشست عوض نشده
(گارد `dev/pulse_ta_scope_v1063.py`: ۶۲/۶۲ سبز).
