# ADR-OC-003 — Registry خصوصی برای سه کاربر بدون سرور دائمی

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **پرسش مرتبط:** Q16 (روش دسترسی)

## Context

نسخه‌های Stable باید به سه کاربر برسد، اما هیچ سرور دائمی/هزینهٔ میزبانی مفروض نیست. Stage 4 نشان داد GitHub Releases برای توزیع Snapshotهای امضاشده کار می‌کند و Client می‌تواند Minisign/SHA-256 را بررسی کند. Registry استراتژی حاوی IP است و باید خصوصی باشد؛ دادهٔ شخصی کاربران نباید وارد آن شود.

## Decision

1. Transport پیش‌فرض: **مخزن GitHub خصوصی + Releaseهای تغییرناپذیر + ایندکس امضاشده**. هیچ سرویس دائمی جدید ساخته نمی‌شود.
2. مالک تنها نویسندهٔ مخزن است؛ سه کاربر دسترسی خواندنی محدود دارند.
3. v1: هر کاربر یک Fine-grained PAT با `Contents: Read` روی همان مخزن می‌گیرد؛ در OS Keychain ذخیره می‌شود؛ مالک می‌تواند جدا Revoke کند.
4. `RegistryTransport` یک Interface است: `github_private` (v1)، `file` (Export/Import آفلاین)، `static_https` (آینده).
5. ایندکس `oc.registry/1` + `registry.json.sig`؛ دارایی‌ها با Release Tag تغییرناپذیر.
6. هیچ دادهٔ شخصی/Telemetry در Registry نیست؛ فقط Bundleهای Stable + Evidence Summary + Revocation.
7. حالت Export/Import برای نصب اولیه/شبکهٔ محدود/پشتیبان پشتیبانی می‌شود.

## Consequences

- وابستگی به GitHub برای Sync؛ با Cache/Offline کاهش می‌یابد.
- توکن خواندنی می‌تواند به اشتراک گذاشته شود؛ برای سه کاربر مورد اعتماد پذیرفته است. امضا یکپارچگی می‌دهد، نه محرمانگی.
- اگر GitHub مناسب نبود، Interface اجازهٔ تغییر Transport بدون تغییر Semantics را می‌دهد.
- محرمانگی قوی‌تر (per-user encryption) در آینده و با ADR جدا.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| سرور دائمی Owner PC | وابسته به روشن‌بودن/شبکه؛ هزینهٔ دسترس‌پذیری |
| Object Storage با Signed URL | هزینه/مدیریت اضافه؛ برای ۳ کاربر توجیه ندارد |
| GitHub Private Releases | صفر هزینهٔ اضافه، امضاشده، تغییرناپذیر — انتخاب |
| File-only | ساده اما Onboarding/به‌روزرسانی دستی؛ حالت پشتیبان |

## Evidence

- Stage 4 Release/Minisign: `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md:260-289`.
- `backend-go/internal/snapshot/publisher.go:275-372` — ترتیب انتشار.
- `frontend/src-tauri/tauri.conf.json:31-35` — GitHub به‌عنوان کانال توزیع موجود.
- دستور مالک ۲۰۲۶-۱۱-۰۸ (بند ۳).
