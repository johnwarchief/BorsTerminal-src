import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { mainRoutes } from './routes';
import './index.css';
// استایل موبایل ایستا ایمپورت می‌شود (نه داینامیک) تا خطای بارگذاری chunk در
// WebView نتواند پوسته را بشکند؛ همهٔ قواعدش پشت html.bors-mobile است و در
// دسکتاپ (که این کلاس را نمی‌گیرد) کاملاً بی‌اثر می‌ماند (~۲KB).
import './shared/styles/mobile.css';

// بیلد موبایل (VITE_LOCAL_DATA='1'): کلاس پوستهٔ موبایل روی ریشهٔ سند +
// پنل عیب‌یابی روی خود دستگاه (دکمهٔ 🛠 — برچسب بیلد/وضعیت داده/زنده).
if (import.meta.env.VITE_LOCAL_DATA === '1') {
  document.documentElement.classList.add('bors-mobile');
  void import('./shared/api/local/diagnostics')
    .then((m) => m.mountDiagnostics())
    .catch(() => { /* پنل عیب‌یابی نیامد — اپ بدون آن هم کار می‌کند */ });
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
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
);
