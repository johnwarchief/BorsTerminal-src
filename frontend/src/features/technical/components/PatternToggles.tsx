// features/technical/components/PatternToggles.tsx -- سوییچ‌های مستقل ۹ الگوی FTS (رنگ/شفافیت)
// هر الگو مستقل: خاموش ⇒ هیچ اورلی ساخته نمی‌شود. ترجیحات در localStorage پایدار می‌مانند.
import { PATTERN_LABELS, type PatternKind } from '../lib/patternOverlays';
import { usePatternPrefsStore } from '../stores/patternPrefsStore';

const KINDS = Object.keys(PATTERN_LABELS) as PatternKind[];

export function PatternToggles() {
  const prefs = usePatternPrefsStore((s) => s.prefs);
  const toggle = usePatternPrefsStore((s) => s.toggle);
  const setPref = usePatternPrefsStore((s) => s.setPref);
  const reset = usePatternPrefsStore((s) => s.reset);

  return (
    <div className="grid grid-cols-1 gap-1 md:grid-cols-2" data-testid="pattern-toggles">
      <span className="col-span-full text-[11px] font-bold text-text-secondary">الگوهای FTS (مستقل)</span>
      {KINDS.map((k) => (
        <div key={k} className="flex items-center gap-2 rounded border border-border-c bg-bg-card/40 px-2 py-1">
          <input
            type="checkbox"
            checked={prefs[k].enabled}
            onChange={() => toggle(k)}
            data-testid={`pattern-toggle-${k}`}
            aria-label={PATTERN_LABELS[k]}
            className="accent-sky-400"
          />
          <span className="min-w-0 flex-1 truncate text-[11px] text-text-secondary">{PATTERN_LABELS[k]}</span>
          <input
            type="color"
            value={prefs[k].color}
            onChange={(e) => setPref(k, { color: e.target.value })}
            data-testid={`pattern-color-${k}`}
            aria-label={`رنگ ${PATTERN_LABELS[k]}`}
            className="h-5 w-6 rounded border border-border-c bg-transparent"
          />
          <input
            type="range"
            min={5}
            max={100}
            value={Math.round(prefs[k].opacity * 100)}
            onChange={(e) => setPref(k, { opacity: Number(e.target.value) / 100 })}
            data-testid={`pattern-opacity-${k}`}
            aria-label={`شفافیت ${PATTERN_LABELS[k]}`}
            className="h-1 w-20 accent-sky-400"
          />
          <span className="num w-8 text-left text-[10px] text-text-muted">{Math.round(prefs[k].opacity * 100)}</span>
        </div>
      ))}
      <button
        type="button"
        data-testid="pattern-reset"
        onClick={reset}
        className="col-span-full self-start rounded border border-border-c px-2 py-0.5 text-[11px] text-text-muted hover:text-accent-blue"
      >
        بازنشانی پیش‌فرض‌ها
      </button>
    </div>
  );
}
