# سرخطی (Sarkhati) — سندِ معماری

**وضعیت: Stage A تمام شد — فقط مماریِ معماری. هیچ implementation شروع نشده.**
تاریخِ سنجش: ۱۴۰۵-۰۷-۱۴، روی همین ماشین، روی همین clone.
همه‌چیز با `path:line`؛ هرچه چشمِ خودم ندیده صریح علامت خورده است.

---

## ۰) این سند چیست و چیست نیست

Stage A پاسخِ ده پرسشِ بندِ ۱ِ دستورِ کار است: مسیرِ واقعیِ نماد→شناسه، جایِ
قیمتِ زنده، جایِ تعریفِ نشستِ معاملاتی، زیرساختِ polling، توانِ Tauri/WebView،
مدیریتِ secret، routing و نقطهٔ نشستنِ سرویسِ جدید.

**این سند معماری نهایی را اعلام نمی‌کند.** §5 فهرستِ تصمیم‌هایی است که بی‌پاسخ
مانده و §6 فهرستِ منابعی است که در Stage B خوانده می‌شوند. هیچ ادعایِ
کارایی/latency درِ این سند نیست؛ benchmark داخلی هنوز گرفته نشده.

---

## ۱) نقشهٔ وضعیتِ موجود (سنجیده‌شده)

### ۱-الف) نماد → شناسهٔ canonical

- ورودیِ API یک `symbol` متنی است؛ تبدیلِ آن به `insCode` از
  `api/chart.py:296-300` می‌گذرد: `sym_pred("l_val18", symbol)` →
  `SELECT ins_code FROM instruments WHERE …`.
- `sym_pred` درِ `api/_core.py:298` است و به `fts_engine.sym_in` /
  `symbol_aliases` / `norm_fa` (`fts_engine.py:46-56, 84-153`) تکیه می‌کند.
  **تطبیق «تاشبکه‌ای» است، نه exact** — چون نمادهایِ بانک با حرفِ عربی ذخیره
  می‌شوند: سنجشِ زندهٔ امروز رویِ `market.db` = ۶۱۰ ردیف با `ک` عربی و ۱۱۰۳ ردیف با `ي`
  عربی (کامنتِ `api/_core.py:288-297` هنوز ۳۴۴/۵۵۴ می‌گوید، یعنی خودش کهنه است)
  و `WHERE symbol = ?`
  بی‌صدا صفر ردیف برمی‌گرداند؛ `norm_fa(col)=?` هم سنجیده‌شده ۵۷۴ برابر کند است
  (`fts_engine.py:68-71`) چون ایندکس را می‌بندد.
- **خطرِ اثبات‌شده:** همان بسطِ alias با `ORDER BY updated_at DESC LIMIT 1`
  یک‌بار «اعتماد4» را به `insCode`ِ خواهرش رسانده (`_audit/adjustment_parity_phasea.md:471`).
  برایِ تابلو این یک خطایِ نمایشی است؛ **برایِ سفارش، این یعنی ارسالِ سفارش رویِ
  نمادِ اشتباه.** هر مسیرِ execution باید شناسه را از یک منبعِ *تک‌مقداریِ تأییدشده*
  بگیرد، نه از fuzzy matchِ چندگزینه‌ای.
- یک مسیرِ exact-matchِ کهنه هم هست: `test_tsetmc.py:1796-1798`.

### ۱-ب) ISIN — هست، ولی نه برایِ همه

- `instruments(ins_code PK, l_val18, l_val30, …, isin TEXT, c_gr_val_cot TEXT)`
  درِ `test_tsetmc.py:1478-1488`؛ ISIN از کلیدِ خامِ `insID` همان پاسخِ تابلو می‌آید
  (`test_tsetmc.py:2004, 2423`) و «چسبنده» است (COALESCE درِ `:124-152`).
- **سنجشِ مستقیمِ من رویِ `market.db` امروز: ۵۶۷۴ نماد، ۱۸۲۰ تای ISIN ندارند
  (~۳۲٪ فقدان)، ۳۸۵۴ ISIN متمایز، ۰ تکراری.** هیچ اسکریپتی درِ ریپو پوششِ ISIN
  را اندازه نمی‌گیرد. اگر کارگزاری با ISIN کار کند، ۱۸۲۰ نماد بی‌ISIN یعنی
  «قابلِ سفارش نیستند» — باید معلوم شود این فقدان از سینک است یا از مبدأ.

### ۱-ج) نگاشتِ کارگزاری: **وجود ندارد**

