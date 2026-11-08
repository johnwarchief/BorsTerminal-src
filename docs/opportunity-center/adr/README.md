# ADR Index — Opportunity Lab

> **تاریخ:** ۲۰۲۶-۱۱-۰۸ · **مبنا:** Stage 4 پذیرفته‌شده `11f4b128` · **شاخه:** `mission/opportunity-center-design-2026-11-08`
>
> هر ADR یک تصمیم فنی با پیامدهای مشخص است. وضعیت‌ها:
> **Accepted (Engineering)** = تصمیم فنی این مأموریت؛ **Owner Sign-off Pending** = ساختار فنی قطعی است اما محتوای سیاست/محصول در اختیار مالک است؛ **Proposed** = گزینهٔ پیشنهادی بدون پذیرش.

| ADR | عنوان | وضعیت | پرسش/مرجع |
|---|---|---|---|
| [ADR-OC-001](ADR-OC-001-runtime-research-split.md) | جداسازی Runtime Go از Research/Training پایتون | Accepted (Engineering) | A1 |
| [ADR-OC-002](ADR-OC-002-owner-only-control.md) | کنترل، تأیید و انتشار فقط روی سیستم مالک | Accepted (Owner instruction) | A2/A11 |
| [ADR-OC-003](ADR-OC-003-private-registry.md) | Registry خصوصی برای سه کاربر بدون سرور دائمی | Accepted (Engineering) | Q16 |
| [ADR-OC-004](ADR-OC-004-signed-bundles.md) | زنجیرهٔ اعتماد Manifest/Bundle/Index و جداسازی کلیدها | Accepted (Engineering) | Q18 |
| [ADR-OC-005](ADR-OC-005-atomic-offline-rollback.md) | نصب اتمیک، Rollback، Offline و Revocation | Accepted (Engineering) | Q17 |
| [ADR-OC-006](ADR-OC-006-storage-boundaries.md) | توپولوژی ذخیره‌سازی و مرزهای Single-Writer | Accepted (Engineering) | Q13 |
| [ADR-OC-007](ADR-OC-007-typed-ir-interpreter.md) | IR تایپ‌شده و Interpreter Go؛ بدون کد دلخواه | Accepted (Engineering) | OC-D-021 |
| [ADR-OC-008](ADR-OC-008-fts-canonical-adapter.md) | FTS کانونیکال به‌صورت Adapter و Envelope؛ دروازهٔ پاریتی | Accepted (Engineering) | Q5 |
| [ADR-OC-009](ADR-OC-009-validation-policy.md) | Validation Policy به‌عنوان دادهٔ امضاشده | Owner Sign-off Pending | Q1 |
| [ADR-OC-010](ADR-OC-010-ranking-policy.md) | Ranking Policy به‌عنوان دادهٔ امضاشده؛ بدون Score مرکب | Owner Sign-off Pending | Q11 |
| [ADR-OC-011](ADR-OC-011-cloud-gpu-jobs.md) | GPU موقت اختیاری و مجوز خروج داده | Owner Sign-off Pending | Q15 |
| [ADR-OC-012](ADR-OC-012-local-api-personal-data.md) | امنیت API محلی و مرز دادهٔ شخصی/سه کاربر | Accepted (Engineering) | A4/A12 |
| [ADR-OC-013](ADR-OC-013-artifacts-vs-app-updater.md) | جداسازی Registry استراتژی از App Updater | Accepted (Engineering) | A12/A14 |
| [ADR-OC-014](ADR-OC-014-read-models-lab-boundary.md) | Read Model/API، حالت‌های داده و Lab read-only | Accepted (Engineering) | Owner #1 |
| [ADR-OC-015](ADR-OC-015-desktop-notifications.md) | زیرسیستم اعلان دسکتاپ: موتور Go، پل Tauri، مرکز اعلان | Accepted (Engineering)؛ پیش‌فرض‌های محصول Pending | Q20–Q24 |

## قالب ADR

هر ADR شامل Context، Decision، Consequences، Alternatives و Evidence است. تصمیم مالک با نقل صریح یا ارجاع به دستور تاریخ‌دار ثبت می‌شود؛ تصمیم مهندسی به‌عنوان تصمیم مالک ثبت نمی‌شود.
