import { faNum } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { useSymbolCalendar, type CalendarEvent } from '../api/useCalendar';

const CAT_LABEL: Record<string, string> = {
  assembly: 'مجمع',
  assemblyChange: 'تغییر/لغو مجمع',
  capitalIncrease: 'افزایش سرمایه',
  ipo: 'عرضه اولیه',
  bondMaturity: 'سررسید',
  other: 'سایر',
};

function categoryOf(ev: CalendarEvent): { label: string; tone: string } {
  const title = ev.title ?? '';
  if (/سود\s*نقدی|تقسیم\s*سود/.test(title)) {
    return { label: 'سود نقدی', tone: 'border-[var(--fd-up)] text-[var(--fd-up)]' };
  }
  const cat = ev.cat ?? 'other';
  return {
    label: CAT_LABEL[cat] ?? 'سایر',
    tone: cat === 'capitalIncrease'
      ? 'border-[var(--fd-accent)] text-[var(--fd-accent)]'
      : 'border-[var(--fd-line)] bg-[var(--fd-panel-2)] text-[var(--fd-text-2)]',
  };
}

function jalaliDate(ymd: string): string {
  const n = Number(String(ymd).replace(/-/g, ''));
  return Number.isFinite(n) ? jalaliFromYmd(n) : '—';
}

function todayYmd(): string {
  const d = new Date();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${d.getFullYear()}-${m}-${day}`;
}

function EventRow({ ev, kind }: { ev: CalendarEvent; kind: 'future' | 'past' | 'notice' }) {
  const cat = categoryOf(ev);
  return (
    <li
      data-testid={`calendar-event-${ev.date}`}
      className={`flex flex-wrap items-baseline gap-1.5 border-b border-[var(--fd-line)] px-1 py-1 last:border-0 ${kind === 'past' ? 'opacity-70' : ''}`}
    >
      <span className="num w-20 flex-none text-[var(--fd-text-3)]" title={kind === 'notice' ? 'تاریخِ برگزاری در عنوان نبود؛ تاریخِ انتشار نمایش داده می‌شود' : undefined}>
        {jalaliDate(ev.date)}
      </span>
      <span className={`flex-none rounded-[3px] border px-1 t-85 ${cat.tone}`}>{cat.label}</span>
      <span className="min-w-0 flex-1 truncate text-[var(--fd-text-2)]" title={ev.title}>{ev.title}</span>
      {kind === 'past' ? <span className="t-85 text-[var(--fd-text-3)]">گذشته</span> : null}
      {kind === 'notice' ? <span className="t-85 text-[var(--fd-text-3)]">انتشار</span> : null}
    </li>
  );
}

export function CorporateCalendar({ symbol }: { symbol: string }) {
  const query = useSymbolCalendar(symbol);
  const events = query.data?.events ?? [];
  const today = todayYmd();
  // فقط رویدادی که تاریخِ برگزاری‌اش از عنوان آمده «آینده» است؛ تاریخِ
  // انتشار (publication_fallback) نباید رویداد را آینده جلوه بدهد.
  const dated = events.filter((ev) => ev.date_source === 'title');
  const future = dated.filter((ev) => ev.date >= today)
    .slice().sort((a, b) => a.date.localeCompare(b.date));
  const past = dated.filter((ev) => ev.date < today)
    .slice().sort((a, b) => b.date.localeCompare(a.date)).slice(0, 6);
  const notices = events.filter((ev) => ev.date_source !== 'title')
    .slice().sort((a, b) => b.date.localeCompare(a.date)).slice(0, 5);

  return (
    <section data-testid="corporate-calendar" className="rounded-[var(--radius-sm)] border border-[var(--fd-line)] bg-[var(--fd-panel)] p-2">
      <div className="mb-1 flex flex-wrap items-baseline justify-between gap-1">
        <h3 className="t-10 font-bold text-[var(--fd-text-2)]">رویدادهای شرکتی</h3>
        {query.data ? (
          <span className="t-85 text-[var(--fd-text-3)]">
            {faNum(future.length)} آینده · {faNum(events.length)} در کش
          </span>
        ) : null}
      </div>

      {query.isLoading ? (
        <p data-testid="calendar-loading" className="t-95 text-[var(--fd-text-3)]">تقویم کدال در حال خواندن…</p>
      ) : query.isError || !query.data ? (
        <p data-testid="calendar-error" className="t-95 text-[var(--fd-text-3)]">تقویم کدال نیامد؛ رویدادی ساخته نشد.</p>
      ) : events.length === 0 ? (
        <p data-testid="calendar-empty" className="t-95 text-[var(--fd-text-3)]">
          رویدادی برای این نماد در کشِ تقویم نیست؛ نبودِ رویداد به‌معنای نبودِ مجمع در آینده نیست.
        </p>
      ) : (
        <>
          {future.length ? (
            <ul data-testid="calendar-future" className="m-0 list-none p-0">
              {future.map((ev) => <EventRow key={`${ev.date}-${ev.title}`} ev={ev} kind="future" />)}
            </ul>
          ) : (
            <p data-testid="calendar-no-future" className="t-95 text-[var(--fd-text-3)]">
              رویدادِ آینده‌ای در کشِ فعلی تقویم نیست.
            </p>
          )}
          {past.length ? (
            <div className="mt-1">
              <div className="t-85 font-bold text-[var(--fd-text-3)]">آخرین رویدادهای گذشته</div>
              <ul className="m-0 list-none p-0">
                {past.map((ev) => <EventRow key={`${ev.date}-${ev.title}`} ev={ev} kind="past" />)}
              </ul>
            </div>
          ) : null}
          {notices.length ? (
            <div className="mt-1">
              <div className="t-85 font-bold text-[var(--fd-text-3)]">اطلاعیه‌های تازه (بدون تاریخ برگزاری در عنوان)</div>
              <ul data-testid="calendar-notices" className="m-0 list-none p-0">
                {notices.map((ev) => <EventRow key={`${ev.date}-${ev.title}`} ev={ev} kind="notice" />)}
              </ul>
            </div>
          ) : null}
        </>
      )}
    </section>
  );
}
