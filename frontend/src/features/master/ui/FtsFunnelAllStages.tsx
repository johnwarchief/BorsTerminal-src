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
import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useVirtualizer } from '@tanstack/react-virtual';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { QUICK_FILTERS, QUICK_LABELS, useTapeStore, type QuickFilter } from '@features/market/stores/tapeStore';
import { absurdHint } from '@features/fundamental/lib/numFmt';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { useFlip } from '@shared/lib/useFlip';
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
  tape: 'نمادهایی که همین نشست دستِ‌کم یکی از پنج فیلترِ جزوه را رد کرده‌اند — عینِ چیپ و بجِ تبِ تابلو.',
  technical: 'ترتیبِ T: اول روند هفتگی، بعد روند روزانه؛ هفتگی نزولی/خنثی = وتو. هر سه شاخهٔ روزانهٔ صعودی/نزولی/خنثی معتبرند؛ جت، پولبک، فیبو، CHoCH و دیگر ستاپ‌ها فقط شواهد و امتیاز کمکی‌اند، نه گیت.',
  fundamental: '',
  handover: 'فقط آنچه بنیادش قبول شده و تا ۱۴ روز مجمعِ عمومی پیشِ رو ندارد. وتوی مجمع زمان‌بندیِ ورود است نه ضعفِ بنیادی — نمره دست‌نخورده می‌ماند و فردا خودش برمی‌گردد.',
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
  | 'ind1' | 'ind2' | 'ind3' | 'ind4' | 'ind5' | 'score' | 'why' | 'basket';

const COL: Record<ColKey, { label: string; title: string; end?: boolean }> = {
  symbol: { label: 'نماد', title: 'کلیک = انتخابِ نماد' },
  last: { label: 'آخرین', title: 'قیمت آخرین معامله', end: true },
  chg: { label: 'تغییر٪', title: 'تغییر درصدی امروز', end: true },
  vol: { label: 'حجم/ماه', title: 'حجم امروز ÷ میانگین ماهانه', end: true },
  pattern: { label: 'نشانه', title: 'فیلترهای جزوه‌ای که این ردیف رد کرده است' },
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
  basket: { label: 'سبد', title: 'افزودن به سبد', end: true },
};

