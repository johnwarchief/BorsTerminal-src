import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { CommandPalette } from '../components/CommandPalette';
import { SymbolInspector } from '../../widgets/SymbolInspector';
import { useSymbolStore } from '@shared/stores/symbolStore';

export function AppShell() {
  const symbol = useSymbolStore((s) => s.symbol);
  const inspectorOpen = symbol.length > 0;

  // ریسپانسیو (فاز ۲): فاصله/اورلی سایدبار و داور با CSS و توکنها مدیریت میشود
  // (.app-content / .app-main در index.css) — بدون هک جاوااسکریپت در رندر.
  return (
    <div className="flex min-h-screen overflow-hidden bg-bg-primary text-text-primary">
      <Sidebar />
      <div
        className="app-content flex min-w-0 flex-1 flex-col overflow-y-auto transition-[padding] duration-200 ease-out"
        data-inspector={inspectorOpen ? 'open' : 'closed'}
      >
        <Topbar />
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