// features/execution/routes/OrderLinePage.tsx -- سرخطیِ چندنمادی
//
// بندِ ۱.۲ وِ ۱.۳ مأموریتِ System 2: چندِ تبِ مستقل برایِ آماده‌سازیِ سرخطی،
// جایی که قیمت، تعداد، نماد، شناسۀِ اجرا وِ نتیجهٔ هرِ تب مالِ همونِ تب است.
//
// سه چیز درِ اینِ صفحه عمداً «نیست»:
//  • هیچِ داوریِ تازه‌ای درِ رابط ساخته نمی‌شود. آنچه زیرِ «اعتبارسنجی» خوانده
//    می‌شود `checks`/`reasons` خودِ سرویس است (PASS/FAIL/UNKNOWN) وِ UNKNOWN باِ
//    FAIL یکِ رنگ ندارد.
//  • هیچِ «ارسالِ گروهی»ای بی‌مرورِ پیش ازِ آن وجود ندارد: دکمه اول چک‌لیستِ
//    همانِ سفارش‌ها را باز می‌کند (نماد، قیمت، تعداد، شناسۀِ اجرا) وِ ارسالِ
//    واقعی باِ `confirmed: true` درِ همانِ کلیک است -- همانِ `require_confirmation`
//    خودِ بک‌اند، نه یکِ عادتِ UI.
//  • هیچِ تبی رنگِ تبِ دیگری را نمی‌بیند: نتیجه، خطا وِ «نامعلوم» درِ stateِ
//    همانِ تب می‌نشینند (`orderLineStore`) وِ سقفِ هم‌زمانی ازِ `limits.max_orders`
//    خوانده می‌شود، نه ازِ حدسِ رابط.
//
// دروازۀِ احرازِ هویتِ سرویس ازِ `orderClient.deriveGate` می‌آید: «سرویس نیست»،
// «هنوز نرسیده» وِ «هست ولیِ زنده نیست» سه متنِ جدا‌اند وِ هیچ‌کدام دکمه را
// فعال نمی‌کند.
import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@shared/components/ui/tabs';
import { useExecutionStatus } from '@features/portfolio/lib/orderClient';
import { toFaDigits } from '@shared/lib/fmt';
import { fetchLimits, PHASE_FA, VERDICT_FA, type ExecutionPhase } from '../api/orderLineApi';
import {
  batchDispatch, localGaps, tabDispatch, tabPreflight, tabReconcile,
  type ActionDeps,
} from '../lib/orderLineActions';
import { formNumber, useOrderLineStore, type OrderTab } from '../stores/orderLineStore';

const PHASE_TONE: Record<string, string> = {
  idle: 'text-text-muted',
  draft: 'text-text-muted',
  sending: 'text-accent-yellow',
  validated: 'text-accent-blue',
  prepared: 'text-accent-blue',
  scheduled: 'text-accent-yellow',
  dispatched: 'text-accent-yellow',
  acknowledged: 'text-accent-green',
  reconciled: 'text-accent-green',
  unknown_result: 'text-accent-yellow',
  failed: 'text-accent-red',
};

const VERDICT_TONE: Record<string, string> = {
  PASS: 'text-accent-green', FAIL: 'text-accent-red', UNKNOWN: 'text-text-muted',
};

function phaseText(phase: string): string {
  return PHASE_FA[phase as ExecutionPhase] ?? (phase === 'sending' ? 'در حالِ ارسال' : 'پیش‌نویس');
}

function TabBadge({ tab }: { tab: OrderTab }) {
  return (
    <span className={`num-text text-3xs ${PHASE_TONE[tab.phase] ?? 'text-text-muted'}`}>
      {phaseText(tab.phase)}
    </span>
  );
}

