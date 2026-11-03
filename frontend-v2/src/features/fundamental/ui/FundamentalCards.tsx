import clsx from 'clsx';
import { faNum, fmtInt, toFaDigits } from '@shared/lib/fa';
import { useFtsCard, type FtsCard } from '../api/useFtsCard';

export type Quality = 'ideal' | 'ok' | 'below' | 'na';

export const QUALITY_WORD: Record<Quality, string> = {
  ideal: 'ایده‌آل',
  ok: 'قبول',
  below: 'رد',
  na: 'بی‌نظر',
};

const CHIP: Record<Quality, { word: string; tone: string }> = {
  ideal: { word: QUALITY_WORD.ideal, tone: 'text-cyan-300' },
  ok: { word: QUALITY_WORD.ok, tone: 'text-up' },
  below: { word: QUALITY_WORD.below, tone: 'text-down' },
  na: { word: QUALITY_WORD.na, tone: 'text-text-3' },
};

export interface FundamentalFact {
  key: string;
  label: string;
  value: string;
  quality: Quality;
  note: string;
}

function qualityOf(pass: boolean | null | undefined, ideal = false): Quality {
  if (pass == null) return 'na';
  if (pass && ideal) return 'ideal';
  return pass ? 'ok' : 'below';
}

function signedPct(input: number | null | undefined): string {
  if (input == null || !Number.isFinite(input)) return '—';
  return `${input >= 0 ? '+' : '−'}${faNum(Math.abs(input), 1)}٪`;
}

function ratioPct(input: number | null | undefined): string {
  if (input == null || !Number.isFinite(input)) return '—';
  return `${faNum(input * 100, 1)}٪`;
}

export function fundamentalFacts(card: FtsCard): FundamentalFact[] {
  const passes = card.passes ?? {};
  const indicators = card.indicators ?? {};
  const out: FundamentalFact[] = [];

  const one = indicators['1'];
  const monetary = one?.monetary;
  const pass1 = monetary?.data_gap ? null : passes['1_growth'];
  out.push({
    key: '1_growth',
    label: '۱. رشد فروش کدال',
    value: signedPct(monetary?.monetary_pct),
    quality: qualityOf(pass1),
    note: pass1 == null
      ? (monetary?.reason || 'رشد ریالی سنجیده نشد')
      : monetary?.threshold == null
        ? (one?.volume?.applicable === false ? 'رشد تولیدی بر این شرکت اعمال نمی‌شود' : 'رشد ریالی فروش')
        : `کفِ ${faNum(monetary.threshold)}٪`,
  });

  const two = indicators['2'];
  const series = two?.eps_series ?? null;
  const lastEps = series?.length ? series[series.length - 1] : null;
  const pass2 = passes['2_eps_trend'];
  out.push({
    key: '2_eps_trend',
    label: '۲. سودآوری ۳ ساله',
    value: lastEps == null ? '—' : fmtInt(lastEps),
    quality: qualityOf(pass2),
    note: pass2 == null
      ? 'سابقهٔ سه‌سالۀ کامل نیست'
      : two?.years_available == null
        ? 'سه سالِ متوالیِ حسابرسی‌شده'
        : `${faNum(two.years_available)}${two.years_required == null ? '' : `/${faNum(two.years_required)}`} سال`,
  });

  const three = indicators['3'];
  const pass3 = passes['3_gross_margin'];
  const ideal3 = three?.band === 'ideal' || three?.optimal === true;
  out.push({
    key: '3_gross_margin',
    label: '۳. حاشیه سود ناخالص',
    value: three?.margin_pct == null ? '—' : faNum(three.margin_pct, 1) + '٪',
    quality: qualityOf(pass3, ideal3),
    note: pass3 == null
      ? 'حاشیۀ ناخالص ثبت نشده'
      : three?.threshold == null
        ? 'حاشیهٔ ناخالص ÷ درآمد عملیاتی'
        : `≥ ${toFaDigits(three.threshold)}٪`,
  });

  const four = indicators['4'];
  const pass4 = four?.available === false || four?.data_gap ? null : passes['4_sales_to_mcap'];
  out.push({
    key: '4_sales_to_mcap',
    label: '۴. پتانسیل سود تا آخر سال',
    value: ratioPct(four?.sales_to_mcap),
    quality: qualityOf(pass4),
    note: pass4 == null
      ? (four?.gap_cause || four?.reason || 'فروش سالانه یا ارزش بازار نداشت')
      : four?.sales_threshold == null
        ? 'فروش ÷ ارزش بازار'
        : `≥ ${ratioPct(four.sales_threshold)}`,
  });

  const five = indicators['5'];
  const pass5 = passes['5_industry'];
  const regime = five?.label ?? five?.regime_label ?? null;
  out.push({
    key: '5_industry',
    label: '۵. رژیم صنعت',
    value: regime == null || regime === '' ? '—' : String(regime),
    quality: qualityOf(pass5),
    note: pass5 == null
      ? 'صنعت یا نرخ‌گذاری معلوم نیست'
      : (five?.sector ?? card.sector ?? 'رژیم قیمت‌گذاری صنعت'),
  });

  return out;
}

