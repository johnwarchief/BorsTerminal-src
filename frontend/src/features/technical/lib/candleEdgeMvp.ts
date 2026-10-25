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
import type { RegisterOverlayDef } from '../../../vendor/klinecharts';
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

export type CandleEdgeFamily = 'engulfing' | 'bos' | 'sweep' | 'double';

export const CANDLEEDGE_FAMILIES = ['engulfing', 'bos', 'sweep', 'double'] as const;

export const CANDLEEDGE_FAMILY_LABELS: Record<CandleEdgeFamily, string> = {
  engulfing: 'پوشا',
  bos: 'BOS',
  sweep: 'جارو',
  double: 'دوقلو',
};

export const CANDLEEDGE_FAMILY_TITLES: Record<CandleEdgeFamily, string> = {
  engulfing: 'الگوهای کندلی',
  bos: 'شکست ساختار',
  sweep: 'جاروی نقدینگی',
  double: 'سقف و کف دوقلو',
};

/** خانوادهٔ نمایشی از روی detector؛ تعریف الگوریتم دست‌نخورده است. */
export function candleEdgeFamilyOf(detector: DetectorId | string): CandleEdgeFamily {
  if (detector === 'bullish_engulfing' || detector === 'bearish_engulfing') return 'engulfing';
  if (detector === 'bos_bullish' || detector === 'bos_bearish') return 'bos';
  if (detector === 'double_top' || detector === 'double_bottom') return 'double';
  return 'sweep';
}

export type CandleEdgeFamilyFilter = Record<CandleEdgeFamily, boolean>;

export const CANDLEEDGE_ALL_FAMILIES: CandleEdgeFamilyFilter = {
  engulfing: true,
  bos: true,
  sweep: true,
  double: true,
};

export function filterCandleEdgeByFamily(
  events: readonly PatternEvent[],
  families: CandleEdgeFamilyFilter,
): PatternEvent[] {
  return events.filter((event) => families[candleEdgeFamilyOf(event.detector)]);
}

export function candleEdgeFamilyCounts(
  events: readonly PatternEvent[],
): Record<CandleEdgeFamily, number> {
  const counts: Record<CandleEdgeFamily, number> = {
    engulfing: 0,
    bos: 0,
    sweep: 0,
    double: 0,
  };
  for (const event of events) counts[candleEdgeFamilyOf(event.detector)] += 1;
  return counts;
}

/** بازهٔ کندلیِ دیدِ چارت؛ همان اندیس‌های getVisibleRange. */
export interface CandleEdgeViewport {
  from: number;
  to: number;
}

