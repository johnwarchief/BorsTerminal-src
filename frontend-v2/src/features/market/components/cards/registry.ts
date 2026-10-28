import { faNum, fmtInt, fmtMcap, fmtVolume } from '@shared/lib/fa';
import type { MarketFeed, MarketRow } from '@shared/types/market';
import type { CardId } from '@shared/workspace/store';
import type { MarketSnapshot } from '../../api/useMarketSnapshot';
import { boardSums, breadthOf, compositionOf, TYPE_LABEL } from '../../lib/boardMetrics';

export interface CardContext {
  rows: readonly MarketRow[];
  feed?: MarketFeed;
  snapshot?: MarketSnapshot;
}

export interface PreviewRow {
  label: string;
  value: string;
  basis?: 'board' | 'market';
  note?: string;
}

export interface CardDescriptor {
  id: CardId;
  label: string;
  unit?: string;
  basis: 'board' | 'market';
  value: (ctx: CardContext) => string | null;
  delta: (ctx: CardContext) => number | null;
  preview: (ctx: CardContext) => PreviewRow[];
}

const noPrev = 'نشستِ قبل در دسترس نیست';

/** عددِ همتی: snapshot همین واحد را می‌فرستد، پس تقسیمِ دوباره ندارد. */
function fmtHemat(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '—' : faNum(value, 1);
}

function marketDelta(current: number | null | undefined, previous: number | null | undefined): number | null {
  if (current == null || previous == null || previous === 0) return null;
  return ((current - previous) / previous) * 100;
}

