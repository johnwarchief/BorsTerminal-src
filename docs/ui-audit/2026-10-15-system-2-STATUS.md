# وضعیتِ مأموریتِ ممیزیِ UI — system‑2 (۱۴۰۵‑۱۰‑۲۳ / 2026‑10‑15)

> اینِ سند **وضعیتِ واقعیِ یکِ کارِ نیمه‌تمام** را ثبت می‌کند تا ازِ همانِ نقطه ادامه
> شود. مأموریتِ جاری «تحویلِ کارها به GitHub» است؛ پس اینجا هیچِ ادعایِ تکمیلِ
> مأموریتِ UI نمی‌شود و هیچِ آزمونی که اجرا نشده PASS خوانده نمی‌شود.
> رأیِ اینِ شاخه: **IN_PROGRESS** (۶ اصلاحِ تأییدشده درِ کد + جاروبِ ناقص).

- Branch: `mission/ui-audit-system-2-2026-10-15`
- Base HEAD پیش از اصلاحات: `165bdca` (same tip as `mission/fts-indicator-engineering`)
- Worktree: `C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/ui-audit-system-2`
- راویِ سنجش: Edge ازِ راهِ playwright-core درِ `frontend/node_modules`، پروفایلِ موقتِ خودِ harness (نه پروفایلِ مالک)

## ۱) محیطِ سنجش (مرحلۀِ ۲ — فقطِ حالتِ شبیه‌سازی اندازه‌گیری شد)

| قلم | مقدارِ واقعیِ پنل | حالتِ em (Playwright) |
|---|---|---|
| رزولوشنِ فیزیکی | ۱۳۶۶×۷۶۸ @۵۹Hz (Intel HD 3000) | — |
| مقیاسِ ویندوز | ۱۰۰٪ (AppliedDPI = ۹۶) | — |
| DPR | ۱ | `1` |
| CSS viewport | — | `1366×768`، `visualViewport.scale = 1` |
| زومِ مرورگر | — | `100٪` (zoomEstimated) |
| root font‑size | ۱۶px | ۱۶px (`remUnitPx` = ۱۶۰ برایِ ۱۰rem) |
| نسخه‌ها | backend `APP_VERSION = 1.0.86`، نشانۀِ UI «FTS v2.1» | همان |

**هنوز اندازه‌گیری نشده:** `--mode=real` (پنجرۀِ بیشینۀِ واقعی رویِ همانِ پنل) و
`outerWidth/Height` درِ حالتِ واقعی. اینِ دو درِ مرحلۀِ ۲ مأموریتِ UI لازم‌اند و
درِ اینِ شاخه **NOT RUN**‌اند.

## ۲) چه چیزی درِ کد اصلاح شد (همۀ باِ شاهدِ عددیِ قبل/بعد)

