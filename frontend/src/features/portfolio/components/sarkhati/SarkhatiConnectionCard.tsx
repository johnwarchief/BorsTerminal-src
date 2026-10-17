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
import { ConnectBrokerRow } from '../ConnectBrokerRow';
import { useBrokerConnect, type ConnectState } from '../../lib/orderClient';
import { Chip, Field, Line, Note, Section } from './parts';

const ROLE_LABEL: Record<string, string> = {
  auth: 'احراز هویت (OAuth/OIDC)',
  ui: 'رابطِ کاربری کارگزاری',
  api: 'آدرسِ API که سفارش به آن می‌رود',
};

export function SarkhatiConnectionCard() {
  const q = useBrokerConnect();
  const c = q.data;
  const last = (c?.last_verify ?? {}) as Record<string, unknown>;
  const browser = (c?.browser ?? {}) as Record<string, unknown>;
  const roles = ((c as unknown as Record<string, unknown> | undefined)?.host_roles
    ?? {}) as Record<string, unknown>;
  const evidence = String(roles.evidence ?? '');
  const state = String(last.state ?? 'UNKNOWN') as ConnectState;
  const blocked = String(c?.login_host_blocked_reason ?? '');
  const verdict = state === 'CONNECTED' ? 'تأیید شده' : state === 'EXPIRED' ? 'منقضی'
    : state === 'DISCONNECTED' ? 'تأیید نشده' : 'نامعلوم';
  const verdictTone = state === 'CONNECTED' ? 'ok' : state === 'UNKNOWN' ? 'idle' : 'warn';

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
