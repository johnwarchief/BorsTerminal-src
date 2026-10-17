// features/portfolio/components/sarkhati/SarkhatiMonitorCard.tsx — سلامت، سابقه،
// و خروجیِ بی‌راز
//
// سه ادعا که این کارت می‌کند، همگی ازِ پاسخِ سرویس‌اند:
//  • سلامتِ درِ اجرا ازِ خودِ `useExecutionStatus` (نبودِ پاسخ = «سرویس نیست»، نه صفر)
//  • تأخیرها ازِ `/api/execution/timings` (monotonic؛ با «نمونۀ کم» صریح)
//  • سابقه ازِ `/api/execution/events` — ردِّپایِ ماندگارِ *خودِ برنامه*، که
//    `payload` ندارد و `detail`ش ازِ همان `redact`ِ قراردادِ اجرا گذشته است
//    (dev/sarkhati_tab_v1122.py: توکن کاشته‌شده درِ پاسخ نمی‌ماند).
//
// فیلترها رویِ ستون‌هایِ خودِ ردِّپا هستند؛ تاریخ با قالبِ `YYYY-MM-DD` و
// تبدیلش درِ بک‌اند انجام می‌شود، پس ساعتِ منطقۀِ مرورگر درِ فیلتر نقشی ندارد.
import { useState } from 'react';
import { Badge } from '@shared/components/Badge';
import { fmtAge } from '@shared/lib/time';
import { toFaDigits } from '@shared/lib/fmt';
import { downloadCsvWithMeta, toExportTable } from '@shared/lib/tableExport';
import {
  CODE_LABEL, useExecutionEvents, useExecutionTimings,
  type EventFilters, type ExecutionEvent,
} from '../../lib/orderClient';

const KINDS = ['connect', 'session', 'preflight', 'prepare', 'dispatch', 'state',
  'reconcile', 'cancel', 'halt', 'resume', 'duplicate'];

function dayAgo(n: number): string {
  const d = new Date(Date.now() - n * 86_400_000);
  return d.toISOString().slice(0, 10);
}

