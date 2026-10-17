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
//    از `last_verify.state` که پرسشِ واقعیِ کارگزاری است.
//  • «HTTP 200 ⇒ متصل» — نه؛ پاسخِ ۲۰۰ با بدنۀ HTML درِ بک‌اند `UNKNOWN_RESULT`
//    می‌شود و همان‌طور هم اینجا نمایش داده می‌شود.
import { Badge } from '@shared/components/Badge';
import { ConnectBrokerRow } from '../ConnectBrokerRow';
import { useBrokerConnect, type ConnectState } from '../../lib/orderClient';

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

  return (
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-connection-card">
      <div className="flex flex-wrap items-center gap-1.5">
        <h4 className="text-2xs font-black text-text-secondary">اتصالِ کارگزاری</h4>
        {q.isError ? <Badge tone="red">پاسخی از درِ اتصال نرسید</Badge> : null}
        {c?.secrets_stored === false ? (
          <Badge tone="green" title="رمز، کوکی و نشانی درِ فایل، دیتابیس یا لاگ نوشته نمی‌شود">
            هیچ رازی ذخیره نشده
          </Badge>
        ) : null}
      </div>

      <ConnectBrokerRow />

      <div className="flex flex-wrap items-baseline gap-1.5 text-3xs"
        data-testid="sarkhati-window-vs-session">
        <span className="text-text-muted">پنجرۀ ورود:</span>
        <span className={browser.open ? 'font-bold text-accent-blue' : 'text-text-secondary'}
          data-testid="sarkhati-window-state">
          {browser.open ? 'باز شده' : 'بسته'}
        </span>
        <span className="text-text-muted">·</span>
        <span className="text-text-muted">نشستِ احراز شده:</span>
        <span data-testid="sarkhati-session-verdict"
          className={state === 'CONNECTED' ? 'font-bold text-accent-green' : 'font-bold text-accent-yellow'}>
          {state === 'CONNECTED' ? 'تأیید شده' : state === 'EXPIRED' ? 'منقضی'
            : state === 'DISCONNECTED' ? 'تأیید نشده' : 'نامعلوم'}
        </span>
        <span className="text-text-muted" title="دو ادعایِ جدا، نه یکِ ادعا">
          — «پنجره باز شد» به‌تنهایی اتصال نیست
        </span>
      </div>

      <div className="flex flex-col gap-0.5 text-3xs" data-testid="sarkhati-host-roles">
        {Object.keys(ROLE_LABEL).map((role) => {
          const list = Array.isArray(roles[role]) ? (roles[role] as string[]) : [];
          return (
            <div key={role} className="flex flex-wrap items-baseline gap-1.5"
              data-testid={`sarkhati-role-${role}`}>
              <span className="text-text-muted">{ROLE_LABEL[role]}:</span>
              {list.length ? (
                <span className="num font-bold text-text-primary" dir="ltr">{list.join('، ')}</span>
              ) : (
                <span className="text-accent-yellow">تنظیم نشده — بی‌تنظیمِ صریح هیچ نشانی‌ای باز نمی‌شود</span>
              )}
              {role === 'api' && evidence ? (
                <span className="text-accent-yellow" title={evidence}>
                  منشأِ API: سندِ رسمی منتشر نشده (۴۰۳) — سیم هنوز فرضیۀ مهندسی معکوس
                </span>
              ) : null}
            </div>
          );
        })}
      </div>

      <p className="text-3xs leading-4 text-text-muted" data-testid="sarkhati-last-check">
        آخرینِ بررسی: {String(last.checked_at ?? '—')}
        {last.reason ? ` · ${String(last.reason)}` : ''}
        {blocked ? (
          <span className="text-accent-yellow" data-testid="sarkhati-connect-blocked">
            {' '}· {blocked}
          </span>
        ) : null}
      </p>

      <details className="text-3xs text-text-muted" data-testid="sarkhati-error-legend">
        <summary className="cursor-pointer text-accent-blue">معنای خطاهایِ اتصال</summary>
        <ul className="mt-1 flex flex-col gap-0.5">
          <li>۴۰۱ — اجازۀ دسترسی داده نشد: نشست نیست یا منقضی شده. «رفعِ ابهام» می‌شود، ارسالِ دوباره نه.</li>
          <li>۴۰۳ — اجازۀ دسترسی رد شد: میزبان یا مسیر درِ allowlist تنظیم‌شده نیست.</li>
          <li>timeout — پاسخی نیامد؛ نتیجه نامعلوم می‌ماند و هیچ تلاشِ تازه‌ای نمی‌شود.</li>
          <li>پاسخِ نامعتبر (مثلاً HTML در جایِ JSON) — «اتصال تأیید نشد»، نه خطایِ صفحه.</li>
        </ul>
      </details>
    </div>
  );
}
