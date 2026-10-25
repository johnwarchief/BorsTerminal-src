import type {
  SalienceBias,
  SalienceGroup,
  SalienceInputEvent,
  SalienceMethod,
  SalienceResult,
} from './types';

const FAMILY_ORDER: Record<string, number> = {
  market_structure: 0,
  chart_structure: 1,
  candlestick: 2,
};

/** Maximum pivot confirmation delay in the scanner (extrema lookback is 5). */
export const SALIENCE_LOCAL_WINDOW = 5;

function uniqueSorted<T>(values: Iterable<T>, compare?: (a: T, b: T) => number): T[] {
  return [...new Set(values)].sort(compare);
}

function groupBias(events: SalienceInputEvent[]): SalienceBias {
  const directional = new Set(
    events.map((e) => e.bias).filter((b) => b === 'bullish' || b === 'bearish'),
  );
  if (directional.size === 0) return 'neutral';
  if (directional.size === 1) return [...directional][0] as SalienceBias;
  return 'mixed';
}

function anchorSignature(event: SalienceInputEvent): string {
  return `${event.detector}|${uniqueSorted(event.anchors.map((a) => a.index)).join(',')}`;
}

/**
 * Groups events locally: an event joins an open group only when it shares an
 * anchor and confirms within SALIENCE_LOCAL_WINDOW bars of the group's first
 * confirmation. This is a bounded display cluster, not a transitive component:
 * a level reused months later starts a new group.
 */
