// features/master/ui/FtsFunnelStages.tsx -- قیفِ مرحلۀ‌بدر‌مرحلۀ FTS درِ تبِ درخت استراتژی
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
import { useMemo, useRef, useState } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { useFtsScreen } from '@features/fundamental/api/useFtsScreen';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { useFlip } from '@shared/lib/useFlip';
import { buildFunnel, PRESET_ENTRY, tapePickedSymbols, IND_COLUMNS, trendLabel, type FunnelEntry, type FunnelStage, type FunnelStageKey, type FunnelOptions, type StageMark, type TreePreset } from '../lib/ftsFunnel';
import { useFtsTechBoard } from '../api/useFtsTechBoard';
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
  handover: 'تحویل',
};

const STAGE_RULE: Record<FunnelStageKey, string> = {
  tape: 'نمادهایی که همین نشست دستِ‌کم یکی از پنج فیلترِ جزوه را رد کرده‌اند — عینِ چیپ و بجِ تبِ تابلو.',
  technical: 'ستون‌های خودِ این مرحله: روندِ هفتگی و روزانه و ستاپ. با «رد می‌کند» وتوی هفتگی یا نبودِ ستاپِ سبک نماد را بیرون می‌اندازد؛ با «خودم چک می‌کنم» ردشده‌ها برچسب می‌خورند و به بنیادی می‌رسند. سنجیده‌نشده هیچ‌وقت رد نیست.',
  fundamental: '',
  handover: 'فقط آنچه بنیادش واقعاً سنجیده و قبول شده — در انتظارِ انتخابِ شما برایِ سبد و مدیریتِ سرمایه.',
};

/** شرحِ درِ بنیادی به دو پیچِ دستِ کاربر وصل است تا متنِ rule دروغِ پیش‌فرض نگوید. */
function fundRule(o: FunnelOptions): string {
  const un =
    o.unmeasured === 'hold'
      ? 'و بی‌گزارش در صفِ خودش می‌ماند'
      : o.unmeasured === 'pass'
        ? 'و بی‌گزارش با برچسبِ «سنجیده نشد» عبور می‌کند'
        : 'و بی‌گزارش از قیف حذف می‌شود';
  return `پنج شاخصِ کدال: ${toFaDigits(o.fundFloor)} از ${toFaDigits(FUND_FLOOR_MAX)} به بالا به تحویل می‌رود، ردِ صریح می‌افتد ${un}.`;
}

const ORDER: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

/**
 * دربِ قیف = همان افقی که درِ «درخت استراتژی» و داوریِ نماد انتخاب می‌شود.
 * پیش از این قیف فقط با prop آن را می‌خواند و انتخابش درِ جایِ دیگری از صفحه
 * بود؛ مالک پرسید «چرا برای قیف غربالگری انتخاب استراتژی‌ها حذف شد» — چون
 * بعد از جابه‌جاییِ قیف به این تب، کلیدش رویِ صفحه نماند.
 */
const FUNNEL_PRESETS = ['swing', 'trend', 'hourglass'] as const;
const PRESET_SHORT: Record<(typeof FUNNEL_PRESETS)[number], string> = {
  swing: 'نوسان‌گیر',
  trend: 'روندگیر',
  hourglass: 'ساعت شنی',
};

const MARK_DOT: Record<StageMark, string> = {
  ok: 'bg-accent-green',
  no: 'bg-accent-red',
  na: 'bg-border-c',
};
const MARK_LABEL: Record<StageMark, string> = { ok: 'تایید', no: 'رد', na: 'سنجیده نشد' };

/**
 * ستون‌هایِ هر مرحله — «هر بخش باید ستونِ مربوط به خودش را داشته باشد».
 * تا پیش از این چهار جدول یک سرستون مشترک داشتند (نماد/آخرین/تغییر٪/حجم-ماه/
 * نشانه/بنیادی)، پس مرحلۀ تکنیکال هیچ چیز از روندِ هفتگی نمی‌گفت و مرحلۀ
 * بنیادی فقط جمعِ پنج شاخص را. اینجا هر مرحله ستون‌هایِ همان سطرِ چارت را
 * می‌خواند: T (صفحه ۲) برای تکنیکال، F (صفحه ۱) برای بنیادی.
 */
