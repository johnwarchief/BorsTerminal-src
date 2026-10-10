# راهنمای مستندات BorsTerminal

**از این فایل شروع کنید.** این صفحه نقشهٔ ناوبری و تقدم منابع است، نه ادعای وضعیت لحظه‌ای تمام قابلیت‌ها. گزارش‌های زمان‌دار فقط شواهد همان تاریخ‌اند؛ پیش از اجرای دستور یا فرض‌کردن یک باگِ «باز»، وضعیت branch، کد و تست‌های جاری را بررسی کنید.

## از کجا شروع کنم؟

1. **قواعد مهندسی و فرمان‌ها:** [`AGENTS.md`](../AGENTS.md)
2. **نقشهٔ تولیدشدهٔ کد:** [`AGENT-INDEX.md`](AGENT-INDEX.md) — فقط خواندنی؛ با `python tools/build_agent_index.py` بازتولید و با `python dev/code_index_guard_v1065.py` بررسی می‌شود.
3. **نقشهٔ کلان و سابقهٔ تصمیم‌ها:** [`MASTER-EXECUTION-ROADMAP.md`](MASTER-EXECUTION-ROADMAP.md) — roadmap/ledger حجیم و تاریخ‌دار؛ صف کار امروز را بدون تطبیق با رأی جدیدتر مالک از آن برداشت نکنید.
4. **قواعد FTS:** [`fts-notes/OWNER_RULINGS.md`](fts-notes/OWNER_RULINGS.md) و [راهنمای تقدم منابع FTS](fts-notes/README.md).
5. **انتشار:** [`RELEASE_NOTES.md`](RELEASE_NOTES.md) برای متن انتشار؛ مقدار جاری `APP_VERSION` را از `bors_config.py` بخوانید. [`CHANGELOG.md`](../CHANGELOG.md) تاریخچه‌ای ناقص است.
6. **تحلیل داده و UI:** گزارش‌های زمان‌دار TSETMC، TradersArena، candle/chart parity و UX؛ تاریخ، نسخه و دامنهٔ هر سنجش را قبل از استفاده بررسی کنید.
7. **دریافت اندیکاتورهای پیشنهادی:** [`technical-indicators/inbox/`](technical-indicators/inbox/README.md).

## مرجع و تقدم اسناد FTS

قواعد پارامترهای پیش‌فرض و قابلیت سفارشی‌سازی ساعت شنی در [fts-notes/OWNER_RULINGS.md](fts-notes/OWNER_RULINGS.md) رأی شده‌اند؛ قرارداد اجرایی و تست پذیرش در [FTS-USER-CONFIGURATION-SPEC.md](FTS-USER-CONFIGURATION-SPEC.md) است. سند طراحی به‌تنهایی اثبات نمی‌کند که UI و موتور به‌روزرسانی شده‌اند.

در تعارض قواعد روش‌شناسی، این ترتیب را رعایت کنید:

1. **منابع اصلی روش‌شناسی:** [جزوهٔ FTS](%D8%AC%D8%B2%D9%88%D9%87%20FTS.pdf) و [چارت چهارصفحه‌ای FTS](FTS.CHART_3.pdf).
2. **تصحیح یا رأی صریح بعدی مالک:** [`OWNER_RULINGS.md`](fts-notes/OWNER_RULINGS.md)، فقط وقتی رأی صریح است و موضوع اختلاف را مشخص می‌کند.
3. **مشخصات مهندسی مشتق‌شده:** [`FTS_SPEC.md`](FTS_SPEC.md)، [`FTS_SYSTEM_SPECIFICATION_v2.md`](FTS_SYSTEM_SPECIFICATION_v2.md) و گزارش‌های ممیزی. این اسناد تفسیر/راهنمای پیاده‌سازی‌اند؛ به‌تنهایی نمی‌توانند PDF اصلی یا رأی صریح مالک را لغو کنند.
4. **متن استخراج‌شده و رونوشت‌ها:** برای جست‌وجو مفیدند؛ در ابهام به PDF اصلی برگردید.

## مرزبندی فایل‌های مهم

