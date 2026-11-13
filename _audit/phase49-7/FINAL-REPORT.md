# گزارش نهایی Phase 4.9.7 — کشف کامل دادهٔ رهاورد + طراحی جداسازی

## یافته‌های قطعی (شواهد read-only)
- آرشیو ۳۴٫۴ GB = **فقط کندل + متادیتای عمومی دارایی + خطاها**. ۶۳ JSONL = ۴۵۷,۷۱۲ رکورد = ۱۵۴,۶۳۲,۹۳۳ کندل (تطابق کامل با DB). بنیادی/صورت مالی/جریان پول/دفتر سفارش/شاخص **استخراج نشده** (تأیید از کد استخراج + PROVENANCE).
- ۷ پایه: real_close≡last (۱۰۰٪)؛ close=پایانی رسمی؛ type0≡type5 (۵۲/۵۲ دارایی)؛ type7=عملکردی. گرید ۶۳ mode در عمل ۳۶ سری متمایز دارد.
- فرمول USD: close_usd = close / نرخ دلار (دارایی id=2)؛ market_cap_usd = market_cap×1e6/نرخ؛ last_usd تبدیل‌نشده.
- صفرهای W/M و dup-t آن‌ها = **placeholder با t=0** (صندوق‌ها)؛ dup-t در D = bar تکراری identical مبدأ (۱۱ دارایی). ناهنجاری OHLC = source-level (در type7 دست‌نخورده).
- پوشش: ۱۰,۷۱۵ دارایی دارای کندل از ۴۵,۱۵۷؛ صندوق ۶۸۶/۶۰,۳۶۱,۹۶۳ ردیف، سهام ۹۱۰/۵۶,۴۰۵,۲۳۷، رمزارز ۶۱۸، اختیار ۵,۳۳۷ (کم‌تاریخچه).

## ابهام‌های حل‌نشده (نیازمند مستندات رهاورد / تصمیم مالک)
- نام‌گذاری رسمی real_close و intent دقیق type5 (چرا ≡type0) — شواهد داده‌ای قطعی، تسمیهٔ رسمی UNKNOWN.
- واحد مطلق market_cap (میلیون ریال از فرمول استنباط شد) و انطباق دقیق روز نرخ دلار — PARTIALLY_CONFIRMED.
- تقویم معاملاتی TSE در آرشیو نیست (شکاف Technical DB).
- dataset_split و scope نهایی دیتاست آموزش — تصمیم مالک.

## اطلاعات ارزشمند کشف‌شده
- **افزونگی ۴۳.۱۰٪**: real_close≡last و type0≡type5 → انبار عملیاتی می‌تواند از ۱۴.۶۱ GB به ≈۵.۲۰ GB کاهش یابد (حذف alias + padding t=0).
- **دارایی دلار id=2** کلید تبدیل USD است (باید در Shared Metadata بماند).
- **فیلد utc** در JSONL هست ولی DB مرجع حذف کرده — در Technical DB حفظ می‌شود.
- **pack تعدیل** ۸,۲۸۰ step (۸۰۸ دارایی) منبع رویداد/ضریب برای بازتولید عملکردی.
- API رهاورد top-lists (instrument_state/ask-bid/value/اثر شاخص) را ارائه می‌دهد ولی استخراج نشده — هدف استخراج آینده برای Market Intelligence.

## پیشنهاد نهایی معماری (برای تصمیم مالک)
- **Reference Archive** (سرد، immutable): ۳۴٫۴ GB faithful — منبع parity/بازتولید/corpus خام.
- **A. Technical Market DB** (گرم): کندل متمایز پاک‌سازی‌شده + utc + رویداد/ضریب تعدیل + تقویم + منشأ ≈۵.۲۰ GB. همهٔ موتورهای قیمت‌محور (Technical/FTS-setup/Forecasting/Regime/Volatility) را تغذیه می‌کند.
- **B. Other Market Data DB**: بنیادی/جریان/دفتر سفارش/شاخص از CODAL/TSETMC (موجود) + top-lists آیندهٔ رهاورد. سهم آرشیو فعلی رهاورد = ۰ فراتر از متادیتا.
- **C. Shared Metadata**: asset/mode_def/usd_rate/id_crosswalk — کلید مشترک asset_id، بی‌تکرار متادیتا.
- برنامهٔ انتقال P0…P6 با اعتبارسنجی per-phase (MIGRATION-PLAN.md)؛ اجرا منوط به مالک.

## خروجی‌ها
CATALOG / JSONL-REPORT / AMBIGUITIES / DATA-DICTIONARY / DATA-MAP / ARCHITECTURE / ENGINE-USABILITY / MIGRATION-PLAN / schema_technical.sql / FINAL-REPORT + اسکریپت‌های بازتولیدپذیر p7_*.py + artifacts (catalog_jsonl/ambiguity_evidence*/arch_volumes).

**هیچ DB/موتوری تغییر نکرد؛ هیچ merge/release/push انجام نشد. تصمیم اجرای جداسازی با مالک است.**