type ColKey =
  | 'symbol' | 'last' | 'chg' | 'vol' | 'pattern'
  | 'weekly' | 'daily' | 'setup' | 'mark'
  | 'ind1' | 'ind2' | 'ind3' | 'ind4' | 'ind5' | 'score' | 'basket';

const COL: Record<ColKey, { label: string; title: string; end?: boolean }> = {
  symbol: { label: 'نماد', title: 'کلیک = انتخابِ نماد' },
  last: { label: 'آخرین', title: 'قیمت آخرین معامله', end: true },
  chg: { label: 'تغییر٪', title: 'تغییر درصدی امروز', end: true },
  vol: { label: 'حجم/ماه', title: 'حجم امروز ÷ میانگین ماهانه', end: true },
  pattern: { label: 'نشانه', title: 'فیلترهای جزوه‌ای که این ردیف رد کرده است' },
  weekly: { label: 'هفتگی', title: 'روند هفتگی — چارت ۲: نزولی و خنثی = reject', end: true },
  daily: { label: 'روزانه', title: 'روند روزانه — شاخه‌بندی پولبک/جت، فیبو/CHoCH، کف دوقلو', end: true },
  setup: { label: 'ستاپ', title: 'ستاپ‌های فعال روی همین نماد' },
  mark: { label: 'داوری', title: 'حکم این مرحله', end: true },
  ind1: { label: IND_COLUMNS[0].label, title: IND_COLUMNS[0].full, end: true },
  ind2: { label: IND_COLUMNS[1].label, title: IND_COLUMNS[1].full, end: true },
  ind3: { label: IND_COLUMNS[2].label, title: IND_COLUMNS[2].full, end: true },
  ind4: { label: IND_COLUMNS[3].label, title: IND_COLUMNS[3].full, end: true },
  ind5: { label: IND_COLUMNS[4].label, title: IND_COLUMNS[4].full, end: true },
  score: { label: 'بنیادی', title: 'جمع پنج شاخص', end: true },
  basket: { label: 'سبد', title: 'افزودن به سبد', end: true },
};

const STAGE_COLS: Record<FunnelStageKey, ColKey[]> = {
  tape: ['symbol', 'last', 'chg', 'vol', 'pattern'],
  technical: ['symbol', 'weekly', 'daily', 'setup', 'mark'],
  fundamental: ['symbol', 'ind1', 'ind2', 'ind3', 'ind4', 'ind5', 'score'],
  handover: ['symbol', 'weekly', 'score', 'basket'],
};

const TREND_COLOR: Record<string, string> = {
  up: 'text-accent-green',
  down: 'text-accent-red',
  range: 'text-accent-yellow',
  na: 'text-text-muted',
};

/** سلولِ «ردیفِ پنج‌شاخصه»: ✓ / ✗ / — با عددِ خودش، نه فقط رنگ. */
function IndCell({ mark, value }: { mark: StageMark; value: string | null }) {
  const glyph = mark === 'ok' ? '✓' : mark === 'no' ? '✗' : '—';
  const cls =
    mark === 'ok' ? 'text-accent-green' : mark === 'no' ? 'text-accent-red' : 'text-text-muted';
  return (
    <td className={`num px-2 py-1 text-end ${cls}`} title={value ?? MARK_LABEL[mark]}>
      {value ? <span className="ms-1 opacity-70">{value}</span> : null}
      <span className="font-black">{glyph}</span>
    </td>
  );
}

function TrendCell({ t }: { t: string | null }) {
  const key = t ?? 'na';
  return (
    <td className={`px-2 py-1 text-end font-bold ${TREND_COLOR[key] ?? 'text-text-muted'}`}>
      {trendLabel(t)}
    </td>
  );
}

