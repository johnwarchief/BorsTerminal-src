// features/portfolio/components/sarkhati/SarkhatiRiskCard.tsx — گیت‌ها، همان‌طور
// که سرویس اعلام می‌کند
//
// این کارت هیچ داوریِ تازه‌ای نمی‌کند: سقف‌ها از `/api/execution/limits`، توانایی‌ها
// و دروازۀِ عبارت از `/api/execution/status` خوانده می‌شوند. دو قاعدۀِ نمایش که
// درِ این برنامه قانونِ عمومی است:
//  • `None` یعنی «این سقف تعریف نشده» (گیت خاموش)، نه «صفر». صفرِ نمایشی درِ
//    ریسک یعنی کاربر باور کند جایی بسته شده که بسته نشده است.
//  • نبودِ capability یعنی «این کار را نمی‌توانیم بکنیم» — پس درِ «اثبات‌نشده»
//    نوشته می‌شود، نه درِ «آماده».
//
// کنشِ «توقف/ادامه» درِ کارتِ سفارش می‌ماند (تکِ صاحبِ عمل)؛ اینجا فقط وضعیتش
// خوانده می‌شود.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { BrokerCapabilities, ExecutionStatus } from '../../lib/orderClient';

const CAP_LABEL: Record<string, string> = {
  place: 'ساختنِ سفارش',
  list_orders: 'فهرستِ سفارش‌ها (رفعِ ابهام)',
  order_state: 'وضعیتِ سفارش (بازخوانی)',
  queue_position: 'جایِ صف',
  cancel: 'لغوِ سفارش',
  best_bid_ask: 'دو قیمتِ اول',
  balances: 'موجودیِ نقدِ کارگزاری',
};

const LIMIT_LABEL: Record<string, string> = {
  max_orders: 'حداکثرِ سفارش‌هایِ هم‌زمان',
  max_total_value: 'ارزشِ کلِ مجاز',
  max_total_quantity: 'حجمِ کلِ مجاز',
  max_order_value: 'حداکثرِ ارزشِ هر سفارش',
  max_symbol_exposure: 'سقفِ exposure هر نماد',
  max_total_exposure: 'سقفِ exposure کلِ پرتفو',
  max_daily_loss: 'ضررِ روزانۀِ توقفِ خودکار',
  max_orders_per_window: 'سقفِ سفارش درِ پنجره (هر نماد)',
  max_total_orders_per_window: 'سقفِ جمعِ سفارش درِ پنجره',
  window_seconds: 'طولِ پنجرۀِ نرخ (ثانیه)',
  max_data_age_s: 'حداکثرِ کهنگیِ داده (ثانیه)',
};

const not = (v: unknown) => v == null;

