// features/portfolio/routes/SarkhatiPage.tsx — تبِّ مستقلِ «سرخطی»
//
// یکِ صفحه، شش بخش، و یکِ صاحبِ عمل: جریانِ «انتخابِ نماد ← تنظیمِ سفارش ←
// پیش‌فرود ← آماده‌سازی ← بازبینی ← تأیید ← گیتِ اجرا ← نتیجه ← استعلامِ دوباره ←
// تاریخچه» ازِ همان `api/execution.py` می‌گذرد. هیچ‌کدام ازِ این کارت‌ها سفارش
// نمی‌سازند و هیچ‌کدام وضعیتِ اتصال را ازِ متنِ رابط نمی‌خوانند؛ تنها درِ نوشتنِ
// سفارش، پنلِ سفارش است (`ExecutionPanel`) و بقیه می‌خوانند.
//
// ستونِ فقراتِ صفحه «خطِ جریانِ اجرا» است (`SarkhatiPipeline`): همان ترتیبِ
// دروازه‌دار را نشان می‌دهد و می‌گوید نوبتِ تصمیم کجاست. این انتخاب ازِ خودِ
// محصول آمده، نه ازِ قالبِ «فرمِ سفارش»: چیزی که کاربر روزِ بازار دنبال آن است
// «کدام در بسته است» است، نه «چند کارت رویِ صفحه است».
//
// نشانی: `#/sarkhati` (Hash Router، مثلِ بقیۀِ مقصدها) — refresh و لینکِ مستقیم
// کار می‌کند چون route درِ `routes.tsx` ثبت شده است.
import { useMemo, useState } from 'react';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useExecutionLedger, useExecutionStatus, useExecutionTimings } from '../lib/orderClient';
import { useSarkhatiFormStore } from '../stores/sarkhatiFormStore';
import { ExecutionPanel } from '../components/ExecutionPanel';
import { SarkhatiConnectionCard } from '../components/sarkhati/SarkhatiConnectionCard';
import { SarkhatiMonitorCard } from '../components/sarkhati/SarkhatiMonitorCard';
import { SarkhatiPipeline } from '../components/sarkhati/SarkhatiPipeline';
import { SarkhatiRiskCard } from '../components/sarkhati/SarkhatiRiskCard';
import { SarkhatiScheduleCard } from '../components/sarkhati/SarkhatiScheduleCard';
import { SarkhatiStatusStrip } from '../components/sarkhati/SarkhatiStatusStrip';
import { SarkhatiSymbolCard, estValue, selectRowFor }
  from '../components/sarkhati/SarkhatiSymbolCard';
import { SarkhatiTrackingCard } from '../components/sarkhati/SarkhatiTrackingCard';

type Section = 'order' | 'connect' | 'schedule' | 'tracking' | 'risk' | 'monitor';

const SECTIONS: { id: Section; label: string; testId: string }[] = [
  { id: 'order', label: 'سفارش', testId: 'sarkhati-tab-order' },
  { id: 'connect', label: 'اتصال', testId: 'sarkhati-tab-connect' },
  { id: 'schedule', label: 'زمان‌بندی', testId: 'sarkhati-tab-schedule' },
  { id: 'tracking', label: 'پیگیریِ نتیجه', testId: 'sarkhati-tab-tracking' },
  { id: 'risk', label: 'ریسک و ایمنی', testId: 'sarkhati-tab-risk' },
  { id: 'monitor', label: 'پایش و سابقه', testId: 'sarkhati-tab-monitor' },
];