هیچ «mofid» درِ کد نیست. `کارگزاری` فقط متنِ نامِ شرکت است
(`frontend/src/features/fundamental/lib/assetScope.ts:10,20` — فقط برایِ فیلترِ نمایش). پس نمادِ کارگزاری ↔ نمادِ TSETMC امروز هیچ جایی تعریف نشده.

### ۱-د) قیمتِ زنده — و چیزی که **نمی‌رسد**

- تابلو `p_last`، `p_closing`، `price_yesterday` و `tmin` (مجازِ پایین) را می‌فرستد
  (`api/market.py:835`، زنده‌سازیِ `:505-515`، عبور از `_DROP_FIELDS` درِ `:638-649`).
- **بهترین خرید/فروش درِ پاسخِ تابلو نیست:** `buy_q1_px` و `sell_q1_px` (و
  `sell_q1_vol`) درِ `_DROP_FIELDS` هستند (`api/market.py:643`) — یعنی درِ بانک
  هستند و به UI نمی‌رسند. تعجبِ خوب: `buy_q1_vol` حذف نشده؛ فقط *قیمت‌ها* می‌افتند.
- عمقِ ۵ سطحی فقط تک‌نمادی است: `/api/order-book/{symbol}` از جدولِ `order_book`
  (`api/chart.py:783-827`) که **فقط سینکِ کامل** می‌نویسدش (`test_tsetmc.py:514, 2462`)؛
  تیکِ ۵ ثانیه‌ای اصلاً ستون‌هایِ صف را دست نمی‌زند (`test_tsetmc.py:2209-2232`).
  پس تازگیِ دفتر ≈ ۹۰ ثانیه و بعد از ۱۲:۳۰ کهنه.
- برچسبِ تازگی: `meta.last_sync` (`api/market.py:699-714`).

**نتیجهٔ عملی برایِ بندِ ۱۷ دستورِ کار (قیمتِ سفارش):** گزینه‌هایِ «Best Ask»
و «Limit Up» امروز از مسیرِ تابلو قابلِ پیاده‌سازی نیستند؛ یا `_DROP_FIELDS`
برایِ یک پاسخِ اختصاصی باز می‌شود یا از `order-book` تک‌نمادی خوانده می‌شود با
قیدِ ۹۰ ثانیه. این یک تصمیمِ معماری است، نه یک خطا.

### ۱-ه) زمان‌بندیِ نشست: **یک منبعِ حقیقت ندارد**

| کجا | پنجره | ساعتِ مرجع |
| --- | --- | --- |
| `mstat_engine.py:78-98` (`SESSION_OPEN_HM=85500`, `CLOSE=130005`) | ۰۸:۵۵–۱۳:۰۰ | naiveِ سیستم |
| `test_tsetmc.py:2165-2170` (`tick_live`) | <۰۸:۵۵ یا ≥۲۰:۰۰ = بی‌درخواست؛ ≥۱۲:۳۰ فقط عدد | naiveِ سیستم |
| `frontend/src/shared/lib/marketHours.ts:10-21` | ۰۸:۴۵–۱۲:۳۰، شنبه–چهارشنبه | **ساعتِ مرورگر** |

- هیچ NTP و هیچ تبدیلِ منطقهٔ زمانی درِ بک‌اند نیست؛ `Asia/Tehran` فقط درِ پیکربندیِ
  نمایشِ چارت آمده (`ftsConfigStore.ts:99`). رویِ ماشینِ غیرتهرانی هر سه دروازه
  جابه‌جا می‌شود — و این برایِ «dispatch درِ ثانیهٔ دقیق» یعنی زمان‌بندیِ غلط.
- «تابلو بسته است» به‌صورتِ حالتِ صریح وجود ندارد؛ فقط `is_live`/شمارشِ فسیل‌ها
  (`api/market.py:1039-1041`).

### ۱-و) زیرساختِ قابلِ استفادهٔ مجدد

- **بله، هست:** `time.monotonic()` برایِ TTL (`api/market_status.py:51`)، cooldownِ ۴۲۹
  (`test_tsetmc.py:909-953`)، زمان‌بندیِ تیک (`:2172`)؛ و اندازه‌گیریِ RTTِ هر چرخه
  `note_cycle(elapsed_s)` (`market_state.py:221-229`) که از `/api/live-stats`
  بیرون می‌رود (`api/market.py:1120-1133`). این هستۀِ «latencyِ اندازه‌گیری‌شده» است.
- **تغییرِ تابلو ارزان قابلِ فهمیدن است:** ETag بدنه با 304 (`api/market.py:717-724`)،
  شمارندۀِ revision در RAM که فقط بعدِ نوشتنِ موفق بالا می‌رود
  (`market_state.py:168-172`)، و `/api/market/delta?since=rev`
  با سه حالتِ `unchanged|delta|full` (`api/market.py:1069-1110`).
  `tick_live` امضایِ تابلویِ قبلی را نگه می‌دارد (`test_tsetmc.py:2124-2140`).
