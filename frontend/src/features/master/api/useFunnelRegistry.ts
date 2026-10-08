// features/master/api/useFunnelRegistry.ts — فهرستِ فیلترهایِ Custom از خودِ بک‌اند
//
// قانونِ مأموریت (§۵ و §۸): «لیست Custom باید از Registry بیاید، نه از یک array
// دست‌ساز ناقص.» تا پیش از این `FILE_FILTERS` درِ `lib/ftsFunnel.ts` پنج فیلترِ
// ثابت را می‌شمرد و «پول هوشمند»/«کد به کد» درِ Custom دیده نمی‌شدند، با اینکه
// موتور هر هفت را می‌شناسد. اینجا همان `GET /api/funnel/registry` خوانده می‌شود
// — با source_file، source_hash و نسخۀ فرمول، تا هر چیپ بگوید قانونش از کجاست.
import { useQuery } from '@tanstack/react-query';
import { http } from '@shared/api/http';

export type RegistryParam = {
  param_id: string; label: string; source?: string; value?: number | null;
  value_text?: string | null; unit?: string | null; configurable?: boolean;
  min?: number | null; max?: number | null; note?: string | null;
};

export type RegistryFilter = {
  filter_id: string; name: string; description?: string | null;
  source_file?: string | null; source_hash?: string | null;
  formula_version?: string | null; backend_impl?: string | null;
  availability?: string | null; status?: string | null; note?: string | null;
  params?: RegistryParam[];
};

export type RegistryPreset = {
  preset_id: string; label: string; chain: string[]; technical_gate?: string | null;
  source?: string | null; status?: string | null; note?: string | null;
};

export type RegistryPayload = {
  registry_version?: string;
  ruleset_version?: string;
  filters: RegistryFilter[];
  presets: RegistryPreset[];
  unimplemented_filters?: RegistryFilter[];
  gates?: Record<string, unknown>;
};

/** رجیستری ثابت است تا رجیستری بازتولید نشود (ruleset_version درِ کلید است). */
export function registryQueryKey() {
  return ['funnel-registry'];
}

export function useFunnelRegistry() {
  const q = useQuery<RegistryPayload>({
    queryKey: registryQueryKey(),
    queryFn: () => http<RegistryPayload>('/api/funnel/registry'),
    staleTime: 300_000,
  });
  const filters = q.data?.filters ?? [];
  return {
    filters,
    presets: q.data?.presets ?? [],
    unimplemented: q.data?.unimplemented_filters ?? [],
    rulesetVersion: q.data?.ruleset_version ?? '',
    loading: q.isPending,
    error: q.error ? String((q.error as Error).message ?? q.error) : null,
    byId: (id: string) => filters.find((f) => f.filter_id === id) ?? null,
  };
}