export default function SarkhatiPage() {
  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const { gate, dataUpdatedAt } = useExecutionStatus();
  const ledger = useExecutionLedger(gate.endpointPresent);
  const timings = useExecutionTimings(gate.endpointPresent);
  const fields = useSarkhatiFormStore((s) => (symbol ? s.bySymbol[symbol] : undefined));
  const row = useMarketFeedShared(selectRowFor(symbol || '__none__'), 5_000);
  const [section, setSection] = useState<Section>('order');

  const latest = useMemo(() => {
    const recs = ledger.data?.records ?? [];
    return recs.length ? recs[recs.length - 1] : null;
  }, [ledger.data]);

  // رشته‌ها همان چیزی است که آزمون‌ها می‌خوانند (`نماد: `، `هدفِ ارسال: فوری`،
  // `۱۲٬۶۱۰٬۰۰۰ ریال`)؛ فقط برچسب و مقدار از هم جدا شده‌اند تا مقدار برجسته بماند.
  const summary = useMemo(() => {
    const f = fields;
    if (!symbol) {
      return [{ label: 'نماد', value: '—', tone: 'warn' as const },
        { label: '', value: 'بی‌نماد هیچ سفارشی ساخته نمی‌شود', tone: 'muted' as const }];
    }
    return [
      { label: 'نماد', value: symbol, tone: 'strong' as const },
      { label: 'جهت', value: f?.side === 'sell' ? 'فروش' : 'خرید',
        tone: (f?.side === 'sell' ? 'bad' : 'ok') as 'bad' | 'ok' },
      { label: 'قیمت', value: f?.price ? `${f.price} ریال` : '—', tone: 'strong' as const },
      { label: 'حجم', value: f?.quantity ? `${f.quantity} سهم` : '—', tone: 'strong' as const },
      { label: 'ارزشِ تخمینی', value: estValue(f?.price ?? '', f?.quantity ?? ''),
        tone: 'strong' as const },
      { label: 'هدفِ ارسال', value: f?.targetLocal ? f.targetLocal.replace('T', ' ') : 'فوری',
        tone: (f?.targetLocal ? 'warn' : 'muted') as 'warn' | 'muted' },
    ];
  }, [symbol, fields]);

  return (
    <div className="flex w-full min-w-0 flex-col gap-1.5 p-2" data-testid="sarkhati-page"
      data-symbol={symbol || ''}>
      <div className="flex flex-wrap items-baseline gap-x-2.5 gap-y-1">
        <h3 className="text-sm font-black leading-5 text-text-primary">سرخطی</h3>
        <span className="text-2xs text-text-muted">
          اتصال، سفارش، زمان‌بندی، ریسک و پایش درِ یکِ صفحه — همه از سرویسِ مرکزیِ اجرا
        </span>
      </div>

      <SarkhatiStatusStrip gate={gate} />
      <SarkhatiPipeline status={gate.status} timings={timings.data ?? null}
        latest={latest} hasSymbol={!!symbol} />
      <SarkhatiSymbolCard symbol={symbol} row={row.data ?? null} onSelect={setSymbol} />

      <div className="flex flex-wrap items-center gap-1" role="tablist"
        aria-label="بخش‌هایِ سرخطی" data-testid="sarkhati-sections">
        {SECTIONS.map((sec) => (
          <button key={sec.id} type="button" role="tab"
            aria-selected={section === sec.id}
            data-testid={sec.testId}
            onClick={() => setSection(sec.id)}
            className={`rounded-lg px-3 py-1 text-2xs font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${
              section === sec.id
                ? 'bg-neon-cyan/15 text-neon-cyan shadow-[inset_0_-2px_0_var(--neon-cyan)]'
                : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}>
            {sec.label}
          </button>
        ))}
      </div>

      {/* «برچسب: مقدار» باید درِ یکِ باکسِ درون‌خطی بنشیند: اگر برچسب و مقدار دو
          flex-item جدا شوند، inner_textِ کرومیوم بینشان خط می‌اندازد و «نماد: »
          دیگر آن رشته نیست — آنگاه آزمونِ واحد (textContent) سبز است و سنجۀِ
          زنده (innerText) قرمز؛ دو خوانش از یکِ پاسخ. مقدار با num-text می‌آید،
          چون «۱۲٬۶۱۰٬۰۰۰ ریال» عددِ خالص نیست و `.num` جهتِ جمله را LTR می‌کند. */}
      <p className="flex flex-wrap items-baseline gap-x-2 text-2xs leading-5"
        data-testid="sarkhati-draft-summary">
        {summary.map((part, i) => (
          <span key={i}>
            {i > 0 ? <span aria-hidden="true" className="me-2 text-border-c">·</span> : null}
            <span className="text-text-muted">{part.label ? `${part.label}: ` : ''}</span>
            <b className={`num-text font-black ${
              part.tone === 'strong' ? 'text-text-primary'
                : part.tone === 'ok' ? 'text-accent-green'
                  : part.tone === 'bad' ? 'text-accent-red'
                    : part.tone === 'warn' ? 'text-accent-yellow'
                      : 'text-text-secondary'}`}>
              {part.value}
            </b>
          </span>
        ))}
      </p>

      {section === 'order' ? (
        <div className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
          data-testid="sarkhati-order-section">
          <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h4 className="text-xs font-black leading-4 text-text-primary">سفارش</h4>
            {!symbol ? (
              <span className="text-2xs text-accent-yellow" data-testid="sarkhati-no-symbol">
                بی‌نمادِ انتخاب‌شده هیچ سفارشی ساخته نمی‌شود
              </span>
            ) : row.data == null ? (
              <span className="text-2xs text-accent-yellow" data-testid="sarkhati-no-row">
                این نماد ردیفی درِ تابلویِ امروز ندارد؛ پیش‌فرود آن را رد می‌کند
              </span>
            ) : null}
          </div>
          {symbol ? (
            <ExecutionPanel symbol={symbol} row={row.data ?? null} schedule />
          ) : (
            <p className="text-2xs leading-5 text-text-muted" data-testid="sarkhati-order-empty">
              پیشِ انتخابِ نماد، فرمِ سفارش ساخته نمی‌شود — «—» نماد نیست و هیچ
              پیش‌فرودی با آن معنی ندارد.
            </p>
          )}
        </div>
      ) : section === 'connect' ? (
        <SarkhatiConnectionCard />
      ) : section === 'schedule' ? (
        <SarkhatiScheduleCard ledger={ledger.data ?? null} />
      ) : section === 'tracking' ? (
        <SarkhatiTrackingCard ledger={ledger.data ?? null} caps={gate.caps}
            status={gate.status} endpointPresent={gate.endpointPresent} />
      ) : section === 'risk' ? (
        <SarkhatiRiskCard status={gate.status} />
      ) : (
        <SarkhatiMonitorCard lastStatusAt={dataUpdatedAt} />
      )}

      <p className="text-2xs leading-4 text-text-muted" data-testid="sarkhati-footnote">
        شمارۀِ ردیف‌ها ازِ پاسخِ سرویس است: دفترِ اجرا{' '}
        <span className="num font-bold text-text-secondary">
          {toFaDigits(String(gate.status?.ledger_size ?? 0))}</span> رکورد و{' '}
        <span className="num font-bold text-text-secondary">
          {toFaDigits(String(gate.status?.durable_events ?? 0))}</span> رخدادِ ماندگار.
        بی‌نشستِ تأییدشده هیچ سفارشی ازِ این صفحه ارسال نمی‌شود.
      </p>
    </div>
  );
}
