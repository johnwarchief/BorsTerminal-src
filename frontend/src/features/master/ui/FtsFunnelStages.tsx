// features/master/ui/FtsFunnelStages.tsx -- قیفِ مرحلۀ‌بدر‌مرحلۀ FTS درِ تبِ درخت استراتژی
//
// چهار مرحلۀ جزوه، بالابهپایین و *متحرک*: تابلوخوانی ← تکنیکال ← بنیادی ← تحویل.
// هر مرحلۀ جدولِ خودش را دارد و ردیف‌ها با FLIP از مرحلۀ بالا به پایین حرکت
// می‌کنند (shared/lib/useFlip.ts)، تا معلوم شود کدام نماد کجا کم شد.
//
// دو تصمیمی که عمداً این‌جا نشسته:
//   ۱) تکنیکال حذف نمی‌کند. موتورِ تکنیکال تمام نیست و رأیِ مالک (۱۴۰۵-۰۷-۰۷)
//      این است که غربالِ واقعی با تابلو و بنیاد باشد؛ ستونِ تکنیکال فقط نشانه
//      می‌گذارد و همان هم درِ جدول نوشته می‌شود، نه سکوت.
//   ۲) مرحلۀ «تحویل» پایِ قیف است، نه خریدِ خودکار: نمادها منتظرِ انتخابِ خودِ
//      مالک می‌مانند تا به سبد و مدیریتِ سرمایه برود (جزوه: selection ← سبدگردانی).
import { useMemo, useRef, useState } from 'react';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useTapeStore } from '@features/market/stores/tapeStore';
import { useFtsScreen } from '@features/fundamental/api/useFtsScreen';
import { usePortfolio } from '@features/portfolio/api/usePortfolio';
import { SymbolBasketAction } from '@features/portfolio/components/SymbolBasketAction';
import { fmtInt, fmtPct, toFaDigits } from '@shared/lib/fmt';
import { useFlip } from '@shared/lib/useFlip';
import { buildFunnel, PRESET_ENTRY, type FunnelEntry, type FunnelStage, type FunnelStageKey, type StageMark, type TreePreset } from '../lib/ftsFunnel';

const STAGE_TITLE: Record<FunnelStageKey, string> = {
  tape: 'تابلوخوانی',
  technical: 'تکنیکال',
  fundamental: 'بنیادی',
  handover: 'تحویل',
};

const STAGE_RULE: Record<FunnelStageKey, string> = {
  tape: 'نمادهایی که همین نشست دستِ‌کم یکی از پنج فیلترِ جزوه را رد کرده‌اند — عینِ چیپ و بجِ تبِ تابلو.',
  technical: 'روندِ هفتگی و ستاپ فقط علامت می‌خورند؛ درِ این مرحلۀ هیچ نمادی حذف نمی‌شود (موتورِ تکنیکال تمام نیست — رأیِ مالک).',
  fundamental: 'پنج شاخصِ کدال: سه از پنج به بالا به تحویل می‌رود، ردِ صریح می‌افتد، و بی‌گزارش در صفِ خودِ خودش می‌ماند.',
  handover: 'فقط آنچه بنیادش واقعاً سنجیده و قبول شده — در انتظارِ انتخابِ شما برایِ سبد و مدیریتِ سرمایه.',
};

const ORDER: FunnelStageKey[] = ['tape', 'technical', 'fundamental', 'handover'];

const MARK_DOT: Record<StageMark, string> = {
  ok: 'bg-accent-green',
  no: 'bg-accent-red',
  na: 'bg-border-c',
};
const MARK_LABEL: Record<StageMark, string> = { ok: 'تایید', no: 'رد', na: 'سنجیده نشد' };