| # | ایرادِ اندازه‌گیری‌شده | ریشۀِ کد | اصلاح | شاهدِ بعدِ اصلاح |
|---|---|---|---|---|
| ۱ | هیچِ لایۀِ چسبانی نمی‌چسبید؛ باِ اسکرولِ ۶۰۰px، `Topbar` بهِ `top=-825` رفت و سایدبار و ناوبریِ بخش هم باِ صفحه خارج شدند | پوسته `min-h-screen` بود و خودش قد می‌گرفت ⇒ **سندِ مرورگر** اسکرول می‌کرد، نه `.app-content` | `AppShell.tsx`: `min-h-screen` → `h-dvh` | `_audit/ui/AFTER1b_STICKY_marketstatus.txt`: `window.scrollY=0`, `.app-content` = ۰/۷۲۷۵ و `header … top=0 bottom=36` |
| ۲ | ارتفاعِ `Topbar` بهِ محتوا افت می‌کرد: ۲۵px درِ `/market-status`، ۳۲px درِ `/technical`، ۳۶px درِ `/market` ⇒ ۱۱px شکافِ شفافِ وسطِ نوارها | فرزندانِ ستونیِ `.app-content` `flex-shrink:1` داشتند و صفحه‌هایِ بلند آنها را می‌چلاندم | `shrink-0` بهِ `Topbar.tsx` و `SymbolContextStrip.tsx` | `ENV_em_picked_after2.json`: درِ هرِ چهار route ارتفاعِ هدر = **۳۶** |
| ۳ | ناوبریِ بخش‌ها (`sticky top-0 z-20`) هنگامِ چسبیدن **زیرِ** هدرِ `z-40` می‌رفت؛ `elementFromPoint` می‌گفت `COVERED ← by header` | عددِ ثابتِ `top-0` بدونِ احتسابِ پشتهٔ بالایِ صفحه | token درِ `index.css` (`.app-content { --chrome-h: 2.25rem }`) + `top-[var(--chrome-h)]` درِ `MarketSectionNav.tsx` | `sticky_probe`: `VISIBLE [t=market-section-nav] top=36 bottom=74` |
| ۴ | نوارِ نماد اگر چسبان می‌ماند پشته را نامعلوم می‌کرد (باِ داورِ باز ۶۵px، بی‌داور ۳۸px — `flex-wrap`) و ارتفاعِ چسبانِ ناوبری/عنوان را نمی‌شد ثابت گرفت | عددِ `top-9` فرضِ ۳۸px داشت | نوارِ نماد ازِ چسبان بودنِ موقتاً خارج شد (`sticky top-9` → `relative`)؛ نمادِ انتخابی همانِ‌جا درِ breadcrumbِ `Topbar` می‌ماند | پشتهٔ چسبان حالا همیشه ۳۶pxِ قطعی است؛ عنوانِ بخش درِ `y=82` می‌نشیند |
| ۵ | خودِ ناوبریِ بخش رویِ ۹۵۸px دوخطه می‌شد (h=۶۷) و ارتفاعِ چسباننش ثابت نبود | `flex-wrap` | تک‌ردیفه باِ `overflow-x-auto` (دکمه‌ها پاک نشده‌اند، افقی جابه‌جا می‌شوند) | `ENV_em_picked_after2.json`: ناوبری h=**38**، و `SWEEP_refine.json` بدونِ `UNDER-STICKY` |
| ۶ | `scroll-mt-24` (۹۶px) باِ پشتهٔ واقعیِ ۳۶px همخوان نبود؛ پرشِ بخش عنوان را زیرِ هدر می‌برد | عددِ hard‑coded | `scroll-mt-[calc(var(--chrome-h)+2.875rem)]` | `SWEEP_refine.json`: هرِ هفت عنوان درِ `y=82` (۳۶ هدر + ۳۸ ناوبری + ۸ فاصل) |
| ۷ | ۱۰۲px ازِ پایینِ چارتِ «وضعیت بازار» بریده و **غیرقابلِرس** بود: میزبان `h-[420px]` باِ `overflow-hidden`، کنتینرِ موتور `min-height:520px` | دو عددِ مستقل که بهِ هم بند نبودند | `MarketChartSection.tsx`: `CHART_H = h-[520px]` | `sticky_probe` دیگر `CLIP-Y div[t=ms-chart-host]` گزارش نمی‌کند |

نتیجهٔ جاروبِ بخش‌به‌بخشِ `/market-status` بعدِ اصلاحات (`SWEEP_refine.json`، ۱۰ بخش):
هیچِ `TITLE-UNDER-BAND`، `CLIPPED` یا `UNSCROLLABLE` نمی‌ماند؛ فقطِ `below-fold`
(زیرِ تا، باِ اسکرولِ صفحه قابلِرس) درِ بخش‌هایِ بلندِ ۵ وِ ۷.

نتیجهٔ جاروبِ صفحۀِ کاملِ **۲۱ route** (`LAYOUT_em_after2.txt`): `ovX=0px` و
`hardClip=0` و `offscreen(unreachable)=0` درِ همه؛ همه باِ نشانۀِ درستِ
`ready=marker` (نشانۀِ غلطِ قبلی درِ `_audit/ui/READY_PROBE.json` اصلاح شد:
`tape-row` درِ اینِ نشست ۲۵ ردیف دارد نه ۳۰، و `master-breadcrumb` فقط رویِ
`/master/<symbol>` است).

## ۳) یافته‌هایِ باز — **اصلاح نشده**، دقیقاً همانِ جا که متوقف شد

