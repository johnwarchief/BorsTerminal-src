// features/technical/components/FtsDock.tsx -- داک پایین چارت به سبک Trading Panel / Pine Editor
// پیش‌فرض: استاتوس‌بار باریک (~۲۸px). با کلیک روی هر تب باز می‌شود و با «جمع کردن» به همان نوار برمی‌گردد
// تا چارت در حالت عادی تقریباً تمام ارتفاع را بگیرد.
import { useState } from 'react';

export type DockTab = { id: string; label: string; node: React.ReactNode };

export function FtsDock({ tabs, defaultOpen = false }: { tabs: DockTab[]; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [active, setActive] = useState(tabs[0]?.id ?? '');
  const current = tabs.find((t) => t.id === active) ?? tabs[0];

  return (
    <section
      data-testid="fts-dock"
      data-open={open ? 'true' : 'false'}
      className={`flex shrink-0 flex-col overflow-hidden rounded-lg border border-[var(--hairline)] bg-bg-secondary ${
        open ? 'h-[42%] min-h-[220px]' : 'h-7'
      }`}
    >
      <div className="flex h-7 shrink-0 items-center gap-0.5 px-1" role="tablist" aria-label="داک پایین چارت">
        <button
          type="button"
          data-testid="fts-dock-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="px-1.5 text-[11px] font-bold text-text-muted hover:text-accent-blue"
          title={open ? 'جمع کردن پنل‌ها' : 'باز کردن پنل‌ها'}
        >
          {open ? '⌄' : '⌃'}
        </button>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={open && active === t.id}
            data-testid={`fts-dock-tab-${t.id}`}
            onClick={() => {
              setActive(t.id);
              setOpen(true);
            }}
            className={`rounded px-2 py-0.5 text-[11px] font-semibold transition-colors ${
              open && active === t.id ? 'bg-accent-blue/15 text-accent-blue' : 'text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
        <span className="mr-auto pr-1 text-[10px] text-text-muted">{open ? '' : 'پنل‌های تحلیل'}</span>
      </div>
      {open ? (
        <div role="tabpanel" data-testid="fts-dock-body" className="min-h-0 flex-1 overflow-y-auto p-2">
          {current?.node}
        </div>
      ) : null}
    </section>
  );
}
