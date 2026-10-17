// features/master/ui/FtsFunnelAllStages.tsx -- قیفِ مرحلۀ‌بدر‌مرحلۀ FTS درِ تبِ درخت استراتژی
//
// چهار مرحلۀ جزوه، بالابهپایین و *متحرک*: تابلوخوانی ← تکنیکال ← بنیادی ← تحویل.
// هر مرحلۀ جدولِ خودش را دارد و ردیف‌ها با FLIP از مرحلۀ بالا به پایین حرکت
// می‌کنند (shared/lib/useFlip.ts)، تا معلوم شود کدام نماد کجا کم شد.
//
// دو تصمیمی که عمداً این‌جا نشسته:
//   - تکنیکال غربال می‌کند: وتوی هفتگی یا نبودِ ستاپِ همان سبک، نماد را بیرون
//     می‌اندازد (ستون T درِ چارت). رأیِ هفتگی از ماتریسِ بک‌اند می‌آید، نه از
//     فرمولِ دومِ فرانت. بی‌داده وتو نیست: ردیفی که اسکرینر تحلیلش نکرده
//     «سنجیده نشد» می‌خورد و درِ قیف نمی‌سوزد.
//   - مرحلۀ «تحویل» پایِ قیف است، نه خریدِ خودکار: نمادها منتظرِ انتخابِ خودِ
//     مالک می‌مانند تا به سبد و مدیریتِ سرمایه برود (جزوه: selection ← سبدگردانی).
import { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useScreenFilterStore } from '@shared/stores/screenFilterStore';
import { QUICK_FILTERS, QUICK_LABELS, type QuickFilter } from '@features/market/stores/tapeStore';
import { MicroBadge, type MicroTone } from '@features/market/components/TapeTable';
import { absurdHint } from '@features/fundamental/lib/numFmt';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { SymbolWatchAction } from '@features/portfolio/components/SymbolWatchAction';
import SymbolSelectBox from '@shared/components/SymbolSelectBox';
import { useSelectedSymbolsStore } from '@shared/stores/selectedSymbolsStore';
import { useWatchlistAddMany } from '@shared/api/userWatchlist';
import { FormingCandle } from '@shared/components/FormingCandle';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { normalizeFa } from '@shared/lib/normalizeFa';
import { useFlip } from '@shared/lib/useFlip';
import { useVerdictChanges } from '../lib/funnelChangeTrack';
import { FunnelErrorBanner } from './FunnelErrorBanner';
import {
  MODE_HINT,
  MODE_LABEL,
  MODE_PATH,
  TAPE_FRESHNESS_LABEL,
  PRESET_ENTRY,
  STATUS_LABEL,
  STATUS_HINT,
  IND_COLUMNS,
  trendLabel,
  type FilterCount,
  type FunnelEntry,
  type FunnelStage,
  type FunnelStageKey,
  type Funnel,
  type FunnelOptions,
  type StageStatus,
  type TreePreset,
} from '../lib/ftsFunnel';
import { useFtsFunnel } from '../api/useFtsFunnel';
import {
  DEFAULT_FUND_FLOOR,
  FUND_FLOOR_MAX,
  TECH_SCREEN_HINT,
  TECH_SCREEN_LABEL,
  UNMEASURED_HINT,
  UNMEASURED_LABEL,
  useFunnelPrefsStore,
  type UnmeasuredPolicy,
} from '../stores/funnelPrefsStore';

const STAGE_TITLE: Record<FunnelStageKey, string> = {
  tape: 'تابلوخوانی',
  technical: 'تکنیکال',
  fundamental: 'بنیادی',
  handover: 'نمادهای عبوری',
};

const STAGE_RULE: Record<FunnelStageKey, string> = {
  tape: 'نمادهایی که از درِ فیلترهایِ روشنِ امروز عبور کرده‌اند — عینِ داوریِ چیپ و بجِ تبِّ تابلو. نمادهای عبورنکرده درِ جدول نمی‌نشینند؛ شمارشان درِ همین سرخط است.',
  technical: 'ابتدا روند هفتگی بررسی می‌شود؛ اگر نزولی یا خنثی باشد، نماد از این مسیر عبور نمی‌کند. سپس روند روزانه سنجیده می‌شود و شواهدی مانند جت، پولبک و فیبوناچی امتیاز می‌دهند — هر سه شاخۀ روزانۀ صعودی/نزولی/خنثی معتبرند و این شواهد گیت نیستند.',
  fundamental: '',
  handover: 'فقط نمادهایی به مرحلۀ تحویل می‌رسند که شرط بنیادی لازم را دارند و در ۱۴ روز آیندۀ کاری مجمع عمومی پیشِ رو ندارند. وجودِ مجمع به‌تنهایی به معنای ضعفِ بنیادی نیست و فقط زمانِ بررسیِ ورود را جابه‌جا می‌کند؛ نمره دست‌نخورده می‌ماند.',
};

/** شرحِ درِ بنیادی به دو پیچِ دستِ کاربر وصل است تا متنِ rule دروغِ پیش‌فرض نگوید. */
function fundRule(o: FunnelOptions): string {
  const un =
    o.unmeasured === 'hold'
      ? 'و بی‌گزارش در صفِ خودش می‌ماند'
      : o.unmeasured === 'pass'
        ? 'و بی‌گزارش با برچسبِ «سنجیده نشد» عبور می‌کند'
        : 'و بی‌گزارش از غربالگری حذف می‌شود';
  return `پنج شاخصِ کدال: ${toFaDigits(o.fundFloor)} از ${toFaDigits(FUND_FLOOR_MAX)} به بالا به تحویل می‌رود، ردِ صریح می‌افتد ${un}.`;
}

const ORDER: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

/** ارتفاعِ تقریبیِ یک سطرِ جدول — مبنایِ مجازی‌سازیِ بدنه (سلول‌ها `py-1` +
 *  متنِ ۱۲px؛ همان عددی که `TapeTable` برایِ سطرهایِ خودش اندازه گرفته است). */
const ROW_H = 29;

// ---- برگشتِ قیف (Round M §۹، باقی‌ماندۀ ۲): مرحلۀ فعال و scroll پیش از رفتن به
// Master در sessionStorage ثبت می‌شوند و پس از بازگشت یک‌بار بازخوانده می‌شوند.
// بی‌store سراسری؛ snapshot مصرف‌شده پاک می‌شود تا ورودِ تازه از صفر باشد.
export const FUNNEL_SNAP_KEY = 'bors.funnel.snapshot.v1';

type FunnelSnap = { stage: FunnelStageKey; scroll: number };

function readFunnelSnap(): FunnelSnap | null {
  try {
    const raw = sessionStorage.getItem(FUNNEL_SNAP_KEY);
    if (!raw) return null;
    const p = JSON.parse(raw) as Partial<FunnelSnap>;
    if (p.stage && ORDER.includes(p.stage as FunnelStageKey) && typeof p.scroll === 'number') {
      return { stage: p.stage as FunnelStageKey, scroll: p.scroll };
    }
  } catch {
    /* snapshot ناقص = بی snapshot */
  }
  return null;
}

function scrollTargets(): HTMLElement[] {
  // در این پوسته هر دو آرایش دیده شده: .app-content اسکرول‌کنندهٔ داخلی است،
  // ولی در عرض‌های بلندِ قیف خودِ سند می‌لغزد — پس هر دو نامزد می‌شوند.
  const out: HTMLElement[] = [];
  const inner = document.querySelector('.app-content');
  if (inner) out.push(inner as HTMLElement);
  const doc = (document.scrollingElement ?? document.documentElement) as HTMLElement | null;
  if (doc && !out.includes(doc)) out.push(doc);
  return out;
}

function readAppScroll(): number {
  return Math.max(0, ...scrollTargets().map((t) => t.scrollTop));
}

function applyAppScroll(v: number): boolean {
  let done = false;
  for (const t of scrollTargets()) {
    if (t.scrollHeight - t.clientHeight >= v) {
      t.scrollTop = v;
      done = true;
    }
  }
  return done;
}

/**
 * دربِ قیف = همان افقی که درِ «درخت استراتژی» و داوریِ نماد انتخاب می‌شود.
 * کلیدِ انتخابِ سیستم از این جدول بیرون رفته و درِ سرخطِ همان workspace نشسته
 * است (`FtsFunnelStages` → FUNNEL_MODES): یک انتخابگر، نه دو تا. این فایل دیگر
 * preset را عوض نمی‌کند، فقط همان را می‌خواند و جدولش را می‌سازد.
 */

const MARK_DOT: Record<StageStatus, string> = {
  pass: 'bg-accent-green',
  reject: 'bg-accent-red',
  pending: 'bg-accent-yellow',
  unavailable: 'bg-border-c',
  not_required: 'bg-border-c/40',
  not_in_universe: 'bg-bg-secondary',
  not_applicable: 'bg-border-c/30',
};
/** واژگانِ داوری از خودِ مدلِ canonical می‌آید — دو نسخهٔ برچسب نداریم. */
const MARK_LABEL = STATUS_LABEL;

/**
 * ستون‌هایِ هر مرحله — «هر بخش باید ستونِ مربوط به خودش را داشته باشد».
 * تا پیش از این چهار جدول یک سرستون مشترک داشتند (نماد/آخرین/تغییر٪/حجم-ماه/
 * نشانه/بنیادی)، پس مرحلۀ تکنیکال هیچ چیز از روندِ هفتگی نمی‌گفت و مرحلۀ
 * بنیادی فقط جمعِ پنج شاخص را. اینجا هر مرحله ستون‌هایِ همان سطرِ چارت را
 * می‌خواند: T (صفحه ۲) برای تکنیکال، F (صفحه ۱) برای بنیادی.
 */
type ColKey =
  | 'symbol' | 'last' | 'chg' | 'vol' | 'pattern'
  | 'weekly' | 'daily' | 'branch' | 'setup' | 'techPoints' | 'mark'
  | 'ind1' | 'ind2' | 'ind3' | 'ind4' | 'ind5' | 'score' | 'why' | 'basket'
  | 'watch' | 'candle';

