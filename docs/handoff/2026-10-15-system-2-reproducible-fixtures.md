# fixtureها وِ شاهدهایِ بازتولیدپذیر — سیستمِ دوم — ۲۰۲۶‑۱۰‑۱۵

مأموریت: «هر کارِ فنیِ مفید یا درِ GitHub باشد یا باِ دلیلِ روشن استثنا شده باشد.»
اینِ سند نتیجهٔ ممیزیِ موجودیِ سیستمِ دوم است و **فقط** چیزهایی را می‌گوید که باِ فرمان
سنجیده شدند؛ هر عددِ دیگری درِ ارجاعِ فایلِ شاهدش هست.

- مخزن: `johnwarchief/BorsTerminal-src`
- شاخۀ این سند: `fix/system-2-reproducible-fixtures-2026-10-15` (پایه `ff6b2fb`)
- worktreeِ سنجش: `.worktrees/system-2-fixtures` — یکِ درختِ **بی‌هیچِ فایلِ ignoredِ
  چک‌اوتِ اصلی**، پس همانِ چیزی است که یکِ ماشینِ تازه باِ `git clone` می‌بیند.

## ۱) ایرادِ پیدا‌شده: دوِ suite که ازِ GitHub بازتولید نمی‌شدند

| suite | چه می‌خواست | چرا رویِ cloneِ تازه قرمز می‌شد |
|---|---|---|
| `dev/test_adjustment_engine_v1.py` | بندِ «ج»: بازتولیدِ فاکتورِ تعدیلِ `وبصادر` وِ کنترلِ بی‌رویدادِ `طلا` ازِ سریِ مرجعِ rahavard365 | شاهدِ مرجع `_audit/ra365_ref_bars.json` است (~۱۲MB) وِ `_audit/*.json` درِ `.gitignore` می‌ماند ⇒ بندِ «ج۰ شاهدِ مرجع موجود نیست» قرمز می‌داد |
| `dev/db_housekeeping.py --selftest` | dedupe + prev‑year backfill رویِ یکِ کپیِ تازه | `_fresh_copy()` مسیرِ `_ROOT/market.db.lzma` را hardcode می‌کند وِ `[FAIL] market.db.lzma not found` می‌داد |

هرِ دو درِ ممیزیِ UI (همینِ تاریخ) درِ worktreeِ `ui-audit-system-2` دیده شدند:
جاروبِ کاملِ `python dev/run_all_tests.py` → **۱۲۱ سبز / ۲ قرمز**، وِ هرِ دوِ قرمز
ازِ همینِ دوِ نبودِ fixture بود، نه ازِ کد. شاهدِ عددیِ همانِ دور:
`_audit/ui/GATE_python_final.txt` وِ `_audit/ui/GATE_housekeeping.txt` درِ آنِ شاخه.

## ۲) راهِ «ج» — زیرمجموعۀ شاهدِ منتشرشدنی

- `tools/make_adjustment_witness_fixture.py` ازِ کشیدنیِ کامل، **فقط** کلیدهایی را
  برمی‌دارد که آنِ suite می‌خواند: `وبصادر|type0|D`، `وبصادر|type7|D`،
  `طلا|type0|D`، `طلا|type7|D` وِ `meta["marks|…"]` دوِ نماد، به‌عالوۀِ بلوکِ
  `witness` (تعدادِ ردیفها، تعدادِ رویدادها، `source_sha256` مبدأ، `corpusSize`).
- خروجی: `dev/fixtures/ra365_witness_subset.json` — **۴۵۹٫۹۷۵ بایت** ازِ مبدأِ
  ۱۲٫۰۳۵٫۲۸۲ بایتی. مسیرِ `dev/fixtures/` عمداً انتخاب شد: همانِ جایی که مخزن
  fixtureهایِ تست را نگه می‌دارد (`dev/fixtures/fts_v10_payloads.json`)، پس بی‌هیچ
  استثنایِ `.gitignore` وِ بی‌`git add -f` درِ گیت می‌نشیند.
