// lib/candleEdgeMvp.ts -- لایهٔ نمایشیِ MVP روی خروجی ماژول CandleEdge.
// فقط هشت آشکارسازِ VALIDATED_CANDIDATE؛ هیچ محاسبهٔ الگوی تازه، هیچ آستانهٔ تازه.
// سالینس همان لایهٔ پژوهش است و روشِ واحدِ MVP «structure_first» است.
import { fmtInt, toFaDigits } from '@shared/lib/fmt';
import type {
  CandleTime,
  DetectorId,
  PatternBias,
  PatternEvent,
} from '../signals/candleedge';
import { buildSalience } from '../signals/candleedge/research/salience';
import type { SalienceBias, SalienceInputEvent, SalienceMethod } from '../signals/candleedge/research/types';
import { TIMEFRAME_LABELS, type Timeframe } from '../nahayatnegar/lib/timeframe';
import { epochToJalali, parseCandleTimestamp } from './jalaliDate';

export const CANDLEEDGE_MVP_DETECTORS = [
  'bullish_engulfing',
  'bearish_engulfing',
  'bos_bullish',
  'bos_bearish',
  'liquidity_sweep_high',
  'liquidity_sweep_low',
  'double_top',
  'double_bottom',
] as const satisfies readonly DetectorId[];

export type CandleEdgeMvpDetector = (typeof CANDLEEDGE_MVP_DETECTORS)[number];

const MVP_SET: ReadonlySet<string> = new Set(CANDLEEDGE_MVP_DETECTORS);

/** تنها روشِ ترتیبِ MVP. مقایسهٔ چند روش به پژوهش بعدی موکول شد. */
export const CANDLEEDGE_MVP_METHOD: SalienceMethod = 'structure_first';
export const CANDLEEDGE_MVP_METHOD_NOTE =
  'ترتیب: ساختار بازار، سپس ساختار نمودار، سپس کندل؛ درون هر رتبه آخرین تأیید. این ترتیب نمایش است، نه اعتبار یا احتمال.';

export const CANDLEEDGE_EXPERIMENTAL_NOTE =
  'الگوریتم آزمایشی؛ سیگنال رسمی FTS یا توصیهٔ خرید/فروش نیست.';

/** یک کندلِ سریِ نمایشیِ چارت (تعدیل‌شده و تجمیع‌شده). */
export interface CandleEdgeBar {
  timestamp: CandleTime;
  open: number;
  high: number;
  low: number;
  close: number;
}

/** همان قراردادی که چارت به پنل می‌دهد؛ اسکن روی همین سری انجام شده است. */
export interface CandleEdgeChartData {
  symbol: string;
  timeframe: Timeframe;
  bars: readonly CandleEdgeBar[];
  events: readonly PatternEvent[];
  error: string | null;
}

export const CANDLEEDGE_DETECTOR_LABELS: Record<CandleEdgeMvpDetector, string> = {
  bullish_engulfing: 'پوشای صعودی',
  bearish_engulfing: 'پوشای نزولی',
  bos_bullish: 'شکست ساختار صعودی (BOS)',
  bos_bearish: 'شکست ساختار نزولی (BOS)',
  liquidity_sweep_high: 'جاروی نقدینگی بالا',
  liquidity_sweep_low: 'جاروی نقدینگی پایین',
  double_top: 'سقف دوقلو',
  double_bottom: 'کف دوقلو',
};

const BIAS_LABELS: Record<SalienceBias, string> = {
  bullish: 'صعودی',
  bearish: 'نزولی',
  neutral: 'بی‌جهت',
  mixed: 'دوجهته',
};

export function candleEdgeLabel(detector: DetectorId | string): string {
  return (CANDLEEDGE_DETECTOR_LABELS as Record<string, string>)[detector] ?? detector;
}

export function candleEdgeBiasLabel(bias: PatternBias | SalienceBias): string {
  return BIAS_LABELS[bias] ?? bias;
}

export function candleEdgeDate(time: CandleTime | null | undefined): string {
  if (time == null) return '';
  const ms = parseCandleTimestamp(time);
  return Number.isFinite(ms) && ms > 0 ? toFaDigits(epochToJalali(ms)) : '';
}

export function isCandleEdgeMvpDetector(detector: DetectorId | string): boolean {
  return MVP_SET.has(detector);
}

/** رویدادهای confirmed از هشت آشکارسازِ MVP؛ خروجی provisional هرگز وارد نمی‌شود. */
export function filterCandleEdgeEvents(events: readonly PatternEvent[]): PatternEvent[] {
  return events.filter(
    (event) => event.status === 'confirmed' && isCandleEdgeMvpDetector(event.detector),
  );
}

