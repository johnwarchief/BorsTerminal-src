// widgets/inspectorStage.ts -- تبِ فعال ⇒ مرحلۀ قیف FTS
// مالک: «وقتی نماد رو انتخاب میکنیم بر اساس تبی که توش هستیم بگی الان تو چه
// مرحله‌ای هستیم، بعد باید بریم تکنیکال بعد بنیادی». نامِ مرحلها عینِ قیف است.
export type InspectorStage = { key: string; label: string; base: string };

export const INSPECTOR_STAGES: readonly InspectorStage[] = [
  { key: 'tape', label: 'تابلوخوانی', base: '/market' },
  { key: 'technical', label: 'تکنیکال', base: '/technical' },
  { key: 'fundamental', label: 'بنیادی', base: '/fundamental' },
  { key: 'handover', label: 'تحویل', base: '/master' },
];

/** ریشۀ مسیر (~/technical/شپنا ⇒ /technical)؛ تبهایِ بیرونِ قیف null می‌دهند */
export function stageIndexForPath(pathname: string): number | null {
  const base = '/' + (pathname.split('/')[1] ?? '');
  if (base === '/portfolio' || base === '/strategy-tree') return INSPECTOR_STAGES.length - 1;
  const i = INSPECTOR_STAGES.findIndex((s) => s.base === base);
  return i === -1 ? null : i;
}

/** تابلوخوانی نماد را در مسیر نمی‌خواهد؛ سه مرحلۀ بعدی بله */
export function stageHref(index: number, symbol: string): string {
  const stage = INSPECTOR_STAGES[index];
  if (!stage) return '/market';
  if (stage.key === 'tape' || !symbol) return stage.base;
  return `${stage.base}/${encodeURIComponent(symbol)}`;
}
