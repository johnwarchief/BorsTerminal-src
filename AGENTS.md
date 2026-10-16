# AGENTS.md — نقطۀ شروعِ هر ایجنت روی BorsTerminal

این فایل نقطۀ شروعِ هر ایجنت است: ساختار، فرمان‌ها، نام‌گذاریِ بیلد/ریلیز و قیدهایِ شکست‌پذیر.
اگر روی ماشینِ تازه‌ای clone کردید، **همین فایل + پوشۀ `skills/`** باید برای کار کافی باشد؛
چیزِ دیگری از حافظۀ ماشینِ من لازم نباشد. (استثنائات در بندِ «چی در گیت نیست».)

**پیش از استفاده از دستورهای مستندات، `docs/README.md` را هم بخوانید.** آن فایل تقدم منابع FTS را روشن می‌کند و اسناد handoff/roadmap تاریخ‌دار را از وضعیت جاری جدا می‌کند. `docs/AGENT-INDEX.md` نقشهٔ کدِ تولیدشده است؛ آن را دستی ویرایش نکنید.

## ساختارِ ریپو

| مسیر | چیست |
| --- | --- |
| `app.py`, `bors_entry.py`, `bors_config.py` | بک‌اند FastAPI + لانچرِ دسکتاپ + ثابت‌ها (از جمله `APP_VERSION`) |
| `api/*.py` | اندپوینت‌ها (`market`, `chart`, `screener`, `update`, `_sync_codal`, …) |
| `tape_flags.py`, `mstat_engine.py`, `fts_engine.py`, `codal_fetcher.py` | موتورهایِ پرچم/نبض بازار/قیف FTS/واکشی کدال |
| `price_basis.py`, `candle_contract.py`, `codal_periods.py` | قراردادِ frozen: تنها resolverِ مبنایِ قیمت (last/closing)، تنها سازندۀ هندسۀ کندل، و تنها تعریفِ «دورۀ گزارش» (`YYYY/MM/DD`، قاعدۀ «بی‌دوره»، زنجیرۀ datasource ← عنوان، و `undated_counts()` به‌عنوان یگانه شمارش). هر سه درِ `fts_terminal.spec` → `hiddenimports` فهرست شده‌اند |
| `frontend/src/` | React + Vite + TanStack Query + zustand، چیدمانِ Feature-Sliced (`app/ features/ widgets/ shared/`) |
| `dev/` | گاردها و ابزارهایِ توسعه (`run_all_tests.py`, `version_anchor_guard.py`, `data_age_release_guard.py`, …) |
| `tools/` | سنجش‌هایِ زنده (pilot/jev، parity، probeها) — خروجی‌شان در `_audit/` |
| `scripts/` | زنجیرۀ بیلد و انتشار (`build_all.py`, `check_release_db.py`, `make_patch.py`, `publish_github_release.py`) |
| `installer/` | Inno Setup (`bors_setup.iss`) و خروجیِ نصاب در `installer/out/` |
| `docs/` | جزوۀ روش‌شناسی FTS (`docs/fts-notes/`)، SPECها، `PLAN-remaining.md`، `RELEASE_NOTES.md`، و نقشۀ کدِ هر ایجنت (`docs/AGENT-INDEX.md` — با `python tools/build_agent_index.py` بازتولید می‌شود) |
| `skills/` | ده اسکیلِ قراردادِ کار — جدولِ زمان‌بندی‌شان در `skills/README.md` |

## فرمان‌ها

```bash
# فرانت (از frontend/)
npm ci                          # npm v12 + Node 22.22.0 ناسازگار است؛ قفلِ نسخه را نگه دارید
npm install-scripts approve esbuild   # esbuild@0.21.5 زیر allowScripts مسدود می‌شود
npm run dev                     # vite روی 5173، /api را به 127.0.0.1:8001 پروکسی می‌کند
npm run build                   # vite build → frontend/dist (همین را PyInstaller بردار می‌کند)
npx tsc -b                      # تایپ‌چک؛ باید صفر خطا باشد
npx vitest run                  # ۱۱۰ پروندۀ تستِ فرانت

# بک‌اند
python app.py                   # dev سرور روی 127.0.0.1:8000 (بستۀ onedir با scripts/build_all.py ساخته می‌شود)
python -m uvicorn app:app --port 8002   # نسخۀ دوم برای سنجشِ «نصبی در برابر dev»

# کل گیت‌ها (سرورهایِ dev باید بسته باشند)
python dev/run_all_tests.py
python dev/version_anchor_guard.py      # باید «VERSION ANCHOR GUARD OK» بدهد
```