export interface CandleEdgeCounts {
  total: number;
  bullish: number;
  bearish: number;
  neutral: number;
}

export function candleEdgeCounts(events: readonly PatternEvent[]): CandleEdgeCounts {
  const counts: CandleEdgeCounts = { total: events.length, bullish: 0, bearish: 0, neutral: 0 };
  for (const event of events) {
    if (event.bias === 'bullish') counts.bullish += 1;
    else if (event.bias === 'bearish') counts.bearish += 1;
    else counts.neutral += 1;
  }
  return counts;
}

export interface CandleEdgeGroupView {
  id: string;
  events: PatternEvent[];
  bias: SalienceBias;
  detectors: DetectorId[];
  earliestConfirmedAtIndex: number;
  latestConfirmedAtIndex: number;
}

export interface CandleEdgeGroups {
  groups: CandleEdgeGroupView[];
  method: SalienceMethod;
  note: string;
}

function toSalienceInput(event: PatternEvent): SalienceInputEvent {
  return {
    key: event.key,
    detector: event.detector,
    family: event.family,
    bias: event.bias,
    confirmedAtIndex: event.confirmedAtIndex,
    confirmedAt: typeof event.confirmedAt === 'number' ? event.confirmedAt : undefined,
    anchors: event.anchors,
    level: event.level,
  };
}

/** گروه‌بندی و ترتیبِ موجودِ پژوهش، بدون بازسازی یا امتیاز تازه. */
export function buildCandleEdgeGroups(
  seriesKey: string,
  events: readonly PatternEvent[],
): CandleEdgeGroups {
  if (events.length === 0) {
    return { groups: [], method: CANDLEEDGE_MVP_METHOD, note: CANDLEEDGE_MVP_METHOD_NOTE };
  }
  const input = events.map(toSalienceInput);
  const latest = Math.max(...events.map((event) => event.confirmedAtIndex));
  const result = buildSalience(seriesKey, input, latest);
  const byKey = new Map(events.map((event) => [event.key, event]));
  const byId = new Map(result.groups.map((group) => [group.id, group]));
  const groups: CandleEdgeGroupView[] = [];
  for (const id of result.order[CANDLEEDGE_MVP_METHOD]) {
    const raw = byId.get(id);
    if (!raw) continue;
    const groupedEvents = raw.eventKeys
      .map((key) => byKey.get(key))
      .filter((event): event is PatternEvent => Boolean(event));
    if (groupedEvents.length === 0) continue;
    groups.push({
      id,
      events: groupedEvents,
      bias: raw.bias,
      detectors: raw.detectors as DetectorId[],
      earliestConfirmedAtIndex: raw.earliestConfirmedAtIndex,
      latestConfirmedAtIndex: raw.latestConfirmedAtIndex,
    });
  }
  return { groups, method: CANDLEEDGE_MVP_METHOD, note: CANDLEEDGE_MVP_METHOD_NOTE };
}

/** سقفِ نشانگرهای چارت: یک نماینده از هر گروهِ پیشرو، نه هر ۱۰۰۰ رویداد. */
export const CANDLEEDGE_CHART_GROUP_LIMIT = 30;
export const CANDLEEDGE_CHART_NOTE =
  `روی چارت فقط ${toFaDigits(String(CANDLEEDGE_CHART_GROUP_LIMIT))} گروهِ نخست به ترتیب بالا رسم می‌شود؛ ` +
  'انتخاب هر رویداد آن را جدا روی چارت نشان می‌دهد.';

/** یک نمایندهٔ تازه‌ترین‌تأیید از هر گروهِ پیشرو + همیشه رویدادِ انتخاب‌شده. */
export function selectCandleEdgeChartEvents(
  groups: readonly CandleEdgeGroupView[],
  selectedKey: string | null,
  limit = CANDLEEDGE_CHART_GROUP_LIMIT,
): PatternEvent[] {
  const chosen = new Map<string, PatternEvent>();
  for (const group of groups.slice(0, Math.max(0, limit))) {
    if (group.events.length === 0) continue;
    const newest = [...group.events].sort(
      (a, b) => b.confirmedAtIndex - a.confirmedAtIndex || a.key.localeCompare(b.key),
    )[0];
    chosen.set(newest.key, newest);
  }
  if (selectedKey != null) {
    const selected = groups
      .flatMap((group) => group.events)
      .find((event) => event.key === selectedKey);
    if (selected) chosen.set(selected.key, selected);
  }
  return [...chosen.values()].sort(
    (a, b) => a.confirmedAtIndex - b.confirmedAtIndex || a.key.localeCompare(b.key),
  );
}

