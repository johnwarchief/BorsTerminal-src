# ADR-OC-011 — GPU موقت اختیاری و مجوز خروج داده

- **وضعیت:** Owner Sign-off Pending (Q15) — ساختار فنی Accepted
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **دستور مالک:** استفادهٔ اختیاری از GPU ابری موقت مانند Kaggle/Colab؛ بدون سرور/هزینهٔ میزبانی دائمی

## Context

آموزش مدل/جست‌وجوی سنگین می‌تواند روی CPU طولانی شود. GPU ابری موقت می‌تواند کمک کند، اما داده از ماشین خارج می‌شود و محیط ابری قابل‌اعتماد/تکرارپذیر کامل نیست. قاعدهٔ قبلی «هیچ داده‌ای خارج نمی‌شود» باید با این استثنای صریح و کنترل‌شده هم‌زیستی کند.

## Decision

1. پیش‌فرض CPU محلی است؛ GPU ابری فقط با اقدام صریح مالک برای یک Job.
2. `oc-owner gpu package` یک Job Bundle می‌سازد: Git SHA، Env Lock، Dataset Scope Hash، Params، Seed، Expected Outputs، Limits. دادهٔ شخصی هرگز وارد نمی‌شود.
3. Job State: `Draft → Packaged → Uploaded → RunningExternal → ArtifactsFetched → Verified → Imported`؛ خطا/timeout → `Failed` با Retry.
4. خروجی با Hash برمی‌گردد و در `research.db` ثبت می‌شود؛ تا Validation محلی + Approval مالک، Stable نیست.
5. هیچ Credential دائمی در Notebook/Cloud نیست؛ Token یک‌بارمصرف/محیطی.
6. محیط GPU (کتابخانه/درایور) در Manifest ثبت می‌شود؛ تکرارپذیری کامل ادعا نمی‌شود.
7. Confidentiality ابری تضمین نمی‌شود؛ مالک باید آگاهانه Scope را تأیید کند. Encryption at rest فقط انتقال/ذخیره را می‌پوشاند.
8. هیچ Background Upload/Sync وجود ندارد.

## Consequences

- وابستگی به سرویس خارجی برای Jobهای GPU؛ Timeout/محدودیت پذیرفته می‌شود.
- Data Governance نیاز به Review/Log دارد.
- مدل‌های آموزش‌دیده در v1 وارد Runtime نمی‌شوند؛ فقط Research Artifact.
- Kronos/پیش‌بینی متعلق به Technical Intelligence است و در این Jobها با Strategy Intelligence مخلوط نمی‌شود.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| GPU Cloud دائمی | هزینه/پیچیدگی/نقض فرض؛ رد |
| CPU-only اجباری | کند اما ساده؛ پیش‌فرض |
| GPU محلی در کلاینت | سخت‌افزار متغیر/نصب سنگین؛ رد برای v1 |
| ارسال خودکار داده | نقض حریم خصوصی؛ رد |

## Evidence

- دستور مالک ۲۰۲۶-۱۱-۰۸ بند ۲.
- `OPEN-QUESTIONS.md` Q15.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۳.
