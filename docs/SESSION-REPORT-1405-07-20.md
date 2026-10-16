# گزارشِ دورِ ۱۴۰۵-۰۷-۲۰ — یکپارچه‌سازی، انتشارِ v1.0.82 و به‌روزرسانیِ دلتا رویِ برنامهٔ نصبی

**نتیجهٔ کلی: منتشر شد و مسیرِ به‌روزرسانی با شواهد تأیید شد.** نسخهٔ **v1.0.82** از
مسیرِ استانداردِ پروژه (تگ → `release.yml` → `release-inno`) ساخته و در
`johnwarchief/BorsTerminal` منتشر شد؛ سه پچِ دلتا تولید شد؛ و رویِ همین ماشین،
برنامۀ نصبی از **۱٫۰٫۸۰ با همان پچِ دلتا به ۱٫۰٫۸۲ ارتقا یافت** (بدونِ نصابِ کامل،
بدونِ دست‌زدن به دادۀ کاربر). تنها چیزی که همچنان باز است **اثباتِ چرخۀ زندۀ بازار**
است که عمداً «UNVERIFIED» نگه داشته شده.

## مشخصاتِ انتشار (بخشِ E)

| | |
| --- | --- |
| نسخۀ پایهٔ سورس | `github/main` @ `24320a9` (شاملِ PR#2/#3/#4/#5) |
| یکپارچه‌سازی | برانشِ `integration/desktop-review-2026-10-11` (mergeِ `fix/fts-p0-2-gates-flip` = ۳۷ کامیت) → **PR #6** → merge با کامیت `dc99210` |
| کامیتِ bump | `8191246` «release: v1.0.82» (شش لنگر + RELEASE_NOTES) |
| کامیتِ نهاییِ سورس | **`48e1042`** — همان چیزی که درِ `Version.txt`ِ برنامهٔ نصبی ثبت شده (`git_commit=48e1042`) |
| تگ | `v1.0.82` (اول `8191246` → بعد ازِ رفعِ تستِ شکست‌خورده به `48e1042` منتقل شد؛ ریلیزی بینِ آن دو منتشر نشده بود) |
| رانِ موفق | run `38051171857` — `Build & Release Inno Installer (PyInstaller)` = **success**، همهٔ ۱۶ گام |
| لینک ریلیز | https://github.com/johnwarchief/BorsTerminal/releases/tag/v1.0.82 |
| نصب‌کننده | https://github.com/johnwarchief/BorsTerminal/releases/download/v1.0.82/BorsTerminal_Ultimate_Setup_v1.0.82.exe — ۴۰٬۴۹۸٬۳۹۱ بایت، sha256 `6f44a0c6654784a97340911d667f15bb6e38be3cfe6a565bbd7643a44cc17f48`، امضای minisign با `api/update.UPDATE_PUBKEY` **بررسی و درست** |
| manifest | `BorsTerminal_Manifest_v1.0.82.json` (۱۷۱٬۵۱۱ بایت، ۱۵۰۹ فایل) |
| `latest.json` | `releases/latest/download/latest.json` ⇒ `version: 1.0.82`، `platforms.windows-x86_64.url` به نصابِ ۱٫۰٫۸۲، `patches` با سه ورودیِ ۱٫۰٫۷۹/۸۰/۸۱ → ۱٫۰٫۸۲ (هرکدام `url` + `signature` ۴۳۲ بایتی + `size`)، `notes` = بخشِ v1.0.82 از `docs/RELEASE_NOTES.md` |
| تاریخ build | `built=2026-10-10 12:19` (UTC) درِ `Version.txt` |

## پچ دلتا — تولید و راستی‌آزمایی

annotationهای workflow (چون لاگِ رانر از این شبکه باز نمی‌شود و گام‌ها
`continue-on-error` دارند، همین‌ها تنها شاهدِ معتبرند):

```
[patch] مبدأهایِ پچ: v1.0.81 v1.0.80 v1.0.79 -> v1.0.82
[patch] make_patch(1.0.81) exit=0 … changed=34 unchanged=1478 skipped_user_state=0 size=15.0 MB
[patch] make_patch(1.0.80) exit=0 … changed=34 unchanged=1478 …
[patch] make_patch(1.0.79) exit=0 … changed=47 unchanged=1465 … size=17.2 MB
[manifest] dist/BorsTerminal_Manifest_v1.0.82.json = 171511 بایت
[data-age] BASELINE_MISSING market.db.lzma not in this tree      ← از دورۀ جداشدنِ دیتا از گیت، طبیعی
```

- `BorsTerminal_Patch_1.0.80_to_1.0.82.zip` = ۱۵٬۷۵۶٬۴۷۳ بایت،
  sha256 `b00979b29369483ac40ce28916621f2781c476a78fcbb38f57a5c65b9ab7fe8a`،
  امضا با کلیدِ خودِ آپدیتر **درست**. ۳۴ ورودی دارد و فقط فایل‌های تغییریافته را
  می‌برد (نمونهٔ داخلِ پچ: `_internal/api/market.py`،
  `_internal/frontend/dist/assets/MarketPage-*.js`) — یعنی واقعاً دلتاست، نه نصابِ کوچک‌شده.
- `BorsTerminal_Patch_1.0.81_to_1.0.82.zip` = همان اندازه، sha256
  `7fd34a137d96ba4f13e9cb04c4bcc121fa46aab492dd581086c59cfee6c33d6e`، امضا درست.

### سناریویِ واقعیِ «نسخۀ قبلی ← دلتا ← نسخۀ جدید» — **PASS**

رویِ نصبِ موجود در `C:\Users\PCMOD\Desktop\v1080_verify\app`:

| گام | شهادت |
| --- | --- |
| versionِ قبل | `{"version":"1.0.80","tauri":false}` |
| `/api/update/check` | `available: true`، `latest_version: 1.0.82`، **`delta: true`**، `url = …/BorsTerminal_Patch_1.0.80_to_1.0.82.zip`، `size 15756473`، `updater: python` |
| `/api/update/download` → `progress` | `status: ready`، `downloaded = total = 15756447`→`15756473`، `version: 1.0.82` |
| وارسیِ مستقلِ فایلِ دانلودشده | sha256 فایلِ `%TEMP%\bors_update\…` **عیناً** برابرِ نسخۀِ GitHub (`b00979b2…`) و امضا با `UPDATE_PUBKEY` → `True` |
| `/api/update/install` | `{"status":"installing","delta":true,"applier":"…\apply_update.bat"}`؛ پس از ~۴۰ ثانیه پروسهٔ تازه با PID 3216 |
| versionِ بعد | `{"version":"1.0.82","tauri":false}` |
| `Version.txt` | `app_version=1.0.82 · patch_from=1.0.80 · git_commit=48e1042 · built=2026-10-10 12:19` |
| دادۀِ کاربر | `user.db` **بایت‌به‌بایت یکسان** (۲۴٬۵۷۶ / sha۱۶ `e4bd2ef1ca88cdcf`). `.screener_cache.json` عوض شده (۹۷۰٬۱۴۹→۹۷۰٬۰۸۰) چون کلیدش نسخهٔ اپ است (`#v1.0.81`) و عمداً دوباره حساب می‌شود؛ این کش است، نه دادۀِ کاربر. `market.db` رشد کرده چون برنامه بعد ازِ آپدیت دوباره سینک کرده. |
| قابلیت‌های نو درِ همین نصبِ به‌روز‌شده | `/api/live-stats` حالا `window` + `tick` (`timeout_s [4.0, 12.0]`) + `universe` دارد؛ `/api/universe/live` پیش‌تر **HTML** می‌داد، حالا `200 application/json` با ۳۷۵٬۸۹۷ بایت و شمارشِ واقعی (total ۵۸۹۹، duplicate_rows ۳، market_closed ۵۸۹۹)؛ آسهتِ `MarketPage-*.js` شاملِ `market-status-panel` است |

## A. تغییراتِ تکمیل‌شده (و وضعیتشان درِ برنامۀ دسکتاپ)

| قابلیت | مشکلِ قبلی | اصلاح | مرجع | درِ v1.0.82 |
| --- | --- | --- | --- | --- |
| تیکِ زندهٔ تابلو | درخواستِ آویزان تا ۹۰ ثانیه + retry، حلقه را بلوکه می‌کرد | `TICK_TIMEOUT_S=(4,12)` + شمارش‌هایِ چرخه درِ `tick_health()` | `7989292` | **PRESENT** (درِ بسته با probe دیده شد) |
| بارِ مزاحمِ Job پایش | ۱۲۷۲ درخواستِ CDN هر ۱۵ دقیقه، همان IPِ تیک را ۴۲۹ می‌کرد | برشِ ۱/۸ جهان، کندل از بانکِ محلی، ۱۲ نمونۀِ چرخشیِ CDN، عقب‌نشینی وقتی تیک گرسنه است، stream+flush، `run.log`، قفلِ مبتنی بر PIDِ زنده | `7989292`, `9c71357` | منطقِ Job **درِ ریپو** (نه درِ EXE) — زمان‌بند از `tools/…` اجرا می‌کند؛ `tools/fts_live_audit.py` درِ `_internal` نیست (عمداً) |
| presetها | `technical_gate` هیچ‌جا مصرف نمی‌شد ⇒ `hourglass ≡ custom[]`؛ `?chain=` نادیده؛ ترتیبِ ثابت | گیت مصرف می‌شود؛ زنجیرۀ URL؛ `orderStageRows`؛ `signal`؛ «محاسبه: HH:MM»؛ گاردِ رجیستری → گاردِ **خروجِ موتور** (۶→۱۲) | `09bd3a4`, `3e7a741`, `8d1489d` | **PRESENT** — درِ همین بانک: ساعت‌شنی ۰ عبور/۷۲ رد، سفارشی ۷۷ عبور/۳۴ تحویل |
| جهانِ معاملاتی | بی‌راننده، بی‌مصرف‌کننده، کهنگیِ هرگز‌روشن‌نشونده، ردیفِ تکراریِ جعلی | یکِ ردیاب با رانندۀ «بازسازیِ کشِ تابلو»، کهنگی از `meta.last_sync`، dedupe، `/api/universe/live` درِ `api/market.py` | `09bd3a4` | **PRESENT** (`/api/universe/live` JSON با شمارش‌ها) |
| تازگی | «لحظاتی پیش» رویِ دادۀِ یخ‌زده (سنجشِ `dataUpdatedAt`) | `rev_at` درِ فید + `dataAgeMs` درِ `computeFeedStatus` | `8d1489d` | **PRESENT با نقصِ شناخته‌شده** (بخشِ C) |
| پنلِ «وضعیت بازار» | فقط یکِ نشانِ ریز؛ اتصال/دریافت/تازگی قاطی | بخشِ مستقلِ بالایِ تابلو از `/api/live-stats` + ساعتِ مستقلِ ۱۵ ثانیه | `8d1489d`, `2a19238` | **PRESENT** (testid درِ آسهتِ served) |
| تنظیماتِ ساعت‌شنی + کشِ تحلیل | آستانه‌ها ثابت؛ با تغییرِ تنظیم، کشِ ۹۰۰ ثانیه رأیِ قدیمی می‌داد | PR#4/#5 (ساعت‌شنیِ قابل‌تنظیم) + کلیدِ کشِ یکپارچۀ `…\|hg=…\|basis` | `f96ce3d`, `24320a9`, merge `e9c1c3f` | **PRESENT** |
| باطل‌سازیِ سراسریِ آستانه | `fund-gate`/`stop-fund`/`stop-fts`/`funnel` تا ۶۰ دقیقه کهنه می‌ماندند | پنج invalidate درِ `onSuccess` | `8d1489d` + merge | **PRESENT** |
| «دیدهبانِ بازار» | نایافزوده | دو زیرتبِ مستقل + جدولِ زنده + کندل + دفترِ پنج‌سطحی + خلاصه؛ خرید/فروش `disabled` | `db51d95` | **PRESENT** |
| مقایسهٔ فیلترها با TSETMC | `GetInstrumentInfo?a=…` هر دوازده نماد ۴۰۴ ⇒ مقایسه هیچ‌وقت اجرا نشده بود؛ و مقایسۀِ `h*_max` با سقفِ مجاز، مقایسۀِ بی‌معنی | قالبِ مسیر‌محور؛ فقط کمیت‌هایِ هم‌نام (`allowed_min/max ⇔ psGelSta*`: ۵/۵ برابر)؛ `qTotTran5JAvg` = UNVERIFIED | `9c71357` + `docs/TAPE_FILTERS_VS_SOURCES_1405-07-18.md` | درِ Jobها (dev tool) |

## B. کجا دیده می‌شود

- **تابلو**: بالایِ صفحۀ «تابلوخووانی / بازار» → نوارِ «وضعیت بازار» (باز/بسته، اتصال،
  آخرین دادۀِ بازار، عوض‌شدنِ عدد، ویرایش + بازشونده: پنجره‌ها، حلقۀ تیک، جهانِ نمادها).
- **غربالگری FTS (درخت استراتژی)**: دکمه‌هایِ نوسان‌گیر/روندگیر/Custom حالا ردیف‌ها و
  شمارش‌ها را عوض می‌کنند؛ «محاسبه: HH:MM» درِ سرخط؛ نمادهایِ در حالِ معامله رو‌به‌رو.
- **مدیریت پرتفوی**: دو زیرتب — «پرتفوی من» و «دیدهبانِ بازار» (جدول + کندل + دفترِ
  پنج‌سطحی + خلاصه؛ کلیک رویِ نماد هر سه پنل را می‌برد).
- **تنظیمات (⚙ / دراورِ «تنظیمات پیش‌شرط‌های FTS») **: دورهٔ RSI، آستانۀ اشباع و حالتِ
  MA52؛ با ذخیره، تحلیل و دروازۀِ بنیادی و قیف فوراً تازه می‌شوند.

## C. باقی‌مانده‌ها (وضعیتِ کنونی، نه کپی‌کردنِ گزارشِ قبلی)

| مورد | وضعیت | شهادت/چرا |
| --- | --- | --- |
| اثباتِ زندۀ P0-1 درِ پنجرۀِ ۰۸:۴۵–۰۹:۱۵ | **UNVERIFIED** | بازار درِ این دور بسته بود (۱۴:۱۸–۱۶:۱۰ تهران). برنامهٔ به‌روز‌شده درِ همین حالتِ پس‌ازبستن: `cycles=16, revision=10, nochange_cycles=6, last_cycle_s=1.078` — یعنی حلقه می‌دود و می‌نویسد، ولی این جانشینِ اثباتِ نشستِ واقعی نیست. روشِ آزمون: `docs/SESSION-REPORT-1405-07-19.md` |
| نقصِ `rev_at` درِ مسیرِ «بدنۀِ کامل» | **باز / NOT IMPLEMENTED** | `marketFeed.ts:78` هنوز `return f;` (بدنۀِ سرور، بی‌`rev_at`) و فقط مسیرِ دلتا/`unchanged` (`:133,:136`) `snapshot()` را می‌دهد ⇒ اگر آخرینِ پاسخِ موفق `full` باشد پنل «نامعلوم» می‌گوید. درِ برنامۀِ نصبیِ به‌روز‌شده هم دیده شد (`عوض‌شدنِ عدد: نامعلوم` با `اتصال: رسید`). عمداً درِ این دور اصلاح نشد (دامنۀِ دور = یکپارچه‌سازی/انتشار) |
| `دتوزيع`: I1–I5 خالی با وجودِ دادۀِ API | **باز / NOT IMPLEMENTED** | درِ دورهایِ قبل با API مقابله و ثبت شد؛ درِ این دور دوباره دست‌نزده (دستورِ صریحِ شما). نامزدِ علت: منبعِ کارتِ سایدبار با `screener` فرق دارد |
| شمارشِ `TRADING_ACTIVE` با دادۀِ زنده | **UNVERIFIED** | بازار بسته ⇒ `market_closed: 5899` و `trading: 0` (درست ولی بی‌معنا برایِ اثبات) |
| واکنش‌گراییِ ۱۳۶۶px درِ دفترِ دیدهبان | **PARTIAL** | علتِ شکایت (چسبیدنِ ارقام) اصلاح و بیلدِ تازه گرفته شد؛ سنجشِ دوبارهٔ مرورگریِ *همان حالت* انجام نشد. درِ این دور شواهدِ ۱۳۶۶/۱۹۲۰ برایِ صفحۀ تابلو از بیلدِ onedir گرفته شد (`_audit/desktop-build-20261010/jev_ui_check-1366.png`) |
| jev-pilot | **UNAVAILABLE** | `tools/pilot_ctl.py arbitrate …` → `TypeSafe Jev API HTTP 451: Typesafe is not available in your region`. دروازۀِ dual-jev یک‌طرفه ماند |
| گاردِ `dev/test_roundm_freeze.py` (هفتۀ ساعت‌شنی از `closes_w`) | **باز، از قبل رویِ main** | با chک‌اوتِ خالصِ `24320a9` هم FAIL است (۵ pass/۱ fail) ⇒ کارآمدیِ تغییرِ PR#4، نه این merge. نیازمندِ رأیِ شما: بازگشت به رفتارِ منجمد یا به‌روزرسانیِ صریحِ گارد |
| انتشارِ دادۀِ بازارِ تازه (`market.db.lzma`) | **باز / جدا** | baseline درِ این دور با `check_release_db.py --pack` ساخته و round-trip شد (۵۵٫۳MB، آخرینِ نشست ۲۰۲۶۱۰۱۰) ولی `*.lzma` از گیت بیرون است (`.gitignore:147`) و انتشارش کارِ `market-data.yml` با `RELEASE_TOKEN` است. ریلزی که رفت همان دادۀِ `data-latest`ِ قبلی را bootstrap می‌کند |

## D. نتایجِ واقعیِ آزمون

| دروازه | نتیجه | تفکیک |
| --- | --- | --- |
| `dev/run_all_tests.py` رویِ `mainِ` یکپارچه | **۱۰۱ OK / ۲ FAIL** (دورِ اولِ این دور) | هر دو از قبل رویِ `main`: `test_roundm_freeze` (۵/۱ رویِ chک‌اوتِ خالصِ main) و `db_housekeeping --selftest` (فقط به‌خاطرِ نبودنِ `market.db.lzma` درِ worktreeِ تازه؛ با حضورش `[selftest] PASS`) |
| `vitest` رویِ درختِ merge (پیش ازِ رفع) | ۱۴۸۶ pass / **۲ fail** | همان دو failure رویِ `24320a9`ِ خالص هم بازتولید شد (۲ fail / ۲۲ pass درِ `fts-settings-drawer.spec.tsx`) ⇒ رگرسیونِ این دور **نیست** |
| رفعِ آن دو | `FtsSettingsDrawer.tsx` نامِ دسترسیِ کامل را پس گرفت (`48e1042`)؛ تست‌ها دست‌نخورده | `vitest run` کامل: **۱۴۸۸ pass / ۰ fail** (۱۴۷ پروندۀ سبز، ۱ skip) · `tsc -b` صفر · build موفق |
| CI (run `38051171857`) | **success**، هر ۱۶ گام از «Run Frontend Tests» تا «Publish Release» | اولین ران (`38050649759`) درِ همان گامِ تستِ فرانت شکست و **هیچ چیزی منتشر نکرد** (گام‌های ۹–۱۶ skipped) — بعد ازِ رفع، دوباره تگ زده شد |
| آزمونِ onedir محلی (بیلدِ `e9c1c3f`) | ۱۱۹٫۵MB، اپ بالا آمد، API/panel/endpoints همگی نو دیده شدند | `dist/BorsTerminal_Ultimate` + `BORS_NO_FETCH_LOOPS=1`؛ شواهد: `_audit/desktop-build-20261010/` |
| آزمونِ برنامۀِ نصبیِ به‌روز‌شده | startup و API سالم؛ `universe/live` از HTML به JSON؛ `live-stats` با `window/tick/universe` | ۱۶:۰۵ تهران، بازار بسته ⇒ **آفلاین/smoke**، نه اثباتِ چرخۀِ زنده |

## E) جدولِ نهایی

| مورد | وضعیت کد | وضعیت نسخۀ دسکتاپ | شواهد | کارِ باقی‌مانده |
| --- | --- | --- | --- | --- |
| تیکِ زنده (رفعِ بلوکه‌شدن) | DONE | DONE (timeout_s درِ بسته) | probe رویِ ۸۰۱۰ و رویِ نصبِ ۱٫۰٫۸۲ | اثباتِ زندهٔ ۰۸:۴۵–۰۹:۱۵ |
| رفعِ بارِ Job (۱۲۷۲→۱۲ درخواست) | DONE | درِ Jobها (dev tool، بیرون از EXE) | ۸ عبور = ۱۲۷۲ نماد، ۰ خطا، `run.log` | اولینِ عبورِ زمان‌بندشده درِ نشست با کدِ نو |
| presetها (گیت/ترتیب/URL/abort/as_of) | DONE | DONE | مرورگر: UI==API پنج preset؛ درِ بسته: ۰/۷۲ در برابرِ ۷۷/۳۴ | — |
| جهانِ معاملاتی (رانندۀ مشترک، dedupe، کهنگی) | DONE | DONE | `universe counts` درِ ۸۰۰۱ به‌روز‌شده (total ۵۸۹۹، dup ۳) | شمارشِ TRADING_ACTIVE زنده |
| پنلِ «وضعیت بازار» | DONE | DONE | testid درِ served asset + رندرِ واقعی | — |
| `rev_at` درِ بدنۀِ کامل | **NOT IMPLEMENTED (نقصِ ثبت‌شده)** | PARTIAL (گاهی «نامعلوم») | دو شاهدِ متناقضِ ۱۳:۱۱/۱۳:۵۵ + `marketFeed.ts:78` | یکِ دورِ اصلاحِ کوچک |
| تنظیماتِ ساعت‌شنی + کلیدِ کش | DONE | DONE | `/api/fts/config` درِ بسته؛ `hg=` درِ کلید | گاردِ `test_roundm_freeze` (رأیِ شما) |
| دیدهبانِ بازار | DONE | DONE | `PortfolioPage-*.js` + ۸ تست | بازبینیِ ۱۳۶۶px درِ مرورگر |
| دتوزيع I1–I5 | **NOT IMPLEMENTED** | نه‌تنها باز، درِ بسته هم همان است | شاهدِ API/DOM درِ `verify2` | ریشه‌یابیِ منبعِ کارت |
| ریلیز + دلتا + آپدیتر | DONE | DONE (۱٫۰٫۸۰ → ۱٫۰٫۸۲ رویِ همین ماشین) | `check delta:true` → `progress ready` → sha256 یکسان → امضای درست → `Version.txt: patch_from=1.0.80` | — |
| jev-pilot | UNAVAILABLE | UNAVAILABLE | HTTP 451 region | ازِ ماشین/حوزۀِ دیگر امتحان شود |
