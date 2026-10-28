import { getJson, HttpError } from '@shared/api/http';
import {
  MarketDeltaSchema,
  MarketFeedSchema,
  type MarketDelta,
  type MarketFeed,
  type MarketRow,
} from '@shared/types/market';

let rows: MarketRow[] = [];
let indexBy = new Map<string, number>();
let rev = -1;
let revAt = 0;
let meta: MarketFeed['meta'] = null;
let counts = { count: 0, live_count: 0, fossil_count: 0 };
let deltaUnsupported = false;
let snap: MarketFeed = {
  status: 'success', data: rows, meta, rev: null, rev_at: null, ...counts,
};

function rebuildSnapshot(): void {
  snap = { status: 'success', data: rows, meta, rev, rev_at: revAt, ...counts };
}

export function getBoardSnapshot(): MarketFeed {
  return snap;
}

export function resetBoardMirror(): void {
  rows = [];
  indexBy = new Map();
  rev = -1;
  revAt = 0;
  meta = null;
  counts = { count: 0, live_count: 0, fossil_count: 0 };
  deltaUnsupported = false;
  rebuildSnapshot();
}

export function adoptBoard(feed: MarketFeed, now = Date.now()): MarketFeed {
  const previousRev = rev;
  rows = feed.data ?? [];
  indexBy = new Map(rows.map((row, index) => [row.ins_code ?? `#${index}`, index]));
  counts = {
    count: feed.count ?? rows.length,
    live_count: feed.live_count ?? 0,
    fossil_count: feed.fossil_count ?? 0,
  };
  meta = feed.meta ?? null;
  rev = typeof feed.rev === 'number' ? feed.rev : -1;
  if (typeof feed.rev_at === 'number' && feed.rev_at > 0) {
    revAt = feed.rev_at;
  } else if (previousRev < 0 || (rev >= 0 && rev !== previousRev)) {
    revAt = now;
  }
  rebuildSnapshot();
  return snap;
}

export function applyBoardDelta(delta: MarketDelta, now = Date.now()): 'unchanged' | 'merged' | 'full' {
  if (delta.status === 'unchanged') return 'unchanged';
  if (delta.status === 'full') return 'full';

  const nextRows = rows.slice();
  const nextIndex = new Map(indexBy);
  for (const row of delta.rows) {
    const code = row.ins_code;
    if (!code) return 'full';
    const index = nextIndex.get(code);
    if (index === undefined) {
      nextIndex.set(code, nextRows.length);
      nextRows.push(row);
    } else {
      nextRows[index] = row;
    }
  }
  if (delta.count != null && delta.count !== nextRows.length) return 'full';

  rows = nextRows;
  indexBy = nextIndex;
  if (delta.rev !== rev) revAt = now;
  rev = delta.rev;
  if (delta.meta) meta = delta.meta;
  counts = {
    count: delta.count ?? counts.count,
    live_count: delta.live_count ?? counts.live_count,
    fossil_count: delta.fossil_count ?? counts.fossil_count,
  };
  rebuildSnapshot();
  return 'merged';
}

async function fetchFull(signal?: AbortSignal): Promise<MarketFeed> {
  const feed = await getJson('/api/market', MarketFeedSchema, signal);
  return adoptBoard(feed);
}

export async function fetchBoard(signal?: AbortSignal): Promise<MarketFeed> {
  if (rev < 0 || deltaUnsupported) return fetchFull(signal);
  let delta: MarketDelta;
  try {
    delta = await getJson(`/api/market/delta?since=${rev}`, MarketDeltaSchema, signal);
  } catch (error) {
    if (error instanceof HttpError && error.status === 404) deltaUnsupported = true;
    return fetchFull(signal);
  }
  if (delta.status === 'unchanged') return getBoardSnapshot();
  if (applyBoardDelta(delta) === 'merged') return getBoardSnapshot();
  return fetchFull(signal);
}