const COL: Record<ColKey, { label: string; title: string; end?: boolean }> = {
  symbol: { label: 'نماد', title: 'کلیک = انتخابِ نماد' },
  last: { label: 'آخرین', title: 'قیمت آخرین معامله', end: true },
  chg: { label: 'تغییر٪', title: 'تغییر درصدی امروز', end: true },
  vol: { label: 'حجم/ماه', title: 'حجم امروز ÷ میانگین ماهانه', end: true },
  pattern: { label: 'نشانه', title: 'الگوهای تابلوخوانی که این نماد امروز دارد — همان برچسب و رنگِ تبِّ تابلو' },
  weekly: { label: 'هفتگی', title: 'روند هفتگی — چارت ۲: نزولی و خنثی = reject', end: true },
  daily: { label: 'روزانه', title: 'روند روزانه — شاخه بعدی بر اساس این روند تعیین می‌شود', end: true },
  branch: { label: 'شاخه', title: 'شاخه FTS بر اساس روند روزانه' },
  setup: { label: 'شواهد', title: 'ستاپ‌های فعال؛ فقط شواهد کمکی و نه گیت عبور' },
  techPoints: { label: 'امتیاز', title: 'امتیاز کمکی Ranking؛ روند هفتگی/روزانه اصل است و ستاپ‌ها فقط تا ۲ امتیاز کمکی دارند', end: true },
  mark: { label: 'داوری', title: 'حکم این مرحله بر اساس روند هفتگی سپس روزانه', end: true },
  ind1: { label: IND_COLUMNS[0].label, title: IND_COLUMNS[0].full, end: true },
  ind2: { label: IND_COLUMNS[1].label, title: IND_COLUMNS[1].full, end: true },
  ind3: { label: IND_COLUMNS[2].label, title: IND_COLUMNS[2].full, end: true },
  ind4: { label: IND_COLUMNS[3].label, title: IND_COLUMNS[3].full, end: true },
  ind5: { label: IND_COLUMNS[4].label, title: IND_COLUMNS[4].full, end: true },
  score: { label: 'بنیادی', title: 'جمع پنج شاخص', end: true },
  // حکمِ بی‌دلیل نگه ندارید: همین «دلیل» را پیشِ این فقط `title`ِ ردیف می‌داد و
  // برای دیدنش باید نشانگر را نگه می‌داشتید (رویِ لمسی اصلاً دیده نمی‌شد).
  why: { label: 'دلیل', title: 'دلیلِ همین حکم — همان متنی که موتورِ غربالگری ساخته' },
  // همان ویجتِ ستونِ «کندل روز» درِ تبِّ تابلو (`FormingCandle`)، نه نمودارِ
  // تازه: رأیِ مالک ۱۴۰۵-۰۷-۲۲ «جاهایی که می‌طلبد نمودار هم باشد» — جدولِ
  // غربالگری تنها جایِ برنامه بود که همین ردیف‌ها را بی‌شکلِ نشست می‌نمود.
  // بی‌OHLC همان «—»ِ خودِ ویجت می‌آید؛ کندلِ ساختگی ساخته نمی‌شود.
  candle: { label: 'کندل روز', title: 'اولین، بیشترین، کمترین و آخرینِ همین روز معاملاتی — عینِ تبِّ تابلو' },
  basket: { label: 'سبد', title: 'افزودن به سبد', end: true },
  // رأیِ مالک: رسیدۀ «تحویل» باید راهِ رفتن به «دیده‌بان» را هم داشته باشد —
  // رصد، نه تصمیمِ سرمایه‌ای.
  watch: { label: 'دیده‌بان', title: 'افزودن به تبِّ اصلیِ دیده‌بان بازار', end: true },
};

/** رنگِ هر نشانه، همان تقسیمِ تبِّ تابلو (`tapeBadges.patternBadges`):
 *  ساعت/violet، طلایی و حجم مشکوک و نقطه/amber، جت و پول هوشمند/cyan،
 *  کف‌روب/emerald، صف+/green، صف−/red. */
const PATTERN_TONE: Record<string, MicroTone> = {
  'ساعت': 'violet',
  'طلایی': 'amber',
  'مشکوک': 'amber',
  'حجم مشکوک': 'amber',
  'جت': 'cyan',
  'پول هوشمند': 'cyan',
  'کفروب': 'emerald',
  'کف‌روب': 'emerald',
  'نقطه': 'amber',
  'نقطه‌زنی': 'amber',
  'کد به کد': 'violet',
  'صف+': 'green',
  'صف−': 'red',
};

const STAGE_COLS: Record<FunnelStageKey, ColKey[]> = {
  tape: ['symbol', 'last', 'chg', 'vol', 'candle', 'pattern', 'why'],
  technical: ['symbol', 'weekly', 'daily', 'branch', 'setup', 'techPoints', 'mark', 'why'],
  fundamental: ['symbol', 'ind1', 'ind2', 'ind3', 'ind4', 'ind5', 'score', 'why'],
  // گامِ تحویل دو ستونِ روندِ روزانه و شاخه را کم داشت، در حالی که همان داده
  // درِ پاسخِ سرور هست (`daily`/`branch`) و درِ گامِ تکنیکال هم نشان داده می‌شود؛
  // خوانندۀ «تحویل» باید بدود سهم با کدام شاخه به این گام رسیده، نه فقط اینکه
  // هفتگی صعودی بوده. واژۀ تازه‌ای اضافه نشد: سرستون‌ها همان تعریف‌هایِ موجودند.
  handover: ['symbol', 'weekly', 'daily', 'branch', 'candle', 'score', 'why', 'watch', 'basket'],
};

/**
 * پهنایِ هر ستون (درصد) — با `table-layout: fixed`.
 *
 * چرا دستی: با چیدمانِ خودکار، مرورگر فضایِ اضافی را به سرستونِ بلندِ «رشد فروش»
 * می‌دهد (۵۲۷px) ولی سلولِ همان ستون ۵۲px می‌ماند؛ نتیجه‌اش این بود که
 * سرستون تا ۸۸۲ پیکسل از مقدارِ خودش جدا می‌افتاد و پنج شاخصِ بنیادی زیرِ
 * سرستونِ اشتباه می‌نشستند. جدولِ «در انتظارِ گزارش» هم جدولِ دومی است، پس
 * همان colgroup را می‌گیرد — وگرنه دو سرستونِ ناهم‌راستا رویِ هم می‌آیند.
 * ارقام نسبی‌اند: ColGroup آن‌ها را به ۱۰۰٪ نرمال می‌کند، پس هر مرحله لازم نیست
 * جمعش دقیقاً صد شود (و افزودنِ ستونِ تازه جمع را نمی‌شکند).
 */
const COL_W: Record<ColKey, number> = {
  symbol: 16, last: 11, chg: 10, vol: 9, pattern: 20,
  // فقط «شواهد» و دو ستونِ کوتاه عوض شدند (سنجشِ زنده ws10): با برچسبِ فارسی
  // ۱۶۸ پیکسل می‌خواست و ۱۵۰ می‌گرفت؛ «امتیاز» و «علامت» کوتاه‌ترین ستون‌های
  // همین جدول‌اند. «دلیل» عمداً دست‌نخورده است — متن‌های ۳۳۵ و ۸۳۶ پیکسلی با
  // هیچ تقسیمی رویِ یک خط جا نمی‌شوند و شکلشان رأیِ مالک را می‌خواهد.
  weekly: 11, daily: 11, branch: 19, setup: 17, techPoints: 6, mark: 11,
  ind1: 12, ind2: 12, ind3: 12, ind4: 12, ind5: 12, score: 9, basket: 18, watch: 12,
  why: 22, candle: 5,
};

function ColGroup({ cols }: { cols: ColKey[] }) {
  const sum = cols.reduce((a, k) => a + COL_W[k], 0) || 1;
  return (
    <colgroup>
      {cols.map((k) => (
        <col key={k} style={{ width: `${((COL_W[k] / sum) * 100).toFixed(3)}%` }} />
      ))}
    </colgroup>
  );
}

const TREND_COLOR: Record<string, string> = {
  up: 'text-accent-green',
  down: 'text-accent-red',
  range: 'text-accent-yellow',
  na: 'text-text-muted',
};

/** سلولِ «ردیفِ پنج‌شاخصه»: ✓ / ✗ / — با عددِ خودش، نه فقط رنگ.
 *  عددِ غیرمعقول همان نشانِ جدولِ غربالگری را می‌گیرد (نه حذفِ عدد). */
function IndCell({ mark, value, hint }: { mark: StageStatus; value: string | null; hint?: string | null }) {
  const glyph = mark === 'pass' ? '✓' : mark === 'reject' ? '✗' : mark === 'pending' ? '…'
    : mark === 'not_required' ? '·' : '—';
  const cls =
    mark === 'pass' ? 'text-accent-green' : mark === 'reject' ? 'text-accent-red' : 'text-text-muted';
  return (
    <td className={`truncate px-2 py-1 text-end ${cls}`} title={hint ?? MARK_LABEL[mark]}>
      {value ? <span className="ms-1 opacity-70">{value}</span> : null}
      {hint ? <span className="text-accent-yellow">⚠</span> : null}
      <span className="font-black">{glyph}</span>
    </td>
  );
}

function TrendCell({ t }: { t: string | null }) {
  const key = t ?? 'na';
  return (
    <td className={`truncate px-2 py-1 text-end font-bold ${TREND_COLOR[key] ?? 'text-text-muted'}`}>
      {trendLabel(t)}
    </td>
  );
}

/** نرخ‌گذاری به زبانِ خودِ جدول: بک‌اند 'free' / 'mandatory' / 'neutral' را می‌دهد
 *  و واژۀ خامِ موتور نباید در ستونِ فارسی بنشیند (۴۰۴ شرکت از ۸۷۳ neutral‌اند). */
function pricingLabel(mode: string | null | undefined): string | null {
  const m = (mode ?? '').trim().toLowerCase();
  if (m === 'free' || m === 'آزاد') return 'آزاد';
  if (m === 'mandatory' || m === 'regulated' || m === 'دستوری') return 'دستوری';
  if (m === 'neutral') return 'سایر صنایع';
  return null;
}

function Cell({ k, e, mark, why }: { k: ColKey; e: FunnelEntry; mark: StageStatus | null; why: string | null }) {
  const r = e.row;
  switch (k) {
    case 'last':
      return <td className="truncate px-2 py-1 text-end text-text-secondary"><span className="num">{r?.p_last != null ? fmtInt(r.p_last) : '—'}</span></td>;
    case 'chg':
      return (
        <td className={`truncate px-2 py-1 text-end ${
          (r?.percent_change ?? 0) > 0 ? 'text-accent-green' : (r?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
        }`}>
          <span className="num">{r?.percent_change != null ? fmtPct(r.percent_change) : '—'}</span>
        </td>
      );
    case 'vol':
      return <td className="truncate px-2 py-1 text-end text-text-secondary"><span className="num">{r?.vol_ratio != null ? `${toFaDigits(r.vol_ratio.toFixed(1))}×` : '—'}</span></td>;
    case 'pattern': {
      // همان برچسب‌هایِ تبِّ تابلو، همان رنگ‌ها (رأیِ مالک ۱۴۰۵-۰۷-۱۹): متنِ
      // «ساعت + مشکوک» بج‌شمار نبود؛ اینجا هر نشانه یک pillِ جداست. نبودنشان
      // «بی‌نشانه» است نه «تأیید».
      return (
        <td className="px-2 py-1 text-start">
          <span data-testid={`funnel-patterns-${e.symbol}`} className="flex min-w-0 flex-wrap items-center gap-0.5">
            {e.patterns.length
              ? e.patterns.map((p) => (
                  <MicroBadge key={p} pattern={p} tone={PATTERN_TONE[p] ?? 'gray'} title={`نشانهٔ تابلو: ${p}`}>
                    {p}
                  </MicroBadge>
                ))
              : <span className="text-2xs text-text-muted">بی‌نشانه</span>}
          </span>
        </td>
      );
    }
    case 'candle':
      // همان ویجتِ تبِّ تابلو، با همان تستیدِ قابلِ ردیابی؛ بی‌OHLC «—» می‌ماند
      return (
        <td className="px-2 py-1 text-center">
          <FormingCandle candle={r ?? null} testId={`funnel-candle-${e.symbol}`} />
        </td>
      );
    case 'weekly':
      return <TrendCell t={e.trendW} />;
    case 'daily':
      return <TrendCell t={e.trendD} />;
    case 'branch':
      return <td className="truncate px-2 py-1 text-start text-2xs text-text-secondary">{e.dailyStrategy || '—'}</td>;
    case 'setup':
      return <td className="truncate px-2 py-1 text-start text-2xs text-text-secondary">{e.setups || '—'}</td>;
    case 'techPoints':
      return <td className="px-2 py-1 text-end text-2xs font-bold text-text-primary"><span className="num">{e.technicalPoints != null ? toFaDigits(e.technicalPoints) : '—'}</span></td>;
    case 'mark':
      return <td className="truncate px-2 py-1 text-end text-2xs font-bold" title={why ?? undefined}>{mark ? MARK_LABEL[mark] : '—'}</td>;
    case 'ind1':
    case 'ind2':
    case 'ind3':
    case 'ind4':
    case 'ind5': {
      const i = Number(k.slice(3)) - 1;
      const sc = e.screen;
      // عددِ هر شاخص کنارِ علامتش می‌آید (نه فقط ✓/✗)، و با جداکنندهٔ هزارگان:
      // رشد فروشِ بعضی نمادها میلیاردی است و بی‌جداکننده خوانده نمی‌شد.
      const raw = [
        sc?.rev_growth != null ? `${fmtInt(sc.rev_growth)}٪` : null,
        sc?.eps_last != null ? fmtInt(sc.eps_last) : null,
        sc?.gross_margin != null ? `${fmtInt(sc.gross_margin)}٪` : null,
        sc?.sales_to_mcap != null ? toFaDigits(sc.sales_to_mcap.toFixed(2)) : null,
        pricingLabel(sc?.pricing_mode),
      ][i];
      // دو ستون درصدیِ جزوه (رشد فروش، حاشیهٔ ناخالص): عددِ غیرمعقول حذف
      // نمی‌شود، همان هشدارِ جدولِ غربالگری رویش می‌نشیند.
      const hint = [absurdHint(sc?.rev_growth), null, absurdHint(sc?.gross_margin), null, null][i];
      return <IndCell mark={e.inds[i] ?? 'pending'} value={raw} hint={hint} />;
    }
    case 'score':
      return <td className="px-2 py-1 text-end font-bold text-text-primary"><span className="num">{e.score != null ? `${toFaDigits(e.score)}/۵` : '—'}</span></td>;
    case 'why':
      return (
        <td className="truncate px-2 py-1 text-start text-2xs text-text-secondary" title={why ?? undefined}
            data-testid={`funnel-why-${e.symbol}`}>
          {why || (mark ? MARK_LABEL[mark] : '—')}
        </td>
      );
    case 'basket':
      return <td className="px-2 py-1 text-end"><SymbolBasketAction symbol={e.symbol} /></td>;
    case 'watch':
      return <td className="px-2 py-1 text-end"><SymbolWatchAction symbol={e.symbol} /></td>;
    default:
      return null;
  }
}

