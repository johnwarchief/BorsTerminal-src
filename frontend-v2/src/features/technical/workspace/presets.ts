/**
 * frontend-v2/src/features/technical/workspace/presets.ts
 *
 * مودها و چیدمان‌های نام‌دار میزکار ۲.۰ (E1):
 *   تحلیل: چارت + بازرس + فید  (سهم چارت ≥۶۰٪ در ۱۳۶۶)
 *   اسکن: ۵۰ نماد + چارت فشرده + فید (سهم چارت ≥۵۵٪)
 *   پژوهش: چارت + بنیادی + فید + بازرس (سهم چارت ≥۵۰٪)
 *
 * این فایل هیچ مؤلفه‌ای ایمپورت نمی‌کند؛ فقط درخت چیدمان و سقف‌های
 * پنلی میزکار تکنیکال را می‌سازد تا استور خالص بماند.
 */

import {
  panelsInOrder, type LayoutNode, type SplitDir,
} from '@shared/workspace/layout';

export type WorkspaceMode = 'analysis' | 'scan' | 'research';

export const WORKSPACE_MODES: WorkspaceMode[] = ['analysis', 'scan', 'research'];

export const MODE_LABEL: Record<WorkspaceMode, string> = {
  analysis: 'تحلیل',
  scan: 'اسکن',
  research: 'پژوهش',
};

export type TechnicalPanelKind =
  | 'chart' | 'inspector' | 'feed' | 'scanner' | 'fundamental' | 'indicators';

export const PANEL_KIND_LABEL: Record<TechnicalPanelKind, string> = {
  chart: 'چارت',
  inspector: 'بازرس',
  feed: 'فید رویدادها',
  scanner: '۵۰ نماد',
  fundamental: 'بنیادی',
  indicators: 'اندیکاتورها',
};

export interface NamedLayout {
  id: string;
  name: string;
  mode: WorkspaceMode;
  root: LayoutNode<TechnicalPanelKind>;
  panelKinds: Record<string, TechnicalPanelKind>;
}

/** حداقل‌های پنل طبق §4: هر پنل ۳۲۰px و چارت ۴۸۰px. */
export const TECHNICAL_PANEL_MIN: Record<TechnicalPanelKind, { w: number; h: number }> = {
  chart: { w: 480, h: 320 },
  inspector: { w: 320, h: 240 },
  feed: { w: 320, h: 240 },
  scanner: { w: 320, h: 240 },
  fundamental: { w: 320, h: 240 },
  indicators: { w: 320, h: 240 },
};

/** سهم عرضیِ چارت از کل ویوپورت (شکست‌های عمودی سهم عرض را نمی‌شکنند). */
export function chartShareOf(
  root: LayoutNode<TechnicalPanelKind>, kind: TechnicalPanelKind = 'chart',
): number {
  let share = 0;
  function walk(node: LayoutNode<TechnicalPanelKind>, factor: number): void {
    if (node.kind === 'tile') {
      if (node.panel === kind) share += factor;
      return;
    }
    if (node.dir === 'row') {
      walk(node.first, factor * node.ratio);
      walk(node.second, factor * (1 - node.ratio));
    } else {
      walk(node.first, factor);
      walk(node.second, factor);
    }
  }
  walk(root, 1);
  return share;
}

/** سقف/کفِ نسبتِ شکاف بر پایهٔ حداقل‌های پنل تکنیکال. */
export function clampTechnicalRatio(
  node: LayoutNode<TechnicalPanelKind>, ratio: number, width: number, height: number,
): number | null {
  if (node.kind !== 'split') return null;
  const total = node.dir === 'row' ? width : height;
  if (total <= 0) return null;
  const axis = node.dir === 'row' ? 'w' : 'h';

  const minExtent = (item: LayoutNode<TechnicalPanelKind>): number => {
    if (item.kind === 'tile') return TECHNICAL_PANEL_MIN[item.panel][axis];
    const sameAxis = (item.dir === 'row') === (axis === 'w');
    return sameAxis
      ? minExtent(item.first) + minExtent(item.second)
      : Math.max(minExtent(item.first), minExtent(item.second));
  };

  const lo = minExtent(node.first) / total;
  const hi = 1 - minExtent(node.second) / total;
  if (lo > hi) return null;
  return Math.min(hi, Math.max(lo, ratio));
}

