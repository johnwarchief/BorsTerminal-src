// features/technical/components/DrawingToolbar.tsx -- ریل عمودی ابزارهای ترسیم (سبک TradingView)
// گروه‌های بازشو (flyout) شامل خطوط/کانال/فیبوناچی/اندازه‌گیری/حاشیه‌نویسی — همه از
// overlayهای پشتیبانی‌شدهٔ klinecharts v10 + ابزارهای سفارشی FTS.
// پولیش ظاهری: آیکون SVG یکدست (بدون ایموجی)، حالت hover/active/selected،
// flyout فشرده با بستنِ بیرون‌کلیک.
import { useEffect, useRef, useState } from 'react';
import { buildDrawingGroups, type DrawingGroup } from '../lib/drawingTools';
import type { ChartDrawApi } from './KLineChartWrapper';

/** آیکون‌های سادهٔ SVG هر گروه (بدون ایموجی) */
const GROUP_ICONS: Record<string, React.ReactNode> = {
  خطوط: (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <line x1="2" y1="13" x2="14" y2="3" stroke="currentColor" strokeWidth="1.6" />
      <circle cx="2" cy="13" r="1.6" fill="currentColor" />
      <circle cx="14" cy="3" r="1.6" fill="currentColor" />
    </svg>
  ),
  کانال: (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <line x1="2" y1="11" x2="14" y2="4" stroke="currentColor" strokeWidth="1.4" />
      <line x1="2" y1="14" x2="14" y2="7" stroke="currentColor" strokeWidth="1.4" strokeDasharray="2 2" />
    </svg>
  ),
  فیبوناچی: (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <line x1="2" y1="3" x2="14" y2="3" stroke="currentColor" strokeWidth="1.2" />
      <line x1="2" y1="7" x2="14" y2="7" stroke="currentColor" strokeWidth="1.2" strokeDasharray="2 2" />
      <line x1="2" y1="11" x2="14" y2="11" stroke="currentColor" strokeWidth="1.2" strokeDasharray="2 2" />
      <line x1="2" y1="14" x2="14" y2="14" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  ),
  'اندازه‌گیری / پوزیشن': (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <rect x="2" y="3" width="12" height="4" fill="currentColor" opacity="0.35" />
      <rect x="2" y="9" width="12" height="4" fill="currentColor" opacity="0.15" />
      <line x1="2" y1="8" x2="14" y2="8" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  ),
  'حاشیه‌نویسی': (
    <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
      <path d="M2 12h9l3-3-3-3H2z" fill="none" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  ),
};

/** آیکون‌های عملیات ریل (واگرد/ازنو/پاک/پنهان) */
const ICON_UNDO = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M6 3 2 7l4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M2 7h7a4 4 0 0 1 0 8H6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);
const ICON_REDO = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M10 3l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    <path d="M14 7H7a4 4 0 0 0 0 8h1" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
  </svg>
);
const ICON_TRASH = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M3 5h10M6 5V3h4v2M5 5l1 9h4l1-9" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
  </svg>
);
const ICON_EYE = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M1.5 8S4 4 8 4s6.5 4 6.5 4S12 12 8 12 1.5 8 1.5 8z" fill="none" stroke="currentColor" strokeWidth="1.3" />
    <circle cx="8" cy="8" r="1.8" fill="currentColor" />
  </svg>
);
const ICON_EYE_OFF = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M1.5 8S4 4 8 4s6.5 4 6.5 4S12 12 8 12 1.5 8 1.5 8z" fill="none" stroke="currentColor" strokeWidth="1.2" />
    <line x1="2" y1="14" x2="14" y2="2" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);

function RailButton({
  label,
  icon,
  title,
  onClick,
  disabled,
  active,
  testId,
}: {
  label: string;
  icon?: React.ReactNode;
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
      aria-pressed={active === true}
      aria-label={title}
      title={title}
      data-testid={testId}
      className={`flex h-8 w-8 items-center justify-center rounded-lg border transition-colors disabled:opacity-40 ${
        active
          ? 'border-border-accent bg-accent-blue/15 text-accent-blue shadow-[inset_0_0_10px_rgba(56,189,248,0.15)]'
          : 'border-border-c bg-bg-card text-text-secondary hover:border-border-accent hover:bg-bg-card/80 hover:text-accent-blue'
      }`}
    >
      {icon ?? label}
    </button>
  );
}

