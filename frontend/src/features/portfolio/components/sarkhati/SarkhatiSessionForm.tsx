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
import { useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toFaDigits } from '@shared/lib/fmt';
import { messageOf, orderApi, useBrokerConfig, useExecutionStatus } from '../../lib/orderClient';
import { connectionLadder } from '../../lib/sarkhatiFlow';
import { Chip, GhostBtn, Note } from './parts';

/** یکِ سطرِ `api_paths` ازِ `/api/execution/har/inspect`. هیچ‌کدام ازِ فیلدها
 *  مقدارِ هدر یا بدنه نیست — بک‌اند فقط نام می‌سازد و گاردِ `dev/execution_har_v1.py`
 *  باِ sentinel کاشته‌شده همین را می‌سنجد. */
type HarPath = { host?: string; method?: string; path?: string; status?: number;
  response_keys?: string[]; auth?: boolean; cookie?: boolean };

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
  const [busy, setBusy] = useState<'' | 'set' | 'clear' | 'harRead' | 'harUse'>('');
  const [note, setNote] = useState('');
  const [tone, setTone] = useState<'ok' | 'bad'>('bad');
  const [harName, setHarName] = useState('');
  const [harRows, setHarRows] = useState<HarPath[]>([]);
  const [harMeta, setHarMeta] = useState('');
  const fileRef = useRef<HTMLInputElement | null>(null);

  const blank = token.trim() === '';
  const ladder = connectionLadder({ cfg: cfg.data, st: st.data });

  const fresh = () => {
    qc.invalidateQueries({ queryKey: ['execution-status'] });
    qc.invalidateQueries({ queryKey: ['execution-connect'] });
  };

  /** متنِ HAR را ازِ فایل می‌خواند و *بلافاصله* آدرسِ فایل را ازِ input می‌گیرد.
   *  فایل رویِ دیسک دست‌نخورده می‌ماند و ما فقط بدنه را به درِ خودِ برنامه می‌دهیم. */
  const readHar = async (): Promise<string | null> => {
    const f = fileRef.current?.files?.[0];
    if (!f) {
      setTone('bad'); setNote('پرونده‌ای انتخاب نشده — «انتخاب پروندۀ HAR» را بزنید');
      return null;
    }
    setHarName(f.name);
    try {
      return await f.text();
    } catch {
      setTone('bad'); setNote('متنِ پرونده خوانده نشد');
      return null;
    } finally {
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const runHar = async (kind: 'harRead' | 'harUse') => {
    setBusy(kind); setNote('');
    const text = await readHar();
    if (text == null) { setBusy(''); return; }
    try {
      if (kind === 'harRead') {
        const r = await orderApi.harInspect(text);
        const ok = String(r.status ?? '') === 'success';
        const paths = Array.isArray(r.api_paths) ? (r.api_paths as HarPath[]) : [];
        setTone(ok ? 'ok' : 'bad');
        setHarRows(ok ? paths : []);
        setHarMeta(ok
          ? `${toFaDigits(String(r.entries_total ?? 0))} ردیفِ پرسش · `
            + `${toFaDigits(String(paths.length))} مسیر رویِ میزبانِ API · `
            + `بیرونِ آن ${toFaDigits(String(r.off_wire_hosts ?? 0))} میزبان`
          : '');
        setNote(ok
          ? (paths.length
            ? 'فقط نامِ مسیرها و کلیدهایِ پاسخ درآمد؛ هیچ مقداری ازِ پرونده '
              + 'نمایش داده نشد'
            : 'هیچ پرسشی رویِ میزبانِ APIِ این آداپتور درِ پرونده نیست')
          : (String(r.detail ?? '') || 'پروندۀ خراب بود'));
      } else {
        const r = await orderApi.harSession(text);
        const ok = r.imported === true;
        setTone(ok ? 'ok' : 'bad');
        setNote(String(r.detail ?? '')
          + (ok ? ' · تأییدِ واقعی فقط با «بررسی اتصال»' : ''));
        fresh();
      }
    } catch (e) {
      setTone('bad');
      setNote(e instanceof Error ? e.message.slice(0, 160) : 'خطای نامعلوم');
    } finally {
      setBusy('');
    }
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
          نشانیِ نشست = همان مقداری که هدرِ <span className="num" dir="ltr">Authorization: Bearer</span>
          {' '}می‌شود؛ کوکی، آدرسِ سایت یا نام‌کاربری/رمز اینجا پذیرفته نیست
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            aria-label="نشانیِ نشستِ کارگزاری"
            data-testid="sarkhati-token-input"
            className="rounded-lg border border-border-c bg-bg-primary px-1.5 py-1 text-2xs text-text-primary"
          />
        </label>
        <GhostBtn testId="sarkhati-token-save" disabled={busy !== '' || blank}
          title="نوشته نمی‌شود؛ فقط درِ حافظۀِ پروسه می‌نشیند. «ثبتِ نشست» با «تأییدِ نشست» یکی نیست."
          onClick={() => void act('set')}>
          {busy === 'set' ? 'در حالِ ثبت' : 'ثبتِ نشست'}
        </GhostBtn>
        <GhostBtn testId="sarkhati-token-clear" disabled={busy !== ''}
          title="DELETE /api/execution/session — برمی‌گردد به حالتِ قطعِ نشست و هیچ پرسشی نمی‌زند"
          onClick={() => void act('clear')}>
          {busy === 'clear' ? 'در حالِ پاک‌کردن' : 'پاک کردنِ نشست'}
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

      {/* برداشتِ نشست از پروندۀ HAR — بندِ ۷ مأموریت: نشانیِ حاویِ توکن ازِ دستِ
          کاربر به فیلدِ متنی نمی‌رود. فایل را خودِ ویندوز انتخاب می‌کند، بدنه به
          درِ خودِ همین برنامه می‌رود، و رشته هرگز درِ این رابط نشان داده نمی‌شود. */}
      <div className="mt-1.5 flex flex-col gap-1 rounded-lg border border-border-c/50
        bg-bg-primary/40 px-2 py-1.5" data-testid="sarkhati-har-block">
        <div className="flex flex-wrap items-center gap-1.5">
          <input type="file" accept=".har,application/json" ref={fileRef}
            aria-label="پروندۀ HARِ نشستِ کارگزاری"
            data-testid="sarkhati-har-file"
            className="min-w-0 max-w-[16rem] flex-1 text-3xs text-text-secondary" />
          <GhostBtn testId="sarkhati-har-inspect" disabled={busy !== ''}
            title="فقط نامِ میزبان، متد، مسیر و نامِ کلیدهایِ پاسخ را می‌خواند؛ برایِ کشفِ مسیرِ موجودی و قدرت خرید"
            onClick={() => void runHar('harRead')}>
            {busy === 'harRead' ? 'در حالِ خواندن' : 'تحلیلِ مسیرها'}
          </GhostBtn>
          <GhostBtn testId="sarkhati-har-import" disabled={busy !== ''}
            title="آخرین هدرِ Bearer رویِ میزبانِ API را فقط درِ حافظۀِ همین پروسه می‌گذارد؛ نوشته، لاگ یا نمایش داده نمی‌شود"
            onClick={() => void runHar('harUse')}>
            {busy === 'harUse' ? 'در حالِ برداشت' : 'برداشتِ نشست'}
          </GhostBtn>
        </div>
        {harName ? (
          <p className="text-3xs text-text-muted" data-testid="sarkhati-har-name">
            پروندۀ انتخابی: <span dir="ltr">{harName}</span> — پس ازِ خواندن، انتخاب
            ازِ فیلد پاک می‌شود و خودِ پرونده دست‌نخورده رویِ دیسک می‌ماند
          </p>
        ) : null}
        {harMeta ? (
          <p className="num text-3xs text-text-secondary" dir="rtl"
             data-testid="sarkhati-har-meta">{harMeta}</p>
        ) : null}
        {harRows.length > 0 ? (
          <ul className="flex flex-col gap-0.5" data-testid="sarkhati-har-paths">
            {harRows.slice(0, 8).map((r, i) => (
              <li key={`${r.method}-${r.path}-${i}`}
                  className="flex flex-wrap items-baseline gap-1 text-3xs">
                <span className="num font-bold text-text-primary" dir="ltr">
                  {String(r.method)} {String(r.path)}
                </span>
                <span className="num text-text-muted" dir="ltr">{String(r.status)}</span>
                {r.auth ? <span className="text-accent-blue">هدرِ دسترسی داشت</span> : null}
                {(r.response_keys ?? []).slice(0, 5).map((k) => (
                  <span key={k} className="num rounded border border-border-c/60
                    px-1 text-3xs text-text-muted" dir="ltr">{k}</span>
                ))}
              </li>
            ))}
            {harRows.length > 8 ? (
              <li className="text-3xs text-text-muted" data-testid="sarkhati-har-more">
                و {toFaDigits(String(harRows.length - 8))} مسیرِ دیگر درِ پاسخ
              </li>
            ) : null}
          </ul>
        ) : null}
      </div>

      <Note label="نشست ازِ کجا می‌آید" testId="sarkhati-session-how">
        <ul className="flex flex-col gap-0.5">
          <li>ابتدا خودتان درِ پنجرۀِ کارگزاری وارد شوید («ورود به ایزی‌تریدر» درِ
              همین کارت). این برنامه نامِ کاربری و رمزِ شما را نمی‌پرسد و هیچ
              ورودِ خودکاری ندارد.</li>
          <li>راهکارِ ترجیحی «برداشتِ نشست» است: پروندۀ HAR را خودِ ویندوز انتخاب
              می‌کنید، بدنه فقط به درِ همین برنامه (رویِ 127.0.0.1) می‌رود، و نشانی
              هرگز درِ این رابط تایپ یا نشان داده نمی‌شود. اگر آن‌جا رد شد، علتش
              درِ همان سطر نوشته می‌شود (بی‌میزبانِ API / فقط‌کوکی).</li>
          <li>فیلدِ متنی جایِ دوم است و فقط همان مقداری را می‌پذیرد که هدرِ
              <span className="num" dir="ltr"> Authorization: Bearer</span> می‌شود.
              هر دو راه فقط درِ حافظۀِ پروسه می‌نشیند: درِ هیچ فایلی نوشته نمی‌شود،
              درِ هیچ لاگی ظاهر نمی‌شود، و با restart می‌میرد.</li>
          <li>«بررسی اتصال» تنها چیزی است که «تأیید شد» می‌سازد — آن هم فقط باِ
              پاسخِ واقعیِ کارگزاری. ثبتِ نشانی به‌تنهایی هیچ‌چیز را تأیید نمی‌کند.</li>
        </ul>
      </Note>
    </div>
  );
}
