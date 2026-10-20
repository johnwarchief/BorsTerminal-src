// features/portfolio/components/sarkhati/SarkhatiConnectionSettings.tsx —
// «تنظیمِ اتصال» درونِ خودِ برنامه، با دو گیتِ جدا
//
// چرا این کنترل لازم شد: درِ v1.0.93 انتخابِ آداپتور فقط ازِ متغیرِ محیطی
// `BORS_EXECUTION_ADAPTER` می‌آمد، و بیلدِ منجمدِ دسکتاپ هیچ env ای ازِ کاربر
// نمی‌گیرد — پس «اتصال به مفید» برایِ مالک عملاً خاموش بود. حالا همان انتخاب
// دو کلیدِ *غیرمحرمانه* است که رویِ `user.db` می‌نشیند.
//
// سه ادعایی که این مؤلفه نمی‌کند:
//  • «ذخیره شد» ≠ «اعمال شد»: آداپتور و نوعِ ترافیک درِ `import` خوانده می‌شوند،
//    پس تا restart برنامه، تنظیمِ ذخیره‌شده مؤثر نیست. هر دو عدد جدا نشان داده
//    می‌شوند (`stored.adapter` در برابرِ `effective.adapter`).
//  • «فقط‌خواندنی» یعنی خواندن، نه اجازهٔ ارسال. گیتِ نوشتن (*فقط*
//    `BORS_EXECUTION_LIVE=1`) ازِ این مسیر روشن نمی‌شود — هیچ دکمه‌ای درِ رابط
//    پولِ واقعی را آزاد نمی‌کند.
//  • هیچ رمز/نشانی/کوکی ازِ این مسیر نمی‌گذرد و هیچ‌جا نوشته نمی‌شود؛ بک‌اند
//    کلیدِ ناشناخته را رد می‌کند.
import { useState } from 'react';
import { configApi, useBrokerConfig, type BrokerConfig } from '../../lib/orderClient';
import { Chip, Field, Line, Note } from './parts';

const ADAPTERS: ReadonlyArray<{ value: string; label: string; title: string }> = [
  { value: 'mock', label: 'بدل', title: 'هیچ ترافیکی به کارگزاری نمی‌رود — مسیرِ آزمایشیِ خودِ برنامه' },
  { value: 'easytrader', label: 'مفید (EasyTrader)', title: 'سیمِ read-only به api-mts.orbis.easytrader.ir' },
];

const SOURCE_LABEL: Record<string, string> = {
  env: 'متغیرِ محیطی (بر تنظیمِ دیسک مقدم است)',
  settings: 'تنظیمِ ذخیره‌شده درِ برنامه',
  default: 'پیش‌فرض (بدونِ تنظیم)',
  unavailable: 'تنظیمِ دیسک خوانده نشد',
};

