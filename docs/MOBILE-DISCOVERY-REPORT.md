# Mobile Discovery Report - BorsTerminal

این گزارش بر اساس تحلیل وضعیت فعلی کدهای موجود در Branch اصلی `arena/01a0f32b-borsterminal-src` تهیه شده است.

### A. Mobile current state
برنامه فعلی یک ساختار ترکیبی (Hybrid) بر پایه React/Vite و **Capacitor** است. پوسته اندروید در پوشه `frontend/android` قرار دارد و شامل تنظیمات پایه Gradle است. استایل‌های مختص موبایل در `mobile.css` پیاده‌سازی شده‌اند که شامل تنظیمات Safe-area و Navigation پایین صفحه است. قابلیت مدیریت دکمه Back سخت‌افزاری اندروید در `androidShell.ts` وجود دارد که از بسته شدن ناگهانی برنامه جلوگیری می‌کند و درخواست‌های خارجی از طریق درگاه بومی `nativeHttp.ts` (برای دور زدن محدودیت‌های CORS) مدیریت می‌شوند.

### B. Branch comparison
مقایسه `arena/01a0ea35` با `arena/01a0f32b` نشان‌دهنده تغییرات و پیشرفت‌های بسیار گسترده در برنچ `01a0f32b` است (بیش از ۱۴۳۰۰ خط اضافه شده در ۱۶۰ فایل). این تغییرات شامل اضافه‌شدن تست‌های حیاتی برای موبایل (مثل `android-back.spec.ts` و `mobile-portrait.spec.ts`)، استایل‌های موبایل، معماری `androidShell.ts`، و کامپوننت‌های جدید مثل `EliteFunnelHub.tsx` و همچنین سند استراتژی `ANDROID-PLAN.md` است. به همین دلیل، مبنا قرار دادن `01a0f32b` کاملاً منطقی و ضروری است.

### C. Android architecture
معماری اپلیکیشن بر اساس الگوی **Local-First** روی Capacitor بنا شده است:
- `webDir` به فولدر `dist` اشاره دارد.
- برای جلوگیری از دانلود مکرر دیتابیس ۲۲ مگابایتی (`mobile_snapshot.db.gz`)، داده‌ها به صورت آفلاین داخل WebView و از طریق `sql.js` (WebAssembly) اجرا می‌شوند.
- برای جلوگیری از تداخل سرور مجازی WebView با ریکوئست‌های خارجی، پلاگین سراسری `CapacitorHttp` غیرفعال شده و به جای آن از تابع اختصاصی `nativeHttp.ts` فقط برای ارتباط با سرورهای خارجی (TSETMC/GitHub) استفاده می‌شود.

### D. Current capabilities
- مدیریت دکمه Back (بستن Modals Radix با شبیه‌سازی کلید Escape، برگشت در تاریخچه، و خروج دو-مرحله‌ای).
- استایل‌های تطبیق‌پذیر برای Portrait/Landscape.
- واکشی داده‌های باینری، JSON، و Text از طریق `CapacitorHttp` در لایه Native.
- ساختار کامپوننت‌های FTS (مانند `FtsFunnelStages` و `EliteFunnelHub`) وجود دارد.

### E. Missing capabilities
بر اساس تحلیل کد و `ANDROID-PLAN.md`:
- عدم وجود `ErrorBoundary` (بروز خطا باعث ایجاد صفحه سفید کامل یا White Screen of Death می‌شود).
- اجرای `sql.js` روی Main Thread که باعث قفل شدن UI در زمان بارگذاری و کوئری‌های سنگین می‌شود.
- نبود نشانگر بارگذاری (Loading Indicator) در زمان استخراج و خواندن دیتابیس آفلاین.
- عدم پشتیبانی از مکانیزم Pull-to-Refresh.
- اتصال واقعی و Intersection قطعی در FTS (باید AND منطقی روی موبایل پیاده و تست شود).