/** ترتیبِ نمایشِ ردیف‌ها درِ هر گام: عبوری‌ها رو‌به‌رو، و درِ میانشان آنچه همین
 *  حالا معامله دارد بالاتر. داوری و شمارشِ موتور دست‌نخورده‌اند — همین ردیف‌ها،
 *  همین حکم‌ها؛ فقط جابه‌جا می‌شوند.
 *
 *  چرا لازم شد (باگِ P0): هر چهار گام «کلِ جامعۀ غربالگری» را با ترتیبِ ثابتِ
 *  خودِ تابلو می‌داد، پس کلیک رویِ Preset هیچ چیزِ دیدنی را درِ جدول عوض نمی‌کرد
 *  و شمارۀِ سرِ گام («حکم: ۲۸۱۳ = کلِ جامعۀ غربالگری») برایِ همهٔ presetها یکی
 *  می‌ماند. سنجشِ زندهٔ ۱۴۰۵-۰۷-۱۸ همین را نشان داد ( عبورِ تابلو: نوسان‌گیر ۱،
 *  روندگیر ۰، ساعت‌شنی ۲۷۹۸ — و جدول بی‌تغییر).
 */
const VERDICT_RANK: Record<StageStatus, number> = {
  pass: 0, pending: 1, unavailable: 2, reject: 3, not_required: 4, not_in_universe: 5,
  not_applicable: 6,
};

export function orderStageRows(key: FunnelStageKey, entries: FunnelEntry[]): FunnelEntry[] {
  const keyed = entries.map((c, i) => ({
    c, i,
    v: VERDICT_RANK[c.status?.[key]] ?? 9,
    p: c.universePriority ?? 9,
  }));
  keyed.sort((a, b) => (a.v - b.v) || (a.p - b.p) || (a.i - b.i));
  return keyed.map((k) => k.c);
}

/** یک مرحلۀ قیف: سرشماره + نوارِ کاهش + جدولِ ردیف‌ها با FLIP
 *
 *  جدولِ هر مرحله **کلِ جامعۀ ورودی** است، نه فقط رسیدگان: قاعدۀ مالک این است
 *  که هیچ نمادی «بی‌حکم» از قیف بیرون نیفتد، پس نمادی که تابلو ردش کرده درِ
 *  مرحلۀ تکنیکال هم دیده می‌شود و حکمش `not_required` است با دلیلِ گامِ
 *  بازدارنده. بی‌این، نبودنِ یک نماد از جدولِ دوم خوانده می‌شد به «سنجیده
 *  نشد». پنج‌هزار ردیفِ DOM رویِ هم اسکرول را می‌خواباند، پس بدنه مجازی‌سازی
 *  شده است (`@tanstack/react-virtual`) — همان کاری که جدولِ تابلو می‌کند؛
 *  virtualization نمایش است، حذف نه: شمارشِ سرِ جدول همیشه کلِ ردیف‌ها را
 *  می‌گوید. */
