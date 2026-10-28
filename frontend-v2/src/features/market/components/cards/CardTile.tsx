import { useState } from 'react';
import clsx from 'clsx';
import { faNum } from '@shared/lib/fa';
import type { CardId } from '@shared/workspace/store';
import { CARD_ORDER, CARD_REGISTRY, type CardContext, type CardDescriptor } from './registry';

interface Props {
  descriptor: CardDescriptor;
  context: CardContext;
  onMoveLeft: () => void;
  onMoveRight: () => void;
  onPick: (id: CardId) => void;
}

export function CardTile({ descriptor, context, onMoveLeft, onMoveRight, onPick }: Props) {
  const [open, setOpen] = useState(false);
  const [picking, setPicking] = useState(false);
  const value = descriptor.value(context);
  const delta = descriptor.delta(context);
  const rows = descriptor.preview(context);

  return (
    <section
      data-testid={`card-${descriptor.id}`}
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
      onFocus={() => setOpen(true)}
      onBlur={() => setOpen(false)}
      tabIndex={0}
      className="relative min-w-0 flex-1 rounded-[var(--radius-sm)] border border-line bg-panel px-2 py-1"
    >
      <div className="flex items-baseline justify-between gap-2 t-9 font-bold text-text-2">
        <span className="truncate">{descriptor.label}</span>
        <div className="flex items-center gap-0.5">
          <button type="button" data-testid={`card-move-right-${descriptor.id}`} aria-label="یک خانه به راست"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={onMoveRight}>›</button>
          <button type="button" data-testid={`card-move-left-${descriptor.id}`} aria-label="یک خانه به چپ"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={onMoveLeft}>‹</button>
          <button type="button" data-testid={`card-pick-${descriptor.id}`} aria-label="تغییرِ کارت"
            className="grid h-4 w-4 place-items-center rounded-[var(--radius-xs)] text-text-3 hover:bg-panel-2"
            onClick={() => setPicking((value) => !value)}>⋯</button>
        </div>
      </div>

      <div className="mt-0.5 flex items-baseline gap-1.5">
        <b className="num text-[19px] font-extrabold leading-none tracking-tight">{value ?? '—'}</b>
        {descriptor.unit && value != null ? <small className="t-95 text-text-3">{descriptor.unit}</small> : null}
        {delta != null ? (
          <span className={clsx('num t-9', delta > 0 ? 'text-up' : delta < 0 ? 'text-down' : 'text-flat')}>
            {delta > 0 ? '▲' : delta < 0 ? '▼' : '•'} {faNum(Math.abs(Math.round(delta * 10) / 10))}٪
          </span>
        ) : (
          <span className="t-9 text-text-3" title="نشستِ قبلِ هم‌مبنا در دسترس نیست">—</span>
        )}
      </div>

      {picking ? (
        <div className="absolute inset-x-0 top-full z-30 mt-1 rounded-[var(--radius-sm)] border border-line bg-panel p-1 t-9">
          {CARD_ORDER
            .filter((id) => id !== descriptor.id)
            .map((id) => (
              <button key={id} type="button" data-testid={`card-option-${descriptor.id}-${id}`}
                className="block w-full rounded-[var(--radius-xs)] px-2 py-1 text-start hover:bg-panel-2"
                onClick={() => { setPicking(false); onPick(id); }}>
                {CARD_REGISTRY[id].label}
              </button>
            ))}
        </div>
      ) : null}

      {open && !picking ? (
        <div data-testid={`preview-${descriptor.id}`}
          className="absolute inset-x-0 top-full z-30 mt-1 rounded-[var(--radius-sm)] border border-line bg-panel p-1.5 t-9 text-text-2">
          <div className="mb-1 flex items-center justify-between text-text-3">
            <span>{descriptor.basis === 'board' ? 'تابلو' : 'کل بازار'}</span>
            <span className="t-85">پیش‌نمایش</span>
          </div>
          {rows.map((row) => (
            <div key={row.label} className="flex items-baseline justify-between gap-2">
              <span className="text-text-3">{row.label}</span>
              <span className="num font-semibold" title={row.note}>{row.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </section>
  );
}
