import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { CommandPalette } from '../components/CommandPalette';
import { SymbolInspector } from '../../widgets/SymbolInspector';
import { FtsPipelineBar } from '../../widgets/FtsPipelineBar';
import { useEffect } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useAuthStore } from '@shared/stores/authStore';
import { useMarketStore } from '@shared/stores/marketStore';
import { LoginScreen } from '../../widgets/LoginScreen';

export function AppShell() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const symbol = useSymbolStore((s) => s.symbol);
  const inspectorOpen = symbol.length > 0;

  // بهینه‌سازی پرفورمنس: تعلیق هوشمند پولینگ هنگام مینیمایز بودن پنجره یا عدم فوکوس
  useEffect(() => {
    const handleVisibility = () => {
      useMarketStore.getState().setPaused(document.hidden);
    };
    document.addEventListener('visibilitychange', handleVisibility);
    return () => document.removeEventListener('visibilitychange', handleVisibility);
  }, []);

  if (!isAuthenticated) {
    return <LoginScreen />;
  }

  // ریسپانسیو (فاز ۲): فاصله/اورلی سایدبار و داور با CSS و توکنها مدیریت میشود
  // (.app-content / .app-main در index.css) — بدون هک جاوااسکریپت در رندر.
  return (
    <div className="flex min-h-screen overflow-hidden bg-bg-primary text-text-primary">
      <Sidebar />
      <div
        className="app-content flex min-w-0 flex-1 flex-col overflow-y-auto overflow-x-hidden transition-[padding] duration-200 ease-out"
        data-inspector={inspectorOpen ? 'open' : 'closed'}
      >
        <Topbar />
        <FtsPipelineBar />
        <main className="app-main flex-1 py-2">
          <div className="panel-in flex w-full flex-col gap-4">
            <Outlet />
          </div>
        </main>
      </div>
      <SymbolInspector />
      <CommandPalette />
    </div>
  );
}