export function SarkhatiConnectionSettings() {
  const q = useBrokerConfig();
  const cfg = q.data;
  const stored = cfg?.stored ?? {};
  const eff = cfg?.effective ?? {};
  const [adapter, setAdapter] = useState<string | null>(null);
  const [readOnly, setReadOnly] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState('');

  const wantAdapter = adapter ?? String(stored.adapter ?? 'mock');
  const wantReadOnly = readOnly ?? stored.read_only === true;
  const dirty = adapter !== null ? adapter !== String(stored.adapter ?? 'mock')
    : readOnly !== null ? readOnly !== (stored.read_only === true) : false;

  const save = async () => {
    setBusy(true); setNote('');
    try {
      const r: BrokerConfig = await configApi.put({ adapter: wantAdapter, read_only: wantReadOnly });
      if (r.status !== 'success') {
        setNote(String(r.detail ?? r.code ?? 'ذخیره نشد'));
      } else {
        setNote(String(r.detail ?? 'ذخیره شد'));
        setAdapter(null); setReadOnly(null);
        await q.refetch();
      }
    } catch (e) {
      setNote(e instanceof Error ? e.message.slice(0, 140) : 'خطای نامعلوم');
    } finally {
      setBusy(false);
    }
  };

  const btn = 'min-h-[36px] rounded-lg border px-2 text-2xs font-bold';
  const pending = cfg?.applies_on_restart === true
    && String(stored.adapter ?? '') !== String(eff.adapter ?? '');

  return (
    <div className="mt-2 flex flex-col gap-1 rounded-lg border border-border-c/50
      bg-bg-primary/40 px-2 py-1.5" data-testid="sarkhati-connection-settings">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-2xs font-bold text-text-secondary">کارگزاری</span>
        {ADAPTERS.map((a) => (
          <button key={a.value} type="button" title={a.title}
                  onClick={() => setAdapter(a.value)} disabled={busy}
                  data-testid={`sarkhati-adapter-${a.value}`}
                  className={`${btn} ${wantAdapter === a.value
                    ? 'border-accent-blue bg-accent-blue/15 text-accent-blue'
                    : 'border-border-c bg-bg-card text-text-secondary'}`}>
            {a.label}
          </button>
        ))}
        <button type="button" data-testid="sarkhati-read-only" title="خواندن بله، ارسالِ سفارش نه"
                onClick={() => setReadOnly(!wantReadOnly)} disabled={busy}
                aria-pressed={wantReadOnly}
                className={`${btn} ${wantReadOnly
                  ? 'border-accent-green bg-accent-green/15 text-accent-green'
                  : 'border-border-c bg-bg-card text-text-secondary'}`}>
          فقط‌خواندنی
        </button>
        <button type="button" data-testid="sarkhati-config-save" onClick={save}
                disabled={busy || !dirty}
                className={`${btn} ${dirty ? 'border-accent-blue text-accent-blue' : 'border-border-c text-text-muted opacity-50'}`}>
          {busy ? 'در حالِ ذخیره' : 'ذخیرهٔ تنظیم'}
        </button>
        {cfg ? (
          <Chip tone={cfg.secrets_stored === false ? 'ok' : 'warn'} testId="sarkhati-config-secrets"
                title="این تنظیم فقط دو کلید دارد: adapter و read_only">
            بدونِ ذخیرهٔ رمز
          </Chip>
        ) : null}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <Field label="ذخیره شده" value={(
          <span className="num text-2xs text-text-primary" data-testid="sarkhati-config-stored">
            {String(stored.adapter ?? '—')}
            {stored.read_only === true ? ' · فقط‌خواندنی' : ' · بدونِ فقط‌خواندنی'}
          </span>)} />
        <Field label="همین حالا مؤثر" value={(
          <span className="num text-2xs text-text-primary" data-testid="sarkhati-config-effective">
            {String(eff.adapter ?? '—')}
            {eff.traffic_allowed === true ? ' · ترافیک مجاز' : ' · بی‌ترافیک'}
            {eff.live_requested === true ? ' · ارسال آزاد' : ''}
          </span>)} />
        <Field label="منشأِ انتخاب" value={(
          <span className="text-2xs text-text-secondary" data-testid="sarkhati-config-source">
            {SOURCE_LABEL[String(stored.source ?? 'default')] ?? String(stored.source ?? '—')}
          </span>)} />
      </div>

      {pending ? (
        <Line kind="warn" testId="sarkhati-config-restart">
          تنظیمِ ذخیره‌شده هنوز مؤثر نیست — آداپتور درِ راه‌اندازی خوانده می‌شود؛
          برنامه را یک‌بار ببندید و باز کنید.
        </Line>
      ) : null}
      {dirty ? (
        <p className="text-3xs text-text-muted" data-testid="sarkhati-config-dirty">
          تغییرِ شما هنوز ذخیره نشده است.
        </p>
      ) : null}
      {note ? (
        <p className="text-3xs text-text-secondary" data-testid="sarkhati-config-note">{note}</p>
      ) : null}

      <Note label="دو گیتِ جدا" testId="sarkhati-config-gates">
        <ul className="flex flex-col gap-0.5">
          <li>فقط‌خواندنی یعنی GETِ وضعیت دسترسی و فهرست‌ها؛ «ارسال سفارش» با این
              روشن نمی‌شود.</li>
          <li>گیتِ نوشتن فقط باِ متغیرِ محیطی <span className="num" dir="ltr">BORS_EXECUTION_LIVE=1</span> است —
              تصمیمِ جدا و آگاهانۀ خودِ کاربر، نه یکِ دکمه درِ این صفحه.</li>
          <li>مسیرِ سیمِ کارگزاری هنوز سندِ رسمیِ منتشرشده ندارد (۴۰۳)؛ «متصل» فقط باِ
              پاسخِ واقعیِ کارگزاری گفته می‌شود.</li>
        </ul>
      </Note>

      {q.isError ? (
        <Line kind="error">
          درِ تنظیمِ اتصال پاسخی نداد — این نسخه آن در را ندارد یا بک‌اند پاسخ نمی‌دهد؛
          وضعیتِ کنونی از «بدونِ تنظیم» معتبرتر نیست.
        </Line>
      ) : null}
    </div>
  );
}
