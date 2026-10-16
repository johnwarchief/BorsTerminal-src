# REPO_MAP — BorsTerminal_Ultimate

> **نقشهٔ تاریخی/قدیمی:** این نقشه v9.7.2 و ساختار legacy مبتنی بر static را توصیف می‌کند و با معماری فعلی React/Vite در frontend ممکن است نخواند. برای کد جاری، ابتدا AGENTS.md و سپس docs/AGENT-INDEX.md تولیدشده را ببینید. این فایل حذف نشده تا تاریخچهٔ معماری حفظ شود.

نقشهٔ ناوبری مخزن. هدف: یک انسان یا یک ایجنت AI بتواند در ۲ دقیقه بداند
**کجا نگاه کند**، **چه چیزی به چه چیزی وصل است** و **چه چیزی را نباید جابه‌جا کند**.

نسخهٔ نرم‌افزار: `v9.7.2` · پورت پیش‌فرض توسعه: `8012` (لاانچرها: ۸۰۰۰ / ۸۰۰۱)

---

## ۱. ساختار پوشه‌ها

```
BorsTerminal_Ultimate/
├── app.py                  ★ سرور FastAPI — تنها نقطهٔ ورود HTTP (۴۳ route)
├── test_tsetmc.py          ⚠ موتور همگام‌ساز TSETMC — تست نیست! (بخش ۵)
├── codal_fetcher.py        خزندهٔ کدال (discover / update / backfill / feed)
├── codal_engine.py         لایهٔ نازک sync/ADB روی codal_fetcher (v9.7.7 — app.py مستقیم import می‌کند)
├── fts_engine.py           منطق ۵ شاخص بنیادی (FTS) — بدون وابستگی به HTTP
├── notifier.py             ارسال اعلان به Telegram + Bale
├── v2ray_rotator.py        چرخش IP از طریق پروکسی v2ray/Xray
├── bootstrap_first_run.py  پیش‌اجرا: بررسی DB و وابستگی‌ها
├── start_dashboard.py      لاانچر uvicorn (توسط *.bat صدا زده می‌شود)
├── bors_entry.py           لاانچر بستهٔ EXE (PyInstaller entry point)
├── bors_exe*.spec          مشخصات PyInstaller
├── fts_thresholds.json     آستانه‌های FTS (توسط UI بازنویسی می‌شود)
├── requirements.txt · CHANGELOG.md
│
├── static/                 ★ فرانت‌اند (ساختار دست‌نخورده بماند)
│   ├── index.html          تک‌صفحه‌ای + همهٔ handlerهای inline (onclick=…)
│   ├── app.js              نمای بازار / اسکرینر / کدال / تنظیمات
│   ├── fundamental_ui.js  تحلیل بنیادی (#tabFund) — فاز ۰
│   ├── portfolio_ui.js    کارتابل سبد FTS (#portfolioView) — فاز ۰
│   ├── tech_rtv.js         ★ چارت KLineCharts v10، overlayها، نوار ابزار
│   ├── tech_tools.js       ابزارهای ترسیم، زیرپنل‌ها، پنل شناور رسم
│   ├── tech_365.js         تنظیمات چارت بورش‌اجنت 365 (تعدیل/نوع قیمت/مقیاس)

│   ├── selection.js        سبد / رادار / تصمیم‌گیری روی نماد
│   ├── calendar/           تقویم رویدادها (service + UI + cache.json)
│   └── vendor/             کتابخانه‌های شخص ثالث (klinecharts، فونت، آیکون)
│
├── dev/                    تست‌های فعال + ابزارهای عملیاتی داده
├── scripts/                ابزار بسته‌بندی و انتشار (از ریشه منتقل شد)
├── docs/                   مستندات تحلیلی و گزارش ممیزی
└── data/                   ❌ عمداً ساخته نشد — دلیلش در بخش ۵
```

