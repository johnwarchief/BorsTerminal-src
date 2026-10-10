// features/portfolio/components/WatchMarketWorkspace.tsx — زیرتبِ «دیده‌بان بازار»
//
// چیدمانِ چهارناحیه‌ای که مالک خواسته: بالا جدولِ زنده؛ پایین سه‌تاییِ
// چپ=کندلِ روزانه، وسط=عمقِ پنج‌سطحی، راست=خلاصۀِ نماد + جایگاهِ خالیِ پنلِ
// ربات (دکمه‌ها غیرفعال). درِ ۱۳۶۶×۷۶۸ سه ستون می‌ماند (xl = ۱۲۸۰) و هر پنل
// `min-w-0` است تا جدول/چارت صفحه را بیرون نبرند.
//
// انتخابِ نماد ازِ همان `useSymbolStore` سراسری است: یک کلیک رویِ ردیف هر سه
// پنلِ پایین را هم‌زمان به همان نماد می‌بَرَد (هر سه با queryKeyِ نماد).
import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtAge } from '@shared/lib/time';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { useUserWatchlist } from '@shared/api/userWatchlist';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { useSymbolSearch } from '../api/useSymbolSearch';
import { useWatchSymbolsStore, WATCH_MAX } from '../stores/watchSymbolsStore';
import { WatchTable } from './WatchTable';
import { WatchMiniChart } from './WatchMiniChart';
import { WatchOrderBookPanel } from './WatchOrderBookPanel';
import { WatchSummaryPanel } from './WatchSummaryPanel';