/** هندسهٔ رویداد با دید تلاقی دارد؟ لنگرِ دورِ چپ هم حساب می‌شود تا خط سطحِ BOS قطع نشود. */
export function eventIntersectsViewport(
  event: PatternEvent,
  viewport: CandleEdgeViewport,
  padding = 2,
): boolean {
  if (!Number.isFinite(viewport.from) || !Number.isFinite(viewport.to)) return false;
  const indices = [event.confirmedAtIndex, ...event.anchors.map((anchor) => anchor.index)];
  const start = Math.min(...indices);
  const end = Math.max(...indices);
  return end >= viewport.from - padding && start <= viewport.to + padding;
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

/** سقفِ نشانگرهای چارت در هر نمای دید؛ نه سقفِ فهرست. */
export const CANDLEEDGE_VISIBLE_MARK_LIMIT = 10;
export const CANDLEEDGE_CHART_NOTE =
  `روی چارت فقط رویدادهای محدودهٔ دید (حداکثر ${toFaDigits(String(CANDLEEDGE_VISIBLE_MARK_LIMIT))}) ` +
  'به ترتیب ساختار رسم می‌شوند؛ فهرست کامل در همین پنل است.';

/** فالبکِ بدون‌دید: یک نماینده از هر گروهِ پیشرو (برای آماده‌نبودن viewport). */
export const CANDLEEDGE_CHART_GROUP_LIMIT = 30;

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

/**
 * رویدادهای قابل‌رسم در دید: از هر گروهِ دیده‌شده یک نمایندهٔ تازه، به ترتیب
 * سالینس، تا سقفِ خوانایی. رویداد انتخاب/هاور همیشه می‌ماند تا هایلایت گم نشود.
 */
export function selectCandleEdgeViewportEvents(
  groups: readonly CandleEdgeGroupView[],
  viewport: CandleEdgeViewport,
  selectedKey: string | null,
  hoveredKey: string | null = null,
  limit = CANDLEEDGE_VISIBLE_MARK_LIMIT,
): PatternEvent[] {
  const chosen = new Map<string, PatternEvent>();
  if (viewport.to < viewport.from) return [];
  for (const group of groups) {
    const visible = group.events.filter((event) => eventIntersectsViewport(event, viewport));
    if (visible.length === 0) continue;
    const newest = [...visible].sort(
      (a, b) => b.confirmedAtIndex - a.confirmedAtIndex || a.key.localeCompare(b.key),
    )[0];
    chosen.set(newest.key, newest);
    if (chosen.size >= Math.max(1, limit)) break;
  }
  const all = groups.flatMap((group) => group.events);
  for (const key of [selectedKey, hoveredKey]) {
    if (key == null) continue;
    const event = all.find((candidate) => candidate.key === key);
    if (event) chosen.set(event.key, event);
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

export type CandleEdgeOverlayKind = 'pattern' | 'level' | 'pivot' | 'break' | 'tag';

export const CANDLEEDGE_OVERLAY_GROUP = 'candleedge_mvp';

/**
 * تگ و نشانهٔ شکست را خودمان ثبت می‌کنیم: `simpleAnnotation` داخلیِ klinecharts
 * متن را ۵۰px بالاتر با خط راهنما می‌کشد و استایلِ چیپ را نمی‌پذیرد. این دو
 * تمپلیت با همان registerOverlay موجود ثبت می‌شوند؛ وابستگی تازه‌ای نیست.
 */
export const CANDLEEDGE_TAG_OVERLAY = 'candleEdgeTag';
export const CANDLEEDGE_MARK_OVERLAY = 'candleEdgeMark';

export interface CandleEdgeTagData {
  text: string;
  color: string;
  background: string;
  place: 'above' | 'below';
}

export interface CandleEdgeMarkData {
  color: string;
  dir: 'up' | 'down';
}

export interface CandleEdgeOverlaySpec {
  name: 'segment' | 'rect' | typeof CANDLEEDGE_TAG_OVERLAY | typeof CANDLEEDGE_MARK_OVERLAY;
  groupId: string;
  lock: boolean;
  points: CandleEdgeOverlayPoint[];
  extendData?: CandleEdgeTagData | CandleEdgeMarkData;
  styles?: Record<string, unknown>;
  zLevel?: number;
  /** فرادادهٔ داخلیِ پنل/چارت؛ پیش از createOverlay حذف می‌شود. */
  meta: { eventKey: string; kind: CandleEdgeOverlayKind; family: CandleEdgeFamily };
}

/** ثبت idempotent؛ دوباره‌فراخوانی خطا نمی‌دهد و با تمپلیتِ FTS قاطی نمی‌شود. */
export function registerCandleEdgeOverlays(api: {
  registerOverlay: (overlay: RegisterOverlayDef) => void;
}): void {
  api.registerOverlay({
    name: CANDLEEDGE_MARK_OVERLAY,
    totalStep: 2,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: ({ coordinates, overlay }) => {
      const data = (overlay.extendData ?? {}) as Partial<CandleEdgeMarkData>;
      const point = coordinates[0];
      if (!point) return [];
      const up = data.dir !== 'down';
      const r = 4.5;
      const baseY = up ? point.y + r : point.y - r;
      const tipY = up ? point.y - r : point.y + r;
      return [
        {
          type: 'polygon',
          attrs: {
            coordinates: [
              { x: point.x - r, y: baseY },
              { x: point.x + r, y: baseY },
              { x: point.x, y: tipY },
            ],
          },
          styles: { style: 'fill', color: data.color, borderColor: data.color, borderSize: 1 },
          ignoreEvent: true,
        },
      ];
    },
  });

  api.registerOverlay({
    name: CANDLEEDGE_TAG_OVERLAY,
    totalStep: 2,
    needDefaultPointFigure: false,
    needDefaultXAxisFigure: false,
    needDefaultYAxisFigure: false,
    ignoreEvent: true,
    createPointFigures: ({ coordinates, overlay, bounding }) => {
      const data = (overlay.extendData ?? {}) as Partial<CandleEdgeTagData>;
      const point = coordinates[0];
      if (!point || !data.text) return [];
      const size = 10;
      const height = 17;
      const width = Math.ceil(data.text.length * 6.1) + 12;
      const x = Math.max(2, Math.min(bounding.width - width - 2, point.x - width / 2));
      const y = data.place === 'above' ? point.y - height - 4 : point.y + 4;
      return [
        {
          type: 'rect',
          attrs: { x, y, width, height },
          styles: {
            style: 'fill',
            color: data.background ?? CANDLEEDGE_COLORS.tagBg,
            borderColor: data.color,
            borderSize: 1,
            borderRadius: 3,
          },
          ignoreEvent: true,
        },
        {
          type: 'text',
          attrs: {
            x: x + width / 2,
            y: y + height / 2,
            text: data.text,
            align: 'center',
            baseline: 'middle',
          },
          styles: {
            color: CANDLEEDGE_COLORS.tagText,
            size,
            family: CHART_FONT,
            weight: '600',
            // تمِ چارت برای متنِ اورلی پس‌زمینهٔ آبی دارد؛ چیپِ خودمان تنها پس‌زمینه باشد.
            backgroundColor: 'transparent',
            borderColor: 'transparent',
            borderSize: 0,
            paddingLeft: 0,
            paddingRight: 0,
            paddingTop: 0,
            paddingBottom: 0,
          },
          ignoreEvent: true,
        },
      ];
    },
  });
}

/**
 * زبانِ بصریِ واحد: رنگ = جهت، شکل = خانواده، آبی = انتخاب.
 * سطح‌ها خنثی و خط‌چین‌اند تا با لایه‌های FTS قاطی نشوند؛ متن فقط برای
 * رویدادِ انتخاب/هاور می‌آید.
 */
export const CANDLEEDGE_COLORS = {
  bullish: '#2fd1a3',
  bearish: '#ff6b7a',
  structure: '#c4d0e2',
  selection: '#7cc4ff',
  tagText: '#e9f0f9',
  tagBg: 'rgba(8, 13, 22, 0.92)',
} as const;

const CHART_FONT = 'Vazirmatn, Tahoma, sans-serif';
const TICK_RATIO = 0.22;
const GEOMETRY_Z = 7;
const TAG_Z = 8;

function withAlpha(hex: string, alpha: number): string {
  const value = hex.replace('#', '');
  const n = Number.parseInt(value, 16);
  const r = (n >> 16) & 255;
  const g = (n >> 8) & 255;
  const b = n & 255;
  return `rgba(${r}, ${g}, ${b}, ${Math.max(0, Math.min(1, alpha))})`;
}

function directionColor(event: PatternEvent): string {
  return event.bias === 'bearish' ? CANDLEEDGE_COLORS.bearish : CANDLEEDGE_COLORS.bullish;
}

function barSpan(bar: CandleEdgeBar): number {
  return Math.max(bar.high - bar.low, Math.abs(bar.close) * 0.001, 1);
}

function overlayTimestamp(time: CandleTime): number {
  const ts = parseCandleTimestamp(time);
  return Number.isFinite(ts) && ts > 0 ? ts : Number.NaN;
}

function lineStyles(color: string, size: number, style: 'solid' | 'dashed' = 'solid') {
  return { line: { color, size, style } };
}

function tagText(event: PatternEvent): string {
  const up = event.bias === 'bullish';
  switch (candleEdgeFamilyOf(event.detector)) {
    case 'engulfing':
      return up ? 'پوشای ↑' : 'پوشای ↓';
    case 'bos':
      return up ? 'BOS ↗' : 'BOS ↘';
    case 'sweep':
      return up ? 'جارو ↑' : 'جارو ↓';
    case 'double':
      return event.detector === 'double_top' ? 'سقف دوقلو' : 'کف دوقلو';
  }
}

interface OverlayBuildContext {
  specs: CandleEdgeOverlaySpec[];
  event: PatternEvent;
  family: CandleEdgeFamily;
  selected: boolean;
  hovered: boolean;
  dimmed: boolean;
  priceScale: number;
  bars: readonly CandleEdgeBar[];
}

function pushOverlay(
  ctx: OverlayBuildContext,
  overlay: Omit<CandleEdgeOverlaySpec, 'groupId' | 'lock' | 'zLevel' | 'meta'>,
  kind: CandleEdgeOverlayKind,
  zLevel = GEOMETRY_Z,
): void {
  ctx.specs.push({
    ...overlay,
    groupId: CANDLEEDGE_OVERLAY_GROUP,
    lock: true,
    zLevel,
    meta: { eventKey: ctx.event.key, kind, family: ctx.family },
  });
}

function pushTag(
  ctx: OverlayBuildContext,
  timestamp: number,
  value: number,
  borderColor: string,
  place: 'above' | 'below',
): void {
  if (!Number.isFinite(timestamp) || !Number.isFinite(value) || value <= 0) return;
  pushOverlay(
    ctx,
    {
      name: CANDLEEDGE_TAG_OVERLAY,
      points: [{ timestamp, value }],
      extendData: {
        text: tagText(ctx.event),
        color: borderColor,
        background: CANDLEEDGE_COLORS.tagBg,
        place,
      },
    },
    'tag',
    TAG_Z,
  );
}

function buildEngulfing(ctx: OverlayBuildContext, bar: CandleEdgeBar): void {
  const { event, bars, dimmed, selected, hovered } = ctx;
  const prevAnchor = [...event.anchors]
    .filter((anchor) => anchor.index < event.confirmedAtIndex)
    .sort((a, b) => b.index - a.index)[0];
  const prevBar = prevAnchor ? bars[prevAnchor.index] : null;
  const first = prevBar ?? bar;
  const firstTs = overlayTimestamp(first.timestamp);
  const lastTs = overlayTimestamp(bar.timestamp);
  if (!Number.isFinite(firstTs) || !Number.isFinite(lastTs)) return;
  const color = directionColor(event);
  const alpha = dimmed ? 0.3 : 1;
  pushOverlay(
    ctx,
    {
      name: 'rect',
      points: [
        { timestamp: Math.min(firstTs, lastTs), value: Math.max(first.high, bar.high) },
        { timestamp: Math.max(firstTs, lastTs), value: Math.min(first.low, bar.low) },
      ],
      styles: {
        line: {
          color: withAlpha(color, (selected ? 0.95 : hovered ? 0.85 : 0.55) * alpha),
          size: selected ? 1.6 : 1,
          style: 'solid',
        },
        polygon: { color: withAlpha(color, (selected ? 0.1 : 0.05) * alpha) },
      },
    },
    'pattern',
  );

  if (!selected && !hovered) return;
  pushTag(
    ctx,
    overlayTimestamp(bar.timestamp),
    event.bias === 'bearish' ? bar.high : bar.low,
    selected ? CANDLEEDGE_COLORS.selection : color,
    event.bias === 'bearish' ? 'above' : 'below',
  );
}

function buildBos(ctx: OverlayBuildContext, bar: CandleEdgeBar): void {
  const { event, bars, priceScale, dimmed, selected, hovered } = ctx;
  const level = event.level;
  const pivot = event.anchors.find((anchor) => anchor.role === 'high' || anchor.role === 'low');
  const breakTs = overlayTimestamp(event.confirmedAt);
  if (level == null || !Number.isFinite(level) || level <= 0 || !pivot) return;
  const pivotTs = overlayTimestamp(pivot.time);
  if (!Number.isFinite(pivotTs) || !Number.isFinite(breakTs)) return;
  const color = directionColor(event);
  const alpha = dimmed ? 0.28 : 1;
  const levelColor = selected
    ? withAlpha(CANDLEEDGE_COLORS.selection, 0.95)
    : hovered
      ? withAlpha(color, 0.85)
      : withAlpha(CANDLEEDGE_COLORS.structure, 0.55 * alpha);
  const levelValue = level * priceScale;
  pushOverlay(
    ctx,
    {
      name: 'segment',
      points: [
        { timestamp: Math.min(pivotTs, breakTs), value: levelValue },
        { timestamp: Math.max(pivotTs, breakTs), value: levelValue },
      ],
      styles: lineStyles(levelColor, selected ? 1.8 : 1, 'dashed'),
    },
    'level',
  );

  const pivotBar = bars[pivot.index];
  const tick = Math.max((pivotBar ? barSpan(pivotBar) : Math.abs(level) * 0.004) * TICK_RATIO, 1);
  pushOverlay(
    ctx,
    {
      name: 'segment',
      points: [
        { timestamp: pivotTs, value: levelValue - tick },
        { timestamp: pivotTs, value: levelValue + tick },
      ],
      styles: lineStyles(withAlpha(color, (selected ? 0.95 : 0.8) * alpha), selected ? 2 : 1.4),
    },
    'pivot',
  );

  const span = barSpan(bar);
  const markY = event.bias === 'bullish' ? bar.high + span * 0.12 : bar.low - span * 0.12;
  const arrowTs = overlayTimestamp(bar.timestamp);
  if (!Number.isFinite(arrowTs) || !Number.isFinite(markY) || markY <= 0) return;
  pushOverlay(
    ctx,
    {
      name: CANDLEEDGE_MARK_OVERLAY,
      points: [{ timestamp: arrowTs, value: markY }],
      extendData: {
        color: withAlpha(color, (selected ? 1 : 0.9) * alpha),
        dir: event.bias === 'bullish' ? 'up' : 'down',
      },
    },
    'break',
  );

  if (!selected && !hovered) return;
  pushTag(
    ctx,
    overlayTimestamp(bar.timestamp),
    event.bias === 'bearish' ? bar.high : bar.low,
    selected ? CANDLEEDGE_COLORS.selection : color,
    event.bias === 'bearish' ? 'above' : 'below',
  );
}

function buildSweep(ctx: OverlayBuildContext, bar: CandleEdgeBar): void {
  const { event, priceScale, dimmed, selected, hovered } = ctx;
  const level = event.level;
  const pivot = event.anchors.find((anchor) => anchor.role === 'high' || anchor.role === 'low');
  const eventTs = overlayTimestamp(bar.timestamp);
  if (level == null || !Number.isFinite(level) || level <= 0 || !pivot) return;
  const pivotTs = overlayTimestamp(pivot.time);
  if (!Number.isFinite(pivotTs) || !Number.isFinite(eventTs)) return;
  const color = directionColor(event);
  const alpha = dimmed ? 0.28 : 1;
  const levelColor = selected
    ? withAlpha(CANDLEEDGE_COLORS.selection, 0.95)
    : hovered
      ? withAlpha(color, 0.85)
      : withAlpha(CANDLEEDGE_COLORS.structure, 0.55 * alpha);
  const levelValue = level * priceScale;
  pushOverlay(
    ctx,
    {
      name: 'segment',
      points: [
        { timestamp: Math.min(pivotTs, eventTs), value: levelValue },
        { timestamp: Math.max(pivotTs, eventTs), value: levelValue },
      ],
      styles: lineStyles(levelColor, selected ? 1.8 : 1, 'dashed'),
    },
    'level',
  );

  // سایهٔ عبور و برگشت روی همان کندلِ جارو؛ صرفاً یک آیکون عمومی نه.
  pushOverlay(
    ctx,
    {
      name: 'segment',
      points: [
        { timestamp: eventTs, value: event.detector === 'liquidity_sweep_high' ? bar.high : bar.low },
        { timestamp: eventTs, value: bar.close },
      ],
      styles: lineStyles(
        withAlpha(color, (selected ? 0.98 : 0.85) * alpha),
        selected ? 3 : 2.2,
      ),
    },
    'pattern',
  );

  if (!selected && !hovered) return;
  pushTag(
    ctx,
    eventTs,
    event.bias === 'bearish' ? bar.high : bar.low,
    selected ? CANDLEEDGE_COLORS.selection : color,
    event.bias === 'bearish' ? 'above' : 'below',
  );
}

function buildDouble(ctx: OverlayBuildContext, bar: CandleEdgeBar): void {
  const { event, bars, priceScale, dimmed, selected, hovered } = ctx;
  const [first, second] = event.anchors;
  if (!first || !second) return;
  const firstTs = overlayTimestamp(first.time);
  const secondTs = overlayTimestamp(second.time);
  if (!Number.isFinite(firstTs) || !Number.isFinite(secondTs)) return;
  const color = directionColor(event);
  const alpha = dimmed ? 0.28 : 1;
  const firstBar = bars[first.index];
  const secondBar = bars[second.index];
  const firstTick = Math.max((firstBar ? barSpan(firstBar) : first.price * 0.004) * TICK_RATIO, 1);
  const secondTick = Math.max((secondBar ? barSpan(secondBar) : second.price * 0.004) * TICK_RATIO, 1);

  for (const [anchor, ts, tick] of [
    [first, firstTs, firstTick],
    [second, secondTs, secondTick],
  ] as const) {
    pushOverlay(
      ctx,
      {
        name: 'segment',
        points: [
          { timestamp: ts, value: anchor.price * priceScale - tick },
          { timestamp: ts, value: anchor.price * priceScale + tick },
        ],
        styles: lineStyles(
          withAlpha(color, (selected ? 0.95 : 0.8) * alpha),
          selected ? 2 : 1.4,
        ),
      },
      'pivot',
    );
  }

  const connectorColor = selected
    ? withAlpha(CANDLEEDGE_COLORS.selection, 0.9)
    : hovered
      ? withAlpha(color, 0.8)
      : withAlpha(CANDLEEDGE_COLORS.structure, 0.45 * alpha);
  pushOverlay(
    ctx,
    {
      name: 'segment',
      points: [
        { timestamp: firstTs, value: first.price * priceScale },
        { timestamp: secondTs, value: second.price * priceScale },
      ],
      styles: lineStyles(connectorColor, selected ? 1.6 : 1, 'dashed'),
    },
    'pattern',
  );

  if (!selected && !hovered) return;
  const tagBar = secondBar ?? bar;
  pushTag(
    ctx,
    secondTs,
    event.bias === 'bearish' ? Math.max(tagBar.high, second.price) : Math.min(tagBar.low, second.price),
    selected ? CANDLEEDGE_COLORS.selection : color,
    event.bias === 'bearish' ? 'above' : 'below',
  );
}

/**
 * هندسهٔ هر خانواده از دادهٔ واقعی: کادر دو کندلِ پوشا، سطح+تیغهٔ پیوت+فلشِ شکست
 * برای BOS، سطح+سایهٔ برگشت برای جارو، دو پیوت+اتصال برای دوقلو. متن فقط برای
 * رویدادِ انتخاب/هاور؛ بقیه با رنگ و شکل خوانده می‌شوند.
 * `priceScale` نسبتِ آخرین کندلِ نمایشی به کندلِ اسکن است (Heikin-Ashi)؛
 * نشانگرها از high/low سریِ نمایشی می‌آیند.
 */
export function buildCandleEdgeOverlays(
  events: readonly PatternEvent[],
  bars: readonly CandleEdgeBar[],
  selectedKey: string | null,
  priceScale = 1,
  hoveredKey: string | null = null,
): CandleEdgeOverlaySpec[] {
  const specs: CandleEdgeOverlaySpec[] = [];
  for (const event of events) {
    if (event.status !== 'confirmed') continue;
    const bar = bars[event.confirmedAtIndex];
    if (!bar) continue;
    const family = candleEdgeFamilyOf(event.detector);
    const selected = selectedKey != null && event.key === selectedKey;
    const hovered = !selected && hoveredKey != null && event.key === hoveredKey;
    const dimmed = selectedKey != null && !selected;
    const ctx: OverlayBuildContext = {
      specs,
      event,
      family,
      selected,
      hovered,
      dimmed,
      priceScale,
      bars,
    };
    if (family === 'engulfing') buildEngulfing(ctx, bar);
    else if (family === 'bos') buildBos(ctx, bar);
    else if (family === 'sweep') buildSweep(ctx, bar);
    else buildDouble(ctx, bar);
  }
  return specs;
}
