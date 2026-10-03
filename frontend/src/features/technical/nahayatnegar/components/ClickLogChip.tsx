// features/technical/nahayatnegar/components/ClickLogChip.tsx -- خطِ کلیکِ چارت
// یک خط در نوارِ پایینی: آخرینِ کلیکی که کاربر زد، با نماد/بازه/میله/نتیجهٔ موتور.
// فهرستِ کامل پشتِ همان خط باز می‌شود تا ارتفاعِ ثابتِ چارت عوض نشود.
import { useState } from 'react';

import { toFaDigits } from '@shared/lib/fmt';
import { useChartClickStore } from '../../stores/chartClickStore';
import { describeClick } from '../lib/barClicks';
import { TIMEFRAME_LABELS } from '../lib/timeframe';

export function ClickLogChip({ symbol }: { symbol: string }) {
  const clicks = useChartClickStore((s) => s.clicks);
  // خطِ دیدنی مالِ همین نماد است؛ در غیر آن پس از عوض‌کردنِ نماد رویدادِ نمادِ
  // قبلی مثلِ رویدادِ امروز خوانده می‌شود. فهرستِ باز‌شونده سراسری می‌ماند.
  const last = clicks.find((c) => c.symbol === symbol) ?? null;
  const clear = useChartClickStore((s) => s.clear);
  const [open, setOpen] = useState(false);

  if (!last) {
    return (
      <div className="nn-timezone-badge" data-testid="chart-click-chip" title="روی یک کندل کلیک کنید">
        <span>کلیک: —</span>
      </div>
    );
  }

  return (
    <div className="nn-timezone-badge" style={{ position: 'relative' }}>
      <button
        type="button"
        className="nn-range-btn"
        data-testid="chart-click-chip"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        title={`${last.symbol} · ${TIMEFRAME_LABELS[last.timeframe]} · ${
          last.kind === 'marker' ? 'مارکر' : 'کندل'
        }`}
      >
        <span className="num">{describeClick(last)}</span>
      </button>

      {open ? (
        <div
          data-testid="chart-click-list"
          title="کلیک‌هایِ این نشست و نشست‌هایِ پیش — از لاگِ محلیِ همین برنامه"
          style={{
            position: 'absolute',
            bottom: '26px',
            insetInlineEnd: '0',
            minWidth: '240px',
            maxWidth: '340px',
            background: '#1e222d',
            border: '1px solid #2a2e39',
            borderRadius: '8px',
            padding: '8px',
            boxShadow: '0 8px 24px rgba(0,0,0,.6)',
            zIndex: 160,
            display: 'flex',
            flexDirection: 'column',
            gap: '4px',
          }}
        >
          {clicks.slice(0, 10).map((c) => (
            <div key={c.key} data-testid="chart-click-row" style={{ fontSize: '11px', color: '#d6dbe6' }}>
              <span style={{ opacity: .75 }}>{c.symbol} · {TIMEFRAME_LABELS[c.timeframe]} · </span>
              <span className="num">{describeClick(c)}</span>
              {' · '}
              <span className="num">{toFaDigits(c.close)}</span>
            </div>
          ))}
          <button type="button" className="nn-range-btn" data-testid="chart-click-clear" onClick={clear}>
            پاک‌کردن
          </button>
        </div>
      ) : null}
    </div>
  );
}
