// features/master/ui/EliteFunnelHub.tsx -- سه فهرستِ تحویلِ قیف (رندرر، نه موتورِ داوری)
//
// پیش از این این فایل **چهارمین** مدلِ داوریِ تب بود: `score>=3` به‌عنوان درِ
// ورود، `slice(0,50)` و `slice(0,10)` برایِ رسیدن به عددِ جزوه، `phaseMarksFor`
// که F را همیشه «تایید» می‌زد، و سه ستادِ ساختگی («پولبک فیبو ۳۸-۶۲٪»،
// «الگوی ساعت» با `buy_power_i > 1.5`، و «فاصله تا ماشه» با `2.5 - percent_change`).
// هیچ‌کدام از این‌ها درِ `api/chart.py`، `api/screener.py` یا `tape_flags.py`
// وجود نداشت. حالا همه‌چیز از `lib/ftsFunnel.ts` (تک‌منبعِ کاندید) خوانده
// می‌شود و شمارش‌ها **واقعاً همان چیزی‌اند که بازار داده** — نه ۵۰ و ۱۰ به زور.
//
// هدف‌هایِ جزوه (رأیِ ۶: ۵۰ مانور اولیه، ۱۰ واچ‌لیست، ۵ تا ۷ سبد) فقط به‌عنوان
// «هدف» کنارِ عددِ واقعی نوشته می‌شوند؛ هیچ‌جا گیتِ عبور نیستند (#3 و #15).
import { useMemo, useState } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { Badge } from '@shared/components/Badge';
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import {
  MODE_LABEL,
  MODE_PATH,
  STATUS_LABEL,
  TAPE_FRESHNESS_LABEL,
  trendLabel,
  type Candidate,
  type TreePreset,
} from '../lib/ftsFunnel';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';

type HubTab = 'qualified' | 'ready' | 'portfolio';
type SortField = 'score' | 'growth' | 'margin' | 'vol';

const SORT_LABEL: Record<SortField, string> = {
  score: 'امتیاز بنیاد',
  growth: 'رشد فروش YTD',
  margin: 'حاشیه سود ناخالص',
  vol: 'ضریب حجم',
};

/** چهار نقطۀ F/T/S/M — از `candidate.status`، یعنی همان داوریِ قیف. */
const DOT_CLASS: Record<string, string> = {
  pass: 'bg-accent-green text-[#04121f]',
  reject: 'bg-accent-red text-white',
  pending: 'bg-accent-yellow text-[#1a1200]',
  unavailable: 'bg-bg-secondary text-text-muted border border-border-c',
};

function StatusDots({ c }: { c: Candidate }) {
  return (
    <div className="flex items-center justify-center gap-1" title="F بنیادی · T تکنیکال · S تابلو · M تحویل">
      {(['fundamental', 'technical', 'tape', 'handover'] as const).map((k) => (
        <span
          key={k}
          title={`${c.why[k] || '—'} — ${STATUS_LABEL[c.status[k]]}`}
          className={`inline-flex h-4 w-4 items-center justify-center rounded-full text-[8px] font-black ${DOT_CLASS[c.status[k]]}`}
        >
          {k === 'fundamental' ? 'F' : k === 'technical' ? 'T' : k === 'tape' ? 'S' : 'M'}
        </span>
      ))}
    </div>
  );
}

