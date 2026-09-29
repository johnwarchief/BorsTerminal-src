import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { mainRoutes } from './routes';
import './index.css';

// بیلد موبایل (VITE_LOCAL_DATA='1'): کلاس پوستهٔ موبایل + استایل مخصوص لمس.
// در بیلد دسکتاپ این شاخه tree-shake می‌شود و هیچ اثری در باندل ندارد.
if (import.meta.env.VITE_LOCAL_DATA === '1') {
  document.documentElement.classList.add('bors-mobile');
  void import('./shared/styles/mobile.css');
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
