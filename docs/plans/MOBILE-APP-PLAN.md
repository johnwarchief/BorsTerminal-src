# نقشهٔ راه اپ اندروید مستقل — بدون سرور، بدون PC روشن

> برنچ کار: `arena/01a0ea35-borsterminal-src` — تا تصمیم مالک، چیزی وارد `main` نمی‌شود.

## معماری (تصمیم نهایی‌شده با مالک)

```
اپ اندروید (همان React موجود + پوستهٔ Capacitor)
 ├── دادهٔ کُند (بنیادی/FTS/اسکرینر/تقویم)
 │     ← اسنپ‌شات پخته‌شده از GitHub Releases (CDN رایگان)
 │     ← پخت روی PC با TestClient خودِ app.py ⇒ برابری بایت‌به‌بایت با دسکتاپ
 ├── دادهٔ زنده (تابلو/قیمت لحظه‌ای)
 │     ← مستقیم از cdn.tsetmc.com روی خود گوشی (IP ایرانی؛ توسط مالک
 │        روی Wi-Fi و سیم‌کارت راستی‌آزمایی شد — JSON برگشت)
 └── چارت تاریخی ← price_history داخل SQLite روی خود گوشی (آفلاین)
```

چرا نه سرور؟ مالک هزینهٔ ماهانه نمی‌پردازد. چرا نه بازنویسی Rust؟ ریسک
انحراف رفتاری از ۱۹هزار خط منطق مالی گاردشده؛ ارزش افزودهٔ فوری ندارد.

## وضعیت فازها

| فاز | شرح | وضعیت |
|---|---|---|
| ۰ | تست دسترسی TSETMC از گوشی (مرورگر، Wi-Fi + سیم‌کارت) | ✅ توسط مالک — JSON دیده شد |
| ۱ | `scripts/build_mobile_snapshot.py` — پخت اسنپ‌شات موبایل | ✅ v2 روی **1.0.64** — ۴۳۸۱ بسته، gz=**22.4MB**؛ ترتیب فشرده‌سازی: اول gz (کم‌حافظه) بعد lzma |
| ۲ | پوستهٔ Capacitor (اندروید) | ✅ `frontend/android/` + `capacitor.config.ts` (CapacitorHttp فعال ⇒ بدون CORS روی گوشی)؛ اسنپ‌شات داخل asset های APK باندل می‌شود (آفلاین از جعبه) |
| ۳ | آداپتور محلی: مسیرهای `/api/*` بدون هیچ بک‌اندی از اسنپ‌شات روی دستگاه (sql.js) | ✅ + کش پارس تابلو برای پولینگ ۵ثانیه‌ای |
| ۳ب | لایهٔ زندهٔ TSETMC روی خود گوشی | ✅ `local/live.ts` — مارکت‌واچ (رونشانی قیمت/حجم/صف روی تابلو)، حقیقی/حقوقی، کندل زندهٔ امروز روی چارت، شاخص کل زنده (GetIndexB2History، همتای market_index.py). شکست شبکه ⇒ بازگشت بی‌صدا به اسنپ‌شات. **راستی‌آزمایی زنده فقط روی گوشی ممکن است** (سندباکس به TSETMC راه ندارد) |
| ۴ | ریسپانسیوسازی — گذر نخست | ✅ `shared/styles/mobile.css` با گیت کلاس `bors-mobile` (فقط بیلد موبایل): سایدبار → نوار پایین لمسی، اسکرول افقی جدول‌ها، مودال تمام‌عرض. **نیازمند بازبینی بصری مالک؛ گذرهای بعدی لازم است** |
| ۵ | ورک‌فلوی GitHub Actions | ✅ `.github/workflows/mobile.yml` (اجرای دستی): پخت اسنپ‌شات + بیلد فرانت موبایل + `gradlew assembleDebug` → artifact های APK و snapshot. امضای release keystore هنوز مانده |

## به‌روزرسانی مهم — همگام‌سازی با main جدید

مالک main را با force-push تا **1.0.64** جلو برد (تاریخچهٔ بازنویسی‌شده).
کار موبایل روی همان بازچیده شد (cherry-pick روی `origin/main`) و لنگرهای
نسخه ۶/۶ سبزند. پخت اسنپ‌شات با TestClient یعنی منطق جدید 1.0.64 (چارت/تابلو)
**خودکار** در بسته‌ها لحاظ شد — هیچ نگاشت دستی‌ای لازم نشد.

## نکته‌های فنی فاز ۳ب (نگاشت‌های مرجع)

