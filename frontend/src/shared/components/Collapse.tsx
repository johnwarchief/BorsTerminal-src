// shared/components/Collapse.tsx -- نشانهٔ مشترکِ «این نوار باز می‌شود»
// کاربر گفت نوارهایِ دراپ‌داونی (مثل «نمودارهای جریان سفارش‌ها») شبهِ تیترِ
// متنی‌اند و نمی‌فهمد کلیک‌پذیرند. سه چیز همینجا یکجا می‌آید: چیپِ شِورونِ
// دایره‌ای که ۱۸۰ درجه می‌چرخد، برچسبِ «باز کردن» وقتی بسته است، و انیمیشنِ
// ارتفاع وقتی محتوا باز می‌شود (.collapse-in در index.css).
import type { ReactNode } from 'react';

/** شِورونِ داخلِ یک دایره؛ بسته ⇒ رو به پایین، باز ⇒ ۱۸۰ درجه چرخیده */
export function Chevron({ open, className = '' }: { open: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-c bg-bg-card text-text-secondary transition-transform duration-200 ease-out ${
        open ? 'rotate-180' : ''
      } ${className}`}
    >
      <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
        <path d="M2 3.5 5 6.5 8 3.5" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

/**
 * دکمهٔ تمام‌عرضِ نوارهای بازشو. برچسبِ «باز کردن» فقط در حالتِ بسته دیده
 * می‌شود: وقتی باز است خودِ محتوا روشن است و برچسب جای بی‌مصرف می‌گیرد.
 */
export function CollapseToggle({
  open,
  onToggle,
  label,
  openLabel = 'باز کردن',
  testId,
}: {
  open: boolean;
  onToggle: () => void;
  label: ReactNode;
  openLabel?: string;
  testId?: string;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      data-testid={testId}
      title={open ? 'بستن' : openLabel}
      className="group flex w-full items-center justify-between gap-2 rounded-xl border border-transparent px-1 py-1 text-start text-xs font-black text-text-primary transition-colors duration-200 hover:border-border-c hover:bg-bg-card/70 hover:text-accent-blue"
    >
      <span className="flex min-w-0 items-center gap-2">
        <Chevron open={open} className="group-hover:border-border-accent group-hover:text-accent-blue" />
        <span className="min-w-0 truncate">{label}</span>
      </span>
      {open ? null : (
        <span
          data-testid={testId ? `${testId}-hint` : undefined}
          className="shrink-0 rounded-full border border-dashed border-border-accent/70 px-2 py-0.5 text-3xs font-bold text-accent-blue opacity-80 transition-opacity duration-200 group-hover:opacity-100"
        >
          {openLabel}
        </span>
      )}
    </button>
  );
}

/** بدنهٔ بازشو: فقط وقتی باز است در DOM می‌آید و همان لحظه از ارتفاعِ صفر باز می‌شود */
export function CollapseBody({ open, children, testId }: { open: boolean; children: ReactNode; testId?: string }) {
  if (!open) return null;
  return (
    <div data-testid={testId} className="collapse-in">
      <div className="min-w-0">{children}</div>
    </div>
  );
}
