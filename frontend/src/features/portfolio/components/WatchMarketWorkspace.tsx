// features/portfolio/components/WatchMarketWorkspace.tsx — زیرتبِ «دیده‌بان بازار»
//
// چیدمان: بالا جدولِ زنده؛ زیرِ آن نوارِ تب‌هایِ افقیِ اسکرول‌پذیر و پروندۀ همان
// نماد (تابلو+سابقه / نمودار / پنج کارت بنیادی / بازار در یک نگاه). درِ ۱۳۶۶
// پیکسل یک پنلِ تمام‌عرض می‌ماند و هیچ‌کدام `min-w-0` را نمی‌شکنند.
//
// انتخابِ نماد ازِ همان `useSymbolStore` سراسری است: یک کلیک رویِ ردیف هر سه
// پنلِ پایین را هم‌زمان به همان نماد می‌بَرَد (هر سه با queryKeyِ نماد).
import { useEffect, useMemo, useRef, useState } from 'react';
import { fmtAge } from '@shared/lib/time';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { useUserWatchlist, useWatchlistToggle } from '@shared/api/userWatchlist';
import { useInsCodeFor } from '@shared/api/tapeHistory';
import TapeHistoryPanel from '@shared/components/TapeHistoryPanel';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { patternBadges } from '@features/market/lib/tapeBadges';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { FtsCardDossier } from '@features/fundamental/components/FtsCardDossier';
import { useSymbolSearch } from '../api/useSymbolSearch';
import { useWatchSymbolsStore, WATCH_MAX } from '../stores/watchSymbolsStore';
import { WatchTable } from './WatchTable';
import { WatchChartDeck } from './WatchChartDeck';
import { OrderBookFive } from '@shared/components/OrderBookFive';
import { WatchSummaryPanel } from './WatchSummaryPanel';

/** تب‌های پروندۀ نماد — هر چهار پنلِ قبلی این صفحه زنده ماندند، فقط درِ تب
 *  خودشان می‌نشینند (چهارستونه رویِ ۱۳۶۶ پیکسل یعنی اسکرولِ افقیِ جدول). */
