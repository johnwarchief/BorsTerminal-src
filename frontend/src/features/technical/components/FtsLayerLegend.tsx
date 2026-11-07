// features/technical/components/FtsLayerLegend.tsx -- افسانۀ لایه‌های رسم‌شده رویِ چارت
// کلیدِ رنگ/نامِ همان چیزی که رویِ بوم است، درِ هر دو موتور. فهرست از همان
// رجیستری + همان رنگ‌هایِ ترجیحات ساخته می‌شود، پس «افسانه» چیزی را که چارت
// نگفته تضمین نمی‌کند: لایه‌ای که درِ این موتور رسم نمی‌شود (engines[*] = false)
// درِ افسانه هم نیست.
import { CATALOG_GROUPS, CHART_VIEW_FLAGS, FTS_INDICATOR_CATALOG, type IndicatorGroupId } from '../lib/ftsIndicatorCatalog';
import { LAYER_STATE_FA, layerEvidence } from '../lib/ftsLayerEvidence';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import type { Structure3Data } from '../api/useStructure3';
import type { PatternPrefs } from '../lib/patternOverlays';
import { usePatternPrefsStore } from '../stores/patternPrefsStore';
import { useFtsConfigStore } from '../stores/ftsConfigStore';
import { layerColor } from './FtsIndicatorPanel';
import type { ChartEngineId } from '../engine/types';

/** توسلِ لایه از بیرونِ چارت: همان storeها، همان مسیرِ پنل */
function useLayerFlags() {
  const prefs = usePatternPrefsStore((s) => s.prefs);
  const togglePattern = usePatternPrefsStore((s) => s.toggle);
  const view = useFtsConfigStore((s) => s.view);
  const setView = useFtsConfigStore((s) => s.setView);
  // پرچم‌های view از همان فهرستِ کاتالوگ خوانده می‌شوند؛ «توسلِ پیش‌فرض روشن»
  // فقط رویدادهایِ شرکتی است، بقیه با true صریح روشن می‌شوند.
  const flag = (t: string): boolean =>
    t === 'showCorporateActions' ? view?.showCorporateActions !== false : view?.[t as keyof typeof view] === true;
  const enabled = (t: string | null): boolean | null => {
    if (t === null) return null;
    if ((CHART_VIEW_FLAGS as readonly string[]).includes(t)) return flag(t);
    return prefs[t as keyof PatternPrefs]?.enabled ?? null;
  };
  return { prefs, enabled, setEnabled: (t: string | null, on: boolean) => {
    if (t && (CHART_VIEW_FLAGS as readonly string[]).includes(t)) {
      setView({ [t]: on } as Partial<typeof view>);
      return;
    }
    if (t) togglePattern(t as keyof PatternPrefs);
  } };
}

export function FtsLayerLegend({
  fts,
  engineId,
  adjustmentEvents,
  e3,
}: {
  fts: FtsAnalysisData | null | undefined;
  engineId: ChartEngineId;
  adjustmentEvents?: number | null;
  e3?: Structure3Data | null;
}) {
  const { prefs, enabled, setEnabled } = useLayerFlags();
  const drawn = FTS_INDICATOR_CATALOG.filter((e) => {
    if (e.engines[engineId] !== true) return false;
    const on = enabled(e.toggle);
    if (on === false) return false;
    const st = layerEvidence(e, fts, { adjustmentEvents: adjustmentEvents ?? null, structure3: e3 ?? null }).state;
    // افسانه جایِ «لایه‌ای که همین حالا رویِ بوم است» است؛ پیش‌نویس هم رسم
    // می‌شود (برچسبِ «در حال تشکیل» دارد) پس می‌آید، «فعال نیست» نه.
    return st === 'active' || st === 'forming';
  });

  if (drawn.length === 0) {
    return (
      <div className="pointer-events-none rounded border border-border-c bg-bg-primary/80 px-2 py-1 text-3xs text-text-muted" data-testid="fts-layer-legend">
        افسانۀ FTS: لایۀ فعالی رویِ چارت نیست
      </div>
    );
  }

  return (
    <div className="flex max-w-[min(92vw,560px)] flex-wrap items-center gap-1.5 rounded border border-border-c bg-bg-primary/85 px-2 py-1" data-testid="fts-layer-legend" dir="rtl">
      <span className="text-3xs font-bold text-text-secondary">افسانۀ FTS</span>
      {drawn.map((e) => {
        const groupTitle = CATALOG_GROUPS[e.group as IndicatorGroupId].fa;
        const state = layerEvidence(e, fts, { adjustmentEvents: adjustmentEvents ?? null, structure3: e3 ?? null }).state;
        const chip = (
          <span className="flex items-center gap-1.5 text-3xs text-text-secondary">
            <span className="h-2 w-2 shrink-0 rounded-full" style={{ background: layerColor(e, prefs) }} aria-hidden="true" />
            {e.fa}
          </span>
        );
        // لایه‌ای که توسلِ جدا ندارد دکمهٔ مرده نمی‌شود (قاعدۀ نوارِ ابزارِ چارت)
        if (e.toggle === null) {
          return (
            <span key={e.id} title={`${groupTitle} · ${LAYER_STATE_FA[state]}`} data-testid={`fts-legend-item-${e.id}`}>
              {chip}
            </span>
          );
        }
        return (
          <button
            key={e.id}
            type="button"
            onClick={() => setEnabled(e.toggle, false)}
            title={`${groupTitle} · ${LAYER_STATE_FA[state]} — کلیک: خاموش‌کردنِ این لایه`}
            data-testid={`fts-legend-item-${e.id}`}
            className="rounded px-0.5 transition-colors hover:bg-bg-card hover:text-text-primary"
          >
            {chip}
          </button>
        );
      })}
    </div>
  );
}
