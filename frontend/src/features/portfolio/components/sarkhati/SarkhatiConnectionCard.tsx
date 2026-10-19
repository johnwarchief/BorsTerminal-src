// features/portfolio/components/sarkhati/SarkhatiConnectionCard.tsx — «اتصال» با
// سه چیزِ جدا: پنجرۀِ ورود، پرسشِ وضعیتِ نشست، و میزبان/روشِ احراز هویت
//
// خودِ ردیفِ کنش (`ConnectBrokerRow`) دست‌نخورده استفاده می‌شود تا «باز کردنِ
// پنجره» و «بررسی اتصال» همان دو درِ همیشگی باشند. این کارت فقط چیزی را که
// پاسخِ `/api/execution/connect` می‌گوید ولی درِ ردیفِ فشرده جا نمی‌شد را باز
// می‌کند: نقشِ هر مبدأ (ورود / رابطِ کاربری / API)، نشانیِ میزبانِ موردِ استفاده،
// و اینکه هیچ رازی ذخیره نشده است.
//
// دو ادعایی که اینجا هرگز نوشته نمی‌شود:
//  • «صفحۀ ورود باز شد» ≠ «نشست احراز شده» — اولی از `browser.open`، دومی فقط
//    از `last_verify.state` که پرسشِ واقعیِ کارگزاری است. این دو را درِ یک خطِ
//    رو‌به‌رو می‌گذارم تا تفاوتِش دیده شود، نه درِ دو پاراگرافِ جدا.
//  • «HTTP 200 ⇒ متصل» — نه؛ پاسخِ ۲۰۰ با بدنۀ HTML درِ بک‌اند `UNKNOWN_RESULT`
//    می‌شود و همان‌طور هم اینجا نمایش داده می‌شود.
//
// دورِ دومِ همین مأموریت (2026-10-18): «نشست تأیید نشده» بدونِ هیچ دری برای
// واردکردنِ نشانی، کاربر را درِ بن‌بست می‌گذاشت. فرمِ نشست (`SarkhatiSessionForm`)
// همان `POST/DELETE /api/execution/session` را باز می‌کند و چهار وضعیتِ خواستۀ
// مالک — تنظیمِ ذخیره‌شده، نشانیِ واردشده، تأییدِ واقعی، اجازهٔ ارسال — درِ چهار
// سطرِ جدا خوانده می‌شوند، نه درِ یک جمله.
import { ConnectBrokerRow } from '../ConnectBrokerRow';
import { SarkhatiConnectionSettings } from './SarkhatiConnectionSettings';
import { SarkhatiSessionForm } from './SarkhatiSessionForm';
import { toFaDigits } from '@shared/lib/fmt';
import { PORTFOLIO_LABEL, PORTFOLIO_STATES, TRAFFIC_LABEL, TRAFFIC_MODES,
  useBrokerConnect, useExecutionPortfolio, useExecutionStatus,
  type ConnectState, type PortfolioState, type TrafficMode }
  from '../../lib/orderClient';
import { Chip, Field, Line, Note, Section } from './parts';

const ROLE_LABEL: Record<string, string> = {
  auth: 'احراز هویت (OAuth/OIDC)',
  ui: 'رابطِ کاربری کارگزاری',
  api: 'آدرسِ API که سفارش به آن می‌رود',
};

