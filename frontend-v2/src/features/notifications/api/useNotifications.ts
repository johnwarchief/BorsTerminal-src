import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { getJson } from '@shared/api/http';

const NoticeSchema = z.looseObject({
  id: z.union([z.string(), z.number()]).nullish(),
  level: z.enum(['high', 'medium', 'low', 'unclassified']),
  title: z.string(),
  symbol: z.string().nullish(),
  company: z.string().nullish(),
  publish_date: z.string().nullish(),
  url: z.string().nullish(),
  kind: z.string().nullish(),
  occurrences: z.number().nullish(),
});

export const FeedSchema = z.looseObject({
  status: z.literal('ok'),
  items: z.array(NoticeSchema),
});

export const SourcesSchema = z.looseObject({
  status: z.literal('ok'),
  sources: z.array(z.looseObject({
    source: z.string(),
    label: z.string().nullish(),
    rows: z.number().nullish(),
    state: z.string(),
    message: z.string().nullish(),
    newest_publish: z.string().nullish(),
    last_fetch: z.string().nullish(),
  })),
});

export type NoticeFeed = z.infer<typeof FeedSchema>;
export type NotificationSources = z.infer<typeof SourcesSchema>;

export function useNotificationsFeed(level?: string) {
  const suffix = level ? `?levels=${encodeURIComponent(level)}` : '';
  return useQuery<NoticeFeed>({
    queryKey: ['notifications', level ?? 'all'],
    queryFn: ({ signal }) => getJson(`/api/notifications/feed${suffix}`, FeedSchema, signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}

export function useNotificationSources() {
  return useQuery<NotificationSources>({
    queryKey: ['notification-sources'],
    queryFn: ({ signal }) => getJson('/api/notifications/sources', SourcesSchema, signal),
    refetchInterval: 60_000,
    staleTime: 30_000,
    refetchOnWindowFocus: false,
  });
}