/** یک مرحلۀ قیف: سرشماره + نوارِ کاهش + جدولِ ردیف‌ها با FLIP */
function StageCard({
  stage,
  index,
  wide,
  showMark,
  onPick,
  active,
  last,
}: {
  stage: FunnelStage;
  index: number;
  wide: number;
  showMark: 'tech' | 'fund' | null;
  onPick: (s: string) => void;
  active: boolean;
  last: boolean;
}) {
  const bodyRef = useRef<HTMLDivElement>(null);
  const rows = stage.entries;
  useFlip({ root: bodyRef, deps: [rows.map((r) => r.symbol).join(' ')] });
  const pct = wide > 0 ? Math.round((rows.length / wide) * 100) : 0;

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
        ) : stage.key === 'technical' ? (
          <span className="rounded-full bg-accent-yellow/15 px-2 py-0.5 text-2xs font-bold text-accent-yellow">
            بی‌حذف
          </span>
        ) : null}
        {stage.unmeasured > 0 ? (
          <span className="num rounded-full bg-bg-secondary px-2 py-0.5 text-2xs font-medium text-text-muted">
            {toFaDigits(stage.unmeasured)} سنجیده‌نشده
          </span>
        ) : null}
        <span className="ms-auto max-w-[46ch] text-3xs leading-4 text-text-muted">{STAGE_RULE[stage.key]}</span>
      </header>

      <div ref={bodyRef} className="relative max-h-[280px] overflow-y-auto">
        {rows.length === 0 ? (
          <p className="px-3 py-4 text-xs text-text-muted">درِ این مرحلۀ نمادی نمانده است.</p>
        ) : (
          <table className="w-full border-collapse text-xs">
            <thead className="sticky top-0 bg-bg-primary/95 text-3xs text-text-muted backdrop-blur-sm">
              <tr>
                <th className="px-2 py-1 text-start font-bold">نماد</th>
                <th className="px-2 py-1 text-end font-bold">آخرین</th>
                <th className="px-2 py-1 text-end font-bold">تغییر٪</th>
                <th className="px-2 py-1 text-end font-bold">حجم/ماه</th>
                <th className="px-2 py-1 text-start font-bold">نشانه</th>
                <th className="px-2 py-1 text-end font-bold">بنیادی</th>
                {last ? <th className="px-2 py-1 text-end font-bold">سبد</th> : null}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <StageRow key={r.symbol} entry={r} showMark={showMark} onPick={onPick} last={last} />
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
            <tbody>
              {stage.pending.map((r) => (
                <StageRow key={r.symbol} entry={r} showMark="fund" onPick={onPick} last={false} />
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
  showMark,
  onPick,
  last,
}: {
  entry: FunnelEntry;
  showMark: 'tech' | 'fund' | null;
  onPick: (s: string) => void;
  last: boolean;
}) {
  const mark = showMark ? (showMark === 'tech' ? entry.tech : entry.fund) : null;
  const why = showMark === 'tech' ? entry.techWhy : entry.fundWhy;
  const r = entry.row;
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
      <td className="num px-2 py-1 text-end text-text-secondary">{r?.p_last != null ? fmtInt(r.p_last) : '—'}</td>
      <td
        className={`num px-2 py-1 text-end ${
          (r?.percent_change ?? 0) > 0 ? 'text-accent-green' : (r?.percent_change ?? 0) < 0 ? 'text-accent-red' : 'text-text-secondary'
        }`}
      >
        {r?.percent_change != null ? fmtPct(r.percent_change) : '—'}
      </td>
      <td className="num px-2 py-1 text-end text-text-secondary">
        {r?.vol_ratio != null ? `${toFaDigits(r.vol_ratio.toFixed(1))}×` : '—'}
      </td>
      <td className="px-2 py-1 text-start text-3xs text-text-muted">
        {entry.patterns.length ? entry.patterns.join(' + ') : MARK_LABEL[mark ?? 'na']}
      </td>
      <td className="num px-2 py-1 text-end font-bold text-text-primary">
        {entry.score != null ? `${toFaDigits(entry.score)}/۵` : '—'}
      </td>
      {last ? (
        <td className="px-2 py-1 text-end">
          <SymbolBasketAction symbol={entry.symbol} />
        </td>
      ) : null}
    </tr>
  );
}

export function FtsFunnelStages({ preset = 'custom' }: { preset?: TreePreset }) {
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const [active, setActive] = useState<FunnelStageKey>('tape');

  const feed = useMarketFeed();
  // limit همان شمارۀ خودِ هاب است تا کوئریِ مشترک دوباره ساخته نشود؛
  // خودِ بک‌اند limit را نمی‌خواند و هر ۸۷۳ شرکتِ واجد را می‌فرستد.
  const screen = useFtsScreen(120);
  const portfolio = usePortfolio();
  const cfg = useTapeStore((s) => s.tapeFilterConfig);
  const quickFilters = useTapeStore((s) => s.quickFilters);

  const funnel = useMemo(() => {
    const rows = feed.data?.data ?? [];
    const basket = new Set((portfolio.data?.portfolio ?? []).map((h) => h.symbol));
    return buildFunnel(rows, cfg, quickFilters ?? [], screen.data?.data ?? [], basket, preset);
  }, [feed.data, screen.data, portfolio.data, cfg, quickFilters, preset]);

  const stages = ORDER.map((k) => funnel.stages[k]);
  const wide = Math.max(1, ...stages.map((s) => s.entries.length));
  const marks: ('tech' | 'fund' | null)[] = [null, 'tech', 'fund', 'fund'];

  return (
    <section className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-black text-text-primary">قیفِ غربالگری FTS</h2>
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
      </div>

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
            last={i === stages.length - 1}
          />
        ))}
      </div>
    </section>
  );
}