export function SarkhatiConnectionCard() {
  const q = useBrokerConnect();
  const pf = useExecutionPortfolio();
  const { gate } = useExecutionStatus();
  const c = q.data;
  const last = (c?.last_verify ?? {}) as Record<string, unknown>;
  const browser = (c?.browser ?? {}) as Record<string, unknown>;
  const roles = ((c as unknown as Record<string, unknown> | undefined)?.host_roles
    ?? {}) as Record<string, unknown>;
  const evidence = String(roles.evidence ?? '');
  const state = String(last.state ?? 'UNKNOWN') as ConnectState;
  const blocked = String(c?.login_host_blocked_reason ?? '');
  const traffic = (TRAFFIC_MODES as readonly string[]).includes(String(c?.traffic_mode))
    ? String(c?.traffic_mode) as TrafficMode : 'blocked';
  const p = pf.data;
  const pfState = (PORTFOLIO_STATES as readonly string[]).includes(String(p?.status))
    ? String(p?.status) as PortfolioState : null;
  const pfRows = Array.isArray(p?.rows) ? (p?.rows?.length ?? null) : null;
  const pfAsOf = p?.as_of ?? p?.cached_at ?? null;
  const pfError = p?.error ?? (pf.isError ? 'پرسشِ پرتفوی خطا داد' : null);
  const verdict = state === 'CONNECTED' ? 'تأیید شده' : state === 'EXPIRED' ? 'منقضی'
    : state === 'DISCONNECTED' ? 'تأیید نشده' : 'نامعلوم';
  const verdictTone = state === 'CONNECTED' ? 'ok' : state === 'UNKNOWN' ? 'idle' : 'warn';
  // اعتبارنامه از `/api/execution/status` می‌آید و درِ `ExecutionStatusSchema`
  // محدود شده است؛ پس هر فیلدِ اضافی (رمز، نامِ کامل) پیش ازِ رسیدن به اینجا
  // افتاده می‌کند. «بی‌کلید» با «بی‌پاسخ» یکی نیست: نبودِ پاسخ ← «پاسخی نیامده».
  const cred = gate.status?.credential ?? null;
  const credCode = cred ? String(cred.code ?? '') : (gate.endpointPresent ? 'ABSENT' : '');
  const credText = !gate.endpointPresent ? 'پاسخی نیامده'
    : credCode === 'ABSENT' ? 'پاسخِ بی‌این بخش'
      : credCode === 'OK' ? `هست · ${String(cred?.user_masked || '—')}`
        : credCode === 'MISSING' ? 'نیست'
          : credCode === 'UNSUPPORTED' ? 'این سامانه پشتیبانی نمی‌کند'
            : credCode === 'DENIED' ? 'دسترسی رد شد'
              : credCode === 'MALFORMED' ? 'ساختارش خوانده نشد' : 'نامعلوم';
  const credHint = ['MISSING', 'MALFORMED', 'DENIED'].includes(credCode)
    ? String(cred?.hint || '') : '';

  return (
    <Section title="اتصالِ کارگزاری" testId="sarkhati-connection-card"
      sub="پنجرۀ ورود و نشستِ احراز شده دو چیزِ جدا"
      right={(
        <>
          {c?.secrets_stored === false ? (
            <Chip tone="ok" title="رمز، کوکی و نشانی درِ فایل، دیتابیس یا لاگ نوشته نمی‌شود">
              هیچ رازی ذخیره نشده
            </Chip>
          ) : null}
        </>
      )}>
      <ConnectBrokerRow />

      <div className="mt-2 flex flex-wrap items-baseline gap-x-4 gap-y-1 rounded-lg
        border border-border-c/50 bg-bg-primary/40 px-2 py-1"
        data-testid="sarkhati-window-vs-session">
        <Field label="پنجرۀ ورود" value={(
          <span data-testid="sarkhati-window-state"
            className={browser.open ? 'text-accent-blue' : 'text-text-secondary'}>
            {browser.open ? 'باز شده' : 'بسته'}
          </span>)} />
        <Field label="نشستِ احراز شده" value={(
          <Chip tone={verdictTone} testId="sarkhati-session-verdict">{verdict}</Chip>)} />
        <span className="text-2xs text-text-muted" title="دو ادعایِ جدا، نه یکِ ادعا">
          «پنجره باز شد» به‌تنهایی اتصال نیست
        </span>
      </div>

      {/* «راه» ازِ `/connect` است (ترافیکِ واقعیِ همین پروسه). ادعاهایِ نشست و
          تأیید به چهار سطرِ جدا رفته‌اند (`connectionLadder` درِ فرمِ نشست)، تا
          یکِ جملهٔ بلند جایِ چهار وضعیت را نگیرد. */}
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-4 gap-y-1"
           data-testid="sarkhati-traffic-and-proof">
        <Field label="راه" value={(
          <Chip tone={TRAFFIC_LABEL[traffic].tone} testId="sarkhati-traffic-mode">
            {TRAFFIC_LABEL[traffic].text}
          </Chip>)} />
        {/* اعتبارنامۀ محلی: پنجمین واقعیتِ جدا. «هست» هیچ‌وقت به معنی «وارد شدیم»
            نیست، و نامِ کاملِ کاربری هرگز نشان داده نمی‌شود. */}
        <Field label="اعتبارنامۀ ویندوز" value={(
          <span className="text-2xs" data-testid="sarkhati-credential-state"
                data-code={credCode || 'NONE'}
                title={cred?.target
                  ? `مخزن: ${cred.target} — رمز هیچ‌جا درِ این برنامه ذخیره نمی‌شود`
                  : 'مخزنِ اعتبارنامۀ ویندوز'}>
            {credText}
          </span>)} />
        {credHint ? (
          <span className="text-3xs text-accent-yellow" data-testid="sarkhati-credential-hint">
            {credHint}
          </span>
        ) : null}
      </div>

      <SarkhatiConnectionSettings />
      <SarkhatiSessionForm />

      {/* پرتفوی: «ردیفِ خالی» و «بی‌منبع» دو چیزند. عدد فقط ازِ پاسخ می‌آید. */}
      <div className="mt-1.5 flex flex-wrap items-baseline gap-x-4 gap-y-1"
           data-testid="sarkhati-portfolio-line">
        <Field label="پرتفویِ فقط‌خواندنی" value={(
          <span className="text-2xs text-text-secondary" data-testid="sarkhati-portfolio-status">
            {pfState ? PORTFOLIO_LABEL[pfState] : 'پاسخی نیامده'}
            {pfRows != null ? ` · ${toFaDigits(pfRows)} ردیف` : ''}
          </span>)} />
        {pfAsOf ? (
          <span className="num text-3xs text-text-muted" data-testid="sarkhati-portfolio-asof"
                dir="ltr">
            {String(pfAsOf)}
          </span>
        ) : null}
        {pfError ? (
          <span className="text-3xs text-accent-yellow" data-testid="sarkhati-portfolio-error">
            {pfError}
          </span>
        ) : null}
      </div>

      <div className="mt-1.5 flex flex-col gap-0.5" data-testid="sarkhati-host-roles">
        {Object.keys(ROLE_LABEL).map((role) => {
          const list = Array.isArray(roles[role]) ? (roles[role] as string[]) : [];
          return (
            <div key={role} data-testid={`sarkhati-role-${role}`}>
              <Field wide label={ROLE_LABEL[role]} value={(
                list.length
                  ? <span className="num font-bold text-text-primary" dir="ltr">{list.join('، ')}</span>
                  : <span className="text-accent-yellow">تنظیم نشده — بی‌تنظیمِ صریح هیچ نشانی‌ای باز نمی‌شود</span>
              )} />
              {role === 'api' && evidence ? (
                <Line kind="warn" >
                  <span title={evidence}>
                    منشأِ API: سندِ رسمی منتشر نشده (۴۰۳) — سیم هنوز فرضیۀ مهندسی معکوس
                  </span>
                </Line>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="mt-1.5 text-2xs leading-4 text-text-muted" data-testid="sarkhati-last-check">
        آخرینِ بررسی: {String(last.checked_at ?? '—')}
        {last.reason ? ` · ${String(last.reason)}` : ''}
        {blocked ? (
          <span className="text-accent-yellow" data-testid="sarkhati-connect-blocked">
            {' '}· {blocked}
          </span>
        ) : null}
      </p>

      <div className="mt-1">
        <Note label="معنای خطاهایِ اتصال" testId="sarkhati-error-legend">
          <ul className="flex flex-col gap-0.5">
            <li>۴۰۱ — اجازۀ دسترسی داده نشد: نشست نیست یا منقضی شده. «رفعِ ابهام» می‌شود، ارسالِ دوباره نه.</li>
            <li>۴۰۳ — اجازۀ دسترسی رد شد: میزبان یا مسیر درِ allowlist تنظیم‌شده نیست.</li>
            <li>timeout — پاسخی نیامد؛ نتیجه نامعلوم می‌ماند و هیچ تلاشِ تازه‌ای نمی‌شود.</li>
            <li>پاسخِ نامعتبر (مثلاً HTML در جایِ JSON) — «اتصال تأیید نشد»، نه خطایِ صفحه.</li>
          </ul>
        </Note>
      </div>

      {q.isError ? (
        <Line kind="error">
          درِ اتصال پاسخی نداد — با «بررسی اتصال» دوباره بسنجید؛ تا پاسخ نیامده
          نشست تأیید نشده می‌ماند و هیچ سفارشی باز نمی‌شود.
        </Line>
      ) : null}
    </Section>
  );
}
