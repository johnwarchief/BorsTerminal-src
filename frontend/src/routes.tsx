import { RouteObject } from 'react-router';
import { Lazy } from '@shared/components/Lazy';

const page = (load: () => Promise<{ default: React.ComponentType }>) => (
  <Lazy load={load} />
);

export const mainRoutes: RouteObject[] = [
  { path: '', element: page(() => import('@features/market/routes/MarketPage')) },
  { path: 'market', element: page(() => import('@features/market/routes/MarketPage')) },
  {
    path: 'fundamental/:symbol?',
    element: page(() => import('@features/fundamental/routes/FundamentalPage')),
  },
  {
    path: 'technical/:symbol?',
    element: page(() => import('@features/technical/routes/TechnicalPage')),
  },
  // ابزارِ توسعه‌ایِ مالک: مقایسهٔ موتورهایِ چارت درِ همان shell (بدون منو/سایدبار)
  {
    path: 'engine-lab',
    element: page(() => import('@features/technical/engine-lab/EngineLabPage')),
  },
  {
    path: 'strategy-tree/:symbol?',
    element: page(() => import('@features/master/routes/StrategyTreePage')),
  },
  { path: 'portfolio', element: page(() => import('@features/portfolio/routes/PortfolioPage')) },
  {
    path: 'master/:symbol?',
    element: page(() => import('@features/master/routes/MasterPage')),
  },
];