| # | یافته | شواهد | چرا باز ماند |
|---|---|---|---|
| a | درِ `/technical/فولاد` باِ نمادِ انتخاب‌شده، `chart-area` درِ `y=109` باِ ارتفاعِ ۶۹۲ ⇒ لبۀِ پایینِ چارت ۳۳px بیرونِ viewport است (کلِ workbench ≈۵۳px) | `INTERACT_all.json` (دوِ قدمِ تایم‌فریم، `OUTSIDE bottom=33`) | ریشه: `h-[calc(100dvh-3rem)]` درِ `TechnicalPage.tsx:260` فقطِ هدرِ ۳۶px را حساب می‌کند و نوارِ نماد/داور را نه. اصلاحِ درست زنجیرۀِ `min-h-0` ( `.app-main` → `.panel-in` → ریشۀِ صفحه ) است، نه عددِ جادوییِ دوم. مرحلۀِ ۵ مأموریتِ UI |
| b | کلیکِ `open-chart-settings` درِ ۸ ثانیه انجام نشد؛ elementFromPoint گفت مسیرِ کلیک را `fts-settings-btn «⚙تنظیمات»` گرفته است | `INTERACT_all.txt` سطرِ «دیالوگِ تنظیماتِ چارت» | هنوز معلوم نیست هم‌پوشانیِ واقعی است یا جابه‌جاییِ لحظه‌ایِ نوارِ ابزار؛ نیازمندِ آزمونِ overlap درِ همانِ حالت |
| c | `Escape` داورِ نماد (SymbolInspector) را نبست («OPEN, NOT‑RESTORED»)، در حالی که هرِ سه مودالِ سراسری باِ Escape بسته شدند و فوکوس داخلِ لایه ماند | `INTERACT_all.json` قدم‌هایِ global و tape‑row | بستنِ داور باِ دکمۀِ خودش تست نشده؛ باید روشن شود آیا Escape باید کار کند یا نه |
| d | `/api/fundamental/خوز` هرِ بارِ مراجعه HTTP 404 می‌دهد و UI درستِ حالتِ «نماد خوز درِ کدال صورتِ مالی ندارد» را می‌نشاند؛ `/api/index/tedpix` باِ `ERR_ABORTED` | `LAYOUT_em_after2.json` (سطرهایِ network) | رفتارِ رابط **درست** است؛ تکرارِ درخواستِ ۴۰۴‑شدنی درِ هرِ navigation یکِ هزینهِٔ تکراری است (مرحلۀِ ۵) |
| e | **۱۳ قدمِ تعاملی هیچ‌وقت سنجیده نشد** (NO‑TRIGGER/NOT‑VERIFIED): زیرتبِ معیارِ دوناتِ طلا، بازۀِ مقایسه، انتخابِ نمادِ نمودار، تبِ دومِ تنظیماتِ چارت، منویِ موتور، مودالِ تحلیل‌گر، پری‌ستِ استراتژیک، جست‌وجویِ غربالگری، مودهایِ مستر، سبدِ پرتفوی، فیلترِ نوعِ اطلاعیه، زنگِ هشدارِ قیمیتی | `INTERACT_all.txt` | دوِ علتِ harness (نه محصول): انتظارِ ثابتِ ۳٫۲ ثانیه برایِ بارگذاری (صفحه‌هایِ سنگین بیشتر می‌برند) و گزینشِ حدسیِ سلکتورها. راه‌حلِ مستند: منتظرِ خودِ دستگیره بنشیند، نه زمان |
| f | جاروبِ حالتِ واقعیِ نمایشگر (`--mode=real`) و آزمونِ ترازبندیِ افقی درِ پنجرۀِ واقعی | — | اجرا نشد؛ پس هیچِ ادعایی «رویِ نمایشگرِ واقعی هم درست است» ساخته نمی‌شود |
| g | سندِ نهاییِ مرحلۀِ ۷ مأموریتِ UI (`docs/ui-audit/2026-10-15-system-2.md`) باِ تصاویرِ قبل/بعد | ۱۶۸ گرفتنیِ PNG (≈۲۰ مگابایت) درِ `_audit/ui/shots/` | `*.png` درِ `_audit/.gitignore` است و عمداً منتشر نشد (سنگینِ مخزن). تصاویرِ گزینۀِ فشرده باید بهِ `docs/ui-audit/` برود |
| h | مرحلۀِ ۴ (پوششِ ماژول‌به‌ماژولِ ابزارهایِ رسم، اندیکاتورها، پخشِ مجدد، فرمِ سفارشِ کاغذی) | — | شروع نشده؛ فقطِ لایه‌هایِ FTS/چارتِ تکنیکال دیده شدند. آزمونِ «سفارشِ واقعی» هرگز اجرا نمی‌شود |

## ۴) گیت‌هایی که برایِ همینِ تحویل اجرا شدند (تازة، رویِ همینِ ۶ فایلِ تغییریافته)

