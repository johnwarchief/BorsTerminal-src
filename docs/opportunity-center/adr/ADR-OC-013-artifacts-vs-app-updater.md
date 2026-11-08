# ADR-OC-013 — جداسازی Registry استراتژی از App Updater

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** A12/A14؛ Stage 4 Final Report §۵

## Context

Stage 4 نشان داد مسیر Update اپ در Go پیاده نشده است (`/api/update/*` 501)، `latest.json`/Version.txt غیرامضاشده‌اند و Tauri Updater در Shell کامپایل شده اما از JS استفاده نمی‌شود. هم‌زمان Registry استراتژی باید امضا، Verify، Atomic Install، Rollback و Offline داشته باشد. مخلوط‌کردن این دو، سطح حمله و پیچیدگی را بالا می‌برد.

## Decision

1. **Registry استراتژی** یک کانال مستقل با قرارداد `oc.registry/1`/`oc.bundle/1` است؛ از `latest.json`، Inno Silent Install یا Patch App استفاده نمی‌کند.
2. بسته‌های استراتژی **دادهٔ تفسیری** هستند، نه کد اجرایی؛ Runtime با Primitive Registry آن‌ها را اجرا می‌کند.
3. App Update (کد `borsd`/Shell/UI) کانال جدا دارد؛ وضعیت فعلی آن OPEN است و در P0/P5 مستقل بازبینی می‌شود.
4. Compatibility: Bundle `runtime_min/max`، IR Schema و Primitive Version دارد؛ Client ناسازگار نصب نمی‌کند.
5. هر کانال کلید/Manifest/Retention خود را دارد؛ Rollback استراتژی و Rollback اپ دو مکانیزم جدا هستند.
6. هیچ Registry Bundle اجازهٔ اجرای کد/Plugin/Shell را ندارد.

## Consequences

- OC v1 می‌تواند بدون تعمیر کامل App Updater منتشر شود، اما ارتقای Runtime (Primitive جدید) به کانال اپ وابسته است.
- App Updater معیوب یک ریسک جدا باقی می‌ماند؛ نمی‌توان آن را با Registry پنهان کرد.
- دو نسخه‌بندی (App/Runtime و Bundle) باید در UI مشخص باشد.
- Rollback اپ باید مستقل و با Backup طراحی شود.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| استفاده از Inno/Updater موجود برای استراتژی | Unsigned/Code Execution/Blast radius؛ رد |
| قرار دادن استراتژی در Snapshot داده | Manifest فقط `.db`/LZMA؛ چرخهٔ داده را آلوده می‌کند؛ رد |
| یک Updater برای همه | مالکیت/امنیت/Retention مبهم؛ رد |
| Registry فقط کد | نقض IR/No arbitrary code؛ رد |

## Evidence

- `backend-go/internal/httpapi/server.go` و `routes.json` — Update routes 501.
- `frontend/src-tauri/tauri.conf.json:31-35` — Updater.
- `scripts/publish_github_release.py` — `latest.json`/Patch.
- `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md:236-240` — remaining update/key actions.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۰، §۱۵.
