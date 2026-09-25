// features/fundamental/components/MathFormula.tsx -- نمایش استاندارد فرمول‌های ریاضی صورت‌های مالی
import type { ReactNode } from 'react';

/** کسر ریاضی استاندارد با خط کسری واقعی (Vinculum) */
export function MathFraction({
  numerator,
  denominator,
  className = '',
}: {
  numerator: ReactNode;
  denominator: ReactNode;
  className?: string;
}) {
  return (
    <span className={`inline-flex flex-col items-center justify-center align-middle text-center leading-none ${className}`}>
      <span className="w-full border-b border-current/70 px-1 pb-0.5 text-center font-bold">
        {numerator}
      </span>
      <span className="w-full px-1 pt-0.5 text-center font-bold">
        {denominator}
      </span>
    </span>
  );
}

/** بلوک فرمول ریاضی با نمادگذاری دقیق */
export function MathFormulaBlock({
  children,
  className = '',
  dir = 'ltr',
}: {
  children: ReactNode;
  className?: string;
  dir?: 'ltr' | 'rtl';
}) {
  return (
    <div
      dir={dir}
      className={`inline-flex items-center justify-center gap-1.5 rounded-lg border border-border-c/50 bg-bg-card/40 px-2 py-1 font-mono text-2xs select-none ${className}`}
    >
      {children}
    </div>
  );
}
