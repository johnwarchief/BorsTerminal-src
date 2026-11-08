# ADR-OC-008 — FTS کانونیکال به‌صورت Adapter و Envelope؛ دروازهٔ پاریتی

- **وضعیت:** Accepted (Engineering) — جایگاه محصول: Owner Sign-off Pending (Q5)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** OC-D-025/028/032; Phase 2 §۸

## Context

FTS یک استراتژی مستقل و کانونیکال با قواعد جزوه است. Phase 2 قرارداد `fts.envelope/1` را تعریف کرد. Go امروز بخشی از FTS را دارد (`internal/fundamental.EvaluateV10`, `internal/chart.FTS`) اما Ruleset تکنیکال `"3"` است در حالی که Python `"6"` دارد؛ قیف Go pass-through است و برخی مسیرها 501 هستند. بازپیاده‌سازی در OC ممنوع است.

## Decision

1. `internal/oc/fts` یک **Adapter** است که Envelope می‌سازد و از موتورهای Go موجود استفاده می‌کند؛ هیچ فرمول FTS در OC تکرار نمی‌شود.
2. Envelope سه‌حالتی (`pass/fail/unknown` + `NA`)، `ruleset_version`, `config_hash`, `as_of.kind`, `coverage`, `provenance` را حمل می‌کند.
3. `/fts-screen` سطح کانونیکال مستقل می‌ماند؛ Today همان Envelope را مصرف می‌کند؛ هیچ غربالگری موازی ساخته نمی‌شود.
4. FTS Strategy در Library `engine=fts.canonical` است؛ Bundle آن فرمول ندارد، فقط Ruleset/Config/Approval/Evidence.
5. **دروازهٔ پاریتی:** تا هم‌ترازی Ruleset/Config و Golden Vectors، FTS Stable منتشر نمی‌شود. Stub/501/Pass-through به‌عنوان pass مصرف نمی‌شود؛ `unavailable` نمایش داده می‌شود.
6. Config کانونیکال از Snapshot/Registry می‌آید؛ Override کاربر جدا و در Envelope با `config_override=true` علامت می‌خورد و برای Approved معتبر نیست.
7. Replay تاریخی فقط با Envelope/دادهٔ امضاشده یا Oracle Research؛ Runtime ادعای تاریخی بدون Replay ندارد.

## Consequences

- v1 Today به تکمیل FTS Go وابسته است؛ این یک Gate است، نه یک جزئیات.
- FTS می‌تواند به‌عنوان `canonical_baseline` با امضای مالک در Registry باشد، اما همچنان به پاریتی/شواهد نیاز دارد.
- Config دوگانه (user.db vs file) باید حل شود؛ Approved فقط Config کانونیکال را می‌بیند.
- Funnel ناقص، `coverage<1` یا `unavailable` تولید می‌کند؛ فرصت FTS ساخته نمی‌شود.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| بازپیاده‌سازی FTS در OC | تصمیم مالک را نقض می‌کند؛ رد |
| استفاده از Stub به‌عنوان pass | نتیجهٔ جعلی؛ رد |
| ادغام کامل FTS در Today | غربالگری/Replay را حذف می‌کند؛ رد |
| Python runtime برای FTS | Runtime Go را نقض می‌کند؛ رد |

## Evidence

- `api/chart.py:3896` — Ruleset 6.
- `backend-go/internal/chart/fts_swings.go:20` — Ruleset 3.
- `backend-go/internal/funnel/funnel.go` — pass-through.
- `backend-go/internal/httpapi/server.go:225-291` — FTS/Funnel routes.
- Phase 2 §۸؛ `04-TECHNICAL-ARCHITECTURE.md` §۱۲.
