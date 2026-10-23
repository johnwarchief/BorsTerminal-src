// features/portfolio/components/sarkhati/SarkhatiPipeline.tsx — خطِ جریانِ اجرا
//
// این نوار، همان چیزی است که این تب را از هر «فرمِ سفارش» دیگری جدا می‌کند:
// سفرِ یکِ سرخطی یکِ توالیِ دروازه‌دار است — نماد ← پیش‌فرود ← آماده‌سازی ←
// تأیید ← گیتِ اجرا ← ارسال ← پذیرشِ کارگزاری ← استعلام/رفعِ ابهام ← تاریخچه —
// و هر مرحله رأیِ *جدایی* دارد. «۲۰۰» مرحلهٔ ارسال را سبز می‌کند نه مرحلهٔ
// پذیرش (§۴-ج). پس ترتیب اینجا تزئین نیست، خودِ اطلاعات است.
//
// داده: وضعیتِ کنونی از `/api/execution/status` و تازه‌ترین رکوردِ `/ledger`؛
// مدتِ هر گره از `/api/execution/timings` (monotonic، با پرچمِ «نمونۀ کم»).
// هیچ مرحله‌ای بی‌شاهد سبز نمی‌شود و هیچ عددی اینجا محاسبه نمی‌شود: گره‌ای که
// فازِ زمان‌سنجیِ خودِ `timings` را ندارد «—» می‌گیرد، نه صفر و نه حدس.
//
// علامت‌ها آیکونِ خودِ برنامه‌اند (همان viewBox ۲۴ و سروک ۲ درِ Icons.tsx)، نه
// یونیکدِ ✓ ✕ ? — آن علامت‌ها درِ متنِ فارسی جابه‌جا چاپ می‌شوند و وزنشان با
// بقیۀِ آیکون‌ها یکی نیست.
import { useMemo } from 'react';
import { CheckIcon, HelpIcon, LockIcon, XIcon } from '@shared/components/Icons';
import { toFaDigits } from '@shared/lib/fmt';
import type { ExecutionRecord, ExecutionStatus, TimingsView } from '../../lib/orderClient';
import { phaseOf } from '../../lib/orderClient';

type NodeState = 'done' | 'now' | 'held' | 'idle' | 'bad' | 'unknown';

const NODES: { id: string; label: string; phase?: string; lock?: boolean }[] = [
  { id: 'symbol', label: 'نماد' },
  { id: 'preflight', label: 'پیش‌فرود', phase: 'preflight' },
  { id: 'prepare', label: 'آماده‌سازی', phase: 'preflight' },
  { id: 'confirm', label: 'تأیید' },
  { id: 'gate', label: 'گیتِ اجرا', lock: true },
  { id: 'send', label: 'ارسال', phase: 'submitted' },
  { id: 'accept', label: 'پذیرشِ کارگزاری', phase: 'accepted' },
  { id: 'check', label: 'استعلام / رفعِ ابهام', phase: 'submitted' },
  { id: 'history', label: 'تاریخچه' },
];

/** نامِ فازِ `timings` برایِ هر گره؛ بی‌فاز = مدتِ اندازه‌گیری‌شده ندارد */
const TIMING_KEY: Record<string, string> = {
  preflight: 'preflight_ms', prepare: 'prepare_ms', send: 'dispatch_ms',
  check: 'reconcile_ms',
};

const SENT_PHASES = ['submitted', 'accepted', 'partial', 'filled', 'rejected', 'cancelled'];
const ACCEPTED_PHASES = ['accepted', 'partial', 'filled'];

