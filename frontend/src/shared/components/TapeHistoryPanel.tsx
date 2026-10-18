// shared/components/TapeHistoryPanel.tsx — جدولِ «کدام فیلتر، کدام روز، چند بار»
//
// بندِ سوم مأموریتِ پروندۀ نماد: کاربر باید ببیند یک نماد در چند روزِ اخیر چند بار
// هر فیلترِ تابلوخوانی را داشته است — نه فقط اینکه همین لحظه روشن است یا نه.
//
// سه قاعده‌ای که این جدول را از «سابقۀ ساختگی» جدا می‌کند:
//   • ستون‌ها فقط روزهای **رصدشده‌اند**. روزی که درِ تقویم نیست یعنی «ثبت نشده»
//     و هرگز با «غیرفعال» پر نمی‌شود؛ روزی که درِ تقویم است و ردیف ندارد یعنی
//     فیلتر آن روز واقعاً روشن نبوده.
//   • ستونِ «مجموع دفعات» شمارِ روزهاست (تعریفِ شمارش درِ سطرِ راهنما نوشته شده)،
//     و شمارۀ نوبت‌هایِ ثبتِ همان روز جدا درِ tooltip می‌آید.
//   • هیچ امتیاز یا حکمی اینجا ساخته نمی‌شود؛ فقط `tape_flag_day` خوانده می‌شود.
import { useTapeHistory, seriesFor, type TapeDayCell } from '@shared/api/tapeHistory';
import { dEvenToJalali } from '@shared/lib/jalaali';
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import { TAPE_FLAGS, TAPE_FLAG_LABELS, EVIDENCE_LABELS, type TapeFlag } from '@shared/lib/tapeFlags';

const WEEKDAY = ['یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنج‌شنبه', 'جمعه', 'شنبه'];

/** «۲۰۲۶۱۰۱۱» → «دوشنبه ۲۰» (نامِ روز از خودِ تاریخِ میلادیِ ثبت‌شده، نه از حدس) */
function dayLabel(dEven: number): string {
  const s = String(dEven);
  const jal = dEvenToJalali(dEven);
  const jd = jal ? jal.split(/[/-]/).pop() : s.slice(6, 8);
  const dt = new Date(Number(s.slice(0, 4)), Number(s.slice(4, 6)) - 1, Number(s.slice(6, 8)));
  const wd = Number.isNaN(dt.getDay()) ? '' : WEEKDAY[dt.getDay()];
  return `${wd} ${toFaDigits(String(jd ?? '').replace(/^0+/, ''))}`;
}

function evidenceTitle(flag: string, cells: Record<string, TapeDayCell>): string {
  const on = Object.entries(cells).filter(([, v]) => v.active).slice(-2);
  if (!on.length) return `${TAPE_FLAG_LABELS[flag as TapeFlag]} — درِ این پنجره روشن نشده`;
  return on.map(([d, c]) => {
    const ev = Object.entries(c.evidence ?? {}).map(([k, v]) =>
      `${EVIDENCE_LABELS[k] ?? k}: ${typeof v === 'number' ? fmtInt(v) : String(v)}`).join('، ');
    return `${dayLabel(Number(d))}${ev ? ` — ${ev}` : ''}`;
  }).join(' · ');
}

/** روندِ تکرار: شمارۀ روزهایِ روشنِ دو روزِ اخیر در برابر دو روزِ پیش از آن.
 *  بی‌چهار روزِ رصدشده چیزی نمی‌گوید (نه صفر، نه «تثبیت»). */
function trendOf(days: number[], cellDays: Record<string, TapeDayCell>): 'up' | 'down' | 'flat' | null {
  if (days.length < 4) return null;
  const on = (d: number) => (cellDays[String(d)]?.active ? 1 : 0);
  const recent = on(days[days.length - 1]) + on(days[days.length - 2]);
  const prior = on(days[days.length - 3]) + on(days[days.length - 4]);
  return recent > prior ? 'up' : recent < prior ? 'down' : 'flat';
}

const TREND_LABEL = { up: 'روندِ تکرار بالا رفته', down: 'روندِ تکرار پایین آمده', flat: 'همان تعدادِ دو دورِ پیش' };

