import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { mainRoutes } from './routes';
import { MobileBootstrap } from '@app/components/MobileBootstrap';
import './index.css';
import './shared/styles/mobile.css';

if (import.meta.env.VITE_LOCAL_DATA === '1') {
  document.documentElement.classList.add('bors-mobile');
  void import('./shared/api/local/diagnostics').then((m) => m.mountDiagnostics()).catch(() => {});
  void import('./shared/api/local/androidShell').then((m) => m.mountAndroidBack()).catch(() => {});
  // برگشت ازِ پس‌زمینه: فرصتِ بررسیِ بستۀِ داده. خودِ localData گیتِ
  // پنجرۀِ ۲۴ساعته/backoff/سنجه‌دار را دارد؛ این‌جا فقط زنگ می‌زند. بی‌این،
  // گوشیِ همیشه‌باز بی‌restartِ کامل هرگز بستۀِ تازه‌تر نمی‌دید.
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) return;
    void import('./shared/api/local/localData')
      .then((m) => m.resumeSnapshotCheck())
      .catch(() => {});
  });
  // قلابِ خواندنیِ سنجهٔ دستگاه — فقط بیلدِ آزمایشیِ bake؛ درِ artifactِ
  // منتشرشدنی این شاخه بی‌بایت است (خروجیِ bake هرگز منتشر نمی‌شود).
  if (import.meta.env.VITE_ANDROID_PROBE === '1') {
    void import('./shared/api/local/probe').then((m) => m.mountProbe()).catch(() => {});
  }
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
      <MobileBootstrap><RouterProvider router={router} /></MobileBootstrap>
    </QueryClientProvider>
  </StrictMode>,
);
