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
// کنشِ «توقف/ادامه» درِ بخشِ سفارش می‌ماند (تکِ صاحبِ عمل)؛ اینجا فقط وضعیتش
// خوانده می‌شود.
import { CheckIcon, XIcon } from '@shared/components/Icons';
import { toFaDigits } from '@shared/lib/fmt';
import type { BrokerCapabilities, ExecutionStatus } from '../../lib/orderClient';
import { Chip, Field, Line, Section, Table, Td, Tr } from './parts';

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
  const provenance = Object.entries((status?.wire_provenance ?? {}) as
    Record<string, { value?: unknown; kind?: string; hypothesis?: boolean;
      official_docs?: string; proves_session?: boolean; body_semantics?: string;
      observed?: string }>);
  const halted = status?.halted === true;
  const tripped = status?.kill_switch === 'TRIPPED';

  return (
    <div className="flex flex-col gap-2" data-testid="sarkhati-risk-card">
      <Section title="گیت‌هایِ اجرا" testId="sarkhati-gates"
        tone={halted ? 'alarm' : 'default'}
        right={(
          <>
            <Chip tone={halted ? (tripped ? 'warn' : 'bad') : 'ok'}
              title={tripped ? 'توقفِ خودکارِ ریسک — بی‌confirm=True باز نمی‌شود' : undefined}>
              {halted ? (tripped ? 'توقفِ خودکارِ ریسک' : 'توقفِ دستوری') : 'بدونِ توقف'}
            </Chip>
            <span className="text-2xs text-text-muted" data-testid="sarkhati-kill-reason">
              {status?.kill_reason ? `علت: ${String(status.kill_reason)}` : 'علتی ثبت نشده'}
            </span>
          </>
        )}>
        <dl className="grid gap-x-4 gap-y-1 sm:grid-cols-2">
          <Gate name="پیش‌فرود" body="پیش ازِ هر عملِ حساس؛ نتیجه‌اش درِ بخشِ سفارش است. نبودِ پاسخ = عبور نیست." />
          <Gate name="عبارتِ تأیید" body={cgate.required === true
            ? `الزامی است و درِ بک‌اند سنجیده می‌شود («${String(cgate.phrase ?? '')}») — با هر نشست/tokenِ تازه، تأییدهایِ قبلی بی‌اعتبار می‌شوند.`
            : 'فعلاً لازم نیست، چون اجرایِ زنده خاموش است.'}
            extra={`دورۀِ تأیید: ${toFaDigits(String(status?.confirm_epoch ?? 0))}`} />
          <Gate name="شناسۀِ اجرا" body="هر تلاشِ تازه شناسۀِ تازه می‌گیرد؛ ردِّپایِ dispatch رویِ دیسک «دو بار فرستادنِ همان سفارش» را می‌گیرد (DUPLICATE_GUARD)." />
          <Gate name="توقفِ اضطراری" body="رویِ دیسک می‌ماند و زمان‌بندی‌هایِ درِ انتظار را همان لحظه لغو می‌کند؛ دکمه‌اش درِ بخشِ سفارش است." />
          <Gate name="سرریزِ امن" body="بی‌پیکربندیِ معتبر یا وضعیتی مبهم، اقدامِ تازه ساخته نمی‌شود — نه دورزدنِ گیت." />
        </dl>
      </Section>

      {/* اندازه‌گیریِ ۱۳۶۶×۷۶۸ (_test_runs/sk_shot_probe.py): کنارِ هم گذاشتنِ این
          دو بخش ارتفاعِ کارت را ۶۴۲ ← ۶۹۸ برد — درِ ستونِ ۴۷۰پیکسلی مقدارها
          می‌شکنند و سطرها زیاد می‌شود. پس تک‌ستونی می‌ماند. */}
      <Section title="توانایی‌هایِ اعلامیِ اتصال" testId="sarkhati-caps"
        sub="اعلام‌نشده یعنی «نمی‌توانیم بکنیم»، نه صفر">
        <div className="flex flex-wrap gap-1">
          {Object.entries(CAP_LABEL).map(([key, label]) => {
            const on = caps[key as keyof BrokerCapabilities] === true;
            return (
              <Chip key={key} tone={on ? 'ok' : 'bad'}
                title={on ? 'اعلام شده' : 'اعلام نشده — بی‌داده، نه صفر'}>
                {on ? <CheckIcon size={11} /> : <XIcon size={11} />}
                {label}
              </Chip>
            );
          })}
        </div>
      </Section>

      <details className="rounded-xl border border-border-c/50 bg-bg-card/20 px-2 py-1"
        data-testid="sarkhati-risk-details">
        <summary className="cursor-pointer text-2xs font-bold text-accent-blue">
          سقف‌های ریسک و شواهد فنی (بازکردن)
        </summary>
      <Section title="سقف‌هایِ تنظیم‌شده" testId="sarkhati-limits"
        sub="از /api/execution/limits، بی‌عددِ ساختگی">
        <div className="grid gap-x-4 gap-y-0.5 sm:grid-cols-2 lg:grid-cols-3">
          {Object.entries(LIMIT_LABEL).map(([key, label]) => {
            const v = limits[key];
            return (
              <div key={key} data-testid={`sarkhati-limit-${key}`}>
                <Field label={label} value={(
                  <span className={not(v) ? 'text-accent-yellow' : ''}>
                    {not(v) ? 'تعریف‌نشده (گیت خاموش)'
                      : typeof v === 'boolean' ? (v ? 'بله' : 'خیر')
                        : toFaDigits(String(v))}
                  </span>
                )} />
              </div>
            );
          })}
          <div data-testid="sarkhati-limit-confirm">
            <Field label="تأییدِ صریح لازم است" value={(
              <span>{limits.require_confirmation === true ? 'بله' : 'در پاسخِ سرویس نیامد'}</span>
            )} />
          </div>
        </div>
      </Section>

      <Section title="چیزی که هنوز اثبات نشده" testId="sarkhati-unproven"
        sub="هر ادعایِ «چقدر نزدیک به هدف» فقط با همین دو منبع قابلِ ادعا است"
        tone="quiet">
        {provenance.length ? (
          <Table testId="sarkhati-prov-rows" minWidth={560}
            head={['ماده', 'منشأ', 'سندِ رسمی', 'ثبتِ نشست', 'معنایِ بدنۀ پاسخ', 'مشاهده']}>
            {provenance.map(([key, p]) => (
              <Tr key={key} testId={`sarkhati-prov-${key}`}>
                <Td num strong>{key}</Td>
                <Td>
                  <span className="text-text-secondary">{String(p.kind ?? '—')}</span>
                  {p.hypothesis === true ? <Chip tone="warn" title="سیم از مهندسی معکوسِ منابعِ عمومی است">فرضیه</Chip> : null}
                </Td>
                <Td tone={p.official_docs ? 'warn' : 'muted'}>
                  {p.official_docs ? `سندِ رسمی: ${String(p.official_docs)}` : '—'}
                </Td>
                <Td tone={p.proves_session === false ? 'warn' : 'muted'}>
                  {p.proves_session == null ? '—' : (p.proves_session ? 'بله' : 'خیر')}
                </Td>
                <Td tone={p.body_semantics === 'unverified' ? 'warn' : 'muted'}>
                  {p.body_semantics === 'unverified' ? 'تأیید نشده' : (p.body_semantics ? String(p.body_semantics) : '—')}
                </Td>
                <Td tone="muted">{p.observed ? String(p.observed) : '—'}</Td>
              </Tr>
            ))}
          </Table>
        ) : (
          <Line testId="sarkhati-prov-none">
            سرویس درِ این پاسخ هیچ مادۀِ منشأدارِ «اثبات‌نشده» اعلام نکرده است — این
            یعنی «معلوم نیست»، نه یعنی «همه‌چیز تأیید شده».
          </Line>
        )}
        <Line kind="warn" testId="sarkhati-unproven-clock">
          زمانِ سرورِ کارگزاری: NOT_PROVEN · رتبۀِ صفِ رسمی: NOT_PROVEN
        </Line>
      </Section>
      </details>
    </div>
  );
}

function Gate({ name, body, extra }: { name: string; body: string; extra?: string }) {
  return (
    <div className="min-w-0">
      <dt className="text-2xs font-black text-text-primary">{name}</dt>
      <dd className="text-2xs leading-4 text-text-secondary">
        {body}
        {extra ? <span className="text-text-muted"> · {extra}</span> : null}
      </dd>
    </div>
  );
}