export function TapeHistoryPanel({ insCode, symbol, days = 6, className = '' }: {
  insCode: string | null | undefined;
  symbol: string;
  /** پنجرۀ پیش‌فرضِ مالک: سه‌تا‌چهار روزِ اخیر؛ با «بیشتر» باز می‌شود */
  days?: number;
  className?: string;
}) {
  const q = useTapeHistory(insCode, days);
  const payload = q.data;
  const cal = payload?.days ?? [];
  const series = seriesFor(payload, insCode);

  if (!insCode) {
    return (
      <p className={`text-2xs text-text-muted ${className}`} data-testid={`tape-history-nocode-${symbol}`}>
        شناسۀ پایدارِ این نماد (ins_code) در دست نیست — سابقه خوانده نمی‌شود.
      </p>
    );
  }
  if (q.isPending && !payload) {
    return (
      <p className={`text-2xs text-text-muted ${className}`} data-testid={`tape-history-loading-${symbol}`} role="status">
        سابقۀ فیلترها در حالِ خواندن…
      </p>
    );
  }
  if (q.isError) {
    return (
      <p className={`text-2xs text-accent-red ${className}`} data-testid={`tape-history-error-${symbol}`}>
        سابقۀ فیلترها نرسید — این با نبودِ سابقه یکی نیست.
      </p>
    );
  }
  if (!cal.length) {
    return (
      <p className={`text-2xs leading-5 text-text-muted ${className}`} data-testid={`tape-history-empty-${symbol}`}>
        هنوز هیچ روزی برایِ این نماد ثبت نشده. ثبت از نخستین نشستِ زندهٔ تابلو
        شروع می‌شود و پیش‌از آن «سابقه» چیزی برایِ نمایش ندارد — نه «غیرفعال»،
        نه صفرِ ساختگی.
      </p>
    );
  }

  return (
    <div className={`min-w-0 ${className}`} data-testid={`tape-history-${symbol}`}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[420px] table-fixed border-collapse text-2xs">
          <thead>
            <tr className="border-b border-border-c/70 text-text-muted">
              <th className="w-[9.5rem] truncate px-1.5 py-1 text-start font-bold">فیلتر</th>
              {cal.map((d) => (
                <th key={d} className="px-1.5 py-1 text-center font-bold" title={dEvenToJalali(d) ?? String(d)}>
                  {dayLabel(d)}
                </th>
              ))}
              <th className="w-14 px-1.5 py-1 text-center font-bold" title="شمارِ روزهایِ رصدشده‌ای که فیلتر روشن بوده">
                دفعات
              </th>
              <th className="w-16 px-1.5 py-1 text-center font-bold">روند</th>
            </tr>
          </thead>
          <tbody>
            {TAPE_FLAGS.map((f) => {
              const s = series[f] ?? { days: {}, total: 0, last_seen_at: null };
              const tr = trendOf(cal, s.days);
              return (
                <tr key={f} className="border-b border-border-c/30 last:border-0"
                    data-testid={`tape-history-row-${symbol}-${f}`}>
                  <td className="truncate px-1.5 py-1 text-start font-bold text-text-primary"
                      title={evidenceTitle(f, s.days)}>
                    {TAPE_FLAG_LABELS[f]}
                  </td>
                  {cal.map((d) => {
                    const c = s.days[String(d)];
                    if (!c) {
                      return <td key={d} className="px-1.5 py-1 text-center text-text-muted/50" title="ثبت نشده">·</td>;
                    }
                    return (
                      <td key={d} className="px-1.5 py-1 text-center">
                        {c.active ? (
                          <span className={`num rounded px-1 font-black ${c.passes > 1 ? 'bg-accent-green/20 text-accent-green' : 'text-accent-green'}`}
                                title={`روشن — ${toFaDigits(c.passes)} نوبتِ ثبت · ${c.first_at ?? ''}`}>✓</span>
                        ) : (
                          <span className="text-text-muted" title="رصد شد، فیلتر روشن نبود">—</span>
                        )}
                      </td>
                    );
                  })}
                  <td className="num px-1.5 py-1 text-center font-black text-text-primary"
                      title={s.last_seen_at ? `آخرین مشاهده: ${s.last_seen_at}` : 'هرگز در این پنجره روشن نشده'}>
                    {toFaDigits(s.total)}
                  </td>
                  <td className="px-1.5 py-1 text-center text-3xs"
                      title={tr ? `${TREND_LABEL[tr]} (دو روزِ اخیر در برابر دو روزِ پیش از آن)` : 'برایِ روند به چهار روزِ رصدشده نیاز است'}>
                    {tr === 'up' ? <span className="text-accent-green">▲</span>
                      : tr === 'down' ? <span className="text-accent-red">▼</span>
                      : tr === 'flat' ? <span className="text-text-muted">=</span>
                      : <span className="text-text-muted/50">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-1 text-3xs leading-4 text-text-muted" data-testid={`tape-history-note-${symbol}`}>
        شمارش = تعدادِ روزهایِ رصدشده‌ای که فیلتر روشن بوده (نه تعدادِ نوبت‌هایِ
        ثبتِ درونِ یک روز). ✓ = روشن، — = رصد شد و روشن نبود، · = آن روز ثبت نشده.
        {payload?.reliable_from
          ? ` سابقه از ${dEvenToJalali(payload.reliable_from)} به بعد قابل‌اعتماد است.`
          : ''}
        {payload?.write_error ? ` ثبتِ این دور خطا داشت: ${payload.write_error}` : ''}
      </p>
    </div>
  );
}

export default TapeHistoryPanel;
