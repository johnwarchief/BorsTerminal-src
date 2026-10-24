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
import { fmtAge } from '@shared/lib/time';
import { toFaDigits } from '@shared/lib/fmt';
import { downloadCsvWithMeta, toExportTable } from '@shared/lib/tableExport';
import {
  CODE_LABEL, useExecutionEvents, useExecutionTimings,
  type EventFilters, type ExecutionEvent,
} from '../../lib/orderClient';
import { Chip, GhostBtn, Line, Note, Section, Table, Td, Tr } from './parts';

const KINDS = ['connect', 'session', 'preflight', 'prepare', 'dispatch', 'state',
  'reconcile', 'cancel', 'halt', 'resume', 'duplicate'];

const INPUT = 'rounded-lg border border-border-c bg-bg-primary px-1.5 py-0.5 text-2xs '
  + 'text-text-primary placeholder:text-text-muted';

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
    <Section title="پایشِ ارتباط و سابقه" testId="sarkhati-monitor-card"
      sub="ردِّپایِ ماندگارِ خودِ برنامه، نه لاگِ کارگزاری"
      right={(
        <>
          <Chip tone={failed ? 'bad' : 'ok'} title="خودِ درِ /api/execution/status">
            {failed ? 'سرویسِ اجرا پاسخ نداد' : 'درِ اجرا پاسخ می‌دهد'}
          </Chip>
          <Chip tone="idle" testId="sarkhati-latency"
            title="از /api/execution/timings — monotonic، نه ساعتِ دیواری">
            تأخیرِ dispatch p50:{' '}
            <span className="num">{p50 != null ? `${toFaDigits(String(p50))} ms` : 'اندازه‌گیری‌نشده'}</span>
          </Chip>
          <span className="text-2xs text-text-muted" data-testid="sarkhati-last-status">
            آخرینِ خواندنِ وضعیت:{' '}
            {lastStatusAt ? <span className="num">{fmtAge(Date.now() - lastStatusAt)}</span> : '—'}
          </span>
        </>
      )}>
      <div className="flex flex-wrap items-end gap-1.5" data-testid="sarkhati-event-filters">
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">نماد
          <input value={sym} onChange={(e) => setSym(e.target.value)}
            data-testid="sarkhati-ev-f-symbol" className={`${INPUT} w-24`} />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">شناسۀِ اجرا
          <input value={id} onChange={(e) => setId(e.target.value)}
            data-testid="sarkhati-ev-f-id" className={`${INPUT} num w-32`} />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">وضعیت
          <input value={st} onChange={(e) => setSt(e.target.value)}
            placeholder="مثلاً acknowledged"
            data-testid="sarkhati-ev-f-status" className={`${INPUT} w-32`} />
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">گونه
          <select value={kind} onChange={(e) => setKind(e.target.value)}
            data-testid="sarkhati-ev-f-kind" className={INPUT}>
            <option value="">همۀِ گونه‌ها</option>
            {KINDS.map((k) => (<option key={k} value={k}>{k}</option>))}
          </select>
        </label>
        <label className="flex flex-col gap-0.5 text-3xs text-text-muted">از تاریخ
          <input type="date" value={since} onChange={(e) => setSince(e.target.value)}
            data-testid="sarkhati-ev-f-since" dir="ltr" className={`${INPUT} num`} />
        </label>
        <GhostBtn testId="sarkhati-ev-apply" onClick={apply}
          title="فیلترها فقط با این دکمه رویِ پرسشِ سرویس اعمال می‌شوند">
          اعمالِ فیلتر
        </GhostBtn>
        <GhostBtn testId="sarkhati-ev-export" disabled={rows.length === 0}
          title={rows.length === 0 ? 'بدونِ ردیف، فایلِ خالی ساخته نمی‌شود'
            : 'CSV با سرستونِ فیلترها، بدونِ payload و بدونِ راز'}
          onClick={exportCsv}>
          خروجیِ CSV
        </GhostBtn>
      </div>

      <div className="mt-2">
        {badFilter ? (
          <Line kind="error" testId="sarkhati-ev-badfilter">
            {String(events.data?.detail ?? 'قالبِ فیلتر درست نیست')} — فرمتِ تاریخ YYYY-MM-DD است.
          </Line>
        ) : null}

        {failed ? (
          <Line kind="error" testId="sarkhati-ev-error">
            سابقه نرسید — «خالی» با «نرسیدن» یکی نیست. با «اعمالِ فیلتر» دوباره بسنجید.
          </Line>
        ) : rows.length === 0 ? (
          <Line testId="sarkhati-ev-empty">
            ردیدی با این فیلترها نیست (صفرِ واقعی، نه خطا).
          </Line>
        ) : (
          <Table testId="sarkhati-ev-rows" minWidth={620}
            head={['زمان', 'شناسه', 'گونه', 'وضعیت', 'نماد', 'جزئیات']}>
            {rows.map((e) => (
              <Tr key={e.id} testId={`sarkhati-ev-${e.id}`}>
                <Td num>{String(e.written_at ?? '')}</Td>
                <Td num>{e.execution_id}</Td>
                <Td strong>{String(e.kind ?? '')}</Td>
                <Td>
                  <span className="num-text">
                    {String(e.status ?? '')}{e.order_state ? `/${String(e.order_state)}` : ''}
                  </span>
                  {e.error_code ? (
                    <Chip tone="bad" title={String(e.detail ?? '')}>
                      {CODE_LABEL[String(e.error_code)] ?? String(e.error_code)}
                    </Chip>
                  ) : null}
                </Td>
                <Td num>{e.symbol ?? '—'}</Td>
                <Td tone="muted">
                  <span className="block max-w-[46ch] break-words">{String(e.detail ?? '—')}</span>
                </Td>
              </Tr>
            ))}
          </Table>
        )}
      </div>

      <div className="mt-1.5">
        <Note label="این سابقه چه چیزی نیست" testId="sarkhati-monitor-note">
          این فهرست فقطِ رخدادهایِ خودِ برنامه است (اتصال، دسترسی، پیش‌فرود، آماده‌سازی،
          ارسال، نتیجه، رفعِ ابهام، توقف، لغو) — نه لاگِ کارگزاری. رمز، کوکی، JWT و
          دسترسی به حساب هیچ‌وقت در آن نمی‌نشیند و در فایل خروجی هم نمی‌آید.
        </Note>
      </div>
    </Section>
  );
}
