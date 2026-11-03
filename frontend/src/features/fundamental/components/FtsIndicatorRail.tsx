// features/fundamental/components/FtsIndicatorRail.tsx -- پنج شاخص بنیادی درِ پنلِ چپ
//
// چرا این فایل متولد شد (بندِ ۲ مأموریتِ رابط، 1405-07-24). پنلِ فیزیکیِ سمتِ چپ
// (`widgets/SymbolInspector.tsx`) پنج شاخص را درِ یک ردیفِ **افقیِ چیپ** می‌ریخت:
// برچسبِ کوتاه + عدد، بی‌علت، بی‌کلیک، و با `flex-wrap` که درِ عرضِ ۲۴۰ پیکسل دو
// تا سه خط می‌گرفت. حالا پنج کارتِ عمودیِ جمع‌وجور است — همان پنج مقدار، همان
// سه‌حالۀ حکم، به‌علاوه یک خطِ علت — و کلیکِ هر کارت **همان** drill-downِ موجود
// را درِ `#/fundamental/<symbol>` باز می‌کند (پارامترِ `?drill=`)، نه یک رابطِ
// جزئیاتِ دوم.
//
// دو تصمیمِ عمدی:
//  1) منبعِ داده `useFtsCard(symbol)` است (خروجیِ canonicalِ تک‌نمادیِ
//     `/api/fundamental/{symbol}` — همان چیزی که کارتِ بنیادی و FtsDrillDown
//     می‌خوانند). هیچ محاسبۀ دومی درِ رابط ساخته نمی‌شود؛ نه آستانه، نه
//     «ایده‌آل»، نه رشدِ ترکیبی. ردیفِ غربالگری (`fallback`) فقط تا پیشِ رسیدنِ
//     کارت جانشینِ همان فیلدهاست — و آن دو با گیتِ
//     `dev/fts_screener_card_parity_v10` هم‌رأی نگه داشته می‌شوند، پس دو حقیقت
//     نیست.
//  2) حکمِ «نظر نمی‌دهد» رأی نیست: `pass == null` ⇒ «—» با علتِ همان محور از
//     `gapReason` (رأیِ مالک ۱۴۰۵-۰۷-۰۳). هیچ nullی به صفر یا سرخ تبدیل نمی‌شود.
import { Link } from 'react-router';
import { FTS_LABEL } from '@shared/lib/ftsLabels';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { useFtsCard, type FtsCard } from '../api/useFtsCard';
import type { FtsScreenRow } from '../api/useFtsScreen';
import { gapLabel, gapTooltip } from '../lib/gapReason';
import { QUALITY_WORD, qualityFrom, type Quality } from './FtsCard';

type DrillKey = '1' | '2' | '3' | '4' | '5';

/** هرچه رابط تا رسیدنِ کارتِ canonical می‌تواند جانشین بخواند: ردیفِ غربالگری
 *  (`/api/screener`) یا نمادِ دیدۀ `screen` درِ ردیفِ قیف. فقط همان فیلدهایِ
 *  لازم — و هیچ‌کدام محاسبۀ دوم نیستند. */
export type RailFallbackRow = Partial<Pick<
  FtsScreenRow,
  'rev_growth' | 'eps_series' | 'eps_last' | 'eps_years_available' | 'eps_years_required'
  | 'gross_margin' | 'sales_to_mcap' | 'pricing_mode'
  | 'i1_pass' | 'i2_pass' | 'i3_pass' | 'i4_pass' | 'i5_pass'
>>;

/** ترتیبِ پنج محور = ترتیبِ جزوۀ ص ۱؛ کلیدِ `passes` همان نامِ موتور است. */
const AXES: { key: string; drill: DrillKey; col: string }[] = [
  { key: '1_growth', drill: '1', col: 'i1' },
  { key: '2_eps_trend', drill: '2', col: 'i2' },
  { key: '3_gross_margin', drill: '3', col: 'i3' },
  { key: '4_sales_to_mcap', drill: '4', col: 'i4' },
  { key: '5_industry', drill: '5', col: 'i5' },
];

