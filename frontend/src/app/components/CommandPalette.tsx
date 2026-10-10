// app/components/CommandPalette.tsx -- پالت فرمان پیشرفته ترمینال مالی با Ctrl+K
// الگوی Raycast / Bloomberg / Linear: دسترسی سریع به نمادها، صفحات، و فرمان‌های اصلی
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import type { MarketFeed } from '@shared/types/marketRow';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useUiStore } from '@shared/stores/uiStore';
import { toFaDigits } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { useDialogA11y } from '@shared/lib/useDialogA11y';
import { Skeleton } from '@shared/components/ui/skeleton';
import { Badge } from '@shared/components/ui/badge';

type Dest = 'master' | 'technical' | 'fundamental' | 'strategy-tree' | 'market';

const DESTS: { id: Dest; label: string }[] = [
  { id: 'master', label: 'استراتژی FTS' },
  { id: 'technical', label: 'تکنیکال' },
  { id: 'fundamental', label: 'بنیادی' },
  { id: 'strategy-tree', label: 'درخت FTS' },
  { id: 'market', label: 'تابلو' },
];

const PAGES: { path: string; label: string; hint: string }[] = [
  // صفحۀ نخستِ برنامه «استراتژی FTS» است، پس درِ پالت هم اول می‌آید.
  { path: '/master', label: 'استراتژی FTS', hint: 'تب' },
  { path: '/market', label: 'تابلوخوانی / بازار', hint: 'تب' },
  { path: '/technical', label: 'تحلیل تکنیکال', hint: 'تب' },
  { path: '/fundamental', label: 'تحلیل بنیادی', hint: 'تب' },
  { path: '/strategy-tree', label: 'درخت استراتژی', hint: 'تب' },
  { path: '/portfolio', label: 'مدیریت پرتفوی', hint: 'تب' },
];

type Row = { symbol: string; name: string; sector: string };

