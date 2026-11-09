import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson, requestJson } from '@shared/api/http';

const LastUpdateSchema = z.looseObject({
  status: z.string(),
  from: z.string().nullish(),
  to: z.string().nullish(),
  at: z.string().nullish(),
  message: z.string().nullish(),
});

const VersionSchema = z.looseObject({
  version: z.string(),
  mode: z.string().nullish(),
  rollback_available: z.boolean().optional(),
  rollback_version: z.string().nullish(),
  last_update: LastUpdateSchema.nullish(),
});

const CheckSchema = z.looseObject({
  status: z.string(),
  current_version: z.string().nullish(),
  latest_version: z.string().nullish(),
  available: z.boolean().optional(),
  installable: z.boolean().optional(),
  portable: z.boolean().optional(),
  notes: z.string().nullish(),
  size: z.number().nullish(),
  message: z.string().nullish(),
});

const ProgressSchema = z.looseObject({
  status: z.string(),
  downloaded: z.number().optional(),
  total: z.number().optional(),
  version: z.string().nullish(),
  message: z.string().nullish(),
});

const ActionSchema = z.looseObject({ status: z.string(), message: z.string().nullish() });

export type UpdateVersion = z.infer<typeof VersionSchema>;
export type UpdateCheck = z.infer<typeof CheckSchema>;
export type UpdateProgress = z.infer<typeof ProgressSchema>;

export function useUpdateVersion() {
  return useQuery<UpdateVersion>({
    queryKey: ['update', 'version'],
    queryFn: ({ signal }) => getJson('/api/update/version', VersionSchema, signal),
    refetchInterval: 30_000,
    staleTime: 10_000,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateProgress(enabled: boolean) {
  return useQuery<UpdateProgress>({
    queryKey: ['update', 'progress'],
    queryFn: ({ signal }) => getJson('/api/update/progress', ProgressSchema, signal),
    enabled,
    refetchInterval: enabled ? 600 : false,
    refetchOnWindowFocus: false,
  });
}

export function useUpdateCheck() {
  return useMutation<UpdateCheck>({
    mutationFn: () => getJson('/api/update/check', CheckSchema),
  });
}

export function useUpdateDownload() {
  const qc = useQueryClient();
  return useMutation<z.infer<typeof ActionSchema>>({
    mutationFn: () => requestJson('/api/update/download', ActionSchema, { method: 'POST', body: {} }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['update', 'progress'] }),
  });
}

export function useUpdateInstall() {
  return useMutation<z.infer<typeof ActionSchema>>({
    mutationFn: () => requestJson('/api/update/install', ActionSchema, { method: 'POST', body: {} }),
  });
}

export function useUpdateRollback() {
  return useMutation<z.infer<typeof ActionSchema>>({
    mutationFn: () => requestJson('/api/update/rollback', ActionSchema, { method: 'POST', body: {} }),
  });
}
