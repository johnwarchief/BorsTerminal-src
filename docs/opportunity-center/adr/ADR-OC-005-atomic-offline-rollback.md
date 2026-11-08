# ADR-OC-005 — نصب اتمیک، Rollback، Offline و Revocation

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **پرسش مرتبط:** Q17 (سیاست آفلاین/Revocation)

## Context

کلاینت باید بستهٔ Stable را بدون احتمال نصب نیمه‌کاره دریافت کند، در قطع شبکه از آخرین نسخهٔ معتبر استفاده کند و در صورت خرابی به نسخهٔ قبلی برگردد. Revocation نیز باید بدون ایجاد وقفه در حالت آفلاین مدیریت شود.

## Decision

1. **Staging → Verify → Commit:** دانلود در Staging هم‌Volume، بررسی امضا/هش/Schema/Compatibility، سپس نوشتن در Content-Addressed Store، fsync و Pointer اتمیک.
2. **Retention:** نسخهٔ فعال N و نسخهٔ قبلی N-1 نگه داشته می‌شوند؛ N-2+ قابل پاک‌سازی است.
3. **Rollback:** Pointer به N-1؛ فقط به نسخهٔ نصب‌شده/معتبر؛ Audit ثبت می‌شود.
4. **Offline:** آخرین ایندکس/بستهٔ تأییدشده در Cache؛ وضعیت `offline_verified` + زمان آخرین Verify. نصب جدید انجام نمی‌شود؛ نسخه‌های فعال با دادهٔ محلی ادامه می‌دهند.
5. **Revocation:** فهرست در ایندکس امضاشده؛ اولین Sync آن را اعمال و فرصت‌های مربوط را باطل می‌کند. تا Sync بعدی، کلاینت آفلاین نمی‌تواند Revocation جدید را بداند؛ این وضعیت صادقانه نمایش داده می‌شود.
6. **Anti-Rollback:** `sequence` یکنواست؛ ایندکس قدیمی‌تر رد می‌شود مگر `recovery=true` امضاشده.
7. **Crash/فایل قفل/فضای کم:** Pointer دست‌نخورده، Staging پاک، خطای متنی؛ نسخهٔ قبلی فعال می‌ماند.
8. **Data Generation:** Rollback داده تابع Stage 4 Applier است؛ `borsd` باید پس از Apply، نسل فعال را Resolve/Reload کند (P0).

## Consequences

- نگهداشتن N-1 فضای دیسک می‌خواهد؛ سیاست Retention بر اساس حجم/تعداد.
- Revocation در آفلاین بلافاصله اثر ندارد؛ Q17 باید مدت/برچسب را تعیین کند.
- Rollback بستهٔ استراتژی و Rollback داده دو مکانیزم جدا با Pointerهای جدا هستند.
- User Data هرگز در این چرخه شرکت نمی‌کند.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| نصب درجا/بازنویسی | ریسک نیمه‌کاره/خرابی؛ رد |
| حذف نسخهٔ قبلی بلافاصله | بدون Rollback؛ رد |
| اعتماد به Cache بدون Verify | Tamper؛ رد |
| Sync اجباری همیشه | آفلاین را می‌شکند؛ رد |

## Evidence

- `backend-go/internal/snapshot/applier.go:124-418` — Staging/Verify/Pointer/Rollback/Retention.
- `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md:208-217, 262-289` — `user.db` و Generation.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۰.۴، §۱۰.۵، §۱۵.