اپِ نصب‌شده بک‌اندش روی `127.0.0.1:8001` است و `vite` همین‌جا را پروکسی می‌کند؛ پس برای
دیدنِ کدِ رابطِ تازه یا `npm run dev` را بالا بیاورید (بک‌اندِ نصبیِ ۸۰۰۱ را نگه دارید،
چون `market.db` اینجاست) یا نسخۀ تازه را بسازید و نصب کنید.

## نام‌گذاریِ بیلد و ریلیز (همان چیزی که CI انتظار دارد)

- شش لنگرِ نسخه باید یکی باشند: `bors_config.APP_VERSION`, `frontend/package.json`,
  `frontend/package-lock.json` (`version` و `packages[""].version`),
  `frontend/src-tauri/tauri.conf.json`, `installer/bors_setup.iss` (`#define AppVersion`).
  بعد از هر bump `python dev/version_anchor_guard.py` را اجرا کنید.
- تگ: `vX.Y.Z` (نقطه‌چین، بدونِ `release/`). بیلد روی تگ در `johnwarchief/BorsTerminal-src`
  (remote `github`) می‌دود و خروجی‌ها را در `johnwarchief/BorsTerminal` منتشر می‌کند.
- نامِ خروجی‌ها: پوشۀ `dist/BorsTerminal_Ultimate/` (onedir)، `market.db.lzma` **کنارِ EXE**،
  `BorsTerminal_Manifest_v<tag>.json` (relpath → sha256، مبنایِ پچِ دلتا)،
  `codal.db.lzma` + `.sig` باید روی **تازۀترین** ریلیز باشند وگرنه دکمۀ «بروزرسانی دیتابیس کدال» ۴۰۴ می‌دهد.
- نصاب: `installer/out/`؛ آپدیتِ درون‌اپ از
  `https://github.com/johnwarchief/BorsTerminal/releases/latest/download/latest.json` می‌خواند.
- زنجیرۀ کامل، مرحله‌به‌مرحله و جدولِ «این علامت یعنی چه»: `skills/bors-build-release/SKILL.md`.

## راستی‌آزمایی مرورگر و وضعیت مهاجرت Jev → Laya

> **تصمیم مالک در 2026-10-10:** مسیر تصمیم‌گیری و ابزارهای Jev باید تا حد امکان با Laya جایگزین شوند. این مهاجرت در مخزن هنوز اثبات‌شده نیست؛ تا زمان آزمون موفق، ادعا نکنید Laya جایگزین کامل شده است. دستورهای زیرِ Jev تاریخی/سازگاری‌اند و نباید به‌صورت الزام دائمیِ همهٔ کارها تفسیر شوند.

- بعد از تغییر UI، آزمون زندهٔ مرورگر همچنان لازم است؛ سبز بودن jsdom یا Vitest به‌تنهایی اثبات UI واقعی نیست.
- اگر Laya روی ماشین نصب و پیکربندی شده است، ابتدا endpoint/MCP واقعی آن را بررسی و تصمیم ساختاریافته و اقدام مرورگر را end-to-end آزمایش کنید.
- اگر Laya هنوز آماده نیست، از Playwright/CDP و probeهای زندهٔ موجود برای راستی‌آزمایی استفاده کنید و وضعیت مهاجرت را صادقانه `UNVERIFIED` بنویسید؛ اجرای Jev فقط fallback مقایسه‌ای است، نه مدرکِ مهاجرت.
- متغیرهای `JEV_BROWSER_DIR`، `JEV_CHROME`، `tools/pilot_ctl.py` و `tools/jev_ui_check.mts` را تا وقتی جایگزین آزمایش و تأیید نشده حذف یا rename نکنید.

