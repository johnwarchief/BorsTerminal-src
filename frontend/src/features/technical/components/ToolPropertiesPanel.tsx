// features/technical/components/ToolPropertiesPanel.tsx -- پنل تنظیمات آخرین ابزار ترسیم (سبک TV)
// تب‌ها: استایل · مختصات · متن · نمایش · هشدار. کنترل‌ها روی آخرین ترسیم اعمال می‌شوند
// (overrideOverlay) و «ذخیره به‌عنوان پیشفرض» آنها را برای همان ابزار ماندگار می‌کند.
import { useMemo, useState } from 'react';
import { toolLabel } from '../lib/drawingTools';
import type { ChartDrawApi, LastDraw } from './KLineChartWrapper';

type Tab = 'style' | 'coords' | 'text' | 'visibility' | 'alerts';

const COLORS = ['#38bdf8', '#10b981', '#f43f5e', '#fbbf24', '#a78bfa', '#e5e7eb'];
const WIDTHS = [1, 2, 3];
const LINE_STYLES = [
  { key: 'solid', label: 'توپر' },
  { key: 'dashed', label: 'خط‌چین' },
  { key: 'dotted', label: 'نقطه‌چین' },
];
const FONT_SIZES = [10, 12, 14];

function Chip({ active, label, onClick, color }: { active: boolean; label: string; onClick: () => void; color?: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      title={label}
      className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold transition-colors ${
        active ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted hover:text-text-secondary'
      }`}
    >
      {color ? <span aria-hidden className="ml-1 inline-block h-2.5 w-2.5 rounded-full align-middle" style={{ background: color }} /> : null}
      {label}
    </button>
  );
}

export function ToolPropertiesPanel({ api, last }: { api: ChartDrawApi | null; last: LastDraw }) {
  const [tab, setTab] = useState<Tab>('style');
  const [visible, setVisible] = useState(true);
  const [text, setText] = useState('');
  const [fontSize, setFontSize] = useState(12);
  const [applied, setApplied] = useState<{ styles: Record<string, unknown>; extendData: Record<string, unknown> }>({
    styles: {},
    extendData: {},
  });
  const [coordsTick, setCoordsTick] = useState(0);

  const points = useMemo(() => (last && api ? api.getLastPoints() : []), [api, last, coordsTick]);

  if (!last) return null;
  const custom = last.name.startsWith('fts');

  const apply = (patch: { styles?: Record<string, unknown>; extendData?: Record<string, unknown> }) => {
    setApplied((prev) => ({
      styles: { ...prev.styles, ...(patch.styles ?? {}) },
      extendData: { ...prev.extendData, ...(patch.extendData ?? {}) },
    }));
    api?.updateLast(patch);
  };

  const tabs: { id: Tab; label: string }[] = [
    { id: 'style', label: 'استایل' },
    { id: 'coords', label: 'مختصات' },
    { id: 'text', label: 'متن' },
    { id: 'visibility', label: 'نمایش' },
    { id: 'alerts', label: 'هشدار' },
  ];

  return (
    <div className="glass-panel flex flex-col gap-2 rounded-2xl p-2.5" data-testid="tool-properties">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-bold text-text-secondary">تنظیمات ابزار: {toolLabel(last.name)}</span>
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            role="tab"
            aria-selected={tab === t.id}
            data-testid={`tool-tab-${t.id}`}
            onClick={() => setTab(t.id)}
            className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${
              tab === t.id ? 'border-border-accent bg-accent-blue/15 text-accent-blue' : 'border-border-c bg-bg-card text-text-muted'
            }`}
          >
            {t.label}
          </button>
        ))}
        <button
          type="button"
          data-testid="tool-save-default"
          onClick={() => api?.saveAsDefault(applied)}
          className="mr-auto rounded-full border border-border-accent bg-bg-card px-2.5 py-0.5 text-[11px] font-bold text-accent-blue hover:bg-accent-blue/15"
        >
          ذخیره به‌عنوان پیش‌فرض
        </button>
      </div>

      {tab === 'style' ? (
        <div className="flex flex-wrap items-center gap-2" data-testid="tool-style">
          <span className="text-[10px] text-text-muted">رنگ</span>
          {COLORS.map((c) => (
            <button
              key={c}
              type="button"
              aria-label={`رنگ ${c}`}
              data-testid={`tool-color-${c}`}
              onClick={() => apply({ styles: { color: c } })}
              className="h-5 w-5 rounded-full border border-border-c"
              style={{ background: c }}
            />
          ))}
          <span className="text-[10px] text-text-muted">ضخامت</span>
          {WIDTHS.map((w) => (
            <button
              key={w}
              type="button"
              data-testid={`tool-width-${w}`}
              onClick={() => apply({ styles: { size: w } })}
              className="num rounded-full border border-border-c bg-bg-card px-2.5 py-0.5 text-[11px] text-text-muted hover:text-text-secondary"
            >
              {w}
            </button>
          ))}
          <span className="text-[10px] text-text-muted">نوع خط</span>
          {LINE_STYLES.map((s) => (
            <Chip key={s.key} active={false} label={s.label} onClick={() => apply({ styles: { style: s.key } })} />
          ))}
          {custom ? (
            <span className="w-full text-[10px] text-text-muted">ابزارهای سفارشی FTS استایل ثابت دارند؛ تغییرات استایل روی ابزارهای استاندارد klinecharts اثر دارد.</span>
          ) : null}
        </div>
      ) : null}

      {tab === 'coords' ? (
        <div className="flex flex-col gap-1" data-testid="tool-coords">
          {points.length === 0 ? (
            <span className="text-[10px] text-text-muted">نقطه‌ای برای نمایش نیست</span>
          ) : (
            <dl className="rounded-xl border border-border-c bg-bg-card/40 px-2.5">
              {points.map((p, i) => (
                <div key={i} className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-1 last:border-b-0">
                  <dt className="text-[10px] text-text-secondary">نقطه {i + 1}</dt>
                  <dd className="num text-[11px] font-bold text-text-primary">
                    قیمت {p.price == null ? '-' : p.price.toFixed(0)} · زمان {p.date ?? '-'}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          <button type="button" data-testid="tool-coords-refresh" onClick={() => setCoordsTick((n) => n + 1)} className="self-start rounded-full border border-border-c px-2.5 py-0.5 text-[10px] text-text-muted hover:text-text-secondary">
            بازخوانی مختصات
          </button>
          <span className="text-[10px] text-text-muted">ویرایش مستقیم نقطه‌ها نیازمند رویداد انتخاب شیء در موتور است و فعلاً در دسترس نیست (فقط نمایش).</span>
        </div>
      ) : null}

      {tab === 'text' ? (
        <div className="flex flex-wrap items-center gap-2" data-testid="tool-text">
          <input
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="متن برچسب/یادداشت..."
            aria-label="متن ابزار"
            className="rounded-lg border border-border-c bg-bg-card px-2 py-1 text-xs text-text-primary outline-none focus:border-border-accent"
          />
          {FONT_SIZES.map((s) => (
            <Chip key={s} active={fontSize === s} label={`${s}`} onClick={() => setFontSize(s)} />
          ))}
          <Chip
            active={false}
            label="اعمال"
            onClick={() => apply({ extendData: { text, size: fontSize }, styles: { size: fontSize } })}
          />
          <span className="w-full text-[10px] text-text-muted">
            متن/اندازه برای ابزارهای «یادداشت/برچسب» معنا دارد؛ فونت/پس‌زمینهٔ مستقل در استایل overlayهای فعلی پشتیبانی نمی‌شود.
          </span>
        </div>
      ) : null}

      {tab === 'visibility' ? (
        <div className="flex items-center gap-2" data-testid="tool-visibility">
          <Chip
            active={visible}
            label={visible ? 'نمایان' : 'پنهان'}
            onClick={() => {
              const next = !visible;
              setVisible(next);
              apply({ styles: { visible: next } });
            }}
          />
          <span className="text-[10px] text-text-muted">نمایش/پنهان‌سازی این ترسیم؛ نمایش مشروط به تایم‌فریم در این موتور پشتیبانی نمی‌شود.</span>
        </div>
      ) : null}

      {tab === 'alerts' ? (
        <p className="text-[10px] leading-4 text-text-muted" data-testid="tool-alerts-note">
          هشدار قیمت سمت سرور در دسترس نیست؛ این تب فعلاً غیرفعال است (بدون شبیه‌سازی).
        </p>
      ) : null}
    </div>
  );
}
