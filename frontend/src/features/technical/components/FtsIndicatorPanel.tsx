// features/technical/components/FtsIndicatorPanel.tsx -- پنلِ کاتالوگِ لایه‌های FTS (مرحلۀ ۶)
// رجیستری (lib/ftsIndicatorCatalog) تنها راهنمایِ این صفحه است: نامِ فارسی، گروه،
// توسلِ مستقل، رنگِ همان لایه و صادق‌گوییِ «درِ کدام موتور رسم می‌شود». عددی اینجا
// حساب نمی‌شود -- شواهد از lib/ftsLayerEvidence خوانده می‌شود که فقط payloadِ
// `/api/fts` را برمی‌دارد. بی‌داده، برچسب «منتشر نشده» است، نه «فعال»ِ ساختگی.
import { useMemo, useState } from 'react';
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import type { Structure3Data } from '../api/useStructure3';
import { CATALOG_GROUPS, CHART_VIEW_FLAGS, FTS_INDICATOR_CATALOG, type FtsIndicatorEntry, type IndicatorGroupId, type LayerToggle } from '../lib/ftsIndicatorCatalog';
import { E3_COLORS } from '../lib/structure3Layers';
import { LAYER_STATE_FA, layerEvidence, type LayerState } from '../lib/ftsLayerEvidence';
import { FTS_OVERLAY_COLORS } from '../lib/ftsOverlays';
import { PATTERN_LABELS, type PatternKind, type PatternPrefs } from '../lib/patternOverlays';
import { usePatternPrefsStore } from '../stores/patternPrefsStore';
import { useFtsConfigStore } from '../stores/ftsConfigStore';

/** پرچم‌های نوارِ ابزار (درِ view store)، نه الگوهایِ PatternPrefs -- یک فهرستِ
 *  مشترک با کاتالوگ و تست، تا سوییچِ اعلام‌شدنِ لایه‌ای درِ جایی نمرد. */
const VIEW_FLAGS = CHART_VIEW_FLAGS;
type ViewFlag = (typeof VIEW_FLAGS)[number];

const FLAG_COLORS: Record<ViewFlag, string> = {
  showFibLevels: FTS_OVERLAY_COLORS.fibText,
  showHistoryEvents: FTS_OVERLAY_COLORS.fibText2,
  showCorporateActions: '#8a93a6',
  // رنگِ خودِ لایه، از پالتِ موتورِ سوم -- نه یک پالتِ دوم درِ پنل
  showStructure3: E3_COLORS.line,
};

/** لایه‌های بی‌توسلِ الگو که رنگشان درِ نگاشتِ لایه ثابت است */
const ID_COLORS: Record<string, string> = {
  'trend-daily': '#4ade80',
  'trend-weekly-gate': '#f87171',
  'current-trigger': '#22d3ee',
  'hard-stop': '#f23645',
};

const STATE_TONE: Record<LayerState, 'green' | 'blue' | 'yellow' | 'gray'> = {
  active: 'green',
  forming: 'blue',
  inactive: 'gray',
  insufficient: 'yellow',
  'not-published': 'gray',
};

const isViewFlag = (t: LayerToggle): t is ViewFlag =>
  typeof t === 'string' && (VIEW_FLAGS as readonly string[]).includes(t);

const isPatternKind = (t: LayerToggle): t is PatternKind =>
  t !== null && !isViewFlag(t);

/** رنگِ همان لایه، از همان ترجیحاتی که چارت می‌خواند — نه یک پالتِ دوم */
export function layerColor(entry: FtsIndicatorEntry, prefs: PatternPrefs): string {
  if (isPatternKind(entry.toggle)) return prefs[entry.toggle].color;
  if (isViewFlag(entry.toggle)) return FLAG_COLORS[entry.toggle];
  return ID_COLORS[entry.id] ?? '#8a93a6';
}