export function SarkhatiRiskCard({ status }: { status: ExecutionStatus | null }) {
  const limits = (status?.limits ?? {}) as Record<string, number | boolean | null | undefined>;
  const caps = (status?.capabilities ?? {}) as BrokerCapabilities;
  const cgate = (status?.confirm_gate ?? {}) as { required?: boolean; phrase?: string };
  const provenance = (status?.wire_provenance ?? {}) as
    Record<string, { value?: unknown; kind?: string; hypothesis?: boolean;
      official_docs?: string; proves_session?: boolean; body_semantics?: string;
      observed?: string }>;
  const halted = status?.halted === true;
  const tripped = status?.kill_switch === 'TRIPPED';

  return (
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-risk-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">ریسک و ایمنی</h4>
        <Badge tone={halted ? (tripped ? 'orange' : 'red') : 'green'}
          title={tripped ? 'توقفِ خودکارِ ریسک — بی‌confirm=True باز نمی‌شود' : undefined}>
          {halted ? (tripped ? 'توقفِ خودکارِ ریسک' : 'توقفِ دستوری') : 'بدونِ توقف'}
        </Badge>
        <span className="text-3xs text-text-muted" data-testid="sarkhati-kill-reason">
          {status?.kill_reason ? `علت: ${String(status.kill_reason)}` : 'علتی ثبت نشده'}
        </span>
      </div>

      <ul className="flex flex-col gap-0.5 text-3xs leading-4" data-testid="sarkhati-gates">
        <li>
          <span className="font-bold text-text-primary">پیش‌فرود</span> — پیش ازِ هر
          عملِ حساس؛ نتیجه‌اش درِ کارتِ سفارش است، و نبودِ پاسخ = عبور نیست.
        </li>
        <li>
          <span className="font-bold text-text-primary">عبارتِ تأیید</span> —{' '}
          {cgate.required === true
            ? `الزامی است و درِ بک‌اند سنجیده می‌شود («${String(cgate.phrase ?? '')}»)`
            : 'فعلاً لازم نیست، چون اجرایِ زنده خاموش است'}
          {' '}· دورۀِ تأیید: <span className="num">{toFaDigits(String(status?.confirm_epoch ?? 0))}</span>
          — با هر نشست/tokenِ تازه، تأییدهایِ قبلی بی‌اعتبار می‌شوند.
        </li>
        <li>
          <span className="font-bold text-text-primary">شناسۀِ اجرا</span> — هر تلاشِ تازه
          شناسۀِ تازه می‌گیرد؛ ردِّپایِ dispatch رویِ دیسک، «دو بار فرستادنِ همان سفارش» را
          می‌گیرد (DUPLICATE_GUARD).
        </li>
        <li>
          <span className="font-bold text-text-primary">توقفِ اضطراری</span> — رویِ دیسک
          می‌ماند و زمان‌بندی‌هایِ درِ انتظار را همان لحظه لغو می‌کند؛ دکمه‌اش درِ کارتِ سفارش است.
        </li>
        <li>
          <span className="font-bold text-text-primary">سرریزِ امن</span> — بی‌پیکربندیِ
          معتبر یا وضعیتی مبهم، اقدامِ تازه ساخته نمی‌شود (نه دورزدنِ گیت).
        </li>
      </ul>

      <div className="grid gap-x-3 gap-y-0.5 text-3xs sm:grid-cols-2"
        data-testid="sarkhati-limits">
        <span className="text-2xs font-bold text-text-secondary sm:col-span-2">سقف‌هایِ تنظیم‌شده</span>
        {Object.entries(LIMIT_LABEL).map(([key, label]) => {
          const v = limits[key];
          return (
            <span key={key} className="flex flex-wrap items-baseline gap-1"
              data-testid={`sarkhati-limit-${key}`}>
              <span className="text-text-muted">{label}:</span>
              <span className={`num font-bold ${not(v) ? 'text-accent-yellow' : 'text-text-primary'}`}>
                {not(v) ? 'تعریف‌نشده (گیت خاموش)'
                  : typeof v === 'boolean' ? (v ? 'بله' : 'خیر')
                    : toFaDigits(String(v))}
              </span>
            </span>
          );
        })}
        <span className="flex flex-wrap items-baseline gap-1 sm:col-span-2"
          data-testid="sarkhati-limit-confirm">
          <span className="text-text-muted">تأییدِ صریح لازم است:</span>
          <span className="num font-bold text-text-primary">
            {limits.require_confirmation === true ? 'بله' : 'در پاسخِ سرویس نیامد'}
          </span>
        </span>
      </div>

      <div className="flex flex-col gap-0.5 text-3xs" data-testid="sarkhati-caps">
        <span className="text-2xs font-bold text-text-secondary">توانایی‌هایِ اعلامیِ اتصال</span>
        <div className="flex flex-wrap gap-1">
          {Object.entries(CAP_LABEL).map(([key, label]) => (
            <Badge key={key} tone={caps[key as keyof BrokerCapabilities] === true ? 'green' : 'red'}
              title={caps[key as keyof BrokerCapabilities] === true ? 'اعلام شده' : 'اعلام نشده — بی‌داده، نه صفر'}>
              {label}: {caps[key as keyof BrokerCapabilities] === true ? '✓' : '✕'}
            </Badge>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-0.5 text-3xs" data-testid="sarkhati-unproven">
        <span className="text-2xs font-bold text-text-secondary">چیزی که هنوز اثبات نشده</span>
        {Object.entries(provenance).map(([key, p]) => (
          <span key={key} className="flex flex-wrap items-baseline gap-1.5"
            data-testid={`sarkhati-prov-${key}`}>
            <span className="num font-bold text-text-primary">{key}</span>
            <span className="text-text-muted">{String(p.kind ?? '—')}</span>
            {p.official_docs ? <span className="text-accent-yellow">سندِ رسمی: {String(p.official_docs)}</span> : null}
            {p.hypothesis === true ? <span className="text-accent-yellow">فرضیه</span> : null}
            {p.proves_session === false ? <span className="text-text-muted">نشست را ثابت نمی‌کند</span> : null}
            {p.body_semantics === 'unverified' ? <span className="text-accent-yellow">معنایِ بدنۀ پاسخ تأیید نشده</span> : null}
            {p.observed ? <span className="text-text-muted" title="مشاهدهٔ فقط‌خواندنی">دیده‌شدن: {String(p.observed)}</span> : null}
          </span>
        ))}
        <span className="text-text-muted" data-testid="sarkhati-unproven-clock">
          زمانِ سرورِ کارگزاری: NOT_PROVEN · رتبۀِ صفِ رسمی: NOT_PROVEN · هر عددِ
          «چقدر نزدیک به هدف» فقط باِ همین دو منبع قابلِ ادعا است.
        </span>
      </div>
    </div>
  );
}
