# ADR-OC-008 — FTS کانونیکال به‌صورت Adapter و Envelope؛ دروازهٔ پاریتی

- **وضعیت:** Accepted (Owner Decision 2026-11-09) — FTS Conformance/Parity Gate OPEN
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** OC-D-025/028/032; Phase 2 §۸

## Context

FTS یک استراتژی مستقل و کانونیکال است، اما کانونیکال بودن به معنی درست بودن کد فعلی نیست. مرجع قواعد `docs/جزوه FTS.pdf` و احکام مالک در `docs/fts-notes/OWNER_RULINGS.md` است. Go امروز بخشی از FTS را دارد (`internal/fundamental.EvaluateV10`, `internal/chart.FTS`) اما Ruleset تکنیکال `"3"` است و Python `"6"` را گزارش می‌کند؛ قیف Go pass-through است و برخی مسیرها 501 هستند. علاوه بر آن، رفتار/نمایش FTS روی چارت باید با قواعد جزوه و خروجی محاسباتی تطبیق داده شود. هیچ‌یک از این پیاده‌سازی‌ها از پیش مرجع حقیقت نیست.

## Decision

1. `internal/oc/fts` یک **Adapter** است که Envelope می‌سازد؛ محاسبهٔ Runtime در Go انجام می‌شود، Python فقط Research/Oracle تست است و نمودار باید همان خروجی/Envelope مرجع را نمایش دهد. هیچ فرمول یا غربالگری موازی در OC یا Renderer ساخته نمی‌شود.
2. Envelope سه‌حالتی (`pass/fail/unknown` + `NA`)، `ruleset_version`, `config_hash`, `as_of.kind`, `coverage`, `provenance` را حمل می‌کند.
3. `/fts-screen` سطح کانونیکال مستقل می‌ماند؛ Today همان Envelope را مصرف می‌کند؛ هیچ غربالگری موازی ساخته نمی‌شود.
4. FTS Strategy در Library `engine=fts.canonical` است؛ Bundle آن فرمول ندارد، فقط Ruleset/Config/Approval/Evidence.
5. **دروازهٔ تطابق سه‌جانبه:** پیش از مصرف خروجی در Today/Stable، Rule Inventory از جزوه استخراج و رفتار چارت و خروجی Python/Go با Golden Vectors تطبیق داده می‌شوند. هیچ کدام به‌صورت پیش‌فرض درست فرض نمی‌شوند. تا رفع تمام اختلاف‌های حیاتی و ابهام‌های قواعد، Stub/501/Pass-through هرگز pass نیست و وضعیت `unavailable`/`not_parity_verified` نمایش داده می‌شود.
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

- `docs/جزوه FTS.pdf` — مرجع قواعد.
- `docs/fts-notes/OWNER_RULINGS.md` — احکام مالک.
- `api/chart.py:3896` — Ruleset 6.
- `backend-go/internal/chart/fts_swings.go:20` — Ruleset 3.
- رفتار FTS chart/overlays باید در P0.5 با سناریوهای مرجع ثبت و تطبیق شود.
- `backend-go/internal/funnel/funnel.go` — pass-through.
- `backend-go/internal/httpapi/server.go:225-291` — FTS/Funnel routes.
- Phase 2 §۸؛ `04-TECHNICAL-ARCHITECTURE.md` §۱۲.