export function SarkhatiPipeline({ status, timings, latest, hasSymbol }: {
  status: ExecutionStatus | null;
  timings: TimingsView | null;
  latest: ExecutionRecord | null;
  hasSymbol: boolean;
}) {
  const states = useMemo(() => {
    const live = status?.live_enabled === true;
    const halted = status?.halted === true;
    const ph = latest ? phaseOf(latest) : 'idle';
    const out: Record<string, NodeState> = {};
    const have = latest != null;
    out.symbol = hasSymbol ? 'done' : 'now';
    const validated = have && ['preflight', 'scheduled', 'submitted', 'accepted',
      'partial', 'filled', 'rejected', 'cancelled', 'unknown', 'errored']
      .includes(ph);
    out.preflight = validated ? 'done' : (hasSymbol ? 'now' : 'idle');
    out.prepare = have && (latest?.status === 'prepared' || ['scheduled', 'submitted',
      'accepted', 'partial', 'filled'].includes(ph)) ? 'done'
      : (validated ? 'now' : 'idle');
    const confirmed = have && latest?.status !== 'draft';
    out.confirm = confirmed ? 'done' : (out.prepare === 'done' ? 'now' : 'idle');
    // گیتِ اجرا را کاربر نمی‌زَنَد؛ یا سرویس باز کرده یا بسته است. «held» یعنی
    // دروازۀِ زنده قفل است (یا توقفِ اضطراری خورده) — نه اینکه کارِ شما عقب افتاده.
    out.gate = halted ? 'held' : live ? 'done' : 'held';
    const sent = have && SENT_PHASES.includes(ph);
    // `unknown_result` یعنی درخواست رفته و رأیی برگشته که نمی‌شود به آن اعتماد
    // کرد: «ارسال» را خاکستری (یعنی «انجام نشده») نمی‌نشانیم و سبز هم نمی‌کنیم.
    out.send = sent ? 'done' : ph === 'unknown' ? 'unknown' : ph === 'scheduled' ? 'now'
      : (out.gate === 'done' && confirmed ? 'now' : 'idle');
    const accepted = have && ACCEPTED_PHASES.includes(ph);
    out.accept = accepted ? 'done' : ph === 'unknown' ? 'unknown'
      : ph === 'rejected' || ph === 'errored' ? 'bad' : (sent ? 'now' : 'idle');
    out.check = have && (latest?.status === 'reconciled' || ph === 'unknown')
      ? (ph === 'unknown' ? 'unknown' : 'done') : 'idle';
    out.history = (status?.durable_events ?? 0) > 0 ? 'done' : 'idle';
    return out;
  }, [status, latest, hasSymbol]);

  const phases = (timings?.phases ?? {}) as Record<string,
    { n?: number | null; p50?: number | null; thin?: boolean | null }>;
  // «کجا نگاه کنم؟» اول مشکل را می‌گوید، بعد نوبتِ تصمیم، و بعد قفلِ گیت:
  // رکوردِ مبهم از «هنوز نماد نزده‌اید» فوریاتی‌تر است.
  const current = NODES.find((n) => states[n.id] === 'unknown' || states[n.id] === 'bad')
    ?? NODES.find((n) => states[n.id] === 'now')
    ?? NODES.find((n) => states[n.id] === 'held')
    ?? NODES[NODES.length - 1];

  return (
    <div className="rounded-xl border border-border-c/70 bg-bg-secondary/40 px-2 py-1.5"
      data-testid="sarkhati-rail">
      <ol data-testid="sarkhati-pipeline" aria-label="جریانِ اجرا"
        className="sk-scroll flex snap-x items-start gap-0 overflow-x-auto pb-0.5">
        {NODES.map((n, i) => {
          const st: NodeState = states[n.id] ?? 'idle';
          const tk = TIMING_KEY[n.id];
          const t = tk ? phases[tk] : undefined;
          const skin = {
            done: 'border-accent-green/60 bg-accent-green/15 text-accent-green',
            now: 'border-neon-cyan/70 bg-neon-cyan/15 text-neon-cyan',
            held: 'border-accent-yellow/60 bg-accent-yellow/15 text-accent-yellow',
            bad: 'border-accent-red/60 bg-accent-red/15 text-accent-red',
            unknown: 'border-accent-susp/70 bg-accent-susp-bg text-accent-susp',
            idle: 'border-border-c/70 bg-bg-card/50 text-text-muted',
          }[st];
          const seg = i === 0 ? '' : (st === 'idle' || states[NODES[i - 1].id] === 'idle'
            ? 'bg-border-c/70' : 'bg-accent-green/45');
          return (
            <li key={n.id} data-testid={`sarkhati-node-${n.id}`} data-state={st}
              title={nodeHint(n.id, st, status, t)}
              className="relative flex min-w-[84px] snap-start shrink-0 grow flex-col items-center gap-0.5 px-1">
              {i > 0 ? (
                <span aria-hidden="true"
                  className={`absolute -start-[8px] top-[10px] h-px w-4 ${seg}`} />
              ) : null}
              <span className={`grid size-5 place-items-center rounded-full border motion-safe:transition-colors
                motion-safe:duration-200 ${skin} ${st === 'now' ? 'sk-node-now' : ''}`}>
                {st === 'done' ? <CheckIcon size={12} />
                  : st === 'bad' ? <XIcon size={12} />
                    : st === 'unknown' ? <HelpIcon size={12} />
                      : n.lock ? <LockIcon size={12} />
                        : <span className="num text-3xs font-black">{toFaDigits(String(i + 1))}</span>}
              </span>
              <span className={`text-center text-3xs leading-3 ${st === 'idle' ? 'text-text-muted' : 'text-text-secondary'}`}>
                {n.label}
              </span>
              <span className={`num text-2xs leading-3 ${t?.p50 != null ? 'text-text-secondary' : 'text-text-muted'}`}>
                {t && t.p50 != null
                  ? `${toFaDigits(String(t.p50))}ms${t.thin ? ' · کم‌نمونه' : ''}`
                  : t ? 'بی‌نمونه' : '—'}
              </span>
            </li>
          );
        })}
      </ol>
      <p className="mt-1 border-t border-border-c/40 pt-1 text-2xs leading-4 text-text-secondary"
        data-testid="sarkhati-pipeline-hint" data-node={current.id}>
        <span className="font-black text-text-primary">{current.label}</span>
        {' — '}
        {nodeHint(current.id, states[current.id] ?? 'idle', status)}
      </p>
    </div>
  );
}

