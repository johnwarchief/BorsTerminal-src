// features/technical/components/FtsDock.tsx -- داک کشویی پایین چارت (سبک Pine Editor)
// کارت‌های حجیم (وضعیت FTS / تحلیل ساختاری / مقایسه / داوری) به تب‌های جمع‌شونده منتقل
// شده‌اند تا در حالت پیش‌فرض چارت تقریباً تمام ارتفاع را بگیرد و اسکرول عمودی نباشد.
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
      className={`glass-panel flex shrink-0 flex-col overflow-hidden rounded-2xl ${
        open ? 'h-[46%] min-h-[240px]' : 'h-10'
      }`}
    >
      <div className="flex h-10 shrink-0 items-center gap-1 px-2" role="tablist" aria-label="داک پایین چارت">
        <button
          type="button"
          data-testid="fts-dock-toggle"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="rounded-full border border-border-c bg-bg-card px-2.5 py-1 text-[11px] font-bold text-text-secondary hover:text-accent-blue"
        >
          {open ? 'جمع کردن ⌄' : 'پنل‌های تحلیل ⌃'}
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
            className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold transition-colors ${
              open && active === t.id
                ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:text-text-secondary'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {open ? (
        <div role="tabpanel" data-testid="fts-dock-body" className="min-h-0 flex-1 overflow-y-auto p-3 pt-1">
          {current?.node}
        </div>
      ) : null}
    </section>
  );
}
