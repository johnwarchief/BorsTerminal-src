import type { AssetType } from './assetType';

/** پیش‌فرضِ محصول: سهام، پایه، حق تقدم، انرژی، صندوق — اوراق/اختیار/... خاموش */
export const DEFAULT_ASSET_TYPES: AssetType[] = ['stock', 'payeh', 'right', 'energy', 'fund'];

export function sameAssetSets(a: readonly AssetType[], b: readonly AssetType[]): boolean {
  if (a.length !== b.length) return false;
  const set = new Set(a);
  return b.every((t) => set.has(t));
}