function freshnessLine(basis: string | null | undefined, bars: number | null | undefined, lastBarDate: string | null | undefined, fetchedAtMs: number | null | undefined): string {
  const bits: string[] = [];
  bits.push(basis ? `مبنا: ${basis}` : 'مبنا: اعلام نشده');
  bits.push(typeof bars === 'number' ? `${toFaDigits(bars)} کندلِ تحلیل` : 'تعدادِ کندلِ تحلیل اعلام نشده');
  if (lastBarDate) bits.push(`آخرین کندل: ${lastBarDate}`);
  // ساعتِ دریافت از react-query است (ساعتِ دستگاه)، نه از سرور -- پس برچسبش
  // «دریافت» است نه «تازه‌ترین دادهٔ بازار».
  if (typeof fetchedAtMs === 'number' && fetchedAtMs > 0) {
    bits.push(`دریافت: ${new Date(fetchedAtMs).toLocaleTimeString('fa-IR', { hour: '2-digit', minute: '2-digit' })}`);
  }
  return bits.join(' · ');
}

export function FtsIndicatorPanel({
  fts,
  basis,
  bars,
  lastBarDate,
  fetchedAtMs,
  adjustmentEvents,
  e3,
}: {
  fts: FtsAnalysisData | null | undefined;
  basis?: string | null;
  bars?: number | null;
  lastBarDate?: string | null;
  fetchedAtMs?: number | null;
  adjustmentEvents?: number | null;
  /** قراردادِ موتورِ سوم (`/api/structure3`) -- شواهدِ دو سطرِ e3 فقط از این است */
  e3?: Structure3Data | null;
}) {
  const prefs = usePatternPrefsStore((s) => s.prefs);
  const togglePattern = usePatternPrefsStore((s) => s.toggle);
  const view = useFtsConfigStore((s) => s.view);
  const setView = useFtsConfigStore((s) => s.setView);
  const [selected, setSelected] = useState<FtsIndicatorEntry | null>(null);

  const enabledOf = (t: LayerToggle): boolean | null => {
    if (t === null) return null; // لایه‌ای که توسلِ جدا ندارد؛ سوییچِ مرده نمی‌سازیم
    if (isViewFlag(t)) return t === 'showCorporateActions' ? view?.showCorporateActions !== false : view?.[t] === true;
    if (isPatternKind(t)) return prefs[t].enabled;
    return null;
  };

  const groups = useMemo(() => {
    const ids = Object.keys(CATALOG_GROUPS) as IndicatorGroupId[];
    return ids
      .sort((a, b) => CATALOG_GROUPS[a].order - CATALOG_GROUPS[b].order)
      .map((g) => ({ g, title: CATALOG_GROUPS[g].fa, entries: FTS_INDICATOR_CATALOG.filter((e) => e.group === g) }));
  }, []);

  const onToggle = (entry: FtsIndicatorEntry) => {
    const t = entry.toggle;
    if (t === null) return;
    if (isViewFlag(t)) {
      const cur = enabledOf(t) === true;
      setView({ [t]: !cur } as Partial<typeof view>);
      return;
    }
    if (isPatternKind(t)) togglePattern(t);
  };

  const evidenceOf = (entry: FtsIndicatorEntry) =>
    layerEvidence(entry, fts, { adjustmentEvents: adjustmentEvents ?? null, structure3: e3 ?? null });

  return (
    <div className="glass-panel flex flex-col gap-2.5 p-3" data-testid="fts-layer-panel" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-xs font-black text-text-primary">کاتالوگِ لایه‌های FTS</h3>
        <span className="text-3xs text-text-muted" data-testid="fts-layer-freshness">
          {freshnessLine(basis, bars, lastBarDate, fetchedAtMs)}
        </span>
      </div>

      {groups.map(({ g, title, entries }) => (
        <div key={g} className="flex flex-col gap-1" data-testid={`fts-layer-group-${g}`}>
          <span className="text-[11px] font-bold text-text-secondary">{title}</span>
          {entries.map((e) => {
            const enabled = enabledOf(e.toggle);
            const evd = evidenceOf(e);
            return (
              <div
                key={e.id}
                className="flex flex-wrap items-center gap-2 rounded border border-border-c bg-bg-card/40 px-2 py-1"
                data-testid={`fts-layer-row-${e.id}`}
              >
                <input
                  type="checkbox"
                  checked={enabled === true}
                  disabled={enabled === null}
                  title={enabled === null ? 'این لایه توسلِ جدا ندارد؛ همیشه با موتور می‌آید' : undefined}
                  onChange={() => onToggle(e)}
                  data-testid={`fts-layer-toggle-${e.id}`}
                  aria-label={e.fa}
                  className="accent-sky-400"
                />
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: layerColor(e, prefs) }}
                  title={PATTERN_LABELS[e.toggle as PatternKind] ?? e.fa}
                  aria-hidden="true"
                />
                <button
                  type="button"
                  onClick={() => setSelected(e)}
                  data-testid={`fts-layer-evidence-btn-${e.id}`}
                  aria-expanded={selected?.id === e.id}
                  className="min-w-0 flex-1 truncate text-start text-[11px] text-text-secondary transition-colors hover:text-text-primary"
                >
                  {e.fa}
                </button>
                {/* صادق‌گوییِ رجیستری: ✓ یعنی «امروز رویِ بوم می‌آید»، ✗ یعنی نه */}
                <span className="flex shrink-0 items-center gap-1 text-3xs text-text-muted">
                  <span title={e.engines.klinecharts ? 'در KLineCharts رسم می‌شود' : 'در KLineCharts رسم نمی‌شود'}>
                    K {e.engines.klinecharts ? '✓' : '✗'}
                  </span>
                  <span title={e.engines.ffc ? 'در FFC رسم می‌شود' : 'در FFC رسم نمی‌شود'}>
                    F {e.engines.ffc ? '✓' : '✗'}
                  </span>
                </span>
                <span data-testid={`fts-layer-state-${e.id}`}>
                  <Badge tone={STATE_TONE[evd.state]} title={`${e.fa}: ${LAYER_STATE_FA[evd.state]}`}>
                    {LAYER_STATE_FA[evd.state]}
                  </Badge>
                </span>
              </div>
            );
          })}
        </div>
      ))}

      {selected ? (() => {
        const evd = evidenceOf(selected);
        return (
          <div
            className="flex flex-col gap-1.5 rounded-lg border border-border-accent bg-bg-card/60 p-2.5"
            data-testid="fts-layer-evidence"
          >
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="text-2xs font-black text-text-primary">{selected.fa}</span>
              <span className="text-3xs text-text-muted">{selected.en}</span>
            </div>
            {/* زنجیرۀ ردپا: قاعده → خروجیِ الگوریتم → انوتیشنِ چارت */}
            <div className="text-3xs text-text-secondary" data-testid="fts-evidence-rule">
              قاعده: {selected.rule} — مرجع: docs/FTS-RULE-ALGORITHM-MAP.md
            </div>
            <div className="text-3xs text-text-muted" data-testid="fts-evidence-source">
              دهانۀ payload: <span className="num">{selected.source}</span> · ترسیم: {selected.display.join(' + ')}
            </div>
            {evd.facts.length > 0 ? (
              <dl className="grid grid-cols-2 gap-x-3 gap-y-0.5 text-[11px]">
                {evd.facts.map((f) => (
                  <div key={f.label} className="flex justify-between gap-2">
                    <dt className="text-text-secondary">{f.label}</dt>
                    <dd className="num font-bold text-text-primary">{f.value}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-[11px] text-text-muted" data-testid="fts-evidence-no-facts">
                سرور برایِ این لایه عددی منتشر نکرده است — چیزی برایِ نشان دادن نیست.
              </p>
            )}
            <div className="flex flex-wrap gap-3 text-3xs" data-testid="fts-evidence-times">
              <span className="text-text-secondary">
                کِی رخ داد: <span className="num text-text-primary">{evd.occurredAt ?? '—'}</span>
              </span>
              <span className="text-text-secondary" title="زمانِ تأیید؛ تا این لحظه مارکر قابل رسم نبود (ضدِ repaint)">
                کِی فهمیدیم: <span className="num text-text-primary">{evd.confirmedAt ?? '—'}</span>
              </span>
            </div>
            {evd.note ? (
              <p className="text-[11px] text-accent-yellow" data-testid="fts-evidence-note">
                {evd.note}
              </p>
            ) : null}
          </div>
        );
      })() : (
        <p className="text-3xs text-text-muted">
          رویِ نامِ هر لایه کلیک کنید: قاعدۀ جزوه، خروجیِ الگوریتم و زمانِ وقوع/تأییدِ همان انوتیشن.
        </p>
      )}
    </div>
  );
}