پوشه‌های تولیدی که در گیت **نیستند**: `build/` `dist/` `portable/` `releases/`
`venv_build/` `android/` `logs/` `backups/` `.v2cache/` `__pycache__/`

---

## ۲. گراف وابستگی زمان اجرا (پایتون)

```
app.py ──┬──> codal_engine.py ──> codal_fetcher.py ──> v2ray_rotator.py
         │        (لایهٔ نازک sync/ADB روی codal_fetcher — app.py آن را هم مستقیم import می‌کند)
         ├──> fts_engine.py          (در ۴ نقطه از app.py import می‌شود)
         ├──> watchlist_store.py ──> confidence_engine.py ──> fts_engine.py
         │        (ماتریس «تایید سه‌گانه»: سه ستون pass|warn|fail|nodata، read-only)
         ├──> notifier.py            (داخل try/except — نبودش کشنده نیست)
         └──> test_tsetmc.py         (import + پایش زنده بودن پروسه)

start_dashboard.py    ──> app.py        (uvicorn run)
bootstrap_first_run.py  <── app.py      (subprocess، مسیر نسبی)
bors_entry.py         ──> app.py        (حالت EXE)
```

**هیچ ماژول پایتون ریشه‌ای را نمی‌توان به پوشهٔ دیگری منتقل کرد** مگر با
اصلاح هم‌زمان `sys.path`، `.spec`ها و لاانچرها.


---

## ۳. اندپوینت‌های فعال API

منبع: استخراج خودکار از `app.app.routes` (نه از حافظه).

**دادهٔ بازار و چارت**

| متد | مسیر | وظیفه |
|---|---|---|
| GET | `/` | سرو `static/index.html` |
| GET | `/api/market` | تابلو بازار (ORJSON + GZip + ETag/304) |
| GET | `/api/chart/{symbol}` | OHLCV روزانه + رویدادهای تعدیل از CDN TSETMC |
| GET | `/api/chart-db/{symbol}` | تاریخچهٔ کامل از `price_history` + تزریق کندل امروز |
| GET | `/api/chart/{symbol}/key-levels` | سطوح کلیدی (Swing) + بلوک عرضه/تقاضا |
| GET | `/api/patterns/{symbol}` | نقاط الگوها برای `KLineChart.createOverlay` |
| GET | `/api/history/{symbol}` | تاریخچهٔ خام |
| GET/POST | `/api/export` | خروجی Excel (GET قدیمی / POST با فیلترهای UI) |

**بنیادی (FTS)**

| متد | مسیر | وظیفه |
|---|---|---|
| GET | `/api/screener` | غربالگری ۵ شاخص FTS روی همهٔ نمادها |
| GET | `/api/fts` | اسکن کامل FTS، مرتب بر اساس امتیاز |
| GET | `/api/fts/{symbol}` | ۵ شاخص یک نماد + جزئیات هر شاخص |
| GET | `/api/fundamental/{symbol}` | کارت بنیادی پنج‌لایهٔ FTS v10 (insights + details + data_gaps) |
| GET | `/api/sync/codal/fts-coverage` | پوشش دادهٔ هر لایه روی کل بازار (تشخیص «قابل محاسبه نبود» از «رد») |

---

## ۴. راهنمای سریع اجرا و تست

```bash
# اجرا (ویندوز)
run_terminal.bat                        # پورت ۸۰۰۰
python start_dashboard.py --port 8012   # مستقیم

# تست‌های آفلاین — باید همیشه ۱۰۰٪ سبز باشند
python dev/run_all_tests.py

# تست نیازمند سرور روشن روی پورت ۸۰۱۲
python dev/serve_check_v95.py
python dev/fts_roundtrip_v91.py

# بررسی ساختار کد (بدون اجرا)
python dev/struct_check.py

# گارد سینتکس
node --check static/app.js
node --check static/fundamental_ui.js
node --check static/portfolio_ui.js
node --check static/tech_rtv.js
node --check static/tech_tools.js
```

