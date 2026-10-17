import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { QueryClientProvider } from '@tanstack/react-query';
import { createHashRouter, RouterProvider } from 'react-router';
import { AppShell } from '@app/layouts/AppShell';
import { queryClient } from '@app/lib/queryClient';
import { mainRoutes } from './routes';
import './index.css';

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
