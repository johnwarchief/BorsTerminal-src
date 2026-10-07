import { createPortal } from 'react-dom';
import { Link } from 'react-router';
import { StrategyTreeStepper } from './StrategyTreeStepper';

export function StrategyTreeDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  if (!open) return null;
  return createPortal(
    <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-black/75 p-4" role="presentation" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div role="dialog" aria-modal="true" aria-labelledby="strategy-tree-new-title" className="w-full max-w-5xl rounded-3xl border border-border-c bg-bg-primary shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-border-c p-4 sm:p-5">
          <div>
            <div className="text-3xs font-black uppercase tracking-[0.18em] text-accent-blue">FTS · Roadmap</div>
            <h2 id="strategy-tree-new-title" className="mt-1 text-base font-black text-text-primary">درخت جدید استراتژی FTS</h2>
            <p className="mt-1 text-2xs leading-5 text-text-muted">نمای گراف قدیمی حذف شده؛ نقشهٔ جدید چهار صفحه را ساده، روشن و مرحله‌ای نشان می‌دهد.</p>
          </div>
          <button type="button" onClick={onClose} aria-label="بستن" className="rounded-xl border border-border-c px-2 py-1 text-text-muted hover:text-text-primary">✕</button>
        </div>
        <div className="p-4 sm:p-5">
          <StrategyTreeStepper active={null} preset="trend" />
          <div className="mt-5 rounded-2xl border border-border-c bg-bg-card/50 p-4 text-xs leading-6 text-text-secondary">
            برای نقشهٔ کامل، روی یکی از چهار صفحه بروید یا نمای یک‌صفحه‌ای را باز کنید.
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-xl border border-border-c px-3 py-2 text-2xs font-bold text-text-secondary hover:text-text-primary">بستن</button>
            <Link to="/strategy-tree" onClick={onClose} className="rounded-xl bg-accent-blue px-4 py-2 text-2xs font-black text-black hover:bg-accent-blue/90">بازکردن درخت FTS ←</Link>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
