# STATE — اسنپ‌شات سیستم (به‌روز: 2026-09-14 ۱۶:۰۰ محلی)

## Repo / سرور
- **master HEAD:** `bf373ec` (شامل همهٔ کارها + بستهٔ agent-system؛ سرِ آن `4f180ac` فیکس دراور بنیادی است)
- **خط پایهٔ تست:** ۴۰۸ سبز (۳۸ فایل) · eslint صفر · build سالم
- **سرور:** `python start_dashboard.py --port 8012` از ریشه (پایدار در این ماشین، PID متغیر)
- **دیتابیس:** market.db (≈۱۰۴MB، sync خودکار صبحگاهی) + codal.db در ریشه

## برنچ‌ها / ورک‌تری‌ها / سشن‌ها (ماشین مبدأ — روی ماشین جدید session id معنا ندارد)
| برنچ | ورک‌تری | HEAD | وضعیت | Session ID |
|---|---|---|---|---|
| agent/tape | silky-arch | da5268b | clean، مرج‌شده | e5f55980-77fb-4c98-9557-05099566f2ce |
| agent/fundamental | serene-mountain | 4f180ac | مرج‌شده | 7750c3e9-694a-477c-9eb9-7c127d81e56b |
| agent/technical | neat-plateau | 6d2c036 (+1 dirty) | **در حال کار** | 3f5fa69b-626f-4820-879c-3b31aaa419be |
| agent/master-portfolio | mellow-brook | 4177e24 | clean، مرج‌شده | ac6ab3ac-ae87-4507-a70d-d321e6034ccf |

## مأموریت باز (اگر迁移 وسط کار کردید، همین را re-dispatch کنید)
**T-01 · Technical · RightDock:**
```
۱) Read TechnicalPage.tsx
۲) components/RightDock.tsx جدید: سه تب (شاخص‌ها: macro.value_hemat + متریک ۲۰ همت + صادقانه «سری شاخص کل نیست»؛
   FTS: top-scored /api/screener با p_last/percent؛ تحرکات: f_susp/f_clock) + Radar (passes از /api/fundamental/{sym} + fib_zones/ستاپ /api/chart/{sym})
۳) symbol خالی ⇒ fallback اولین screener؛ چیدمان چارت + RightDock
۴) curl /api/chart/کانسار: بک‌اند سالم ⇒ فیکس feed؛ بک‌اند flat ⇒ گزارش
۵) vitest سبز (ریدایرکت) → eslint → build → commit "feat(technical): right dock watchlist + radar with default symbol fallback"
```

## گره‌های حل‌شدهٔ امروز (برای حفظ در refactors بعدی)
- Market menu → `createPortal` (بدون پکیج جدید) — Radix اضافه نکنید
- FtsSettingsDrawer → پنل `fixed inset-y-0 right-0` + backdrop (anchor-math حذف شد)
- `macro.value_hemat_all_market` از همان /api/mstat/smart-money
- Axis چارت: ایزوله LTR؛ سورت صعودی `a.time-b.time` قبل از feed
- طلا در targetAllocation: فیزیکی ۲۵ + صندوق/گواهی ۲۰ (جمع ۱۰۰٪)

## ریسک‌های محیط free-model
این ماشین چند بار zombie/quota دید (_pattern در PLAYBOOK). روی Hermes با مدل‌های پایدارتر این‌ها کمترند، ولی PLAYBOOK-ORCHESTRATOR را نگه دارید.


## به‌روزرسانی (ایجنتهد main — 2026-09-14 ~19:00)
- **agent/fundamental (F-01)** مرج شد: `git merge agent/fundamental` → `b261abe` (کارت خالی FTS + جای پنل تنظیمات). vitest ۴۰۸/۳۸ سبز، eslint صفر، build سالم.
- **فیکس سیستمیک `frontend/src/index.css`** (خارج قلمرو ایجنت‌ها، اعمال هد): کلاس‌های `.glass-panel/.glass-strip/.num/.panel-in/.scale-in/.conflict-pulse/.flash-up/.flash-down/.hud-beam/.neon-edge-cyan` داخل `@layer components` رفتند تا utilities تیلویند (`fixed/sticky/rounded-*`) دیگر باطل نشوند → Sidebar (sticky) و widgets/SymbolInspector (fixed) و کارت‌های rounded-* هم اصلاح شدند. کامیت `bf373ec`.
- ⚠️ **سرور 8012 الان از ریپوی `Desktop\BorsTerminal_Ultimate` (دیست قدیمی، 3:08PM) سرو می‌کند، نه از `_Base`.** برای دیدن فیکس‌ها یا سرور را از ریشهٔ `_Base` بالا بیاورید یا `frontend/dist` همان ریپو را rebuild کنید.
