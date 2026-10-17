// features/fundamental/components/CodalHealthStrip.tsx -- نوارِ باریکِ سلامتِ خطِ کدال
//
// چرا این فایل متولد شد (مأموریتِ ۱۴۰۵-۰۷-۲۳، بندِ ۷؛ spec:
// `docs/CODAL-AUTO-UPDATE-2026-10-14.md` §۵-۳). خطِ دریافتِ خودکارِ کدال ازِ
// قبل درِ سرور بود (صف، checkpoint، worker، زمان‌بند) ولی درِ رابط هیچ نشانی
// نداشت: کاربر نمی‌فهمید دادهٔ بنیادی «کی» تازه شده، چه چیزی درِ صف مانده، و
// آیا worker واقعاً کار می‌کند یا خاموش است. این نوار همان را از
// `/api/sync/codal/pipeline` می‌خواند — از جدول، نه از شمارندهٔ حافظه‌ای.
//
// سه تصمیمِ عمدی:
//  1) ارتفاعِ محدود: یکِ خطِ پاسخ + چیپ‌ها، جزئیات پشتِ `<details>` (الگویِ
//     `FtsIndicatorRail`). جدولِ غربالگری باید غالبِ صفحه بماند.
//  2) هیچ عددی ساخته نمی‌شود: نبودِ `last_data_update` یعنی «درِ این بانک
//     چرخۀ موفقی ثبت نشده»، نه صفر و نه «همیشه تازه». علتِ همان خانۀ خالی
//     درِ title می‌آید (قواعدِ رابط: مقدارِ غایب با علتِ همان محور).
//  3) ادعایی که پاسخ ندارد اینجا نوشته نمی‌شود: `last_successful_sync` تنها
//     «زمانِ چرخه» را می‌دهد، نه تعدادِ نمادهایِ نجات‌یافته — پس شمارِ نماد درِ
//     این نوار نیست.
import { toFaDigits } from '@shared/lib/fmt';
import { useCodalHealth, type CodalHealth } from '../api/useCodalHealth';

/** سه حالتِ «چراغ»: روشن (کار در جریان)، خنثی (بی‌کارِ باز)، سرخ (خطا/نرسیدن).
 *  `loading` جداست: «هنوز پاسخی نرسیده» با «خطا داد» یکی نیست، و بی‌این تفکیک
 *  هر ورودِ تازه به تب یکِ «وضعیت نرسید» کاذب نشان می‌دهد.
 */
type State = 'working' | 'idle' | 'blocked' | 'failed' | 'unreachable' | 'loading';

const STATE_TEXT: Record<State, string> = {
  working: 'خطِ کدال درِ کار است',
  idle: 'خطِ کدال بیکار است — کاری درِ صف نیست',
  blocked: 'کاری مانده که باید دوباره تلاش شود',
  failed: 'آخرین چرخه با خطا تمام شد',
  unreachable: 'وضعیتِ خطِ کدال نرسید',
  loading: 'وضعیتِ خطِ کدال خوانده می‌شود…',
};

const STATE_TONE: Record<State, string> = {
  working: 'text-accent-blue',
  idle: 'text-text-secondary',
  blocked: 'text-accent-yellow',
  failed: 'text-accent-red',
  unreachable: 'text-accent-red',
  loading: 'text-text-muted',
};

function stateOf(h: CodalHealth | undefined, errored: boolean, pending: boolean): State {
  if (errored || (h && h.status === 'error')) return 'unreachable';
  if (!h) return pending ? 'loading' : 'unreachable';
  if (h.worker?.running === true) return 'working';
  if ((h.queue?.failed ?? 0) + (h.queue?.unresolved ?? 0) > 0) return 'failed';
  if ((h.queue?.retryable ?? 0) > 0) return 'blocked';
  return 'idle';
}

/** فقط وقتی عدد می‌نویسیم که خانۀ پاسخ آمده باشد؛ بی‌خانۀ null با «—». */
function num(v: number | null | undefined): string {
  return v == null ? '—' : toFaDigits(v);
}

function Chip({ testid, label, value, title, tone }: {
  testid: string; label: string; value: string; title: string; tone?: string;
}) {
  return (
    <span
      data-testid={testid}
      data-count={value}
      title={title}
      className={`inline-flex items-center gap-1 rounded-md border border-border-c/70 bg-bg-card/60 px-1.5 py-0.5 text-3xs ${tone ?? 'text-text-secondary'}`}
    >
      <span className="text-text-muted">{label}</span>
      <span className="num font-bold">{value}</span>
    </span>
  );
}