function OrderForm({ tab, deps, allowMock }: { tab: OrderTab; deps: ActionDeps; allowMock: boolean }) {
  const patch = useOrderLineStore((s) => s.patch);
  const [busy, setBusy] = useState<'pre' | 'send' | 'rec' | null>(null);
  const gaps = localGaps(tab);
  const checkNames = Object.keys(tab.checks ?? {});

  const go = async (which: 'pre' | 'send' | 'rec') => {
    setBusy(which);
    try {
      if (which === 'pre') await tabPreflight(tab, deps);
      if (which === 'send') await tabDispatch(tab, deps);
      if (which === 'rec') await tabReconcile(tab, deps);
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="flex min-w-0 flex-col gap-2" data-testid={`order-tab-panel-${tab.id}`}>
      <div className="flex flex-wrap items-end gap-2">
        <label className="flex min-w-0 flex-col gap-1 text-3xs text-text-muted">
          نماد
          <input
            data-testid={`order-symbol-${tab.id}`}
            value={tab.symbol}
            onChange={(e) => patch(tab.id, { symbol: e.target.value })}
            placeholder="مثلاً فولاد"
            className="w-40 rounded-md border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-3xs text-text-muted">
          قیمت
          <input
            data-testid={`order-price-${tab.id}`}
            inputMode="decimal"
            value={tab.price}
            onChange={(e) => patch(tab.id, { price: e.target.value })}
            className="num w-28 rounded-md border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-3xs text-text-muted">
          تعداد
          <input
            data-testid={`order-qty-${tab.id}`}
            inputMode="numeric"
            value={tab.quantity}
            onChange={(e) => patch(tab.id, { quantity: e.target.value })}
            className="num w-24 rounded-md border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
          />
        </label>
        <label className="flex flex-col gap-1 text-3xs text-text-muted">
          جهت
          <select
            data-testid={`order-side-${tab.id}`}
            value={tab.side}
            onChange={(e) => patch(tab.id, { side: e.target.value === 'sell' ? 'sell' : 'buy' })}
            className="rounded-md border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
          >
            <option value="buy">خرید</option>
            <option value="sell">فروش</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-3xs text-text-muted">
          حالت
          <select
            data-testid={`order-mode-${tab.id}`}
            value={tab.mode}
            onChange={(e) => patch(tab.id, { mode: e.target.value as OrderTab['mode'] })}
            className="rounded-md border border-border-c bg-bg-primary px-2 py-1 text-2xs text-text-primary"
          >
            <option value="safe">safe</option>
            <option value="fast">fast</option>
            <option value="ultra">ultra</option>
          </select>
        </label>
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <button type="button" data-testid={`order-preflight-${tab.id}`} disabled={busy !== null}
                onClick={() => void go('pre')}
                className="rounded-md border border-border-c px-2 py-1 text-3xs font-bold text-text-secondary hover:text-text-primary disabled:opacity-50">
          اعتبارسنجی
        </button>
        {/* «آماده‌سازی» عمداً دکمه ندارد: `/prepare` شناسۀِ اجرا را درِ سرویس رزرو
            می‌کند وِ آنِ رزرو هیچ‌گاه آزاد نمی‌شود (شاهدِ زنده: prepare(id) وِ بعد
            dispatch(id) ⇒ `DUPLICATE_GUARD`، `execution_service.py:383`). دوِ دکمه
            درِ یکِ تب یعنی اولینِ کلیکِ بی‌ضرر، دومِی را رد می‌کند. */}
        <button type="button" data-testid={`order-dispatch-${tab.id}`} disabled={busy !== null || gaps.length > 0}
                onClick={() => void go('send')}
                title="باِ تأییدِ صریحِ همینِ کلیک ارسال می‌شود (confirmed: true)"
                className="rounded-md border border-accent-blue/60 bg-accent-blue/10 px-2 py-1 text-3xs font-black text-accent-blue disabled:opacity-50">
          ارسالِ همینِ تب
        </button>
        {tab.phase === 'unknown_result' || tab.phase === 'dispatched' ? (
          <button type="button" data-testid={`order-reconcile-${tab.id}`} disabled={busy !== null}
                  onClick={() => void go('rec')}
                  className="rounded-md border border-accent-yellow/60 px-2 py-1 text-3xs font-bold text-accent-yellow">
            مطابقتِ نتیجه
          </button>
        ) : null}
        {allowMock ? (
          <label className="flex items-center gap-1 text-3xs text-text-muted"
                 data-testid={`order-mockswitch-${tab.id}`}>
            <input type="checkbox" checked={tab.mockInstrument}
                   onChange={(e) => patch(tab.id, { mockInstrument: e.target.checked })} />
            شناسۀِ بدلِ کارگزاری
          </label>
        ) : null}
        <span className="num text-3xs text-text-muted" data-testid={`order-execid-${tab.id}`}>
          شناسه: {tab.executionId}
        </span>
        <TabBadge tab={tab} />
      </div>

      {gaps.length ? (
        <p className="text-3xs text-text-muted" data-testid={`order-gaps-${tab.id}`}>{gaps.join(' · ')}</p>
      ) : null}
      {tab.note ? (
        <p className="text-3xs text-accent-yellow" data-testid={`order-note-${tab.id}`}>{tab.note}</p>
      ) : null}

      {checkNames.length ? (
        <ul className="flex flex-col gap-0.5 rounded-lg border border-border-c bg-bg-card/60 px-2 py-1.5"
            data-testid={`order-checks-${tab.id}`}>
          {checkNames.map((k) => {
            const v = tab.checks[k];
            return (
              <li key={k} className="flex flex-wrap items-baseline gap-x-2 text-3xs">
                <span className={`font-black ${VERDICT_TONE[v] ?? 'text-text-secondary'}`}
                      data-testid={`order-check-${tab.id}-${k}`}>
                  {VERDICT_FA[v] ?? v}
                </span>
                <span className="font-bold text-text-primary">{k}</span>
                {tab.reasons?.[k] && v !== 'PASS' ? <span className="text-text-muted">{tab.reasons[k]}</span> : null}
              </li>
            );
          })}
        </ul>
      ) : null}

      {tab.result ? (
        <pre className="max-h-40 overflow-auto rounded-lg border border-border-c bg-bg-primary px-2 py-1.5 text-3xs leading-5 text-text-secondary"
             data-testid={`order-result-${tab.id}`}>
          {JSON.stringify(tab.result, null, 2)}
        </pre>
      ) : null}
    </div>
  );
}

export default function OrderLinePage() {
  const { tabs, activeId, addTab, closeTab, activate, mark, beginSend, endSend } = useOrderLineStore();
  const deps: ActionDeps = useMemo(() => ({ beginSend, endSend, mark }), [beginSend, endSend, mark]);
  const { gate, isPending } = useExecutionStatus();
  const limits = useQuery({ queryKey: ['execution-limits'], queryFn: () => fetchLimits(), retry: 1, staleTime: 120_000 });
  const [review, setReview] = useState(false);
  const [batchBusy, setBatchBusy] = useState(false);

  const maxOrders = Math.max(1, Math.floor(limits.data?.limits?.max_orders ?? 1));
  // آداپتور را خودِ سرویس اعلام می‌کند؛ رابط تصمیم نمی‌گیرد. تیکِ `mock_instrument`
  // فقط درِ adapterِ mock دیده می‌شود تا درِ اتصالِ واقعی هرگز Mock: ساخته نشود.
  const allowMock = gate.status?.adapter === 'mock';
  const ready = tabs.filter((t) => localGaps(t).length === 0);
  const active = tabs.find((t) => t.id === activeId) ?? null;

  const startTab = () => addTab();

  return (
    <div className="flex w-full min-w-0 flex-col gap-2" data-testid="order-line-page">
      <section className="glass-panel flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-border-c px-2.5 py-2"
               data-testid="order-line-gate" data-state={gate.canTrade ? 'ready' : 'closed'}>
        <span className="text-2xs font-black text-text-primary">سرخطیِ چندنمادی</span>
        <span className="num-text text-3xs text-text-muted" data-testid="order-line-adapter">
          آداپتور: {gate.status?.adapter ?? '—'} · dry_run: {gate.status?.dry_run == null ? '—' : (gate.status.dry_run ? 'بله' : 'خیر')} ·
          live: {gate.status?.live_enabled ? 'وصل' : 'خاموش'} ·
          بیرون‌ازدستگاه: {gate.status?.nothing_will_leave_the_machine == null ? '—'
            : (gate.status.nothing_will_leave_the_machine ? 'نمی‌رود' : 'ممکن است برود')}
        </span>
        <span className={`text-3xs ${gate.canTrade ? 'text-accent-green' : 'text-accent-yellow'}`}
              data-testid="order-line-gate-reason">
          {isPending && !gate.status ? 'در حالِ خواندنِ وضعیتِ سرویس…' : gate.reason}
        </span>
        <span className="num text-3xs text-text-muted" data-testid="order-line-limits">
          سقفِ سفارش: {toFaDigits(maxOrders)} · تأییدِ صریح: {limits.data?.limits?.require_confirmation === false ? 'لازم نیست' : 'لازم است'}
        </span>
        <span className="ms-auto flex items-center gap-1.5">
          <button type="button" data-testid="order-add-tab" onClick={startTab}
                  className="rounded-md border border-accent-blue/50 bg-accent-blue/10 px-2 py-1 text-3xs font-black text-accent-blue">
            ＋ تبِ تازه
          </button>
        </span>
      </section>

      {tabs.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border-c bg-bg-card/40 px-3 py-3 text-2xs text-text-muted"
           data-testid="order-line-empty">
          هیچِ تبی باز نیست. هرِ تب یکِ نماد باِ قیمت، تعداد وِ شناسۀِ اجرایِ خودش است؛
          تب‌ها هیچ فیلدی را باِ هم بهِ اشتراک نمی‌گذارند.
        </p>
      ) : (
        <Tabs value={activeId ?? undefined} onValueChange={activate} className="flex min-w-0 flex-col gap-2">
          <TabsList aria-label="تب‌های سرخطی" className="flex flex-wrap items-center gap-1">
            {tabs.map((t) => (
              <span key={t.id} className="flex items-center gap-0.5 rounded-full border border-border-c bg-bg-card/70 ps-2">
                <TabsTrigger value={t.id} data-testid={`order-tab-${t.id}`}
                             className="px-1 py-1 text-2xs font-bold">
                  <span className="num">{t.symbol || 'بی‌نماد'}</span>
                  <span className="ms-1">·</span>
                  <TabBadge tab={t} />
                </TabsTrigger>
                <button type="button" data-testid={`order-close-${t.id}`}
                        onClick={() => closeTab(t.id)}
                        title="بستنِ همینِ تب (دیگرِ تب‌ها دست‌نخورده می‌مانند)"
                        className="mx-0.5 rounded-full px-1.5 py-0.5 text-2xs text-text-muted hover:text-accent-red">
                  ×
                </button>
              </span>
            ))}
          </TabsList>
          {tabs.map((t) => (
            <TabsContent key={t.id} value={t.id} data-testid={`order-content-${t.id}`} className="min-w-0">
              <OrderForm tab={t} deps={deps} allowMock={allowMock} />
            </TabsContent>
          ))}
        </Tabs>
      )}

      {tabs.length > 0 ? (
        <section className="glass-panel flex min-w-0 flex-col gap-2 rounded-xl border border-border-c px-2.5 py-2"
                 data-testid="order-batch">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-2xs font-black text-text-primary">ارسالِ گروهیِ کنترل‌شده</span>
            <span className="num text-3xs text-text-muted" data-testid="order-batch-count">
              آماده: {toFaDigits(ready.length)} از {toFaDigits(tabs.length)} · سقفِ هم‌زمانی: {toFaDigits(maxOrders)}
            </span>
            <button type="button" data-testid="order-batch-review" disabled={ready.length === 0 || batchBusy}
                    onClick={() => setReview((v) => !v)}
                    className="rounded-md border border-accent-blue/60 bg-accent-blue/10 px-2 py-1 text-3xs font-black text-accent-blue disabled:opacity-50">
              {review ? 'بستنِ مرور' : 'مرورِ سفارش‌ها پیش ازِ ارسال'}
            </button>
            {review ? (
              <button type="button" data-testid="order-batch-send" disabled={batchBusy || ready.length === 0}
                      onClick={async () => {
                        setBatchBusy(true);
                        try { await batchDispatch(ready, deps, limits.data); setReview(false); }
                        finally { setBatchBusy(false); }
                      }}
                      className="rounded-md border border-accent-green/60 bg-accent-green/10 px-2 py-1 text-3xs font-black text-accent-green disabled:opacity-50">
                تأیید و ارسالِ {toFaDigits(ready.length)} سفارش
              </button>
            ) : null}
          </div>

          {review ? (
            <ul className="flex flex-col gap-1 rounded-lg border border-dashed border-accent-blue/40 bg-bg-primary/60 px-2 py-1.5"
                data-testid="order-batch-review-list">
              {ready.map((t) => (
                <li key={t.id} className="num-text flex flex-wrap items-baseline gap-x-2 text-3xs text-text-secondary">
                  <span className="font-black text-text-primary">{t.symbol}</span>
                  <span>{t.side === 'buy' ? 'خرید' : 'فروش'}</span>
                  <span>{toFaDigits(formNumber(t.price) ?? 0)}</span>
                  <span>× {toFaDigits(formNumber(t.quantity) ?? 0)}</span>
                  <span className="text-text-muted">{t.mode}</span>
                  <span className="text-text-muted">{t.executionId}</span>
                </li>
              ))}
              {tabs.filter((t) => localGaps(t).length > 0).map((t) => (
                <li key={t.id} className="text-3xs text-text-muted" data-testid={`order-batch-skipped-${t.id}`}>
                  {(t.symbol || 'بی‌نماد')}: درِ صفِ گروهی نمی‌نشیند — {localGaps(t).join(' · ')}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      {active ? (
        <p className="text-3xs leading-5 text-text-muted" data-testid="order-line-note">
          هیچِ سفارشی باِ بازکردنِ اینِ صفحه اجرا نمی‌شود؛ پیش‌نویس‌ها ازِ همینِ دستگاه
          بازیابی می‌شوند وِ حالتِ «در حالِ ارسالِ دیروز» بهِ پیش‌نویس برمی‌گردد. نتیجهٔ
          نامعلوم باِ رد یکی نیست وِ باِ همانِ شناسه مطابقت می‌شود.
          {allowMock ? (
            <span data-testid="order-line-mockhint">
              {' '}آداپتورِ mock نگاشتِ کارگزاری اختراع نمی‌کند: برایِ پیمودنِ کلِ مسیر،
              تیکِ «شناسۀِ بدلِ کارگزاری» را درِ همانِ تب بزنید. نمادی که ISIN درِ بانکِ
              محلی ندارد حتی باِ تیک `NOT_ORDERABLE` می‌ماند.
            </span>
          ) : null}
        </p>
      ) : null}
    </div>
  );
}