// انتخابگرِ پایدار (مرجع ثابت) — نقشه بردنِ کل تابلو فقط وقتی داده عوض می‌شود
// اجرا می‌شود، نه هر رندر؛ وگرنه mappingِ ۵٬۸۰۰ ردیف درِ هر کلیدِ کیبورد سوخت می‌شد.
const selectPaletteRows = (f: MarketFeed): Row[] =>
  (f.data ?? []).filter((r) => r.symbol).map((r) => ({ symbol: r.symbol, name: r.name ?? '', sector: r.sector_name ?? '' }));

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
  const togglePin = useSymbolStore((s) => s.togglePin);
  const toggleTheme = useUiStore((s) => s.toggleTheme);

  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [dest, setDest] = useState<Dest>('master');
  const [cursor, setCursor] = useState(0);
  // جست‌وجو از همان فیدِ مشترکِ تابلو می‌خواند (select فقط) — نه یکِ fetchِ دومِ
  // /api/market که snapshotِ جدا و کهنه نگه می‌داشت (#M2.2). کلیدِ یکی ⇒ درخواستِ یکی.
  const feed = useMarketFeedShared(selectPaletteRows);
  const rows = feed.data ?? null;
  const loading = feed.isPending;
  const error = !!feed.error && rows === null;
  const inputRef = useRef<HTMLInputElement>(null);

  const openPalette = useCallback(() => {
    setOpen(true);
    setQuery('');
    setCursor(0);
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
        hint: 'دستور',
        run: () => toggleTheme(),
      },
      {
        kind: 'command',
        id: 'cmd-clear',
        label: 'پاک کردن نمادِ انتخابی',
        hint: 'دستور',
        run: () => clearSymbol(),
      },
      {
        kind: 'command',
        id: 'cmd-funnel',
        label: 'باز کردن غربالگری FTS',
        hint: 'دستور',
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
      // صدر فهرست: نشان‌شده‌ها و اخیرها
      for (const s of pinned) {
        out.push({
          kind: 'symbol',
          id: 'p_' + s,
          row: rowBySymbol.get(s) ?? { symbol: s, name: '', sector: '' },
          pinned: true,
        });
      }
      for (const s of recent) {
        if (pinned.includes(s)) continue;
        out.push({
          kind: 'symbol',
          id: 'r_' + s,
          row: rowBySymbol.get(s) ?? { symbol: s, name: '', sector: '' },
          recent: true,
        });
      }
      for (const p of PAGES) out.push({ kind: 'page', id: 'pg_' + p.path, page: p });
      out.push(...commands);
      return out;
    }
    const symHits = (rows ?? [])
      .filter((r) => matchFa(r.symbol, q) || matchFa(r.name, q))
      .slice(0, 12)
      .map<Item>((r) => ({
        kind: 'symbol',
        id: 's_' + r.symbol,
        row: r,
        pinned: pinned.includes(r.symbol),
        recent: recent.includes(r.symbol),
      }));
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
    if (e.key === 'Escape') {
      setOpen(false);
    } else if (e.key === 'ArrowDown') {
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
      className="fixed inset-0 z-[200] flex items-start justify-center bg-black/65 p-4 pt-[10vh] backdrop-blur-xs overscroll-contain"
      onClick={() => setOpen(false)}
      role="presentation"
    >
      <div
        ref={panelRef}
        tabIndex={-1}
        className="glass-panel scale-in w-full max-w-2xl overflow-hidden rounded-2xl border border-border-c bg-bg-secondary shadow-2xl outline-none"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="پالت فرمان"
        onKeyDown={onKeyDown}
      >
        {/* کادر ورودی پالت */}
        <div className="flex items-center gap-3 border-b border-border-c/70 px-4 py-3">
          <span className="text-neon-cyan text-base font-bold select-none" aria-hidden>
            ⌘
          </span>
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setCursor(0);
            }}
            placeholder="جستجوی نماد، صفحه یا فرمان... (↑↓ جابه‌جایی، Enter انتخاب)"
            className="flex-1 bg-transparent text-sm text-text-primary outline-none placeholder:text-text-muted"
            aria-label="جستجو در نمادها، صفحه ها و فرمان ها"
          />
          <kbd className="rounded-md border border-border-c bg-bg-card/70 px-1.5 py-0.5 text-2xs text-text-muted">
            Esc
          </kbd>
        </div>

        {/* انتخاب مقصد باز کردن نماد */}
        <div className="flex flex-wrap items-center gap-2 border-b border-border-c/40 bg-bg-card/30 px-4 py-2">
          <span className="text-2xs font-medium text-text-muted">مقصد بازگشایی:</span>
          {DESTS.map((d) => (
            <button
              key={d.id}
              type="button"
              onClick={() => setDest(d.id)}
              className={`rounded-full border px-2.5 py-0.5 text-2xs font-bold transition-all ${
                dest === d.id
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue shadow-2xs'
                  : 'border-border-c text-text-muted hover:border-border-accent hover:text-text-secondary'
              }`}
            >
              {d.label}
            </button>
          ))}
        </div>

        {/* فهرست نتایج */}
        <div className="max-h-[50vh] overflow-y-auto overscroll-contain p-1.5 scrollbar-thin" role="listbox" aria-label="نتایج پالت فرمان">
          {loading && (
            <div className="flex flex-col gap-2 p-4" role="status" aria-live="polite">
              <span className="sr-only">در حال دریافت فهرست نمادها...</span>
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-4/5" />
              <Skeleton className="h-8 w-2/3" />
            </div>
          )}

          {error && !loading && (
            <div className="p-4 text-center text-xs text-accent-red">
              خطا در دریافت برخط داده‌ها — نتایج محلی و فرمان‌ها در دسترس هستند.
            </div>
          )}

          {!loading && items.length === 0 && (
            <div className="py-8 text-center text-xs text-text-muted">موردی یافت نشد.</div>
          )}

          {items.map((it, i) => {
            const g = groupOf(it);
            const header = g !== lastGroup ? g : null;
            lastGroup = g;
            const active = i === cursor;

            return (
              <div key={it.id}>
                {header ? (
                  <div className="px-3 pb-1 pt-2.5 text-3xs font-black uppercase tracking-wider text-text-muted select-none">
                    {header}
                  </div>
                ) : null}

                <div
                  role="option"
                  aria-selected={active}
                  onClick={() => choose(it)}
                  onMouseEnter={() => setCursor(i)}
                  className={`flex cursor-pointer items-center justify-between gap-3 rounded-lg px-3 py-2 text-xs transition-colors duration-100 ${
                    active
                      ? 'bg-accent-blue/15 text-text-primary shadow-2xs'
                      : 'text-text-secondary hover:bg-bg-card/60 hover:text-text-primary'
                  }`}
                >
                  {it.kind === 'symbol' ? (
                    <div className="flex min-w-0 items-center gap-2">
                      <span className="font-black text-text-primary text-sm">{it.row.symbol}</span>
                      {it.pinned ? (
                        <Badge variant="warning" size="xs">
                          سنجاق
                        </Badge>
                      ) : null}
                      {it.recent && !it.pinned ? (
                        <Badge variant="secondary" size="xs">
                          اخیر
                        </Badge>
                      ) : null}
                      {it.row.name ? (
                        <span className="truncate text-2xs text-text-muted max-w-[180px]">
                          {it.row.name}
                        </span>
                      ) : null}
                    </div>
                  ) : it.kind === 'page' ? (
                    <span className="font-bold text-text-primary">{it.page.label}</span>
                  ) : (
                    <span className="font-bold text-text-primary">{it.label}</span>
                  )}

                  <div className="flex items-center gap-2 shrink-0">
                    {it.kind === 'symbol' && (
                      <button
                        type="button"
                        title={it.pinned ? 'برداشتن سنجاق' : 'افزودن سنجاق'}
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePin(it.row.symbol);
                        }}
                        className={`p-1 text-2xs hover:scale-110 transition-transform ${
                          it.pinned ? 'text-accent-yellow' : 'text-text-muted hover:text-text-primary'
                        }`}
                      >
                        {it.pinned ? '★' : '☆'}
                      </button>
                    )}
                    <span className="text-3xs text-text-muted font-mono">
                      {it.kind === 'symbol' ? it.row.sector : it.kind === 'page' ? it.page.hint : it.hint}
                    </span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* فوتر اطلاعاتی */}
        <div className="flex items-center justify-between border-t border-border-c/50 bg-bg-card/20 px-4 py-2 text-3xs text-text-muted">
          <span>{toFaDigits(items.length)} نتیجه موجود</span>
          <div className="flex items-center gap-2">
            <span>
              Enter برای اجرای «
              {items[cursor]?.kind === 'symbol'
                ? `${DESTS.find((d) => d.id === dest)?.label} (${(items[cursor] as { row: Row }).row.symbol})`
                : items[cursor]?.kind === 'page'
                  ? (items[cursor] as { page: { label: string } }).page.label
                  : items[cursor]?.kind === 'command'
                    ? (items[cursor] as { label: string }).label
                    : '—'}
              »
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
