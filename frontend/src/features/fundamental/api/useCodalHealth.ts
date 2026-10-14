// features/fundamental/api/useCodalHealth.ts -- سلامتِ خطِ دریافتِ خودکارِ کدال
//
// چرا این hook جداست (مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۷؛ spec درِ
// `docs/CODAL-AUTO-UPDATE-2026-10-14.md` §۵): پنلِ بنیادی هیچ‌جا نمی‌گفت داده
// «چند وقت است تازه می‌شود، چه چیزی درِ صف مانده، و آخرین چرخه موفق کی بود».
// پاسخِ `/api/sync/codal/pipeline` همهٔ آن را از **جدول** می‌دهد
// (`codal_pipeline.health`) — نه از شمارندهٔ حافظه‌ای — و اینجا فقط همان را
// می‌خواند: هیچ شمارشِ دومی درِ رابط ساخته نمی‌شود.
//
// دو نکته که بی‌آن‌ها این panel کهنه می‌ماند:
//  • `data_epoch` امضایِ «تازگیِ دادهٔ بنیادی» است (`bank + جدولِ صورتِ مالی`).
//    کارتِ FTS و غربالگری پشتِ `staleTime` ۱۰ دقیقه‌ای‌اند؛ بی‌باختنِ کش با
//    عوض‌شدنِ همین امضا، کاربر تا ده دقیقه عددِ قبلی را می‌بیند و پنلِ سلامت
//    راست می‌گوید که داده عوض شده. پس همین‌جا invalidate می‌شود، نه درِ هر مصرف‌کننده.
//  • هر خانۀ این پاسخ می‌تواند `null` باشد («ثبت نشده»). `null` درِ رابط صفر
//    نمی‌شود؛ علت نشان داده می‌شود.
import { useEffect, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { http } from '@shared/api/http';

const Counters = z.object({
  queued: z.number().nullish(),
  running: z.number().nullish(),
  done: z.number().nullish(),
  empty: z.number().nullish(),
  failed: z.number().nullish(),
  unresolved: z.number().nullish(),
  total: z.number().nullish(),
  legacy: z.number().nullish(),
  retryable: z.number().nullish(),
});

const Instruments = z.object({
  ledger: z.number().nullish(),
  present: z.number().nullish(),
  absent: z.number().nullish(),
  removed: z.number().nullish(),
  ambiguous: z.number().nullish(),
  no_publisher: z.number().nullish(),
  no_fundamental: z.number().nullish(),
});

export const CodalHealthSchema = z
  .object({
    /** اندپوینتِ خطا را با `status: 'error'` و همان HTTP 200 می‌فرستد */
    status: z.string().nullish(),
    message: z.string().nullish(),
    queue: Counters.nullish(),
    instruments: Instruments.nullish(),
    dirty_symbols: z.number().nullish(),
    incomplete_extractions: z.number().nullish(),
    undated_notices: z.number().nullish(),
    data_epoch: z.string().nullish(),
    last_data_update: z.string().nullish(),
    last_successful_sync: z.string().nullish(),
    last_attempt: z.string().nullish(),
    checked_at: z.string().nullish(),
    offline_gate: z.boolean().nullish(),
    worker: z
      .object({
        running: z.boolean().nullish(),
        owner: z.string().nullish(),
        started_at: z.string().nullish(),
        cycles: z.number().nullish(),
        last: z.string().nullish(),
        last_error: z.string().nullish(),
      })
      .nullish(),
    lock: z
      .object({
        held: z.boolean().nullish(),
        owner: z.string().nullish(),
        heartbeat_at: z.string().nullish(),
        note: z.string().nullish(),
      })
      .nullish(),
    catchup: z
      .object({
        last_successful_sync: z.string().nullish(),
        gap_seconds: z.number().nullish(),
        never_synced: z.boolean().nullish(),
        queued: z.number().nullish(),
        failed: z.number().nullish(),
        running: z.number().nullish(),
        unresolved: z.number().nullish(),
        retryable: z.number().nullish(),
        dirty: z.number().nullish(),
        last_network_pass: z.string().nullish(),
      })
      .nullish(),
    cadence: z
      .object({
        at: z.string().nullish(),
        seconds: z.number().nullish(),
        reason: z.string().nullish(),
        need_network: z.boolean().nullish(),
      })
      .nullish(),
  })
  // فیلدهایِ تازهٔ بک‌اند نباید باعث شوند کلِ پاسخ درِ parse بیفتد و پنل
  // «نرسید» بگوید (همان رگرسیونی که درِ useFtsCard ثبت شده).
  .catchall(z.unknown());

export type CodalHealth = z.infer<typeof CodalHealthSchema>;
export type CodalQueue = NonNullable<CodalHealth['queue']>;

export function useCodalHealth() {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ['codal-health'],
    queryFn: ({ signal }) =>
      http<CodalHealth>('/api/sync/codal/pipeline', { schema: CodalHealthSchema, signal }),
    // دو دقیقه: چرخۀ کشف خودِ سرور رویِ همین ریتم است؛ تازه‌تر از این یعنی
    // پولینگِ بی‌فایده رویِ یکِ پاسخِ چندکوئری‌ای.
    refetchInterval: 120_000,
    staleTime: 30_000,
  });

  // باختنِ کشِ کارت/غربالگری با عوض‌شدنِ امضایِ تازگی — یک‌بار به‌ازایِ هر epoch.
  const seen = useRef<string | null>(null);
  const epoch = q.data?.data_epoch ?? null;
  useEffect(() => {
    if (!epoch) return;
    if (seen.current === null) {
      // اولین خواندنِ این نشست: کارت‌ها همین حالا با همان داده کش شده‌اند،
      // پس بی‌دلیل بازشان نمی‌کنیم.
      seen.current = epoch;
      return;
    }
    if (seen.current === epoch) return;
    seen.current = epoch;
    qc.invalidateQueries({ queryKey: ['fts-card'] });
    qc.invalidateQueries({ queryKey: ['fts-screen'] });
  }, [epoch, qc]);

  return q;
}