- تولید **قطعی** است: اجرایِ دوباره باِ همانِ مبدأ، بایت‌به‌بایت همانِ فایل را می‌دهد (سنجیده شد)، وِ خروجی باِ `newline=LF` نوشته می‌شود تاِ بایتِ فایلِ تولیدشده باِ بایتِ commit یکی باشد وِ `git status` بعدِ بازتولید تمیز بماند
  (شاهد: `sha256` یکسان درِ دوِ اجرایِ متوالی).
- ابزار هیچِ داده‌ای نمی‌سازد: اگر کلیدی درِ مبدأ نباشد، همانِ نماد بی‌داده می‌ماند،
  `WARN` روشن چاپ می‌شود وِ rc≠0. اگر مبدأ نباشد، rc=2 و هیچِ فایلِ خروجی نمی‌نویسد
  (سنجیده شد).
- `dev/test_adjustment_engine_v1.py` چهارِ سطر عوض شد: اول `_audit/ra365_ref_bars.json`
  (رفتارِ قبلیِ کامل، بی‌هیچ تغییرِ عددی)، وِ اگر نبود `dev/fixtures/ra365_witness_subset.json`.
  پیامِ «ج۰» حالا هرِ دوِ مسیر وِ ابزارِ سازنده را نام می‌برد.

**اثبات، درِ درختی که فایلِ ۱۲MB را ندارد:**

```
$ ls _audit/ra365_ref_bars.json          → No such file or directory
$ PYTHONIOENCODING=utf-8 python dev/test_adjustment_engine_v1.py
  ✓ ج۴ [وبصادر] میانۀِ خطا < ۰٫۱٪ درِ برابرِ type7/type0 (واقعی، بدونِ تنظیم)
     ↳ [وبصادر] نقاط=601 میانۀِ خطا=0.0370٪ رویدادها=9
نتیجه: 44 سبز، 0 قرمز        exit=0
```

میانۀِ خطا وِ شمارِ نقاط/رویدادها باِ اجرایِ رویِ کشیدنیِ کاملِ ۱۲MB یکی است (۰٫۰۳۷۰٪،
۶۰۱ نقطه، ۹ رویداد) ⇒ زیرمجموعه چیزی را دستکاری نکرده، فقط همانِ باریکه را آورده است.

## ۳) راهِ «دیتابیس» — درِ مخزن نیست، وِ نباید باشد

`docs/MARKET_DATA_RELEASE.md` ازِ قبل قراردادِ روشن دارد: مخزنِ سورس `market.db.lzma` را
عمداً نگه نمی‌دارد؛ بیس‌لاین درِ ریلیزِ `data-latest` رویِ `johnwarchief/BorsTerminal`
منتشر می‌شود وِ اپِ تازه‌نصب همان را می‌گیرد (`_download_market_db_lzma()` /
`ensure_market_db()` درِ `bors_config.py`). عددِ تأییدشده ازِ GitHub درِ همینِ ممیزی:

| قلم | مقدار |
|---|---|
| asset | `…/releases/download/data-latest/market.db.lzma` |
| HTTP | `200` (دنبالۀِ redirectِ asset سالم) |
| `size` | ۷۸٫۶۶۷٫۸۰۰ بایت |
| `sha256` | `e7df91dc0af257715494fbf31d64047ab4043d4b9d165e2467ca73b52d308157` |
| `source_repo` / `source_commit` | `johnwarchief/BorsTerminal-src` / `018d7856…` |
| `release_tag` / `published_at_utc` | `v1.0.88` / ۲۰۲۶‑۱۰‑۱۴T۱۸:۱۴:۵۸Z |

**سنجشِ واقعی، درِ worktreeِ تازه‌ای که خودِ asset را ازِ GitHub گرفت** (نه کپی ازِ چک‌اوتِ
اصلی؛ شاهدِ خامِ masked: `_audit/BASELINE_FETCH_RUN.txt` وِ
`_audit/GATE_housekeeping_from_release.txt`):

