// features/execution/lib/orderLineActions.ts -- حرکتِ یکِ تب رویِ قراردادِ اجرا
//
// چرا جدا ازِ کامپوننت: «استقلالِ تب‌ها»، «قفلِ دوباره‌ارسال» وِ «نتیجهٔ نامعلوم»
// سه چیزی‌اند که باید درِ آزمونِ واحدِ ثابت بمانند، نه درِ رفتارِ یکِ صفحه. اگرِ
// منطقِ ارسال درِ JSX بنشیند، آزمودنش مرورگرِ کامل می‌خواهد وِ آنِ چهار سطحِ تست
// باِ هم قاطی می‌شوند (بندِ ۱.۵ مأموریت).
//
// سه قاعده که درِ همینِ فایل نگهبانی می‌شوند:
//  ۱) هیچِ نوشتاری بی‌`beginSend()` موفق آغاز نمی‌شود. `beginSend` اتم است: دوِ
//     کلیکِ سریع، Enter+کلیک، یاِ دوِ حلقۀِ batch رویِ یکِ تب، دومی را نمی‌فرستد.
//  ۲) `execution_id` ازِ تب خوانده می‌شود وِ هیچ‌جا تازه ساخته نمی‌شود؛ کلیدِ
//     idempotencyِ سرویس همانِ شناسه است.
//  ۳) نتیجهٔ نامعلوم باِ رد یکی نیست: `unknown_result` یاِ `status: 'error'`
//     بی‌`code` روشن نوشته می‌شود وِ تب درِ همانِ شناسه می‌ماند تاِ reconcile
//     پاسخِ واقعی را بیاورد، نه اینکه سفارشِ تازه بسازد.
//  ۴) `/prepare` درِ اینِ لایه برایِ رابط باز نمی‌شود: خودِ دروازہ شناسۀِ همان
//     پیش‌نویس را رزرو می‌کند وِ آزادش نمی‌کند، پسِ «آماده‌سازی» وِ بعد «ارسال» باِ یک
//     شناسه ⇒ `DUPLICATE_GUARD` (شاهدِ ضبط‌شده: `order-line-contract.spec.ts`).
import {
  dispatchOrder,
  reconcileOrder,
  runPreflight,
  type DispatchResult,
  type LimitsView,
  type OrderDraftBody,
  type PreflightResult,
} from '../api/orderLineApi';
import { formNumber, type OrderTab, type TabPhase } from '../stores/orderLineStore';

export type ActionDeps = {
  beginSend: (id: string) => boolean;
  endSend: (id: string) => void;
  mark: (id: string, fields: Partial<OrderTab>) => void;
};

/** بدنهٔ درخواستِ تب -- هیچِ فیلدی ازِ تبِ دیگری قرض گرفته نمی‌شود */
export function draftBody(tab: OrderTab, confirmed = false): OrderDraftBody {
  return {
    execution_id: tab.executionId,
    symbol: tab.symbol.trim(),
    side: tab.side,
    mode: tab.mode,
    price: formNumber(tab.price),
    quantity: formNumber(tab.quantity),
    price_source: tab.symbol ? 'ui:order-line' : 'unspecified',
    confirmed,
    // §۱-ج خودِ قرارداد: بی‌اینِ صریح هیچِ نگاشتِ کارگزاری ساخته نمی‌شود.
    // لینکِ UI فقطِ تیکِ همانِ تب را منتقل می‌کند وِ خود تصمیم نمی‌گیرد.
    ...(tab.mockInstrument ? { mock_instrument: true } : {}),
  };
}

/** کمینۀِ محلیِ فرم، پیش ازِ آنکه درِ صفِ سرویس بنشیند (بی‌ادعایِ داوریِ موتور) */
export function localGaps(tab: OrderTab): string[] {
  const out: string[] = [];
  if (!tab.symbol.trim()) out.push('نماد نوشته نشده');
  if (formNumber(tab.quantity) == null || (formNumber(tab.quantity) ?? 0) <= 0) out.push('تعدادِ معتبر نوشته نشده');
  if (formNumber(tab.price) == null || (formNumber(tab.price) ?? 0) <= 0) out.push('قیمتِ معتبر نوشته نشده');
  return out;
}

export async function tabPreflight(tab: OrderTab, deps: ActionDeps): Promise<PreflightResult | null> {
  const gaps = localGaps(tab);
  if (gaps.length) {
    deps.mark(tab.id, { phase: 'draft', checks: {}, reasons: {}, unknown: [], note: gaps.join(' · ') });
    return null;
  }
  if (!deps.beginSend(tab.id)) return null;
  try {
    const r = await runPreflight(draftBody(tab));
    deps.mark(tab.id, {
      phase: r.ok ? 'validated' : 'failed',
      checks: r.checks, reasons: r.reasons, unknown: r.unknown,
      note: r.ok ? null : (Object.values(r.reasons)[0] ?? 'پیش‌فرود رد شد'),
    });
    return r;
  } catch (e) {
    deps.mark(tab.id, { phase: 'draft', note: `پیش‌فرود نرسید: ${String((e as Error).message || e).slice(0, 90)}` });
    return null;
  } finally {
    deps.endSend(tab.id);
  }
}

