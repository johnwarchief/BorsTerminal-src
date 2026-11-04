import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@app/shell/AppShell';
import { FundamentalPage } from '@features/fundamental/routes/FundamentalPage';
import { MarketPage } from '@features/market/routes/MarketPage';
import { MarketStatusPage } from '@features/market/routes/MarketStatusPage';
import { NotificationsPage } from '@features/notifications/ui/NotificationsPage';
import { TechnicalPage } from '@features/technical/routes/TechnicalPage';

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/market" element={<MarketPage />} />
          <Route path="/technical" element={<TechnicalPage />} />
          <Route path="/technical/:symbol" element={<TechnicalPage />} />
          <Route path="/market-status" element={<MarketStatusPage />} />
          <Route path="/fundamental" element={<FundamentalPage />} />
          <Route path="/fundamental/:symbol" element={<FundamentalPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="*" element={<Navigate to="/market" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
