// features/portfolio/components/WatchTable.tsx -- جدولِ زندهٔ «دیده‌بان بازار»
//
// ردیف‌ها = اشتراکِ (نمادهایِ رصدِ کاربر درِ localStorage) با (ردیف‌هایِ
// useMarketFeedShared) — همان فیدِ مشترکِ تابلو با دلتایِاش؛ نه پولینگِ موازی،
// نه درخواستِ تازه. با هر revisionِ تازه، selectِ باریک فقط آرایه را دوباره
// می‌پیماید و ردیفِ تغییریافته به‌همین‌ترتیب رندرِ تازه می‌گیرد (بی‌دکمهٔ
// «تازگی‌سازی» دستی).
//
// ستون‌ها از چیدمانِ مرجعِ مالک (1405-07-20) می‌آیند: نماد، حجم، ارزش، آخرین،
// کندلِ روز، پایانی، سپس چهار خانۀ تقاضا/عرضه (تقاضا سبز، عرضه قرمز)، وضعیت،
// ساعتِ خودِ ردیف و حذف. هیچ ستونِ پیشین حذف نشده — «تعدادِ معاملات» و
// «حجم/ارزش» سرِ جایش‌اند و صفِ اول جایِ جمعِ کلِ صف را نگرفته، چون مرجع همان
// صفِ اول را نشان می‌دهد. ستونِ «برچسب‌های تابلو» (رأیِ مالک 1405-07-21): همان
// هفت چیپِ `patternBadges`ِ تابلو، بی‌موتورِ دوم.
//
// ترازِ عددی طبقِ گاردِ UI: مقدارِ num در لبۀِ start، بعدش نشان؛ جدولِ عریض درِ
// `min-w-0 max-w-full overflow-auto`.
import { useMemo } from 'react';
import { FormingCandle } from '@shared/components/FormingCandle';
import { FlashNum } from '@shared/components/FlashNum';
import { fmtInt, fmtPct, toFaDigits, billionRialText, toBillionRial } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { patternBadges } from '@features/market/lib/tapeBadges';
import { MicroBadge } from '@features/market/components/TapeTable';
import { useTapeStore } from '@features/market/stores/tapeStore';
import {
  MATRIX_STATE_LABEL, matrixBySymbol, useWatchMatrix,
  type MatrixState, type WatchMatrixRow,
} from '@shared/api/userWatchlist';
import type { MarketFeed, MarketRow } from '@shared/types/marketRow';

/** نگاشتِ نماد(نرمال) → ردیفِ فید؛ ممو بر اساسِ مرجعِ آرایه تا هر pollِ بی‌تغییری
 *  بی‌هزینه باشد (الگویِ selectMarketCloses درِ usePortfolio.ts). */
let mapCache: { src: MarketFeed['data']; map: Map<string, MarketRow> } | null = null
function selectRowMap(feed: MarketFeed): Map<string, MarketRow> {
  if (mapCache && mapCache.src === feed.data) return mapCache.map;
  const m = new Map<string, MarketRow>();
  for (const r of feed.data ?? []) m.set(normalizeFa(String(r.symbol ?? '')), r);
  mapCache = { src: feed.data, map: m };
  return m;
}

const EMPTY_MAP = new Map<string, MarketRow>();

/** وضعیتِ معاملاتیِ canonical — سه حالتِ جدا (P0-3): متوقف ≠ st_title ≠ «موردی ثبت نشده» */
function statusText(row: MarketRow | null): { text: string; title: string; tone: string } {
  if (row == null) return { text: 'بی‌ردیف', title: 'نماد در ردیف‌های فیدِ تابلو نیست (نام معتبر یا تعطیلِ دائم؟)', tone: 'text-text-muted' };
  if (row.stop_state != null && row.stop_state !== '') {
    return { text: 'متوقف', title: row.stop_reasons ?? row.stop_state, tone: 'text-accent-red' };
  }
  if (row.sup_flag != null && row.sup_flag > 0) {
    return { text: 'زیرِ نظر', title: row.sup_reasons ?? row.sup_title ?? '', tone: 'text-accent-yellow' };
  }
  if (row.st_title || row.st_code) {
    return { text: row.st_title ?? row.st_code ?? '', title: row.st_title ?? '', tone: 'text-text-secondary' };
  }
  return { text: 'موردی ثبت نشده', title: 'هیچ وضعیتِ رسمی‌ای برایِ این نماد ثبت نشده است — «سالم» جا نمی‌زند', tone: 'text-text-muted' };
}

