// shared/components/FreshnessBadge.tsx — نشانِ تفکیک‌شدهٔ «اتصال» و «تازگیِ داده»
// داوری از `computeFeedStatus` می‌آید؛ هیچ عددی اینجا ساخته نمی‌شود. یک تیکِ آرام
// فقط برایِ این است که اگر تازه‌سازی خوابید (بدونِ notifyِ cache) سن و «کهنه» بزرگ
// شود — وگرنه نشانِ سبز رویِ دادهٔ منجمد می‌ماند.
import { useEffect, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { MARKET_FEED_KEY } from '@shared/api/marketFeed';
import type { MarketFeed } from '@shared/types/marketRow';
import { computeFeedStatus, type FeedStatus } from '@shared/lib/feedFreshness';
import { fmtAge } from '@shared/lib/time';

type Snap = { status: string; dataUpdatedAt: number; dataChangedAt: number | null;
              liveCount: number | null; total: number | null };

function readSnap(qc: ReturnType<typeof useQueryClient>): Snap {
  const q = qc.getQueryCache().find({ queryKey: MARKET_FEED_KEY });
  if (!q) return { status: 'idle', dataUpdatedAt: 0, dataChangedAt: null, liveCount: null, total: null };
  const d = q.state.data as MarketFeed | undefined;
  return {
    status: q.state.status,
    dataUpdatedAt: q.state.dataUpdatedAt,
    // «کی عدد عوض شد» از خودِ فید، نه از رسیدنِ پاسخِ HTTP.
    dataChangedAt: d?.rev_at ?? null,
    liveCount: d?.live_count ?? null,
    total: d?.count ?? null,
  };
}

export function FreshnessBadge() {
  const qc = useQueryClient();
  const [snap, setSnap] = useState<Snap>(() => readSnap(qc));
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    setSnap(readSnap(qc));
    const unsub = qc.getQueryCache().subscribe(() => {
      queueMicrotask(() => {
        const next = readSnap(qc);
        setSnap((prev) => (prev.status === next.status && prev.dataUpdatedAt === next.dataUpdatedAt
          && prev.dataChangedAt === next.dataChangedAt
          && prev.liveCount === next.liveCount && prev.total === next.total ? prev : next));
        setNow(Date.now());
      });
    });
    // تیکِ ۱۵ ثانیه‌ای: «کهنه» باید بی‌تغییریِ cache هم خودش را نشان بدهد.
    const id = setInterval(() => setNow(Date.now()), 15_000);
    return () => { unsub(); clearInterval(id); };
  }, [qc]);

  const st: FeedStatus = computeFeedStatus({
    status: snap.status, dataUpdatedAt: snap.dataUpdatedAt, dataChangedAt: snap.dataChangedAt,
    liveCount: snap.liveCount, totalCount: snap.total, now,
  });

  return (
    <span
      role="status"
      aria-label={st.label}
      data-testid="freshness-badge"
      data-freshness={st.freshness}
      data-connection={st.connection}
      data-data-age-ms={st.dataAgeMs ?? ''}
      className="inline-flex shrink-0 items-center gap-1.5"
      title={st.ageMs != null
        ? `${st.label} · آخرین دریافت: ${fmtAge(snap.dataUpdatedAt, now)}`
          + (snap.dataChangedAt
            ? ` · آخرین عوض‌شدنِ داده: ${fmtAge(snap.dataChangedAt, now)}`
            : '')
        : st.label}
    >
      <span aria-hidden
        className={`inline-block h-2 w-2 rounded-full ${st.tone} ${st.pulse ? 'animate-pulse' : ''}`} />
      <span className="hidden text-2xs text-text-secondary sm:inline">{st.label}</span>
    </span>
  );
}
