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
  { path: 'portfolio', element: page(() => import('@features/portfolio/routes/PortfolioPage')) },
  {
    path: 'master/:symbol?',
    element: page(() => import('@features/master/routes/MasterPage')),
  },
];
