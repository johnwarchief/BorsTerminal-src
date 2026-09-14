import { Outlet } from 'react-router';
import { Sidebar } from '../components/Sidebar';
import { Topbar } from '../components/Topbar';
import { CommandPalette } from '../components/CommandPalette';
import { SymbolInspector } from '../../widgets/SymbolInspector';
import { useSymbolStore } from '@shared/stores/symbolStore';

export function AppShell() {
  const symbol = useSymbolStore((s) => s.symbol);
  const inspectorOpen = symbol.length > 0;

  return (
    <div className="flex min-h-screen overflow-hidden bg-bg-primary text-text-primary">
      <Sidebar />
      <div
        className="flex min-w-0 flex-1 flex-col overflow-y-auto transition-[padding] duration-200 ease-out"
        style={{ paddingLeft: inspectorOpen ? 264 : 0 }}
      >
        <Topbar />
        <main className="flex-1 px-0 py-2">
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
