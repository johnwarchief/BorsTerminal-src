import { faNum, fmtInt, fmtVolume, toFaDigits } from '@shared/lib/fa';
import { useBoard } from '../api/useBoard';
import { useMarketSnapshot } from '../api/useMarketSnapshot';
import { usePhase } from '../api/usePhase';

function Row({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-line/60 py-1">
      <span className="t-95 text-text-3">{label}</span>
      <b className="num t-95 text-text-2" title={note}>{value}</b>
    </div>
  );
}

function hemat(value: number | null | undefined): string {
  return value == null || !Number.isFinite(value) ? '—' : `${faNum(value, 1)} همت`;
}

export function MarketStatusPage() {
  const phase = usePhase();
  const board = useBoard();
  const snapshot = useMarketSnapshot();
  const data = phase.data;
  const meta = board.data?.meta;

  const phaseLabel = data?.label ?? (phase.isError ? 'نامعلوم — پاسخِ مرحله نرسید' : '—');
  const source = data?.official
    ? 'رسمی — از خودِ بورس'
    : 'تقویمی — رأیِ رسمی در دست نیست';

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      <h1 className="mb-2 t-125 font-extrabold">وضعیت بازار</h1>

      <section className="mb-3 rounded-[var(--radius-sm)] border border-line bg-panel p-2">
        <div className="flex items-baseline gap-2">
          <b data-testid="phase-label" className="t-115">{phaseLabel}</b>
          <span data-testid="phase-source" className="t-9 text-text-3">{source}</span>
        </div>
        {data?.official_state_title ? (
          <p className="mt-1 t-9 text-text-3">اعلامِ بورس: {data.official_state_title}</p>
        ) : null}
        <Row label="روزِ داده" value={meta?.d_even != null ? toFaDigits(String(meta.d_even)) : '—'} />
        <Row label="آخرین همگام‌سازی" value={meta?.last_sync ?? '—'} />
        <Row label="زنده / کهنه" value={`${fmtInt(board.data?.live_count)} / ${fmtInt(board.data?.fossil_count)}`} />
        <Row label="ساعتِ بررسی" value={data?.clock_now ?? '—'} />
      </section>

      <section className="mb-3 rounded-[var(--radius-sm)] border border-line bg-panel p-2">
        <div className="mb-1 t-10 font-bold text-text-2">شاخص و ارزش</div>
        <Row label="شاخص کل" value={snapshot.data?.index?.last != null ? fmtInt(snapshot.data.index.last) : '—'} />
        <Row label="هم‌وزن" value={snapshot.data?.index?.ew_last != null ? fmtInt(snapshot.data.index.ew_last) : '—'} />
        <Row label="ارزش معاملات بازار" value={hemat(snapshot.data?.market?.trade_value_hemat)} />
        <Row label="حجم بازار" value={snapshot.data?.market?.volume != null ? fmtVolume(snapshot.data.market.volume) : '—'} />
        <Row label="تعداد معاملات" value={snapshot.data?.market?.trades != null ? fmtInt(snapshot.data.market.trades) : '—'} />
        <Row label="ارزش بازار" value={hemat(snapshot.data?.market?.market_value_hemat)} />
      </section>

      <section className="mb-3 rounded-[var(--radius-sm)] border border-line bg-panel p-2">
        <div className="mb-1 t-10 font-bold text-text-2">ارزش معاملات خرد</div>
        <Row label="ارزش" value={hemat(snapshot.data?.retail?.value_hemat)} />
        <Row label="وضعیت" value={snapshot.data?.retail?.label ?? '—'} note={snapshot.data?.retail?.cause ?? undefined} />
        <Row label="آستانهٔ مساعد" value={snapshot.data?.retail?.good_min != null ? `${faNum(snapshot.data.retail.good_min)} همت` : '—'} />
        <Row label="آستانهٔ نامساعد" value={snapshot.data?.retail?.bad_max != null ? `${faNum(snapshot.data.retail.bad_max)} همت` : '—'} />
        <Row label="آستانهٔ عالی" value={snapshot.data?.retail?.excellent_min != null ? `${faNum(snapshot.data.retail.excellent_min)} همت` : '—'} />
      </section>

      <p className="t-9 text-text-3">
        این صفحه فقط‌خواندنی است؛ عددِ کهنه با برچسبِ زنده نمایش داده نمی‌شود.
      </p>
    </div>
  );
}
