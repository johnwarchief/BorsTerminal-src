// app/components/CommandPalette.tsx -- پالت فرمان سریع با Ctrl+K / Cmd+K
// جستجوی نماد و پرش بدون ماوس بین مستر، تکنیکال و تابلو.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { toFaDigits } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { useDialogA11y } from '@shared/lib/useDialogA11y';
import { Skeleton } from '@shared/components/Skeleton';

type Dest = 'master' | 'technical' | 'market';

const DESTS: { id: Dest; label: string }[] = [
  { id: 'master', label: 'مستر' },
  { id: 'technical', label: 'تکنیکال' },
  { id: 'market', label: 'تابلو' },
];

type Row = { symbol: string; name: string; sector: string };

export const PALETTE_OPEN_EVENT = 'bors:palette';

function destPath(dest: Dest, symbol: string): string {
  if (dest === 'master') return `/master/${encodeURIComponent(symbol)}`;
  if (dest === 'technical') return `/technical/${encodeURIComponent(symbol)}`;
  return '/market';
}

export function CommandPalette() {
  const navigate = useNavigate();
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [dest, setDest] = useState<Dest>('master');
  const [cursor, setCursor] = useState(0);
  const [rows, setRows] = useState<Row[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const loadedOnce = useRef(false);

  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery('');
    setCursor(0);
    setError(false);
    if (!loadedOnce.current) {
      loadedOnce.current = true;
      setLoading(true);
      http<MarketFeed>('/api/market', { schema: MarketFeedSchema })
        .then((feed) =>
          setRows(
            feed.data
              .filter((r) => r.symbol)
              .map((r) => ({ symbol: r.symbol, name: r.name ?? '', sector: r.sector_name ?? '' })),
          ),
        )
        .catch(() => {
          setError(true);
          loadedOnce.current = false;
        })
        .finally(() => setLoading(false));
    }
  }, []);

  useEffect(() => {
    const onGlobalKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        if (open) setOpen(false);
        else openPalette();
      }
    };
    const onEvent = () => openPalette();
    window.addEventListener('keydown', onGlobalKey);
    window.addEventListener(PALETTE_OPEN_EVENT, onEvent);
    return () => {
      window.removeEventListener('keydown', onGlobalKey);
      window.removeEventListener(PALETTE_OPEN_EVENT, onEvent);
    };
  }, [open, openPalette]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);

  const results = useMemo<Row[]>(() => {
    if (!rows) return [];
    if (!query.trim()) return rows.slice(0, 12);
    return rows
      .filter((r) => matchFa(r.symbol, query) || matchFa(r.name, query))
      .slice(0, 12);
  }, [rows, query]);

  const choose = useCallback(
    (row: Row) => {
      setSymbol(row.symbol);
      setOpen(false);
      navigate(destPath(dest, row.symbol));
    },
    [dest, navigate, setSymbol],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setOpen(false);
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCursor((c) => Math.min(results.length - 1, c + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (e.key === 'Enter' && results[cursor]) {
      e.preventDefault();
      choose(results[cursor]);
    }
  };

  const panelRef = useDialogA11y<HTMLDivElement>({ open, onClose: () => setOpen(false) });

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[200] flex items-start justify-center bg-black/55 p-4 pt-[14vh]"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="glass-panel scale-in w-full max-w-xl overflow-hidden outline-none overscroll-contain"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="پالت فرمان"
        onKeyDown={onKeyDown}
      >
        <div className="flex items-center gap-3 border-b border-[var(--hairline)] px-4 py-3">
          <span className="text-neon-cyan" aria-hidden>
            ⌘
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            placeholder="جستجوی نماد... (برای جابه جایی از کلیدهای جهت استفاده کن)"
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
            aria-label="جستجوی نماد"
          />
          <kbd className="rounded-md border border-border-c px-1.5 py-0.5 text-2xs text-text-muted">Esc</kbd>
        </div>

        <div className="flex items-center gap-2 px-4 py-2">
          <span className="text-xs text-text-muted">مقصد:</span>
          {DESTS.map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setDest(d.id)}
              className={`rounded-full border px-3 py-1 text-xs font-bold transition-colors ${
                dest === d.id
                  ? 'border-border-accent bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c text-text-muted hover:text-text-secondary'
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

        <div className="max-h-[46vh] overflow-y-auto pb-2">
          {loading && (
            <div className="flex flex-col gap-2 px-4 py-4" role="status" aria-live="polite">
              <span className="sr-only">در حال دریافت فهرست نمادها...</span>
              <div className="flex flex-col gap-2" aria-hidden="true">
                <Skeleton className="h-8 w-full" />
                <Skeleton className="h-8 w-5/6" />
                <Skeleton className="h-8 w-2/3" />
              </div>
            </div>
          )}
          {error && <div className="px-4 py-6 text-center text-xs text-accent-red">خطا در دریافت فهرست نمادها</div>}
          {!loading && !error && results.length === 0 && (
            <div className="px-4 py-6 text-center text-xs text-text-muted">نتیجه ای نیست</div>
          )}
          {results.map((r, i) => (
            <button
              key={r.symbol}
              type="button"
              onClick={() => choose(r)}
              onMouseEnter={() => setCursor(i)}
              className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-start text-sm transition-colors ${
                i === cursor ? 'bg-accent-blue/12 text-text-primary' : 'text-text-secondary hover:bg-bg-card/50'
              }`}
            >
              <span>
                <span className="font-black text-text-primary">{r.symbol}</span>
                <span className="ms-2 text-xs text-text-muted">{r.name}</span>
              </span>
              <span className="text-2xs text-text-muted">{r.sector}</span>
            </button>
          ))}
        </div>

        <div className="border-t border-[var(--hairline)] px-4 py-2 text-2xs text-text-muted">
          {toFaDigits(results.length)} نتیجه · Enter برای پرش به {DESTS.find((d) => d.id === dest)?.label}
        </div>
      </div>
    </div>
  );
}