export function CodalHealthStrip() {
  const q = useCodalHealth();
  const h = q.data;
  const errored = q.isError || h?.status === 'error';
  const st = stateOf(h, errored, q.isPending);
  const reason = errored || (h && h.status === 'error')
    ? (h?.message ? `علتِ سرور: ${String(h.message)}` : 'پاسخِ /api/sync/codal/pipeline نرسید یا خوانده نشد')
    : '';

  // «ثبت نشده» با «صفر» یکی نیست — و علتِ هر خانۀ خالی جدا نوشته می‌شود.
  const lastSync = h?.last_data_update ?? null;
  const lastSyncTitle = lastSync
    ? `زمانِ آخرین به‌روزرسانیِ دادهٔ بنیادی: ${lastSync}`
    : 'درِ این بانک هیچ چرخۀ موفقی ثبت نشده (`last_data_update = null`) — صفر نیست، بی‌سابقه است';
  const cycleTitle = h?.last_successful_sync
    ? `آخرین چرخۀ موفق: ${h.last_successful_sync}` +
      (h.last_attempt ? ` | آخرین تلاش: ${h.last_attempt}` : ' | آخرین تلاشی ثبت نشده')
    : 'چرخۀ موفقی ثبت نشده؛ `catchup.never_synced` همین را می‌گوید';
  const next = h?.cadence?.seconds != null
    ? `چرخۀ بعدی حدود ${toFaDigits(Math.round(h.cadence.seconds))} ثانیه دیگر (${h.cadence.reason ?? '—'})`
    : 'زمانِ چرخۀ بعدی از پاسخ نرسید';

  return (
    <div
      data-testid="codal-health-strip"
      data-state={st}
      className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-xl border border-border-c/70 bg-bg-card/50 px-2.5 py-1 text-3xs"
    >
      <span data-testid="codal-health-state" className={`font-bold ${STATE_TONE[st]}`}
            title={reason || cycleTitle}>
        {STATE_TEXT[st]}
      </span>

      <Chip testid="codal-health-count-queued" label="در صف"
            value={num(h?.queue?.queued)}
            title="اطلاعیه‌هایی که هنوز پردازش نشده‌اند (از جدولِ صف، نه حافظه)" />
      <Chip testid="codal-health-count-failed" label="بی‌نتیجه"
            value={num(h == null ? null : (h.queue?.failed ?? 0) + (h.queue?.unresolved ?? 0))}
            tone={(h?.queue?.failed ?? 0) + (h?.queue?.unresolved ?? 0) > 0 ? 'text-accent-red' : undefined}
            title="کارهایی که شکست خوردند یا نتیجه‌شان معلوم نمانده" />
      <Chip testid="codal-health-count-incomplete" label="استخراجِ ناقص"
            value={num(h?.incomplete_extractions)}
            title="ردیف‌هایی که اطلاعیه‌شان هست ولی جدولِ پنج شاخص از آن‌ها درنیامده" />
      <Chip testid="codal-health-count-gap" label="بی‌صورتِ مالی"
            value={num(h?.instruments?.no_fundamental)}
            title="نمادهای دارای شکاف پوشش (`instruments.no_fundamental`)" />
      <Chip testid="codal-health-count-dirty" label="نیازمندِ بازشماری"
            value={num(h?.dirty_symbols)}
            title="نمادهایی که داده‌شان عوض شده و شاخص‌هایشان هنوز دوباره حساب نشده" />

      <span data-testid="codal-health-last-sync" className="num text-text-muted" title={lastSyncTitle}>
        آخرین تازگی: {lastSync ? toFaDigits(lastSync) : '—'}
      </span>
      <span className="text-text-muted" title={cycleTitle}>
        {h?.worker?.running ? 'worker روشن' : 'worker خاموش'}
      </span>
      {h?.offline_gate ? (
        <span className="rounded-md border border-accent-yellow/50 bg-accent-yellow/10 px-1.5 py-0.5 text-accent-yellow"
              title="دربۀ آفلاین (`BORS_CODAL_OFFLINE`) روشن است: هیچ درخواستی به کدال نمی‌رود، ولی صف و چرخه اجرا می‌شوند">
          دربۀ آفلاین روشن
        </span>
      ) : null}

      <details className="ms-auto min-w-0">
        <summary className="cursor-pointer text-text-muted hover:text-text-secondary">جزئیات</summary>
        <ul className="mt-1 max-h-40 w-[min(92vw,520px)] overflow-auto space-y-0.5 text-3xs text-text-secondary">
          <li title={cycleTitle}>{cycleTitle}</li>
          <li>{next}</li>
          <li title="مجموعِ کارهایِ جدولِ صف؛ `legacy` یعنی ردیف‌هایی که پیش از این قرارداد وضعیتِ ثبت‌شده نداشته‌اند">
            حجمِ صف: <span className="num">{num(h?.queue?.total)}</span> ردیف،
            از آنِ <span className="num">{num(h?.queue?.legacy)}</span> کهنه
          </li>
          <li title="امضایِ تازگیِ داده (`data_epoch`)؛ با عوض‌شدنش کشِ کارت و غربالگری باطل می‌شود">
            امضایِ تازگی: <span className="num break-all">{h?.data_epoch ?? '—'}</span>
          </li>
          {h?.worker?.last_error ? (
            <li className="text-accent-red">خطایِ آخرین چرخه: {String(h.worker.last_error)}</li>
          ) : null}
          {reason ? <li className="text-accent-red">علت: {reason}</li> : null}
        </ul>
      </details>
    </div>
  );
}
