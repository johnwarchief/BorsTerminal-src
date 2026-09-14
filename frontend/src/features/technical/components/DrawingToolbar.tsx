// features/technical/components/DrawingToolbar.tsx -- ریل عمودی ابزارهای ترسیم (سبک TradingView)
// گروه‌های بازشو (flyout) شامل خطوط/کانال/فیبوناچی/حاشیه‌نویسی — همه از overlayهای
// پشتیبانی‌شدهٔ klinecharts v10. به‌همراه واگرد/ازنو/پاک‌کردن/پنهان‌کردن.
import { useEffect, useState } from 'react';
import { buildDrawingGroups, type DrawingGroup } from '../lib/drawingTools';
import type { ChartDrawApi } from './KLineChartWrapper';

function RailButton({
  label,
  title,
  onClick,
  disabled,
  active,
  testId,
}: {
  label: string;
  title: string;
  onClick: () => void;
  disabled?: boolean;
  active?: boolean;
  testId: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      title={title}
      data-testid={testId}
      className={`flex h-8 w-8 items-center justify-center rounded-lg border text-sm font-bold transition-colors disabled:opacity-40 ${
        active ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-secondary hover:text-accent-blue'
      }`}
    >
      {label}
    </button>
  );
}

export function DrawingToolbar({ api }: { api: ChartDrawApi | null }) {
  const [groups, setGroups] = useState<DrawingGroup[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [hidden, setHidden] = useState(false);

  useEffect(() => {
    const supported = window.klinecharts?.getSupportedOverlays?.() ?? [];
    setGroups(buildDrawingGroups(supported));
  }, [api]);

  return (
    <div
      data-testid="drawing-toolbar"
      aria-label="ابزارهای ترسیم چارت"
      className="glass-panel flex w-11 shrink-0 flex-col items-center gap-1 self-start rounded-2xl p-1.5"
    >
      {groups.map((g) => (
        <div key={g.label} className="relative">
          <RailButton
            label={g.glyph}
            title={g.label}
            active={open === g.label}
            onClick={() => setOpen(open === g.label ? null : g.label)}
            testId={`draw-group-${g.tools[0].name}`}
          />
          {open === g.label ? (
            <div
              role="menu"
              className="glass-panel absolute right-11 top-0 z-40 flex w-36 flex-col gap-0.5 rounded-xl p-1"
              data-testid="draw-flyout"
            >
              <span className="px-2 py-1 text-[10px] font-bold text-text-muted">{g.label}</span>
              {g.tools.map((t) => (
                <button
                  key={t.name}
                  type="button"
                  role="menuitem"
                  disabled={!api}
                  onClick={() => {
                    api?.startDraw(t.name);
                    setOpen(null);
                  }}
                  data-testid={`draw-${t.name}`}
                  className="rounded-lg px-2 py-1 text-right text-xs text-text-secondary transition-colors hover:bg-bg-card hover:text-accent-blue disabled:opacity-40"
                >
                  {t.label}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ))}

      <span aria-hidden className="my-0.5 h-px w-6 bg-border-c" />

      <RailButton label="وا" title="واگرد (Undo)" disabled={!api} onClick={() => api?.undo()} testId="draw-undo" />
      <RailButton label="از" title="ازنو (Redo)" disabled={!api} onClick={() => api?.redo()} testId="draw-redo" />
      <RailButton label="پاک" title="پاک‌کردن همهٔ ترسیم‌ها" disabled={!api} onClick={() => api?.clearDrawings()} testId="draw-clear" />
      <RailButton
        label={hidden ? 'نمایان' : 'پنهان'}
        title={hidden ? 'نمایش ترسیم‌ها' : 'پنهان‌کردن همهٔ ترسیم‌ها'}
        disabled={!api}
        active={hidden}
        onClick={() => {
          const next = !hidden;
          setHidden(next);
          api?.hideDrawings(next);
        }}
        testId="draw-hide"
      />
    </div>
  );
}