export function buildSalience(
  seriesKey: string,
  events: readonly SalienceInputEvent[],
  latestIndex: number,
): SalienceResult {
  if (events.length === 0) {
    return {
      seriesKey,
      groups: [],
      order: { latest: [], structure_first: [], evidence_count: [] },
      rules: rankingRules(),
      repeatedGroups: 0,
      multiEventGroups: 0,
    };
  }

  const sorted = [...events].sort(
    (a, b) => a.confirmedAtIndex - b.confirmedAtIndex || a.key.localeCompare(b.key),
  );

  interface OpenGroup {
    start: number;
    events: SalienceInputEvent[];
    anchors: Set<number>;
  }
  const buckets: OpenGroup[] = [];
  for (const event of sorted) {
    let target: OpenGroup | null = null;
    for (let i = buckets.length - 1; i >= 0; i -= 1) {
      const group = buckets[i];
      if (event.confirmedAtIndex - group.start > SALIENCE_LOCAL_WINDOW) break;
      if (event.anchors.some((anchor) => group.anchors.has(anchor.index))) {
        target = group;
        break;
      }
    }
    if (target) {
      target.events.push(event);
      for (const anchor of event.anchors) target.anchors.add(anchor.index);
    } else {
      buckets.push({
        start: event.confirmedAtIndex,
        events: [event],
        anchors: new Set(event.anchors.map((anchor) => anchor.index)),
      });
    }
  }

  const rawGroups = buckets.map((bucket) => {
    const groupEvents = bucket.events;
    const anchors = uniqueSorted(groupEvents.flatMap((e) => e.anchors.map((a) => a.index)));
    const anchorCounts = new Map<number, number>();
    for (const e of groupEvents) {
      for (const a of uniqueSorted(e.anchors.map((x) => x.index))) {
        anchorCounts.set(a, (anchorCounts.get(a) ?? 0) + 1);
      }
    }
    const shared = [...anchorCounts.entries()]
      .filter(([, count]) => count > 1)
      .map(([index]) => index)
      .sort((a, b) => a - b);
    const prices = groupEvents
      .flatMap((e) => e.anchors.map((a) => a.price))
      .filter((p): p is number => typeof p === 'number' && Number.isFinite(p));
    const signatures = new Set<string>();
    let repeated = false;
    for (const e of groupEvents) {
      const sig = anchorSignature(e);
      if (signatures.has(sig)) repeated = true;
      signatures.add(sig);
    }
    const latestConfirmedAtIndex = Math.max(...groupEvents.map((e) => e.confirmedAtIndex));
    const earliestConfirmedAtIndex = Math.min(...groupEvents.map((e) => e.confirmedAtIndex));
    return {
      seriesKey,
      eventKeys: groupEvents.map((e) => e.key).sort(),
      anchorIndices: anchors,
      sharedAnchorIndices: shared,
      anchorPriceRange: prices.length
        ? ([Math.min(...prices), Math.max(...prices)] as [number, number])
        : null,
      detectors: uniqueSorted(groupEvents.map((e) => e.detector)),
      families: uniqueSorted(groupEvents.map((e) => e.family)),
      bias: groupBias(groupEvents),
      levels: uniqueSorted(
        groupEvents
          .map((e) => e.level)
          .filter((v): v is number => typeof v === 'number' && Number.isFinite(v)),
      ),
      earliestConfirmedAtIndex,
      latestConfirmedAtIndex,
      ageBars: Math.max(0, latestIndex - latestConfirmedAtIndex),
      newestEventKey: [...groupEvents].sort(
        (a, b) => a.confirmedAtIndex - b.confirmedAtIndex || a.key.localeCompare(b.key),
      ).at(-1)!.key,
      oldestEventKey: [...groupEvents].sort(
        (a, b) => a.confirmedAtIndex - b.confirmedAtIndex || a.key.localeCompare(b.key),
      )[0].key,
      repeatedDetectorAnchorSets: repeated,
    };
  });

  rawGroups.sort(
    (a, b) =>
      a.earliestConfirmedAtIndex - b.earliestConfirmedAtIndex ||
      a.eventKeys[0].localeCompare(b.eventKeys[0]),
  );
  const groups: SalienceGroup[] = rawGroups.map((group, index) => ({
    ...group,
    id: `${seriesKey}#g${index}`,
  }));

  const order: Record<SalienceMethod, string[]> = {
    latest: [...groups]
      .sort(
        (a, b) =>
          b.latestConfirmedAtIndex - a.latestConfirmedAtIndex ||
          b.earliestConfirmedAtIndex - a.earliestConfirmedAtIndex ||
          a.id.localeCompare(b.id),
      )
      .map((g) => g.id),
    structure_first: [...groups]
      .sort((a, b) => {
        const rank = (g: SalienceGroup) =>
          Math.min(...g.families.map((f) => FAMILY_ORDER[f] ?? 3));
        return (
          rank(a) - rank(b) ||
          b.latestConfirmedAtIndex - a.latestConfirmedAtIndex ||
          a.id.localeCompare(b.id)
        );
      })
      .map((g) => g.id),
    evidence_count: [...groups]
      .sort(
        (a, b) =>
          b.anchorIndices.length - a.anchorIndices.length ||
          b.latestConfirmedAtIndex - a.latestConfirmedAtIndex ||
          a.id.localeCompare(b.id),
      )
      .map((g) => g.id),
  };

  return {
    seriesKey,
    groups,
    order,
    rules: rankingRules(),
    repeatedGroups: groups.filter((g) => g.repeatedDetectorAnchorSets).length,
    multiEventGroups: groups.filter((g) => g.eventKeys.length > 1).length,
  };
}

function rankingRules(): Record<SalienceMethod, string> {
  return {
    latest:
      'گروه: لنگر مشترک در بازهٔ ۵ کندلیِ تأیید (بیشترین تأخیر تأیید پیوت). نمایش: آخرین تأیید، سپس زودترین، سپس شناسه. ترتیب نمایش است، نه احتمال.',
    structure_first:
      'نمایش: ساختار بازار پیش از ساختار نمودار پیش از کندل؛ درون هر رتبه، آخرین تأیید. رتبهٔ خانواده یک قاعدهٔ ترتیب است، نه اعتبار.',
    evidence_count:
      'نمایش: تعداد لنگرهای یکتا (غنای شواهد)، سپس آخرین تأیید. تعداد لنگر بیشتر به‌تنهایی درستی یا احتمال را نمی‌سنجد.',
  };
}
