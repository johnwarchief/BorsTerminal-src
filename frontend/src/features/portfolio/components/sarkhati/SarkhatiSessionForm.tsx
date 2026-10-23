// features/portfolio/components/sarkhati/SarkhatiSessionForm.tsx — نشانیِ نشست و
// چهار وضعیتی که هیچ‌کدام جایِ دیگری را نمی‌گیرد
//
// چرا این فرم لازم بود: بک‌اند نشانی را فقط ازِ `POST /api/execution/session`
// می‌گیرد و همان درِ `/portfolio` صریح «کمبودِ اصلی» را همان نشانی می‌داند، ولی
// درِ کارتِ اتصالِ تبِّ سرخطی هیچ دری برایش نبود — کاربر «نشست تأیید نشده»
// می‌دید و جایی برای واردکردنش نداشت. فرمِ پنلِ معامله (`exec-token-input`) سرِ
// راهِ همان در است؛ این مؤلفه همان قرارداد را درِ همان کارت می‌آورد، نه یک
// قراردادِ دوم.
//
// چهار چیزی که این مؤلفه *نمی‌کند*:
//  • نشانی را نمایش/بازگردانی/لاگ نمی‌کند: `type=password`، و مقدار پیشِ هر
//    پرسش ازِ state می‌رود تا هیچ رندرِ تازه‌ای او را نبیند. پاسخِ بک‌اند هم
//    هیچ‌وقت مقدار را برنمی‌گرداند.
//  • «ثبت شد» را «تأیید شد» نمی‌خواند: چهار وضعیت ازِ چهار فیلدِ جدا می‌آیند
//    (`connectionLadder`) و هیچ دکمه‌ای اینجا تأیید نمی‌سازد.
//  • گیتِ نوشتن را باز نمی‌کند: دو پرسشِ این فایل فقط نشانی را می‌گذارند یا
//    برمی‌دارند؛ تنظیمِ ذخیره‌شده هم هرگز `live_enabled` را روشن نمی‌کند.
//  • نشانیِ خالی را نمی‌فرستد: «چیزی ننوشتی» پیامِ خودِ رابط است، نه خطایِ سرور.
import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import { messageOf, orderApi, useBrokerConfig, useExecutionStatus } from '../../lib/orderClient';
import { connectionLadder } from '../../lib/sarkhatiFlow';
import { Chip, GhostBtn, Note } from './parts';

/** `confirmations_voided` درِ قرارداد *شمارش* است، نه بُولین (سنجشِ زندۀ
 *  `/api/execution/session`: `0`). بی‌این، سطرِ بی‌اعتبارشدن هرگز اجرا نمی‌شد. */
function voidedNote(n: unknown): string {
  const c = Number(n ?? 0);
  return Number.isFinite(c) && c > 0 ? ` · ${toFaDigits(c)} تأییدِ پیشین بی‌اعتبار شد` : '';
}