function StageCard({
  stage,
  index,
  wide,
  showMark,
  onPick,
  active,
  opts,
  emptyWhy,
  collapsed = false,
  onToggle,
}: {
  stage: FunnelStage;
  index: number;
  wide: number;
  showMark: 'tech' | 'fund' | 'handover' | null;
  onPick: (s: string) => void;
  active: boolean;
  opts: FunnelOptions;
  emptyWhy: string | null;
  /** سه مرحلۀ اول با پیش‌فرضِ بسته (رأیِ مالک ۱۴۰۵-۰۷-۲۲) */
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  // رأیِ مالک ۱۴۰۵-۰۷-۱۹: «جدول‌های استراتژی FTS فقط باید نمادهایی که پاس میشن
  // رو نشون بدن». حکمِ رد/بی‌داده/لازم‌نبود هیچ‌جا پاک نمی‌شود — درِ شمارش‌های
  // همین کارت، درِ خطِ «چرا» و درِ بازرسیِ نماد می‌ماند؛ فقط بدنهٔ جدول محلِ
  // ردیف‌هایِ مردود نیست.
  const passedRows = useMemo(() => stage.entries.filter((e) => e.status[stage.key] === 'pass'),
                             [stage]);
  // ترتیبِ نمایش (عبور_then_زنده) — خروجیِ موتور، فقط رو‌به‌رو شده.
  const rows = useMemo(() => orderStageRows(stage.key, passedRows),
                       [stage.key, passedRows]);
  useFlip({ root: bodyRef, deps: [rows.map((r) => r.symbol).join(' ')] });
  // نوارِ کاهش = سهمِ عبوری‌هایِ همین گام از کلِ جامعۀ ورودی. پیش‌تر عرضش
  // «ردیفِ این مرحله ÷ پهن‌ترین مرحله» بود؛ وقتی هر چهار مرحله کلِ universe را
  // می‌شمارند آن کسر همیشه ~۱ می‌شد و قیف دیگر شکلِ قیف نداشت.
  const passed = stage.summary.pass;
  const pct = wide > 0 ? Math.round((passed / wide) * 100) : 0;
  const cols = STAGE_COLS[stage.key];
  const techScreens = useFunnelPrefsStore((s) => s.techScreens);
  const setTechScreens = useFunnelPrefsStore((s) => s.setTechScreens);
  const rule = stage.key === 'fundamental' ? fundRule(opts) : STAGE_RULE[stage.key];

  // «چه چیزی همین حالا عوض شد»: ردیف‌هایِ داورى‌تازه و جابه‌جاییِ شمارِ گام.
  // هیچ عددِ تازه‌ای ساخته نمی‌شود — فقط دورۀ پیشین با این دور مقایسه می‌شود.
  const { changed, delta } = useVerdictChanges(stage.key, rows,
                                               { passed, ruled: stage.ruled });
  // قوسِ اسکرولِ همین کارت همان بدنه است (bodyRef). پیش‌تر مجازی‌ساز refِ دومی
  // می‌خواست که هرگز به DOM وصل نمی‌شد، پس هیچ اسکرولی نمی‌دید و فقط پنجرۀ
  // initialRect را می‌ساخت: رویِ ۹۰۶ ردیفِ تابلو ۲۳ ردیف درِ DOM می‌ماند و
  // اسکرول تا انتها هیچ ردیفِ تازه‌ای اضافه نمی‌کرد (اثبات:
  // tools/funnel_scroll_probe.mts). یک عنصر، یک ref.
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => bodyRef.current,
    estimateSize: () => ROW_H,
    overscan: 8,
    initialRect: { width: 0, height: 380 },
  });
  const vRows = virt.getVirtualItems();
  const padTop = vRows.length ? vRows[0].start : 0;
  const padBottom = vRows.length
    ? Math.max(0, virt.getTotalSize() - (vRows[vRows.length - 1].start + ROW_H))
    : 0;
  const pendingRef = useRef<HTMLDivElement | null>(null);
  const pendingVirt = useVirtualizer({
    count: stage.pending.length,
    getScrollElement: () => pendingRef.current,
    estimateSize: () => ROW_H,
    overscan: 6,
    initialRect: { width: 0, height: 160 },
  });
  const pRows = pendingVirt.getVirtualItems();
  const padTopP = pRows.length ? pRows[0].start : 0;
  const padBottomP = pRows.length
    ? Math.max(0, pendingVirt.getTotalSize() - (pRows[pRows.length - 1].start + ROW_H))
    : 0;
  // «بی‌حکم» از کلِ ردیف‌هایِ همین گام خوانده می‌شود، نه از آنچه جدول نشان می‌دهد:
  // جدول از رأیِ مالک فقط پاس‌شده‌ها را می‌شمارد.
  const unseen = stage.entries.length + stage.pending.length - stage.ruled;

  return (
    <section
      data-testid={`funnel-stage-${stage.key}`}
      className={`glass-panel relative overflow-hidden rounded-2xl border bg-bg-card/45 transition-all duration-300 ${
        active ? 'border-accent-blue/70 shadow-[0_0_0_1px_rgba(56,189,248,0.25)]' : 'border-border-c'
      }`}
    >
      {/* شیارِ کاهش: عرضش نسبتِ این مرحلۀ به پهن‌ترین مرحلۀ قیف است */}
      <span
        aria-hidden
        className="absolute inset-y-0 start-0 bg-accent-blue/10 transition-[width] duration-500 ease-out"
        style={{ width: `${pct}%` }}
      />
      <header className="relative flex flex-wrap items-center gap-2 border-b border-border-c/60 px-3 py-2">
        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-blue/20 text-2xs font-black text-accent-blue">
          {toFaDigits(index + 1)}
        </span>
        <h3 className="text-xs font-black text-text-primary sm:text-sm">{STAGE_TITLE[stage.key]}</h3>
        {onToggle ? (
          <button
            type="button"
            data-testid={`funnel-stage-toggle-${stage.key}`}
            aria-expanded={!collapsed}
            onClick={onToggle}
            title={collapsed ? 'باز کردنِ جدولِ این مرحله' : 'بستنِ جدولِ این مرحله'}
            className="shrink-0 rounded-md border border-border-c bg-bg-card px-1.5 py-0.5 text-2xs font-bold text-text-muted transition-colors hover:border-accent-blue/60 hover:text-text-primary"
          >
            {collapsed ? '▼' : '▲'}
          </button>
        ) : null}
        <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-bold text-text-secondary"
              title="تک‌تکِ نمادهایِ جامعۀ غربالگری درِ این گام حکم دارند؛ بدنهٔ جدول فقط عبوری‌ها را می‌شمارد (رأیِ مالک ۱۴۰۵-۰۷-۱۹) و بقیه درِ همین خطِ شمارش و درِ بازرسیِ نماد خوانده می‌شوند">
          {toFaDigits(stage.ruled)} نماد
        </span>
        {delta && (delta.passed !== 0 || delta.ruled !== 0) ? (
          <span data-testid={`funnel-delta-${stage.key}`}
                key={`${delta.passed}:${delta.ruled}`}
                title="تغییرِ همین دور نسبت به دورِ پیشِ قیف"
                className={`num fts-delta-chip rounded-full px-2 py-0.5 text-2xs font-black ${
                  delta.passed > 0 ? 'bg-accent-green/15 text-accent-green'
                    : delta.passed < 0 ? 'bg-accent-red/15 text-accent-red'
                      : 'bg-bg-secondary text-text-muted'
                }`}>
            {delta.passed > 0 ? '+' : ''}{toFaDigits(delta.passed)} عبور
          </span>
        ) : null}
        {stage.dropped > 0 ? (
          <span className="num rounded-full bg-accent-red/15 px-2 py-0.5 text-2xs font-black text-accent-red"
                data-testid={`funnel-dropped-${stage.key}`}
                title="چند نماد درِ این گام رد شده‌اند — بدنهٔ جدول فقط عبوری‌ها را می‌شمارد، پس شمارشان همین‌جا خوانده می‌شود">
            − {toFaDigits(stage.dropped)}
          </span>
        ) : null}
        {/* با «رد نکند، خودم چک می‌کنم» چیزی حذف نمی‌شود، پس dropped صفر است؛
            این شمار نگه می‌دارد که چند ردیف برچسبِ رد دارند. */}
        {stage.dropped === 0 && stage.rejected > 0 ? (
          <span
            data-testid={`funnel-rejected-${stage.key}`}
            className="num rounded-full bg-accent-red/10 px-2 py-0.5 text-2xs font-bold text-accent-red"
            title="رد خورده ولی از غربالگری بیرون نیفتاده — «خودم چک می‌کنم» روشن است"
          >
            {toFaDigits(stage.rejected)} رد (بی‌حذف)
          </span>
        ) : null}
        {stage.unmeasured > 0 ? (
          <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-medium text-text-muted"
                title={STATUS_HINT.unavailable}>
            {toFaDigits(stage.unmeasured)} بی‌داده
          </span>
        ) : null}
        {/* «لازم نبود» ≠ «سنجیده نشده»: این نمادها حکمِ صریح دارند — گامِ پیشین
            ردشانه کرده. بی‌این chip، پریدنِ نماد از گامِ دوم سوم خوانده می‌شد. */}
        {stage.notRequired > 0 ? (
          <span
            data-testid={`funnel-not-required-${stage.key}`}
            className="num rounded-full bg-bg-secondary/70 px-2 py-0.5 text-2xs font-medium text-text-muted"
            title={STATUS_HINT.not_required}
          >
            {toFaDigits(stage.notRequired)} لازم نبود
          </span>
        ) : null}
        {/* گاردِ جامعیت درِ screen: جمعِ پنج وضعیت باید با جامعۀ ورودی بخواند.
            نخواند یعنی نمادی بی‌حکم گم شده — این عدد خودِ بک‌اند است، نه شمارشِ
            ردیف‌هایِ دیدنیِ جدول. */}
        <span
          data-testid={`funnel-ruled-${stage.key}`}
          className={`num rounded-full px-2 py-0.5 text-2xs font-bold ${
            unseen === 0 ? 'bg-accent-green/10 text-accent-green' : 'bg-accent-red/15 text-accent-red'
          }`}
          title={unseen === 0
            ? 'تک‌تکِ نمادهایِ جامعۀ غربالگری درِ این گام حکم دارند (pass + reject + pending + بی‌داده + لازم نبود = Y)'
            : `${toFaDigits(unseen)} نماد در این گام بی‌حکم مانده است؛ نتیجهٔ این مرحله برایشان مشخص نشده و نیاز به بررسی دارد`}
        >
          حکم: {toFaDigits(stage.ruled)}{unseen === 0 ? ' = کلِ جامعۀ غربالگری' : ` ≠ ${toFaDigits(stage.ruled + unseen)}`}
        </span>
        {/* مالک: «تنظیماتِ مرحلۀ بنیادی رو روی نوارِ جدول بنیادی بذار». پیش‌تر یک
            نوارِ سراسری زیرِ چهار مرحله بود؛ هر مرحله پیچ‌هایِ خودش را رویِ
            نوارِ خودش می‌گیرد — همان کاری که کلیدِ تکنیکال از قبل می‌کرد. */}
        {stage.key === 'fundamental' ? (
          <FundStagePrefs passed={stage.summary.pass} techScreens={techScreens} />
        ) : null}
        {/* چیپ‌هایِ فیلتر از این کارت رفتند: سه مرحلۀ اول بسته‌اند و کنترلِ
            داخلِ کارتِ بسته دیده نمی‌شد (رأیِ مالک ۱۴۰۵-۰۷-۲۰). جابه‌جا شدند،
            حذف نشدند — نوارِ بالایِ همین صفحه، با عددِ نامزدِ هر فیلتر. */}
        {/* کنترلِ درِ تکنیکال کنارِ همین مرحله نشسته است، نه در منویِ سراسری. */}
        {stage.key === 'technical' ? (
          <span
            className="flex items-center gap-1"
            role="group"
            aria-label="تکنیکال رد کند یا نه"
            data-testid="funnel-tech-gate"
          >
            {([true, false] as const).map((on) => (
              <button
                key={String(on)}
                type="button"
                data-testid={`funnel-tech-${on ? 'screens' : 'selfcheck'}`}
                aria-pressed={techScreens === on}
                onClick={() => setTechScreens(on)}
                title={on ? TECH_SCREEN_HINT.on : TECH_SCREEN_HINT.off}
                className={`rounded-md border px-1.5 py-0.5 text-2xs font-bold transition-colors ${
                  techScreens === on
                    ? 'border-accent-yellow bg-accent-yellow/15 text-accent-yellow'
                    : 'border-border-c bg-bg-card text-text-muted hover:border-accent-yellow/60'
                }`}
              >
                {on ? TECH_SCREEN_LABEL.on : TECH_SCREEN_LABEL.off}
              </button>
            ))}
          </span>
        ) : null}
        <span className="ms-auto max-w-[46ch] text-3xs leading-4 text-text-muted">{rule}</span>
      </header>

      {/* انتخاب و عملیاتِ دسته‌ای — فقط درِ «جدول تحویل» (بندِ اول مأموریتِ
          پروندۀ نماد). بیرون از بدنهٔ اسکرول‌شونده می‌نشیند تا با سرستونِ
          چسبانِ جدول در نیفتد، و یک خط نازک است: کنترلی که دیده نشود، کنترلی
          است که حذف شده خوانده می‌شود. */}
      {stage.key === 'handover' && !collapsed ? (
        <HandoverActions rows={rows} onPick={onPick} />
      ) : null}

      {/* بدنه: درِ حالتِ بسته هیچ جدولی نمی‌راند (نه display:none) — چهار مرحلۀ
          باز رویِ نمایشگرِ ۱۳۶۶×۷۶۸ یعنی اسکرولِ بی‌پایان پیش از رسیدن به تحویل. */}
      {collapsed ? null : (<>
      <div ref={bodyRef} className="relative h-[calc(100dvh-392px)] min-h-[380px] overflow-y-auto overflow-x-auto" data-testid={`funnel-scroll-${stage.key}`}>
        {rows.length === 0 ? (
          <p className="px-3 py-4 text-xs text-text-muted" data-testid={`funnel-empty-${stage.key}`}>
            {emptyWhy ?? 'هیچ نمادی از این مرحله عبور نکرد.'}
          </p>
        ) : (
          <table className="w-full min-w-[720px] table-fixed border-collapse text-sm">
            {/* `min-w-[720px]` + اسکرولِ افقیِ همان ظرف: درِ ۳۹۰px ستونِ نماد به
                ~۴۸px می‌افتاد و نامِ خودِ نماد وسطِ حروف می‌شکست («آبنو/س») —
                یعنی بریدگیِ تازه، نه حلِّ بریدگی. با کفِ عرض ستون‌ها جا
                می‌مانند و اسکرولِ افقی جدول را می‌خواند. */}
            <ColGroup cols={cols} />
            <thead className="sticky top-0 bg-bg-primary/95 text-2xs text-text-muted backdrop-blur-sm">
              <tr>
                {cols.map((k) => (
                  <th
                    key={k}
                    title={COL[k].title}
                    className={`truncate px-2 py-1 font-bold ${COL[k].end ? 'text-end' : 'text-start'}`}
                  >
                    {COL[k].label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {padTop > 0 ? <tr aria-hidden style={{ height: padTop }} /> : null}
              {vRows.map((vr) => {
                const r = rows[vr.index];
                return (
                  <StageRow key={r.symbol} entry={r} cols={cols} showMark={showMark}
                            stageKey={stage.key} onPick={onPick}
                            selectable={stage.key === 'handover'}
                            changed={changed.has(r.symbol)} />
                );
              })}
              {padBottom > 0 ? <tr aria-hidden style={{ height: padBottom }} /> : null}
            </tbody>
          </table>
        )}
      </div>

      {/* گروهِ «در انتظار»: نه مردود است نه تحویل. بی‌این، نبودنِ گزارشِ کدال
          «رد» به‌نظر می‌رسید و کاربر نمادی را از دست می‌داد که فقط بی‌داده است.
          این ردیف‌ها از جدولِ بالا جدا شده‌اند (تکراری نیستند) ولی همچنان
          شمارشان درِ coverageِ همان مرحله می‌نشیند. */}
      {stage.pending.length > 0 ? (
        <div data-testid={`funnel-pending-${stage.key}`} className="border-t border-dashed border-border-c/70 bg-bg-secondary/40">
          <p className="px-3 py-1.5 text-3xs font-bold text-text-muted">
            {stage.key === 'handover'
              ? `نگه‌داشته در مرحلۀ تحویل: هنوز آمادهٔ عبور نیست و رد قطعی هم نشده است (${toFaDigits(stage.pending.length)})`
              : `بررسی شده اما نتیجهٔ قطعی ندارد؛ بنابراین رد نشده است (${toFaDigits(stage.pending.length)})`}
          </p>
          <div ref={pendingRef} className="max-h-[160px] overflow-y-auto overflow-x-auto">
            <table className="w-full min-w-[720px] table-fixed border-collapse text-sm">
              {/* سرستونِ همان مرحله، با همان colgroup: ردیف‌هایِ انتظار هم باید
                  بدانند کدام ✓/✗ کدام شاخص است، و ستون‌هایِ دو جدول رویِ هم
                  بنشینند وگرنه «سرستونِ دوم» کج می‌آید. */}
              <ColGroup cols={cols} />
              <thead className="sticky top-0 text-2xs text-text-muted">
                <tr>
                  {cols.map((k) => (
                    <th key={k} className={`truncate px-2 py-1 font-bold ${COL[k].end ? 'text-end' : 'text-start'}`}>
                      {COL[k].label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {padTopP > 0 ? <tr aria-hidden style={{ height: padTopP }} /> : null}
                {pRows.map((vr) => {
                  const r = stage.pending[vr.index];
                  return (
                    <StageRow
                      key={r.symbol}
                      entry={r}
                      cols={cols}
                      showMark={stage.key === 'handover' ? 'handover' : 'fund'}
                      stageKey={stage.key}
                      onPick={onPick}
                      selectable={stage.key === 'handover'}
                    />
                  );
                })}
                {padBottomP > 0 ? <tr aria-hidden style={{ height: padBottomP }} /> : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
      </>)}
    </section>
  );
}

/** نوارِ انتخاب و عملیاتِ «جدول تحویل» (بندِ اول مأموریتِ پروندۀ نماد).
 *
 *  سه چیز را با هم نگه می‌دارد: انتخاب از فهرست، افزودنِ دسته‌ای به واچ‌لیست،
 *  و بردنِ نماد به برآیند. «افزودنِ دسته‌ای» انتخاب را پاک نمی‌کند (مالک:
 *  «انتخاب‌ها در زمان عملیات دسته‌ای از بین نروند»)، و پیغامِ نتیجه سه شمارۀ
 *  جدا می‌دهد: افزوده‌شده، از قبل موجود، و نپذیرفته‌شده (سقفِ واچ‌لیست درِ
 *  `api/watchlist.py:53` واقعی است و بی‌این شمار کاربر ردِّ بی‌صدا می‌دید).
 *  عملیات فقط رویِ نمادهایِ واقعاً انتخاب‌شده می‌دود؛ «همه» یعنی همان
 *  ردیف‌هایی که همین حالا درِ جدولِ تحویل‌اند (عبورکرده‌هایِ دورِ جاری). */
function HandoverActions({ rows, onPick }: {
  rows: FunnelEntry[];
  onPick: (s: string) => void;
}) {
  const items = useSelectedSymbolsStore((s) => s.items);
  const addMany = useSelectedSymbolsStore((s) => s.addMany);
  const clearSel = useSelectedSymbolsStore((s) => s.clear);
  const addWatch = useWatchlistAddMany();
  const [msg, setMsg] = useState<string | null>(null);
  const selectedCount = items.length;
  // «چندتای انتخابی درِ همین جدول‌اند» با «چندتا انتخاب شده» یکی نیست: فهرستِ
  // انتخاب سراسری است و از تابلو/بنیادی هم پر می‌شود.
  const inRows = useMemo(() => {
    const norms = new Set(items.map((i) => i.norm));
    return rows.filter((r) => norms.has(normalizeFa(r.symbol))).length;
  }, [items, rows]);
  const target = useMemo(() => {
    const norms = new Set(items.map((i) => i.norm));
    const hit = rows.find((r) => norms.has(normalizeFa(r.symbol)));
    return hit?.symbol ?? items[0]?.symbol ?? null;
  }, [items, rows]);

  const runAdd = () => {
    setMsg(null);
    addWatch.mutate(items.map((i) => ({ symbol: i.symbol, name: i.name })), {
      onSuccess: (r) => {
        const parts = [`افزوده شد: ${toFaDigits(r.added)}`,
                       `از قبل در واچ‌لیست: ${toFaDigits(r.already)}`];
        if (r.failed) parts.push(`نشد: ${toFaDigits(r.failed)}`);
        setMsg(parts.join(' · ') + (r.message ? ` — ${r.message}` : ''));
      },
      onError: (e) => setMsg(`افزودن ناموفق: ${e instanceof Error ? e.message : 'خطا'}`),
    });
  };

  return (
    <div
      data-testid="funnel-handover-actions"
      className="relative flex flex-wrap items-center gap-1.5 border-b border-border-c/60 bg-bg-secondary/50 px-3 py-1 text-2xs"
    >
      <button
        type="button"
        data-testid="funnel-select-all"
        onClick={() => { setMsg(null); addMany(rows.map((r) => ({ symbol: r.symbol, name: r.name }))); }}
        disabled={!rows.length}
        title="همۀ عبوری‌های همین دور از جدول تحویل انتخاب می‌شوند؛ نمادی که انتخاب است دوباره شمارش نمی‌شود"
        className="rounded-md border border-border-c bg-bg-card px-2 py-0.5 font-bold text-text-secondary hover:border-accent-blue/60 hover:text-accent-blue disabled:opacity-40"
      >
        انتخاب همۀ نتایج فعلی ({toFaDigits(rows.length)})
      </button>
      {selectedCount > 0 ? (
        <button
          type="button"
          data-testid="funnel-select-clear"
          onClick={() => { clearSel(); setMsg(null); }}
          className="rounded-md border border-border-c bg-bg-card px-2 py-0.5 font-bold text-text-muted hover:border-accent-red/60 hover:text-accent-red"
        >
          لغو انتخاب
        </button>
      ) : null}
      <span
        data-testid="funnel-selection-count"
        className={`font-bold ${selectedCount ? 'text-accent-blue' : 'text-text-muted'}`}
      >
        {selectedCount
          ? `${toFaDigits(selectedCount)} نماد انتخاب شده (${toFaDigits(inRows)} در این جدول)`
          : 'چیزی انتخاب نشده'}
      </span>
      {selectedCount > 0 ? (
        <>
          <button
            type="button"
            data-testid="funnel-bulk-watch"
            onClick={runAdd}
            disabled={addWatch.isPending}
            title="نمادهای انتخاب‌شده به واچ‌لیست اضافه می‌شوند؛ رکورد تکراری ساخته نمی‌شود و انتخاب نمی‌سوزد"
            className="rounded-md border border-accent-blue/50 bg-accent-blue/15 px-2 py-0.5 font-black text-accent-blue hover:bg-accent-blue/25 disabled:opacity-50"
          >
            {addWatch.isPending ? 'در حال افزودن…' : `افزودن به واچ‌لیست (${toFaDigits(selectedCount)})`}
          </button>
          {target ? (
            <button
              type="button"
              data-testid="funnel-bulk-review"
              onClick={() => { setMsg(null); onPick(target); }}
              title="پروندۀ کاملِ همین نماد در صفحهٔ برآیند باز می‌شود؛ از همان‌جا می‌توان به نماد بعدیِ انتخابی رفت"
              className="rounded-md border border-border-c bg-bg-card px-2 py-0.5 font-bold text-text-secondary hover:border-accent-blue/60 hover:text-accent-blue"
            >
              بررسی در برآیند
            </button>
          ) : null}
        </>
      ) : null}
      {msg ? (
        <span data-testid="funnel-bulk-result" className="min-w-0 truncate text-text-muted" title={msg}>
          {msg}
        </span>
      ) : null}
    </div>
  );
}

/** صادر شده تا تستِ واحد بتواند یکِ ردیفِ تنها را بسنجد (بندِ ۱ مأموریتِ رابط:
 *  نامِ نماد درِ حضورِ برچسبِ بلند نباید بریده شود). */
export function StageRow({
  entry,
  cols,
  showMark,
  stageKey,
  onPick,
  changed,
  selectable = false,
}: {
  entry: FunnelEntry;
  cols: ColKey[];
  showMark: 'tech' | 'fund' | 'handover' | null;
  /** دلیلِ هر ردیف از همان گامی است که کارت نمایشش می‌دهد — درِ «تابلوخوانی»
   *  هم باید نوشته باشد کدام فیلتر ردش کرد؛ پیشِ این showMark آن را null می‌گذاشت
   *  و ستونِ دلیل درِ آن گام همیشه «—» می‌ماند. */
  stageKey: FunnelStageKey;
  onPick: (s: string) => void;
  /** حکمِ این نماد درِ دورِ اخیر عوض شده — ردیف یک لحظه روشن می‌شود تا
   *  «زنده بودنِ» قیف دیده شود (نه یک داوریِ تازه). */
  changed?: boolean;
  /** جعبۀ انتخاب فقط درِ «جدول تحویل» (بندِ اول مأموریتِ پروندۀ نماد). ستونِ
   *  تازه نمی‌سازد — داخلِ همان سلولِ نماد می‌نشیند، همان قراردادی که
   *  `SymbolSelectBox` درِ تابلو رعایت می‌کند و افزودنِ ستونِ جدید grid را کج کرد. */
  selectable?: boolean;
}) {
  const key = showMark === 'tech' ? 'technical' : showMark === 'handover' ? 'handover' : 'fundamental';
  const mark = showMark ? entry.status[key] : entry.status[stageKey] || null;
  const why = entry.why[stageKey] || null;
  // وتوی مجمع فقط درِ مرحلۀ «تحویل» نماد را بیرون می‌اندازد، ولی برچسبش در
  // همهٔ مرحله‌ها می‌نشیند: وگرنه کاربر می‌بیند نمادی که درِ بنیادی قبول شده
  // در مرحلۀ آخر غیب شده و هیچ دلیلی برایش نوشته نیست.
  const rowTitle = entry.assemblyVeto ? [why, entry.assemblyWhy].filter(Boolean).join(' · ') : (why ?? undefined);
  return (
    <tr
      data-fkey={entry.symbol}
      data-changed={changed ? '1' : undefined}
      className={`group border-b border-border-c/40 last:border-0 hover:bg-bg-card/70${changed ? ' fts-row-changed' : ''}`}
      title={rowTitle}
    >
      <td className="px-2 py-1 text-start">
        {/* دو خط: خطِ اول خودِ نماد (همیشه کامل)، خطِ دوم برچسبِ وضعیت.
            پیش‌تر نامک و برچسب‌ها درِ یک `flex … truncate` با `max-w-[15ch]`
            بودند و هر دو برچسب `shrink-0` — یعنی «عبور با ملاحظات» (۱۴ نویسه)
            نماد را به «…» می‌کوبید. نام نماد نباید قربانیِ برچسب شود. */}
        <div className="flex min-w-0 flex-col gap-0.5">
          <div className="flex min-w-0 items-center gap-1">
            {selectable ? <SymbolSelectBox symbol={entry.symbol} name={entry.name ?? ''} /> : null}
            <button
              type="button"
              onClick={() => onPick(entry.symbol)}
              className="flex min-w-0 items-center gap-1 text-start font-black text-text-primary hover:text-accent-blue"
            >
              {mark ? <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${MARK_DOT[mark]}`} /> : null}
              <span className="min-w-0 whitespace-normal break-words leading-tight">{entry.symbol}</span>
            </button>
          </div>
          {entry.assemblyVeto || entry.fundCaveat ? (
            <div data-testid={`funnel-row-marks-${entry.symbol}`}
                 className="flex min-w-0 flex-wrap items-center gap-1 ps-4">
              {entry.assemblyVeto ? (
                <span
                  data-testid={`funnel-assembly-veto-${entry.symbol}`}
                  className="shrink-0 rounded border border-accent-red/40 bg-accent-red/15 px-1 text-[9px] font-bold text-accent-red"
                  title={entry.assemblyWhy}
                >
                  وتوی مجمع
                </span>
              ) : null}
              {/* عبور با ملاحظات: رأیِ مالک ۱۴۰۵-۰۷-۲۱ — سه PASS کافی است، پس این
                  نماد درِ فهرستِ عبوری‌هاست؛ زرد فقط می‌گوید کدام‌ها سنجیده نشدند یا
                  رد شدند. متنِ علت را خودِ موتور نوشته، اینجا بازنویسی نمی‌شود. */}
              {entry.fundCaveat ? (
                <span
                  data-testid={`funnel-fund-caveat-${entry.symbol}`}
                  className="shrink-0 rounded border border-accent-yellow/50 bg-accent-yellow/15 px-1 text-[9px] font-bold text-accent-yellow"
                  title={entry.why.fundamental || 'عبور با ملاحظات'}
                >
                  عبور با ملاحظات
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
      </td>
      {cols.filter((k) => k !== 'symbol').map((k) => (
        <Cell key={k} k={k} e={entry} mark={mark} why={why} />
      ))}
    </tr>
  );
}

/**
 * چیپ‌هایِ هفت فیلترِ رجیستری + کلیدِ اشتراک/اجتماع. با رأیِ مالکِ ۱۴۰۵-۰۷-۲۰
 * از سرِ کارتِ «تابلوخوانی» به **نوارِ بالایِ غربالگری** آمد: سه مرحلۀ اول
 * بسته‌اند، پس کنترلی که داخلِ کارتِ بسته است درِ عمل دیده نمی‌شد.
 * عددِ کنارِ هر چیپ نامزدِ همان فیلتر رویِ **نامزدِ جاری** است
 * (`funnel_engine.filter_counts` با زنجیره و منطقِ همین دور) — رأیِ مالک
 * ۱۴۰۵-۰۷-۲۱: «وقتی حجم مشکوک روشن است، جت بگوید از این‌ها چندتا». بی‌هیچ
 * چیپِ روشن مبنایِ شمارش کلِّ جامعۀ غربالگری است، پس عددِ همیشگی می‌ماند.
 * این همان `quickFilters` تبِّ تابلو است، پس دو منبعِ حقیقت نیست و از قیف روشن
 * شدنش هم عوضی در نمی‌آید.
 */
function TapeStagePrefs({ picked, counts, filters }: {
  picked: number;
  counts: Record<string, FilterCount>;
  filters: { active: string[]; source: 'chips' | 'chain'; toggle: (f: string) => void };
}) {
  const logic = useScreenFilterStore((s) => s.logic);
  const setLogic = useScreenFilterStore((s) => s.setLogic);
  const onCount = filters.active.length;
  return (
    <span
      data-testid="funnel-tape-prefs"
      className="sticky top-[var(--pinned-h)] z-20 -mx-1 flex flex-wrap items-center justify-end gap-1 rounded-lg bg-bg-card/95 px-1 py-0.5 backdrop-blur-sm"
      role="group"
      aria-label="فیلترهای ورودی غربالگری"
    >
      {QUICK_FILTERS.map((f: QuickFilter) => {
        const on = filters.active.includes(f);
        const c = counts[f];
        return (
          <button
            key={f}
            type="button"
            data-testid={`funnel-tape-chip-${f}`}
            aria-pressed={on}
            onClick={() => filters.toggle(f)}
            title={c
              ? `${QUICK_LABELS[f]} — ${toFaDigits(c.matched)} نامزد از ${toFaDigits(c.input)} ردیفِ نامزدِ فعلی`
                + `؛ ${toFaDigits(c.removed)} رد، ${toFaDigits(c.unmeasured)} بی‌حکم`
                + (c.universe ? ` (کلِّ جامعۀ غربالگری: ${toFaDigits(c.universe)})` : '')
              : `${QUICK_LABELS[f]} — شمارشِ نامزد از سرور نرسید`}
            className={`rounded-md border px-1.5 py-0.5 text-2xs font-bold transition-colors ${
              on
                ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:border-accent-blue/60'
            }`}
          >
            {QUICK_LABELS[f]}
            <span className="num ms-1 font-black opacity-95">
              {c ? `(${toFaDigits(c.matched)})` : '(—)'}
            </span>
          </button>
        );
      })}
      {/* یک کلید، دو حالت: «اشتراک» یعنی هر چیپِ روشن لازم است (AND)، «اجتماع» یعنی
          داشتنِ یکی کافی است (OR). همان `bors.screen.logic.v1` که کنارِ چیپ‌هایِ تبِّ
          تابلو است. */}
      <button
        type="button"
        data-testid="funnel-screen-logic"
        aria-pressed={logic === 'or'}
        disabled={onCount === 0}
        onClick={() => setLogic(logic === 'or' ? 'and' : 'or')}
        title={onCount === 0
          ? 'برای شروع غربالگری، دست‌کم یک فیلتر را روشن کنید'
          : logic === 'or'
            ? `اجتماع (OR): داشتنِ حداقل یکی از ${toFaDigits(onCount)} فیلترِ روشن کافی است`
            : `اشتراک (AND): نماد باید هر ${toFaDigits(onCount)} فیلترِ روشن را داشته باشد`}
        className={`rounded-md border px-1.5 py-0.5 text-2xs font-bold transition-colors ${
          logic === 'or'
            ? 'border-accent-yellow bg-accent-yellow/15 text-accent-yellow'
            : 'border-border-c bg-bg-card text-text-muted hover:border-accent-yellow/60'
        }`}
      >
        {logic === 'or' ? 'اجتماع' : 'اشتراک'}
      </button>
      <span className="num text-3xs text-text-muted">ورودی: {toFaDigits(picked)}</span>
    </span>
  );
}

/** پیچ‌هایِ درِ بنیادی — سخت‌گیریِ جزوه کم نمی‌شود، حقِ انتخاب دستِ خودِ مالک است.
    درونِ <header> همان مرحله می‌نشیند، پس جعبه و عنوانِ تکراری ندارد. */
function FundStagePrefs({ passed, techScreens }: { passed: number; techScreens: boolean }) {
  const fundFloor = useFunnelPrefsStore((s) => s.fundFloor);
  const unmeasured = useFunnelPrefsStore((s) => s.unmeasured);
  const setFundFloor = useFunnelPrefsStore((s) => s.setFundFloor);
  const setUnmeasured = useFunnelPrefsStore((s) => s.setUnmeasured);
  const reset = useFunnelPrefsStore((s) => s.reset);

  const chip = (on: boolean) =>
    `rounded-md border px-1.5 py-0.5 text-2xs font-bold transition-colors ${
      on ? 'border-accent-yellow bg-accent-yellow/15 text-accent-yellow' : 'border-border-c bg-bg-card text-text-muted hover:border-accent-yellow/60'
    }`;

  return (
    <div
      data-testid="funnel-prefs"
      className="flex flex-wrap items-center gap-x-2 gap-y-1"
    >
      <span
        className="text-2xs font-black text-text-secondary"
        title={`پیش‌فرض FTS: ${toFaDigits(DEFAULT_FUND_FLOOR)} از ${toFaDigits(FUND_FLOOR_MAX)}`}
      >
        حداقل امتیاز بنیادی
      </span>
      <span className="flex items-center gap-1" role="group" aria-label="حداقل امتیاز بنیادی از پنج شاخص">
        {Array.from({ length: FUND_FLOOR_MAX }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`funnel-floor-${n}`}
            aria-pressed={fundFloor === n}
            onClick={() => setFundFloor(n)}
            className={`num h-6 w-6 rounded-md border text-2xs font-black transition-colors ${chip(fundFloor === n)}`}
            title={n === DEFAULT_FUND_FLOOR ? 'پیش‌فرض FTS' : undefined}
          >
            {toFaDigits(n)}
          </button>
        ))}
      </span>
      <span className="flex items-center gap-1" role="group" aria-label="تکلیفِ سنجیده‌نشده‌ها">
        {(['hold', 'pass', 'drop'] as UnmeasuredPolicy[]).map((p) => (
          <button
            key={p}
            type="button"
            data-testid={`funnel-unmeasured-${p}`}
            aria-pressed={unmeasured === p}
            onClick={() => setUnmeasured(p)}
            title={UNMEASURED_HINT[p]}
            className={chip(unmeasured === p)}
          >
            {UNMEASURED_LABEL[p]}
          </button>
        ))}
      </span>
      <span className="num text-3xs text-text-muted">
        عبور با این پیچ‌ها: {toFaDigits(passed)}
      </span>
      {fundFloor !== DEFAULT_FUND_FLOOR || unmeasured !== 'hold' || !techScreens ? (
        <button
          type="button"
          data-testid="funnel-prefs-reset"
          onClick={reset}
          title="بازگردانی تنظیمات به پیش‌فرض FTS"
          className="text-3xs font-bold text-text-muted underline hover:text-accent-yellow"
        >
          بازگردانی به پیش‌فرض FTS
        </button>
      ) : null}
    </div>
  );
}

/** بخشِ بازشوندهٔ «خارج از جامعۀ غربالگری».
 *
 *  این نمادها نه رد شده‌اند نه «سنجیده نشده»: وضعیتِ رسمیِ بازار اجازهٔ غربال
 *  نمی‌دهد، پس درِ جدولِ چهار گام نمی‌نشینند (رأیِ مالک ۱۴۰۵-۰۷-۱۶: «جدول را
 *  با این نمادها شلوغ نکن… برای Z یک بخش بازشونده/Inspector بگذار که علتِ
 *  خروج را نشان دهد»). فهرست مجازی و بی‌سقف است: علتِ هر نماد عیناً از
 *  `human_reasonِ` خودِ موتور می‌آید، واژۀ دومی ساخته نمی‌شود. */
function OutOfUniversePanel({ funnel, onPick }: { funnel: Funnel; onPick: (s: string) => void }) {
  const rows = funnel.exclusions;
  const ref = useRef<HTMLDivElement | null>(null);
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => ref.current,
    estimateSize: () => 26,
    overscan: 10,
    initialRect: { width: 0, height: 224 },
  });
  const reasons = Object.entries(funnel.exclusionCounts).sort((a, b) => b[1] - a[1]);
  const labelOf = (code: string) => funnel.exclusionLabels[code] ?? code;
  return (
    <div className="glass-panel rounded-xl border border-border-c bg-bg-card/40 p-2"
         data-testid="funnel-exclusions">
      <div className="mb-1 flex flex-wrap items-center gap-2 text-3xs font-bold text-text-muted">
        <span>علتِ خروج:</span>
        {reasons.map(([code, count]) => (
          <span key={code} data-testid={`funnel-exclusion-${code}`}
                className="num rounded-full bg-bg-secondary px-2 py-0.5">
            {labelOf(code)}: {toFaDigits(count)}
          </span>
        ))}
        {!reasons.length ? <span data-testid="funnel-exclusion-none">چیزی خارج از جامعه نیست.</span> : null}
      </div>
      {/* توضیحِ تفاوتِ شمارۀ تابلو با غربالگری (گزینهٔ الف): شمارۀ چیپِ تبِّ تابلو
          این نمادها را هم می‌شمرد (چون فیلتر را پاس می‌کنند)؛ اینجا فقط علتِ بیرون‌
          ماندنشان از غربالگری نوشته می‌شود. تفاوت از جامعۀ نماد/قواعدِ پذیرش است،
          نه از اختلافِ محاسبه — و شمارۀ تابلو برایِ برابرشدن کم نمی‌شود. */}
      {rows.length ? (
        <p className="mb-1 text-3xs leading-4 text-text-muted" data-testid="funnel-universe-reconcile">
          این نمادها فیلترِ تابلو را پاس می‌کنند و درِ شمارۀ چیپِ تبِّ «تابلوخوانی» شمرده
          می‌شوند؛ قواعدِ پذیرشِ غربالگری (توقف/ممنوعیت/پسوندِ عددی) آن‌ها را از جامعۀ
          غربالگری بیرون می‌گذارد. پس تفاوتِ شمارۀ تابلو و غربالگری از جامعۀ نماد است،
          نه اختلافِ محاسبه.
        </p>
      ) : null}
      <div ref={ref} className="max-h-56 overflow-y-auto">
        <div className="relative" style={{ height: virt.getTotalSize() }}>
          {virt.getVirtualItems().map((it) => {
            const e = rows[it.index];
            return (
              <div key={e.symbol} data-index={it.index}
                   className="absolute inset-x-0 flex items-center gap-2 border-b border-border-c/40 px-1 text-2xs"
                   style={{ top: it.start, height: it.size }}>
                <button type="button" data-testid={`funnel-exclusion-row-${e.symbol}`}
                        onClick={() => onPick(e.symbol)}
                        className="shrink-0 font-black text-text-primary hover:text-accent-blue">
                  {e.symbol}
                </button>
                <span className="min-w-0 truncate text-text-muted">{e.name}</span>
                <span className="num ms-auto shrink-0 text-text-secondary"
                      title={e.last != null && e.last <= 0 ? 'صفرِ واقعی: مبادله‌ای ثبت نشده' : undefined}>
                  {e.last != null ? fmtInt(e.last) : '—'}
                </span>
                <span className="max-w-[46ch] shrink-0 truncate text-text-muted"
                      title={e.humanReason}>
                  {e.humanReason || labelOf(e.reasonCode)}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export function FtsFunnelStages({
  preset = 'custom',
  only,
}: {
  preset?: TreePreset;
  /** حالتِ مسیریافته: فقط کارتِ همین مرحله؛ فهرستِ چهارتایی درِ گام چهارم می‌ماند */
  only?: FunnelStageKey;
}) {
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const navigate = useNavigate();
  const [snap] = useState(readFunnelSnap);
  // «خارج از جامعۀ غربالگری» بسته است تا جدولِ گام‌ها با این ردیف‌ها شلوغ
  // نشود؛ خطِ خلاصه خودش Z را می‌گوید و همین دکمه علتِ تک‌تکشان را باز می‌کند.
  const [showExcluded, setShowExcluded] = useState(false);
  const [activeState] = useState<FunnelStageKey>(() => snap?.stage ?? 'tape');
  // رأیِ مالک (۱۴۰۵-۰۷-۲۲): سه جدولِ اول بسته‌اند و «نمادهای عبوری» (تحویل) باز —
  // چیزی که کاربر می‌خواهد ببیند همان آخری است، نه اینکه چهار جدول را اسکرول کند.
  // درِ حالتِ مسیریافته (`only`) همان یک کارت باز می‌ماند، چون کاربر صریح
  // به‌آن مرحله رفته است. کلیک رویِ گامِ بسته، خودش را باز می‌کند (کنترلِ
  // جاافتاده باقی نمی‌ماند).
  const [openStages, setOpenStages] = useState<Record<FunnelStageKey, boolean>>({
    tape: false, technical: false, fundamental: false, handover: true,
  });
  const dropSuffix = useFunnelPrefsStore((s) => s.dropSuffix);
  const setDropSuffix = useFunnelPrefsStore((s) => s.setDropSuffix);
  // درِ حالتِ مسیریافته (`only`) گامِ واقعی همان `only` است، نه stateِ داخلیِ
  // این کامپوننت (که از snapshotِ قدیم پر شده). بی‌این، کلیکِ سطر درِ گامِ
  // تکنیکال آدرسِ `?stage=tape` می‌ساخت و بازگشت کاربر را یک گام عقب می‌برد.
  const active = only ?? activeState;
  // کلیکِ سطر یک گذرِ واقعی است، نه فقط یک استور: URL نماد را نگه می‌دارد تا
  // «← بازگشت» و دکمۀ عقبِ مرورگر هر دو به همان قیف برسند (Round M §۱۰).
  const pick = (s: string) => {
    try {
      sessionStorage.setItem(FUNNEL_SNAP_KEY, JSON.stringify({ stage: active, scroll: readAppScroll() }));
    } catch {
      /* حافظه پر/غیرقابل دسترس: بازگشت بی‌اسکرول بهتر از بی‌عبور است */
    }
    setSymbol(s);
    // گامِ فعال درِ URL می‌ماند: بی‌این «بازگشت» کاربر را از گام چهارم به گام
    // اول می‌انداخت (snapshot تنها برایِ اسکرول نوشته شده بود، و همان هم درِ
    // اسکرولِ صفر پاک می‌شد).
    navigate(`/master/${encodeURIComponent(s)}?stage=${active}`);
  };

  // یک مدل، چند رندرر: قیف از `useFtsFunnel` می‌آید — همان چیزی که فهرستِ تحویل
  // و سایدبار هم می‌خوانند، پس دو دورۀ داوری درِ این تب نداریم.
  const { funnel, mode, tape, tech, scan, refreshing, screenFilters, opts, error, hasData, retry } = useFtsFunnel(preset);
  const setMode = useFunnelPrefsStore((s) => s.setMode);

  // بازگردانی scroll: قیف پولینگ می‌شود و سطرهایش چند دور بعد جا می‌افتند؛
  // تا سطر به اندازه نگه داشته نشده، تلاشِ بعدی رندر دوباره می‌آزماید.
  const scrollRestored = useRef(false);
  useEffect(() => {
    if (!snap || scrollRestored.current) return;
    if (snap.scroll <= 0 || scrollTargets().length === 0) {
      scrollRestored.current = true;
      try {
        sessionStorage.removeItem(FUNNEL_SNAP_KEY);
      } catch {
        /* بی‌مصرف باقی می‌ماند و دفعۀ بعد دوباره خوانده می‌شود */
      }
      return;
    }
    if (!applyAppScroll(snap.scroll)) return; // محتوا هنوز کوتاه است — رندرِ بعد دوباره می‌آزماید
    scrollRestored.current = true;
    try {
      sessionStorage.removeItem(FUNNEL_SNAP_KEY);
    } catch {
      /* همان بالا */
    }
  }, [snap, funnel]);

  const stages = ORDER.map((k) => funnel.stages[k]);
  const shownKeys = only ? [only] : ORDER;
  // شمارشِ واقعیِ درِ تحویل: «چند تا واقعاً» — نه اینکه برایِ رسیدن به ۱۰ نماد
  // ضعیف اضافه شود. هدف‌هایِ جزوه فقط مرجعِ کناری‌اند.
  const hc = funnel.counts.handover;
  const wide = Math.max(1, funnel.total);
  const marks: ('tech' | 'fund' | 'handover' | null)[] = [null, 'tech', 'fund', 'handover'];

  // «چرا خالی است» باید خودش را بگوید، وگرنه مرحلۀ خالی با مرحلۀ خراب یکی
  // به‌نظر می‌رسد: «هیچ‌کدام به این در نرسید» با «همه رد شدند» یکی نیست.
  const fund = funnel.stages.fundamental;
  const hand = funnel.stages.handover;
  const emptyWhy: Record<FunnelStageKey, string | null> = {
    tape: funnel.total ? null : 'هیچ نمادی درِ جامعۀ غربالگریِ این روز نبود (تابلو یا وضعیتِ رسمیِ نمادها اجازهٔ غربال نداد).',
    technical: funnel.stages.technical.entries.length
      ? null
      : 'مرحلۀ تابلو خالی بود تا تکنیکال چیزی برای داوری داشته باشد.',
    fundamental: fund.entries.length
      ? null
      : fund.unmeasured
        ? 'رسیدگان همه بی‌گزارش‌اند — در صفِ پایینِ همین مرحله می‌مانند.'
        : funnel.stages.technical.dropped
          ? `به این مرحله کسی نرسید: ${toFaDigits(funnel.stages.technical.dropped)} نماد در مرحلۀ تکنیکال رد شدند.`
          : 'هیچ‌کدام پنج‌شاخصهٔ قبول‌شدن ندارد.',
    handover: hand.entries.length
      ? null
      : (() => {
          // علت از خودِ ردیف‌ها خوانده می‌شود: توقفِ مجمع با توقفِ «در سبد» و با
          // «بنیادی کسی را قبول نکرد» یکی نیست (#15).
          const assembly = hand.pending.filter((e) => e.assemblyVeto).length;
          const held = hand.pending.length - assembly;
          if (assembly) {
            return `${toFaDigits(assembly)} نماد تا ۱۴ روز مجمعِ عمومی دارد — ورود وتو است${
              held ? `؛ ${toFaDigits(held)} نمادِ دیگر همین حالا در سبدِ شماست` : ''
            }.`;
          }
          if (held) return 'رسیدگانِ بنیادی همه همین حالا در سبدِ شما هستند.';
          return fund.entries.length
            ? 'مرحلۀ تحویل چیزی برای تحویل نداشت — بنیادی یا تکنیکال بالا را ببینید.'
            : 'مرحلۀ بنیادی کسی را قبول نکرد.';
        })(),
  };

  return (
    <section className="flex flex-col gap-2">
      {error ? <FunnelErrorBanner onRetry={retry} blocking={!hasData} /> : null}
      {/* سرستونِ غربالگری سمتِ راست می‌ایستد (رأیِ مالک ۱۴۰۵-۰۷-۱۹): عنوانِ صفحه،
          دو حالتِ کشف، تازگیِ تابلو و ساعتِ محاسبه. خطِ شمارش‌ها پایین‌تر همان
          لبۀِ چپ را نگه می‌دارد (رأیِ ۱۴۰۵-۰۷-۲۰). */}
      <div className="flex flex-wrap items-center justify-start gap-2">
        <h2 className="text-sm font-black text-text-primary">غربالگری FTS</h2>
        {/* دو حالتِ کشف، یک قراردادِ داوری (#2 و #14): مهندسیِ معکوس مسیرِ اصلیِ
            جزوه است؛ مرورِ بازار برایِ بازارِ بسته یا بررسیِ کلِ universe. */}
        <div className="flex flex-wrap items-center gap-1" role="group" aria-label="حالتِ کشفِ نماد" data-testid="funnel-mode-picker">
          {(['reverse', 'review'] as const).map((m) => (
            <button
              key={m}
              type="button"
              aria-pressed={mode === m}
              data-testid={`funnel-mode-${m}`}
              title={MODE_HINT[m] + ' — ' + MODE_PATH[m]}
              onClick={() => setMode(m)}
              className={`rounded-full border px-2 py-0.5 text-3xs font-bold transition-all ${
                mode === m
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-muted hover:border-accent-blue/60 hover:text-text-primary'
              }`}
            >
              {MODE_LABEL[m]}
            </button>
          ))}
          <span
            className="rounded-full border border-border-c bg-bg-secondary px-2 py-0.5 text-3xs font-bold text-text-muted"
            data-testid="funnel-tape-freshness"
            title="تازگیِ خوراکِ تابلو — دادهٔ آخرین روز معاملاتی جایِ زنده خوانده نمی‌شود"
          >
            {TAPE_FRESHNESS_LABEL[tape]}
          </span>
          {/* آخرین محاسبۀِ *موفق* از خودِ سرور (`as_of`) — ساعتِ همان ماشین. بی‌این،
              «در حال محاسبه» هیچ نقطۀِ پایانی نداشت و کاربر نمی‌دانست عددی که می‌بیند
              متعلق به کِی است (بندِ «وضعیت پردازش و تازگی» مأموریت). */}
          <span
            className="num rounded-full border border-border-c bg-bg-secondary px-2 py-0.5 text-3xs font-bold text-text-muted"
            data-testid="funnel-as-of"
            title="زمانِ داوریِ این پاسخ درِ سرور"
          >
            {funnel.asOf
              ? `محاسبه: ${new Date(funnel.asOf * 1000).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })}`
              : 'محاسبه: گزارش نشده'}
          </span>
        </div>
      </div>
      {/* شمارشِ واقعیِ درِ تحویل (#15): Qualified / Pending / Rejected / Unavailable
          / Not-required با عددِ خودِ بازار. این پنج از `coverage`ِ بک‌اند می‌آیند،
          یعنی شمارشِ **کلِ جامعۀ غربالگری** درِ هر گام — پس جمعشان همان Y است
          و نمادی بی‌حکم نمی‌ماند. هدف‌هایِ جزوه (۵۰ و ۱۰ و ۵-۷) فقط مرجعِ کناری‌اند
          و هیچ‌جا گیتِ عبور نیستند.
          `justify-end` با رأیِ مالک (۱۴۰۵-۰۷-۲۰) آمده: درِ RTL لبۀِ پایانِ خطِ
          اصلی سمتِ چپِ صفحه است — سرستون و شمارش‌ها باید آن‌جا بایستند. */}
      <div
        className="flex flex-wrap items-center justify-end gap-x-3 gap-y-1 text-3xs font-bold text-text-muted"
        data-testid="funnel-counts"
      >
        <span className="text-accent-green" data-testid="funnel-count-pass">جامعِ چهار در: {toFaDigits(hc.pass)}</span>
        <span data-testid="funnel-count-pending">در انتظار: {toFaDigits(hc.pending)}</span>
        <span data-testid="funnel-count-reject">رد: {toFaDigits(hc.reject)}</span>
        <span data-testid="funnel-count-unavailable">بی‌داده: {toFaDigits(hc.unavailable)}</span>
        <span data-testid="funnel-count-not-required" title={STATUS_HINT.not_required}>
          لازم نبود: {toFaDigits(hc.not_required)}
        </span>
        {/* دو جامعۀ جدا (رأیِ مالک ۱۴۰۵-۰۷-۱۶): تابلو ≠ غربالگری. Z درِ این خطِ
            خلاصه می‌نشیند نه درِ جدولِ گام‌ها، و بازشونده است تا علتِ هر نماد
            (متوقف / ممنوع / ردیفِ نشستِ کهنه) دیده شود. سه عدد درِ یک خانۀ
            مرزی‌اند و «|» و «/» متنِ جداکننده حذف شد: درِ RTL آن‌ها لبهٔ
            جمله می‌افتادند و خواننده فکر می‌کرد کاراکترِ خراب است. */}
        <span className="flex items-center gap-x-2 rounded-full border border-[var(--hairline)] bg-bg-card/50 px-2 py-0.5">
        <span className="text-text-secondary" data-testid="funnel-universe-market"
              title="تک‌تکِ نمادهایِ امروزِ تابلو (ردیفِ تکراری یکی‌شده)">
          جامعۀ تابلو: {toFaDigits(funnel.marketUniverse)}
        </span>
        <span className="text-accent-blue" data-testid="funnel-universe-screening"
              title="فقط نمادهایِ زنده/واجدِ شرایط — همان که جدولِ چهار گام از آن ساخته می‌شود">
          واجدِ غربالگری: {toFaDigits(funnel.total)}
        </span>
        <button
          type="button"
          data-testid="funnel-universe-excluded"
          aria-expanded={showExcluded}
          onClick={() => setShowExcluded((v) => !v)}
          title="این نمادها رد نشده‌اند و «سنجیده نشده» هم نیستند: اصلاً عضو جامعۀ غربالگری نیستند"
          className={`rounded-full px-1.5 py-0.5 transition-colors ${
            showExcluded ? 'bg-accent-yellow/15 text-accent-yellow' : 'text-text-muted hover:text-text-primary'
          }`}
        >
          خارج از جامعۀ غربالگری: {toFaDigits(funnel.excludedCount)} {showExcluded ? '▲' : '▼'}
        </button>
        </span>
        {/* عددِ رویِ صفحه کهنه است و تازه‌اش در راه — صریح گفته می‌شود، چون
            پاسخِ قبلی عمداً رویِ جدول نگه داشته شده (بی‌صفرفلاش شدنِ جدول). */}
        {refreshing && funnel.total > 0 ? (
          <span
            data-testid="funnel-refreshing"
            className="num rounded-full bg-accent-yellow/15 px-2 py-0.5 text-3xs font-bold text-accent-yellow"
            title="عددِ فعلی از آخرینِ پاسخِ کامل است؛ پاسخِ تازه در راه است"
          >
            در حالِ به‌روزرسانی
          </span>
        ) : null}
      </div>
      {/* چیپ‌هایِ فیلتر + کلیدِ اشتراک/اجتماع، با نامزدِ زندهٔ هر فیلتر — نوارِ
          بالایِ غربالگری (رأیِ مالک ۱۴۰۵-۰۷-۲۰). */}
      <TapeStagePrefs picked={funnel.counts.tape.pass} counts={funnel.filterCounts}
                      filters={screenFilters} />
      {showExcluded ? <OutOfUniversePanel funnel={funnel} onPick={pick} /> : null}
      {/* فهرستِ چهار گام این‌جا حذف شد (رأیِ مالک ۱۴۰۵-۰۷-۱۹): «بالاش همین هست
          که انتخاب می‌کنیم کدام صفحه» — ناوبریِ `FtsProcessStepper` بالایِ همین
          جدول گام را از URL می‌خواند و همین کارت را باز می‌کند. */}
      <div className="flex flex-wrap items-center gap-2">
        {/* «حذفِ پسوندِ عددی» — همان گزینه و همان پیش‌فرضِ تبِ تابلو، اینجا درِ
            سطحِ جامعۀ غربالگری (بک‌اند) اعمال می‌شود تا شمارش‌ها با جدول یکی
            بمانند. نشانهٔ کهنه: اگر موتور غیرِ خواستِ کاربر عمل کند صریح گفته
            می‌شود، نه اینکه عددِ جدول بی‌توضیح جابه‌جا شود. */}
        <button
          type="button"
          onClick={() => setDropSuffix(!dropSuffix)}
          aria-pressed={dropSuffix}
          data-testid="funnel-numeric-suffix-toggle"
          title={dropSuffix
            ? 'روشن (پیش‌فرض): نمادهایِ پسونددار (فولاد۱، خودرو۲) واردِ جامعۀ غربالگری نمی‌شوند؛ درِ «خارج از جامعۀ غربالگری» با همین علت دیده می‌شوند.'
            : 'خاموش: نمادهایِ پسونددار هم مثلِ بقیه داوری می‌شوند.'}
          className={`shrink-0 rounded-lg border px-2 py-1 text-2xs font-bold transition-all ${
            dropSuffix
              ? 'border-accent-blue/50 bg-accent-blue/15 text-accent-blue'
              : 'border-border-c bg-bg-card text-text-muted hover:text-text-primary'
          }`}
        >
          حذفِ پسوندِ عددی
        </button>
        {funnel.dropSuffixApplied !== null && funnel.dropSuffixApplied !== dropSuffix ? (
          <span
            data-testid="funnel-suffix-mismatch"
            className="num rounded-full bg-accent-yellow/15 px-2 py-0.5 text-3xs font-bold text-accent-yellow"
            title="پاسخِ سرور با خواستِ این کلید نمی‌خواند — کلیدِ کشِ تازه را منتظر بمانید"
          >
            اعمال‌نشده درِ سرور
          </span>
        ) : null}
        <span className="ms-auto text-3xs text-text-muted">
          {/* منبعِ فعلیِ زنجیره صریح گفته می‌شود: درِ Custom چیپ‌ها زنجیرۀِ خودِ
              شخص را کم و زیاد می‌کنند، درِ بقیۀ اشخاص چیپ‌هایِ تبِّ تابلو. */}
          ورودیِ غربالگری:{' '}
          {screenFilters.active.length
            ? `${screenFilters.source === 'chain' ? 'زنجیرۀِ خودِ شما' : 'چیپ‌هایِ روشنِ تابلو'} (${toFaDigits(screenFilters.active.length)})`
            : (preset === 'custom' ? 'زنجیرۀِ Custom خالی است' : PRESET_ENTRY[preset].label)} ·{' '}
          از {toFaDigits(funnel.marketUniverse)} نمادِ تابلو، {toFaDigits(funnel.total)} درِ جامعۀ غربالگری
        </span>
        {/* پوششِ رأیِ تکنیکال پنهان نمی‌ماند: «سنجیده نشد» با «رد شده» یکی نیست،
            و «هنوز اسکن نشده» با هر دوی آنها یکی نیست. اسکن درِ پس‌زمینه می‌رود،
            پس سرخطِ پیشرفتِ خودش را می‌گیرد — و وقتی در حالِ ساختن است همین خط
            زنده می‌شود: نقطۀ تپندۀ همان شمارِ ساخته‌شده و صف، تا معلوم باشد
            عددِ جدول در راه است نه تمام‌شده (رأیِ مالک: «زنده نشان بدهد»). */}
        {tech.wanted > 0 ? (
          scan.running || scan.pending > 0 ? (
            <span
              data-testid="funnel-computing"
              className="num inline-flex items-center gap-1.5 rounded-full bg-accent-yellow/15 px-2 py-0.5 text-2xs font-bold text-accent-yellow"
              title={`اسکنِ پس‌زمینه در حالِ کار است: ${toFaDigits(scan.done)} داوری ساخته شده، ${toFaDigits(scan.queued)} نماد در صف.`}
            >
              <span aria-hidden className="h-1.5 w-1.5 shrink-0 animate-pulse rounded-full bg-accent-yellow" />
              در حال محاسبه — ساخته‌شده: {toFaDigits(scan.done)} · در صف: {toFaDigits(scan.queued)}
              {' '}· سنجیده‌شده: {toFaDigits(tech.resolved)} از {toFaDigits(tech.wanted)}
            </span>
          ) : (
            <span
              data-testid="funnel-tech-coverage"
              className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-bold text-text-secondary"
              title="داوریِ تکنیکال برایِ هر نمادی که به این گام رسیده ساخته شده"
            >
              {`تکنیکال سنجیده شده: ${toFaDigits(tech.resolved)} از ${toFaDigits(tech.wanted)}`}
            </span>
          )
        ) : null}
      </div>


      <div className="flex flex-col gap-2">
        {stages.map((s, i) => (shownKeys.includes(s.key) ? (
          <StageCard
            key={s.key}
            stage={s}
            index={i}
            wide={wide}
            showMark={marks[i]}
            onPick={pick}
            active={active === s.key}
            opts={opts}
            emptyWhy={emptyWhy[s.key]}
            collapsed={!only && !openStages[s.key]}
            onToggle={() => setOpenStages((prev) => ({ ...prev, [s.key]: !prev[s.key] }))}
          />
        ) : null))}
      </div>
    </section>
  );
}