const CARD_TONE: Record<Quality, string> = {
  ideal: 'border-cyan-400/45 bg-cyan-400/[0.07] hover:border-cyan-400/80',
  ok: 'border-accent-green/40 bg-accent-green/[0.06] hover:border-accent-green/75',
  below: 'border-accent-red/40 bg-accent-red/[0.06] hover:border-accent-red/75',
  na: 'border-border-c/70 bg-bg-card/60 hover:border-border-accent',
};

const WORD_TONE: Record<Quality, string> = {
  ideal: 'text-cyan-300',
  ok: 'text-accent-green',
  below: 'text-accent-red',
  na: 'text-text-muted',
};

/** نسبتِ ۰٫۴۱ → «۴۱٫۰٪» — همان عرضِ رأیِ مالک ۱۴۰۵-۰۷-۲۰ درِ کارتِ بنیادی
 *  (عددِ موتور دست‌نخورده؛ فقط ×۱۰ و ٪). */
function ratioPct(v: number | null | undefined): string {
  return v == null || !Number.isFinite(v) ? '—' : `${toFaDigits((v * 100).toFixed(1))}٪`;
}

function signedPct(v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return '—';
  return `${v >= 0 ? '+' : '−'}${toFaDigits(Math.abs(v).toFixed(1))}٪`;
}

type Fact = { value: string; pass: boolean | null | undefined; quality: Quality; note: string };

/** مقدار + حکم + علتِ یک محوره، از خودِ کارت؛ جانشینِ ردیفِ غربالگری فقط تا
 *  رسیدنِ کارت. هیچ عددی اینجا ساخته یا ترکیب نمی‌شود. */
function axisFact(i: number, card: FtsCard | undefined, row: RailFallbackRow | null | undefined): Fact {
  const axis = AXES[i].key;
  const p = card?.passes?.[axis];
  const gap = () => (p == null ? gapLabel(axis) : '');
  if (i === 0) {
    const mon = card?.indicators?.['1']?.monetary;
    const vol = card?.indicators?.['1']?.volume;
    /** رأیِ ۱۶: شکافِ داده رأی نیست — کارتِ بنیادی هم همین را `null` می‌خواند
     *  (`monetary.data_gap`)، پس رابط دوم نمی‌سازد. */
    const pass = card ? (mon?.data_gap ? null : p) : row?.i1_pass;
    const v = mon?.monetary_pct ?? row?.rev_growth ?? null;
    const floor = mon?.threshold ?? null;
    return {
      value: signedPct(v),
      pass,
      quality: qualityFrom(pass),
      note: pass == null ? (gap() || 'رشد ریالی سنجیده نشد')
        : vol?.applicable === false ? 'رشد تولیدی بر این شرکت اعمال نمی‌شود'
          : floor == null ? 'کفِ آستانه از موتور نرسید' : `کفِ ${toFaDigits(floor)}٪`,
    };
  }
  if (i === 1) {
    const ind = card?.indicators?.['2'];
    const series = ind?.eps_series ?? row?.eps_series ?? null;
    const last = series?.length ? series[series.length - 1] : (row?.eps_last ?? null);
    const pass = card ? p : row?.i2_pass;
    const av = ind?.years_available ?? row?.eps_years_available ?? series?.length ?? null;
    const rq = ind?.years_required ?? row?.eps_years_required ?? null;
    return {
      value: last == null ? '—' : fmtInt(last),
      pass,
      quality: qualityFrom(pass),
      note: pass == null ? (gap() || 'سابقۀ سه‌سالۀ کامل نیست')
        : av == null ? 'سه سالِ متوالیِ حسابرسی‌شده'
          : `${toFaDigits(av)}${rq == null ? '' : `/${toFaDigits(rq)}`} سال`,
    };
  }
  if (i === 2) {
    const ind = card?.indicators?.['3'];
    const v = ind?.margin_pct ?? row?.gross_margin ?? null;
    const pass = card ? p : row?.i3_pass;
    const ideal = ind?.band === 'ideal' || ind?.optimal === true;
    return {
      value: v == null ? '—' : fmtPct(v),
      pass,
      quality: qualityFrom(pass, ideal),
      note: pass == null ? (gap() || 'حاشیۀ ناخالص ثبت نشده')
        : ind?.threshold == null ? 'حاشیهٔ ناخالص ÷ درآمد عملیاتی'
          : `≥ ${toFaDigits(ind.threshold)}٪`,
    };
  }
  if (i === 3) {
    const ind = card?.indicators?.['4'];
    const v = ind?.sales_to_mcap ?? row?.sales_to_mcap ?? null;
    // معافیتِ صنعتی (F-04) رأیِ «رد» نیست؛ موتور آن را null می‌فرستد و علت را
    // در `gap_cause` می‌نویسد — رابط همان را نشان می‌دهد، قضاوتِ تازه نمی‌کند.
    const pass = card ? p : row?.i4_pass;
    return {
      value: ratioPct(v),
      pass,
      quality: qualityFrom(pass),
      note: pass == null
        ? (ind?.gap_cause || gap() || 'فروش سالانه یا ارزش بازار نداشت')
        : ind?.sales_threshold == null ? 'فروش ÷ ارزش بازار'
          : `≥ ${ratioPct(ind.sales_threshold)}`,
    };
  }
  const ind = card?.indicators?.['5'];
  const v = ind?.label ?? ind?.regime_label ?? row?.pricing_mode ?? null;
  const pass = card ? p : row?.i5_pass;
  return {
    value: v == null || v === '' ? '—' : String(v),
    pass,
    quality: qualityFrom(pass),
    note: pass == null
      ? (gap() || 'صنعت یا نرخ‌گذاری معلوم نیست')
      : (ind?.sector ?? card?.sector ?? 'رژیم قیمت‌گذاری صنعت'),
  };
}

