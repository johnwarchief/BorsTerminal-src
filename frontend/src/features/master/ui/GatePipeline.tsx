// features/master/ui/GatePipeline.tsx -- استپر افقی متراکم چهار گیتی
// یک نوار تک‌ردیفه: [گیت ۱: بنیاد] ─> [گیت ۲: تکنیکال] ─> [گیت ۳: تابلو] ─> [گیت ۴: سبد]
// هر کارت: وضعیت رنگی (عبور/رد/انتظار = Passed/Blocked/Pending) + Audit Popover با دلیل ریاضی.
import { fa0 } from '../lib/fmtNum';
import type { StrictGate, StrictGateState } from '../lib/strictGates';

/** نام‌های پایدار هر پله (سازگاری UI) */
const GATE_TITLE: Record<StrictGate['id'], string> = {
  fundamental: 'گیت ۱ · بنیادی',
  technical: 'گیت ۲ · تکنیکال',
  tape: 'گیت ۳ · تابلو',
  portfolio: 'گیت ۴ · سبد و رژیم ریسک',
};

const GATE_SHORT: Record<StrictGate['id'], string> = {
  fundamental: 'بنیاد',
  technical: 'تکنیکال',
  tape: 'تابلو',
  portfolio: 'سبد',
};

const STATUS_FA: Record<StrictGateState, { label: string; cls: string; en: string }> = {
  passed: { label: 'عبور', cls: 'border-accent-green/40 bg-accent-green/12 text-accent-green', en: 'Passed' },
  blocked: { label: 'رد', cls: 'border-accent-red/40 bg-accent-red/12 text-accent-red', en: 'Blocked' },
  pending: { label: 'انتظار', cls: 'border-accent-yellow/40 bg-accent-yellow/12 text-accent-yellow', en: 'Pending' },
};

function GateCard({ gate, index }: { gate: StrictGate; index: number }) {
  const st = STATUS_FA[gate.state];
  return (
    <li className="relative flex min-w-0 flex-1 flex-col gap-1.5 rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-2.5 py-2">
      <div className="flex items-center gap-1.5">
        <span className="num flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-border-c text-2xs font-black text-text-secondary">
          {fa0(index + 1)}
        </span>
        <span className="min-w-0 flex-1 truncate text-2xs font-bold text-text-primary" title={GATE_TITLE[gate.id]}>
          {GATE_TITLE[gate.id]}
        </span>
        <span
          className={`shrink-0 rounded-full border px-1.5 py-0.5 text-2xs font-bold ${st.cls}`}
          title={`${st.en}${gate.veto ? ' · VETO' : ''}`}
          aria-label={`وضعیت ${GATE_TITLE[gate.id]}: ${st.label}`}
        >
          {st.label}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-2xs text-text-muted">{GATE_SHORT[gate.id]}</span>
        {gate.veto ? (
          <span className="rounded-full border border-accent-red/40 bg-accent-red/10 px-1.5 py-0.5 text-2xs font-black text-accent-red">
            وتوی فوری
          </span>
        ) : null}
        {/* Audit Popover — با هاور/فوکوس باز می‌شود؛ دلیل ریاضی وضعیت */}
        <span className="group/audit relative ms-auto shrink-0">
          <button
            type="button"
            aria-label={`ممیزی ${GATE_TITLE[gate.id]}`}
            className="rounded-full border border-border-c bg-bg-card px-1.5 py-0.5 text-2xs font-bold text-text-secondary hover:border-border-accent hover:text-accent-blue"
          >
            ممیزی ⓘ
          </button>
          <span
            role="tooltip"
            className="pointer-events-none absolute end-0 top-full z-30 mt-1 hidden w-64 rounded-xl border border-border-c bg-bg-primary/95 p-2.5 text-2xs leading-5 text-text-secondary shadow-lg backdrop-blur-md group-hover/audit:block group-focus-within/audit:block"
          >
            <b className="text-text-primary">دلیل ریاضی وضعیت «{st.label}»:</b> {gate.reason}
          </span>
        </span>
      </div>
    </li>
  );
}

export function GatePipeline({ gates }: { gates: StrictGate[] }) {
  const passed = gates.filter((g) => g.state === 'passed').length;
  return (
    <div className="glass-panel panel-in relative p-4">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black text-text-primary">پایپ‌لاین گیتینگ FTS</h3>
        <span className="num rounded-full border border-border-c bg-bg-card px-2.5 py-0.5 text-2xs font-bold text-text-secondary">
          {fa0(passed)}/{fa0(gates.length)} گیت سبز
        </span>
      </div>
      <p className="mb-3 text-2xs leading-5 text-text-muted">
        ترتیب سلسله‌مراتبی: [بنیاد] ─&gt; [تکنیکال ماژور/مینور] ─&gt; [تابلوخوانی] ─&gt; [سبد و رژیم ریسک] — «خرید پله‌ای» فقط با سبز بودن هم‌زمان هر چهار گیت؛ تابلو تنها زمان‌سنج ورود است.
        (راهنمای وضعیت: عبور = Passed · رد = Blocked · انتظار = Pending)
      </p>

      {/* نوار افقی تک‌ردیفه: ۴ کارت متصل با فلش ترتیب */}
      <ol className="flex flex-col gap-2 lg:flex-row lg:items-stretch">
        {gates.map((g, i) => (
          <GateCard key={g.id} gate={g} index={i} />
        ))}
      </ol>
      <div className="mt-2 flex items-center justify-center gap-1 text-2xs text-text-muted">
        {gates.map((g, i) => (
          <span key={g.id} className="flex items-center gap-1">
            {i > 0 ? <span aria-hidden>◄</span> : null}
            <span className={g.state === 'passed' ? 'text-accent-green' : g.state === 'blocked' ? 'text-accent-red' : 'text-accent-yellow'}>
              {GATE_SHORT[g.id]}
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}
