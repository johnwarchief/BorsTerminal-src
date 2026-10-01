import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { TooltipProvider } from '@shared/ui/Tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { mainRoutes } from './routes';
import './index.css';
// استایل موبایل ایستا ایمپورت می‌شود (نه داینامیک) تا خطای بارگذاری chunk در
// WebView نتواند پوسته را بشکند؛ همهٔ قواعدش پشت html.bors-mobile است و در
// دسکتاپ کاملاً بی‌اثر می‌ماند (~۲KB).
import './shared/styles/mobile.css';

// بیلد موبایل (VITE_LOCAL_DATA='1'): کلاس پوستهٔ موبایل روی ریشهٔ سند +
// پنل عیب‌یابی روی خود دستگاه (دکمهٔ 🛠).
if (import.meta.env.VITE_LOCAL_DATA === '1') {
  document.documentElement.classList.add('bors-mobile');
  void import('./shared/api/local/diagnostics')
    .then((m) => m.mountDiagnostics())
    .catch(() => { /* پنل عیب‌یابی نیامد — اپ بدون آن هم کار می‌کند */ });
  // دکمهٔ بازگشتِ سخت‌افزاری. بی‌این، اندروید با یک لمس کلِ اپ را می‌بندد
  // و بارگذاریِ بعدی یعنی بازکردنِ دوبارهٔ دیتابیسِ ۲۲ مگابایتی.
  void import('./shared/api/local/androidShell')
    .then((m) => m.mountAndroidBack())
    .catch(() => { /* پوستهٔ بومی نبود — رفتارِ مرورگر می‌ماند */ });
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

const router = createHashRouter([
  {
    path: '/',
    element: <AppShell />,
    children: mainRoutes,
  },
]);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      {/* یک Provider برایِ کلِ برنامه: تأخیرِ مشترک و «پرشِ سریع» بینِ دو
          راهنمایِ همسایه — اولی با تأخیر، بعدی‌ها فوری. */}
      <TooltipProvider>
        <RouterProvider router={router} />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
);
