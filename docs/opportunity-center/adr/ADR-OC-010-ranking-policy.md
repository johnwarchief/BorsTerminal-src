# ADR-OC-010 — Ranking Policy به‌عنوان دادهٔ امضاشده؛ بدون Score مرکب

- **وضعیت:** Owner Sign-off Pending (Q11) — ساختار فنی Accepted
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** OC-D-024/035/039; Phase 2 §۴.۳

## Context

رتبه‌بندی Today باید قابل‌توضیح باشد و روش‌های ناهمگون را به یک امتیاز مبهم تقلیل ندهد. ترتیب/ابعاد به ریسک‌پذیری و روش کار مالک وابسته است. Runtime نباید ترتیب را در کد ثابت کند.

## Decision

1. `oc.ranking_policy/1` یک سند امضاشده است؛ Runtime فقط Comparator را اجرا می‌کند.
2. ساختار: `dimensions[]` با `key/direction`، `tie_breakers[]`، `exclusions[]`؛ بدون Weight/Score/جمع.
3. هر ردیف `rank_trace` دارد: مقدار ابعاد، بعد تعیین‌کننده، Tie-breaker، Policy Hash.
4. پیشنهاد v1: `freshness desc → strategy_trust desc → evidence_coverage desc → liquidity_participation desc → signal_time desc → symbol asc`؛ «نزدیکی به ابطال» هشدار است، نه معیار رتبه.
5. Policy غایب/نامعتبر ⇒ Fallback شفاف `freshness desc, symbol asc` با برچسب `fallback`.
6. `incomparable`/`not distinguishable` نتیجهٔ معتبر است؛ رتبهٔ پایین نیست.
7. تغییر Policy بدون تغییر کد/بسته ممکن است؛ Audit و UI Policy Hash را نشان می‌دهد.

## Consequences

- مالک می‌تواند ترتیب را بدون Release تغییر دهد؛ اما تغییر Policy باید امضا شود.
- Lexicographic می‌تواند در مواردی «کاملاً برابر» بدهد؛ Tie-breaker پایدار لازم است.
- Policy باید فقط از فیلدهای موجود در Read Model استفاده کند؛ Validator در Load.
- هیچ Radar Area/Star/Composite در UI نیست.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| Composite Score | تصمیم مالک را نقض می‌کند؛ رد |
| Hardcode ترتیب | تغییر سخت؛ رد |
| رتبهٔ تصادفی/زمانی | غیرقابل‌توضیح؛ رد |
| Probabilistic dominance برای Today | سنگین/نیازمند شواهد بیشتر؛ برای Compare نگه داشته می‌شود |

## Evidence

- Phase 2 §۴.۳ (Dominance/Profile/Lexical/Probabilistic).
- `03-UX-AND-PRODUCT-EXPERIENCE.md` §۵.۱.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۱.۳، §۱۸.۳.
