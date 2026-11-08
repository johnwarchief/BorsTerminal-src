# ADR-OC-014 — Read Model/API، حالت‌های داده و Lab read-only

- **وضعیت:** Accepted (Engineering) — منطبق با دستور مالک ۲۰۲۶-۱۱-۰۸ بند ۱
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** Phase 3 §۵.۴؛ PRD FR-OC-029..037

## Context

Phase 3 یک Lab با پیکربندی و دکمهٔ اجرای آزمایش طراحی کرد. دستور جدید مالک می‌گوید آموزش/تکامل/تأیید/انتشار فقط روی سیستم مالک انجام شود. همچنین Read Model باید وضعیت داده/تازگی/Registry را صادقانه نشان دهد و APIهای طولانی نباید «۲۰۰ = شروع شد» جعلی بدهند.

## Decision

1. Lab کلاینت **read-only** است: Evidence Summary، Protocol، Gate Table و Run History بستهٔ Stable را نشان می‌دهد؛ دکمهٔ اجرای آزمایش/ویرایش IR/Approval ندارد.
2. اجرای Experiment/Training فقط در Owner Research Workbench است.
3. APIهای OC پاسخ نسخه‌دار با `schema`, `as_of`, `data_state`, `freshness`, `generated_at` می‌دهند؛ فهرست‌ها صفحه‌بندی می‌شوند.
4. عملیات طولانی (Registry Sync) با Job ID و Status واقعی برمی‌گردند؛ 200 بدون Job ممنوع.
5. Read Model در `oc_client.db` ذخیره و با تغییر `data_generation`، فعال‌سازی، Revocation یا بستهٔ جدید باطل می‌شود.
6. حالت‌ها: `ready/empty/stale/degraded/error/unavailable/insufficient_evidence/offline_verified/suspended` با متن/اقدام مشخص.
7. `rank_trace` و Policy Hash در پاسخ Today؛ هیچ Score پنهان.
8. Compare فقط از Evidence Summaryهای Stable/نصب‌شده استفاده می‌کند؛ FTS `incomparable` با دلیل.
9. Monitor مشاهدات محلی را Append-Only نگه می‌دارد؛ هیچ Telemetry به Owner نمی‌رود.

## Consequences

- Phase 3 Lab UI در کلاینت ساده‌تر از Prototype می‌شود؛ Prototype همچنان مرجع Owner Workbench است.
- UI باید حالت Offline/Registry Error را مستقل از Data Error نشان دهد.
- API Job/Status و Cache Invalidation بخشی از P0/P1 است.
- مالک می‌تواند Experimentها را در سیستم خود اجرا کند؛ سه کاربر فقط شواهد Stable را می‌بینند.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| اجرای Experiment در کلاینت | نقض دستور مالک و منابع/امنیت؛ رد |
| API بدون As-of/Freshness | ادعای قطعیت جعلی؛ رد |
| 200=Started بدون Job | نقص موجود Stage 4؛ رد |
| Read Model فقط در حافظه | از دست رفتن/ناسازگاری؛ رد |

## Evidence

- دستور مالک ۲۰۲۶-۱۱-۰۸ بند ۱.
- `03-UX-AND-PRODUCT-EXPERIENCE.md` §۵.۴.
- `backend-go/internal/sync/handlers.go:93-133` — الگوی نامطلوب 200=started.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۱.