| گیت | نتیجه | یادداشت |
|---|---|---|
| `python dev/persian_glyph_guard.py` | **4 passed / 0 failed** | بعدِ افزودنِ توضیحاتِ فارسی |
| `npx tsc -b` | **exit 0** (۴۷ ثانیه) | — |
| `npx vitest run` رویِ ۵ فایلِ مرتبط | **5 files / 55 tests passed** | `app-shell`, `market-status-sections`, `round78-ux`, `ux-round79`, `market-gold-compare-chart` |
| `npm run build` (vite) | **built in 16.4–18.3s** | سه بارِ build برایِ سنجشِ قبل/بعد |
| `npx vitest run` (کلِ ۱۶۷ فایل / ۱۷۱۳ آزمون) | **STALE** | آخرین اجرایِ سبز متعلق بهِ پایهٔ `165bdca` است؛ بعدِ اینِ ۶ تغییرِ فایل دوباره اجرا نشده |
| `python dev/run_all_tests.py` (۱۱۴ suite) | **NOT RUN** درِ اینِ شاخه | نیازمندِ خاموش‌بودنِ سرویس‌هایِ dev است؛ برایِ نشرِ سند/شاخه لازم نبود |

## ۵) راهنمایِ بازتولیدِ شواهد

بک‌اندِ همینِ worktree باید رویِ `127.0.0.1:8000` باشد (خودش `frontend/dist` را
می‌دهد؛ پس بعدِ هرِ تغییرِ UI اول `cd frontend && npm run build`):

```bash
MSYS_NO_PATHCONV=1 node _audit/ui/ready_probe.js                  # نشانۀِ درستِ هر route
MSYS_NO_PATHCONV=1 node _audit/ui/env_probe.js   --mode=em        # viewport/DPR/پشتهٔ چسبان
MSYS_NO_PATHCONV=1 node _audit/ui/env_probe.js   --mode=em --pick=1   # باِ نمادِ انتخاب‌شده
MSYS_NO_PATHCONV=1 node _audit/ui/env_probe.js   --mode=real      # NOT RUN (مرحلۀِ ۲)
MSYS_NO_PATHCONV=1 node _audit/ui/sticky_probe.js --route=/market-status --scroll=0,600,2500 --click=ms-sec-orders
MSYS_NO_PATHCONV=1 node _audit/ui/section_sweep.js --max=12        # جاروبِ بخش‌به‌بخش
MSYS_NO_PATHCONV=1 node _audit/ui/layout_audit.js --mode=em        # سطحِ صفحه (۲۱ route)
MSYS_NO_PATHCONV=1 node _audit/ui/interact_audit.js                # باز/بسته + فوکوس + Escape
```

نامِ کاربری/رمزِ ورود درِ harness هیچ‌جا نوشته نشده؛ ازِ `authStore.ts` درِ زمانِ
اجازه خوانده می‌شود و درِ هیچِ فایلِ `_audit/ui/*` ذخیره نمی‌شود (جاروبِ الگو:
۰ باندۀِ credential درِ ۳۳ فایلِ منتشرشده).

## ۶) آنچه درِ اینِ شاخه هست

- `frontend/src/app/layouts/AppShell.tsx` — قفلِ ارتفاعِ پوسته (۱)
- `frontend/src/app/components/Topbar.tsx` — `shrink-0` (۲)
- `frontend/src/app/components/SymbolContextStrip.tsx` — `shrink-0`، خارج ازِ چسبان، `data-chrome` (۲،۴)
- `frontend/src/features/market/components/MarketSectionNav.tsx` — چسبیدنِ زیرِ پشته + تک‌ردیفه + `scroll-mt` (۳،۵،۶)
- `frontend/src/features/market/components/MarketChartSection.tsx` — ارتفاعِ میزبانِ چارت (۷)
- `frontend/src/index.css` — توکنِ `--chrome-h`
- `frontend/dist/**` — buildِ تازةِ محلی، **منتشرشده نیست** (`dist/` درِ `.gitignore`)
- `_audit/ui/**` — هارنس‌ها (۷ فایلِ js)، خروجی‌هایِ JSON/TXT و شاخۀِ `TESTID_INVENTORY.txt`؛ PNGها منتشر نشده‌اند (گ)
- `_audit/ui-gates/**` — سه فایلِ متنیِ baseline گیت
