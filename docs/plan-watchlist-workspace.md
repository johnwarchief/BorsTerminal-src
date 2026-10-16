# دیدهبان بازار — طرحِ پیاده‌سازی (زیرتبِ مستقلِ پرتفوی، سه‌پنلی)

وضعیت: **طرح، اجرا‌نشده.** بلوک‌هایِ سازنده تقریباً همه موجودند؛ کار اصلی «مونتاژ + چیدمانِ سه‌پنلی + آزمونِ مرورگری» است، نه از‑نو‑نوشتن.

## زمینۀِ واقعیِ کد (راهنما)
- `frontend/src/features/portfolio/routes/PortfolioPage.tsx` — **از قبل** `type BoardTab = 'portfolio' | 'monitor' | 'rejects'` دارد و `WatchlistSection` را import می‌کند. ⇒ زیرتبِ «دیده‌بان» (monitor) هست؛ باید کامل/جدا شود.
- `frontend/src/features/portfolio/components/WatchlistSection.tsx` — بخشِ فعلیِ دیده‌بان داخلِ پرتفوی.
- `frontend/src/features/technical/api/useWatchlist.ts` — دادهٔ دیده‌بان.
- `frontend/src/features/technical/api/useOrderBook.ts` + `components/SidebarOrderBook.tsx` — دفترِ سفارشِ پنج‌سطحیِ آماده (از `/api/order-book/{symbol}`، `api/chart.py:790`).
- `frontend/src/features/technical/nahayatnegar/components/KLineChartWrapper.tsx` و `components/FtsEngineChart.tsx` — نمودارِ کندلِ روزانه (تعدیل عملکردی ازِ همان مسیرِ production).
- `frontend/src/shared/api/marketFeed.ts` → `useMarketFeedShared(select)` — feedِ مشترکِ زنده (دلتا/revision؛ بدونِ polling موازی).
- `useSymbolStore` (selected symbol)، `FlashNum`/`fmtInt`/`toFaDigits`/`fmtAge` — نمایشِ تازگی/ارقامِ فارسی.

## معماریِ هدف
### ۱) دو زیرتبِ مستقل درِ PortfolioPage
- `portfolio` = دارایی‌هایِ واقعی (همین حالا هست).
- `monitor` = «دیدهبانِ بازار» (چیدمانِ جدیدِ پایین). نمادهایِ دیده‌بان هرگز به‌عنوانِ داراییِ پرتفوی حساب نشوند (منبعِ داده جدا: useWatchlist، نه usePortfolio).

### ۲) بالا: جدولِ زندهٔ دیده‌بان
- ردیف‌ها = اشتراکِ (نمادهایِ دیده‌بان) با (ردیف‌هایِ `useMarketFeedShared`)؛ ستون‌ها ازِ همان row: نماد، وضعیتِ معاملاتی (`market_universe`/`is_live`/`st_code`)، `p_last` + `percent_change`، `p_closing`، `q_tot_tran`/`q_tot_cap`، تقاضا (`buy_q1_px`/`buy_q1_vol` سبز)، عرضه (`sell_q1_px`/`sell_q1_vol` قرمز)، `h_even`/`last_sync`.
- کلیکِ ردیف → `useSymbolStore.setSelected(symbol)` (پایین را هماهنگ می‌کند).
- با revisionِ تازه، فقطِ ردیفِ تغییریافته رندر شود (selectِ باریک + keyِ پایدار؛ ازِ رندرِ کلِ صفحه پرهیز).
- دادهٔ کهنه/خطا: برچسبِ «کهنگی/خطا» جدا ازِ «ارتباطِ موفق» (FreshnessBadge موجود).

### ۳) پایین: سه‌پنلیِ نمادِ انتخابی (gridِ RTL، درِ 1366×768 هم قابل‌استفاده)
- چپ: `FtsEngineChart`/نسخۀِ فشرده‌اش — کندلِ روزانه، تعدیل عملکردی ازِ همان مسیرِ `/api/chart-db` (منبعِ دوم نساز).
- وسط: `SidebarOrderBook` (پنجِ سطح، تقاضا سبز/عرضه قرمز، زمانِ به‌روزرسانی). با تغییرِ selected، دادهٔ نمادِ قبلی بی‌درنگ عوض/پاک شود (queryKey با symbol).
- راست: پنلِ اطلاعات + **قراردادِ ربات**: یک `orderPanelContract` (state machine: idle→armed→submitting→sent→ack/cancelled/error) با `buy/sell DISABLED + «اتصالِ ربات فعال نیست»` تا زمانِ راه‌اندازیِ واقعیِ `api/execution.py` (dry_run). هیچِ سفارشِ واقعی نه. کُردِ اتصالِ بعدی بدونِ بازنویسیِ UI.

## کارهایِ قطعی/رفعِ باگ
- اطمینان ازِ اینکه انتخابِ نماد هر سه پنل را هماهنگ می‌کند (selected ازِ یکِ store).
- آخرینِ نمادِ انتخابی با pollِ تازه گم نشود.
- خطایِ API ≠ نتیجهٔ خالی؛ دادهٔ نمادِ قبلی زیرِ برچسبِ نمادِ جدید نشان داده نشود (queryKey/placeholderData).
- ارتفاعِ جدول/پنل‌ها (نه loaderِ ظاهری).

## آزمون
- jsdom: انتخابِ نماد → هر سه پنل؛ ورود/خروجِ نماد → تعدادِ ردیف؛ خطایِ موقت/کهنگی؛ RTL/ابعاد.
- مرورگرِ واقعی: **نیازمندِ لاگینِ مالک درِ `localhost:5173`** (دروازۀِ احرازِ هویتِ محلی؛ ایجنت رمز وارد نمی‌کند). شاهدِ قبل/بعد + اسکرین‌شات درِ `docs/validation/watchlist/`.
- tsc/eslint/build/vitest + گاردهایِ پرتفوی/feed.

## وابستگی‌ها/محدودیت
- اثباتِ بصری ← لاگینِ مالک.
- پنلِ ربات ← اتصالِ واقعیِ کارگزاری (سرقدرتی، معوق)؛ فعلاً فقطِ قراردادِ UI + دکمهٔ غیرفعال.
