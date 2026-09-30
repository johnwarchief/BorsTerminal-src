import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { TooltipProvider } from '@shared/ui/Tooltip';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { mainRoutes } from './routes';
import './index.css';

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