`dev/run_all_tests.py` این ۱۶ سوئیت را اجرا می‌کند و مبنای «خط قرمز» است
(۱۴ سوئیتِ پایتون + ۲ سوئیتِ Node؛ اگر `node` نصب نباشد سوئیت‌های JS با SKIP رد میشوند).
پیش از سوئیت‌های Node، `dev/make_fts_ui_fixture.py` یک‌بار اجرا میشود تا clone تازه
بدونِ فایلِ generated هم سبز بماند:

| سوئیت | نقش |
|---|---|
| `struct_check.py` | نام‌های تعریف‌نشده / سلامت ساختار |
| `test_fts_isolation.py` | ایزوله بودن فیلترهای FTS |
| `test_fts_v10_ladder.py` | نردبانِ شاهدِ EPS + قاعدهٔ «سطرِ ناقص حذف نمیشود، قرمز میشود» + هدرِ خروجیِ فارسی |
| `test_fts_market_cap.py` | ارزش بازار تک‌منبع (TSETMC) + تبدیلِ همت + دروازه‌های ریسک (ماده ۱۴۱، کفِ ارزش، نقدشوندگی، صنایع) + پروانس/staleness |
| `test_fts_v10_ui.js` | رندرِ جدول بنیادی در `fundamental_ui.js` با DOM ساختگی (fixture از `make_fts_ui_fixture.py`) |
| `test_fts_settings_ui.js` | پنل تنظیمات CODAL v10 در Node با DOM ساختگی: ردِ نامعتبر بدونِ POST، payload درست‌تایپ، خطایِ سرور، بازیابیِ پیش‌فرض، پارسِ اعدادِ فارسی |
| `test_calendar_v92.py` | هم‌خوانی دسته‌های تقویم پایتون↔JS |
| `chart_api_check_v95.py` | گارد API کتابخانهٔ KLineCharts v10 + کش‌بستر |
| `fts_m141_parity_v97.py` | برابری m141/نقدشوندگی + ضد N+1 |
| `adb_resilience_v972.py` | حلقهٔ Retry/Re-connect ADB + بازگشت Wi-Fi |
| `confidence_engine_v973.py` | موتور تایید سه‌گانه (سه ستون، ضد N+1، برابری نوشتار) |
| `soft_warnings_v974.py` | حالت چهارم `warn` — هیچ وتوی سختی باقی نمانده |
| `watchlist_matrix_v973.py` | ذخیرهٔ واچ‌لیست + ماتریس + برابری نوشتار |
| `repo_hygiene_v97.py` | کد مرده/یتیم/توابع بلااستفاده برنمی‌گردند |

---

## ۵. ⚠ پروتکل‌های شکستن‌ناپذیر

این موارد «بوی بد» می‌دهند ولی **عمدی** هستند؛ جابه‌جایی ساکت می‌شکند:

1. **`test_tsetmc.py` یک تست نیست.** ماژول زمان اجراست که `app.py` ایمپورتش
   می‌کند. بدتر: زنده بودنش با **نام پروسه** سنجیده می‌شود
   (`_count_procs("test_tsetmc")` و فیلتر `CommandLine -match 'test_tsetmc'`).
   تغییر نام یا جابه‌جایی‌اش = از دست رفتن تشخیص «sync در حال اجرا».

2. **`market.db` باید در CWD و کنار EXE بماند.** `DB_PATH` نسبی به CWD است
   (`"../market.db"` اگر وجود داشت، وگرنه `"market.db"`) و `bors_entry.py` آن را
   «SAME folder as the EXE» می‌خواهد. پوشهٔ `data/` عمداً ساخته نشد.