/** محورِ ۵ در کارتِ ۴ می‌نشیند تا هر کارت جایِ جزئیات داشته باشد؛ شمارش همچنان پنج محور است. */
export type CardFact = FundamentalFact & { secondary?: FundamentalFact };

export function cardFacts(card: FtsCard): CardFact[] {
  const facts = fundamentalFacts(card);
  const industry = facts.find((fact) => fact.key === '5_industry');
  return facts
    .filter((fact) => fact.key !== '5_industry')
    .map((fact) => (fact.key === '4_sales_to_mcap' && industry
      ? { ...fact, secondary: { ...industry, label: 'صنعت' } }
      : fact));
}

const AXIS_LABEL: Record<string, string> = {
  '1_growth': 'رشد فروش',
  '2_eps_trend': 'سودآوری ۳ ساله',
  '3_gross_margin': 'حاشیه سود ناخالص',
  '4_sales_to_mcap': 'پتانسیل سود',
  '5_industry': 'صنعت',
};

const STATE_LABEL: Record<string, string> = {
  fresh: 'تازه',
  stale: 'نیازمند بازمحاسبه',
  missing: 'بدون داده',
  quarantined: 'قرنطینه',
};

const ATTENTION_STATES = new Set(['stale', 'missing', 'quarantined']);
const FUNDAMENTAL_AXES = ['1_growth', '2_eps_trend', '3_gross_margin'] as const;
const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

/** فقط تاریخ؛ مقدار تاریخ‌تنها به وقت محلی خوانده می‌شود تا روز جابه‌جا نشود. */
function formatAsOf(asOf: string): string {
  const parts = DATE_ONLY.exec(asOf);
  const date = parts
    ? new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]))
    : new Date(asOf);
  if (Number.isNaN(date.getTime())) return asOf;
  return new Intl.DateTimeFormat('fa-IR', { dateStyle: 'medium' }).format(date);
}

function freshnessBadge(card: FtsCard): { text: string; title: string; dot: string } | null {
  const fresh = card.freshness;
  const axes = fresh?.axes;
  if (!fresh || !axes) return null;
  const stamps = FUNDAMENTAL_AXES
    .map((key) => axes[key]?.as_of)
    .filter((value): value is string => Boolean(value));
  if (stamps.length === 0) return null;
  const oldest = stamps.reduce((a, b) => (a < b ? a : b));
  const needsAttention: string[] = [];
  for (const [key, axis] of Object.entries(axes)) {
    const state = axis?.state;
    if (!state || !ATTENTION_STATES.has(state)) continue;
    needsAttention.push(`${AXIS_LABEL[key] ?? key} (${STATE_LABEL[state] ?? state})`);
  }
  const until = formatAsOf(oldest);
  return {
    text: needsAttention.length
      ? `دادهٔ بنیادی تا ${until} · ${toFaDigits(needsAttention.length)} محور نیازمند بررسی`
      : `دادهٔ بنیادی تا ${until}`,
    title: needsAttention.length
      ? `نیازمند بررسی: ${needsAttention.join('، ')}`
      : 'همهٔ محورها از منبع تازه‌اند',
    dot: needsAttention.length ? 'bg-down' : 'bg-up',
  };
}