type WatchTab = 'tape' | 'chart' | 'fund' | 'market';
const TABS: Array<{ id: WatchTab; label: string; hint: string }> = [
  { id: 'tape', label: 'خلاصه و تابلوخوانی', hint: 'قیمت و حجمِ همین نشست + برچسبِ فیلترها + سابقۀ چندروزهٔ هر فیلتر' },
  { id: 'chart', label: 'نمودار تکنیکال', hint: 'همان کارتِ نمودارِ چندصفحهایِ همین نمادها، با همان موتور' },
  { id: 'fund', label: 'بنیادی (پنج کارت)', hint: 'پنج کارت FTS از همان /api/fundamental — بی‌موتورِ دوم' },
  { id: 'market', label: 'بازار در یک نگاه', hint: 'عمقِ پنج‌سطحی و خلاصۀ تابلو درِ یک نگاه' },
];

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
  const localSymbols = useWatchSymbolsStore((s) => s.symbols);
  const removeLocal = useWatchSymbolsStore((s) => s.remove);
  const selected = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  // ستارۀِ واچ‌لیستِ سرور + دیدهبانِ محلی. پیش از این دو فهرست درِ دو جمله
  // جدا نگه داشته می‌شدند («این جدولِ معاملاتیِ همین زیرتب است») و نتیجه‌اش این
  // بود که نمادی که از جدول تحویل ستاره‌دار شده درِ هابِ رصد دیده نمی‌شد. اینجا
  // یکی می‌شوند: اتحادِ دو فهرست با کلیدِ نرمال، بی‌سومینِ منبعِ حقیقت.
  const { rows: serverRows } = useUserWatchlist();
  const serverNorm = useMemo(() => new Set(serverRows.map((r) => normalizeFa(r.symbol))), [serverRows]);
  const watchToggle = useWatchlistToggle();

  const symbols = useMemo(() => {
    const seen = new Set<string>();
    const out: string[] = [];
    for (const s of [...localSymbols, ...serverRows.map((r) => r.symbol)]) {
      const n = normalizeFa(s);
      if (!n || seen.has(n)) continue;
      seen.add(n);
      out.push(s);
    }
    return out;
  }, [localSymbols, serverRows]);

  /** حذف = برداشتنِ عضویت از هر دو جا؛ اگر فقط یکی پاک شود، نماد «برنمی‌دارد»
   *  و کاربر آن را درِ همان فهرست بازمی‌بیند. */
  const removeOne = (s: string) => {
    const n = normalizeFa(s);
    if (localSymbols.some((x) => normalizeFa(x) === n)) removeLocal(s);
    if (serverNorm.has(n)) watchToggle.mutate({ symbol: s, remove: true });
  };

  // نمادِ مؤثرِ پنل‌ها: انتخابِ سراسری اگر درِ رصد باشد، وگرنه اولینِ رصدشده —
  // تا تازه‌وارد بدونِ کلیک هم پروندۀ پر ببیند (نه پروندۀ نمادِ بی‌ربطِ قبلی).
  // پیش از این همان `?? selected` برمی‌گشت، یعنی با انتخابِ خالی هر سه پنل
  // بی‌نماد می‌ماندند و کامنتِ بالایِ خودش را نقض می‌کرد (سنجشِ زنده: عمقِ
  // پنج‌سطحی ۰ سطر تا پیش از نخستین کلیک).
  const effective = useMemo(() => {
    const norm = normalizeFa(selected);
    // `||` نه `??`: انتخابِ خالیِ سراسری رشتهٔ '' است، نه null/undefined؛
    // با `??` همان '' برمی‌گشت و هیچ‌وقت به اولینِ نمادِ رصد نمی‌رسید.
    return symbols.find((s) => normalizeFa(s) === norm) || selected || symbols[0] || '';
  }, [selected, symbols]);

  // تبِ پرونده: با انتخابِ نماد نمی‌سوزد (مالک: تغییرِ نماد نباید کارِ کاربر را
  // بی‌صدا به تبِ اول برگرداند).
  const [tab, setTab] = useState<WatchTab>('tape');

  // خلاصه از همان فیدِ مشترک — ردیفِ نمادِ مؤثر (selectِ باریک، بی‌درخواستِ دوم)
  const summaryRow = useMarketFeedShared(
    (f) => (f.data ?? []).find((r) => normalizeFa(String(r.symbol ?? '')) === normalizeFa(effective)) ?? null,
    60_000,
  );
  // برچسبِ فیلترها از همان `patternBadges` تبِّ تابلو می‌آیند (نه فرمولِ دوم)؛
  // سابقه هم با `ins_code` پرسیده می‌شود، نه با نام.
  const tapeCfg = useTapeStore((s) => s.tapeFilterConfig);
  const liveBadges = useMemo(
    () => (summaryRow.data ? patternBadges(summaryRow.data, tapeCfg).filter((b) => b.filter) : []),
    [summaryRow.data, tapeCfg],
  );
  const insCode = useInsCodeFor(effective);

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
        <WatchTable symbols={symbols} selected={effective} onSelect={setSymbol} onRemove={removeOne} />
      )}

      {symbols.length > 0 ? (
        <>
          {/* تب‌های افقیِ اسکرول‌پذیر: پروندۀ همان نمادِ انتخابی. چارت، عمق و
              خلاصه از این صفحه حذف نشده‌اند — هر چهار پنل درِ یک تب زنده‌اند تا
              عرضِ ۱۳۶۶ پیکسل جدول را بیرون نبرد. */}
          <div
            role="tablist"
            data-testid="watch-dossier-tabs"
            className="flex min-w-0 gap-1 overflow-x-auto rounded-xl border border-border-c bg-bg-card/50 p-1"
          >
            {TABS.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                data-testid={`watch-tab-${t.id}`}
                onClick={() => setTab(t.id)}
                title={t.hint}
                className={`shrink-0 rounded-lg px-2.5 py-1 text-2xs font-bold transition-colors ${
                  tab === t.id
                    ? 'bg-accent-blue/20 text-accent-blue'
                    : 'text-text-muted hover:bg-bg-primary hover:text-text-primary'
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>

          <div className="min-w-0" data-testid={`watch-dossier-${tab}`} role="tabpanel">
            {tab === 'tape' ? (
              <div className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-2">
                <WatchSummaryPanel symbol={effective} row={summaryRow.data ?? null} />
                <div className="glass-panel min-w-0 rounded-2xl p-2.5">
                  <div className="mb-1 flex flex-wrap items-center gap-1" data-testid={`watch-badges-${effective}`}>
                    {liveBadges.length ? (
                      liveBadges.map((b) => (
                        <span key={b.key} title={b.title}
                              className={`rounded border px-1.5 py-0.5 text-3xs font-bold ${
                                b.tone === 'red' ? 'border-accent-red/40 bg-accent-red/15 text-accent-red'
                                                 : 'border-accent-blue/40 bg-accent-blue/15 text-accent-blue'}`}>
                          {b.label}
                        </span>
                      ))
                    ) : (
                      <span className="text-3xs text-text-muted">
                        هیچ فیلترِ تابلویی همین حالا رویِ این نماد روشن نیست (وضعیتِ امروز، جدا از سابقه).
                      </span>
                    )}
                  </div>
                  <TapeHistoryPanel insCode={insCode} symbol={effective} days={5} />
                </div>
              </div>
            ) : null}
            {tab === 'chart' ? (
              <WatchChartDeck symbols={symbols} selected={effective} onSelect={setSymbol} />
            ) : null}
            {tab === 'fund' ? <FtsCardDossier symbol={effective} /> : null}
            {tab === 'market' ? (
              <div className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-2">
                <OrderBookFive symbol={effective} candle={summaryRow.data ?? null} testId="watch-orderbook"
                               className="glass-panel h-full min-w-0 rounded-2xl p-2.5" />
                <WatchSummaryPanel symbol={effective} row={summaryRow.data ?? null} />
              </div>
            ) : null}
          </div>
        </>
      ) : null}

      <p className="text-3xs leading-5 text-text-muted" data-testid="watch-server-note">
        این فهرست اتحادِ دو منبع است: ستارۀ «واچ‌لیست» (<span className="num">{toFaDigits(serverNorm.size)}</span> نماد
        درِ سرور، ماندگار) و دیدهبانِ محلی (<span className="num">{toFaDigits(localSymbols.length)}</span> نماد درِ همین
        دستگاه). حذف، عضویت را از هردو برمی‌دارد. رصد با «داراییِ پرتفوی» فرق دارد: هیچ‌وقت واردِ سبد/وزن نمی‌شود.
      </p>
    </div>
  );
}