function nodeHint(id: string, st: NodeState, status: ExecutionStatus | null,
  t?: { n?: number | null; p50?: number | null } | null): string {
  if (id === 'gate') {
    if (status?.halted === true) {
      return `توقفِ اضطراری رویِ دیسک است${status?.kill_reason ? ` — ${String(status.kill_reason)}` : ''}`;
    }
    if (status?.live_enabled === true) return 'گیتِ اجرا باز است';
    const b = (status?.blocked_on ?? []);
    if (b.length) return `گیتِ اجرا بسته است — ${b[0]}`;
    // گره «held» است ولی پاسخِ سرویس علتِ موجهی نگفته: «باز است» نوشتن اینجا
    // دروغِ رابط است. خاموشیِ زنده را به‌عنوانِ همان خاموشی اعلام می‌کنیم.
    return status?.live_requested === false || status == null
      ? 'گیتِ اجرا بسته است — اجرای زنده در این برنامه درخواست نشده'
      : 'گیتِ اجرا بسته است — علتی ازِ سرویس نیامده';
  }
  if (id === 'check' && st === 'unknown') {
    return 'نتیجه نامعلوم — فقط «رفعِ ابهام»، نه ارسالِ دوباره';
  }
  if (st === 'unknown') return 'پاسخِ مبهم — تعیینِ تکلیف نشده';
  if (st === 'bad') return 'این گره رد شد؛ علتش درِ ردِّپایِ همین شناسه است';
  if (st === 'held') return 'متوقف';
  if (st === 'done') return id === 'history' && t == null ? 'رخدادِ ماندگار ثبت شده' : 'انجام شد';
  if (st === 'now') return 'نوبتِ تصمیمِ شما این‌جاست';
  return 'هنوز نوبتش نرسیده';
}
