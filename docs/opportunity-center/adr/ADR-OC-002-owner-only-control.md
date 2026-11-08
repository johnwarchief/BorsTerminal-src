# ADR-OC-002 — کنترل، تأیید و انتشار فقط روی سیستم مالک

- **وضعیت:** Accepted (Owner instruction, 2026-11-08)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **تصمیم‌گیرنده:** مالک محصول؛ پیاده‌سازی معماری Opportunity Lab

## Context

سه کاربر مصرف‌کنندهٔ نسخه‌های تأییدشده‌اند. اگر تأیید/انتشار در کلاینت یا CI ممکن باشد، مرز اعتماد و «تأیید انسانی» از بین می‌رود. مدل‌های AI نیز فقط پیشنهاد می‌دهند و نباید بتوانند انتشار را آغاز یا امضا کنند.

## Decision

1. آموزش، تکامل، اعتبارسنجی نهایی، تأیید (Stable) و انتشار فقط روی سیستم مالک انجام می‌شود.
2. کلاینت هیچ Endpoint یا کلید خصوصی برای Approval/Publication ندارد؛ فقط Registry را می‌خواند و نصب/فعال‌سازی محلی می‌کند.
3. `oc-owner` تنها ابزار ساخت Approval و Bundle است؛ اجرای آن نیازمند Unlock تعاملی کلید و تأیید صریح است.
4. `APPROVAL_KEY` روی سیستم مالک و آفلاین نگهداری می‌شود؛ در CI، Research Job، Notebook، Client یا Registry نیست.
5. AI/Research Engine فقط `ai_suggestions` و Candidate تولید می‌کند؛ برای تبدیل به Stable باید انسان Hypothesis/Version را ثبت کند، Validation اجرا شود و مالک Approval را امضا کند.
6. Registry فقط بسته‌های دارای Approval امضاشده و `stable` را تبلیغ می‌کند.
7. سه کاربر نقش Approver ندارند؛ فقط مصرف‌کننده‌اند.

## Consequences

- Owner Workstation یک Single Point of Trust است؛ از دست رفتن کلید/دستگاه، انتشار را متوقف می‌کند (Recovery با Backup/Key Ceremony).
- هیچ «Auto-Approve» یا «Auto-Publish» در محصول وجود ندارد، حتی اگر Validation سبز باشد.
- انتشار می‌تواند آفلاین امضا و بعداً Upload شود؛ Approval و Publication دو مرحله‌اند.
- دسترسی سه کاربر به Registry، به آن‌ها اجازهٔ تأیید نمی‌دهد.

## Alternatives

| گزینه | چرا رد شد |
|---|---|
| تأیید در کلاینت با تأیید مالک | توزیع کلید/اعتماد و خطر جعل |
| تأیید در CI با Secret | CI قابل‌تغییر و خارج از کنترل تعاملی مالک |
| Auto-Approve پس از Validation | نقض تصمیم مالک و مدل شواهد |
| Dual-control سه کاربر | کاربران مصرف‌کننده‌اند؛ مدل حاکمیت تغییر می‌کند |

## Evidence

- دستور مالک ۲۰۲۶-۱۱-۰۸ (بندهای ۱، ۳، ۷).
- `DECISION-LOG.md` OC-D-024/OC-D-044/OC-D-049.
- `04-TECHNICAL-ARCHITECTURE.md` §۵، §۱۰، §۱۴.