| سند | کاربرد درست | محدودیت |
|---|---|---|
| [`AGENT-INDEX.md`](AGENT-INDEX.md) | مسیر‌یابی کد، به‌صورت تولیدشده | وضعیت جاری کارها یا منبع قواعد کسب‌وکار نیست |
| [`FTS-USER-CONFIGURATION-SPEC.md`](FTS-USER-CONFIGURATION-SPEC.md) | قرارداد پارامترهای قابل تنظیم FTS، ساعت‌شنی و معیارهای پذیرش | سند طراحی؛ اجرای کد فقط پس از پاس‌شدن تست‌های پذیرش تأیید می‌شود |
| [`CANDLE-CONTRACT.md`](CANDLE-CONTRACT.md) | قرارداد داده و مبنای کندل | گزارش parity تاریخ‌دار، برابری کامل امروز را اثبات نمی‌کند |
| [`RAHAVARD-PARITY-INVENTORY.md`](RAHAVARD-PARITY-INVENTORY.md) | inventory فنی و شواهد یک سنجش | یافته‌ها را بدون تاریخ/کد جاری تعمیم ندهید |
| [`CHART-PARITY-REFERENCE.md`](CHART-PARITY-REFERENCE.md) | رفتار و قابلیت‌های UX چارت با مرجع TradingView/Arshan | مرجع روش‌شناسی FTS یا حقیقت داده/تعدیل نیست |
| [`validation/TRADERSARENA-MARKET-STATUS-PARITY.md`](validation/TRADERSARENA-MARKET-STATUS-PARITY.md) | سنجش وضعیت بازار در یک زمان مشخص | PASS یک فیلد/نشست به همهٔ فیلدها/نشست‌ها تعمیم نمی‌یابد |
| [`TSETMC-DATA-GAP-MATRIX.md`](TSETMC-DATA-GAP-MATRIX.md) | نقشهٔ شکاف‌های داده در زمان ممیزی | بدون تطبیق مجدد، فهرست قطعی باگ‌های امروز نیست |
| [`technical-indicators/inbox/`](technical-indicators/inbox/README.md) | منابع خام در انتظار بررسی | بخشی از موتور فعال یا مورد تأیید نیست |
| [`technical-indicators/reviewed/`](technical-indicators/reviewed/README.md) | نتیجهٔ بررسی و محدودیت‌ها | به معنی پیاده‌سازی نیست |
| [`technical-indicators/implemented/`](technical-indicators/implemented/README.md) | مستندات اندیکاتورهای پیاده‌سازی‌شده و تست‌شده | جایگزین کد و تست رگرسیون نیست |

## اسناد snapshot، handoff و آرشیو

فایل‌های زیر برای تاریخچه و traceability حفظ شده‌اند، اما **منبع اجرای کار فعلی نیستند** مگر پس از تطبیق با کد و رأی مالک:

- [`HANDOFF.md`](../HANDOFF.md) — handoff نسخهٔ قدیمی v1.0.18.
- [`REPO_MAP.md`](../REPO_MAP.md) — نقشهٔ قدیمی v9.7.2 و ساختار legacy مبتنی بر `static/`; برای مسیر‌یابی امروز از [`AGENTS.md`](../AGENTS.md) و [`AGENT-INDEX.md`](AGENT-INDEX.md) استفاده کنید.
- [`PLAN-remaining.md`](PLAN-remaining.md) — snapshot قدیمی v1.0.44، همراه دستورهای Jev و مسیرهای محیطی قدیمی.
- [`REMAINING-WORK.md`](REMAINING-WORK.md) — snapshot تاریخ 2026-10-01 / v1.0.65.
- [`HANDOFF-FTS-TAB-OPEN-WORK.md`](HANDOFF-FTS-TAB-OPEN-WORK.md)، [`HANDOFF-PROMPT.md`](HANDOFF-PROMPT.md) و [`HANDOFF-1081.md`](HANDOFF-1081.md) — handoffهای زمان‌دار؛ branch، release و وظایف را دوباره بررسی کنید.
- [`MIGRATION.md`](../MIGRATION.md) — دستورالعمل انتقال ماشین/AutoClaw؛ برای Qoder/Laya بدون تطبیق استفاده نشود.
- [`UPDATE.md`](../UPDATE.md) و [`TAURI_GUIDE.md`](../TAURI_GUIDE.md) — راهنماهای هدف/معماری‌ویژه؛ فرمان‌های فعال را با `AGENTS.md`، `scripts/` و workflow انتشار تطبیق دهید.
- [`wip/`](wip/README.md) — آرشیو workspace قدیمی؛ diffها را کورکورانه روی HEAD اعمال نکنید.
- [`autoclaw-status-report.html`](autoclaw-status-report.html)، [`autoclaw-ui-remediation-plan.md`](autoclaw-ui-remediation-plan.md) و [`plans/FRONTEND-ARCH-PLAN.md`](plans/FRONTEND-ARCH-PLAN.md) — گزارش/طرح‌های تاریخی وابسته به workspace یا مرحلهٔ مهاجرت قبلی.
- `fts-notes/transcription_*.md` و `jozve_FTS_handwritten_pages_*.md` — رونوشت‌های کمکی با بازه‌های هم‌پوشان؛ PDF اصلی مرجع است.
- گزارش‌های TA-PARITY، INDICATOR-PARITY، UX-PERFORMANCE-AUDIT و ممیزی‌های مشابه، شواهدی مختص تاریخ و نسخه‌اند.

## انتشار و نسخه

- متن release: [`RELEASE_NOTES.md`](RELEASE_NOTES.md).
- نسخهٔ منبع: `APP_VERSION` در `bors_config.py`.
- `CHANGELOG.md` تاریخچه‌ای ناقص دارد و مرجع تشخیص نسخهٔ جاری نیست.
- مخزن منبع `BorsTerminal-src` و مخزن توزیع عمومی `BorsTerminal` نقش‌های جدا دارند؛ نسخهٔ منتشرشده را در مخزن توزیع بررسی کنید.

## محدودیت ممیزی

این راهنما تقدم منابع و مسیر ناوبری را مشخص می‌کند. ادعاهای فنی تاریخ‌دار فقط وقتی وضعیت فعلی محسوب می‌شوند که با branch، کد، تست و در صورت لزوم دادهٔ زنده دوباره تأیید شوند.
