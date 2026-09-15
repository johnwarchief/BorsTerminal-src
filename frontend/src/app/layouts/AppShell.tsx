import { useEffect } from 'react';
import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { CommandPalette } from '../components/CommandPalette';
import { SymbolInspector } from '../../widgets/SymbolInspector';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { MEDIA_SMALL } from '@shared/lib/breakpoints';

export function AppShell() {
  const symbol = useSymbolStore((s) => s.symbol);
  const inspectorOpen = symbol.length > 0;

  // ریسپانسیو (فاز ۲): زیر ۱۲۸۰px سایدبار بهطور پیشفرض جمع میشود.
  const isSmall = useMediaQuery(MEDIA_SMALL);
  const setSidebarCollapsed = useUiStore((s) => s.setSidebarCollapsed);
  useEffect(() => {
    setSidebarCollapsed(isSmall);
  }, [isSmall, setSidebarCollapsed]);

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