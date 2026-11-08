# ADR-OC-015 — زیرسیستم اعلان دسکتاپ: موتور Go، پل Tauri، مرکز اعلان

- **وضعیت:** Accepted (Engineering) — پیش‌فرض‌های محصول Owner Sign-off Pending (Q20–Q24)
- **تاریخ:** ۲۰۲۶-۱۱-۰۸
- **مرجع:** Phase 3 §۵.۹؛ `04-TECHNICAL-ARCHITECTURE.md` §۱۹؛ OC-D-064..073

## Context

الزام تازه، تجربه‌ای شبیه Telegram Desktop می‌خواهد: Toast بومی Windows، فقط رویدادهای مهم، تعامل، Dedup، Quiet Hours، مرکز اعلان دائمی و کارکرد در حالت Minimized/Background. وضعیت فعلی:

- Tauri `2.12.5` است اما `tauri-plugin-notification` در `Cargo.toml`، `Cargo.lock`، `lib.rs` و Capabilityها وجود ندارد؛ هیچ Command سفارشی/IPC تعریف‌شده‌ای هم ندارد.
- Webview یک URL خارجی `http://127.0.0.1:<port>` را بار می‌کند؛ افزودن Plugin از سمت JS نیازمند `remote` Capability است و سطح حمله را باز می‌کند.
- `borsd` هیچ Event Bus، SSE/WebSocket، Job Registry یا Rule Engine دائمی ندارد. سه Sync POST فقط پیام «شروع شد» می‌دهند.
- `internal/notifications` فقط Feed کدال است؛ موتور اعلان سیستم نیست.
- Alert قیمت در `frontend/` فقط در Renderer و وابسته به Polling است؛ با پنجرهٔ مخفی متوقف می‌شود (`docs/fts-notes/TA_PARITY_AUDIT.md:185-187`).
- `frontend-v2` مسیر `/notifications` و Badge دارد، اما Read State در localStorage است و هیچ Toast/تنظیمات سروری ندارد.
- `user.db` طبق قرارداد Stage 4 باید بایت‌به‌بایت سالم بماند؛ افزودن جدول شخصی جدید به آن مطلوب نیست.

## Decision

1. **مالکیت منطق در Go:** بستهٔ تازهٔ `internal/notify` رویدادها را اعتبارسنجی، طبقه‌بندی، Dedup/Aggregate، Rate Limit، Quiet Hours و در `oc_client.db` ثبت می‌کند. `internal/notifications` (Feed کدال) دست‌نخورده می‌ماند.
2. **چهار سطح:** `critical`, `important`, `normal`, `informational`. فقط Critical/Important واجد Toastاند؛ Normal فقط مرکز؛ Informational فقط تاریخچه/سطح مربوط. `signal.created` و `price.changed` هرگز Important نمی‌شوند؛ تنها استثنا `market.threshold_crossed` است که کاربر خودش Alert ساخته.
3. **مالکیت Toast در Rust:** `tauri-plugin-notification` (رسمی، نسخهٔ ۲، Pin در P1) در Shell راه‌اندازی می‌شود و فقط از Rust فراخوانی می‌شود. هیچ `remote` Capability برای `http://127.0.0.1` اضافه نمی‌شود؛ SPA نمی‌تواند مستقیماً Toast بسازد.
4. **پل Long-Poll:** Rust با Token فایل ACL‌دار روی `GET /api/oc/notifications/pending?after_seq&wait=25` Long-Poll می‌زند، `show()` می‌کند و `POST /{id}/ack` با `shown|failed|suppressed_os` می‌فرستد. پس از Ack با `webview.eval` یک `CustomEvent('bors:notification')` می‌فرستد؛ این یک Tauri Command نیست.
5. **ذخیره‌سازی در `oc_client.db`:** جداول `notification_events`, `notification_deliveries`, `notification_prefs`, `notification_mutes`. `user.db` دست‌نخورده می‌ماند؛ Watchlist/Portfolio در Event کپی نمی‌شود.
6. **Dedup/Aggregation/Rate Limit:** `dedupe_key` پایدار + `group_key` + `occurrence_count`؛ Toast فقط برای گذار وضعیت یا Digest؛ Token Bucket دسته‌ای/سراسری با سبد رزرو Critical؛ Dedup پس از Restart باقی می‌ماند.
7. **Quiet Hours/DND:** در Go اعمال می‌شود؛ رویداد در تاریخچه ثبت می‌شود اما Toast نمی‌شود. Critical فقط در صورت تنظیم صریح کاربر عبور می‌کند. ساعت محلی Windows مرجع است.
8. **مرکز اعلان:** `/notifications` با فیلتر/گروه‌بندی/خوانده‌شده/جزئیات و `/settings/notifications` با کنترل دسته/Severity/صدا/Preview/Quiet Hours. Badge پیش‌فرض Critical+Important خوانده‌نشده.
9. **حریم خصوصی:** Preview برای `portfolio`/`security` پیش‌فرض خاموش؛ متن ساده؛ بدون HTML/لینک خارجی؛ Deep Link فقط Allowlist داخلی؛ هیچ Token/Secret در Event یا لاگ.
10. **یکپارچگی:** هیچ متن خارجی (کدال) به‌تنهایی اعلان رسمی نیست؛ فقط Event داخلیِ Schema-validated و Source-allowlisted. هیچ AI مجاز به ساخت Critical/Important یا بالا بردن Severity نیست.