export default function FtsIndicatorRail({ symbol, fallbackRow }: {
  symbol: string;
  fallbackRow?: RailFallbackRow | null;
}) {
  const card = useFtsCard(symbol);
  const data = card.data;
  const facts = AXES.map((_a, i) => axisFact(i, data, fallbackRow));
  const href = (drill: DrillKey) =>
    `/fundamental/${encodeURIComponent(symbol)}?drill=${drill}`;
  return (
    <div data-testid="inspector-fts-cards" className="flex flex-col gap-1">
      {AXES.map((a, i) => {
        const f = facts[i];
        const label = FTS_LABEL[a.key];
        return (
          <Link
            key={a.key}
            to={href(a.drill)}
            data-testid={`inspector-card-${a.col}`}
            title={`${label} — کلیک: نمودار و جزئیات درِ تبِ بنیادی`}
            className={`block rounded-md border px-1.5 py-1 text-start transition-colors ${CARD_TONE[f.quality]}`}
          >
            <div className="flex items-start justify-between gap-1">
              <span className="min-w-0 text-3xs font-bold leading-tight text-text-secondary">
                {label}
              </span>
              <span data-testid={`inspector-card-verdict-${a.col}`}
                    className={`shrink-0 text-3xs font-black leading-tight ${WORD_TONE[f.quality]}`}>
                {QUALITY_WORD[f.quality]}
              </span>
            </div>
            <div className="mt-0.5 flex items-end justify-between gap-1.5">
              <span data-testid={`inspector-ind-${a.col}`} className="num text-2xs font-black leading-none">
                {f.value}
              </span>
              <span
                className="min-w-0 max-w-[58%] text-3xs leading-tight text-text-muted line-clamp-2"
                title={f.pass == null ? gapTooltip(a.key) : undefined}
              >
                {f.note}
              </span>
            </div>
          </Link>
        );
      })}
      {card.isPending && !data ? (
        <span data-testid="inspector-fts-cards-pending"
              className="text-3xs leading-tight text-text-muted">
          کارتِ بنیادی هنوز نخوانده شده — تا رسیدنش همان مقادیرِ جدولِ غربالگری
          نشان داده می‌شود و هیچ عددی از خودِ ساختگی نیست.
        </span>
      ) : null}
      {card.isError ? (
        <span data-testid="inspector-fts-cards-error"
              className="text-3xs leading-tight text-accent-red">
          کارتِ بنیادی خوانده نشد؛ مقادیرِ زیر از ردیفِ غربالگری‌اند و علتِ هر
          محور درِ تبِ بنیادی است.
        </span>
      ) : null}
    </div>
  );
}