export function EliteFunnelHub({ preset = 'custom' }: { preset?: TreePreset }) {
  const currentSymbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const portfolioQuery = usePortfolio();
  const marketCloses = useMarketCloses();

  const [tab, setTab] = useState<HubTab>('qualified');
  const [collapsed, setCollapsed] = useState(false);
  const [sortField, setSortField] = useState<SortField>('score');
  const [sortAsc, setSortAsc] = useState(false);

  // تک‌منبع: همان قیفی که `FtsFunnelStages` نشان می‌دهد (کوئری‌ها درِ TanStack
  // مشترک‌اند؛ چیزی دوباره fetch نمی‌شود).
  const { funnel, mode, tape } = useFtsFunnel(preset);

  const sortFn = useMemo(() => {
    const dir = sortAsc ? 1 : -1;
    return (a: Candidate, b: Candidate): number => {
      const va =
        sortField === 'score'
          ? a.score ?? -1
          : sortField === 'growth'
            ? a.screen?.rev_growth ?? -999
            : sortField === 'margin'
              ? a.screen?.gross_margin ?? -999
              : a.row?.vol_ratio ?? 0;
      const vb =
        sortField === 'score'
          ? b.score ?? -1
          : sortField === 'growth'
            ? b.screen?.rev_growth ?? -999
            : sortField === 'margin'
              ? b.screen?.gross_margin ?? -999
              : b.row?.vol_ratio ?? 0;
      // ترتیبِ مساوی هیچ‌وقت به ترتیبِ تابلو واگذار نمی‌شود (ناپایدار): نماد
      // مرجعِ آخر است، همان‌طور که درِ رتبۀ رسمیِ بک‌اند هم هست.
      return (va - vb) * dir || a.symbol.localeCompare(b.symbol);
    };
  }, [sortField, sortAsc]);

  // ۱. واجدانِ شرایطِ بنیادی: هر کاندیدی که درِ F را واقعاً رد کرده — بدونِ
  //    سقفِ ۵۰ و بدونِ «score>=3»ِ دست‌ساز؛ کفِ پنج‌شاخصه خودِ پیچِ قیف است.
  const qualified = useMemo(
    () => funnel.stages.tape.entries.filter((c) => c.status.fundamental === 'pass').sort(sortFn),
    [funnel.stages.tape.entries, sortFn],
  );

  // ۲. آمادۀ تحویل = همان «واچ‌لیست داغ»: چهار درِ S➔T➔F➔M باز، بیرونِ سبد،
  //    بدونِ وتوی مجمع. شمارشِ واقعی کنارش نوشته می‌شود، هدفِ جزوه جدا.
  const ready = funnel.stages.handover.entries;

  // ۳. سبدِ فعال: دیگر `slice(0,7)` نیست — اگر بیشتر از هفت نماد باشد، خودِ
  //    همان تجاوز باید دیده شود (سقفِ رسمی: PORTFOLIO_MAX=7 درِ بک‌اند).
  const holdings = portfolioQuery.data?.portfolio ?? [];
  const overBasket = holdings.length > funnel.targets.basketMax;

  const handleSort = (field: SortField) => {
    if (sortField === field) setSortAsc(!sortAsc);
    else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  return (
    <section
      className="glass-panel panel-in relative mb-3 overflow-hidden rounded-2xl border border-[var(--hairline)] bg-bg-card/85 p-3 shadow-md"
      aria-label="فهرست‌هایِ تحویلِ قیف FTS"
    >
      {/* هدر: حالتِ کشف + شمارشِ واقعی، نه زنجیرۀ ۸۰۰➔۵➔۱ به‌عنوان وعد */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] pb-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg border border-neon-cyan/40 bg-neon-cyan/15 text-xs text-neon-cyan shadow-[0_0_10px_rgba(0,229,255,0.2)]">
            ▼
          </span>
          <div>
            <div className="flex items-center gap-2 flex-wrap">
              <h3 className="text-xs font-black tracking-tight text-text-primary">
                فهرست‌هایِ تحویلِ قیف FTS
              </h3>
              <span
                className="rounded-full border border-border-c bg-bg-secondary px-2 py-0.5 font-mono text-[9px] font-bold text-text-muted"
                data-testid="hub-mode-path"
                title="مسیرِ داوریِ همین فهرست‌ها"
              >
                {MODE_LABEL[mode]} · {MODE_PATH[mode]}
              </span>
              <span
                className="rounded-full border border-border-c bg-bg-secondary px-2 py-0.5 text-[9px] font-bold text-text-muted"
                data-testid="hub-tape-freshness"
              >
                {TAPE_FRESHNESS_LABEL[tape]}
              </span>
            </div>
            <p className="text-[10px] text-text-muted" data-testid="hub-counts">
              شمارشِ واقعی: {toFaDigits(qualified.length)} واجدِ بنیادی · {toFaDigits(ready.length)} آمادۀ
              تحویل · {toFaDigits(funnel.counts.fundamental.pending)} در انتظارِ گزارش ·{' '}
              {toFaDigits(funnel.counts.technical.unavailable)} بی‌داده — هدفِ جزوه ۵۰/۱۰/۵-۷ مرجع است، نه شرطِ عبور
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* سوییچر تب‌ها */}
          <div className="flex items-center rounded-xl border border-border-c bg-bg-secondary/70 p-0.5">
            {(
              [
                ['qualified', 'واجدانِ بنیادی', qualified.length],
                ['ready', 'آمادۀ تحویل', ready.length],
                ['portfolio', 'سبدِ فعال', holdings.length],
              ] as const
            ).map(([k, label, n]) => (
              <button
                key={k}
                type="button"
                onClick={() => setTab(k)}
                data-testid={`hub-tab-${k}`}
                className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-[10px] font-bold transition-all ${
                  tab === k
                    ? 'border border-neon-cyan/50 bg-neon-cyan/20 text-neon-cyan shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <span>{label}</span>
                <span className="font-mono text-[9px]">({toFaDigits(n)})</span>
              </button>
            ))}
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
          {tab === 'qualified' && (
            <table className="w-full border-collapse text-right text-xs">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-bg-secondary/40 text-[10px] font-bold text-text-muted">
                  <th className="px-2.5 py-1">نماد و صنعت</th>
                  {(Object.keys(SORT_LABEL) as SortField[]).map((f) => (
                    <th
                      key={f}
                      className="cursor-pointer px-2.5 py-1 hover:text-neon-cyan"
                      onClick={() => handleSort(f)}
                    >
                      {SORT_LABEL[f]} {sortField === f ? (sortAsc ? '▲' : '▼') : ''}
                    </th>
                  ))}
                  <th className="px-2.5 py-1">روندِ هفتگی</th>
                  <th className="px-2.5 py-1 text-center" title="ارکان چهارگانۀ قیف — از همان داوریِ مرحله‌ها">
                    ارکان ۴گانه
                  </th>
                  <th className="px-2.5 py-1 text-center">اقدام سریع</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {qualified.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="py-4 text-center text-xs text-text-muted">
                      هیچ نمادی درِ مرحلۀ بنیادی قبول نشده — شمارشِ واقعی همین است و برایِ پُردنِ عددِ ۵۰ نمادِ ضعیف اضافه نمی‌شود.
                    </td>
                  </tr>
                ) : (
                  qualified.map((c) => {
                    const r = c.screen;
                    const isSelected = c.symbol === currentSymbol;
                    return (
                      <tr
                        key={c.symbol}
                        onClick={() => setSymbol(c.symbol)}
                        className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                          isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                        }`}
                      >
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-text-primary">{c.symbol}</span>
                            <span className="max-w-[120px] truncate text-[9.5px] text-text-muted">
                              {c.sector || c.name || '—'}
                            </span>
                          </div>
                        </td>
                        <td className="px-2.5 py-1">
                          <Badge tone={(r?.score ?? 0) >= 4 ? 'green' : 'blue'}>
                            {toFaDigits(r?.score ?? 0)} / ۵
                          </Badge>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-primary">
                          {r?.rev_growth != null ? (
                            <span className={r.rev_growth >= 0 ? 'text-accent-green' : 'text-accent-red'}>
                              {r.rev_growth > 0 ? '+' : ''}
                              {toFaDigits(r.rev_growth)}٪
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-secondary">
                          {r?.gross_margin != null ? `${toFaDigits(r.gross_margin)}٪` : '—'}
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums">
                          {c.row?.vol_ratio != null ? (
                            <span className={c.row.vol_ratio >= 1.5 ? 'font-bold text-accent-amber' : 'text-text-muted'}>
                              {toFaDigits(Math.round(c.row.vol_ratio * 10) / 10)}x
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td className="px-2.5 py-1 text-[10px] font-bold text-text-secondary">
                          {trendLabel(c.trendW)}
                        </td>
                        <td className="px-2.5 py-1">
                          <StatusDots c={c} />
                        </td>
                        <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                          <SymbolBasketAction symbol={c.symbol} compact />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'ready' && (
            <table className="w-full border-collapse text-right text-xs">
              <thead>
                <tr className="border-b border-[var(--hairline)] bg-bg-secondary/40 text-[10px] font-bold text-text-muted">
                  <th className="px-2.5 py-1">نماد و صنعت</th>
                  <th className="px-2.5 py-1">ستاپِ موتور</th>
                  <th className="px-2.5 py-1">تراز قیمت</th>
                  <th className="px-2.5 py-1">نشانه‌هایِ تابلو</th>
                  <th className="px-2.5 py-1">منبعِ رأیِ تکنیکال</th>
                  <th className="px-2.5 py-1 text-center">اقدام</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--hairline)]">
                {ready.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-xs text-text-muted">
                      هیچ نمادی هر چهار درِ S➔T➔F➔M را باز ندارد. بی‌داده «رد» نیست؛ علتِ هر مرحله درِ قیفِ بالا نوشته شده است.
                    </td>
                  </tr>
                ) : (
                  ready.map((c) => {
                    const isSelected = c.symbol === currentSymbol;
                    const price = marketCloses.data?.get(c.symbol) ?? c.row?.p_last ?? c.row?.p_closing ?? null;
                    // «فاصله تا ماشه» فقط از شواهدِ خودِ موتور (`jet.resistance`) خوانده
                    // می‌شود؛ بی‌رأیِ زنده خط تیره است، نه عددِ حدسی.
                    const res = c.jetEvidence?.resistance ?? null;
                    const gap = res != null && price != null && price > 0 ? ((res - price) / price) * 100 : null;
                    return (
                      <tr
                        key={c.symbol}
                        onClick={() => setSymbol(c.symbol)}
                        className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                          isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                        }`}
                      >
                        <td className="px-2.5 py-1">
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-text-primary">{c.symbol}</span>
                            <span className="max-w-[110px] truncate text-[9.5px] text-text-muted">{c.sector || '—'}</span>
                          </div>
                        </td>
                        <td className="px-2.5 py-1">
                          <span className="inline-flex items-center rounded border border-accent-amber/40 bg-accent-amber/10 px-2 py-0.5 text-[10px] font-bold text-accent-amber">
                            {c.setups || '—'}
                          </span>
                        </td>
                        <td className="px-2.5 py-1 font-mono tabular-nums text-text-primary">
                          {price != null ? `${fmtInt(price)} ریال` : '—'}
                        </td>
                        <td className="px-2.5 py-1 text-[9.5px] font-bold text-text-secondary">
                          {c.patterns.length ? c.patterns.join(' + ') : 'بی‌نشانه'}
                        </td>
                        <td className="px-2.5 py-1 text-[9.5px] text-text-muted" data-testid={`hub-tech-source-${c.symbol}`}>
                          {c.techSource === 'live'
                            ? '/api/ftsِ زنده'
                            : c.techSource === 'screen'
                              ? 'غنی‌سازیِ اسکرینر'
                              : 'بی‌داده'}
                          {gap != null ? ` · ${toFaDigits(Math.round(gap * 10) / 10)}٪ تا مقاومتِ جت` : ''}
                        </td>
                        <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                          <SymbolBasketAction symbol={c.symbol} compact />
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          )}

          {tab === 'portfolio' && (
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
                {holdings.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-4 text-center text-xs text-text-muted">
                      هیچ نمادی در پورتفوی فعال نیست. نمادهای تاییدشده را اضافه کنید.
                    </td>
                  </tr>
                ) : (
                  <>
                    {overBasket && (
                      <tr data-testid="hub-basket-overflow">
                        <td colSpan={6} className="px-2.5 py-1 text-[10px] font-bold text-accent-red">
                          سبد از سقفِ جزوه بیرون است: {toFaDigits(holdings.length)} نماد در برابرِ ۵ تا {toFaDigits(funnel.targets.basketMax)}.
                        </td>
                      </tr>
                    )}
                    {holdings.map((h) => {
                      const isSelected = h.symbol === currentSymbol;
                      const mrk = funnel.stages.tape.entries.find((c) => c.symbol === h.symbol)?.row ?? null;
                      const price = marketCloses.data?.get(h.symbol) ?? mrk?.p_last ?? mrk?.p_closing ?? null;
                      const pnl =
                        price != null && typeof h.price === 'number' && h.price > 0
                          ? ((price - h.price) / h.price) * 100
                          : null;
                      const weight = h.weight_eff_pct ?? 15;
                      const isWeightExcess = weight > 20;
                      return (
                        <tr
                          key={h.symbol}
                          onClick={() => setSymbol(h.symbol)}
                          className={`cursor-pointer transition-colors duration-150 hover:bg-neon-cyan/5 ${
                            isSelected ? 'bg-neon-cyan/10 font-black text-neon-cyan' : 'odd:bg-bg-secondary/20'
                          }`}
                        >
                          <td className="px-2.5 py-1">
                            <div className="flex items-center gap-1.5">
                              <span className="font-bold text-text-primary">{h.symbol}</span>
                              <span className="max-w-[110px] truncate text-[9.5px] text-text-muted">{h.sector || '—'}</span>
                            </div>
                          </td>
                          <td className="px-2.5 py-1 font-mono tabular-nums">
                            <div className="flex items-center gap-1.5">
                              <span className={`font-bold ${isWeightExcess ? 'text-accent-red' : 'text-text-primary'}`}>
                                {toFaDigits(weight)}٪
                              </span>
                              {isWeightExcess && (
                                <span className="rounded bg-accent-red/10 px-1 py-0.2 text-[9px] font-bold text-accent-red">
                                  هشدار سقف ۲۰٪
                                </span>
                              )}
                            </div>
                          </td>
                          <td className="px-2.5 py-1 font-mono tabular-nums text-text-secondary">
                            <span>{h.price != null ? toFaDigits(h.price) : '—'}</span>
                            <span className="mx-1 text-text-muted">/</span>
                            <span className="font-bold text-text-primary">{price != null ? toFaDigits(price) : '—'}</span>
                          </td>
                          <td className="px-2.5 py-1 font-mono tabular-nums">
                            {pnl != null ? (
                              <span className={`font-bold ${pnl >= 0 ? 'text-accent-green' : 'text-accent-red'}`}>
                                {pnl >= 0 ? '+' : ''}
                                {toFaDigits(Math.round(pnl * 10) / 10)}٪
                              </span>
                            ) : (
                              '—'
                            )}
                          </td>
                          <td className="px-2.5 py-1 font-mono tabular-nums text-text-muted">
                            {h.stop_loss != null ? `${toFaDigits(h.stop_loss)} ریال` : 'تعیین‌نشده'}
                          </td>
                          <td className="px-2.5 py-1 text-center" onClick={(e) => e.stopPropagation()}>
                            <SymbolBasketAction symbol={h.symbol} compact />
                          </td>
                        </tr>
                      );
                    })}
                  </>
                )}
              </tbody>
            </table>
          )}
        </div>
      )}
    </section>
  );
}