```
curl → market.db.lzma   bytes=78,667,800
sha256 = e7df91dc0af257715494fbf31d64047ab4043d4b9d165e2467ca73b52d308157   ← = meta.json
python dev/db_housekeeping.py --selftest      → exit 0، [selftest] PASS
  [ok] dry-run idempotent
  [ok] dedupe deleted 333 rows; dup groups now 0
  [ok] dedupe idempotent
  [ok] backfill filled 11405 cells
  [ok] backfill idempotent
  [ok] شارپيلن canonical (1 row per period)
  [ok] integrity=ok, fk_violations=0
```

یعنی آنِ suite دومی که درِ ممیزیِ UI قرمز شده بود، **بی‌هیچِ وابستگیِ مخفی بهِ اینِ ماشین**
سبز می‌شود؛ فقطِ دوِ فایلِ masked شده بودند چونِ خروجیِ خامِ selftest مسیرِ پروفیلِ موقتِ
`%TEMP%` اینِ کاربر را چاپ می‌کرد وِ مخزن **public** است. نکتهٔ صادقانه: اسنپ‌شاتِ local اینِ ماشین
۵۷٫۱۹۳٫۰۳۲ بایت باِ `sha256 99750b5b…` است وِ باِ assetِ منتشرشده **یکی نیست**
(قدیمی‌تر است). پس دوِ نسخهٔ «درست» داریم که یکی نیستند، وِ اینِ تفاوت باید دیده شود:
هر عددی که درِ اینِ سند ازِ assetِ منتشرشده می‌آید، نسخهٔ `v1.0.88` را ملاک دارد.

## ۴) آنچه ignored ماند (باِ دلیل، نه باِ نادیده‌گرفتن)

| قلم | حجم | چرا درِ گیت نیست | چه چیزی جایش می‌آید |
|---|---|---|---|
| `_audit/ra365_ref_bars.json` | ۱۲MB | کشیدنیِ خامِ بیرونِ مخزن (سیاستِ `_audit/*.json`)؛ renew آن نیازمندِ نشستِ احرازشدۀِ مالک درِ rahavard365 | جدول‌هایِ نتیجه درِ گیت + `dev/fixtures/ra365_witness_subset.json` (بندِ ۲) |
| `_audit/ra365_product_bars*.json` (۴ نسخه) | ~۲۷MB هرکدام | خروجیِ میانیِ pullِ محصول؛ نسخه‌هایِ تاریخیِ یکِ سنجش | `RA365-PHASE6-*.csv`, `RA365-PARITY-*.csv` درِ گیت |
| `market.db` / `market.db.lzma` / `codal.db` | ~۲۲۸MB / ۵۷–۷۹MB | دادهٔ عملیاتیِ بازار + ردیف‌هایِ کاربر؛ قراردادِ ریلیز، نه مخزنِ سورس | assetِ `data-latest` باِ `market.db.meta.json` (بندِ ۳) |
| `_audit/MS-BINDER-SHOTS/*.png` | ۲۶ فایل، ۵٫۹MB | `_audit/.gitignore` رویِ `*.png`؛ سنگینِ مخزن | متنِ `_audit/MS-BINDER-UI-RUN.txt` (tracked) + سندِ تحویل + بندِ ۵‑۲ (ارجاعِ شکستۀِ `binder1_pages` که عمداً درست نشد) |
| `_audit/ui/shots/*.png` | ۱۶۸ فایل، ~۲۳MB | همانِ سیاست | سه برشِ فشرده درِ `docs/ui-audit/img/` + اعدادِ قبل/بعد درِ `docs/ui-audit/2026-10-15-system-2.md` |
| `frontend/dist/**` | build | artefactِ ساخت، قابلِ بازتولید باِ `npm run build` | — |
| لاگِ راه‌اندازیِ مرورگر (`_audit/PHASE5F-CAPTURE*.txt`) | ۵KB | سطرهایشان `--user-data-dir=<پروفیلِ موقتِ کاربر>` وِ pid دارد؛ لاگِ اجراییِ خام | `_audit/PHASE5F-P5G-RUNDIGEST.txt` — همانِ outcomeها، بی‌سطرهایِ launch/مسیرهایِ موقت؛ مقدارِ credential درِ آنِ فایل‌ها نبود (فقطِ «طولِ token» چاپ شده بود که آن هم منتشر نمی‌شود) |