const STAGE_COLS: Record<FunnelStageKey, ColKey[]> = {
  tape: ['symbol', 'last', 'chg', 'vol', 'pattern', 'why'],
  technical: ['symbol', 'weekly', 'daily', 'branch', 'setup', 'techPoints', 'mark', 'why'],
  fundamental: ['symbol', 'ind1', 'ind2', 'ind3', 'ind4', 'ind5', 'score', 'why'],
  // گامِ تحویل دو ستونِ روندِ روزانه و شاخه را کم داشت، در حالی که همان داده
  // درِ پاسخِ سرور هست (`daily`/`branch`) و درِ گامِ تکنیکال هم نشان داده می‌شود؛
  // خوانندۀ «تحویل» باید بدود سهم با کدام شاخه به این گام رسیده، نه فقط اینکه
  // هفتگی صعودی بوده. واژۀ تازه‌ای اضافه نشد: سرستون‌ها همان تعریف‌هایِ موجودند.
  handover: ['symbol', 'weekly', 'daily', 'branch', 'score', 'why', 'basket'],
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
  ind1: 12, ind2: 12, ind3: 12, ind4: 12, ind5: 12, score: 9, basket: 18,
  why: 22,
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
    case 'pattern':
      return <td className="truncate px-2 py-1 text-start text-3xs text-text-muted">{e.patterns.length ? e.patterns.join(' + ') : (mark ? MARK_LABEL[mark] : '—')}</td>;
    case 'weekly':
      return <TrendCell t={e.trendW} />;
    case 'daily':
      return <TrendCell t={e.trendD} />;
    case 'branch':
      return <td className="truncate px-2 py-1 text-start text-3xs text-text-secondary">{e.dailyStrategy || '—'}</td>;
    case 'setup':
      return <td className="truncate px-2 py-1 text-start text-3xs text-text-secondary">{e.setups || '—'}</td>;
    case 'techPoints':
      return <td className="px-2 py-1 text-end text-3xs font-bold text-text-primary"><span className="num">{e.technicalPoints != null ? toFaDigits(e.technicalPoints) : '—'}</span></td>;
    case 'mark':
      return <td className="truncate px-2 py-1 text-end text-3xs font-bold" title={why ?? undefined}>{mark ? MARK_LABEL[mark] : '—'}</td>;
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
        <td className="truncate px-2 py-1 text-start text-3xs text-text-secondary" title={why ?? undefined}
            data-testid={`funnel-why-${e.symbol}`}>
          {why || (mark ? MARK_LABEL[mark] : '—')}
        </td>
      );
    case 'basket':
      return <td className="px-2 py-1 text-end"><SymbolBasketAction symbol={e.symbol} /></td>;
    default:
      return null;
  }
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
}: {
  stage: FunnelStage;
  index: number;
  wide: number;
  showMark: 'tech' | 'fund' | 'handover' | null;
  onPick: (s: string) => void;
  active: boolean;
  opts: FunnelOptions;
  emptyWhy: string | null;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const rows = stage.entries;
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

  const scrollRef = useRef<HTMLDivElement | null>(null);
  const virt = useVirtualizer({
    count: rows.length,
    getScrollElement: () => scrollRef.current,
    estimateSize: () => ROW_H,
    overscan: 8,
    initialRect: { width: 0, height: 280 },
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
  const unseen = rows.length + stage.pending.length - stage.ruled;

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
        <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-bold text-text-secondary"
              title="تک‌تکِ نمادهایِ جامعۀ غربالگری درِ این گام دیده می‌شوند — نه فقط عبوری‌ها">
          {toFaDigits(stage.ruled)} نماد
        </span>
        {stage.dropped > 0 ? (
          <span className="num rounded-full bg-accent-red/15 px-2 py-0.5 text-2xs font-black text-accent-red">
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
            : `${toFaDigits(unseen)} نماد درِ این گام حکم ندارد — نقصِ معماری، نه حالتِ عادی`}
        >
          حکم: {toFaDigits(stage.ruled)}{unseen === 0 ? ' = کلِ جامعۀ غربالگری' : ` ≠ ${toFaDigits(stage.ruled + unseen)}`}
        </span>
        {/* مالک: «تنظیماتِ مرحلۀ بنیادی رو روی نوارِ جدول بنیادی بذار». پیش‌تر یک
            نوارِ سراسری زیرِ چهار مرحله بود؛ هر مرحله پیچ‌هایِ خودش را رویِ
            نوارِ خودش می‌گیرد — همان کاری که کلیدِ تکنیکال از قبل می‌کرد. */}
        {stage.key === 'fundamental' ? (
          <FundStagePrefs passed={stage.summary.pass} techScreens={techScreens} />
        ) : null}
        {stage.key === 'tape' ? <TapeStagePrefs picked={stage.summary.pass} /> : null}
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
                    ? 'border-accent-amber bg-accent-amber/15 text-accent-amber'
                    : 'border-border-c bg-bg-card text-text-muted hover:border-accent-amber/60'
                }`}
              >
                {on ? TECH_SCREEN_LABEL.on : TECH_SCREEN_LABEL.off}
              </button>
            ))}
          </span>
        ) : null}
        <span className="ms-auto max-w-[46ch] text-3xs leading-4 text-text-muted">{rule}</span>
      </header>

      <div ref={bodyRef} className="relative max-h-[280px] overflow-y-auto" data-testid={`funnel-scroll-${stage.key}`}>
        {rows.length === 0 ? (
          <p className="px-3 py-4 text-xs text-text-muted" data-testid={`funnel-empty-${stage.key}`}>
            {emptyWhy ?? 'هیچ نمادی از این مرحله عبور نکرد.'}
          </p>
        ) : (
          <table className="w-full table-fixed border-collapse text-xs">
            <ColGroup cols={cols} />
            <thead className="sticky top-0 bg-bg-primary/95 text-3xs text-text-muted backdrop-blur-sm">
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
                            stageKey={stage.key} onPick={onPick} />
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
              ? `متوقف درِ تحویل — نه رد شده، نه آماده (${toFaDigits(stage.pending.length)})`
              : `در انتظارِ حکم — موتور نگاه کرد و نظر نداد (${toFaDigits(stage.pending.length)})`}
          </p>
          <div ref={pendingRef} className="max-h-[160px] overflow-y-auto">
            <table className="w-full table-fixed border-collapse text-xs">
              {/* سرستونِ همان مرحله، با همان colgroup: ردیف‌هایِ انتظار هم باید
                  بدانند کدام ✓/✗ کدام شاخص است، و ستون‌هایِ دو جدول رویِ هم
                  بنشینند وگرنه «سرستونِ دوم» کج می‌آید. */}
              <ColGroup cols={cols} />
              <thead className="sticky top-0 text-3xs text-text-muted">
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
                    />
                  );
                })}
                {padBottomP > 0 ? <tr aria-hidden style={{ height: padBottomP }} /> : null}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function StageRow({
  entry,
  cols,
  showMark,
  stageKey,
  onPick,
}: {
  entry: FunnelEntry;
  cols: ColKey[];
  showMark: 'tech' | 'fund' | 'handover' | null;
  /** دلیلِ هر ردیف از همان گامی است که کارت نمایشش می‌دهد — درِ «تابلوخوانی»
   *  هم باید نوشته باشد کدام فیلتر ردش کرد؛ پیشِ این showMark آن را null می‌گذاشت
   *  و ستونِ دلیل درِ آن گام همیشه «—» می‌ماند. */
  stageKey: FunnelStageKey;
  onPick: (s: string) => void;
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
      className="border-b border-border-c/40 last:border-0 hover:bg-bg-card/70"
      title={rowTitle}
    >
      <td className="px-2 py-1 text-start">
        <button
          type="button"
          onClick={() => onPick(entry.symbol)}
          className="flex max-w-[16ch] items-center gap-1 truncate font-black text-text-primary hover:text-accent-blue"
        >
          {mark ? <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${MARK_DOT[mark]}`} /> : null}
          <span className="truncate">{entry.symbol}</span>
          {entry.assemblyVeto ? (
            <span
              data-testid={`funnel-assembly-veto-${entry.symbol}`}
              className="shrink-0 rounded border border-accent-red/40 bg-accent-red/15 px-1 text-[9px] font-bold text-accent-red"
              title={entry.assemblyWhy}
            >
              وتوی مجمع
            </span>
          ) : null}
        </button>
      </td>
      {cols.filter((k) => k !== 'symbol').map((k) => (
        <Cell key={k} k={k} e={entry} mark={mark} why={why} />
      ))}
    </tr>
  );
}

