// features/portfolio/routes/SarkhatiPage.tsx — تبِّ مستقلِ «سرخطی»
//
// بازطراحیِ 2026-10-18 (مأموریتِ مالک، بندِ ۳): پیش ازِ این صفحه با پنج نوارِ
// هم‌وزن باز می‌شد (خطِ وضعیتِ ۱۴چیپ، خطِ جریانِ ۹گره، کارتِ نماد، شش تب، فرم).
// هیچ‌کدام نمی‌گفت «از کجا شروع کن». حالا صفحه یک پرسشِ فعال دارد:
//
//   یک خطِ وضعیت ← قدمِ شما (۱ اتصال، ۲ نماد، ۳ سفارش، ۴ نتیجه و پیگیری)
//                ← محتوایِ همان قدم
//                ← «ابزارهایِ حرفه‌ای» (زمان‌بندی، ریسک و ایمنی، پایش و سابقه)
//                ← بازشونده: خطِ جریانِ ۹ گامه + چیپ‌هایِ حالت + شمارش‌هایِ دفتر
//
// سه قید که دست‌نخورده مانده:
//  • هیچ‌کدام ازِ این بخش‌ها سفارش نمی‌سازد؛ تنها نویسندهٔ سفارش `ExecutionPanel`
//    است و تنها منبعِ وضعیتِ اتصال `/api/execution/*` (دو خوانش ازِ یکِ پاسخ).
//  • «قدمِ شما» داوریِ تازهٔ فرانت نیست: `deriveStep` فقط می‌گوید کدام پرسش
//    بی‌پاسخ مانده، و دروازۀ واقعیِ ارسال همان `gate.canTradeِ` خودِ سرویس است.
//  • قابلیتِ معتبری حذف نشده: هرچی ازِ صفحهٔ پیشین رفتنِ چشم بود، به
//    «ابزارهایِ حرفه‌ای» یا بازشونده رفته — نه به سطلِ زباله.
//
// نشانی: `#/sarkhati` (Hash Router) — refresh و لینکِ مستقیم کار می‌کند.
import { useEffect, useMemo, useState } from 'react';
import { useMarketFeedShared } from '@shared/api/marketFeed';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useExecutionLedger, useExecutionStatus, useExecutionTimings } from '../lib/orderClient';
import { deriveStep, statusLine, panelLabel, stepIndex,
  type SarkhatiPanel, type SarkhatiStep } from '../lib/sarkhatiFlow';
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

/** قدم‌هایِ اصلی = همان چهار پرسشِ ترتیب‌دار. */
const STEPS: { id: SarkhatiStep; testId: string }[] = [
  { id: 'connect', testId: 'sarkhati-tab-connect' },
  { id: 'symbol', testId: 'sarkhati-tab-symbol' },
  { id: 'order', testId: 'sarkhati-tab-order' },
  { id: 'tracking', testId: 'sarkhati-tab-tracking' },
];

/** ابزارهایِ حرفه‌ای: واقعی‌اند، ولی اولِ مسیرِ کاربر تازه‌کار نیستند. */
const PRO_SECTIONS = [
  { id: 'schedule', testId: 'sarkhati-tab-schedule' },
  { id: 'risk', testId: 'sarkhati-tab-risk' },
  { id: 'monitor', testId: 'sarkhati-tab-monitor' },
] as const;

