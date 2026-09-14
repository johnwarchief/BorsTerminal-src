// features/technical/components/DrawingToolbar.tsx -- ریل عمودی ابزارهای ترسیم (سبک TradingView)
// گروه‌های بازشو (flyout) شامل خطوط/کانال/فیبوناچی/اندازه‌گیری/حاشیه‌نویسی — همه از
// overlayهای پشتیبانی‌شدهٔ klinecharts v10 + ابزارهای سفارشی FTS.
// پولیش ظاهری: آیکون SVG یکدست (بدون ایموجی)، حالت hover/active/selected،
// flyout فشرده با بستنِ بیرون‌کلیک.
import { useEffect, useRef, useState } from 'react';
import { buildDrawingGroups, type DrawingGroup } from '../lib/drawingTools';
import type { ChartDrawApi, DrawGroup } from './KLineChartWrapper';

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
const ICON_LOCK = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <rect x="3.5" y="7" width="9" height="6.5" rx="1.2" fill="none" stroke="currentColor" strokeWidth="1.4" />
    <path d="M5.5 7V5.2a2.5 2.5 0 0 1 5 0V7" fill="none" stroke="currentColor" strokeWidth="1.4" />
  </svg>
);
const ICON_COPY = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <rect x="2.5" y="2.5" width="8" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.3" />
    <rect x="5.5" y="5.5" width="8" height="8" rx="1" fill="none" stroke="currentColor" strokeWidth="1.3" />
  </svg>
);
const ICON_RESIZE = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M2 14L14 2M2 14h5M2 14v-5M14 2h-5M14 2v5" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
  </svg>
);
const ICON_FOLDER = (
  <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden>
    <path d="M2 4.5h4l1.2 1.5H14v6.5H2z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
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
  const [showGroups, setShowGroups] = useState(false);
  const [hidden, setHidden] = useState(false);
  const [locked, setLocked] = useState(false);
  const [width, setWidth] = useState(1);
  const [shapeGroups, setShapeGroups] = useState<DrawGroup[]>([]);
  const [targetGroup, setTargetGroup] = useState('');
  const [hiddenGroups, setHiddenGroups] = useState<string[]>([]);
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
      <RailButton
        label="قفل"
        icon={ICON_LOCK}
        title={locked ? 'بازکردن قفل ترسیم‌ها' : 'قفل ترسیم‌ها (دیگر قابل ویرایش نیستند)'}
        disabled={!api}
        active={locked}
        onClick={() => {
          const next = !locked;
          setLocked(next);
          api?.setLockAll(next);
        }}
        testId="draw-lock"
      />
      <RailButton
        label="کپی"
        icon={ICON_COPY}
        title="کپی آخرین ترسیم (با جابه‌جایی افقی)"
        disabled={!api}
        onClick={() => api?.copyLast()}
        testId="draw-copy"
      />
      <RailButton
        label="اندازه"
        icon={ICON_RESIZE}
        title={`تغییر ضخامت همهٔ ترسیم‌ها (فعلی: ${width})`}
        disabled={!api}
        onClick={() => {
          const next = width >= 3 ? 1 : width + 1;
          setWidth(next);
          api?.resizeAll(next);
        }}
        testId="draw-resize"
      />
      <div className="relative">
        <RailButton
          label="پوشه"
          icon={ICON_FOLDER}
          title="گروه‌های اشکال (پوشه)"
          disabled={!api}
          active={showGroups}
          onClick={() => {
            const next = !showGroups;
            setShowGroups(next);
            if (next) setShapeGroups(api?.listGroups() ?? []);
          }}
          testId="draw-groups"
        />
        {showGroups ? (
          <div
            role="menu"
            data-testid="draw-groups-flyout"
            className="glass-panel absolute right-11 bottom-0 z-40 flex max-h-72 w-56 flex-col gap-0.5 overflow-y-auto rounded-xl border border-[var(--hairline)] p-1 shadow-lg"
          >
            <span className="px-2 py-1 text-[10px] font-bold text-text-muted">گروه‌های اشکال</span>
            {shapeGroups.length === 0 ? (
              <span className="px-2 py-1 text-[10px] text-text-muted">گروهی ثبت نشده</span>
            ) : (
              shapeGroups.map((g) => {
                const isHidden = hiddenGroups.includes(g.id);
                return (
                  <div key={g.id} className="flex items-center justify-between gap-1 rounded-lg px-2 py-1 text-[11px] text-text-secondary">
                    <span className="num truncate" title={g.id}>
                      {g.id} · {g.count}
                    </span>
                    <span className="flex shrink-0 items-center gap-1">
                      <button
                        type="button"
                        data-testid={`group-toggle-${g.id}`}
                        onClick={() => {
                          const next = !isHidden;
                          setHiddenGroups((prev) => (next ? [...prev, g.id] : prev.filter((x) => x !== g.id)));
                          api?.setGroupVisible(g.id, !next);
                        }}
                        className="rounded border border-border-c px-1.5 text-[10px] hover:text-accent-blue"
                      >
                        {isHidden ? 'نمایان' : 'پنهان'}
                      </button>
                      <button
                        type="button"
                        data-testid={`group-remove-${g.id}`}
                        onClick={() => {
                          api?.removeGroup(g.id);
                          setShapeGroups((prev) => prev.filter((x) => x.id !== g.id));
                        }}
                        className="rounded border border-border-c px-1.5 text-[10px] hover:border-accent-red/50 hover:text-accent-red"
                      >
                        حذف
                      </button>
                    </span>
                  </div>
                );
              })
            )}
            <div className="mt-0.5 flex items-center gap-1 border-t border-[var(--hairline)] px-2 pt-1">
              <input
                value={targetGroup}
                onChange={(e) => setTargetGroup(e.target.value)}
                placeholder="گروه جدید..."
                aria-label="گروه هدف ترسیم"
                data-testid="group-target-input"
                className="w-24 rounded border border-border-c bg-bg-card px-1.5 py-0.5 text-[11px] text-text-primary outline-none focus:border-border-accent"
              />
              <button
                type="button"
                data-testid="group-target-apply"
                onClick={() => {
                  const id = targetGroup.trim();
                  api?.setTargetGroup(id ? id : null);
                  setShapeGroups(api?.listGroups() ?? []);
                }}
                className="rounded border border-border-c px-1.5 py-0.5 text-[10px] text-text-secondary hover:text-accent-blue"
              >
                گروه هدف
              </button>
            </div>
            <span className="px-2 pb-1 text-[9px] leading-4 text-text-muted">ترسیم‌های بعدی در گروه هدف ثبت می‌شوند (klinecharts گروه = برچسب، نه پوشهٔ واقعی).</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