راهنماهای میراثی: `skills/bors-dual-jev-verification/`, `skills/bors-jev-verification/`, `skills/bors-live-ui-check/`,
`skills/canvas-chart-live-pixel-check/`, `skills/bors-installed-vs-dev-diagnosis/`.

## قیدهایِ شکست‌پذیر (اگر نشکنند، کار تمام است)

- `numpy==2.0.2` پین‌شده است (۲٫۱+ روی CPUهایِ قدیمی baseline x86-v2 می‌خواهد و کرش می‌کند).
- هر `api/*.py` تازه باید به `hiddenimports` در `fts_terminal.spec` اضافه شود؛ وگرنه EXE در اولین درخواست `ModuleNotFoundError` می‌دهد.
- `fetch` بیرونِ `shared/api/http.ts` ممنوع.
- ارقامِ فارسی در اسکریپت‌ها با `chr(0x06F0+d)` / `toFaDigits` — ویرایشِ مستقیمِ رقم در متن، رقم را می‌دزدد. بعد از هر ویرایشِ فارسی، خط‌هایِ دست‌خورده را دوباره بخوانید. گاردِ machines: `python dev/persian_glyph_guard.py` (درِ `run_all_tests.py` ثبت شده) سه خانۀ خطا را می‌گیرد — نویسهٔ CJK/هنگول وسطِ واژۀ فارسی، رقمِ شمارۀ بخشِ خورده‌شده (`# ── ) …`)، و ك/ي عربی درِ فایل‌هایِ سرخطی؛ `--selftest` ثابت می‌کند سنسورها کور نیستند. `_audit/cjk_scan.py` نسخهٔ دستیِ همین است.
- CRLF/LFِ هر فایل حفظ شود؛ روی ویندوزِ انگلیسی `PYTHONIOENCODING=utf-8` برایِ stdoutِ فارسی.
- با `git checkout --` بازنمی‌گردانیم (سابقاً fixِ واقعی را هم نابود کرد)؛ از copy برگردانید.
- هیچ داده‌ای از خودِ برنامه/ماشینِ کاربر بیرون نمی‌رود؛ هیچ کنترلِ واقعیِ دستگاه (adb، شبکه) برایِ تستِ یک گارد اجرا نمی‌شود؛ کشتنِ فرآیند فقط PIDی که خودتان بالا آورده‌اید.
- اختلاف‌ها به‌صورت جدولِ RTLِ فارسی گزارش می‌شوند؛ سؤال‌هایِ غیرفوریاتی آخرِ کار؛ چیزی که راستی‌آزمایی نشده را صریح «راستی‌آزمایی نشده» بنویسید.
- متنِ رابط: کوتاه، و واژگانِ جزوه برایِ چیزهایی که جزوه برایشان نام آورده است؛ برایِ چیزهایی که جزوه نمی‌گوید، زبانِ روشنِ خودِ برنامه. استعاره در متنِ دیدنی نگذارید.

## چی در گیت نیست (و از کجا می‌آید)

| چیز | کجا / چطور |
| --- | --- |
| `installer/.setup_password.iss` | gitignored؛ روی ماشینِ بیلد بسازید. نبودش آپدیت را از `/VERYSILENT` به `/SILENT` می‌اندازد (یک بار از کاربر رمز می‌خواهد) |
| `*.tauri_updater_key*` (کلیدِ خصوصیِ امضا) | gitignored؛ فقط pubkey در `tauri.conf.json` و `api/update.UPDATE_PUBKEY` کامیت می‌شود |
| `adb_config.json`, `codal_control.json`, `market.db`, `codal.db` | gitignored؛ `market.db` از `market.db.lzma` بازسازی می‌شود (`ensure_market_db()` در `bors_config.py`) |
| `RELEASE_TOKEN` برایِ انتشار روی مخزنِ توزیع | secretِ CI، نه فایلِ ریپو |
| **Legacy Jev only:** `TYPESAFE_API_KEY` و `~/.jev_pilot/config.json` | فقط برای اجرای fallback قدیمیِ `tools/pilot_ctl.py`؛ پیش‌نیاز عمومی Qoder یا Laya نیست |
| **Legacy Jev only:** `JEV_BROWSER_DIR` / `JEV_CHROME` | فقط مسیرهای harness قدیمی؛ برای Laya/Playwright عمومی لازم نیستند مگر همان harness اجرا شود |

