import { useMemo } from 'react';
import { faNum, fmtInt, fmtMcap, fmtVolume, toFaDigits } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import type { StatusMode } from '@shared/stores/uiStore';
import type { MarketFeed, MarketRow } from '@shared/types/market';

import { boardSums, breadthOf, compositionOf, TYPE_LABEL, type Breadth } from '../lib/boardMetrics';

export { breadthOf, type Breadth } from '../lib/boardMetrics';

function hm(sql: string | null | undefined): string {
  if (!sql) return '—';
  const m = sql.match(/(\d{1,2}):(\d{2})/);
  return m ? toFaDigits(`${m[1]!.padStart(2, '0')}:${m[2]}`) : '—';
}

const MODES: { key: StatusMode; label: string }[] = [
  { key: 'full', label: 'کامل' },
  { key: 'ribbon', label: 'نوار' },
  { key: 'minimal', label: 'کمینه' },
];

function ModeSwitch({ mode, onChange }: { mode: StatusMode; onChange: (mode: StatusMode) => void }) {
  return (
    <div className="status-modes" role="group" aria-label="حالت نوار وضعیت">
      {MODES.map((m) => (
        <button
          key={m.key}
          type="button"
          data-testid={`status-${m.key}`}
          aria-pressed={mode === m.key}
          onClick={() => onChange(m.key)}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

function BreadthBar({ breadth }: { breadth: Breadth }) {
  return (
    <div className="breadth-bar" aria-hidden>
      <i className="b-up" style={{ width: `${breadth.upPct}%` }} />
      <i className="b-flat" style={{ width: `${breadth.flatPct}%` }} />
      <i className="b-down" style={{ width: `${breadth.downPct}%` }} />
    </div>
  );
}

interface Props {
  feed?: MarketFeed;
  rows: readonly MarketRow[];
  mode: StatusMode;
  onMode: (mode: StatusMode) => void;
}

export function StatusStrip({ feed, rows, mode, onMode }: Props) {
  const breadth = useMemo(() => breadthOf(rows), [rows]);
  const sums = useMemo(() => boardSums(rows), [rows]);
  const composition = useMemo(() => compositionOf(rows), [rows]);
  const meta = feed?.meta;
  const day = jalaliFromYmd(meta?.d_even);
  const sync = hm(meta?.last_sync);

  if (mode === 'minimal') {
    return (
      <div
        data-testid="status-strip"
        className="flex h-[31px] shrink-0 items-center gap-4 overflow-hidden border-b border-line bg-panel px-3"
      >
        <span className="pulse-item">
          <span className="t-9 text-text-3">تابلو</span>
          <b className="num t-11 font-bold">{fmtInt(rows.length)}</b>
        </span>
        <span className="pulse-item">
          <span className="t-9 text-text-3">ارزش</span>
          <b className="num t-11 font-bold">{fmtMcap(sums.value)}</b>
          <span className="t-9 text-text-3">همت</span>
        </span>
        <span className="pulse-item">
          <span className="t-9 text-text-3">پهنا</span>
          <b className="num t-10 text-up">{fmtInt(breadth.up)}▲</b>
          <b className="num t-10 text-down">{fmtInt(breadth.down)}▼</b>
        </span>
        <span className="pulse-item">
          <span className="t-9 text-text-3">آخرین همگام‌سازی</span>
          <b className="num t-10 font-semibold">{sync}</b>
        </span>
        <ModeSwitch mode={mode} onChange={onMode} />
      </div>
    );
  }

  if (mode === 'ribbon') {
    return (
      <div
        data-testid="status-strip"
        className="flex h-[33px] shrink-0 items-center overflow-hidden border-b border-line bg-panel px-3"
      >
        <span className="pulse-item" title="تعدادِ ردیف‌های همین پیلود">
          <span className="t-9 text-text-3">تابلو</span>
          <b className="num t-11 font-bold">{fmtInt(rows.length)}</b>
        </span>
        <span className="pulse-item" title="جمعِ ارزش معاملاتِ ردیف‌های تابلو">
          <span className="t-9 text-text-3">ارزش</span>
          <b className="num t-11 font-bold">{fmtMcap(sums.value)}</b>
          <span className="t-9 text-text-3">همت</span>
        </span>
        <span className="pulse-item">
          <span className="t-9 text-text-3">حجم</span>
          <b className="num t-11 font-bold">{fmtVolume(sums.volume)}</b>
        </span>
        <span className="pulse-item" title="شمارشِ تغییر قیمت پایانی روی همهٔ ردیف‌های تابلو">
          <span className="t-9 text-text-3">پهنا</span>
          <span className="breadth-mini-bar" aria-hidden>
            <i className="b-up" style={{ width: `${breadth.upPct}%` }} />
            <i className="b-flat" style={{ width: `${breadth.flatPct}%` }} />
            <i className="b-down" style={{ width: `${breadth.downPct}%` }} />
          </span>
          <b className="num t-10 text-up">{fmtInt(breadth.up)}▲</b>
          <b className="num t-10 text-down">{fmtInt(breadth.down)}▼</b>
        </span>
        <span className="pulse-item">
          <span className="t-9 text-text-3">آخرین همگام‌سازی</span>
          <b className="num t-10 font-semibold">{sync}</b>
        </span>
        <ModeSwitch mode={mode} onChange={onMode} />
      </div>
    );
  }

  return (
    <div data-testid="status-strip" className="flex shrink-0 items-stretch border-b border-line bg-panel px-3 py-[7px]">
      <div className="status-grid">
        <section className="status-card">
          <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
            <span>ارزش معاملات تابلو</span>
            <em className="t-85 font-normal not-italic text-text-3">{day}</em>
          </div>
          <div className="mt-0.5 flex items-baseline gap-1.5">
            <b className="num text-[19px] font-extrabold leading-none tracking-tight">{fmtMcap(sums.value)}</b>
            <small className="t-95 text-text-3">همت</small>
          </div>
          <div className="mt-1 flex flex-wrap items-baseline gap-x-2.5 gap-y-0.5 t-9 text-text-3">
            <span>
              حجم <b className="num font-semibold text-text-2">{fmtVolume(sums.volume)}</b>
            </span>
            <span>
              ردیف <b className="num font-semibold text-text-2">{fmtInt(rows.length)}</b>
            </span>
          </div>
        </section>

        <section className="status-card">
          <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
            <span>پهنا</span>
            <em className="t-85 font-normal not-italic text-text-3">تغییر قیمت پایانی</em>
          </div>
          <div className="mt-0.5 flex items-baseline gap-1 t-85 text-text-3">
            <b className="num text-[15px] leading-none text-up">{fmtInt(breadth.up)}</b>
            <span className="me-1.5">مثبت</span>
            <b className="num text-[15px] leading-none text-down">{fmtInt(breadth.down)}</b>
            <span className="me-1.5">منفی</span>
            <b className="num text-[15px] leading-none text-flat">{fmtInt(breadth.flat)}</b>
            <span>بی‌تغییر</span>
          </div>
          <BreadthBar breadth={breadth} />
          <div className="mt-1 flex flex-wrap items-baseline gap-x-1.5 t-85 text-text-3">
            <span>{faNum(breadth.upPct)}٪ مثبت</span>
            <span>·</span>
            <span>{faNum(breadth.flatPct)}٪ بی‌تغییر</span>
            <span>·</span>
            <span>{faNum(breadth.downPct)}٪ منفی</span>
            {breadth.unknown > 0 && (
              <>
                <span>·</span>
                <span title="در این ردیف‌ها درصدِ تغییر خوانا نیست">{fmtInt(breadth.unknown)} بدون تغییرِ خوانا</span>
              </>
            )}
          </div>
        </section>

        <section className="status-card">
          <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
            <span>ترکیب تابلو</span>
            <em className="t-85 font-normal not-italic text-text-3">نوع دارایی</em>
          </div>
          <div className="mt-1 grid grid-cols-3 gap-x-2 gap-y-[3px] t-95">
            {composition.map(({ type, count }) => (
              <span key={type} className="flex items-baseline justify-between gap-1 whitespace-nowrap text-text-3">
                <span>{TYPE_LABEL[type]}</span>
                <b className="num font-semibold text-text-2">{fmtInt(count)}</b>
              </span>
            ))}
          </div>
        </section>

        <section className="status-card">
          <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
            <span>تازگی داده</span>
            <em className="t-85 font-normal not-italic text-text-3">‎/api/market</em>
          </div>
          <div className="mt-0.5 flex flex-col">
            <div className="flex items-baseline justify-between gap-2 t-85 text-text-3">
              <span>آخرین همگام‌سازی</span>
              <b className="num font-semibold text-text-2">{sync}</b>
            </div>
            <div className="flex items-baseline justify-between gap-2 t-85 text-text-3">
              <span>روزِ داده</span>
              <b className="num font-semibold text-text-2">{day}</b>
            </div>
            <div className="flex items-baseline justify-between gap-2 t-85 text-text-3">
              <span>زنده / کهنه</span>
              <b className="num font-semibold text-text-2">
                <span className="text-up">{fmtInt(feed?.live_count)}</span>
                <span className="px-1 text-text-3">·</span>
                <span>{fmtInt(feed?.fossil_count)}</span>
              </b>
            </div>
            <div className="flex items-baseline justify-between gap-2 t-85 text-text-3">
              <span>ردیف‌ها</span>
              <b className="num font-semibold text-text-2">{fmtInt(rows.length)}</b>
            </div>
          </div>
        </section>
      </div>
      <ModeSwitch mode={mode} onChange={onMode} />
    </div>
  );
}