/** 122959 → «۱۲:۲۹»؛ نبودِ ساعت «—» است، نه «۰۰:۰۰» */
function hhmm(h: number | null | undefined): string {
  if (typeof h !== 'number' || !Number.isFinite(h) || h <= 0) return '—';
  const s = String(Math.floor(h)).padStart(6, '0');
  return toFaDigits(`${s.slice(0, 2)}:${s.slice(2, 4)}`);
}

/** صفرِ صف یعنی «در این طرف صفی نیست»؛ کلیدِ نیامده یعنی بی‌داده. این دو یکی نیستند. */
function queueCell(px: number | null | undefined) {
  if (px == null) return { text: '—', tone: 'text-text-muted', title: 'این خانۀ تابلو نرسیده — بی‌داده، نه صفر' };
  if (px === 0) return { text: 'بی‌صف', tone: 'text-text-muted', title: 'صفِ اولِ این طرف خالی است (صفرِ واقعیِ تابلو)' };
  return { text: fmtInt(px), tone: '', title: '' };
}

/** کندلِ همین نشست (اول/بیشینه/کمترین/آخرین از همان ردیفِ فید) — بی‌منبعِ دوم */
type Props = {
  symbols: string[];
  selected: string;
  onSelect: (symbol: string) => void;
  onRemove: (symbol: string) => void;
};

const TH = 'px-2 py-1.5 text-start text-3xs font-bold whitespace-nowrap';
const TD = 'px-2 py-1 text-start whitespace-nowrap';

/** برچسب‌های تابلوخوانی (هفت فیلتر) — همان `patternBadges` و همان `MicroBadge`
 * ِ خودِ تابلو (رأیِ مالک ۱۴۰-۰۷-۱۹: «همون برچسب‌های تابلوخوانی»، بی‌ترجمۀ دوم).
 *  فقط چیپ‌هایِ فیلتر (`filter:true`)؛ وضعیت‌هایِ صف+/نظارت درِ ستونِ
 *  «وضعیت» هست. */

/** «تکنیکال» و «بنیادی» درِ دیده‌بان (رأیِ مالک ۱۴۰۵-۰۷-۲۲): دو ستونِ وضعیت،
 *  با همان چهار حالتِ `confidence_engine.PILLAR_STATES`. داوری اینجا ساخته
 *  نمی‌شود — `/api/watchlist/matrix` همان «تأیید سه‌گانه» را می‌دهد که سبدگردانی
 *  می‌خواند، پس دو داور نداریم. نبودِ ردیفِ ماتریس «—» است نه «رد». */
const PILLAR_TONE: Record<MatrixState, string> = {
  pass: 'text-accent-green',
  warn: 'text-accent-yellow',
  fail: 'text-accent-red',
  nodata: 'text-text-muted',
};

function asState(v: string | undefined | null): MatrixState | null {
  return v === 'pass' || v === 'warn' || v === 'fail' || v === 'nodata' ? v : null;
}

function PillarCell({ row, pillar, pending }: {
  row: WatchMatrixRow | undefined;
  pillar: 'tech' | 'fund';
  pending: boolean;
}) {
  if (!row) {
    return (
      <span
        className="text-2xs text-text-muted"
        title={pending ? 'ماتریسِ تأیید در راه است' : 'این نماد درِ ماتریسِ تأیید نیست'}
      >
        {pending ? '…' : '—'}
      </span>
    );
  }
  const st = asState(row.states?.[pillar] ?? row.pillars?.[pillar]?.state);
  if (!st) return <span className="text-2xs text-text-muted" title="وضعیتی برایِ این ستون نرسید">—</span>;
  const det = row.pillars?.[pillar];
  const reasons = (det?.reasons ?? []).filter(Boolean).join(' · ');
  const asof = det?.asof ?? row.asof?.[pillar] ?? null;
  const title = [MATRIX_STATE_LABEL[st], reasons, asof != null ? `سنجش: ${asof}` : null]
    .filter(Boolean).join(' — ');
  return (
    <span
      data-testid={`watch-${pillar}-${row.symbol ?? ''}`}
      className={`text-2xs font-bold ${PILLAR_TONE[st]}`}
      title={title}
    >
      {MATRIX_STATE_LABEL[st]}
    </span>
  );
}