## ایجنتِ داده/بک‌اند (codal) — رابطِ ابزارها

> بخشِ زیر دستورِ کارِ ایجنتِ واکشیِ کدال است (قبلاً کلِ این فایل بود). مسیرِ
> `C:\Users\Johnkallnaya\Desktop\BorsTerminal_Ultimate_Base` که در نسخۀ پیشینِ این فایل آمده بود،
> ریپویِ رویِ ماشینِ دیگری است؛ ریشهٔ کارِ شما همین clone است.

**مأموریت:** تازه‌سازیِ دادهٔ خامِ **فقط ۵ شاخص FTS** از کدال، با کمترین نرخِ درخواست (ضد ۴۲۹/بن)، و نگه‌داشتنِ جدول‌های `monthly_sales` / `financial_statements` تازه.

**ابزارها (موجود در ریپو — از نو نساز):**
- `dev/codal_fts_updater.py` — مودها: `--mode monthly|full|local`، `--verify`، `--resume` (از `dev/fts_update_state.json`).
  چرخشِ IP: `--adb-rotate` (روی ۴۲۹/بلاک: Wi-Fi ویندوز موقتاً خاموش، سه متد adb، پایشِ IP هر ۳s تا ۹۰s، **فقط با دیدنِ IP تازه** موفق می‌شود)، `--adb-long`، و راستی‌آزماییِ مستقلِ `--rotate-test` (بدونِ درخواست به کدال).
- `dev/fts_refresh_plan.py` — الگوریتمِ افزایشی: فقط دِلتا را مشخص می‌کند (NEW/NEED_ANNUAL/STALE_MONTHLY/STALE_ANNUAL) + فرمانِ آماده.
- `codal_fetcher.py` — موتورِ HTTP/اسکرپ (`rotate_ip_via_adb`، `fetch_page` با backoffِ ۴۲۹).
  اهرم‌هایِ execution: `--feed update --catchup N` (جبرانِ مشتق‌هایِ عقب‌مانده از خودِ `codal_notices`، بی‌درخواستِ search)، `--extract-workers N` (اندازۀ استخرِ اسکرپِ این مسیر؛ پیش‌فرض ۴، سقف ۱۶، با `--polite` همیشه ۱). سقفِ سرعت پهنای‌باند است نه کارگر: ۴ کارگر ~۱٫۰ گزارش/ثانیه، ۱۰ کارگر ~۲٫۸، ۱۲ کارگر ~۳٫۳ — صفحه‌های `codal.ir/Reports` ۵۵ تا ۹۵۵ کیلوبایت **بی‌فشرده‌سازی**‌اند (`Content-Encoding: none`).

**رویهٔ کار (اجباری):**
۱) `python dev/fts_refresh_plan.py --out plan.json` → کارنامۀ دِلتا.
۲) فقط نمادهای `monthly` را با `--mode monthly` و `full`ها را با `--mode full` (و `--adb-rotate`) واکشی کن؛ دسته‌ای/limit‌دار.
۳) روی ۴۲۹/بن: چرخشِ IP، **تأییدِ تغییرِ IP**، سپس ادامه از همان نقطۀ توقف (`--resume`).
۴) در پایان `--verify` و گزارشِ کوتاه: چند نماد/چند ردیف، وضعیتِ IP، و هر گپ.

**قواعد:** فقط ۵ شاخص؛ هیچ اطلاعیهٔ دیگری واکشی نشود. بدونِ دادهٔ ساختگی؛ غایب ⇒ «بدون داده» (مرجعِ اعتبار: `docs/FTS_SYSTEM_SPECIFICATION_v2.md`). شبکه/چرخشِ IP فقط با adbِ گوشیِ متصل؛ اگر گوشی نبود صریح گزارش بده و توقف کن. فایلِ موقتِ untracked نماند؛ کامیت/مرج نکن.
