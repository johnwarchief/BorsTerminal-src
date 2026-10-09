import { Link, Navigate, type RouteObject } from 'react-router';
import { Lazy } from '@shared/components/Lazy';

const page = (load: () => Promise<{ default: React.ComponentType }>) => (
  <Lazy load={load} />
);

export const mainRoutes: RouteObject[] = [
  // رأیِ مالک (۱۴۰۵-۰۷-۱۷): صفحهٔ نخستِ برنامه غربالگری FTS است. مسیرِ خالی
  // redirect می‌شود نه element، تا آدرسِ نوارِ نشانی همان /master بماند و
  // نوارِ کناری هم درست روشن شود.
  { path: '', element: <Navigate to="/master" replace /> },
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
  // هیچ آدرسی بی‌صفحه نماند: لینکِ مرده باید خودش را نشان دهد، نه صفحه‌ای سفید.
  {
    path: '*',
    element: (
      <div className="flex flex-col items-start gap-3 p-6" data-testid="route-not-found">
        <h1 className="text-lg font-black text-text-primary">این نشانی در اپ ثبت نشده است</h1>
        <p className="text-2xs text-text-muted" data-testid="route-not-found-path">{window.location.hash}</p>
        <Link to="/master" className="rounded-xl border border-accent-blue/50 px-3 py-1.5 text-2xs font-bold text-accent-blue">
          رفتن به غربالگری FTS
        </Link>
      </div>
    ),
  },
];