## ۵) ششِ قلمِ محلی که ازِ اینِ دور درِ GitHub هستند

1. `dev/fixtures/ra365_witness_subset.json` + `tools/make_adjustment_witness_fixture.py`
   وِ falling‑back درِ `dev/test_adjustment_engine_v1.py` (بندِ ۲).
2. **ارجاعِ شکسته‌ای که پیدا شد وِ عمداً منتشر نشد:** دوِ سندِ tracked
   (`docs/technical-indicators/reviewed/BINDER1-MARKET-STATUS-DELIVERY-1405-07-22.md` سطرِ ۵
   وِ `…-CAPABILITY-MATRIX-1405-07-23.md` سطرِ ۴) تصویرهایِ `_audit/binder1_pages/p01.jpg …
   p13.jpg` را ارجاع می‌دهند؛ آنِ سیزده فایل درِ **بیرونِ** مخزن بودند
   (`Borsterminal/_audit/binder1_pages/`، ۴۹۲KB) وِ هیچ‌وقت درِ GitHub نبودند. کپی‌شان درِ
   اینِ دور آماده شد وِ سپس برداشته شد: آنِ صفحه‌ها بریدۀِ **سندِ Binder1** (متعلق بهِ
   طرفِ دیگر)‌اند وِ اینِ مخزن **public** است (`api.github.com/repos/…` → HTTP 200). انتشارِ
   سندِ یکِ شخصِ ثالث تصمیمِ مالک است، نه تصمیمِ ممیزی ⇒ **ACTION REQUIRED (مالک)**؛
   تا then ارجاعِ دوِ سند رویِ GitHub شکسته می‌ماند وِ فایل‌هایِ اصلی سالم درِ دیسکِ همینِ
   ماشین‌اند (هیچ‌کدام جابه‌جا/پاک نشد). جایگزینِ بدونِ ریسک: نوشتنِ همانِ ۱۳ صفحه به‌صورت
   جدولِ متنِ فارسی درِ خودِ سند (دادهٔ خودِ ما، نه تصویرِ آن‌ها).

3. `_audit/P5G-FINAL-RC.txt` — سه rc (۳۲ بایت، بی‌مسیر/بی‌secret).
4. `_audit/PHASE5F-P5G-RUNDIGEST.txt` — خلاصۀِ پاک‌سازی‌شدهٔ پنجِ لاگِ اجرایی (بندِ ۴).
5. `_audit/BASELINE_FETCH_RUN.txt` وِ `_audit/GATE_housekeeping_from_release.txt` —
   سنجشِ «بیس‌لاین ازِ ریلیز بگیرید وِ suite را بزنید» (بندِ ۳).
6. `docs/handoff/2026-10-15-system-2-inventory.md` درِ شاخۀ
   `handoff/system-2/inventory-2026-10-15` به‌روز شد تاِ ممیزیِ UI (که درِ آنِ سند
   IN_PROGRESS بود) باِ رأیِ نهاییِ خودش وِ SHAهایِ تأییدشده جا بیفتد.

## ۶) بازتولید رویِ یکِ ماشینِ تازه

```bash
git clone https://github.com/johnwarchief/BorsTerminal-src && cd BorsTerminal-src
git fetch origin && git checkout fix/system-2-reproducible-fixtures-2026-10-15

cd frontend && npm ci && npm install-scripts approve esbuild && npm run build
npx tsc -b && npx vitest run                    # سوئیتِ کاملِ JS
PYTHONIOENCODING=utf-8 python dev/persian_glyph_guard.py

# شاهدِ تعدیل: بی‌هیچ فایلِ خارجی
PYTHONIOENCODING=utf-8 python dev/test_adjustment_engine_v1.py    # 44 سبز / 0 قرمز

# بیس‌لاینِ دیتابیس ازِ ریلیز (قراردادِ docs/MARKET_DATA_RELEASE.md)
curl -sL -o market.db.lzma https://github.com/johnwarchief/BorsTerminal/releases/download/data-latest/market.db.lzma
sha256sum market.db.lzma        # باید = e7df91dc0af257715494fbf31d64047ab4043d4b9d165e2467ca73b52d308157
PYTHONIOENCODING=utf-8 python dev/db_housekeeping.py --selftest

# سوئیتِ کامل (سرورهایِ dev باید بسته باشند)
PYTHONIOENCODING=utf-8 python dev/run_all_tests.py

# بازتولیدِ خودِ شاهد (فقط اگر کشیدنیِ کامل را دارید — نیازمندِ نشستِ مالک)
PYTHONIOENCODING=utf-8 python tools/make_adjustment_witness_fixture.py
```

