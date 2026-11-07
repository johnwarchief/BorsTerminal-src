/**
 * model/spotlight/select.ts
 *
 * انتخاب «یک» الگوی اصلی برای اسپات‌لایت (spec §3.1):
 * - استخر: الگوهای زندهٔ (غیرِ مرده) با anchor در ۲۵۰ کندل آخر یا محدودهٔ دید.
 * - اولویت: forming در ۶۰ کندل آخر ← confirmed در ۱۲۰ کندل آخر ← بقیه.
 * - در هر گروه: کیفیت، سپس تازگی anchor.
 * - W/M فقط از منبع doubleTap؛ DOUBLE_TOP/BOTTOM کلاسیک هرگز کاندید نمی‌شوند.
 * - اگر هیچ الگویی در پنجره‌ها نبود، بالاترین کیفیت کل استخر برجسته می‌شود.
 */
import type { SpotlightModel, SpotlightStatus } from './types';

export const SPOTLIGHT_LOOKBACK_BARS = 250;
export const SPOTLIGHT_FORMING_WINDOW_BARS = 60;
export const SPOTLIGHT_CONFIRMED_WINDOW_BARS = 120;

const CONFIRMED_STATUSES: ReadonlySet<SpotlightStatus> = new Set<SpotlightStatus>([
  'confirmed',
  'active',
  'tp1_hit',
  'tp2_hit',
]);

function isDead(status: SpotlightStatus): boolean {
  return status === 'invalidated' || status === 'failed' || status === 'timed_out';
}

function isClassicDouble(model: SpotlightModel): boolean {
  return model.source === 'classic' && (model.kind === 'DOUBLE_TOP' || model.kind === 'DOUBLE_BOTTOM');
}

/** کیفیت، سپس تازگی anchor؛ خروجی یکتا. */
function bestOf(models: readonly SpotlightModel[]): SpotlightModel | null {
  let best: SpotlightModel | null = null;
  for (const model of models) {
    if (
      best == null
      || model.quality > best.quality
      || (model.quality === best.quality && model.anchorIndex > best.anchorIndex)
    ) {
      best = model;
    }
  }
  return best;
}

export function selectSpotlightPattern(
  models: readonly SpotlightModel[],
  lastIndex: number,
  visibleRange?: [number, number],
): SpotlightModel | null {
  if (models.length === 0) return null;

  const from = visibleRange ? visibleRange[0] : lastIndex - SPOTLIGHT_LOOKBACK_BARS;
  const to = Math.min(visibleRange ? visibleRange[1] : lastIndex, lastIndex);
  const alive = models.filter((model) => !isDead(model.status) && !isClassicDouble(model));

  const inWindow = alive.filter(
    (model) => model.anchorIndex >= from && model.anchorIndex <= to,
  );

  const forming = bestOf(
    inWindow.filter(
      (model) =>
        model.status === 'forming'
        && model.anchorIndex >= lastIndex - SPOTLIGHT_FORMING_WINDOW_BARS,
    ),
  );
  if (forming) return forming;

  const confirmed = bestOf(
    inWindow.filter(
      (model) =>
        CONFIRMED_STATUSES.has(model.status)
        && model.anchorIndex >= lastIndex - SPOTLIGHT_CONFIRMED_WINDOW_BARS,
    ),
  );
  if (confirmed) return confirmed;

  // بقیهٔ کاندیدهای داخل پنجره (مثلاً forming قدیمی یا confirmedِ بین ۱۲۰ تا ۲۵۰).
  const rest = bestOf(inWindow);
  if (rest) return rest;

  // هیچ الگویی در پنجره نبود: بالاترین کیفیتِ کل استخر.
  return bestOf(alive);
}
