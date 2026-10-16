// features/market/lib/preloadMarketStatusFirstScreen.ts -- پیش‌خوانیِ صفحۀِ اول
//
// چرا این هست (فاز G، بندِ ۵ — «علت زمان پاسخِ اولیهٔ mstat»): سنجشِ زنده درِ
// ۱۳۶۶×۷۶۸ نشان داد پرسش‌هایِ خودِ «وضعیت بازار» ~۱٫۶–۱٫۹ ثانیه پس ازِ ناوبری
// آغاز می‌شوند، در حالی که پوسته درِ ~۱٫۰–۱٫۵ ثانیه رویِ صحنه است. فاصلۀِ میانی
// کارِ رابط نیست: `MarketStatusPage` تنبل (lazy) است وِ هرِ پنلِ اینِ صفحه هوکِ
// خودش را درِ بدنهٔ همانِ کامپوننت می‌خواند، پس هیچِ پرسشی پیش ازِ رسیدنِ chunkِ
// route صادر نمی‌شود. chunkهایِ چارت (`useCandleFeed`, `KLineChartWrapper`) هم
// همینِ باز را عقبتر می‌برند.
//
// اصلاح: دو پرسشِ صفحۀِ اول — کارت‌های شاخص وِ توزیعِ بازدهی — درِ همانِ لحظۀِ
// نشستنِ پوسته صادر می‌شوند، یعنی موازی باِ بارِ chunk. کلیدها ازِ خودِ isِ
// hookها می‌آیند (`indexCardsQueryOptions`, `histogramQueryOptions`), پسِ
// کامپوننتِ بعدی درِ همانِ پرسشِ در حالِ جریان شرکت می‌کند وِ درخواستِ دومی ساخته
// نمی‌شود. بی‌دادهٔ ساختگی، بی‌کشِ بی‌اعتبار، بی‌زمان‌سنجیِ متفاوت.
//
// دو قیدِ عمدی:
//  • فقطِ صفحۀِ اول. `phases`/`mainwatch`/`smart-money` سرد گران‌ترین‌ها هستند
//    (سنجشِ localhost: ۷۵۲/۴۹۵/۳۴۶ms) وِ بک‌اند تک‌روشی است — پیش‌خواندنشان
//    کارِ خودِ صفحۀِ اول را درِ صفِ همانِ سرور می‌اندازد.
//  • فقطِ پس ازِ ورود. پیش ازِ احرازِ هویت هیچِ پرسشی ازِ اینِ route بیرون نمی‌رود;
//    تاِ آنِ وقت کاربرِ واقعیِ واردنشده بهِ دادهٔ بازار نیاز ندارد.
//
// `qc` ازِ بیرون می‌آید (نه ازِ importِ singleton): همانِ کشی که Provider درِ برنامه
// نشاندۀِ is، پسِ آزمونِ «پیش‌خوانی درخواستِ تکراری نمی‌سازد» درِ همانِ کشِ واقعیِ
// خودِ کامپوننت خوانده می‌شود، نه درِ یکِ کشِ موازی.
import type { QueryClient } from '@tanstack/react-query';
import { histogramQueryOptions } from '../api/useMarketStatusFeed';
import { indexCardsQueryOptions } from '../api/useMarketPanels';

export function preloadMarketStatusFirstScreen(qc: QueryClient) {
  void qc.prefetchQuery(indexCardsQueryOptions());
  void qc.prefetchQuery(histogramQueryOptions());
}