export interface CandleEdgeAnchorView {
  roleLabel: string;
  date: string;
  price: number;
  /** تاریخی که پیوت با پنجرهٔ راست تأیید شد — جدا از زمان خودِ پیوت. */
  pivotConfirmedDate: string | null;
}

export interface CandleEdgeCandleView {
  index: number;
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface CandleEdgeAnalysis {
  eventKey: string;
  title: string;
  bias: PatternBias;
  biasLabel: string;
  timeframeLabel: string;
  formationDate: string;
  confirmationDate: string;
  anchors: CandleEdgeAnchorView[];
  level: number | null;
  candles: CandleEdgeCandleView[];
  significance: string;
  limits: string[];
  invalidation: string | null;
}

function anchorRoleLabel(
  event: PatternEvent,
  anchor: PatternEvent['anchors'][number],
  order: number,
): string {
  const isEventBar = anchor.index === event.confirmedAtIndex;
  switch (event.detector) {
    case 'bullish_engulfing':
    case 'bearish_engulfing':
      return isEventBar ? 'کندل پوشاننده' : 'کندل پوشیده‌شده';
    case 'bos_bullish':
    case 'bos_bearish':
      return isEventBar ? 'کندل شکست' : 'سطح شکسته‌شده';
    case 'liquidity_sweep_high':
    case 'liquidity_sweep_low':
      return isEventBar ? 'کندل جارو' : 'سطح نقدینگی جاروشده';
    case 'double_top':
      return `سقف ${order === 0 ? 'اول' : 'دوم'}`;
    case 'double_bottom':
      return `کف ${order === 0 ? 'اول' : 'دوم'}`;
    default:
      return anchor.role;
  }
}

function significanceOf(event: PatternEvent): string {
  switch (event.detector) {
    case 'bullish_engulfing':
      return 'کندل صعودی، بدنهٔ کندل نزولی قبلی را کامل در بر گرفته است؛ خوانشِ تغییر موضع خریدار در همان بازه.';
    case 'bearish_engulfing':
      return 'کندل نزولی، بدنهٔ کندل صعودی قبلی را کامل در بر گرفته است؛ خوانشِ تغییر موضع فروشنده در همان بازه.';
    case 'bos_bullish':
      return 'قیمت با بسته‌شدن بالای آخرین سقفِ تأییدشده بست؛ شکست ساختار محلی به سمت بالا.';
    case 'bos_bearish':
      return 'قیمت با بسته‌شدن زیر آخرین کفِ تأییدشده بست؛ شکست ساختار محلی به سمت پایین.';
    case 'liquidity_sweep_high':
      return 'سایهٔ کندل بالای یک سقفِ ازپیش‌تأییدشده رفت و قیمت زیر آن بست؛ خوانشِ جاروی نقدینگیِ بالای بازار.';
    case 'liquidity_sweep_low':
      return 'سایهٔ کندل زیر یک کفِ ازپیش‌تأییدشده رفت و قیمت بالای آن بست؛ خوانشِ جاروی نقدینگیِ زیر بازار.';
    case 'double_top':
      return 'دو سقفِ نزدیک به یک سطح با فاصلهٔ زمانی معتبر و پولبک میانی؛ ساختار سقف دوقلو.';
    case 'double_bottom':
      return 'دو کفِ نزدیک به یک سطح با فاصلهٔ زمانی معتبر و بازگشت میانی؛ ساختار کف دوقلو.';
    default:
      return '';
  }
}

function limitsOf(event: PatternEvent): string[] {
  const limits = [
    'محاسبه روی همین سریِ تعدیل‌شده و تجمیع‌شدهٔ چارت است؛ تغییر تایم‌فریم یا مبنای قیمت می‌تواند رویداد را جابه‌جا کند.',
    'آستانه‌ها و پنجره‌های الگوریتم ثابت و آزمایشی‌اند و در این نسخه قابل تنظیم نیستند.',
    'تأیید رویداد یعنی عبور از پنجرهٔ راست پیوت؛ وضعیت provisional نمایش داده نمی‌شود.',
  ];
  if (event.detector === 'bos_bullish' || event.detector === 'bos_bearish') {
    limits.push('زمان شکست، بسته‌شدن کندل شکست است؛ تأیید پیوتِ سطح می‌تواند چند کندل زودتر رخ داده باشد.');
  }
  if (event.detector === 'liquidity_sweep_high' || event.detector === 'liquidity_sweep_low') {
    limits.push('سطح جاروشده پیش از رویداد با تأیید پیوت معلوم بوده؛ نفوذ باید با بسته‌شدن در همان سمت سطح برگردد.');
  }
  if (event.detector === 'double_top' || event.detector === 'double_bottom') {
    limits.push('الگوریتم خط گردن و شکست آن را تعریف نمی‌کند؛ تأیید فقط پس از پنجرهٔ راست پیوت دوم است.');
  }
  if (event.detector === 'bullish_engulfing' || event.detector === 'bearish_engulfing') {
    limits.push('الگو فقط از کندل ساخته می‌شود؛ تأیید حجم یا روند بعدی در آن تعریف نشده است.');
  }
  limits.push(CANDLEEDGE_EXPERIMENTAL_NOTE);
  return limits;
}

function invalidationOf(event: PatternEvent): string | null {
  const level = event.level;
  const second = event.anchors[1];
  switch (event.detector) {
    case 'bos_bullish':
      return level == null ? null : `بسته‌شدن دوبارهٔ قیمت زیر سطح شکسته‌شده (${fmtInt(level)}).`;
    case 'bos_bearish':
      return level == null ? null : `بسته‌شدن دوبارهٔ قیمت بالای سطح شکسته‌شده (${fmtInt(level)}).`;
    case 'liquidity_sweep_high':
      return level == null ? null : `بسته‌شدن دوبارهٔ قیمت بالای سطح جاروشده (${fmtInt(level)}).`;
    case 'liquidity_sweep_low':
      return level == null ? null : `بسته‌شدن دوبارهٔ قیمت زیر سطح جاروشده (${fmtInt(level)}).`;
    case 'double_top':
      return second ? `بسته‌شدن قیمت بالای سقف دوم (${fmtInt(second.price)}).` : null;
    case 'double_bottom':
      return second ? `بسته‌شدن قیمت زیر کف دوم (${fmtInt(second.price)}).` : null;
    default:
      return null;
  }
}

export function buildCandleEdgeAnalysis(
  event: PatternEvent,
  data: CandleEdgeChartData,
): CandleEdgeAnalysis {
  const bars = data.bars;
  const anchors = event.anchors.map((anchor, order) => ({
    roleLabel: anchorRoleLabel(event, anchor, order),
    date: candleEdgeDate(anchor.time),
    price: anchor.price,
    pivotConfirmedDate:
      anchor.confirmedAtIndex != null && bars[anchor.confirmedAtIndex]
        ? candleEdgeDate(bars[anchor.confirmedAtIndex].timestamp)
        : null,
  }));

  const formationAnchor = [...event.anchors].sort((a, b) => b.index - a.index)[0];
  const candleIndices = [...new Set(event.anchors.map((anchor) => anchor.index))].sort(
    (a, b) => a - b,
  );
  const candles = candleIndices
    .filter((index) => bars[index])
    .map((index) => {
      const bar = bars[index];
      return {
        index,
        date: candleEdgeDate(bar.timestamp),
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      };
    });

  return {
    eventKey: event.key,
    title: candleEdgeLabel(event.detector),
    bias: event.bias,
    biasLabel: candleEdgeBiasLabel(event.bias),
    timeframeLabel: TIMEFRAME_LABELS[data.timeframe] ?? data.timeframe,
    formationDate: formationAnchor ? candleEdgeDate(formationAnchor.time) : '',
    confirmationDate: candleEdgeDate(event.confirmedAt),
    anchors,
    level: event.level ?? null,
    candles,
    significance: significanceOf(event),
    limits: limitsOf(event),
    invalidation: invalidationOf(event),
  };
}

export interface CandleEdgeOverlayPoint {
  timestamp: number;
  value: number;
}

export interface CandleEdgeOverlaySpec {
  name: 'simpleAnnotation' | 'segment';
  groupId: string;
  lock: boolean;
  points: CandleEdgeOverlayPoint[];
  extendData?: string;
  styles?: Record<string, unknown>;
  /** فرادادهٔ داخلیِ پنل/چارت؛ پیش از createOverlay حذف می‌شود. */
  meta: { eventKey: string; kind: 'marker' | 'level' | 'pivot-link' };
}

export const CANDLEEDGE_OVERLAY_GROUP = 'candleedge_mvp';
export const CANDLEEDGE_GLYPHS: Record<'bullish' | 'bearish', string> = {
  bullish: '▲',
  bearish: '▼',
};
const OVERLAY_COLORS: Record<'bullish' | 'bearish', string> = {
  bullish: '#26a69a',
  bearish: '#ef5350',
};

function overlayTimestamp(time: CandleTime): number {
  const ts = parseCandleTimestamp(time);
  return Number.isFinite(ts) && ts > 0 ? ts : Number.NaN;
}

/**
 * یک نشانگرِ بی‌برچسب برای هر رویداد؛ خط سطح/اتصال پیوت فقط برای رویدادِ
 * انتخاب‌شده. `priceScale` نسبتِ آخرین کندلِ نمایشی به کندلِ اسکن است
 * (برای Heikin-Ashi)؛ خودِ نشانگرها از high/low سریِ نمایشی می‌آیند.
 */
export function buildCandleEdgeOverlays(
  events: readonly PatternEvent[],
  bars: readonly CandleEdgeBar[],
  selectedKey: string | null,
  priceScale = 1,
): CandleEdgeOverlaySpec[] {
  const specs: CandleEdgeOverlaySpec[] = [];
  for (const event of events) {
    if (event.status !== 'confirmed') continue;
    const bar = bars[event.confirmedAtIndex];
    if (!bar) continue;
    const bullish = event.bias !== 'bearish';
    const glyph = bullish ? CANDLEEDGE_GLYPHS.bullish : CANDLEEDGE_GLYPHS.bearish;
    const span = Math.max(bar.high - bar.low, Math.abs(bar.close) * 0.001, 1);
    const value = bullish ? bar.low - span * 0.35 : bar.high + span * 0.35;
    const timestamp = overlayTimestamp(bar.timestamp);
    if (!Number.isFinite(timestamp) || !Number.isFinite(value) || value <= 0) continue;

    const selected = selectedKey != null && event.key === selectedKey;
    specs.push({
      name: 'simpleAnnotation',
      groupId: CANDLEEDGE_OVERLAY_GROUP,
      lock: true,
      points: [{ timestamp, value }],
      extendData: selected ? `${glyph} ${candleEdgeLabel(event.detector)}` : glyph,
      styles: {
        text: {
          color: bullish ? OVERLAY_COLORS.bullish : OVERLAY_COLORS.bearish,
          size: selected ? 10 : 9,
        },
      },
      meta: { eventKey: event.key, kind: 'marker' },
    });

    if (!selected) continue;

    if (event.level != null && Number.isFinite(event.level) && event.level > 0) {
      const levelAnchor = event.anchors.find((anchor) => anchor.role === 'high' || anchor.role === 'low');
      const levelTs = levelAnchor ? overlayTimestamp(levelAnchor.time) : Number.NaN;
      const breakTs = overlayTimestamp(event.confirmedAt);
      if (Number.isFinite(levelTs) && Number.isFinite(breakTs)) {
        const start = Math.min(levelTs, breakTs);
        const end = Math.max(levelTs, breakTs);
        specs.push({
          name: 'segment',
          groupId: CANDLEEDGE_OVERLAY_GROUP,
          lock: true,
          points: [
            { timestamp: start, value: event.level * priceScale },
            { timestamp: end, value: event.level * priceScale },
          ],
          // رنگِ متمایز از لایه‌های FTS تا سطحِ انتخاب‌شده گم نشود.
          styles: { line: { color: '#f0b90b', size: 2, style: 'dashed' } },
          meta: { eventKey: event.key, kind: 'level' },
        });
        specs.push({
          name: 'simpleAnnotation',
          groupId: CANDLEEDGE_OVERLAY_GROUP,
          lock: true,
          points: [{ timestamp: breakTs, value: event.level * priceScale }],
          extendData: `سطح ${fmtInt(event.level)}`,
          styles: { text: { color: '#f0b90b', size: 10 } },
          meta: { eventKey: event.key, kind: 'level' },
        });
      }
    }

    if (event.detector === 'double_top' || event.detector === 'double_bottom') {
      const [first, second] = event.anchors;
      const firstTs = first ? overlayTimestamp(first.time) : Number.NaN;
      const secondTs = second ? overlayTimestamp(second.time) : Number.NaN;
      if (
        Number.isFinite(firstTs) &&
        Number.isFinite(secondTs) &&
        Number.isFinite(first.price * priceScale) &&
        Number.isFinite(second.price * priceScale)
      ) {
        specs.push({
          name: 'segment',
          groupId: CANDLEEDGE_OVERLAY_GROUP,
          lock: true,
          points: [
            { timestamp: firstTs, value: first.price * priceScale },
            { timestamp: secondTs, value: second.price * priceScale },
          ],
          styles: {
            line: {
              color: bullish ? OVERLAY_COLORS.bullish : OVERLAY_COLORS.bearish,
              size: 2,
              style: 'solid',
            },
          },
          meta: { eventKey: event.key, kind: 'pivot-link' },
        });
      }
    }
  }
  return specs;
}
