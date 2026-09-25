// features/fundamental/components/AuditBadge.tsx -- بج ممیزی/شفافیت وضعیت
// یک بجِ متراکم با وضعیت (قبول سبز · مردود قرمز · N/A خاکستری) که با hover یا
// کلیک، کارت «چرا این وضعیت؟» را باز می‌کند: ۱) سربرگ ۲) جدول مقایسهٔ مقدار
// واقعی سهم با تارگت FTS + انحراف ۳) متن تشریحی علت (+ مرجع قاعده).
// دادهٔ ممیزی از فیلدهای بک‌اند (reason/actual_value/target_threshold/rule_ref)
// می‌آید؛ اگر نبود، فقط همان چیزی که هست نشان داده می‌شود — هیچ عدد ساختگی.
// Popover بدون Radix: createPortal + position:fixed (همان الگوی MarketFilters).
import { memo, useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { fmtPctGrouped } from '../lib/numFmt';

export type AuditState = 'pass' | 'fail' | 'na';

/** شاهدِ ممیزی؛ اگر تابع داده شود فقط هنگام باز شدن کارت («چرا این وضعیت؟») محاسبه می‌شود */
export type AuditEvidenceInput = AuditEvidence | (() => AuditEvidence | null) | null | undefined;

export interface AuditEvidence {
  /** مقدار واقعی سهم (عددی یا متن آماده) */
  actualValue?: number | string | null;
  /** تارگت/آستانهٔ FTS */
  targetThreshold?: number | string | null;
  /** مرجع قاعده (جزوه/موتور) */
  ruleRef?: string | null;
  /** متن تشریحی علت */
  reason?: string | null;
  /** واحد نمایش مقدار (٪، ×، سال …) */
  unit?: string | null;
  /** جهت مطلوب: بالاتر بهتر (پیش‌فرض) یا پایین‌تر بهتر */
  direction?: 'higher' | 'lower' | null;
}

const STATE_STYLE: Record<AuditState, { cls: string; label: string }> = {
  pass: { cls: 'border-accent-green/40 bg-accent-green/15 text-accent-green shadow-xs', label: 'قبول' },
  fail: { cls: 'border-accent-red/40 bg-accent-red/15 text-accent-red shadow-xs', label: 'مردود' },
  na: { cls: 'border-border-c bg-bg-card text-text-secondary shadow-xs', label: 'N/A' },
};

const NO_AUDIT_TEXT = 'توضیحات تکمیلی برای این وضعیت ثبت نشده است.';

function fmtValue(v: number | string | null | undefined, unit?: string | null): string | null {
  if (v == null || v === '') return null;
  if (typeof v === 'number') {
    // F-10: جداکنندهٔ هزارگان — مقادیر غول‌آسا جدول مقایسه را نمی‌شکنند
    if (unit === '٪') {
      const pct = fmtPctGrouped(v, 2);
      if (pct) return pct;
    }
    const [int, frac] = v.toFixed(2).split('.');
    const grouped = int.replace(/\B(?=(\d{3})+(?!\d))/g, '٬');
    const s = toFaDigits(Number(frac) === 0 ? grouped : `${grouped}.${frac}`);
    return unit ? `${s}${unit}` : s;
  }
  return v;
}

/** انحراف مقدار واقعی از تارگت — جهت‌آگاه (higher: bigger is better) */
export function auditDeviation(
  actual: number | string | null | undefined,
  target: number | string | null | undefined,
  direction: 'higher' | 'lower' | null = 'higher',
): { delta: number; pct: number | null; meets: boolean } | null {
  if (typeof actual !== 'number' || typeof target !== 'number') return null;
  if (!Number.isFinite(actual) || !Number.isFinite(target)) return null;
  const raw = actual - target;
  const delta = direction === 'lower' ? -raw : raw;
  const pct = target !== 0 ? (delta / Math.abs(target)) * 100 : null;
  return { delta, pct, meets: delta >= 0 };
}

/** کارت «چرا این وضعیت؟» — جدول مقایسه + علت + مرجع قاعده */
export function AuditReasonCard({
  state,
  evidence,
  title = 'چرا این وضعیت؟',
}: {
  state: AuditState;
  evidence?: AuditEvidence | null;
  title?: string;
}) {
  const ev = evidence ?? {};
  const actual = fmtValue(ev.actualValue, ev.unit);
  const target = fmtValue(ev.targetThreshold, ev.unit);
  const dev = auditDeviation(ev.actualValue, ev.targetThreshold, ev.direction ?? 'higher');
  const hasTable = actual != null || target != null;
  const reason = ev.reason ?? null;
  return (
    <div
      role="dialog"
      aria-label={title}
      data-testid="audit-popover"
      dir="rtl"
      className="glass-panel panel-in w-[19rem] max-w-[92vw] p-3 text-start"
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <h4 className="text-xs font-black text-text-primary">{title}</h4>
        <span
          className={`inline-flex items-center rounded-full border px-2 py-0.5 text-2xs font-bold ${STATE_STYLE[state].cls}`}
        >
          {STATE_STYLE[state].label}
        </span>
      </div>

      {hasTable ? (
        <table className="w-full text-2xs" data-testid="audit-compare">
          <thead>
            <tr className="text-text-muted">
              <th className="py-1 text-start font-bold">مقدار نماد</th>
              <th className="py-1 text-start font-bold">تارگت FTS</th>
              <th className="py-1 text-start font-bold">انحراف</th>
            </tr>
          </thead>
          <tbody>
            <tr className="num text-text-primary">
              <td className="num py-1" data-testid="audit-actual">
                {actual ?? '—'}
              </td>
              <td className="num py-1" data-testid="audit-target">
                {target ?? '—'}
              </td>
              <td
                className={`py-1 ${dev == null ? 'text-text-muted' : dev.meets ? 'text-accent-green' : 'text-accent-red'}`}
                data-testid="audit-deviation"
              >
                {dev == null
                  ? 'قابل‌محاسبه نیست'
                  : `${dev.delta >= 0 ? '+' : '−'}${toFaDigits(Math.abs(dev.delta).toFixed(2))}${ev.unit ?? ''}${
                      dev.pct == null ? '' : ` (${toFaDigits(Math.abs(dev.pct).toFixed(0))}٪)`
                    }`}
              </td>
            </tr>
          </tbody>
        </table>
      ) : null}

      <p className="mt-2 text-2xs leading-relaxed text-text-secondary" data-testid="audit-reason">
        {reason ?? NO_AUDIT_TEXT}
      </p>

      {ev.ruleRef ? (
        <p className="mt-1.5 text-2xs text-text-muted" data-testid="audit-rule">
          مرجع قاعده: {ev.ruleRef}
        </p>
      ) : null}
    </div>
  );
}

/**
 * بج ممیزی بازیافت‌پذیر. `children` می‌تواند برچسب دلخواه باشد؛ پیش‌فرض، متن
 * وضعیت (قبول/مردود/N/A) است. کلیک روی بج با stopPropagation بسته می‌شود تا
 * داخل سلول‌های کلیک‌پذیر (کارت FTS و ردیف جدول) با رفتار میزبان تضاد نکند.
 */
export const AuditBadge = memo(function AuditBadge({
  state,
  evidence,
  label,
  title,
  testId = 'audit-badge',
  className = '',
  compact = false,
  hintTitle,
}: {
  state: AuditState;
  evidence?: AuditEvidenceInput;
  /** برچسب دلخواه به‌جای متن پیش‌فرض وضعیت */
  label?: ReactNode;
  /** سربرگ کارت بازشو */
  title?: string;
  testId?: string;
  className?: string;
  /** حالت متراکم جدول (بدون حاشیهٔ پُر) */
  compact?: boolean;
  /** متن tooltip بومی مرورگر روی خود بج (پیش از باز شدن کارت) */
  hintTitle?: string;
}) {
  const [open, setOpen] = useState(false);
  const [pinned, setPinned] = useState(false);
  const [pos, setPos] = useState<{ top: number; right: number } | null>(null);
  /** شاهدِ رندرشدهٔ کارت — با تابعِ تنبل فقط لحظهٔ باز شدن محاسبه می‌شود (حالت بسته = صفر محاسبه) */
  const [resolved, setResolved] = useState<AuditEvidence | null>(null);
  const ref = useRef<HTMLSpanElement | null>(null);
  const popId = useId();

  const place = useCallback(() => {
    const rect = ref.current?.getBoundingClientRect();
    if (!rect) return;
    const width = 320;
    const right = Math.max(8, Math.min(window.innerWidth - rect.right, window.innerWidth - width - 8));
    const below = rect.bottom + 4;
    const top = below + 220 > window.innerHeight && rect.top > 230 ? Math.max(8, rect.top - 224) : below;
    setPos({ top, right });
  }, []);

  /** evidence می‌تواند تابع باشد تا در حالت بسته هیچ محاسبه‌ای انجام نشود */
  const resolveEvidence = useCallback(
    () => (typeof evidence === 'function' ? (evidence() ?? null) : (evidence ?? null)),
    [evidence],
  );

  const close = useCallback(() => {
    setOpen(false);
    setPinned(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    place();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    const onScroll = () => close();
    const onDocClick = (e: MouseEvent) => {
      const t = e.target as Node;
      if (ref.current?.contains(t)) return;
      const pop = document.getElementById(popId);
      if (pop?.contains(t)) return;
      close();
    };
    window.addEventListener('keydown', onKey);
    window.addEventListener('scroll', onScroll, true);
    window.addEventListener('resize', onScroll);
    document.addEventListener('mousedown', onDocClick);
    return () => {
      window.removeEventListener('keydown', onKey);
      window.removeEventListener('scroll', onScroll, true);
      window.removeEventListener('resize', onScroll);
      document.removeEventListener('mousedown', onDocClick);
    };
  }, [open, close, place, popId]);

  const style = STATE_STYLE[state];
  return (
    <span
      ref={ref}
      className={`inline-flex ${className}`}
      onMouseEnter={() => {
        if (!open) {
          place();
          setResolved(resolveEvidence());
          setOpen(true);
        }
      }}
      onMouseLeave={() => {
        if (!pinned) close();
      }}
      onFocus={() => {
        if (!open) {
          place();
          setResolved(resolveEvidence());
          setOpen(true);
        }
      }}
      onBlur={() => {
        if (!pinned) close();
      }}
    >
      {/* راه‌انداز با span نقش‌دار (نه <button>) — این بج داخل سلول‌های کلیک‌پذیر کارت
          (که خودشان <button> هستند) رندر می‌شود و button تودرتو HTML نامعتبر است. */}
      <span
        role="button"
        tabIndex={0}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-describedby={open ? popId : undefined}
        title={hintTitle}
        data-testid={testId}
        onClick={(e) => {
          e.stopPropagation();
          if (open && pinned) close();
          else {
            place();
            setResolved(resolveEvidence());
            setOpen(true);
            setPinned(true);
          }
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            e.stopPropagation();
            if (open && pinned) close();
            else {
              place();
              setResolved(resolveEvidence());
              setOpen(true);
              setPinned(true);
            }
          }
        }}
        className={`inline-flex cursor-pointer items-center justify-center font-bold transition-colors shrink-0 leading-none ${
          compact
            ? typeof label === 'string' && label.length <= 2
              ? 'h-5 w-5 rounded-full text-xs font-black border'
              : 'px-2 py-0.5 rounded-md text-2xs border'
            : 'px-2.5 py-0.5 rounded-full border text-2xs gap-1'
        } ${style.cls}`}
      >
        {label ?? style.label}
        {!compact && (
          <span aria-hidden className="text-2xs leading-none opacity-80 select-none">
            ⓘ
          </span>
        )}
      </span>
      {open && typeof document !== 'undefined'
        ? createPortal(
            <span
              id={popId}
              style={{
                position: 'fixed',
                top: pos?.top ?? 0,
                right: pos?.right ?? 0,
                zIndex: 9999,
              }}
            >
              <AuditReasonCard state={state} evidence={resolved} title={title} />
            </span>,
            document.body,
          )
        : null}
    </span>
  );
});