## Consequences

- یک وابستگی Rust و یک Capability حداقلی اضافه می‌شود؛ اما SPA به API سیستم‌عامل دسترسی ندارد.
- `oc_client.db` یک Migration تازه می‌گیرد؛ `user.db` سالم می‌ماند.
- Windows به AUMID/Shortcut معتبر و نصب واقعی نیاز دارد؛ Toast خارج از پوشهٔ نصب قابل‌اعتماد نیست. نصب‌کنندهٔ فعلی فقط Shortcut را به Go host می‌دهد؛ P1 باید Activation را به همان اپ برساند.
- وقتی برنامه کاملاً بسته است Toast ساخته نمی‌شود؛ تاریخچه در Startup بعدی از منابع بازخوانی می‌شود.
- Focus Assist/Notifications off همیشه قابل‌تشخیص نیست؛ وضعیت `suppressed_os` و پیام صادقانه جای ادعای «دیده شد» را می‌گیرد.
- Dedup/Rate Limit می‌تواند بعضی رویدادهای پرتکرار را فقط در مرکز نشان دهد؛ این رفتار عمدی است.

## Alternatives

| گزینه | ارزیابی |
|---|---|
| Plugin از سمت JS با `remote` Capability | نیازمند بازکردن Commandها به Origin محلی؛ سطح حمله و وابستگی به Timerهای Webview؛ رد |
| Toast مستقیم از Go با WinRT | تکرار منطق Shell، Activation/AUMID و Focus، دو پیاده‌سازی ویندوزی؛ رد |
| Alert در Renderer/SPA | با Minimized/Tray متوقف می‌شود؛ همان نقص فعلی؛ رد |
| Telegram/Bale به‌عنوان کانال اعلان | داده از دستگاه خارج می‌شود؛ Q14 و محدودیت مالک؛ خارج از v1 |
| Plugin غیررسمی/Third-party با Push (FCM/APNs) | سطح بیرونی و وابستگی اضافه برای نیاز محلی؛ رد |
| فقط مرکز اعلان بدون Toast | الزام «اعلان دسکتاپ واقعی» را برآورده نمی‌کند؛ رد |
| یک Severity برای همه | نویز و از دست رفتن رویداد مهم؛ رد |

## Evidence

- `frontend/src-tauri/Cargo.toml:24-37` — بدون Plugin اعلان؛ `src/lib.rs:106-108` — فقط Updater/Process؛ `capabilities/default.json:8-12` — بدون Permission اعلان.
- `frontend/src-tauri/tauri.conf.json:4` — `identifier=com.borsterminal.app`؛ `installer/bors_setup.iss:81-82` — Shortcut فقط برای Go host.
- `backend-go/internal/httpapi/server.go:341-343` — SSE «آینده»؛ `internal/sync/handlers.go:93-133` — Sync no-op؛ `internal/notifications/` — فقط Feed کدال.
- `frontend-v2/src/app/App.tsx:20` — `/notifications`؛ `Sidebar.tsx:82-95` — Badge؛ `features/notifications/lib/unread.ts:34-51` — Read State در localStorage.
- `frontend/src/features/technical/stores/priceAlertStore.ts:97-141` — Alert فقط Renderer؛ `docs/fts-notes/TA_PARITY_AUDIT.md:185-187` — توقف Polling با پنجرهٔ مخفی.
- `docs/BorsTerminal-Desktop-Migration-Decisions.md:86, 368-374, 440` — تصمیم‌های اهمیت/مرکز رویدادها؛ `docs/RELEASE_NOTES.md:705-711` — اعلان ویندوز وصل نیست.
- Tauri v2 Notification Plugin (رسمی): https://v2.tauri.app/plugin/notification/ — بررسی ۲۰۲۶-۱۱-۰۸؛ وجود Plugin و پشتیبانی از Action/Tap در Desktop طبق مستندات رسمی/`docs.rs` تأیید شد. دسترسی مستقیم صفحه در این محیط محدود بود؛ نسخهٔ دقیق Pin، Permissionهای نهایی و Payload کلیک در P1 با Toast واقعی تأیید می‌شود.

## Acceptance

- هیچ `remote` Capability برای Webview اضافه نشده باشد.
- Toast در Minimized/Tray واقعاً دیده شود؛ کلیک به Deep Link معتبر برسد.
- خاموش‌بودن اعلان سیستم‌عامل تاریخچه را از بین نبرد.
- `signal.created`/`price.changed` هیچ Toastی نسازند.
- پس از Restart، Toast تکراری و رویداد گم‌شده نباشد.
- `user.db` بایت‌به‌بایت سالم بماند.
