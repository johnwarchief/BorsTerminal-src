// features/technical/engine/registry.ts -- تنها جایی که «کدام موتور هست» را
// می‌داند. آزمایشگاه و چارتِ اصلی از اینجا می‌سازند، هیچ‌کدام importِ مستقیمِ
// موتور ندارند؛ برایِ همین افزودنِ موتورِ سوم یک سطرِ همین‌جا است.
import type { ChartEngine } from './ChartEngine';
import type { ChartEngineId } from './types';
import { KLineChartsEngine } from './klinecharts/KLineChartsEngine';

export type EngineEntry = {
  id: ChartEngineId;
  /** عنوانِ فارسیِ همان «موتور» درِ فهرست */
  title: string;
  /** ساختنِ نمونه — lazy تا باندلِ FFC فقط وقتی لازم شد بیاید */
  create: () => Promise<ChartEngine>;
  /** موتور درِ این ساختِ اپ فعال است؟ آزمایشگاه برخلافِ چارتِ اصلی هر دو را می‌پذیرد */
  production: boolean;
};

export const ENGINE_REGISTRY: EngineEntry[] = [
  {
    id: 'klinecharts',
    title: 'KLineCharts (موتورِ فعلی)',
    create: async () => new KLineChartsEngine(),
    production: true,
  },
  {
    id: 'ffc',
    title: 'Fast Financial Charts (آزمایشی)',
    create: async () => {
      const mod = await import('./ffc/FastFinancialChartsEngine');
      return new mod.FastFinancialChartsEngine();
    },
    production: false,
  },
];

export const DEFAULT_ENGINE: ChartEngineId = 'klinecharts';

export function engineEntry(id: ChartEngineId): EngineEntry | undefined {
  return ENGINE_REGISTRY.find((e) => e.id === id);
}

/** موتورِ پیش‌فرضِ تولید. اگر روزی FFC جانشین شد، فقط همین تغییر می‌کند */
export async function createDefaultEngine(): Promise<ChartEngine> {
  const entry = engineEntry(DEFAULT_ENGINE) ?? ENGINE_REGISTRY[0];
  return entry.create();
}
