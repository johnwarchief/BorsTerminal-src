// app/components/CommandPalette.tsx -- پالت فرمان سه‌شیاری با Ctrl+K / Cmd+K
// الگوی تحقیق Round UX (Raycast/<GO>/Linear): یک ورودی، سه شیار نتیجه —
// نماد (اول، با اخیر/pinned در صدر)، صفحه، فرمانِ واقعی. هر ردیف سمت‌راستش
// جای‌نما/شرح می‌گیرد نه تزئین. فرمان‌ها فقط کارهایی‌اند که همین‌جا واقعاً اجرا
// می‌شوند (درسِ «دکمه بی‌اثر ممنوع»).
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { http } from '@shared/api/http';
import { MarketFeedSchema, type MarketFeed } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { toFaDigits } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { useDialogA11y } from '@shared/lib/useDialogA11y';
import { Skeleton } from '@shared/components/Skeleton';

type Dest = 'master' | 'technical' | 'fundamental' | 'strategy-tree' | 'market';

const DESTS: { id: Dest; label: string }[] = [
  { id: 'master', label: 'مستر' },
  { id: 'technical', label: 'تکنیکال' },
  { id: 'fundamental', label: 'بنیادی' },
  { id: 'strategy-tree', label: 'درخت' },
  { id: 'market', label: 'تابلو' },
];

const PAGES: { path: string; label: string; hint: string }[] = [
  { path: '/market', label: 'تابلوخوانی / بازار', hint: 'تب' },
  { path: '/technical', label: 'تحلیل تکنیکال', hint: 'تب' },
  { path: '/fundamental', label: 'تحلیل بنیادی', hint: 'تب' },
  { path: '/master', label: 'استراتژی FTS', hint: 'تب' },
  { path: '/strategy-tree', label: 'درخت استراتژی', hint: 'تب' },
  { path: '/portfolio', label: 'مدیریت پرتفوی', hint: 'تب' },
];

type Row = { symbol: string; name: string; sector: string };

type Item =
  | { kind: 'symbol'; id: string; row: Row; recent?: boolean; pinned?: boolean }
  | { kind: 'page'; id: string; page: (typeof PAGES)[number] }
  | { kind: 'command'; id: string; label: string; hint: string; run: () => void };

export const PALETTE_OPEN_EVENT = 'bors:palette';

function destPath(dest: Dest, symbol: string): string {
  if (dest === 'market') return '/market';
  return `/${dest}/${encodeURIComponent(symbol)}`;
}

