import { useState } from 'react';
import { SHORTCUTS } from '@shared/workspace/shortcuts';

export function HelpBlock({ collapsed }: { collapsed: boolean }) {
  const [open, setOpen] = useState(false);

  if (collapsed && !open) {
    return (
      <div className="border-t border-line p-1.5">
        <button type="button" data-testid="help-toggle" onClick={() => setOpen(true)}
          aria-label="راهنما"
          className="grid h-7 w-full place-items-center rounded-[var(--radius-sm)] t-10 text-text-3 hover:bg-panel-2 hover:text-text">
          ؟
        </button>
      </div>
    );
  }

  return (
    <div data-testid="help-block" className="border-t border-line p-2">
      <div className="mb-1 flex items-center justify-between t-9 font-bold text-text-3">
        <span>راهنما</span>
        {collapsed ? (
          <button type="button" onClick={() => setOpen(false)} aria-label="بستنِ راهنما" className="text-text-3">×</button>
        ) : null}
      </div>
      <ul className="space-y-0.5 t-9 text-text-3">
        {SHORTCUTS.map((shortcut) => (
          <li key={shortcut.id} className="flex items-baseline justify-between gap-2">
            <span className="truncate">{shortcut.label}</span>
            <kbd dir="ltr" className="num shrink-0 rounded-[var(--radius-xs)] border border-line px-1 text-text-2">
              {shortcut.keys}
            </kbd>
          </li>
        ))}
      </ul>
    </div>
  );
}