export function FundamentalCards({ symbol }: { symbol: string }) {
  const query = useFtsCard(symbol);

  if (query.isLoading) {
    return <p data-testid="fundamental-loading" className="p-2 t-95 text-text-3">پنج شاخصِ بنیادی در حال خواندن…</p>;
  }
  if (query.isError || !query.data) {
    return (
      <p data-testid="fundamental-error" className="p-2 t-95 leading-relaxed text-text-3">
        بنیادیِ این نماد در دسترس نیست؛ چارت و تابلو دست‌نخورده‌اند.
      </p>
    );
  }

  const fresh = freshnessBadge(query.data);
  return (
    <div className="flex min-h-0 flex-col gap-1">
      {fresh ? (
        <div data-testid="fundamental-freshness" title={fresh.title}
          className="flex items-center gap-1 px-1 pt-1 t-85 text-text-3">
          <span className={clsx('inline-block h-1.5 w-1.5 rounded-full', fresh.dot)} aria-hidden />
          <span>{fresh.text}</span>
        </div>
      ) : null}
      <div data-testid="fundamental-cards"
        className="grid min-h-0 grid-cols-[repeat(auto-fit,minmax(160px,1fr))] content-start gap-1 overflow-y-auto p-1">
        {cardFacts(query.data).map((fact) => {
          const chip = CHIP[fact.quality];
          const sub = fact.secondary;
          const subChip = sub ? CHIP[sub.quality] : null;
          return (
            <div
              key={fact.key}
              data-testid={`fundamental-card-${fact.key}`}
              role="group"
              aria-label={`${fact.label} — ${chip.word}${sub ? `؛ ${sub.label} ${sub.value} ${subChip!.word}` : ''}`}
              title={`${fact.label} — ${fact.value} — ${fact.note}${sub ? `
${sub.label}: ${sub.value} — ${sub.note}` : ''}`}
              className="flex min-h-0 min-w-0 flex-col gap-0.5 rounded-[var(--radius-sm)] border border-line bg-panel-2 px-2 py-1.5"
            >
              <div className="flex items-center justify-between gap-1">
                <span className="flex min-w-0 items-center gap-1">
                  <span className="grid h-4 w-4 flex-none place-items-center rounded-full bg-panel-3 t-85 text-text-3">
                    {toFaDigits(fact.key.slice(0, 1))}
                  </span>
                  <span className="truncate t-9 text-text-3">{fact.label.replace(/^\S+\s/, '')}</span>
                </span>
                <span className={clsx('flex-none t-85 font-bold', chip.tone)}>{chip.word}</span>
              </div>
              <b className="num truncate t-125 font-extrabold leading-tight text-text">{fact.value}</b>
              <span className="line-clamp-2 t-85 leading-relaxed text-text-3">{fact.note}</span>
              {sub && subChip ? (
                <span data-testid="fundamental-industry"
                  className="flex min-w-0 items-center justify-between gap-1 border-t border-line pt-0.5 t-85">
                  <span className="truncate text-text-3">{sub.label}</span>
                  <span className="flex min-w-0 items-center gap-1">
                    <span className="truncate text-text-2">{sub.value}</span>
                    <b className={clsx('flex-none', subChip.tone)}>{subChip.word}</b>
                  </span>
                </span>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
