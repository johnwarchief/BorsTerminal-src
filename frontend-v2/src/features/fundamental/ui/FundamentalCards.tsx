import clsx from 'clsx';
import { faNum, fmtInt, fmtPct, toFaDigits } from '@shared/lib/fa';
import { useFtsCard, type FtsCard } from '../api/useFtsCard';

type Quality = 'ideal' | 'ok' | 'below' | 'na';

const CHIP: Record<Quality, { word: string; tone: string }> = {
  ideal: { word: 'ایده‌آل', tone: 'text-cyan-300' },
  ok: { word: 'قبول', tone: 'text-up' },
  below: { word: 'رد', tone: 'text-down' },
  na: { word: 'نظر نمی‌دهد', tone: 'text-text-3' },
};

interface Fact {
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

function signedPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${value >= 0 ? '+' : '−'}${faNum(Math.abs(value), 1)}٪`;
}

function ratioPct(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return '—';
  return `${toFaDigits((value * 100).toFixed(1))}٪`;
}

function factsOf(card: FtsCard): Fact[] {
  const passes = card.passes ?? {};
  const indicators = card.indicators ?? {};
  const out: Fact[] = [];

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
    value: three?.margin_pct == null ? '—' : fmtPct(three.margin_pct),
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

  const facts = factsOf(query.data);

  return (
    <div data-testid="fundamental-cards" className="flex flex-col gap-1 p-1">
      {facts.map((fact) => {
        const chip = CHIP[fact.quality];
        return (
          <div key={fact.key} data-testid={`fundamental-card-${fact.key}`}
            title={fact.note}
            className="rounded-[var(--radius-sm)] border border-line bg-panel-2 px-1.5 py-1">
            <div className="flex items-baseline justify-between gap-2 t-9 text-text-3">
              <span className="truncate">{fact.label}</span>
              <span className={clsx('shrink-0 t-85 font-bold', chip.tone)}>{chip.word}</span>
            </div>
            <div className="flex items-baseline justify-between gap-2">
              <b className="num t-105 font-extrabold text-text">{fact.value}</b>
              <span className="min-w-0 truncate t-85 text-text-3">{fact.note}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}