## ۷) آنچه بی‌تغییر ماند

- هیچِ merge بهِ `main`، هیچِ tag/release، هیچِ حذفِ شاخه، هیچِ force‑push.
- هیچِ شاخۀِ دیگری (از جمله `mission/easytrader-adapter-*`، `handoff/system-1/*`،
  `mission/ui-audit-system-1-*`) دست نخورد؛ هیچِ کامیت/فایلِ مالِ آن‌ها درِ اینِ شاخه
  گذاشته نشد.
- `dev/fixtures/fts_v10_payloads.json` وِ `_audit/RA365-LEDGER-RULE-2026-10-12.csv` که
  درِ چک‌اوتِ اصلی علامتِ `M` دارند **بی‌تغییرِ محتوا**اند (فقطِ CRLF/LF — اثبات:
  sha256 هرِ دوِ نسخه پس ازِ `tr -d '\r'` یکی است)؛ کامیتِ بی‌محتوا نکردم وِ بازگردانی
  هم نکردم (قانونِ مخزن: باِ `git checkout --` بازنمی‌گردانیم).
- دوِ fixture بزرگ (`ra365_ref_bars.json`، `market.db.lzma`) که برایِ سنجشِ اینِ دور درِ
  worktreeها کپی شدند، ignored می‌مانند وِ پاک نمی‌شوند؛ نسخهٔ **منتشرشدنی وِ کوچک**
  کارِ همانِ تست را ازِ GitHub انجام می‌دهد.

## ۸) دوِ اثرِ بیرونِ مخزن که تعیین‌تکلیف شدند

درِ ریشۀِ اینِ چک‌اوت (`Borsterminal/_audit/`، یعنی **بیرونِ** هرِ repo) ۱۵ فایل بود:
۱۳ تصویرِ `binder1_pages/`، `MS-GATE-mstat.txt` (۱۸KB) وِ `ms_server.log` (۵۴KB).

| قلم | سنجشِ اینِ دور | تکلیف |
|---|---|---|
| `MS-GATE-mstat.txt` | لاگِ `dev/mstat_local_v975.py` ازِ یکِ اجرایِ ۲۰۲۶‑۱۰‑۱۴: **۲۰۷ بررسی، ۱ قرمز** (قاعدهٔ «روزِ ناقصِ ۲۰۲۶۱۰۰۴ ازِ ردیفِ سینک») | بازتولید شد: اجرایِ امروزِ همانِ suite رویِ `ff6b2fb` → **۲۰۵ بررسی، ۰ قرمز، rc=0**. لاگِ تاز (باِ سرِشاخۀِ کد) منتشر شد: `_audit/MS-GATE-mstat-2026-10-15.txt`. لاگِ کهنه **منتشر نشد** (شمارشِ بررسی‌ها وِ دادهٔ آنِ روز باِ کدِ امروز یکی نیست؛ شاهدِ تاریخ‌باختۀِ گمراه‌کننده می‌شد) وِ پاک هم نشد |
| `ms_server.log` | لاگِ خامِ سرویسِ devِ همانِ نشست | منتشر نمی‌شود (لاگِ اجراییِ خام؛ §۴). فایلِ اصلی دست‌نخورده درِ دیسک می‌ماند |
| `binder1_pages/p01…p13.jpg` | ۴۹۲KB، بریدۀِ سندِ Binder1؛ دوِ سندِ tracked ارجاعشان می‌دهند وِ درِ مخزن نبودند | **ACTION REQUIRED (مالک)** — §۵‑۲؛ درِ مخزنِ public منتشر نشد |

