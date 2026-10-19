# ممیزیِ ناوبری و شلوغیِ رابط — 2026-10-19

شاخه: `mission/uiux-nav-audit-2026-10-19` (پایه: `33f7d16f`، همان `github/main`).
هیچ merge به `main` و هیچ انتشارِ نسخه‌ای انجام نشد. اسکرین‌شات‌های خام در
`_audit/uiux-nav/` هستند (۲۳۶ PNG، چهار اندازه، در git نمی‌روند؛ ابزار
`tools/uiux_route_probe.mts` بازتولیدشان می‌کند).

## ۱) بند A — بازگشت/بعدی

- `shared/stores/navHistoryStore.ts` + `shared/lib/useNavHistorySync.ts` +
  `app/components/NavHistoryControls.tsx`؛ اتصال در `Topbar.tsx:59` و
  `AppShell.tsx:44`.
- مدل: PUSH/REPLACE/POP از `useNavigationType()` عمومی؛ `pathname+search`؛
  گاردِ دکمه‌ها از مدل، نه از `window.history.length`؛ `navigate(-1/1)`.
- شاهدِ زنده: `/market → /technical/فولاد → /notifications`؛ back/forward
  دقیق؛ شروعِ سرد در سه نشانی: هر دو دکمه خاموش و کلیکِ خاموش بی‌حرکت؛
  فوکوس پس از back روی `nav-back` و Tab به `nav-forward`؛ ۳۹۰px: عنوان ۶۸px.
- آزمون: `nav-history.spec.tsx` — ۱۵ تست؛ کلِ فرانت ۲۰۱۵ تست سبز.

## ۲) بند B — جدولِ ممیزی (نمونه‌های تصمیم‌ساز)

| Route | Component/File | Visible Element | Evidence | User Value | Classification | Proposed Action |
| --- | --- | --- | --- | --- | --- | --- |
| `/portfolio` | `PortfolioPage.tsx:195,210` | کامنتِ توسعه‌دهنده به‌صورت متن رندر شده | عکسِ ۱۳۶۶ | صفر | REMOVE_CANDIDATE | تبدیل به `{/* */}` |
| symbol routes | `app/components/SymbolContextStrip.tsx:49` | ۶ داده + ۵ پیوند؛ نوار در ۱۳۶۶ می‌شکند | ۶۵px @1366، ۳۸px @1600 | زمینهٔ نماد | SIMPLIFY | پیوندها در ≤۱۳۶۶ آیکنی با tooltip |
| `/notifications` | `NotificationsPage.tsx:190` | ۴ سطح + ۱۲ نوع همیشه باز | ۲۸۹ کنترل، ۱۰٬۳۲۳px زیر تاشو | فیلتر | SIMPLIFY | ۱۲ نوع در popover با شمارش فعال |
| `/notifications` | `NotificationsPage.tsx:104-121` | «منبع» و «خوانده شد» در هر کارت | ۱۲۰ کارت | بازکردن/خواندن | SIMPLIFY | آیکن + aria-label؛ هر دو عمل بماند |
| `/market-status` | `MarketPulseBar.tsx` | حکم + بندهای شرطِ بلند | ۳۰٬۷۰۳ کاراکتر صفحه | علت تصمیم | SIMPLIFY | حکم + علت اصلی بیرون، بقیه در expander موجود |
| `/master` | `FtsFunnelHeader.tsx` | پاراگراف انگیزه، گام/ورودی/عبوری، پوشش تکنیکال | ۲۰۴۳ → ۱۶۰۱ کاراکتر پس از پاک‌سازی | افزوده | KEEP پس از پاک‌سازی | — |
| `/sarkhati` | `SarkhatiPage.tsx` | ۸ چیپ هم‌وزن + متن فنی بلند | ۱۳۲۶ → ۱۲۰۲ کاراکتر پس از پاک‌سازی | مسیر | KEEP پس از پاک‌سازی | — |
| `/market-status` | `MarketStatusPanel.tsx:1-11` | ۵ چیپِ وضعیت/اتصال/تازگی | توضیحِ سه مفهومِ جدا در کد | حقیقتِ داده | KEEP | حذف نکنید |
| `/market-status` | `MarketSectionNav.tsx:121` | شمارهٔ مرجع در چیپ و سرصفحه | آزمون `market-status-sections:91` | نقشهٔ جزوه | KEEP | تکرار عمدی و pin‌شده |

اسکرین‌شات‌های کلیدی: `stage2final__master__1366x768__nosym.png`،
`detail__sarkhati__1366x768.png`، `stage2final__market__1366x768__nosym.png`.

## ۳) بند C — پاک‌سازیِ انجام‌شده

`FtsFilterPanel` (حذف «زنجیره» از متن و انتقال به title)، انتقال
`funnel-counts` به نوار جدول نتایج (`funnel-results-toolbar`)، حذف خطوط
تکراریِ سربرگ، یک‌جا شدنِ سوییچِ حالت کشف، راست‌چین‌شدنِ چیپ‌های تابلوخوانی،
سربرگِ سه‌فیلدی و پیشرفتِ قدم‌های سرخطی، و کشف‌پذیریِ «تب جدید».

## ۴) نام فیلتر

در این شاخه: «ورود پول هوشمند و کد به کد» و نسخهٔ کامل «ورود پول هوشمند و
کد به کد حقوقی به حقیقی» در شش نقطه + بک‌اند. دستورِ 2026-10-19 مالک
(«ورود» در ابتدا) بر متنِ قدیمی‌ترِ همین سند مقدم است.

## ۵) راستی‌آزمایی‌نشده

حالتِ بازارِ باز و جریان زنده، query string در مرورگر واقعی (فقط آزمون واحد)،
Command Palette در جاروب زنده، موبایلِ کامل، پیکسل‌های canvas چارت، و حالت‌های
خالیِ اعلان/پرتفوی/قیف.