- مارکت‌واچ: `pcl/pdv/py/pf/pmn/pmx/qtj/qtc/ztt/eps` + عمق `blDs(qmd,pmd,zmd,qmo,pmo,zmo)`
  — عیناً همان فیلدهایی که `test_tsetmc.py` می‌خواند؛ جمع ۵ خط + خط اول همتای `queue_agg`.
- `ins_code` کلید اتصال ردیف تابلو ↔ مارکت‌واچ زنده است؛ فیلدهای مشتق سنگین
  (vol_ratio، buyer_power، …) از اسنپ‌شات می‌مانند (محاسبهٔ PC).
- شاخص کل: `GetIndexB2History/32097828799138957` با همان نگاشت
  `xNivInuClMresIbs/Ph/Pb` و قاعدهٔ «open = close روز قبل» از `build_tedpix_payload`.
- سبد: وزن‌دهی ارزشی (قیمت پایانی تابلو × تعداد ÷ ۱۰ = تومان) با همان
  سلسله‌مراتب دسکتاپ: value → manual → equal.

## مانده برای جلسه‌های بعد

۱. نصب APK (artifact ورک‌فلوی `mobile-apk` — حالا با هر push روی `arena/**`
   خودکار می‌سازد) روی گوشی مالک → راستی‌آزمایی زندهٔ TSETMC + بازبینی بصری
   ریسپانسیو (گذر دوم بر اساس اسکرین‌شات).
۲. تعریف سکرت‌های keystore برای امضای release (زیرساختش در ورک‌فلو هست —
   `ANDROID_KEYSTORE_B64/…`؛ بدون سکرت، APK دیباگِ قابل‌نصب ساخته می‌شود).
۳. ~~آپلود اسنپ‌شات کنار ریلیزها~~ ✅ خودکار شد: CI با هر بیلد، APK +
   `mobile_snapshot.db.gz` + meta را در ریلیزِ غلتان **mobile-latest**
   (pre-release؛ «Latest» رسمی دسکتاپ دست‌نخورده) منتشر می‌کند و بروزرسانی
   خودکار دادهٔ اپ (`localData.ts`) از همین تگ می‌خواند.

### انجام شد (این جلسه)

- ✅ adjustEvents زندهٔ چارت روی گوشی: `liveChart` در `live.ts` — CSV رسمی
  `GetClosingPriceDailyListCSV` + همان الگوریتم `api/chart.py` (پارس هدرمحور
  v9.7، ترمیم هندسه، LAST-CLAMP، درِ لنگر ANCHOR_MIN=۰٫۹، آستانهٔ ADJ_TOL=۰٫۰۰۱،
  factorهای back-adjust) + کندل زندهٔ امروز از مارکت‌واچ؛ آفلاین ⇒ پختِ محلی.
  تست: `src/__tests__/local-live-chart.spec.ts` (۷ تست).
- ✅ بروزرسانی خودکار داده از GitHub Releases (بدون سرور): بیکر
  `mobile_snapshot.db.meta.json` می‌سازد؛ اپ روزی یک‌بار آن را چک و gz جدیدتر
  را در Cache API می‌گذارد — از اجرای بعدی فعال است.
- ✅ ورک‌فلوی `mobile-apk`: تریگر push روی `arena/**` + آپلود meta + بیلد
  release امضاشدهٔ اختیاری با سکرت‌های keystore.

## فاز ۳ — آداپتور محلی (نسخهٔ ۱، انجام شد)

- `frontend/src/shared/api/local/` (جدید):
  - `localData.ts` — دانلود اسنپ‌شات (`VITE_SNAPSHOT_URL`، پیش‌فرض `/mobile_snapshot.db.gz`)،
    کش با Cache API، گشودن با DecompressionStream بومی (+گارد بایت جادویی gzip)،
    sql.js (WASM) و سرویس‌های `baked()/query()/metaValue()`.
  - `resolvers.ts` — نگاشت کامل ~۲۵ مسیر `/api/*` مصرفی React:
    بنیادی/FTS/اسکرینر/نبض/تقویم از baked · چارت/تاریخچه با SQL روی
    `price_history` (همتای فیلتر/dedupe بک‌اند + نرمال‌سازی ك/ي) ·
    سبد/تصمیم روی localStorage (`selectionLocal.ts`) · جستجوی نماد با SQL ·
    عملیات دسکتاپی (update/sync) → `unsupported`.
  - نقطهٔ تعویض: گیت `import.meta.env.VITE_LOCAL_DATA === '1'` بالای `http()` با
    ایمپورت داینامیک — در بیلد دسکتاپ کل شاخه tree-shake می‌شود؛ +همان گیت در
    تنها fetch مستقیم مجاز (`useSymbolBasket.ts` برای DELETE).
