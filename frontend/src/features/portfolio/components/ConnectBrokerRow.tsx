// features/portfolio/components/ConnectBrokerRow.tsx -- «اتصال به EasyTrader»
//
// یک خط پاسخ + چیپِ حالت + سه کنش، و جزئیات درِ <details> (قاعدۀ ارتفاعِ فشرده).
// سه چیزی که این مؤلفه *ادعا نمی‌کند*:
//  • «متصل» شدن با دیدنِ صفحۀ ورود — حالت فقط از `POST /connect/verify` می‌آید
//    که پرسشِ واقعیِ کارگزاری است؛
//  • نگه‌داشتنِ رمز/کوکی — پنجره با پروفایلِ موقت باز می‌شود و موقع بستن پاک
//    می‌شود، و نشانی فقط درِ حافظۀ بک‌اند می‌نشیند (فیلدِ موجودِ همین پنل)؛
//  • باز کردنِ هر نشانیِ دلخواه — میزبان باید درِ `BORS_EXECUTION_CONNECT_HOSTS`
//    باشد؛ بی‌آن پیامِ BLOCKED با علت نشان داده می‌شود و دکمه بی‌عمل نمی‌ماند.
import { useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { Badge } from '@shared/components/Badge';
import { connectApi, CONNECT_LABEL, useBrokerConnect, type ConnectState } from '../lib/orderClient';

const TONE: Record<ConnectState, 'green' | 'red' | 'yellow' | 'gray'> = {
  CONNECTED: 'green', DISCONNECTED: 'red', EXPIRED: 'yellow', UNKNOWN: 'gray',
};
const isState = (s: unknown): s is ConnectState =>
  s === 'CONNECTED' || s === 'DISCONNECTED' || s === 'EXPIRED' || s === 'UNKNOWN';

export function ConnectBrokerRow() {
  const q = useBrokerConnect();
  const [busy, setBusy] = useState<'' | 'open' | 'verify' | 'close' | 'cut'>('');
  const [note, setNote] = useState('');
  const c = q.data;
  const last = (c?.last_verify ?? {}) as Record<string, unknown>;
  const raw = last.state;
  const state: ConnectState = isState(raw) ? raw : 'UNKNOWN';
  const browser = (c?.browser ?? {}) as Record<string, unknown>;
  const blocked = String(c?.login_host_blocked_reason ?? '');

  const act = async (kind: 'open' | 'verify' | 'close' | 'cut') => {
    setBusy(kind); setNote('');
    try {
      const r = kind === 'open' ? await connectApi.openBrowser()
        : kind === 'verify' ? await connectApi.verify()
          : kind === 'close' ? await connectApi.closeBrowser()
            : await connectApi.disconnect();
      const detail = (r as Record<string, unknown>).detail ?? (r as Record<string, unknown>).note;
      setNote(String(detail ?? ''));
      await q.refetch();
    } catch (e) {
      setNote(e instanceof Error ? e.message.slice(0, 140) : 'خطای نامعلوم');
    } finally {
      setBusy('');
    }
  };

  const btn = 'min-h-[36px] rounded-lg border border-border-c bg-bg-card px-2 text-2xs '
    + 'font-bold text-text-secondary disabled:opacity-40';
  return (
    <div className="flex flex-col gap-1" data-testid="connect-broker-row">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={TONE[state]}>{CONNECT_LABEL[state]}</Badge>
        <button type="button" className={btn} onClick={() => act('open')}
                disabled={busy !== ''} data-testid="connect-open-browser">
          اتصال به EasyTrader
        </button>
        <button type="button" className={btn} onClick={() => act('verify')}
                disabled={busy !== ''} data-testid="connect-verify">
          بررسی اتصال
        </button>
        <button type="button" className={btn} onClick={() => act('close')}
                disabled={busy !== '' || !browser.open} data-testid="connect-close-browser">
          بستن پنجره
        </button>
        <button type="button" className={btn} onClick={() => act('cut')}
                disabled={busy !== ''} data-testid="connect-disconnect">
          قطع اتصال
        </button>
        <details className="text-3xs text-text-muted" data-testid="connect-details">
          <summary>جزئیات نشست</summary>
          <p>{String(last.reason ?? 'پرسشی انجام نشده')}</p>
          {/* تازگیِ ادعا بخشی ازِ خودِ ادعا است: «متصل» بی‌پرسشِ تازه، متصل نیست. */}
          <p data-testid="connect-verify-age">
            {last.age_s == null
              ? 'پرسشِ اتصالِ زمان‌دار ثبت نشده'
              : `پرسشِ اتصال: ${toFaDigits(Math.max(0, Math.round(Number(last.age_s) / 60)))} دقیقه پیش`
                + (last.stale ? ' — کهنه' : '')}
          </p>
          {blocked ? <p className="text-accent-yellow" data-testid="connect-blocked">{blocked}</p> : null}
          <p>پنجره: {browser.open ? 'باز' : 'بسته'} · پروفایل موقت: {browser.profile_kept ? 'نگه داشته' : 'پاک می‌شود'}</p>
          <p>دامنه‌های ورود: {((c?.login_hosts_configured ?? []) as string[]).join('، ') || '—'}</p>
          {note ? <p>{note}</p> : null}
        </details>
      </div>
    </div>
  );
}
