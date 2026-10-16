# پرامپتِ دست‌به‌نفرود — کپی‌پیست در نشستِ تازه

> **پرامپت قدیمی برای workspace/نسخهٔ پیشین:** این سند مسیرهای محلی، نسخهٔ v1.0.43/v1.0.44 و ابزارهای Jev را فرض می‌کند؛ آن‌ها را به‌عنوان تنظیمات فعلی Qoder فرض نکنید. قبل از استفاده، محیط واقعی و branch فعلی را بررسی کنید. مرجع فعلی مستندات: docs/README.md.

تو مهندسِ ارشدِ همین پروژه هستی. این نشستِ تازه است؛ از صفر شروع کن. اول `AGENTS.md`/
`QODER.md` و `docs/PLAN-remaining.md` را بخوان، بعد کارها را به همین ترتیب تا ته ببر.

## محیط و مسیرها
- ریشۀ پروژه (workspace): `C:\Users\PCMOD\.openclaw-autoclaw\workspace\projects\BorsTerminal_Work`
- صفحۀ Shell Git Bash است؛ مسیرِ ویندوز را با `/c/Users/PCMOD/...` بده.
- برنامۀ نصب‌شده (همان exe که پورت ۸۰۰۱ را نگه می‌دارد):
  `C:\Users\PCMOD\AppData\Local\Programs\BorsTerminal Ultimate`
- سرورِ dev (کدِ جاری): `PYTHONIOENCODING=utf-8 py -3.14 -m uvicorn app:app --host 127.0.0.1 --port 8002`
- نسخۀ فعلی: ۱٫۰٫۴۳ منتشرشده. تگِ `v1.0.44` زده‌شده ولی **منتشرنشده** (CI قرمز شد).
- ریموت‌ها: `github` = `johnwarchief/BorsTerminal-src` (منبع؛ pushِ تگ → `release.yml`).
  توزیع = `johnwarchief/BorsTerminal`. `origin` یک آینهٔ محلیِ کهنه است؛ نادیده بگیر.

## ابزارهایِ الزامی (هر واحدِ کار با «هر دو jev» بسته شود)
- داور: `PYTHONIOENCODING=utf-8 py -3.14 tools/pilot_ctl.py arbitrate --context "…" --option "a=…" --option "b=…"`
  (فقط نثر؛ `TYPESAFE_API_KEY` در env؛ هیچ کدِ منبعی ارسال نشود).
- مرورگرِ زنده: `JEV_CHROME="C:/Users/PCMOD/AppData/Local/ms-playwright/chromium-1234/chrome-win64/chrome.exe" MSYS_NO_PATHCONV=1 node --experimental-strip-types tools/jev_ui_check.mts --url http://127.0.0.1:8002/ --route '#/market' --widths 1920 --out _audit/x.json --wait 3500`
  (هش-router: `#/market`، `#/technical/<نماد>`، `#/fundamental/<نماد>`، `#/strategy-tree`).
- گاردها: `dev/version_anchor_guard.py`، `dev/tape_filters_v1034.py`، `dev/run_all_tests.py`
  (پیش از run_all_tests سرورهایِ dev را بکِش؛ CI بانک ندارد ⇒ بخشِ داده SKIP).
- بیلد/ریلیز: `frontend/ npm run build` و `npx vitest run`؛ `scripts/build_all.py`؛
  اثباتِ دلتا روی نصب‌شده: `py -3.14 tools/inapp_update.py --apply`.

## کارها (به همین ترتیب)
۰) **رفعِ بلاکِ ریلیز v1.0.44** — چهار تستِ `frontend/src/__tests__/technical-fts-overlays.spec.tsx`
   می‌شکنند چون #219 لایۀ «تحلیل FTS» را پیش‌فرض خاموش کرد (`isFtsActive=false` در
   `KLineChartWrapper.tsx`). تست را طوری اصلاح کن که اورلی را **صریح روشن** کند (پیش‌فرضِ
   محصول را برنگردان). بعد `npx vitest run` کامل سبز ⇒ `git tag -f v1.0.44 && git push -f github v1.0.44`
   ⇒ تا سبزشدنِ CI و انتشارِ واقعی ⇒ دلتای ۱٫۰٫۴۳→۱٫۰٫۴۴ را روی نصب‌شده اثبات کن.