3. **JSONهای وضعیت توسط چند ماژول مستقل نوشته می‌شوند.** `sync_summary.json`
   را هم `codal_fetcher.py` و هم `test_tsetmc.py` می‌نویسند؛
   `sync_status.json` / `market_sync.json` / `codal_control.json` هم از چند جا.
   همه از الگوی `dirname(abspath(__file__))` استفاده می‌کنند. برای تجمیع،
   ثابت‌های مسیر در یک بلوک واحد بالای `app.py` حول `APP_DIR` جمع شده‌اند —
   ولی خود فایل‌ها جابه‌جا نشده‌اند.

4. **`sync_summary.json` وضعیت زمان اجراست، نه کد.** از گیت untrack شد.

5. **اسکریپت‌های منتقل‌شده به `scripts/`** مسیر نسبی می‌خواهند. همه `ROOT` را از
   `__file__` می‌سازند و اکنون `dirname(dirname(__file__))` است؛
   `run_discovery.sh` هم `cd ..` می‌کند. اگر فایل جدیدی به `scripts/` رفت،
   همین الگو را رعایت کنید.

| GET/POST | `/api/fts/config` | خواندن/ذخیرهٔ آستانه‌ها (`fts_thresholds.json`) |

**سبد و تصمیم**

| متد | مسیر | وظیفه |
|---|---|---|
| GET | `/api/selection/portfolio` | سبد نهایی + رادار + شمارش وضعیت‌ها |
| POST | `/api/selection/decision` | ثبت/بروزرسانی تصمیم روی یک نماد |
| DELETE | `/api/selection/decision/{symbol}` | پاک کردن تصمیم یک نماد |

**وضعیت بازار**
`/api/market-status/{overview,timeline,industries,mainwatch,histo}` ·
`/api/market/sync-state`

**همگام‌سازی و عملیات**

| متد | مسیر | وظیفه |
|---|---|---|
| POST | `/api/sync/market` · `/api/sync/codal` | شروع sync تابلو / کدال |
| POST | `/api/sync/update-existing` · `/api/sync/discover` | فید افزایشی / کشف نماد جدید |
| GET | `/api/sync/pipeline` · `/status` · `/diagnose` | وضعیت و عیب‌یابی |
| POST | `/api/codal/control` | pause / resume / stop اسکن |
| GET/POST | `/api/adb/state` · `/api/adb/set` | وضعیت و تنظیم چرخش IP |
| GET/POST | `/api/notify/status` · `/test-{telegram,bale,all}` | اعلان‌ها |


---

## ۶. بدهی فنی شناخته‌شده (عمداً دست‌نخورده)

| مورد | توضیح |
|---|---|
| **بدهی `tech_panel.js` — حل‌شده در v9.7.1** | پنل قدیمی LightweightCharts حذف شد. دکمهٔ 📊 مودال تحلیل حالا `gotoChart()` را صدا می‌زند و همان موتور زندهٔ KLineCharts v10 (تب `techView`) را باز می‌کند. پیش‌تر کلیک، `ReferenceError: LightweightCharts is not defined` می‌داد و بدتر: مودال `#techWindow` فعال می‌ماند و کاربر یک پنل تمام‌صفحهٔ **کاملاً خالی** می‌دید (با CDP و اسکرین‌شات ثبت شد). `static/tech_panel.js` و `static/lightweight-charts.standalone.production.js` (160KB) و مارک‌آپ `#techWindow` و 14 قاعدهٔ CSS یتیم حذف شدند؛ گارد رگرسیون در `dev/chart_api_check_v95.py` بند ۱۶ اضافه شد. |
| **سرریز چیدمان تب تکنیکال — حل‌شده در v9.7.1** | `.tv5-shell` فقط `grid-template-rows` داشت؛ ستون ضمنیِ `auto` بر پایهٔ max-content و عرض ذاتی `<canvas>`ها 1260px می‌شد (بیش از والد 1164px) و 96px به چپ سرریز می‌کرد → ریل ابزار رسم (129 دکمه) و دکمه‌های تنظیمات/تم کاملاً بیرون ویوپورت (`elementFromPoint` → null). با `grid-template-columns: minmax(0,1fr)` و `flex-wrap: wrap` روی `.nn-head` رفع شد. |
| **`rvSetScale` معکوس — حل‌شده در v9.7.1** | `rv.logScale` ست می‌شد و بی‌درنگ `rvToggleLog()` همان را برمی‌گرداند، پس `?scale=log` مقیاس خطی و `?scale=linear` لگاریتمی می‌داد. حالا به `btsSetScale` واگذار می‌شود که نام محور را ست، ذخیره و با `getYAxes` راستی‌آزمایی می‌کند. |