- **خیر، وجود ندارد:** هیچ asyncio task، هیچ APScheduler، هیچ صفِ کار، هیچ
  `threading.Timer`. همه‌چیز `threading.Thread` daemon است که درِ **یک** قلابِ
  startupِ `app.py:168-352` شروع می‌شود و هیچ‌وقت متوقف نمی‌شود
  (`api/_sync_market.py:66,76`؛ حلقه‌هایِ ۹۰s/۵s/۳۰۰s درِ `app.py:232-318`).
  پایپ‌لاین‌هایِ کدال `subprocess.Popen`اند با دیکتِ درون‌حافظه‌ای
  `_PIPELINE_JOBS` که فرانت poll می‌کند (`api/_pipeline.py:21-45`).

### ۱-ز) کلاینتِ HTTP و keep-alive

`requests` و `httpx` هر دو درِ `requirements.txt:3-4`. TSETMC با `requests`
(`test_tsetmc.py:17`)، کدال با `requests` (`codal_fetcher.py:25`)، نوتیفایر با
`httpx` ولی **کلاینتِ نوپا درِ هر فراخوانی** (`notifier.py:216,237,258`).
reuse واقعی فقط با `requests.Session` + `HTTPAdapter(pool_maxsize=10)` + `Retry`
هست: `codal_fetcher.py:471-518` و `test_tsetmc.py:866-898`؛ و `threading.local()`
برایِ sessionِ به‌ازای‌کارگر (`codal_fetcher.py:2319,3128`). **HTTP/2 هیچ‌جا نیست**
و `curl_cffi` هم نیست — برایِ کارگزاری‌هایی که TLS-fingerprint حساس‌اند این یک
سؤالِ باز است، نه نتیجه.

### ۱-ح) پنجرهٔ واقعی: pywebview، نه Tauri

اپِ منتشرشده درِ **pywebview + Edge WebView2** اجرا می‌شود
(`bors_entry.py:425-474`) با **پروفایلِ ذخیره‌سازیِ ماندگار**
(`_webview_storage_dir()` درِ `bors_entry.py:401-420`، مسیرِ
`%LOCALAPPDATA%\BorsTerminal_Ultimate\webview2`) و `edgechromium` درِ
`fts_terminal.spec:95`. Tauri یک مسیرِ دومِ عملاً بی‌استفاده است: `release.ps1`
هیچ‌وقت `tauri build` را اجرا نمی‌کند، `lib.rs:2-18` فقط سه پلاگین ثبت می‌کند و
**هیچ `#[tauri::command]` ندارد**؛ capabilities فقط `core/updater/process`
(`capabilities/default.json:8-12`). پس اگر روزی «لاگینِ دستی درِ WebView» لازم
شود، میزبانِ واقعی همان WebView2ِ pywebview است و مزیتش همین است که کوکی/ذخیره
بینِ اجراها می‌ماند.

### ۱-ط) رازها و نشست — وضعیتِ امروز

- لاگینِ محلی **مرزِ امنیتی نیست** و خودِ ریپو همین را می‌گوید
  (`app.py:63-75`). `authStore.ts:8-9` کاربر/رمزِ پیش‌فرض را hard-code می‌کند و
  `:71-78` رمزِ تایپ‌شده را **به‌صورتِ متنِ خام** با `localStorage['bors_auth_pass']`
  مقایسه می‌کند؛ قفلِ ضدِ brute-force فقط درِ حافظۀِ zustand است (`:86-94`) و با
  reload می‌پرد.
- **هیچ ذخیره‌سازِ امنِ سیستم‌عاملی وجود ندارد:** zero hit برای
  `keyring` / DPAPI / `win32crypt` / CredentialManager. همه‌چیز فایل/ env /
  localStorage. `winreg` فقط برایِ مسیرِ نصب (`api/update.py:165-211`).
- فایل‌هایِ رازدارِ امروزی: `installer/.setup_password.iss` (gitignored
  `.gitignore:38`، ولی **داخلِ EXE بسته می‌شود** —
  `fts_terminal.spec:45`، `api/update.py:127-159`)؛ `.tauri/updater.key`
  (rsign، رمز‌عبور-رمزنگاری‌شده `scripts/sign_setup.py:67`)؛ `RELEASE_TOKEN`
  فقط secretِ CI؛ `TYPESAFE_API_KEY` فقط env (`tools/pilot_ctl.py:59-60`)؛
  توکنِ ربات از `.env` (`notifier.py:73,80`).