۱) **باگِ تازهنشدنِ اعدادِ تابلو** (اولویتِ بالا؛ مالک می‌بیند سایت هر ۱ ثانیه تکان
   می‌خورد، برنامه نه). شاهد: لاگِ نصب‌شده `GET /api/market` مکرراً `304 Not Modified`.
   علتِ کشِ بک‌اند (TTL/ETagِ `/api/market` و دورۀ واقعیِ گرفتنِ داده از TSETMC/`board refresh
   loop`) را پیدا و درست کن تا اعدادِ آخرین/حجم/تغییر٪ واقعاً ثانیه‌به‌ثانیه/۵-ثانیه تازه
   شوند. با jev-browser قبل/بعد اثبات کن. (ریشۀ #120/#197/#198)

۲) **دروازۀ «گردشِ پولِ امروز» در «ورود به بازار»** — `mstat_engine.py`: `value_hemat` از
   `eq` (گردشِ سهام) و `trade_value_all_market_hemat` از `allmkt` (کلِ بازار). جزوۀ ص۳:
   «ارزش معاملات بازار سهام > ۲۰ همت». اول از مالک بپرس آستانه روی «سهام» است یا «کل
   بازار» (جدولِ RTL)؛ بعد یا فقط برچسب را اصلاح کن یا مبنایِ دروازه را عوض کن.

۳) **#226 تنظیماتِ فرمول** — فقط فرانت (مالک روشن کرد: فقط چیزی که داخلِ جدول فیلتر/نمایش
   می‌شود، بک‌اند دست‌نخورده). دو دستگیره به `TapeFilterConfig` + `TapeFilterSettingsModal`
   که فقط `evaluateDynamicQuickFilter`/`volumeGate` را تغییر دهد: (الف) «امروز داخلِ مبنایِ
   میانگین»، (ب) «دروازۀ ۲۹-نشستِ تاریخچه». پیش‌فرض = رفتارِ فعلی.

۴) **#223** سه گرهٔ مشکوک را با مالک تکلیف کن (در جزوه نیستند): «شاخص ۵: سود انباشته و
   DPS»، «ذخیرۀ سود ۵۰٪ در R1»، «ریسک به ریوارد R/R>۲». بقیۀ لاتین (CHoCH/RSI/MA/EPS/ETF/
   SELECTION) خودِ جزوه‌اند؛ نگه‌دار.

۵) **#225/#224** — هستۀ «انتخابِ خودکار» از قبل هست: `features/master/ui/EliteFunnelHub.tsx`
   (وتوی هفتگی/REJECT ⇒ روندِ هفتگی صعودی ⇒ ستاپِ FTS). آن را به تبِ «درخت استراتژی FTS»
   منتقل/وصل کن با دادهٔ `/api/screener` (هر چهار فازِ بنیادی+تکنیکال یک‌جا در `FtsScreenRow`).

۶) **#222** — وقتی نمادی انتخاب می‌شود، وضعیتِ هر چهار فاز + سطوحِ ورود/خروج روی همان نقشۀ
   چهارچارتیِ `ObsidianStrategyGraph` نشان داده شود.

## قیدهایِ همیشگی
قانونِ اول: بدونِ کوچک‌ترین باگ/ارور/کرش؛ تا ته ادامه بده؛ سؤال‌هایِ غیرفوریتی فقط انتهای
گزارش. `numpy==2.0.2` ثابت. هر `api/*.py` تازه را به `hiddenimports` در `fts_terminal.spec`
اضافه کن. `fetch` بیرونِ `shared/api/http.ts`/`features/*/api` ممنوع (ESLint). ارقامِ فارسی
در اسکریپت را با `chr(0x06F0+d)` بساز (در Edit/Write/heredoc می‌دزدند). CRLF/LFِ هر فایل را
حفظ کن (بعضی specها خالص CRLF). برای undo از `cp` استفاده کن نه `git checkout --`. هیچ secretی
(`.setup_password.iss`، `adb_config.json`، `*.tauri_updater_key*`) وارد مخزن/لاگ نشود. force-push
ممنوع. هر گارد را با negative-control بسنج. اختلاف‌ها را در جدولِ RTL گزارش کن. هر claimِ
«درست شد» را با شاهدِ زنده (API/مرورگر) ثابت کن، نه حدس.