| **همگام‌سازی `rv.logScale` — حل‌شده در v9.7.2** | `btsApplySettings` محور ذخیره‌شده را با `overrideYAxis` اعمال می‌کرد ولی `rv.logScale` را هرگز ست نمی‌کرد؛ بعد از reload محور لگاریتمی بود و پرچم `false` می‌ماند و همان مقدار نادرست داخل بلاب `tech_<sym>` ذخیره می‌شد. حالا پرچم از «نام محوری که کتابخانه واقعاً ساخته» (`btsAxis`) مشتق می‌شود، نه از آنچه درخواست کرده‌ایم. با Playwright روی :8012 تأیید شد. |
| **دورهٔ اندیکاتور بر پایهٔ تایم‌فریم — v9.7.2** | RSI روی کندل هفتگی با دورهٔ ۱۴ (≈۳ ماه) بیش از حد کند بود. `RTV_IND_DEFAULTS` + `rvIndParams()` اضافه شد: RSI روزانه ۱۴ / هفتگی ۷ (ماهانه عمداً ۱۴ چون خواسته نشده بود)، EMA ‏20/50/200 و BOLL ‏20/2. `rvIndSyncParams()` پس از هر `rvLoad` دورهٔ پن‌های فعال را با `overrideIndicator` بازاعمال می‌کند؛ تست زنده نشان داد اورلی کاربر در رفت‌وبرگشت D→W→D بدون تکرار و بدون مفقودی سالم می‌ماند. |
| **ADB: احیای دستگاه و تضمین بازگشت Wi-Fi — v9.7.2** | «offline» و «unauthorized» مثل «دستگاه نیست» رد می‌شدند؛ حالا `_adb_wait_ready` با حلقهٔ Retry + Re-connect و `kill-server`/`start-server` احیا می‌کند. مهم‌تر: `_wifi(True)` فقط در مسیرهای خطای شناخته‌شده زده می‌شد و استثنا یا کشته‌شدن پروسه میانِ توگل، Wi-Fi میزبان را **خاموش** رها می‌کرد؛ اکنون در `finally` تضمین شده. قفل هم غیرهمبلوک شد تا کارگر دوم روی چرخش ۲ دقیقه‌ای فریز نشود. گارد: `dev/adb_resilience_v972.py` (۲۶ چک). |
| **۹ کلاس CSS یتیم — حذف‌شده در v9.7.2** | `.tv-pop-bar` `.tv-pop-btns` `.tv-pop-title` `.tv5-badge` `.tv5-danger` `.tv5-sym` `.tv5-sym-name` `.tv5-tfs` `.tv5-tools` — صفر ارجاع در HTML/JS. قوانین هم‌خانوادهٔ زنده (`.tv-pop`, `.tv-pop-body`, `.tv5-tf`, `.tv5-btn`) دست‌نخورده‌اند و در گارد بند ۱۸ `chart_api_check_v95.py` قفل شده‌اند. |

| **معنای `running` در `/api/market/sync-state`** | یک route تکراری روی همین مسیر ثبت شده بود که به‌دلیل «اولین match برنده است» هرگز اجرا نمی‌شد و حذف گردید. docstringِ بازمانده توضیح می‌دهد که اگر UI باید thread درون‌پروسه‌ای را نشان دهد، تعویض `_market_running()` با `_market_sync_alive()` یک **تغییر رفتار** است، نه اصلاح بی‌ضرر. |
| **USD و مارکت‌کپ** | حالت‌های قیمت USD/مارکت‌کپ در UI غیرفعال‌اند چون دادهٔ مطمئن در بک‌اند نیست. |
| **شبکه** | دریافت زنده از `search.codal.ir` ممکن است با فیلتر/بن WAF محدود شود. |

