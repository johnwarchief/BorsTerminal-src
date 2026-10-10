// features/market/api/useNotifications.ts -- خوانندۀ مرکزِ اعلان
//
// منبع، `codal_notices`ِ خودِ برنامه است (واکشیِ کدال)؛ هیچ سرویسِ بیرونیِ
// تازه‌ای افزوده نشده و هیچ تیترِ ساختگی درِ این لایه نیست. نوع و اهمیت از
// `notifications.py` (بک‌اند) می‌آید — رابط هیچ طبقه‌بندیِ دومی نمی‌سازد.
import { useQuery } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const str = z.string().nullish();
const num = z.number().nullish();

export const NoticeItemSchema = z.object({
  id: num,
  symbol: str,
  company: str,
  title: z.string(),
  kind: z.string(),
  level: z.string(),
  reason: z.string(),
  letter_code: str,
  publish_date: str,
  sent_date: str,
  received_at: str,
  url: str,
  source: z.string(),
  /** چند ردیفِ هم‌متن ادغام شد (حذفِ بی‌صدا نیست) */
  occurrences: num,
});
export type NoticeItem = z.infer<typeof NoticeItemSchema>;

export const NoticeFeedSchema = z.object({
  status: z.string(),
  source: z.string(),
  count: num,
  scanned: num,
  merged_duplicates: num,
  levels: z.array(z.string()).nullish(),
  since: str,
  message: str,
  items: z.array(NoticeItemSchema).default([]),
});
export type NoticeFeed = z.infer<typeof NoticeFeedSchema>;

export const NoticeSourcesSchema = z.object({
  status: z.string(),
  note: str,
  sources: z.array(z.object({
    source: z.string(),
    label: str,
    rows: num,
    newest_publish: str,
    last_fetch: str,
    state: z.string(),
    message: str,
  })).default([]),
});
export type NoticeSources = z.infer<typeof NoticeSourcesSchema>;

export function useNoticeSources() {
  return useQuery({
    queryKey: ['notifications-sources'],
    queryFn: ({ signal }) =>
      http<NoticeSources>('/api/notifications/sources', { schema: NoticeSourcesSchema, signal }),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  });
}

export function useNoticeFeed(levels: string[] = [], limit = 120) {
  const key = [...levels].sort().join(',');
  return useQuery({
    queryKey: ['notifications-feed', key, limit],
    queryFn: ({ signal }) => {
      const q = new URLSearchParams({ limit: String(limit) });
      if (key) q.set('levels', key);
      return http<NoticeFeed>(`/api/notifications/feed?${q.toString()}`, {
        schema: NoticeFeedSchema,
        signal,
      });
    },
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });
}