/**
 * چیپ‌هایِ پنج فیلترِ جزوه رویِ نوارِ خودِ مرحلۀ «تابلو» — «نحوۀ غربالگری» همین
 * است: کدامِ پنج درِ ورودی باز باشند. این همان `quickFilters` تبِ تابلو است، پس
 * دو منبعِ حقیقت نیست و از قیف روشن شدنش هم عوضی در نمی‌آید.
 */
function TapeStagePrefs({ picked }: { picked: number }) {
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const toggle = useTapeStore((s) => s.toggleQuickFilter);
  return (
    <span
      data-testid="funnel-tape-prefs"
      className="flex flex-wrap items-center gap-1"
      role="group"
      aria-label="فیلترهای ورودی غربالگری"
    >
      {QUICK_FILTERS.map((f: QuickFilter) => {
        const on = quickFilters.includes(f);
        return (
          <button
            key={f}
            type="button"
            data-testid={`funnel-tape-chip-${f}`}
            aria-pressed={on}
            onClick={() => toggle(f)}
            title={on ? 'روشن — این فیلتر ورودیِ غربالگری را می‌سازد' : 'خاموش — با این فیلتر نمادها کمتر می‌شوند'}
            className={`rounded-md border px-1.5 py-0.5 text-2xs font-bold transition-colors ${
              on
                ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                : 'border-border-c bg-bg-card text-text-muted hover:border-accent-blue/60'
            }`}
          >
            {QUICK_LABELS[f]}
          </button>
        );
      })}
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
      on ? 'border-accent-amber bg-accent-amber/15 text-accent-amber' : 'border-border-c bg-bg-card text-text-muted hover:border-accent-amber/60'
    }`;

  return (
    <div
      data-testid="funnel-prefs"
      className="flex flex-wrap items-center gap-x-2 gap-y-1"
    >
      <span className="text-2xs font-black text-text-secondary" title={`پیش‌فرضِ جزوه: ${toFaDigits(DEFAULT_FUND_FLOOR)} از ${toFaDigits(FUND_FLOOR_MAX)}`}>
        کفِ نمره
      </span>
      <span className="flex items-center gap-1" role="group" aria-label="کفِ نمرۀ پنج‌شاخصه">
        {Array.from({ length: FUND_FLOOR_MAX }, (_, i) => i + 1).map((n) => (
          <button
            key={n}
            type="button"
            data-testid={`funnel-floor-${n}`}
            aria-pressed={fundFloor === n}
            onClick={() => setFundFloor(n)}
            className={`num h-6 w-6 rounded-md border text-2xs font-black transition-colors ${chip(fundFloor === n)}`}
            title={n === DEFAULT_FUND_FLOOR ? 'پیش‌فرضِ جزوه' : undefined}
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
        <button type="button" data-testid="funnel-prefs-reset" onClick={reset} className="text-3xs font-bold text-text-muted underline hover:text-accent-amber">
          بازگشت به جزوه
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
                <span className="num ms-auto shrink-0 text-text-secondary">
                  {e.last ? fmtInt(e.last) : '—'}
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
  onStageSelect,
}: {
  preset?: TreePreset;
  /** حالتِ مسیریافته: فقط کارتِ همین مرحله؛ فهرستِ چهارتایی درِ گام چهارم می‌ماند */
  only?: FunnelStageKey;
  /** درِ حالتِ مسیریافته: تب به‌جای اسکرول، به routeِ همان مرحله می‌رود */
  onStageSelect?: (stage: FunnelStageKey) => void;
}) {
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const navigate = useNavigate();
  const [snap] = useState(readFunnelSnap);
  // «خارج از جامعۀ غربالگری» بسته است تا جدولِ گام‌ها با این ردیف‌ها شلوغ
  // نشود؛ خطِ خلاصه خودش Z را می‌گوید و همین دکمه علتِ تک‌تکشان را باز می‌کند.
  const [showExcluded, setShowExcluded] = useState(false);
  const [activeState, setActive] = useState<FunnelStageKey>(() => snap?.stage ?? 'tape');
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
  const { funnel, mode, tape, tech, scan, refreshing, quickFilters, opts } = useFtsFunnel(preset);
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
    tape: funnel.total ? null : 'هیچ نمادی درِ جامعۀ غربالگریِ این نشست نبود (تابلو یا وضعیتِ رسمیِ نمادها اجازهٔ غربال نداد).',
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
      <div className="flex flex-wrap items-center gap-2">
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
            title="تازگیِ خوراکِ تابلو — دادهٔ آخرینِ نشست جایِ زنده خوانده نمی‌شود"
          >
            {TAPE_FRESHNESS_LABEL[tape]}
          </span>
        </div>
      </div>
      {/* شمارشِ واقعیِ درِ تحویل (#15): Qualified / Pending / Rejected / Unavailable
          / Not-required با عددِ خودِ بازار. این پنج از `coverage`ِ بک‌اند می‌آیند،
          یعنی شمارشِ **کلِ جامعۀ غربالگری** درِ هر گام — پس جمعشان همان Y است
          و نمادی بی‌حکم نمی‌ماند. هدف‌هایِ جزوه (۵۰ و ۱۰ و ۵-۷) فقط مرجعِ کناری‌اند
          و هیچ‌جا گیتِ عبور نیستند. */}
      <div
        className="flex flex-wrap items-center gap-x-3 gap-y-1 text-3xs font-bold text-text-muted"
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
              title="تک‌تکِ نمادهایِ این نشستِ تابلو (ردیفِ تکراری یکی‌شده)">
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
            در حالِ تازه‌سازی
          </span>
        ) : null}
      </div>
      {showExcluded ? <OutOfUniversePanel funnel={funnel} onPick={pick} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex flex-wrap items-center gap-1" role="tablist">
          {stages.map((s, i) => (
            <button
              key={s.key}
              type="button"
              role="tab"
              aria-selected={active === s.key}
              data-testid={`funnel-step-${s.key}`}
              onClick={() => {
                if (onStageSelect) {
                  onStageSelect(s.key);
                  return;
                }
                setActive(s.key);
                // تب قیف فقط هایلایت نبود؛ کاربر انتظار داشت همان مرحله را ببیند
                const card = document.querySelector(`[data-testid="funnel-stage-${s.key}"]`) as HTMLElement | null;
                if (card) {
                  card.style.scrollMarginTop = '3.2rem';
                  const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
                  card.scrollIntoView?.({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
                }
              }}
              className={`rounded-full border px-2.5 py-1 text-2xs font-bold transition-all ${
                active === s.key
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-secondary hover:border-accent-blue/60'
              }`}
            >
              {toFaDigits(i + 1)}. {STAGE_TITLE[s.key]}
              <span className="num ms-1 opacity-80" title={`عبور از این گام: ${toFaDigits(s.summary.pass)} از ${toFaDigits(s.ruled)} نمادِ جامعۀ ورودی`}>
                ({toFaDigits(s.summary.pass)})
              </span>
            </button>
          ))}
        </div>
        <span className="ms-auto text-3xs text-text-muted">
          ورودیِ غربالگری: {quickFilters.length ? 'چیپ‌هایِ روشنِ تبِ تابلو' : PRESET_ENTRY[preset].label} ·{' '}
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
          />
        ) : null))}
      </div>
    </section>
  );
}