- **مسیرِ نشتیِ مشخص:** stdout/stderr به `logs/bors.log` می‌ریزد
  (`bors_entry.py:37-38`) و `uvicorn.access` کلِ خطِ درخواست را ثبت می‌کند
  (`bors_entry.py:80-96`)؛ همان فایل از `GET /api/diagnostics/log` بی‌احرازِ هویت
  خوانده می‌شود (`api/diagnostics.py:53-69`). دروازهٔ حلقهٔ محروی همهٔ `/api/*`
  را می‌گیرد (`app.py:61-90`) پس مرورگرِ بیرونی نمی‌تواند بخواند، **ولی هر پروسۀِ
  محلی می‌تواند.** نتیجه: اگر توکنِ کارگزاری روزی به query string برود، رویِ دیسک
  و قابلِ خواندن می‌نشیند. (الان همین الگو برایِ `signature` درِ query وجود دارد:
  `useAppUpdater.ts:355`.)
- الگویِ «قبل از اعتماد، امضا را بررسی کن» از قبل هست: `bors_minisign.py:187-211`
  با keyid match و trusted-comment، مصرف‌شده درِ `api/update.py:317-320,355,598`
  و `api/_sync_codal.py:258-261`.

### ۱-ی) routing و قفل‌هایِ build

- `app.py:362` حتماً **پیش از** catch-allِ `app.py:365-374`؛ هر روتری که درِ
  `api/__init__.py:16-18` فهرست نشود اصلاً ثبت نمی‌شود، و هر روتری که بعد از
  خطِ ۳۶۵ اضافه شود زیرِ index.html گم می‌شود.
- `hiddenimports` درِ `fts_terminal.spec:47-104` (۱۸ ماژولِ `api.*`)؛ قاعده:
  هر `api/*.py` تازه باید اینجا بیاید وگرنه EXE درِ اولین درخواست
  `ModuleNotFoundError` می‌دهد — و این را `dev/onedir_contract_v11.py:50-71`
  نگهبانی می‌کند.
- **یافتۀِ جانبی (واگرایی، نه خطرِ ریلیز):** دو spec واگرا شده‌اند. شمارشِ
  دقیقِ `hiddenimports`: `fts_terminal.spec` = ۶۶، `bors_setup.spec` = ۵۱.
  ۲۰ مورد فقط درِ اولی است (`api.diagnostics`, `tsetmc_p0_schema`,
  `candle_contract`, `codal_periods`, `price_basis`, `market_state`, `tape_flags`,
  `webview.*`, `PIL.*`) و ۵ مورد فقط درِ دومی (`codal_engine`, `confidence_engine`,
  `mstat_engine`, `notifier`, `winreg`). **اما** نسخۀِ منتشرشده از
  `fts_terminal.spec` ساخته می‌شود (`release.ps1:121`، `scripts/build_all.py:19`)،
  پس این «ریلیز می‌شکند» نیست؛ یک بدهیِ نگهداری است: `bors_setup.spec` هنوز
  توسطِ `dev/live_bar_session_date_v1059.py:274` خوانده می‌شود، یعنی یک گارد
  دارد چیزی را چک می‌کند که درِ مسیرِ واقعیِ بیلد نیست.
- فرانت: مسیرِ تازه به `frontend/src/routes.tsx:8-33` اضافه می‌شود؛ ماتریسِ
  ESLint درِ `frontend/eslint.config.js:35-47` با `default: disallow` است و
  `features/*` فقط می‌تواند `shared` و `contracts` را ببیند (`:40`)؛ `fetch`
  بیرونِ `shared/api/**` و `features/*/api/**` ممنوع (`:52-58`).

---

## ۲) قیدهایی که از همین‌جا الزامی‌اند

1. **شناسهٔ نماد نباید fuzzy باشد.** یک تطبیقِ چندبه‌چند با `LIMIT 1` برایِ
   نمایش قابلِ تحمل است، برایِ سفارش نه. (سابقۀِ «اعتماد4» درِ §۱-الف.)
2. **هیچ secret درِ URL.** access log رویِ دیسک است و از `/api/diagnostics/log`
   خوانده می‌شود (§۱-ط). این یک قانونِ طراحی است، نه توصیه.
3. **زمان‌بندی بی‌ساعتِ تهرانِ مشخص، بی‌معنی است.** امروز سه پنجرهٔ متفاوت و
   صفر تبدیلِ منطقهٔ زمانی هست (§۱-ه). هر «dispatch درِ ۰۹:۰۰:۰۰» باید اول بگوید
   ۰۹:۰۰ِ کجاست و برچسبِ ساعتِ سیستم چقدر با آن فرق دارد.