---

## ۷. `dev/` — تفکیک فعال از عملیاتی

**تست‌های فعال** (توسط `run_all_tests.py` یا دستی روی سرور):
`run_all_tests.py` · `struct_check.py` · `test_fts_isolation.py` ·
`test_calendar_v92.py` · `chart_api_check_v95.py` · `fts_m141_parity_v97.py` ·
`test_fts_v10_ladder.py` (نردبانِ شاهدِ EPS + قاعدهٔ سطرِ ناقص + هدرِ خروجی) ·
`test_fts_market_cap.py` (ارزش بازار تک‌منبع + دروازه‌های ریسک) ·
`test_fts_v10_ui.js` (رندرِ جدول بنیادی در Node با DOM ساختگی) ·
`test_fts_settings_ui.js` (پنل تنظیمات CODAL v10 + localStorage + apply بی‌reload) ·
`make_fts_ui_fixture.py` (سازندهٔ `dev/fixtures/fts_v10_payloads.json`) ·
`serve_check_v95.py` · `fts_roundtrip_v91.py`

**ابزار عملیاتی داده** (تست نیستند؛ خط تولید داده):
`calendar_fetcher.py` (ساز `static/calendar/cache.json`) ·
`codal_fts_updater.py` · `update_codal.py` · `pipeline_updater.py` ·
`pipeline_discover3.py`

**ابزار عمومی**: `grep.py` · `dump.py`

> `struct_check.py` و `fts_roundtrip_v91.py` هنگام اجرا `dev/_struct.txt` و
> `dev/_fts.txt` می‌نویسند. این‌ها خروجی‌اند و با قاعدهٔ `dev/_*` در
> `.gitignore` نادیده گرفته می‌شوند.

---

## ۸. توابع JS — الگوی نام‌گذاری

| پیشوند | فایل | نقش |
|---|---|---|
| `rv*` | `tech_rtv.js`, `tech_tools.js` | چارت KLineCharts v10 و ابزارهای ترسیم |
| `bts*` | `tech_365.js` | تنظیمات بورش‌اجنت ۳۶۵ (تعدیل، نوع قیمت، مقیاس) |
| `cal*` / `CalService` | `calendar/` | تقویم رویدادها |

| `SEL*` / `sel*` | `selection.js` | سبد و تصمیم |
| `pf*` | `portfolio_ui.js` | کارتابل سبد FTS، نردبان حد ضرر، ماتریس تریپل |
| `loadFundamentalData` / `fmtMcap` / `fmtBil` / `switchModalTab` | `fundamental_ui.js` | تحلیل بنیادی در #chartModal |
| `FTS_SETTINGS` / `saveFtsConfig` / `loadFtsConfig` | `fundamental_ui.js` | پنل تنظیمات CODAL v10 (اعتبارسنجی، localStorage، apply بی‌reload). دو handler سراسری **بازنویسی** میشوند تا `index.html` تغییر نکند؛ `loadFtsConfig(force)` حالتِ «بازیابی پیش‌فرض» است |

نکته برای ایجنت‌ها: توابع این فایل‌ها **سطح‌بالا و سراسری** هستند و بیشترِ
اتصال‌ها از طریق `onclick="…"` در `index.html` انجام می‌شود، نه `import`.
پس برای تشخیص «مرده بودن» یک تابع، باید **همهٔ فایل‌ها از جمله `index.html`**
جستجو شوند؛ جستجوی فایل JS به‌تنهایی نتیجهٔ غلط می‌دهد.

**مستندات API**: `/docs` (Swagger) · `/redoc` · `/openapi.json`
