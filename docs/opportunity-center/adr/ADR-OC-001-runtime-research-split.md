# ADR-OC-001 — جداسازی Runtime Go از Research/Training پایتون

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **تصمیم‌گیرنده:** معماری Opportunity Lab
- **مبنا:** Stage 4 `11f4b128`؛ `docs/BorsTerminal-Desktop-Migration-Decisions.md:519-533`

## Context

Runtime پذیرفته‌شدهٔ دسکتاپ `borsd` (Go) + `frontend-v2` + Tauri v2 است. Python امروز در موتورهای پژوهشی/میراثی و ابزارهای تولید داده وجود دارد، اما نباید در بستهٔ کلاینت یا Process Tree نهایی دیده شود. تولید، آموزش، اعتبارسنجی و بهینه‌سازی استراتژی به داده و کتابخانه‌های تحلیلی نیاز دارد که در Go بازنویسی کامل آن‌ها هزینهٔ بالایی دارد و برای Research کافی نیست.

## Decision

1. **Research Plane** روی سیستم مالک با Python اجرا می‌شود: فرضیه، IR Builder، Backtest، Walk-Forward/PBO/DSR/SPA، Trial Registry، آموزش اختیاری، ساخت شواهد و بسته‌بندی.
2. **Runtime Plane** روی سه کلاینت فقط Go است: تفسیر IR، FTS Adapter، Registry Client، Read Model و API. هیچ Python، Uvicorn، FastAPI، Notebook یا وابستگی آن در بسته/فرآیند کلاینت وجود ندارد.
3. Python فقط از `Dataset Snapshot` تغییرناپذیر و read-only می‌خواند؛ هرگز `market.db`/`codal.db` را نمی‌نویسد و به `user.db` کاربر دسترسی ندارد.
4. خروجی Research تا زمانی که Validation و Approval/امضا نگیرد، مصنوع Runtime نیست.
5. قرارداد بین دو صفحه، JSON Schemaهای نسخه‌دار است (`oc.strategy/1`, `oc.bundle/1`, `oc.evidence/1`)، نه فراخوانی کد Python.
6. Validation در Research انجام می‌شود؛ کلاینت فقط Evidence Summary امضاشده را نمایش می‌دهد و آن را دوباره اجرا نمی‌کند.

## Consequences

- دو محیط توسعه/وابستگی داریم؛ Lockfile Research جدا از بستهٔ کلاینت است.
- تست‌های Cross-Language برای Canonical JSON/Hash و Schema لازم است.
- خطاهای Research به Runtime منتقل نمی‌شوند؛ فقط Artifact معتبر.
- هیچ قابلیت Training/Experiment در UI کلاینت نیست؛ Lab کلاینت read-only است.
- افزودن Primitive جدید نیازمند نسخهٔ Runtime و انتشار اپ است، نه بستهٔ Python.

## Alternatives

| گزینه | چرا رد شد |
|---|---|
| بازنویسی کامل Research در Go | هزینه/زمان زیاد؛ کتابخانه‌های آماری و ML بالغ نیستند |
| اجرای Python در کلاینت به‌عنوان Sidecar | نقض Runtime Go و افزایش سطح حمله/حجم |
| Notebook/Web UI به‌عنوان Runtime | وابستگی به مرورگر/Python و عدم بازتولیدپذیری |
| انتقال Validation به Go | تکرار منطق آماری و ریسک واگرایی؛ فقط برای Parity خاص لازم است |

## Evidence

- `backend-go/cmd/borsd/main.go` و `backend-go/go.mod` — Runtime Go.
- `docs/BorsTerminal-Desktop-Migration-Decisions.md:519-533` — تصمیم DECIDED.
- `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md:208-217` — Zero Python in Distributable.
- `requirements.txt` — وابستگی Research جدا.
