// features/master/lib/useActiveFunnelPreset.ts — تنها منبعِ «presetِ فعالِ قیف»
//
// §۴ سند: یک verdictِ canonical، یک درخواستِ مشترک، چند مصرف‌کننده. تا پیش از این
// dossier از `horizon`، جدول از `URL>saved>prop`، و سایدبار از `'custom'`ِ hardcode
// می‌خواندند ⇒ همان universe دو بار محاسبه می‌شد (دو «داور»). حالا هر سه همین را
// صدا می‌زنند. اولویتِ تعیینِ preset: URL > انتخابِ خودِ کاربر (funnelPrefs.preset) > افق.
import { useSearchParams } from 'react-router';
import { useStrategyStore } from '@shared/stores/strategyStore';
import { useFunnelPrefsStore, type FunnelPreset } from '../stores/funnelPrefsStore';
import type { TreePreset } from './ftsFunnel';

const VALID: readonly TreePreset[] = ['swing', 'trend', 'hourglass', 'custom'];

/** `fallback` آخرین مرجع است — درِ production افقِ سراسری (`horizon`). */
export function useActiveFunnelPreset(fallback?: TreePreset): TreePreset {
  const [params] = useSearchParams();
  const saved = useFunnelPrefsStore((s) => s.preset) as FunnelPreset | null;
  const horizon = useStrategyStore((s) => s.horizon);
  const raw = params.get('preset') as TreePreset | null;
  if (raw && VALID.includes(raw)) return raw;
  return (saved as TreePreset | null) ?? fallback ?? horizon;
}
