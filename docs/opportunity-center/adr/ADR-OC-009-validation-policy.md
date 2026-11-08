# ADR-OC-009 — Validation Policy به‌عنوان دادهٔ امضاشده

- **وضعیت:** Owner Sign-off Pending (Q1) — ساختار فنی Accepted
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** Phase 2 §۵.۱۲–۵.۱۴؛ OC-D-022/027/031

## Context

آستانه‌های Approved (طول OOS، PBO/DSR/SPA، حداقل معامله/`N_eff`، استرس هزینه، تمرکز رژیم) محتوای روش‌شناسی‌اند. Hardcode کردن آن‌ها در Go، تغییر سیاست را به Release گره می‌زند و می‌تواند تصمیم مالک را پنهان کند. با ۵ سال داده و `N≈100`، تأیید `SR<1.5` ممکن نیست؛ سیاست باید `insufficient_evidence` را رسمی نگه دارد.

## Decision

1. `oc.validation_policy/1` یک سند JSON امضاشده با Approval Key است.
2. فیلدها: `policy_id`, `split` (train/validation/holdout), `holdout` (locked/one-shot/access log), `walk_forward` (folds/embargo), `pbo_max`, `dsr_min`, `spa_max`, `min_trades`, `min_trades_per_fold`, `min_n_eff`, `cost_stress_multiplier`, `break_even_min`, `regime_concentration_max`, `sample_adequacy`, `verdict_rules`, `approval_enabled`, `effective_from`.
3. Validation/Approval فقط `policy_hash` را حمل می‌کنند؛ Runtime هیچ عدد آستانه‌ای را Hardcode نمی‌کند.
4. تا امضای مالک: `approval_enabled=false`؛ هیچ استراتژی جدید Stable نمی‌شود. FTS می‌تواند با `approval_basis=canonical_baseline` و امضای جدا مسیر v1 را باز کند.
5. تغییر Policy = Policy جدید؛ Approvalهای قبلی با `policy_hash` قدیم معتبر می‌مانند تا Expire/Review؛ مالک می‌تواند Revalidation اجباری کند.
6. Candidate Profile پیشنهادی Phase 2 (زیر) فقط «پیشنهاد» است، نه تصمیم مالک.

### Candidate Profile (پیشنهادی، غیرنهایی)

| فیلد | مقدار پیشنهادی Phase 2 |
|---|---|
| Split | ۶۰/۲۰/۲۰ |
| Holdout | قفل، یک‌بارمصرف، Access Log |
| Walk-Forward | ≥۴ Fold، Embargo = h+2 |
| حداقل معامله | ۱۰۰ کل / ۳۰ در Fold |
| PBO | ≤۰٫۲۵ |
| DSR | ≥۰٫۹۵ |
| SPA | p≤۰٫۰۵ (B=۱۰۰۰–۵۰۰۰) |
| استرس هزینه | ۲×، Net مثبت، Break-even ≥۲× |
| تمرکز رژیم | <۷۰٪ PnL از یک رژیم |
| نمونه | `N_eff`/MDE؛ کمبود ⇒ `insufficient_evidence` |

> این اعداد از Phase 2 آمده‌اند و در این ADR «پیشنهاد» هستند. مالک باید یک Policy را امضا کند؛ هیچ استراتژی جدیدی تا آن زمان Stable نمی‌شود.

## Consequences

- تغییر آستانه‌ها بدون تغییر کد ممکن است؛ Audit و بازتولیدپذیری حفظ می‌شود.
- UI باید `policy_id/hash` و وضعیت «سیاست پیش‌فرض/امضاشده» را نشان دهد.
- Validationهای قدیمی پس از تغییر Policy می‌توانند `expired` شوند.
- `approval_enabled=false` می‌تواند v1 را برای استراتژی‌های جدید مسدود کند؛ FTS مسیر جدا دارد.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| Hardcode آستانه‌ها | تغییر سخت، پنهان‌شدن سیاست؛ رد |
| یک Policy ثابت برای همیشه | انعطاف/تکامل روش‌شناسی را می‌کشد؛ رد |
| تأیید با آستانهٔ پیش‌فرض بدون امضا | تصمیم مالک را جعل می‌کند؛ رد |
| حذف Approval تا ابد | محصول ناقص؛ رد |

## Evidence

- Phase 2 §۵.۱۲ جدول دروازه‌ها؛ §۵.۱۳ واقعیت نمونه؛ §۵.۱۴ تاکسونومی.
- `OPEN-QUESTIONS.md` Q1.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۸.۱.
