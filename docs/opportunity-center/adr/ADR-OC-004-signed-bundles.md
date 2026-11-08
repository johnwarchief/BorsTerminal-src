# ADR-OC-004 — زنجیرهٔ اعتماد Manifest/Bundle/Index و جداسازی کلیدها

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **پرسش مرتبط:** Q18 (نگهداری/چرخش کلید)

## Context

Runtime باید بدون اعتماد به Transport، اصالت و یکپارچگی بسته‌ها را ثابت کند. Stage 4 از Minisign/SHA-256 برای Snapshot داده استفاده می‌کند و نشان داد Client می‌تواند امضا را قبل از Apply بررسی کند. Registry استراتژی سطح حملهٔ متفاوتی دارد: بستهٔ استراتژی، Approval و ایندکس باید از منابع کلیدی جدا محافظت شوند.

## Decision

1. **Bundle** شامل `manifest.json` و `manifest.json.sig` (Minisign/Ed25519) است؛ Manifest هش همهٔ فایل‌ها را دارد.
2. **Registry Index** شامل `registry.json` + `.sig` است؛ آخرین دارایی منتشرشده است تا کلاینت مجموعهٔ کامل ببیند.
3. **Approval Record** جداگانه با Approval Key امضا می‌شود و داخل Bundle قرار می‌گیرد؛ Bundle نبودِ Approval معتبر را رد می‌کند.
4. چهار نقش کلیدی جدا:
   - `DATA_KEY` (موجود Stage 4) — Snapshot داده.
   - `APP_KEY` (موجود Tauri) — Update اپ.
   - `APPROVAL_KEY` (جدید) — Approval؛ فقط Owner Workstation، آفلاین/رمزدار.
   - `REGISTRY_KEY` (جدید) — Bundle/Index؛ فقط Owner Workstation.
5. `key_id` در همهٔ Manifest/Approval/Index ثبت می‌شود؛ Client Trust Store چند کلید را با بازهٔ اعتبار نگه می‌دارد.
6. Canonical JSON برای IR/Approval/Manifest؛ Hash روی بایت‌های همان فایل؛ اعداد هویتی به‌صورت رشتهٔ اعشاری.
7. هیچ کلید خصوصی در CI، Registry، Research Artifact، Log یا Client نیست.

## Consequences

- Registry Publication نیاز به دو Unlock (Approval و Registry) دارد؛ می‌توان Approval را آفلاین امضا کرد و بعد منتشر کرد.
- چرخش کلید نیازمند Sequence مشخص است: انتشار Client با Public Key جدید، سپس امضای Registry، سپس بازنشستگی قدیم.
- اگر کلید قدیم Compromise شود، Key Transition قابل‌اعتماد نیست؛ Recovery فقط با نصب دستی Client جدید.
- امضا محرمانگی نمی‌دهد؛ دسترسی خصوصی از GitHub/PAT می‌آید.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| یک کلید مشترک Data/App/Registry | Blast radius بزرگ؛ رد |
| امضای هر فایل جدا | پیچیدگی/حجم؛ Manifest+Hash کافی است |
| TLS-only | اصالت بلندمدت/Offline را ثابت نمی‌کند |
| GPG/Web of Trust | عملیاتی سنگین‌تر؛ Minisign موجود است |

## Evidence

- `backend-go/internal/snapshot/manifest.go`, `signer.go`, `publisher.go`.
- `docs/STAGE4-PRODUCTION-ACTIVATION-FINAL-REPORT.md:246-260` — Key audit/rotation.
- `04-TECHNICAL-ARCHITECTURE.md` §۸، §۱۰، §۱۴.
