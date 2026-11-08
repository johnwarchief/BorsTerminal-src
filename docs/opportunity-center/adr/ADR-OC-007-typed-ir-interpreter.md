# ADR-OC-007 — IR تایپ‌شده و Interpreter Go؛ بدون کد دلخواه

- **وضعیت:** Accepted (Engineering)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** OC-D-021

## Context

اجرای استراتژی‌های تولیدشده نباید به کد دلخواه، Plugin داینامیک یا مدل اجرایی غیرقابل‌حسابرسی منجر شود. Runtime Go است و بسته‌ها از Registry می‌آیند. قابلیت توسعه باید بدون شکستن بازتولیدپذیری و امنیت باشد.

## Decision

1. قرارداد `oc.strategy/1`: IR تایپ‌شده با پنج اسلات (Regime/Setup/Confirmation/Exit/Sizing) و پارامترهای Primitive.
2. Primitive Registry در Go کامپایل می‌شود؛ هر Primitive امضای تایپ‌شده، نسخه، Lookback، Schema و تست دارد.
3. Runtime فقط Interpreter است: بدون Exec، Plugin، `plugin.Open`، Reflection برای اجرای کد، File/Network I/O یا Seed غیرقابل‌بازتولید.
4. بستهٔ ناسازگار (Primitive ناشناخته/نسخهٔ Runtime) رد می‌شود؛ هیچ Fallback حدسی وجود ندارد.
5. Expression DSL آزاد در v1 مجاز نیست. اگر لازم شد، AST محدود با Whitelist و سقف عمق/زمان در ADR جدا.
6. ML/ONNX در مسیر Stable v1 نیست؛ مدل پیش‌بینی متعلق به Technical Intelligence است.
7. Hash IR روی Canonical JSON؛ پارامترهای پولی/درصدی رشتهٔ اعشاری.

## Consequences

- افزودن قابلیت جدید = Primitive جدید + نسخهٔ Runtime + انتشار اپ؛ مالک نمی‌تواند فقط با بستهٔ داده کد جدید اجرا کند.
- سطح حملهٔ Runtime کوچک می‌شود؛ اما انعطاف کمتر از کد آزاد است.
- FTS یک Primitive/Adapter ویژه است که قواعدش از کانونیکال می‌آید.
- تست‌های Determinism/Compatibility الزامی است.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| کد Python/JS در بسته | امنیت/بازتولیدپذیری/حجم؛ رد |
| Plugin داینامیک Go | نسخه/ABI/امنیت؛ رد |
| ONNX در v1 | وابستگی/مدل/اعتبارسنجی جدا؛ رد |
| IR آزاد بدون Primitive Registry | غیرقابل‌حسابرسی؛ رد |

## Evidence

- Phase 2 §۱.۳–۱.۷ (IR/اسلات‌ها).
- `DECISION-LOG.md` OC-D-021/OC-D-024.
- `04-TECHNICAL-ARCHITECTURE.md` §۸.
