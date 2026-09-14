// features/technical/components/ToolPropertiesPanel.tsx -- پنل تنظیمات آخرین ابزار ترسیم
// تب‌های مشترک: استایل · متن · نمایان (طبق docs/CHART-PARITY-REFERENCE.md §۴).
// تب «هشدار» صادقانه غیرفعال است (هشدار سمت سرور لازم دارد و در دسترس نیست).
import { useState } from 'react';
import { toolLabel } from '../lib/drawingTools';
import type { ChartDrawApi, LastDraw } from './KLineChartWrapper';

type Tab = 'style' | 'text' | 'visibility' | 'alerts';

const COLORS = ['#38bdf8', '#10b981', '#f43f5e', '#fbbf24', '#a78bfa', '#e5e7eb'];
const WIDTHS = [1, 2, 3];
const LINE_STYLES = [
  { key: 'solid', label: 'توپر' },
  { key: 'dashed', label: 'خط‌چین' },
  { key: 'dotted', label: 'نقطه‌چین' },
];

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

  if (!last) return null;
  const custom = last.name.startsWith('fts');

  const tabs: { id: Tab; label: string }[] = [
    { id: 'style', label: 'استایل' },
    { id: 'text', label: 'متن' },
    { id: 'visibility', label: 'نمایان' },
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
              onClick={() => api?.updateLast({ styles: { color: c } })}
              className="h-5 w-5 rounded-full border border-border-c"
              style={{ background: c }}
            />
          ))}
          <span className="text-[10px] text-text-muted">ضخامت</span>
          {WIDTHS.map((w) => (
            <Chip key={w} active={false} label={String(w)} onClick={() => api?.updateLast({ styles: { size: w } })} />
          ))}
          <span className="text-[10px] text-text-muted">نوع خط</span>
          {LINE_STYLES.map((s) => (
            <Chip key={s.key} active={false} label={s.label} onClick={() => api?.updateLast({ styles: { style: s.key } })} />
          ))}
          {custom ? (
            <span className="w-full text-[10px] text-text-muted">ابزارهای سفارشی FTS استایل ثابت دارند؛ تغییرات استایل روی ابزارهای استاندارد klinecharts اثر دارد.</span>
          ) : null}
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
          <Chip active={false} label="اعمال" onClick={() => api?.updateLast({ extendData: { text } })} />
          <span className="w-full text-[10px] text-text-muted">متن برای ابزارهای «یادداشت/برچسب» معنا دارد؛ در سایر ابزارها نادیده گرفته می‌شود.</span>
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
              api?.updateLast({ styles: { visible: next } });
            }}
          />
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
