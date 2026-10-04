// features/technical/components/FtsBadgeStrip.tsx -- نوار نشان های تحلیل FTS سمت سرور
// معادل بج استریپ v10 در tech_rtv.js: روند D/W/M، هم راستایی، فیبو، جت، CHoCH،
// شکار نقطه، دابل باتم، جعبه رنج و حکم موتور خروج. وضعیت خالی صادقانه نشان داده می شود.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';

export const TREND_FA: Record<string, string> = {
  up: 'صعودی',
  down: 'نزولی',
  range: 'رنج',
  na: 'نامشخص',
};

export function trendTone(t: string | null | undefined): 'green' | 'red' | 'yellow' | 'gray' {
  if (t === 'up') return 'green';
  if (t === 'down') return 'red';
  if (t === 'range') return 'yellow';
  return 'gray';
}

export const VERDICT_META: Record<string, { label: string; tone: 'red' | 'yellow' | 'gray' }> = {
  stop: { label: 'حد ضرر', tone: 'red' },
  exit: { label: 'خروج', tone: 'red' },
  caution: { label: 'احتیاط', tone: 'yellow' },
  hold: { label: 'نگهداری', tone: 'gray' },
  // موتورِ کم‌سابقه رأیِ «خروجی ندارد» نمی‌دهد؛ این «سنجیده نشد» است
  unknown: { label: 'خروج: نسنجیده', tone: 'gray' },
};

export function verdictMeta(v: string | null | undefined): { label: string; tone: 'red' | 'yellow' | 'gray' } {
  return VERDICT_META[v ?? 'unknown'] ?? VERDICT_META.unknown;
}

/** جت استریپ: وضعیت ستاپ شکست سقف ایستا یا ATH — فقط کندلِ آخر.
 *  با وتوی هفتگی برچسب «فعال» گمراه‌کننده است، پس خودِ وتو درِ بج نوشته می‌شود. */
export function jetBadges(f: FtsAnalysisData): { label: string; tone: 'green' | 'blue' | 'gray'; title: string }[] {
  const jet = f.jet;
  if (!jet) return [];
  if (jet.active !== true) return [];
  const vetoed = f.trend?.matrix?.decision === 'REJECT';
  const isAth = jet.ath === true;
  const pct = jet.pct_above_res;
  return [
    {
      label: vetoed ? 'جت (وتوی هفتگی)' : isAth ? 'جت (ATH)' : 'جت فعال',
      tone: vetoed ? 'blue' : 'green',
      title: vetoed
        ? 'شکستِ امروز رخ داده، ولی درخت FTS با این تایم هفتگی فرصت ورود نمی‌دهد'
        : isAth
          ? 'شکست سقف تاریخی با تایید بدنه روزانه'
          : pct != null
            ? `شکست مقاومت ${toFaDigits(jet.resistance?.toFixed(0) ?? '-')} با ${toFaDigits(pct.toFixed(1))}٪ فاصله`
            : 'شکست مقاومت با تایید بدنه روزانه',
    },
  ];
}

/** نشان های روند چند تایم فریمی + هم راستایی */
export function trendBadges(f: FtsAnalysisData): { label: string; value: string; tone: 'green' | 'red' | 'yellow' | 'gray'; title: string }[] {
  const t = f.trend;
  const out: { label: string; value: string; tone: 'green' | 'red' | 'yellow' | 'gray'; title: string }[] = [];
  const legs: [string, 'D' | 'W' | 'M'][] = [
    ['روند روزانه', 'D'],
    ['روند هفتگی', 'W'],
    ['روند ماهانه', 'M'],
  ];
  for (const [label, legKey] of legs) {
    const leg = t?.[legKey] ?? null;
    const tr = leg?.trend ?? 'na';
    out.push({ label, value: TREND_FA[tr] ?? TREND_FA.na, tone: trendTone(tr), title: `${label}: ${TREND_FA[tr] ?? '-'}` });
  }
  const align = t?.alignment;
  if (align === 'up' || align === 'down') {
    out.push({
      label: 'هم راستایی',
      value: align === 'up' ? 'صعودی' : 'نزولی',
      tone: align === 'up' ? 'green' : 'red',
      title: 'هر سه تایم فریم هم جهت هستند',
    });
  }
  return out;
}