### F. Broken capabilities
- رفتار و ابعاد چارت تکنیکال ممکن است در محیط موبایل فضای بیش‌ازحد اشغال کند یا دکمه‌های آن خارج از دید قرار بگیرند.
- ثبت خطاهای سراسری (Global Error Logging) وجود ندارد، بنابراین رفع باگ در دستگاه واقعی به شدت سخت است.
- Build اندروید به صورت محلی به دلیل عدم تنظیم بودن `JAVA_HOME` در محیط فعلی خطای اجرا می‌دهد، اگرچه کانفیگ‌های Gradle از نظر ساختاری سالم هستند.

### G. Mobile Strategy FTS
کامپوننت `FtsFunnelStages.tsx` پیاده‌سازی شده، اما طراحی و تجربه کاربری (UX) آن باید برای حالت موبایل بهینه‌تر شود. جریان عبور کاربر از مراحل `Universe -> S -> T -> F -> Delivery` باید خطی، خوانا و با قابلیت لمس‌پذیری بالا (Touch-friendly) باشد. تقاطع فیلترها (مانند `Suspicious Volume ∩ Code-to-Code`) نیازمند بررسی دقیق منطقی است تا اطمینان حاصل شود از عملگر AND به جای OR استفاده می‌شود تا نتایج فیلتر شده واقعی باشند.

### H. Build status
ساختار پوشه `android` صحیح و شامل فایل‌های Gradle و AndroidManifest است. با اجرای `./gradlew assembleDebug` به دلیل نبود JDK (یا تنظیم نبودن `JAVA_HOME` در این کانتینر ایجنت) پروسه Build متوقف می‌شود. در صورت تامین محیط جاوا، قابلیت بیلد (Build) وجود دارد. فعلا تغییراتی که به Build مربوط می‌شوند بدون تست کامل بیلد نهایی، پرخطر هستند.

### I. Proposed roadmap
برای رسیدن به محصول نهایی پایدار موبایل در ۴ الی ۵ اسپرینت:
1. **Sprint 1: Stability & UX Foundation (پایداری و زیرساخت کاربری):** پیاده‌سازی `ErrorBoundary`های سراسری، نشانگر لودینگ دیتابیس و لاگ خطاهای محلی. همچنین بررسی انتقال `sql.js` به Web Worker.
2. **Sprint 2: Strategy FTS Mobile (اصلاح قیف استراتژی):** بازطراحی مسیر `Funnel` برای موبایل با تاکید بر Intersection دقیق (AND) و رابط کاربری Touch-friendly.
3. **Sprint 3: Technical & Market Shell (چارت و تابلوی بازار):** بهینه‌سازی سایز چارت برای حالت Chart-First، اصلاح Toolbarها و ابزارهای رسم، و بهبود اسکرول جداول بازار. یکپارچگی جستجوی فارسی.
4. **Sprint 4: Android Polish & Edge Cases:** تست دقیق رفتار دکمه Back، Safe-area در حالت Portrait و Landscape، مدیریت کیبورد، و هندل کردن حالت‌های Background/Resume.
5. **Sprint 5: Build & Native Verification:** کامپایل خروجی APK (Debug/Release)، تست روی شبیه‌ساز/دستگاه واقعی، تایید کارکرد `nativeHttp.ts` بدون خطای CORS، و پولیش نهایی.

### J. First implementation sprint
**اسپرینت اول (تثبیت وضعیت - Stability):** طبق اولویت‌های مستند `ANDROID-PLAN.md`، کار را با پیاده‌سازی گاردها شروع می‌کنیم:
- اضافه کردن یک `ErrorBoundary` سراسری برای جلوگیری از Crashها و صفحه سفید.
- ایجاد **Loading Indicator** در زمان لود و آماده‌سازی دیتابیس `sql.js`.
- ایجاد سیستم گرفتن خطاهای سراسری (`window.onerror` و `unhandledrejection`) برای امکان عیب‌یابی داخل اپلیکیشن.
- در صورت نیاز، اصلاح `sql.js` برای جلوگیری از قفل شدن UI.

پس از تایید این گزارش، وارد اجرای Sprint 1 خواهیم شد.
