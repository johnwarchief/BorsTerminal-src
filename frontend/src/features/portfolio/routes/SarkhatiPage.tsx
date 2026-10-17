// features/portfolio/routes/SarkhatiPage.tsx — تبِّ مستقلِ «سرخطی»
//
// یکِ صفحه، شش بخش، و یکِ صاحبِ عمل: جریانِ «انتخابِ نماد ← تنظیمِ سفارش ←
// پیش‌فرود ← آماده‌سازی ← بازبینی ← تأیید ← گیتِ اجرا ← نتیجه ← استعلامِ دوباره ←
// تاریخچه» ازِ همان `api/execution.py` می‌گذرد. هیچ‌کدام ازِ این کارت‌ها سفارش
// نمی‌سازند و هیچ‌کدام وضعیتِ اتصال را ازِ متنِ رابط نمی‌خوانند؛ تنها درِ نوشتنِ
// سفارش، پنلِ سفارش است (`ExecutionPanel`) و بقیه می‌خوانند.
//
// نشانی: `#/sarkhati` (Hash Router، مثلِ بقیۀِ مقصدها) — refresh و لینکِ مستقیم
// کار می‌کند چون route درِ `routes.tsx` ثبت شده است.
import { useMemo, useState } from 'react';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useExecutionLedger, useExecutionStatus } from '../lib/orderClient';
import { useSarkhatiFormStore } from '../stores/sarkhatiFormStore';
import { ExecutionPanel } from '../components/ExecutionPanel';
import { SarkhatiConnectionCard } from '../components/sarkhati/SarkhatiConnectionCard';
import { SarkhatiMonitorCard } from '../components/sarkhati/SarkhatiMonitorCard';
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
  const fields = useSarkhatiFormStore((s) => (symbol ? s.bySymbol[symbol] : undefined));
  const row = useMarketFeedShared(selectRowFor(symbol || '__none__'), 5_000);
  const [section, setSection] = useState<Section>('order');

  const summary = useMemo(() => {
    const f = fields;
    if (!symbol) return 'نمادی انتخاب نشده — ازِ فهرستِ بالا یکِ نمادِ موجود در تابلو بردارید.';
    const parts = [
      `نماد: ${symbol}`,
      `جهت: ${f?.side === 'sell' ? 'فروش' : 'خرید'}`,
      `قیمت: ${f?.price ? `${f.price} ریال` : '—'}`,
      `حجم: ${f?.quantity ? `${f.quantity} سهم` : '—'}`,
      `ارزشِ تخمینی: ${estValue(f?.price ?? '', f?.quantity ?? '')}`,
      f?.targetLocal ? `هدفِ ارسال: ${f.targetLocal.replace('T', ' ')}` : 'هدفِ ارسال: فوری',
    ];
    return parts.join(' · ');
  }, [symbol, fields]);

  return (
    <div className="flex w-full min-w-0 flex-col gap-2 p-2" data-testid="sarkhati-page"
      data-symbol={symbol || ''}>
      <div className="flex flex-wrap items-baseline gap-2">
        <h3 className="text-sm font-black text-text-primary">سرخطی</h3>
        <span className="text-3xs text-text-muted">
          اتصال، سفارش، زمان‌بندی، ریسک و پایش درِ یکِ صفحه — همه از سرویسِ مرکزیِ اجرا
        </span>
      </div>

      <SarkhatiStatusStrip gate={gate} />
      <SarkhatiSymbolCard symbol={symbol} row={row.data ?? null} onSelect={setSymbol} />

      <div className="flex flex-wrap items-center gap-1.5" role="tablist"
        aria-label="بخش‌هایِ سرخطی" data-testid="sarkhati-sections">
        {SECTIONS.map((sec) => (
          <button key={sec.id} type="button" role="tab"
            aria-selected={section === sec.id}
            data-testid={sec.testId}
            onClick={() => setSection(sec.id)}
            className={`rounded-full border px-3 py-1 text-2xs font-bold transition-colors ${
              section === sec.id
                ? 'border-neon-cyan/50 bg-neon-cyan/15 text-neon-cyan'
                : 'border-border-c bg-bg-card text-text-secondary hover:bg-bg-secondary hover:text-text-primary'}`}>
            {sec.label}
          </button>
        ))}
      </div>

      <p className="rounded-lg border border-border-c/60 bg-bg-card/40 px-2 py-1 text-3xs leading-4 text-text-secondary"
        data-testid="sarkhati-draft-summary">
        {summary}
      </p>

      {section === 'order' ? (
        <div className="glass-panel rounded-2xl p-2.5" data-testid="sarkhati-order-section">
          <div className="mb-1 flex flex-wrap items-baseline gap-2">
            <h4 className="text-2xs font-black text-text-secondary">سفارش</h4>
            {!symbol ? (
              <span className="text-3xs text-accent-yellow" data-testid="sarkhati-no-symbol">
                بی‌نمادِ انتخاب‌شده هیچ سفارشی ساخته نمی‌شود
              </span>
            ) : row.data == null ? (
              <span className="text-3xs text-accent-yellow" data-testid="sarkhati-no-row">
                این نماد ردیفی درِ تابلویِ امروز ندارد؛ پیش‌فرود آن را رد می‌کند
              </span>
            ) : null}
          </div>
          {symbol ? (
            <ExecutionPanel symbol={symbol} row={row.data ?? null} schedule />
          ) : (
            <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-order-empty">
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

      <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-footnote">
        شمارۀِ ردیف‌ها ازِ پاسخِ سرویس است: دفترِ اجرا{' '}
        <span className="num">{toFaDigits(String(gate.status?.ledger_size ?? 0))}</span> رکورد و{' '}
        <span className="num">{toFaDigits(String(gate.status?.durable_events ?? 0))}</span> رخدادِ
        ماندگار. بی‌نشستِ تأییدشده هیچ سفارشی ازِ این صفحه ارسال نمی‌شود.
      </p>
    </div>
  );
}