export function FtsBadgeStrip({
  data,
  empty,
  error,
}: {
  data: FtsAnalysisData | null | undefined;
  empty: boolean;
  /** پیامِ شکستِ موتور — بی‌این، نشان‌ها روی «error» تا ابد «در حال دریافت…» می‌ماندند */
  error?: string | null;
}) {
  if (empty) {
    return (
      <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-3 text-xs text-text-muted" data-testid="fts-badges-empty">
        <Badge tone="gray">FTS</Badge>
        <span>تحلیل سمت سرور برای این نماد موجود نیست (تاریخچه خالی)</span>
      </div>
    );
  }
  if (error) {
    return (
      <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-3 text-xs text-text-muted" data-testid="fts-badges-error">
        <Badge tone="red">FTS</Badge>
        <span>تحلیل FTS نرسید — {error}</span>
      </div>
    );
  }
  if (!data) {
    return (
      <div className="glass-panel flex flex-wrap items-center gap-2 rounded-2xl p-3 text-xs text-text-muted" data-testid="fts-badges-loading">
        <Badge tone="gray">FTS</Badge>
        <span>در حال دریافت نشان های تحلیل...</span>
      </div>
    );
  }

  const items: { label: string; value?: string; tone: 'green' | 'red' | 'yellow' | 'blue' | 'gray'; title: string }[] = [];

  for (const b of trendBadges(data)) {
    items.push({ label: b.label, value: b.value, tone: b.tone, title: b.title });
  }

  const fib = data.fib;
  // فیبو «زمینه» است نه سیگنالِ ورود (سنجشِ دورِ I: داخلِ کمربند بودن edge ندارد)
  if (fib?.zone_33_40?.in_zone) {
    items.push({ label: 'موقعیت فیبو', value: '۳۳-۴۰٪', tone: 'gray', title: 'قیمت داخل کمربند اصلاح ۳۳ تا ۴۰ درصد است — زمینه، نه سیگنالِ ورود' });
  }
  if (fib?.zone_618_70?.in_zone) {
    items.push({ label: 'موقعیت فیبو', value: '۶۱.۸-۷۰٪', tone: 'gray', title: 'قیمت داخل کمربند طلایی اصلاح است — زمینه، نه سیگنالِ ورود' });
  }

  for (const b of jetBadges(data)) {
    items.push({ label: b.label, tone: b.tone, title: b.title });
  }

  const choch = data.choch;
  if (choch?.bullish) {
    items.push({ label: 'CHoCH', value: 'صعودی', tone: 'green', title: 'شکست صعودی ساختار؛ برگشت روند' });
  }
  if (choch?.bearish) {
    items.push({ label: 'CHoCH', value: 'نزولی', tone: 'red', title: 'شکست نزولی ساختار؛ هشدار خروج' });
  }

  const ph = data.point_hunt;
  if (ph?.active === true) {
    items.push({
      label: 'شکار نقطه',
      value: `${toFaDigits(ph.touches ?? 0)} لمس`,
      tone: 'blue',
      // «کجا» = کفِ کانال (anchor)، «کِی» = کندلِ تریگر؛ این دو درِ موتور جدا هستند
      title:
        `کف دایامتریک کانال دست کم سه بار لمس شده و همین کندل بازگشت؛ تریگر: ${ph.trigger_date ?? '—'}` +
        ` (لنگرِ کف: ${ph.floor_date ?? '—'})`,
    });
  }

  if (data.double_bottom?.active) {
    items.push({ label: 'دابل باتم', tone: 'green', title: 'شکست یقه دابل باتم تایید شد' });
  }

  if (data.range_box?.active) {
    items.push({ label: 'شکست جعبه', tone: 'green', title: 'پایانی بالای سقف جعبه رنج بسته شد' });
  }

  const mat = data.trend?.matrix;
  if (mat?.decision === 'REJECT') {
    items.push({
      label: 'ماتریس روند',
      value: 'ممنوعیت ورود',
      tone: 'red',
      title: mat.desc ?? 'تایم هفتگی نزولی یا خنثی؛ وتوی کامل ورود طبق FTS',
    });
  } else if (mat?.decision === 'PERMITTED') {
    const setupFa =
      mat.setup === 'JET_OR_PULLBACK_HOLD'
        ? 'نگهداری/جت'
        : mat.setup === 'FIB_CHOCH_STEP_ENTRY'
          ? 'پله‌ای فیبو/CHoCH'
          : 'نوسان کف رنج';
    items.push({
      label: 'ماتریس روند',
      value: setupFa,
      tone: 'green',
      title: mat.desc ?? 'ورود مجاز بر اساس ماتریس هفتگی/روزانه FTS',
    });
  }

  const hg = data.hourglass;
  if (hg?.active) {
    items.push({
      label: 'استراتژی ساعت شنی',
      value: 'اهرم ۲x-۴x',
      tone: 'green',
      title: hg.desc ?? 'اهرم شتاب‌دهنده ساعت شنی فعال: قیمت هفتگی زیر MA52 و RSI هفتگی اشباع فروش',
    });
  }

  const ex = data.exit_engine;
  const vm = verdictMeta(ex?.verdict);
  items.push({
    label: 'موتور خروج',
    value: vm.label,
    tone: vm.tone,
    title: ex?.signals?.length ? `لایه های فعال: ${ex.signals.join('، ')}` : 'هیچ لایه خروجی فعال نیست',
  });

  return (
    <div className="glass-panel flex flex-wrap items-center gap-1.5 rounded-2xl p-3" data-testid="fts-badges" role="status" aria-label="نشان های تحلیل FTS">
      {items.map((it, i) => (
        <Badge key={`${it.label}-${i}`} tone={it.tone}>
          <span title={it.title}>
            {it.label}
            {it.value ? <span className="num"> {it.value}</span> : null}
          </span>
        </Badge>
      ))}
    </div>
  );
}