export default function SarkhatiPage() {
  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const { gate, dataUpdatedAt } = useExecutionStatus();
  const ledger = useExecutionLedger(gate.endpointPresent);
  const timings = useExecutionTimings(gate.endpointPresent);
  const fields = useSarkhatiFormStore((s) => (symbol ? s.bySymbol[symbol] : undefined));
  const row = useMarketFeedShared(selectRowFor(symbol || '__none__'), 5_000);
  const [landed, setLanded] = useState<SarkhatiPanel | null>(null);

  const latest = useMemo(() => {
    const recs = ledger.data?.records ?? [];
    const mine = symbol ? recs.filter((r) => r.symbol === symbol) : recs;
    return mine.length ? mine[mine.length - 1] : null;
  }, [ledger.data, symbol]);

  // «قدمِ شما» فقط می‌گوید کدام پرسش بی‌پاسخ مانده؛ دروازهِ واقعیِ ارسال همان
  // `gate.canTradeِ` خودِ سرویس است (قاعدهٔ مخزن: یک داور).
  const suggested = useMemo(() => deriveStep({
    gate, symbol: symbol ?? null, draft: fields ?? null, hasRecord: !!latest,
  }), [gate, symbol, fields, latest]);

  // قدمِ پیشنهادی یک‌بار صفحه را فرود می‌آورد؛ بعد از آن فقط کلیکِ کاربر
  // بخش را عوض می‌کند. اگر پیشنهاد همیشه برنده بماند، نوشتنِ حجم درِ همان
  // فرم، کاربر را به «نتیجه و پیگیری» می‌کشاند (چون رکوردِ همان نماد درِ
  // دفترِ اجرا هست). راهنمایی که وسطِ کار صفحه را از دستِ کاربر در می‌گیرد،
  // کمک نیست؛ آزار است. دنبالِ پیشنهاد رفتن، همان دکمهٔ «برو به …» است.
  useEffect(() => {
    if (landed === null && gate.endpointPresent) setLanded(suggested.step);
  }, [landed, gate.endpointPresent, suggested.step]);
  const panel: SarkhatiPanel = landed ?? 'connect';

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

  const stepBtn = (id: SarkhatiPanel, label: string, testId: string, n?: number) => {
    const on = panel === id;
    const isSuggested = suggested.go === id;
    return (
      <button key={id} type="button" role="tab" aria-selected={on}
        data-testid={testId} data-suggested={isSuggested ? 'true' : 'false'}
        onClick={() => setLanded(id)}
        className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-2xs font-bold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 ${
          on ? 'border-neon-cyan bg-neon-cyan/15 text-neon-cyan'
            : isSuggested ? 'border-accent-yellow/60 bg-accent-yellow/10 text-accent-yellow'
              : 'border-border-c/60 text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}>
        {n != null ? (
          <span className={`num grid h-4 w-4 place-items-center rounded-md border text-3xs font-black ${
            on ? 'border-neon-cyan/50 bg-neon-cyan/20' : 'border-border-c bg-bg-primary'}`}>
            {toFaDigits(n)}
          </span>
        ) : null}
        {label}
      </button>
    );
  };

  return (
    <div className="flex w-full min-w-0 flex-col gap-1.5 p-2" data-testid="sarkhati-page"
      data-symbol={symbol || ''} data-step={panel} data-suggested-step={suggested.step}>
      {/* یک خطِ وضعیت، یک قدم، یک کنش — پیشِ ازِ هر جدول و هر چیپ. */}
      <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1"
        data-testid="sarkhati-headline">
        <h3 className="text-sm font-black leading-5 text-text-primary">سرخطی</h3>
        <span className="text-2xs font-bold text-text-secondary" data-testid="sarkhati-status-line"
              data-open={gate.endpointPresent ? 'true' : 'false'}
              data-tradeable={gate.canTrade ? 'true' : 'false'}>
          {statusLine(gate)}
        </span>
        <span className="text-2xs text-text-muted" data-testid="sarkhati-current-step"
              data-step={suggested.step} data-go={suggested.go}>
          قدمِ شما: {toFaDigits(stepIndex(suggested.step))} · {panelLabel(suggested.step)}
        </span>
        {suggested.go !== panel ? (
          <button type="button" data-testid="sarkhati-next-action"
            data-go={suggested.go}
            onClick={() => setLanded(suggested.go)}
            className="rounded-lg border border-accent-blue/60 bg-accent-blue/15 px-2 py-0.5 text-2xs font-black text-accent-blue">
            برو به {panelLabel(suggested.go)}
          </button>
        ) : null}
        <span className="min-w-0 flex-1 truncate text-3xs text-text-muted"
              data-testid="sarkhati-step-why" title={suggested.why}>
          {suggested.why}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <div className="flex flex-wrap items-center gap-1" role="tablist"
          aria-label="قدم‌هایِ سرخطی" data-testid="sarkhati-steps">
          {STEPS.map((s) => stepBtn(s.id, panelLabel(s.id), s.testId,
            stepIndex(s.id as SarkhatiStep)))}
        </div>
        <span className="mx-1 h-4 w-px bg-border-c" aria-hidden="true" />
        <span className="text-3xs font-bold text-text-muted" data-testid="sarkhati-pro-label">
          ابزارهایِ حرفه‌ای:
        </span>
        <div className="flex flex-wrap items-center gap-1" role="tablist"
          aria-label="ابزارهایِ حرفه‌ای" data-testid="sarkhati-pro-sections">
          {PRO_SECTIONS.map((sec) => stepBtn(sec.id, panelLabel(sec.id), sec.testId))}
        </div>
      </div>

      {panel === 'connect' ? (
        <div className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
          data-testid="sarkhati-connect-section">
          <h4 className="mb-1 text-xs font-black leading-4 text-text-primary">اتصال</h4>
          <SarkhatiConnectionCard />
        </div>
      ) : panel === 'symbol' ? (
        <div className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
          data-testid="sarkhati-symbol-section">
          <h4 className="mb-1 text-xs font-black leading-4 text-text-primary">نماد</h4>
          <SarkhatiSymbolCard symbol={symbol} row={row.data ?? null} onSelect={setSymbol} />
        </div>
      ) : panel === 'order' ? (
        <div className="rounded-xl border border-border-c/70 bg-bg-card/25 px-3 py-2.5"
          data-testid="sarkhati-order-section">
          <div className="mb-1 flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <h4 className="text-xs font-black leading-4 text-text-primary">سفارش</h4>
            {symbol ? (
              <span className="text-2xs text-text-secondary" data-testid="sarkhati-symbol-chip">
                نماد: <b className="font-black text-text-primary">{symbol}</b>
                <button type="button" onClick={() => setLanded('symbol')}
                  data-testid="sarkhati-change-symbol"
                  className="ms-1.5 rounded border border-border-c px-1 text-3xs text-text-muted hover:text-text-primary">
                  تغییر
                </button>
              </span>
            ) : (
              <span className="text-2xs text-accent-yellow" data-testid="sarkhati-no-symbol">
                بی‌نمادِ انتخاب‌شده هیچ سفارشی ساخته نمی‌شود
              </span>
            )}
            {!symbol ? null : row.data == null ? (
              <span className="text-2xs text-accent-yellow" data-testid="sarkhati-no-row">
                این نماد ردیفی درِ تابلویِ امروز ندارد؛ پیش‌فرود آن را رد می‌کند
              </span>
            ) : null}
          </div>
          {/* «بررسیِ پیش ازِ ارسال» همین‌جاست: مقادیرِ مؤثر ازِ stateِ خودِ فرم،
              نه ازِ داوریِ رابط. بی‌نماد فرم ساخته نمی‌شود («—» نماد نیست). */}
          <p className="mb-1 flex flex-wrap items-baseline gap-x-2 text-2xs leading-5"
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
          {symbol ? (
            <ExecutionPanel symbol={symbol} row={row.data ?? null} schedule connect={false} />
          ) : (
            <p className="text-2xs leading-5 text-text-muted" data-testid="sarkhati-order-empty">
              پیشِ انتخابِ نماد، فرمِ سفارش ساخته نمی‌شود — «—» نماد نیست و هیچ
              پیش‌فرودی با آن معنی ندارد.
            </p>
          )}
        </div>
      ) : panel === 'tracking' ? (
        <SarkhatiTrackingCard ledger={ledger.data ?? null} caps={gate.caps}
            status={gate.status} endpointPresent={gate.endpointPresent} />
      ) : panel === 'schedule' ? (
        <SarkhatiScheduleCard ledger={ledger.data ?? null} />
      ) : panel === 'risk' ? (
        <SarkhatiRiskCard status={gate.status} />
      ) : (
        <SarkhatiMonitorCard lastStatusAt={dataUpdatedAt} />
      )}

      {/* آنچه «باید دیده شود ولی اولِ مسیر نیست»: خطِ جریانِ نُه‌گامه، چیپ‌هایِ
          حالت/شمارش‌ها و علتِ دروازۀ اجرا. بسته است، نه حذف‌شده. */}
      <details className="rounded-xl border border-border-c/60 bg-bg-secondary/30 px-3 py-1.5"
        data-testid="sarkhati-tech-details">
        <summary className="text-2xs font-bold text-text-secondary">
          جزئیاتِ فنی — خطِ جریانِ اجرا، حالت‌ها و شمارش‌هایِ دفتر
        </summary>
        <div className="mt-1.5 flex flex-col gap-1.5">
          <SarkhatiStatusStrip gate={gate} />
          <SarkhatiPipeline status={gate.status} timings={timings.data ?? null}
            latest={latest} hasSymbol={!!symbol} />
        </div>
      </details>

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
