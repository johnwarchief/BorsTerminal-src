// features/master/ui/EliteFunnelHub.tsx -- ماژول قیف غربالگری نخبگان FTS (Elite Funnel Hub)
// زنجیره کاهش نمادها بر اساس متدولوژی FTS: ۸۰۰ سهم ──> ۵۰ سهم بنیادی ──> ۱۰ سهم واچلیست داغ ──> ۵ تا ۷ سهم سبد
import { useState, useMemo } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useFtsScreen } from '@features/fundamental/api/useFtsScreen';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { MarketRow } from '@shared/types/marketRow';

type FunnelTab = 'fundamental50' | 'watchlist10' | 'activePortfolio';
type SortField = 'rank' | 'score' | 'vol_ratio' | 'growth' | 'margin';

/** وضعیتِ هر ارکانِ چهارگانه برای یک سطرِ اسکرینر — عینِ گیت‌هایِ پایینِ همین فایل
 *  (بنیادی F ← تب۱، هفتگی W و ستاپ S ← تب۲، تابلو T ← خوراکِ تابلو). #224 */
type PhaseMark = 'ok' | 'no' | 'na';

const PHASE_DOT_STYLE: Record<PhaseMark, string> = {
  ok: 'bg-accent-green text-[#04121f]',
  no: 'bg-accent-red text-white',
  na: 'bg-bg-secondary text-text-muted border border-border-c',
};

const PHASE_MARK_TITLE: Record<PhaseMark, string> = { ok: 'تایید', no: 'رد/وتو', na: 'قابلِ سنجش نیست' };

/** چهار نقطۀ F/T/S/Mِ هر سطر — هم‌نامِ چهار ستونِ درخت استراتژی (بنیادی،
 *  تکنیکالِ دو زمانه، تابلوخوانی، مدیریتِ سرمایه)؛ همان گیت‌هایی که تبِ
 *  «۱۰ واچلیست داغ» ازیشان می‌سازد تا قیف و درخت یک عدد ببینند (#224).
 *  «na» یعنی داده نیست — نه رد، نه قبول. */
function phaseMarksFor(r: {
  weekly_veto?: boolean | null;
  tech_matrix_decision?: string | null;
  tech_trend_w?: string | null;
  tech_jet?: boolean | null;
  tech_fib_zone?: string | null;
  tech_hourglass_active?: boolean | null;
}, mrk: MarketRow | undefined, inBasket: boolean): { k: string; s: PhaseMark; why: string }[] {
  const vetoed = r.weekly_veto === true || r.tech_matrix_decision === 'REJECT';
  const weeklyUp = r.tech_trend_w === 'up' || r.tech_matrix_decision === 'PERMITTED';
  const setup = r.tech_jet || !!r.tech_fib_zone || r.tech_hourglass_active || mrk?.f_jet || mrk?.f_clock;
  const tapeOk = mrk ? mrk.f_clock === true || mrk.f_jet === true : false;
  const tState: PhaseMark = vetoed ? 'no' : weeklyUp && setup ? 'ok' : 'na';
  return [
    { k: 'F', s: 'ok', why: 'بنیادی: نمرۀ ۵ شاخص بالای ۳ (پیش‌شرطِ همین جدول)' },
    {
      k: 'T',
      s: tState,
      why: vetoed ? 'تکنیکال: وتوی هفتگی / REJECTِ ماتریس' : weeklyUp && setup ? 'تکنیکال: روند هفتگی صعودی با ستاپ فعال' : setup ? 'تکنیکال: ستاپ هست ولی روند هفتگی صعودیِ تاییدشده نیست' : 'تکنیکال: ستاپی نیست',
    },
    {
      k: 'S',
      s: tapeOk ? 'ok' : 'na',
      why: tapeOk ? 'تابلو: الگوی ساعت/جتِ تابلو فعال' : 'تابلو: نشانه‌ای امروز نیست',
    },
    {
      k: 'M',
      s: inBasket ? 'ok' : 'na',
      why: inBasket ? 'مدیریتِ سرمایه: در سبدِ فعال' : 'مدیریتِ سرمایه: هنوز در سبد نیست',
    },
  ];
}