export function CommandPalette() {
  const navigate = useNavigate();
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);
  const recent = useSymbolStore((s) => s.recent);
  const pinned = useSymbolStore((s) => s.pinned);
  const toggleTheme = useUiStore((s) => s.toggleTheme);
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

  const rowBySymbol = useMemo(() => new Map((rows ?? []).map((r) => [r.symbol, r])), [rows]);

  const commands = useMemo<Item[]>(
    () => [
      {
        kind: 'command',
        id: 'cmd-theme',
        label: 'تغییر پوسته (روشن/تیره)',
        hint: 'Ctrl+K دوباره برای بستن',
        run: () => toggleTheme(),
      },
      {
        kind: 'command',
        id: 'cmd-clear',
        label: 'پاک کردن نمادِ انتخابی',
        hint: 'بازرس و context بسته می‌شوند',
        run: () => clearSymbol(),
      },
      {
        kind: 'command',
        id: 'cmd-funnel',
        label: 'باز کردن قیفِ غربالگری',
        hint: 'استراتژی FTS ▸ بی‌نماد',
        run: () => {
          clearSymbol();
          navigate('/master');
        },
      },
    ],
    [clearSymbol, navigate, toggleTheme],
  );

  const items = useMemo<Item[]>(() => {
    const q = query.trim();
    const out: Item[] = [];
    if (!q) {
      // صدرِ جدول: pinnedها سپس اخیرها (الگوی Notion/TV) — حتی پیش از رسیدن فید
      for (const s of pinned) out.push({ kind: 'symbol', id: 'p_' + s, row: rowBySymbol.get(s) ?? { symbol: s, name: '', sector: '' }, pinned: true });
      for (const s of recent) {
        if (pinned.includes(s)) continue;
        out.push({ kind: 'symbol', id: 'r_' + s, row: rowBySymbol.get(s) ?? { symbol: s, name: '', sector: '' }, recent: true });
      }
      for (const p of PAGES) out.push({ kind: 'page', id: 'pg_' + p.path, page: p });
      out.push(...commands);
      return out;
    }
    const symHits = (rows ?? [])
      .filter((r) => matchFa(r.symbol, q) || matchFa(r.name, q))
      .slice(0, 10)
      .map<Item>((r) => ({ kind: 'symbol', id: 's_' + r.symbol, row: r }));
    out.push(...symHits);
    for (const p of PAGES) if (matchFa(p.label, q)) out.push({ kind: 'page', id: 'pg_' + p.path, page: p });
    for (const c of commands) if (c.kind === 'command' && matchFa(c.label, q)) out.push(c);
    return out;
  }, [commands, pinned, query, recent, rowBySymbol, rows]);

  const choose = useCallback(
    (item: Item) => {
      if (item.kind === 'symbol') {
        setSymbol(item.row.symbol);
        setOpen(false);
        navigate(destPath(dest, item.row.symbol));
      } else if (item.kind === 'page') {
        setOpen(false);
        navigate(item.page.path);
      } else {
        item.run();
        setOpen(false);
      }
    },
    [dest, navigate, setSymbol],
  );

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape') setOpen(false);
    else if (e.key === 'ArrowDown') {
      e.preventDefault();
      setCursor((c) => Math.min(items.length - 1, c + 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (e.key === 'Enter' && items[cursor]) {
      e.preventDefault();
      choose(items[cursor]);
    }
  };

  const panelRef = useDialogA11y<HTMLDivElement>({ open, onClose: () => setOpen(false) });

  if (!open) return null;

  let lastGroup = '';
  const groupOf = (it: Item) =>
    it.kind === 'symbol' ? 'نماد' : it.kind === 'page' ? 'صفحه' : 'فرمان';

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
            placeholder="نماد، صفحه یا فرمان... (↑↓ برای جابه جایی، Enter برای اجرا)"
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
            aria-label="جستجو در نمادها، صفحه ها و فرمان ها"
          />
          <kbd className="rounded-md border border-border-c px-1.5 py-0.5 text-2xs text-text-muted">Esc</kbd>
        </div>

        <div className="flex items-center gap-2 px-4 py-2">
          <span className="text-xs text-text-muted">مقصدِ نماد:</span>
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

        <div className="max-h-[46vh] overflow-y-auto pb-2" role="listbox" aria-label="نتایج پالت فرمان">
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
          {error && !loading && (
            <div className="px-4 py-4 text-center text-xs text-accent-red">
              فهرستِ نمادها نمی‌رسد — اخیرها و فرمان‌ها کار می‌کنند
            </div>
          )}
          {!loading && items.length === 0 && (
            <div className="px-4 py-6 text-center text-xs text-text-muted">نتیجه ای نیست</div>
          )}
          {items.map((it, i) => {
            const g = groupOf(it);
            const header = g !== lastGroup ? g : null;
            lastGroup = g;
            const active = i === cursor;
            return (
              <div key={it.id}>
                {header ? (
                  <div className="px-4 pb-1 pt-2 text-3xs font-black uppercase tracking-widest text-text-muted">
                    {header}
                  </div>
                ) : null}
                <button
                  type="button"
                  role="option"
                  aria-selected={active}
                  onClick={() => choose(it)}
                  onMouseEnter={() => setCursor(i)}
                  className={`flex w-full items-center justify-between gap-2 px-4 py-2.5 text-start text-sm transition-colors ${
                    active ? 'bg-accent-blue/12 text-text-primary' : 'text-text-secondary hover:bg-bg-card/50'
                  }`}
                >
                  {it.kind === 'symbol' ? (
                    <span className="flex min-w-0 items-baseline gap-2">
                      <span className="font-black text-text-primary">{it.row.symbol}</span>
                      {it.pinned ? <span className="text-3xs text-accent-amber">سنجاق</span> : null}
                      {it.recent ? <span className="text-3xs text-text-muted">اخیر</span> : null}
                      <span className="truncate text-xs text-text-muted">{it.row.name}</span>
                    </span>
                  ) : it.kind === 'page' ? (
                    <span className="font-bold">{it.page.label}</span>
                  ) : (
                    <span className="font-bold">{it.label}</span>
                  )}
                  <span className="shrink-0 text-2xs text-text-muted">
                    {it.kind === 'symbol'
                      ? it.row.sector
                      : it.kind === 'page'
                        ? it.page.hint
                        : it.hint}
                  </span>
                </button>
              </div>
            );
          })}
        </div>

        <div className="border-t border-[var(--hairline)] px-4 py-2 text-2xs text-text-muted">
          {toFaDigits(items.length)} نتیجه · Enter: «
          {items[cursor]?.kind === 'symbol'
            ? `${DESTS.find((d) => d.id === dest)?.label}ِ نماد`
            : items[cursor]?.kind === 'page'
              ? (items[cursor] as { page: { label: string } }).page.label
              : items[cursor]?.kind === 'command'
                ? (items[cursor] as { label: string }).label
                : '—'}
            »
        </div>
      </div>
    </div>
  );
}