/** نرخ‌گذاری به زبانِ خودِ جدول: بک‌اند 'free' / 'mandatory' را می‌دهد. */
function pricingLabel(mode: string | null | undefined): string | null {
  const m = (mode ?? '').trim().toLowerCase();
  if (!m) return null;
  if (m === 'free') return 'آزاد';
  if (m === 'mandatory' || m === 'regulated' || m === 'دستوری') return 'دستوری';
  if (m === 'آزاد') return 'آزاد';
  return mode ?? null;
}

function Cell({ k, e, mark, why }: { k: ColKey; e: FunnelEntry; mark: StageMark | null; why: string | null }) {
  const r = e.row;
  switch (k) {
    case 'last':
      return <td className="num px-2 py-1 text-end text-text-secondary">{r?.p_last != null ? fmtInt(r.p_last) : '—'}</td>;
    case 'chg':
      return (
        <td className={`num px-2 py-1 text-end ${
          (r?.percent_change ?? 0) > 0 ? 'text-accent-green' : (r?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
        }`}>
          {r?.percent_change != null ? fmtPct(r.percent_change) : '—'}
        </td>
      );
    case 'vol':
      return <td className="num px-2 py-1 text-end text-text-secondary">{r?.vol_ratio != null ? `${toFaDigits(r.vol_ratio.toFixed(1))}×` : '—'}</td>;
    case 'pattern':
      return <td className="px-2 py-1 text-start text-3xs text-text-muted">{e.patterns.length ? e.patterns.join(' + ') : (mark ? MARK_LABEL[mark] : '—')}</td>;
    case 'weekly':
      return <TrendCell t={e.trendW} />;
    case 'daily':
      return <TrendCell t={e.trendD} />;
    case 'setup':
      return <td className="px-2 py-1 text-start text-3xs text-text-secondary">{e.setups || '—'}</td>;
    case 'mark':
      return <td className="px-2 py-1 text-end text-3xs font-bold" title={why ?? undefined}>{mark ? MARK_LABEL[mark] : '—'}</td>;
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
      return <IndCell mark={e.inds[i] ?? 'na'} value={raw} />;
    }
    case 'score':
      return <td className="num px-2 py-1 text-end font-bold text-text-primary">{e.score != null ? `${toFaDigits(e.score)}/۵` : '—'}</td>;
    case 'basket':
      return <td className="px-2 py-1 text-end"><SymbolBasketAction symbol={e.symbol} /></td>;
    default:
      return null;
  }
}