export function DrawingToolbar({ api }: { api: ChartDrawApi | null }) {
  const [groups, setGroups] = useState<DrawingGroup[]>([]);
  const [open, setOpen] = useState<string | null>(null);
  const [hidden, setHidden] = useState(false);
  const [activeTool, setActiveTool] = useState<string | null>(null);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const supported = window.klinecharts?.getSupportedOverlays?.() ?? [];
    setGroups(buildDrawingGroups(supported));
  }, [api]);

  // بستن flyout با کلیک بیرون از ریل (مثل TradingView)
  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (rootRef.current && !rootRef.current.contains(e.target as Node)) setOpen(null);
    };
    document.addEventListener('mousedown', onDown);
    return () => document.removeEventListener('mousedown', onDown);
  }, [open]);

  const groupActive = (g: DrawingGroup): boolean => g.tools.some((t) => t.name === activeTool);

  return (
    <div
      ref={rootRef}
      data-testid="drawing-toolbar"
      aria-label="ابزارهای ترسیم چارت"
      className="glass-panel flex w-10 shrink-0 flex-col items-center gap-0.5 self-start rounded-2xl p-1"
    >
      {groups.map((g) => {
        const active = groupActive(g);
        return (
          <div key={g.label} className="relative">
            <RailButton
              label={g.glyph}
              icon={GROUP_ICONS[g.label]}
              title={g.label}
              active={open === g.label || active}
              onClick={() => setOpen(open === g.label ? null : g.label)}
              testId={`draw-group-${g.tools[0].name}`}
            />
            {active ? <span aria-hidden className="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full bg-accent-blue" /> : null}
            {open === g.label ? (
              <div
                role="menu"
                className="glass-panel absolute right-11 top-0 z-40 flex max-h-72 w-44 flex-col gap-0.5 overflow-y-auto rounded-xl border border-[var(--hairline)] p-1 shadow-lg"
                data-testid="draw-flyout"
              >
                <span className="flex items-baseline justify-between px-2 py-1">
                  <span className="text-[10px] font-bold text-text-muted">{g.label}</span>
                  <span className="num text-[9px] text-text-muted">{g.tools.length}</span>
                </span>
                {g.tools.map((t) => (
                  <button
                    key={t.name}
                    type="button"
                    role="menuitem"
                    disabled={!api}
                    onClick={() => {
                      api?.startDraw(t.name);
                      setActiveTool(t.name);
                      setOpen(null);
                    }}
                    title={t.hint}
                    data-testid={`draw-${t.name}`}
                    className={`flex items-center justify-between gap-2 rounded-lg px-2 py-1 text-right text-xs transition-colors disabled:opacity-40 ${
                      activeTool === t.name
                        ? 'bg-accent-blue/15 text-accent-blue'
                        : 'text-text-secondary hover:bg-bg-card hover:text-accent-blue'
                    }`}
                  >
                    <span>{t.label}</span>
                    {activeTool === t.name ? <span aria-hidden className="text-[9px]">●</span> : null}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
        );
      })}

      <span aria-hidden className="my-0.5 h-px w-6 bg-border-c" />

      <RailButton label="وا" icon={ICON_UNDO} title="واگرد (Undo)" disabled={!api} onClick={() => api?.undo()} testId="draw-undo" />
      <RailButton label="از" icon={ICON_REDO} title="ازنو (Redo)" disabled={!api} onClick={() => api?.redo()} testId="draw-redo" />
      <RailButton
        label="پاک"
        icon={ICON_TRASH}
        title="پاک‌کردن همهٔ ترسیم‌ها"
        disabled={!api}
        onClick={() => {
          api?.clearDrawings();
          setActiveTool(null);
        }}
        testId="draw-clear"
      />
      <RailButton
        label={hidden ? 'نمایان' : 'پنهان'}
        icon={hidden ? ICON_EYE_OFF : ICON_EYE}
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
