/**
 * frontend-v2/src/features/technical/ui/TelegramCatalogList.tsx
 *
 * فهرست مرجع ۶۴ اندیکاتورِ گروه indicators در تلگرام: بندانگشتی + عنوان +
 * کپشنِ خام + نام پیوست‌ها. کلیک روی بندانگشتی تصویر کامل را همان‌جا باز
 * می‌کند؛ مسیر عوض نمی‌شود و صفحه‌ای اضافه نمی‌شود.
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { toFaDigits } from '@shared/lib/fa';
import { useTechnicalStore } from '../model/technicalStore';
import { searchTelegramRows, TELEGRAM_CATALOG, type TelegramRow } from '../lib/telegramIndicatorCatalog';

const THUMB_W = 84;
const THUMB_H = 47;
const MAX_HEIGHT_PX = 420;

export interface TelegramCatalogListProps {
  className?: string;
}

export function TelegramCatalogList({ className = '' }: TelegramCatalogListProps) {
  const [query, setQuery] = useState('');
  const [openRow, setOpenRow] = useState<TelegramRow | null>(null);
  const lightboxRef = useRef<HTMLDivElement | null>(null);

  const active = useTechnicalStore((s) => s.activeUserIndicators);
  const toggle = useTechnicalStore((s) => s.toggleUserIndicator);

  const rows = useMemo(() => searchTelegramRows(query), [query]);

  const closeLightbox = useCallback(() => setOpenRow(null), []);

  useEffect(() => {
    if (!openRow) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpenRow(null);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [openRow]);

  return (
    <div className={`flex flex-col gap-2 ${className}`} data-testid="telegram-catalog-list">
      <div className="flex items-center justify-between gap-2">
        <span className="t-10 font-bold text-accent">کاتالوگ تلگرام ({toFaDigits(TELEGRAM_CATALOG.length)})</span>
        <span className="t-85 text-text-3 font-mono" data-testid="telegram-catalog-count">
          {toFaDigits(rows.length)} سطر
        </span>
      </div>

      <input
        type="search"
        data-testid="telegram-catalog-search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="جستجو در نام، توضیح یا فایل"
        aria-label="جستجو در کاتالوگ تلگرام"
        className="h-7 w-full rounded-[var(--radius-xs)] border border-line bg-panel px-2 t-9 text-text placeholder:text-text-3 focus:outline-none focus:border-accent"
      />

      <div
        className="overflow-y-auto rounded-[var(--radius-sm)] border border-line"
        style={{ maxHeight: `${MAX_HEIGHT_PX}px` }}
      >
        {rows.map((r) => {
          const overlayOn = r.overlayId != null && active.includes(r.overlayId);
          return (
            <div
              key={r.id}
              data-testid={`telegram-row-${r.id}`}
              className="flex items-center gap-2 border-b border-line/40 px-2 py-1 last:border-b-0 odd:bg-panel-2/30"
              style={{ minHeight: '52px' }}
            >
              <button
                type="button"
                data-testid={`telegram-thumb-${r.id}`}
                onClick={() => setOpenRow(r)}
                aria-label={`نمایش تصویر ${r.titleEn || r.id}`}
                className="shrink-0 overflow-hidden rounded-[var(--radius-xs)] border border-line bg-panel"
                style={{ width: `${THUMB_W}px`, height: `${THUMB_H}px` }}
              >
                <img
                  src={r.photoUrl}
                  alt=""
                  width={THUMB_W}
                  height={THUMB_H}
                  loading="lazy"
                  decoding="async"
                  className="h-full w-full object-cover"
                />
              </button>

              <div className="flex min-w-0 flex-1 flex-col gap-0.5">
                <span className="t-95 truncate font-bold text-text">{r.titleEn || r.attachments[0] || r.id}</span>
                <span
                  data-testid={`telegram-caption-${r.id}`}
                  className="t-8 line-clamp-1 text-text-3"
                >
                  {r.captionEn || 'بدون کپشن'}
                </span>
              </div>

              <span className="t-8 shrink-0 font-mono text-text-3">{r.dims || '—'}</span>

              <div className="shrink-0" data-testid={`telegram-status-${r.id}`}>
                {r.overlayId == null ? (
                  <span className="t-8 text-text-3">پیاده‌سازی نشده</span>
                ) : (
                  <button
                    type="button"
                    data-testid={`toggle-indicator-${r.id}`}
                    onClick={() => toggle(r.overlayId as string)}
                    className={`flex items-center gap-1 rounded-[var(--radius-xs)] border px-2 t-9 font-medium transition-colors ${
                      overlayOn
                        ? 'border-emerald-500/40 bg-emerald-500/20 font-bold text-emerald-400'
                        : 'border-line bg-panel text-text-3 hover:text-text'
                    }`}
                  >
                    <span>{overlayOn ? 'روشن' : 'خاموش'}</span>
                    <span className={`h-1.5 w-1.5 rounded-full ${overlayOn ? 'bg-emerald-400' : 'bg-gray-500'}`} />
                  </button>
                )}
              </div>
            </div>
          );
        })}

        {rows.length === 0 && (
          <div className="p-4 t-9 text-center text-text-3">موردی با این عبارت یافت نشد.</div>
        )}
      </div>

      {openRow && (
        <div
          ref={lightboxRef}
          data-testid="telegram-lightbox"
          role="dialog"
          aria-modal="true"
          aria-label={openRow.titleEn || openRow.id}
          tabIndex={-1}
          onClick={closeLightbox}
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 telegram-catalog-lightbox"
        >
          <div
            className="flex max-h-full max-w-4xl flex-col gap-2 rounded-[var(--radius-md)] border border-line bg-panel p-3"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={openRow.photoUrl}
              alt={openRow.titleEn || openRow.id}
              className="max-h-[70vh] w-auto rounded-[var(--radius-sm)] object-contain"
            />
            <div className="flex flex-col gap-1">
              <span className="t-10 font-bold text-text">{openRow.titleEn || openRow.attachments[0] || openRow.id}</span>
              {openRow.captionEn && (
                <p className="t-85 whitespace-pre-line leading-snug text-text-2">{openRow.captionEn}</p>
              )}
              {openRow.attachments.length > 0 && (
                <span className="t-8 font-mono text-text-3">{openRow.attachments.join('، ')}</span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
