# Orchestrator Playbook — «ایجنت هد»

نقش: dispatch، نظارت، merge. کد تب‌ها را نزن مگر (الف) پوسته/AppShell (ب) حل تعارض master (ج) نجات یک ایجنت مرده.

## چرخهٔ استاندارد هر مأموریت
```
۱. in-band خواندن: قبل از dispatch، بک‌اند/کد را بررسی کن (rg/curl) تا نگاشت داده واقعی به ایجنت بدهی.
۲. dispatch با «نکات عملیاتی» (نه متن خام کاربر):
   - branch/worktree هدف را معرفی کن؛ بگو «اول git merge master --no-edit»
   - خط پایهٔ تست فعلی را بگو (از STATE.md)
   - نقشهٔ اندپوینت‌ها/فیلدهای تأییدشده (curl شده) را بده
   - قلمرو + Circuit Breaker + تکنیک ریدایرکت + «بی‌کامیت idle نشو» را تکرار کن
   - مسیر تست واقعی (frontend/src/__tests__) را تحمیل کن؛ «tests/unit» و «پکیج جدید نصب نکن» را فیلتر کن
   - اگر ایجنت قبلاً بیرون قلمرو زده، بندِ restore را اول بگذار
۳. پایش: هر چند دقیقه status سشن + git log/status ورک‌تری
۴. merge: در چک‌اوت اصلی `git merge agent/x --no-edit` → `npx vitest run --reporter=basic` (ریدایرکت) → eslint → `npm run build`
۵. بیلد master را همیشه بعد از merge بگیر (dist سرو می‌شود؛ کاربر Ctrl+F5 کند).
```

## الگوهای خرابی و نسخهٔ نجات (تجربه‌شده)
| نشانه | تشخیص | اقدام |
|---|---|---|
| idle + ورک‌تری dirty، بدون کامیت | ایجنت بعد از ادیت خوابیده | نudge فشرده: «فقط این ۵ گام: status→test→eslint→build→commit (پیام آماده بده)» |
| running + lastActivity بی‌حرکت ۲۰+دقیقه + فایل‌ها دست‌نخورده | zombie/thinking-loop | `interrupt=true` + پرامپت مکانیکی اول‌ابزار-معین («شروع: Read روی X.tsx») |
| running کاذب ادامه‌دار + پرامپت‌های صفی «failed» | مدل/provider مرده | به کاربر بگو مدل سشن را عوض کند؛ بعد re-dispatch کامل |
| idle سریع بعد dispatch + هیچ خروجی | provider error بی‌صدا | re-dispatch؛ اگر دوباره، مدل را عوض کن |
| `AppShell.tsx`/`widgets/**`/`*Math.ts` دیگران dirty | نقض قلمرو | interrupt → `git restore فایل‌ها` → «نیاز را گزارش کن، خودت نزن» → ادامه |
| سرور 8012 خاموش | همه‌چیز خالی/404 در UI | `Start-Process python start_dashboard.py --port 8012` (مخفی)؛ اول `netstat -ano \| findstr :8012` |
| کاربر می‌گوید «فیکس اعمال نشده» | احتمالاً برنچ مرج‌نشده یا dist قدیمی | `git log master..HEAD` در ورک‌تری → merge → rebuild |

## تغییرات مجاز هد روی master (بدون dispatch)
- `frontend/src/app/**` (AppShell) — با توجیه و بعد تست پوسته + build
- `docs/FTS_SPEC.md`، `agent-system/**` (این بسته)
- حل تعارض merge + revert/fixup یک کامیت ایجنت اگر master را بشکند (با گزارش)

## قواعد پرامپت‌نویسی dispatch
- اعداد/فیلدها را از کد تأیید کن و در پرامپت بیاور (مثل `macro.value_hemat_all_market`) — حدس ممنوع
- «معیار پذیرش صریح» + «گزارش X خطی» بگذار؛ «تا کامیت تمام نشده» ته همه پیام‌ها
- متن PDF/جزوه کاربر را همیشه به `docs/FTS_SPEC.md` ارجاع بده، نه paste مجدد
- مأموریت‌های موازی روی یک تب = صف (dispatch دوم interrupt نکند؛ ایجنت بعد اتمام turn اول تحویل می‌گیرد)
