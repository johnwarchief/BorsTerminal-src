# ADR-OC-012 — امنیت API محلی و مرز دادهٔ شخصی/سه کاربر

- **وضعیت:** Accepted (Engineering) — پیاده‌سازی امنیت: P0
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** `docs/BorsTerminal-Desktop-Migration-Decisions.md:559-568` (OPEN)، A4/A12

## Context

`borsd` روی `127.0.0.1:8198` سرو می‌کند و Tauri یک URL خارجی را بار می‌کند. محلی‌بودن آدرس، هویت/همان‌مندی فراخواننده را ثابت نمی‌کند. دادهٔ شخصی (Watchlist/Portfolio/Workspace) محلی است؛ سه کاربر نباید آن را در Registry/Cloud ببینند. OC نوشتن محلی (فعال‌سازی) و API جدید دارد.

## Decision

1. `borsd` فقط Loopback یا IPC بومی؛ بدون Interface عمومی.
2. Token تصادفی per-launch؛ کوکی `HttpOnly; SameSite=Strict` یا فایل محدود؛ نوشتن‌ها نیازمند CSRF Header.
3. Origin/Host Strict؛ CORS بسته؛ `Origin: null` رد؛ Tauri `--url` محدود/همراه Token.
4. سه کاربر = سه نصب محلی مستقل؛ Registry فقط توزیع؛ هیچ دادهٔ شخصی/Telemetry به Owner/GitHub نمی‌رود.
5. Registry Index/Bundle هیچ Personal Data ندارد؛ Client فقط توکن خواندنی خود را به GitHub می‌فرستد.
6. `user.db` هرگز Snapshot/Registry نمی‌شود؛ Workspace در WebView Profile محلی می‌ماند.
7. Logها PII/Token/کلید چاپ نمی‌کنند.
8. هر نوشتن محلی (Activate/Deactivate/Rollback) Audit با دلیل دارد.

## Consequences

- یک Token per-launch ممکن است با Restart عوض شود؛ UI باید Bootstrap را مدیریت کند.
- Tauri Shell فعلی URL دلخواه می‌گیرد؛ باید محدود شود (P0).
- هیچ «حساب کاربری» مرکزی لازم نیست؛ GitHub فقط برای Registry Access.
- اگر بعداً چند دستگاه برای یک کاربر لازم شد، همگام‌سازی شخصی جداگانه و Opt-in می‌خواهد.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| CORS باز/Origin null | خطر CSRF/DNS Rebinding؛ رد |
| Auth کامل OAuth در Runtime | پیچیدگی/هزینه؛ برای محلی لازم نیست |
| سرور چندمستأجری برای ۳ کاربر | نقض معماری محلی؛ رد |
| UUID ساده به‌جای Token | قابل‌حدس/CSRF؛ رد |

## Evidence

- `backend-go/internal/config/config.go:10,24` — Loopback.
- `frontend/src-tauri/src/lib.rs:123-131` — External URL.
- `docs/BorsTerminal-Desktop-Migration-Decisions.md:559-568` — OPEN Local Channel.
- `04-TECHNICAL-ARCHITECTURE.md` §۱۴.