export function WatchTable({ symbols, selected, onSelect, onRemove }: Props) {
  const feedQ = useMarketFeedShared(selectRowMap, 60_000);
  const byNorm = feedQ.data ?? EMPTY_MAP;
  const tapeCfg = useTapeStore((s) => s.tapeFilterConfig);
  // یک درخواست برایِ کلِ فهرستِ رصد (ضدِN+1 درِ خودِ بک‌اند هم همین‌طور)، بی‌
  // پولینگِ موازی با ریتمِ تابلو.
  const matrixQ = useWatchMatrix(symbols);
  const mtx = useMemo(() => matrixBySymbol(matrixQ.data?.rows), [matrixQ.data]);
  const matrixPending = matrixQ.isPending && symbols.length > 0;
  // اندپوینتِ خطا را با HTTP ۲۰۰ و `status: 'error'` می‌دهد (`api/watchlist.py:112`)،
  // پس `isError` تنها شرطِ «نرسید» نیست.
  const matrixFailed = matrixQ.isError || (matrixQ.data != null && matrixQ.data.status !== 'success');

  const rows = useMemo(
    () => symbols.map((s) => ({ symbol: s, row: byNorm.get(normalizeFa(s)) ?? null })),
    [symbols, byNorm],
  );

  return (
    <div className="glass-panel min-w-0 max-w-full overflow-hidden rounded-2xl" data-testid="watch-table">
      <div className="max-w-full overflow-auto">
        <table className="w-full min-w-[1140px] border-collapse text-xs">
          <thead>
            <tr className="bg-bg-card/70 text-start text-3xs uppercase tracking-wider text-text-secondary">
              <th className={TH}>نماد</th>
              <th className={TH}>حجم</th>
              <th className={TH}>تعداد</th>
              <th className={TH}>ارزش (م.ریال)</th>
              <th className={TH}>آخرین</th>
              <th className={TH}>تغییر٪</th>
              <th className={TH}>کندل روز</th>
              <th className={TH}>پایانی</th>
              <th className={`${TH} bg-accent-green/10 text-accent-green`}>حجم تقاضا</th>
              <th className={`${TH} bg-accent-green/10 text-accent-green`}>قیمت تقاضا</th>
              <th className={`${TH} bg-accent-red/10 text-accent-red`}>قیمت عرضه</th>
              <th className={`${TH} bg-accent-red/10 text-accent-red`}>حجم عرضه</th>
              <th className={TH}>وضعیت</th>
              <th className={TH}>برچسب‌های تابلو</th>
              <th className={TH}>تکنیکال</th>
              <th className={TH}>بنیادی</th>
              <th className={TH}>به‌روزرسانی</th>
              <th className={TH}>حذف</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ symbol, row }) => {
              const st = statusText(row);
              const pct = row?.percent_change ?? null;
              const isSel = normalizeFa(symbol) === normalizeFa(selected);
              const dem = queueCell(row?.buy_q1_px);
              const sup = queueCell(row?.sell_q1_px);
              const badges = row ? patternBadges(row, tapeCfg).filter((b) => b.filter) : [];
              return (
                <tr
                  key={symbol}
                  data-testid={`watch-row-${symbol}`}
                  aria-selected={isSel}
                  className={`cursor-pointer border-b border-[var(--hairline)] transition-colors duration-150 last:border-0 odd:bg-bg-secondary/40 hover:bg-bg-card/60 ${
                    isSel ? 'bg-accent-blue/12 outline outline-1 outline-border-accent' : ''
                  }`}
                  tabIndex={0}
                  aria-label={`انتخاب ${symbol} در دیده‌بان`}
                  onClick={() => onSelect(symbol)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault();
                      onSelect(symbol);
                    }
                  }}
                >
                  <td className={`${TD} max-w-[15ch]`}>
                    <span className="font-black text-text-primary">{symbol}</span>
                    <span className="line-clamp-2 block text-3xs leading-3 text-text-muted">{row?.name ?? ''}</span>
                  </td>
                  <td className={TD}>
                    <FlashNum variant="neutral" value={row?.q_tot_tran ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="text-text-secondary" />
                  </td>
                  <td className={TD}>
                    <FlashNum variant="neutral" value={row?.z_tot_tran ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="text-text-secondary" />
                  </td>
                  <td className={TD}>
                    <FlashNum variant="neutral" value={toBillionRial(row?.q_tot_cap ?? null)} render={billionRialText} className="text-text-secondary" />
                  </td>
                  <td className={TD}>
                    <FlashNum variant="neutral" value={row?.p_last ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="font-bold text-text-primary" />
                  </td>
                  <td className={TD}>
                    <FlashNum
                      variant="neutral"
                      value={pct}
                      render={(v) => (v == null ? '—' : fmtPct(v))}
                      className={`font-bold ${
                        pct == null ? 'text-text-muted' : pct > 0 ? 'text-accent-green' : pct < 0 ? 'text-accent-red' : 'text-text-secondary'
                      }`}
                    />
                  </td>
                  <td className={`${TD} text-center`}><FormingCandle candle={row} testId="watch-day-candle" /></td>
                  <td className={TD}>
                    <FlashNum variant="neutral" value={row?.p_closing ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="text-text-secondary" />
                  </td>
                  <td className={`${TD} bg-accent-green/5`} title="حجمِ سفارشِ سطرِ اولِ صفِ خرید">
                    <FlashNum variant="neutral" value={row?.buy_q1_vol ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="font-bold text-accent-green" />
                  </td>
                  <td className={`${TD} bg-accent-green/5`} title={dem.title || 'قیمتِ سطرِ اولِ صفِ خرید'}>
                    <span className={`num font-bold text-accent-green ${dem.tone}`}>{dem.text}</span>
                  </td>
                  <td className={`${TD} bg-accent-red/5`} title={sup.title || 'قیمتِ سطرِ اولِ صفِ فروش'}>
                    <span className={`num font-bold text-accent-red ${sup.tone}`}>{sup.text}</span>
                  </td>
                  <td className={`${TD} bg-accent-red/5`} title="حجمِ سفارشِ سطرِ اولِ صفِ فروش">
                    <FlashNum variant="neutral" value={row?.sell_q1_vol ?? null} render={(v) => (v == null ? '—' : fmtInt(v))} className="font-bold text-accent-red" />
                  </td>
                  <td className={TD}>
                    <span className={`text-2xs font-bold ${st.tone}`} title={st.title}>{st.text}</span>
                    {row && row.is_live === false ? <span className="ms-1 text-3xs text-accent-yellow" title="قیمت‌ها از آخرین روز معاملاتیِ بسته‌شده است">آخرین داده</span> : null}
                  </td>
                  <td className={TD} title="همان هفت فیلترِ تابلوخوانی که درِ تبِّ تابلو روشن می‌شوند (وضعیتِ همین نشست)">
                    {badges.length ? (
                      <span className="flex min-w-0 flex-wrap items-center gap-0.5" data-testid={`watch-tape-badges-${symbol}`}>
                        {badges.map((b) => (
                          <MicroBadge key={b.key} pattern={b.pattern} tone={b.tone} title={b.title}>
                            {b.label}
                          </MicroBadge>
                        ))}
                      </span>
                    ) : (
                      <span className="text-3xs text-text-muted"
                            data-testid={`watch-tape-badges-${symbol}`}>
                        {row ? 'بی‌برچسب' : '—'}
                      </span>
                    )}
                  </td>
                  <td className={TD}>
                    <PillarCell row={mtx.get(normalizeFa(symbol))} pillar="tech" pending={matrixPending} />
                  </td>
                  <td className={TD}>
                    <PillarCell row={mtx.get(normalizeFa(symbol))} pillar="fund" pending={matrixPending} />
                  </td>
                  <td className={TD} title="ساعتِ خودِ همین ردیف در تابلو (نه ساعتِ کلیِ همگام‌سازی)">
                    <span className="num text-2xs text-text-secondary">{hhmm(row?.row_h)}</span>
                  </td>
                  <td className={TD}>
                    <button
                      type="button"
                      data-testid={`watch-remove-${symbol}`}
                      aria-label={`حذفِ ${symbol} از دیده‌بان`}
                      onClick={(e) => {
                        e.stopPropagation();
                        onRemove(symbol);
                      }}
                      className="rounded-md border border-border-c px-1.5 py-0.5 text-2xs font-bold text-text-muted hover:border-accent-red hover:text-accent-red"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <footer className="flex flex-wrap items-center gap-2 border-t border-border-c/60 px-3 py-1.5 text-3xs text-text-muted">
        <span className="num">{toFaDigits(rows.length)} نمادِ رصدشده</span>
        <span title="قیمت/حجم/صف‌ها از همان فیدِ مشترکِ تابلو (دلتا) می‌آید">داده با هر دورِ فیدِ زندهٔ تابلو تازه می‌شود؛ دکمۀ «تازگی‌سازی» دستی لازم نیست</span>
        <span
          data-testid="watch-matrix-state"
          title="«تکنیکال» و «بنیادی» همان تأییدِ سه‌گانۀ خودِ برنامه است (`/api/watchlist/matrix`)، در یک درخواست برایِ کلِ فهرست"
        >
          {matrixFailed
            ? 'ماتریسِ تأیید نرسید — دو ستونِ وضعیت «—» می‌مانند'
            : matrixPending && !matrixQ.data
              ? 'ماتریسِ تأیید در راه است…'
              : `وضعیت‌ها از ماتریسِ تأیید (${toFaDigits(mtx.size)} نماد)`}
        </span>
        <span data-testid="watch-feed-state" className="ms-auto">
          {feedQ.isError ? (
            <span className="text-accent-red">خطایِ فید — اعدادِ پایین آخرینِ پاسخِ موفق‌اند</span>
          ) : feedQ.isPending ? (
            <span>در حالِ خواندنِ فید…</span>
          ) : (
            <span>فیدِ مشترکِ تابلو</span>
          )}
        </span>
      </footer>
    </div>
  );
}