export function EliteFunnelHub() {
  const currentSymbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);

  const [tab, setTab] = useState<FunnelTab>('fundamental50');
  const [collapsed, setCollapsed] = useState(false);
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortAsc, setSortAsc] = useState(false);

  const screenQuery = useFtsScreen(120);
  const marketFeed = useMarketFeed();
  const portfolioQuery = usePortfolio();
  const marketCloses = useMarketCloses();

  // مپ اطلاعات تابلو برای هر نماد (حجم ماهانه، قدرت خریدار، ساعت تابلو)
  const marketMap = useMemo(() => {
    const map = new Map<string, MarketRow>();
    for (const r of marketFeed.data?.data ?? []) {
      map.set(r.symbol, r);
    }
    return map;
  }, [marketFeed.data]);

  // ۱. تب ۵۰ نماد بنیادی: نمره FTS >= 3 و بدون نرخ‌گذاری دستوری
  const fundamental50 = useMemo(() => {    const raw = screenQuery.data?.data ?? [];
    const filtered = raw.filter((r) => {
      const mode = (r.pricing_mode ?? '').toLowerCase();
      const isRegulated = mode === 'regulated' || mode === 'دستوری';
      return (r.score ?? 0) >= 3 && !isRegulated && !r.excluded;
    });

    // مرتب‌سازی
    return [...filtered].sort((a, b) => {
      if (sortField === 'score') {
        const diff = (b.score ?? 0) - (a.score ?? 0);
        if (diff !== 0) return sortAsc ? -diff : diff;
      }
      if (sortField === 'growth') {
        const diff = (b.rev_growth ?? 0) - (a.rev_growth ?? 0);
        return sortAsc ? -diff : diff;
      }
      if (sortField === 'margin') {
        const diff = (b.gross_margin ?? 0) - (a.gross_margin ?? 0);
        return sortAsc ? -diff : diff;
      }
      if (sortField === 'vol_ratio') {
        const vA = marketMap.get(a.symbol)?.vol_ratio ?? 0;
        const vB = marketMap.get(b.symbol)?.vol_ratio ?? 0;
        const diff = vB - vA;
        return sortAsc ? -diff : diff;
      }
      return 0;
    }).slice(0, 50);
  }, [screenQuery.data, sortField, sortAsc, marketMap]);

  // ۲. تب ۱۰ نماد واچلیست داغ (Ready to Fire)
  const watchlist10 = useMemo(() => {
    const pool = fundamental50.length > 0 ? fundamental50 : (screenQuery.data?.data ?? []).filter((r) => (r.score ?? 0) >= 2.5);

    const candidates = pool.filter((r) => {
      const mrk = marketMap.get(r.symbol);
      // وتوی سختِ هفتگی (چارت ۳): نزولی و خنثی هر دو ردند — هیچ ستاپِ روزانه‌ای
      // آن را دور نمی‌زند. 'na' (بی‌داده) وتو نیست.
      if (r.weekly_veto || r.tech_matrix_decision === 'REJECT') return false;
      const isWeeklyUp = r.tech_trend_w === 'up' || r.tech_matrix_decision === 'PERMITTED';
      const hasFtsSetup = r.tech_jet || !!r.tech_fib_zone || r.tech_hourglass_active || mrk?.f_jet || mrk?.f_clock;
      return isWeeklyUp || hasFtsSetup;
    });

    return candidates.slice(0, 10).map((r) => {
      const mrk = marketMap.get(r.symbol);
      const price = marketCloses.data?.get(r.symbol) ?? mrk?.p_last ?? mrk?.p_closing ?? null;
      
      let setup = 'پولبک فیبو ۳۸-۶۲٪';
      if (r.tech_jet || mrk?.f_jet) setup = 'پرتاب ستاپ جت';
      else if (r.tech_hourglass_active) setup = 'فرصت ساعت شنی';
      else if (r.tech_fib_zone) setup = `تراز فیبو ${r.tech_fib_zone}`;

      const clockActive = mrk?.f_clock === true || (mrk?.buy_power_i ?? 0) > 1.5;
      const volRatio = mrk?.vol_ratio ?? 1.2;
      const triggerDistPct = mrk?.percent_change != null ? Math.round((2.5 - mrk.percent_change) * 10) / 10 : 1.2;

      return {
        symbol: r.symbol,
        name: r.name,
        sector: r.sector_name,
        setup,
        entryPrice: price,
        clockActive,
        volRatio,
        triggerDistPct: triggerDistPct > 0 ? triggerDistPct : 0.8,
        score: r.score,
      };
    });
  }, [fundamental50, screenQuery.data, marketMap, marketCloses.data]);

  // ۳. تب ۵ تا ۷ نماد پورتفوی فعال
  const activePortfolio = useMemo(() => {
    const raw = portfolioQuery.data?.portfolio ?? [];
    return raw.slice(0, 7).map((h) => {
      const mrk = marketMap.get(h.symbol);
      const price = marketCloses.data?.get(h.symbol) ?? mrk?.p_last ?? mrk?.p_closing ?? null;
      const pnl = price != null && typeof h.price === 'number' && h.price > 0 ? ((price - h.price) / h.price) * 100 : null;
      const weight = h.weight_eff_pct ?? 15;
      const isWeightExcess = weight > 20;

      return {
        symbol: h.symbol,
        sector: h.sector,
        weight,
        isWeightExcess,
        entryPrice: h.price,
        currentPrice: price,
        pnl,
        stopLoss: h.stop_loss,
      };
    });
  }, [portfolioQuery.data, marketMap, marketCloses.data]);

  // سبدِ فعال برای نقطۀ Mِ ستونِ ارکان (#224)
  const portfolioSet = useMemo(
    () => new Set((portfolioQuery.data?.portfolio ?? []).map((h) => h.symbol)),
    [portfolioQuery.data],
  );

  const handleSort = (field: SortField) => {    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <section
      className="glass-panel panel-in relative mb-3 overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-card/85 p-3 shadow-md"
      aria-label="قیف غربالگری نخبگان FTS"
    >
      {/* هدر قیف نخبگان بلومبرگ */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] pb-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg border border-neon-cyan/40 bg-neon-cyan/15 text-xs text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)]">
            ▼
          </span>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-xs font-black tracking-tight text-text-primary">
                قیف غربالگری نخبگان FTS (Elite Funnel Hub)
              </h3>
              <span className="rounded-full border border-border-c bg-bg-secondary px-2 py-0.5 font-mono text-[9px] font-bold text-text-muted">
                ۸۰۰ ──➔ ۵۰ ──➔ ۱۰ ──➔ ۵-۷
              </span>
            </div>
            <p className="text-[10px] text-text-muted">
              زنجیره کاهش نمادها و استخراج گزینه‌های نهایی ورود بر مبنای ارکان ۴گانه
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* سوییچر تب‌ها */}
          <div className="flex items-center rounded-xl border border-border-c bg-bg-secondary/70 p-0.5">
            <button
              type="button"
              onClick={() => setTab('fundamental50')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-bold transition-all ${
                tab === 'fundamental50'
                  ? 'border border-neon-cyan/50 bg-neon-cyan/20 text-neon-cyan shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span>۵۰ نماد بنیادی</span>
              <span className="font-mono text-[9px]">({toFaDigits(fundamental50.length)})</span>
            </button>
            <button
              type="button"
              onClick={() => setTab('watchlist10')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-bold transition-all ${
                tab === 'watchlist10'
                  ? 'border border-accent-amber/50 bg-accent-amber/20 text-accent-amber shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span>۱۰ واچلیست داغ 🔥</span>
              <span className="font-mono text-[9px]">({toFaDigits(watchlist10.length)})</span>
            </button>
            <button
              type="button"
              onClick={() => setTab('activePortfolio')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-bold transition-all ${
                tab === 'activePortfolio'
                  ? 'border border-accent-green/50 bg-accent-green/20 text-accent-green shadow-sm'
                  : 'text-text-secondary hover:text-text-primary'
              }`}
            >
              <span>پورتفوی فعال</span>
              <span className="font-mono text-[9px]">({toFaDigits(activePortfolio.length)})</span>
            </button>
          </div>

          {/* دکمه تاشو / بازشدن */}
          <button
            type="button"
            onClick={() => setCollapsed(!collapsed)}
            className="flex items-center gap-1 rounded-lg border border-border-c bg-bg-secondary px-2 py-1 text-[10px] font-bold text-text-secondary hover:border-border-accent hover:text-text-primary"
            title={collapsed ? 'گسترش جدول' : 'جمع‌کردن جدول'}
          >
            {collapsed ? 'نمایش قیف ▼' : 'جمع‌کردن ▲'}
          </button>
        </div>
      </div>

      {/* محتوای جدول متراکم */}
      {!collapsed && (
        <div className="mt-2 overflow-x-auto">
          {tab === 'fundamental50' && (
            <table className="w-full border-collapse text-right text-xs">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-bg-secondary/40 text-[10px] font-bold text-text-muted">
                  <th className="px-2.5 py-1">رتبه</th>
                  <th className="px-2.5 py-1">نماد و صنعت</th>
                  <th
                    className="cursor-pointer px-2.5 py-1 hover:text-neon-cyan"
                    onClick={() => handleSort('score')}
                  >
                    امتیاز بنیاد {sortField === 'score' ? (sortAsc ? '▲' : '▼') : ''}
                  </th>
                  <th
                    className="cursor-pointer px-2.5 py-1 hover:text-neon-cyan"
                    onClick={() => handleSort('growth')}
                  >
                    رشد فروش YTD {sortField === 'growth' ? (sortAsc ? '▲' : '▼') : ''}
                  </th>
                  <th
                    className="cursor-pointer px-2.5 py-1 hover:text-neon-cyan"
                    onClick={() => handleSort('margin')}
                  >
                    حاشیه سود ناخالص {sortField === 'margin' ? (sortAsc ? '▲' : '▼') : ''}
                  </th>
                  <th className="px-2.5 py-1">فروش ÷ مارکت‌کپ</th>
                  <th className="px-2.5 py-1 text-center" title="ارکان چهارگانۀ درخت استراتژی: F بنیادی، T تکنیکال، S تابلو، M مدیریتِ سرمایه (#224)">ارکان ۴گانه</th>
                  <th
                    className="cursor-pointer px-2.5 py-1 hover:text-neon-cyan"
                    onClick={() => handleSort('vol_ratio')}
                  >
                    ضریب حجم {sortField === 'vol_ratio' ? (sortAsc ? '▲' : '▼') : ''}
                  </th>
                  <th className="px-2.5 py-1 text-center">اقدام سریع</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {fundamental50.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="py-4 text-center text-xs text-text-muted">
                      داده‌ای در دسترس نیست
                    </td>
                  </tr>
                ) : (
                  fundamental50.map((r, idx) => {
                    const isSelected = r.symbol === currentSymbol;
                    const mrk = marketMap.get(r.symbol);
                    return (
                      <tr
                        key={r.symbol}
                        onClick={() => setSymbol(r.symbol)}
                        className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                          isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                        }`}
                      >
                        <td className="px-2.5 py-1 font-mono text-[10px] text-text-muted tabular-nums">
                          {toFaDigits(idx + 1)}
                        </td>
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-text-primary">{r.symbol}</span>
                            <span className="max-w-[120px] truncate text-[9.5px] text-text-muted">
                              {r.sector_name || r.name || '—'}
                            </span>
                          </div>
                        </td>
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1">
                            <Badge tone={r.score >= 4 ? 'green' : 'blue'}>
                              {toFaDigits(r.score)} / ۵
                            </Badge>
                          </div>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-primary">
                          {r.rev_growth != null ? (
                            <span className={r.rev_growth >= 0 ? 'text-accent-green' : 'text-accent-red'}>
                              {r.rev_growth > 0 ? '+' : ''}{toFaDigits(r.rev_growth)}٪
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-secondary">
                          {r.gross_margin != null ? `${toFaDigits(r.gross_margin)}٪` : '—'}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-secondary">
                          {r.sales_to_mcap != null ? `${toFaDigits(Math.round(r.sales_to_mcap * 100) / 100)}x` : '—'}
                        </td>
                        <td className="px-2.5 py-1">
                          <div className="flex items-center justify-center gap-1" title="F بنیادی · T تکنیکال · S تابلو · M مدیریتِ سرمایه">
                            {phaseMarksFor(r, mrk, portfolioSet.has(r.symbol)).map((m) => (
                              <span
                                key={m.k}
                                title={`${m.why} — ${PHASE_MARK_TITLE[m.s]}`}
                                className={`inline-flex h-4 w-4 items-center justify-center rounded-full text-[8px] font-black ${PHASE_DOT_STYLE[m.s]}`}
                              >
                                {m.k}
                              </span>
                            ))}
                          </div>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          {mrk?.vol_ratio != null ? (
                            <span className={mrk.vol_ratio >= 1.5 ? 'font-bold text-accent-amber' : 'text-text-muted'}>
                              {toFaDigits(Math.round(mrk.vol_ratio * 10) / 10)}x
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                          <SymbolBasketAction symbol={r.symbol} compact />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'watchlist10' && (
            <table className="w-full border-collapse text-right text-xs">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-bg-secondary/40 text-[10px] font-bold text-text-muted">
                  <th className="px-2.5 py-1">نماد و صنعت</th>
                  <th className="px-2.5 py-1">ستاپ معاملاتی</th>
                  <th className="px-2.5 py-1">تراز قیمت ورود</th>
                  <th className="px-2.5 py-1">الگوی ساعت تابلو</th>
                  <th className="px-2.5 py-1">نسبت حجم ماهانه</th>
                  <th className="px-2.5 py-1">فاصله تا ماشه ورود</th>
                  <th className="px-2.5 py-1 text-center">اقدام</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {watchlist10.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-4 text-center text-xs text-text-muted">
                      داده‌ای در واچلیست داغ یافت نشد
                    </td>
                  </tr>
                ) : (
                  watchlist10.map((w) => {
                    const isSelected = w.symbol === currentSymbol;
                    return (
                      <tr
                        key={w.symbol}
                        onClick={() => setSymbol(w.symbol)}
                        className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                          isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                        }`}
                      >
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-text-primary">{w.symbol}</span>
                            <span className="max-w-[110px] truncate text-[9.5px] text-text-muted">{w.sector || '—'}</span>
                          </div>
                        </td>
                        <td className="px-2.5 py-1">
                          <span className="inline-flex items-center rounded border border-accent-amber/40 bg-accent-amber/10 px-2 py-0.5 text-[10px] font-bold text-accent-amber">
                            {w.setup}
                          </span>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-primary">
                          {w.entryPrice != null ? `${toFaDigits(w.entryPrice)} ریال` : '—'}
                        </td>
                        <td className="px-2.5 py-1">
                          {w.clockActive ? (
                            <span className="inline-flex items-center gap-1 rounded bg-accent-green/10 px-1.5 py-0.5 text-[9.5px] font-bold text-accent-green">
                              <span className="h-1 w-1 rounded-full bg-accent-green" />
                              الگوی ساعت فعال
                            </span>
                          ) : (
                            <span className="text-[9.5px] text-text-muted">عادی</span>
                          )}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          <span className={w.volRatio >= 1.5 ? 'font-bold text-accent-amber' : 'text-text-muted'}>
                            {toFaDigits(Math.round(w.volRatio * 10) / 10)}x میانگین
                          </span>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          <span className="text-accent-blue">
                            {toFaDigits(w.triggerDistPct)}٪ تا شکست
                          </span>
                        </td>
                        <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                          <SymbolBasketAction symbol={w.symbol} compact />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'activePortfolio' && (
            <table className="w-full border-collapse text-right text-xs">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-bg-secondary/40 text-[10px] font-bold text-text-muted">
                  <th className="px-2.5 py-1">نماد و صنعت</th>
                  <th className="px-2.5 py-1">وزن در سبد (سقف ۲۰٪)</th>
                  <th className="px-2.5 py-1">قیمت ورود / فعلی</th>
                  <th className="px-2.5 py-1">سود/زیان باز</th>
                  <th className="px-2.5 py-1">حد ضرر</th>
                  <th className="px-2.5 py-1 text-center">اقدام</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {activePortfolio.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-xs text-text-muted">
                      هیچ نمادی در پورتفوی فعال نیست. نمادهای تاییدشده را اضافه کنید.
                    </td>
                  </tr>
                ) : (
                  activePortfolio.map((p) => {
                    const isSelected = p.symbol === currentSymbol;
                    return (
                      <tr
                        key={p.symbol}
                        onClick={() => setSymbol(p.symbol)}
                        className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                          isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                        }`}
                      >
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-text-primary">{p.symbol}</span>
                            <span className="max-w-[110px] truncate text-[9.5px] text-text-muted">{p.sector || '—'}</span>
                          </div>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          <div className="flex items-center gap-1.5">
                            <span className={`font-bold ${p.isWeightExcess ? 'text-accent-red' : 'text-text-primary'}`}>
                              {toFaDigits(p.weight)}٪
                            </span>
                            {p.isWeightExcess && (
                              <span className="rounded bg-accent-red/10 px-1 py-0.2 text-[9px] font-bold text-accent-red">
                                هشدار سقف ۲۰٪
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-secondary">
                          <span>{p.entryPrice != null ? toFaDigits(p.entryPrice) : '—'}</span>
                          <span className="mx-1 text-text-muted">/</span>
                          <span className="font-bold text-text-primary">{p.currentPrice != null ? toFaDigits(p.currentPrice) : '—'}</span>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          {p.pnl != null ? (
                            <span className={`font-bold ${p.pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                              {p.pnl >= 0 ? '+' : ''}{toFaDigits(Math.round(p.pnl * 10) / 10)}٪
                            </span>
                          ) : '—'}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-muted">
                          {p.stopLoss != null ? `${toFaDigits(p.stopLoss)} ریال` : 'تعیین‌نشده'}
                        </td>
                        <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                          <SymbolBasketAction symbol={p.symbol} compact />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
