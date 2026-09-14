// features/portfolio/components/TargetEditModal.tsx -- مودال ویرایش دستی درصدها
// اعتبارسنجی: جمع ≤ ۱۰۰٪ — با پیام خطا؛ ذخیره با نرمال‌سازی به ۱۰۰٪.
import { useState } from 'react';
import { Modal } from '@shared/components/Modal';
import { toFaDigits } from '@shared/lib/fmt';
import { isValidAllocation, sumPct, useTargetAllocation, type TargetClass } from '../stores/targetAllocation';

const PALETTE = ['#f59e0b', '#eab308', '#22d3ee', '#94a3b8', '#10b981', '#64748b', '#38bdf8', '#f43f5e'];

export function TargetEditModal({ open, onClose }: { open: boolean; onClose: () => void }) {
  const classes = useTargetAllocation((s) => s.classes);
  const setClasses = useTargetAllocation((s) => s.setClasses);
  const reset = useTargetAllocation((s) => s.reset);

  const [draft, setDraft] = useState<TargetClass[]>(classes.map((c) => ({ ...c })));
  const [err, setErr] = useState<string | null>(null);
  const [newLabel, setNewLabel] = useState('');
  const total = sumPct(draft);

  const editPct = (id: string, pct: number) => {
    setDraft((d) => d.map((c) => (c.id === id ? { ...c, pct: Math.max(0, Math.round(pct * 10) / 10) } : c)));
  };

  const save = () => {
    if (!isValidAllocation(draft)) {
      setErr('جمع درصدها باید بین ۱ و ۱۰۰ درصد باشد.');
      return;
    }
    setErr(null);
    setClasses(draft);
    onClose();
  };

  const add = () => {
    const label = newLabel.trim();
    if (!label) {
      setErr('نام دارایی خالی است.');
      return;
    }
    const id = `custom-${Date.now()}`;
    const color = PALETTE[draft.length % PALETTE.length];
    setDraft((d) => [...d, { id, label, pct: 0, color }]);
    setNewLabel('');
    setErr(null);
  };

  if (!open) return null;

  return (
    <Modal title="ویرایش دارایی‌های هدف" onClose={onClose}>
      <div className="flex flex-col gap-3">
        <ul className="flex max-h-80 flex-col gap-2 overflow-y-auto pl-1">
          {draft.map((c) => (
            <li key={c.id} className="flex items-center gap-2">
              <span className="inline-block h-3 w-3 shrink-0 rounded-sm" style={{ background: c.color }} aria-hidden />
              <label className="min-w-0 flex-1 truncate text-xs font-bold text-text-primary" title={c.label}>
                {c.label}
              </label>
              <input
                type="number"
                min={0}
                max={100}
                step={0.5}
                value={c.pct}
                onChange={(e) => editPct(c.id, Number(e.target.value))}
                aria-label={`درصد ${c.label}`}
                className="num w-20 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 text-left text-xs text-text-primary outline-none focus:border-border-accent"
                dir="ltr"
              />
              <span className="text-xs text-text-muted">٪</span>
              {c.id.startsWith('custom-') ? (
                <button
                  type="button"
                  onClick={() => setDraft((d) => d.filter((x) => x.id !== c.id))}
                  aria-label={`حذف ${c.label}`}
                  className="rounded-md border border-transparent px-1.5 text-xs text-text-muted hover:border-accent-red/40 hover:text-accent-red"
                >
                  ✕
                </button>
              ) : null}
            </li>
          ))}
        </ul>

        <div className="flex flex-wrap items-center gap-2 rounded-xl border border-dashed border-border-c bg-bg-secondary/40 p-2">
          <input
            type="text"
            value={newLabel}
            onChange={(e) => setNewLabel(e.target.value)}
            placeholder="نام دارایی جدید..."
            aria-label="نام دارایی جدید"
            className="min-w-0 flex-1 rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-xs text-text-primary outline-none focus:border-border-accent"
          />
          <button
            type="button"
            onClick={add}
            className="rounded-full border border-neon-cyan/40 bg-neon-cyan/10 px-3 py-1 text-[11px] font-bold text-neon-cyan hover:bg-neon-cyan/20"
          >
            افزودن دارایی
          </button>
        </div>

        <div className="flex items-center justify-between border-t border-[var(--hairline)] pt-3">
          <span className={`num text-xs font-bold ${total > 100 ? 'text-accent-red' : 'text-text-secondary'}`}>
            جمع: {toFaDigits(Math.round(total * 10) / 10)}٪
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={() => {
                reset();
                setDraft(useTargetAllocation.getState().classes.map((c) => ({ ...c })));
                setErr(null);
              }}
              className="rounded-full border border-border-c px-3 py-1.5 text-[11px] font-bold text-text-secondary hover:text-text-primary"
            >
              بازنشانی به پیش‌فرض FTS
            </button>
            <button
              type="button"
              onClick={save}
              className="rounded-full border border-accent-green/40 bg-accent-green/15 px-4 py-1.5 text-[11px] font-bold text-accent-green hover:bg-accent-green/25"
            >
              ذخیره
            </button>
          </div>
        </div>
        {err ? <p className="text-[11px] font-bold text-accent-red">{err}</p> : null}
        <p className="text-[10px] leading-4 text-text-muted">
          ذخیره با نرمال‌سازی جمع به ۱۰۰٪ انجام می‌شود. حذف فقط برای دارایی‌های افزوده‌شده فعال است.
        </p>
      </div>
    </Modal>
  );
}
