import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { AppShell } from '@app/shell/AppShell';
import { MarketPage } from '@features/market/routes/MarketPage';
import { MarketStatusPage } from '@features/market/routes/MarketStatusPage';
import { NotificationsPage } from '@features/notifications/ui/NotificationsPage';

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/market" element={<MarketPage />} />
          <Route path="/market-status" element={<MarketStatusPage />} />
          <Route path="/notifications" element={<NotificationsPage />} />
          <Route path="*" element={<Navigate to="/market" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}