export function SarkhatiSessionForm() {
  const st = useExecutionStatus();
  const cfg = useBrokerConfig();
  const qc = useQueryClient();
  const [token, setToken] = useState('');
  const [busy, setBusy] = useState<'' | 'set' | 'clear'>('');
  const [note, setNote] = useState('');
  const [tone, setTone] = useState<'ok' | 'bad'>('bad');

  const blank = token.trim() === '';
  const ladder = connectionLadder({ cfg: cfg.data, st: st.data });

  const fresh = () => {
    qc.invalidateQueries({ queryKey: ['execution-status'] });
    qc.invalidateQueries({ queryKey: ['execution-connect'] });
  };

  const act = async (kind: 'set' | 'clear') => {
    if (kind === 'set' && blank) return;
    setBusy(kind); setNote('');
    const value = kind === 'set' ? token : '';
    setToken('');
    try {
      const r = kind === 'set' ? await orderApi.putSession(value) : await orderApi.delSession();
      const ok = String((r as Record<string, unknown>).status ?? '') === 'success';
      const detail = String((r as Record<string, unknown>).detail ?? '');
      const voided = voidedNote((r as Record<string, unknown>).confirmations_voided);
      setTone(ok ? 'ok' : 'bad');
      setNote((ok ? (detail || (kind === 'set'
        ? 'نشست ثبت شد — تأییدِ واقعی فقط با «بررسی اتصال»'
        : 'نشست پاک شد'))
        : (messageOf(r) || 'پاسخِ سرویس خوانا نبود')) + voided);
      fresh();
    } catch (e) {
      setTone('bad');
      // متنِ خطا ازِ `HttpError` است (کدِ وضعیت + آدرس)؛ نشانی درِ هیچ‌کدام نیست.
      setNote(e instanceof Error ? e.message.slice(0, 160) : 'خطای نامعلوم');
      // پرسش نرسید ⇒ نه «ثبت شد» گفته می‌شود نه «پاک شد»؛ وضعیت ازِ خودِ سرویس
      // تازه خوانده می‌شود تا رابط برایِ خودش نتیجه نسازد.
      qc.invalidateQueries({ queryKey: ['execution-status'] });
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="mt-2 flex flex-col gap-1 rounded-lg border border-border-c/50
      bg-bg-primary/40 px-2 py-1.5" data-testid="sarkhati-session-form">
      <div className="flex flex-wrap items-end gap-1.5">
        <label className="flex min-w-0 flex-1 flex-col gap-0.5 text-3xs text-text-muted">
          دسترسی به حساب کارگزاری — فقط در حافظهٔ همین برنامه می‌ماند و با بستن برنامه پاک می‌شود
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            aria-label="دسترسی به حساب کارگزاری"
            data-testid="sarkhati-token-input"
            className="rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs text-text-primary"
          />
        </label>
        <GhostBtn testId="sarkhati-token-save" disabled={busy !== '' || blank}
          title="نوشته نمی‌شود؛ فقط در حافظهٔ برنامه می‌ماند. «ثبت دسترسی» با «تأیید دسترسی» یکی نیست."
          onClick={() => void act('set')}>
          {busy === 'set' ? 'در حالِ ثبت' : 'ثبت دسترسی'}
        </GhostBtn>
        <GhostBtn testId="sarkhati-token-clear" disabled={busy !== ''}
          title="DELETE /api/execution/session — دسترسی را پاک می‌کند و هیچ پرسشی نمی‌زند"
          onClick={() => void act('clear')}>
          {busy === 'clear' ? 'در حالِ پاک‌کردن' : 'پاک کردنِ دسترسی'}
        </GhostBtn>
      </div>

      {note ? (
        <p role="status" data-testid="sarkhati-session-note"
          className={`text-2xs leading-5 ${tone === 'ok' ? 'text-accent-green'
            : tone === 'bad' ? 'text-accent-red' : 'text-accent-yellow'}`}>
          {note}
        </p>
      ) : null}

      {/* چهار سطرِ جدا، هرکدام ازِ یکِ فیلد: «ذخیره شد»، «وارد شد»، «تأیید شد»،
          «ارسال مجاز است». روشن‌شدنِ یکی دیگری را روشن نمی‌کند. */}
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1"
        data-testid="sarkhati-state-ladder">
        {ladder.map((g) => (
          <span key={g.key} className="flex min-w-0 items-baseline gap-1">
            <span className="text-3xs text-text-muted">{g.label}</span>
            <Chip tone={g.tone} testId={`sarkhati-gate-${g.key}`} title={g.title}>
              {g.text}
            </Chip>
          </span>
        ))}
      </div>

      <Note label="دسترسی به حساب از کجا می‌آید" testId="sarkhati-session-how">
        <ul className="flex flex-col gap-0.5">
          <li>ابتدا خودتان در پنجرهٔ کارگزاری وارد شوید («اتصال به EasyTrader» در
              همین کارت). این برنامه نام کاربری و رمز شما را نمی‌پرسد و هیچ ورود
              خودکاری ندارد.</li>
          <li>روش اصلی، دریافت خودکار دسترسی از همان پنجره است. این فیلد فقط برای
              مسیر فنی/سازگاری است؛ مقدارش فقط در حافظه می‌ماند، در هیچ فایلی
              نوشته نمی‌شود و در هیچ لاگی ظاهر نمی‌شود.</li>
          <li>«بررسی وضعیت» تنها چیزی است که تأیید واقعی می‌سازد — آن هم فقط با
              پاسخ واقعی کارگزاری. ثبت دستی به‌تنهایی هیچ‌چیز را تأیید نمی‌کند.</li>
        </ul>
      </Note>
    </div>
  );
}
