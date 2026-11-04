import { useState } from 'react';
import type { FtsCard } from '../api/useFtsCard';

const AXES = [
  { digit: '۱', label: 'رشد فروش' },
  { digit: '۲', label: 'سودآوری ۳ ساله' },
  { digit: '۳', label: 'حاشیهٔ سود' },
  { digit: '۴', label: 'پتانسیل سود' },
  { digit: '۵', label: 'قیمت‌گذاری صنعت' },
] as const;

const STATE_TONE: Record<string, string> = {
  pass: 'border-up/45 bg-up/15 text-up',
  fail: 'border-down/45 bg-down/15 text-down',
  warn: 'border-warn/45 bg-warn/10 text-warn',
};

const STATE_WORD: Record<string, string> = {
  pass: 'قبول',
  fail: 'رد',
  warn: 'هشدار',
};

export function AxisDrilldown({ card }: { card: FtsCard }) {
  const [active, setActive] = useState<string>('۱');
  const detail = card.details?.[active];

  return (
    <section data-testid="axis-drilldown" className="rounded-[var(--radius-sm)] border border-line bg-panel">
      <div className="flex flex-wrap gap-1 border-b border-line px-2 py-1" role="tablist" aria-label="جزئیات پنج محور">
        {AXES.map((axis) => (
          <button
            key={axis.digit}
            type="button"
            role="tab"
            aria-selected={active === axis.digit}
            data-testid={`axis-tab-${axis.digit}`}
            onClick={() => setActive(axis.digit)}
            className={`tape-btn ${active === axis.digit ? 'text-accent' : ''}`}
          >
            {axis.digit}. {axis.label}
          </button>
        ))}
      </div>

      {!detail ? (
        <p data-testid="axis-empty" className="p-2 t-95 text-text-3">جزئیاتِ این محور در کارت نیست.</p>
      ) : (
        <div data-testid={`axis-panel-${active}`} className="flex flex-col gap-1 p-2 t-9">
          {detail.title ? <b className="t-10 text-text">{detail.title}</b> : null}
          {detail.formula ? (
            <p className="leading-relaxed text-text-2"><span className="text-text-3">فرمول: </span>{detail.formula}</p>
          ) : null}
          {detail.source ? (
            <p data-testid="axis-source" className="leading-relaxed text-text-3">منبع: {detail.source}</p>
          ) : null}
          {detail.calc ? (
            <p data-testid="axis-calc" className="leading-relaxed text-text-2">{detail.calc}</p>
          ) : null}
          {detail.what ? (
            <div className="leading-relaxed text-text-3">
              {detail.what.split('<br>').filter(Boolean).map((line, index) => (
                <p key={index} className="whitespace-pre-wrap">{line}</p>
              ))}
            </div>
          ) : null}

          {detail.subchecks?.length ? (
            <div className="mt-1 flex flex-col gap-1">
              {detail.subchecks.map((sub, index) => {
                const state = sub.state ?? 'na';
                return (
                  <div
                    key={sub.key ?? index}
                    data-testid={`axis-subcheck-${active}-${sub.key ?? index}`}
                    className="flex flex-wrap items-baseline gap-1.5 rounded-[var(--radius-xs)] border border-line bg-panel-2 px-1.5 py-1"
                  >
                    <span className={`rounded-[3px] border px-1 t-85 ${STATE_TONE[state] ?? 'border-line text-text-3'}`}>
                      {STATE_WORD[state] ?? state}
                    </span>
                    {sub.label ? <span className="font-bold text-text-2">{sub.label}</span> : null}
                    {sub.value ? <span className="num text-text">{sub.value}</span> : null}
                    {sub.threshold ? <span className="text-text-3">{sub.threshold}</span> : null}
                    {sub.detail ? <span className="w-full text-text-3">{sub.detail}</span> : null}
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
}