4. **بودجۀِ درخواستِ TSETMC دست‌نخورده** (۶۰۰/روز، نگهبانی‌شده). سرخطی نباید
   با pollingِ تازه این را بخورد؛ مسیرِ دادهٔ قیمت یا از همان کش/revision موجود
   می‌آید یا صریح جدا حساب می‌شود.
5. **EXE-first:** هر ماژولِ بک‌اندِ تازه = `hiddenimports` + گاردِ onedir، وگرنه
   ریلیز می‌شکند. (§۱-ی)
6. **منطقِ FTS و contract هایِ canonical نباید لمس شوند.** سرخطی یک لایهٔ
   جداست؛ نه داورِ تازه، نه وزنِ تازه.

---

## ۳) چیزی که **نیست** (تا کسی فرض نکند هست)

کدِ کارگزاری/سفارش؛ نگاشتِ نماد↔کارگزاری؛ ذخیره‌سازِ امنِ سیستم‌عاملی؛
asyncio task / صفِ کار / APScheduler؛ HTTP/2؛ NTP؛ حالتِ صریحِ «تابلو بسته»؛
بهترینِ خرید/فروش درِ پاسخِ تابلو؛ هیچ `#[tauri::command]`؛ هیچ benchmark
داخلیِ latency برایِ مسیرِ سفارش (RTTِ اندازه‌گیری‌شده فقط برایِ چرخۀِ تابلو است).

---

## ۴) آنچه Stage A نتوانست قطع کند

- چرا ۱۸۲۰ نماد ISIN ندارد (سینک یا مبدأ) — هیچ سنجشِ منبع‌محوری نیست.
- آیا مسیرِ exact-matchِ `test_tsetmc.py:1797` از API زنده قابلِ رسیدن هست یا کهنه است.
- چرا `bors_setup.spec` اصلاً هنوز هست و چه چیزی از آن ساخته می‌شود (یک گارد
  می‌خواندش، اما مسیرِ بیلد نه).
- رفتارِ واقعی Inno درِ `install.log` نسبت به `/PASSWORD` (رفتارِ زمانِ اجرا، درِ ریپو دیده نمی‌شود).
- اینکه کارگزاریِ هدف با چه شناسه‌ای کار می‌کند (ISIN؟ کدِ داخلیِ نماد؟) — تا
  Stage E و لاگینِ واقعی روشن نمی‌شود.

---

## ۵) تصمیم‌هایِ بازِ معماری (مرحلهٔ B/C)

| # | تصمیم | چرا الان نه |
| --- | --- | --- |
| D1 | direct HTTP یا browser-automation یا hybrid | دستورِ کار می‌گوید با PoC، نه حدس (بندِ ۷) |
| D2 | منبعِ قیمتِ «Best Ask/Limit Up» با قیدِ ۹۰ ثانیه | §۱-د؛ باید معلوم شود از `_DROP_FIELDS` پس می‌گیرد یا از `order-book` |
| D3 | نشستنِ سرویس: `api/execution*.py` + سرویسِ thread درِ startupِ موجود، یا پروسهٔ جدا | همه‌چیزِ امروز daemon thread است و هیچ‌وقت متوقف نمی‌شود (§۱-و) — برایِ dispatchِ دقیق شاید کافی نباشد |
| D4 | ساعتِ مرجع: monotonic + آفستِ اندازه‌گیری‌شده به تهران | §۱-ه؛ تصمیمِ روش‌شناسی، حکمِ مالک لازم است |
| D5 | محلِ نگه‌داریِ توکن (فقط RAM؟ فایلِ رمزنگاری‌شده؟) | هیچ secure storage‌ای امروز نیست (§۱-ط) |
| D6 | سازگاریِ بودجه با pollingِ جدید | §۲ بندِ ۴ |

---

## ۶) منابعی که در Stage B خوانده می‌شوند (هنوز خوانده **نشده‌اند**)

`RezaMahdaviiDev/mofid` (مسیر‌هایِ `src/brokerages/easy/**`)،
`m-fazel/Sarkhati` (`mofid_online_plus.rs`, `time_reference.rs`, `calibration.rs`,
`rate_limiter.rs`)، `Sir-Sorg/Stock-Headline-Script-Mofid`، `Mkhorasani99/sarkhat`.
از هیچ‌کدام کد کپی نمی‌شود تا license شفاف نشود؛ ادعاهایِ latencyشان
(۵۰/۱۰۰ms) به‌عنوانِ fact پذیرفته نمی‌شود — معیار، benchmarkِ خودِ BorsTerminal است.
