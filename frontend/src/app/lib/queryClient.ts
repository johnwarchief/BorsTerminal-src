// app/lib/queryClient.ts -- تک‌نسخهٔ QueryClient
//
// چرا فایلِ جدا: پیش‌خوانیِ «صفحۀِ اول» باید ازِ همانِ cacheِ خودِ برنامه بخواند،
// نه ازِ یکِ QueryClientِ دوم که پاسخ را درِ جایِ دیگری می‌گذارد وِ بعدِ آنِ کامپوننت
// همانِ داده را دوباره می‌خواهد (یعنی دقیقاً همانِ pollingِ بی‌موردی که مأموریت رد
// می‌کند). `main.tsx` وِ `AppShell` هر دو همینِ شیء را import می‌کنند.
import { QueryClient } from '@tanstack/react-query';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});
