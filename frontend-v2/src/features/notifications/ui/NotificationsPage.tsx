import { useState } from 'react';
import clsx from 'clsx';
import { toFaDigits } from '@shared/lib/fa';
import { useNotificationSources, useNotificationsFeed } from '../api/useNotifications';
import { LEVEL_LABEL, LEVEL_ORDER, markRead, readState, type Level } from '../lib/unread';

const TONE: Record<Level, string> = {
  high: 'text-down',
  medium: 'text-warn',
  low: 'text-text-3',
  unclassified: 'text-text-3',
};

export function NotificationsPage() {
  const [level, setLevel] = useState<Level | 'all'>('all');
  const feed = useNotificationsFeed(level === 'all' ? undefined : level);
  const sources = useNotificationSources();
  const [read, setRead] = useState<Set<string>>(() => readState());

  const source = sources.data?.sources?.[0];
  const items = feed.data?.items ?? [];
  const unavailable = source?.state === 'unavailable' || sources.isError;
  const broken = unavailable || feed.isError;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <h1 className="mb-2 t-125 font-extrabold">اعلان‌ها</h1>

      {broken ? (
        <div data-testid="notif-source-warning" className="mb-2 rounded-[var(--radius-sm)] border border-line bg-panel p-2 t-95 text-warn">
          منبعِ اعلان در دسترس نیست — {source?.message ?? (feed.isError ? 'خوراکِ اعلان پاسخ نداد' : 'دلیل اعلام نشده')}
        </div>
      ) : null}

      <div className="mb-2 flex items-center gap-1" role="tablist">
        <button type="button" data-testid="notif-level-all" onClick={() => setLevel('all')}
          className={clsx('tape-btn', level === 'all' && 'bg-panel-3 text-text')}>همه</button>
        {LEVEL_ORDER.map((item) => (
          <button key={item} type="button" data-testid={`notif-level-${item}`} onClick={() => setLevel(item)}
            className={clsx('tape-btn', level === item && 'bg-panel-3 text-text')}>
            {LEVEL_LABEL[item]}
          </button>
        ))}
      </div>

      {feed.isLoading ? <p className="t-95 text-text-3">در حالِ خواندن…</p> : null}

      {!feed.isLoading && items.length === 0 && !broken ? (
        <p data-testid="notif-empty" className="t-95 text-text-3">اعلانِ تازه‌ای نیست.</p>
      ) : null}

      <ul className="space-y-1">
        {items.map((item, index) => {
          const id = item.id != null ? String(item.id) : null;
          const isRead = id ? read.has(id) : false;
          return (
            <li key={id ?? `row-${index}`} data-testid={`notif-item-${id ?? `row-${index}`}`}
              className={clsx('rounded-[var(--radius-sm)] border border-line bg-panel p-2',
                isRead && 'opacity-60')}>
              <div className="flex items-baseline gap-2">
                <span className={clsx('t-9 font-bold', TONE[item.level])}>{LEVEL_LABEL[item.level]}</span>
                <b className="min-w-0 truncate t-10">{item.title}</b>
                {item.symbol ? <span className="t-9 text-text-3">{item.symbol}</span> : null}
                <span className="num ms-auto t-9 text-text-3">{item.publish_date ?? '—'}</span>
              </div>
              <div className="mt-1 flex items-center gap-2 t-9 text-text-3">
                <span className="truncate">{item.company ?? '—'}</span>
                {item.occurrences && item.occurrences > 1 ? <span>· {toFaDigits(item.occurrences)} بار</span> : null}
                {item.url ? (
                  <a href={item.url} target="_blank" rel="noopener noreferrer" className="text-accent">کدال</a>
                ) : null}
                {id ? (
                  <button type="button" className="ms-auto text-text-3 hover:text-text"
                    onClick={() => { markRead(id); setRead(readState()); }}>
                    خوانده شد
                  </button>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
