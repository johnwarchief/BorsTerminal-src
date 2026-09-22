---
name: bors-frontend-ui-guard
description: قواعد UI/جدول‌های BorsTerminal — قبل از تغییر کامپوننت‌های تابلو/بنیادی/نبض بازار بخوان: تراز ستون‌ها، ارقام فارسی، جهت RTL، قواعد FSD و ESLint، و الگوی «مقدار+نشان» در جدول FTS.
---

# bors-frontend-ui-guard — گارد رابط کاربری BorsTerminal

رابط کاربری React 18 + TS + Vite + Tailwind v4 با معماری Feature-Sliced Design است.
لایه‌ها: `app / shared / contracts / widgets / features-{market,fundamental,technical,portfolio,master}`.
ماتریس import توسط ESLint (`boundaries/element-types`, `default: 'disallow'`) اجباری است؛ `fetch` بیرون از
`shared/api/http.ts` و `features/*/api/` ممنوع است (`no-restricted-syntax`).

## قواعد سخت (نقض نکن)

1. **تراز ستون‌های عددی:** در جدول‌ها مقدارِ عددی باید در اسلات ثابتِ چسبیده به لبه‌ی `start` رندر شود
   (`flex-1 text-start`) و **بعد** از آن نشان (✓/✗/برچسب شکاف) بیاید — نه برعکس. اگر نشان جلوتر باشد،
   چون عرض برچسب‌ها per-row تفاوت دارد، اعداد زیر هدر نمی‌نشینند.
   نمونه‌ی مرجع: `features/fundamental/ui/FtsScreenTable.tsx`.
2. **ارقام و قالب:** همیشه `toFaDigits` از `@shared/lib/fmt`. کلاس `.num` در `src/index.css`
   شامل `font-variant-numeric: tabular-nums; direction: ltr; unicode-bidi: isolate` است — برای هر عدد/ریال
   به‌کار ببر تا ارقام فارسی و LTR درست و ستون‌پایدار بمانند.
3. **درصد/نسبت:** `fmtPctGrouped` / `fmtRatioGrouped` از `features/fundamental/lib/numFmt.ts`
   (جداکنندهٔ هزارگان). مقدار غیرمعقول → هشدار `absurdHint`، **عدد حذف نمی‌شود**.
4. **مقدار غایب:** به‌جای برچسب کلی «داده نیست»، علتِ همان محور (`gapReason`/`gapLabel`) با tooltip نمایش داده می‌شود؛
   حکمِ موتور FTS از پرچم می‌آید (F-10) و «بدون داده» فقط وقتی است که هیچ حکمی نیست.
5. **RTL:** هدر `text-start`، سلول عددی `text-start` — نباید مخلوط شود. برای متن‌های بلند (نام نماد/اوراق)
   از `line-clamp-2` استفاده کن، نه `truncate` تک‌خطی (باعث بریدگی گزارش‌شده می‌شود).
6. **اورفلو:** جدول‌های عریض داخل کانتینر `min-w-0 max-w-full overflow-auto` باشند؛ ریشه `.app-main`
   باید `width:100%` داشته باشد تا جدول پهن کل صفحه را بیرون نزند.

## گردش کار تغییر

```powershell
cd frontend
npx tsc -b                    # خطاهای موجودِ technical را با گیت compare کن (نباید بیشتر شود)
npx vitest run src/__tests__/fts-screen.spec.tsx src/__tests__/fundamental-audit-badge.spec.tsx
npm run build
```

## تست‌های مرتبط کلیدی

`fts-screen.spec.tsx`, `fts-audit-data.spec.tsx`, `fts-exclude-filter.spec.tsx`,
`fundamental-audit-badge.spec.tsx`, `fundamental-eps-history.spec.tsx`.
