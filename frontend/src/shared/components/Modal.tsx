// shared/components/Modal.tsx -- پنجره مودال ساده
import { useDialogA11y } from '@shared/lib/useDialogA11y';

export function Modal({
  title,
  onClose,
  children,
}: {
  title: string;
  onClose: () => void;
  children: React.ReactNode;
}) {
  const panelRef = useDialogA11y<HTMLDivElement>({ open: true, onClose });

  return (
    <div
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="presentation"
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="glass-panel scale-in w-full max-w-2xl p-6 outline-none overscroll-contain"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-base font-black text-text-primary">{title}</h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="بستن"
            className="rounded-lg border border-border-c px-2 py-1 text-text-secondary hover:text-accent-blue"
          >
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