function signedPct(value: number | null): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value >= 0 ? '+' : '−'}${faNum(Math.abs(value), 1)}٪`;
}

export const CARD_REGISTRY: Record<CardId, CardDescriptor> = {
  tedpix: {
    id: 'tedpix', label: 'شاخص کل بورس', basis: 'market',
    value: ({ snapshot }) => (snapshot?.index?.last != null ? fmtInt(snapshot.index.last) : null),
    delta: ({ snapshot }) => marketDelta(snapshot?.index?.last, snapshot?.prev?.last),
    preview: ({ snapshot }) => {
      const index = snapshot?.index;
      const market = snapshot?.market;
      if (!index) return [{ label: 'شاخص کل', value: '—', note: 'snapshot نرسیده' }];
      const vsPrev = marketDelta(index.last, snapshot?.prev?.last);
      return [
        { label: 'نسبت به نشست قبل', value: signedPct(vsPrev), basis: 'market', note: snapshot?.prev ? undefined : noPrev },
        { label: 'درصدِ امروز', value: index.pct != null ? signedPct(index.pct) : '—', basis: 'market' },
        { label: 'هم‌وزن', value: index.ew_last != null ? `${fmtInt(index.ew_last)}${index.ew_pct != null ? ` (${signedPct(index.ew_pct)})` : ''}` : '—', basis: 'market' },
        { label: 'ارزش', value: market?.trade_value_hemat != null ? `${fmtHemat(market.trade_value_hemat)} همت` : '—', basis: 'market' },
        { label: 'حجم', value: market?.volume != null ? fmtVolume(market.volume) : '—', basis: 'market' },
        { label: 'تعداد معاملات', value: market?.trades != null ? fmtInt(market.trades) : '—', basis: 'market' },
      ];
    },
  },
  retailValue: {
    id: 'retailValue', label: 'ارزش معاملات خرد', unit: 'همت', basis: 'market',
    value: ({ snapshot }) => (snapshot?.retail?.value_hemat != null ? fmtHemat(snapshot.retail.value_hemat) : null),
    // نشستِ قبل در snapshot فقط جمعِ کلِ بازار را دارد، نه خرد؛ مقایسهٔ خرد با
    // کل، دو چیز را به هم می‌بندد، پس Δ ساخته نمی‌شود.
    delta: () => null,
    preview: ({ snapshot }) => {
      const retail = snapshot?.retail;
      if (!retail) return [{ label: 'ارزش خرد', value: '—', note: 'snapshot نرسیده' }];
      return [
        { label: 'وضعیت', value: retail.label ?? '—', basis: 'market', note: retail.cause ?? undefined },
        { label: 'آستانهٔ مساعد', value: retail.good_min != null ? `${faNum(retail.good_min)} همت` : '—', basis: 'market' },
        { label: 'آستانهٔ نامساعد', value: retail.bad_max != null ? `${faNum(retail.bad_max)} همت` : '—', basis: 'market' },
        { label: 'ارزش بازار', value: snapshot?.market?.market_value_hemat != null ? `${fmtHemat(snapshot.market.market_value_hemat)} همت` : '—', basis: 'market' },
        { label: 'نسبت به نشست قبل', value: '—', basis: 'market', note: 'ارزش خردِ نشست قبل در پاسخ نیست' },
      ];
    },
  },
  boardValueComposition: {
    id: 'boardValueComposition', label: 'ارزش و ترکیب تابلو', unit: 'همت', basis: 'board',
    value: ({ rows }) => (rows.length ? fmtMcap(boardSums(rows).value) : null),
    delta: () => null,
    preview: ({ rows }) => {
      const sums = boardSums(rows);
      const pieces = compositionOf(rows);
      return [
        { label: 'حجم', value: fmtVolume(sums.volume), basis: 'board' },
        { label: 'ردیف', value: fmtInt(rows.length), basis: 'board' },
        ...pieces.map((piece) => ({
          label: TYPE_LABEL[piece.type],
          value: piece.value ? `${fmtMcap(piece.value)} همت · ${fmtInt(piece.count)}` : fmtInt(piece.count),
          basis: 'board' as const,
        })),
      ];
    },
  },
  breadth: {
    id: 'breadth', label: 'پهنای بازار', basis: 'board',
    value: ({ rows }) => {
      if (!rows.length) return null;
      const b = breadthOf(rows);
      return `${fmtInt(b.up)}▲ / ${fmtInt(b.down)}▼`;
    },
    delta: () => null,
    preview: ({ rows }) => {
      const b = breadthOf(rows);
      return [
        { label: 'مثبت', value: `${fmtInt(b.up)} (${faNum(b.upPct)}٪)`, basis: 'board' },
        { label: 'منفی', value: `${fmtInt(b.down)} (${faNum(b.downPct)}٪)`, basis: 'board' },
        { label: 'بی‌تغییر', value: `${fmtInt(b.flat)} (${faNum(b.flatPct)}٪)`, basis: 'board' },
        { label: 'بدونِ درصدِ خوانا', value: fmtInt(b.unknown), basis: 'board', note: 'در این ردیف‌ها درصد خوانا نیست' },
      ];
    },
  },
  boardVolume: {
    id: 'boardVolume', label: 'حجم تابلو', basis: 'board',
    value: ({ rows }) => (rows.length ? fmtVolume(boardSums(rows).volume) : null),
    delta: () => null,
    preview: ({ rows }) => [
      { label: 'ارزش', value: `${fmtMcap(boardSums(rows).value)} همت`, basis: 'board' },
      { label: 'ردیف', value: fmtInt(rows.length), basis: 'board' },
    ],
  },
  marketTrades: {
    id: 'marketTrades', label: 'تعداد معاملات بازار', basis: 'market',
    value: ({ snapshot }) => (snapshot?.market?.trades != null ? fmtInt(snapshot.market.trades) : null),
    delta: ({ snapshot }) => marketDelta(snapshot?.market?.trades, snapshot?.prev?.z_tot_tran),
    preview: ({ snapshot }) => [
      {
        label: 'نسبت به نشست قبل',
        value: signedPct(marketDelta(snapshot?.market?.trades, snapshot?.prev?.z_tot_tran)),
        basis: 'market',
        note: snapshot?.prev ? undefined : noPrev,
      },
      { label: 'حجم', value: snapshot?.market?.volume != null ? fmtVolume(snapshot.market.volume) : '—', basis: 'market' },
      { label: 'ارزش', value: snapshot?.market?.trade_value_hemat != null ? `${fmtHemat(snapshot.market.trade_value_hemat)} همت` : '—', basis: 'market' },
    ],
  },
};

export const CARD_ORDER: CardId[] = [
  'tedpix', 'retailValue', 'breadth', 'boardValueComposition', 'boardVolume', 'marketTrades',
];