export async function tabDispatch(tab: OrderTab, deps: ActionDeps): Promise<DispatchResult | null> {
  if (localGaps(tab).length) {
    deps.mark(tab.id, { phase: 'draft', note: localGaps(tab).join(' · ') });
    return null;
  }
  if (!deps.beginSend(tab.id)) return null;
  deps.mark(tab.id, { phase: 'sending', note: null });
  try {
    const r = await dispatchOrder(draftBody(tab, true));
    if (r.status === 'error') {
      const unknown = r.unknown_result === true;
      deps.mark(tab.id, {
        phase: unknown ? 'unknown_result' : 'failed',
        note: unknown
          ? 'نتیجهٔ نامعلوم: پاسخ نیامد وِ سفارش ممکن است رفته باشد — باِ همانِ شناسه مطابقت می‌شود.'
          : (r.detail ?? r.code ?? 'ارسال رد شد'),
        result: { code: r.code ?? null, detail: r.detail ?? null, checks: r.checks ?? {} },
      });
      return r;
    }
    deps.mark(tab.id, {
      phase: r.status === 'scheduled' ? 'scheduled' : ((r.record?.status as TabPhase) ?? 'dispatched'),
      result: { record: r.record ?? null, send_at_wall_ms: r.send_at_wall_ms ?? null,
                wait_ms: r.wait_ms ?? null, timings: r.timings ?? null, kill_switch: r.kill_switch ?? null },
      note: r.status === 'scheduled' ? 'زمان‌بندی شد؛ توقف‌پذیر است.' : null,
    });
    return r;
  } catch (e) {
    // خطایِ شبکه یعنی «نمی‌دانیم» -- نه «نرفت». شناسه ثابت می‌ماند.
    deps.mark(tab.id, {
      phase: 'unknown_result',
      note: `پاسخِ سرویس نرسید: ${String((e as Error).message || e).slice(0, 90)} — نتیجه نامعلوم است.`,
    });
    return null;
  } finally {
    deps.endSend(tab.id);
  }
}

export async function tabReconcile(tab: OrderTab, deps: ActionDeps): Promise<DispatchResult | null> {
  if (!deps.beginSend(tab.id)) return null;
  try {
    const r = await reconcileOrder(tab.executionId);
    deps.mark(tab.id, {
      phase: r.record?.status === 'reconciled' ? 'reconciled' : (r.status === 'error' ? 'failed' : 'dispatched'),
      result: { record: r.record ?? null, timings: r.timings ?? null },
      note: r.status === 'error' ? (r.detail ?? 'مطابقت نشد') : null,
    });
    return r;
  } catch (e) {
    deps.mark(tab.id, { note: `مطابقت نرسید: ${String((e as Error).message || e).slice(0, 90)}` });
    return null;
  } finally {
    deps.endSend(tab.id);
  }
}

/**
 * ارسالِ گروهی = چندِ درخواستِ مستقل، بی‌endpointِ گروهیِ ساختگی (بندِ ۱.۳).
 * هم‌زمانی ازِ `limits.max_orders` بیشتر نمی‌شود؛ هرِ تب نتیجهٔ خودش را
 * می‌گیرد وِ موفقیتِ یکی بهِ بقیهٔ نسبت داده نمی‌شود.
 */
export async function batchDispatch(
  tabs: OrderTab[],
  deps: ActionDeps,
  limits: LimitsView | null | undefined,
): Promise<{ attempted: number; concurrency: number; refused: string | null }> {
  const cap = Math.max(1, Math.floor(limits?.limits?.max_orders ?? 1));
  const queue = tabs.filter((t) => localGaps(t).length === 0);
  const concurrency = Math.min(cap, queue.length || 1);
  let attempted = 0;
  let refused: string | null = null;
  if (tabs.length > queue.length) {
    refused = `${tabs.length - queue.length} تب بی‌فرمِ کامل درِ صفِ گروهی ننشست.`;
  }
  // حلقۀِ کارگر: N تب، کمینۀِ `concurrency` درخواستِ هم‌زمانِ درِ حالِ انجام.
  // شمارنده را هرِ کارگر قبل ازِ await برمی‌دارد، پسِ دوِ کارگر یکِ تب را
  // برنمی‌دارند (تقسیمِ کار، نه پخشِ اتفاقی).
  let cursor = 0;
  const workers = Array.from({ length: concurrency }, async () => {
    for (;;) {
      const idx = cursor;
      cursor += 1;
      const t = queue[idx];
      if (!t) break;
      attempted += 1;
      await tabDispatch(t, deps);
    }
  });
  await Promise.all(workers);
  return { attempted, concurrency, refused };
}