- بیلد موبایل: `VITE_LOCAL_DATA=1 npm run build` + کپی `mobile_snapshot.db.gz` در `dist/`
- پیش‌نمایش: `python tools/serve_mobile_preview.py 8090` (ایستا، SPA fallback، **بدون هیچ بک‌اندی**)
- راستی‌آزمایی: تست دود Node روی اسنپ‌شات واقعی (کلیدها/SQL چارت/جستجو سبز) +
  ۱۱۷۵ تست vitest دسکتاپ سبز. رندر مرورگری هنوز فقط با پیش‌نمایش قابل تأیید است
  (سندباکس chromium ندارد) — **راستی‌آزمایی بصری با مالک**.
- نکته‌های شناخته‌شده:
  - `index/tedpix` در پخت سندباکس ۵۰۲ شد (منبعش TSETMC زنده است؛ روی PC مالک پخته می‌شود).
  - `adjustEvents` چارت در اسنپ‌شات نیست (منبع: CDN زنده) — فاز ۳ب روی گوشی پُرش می‌کند.
  - intraday در حالت آفلاین `no_data` است (ذاتاً زنده).
  - وزن‌دهی سبد نسخهٔ سادهٔ محلی است (وزن دستی؛ بدون قیمت×تعداد از تابلو).

## فاز ۱ — اسنپ‌شات موبایل (انجام شد)

- اسکریپت: `scripts/build_mobile_snapshot.py` · خروجی در `dist_mobile/` (gitignored)
- روش: TestClient روی `app.py` با `base_url=127.0.0.1` (گارد لوپ‌بک) —
  **هیچ منطقی بازنویسی نشده**؛ خروجی همان پاسخ‌های دسکتاپ است.
- ساختار خروجی `mobile_snapshot.db`:
  - `baked(key, json, fetched_at)` — کلیدها: `screener`، `fts`، `fts_config`،
    `market_board`، `sectors`، `mstat/*`، `calendar`، `fundamental/<نماد>`، `quarters/<نماد>`
  - جدول‌های خام: `instruments`, `market_watch`, `price_history` (+ ایندکس symbol,date),
    `boards`, `market_index`, `market_totals`, `market_liquidity`, `mstat_snap`
  - `meta`: نسخه (از لنگر `bors_config.APP_VERSION`)، زمان پخت، شمار موفق/ناموفق
- جدول‌های خام کدال عمداً حذف شدند (خروجی پخته‌شان در baked هست) → سبک‌سازی.
- یک 404 شناخته‌شده: `معيار` در اسکرینر هست ولی کارت بنیادی ندارد (skip لاگ می‌شود).

## تصمیم‌های فاز ۲/۳ (برای اجرا)

- پوسته: **Capacitor** (نه Tauri — به خواست مالک) + `@capacitor-community/sqlite`
  + `CapacitorHttp` (دور زدن CORS برای cdn.tsetmc.com).
- نقطهٔ تعویض داده: قانون موجود ریپو «fetch فقط در `shared/api/http.ts`» یعنی
  دقیقاً یک فایل برای سوئیچ به آداپتور محلی؛ گیت با `import.meta.env` تا
  بیلد دسکتاپ/وب دست‌نخورده بماند.
- اندپوینت‌های زندهٔ TSETMC (همان‌های `test_tsetmc.py`):
  `GetMarketWatch`، `GetMarketOverview/{m}`، `GetClientTypeAll`،
  `GetClosingPriceDailyListCSV/{ins}/{from}`، `GetStaticData` — با هدر
  `Referer/Origin: tsetmc.com`.
- توزیع اسنپ‌شات: آپلود `mobile_snapshot.db.lzma` کنار سایر داشته‌های ریلیز
  (الگوی موجود `codal.db.lzma` + امضای minisign).

## قیدهای رعایت‌شده

- هیچ فایل موجودی از پروژهٔ دسکتاپ تغییر نکرد (فقط `+dist_mobile/` در `.gitignore`).
- `market.db` طبق پروتکل REPO_MAP در CWD می‌ماند؛ اسکریپت `os.chdir(ROOT)` می‌کند.
- ارقام/متن فارسی: خروجی‌ها `ensure_ascii=False`.