function AddSymbolBar() {
  const [query, setQuery] = useState('');
  const [open, setOpen] = useState(false);
  const add = useWatchSymbolsStore((s) => s.add);
  const symbols = useWatchSymbolsStore((s) => s.symbols);
  const boxRef = useRef<HTMLDivElement>(null);
  const search = useSymbolSearch(query);
  const hits = useMemo(() => (search.data?.data ?? []).slice(0, 6), [search.data]);
  const normSet = useMemo(() => new Set(symbols.map((s) => normalizeFa(s))), [symbols]);

  useEffect(() => {
    const onDoc = (e: MouseEvent) => {
      if (boxRef.current && !boxRef.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  function commit(symbol: string) {
    add(symbol);
    setQuery('');
    setOpen(false);
  }

  return (
    <div ref={boxRef} className="relative min-w-0" data-testid="watch-add-area">
      <div className="flex items-center gap-1.5">
        <input
          type="text"
          value={query}
          data-testid="watch-add-input"
          aria-label="افزودن نماد به دیده‌بان"
          onChange={(e) => {
            setQuery(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && query.trim()) commit(query.trim());
          }}
          className="w-40 rounded-lg border border-border-c bg-bg-card px-2.5 py-1.5 text-2xs text-text-primary outline-none placeholder:text-text-muted focus:border-accent-blue sm:w-48"
          placeholder="نماد (مثلاً شپنا)"
        />
        <button
          type="button"
          data-testid="watch-add-btn"
          disabled={!query.trim()}
          onClick={() => commit(query.trim())}
          className="rounded-lg border border-neon-cyan/50 bg-neon-cyan/15 px-2.5 py-1.5 text-2xs font-bold text-neon-cyan disabled:cursor-not-allowed disabled:opacity-40"
        >
          افزودن
        </button>
      </div>
      {open && query.trim().length >= 2 && hits.length > 0 ? (
        <ul
          className="absolute z-20 mt-1 w-64 overflow-hidden rounded-xl border border-border-c bg-bg-primary shadow-xl"
          data-testid="watch-add-suggestions"
        >
          {hits.map((h) => (
            <li key={h.symbol}>
              <button
                type="button"
                data-testid={`watch-add-hit-${h.symbol}`}
                disabled={normSet.has(normalizeFa(h.symbol))}
                onClick={() => commit(h.symbol)}
                className="flex w-full items-baseline gap-2 px-3 py-1.5 text-start text-2xs hover:bg-bg-card disabled:opacity-40"
              >
                <span className="font-black text-text-primary">{h.symbol}</span>
                <span className="line-clamp-2 min-w-0 text-text-muted">{h.name || h.sector_name || '—'}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export default function WatchMarketWorkspace() {
  const symbols = useWatchSymbolsStore((s) => s.symbols);
  const remove = useWatchSymbolsStore((s) => s.remove);
  const selected = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  // ستارۀِ واچ‌لیستِ سرور همان ردیفِ `/api/watchlist` را روشن نگه می‌دارد (§۳۱
  // — دو چیزِ جدا: رصدِ محلیِ این جدول، و ستاره درِ پنج سطح).
  const { rows: serverRows } = useUserWatchlist();
  const serverNorm = useMemo(() => new Set(serverRows.map((r) => normalizeFa(r.symbol))), [serverRows]);

  // نمادِ مؤثرِ پنل‌ها: انتخابِ سراسری اگر درِ رصد باشد، وگرنه اولینِ رصدشده —
  // تا تازه‌وارد بدونِ کلیک هم سه پنلِ پر ببیند (نه پنلِ نمادِ بی‌ربطِ قبلی).
  const effective = useMemo(() => {
    const norm = normalizeFa(selected);
    return symbols.find((s) => normalizeFa(s) === norm) ?? selected ?? '';
  }, [selected, symbols]);

  // خلاصه از همان فیدِ مشترک — ردیفِ نمادِ مؤثر (selectِ باریک، بی‌درخواستِ دوم)
  const summaryRow = useMarketFeedShared(
    (f) => (f.data ?? []).find((r) => normalizeFa(String(r.symbol ?? '')) === normalizeFa(effective)) ?? null,
    60_000,
  );

  return (
    <div className="flex w-full max-w-none flex-col gap-3" data-testid="watch-market-workspace">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-black text-text-primary">دیدهبانِ بازار</h2>
        <AddSymbolBar />
        <span
          className="num ms-auto rounded-full bg-bg-card px-2 py-0.5 text-3xs font-bold text-text-secondary"
          title="سنِ فیدِ مشترکِ تابلو — جدولِ بالا با همان دلتا تازه می‌شود"
          data-testid="watch-feed-age"
        >
          فید: {fmtAge(summaryRow.dataUpdatedAt)}
        </span>
      </div>

      {symbols.length === 0 ? (
        <p className="glass-panel rounded-2xl px-3 py-4 text-center text-2xs leading-6 text-text-muted" data-testid="watch-empty">
          دیدهبانِ بازار خالی است. نمادِ موردِ رصد را بالا اضافه کن تا اینجا با
          فیدِ زندهٔ تابلو پیگیری شود. (رصد با «داراییِ پرتفوی» فرق دارد: این
          جدول هیچ‌وقت واردِ سبد/وزن نمی‌شود.) — سقفِ فهرست <span className="num">{toFaDigits(WATCH_MAX)}</span> نماد است.
        </p>
      ) : (
        <WatchTable symbols={symbols} selected={effective} onSelect={setSymbol} onRemove={remove} />
      )}

      <div className="grid min-w-0 max-w-full grid-cols-1 gap-3 lg:grid-cols-2 xl:grid-cols-3">
        <WatchMiniChart symbol={effective} />
        <WatchOrderBookPanel symbol={effective} />
        <WatchSummaryPanel symbol={effective} row={summaryRow.data ?? null} />
      </div>

      <p className="text-3xs leading-5 text-text-muted" data-testid="watch-server-note">
        ستارۀ «واچ‌لیست» (<span className="num">{toFaDigits(serverNorm.size)}</span> نماد درِ سرور) و این دیدهبانِ محلی دو چیزند:
        اولی برایِ رصدِ چندصفحهای، دومی جدولِ معاملاتیِ همین زیرتب.
      </p>
    </div>
  );
}