export function panelKindsOf(
  root: LayoutNode<TechnicalPanelKind>,
): Record<string, TechnicalPanelKind> {
  const kinds: Record<string, TechnicalPanelKind> = {};
  for (const tile of panelsInOrder(root)) kinds[tile.id] = tile.panel;
  return kinds;
}

export function panelsOfKind(root: LayoutNode<TechnicalPanelKind>): TechnicalPanelKind[] {
  return panelsInOrder(root).map((tile) => tile.panel);
}

function leaf(id: string, panel: TechnicalPanelKind): LayoutNode<TechnicalPanelKind> {
  return { kind: 'tile', id, panel, follow: false };
}

function split(
  id: string, dir: SplitDir, ratio: number,
  first: LayoutNode<TechnicalPanelKind>, second: LayoutNode<TechnicalPanelKind>,
): LayoutNode<TechnicalPanelKind> {
  return { kind: 'split', id, dir, ratio, first, second };
}

export interface Preset {
  id: string;
  name: string;
  mode: WorkspaceMode;
  root: LayoutNode<TechnicalPanelKind>;
}

export const TECHNICAL_PRESETS: Record<WorkspaceMode, Preset> = {
  analysis: {
    id: 'layout-analysis-default',
    name: 'تحلیل پیش‌فرض',
    mode: 'analysis',
    // چارت ۶۸٪ عرض؛ ستون سمت راست: بازرس بالا، فید پایین.
    root: split('ta-root', 'row', 0.68,
      leaf('ta-chart', 'chart'),
      split('ta-side', 'col', 0.5,
        leaf('ta-inspector', 'inspector'),
        leaf('ta-feed', 'feed'))),
  },
  scan: {
    id: 'layout-scan-default',
    name: 'اسکن پیش‌فرض',
    mode: 'scan',
    // چارت ۵۸٪ عرض؛ ۵۰ نماد بالا و فید پایین در ستون باریک.
    root: split('ts-root', 'row', 0.58,
      leaf('ts-chart', 'chart'),
      split('ts-side', 'col', 0.55,
        leaf('ts-scanner', 'scanner'),
        leaf('ts-feed', 'feed'))),
  },
  research: {
    id: 'layout-research-default',
    name: 'پژوهش پیش‌فرض',
    mode: 'research',
    // چارت ۵۱٪ عرض؛ بنیادی/بازرس بالا و فید پایین در ستون کنار.
    root: split('tr-root', 'row', 0.51,
      leaf('tr-chart', 'chart'),
      split('tr-side', 'col', 0.52,
        split('tr-top', 'row', 0.5,
          leaf('tr-fundamental', 'fundamental'),
          leaf('tr-inspector', 'inspector')),
        leaf('tr-feed', 'feed'))),
  },
};

export function cloneLayout(
  root: LayoutNode<TechnicalPanelKind>,
): LayoutNode<TechnicalPanelKind> {
  if (root.kind === 'tile') return { ...root };
  return { ...root, first: cloneLayout(root.first), second: cloneLayout(root.second) };
}

export function layoutFromPreset(preset: Preset): NamedLayout {
  const root = cloneLayout(preset.root);
  return {
    id: preset.id,
    name: preset.name,
    mode: preset.mode,
    root,
    panelKinds: panelKindsOf(root),
  };
}

export function initialLayouts(): Record<WorkspaceMode, NamedLayout[]> {
  return {
    analysis: [layoutFromPreset(TECHNICAL_PRESETS.analysis)],
    scan: [layoutFromPreset(TECHNICAL_PRESETS.scan)],
    research: [layoutFromPreset(TECHNICAL_PRESETS.research)],
  };
}