/** یک مرحلۀ قیف: سرشماره + نوارِ کاهش + جدولِ ردیف‌ها با FLIP */
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
  showMark: 'tech' | 'fund' | null;
  onPick: (s: string) => void;
  active: boolean;
  opts: FunnelOptions;
  emptyWhy: string | null;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const rows = stage.entries;
  useFlip({ root: bodyRef, deps: [rows.map((r) => r.symbol).join(' ')] });
  const pct = wide > 0 ? Math.round((rows.length / wide) * 100) : 0;
  const cols = STAGE_COLS[stage.key];
  const techScreens = useFunnelPrefsStore((s) => s.techScreens);
  const setTechScreens = useFunnelPrefsStore((s) => s.setTechScreens);
  const rule = stage.key === 'fundamental' ? fundRule(opts) : STAGE_RULE[stage.key];

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
        <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-bold text-text-secondary">
          {toFaDigits(rows.length)} نماد
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
            title="رد خورده ولی از قیف بیرون نیفتاده — «خودم چک می‌کنم» روشن است"
          >
            {toFaDigits(stage.rejected)} رد (بی‌حذف)
          </span>
        ) : null}
        {stage.unmeasured > 0 ? (
          <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-medium text-text-muted">
            {toFaDigits(stage.unmeasured)} سنجیده‌نشده
          </span>
        ) : null}
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

      <div ref={bodyRef} className="relative max-h-[280px] overflow-y-auto">
        {rows.length === 0 ? (
          <p className="px-3 py-4 text-xs text-text-muted" data-testid={`funnel-empty-${stage.key}`}>
            {emptyWhy ?? 'هیچ نمادی از این مرحله عبور نکرد.'}
          </p>
        ) : (
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 bg-bg-primary/95 text-3xs text-text-muted backdrop-blur-sm">
              <tr>
                {cols.map((k) => (
                  <th
                    key={k}
                    title={COL[k].title}
                    className={`px-2 py-1 font-bold ${COL[k].end ? 'text-end' : 'text-start'}`}
                  >
                    {COL[k].label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <StageRow key={r.symbol} entry={r} cols={cols} showMark={showMark} onPick={onPick} />
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* گروهِ «سنجیده نشد»: نه مردود است نه تحویل. بی‌این، نبودنِ گزارشِ کدال
          «رد» به‌نظر می‌رسید و کاربر نمادی را از دست می‌داد که فقط بی‌داده است. */}
      {stage.pending.length > 0 ? (
        <div data-testid={`funnel-pending-${stage.key}`} className="border-t border-dashed border-border-c/70 bg-bg-secondary/40">
          <p className="px-3 py-1.5 text-3xs font-bold text-text-muted">
            بنیادی‌اش سنجیده نشده — در انتظارِ گزارشِ کدال ({toFaDigits(stage.pending.length)})
          </p>
          <table className="w-full border-collapse text-xs">
            {/* سرستونِ همان مرحله: ردیف‌هایِ انتظار هم باید بدانند کدام ✓/✗
                کدام شاخص است، وگرنه پنج علامت بی‌نام می‌مانند. */}
            <thead className="text-3xs text-text-muted">
              <tr>
                {cols.map((k) => (
                  <th key={k} className={`px-2 py-1 font-bold ${COL[k].end ? 'text-end' : 'text-start'}`}>
                    {COL[k].label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stage.pending.map((r) => (
                <StageRow key={r.symbol} entry={r} cols={cols} showMark="fund" onPick={onPick} />
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}

function StageRow({
  entry,
  cols,
  showMark,
  onPick,
}: {
  entry: FunnelEntry;
  cols: ColKey[];
  showMark: 'tech' | 'fund' | null;
  onPick: (s: string) => void;
}) {
  const mark = showMark ? (showMark === 'tech' ? entry.tech : entry.fund) : null;
  const why = showMark === 'tech' ? entry.techWhy : entry.fundWhy;
  return (
    <tr
      data-fkey={entry.symbol}
      className="border-b border-border-c/40 last:border-0 hover:bg-bg-card/70"
      title={why}
    >
      <td className="px-2 py-1 text-start">
        <button
          type="button"
          onClick={() => onPick(entry.symbol)}
          className="flex max-w-[16ch] items-center gap-1 truncate font-black text-text-primary hover:text-accent-blue"
        >
          {mark ? <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${MARK_DOT[mark]}`} /> : null}
          <span className="truncate">{entry.symbol}</span>
        </button>
      </td>
      {cols.filter((k) => k !== 'symbol').map((k) => (
        <Cell key={k} k={k} e={entry} mark={mark} why={why} />
      ))}
    </tr>
  );
}

/** پیچ‌هایِ درِ بنیادی — سخت‌گیریِ جزوه کم نمی‌شود، حقِ انتخاب دستِ خودِ مالک است. */
function FunnelPrefsBar({ passed, techScreens }: { passed: number; techScreens: boolean }) {
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
      className="flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-xl border border-border-c bg-bg-card/40 px-2.5 py-1.5"
    >
      <span className="text-2xs font-black text-text-secondary">
        مرحلۀ بنیادی
        <span className="ms-1 font-normal text-text-muted">(پیش‌فرضِ جزوه: {toFaDigits(DEFAULT_FUND_FLOOR)} از {toFaDigits(FUND_FLOOR_MAX)})</span>
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
      <span className="num ms-auto text-3xs text-text-muted">
        با این پیچ‌ها: {toFaDigits(passed)} نماد از مرحلۀ بنیادی عبور می‌کند
      </span>
      {fundFloor !== DEFAULT_FUND_FLOOR || unmeasured !== 'hold' || !techScreens ? (
        <button type="button" data-testid="funnel-prefs-reset" onClick={reset} className="text-3xs font-bold text-text-muted underline hover:text-accent-amber">
          بازگشت به جزوه
        </button>
      ) : null}
    </div>
  );
}

export function FtsFunnelStages({
  preset = 'custom',
  onPresetChange,
}: {
  preset?: TreePreset;
  /** وقتی والد، دربِ قیف را از استورِ استراتژی می‌خواند؛ بی‌این کلیدها رسم نمی‌شوند */
  onPresetChange?: (p: (typeof FUNNEL_PRESETS)[number]) => void;
}) {
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const [active, setActive] = useState<FunnelStageKey>('tape');

  const feed = useMarketFeed();
  // limit همان شمارۀ خودِ هاب است تا کوئریِ مشترک دوباره ساخته نشود؛
  // خودِ بک‌اند limit را نمی‌خواند و هر ۸۷۳ شرکتِ واجد را می‌فرستد.
  const screen = useFtsScreen(120);
  const portfolio = usePortfolio();
  const cfg = useTapeStore((s) => s.tapeFilterConfig);
  const quickFilters = useTapeStore((s) => s.quickFilters);
  const fundFloor = useFunnelPrefsStore((s) => s.fundFloor);
  const unmeasured = useFunnelPrefsStore((s) => s.unmeasured);
  const techScreens = useFunnelPrefsStore((s) => s.techScreens);
  const opts = useMemo<FunnelOptions>(
    () => ({ fundFloor, unmeasured, techScreens }),
    [fundFloor, unmeasured, techScreens],
  );

  // دو پاسِ عمدی: نخست فقط مرحلۀ تابلو حساب می‌شود تا معلوم شود برایِ کدام
  // نمادها رأیِ تکنیکال لازم است، سپس `/api/fts` برایِ همان‌ها خوانده می‌شود.
  // بی‌این، درِ T هرگز بسته نمی‌شد چون اسکرینر فقط سقفِ واچ‌لیست را تحلیل کرده.
  const techTargets = useMemo(
    () => tapePickedSymbols(feed.data?.data ?? [], cfg, quickFilters ?? [], preset),
    [feed.data, cfg, quickFilters, preset],
  );
  const tech = useFtsTechBoard(techTargets);

  const funnel = useMemo(() => {
    const rows = feed.data?.data ?? [];
    const basket = new Set((portfolio.data?.portfolio ?? []).map((h) => h.symbol));
    return buildFunnel(rows, cfg, quickFilters ?? [], screen.data?.data ?? [], basket, preset, tech.map, opts);
  }, [feed.data, screen.data, portfolio.data, cfg, quickFilters, preset, tech.map, opts]);

  const stages = ORDER.map((k) => funnel.stages[k]);
  const wide = Math.max(1, ...stages.map((s) => s.entries.length));
  const marks: ('tech' | 'fund' | null)[] = [null, 'tech', 'fund', 'fund'];

  // «چرا خالی است» باید خودش را بگوید، وگرنه مرحلۀ خالی با مرحلۀ خراب یکی
  // به‌نظر می‌رسد: «هیچ‌کدام به این در نرسید» با «همه رد شدند» یکی نیست.
  const fund = funnel.stages.fundamental;
  const hand = funnel.stages.handover;
  const emptyWhy: Record<FunnelStageKey, string | null> = {
    tape: funnel.total ? null : 'این نشست هیچِ یک از پنج فیلترِ جزوه را رد نکرد.',
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
      : fund.entries.length
        ? 'رسیدگانِ بنیادی همه همین حالا در سبدِ شما هستند.'
        : 'مرحلۀ بنیادی کسی را قبول نکرد.',
  };

  return (
    <section className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-black text-text-primary">قیفِ غربالگری FTS</h2>
        {onPresetChange && (
          <div
            className="flex flex-wrap items-center gap-1"
            role="group"
            aria-label="استراتژیِ دربِ قیف"
            data-testid="funnel-preset-picker"
          >
            <span className="text-3xs font-bold text-text-secondary">دربِ قیف:</span>
            {FUNNEL_PRESETS.map((p) => (
              <button
                key={p}
                type="button"
                aria-pressed={preset === p}
                data-testid={`funnel-preset-${p}`}
                title={
                  PRESET_ENTRY[p].label +
                  (quickFilters.length ? ' — فعلاً ورودیِ قیف را چیپ‌هایِ روشنِ تبِ تابلو تعیین می‌کنند، این درب مرحلۀ تکنیکال را می‌زند' : '')
                }
                onClick={() => onPresetChange(p)}
                className={`rounded-full border px-2 py-0.5 text-3xs font-bold transition-all ${
                  preset === p
                    ? 'border-accent-amber bg-accent-amber/15 text-accent-amber'
                    : 'border-border-c bg-bg-card text-text-muted hover:border-accent-amber/60 hover:text-text-primary'
                }`}
              >
                {PRESET_SHORT[p]}
              </button>
            ))}
          </div>
        )}
        <div className="flex flex-wrap items-center gap-1" role="tablist">
          {stages.map((s, i) => (
            <button
              key={s.key}
              type="button"
              role="tab"
              aria-selected={active === s.key}
              data-testid={`funnel-step-${s.key}`}
              onClick={() => setActive(s.key)}
              className={`rounded-full border px-2.5 py-1 text-2xs font-bold transition-all ${
                active === s.key
                  ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                  : 'border-border-c bg-bg-card text-text-secondary hover:border-accent-blue/60'
              }`}
            >
              {toFaDigits(i + 1)}. {STAGE_TITLE[s.key]}
              <span className="num ms-1 opacity-80">({toFaDigits(s.entries.length)})</span>
            </button>
          ))}
        </div>
        <span className="ms-auto text-3xs text-text-muted">
          ورودیِ قیف: {quickFilters.length ? 'چیپ‌هایِ روشنِ تبِ تابلو' : PRESET_ENTRY[preset].label} ·{' '}
          {toFaDigits(funnel.boardScope)} نمادِ زندهٔ تابلو ← {toFaDigits(funnel.total)} نشانه
        </span>
        {/* پوششِ رأیِ تکنیکال پنهان نمی‌ماند: «سنجیده نشد» با «رد شده» یکی نیست. */}
        {tech.wanted > 0 ? (
          <span
            data-testid="funnel-tech-coverage"
            className={`num rounded-full px-2 py-0.5 text-2xs font-bold ${
              tech.loading ? 'bg-accent-yellow/15 text-accent-yellow' : 'bg-bg-secondary text-text-secondary'
            }`}
          >
            {tech.loading ? 'تکنیکال در حالِ خواندن: ' : 'تکنیکال سنجیده شده: '}
            {toFaDigits(tech.resolved)} از {toFaDigits(tech.wanted)}
          </span>
        ) : null}
      </div>

      <FunnelPrefsBar passed={funnel.stages.fundamental.entries.length} techScreens={techScreens} />

      <div className="flex flex-col gap-2">
        {stages.map((s, i) => (
          <StageCard
            key={s.key}
            stage={s}
            index={i}
            wide={wide}
            showMark={marks[i]}
            onPick={setSymbol}
            active={active === s.key}
            opts={opts}
            emptyWhy={emptyWhy[s.key]}
          />
        ))}
      </div>
    </section>
  );
}
