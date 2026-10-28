import { fmtInt, toFaDigits } from '@shared/lib/fa';
import { jalaliFromYmd } from '@shared/lib/jalali';
import { seriesFor, useTapeHistory, type TapeDayCell } from '../api/useTapeHistory';
import { TAPES, tapeLabel, type TapeKey } from '../lib/tapeFilters';

const WEEKDAY = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه'];

function dayLabel(day: number): string {
  const text = String(day);
  const jalali = jalaliFromYmd(day);
  const date = new Date(Date.UTC(Number(text.slice(0, 4)), Number(text.slice(4, 6)) - 1, Number(text.slice(6, 8))));
  const weekday = Number.isNaN(date.getTime()) ? '' : WEEKDAY[date.getUTCDay()];
  return `${weekday} ${jalali.split('/').pop() ?? text.slice(6, 8)}`;
}

function evidenceTitle(flag: TapeKey, cells: Record<string, TapeDayCell>): string {
  const active = Object.entries(cells).filter(([, cell]) => cell.active).slice(-2);
  if (!active.length) return `${tapeLabel(flag)} — در این پنجره روشن نشده`;
  return active.map(([day, cell]) => {
    const evidence = Object.entries(cell.evidence ?? {})
      .map(([key, value]) => `${key}: ${typeof value === 'number' ? fmtInt(value) : String(value)}`)
      .join('، ');
    return `${dayLabel(Number(day))}${evidence ? ` — ${evidence}` : ''}`;
  }).join(' · ');
}

function trendOf(days: number[], cells: Record<string, TapeDayCell>): 'up' | 'down' | 'flat' | null {
  if (days.length < 4) return null;
  const active = (day: number) => (cells[String(day)]?.active ? 1 : 0);
  const recent = active(days[days.length - 1]) + active(days[days.length - 2]);
  const prior = active(days[days.length - 3]) + active(days[days.length - 4]);
  return recent > prior ? 'up' : recent < prior ? 'down' : 'flat';
}

export function TapeHistoryPanel({ insCode, symbol, days = 6 }: {
  insCode: string | null | undefined;
  symbol: string;
  days?: number;
}) {
  const query = useTapeHistory(insCode, days);
  const payload = query.data;
  const calendar = payload?.days ?? [];
  const series = seriesFor(payload, insCode);

  if (!insCode) {
    return <p className="t-95 text-text-3">شناسهٔ پایدار نماد در دست نیست؛ سابقه خوانده نمی‌شود.</p>;
  }
  if (query.isPending && !payload) {
    return <p className="t-95 text-text-3" role="status">سابقهٔ فیلترها در حال خواندن…</p>;
  }
  if (query.isError) {
    return <p className="t-95 text-down">سابقهٔ فیلترها نرسید؛ این با نبودِ سابقه یکی نیست.</p>;
  }
  if (!calendar.length) {
    return (
      <p className="t-95 leading-relaxed text-text-3" data-testid={`tape-history-empty-${symbol}`}>
        هنوز روزی برای این نماد ثبت نشده. ثبت از نخستین نشست زنده شروع می‌شود؛ گذشته از دادهٔ امروز ساخته نمی‌شود.
      </p>
    );
  }

  return (
    <div className="min-w-0" data-testid={`tape-history-${symbol}`}>
      <div className="max-w-full overflow-x-auto">
        <table className="w-full min-w-[420px] table-fixed border-collapse t-9">
          <thead>
            <tr className="border-b border-line text-text-3">
              <th className="w-[92px] px-1 py-1 text-start font-bold">فیلتر</th>
              {calendar.map((day) => (
                <th key={day} className="px-1 py-1 text-center font-bold" title={jalaliFromYmd(day)}>{dayLabel(day)}</th>
              ))}
              <th className="w-12 px-1 py-1 text-center font-bold">دفعات</th>
              <th className="w-12 px-1 py-1 text-center font-bold">روند</th>
            </tr>
          </thead>
          <tbody>
            {TAPES.map(({ key }) => {
              const flagSeries = series[key] ?? { days: {}, total: 0, last_seen_at: null };
              const trend = trendOf(calendar, flagSeries.days);
              return (
                <tr key={key} className="border-b border-line/60 last:border-0" data-testid={`tape-history-row-${symbol}-${key}`}>
                  <td className="truncate px-1 py-1 text-start font-bold text-text" title={evidenceTitle(key, flagSeries.days)}>
                    {tapeLabel(key)}
                  </td>
                  {calendar.map((day) => {
                    const cell = flagSeries.days[String(day)];
                    const testId = `tape-history-cell-${symbol}-${key}-${day}`;
                    if (!cell) {
                      return <td key={day} data-testid={testId} className="px-1 py-1 text-center text-text-3/50" title="ثبت نشده">·</td>;
                    }
                    return (
                      <td
                        key={day}
                        data-testid={testId}
                        className="px-1 py-1 text-center"
                        title={cell.active ? `روشن — ${toFaDigits(cell.passes)} نوبت ثبت` : 'رصد شد، فیلتر روشن نبود'}
                      >
                        {cell.active ? <span className="font-black text-up">✓</span> : <span className="text-text-3">—</span>}
                      </td>
                    );
                  })}
                  <td className="num px-1 py-1 text-center font-bold text-text" title={flagSeries.last_seen_at ?? 'در این پنجره روشن نشده'}>
                    {toFaDigits(flagSeries.total)}
                  </td>
                  <td className="px-1 py-1 text-center" title={trend ? 'دو روز اخیر در برابر دو روز پیش' : 'برای روند چهار روز رصدشده لازم است'}>
                    {trend === 'up' ? <span className="text-up">▲</span>
                      : trend === 'down' ? <span className="text-down">▼</span>
                        : trend === 'flat' ? <span className="text-text-3">=</span>
                          : <span className="text-text-3/50">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1 t-85 leading-relaxed text-text-3" data-testid={`tape-history-note-${symbol}`}>
        ✓ روشن، — رصد شد و روشن نبود، · آن روز ثبت نشده. دفعات = روزهای روشن، نه نوبت‌های درون یک روز.
        {payload?.reliable_from ? ` سابقه از ${jalaliFromYmd(payload.reliable_from)} قابل‌اعتماد است.` : ''}
        {payload?.write_error ? ` ثبت این دور خطا داشت: ${payload.write_error}` : ''}
      </p>
    </div>
  );
}