export function SarkhatiMonitorCard({ lastStatusAt }: { lastStatusAt?: number | null }) {
  const [f, setF] = useState<EventFilters>({ since: dayAgo(3), limit: 200 });
  const [sym, setSym] = useState('');
  const [id, setId] = useState('');
  const [st, setSt] = useState('');
  const [kind, setKind] = useState('');
  const [since, setSince] = useState(f.since ?? '');
  const events = useExecutionEvents({ ...f, symbol: sym, executionId: id, status: st, kinds: kind, since });
  const timings = useExecutionTimings();
  const rows = events.data?.events ?? [];
  const failed = events.isError;
  const badFilter = events.data?.status === 'error';

  const apply = () => setF({ symbol: sym, executionId: id, status: st, kinds: kind, since, limit: 200 });

  const exportCsv = () => {
    downloadCsvWithMeta('سرخطی-رخدادها', toExportTable(
      ['زمانِ نوشتن', 'شناسۀ اجرا', 'گونه', 'وضعیتِ اجرا', 'وضعیتِ سفارش', 'کدِ خطا',
        'کارگزاری', 'نماد', 'جهت', 'قیمت', 'حجم', 'پر شده', 'حالت', 'جزئیات'],
      rows as ExecutionEvent[],
      (e) => [e.written_at ?? '', e.execution_id, e.kind ?? '', e.status ?? '',
        e.order_state ?? '', e.error_code ?? '', e.broker ?? '', e.symbol ?? '',
        e.side ?? '', e.price ?? null, e.quantity ?? null, e.filled ?? null,
        e.mode ?? '', e.detail ?? ''],
    ), [['منبع', 'ردِّپایِ ماندگارِ خودِ برنامه (/api/execution/events)'],
        ['فیلترِ اعمال‌شده', JSON.stringify({ sym, id, st, kind, since })],
        ['راز', 'بدونِ payload؛ detail از redactِ قرارداد گذشته است']]);
  };

  const p50 = (timings.data?.phases as Record<string, { p50?: number | null }> | undefined)
    ?.dispatch_ms?.p50;

  return (
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-monitor-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">پایشِ ارتباط و سابقه</h4>
        <Badge tone={failed ? 'red' : 'green'} title="خودِ درِ /api/execution/status">
          {failed ? 'سرویسِ اجرا پاسخ نداد' : 'درِ اجرا پاسخ می‌دهد'}
        </Badge>
        <span className="text-3xs text-text-muted" data-testid="sarkhati-last-status">
          آخرینِ خواندنِ وضعیت: {lastStatusAt ? fmtAge(Date.now() - lastStatusAt) : '—'}
        </span>
        <span className="text-3xs text-text-muted" data-testid="sarkhati-latency">
          تأخیرِ dispatch p50:{' '}
          <span className="num text-text-primary">
            {p50 != null ? `${toFaDigits(String(p50))} ms` : 'اندازه‌گیری‌نشده'}
          </span>
        </span>
      </div>

      <div className="flex flex-wrap items-end gap-1.5 text-3xs" data-testid="sarkhati-event-filters">
        <label className="flex flex-col gap-0.5 text-text-muted">نماد
          <input value={sym} onChange={(e) => setSym(e.target.value)}
            data-testid="sarkhati-ev-f-symbol"
            className="w-24 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-text-primary" />
        </label>
        <label className="flex flex-col gap-0.5 text-text-muted">شناسۀِ اجرا
          <input value={id} onChange={(e) => setId(e.target.value)}
            data-testid="sarkhati-ev-f-id"
            className="w-28 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-text-primary" />
        </label>
        <label className="flex flex-col gap-0.5 text-text-muted">وضعیت
          <input value={st} onChange={(e) => setSt(e.target.value)}
            placeholder="مثلاً acknowledged"
            data-testid="sarkhati-ev-f-status"
            className="w-32 rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-text-primary" />
        </label>
        <label className="flex flex-col gap-0.5 text-text-muted">گونه
          <select value={kind} onChange={(e) => setKind(e.target.value)}
            data-testid="sarkhati-ev-f-kind"
            className="rounded-lg border border-border-c bg-bg-primary px-1 py-0.5 text-text-primary">
            <option value="">همۀِ گونه‌ها</option>
            {KINDS.map((k) => (<option key={k} value={k}>{k}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-text-muted">از تاریخ
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)}
            data-testid="sarkhati-ev-f-since" dir="ltr"
            className="num rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-text-primary" />
        </label>
        <button type="button" onClick={apply}
          data-testid="sarkhati-ev-apply"
          className="rounded-lg border border-accent-blue/40 px-2 py-1 font-bold text-accent-blue hover:bg-accent-blue/10">
        اعمالِ فیلتر
        </button>
        <button type="button" onClick={exportCsv} disabled={rows.length === 0}
          data-testid="sarkhati-ev-export"
          title={rows.length === 0 ? 'بدونِ ردیف، فایلِ خالی ساخته نمی‌شود' : 'CSV با سرستونِ فیلترها'}
          className="rounded-lg border border-border-c px-2 py-1 font-bold text-text-secondary hover:bg-bg-card disabled:cursor-not-allowed disabled:opacity-40">
          خروجیِ CSV
        </button>
      </div>

      {badFilter ? (
        <p className="text-3xs text-accent-red" data-testid="sarkhati-ev-badfilter">
          {String(events.data?.detail ?? 'قالبِ فیلتر درست نیست')}
        </p>
      ) : null}

      {failed ? (
        <p className="text-3xs text-accent-red" data-testid="sarkhati-ev-error">
          سابقه نرسید — «خالی» با «نرسیدن» یکی نیست.
        </p>
      ) : rows.length === 0 ? (
        <p className="text-3xs text-text-muted" data-testid="sarkhati-ev-empty">
          ردیدی با این فیلترها نیست (صفرِ واقعی، نه خطا).
        </p>
      ) : (
        <div className="max-h-[46vh] overflow-auto">
          <table className="w-full min-w-[560px] text-3xs" data-testid="sarkhati-ev-rows">
            <thead className="sticky top-0 bg-bg-primary/90">
              <tr className="text-text-muted">
                <th className="text-start font-bold">زمان</th>
                <th className="text-start font-bold">شناسه</th>
                <th className="text-start font-bold">گونه</th>
                <th className="text-start font-bold">وضعیت</th>
                <th className="text-start font-bold">نماد</th>
                <th className="text-start font-bold">جزئیات</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((e) => (
                <tr key={e.id} className="border-t border-border-c/40 align-top"
                  data-testid={`sarkhati-ev-${e.id}`}>
                  <td className="num py-0.5">{String(e.written_at ?? '')}</td>
                  <td className="num">{e.execution_id}</td>
                  <td className="font-bold">{String(e.kind ?? '')}</td>
                  <td>
                    {String(e.status ?? '')}
                    {e.order_state ? `/${String(e.order_state)}` : ''}
                    {e.error_code ? (
                      <span className="ms-1 text-accent-red"
                        title={String(e.detail ?? '')}>
                        {CODE_LABEL[String(e.error_code)] ?? String(e.error_code)}
                      </span>
                    ) : null}
                  </td>
                  <td className="num">{e.symbol ?? '—'}</td>
                  <td className="max-w-[42ch] break-words text-text-secondary">
                    {String(e.detail ?? '—')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-monitor-note">
        این فهرست فقطِ رخدادهایِ خودِ برنامه است (اتصال، نشست، پیش‌فرود، آماده‌سازی،
        ارسال، نتیجه، رفعِ ابهام، توقف، لغو). رمز، کوکی، JWT و نشانیِ نشست هیچ‌وقت
        درِ آن نمی‌نشینند و درِ فایلِ خروجی هم نمی‌آیند.
      </p>
    </div>
  );
}
