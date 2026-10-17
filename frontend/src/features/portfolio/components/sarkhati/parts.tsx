// features/portfolio/components/sarkhati/parts.tsx — اجزایِ مشترکِ تبِّ «سرخطی»
//
// چرا: شش کارتِ این تب پیش از این هرکدام `rounded-2xl p-2.5` و سرتیترِ خودش را
// جدا می‌نوشت؛ نتیجه شش جعبۀ هم‌اندازه بود و چشم هیچ سلسله‌مراتبی پیدا نمی‌کرد.
// اینجا فاصله، اندازه، و رنگ تنها یک تعریف دارند تا کارت‌ها *یک* صفحه به نظر
// برسند، نه شش ویجتِ الحاقی. هیچ داوریِ داده‌ای در این فایل نیست — فقط پوسته.
//
// دو قاعدۀ خانۀ طراحی که اینجا رعایت می‌شود (و پیش از این نقض می‌شد):
//  • `text-3xs` فقط برچسبِ واحد و تگ است؛ عدد، نامِ نماد و حکم هرگز زیرِ
//    `text-2xs` نمی‌روند (`tokens.css:31-35`).
//  • `.num` داخلِ `<td>` نمی‌نشیند (`index.css:175-180` — inline-block بودنش
//    ستونِ جدول را از شبکه بیرون می‌اندازد)؛ عدد در `<span class="num">` می‌رود.
import type { ReactNode } from 'react';

/** یک بلوکِ هم‌عرض درِ همان سطحِ کارت — کارتِ داخلِ کارت ندارد */
export function Section({ title, sub, right, children, testId, tone = 'default' }: {
  title: string;
  /** یک خطِ زمینه، کنارِ عنوان؛ متنِ طولانی به اینجا نمی‌آید */
  sub?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  testId?: string;
  tone?: 'default' | 'alarm' | 'quiet';
}) {
  const edge = tone === 'alarm' ? 'border-accent-red/35' : tone === 'quiet'
    ? 'border-border-c/45' : 'border-border-c/70';
  return (
    <section
      data-testid={testId}
      className={`rounded-xl border ${edge} bg-bg-card/25 px-3 py-2.5`}
    >
      <header className="mb-2 flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h4 className="text-xs font-black leading-4 text-text-primary">{title}</h4>
        {sub ? <span className="text-2xs text-text-muted">{sub}</span> : null}
        {right ? <div className="ms-auto flex flex-wrap items-center gap-1.5">{right}</div> : null}
      </header>
      {children}
    </section>
  );
}

/** برچسب + مقدار در یک خط؛ مقدار همیشه در لبه‌ای که چشم می‌خواند */
export function Field({ label, value, hint, wide = false }: {
  label: string; value: ReactNode; hint?: string; wide?: boolean;
}) {
  return (
    <div className={`flex min-w-0 flex-wrap items-baseline gap-1.5 ${wide ? 'basis-full' : ''}`}
      title={hint}>
      <span className="text-3xs text-text-muted">{label}</span>
      <span className="min-w-0 text-2xs font-bold text-text-primary">{value}</span>
    </div>
  );
}

/** چیپِ وضعیت: واژه + رنگ، بی‌متنِ توضیحی (توضیح در `title` می‌ماند) */
export function Chip({ tone, children, title, testId }: {
  tone: 'ok' | 'warn' | 'bad' | 'idle' | 'live';
  children: ReactNode; title?: string; testId?: string;
}) {
  const skin: Record<string, string> = {
    ok: 'border-accent-green/40 bg-accent-green/12 text-accent-green',
    warn: 'border-accent-yellow/40 bg-accent-yellow/12 text-accent-yellow',
    bad: 'border-accent-red/45 bg-accent-red/12 text-accent-red',
    idle: 'border-border-c bg-bg-card/70 text-text-secondary',
    live: 'border-neon-cyan/45 bg-neon-cyan/12 text-neon-cyan',
  };
  return (
    <span data-testid={testId} title={title}
      className={`inline-flex shrink-0 items-center gap-1 rounded-md border px-1.5 py-[1px]
        text-3xs font-black leading-4 ${skin[tone]}`}>
      {children}
    </span>
  );
}

// حلقۀِ فوکوس را خودِ رابط نمی‌کشد: `index.css:129` همه‌جا `outline: 2px solid
// var(--focus-ring)` را رویِ `:focus-visible` گذاشته است و افزودنش اینجا فقط
// پهنایِ همان حلقه را بی‌رنگ دوباره بیان می‌کند.
const BTN = 'inline-flex min-h-[26px] items-center justify-center gap-1 rounded-md border px-2 '
  + 'text-2xs font-bold transition-colors disabled:cursor-not-allowed disabled:opacity-40';

export function GhostBtn(props: {
  onClick: () => void; disabled?: boolean; testId: string; title?: string; children: ReactNode;
}) {
  return (
    <button type="button" onClick={props.onClick} disabled={props.disabled}
      data-testid={props.testId} title={props.title}
      className={`${BTN} border-border-c bg-bg-primary/40 text-text-secondary hover:border-border-accent hover:text-accent-blue`}>
      {props.children}
    </button>
  );
}

export function DangerBtn(props: {
  onClick: () => void; disabled?: boolean; testId: string; title?: string; children: ReactNode;
}) {
  return (
    <button type="button" onClick={props.onClick} disabled={props.disabled}
      data-testid={props.testId} title={props.title}
      className={`${BTN} border-accent-red/45 bg-accent-red/10 text-accent-red hover:bg-accent-red/20`}>
      {props.children}
    </button>
  );
}

export function LiveBtn(props: {
  onClick: () => void; disabled?: boolean; testId: string; title?: string; children: ReactNode;
}) {
  return (
    <button type="button" onClick={props.onClick} disabled={props.disabled}
      data-testid={props.testId} title={props.title}
      className={`${BTN} border-neon-cyan/50 bg-neon-cyan/12 text-neon-cyan hover:bg-neon-cyan/20`}>
      {props.children}
    </button>
  );
}

/** خطِ خالی / خطا / راهنما — هرکدام یک کار: دعوت به اقدام، یا گفتنِ راهِ حل */
export function Line({ kind = 'muted', testId, children }: {
  kind?: 'muted' | 'error' | 'warn' | 'ok'; testId?: string; children: ReactNode;
}) {
  const skin = {
    muted: 'text-text-muted', error: 'text-accent-red', warn: 'text-accent-yellow',
    ok: 'text-accent-green',
  }[kind];
  return (
    <p data-testid={testId} className={`text-2xs leading-5 ${skin}`}>{children}</p>
  );
}

/** ردیفِ جدول: نوارِ تیرهٔ متناوب رویِ <tr> است، نه <td> — `odd:` رویِ سلول
 *  زوج/فردِ ستون را می‌شمارد و راه‌راهِ کج می‌سازد. */
export function Tr({ children, testId }: { children: ReactNode; testId?: string }) {
  return (
    <tr data-testid={testId} className="align-top odd:bg-bg-card/25 hover:bg-bg-secondary/60">
      {children}
    </tr>
  );
}

/** جدولِ ساده با سرستون چسبان و ردیفِ فردِ کمی تیره‌تر */
export function Table({ head, children, testId, minWidth = 560 }: {
  head: string[]; children: ReactNode; testId: string; minWidth?: number;
}) {
  return (
    <div className="sk-scroll -mx-1 max-h-[52vh] overflow-auto rounded-lg border border-border-c/50">
      <table className="w-full border-collapse text-2xs" data-testid={testId}
        style={{ minWidth }}>
        <thead className="sticky top-0 z-10 bg-bg-secondary/95 backdrop-blur-[2px]">
          <tr>
            {head.map((h) => (
              <th key={h} scope="col"
                className="border-b border-border-c/70 px-2 py-1 text-start text-3xs font-black text-text-muted">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

export function Td({ children, num = false, strong = false, tone, className = '' }: {
  children?: ReactNode; num?: boolean; strong?: boolean;
  tone?: 'muted' | 'bad' | 'ok' | 'warn'; className?: string;
}) {
  const t = tone === 'bad' ? 'text-accent-red' : tone === 'ok' ? 'text-accent-green'
    : tone === 'warn' ? 'text-accent-yellow' : tone === 'muted' ? 'text-text-muted' : '';
  return (
    <td className={`border-b border-border-c/30 px-2 py-1 ${t} ${className}`}>
      {num
        ? <span className={`num ${strong ? 'font-black' : 'font-semibold'} text-text-primary`}>{children}</span>
        : strong
          ? <span className="font-black text-text-primary">{children}</span>
          : children}
    </td>
  );
}

/** اسکلتونِ بارگذاری: همان ارتفاعِ محتوا، تا چیدمان موقع رسیدنِ داده نپرد */
export function Skeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="flex flex-col gap-1.5" data-testid="sarkhati-skeleton" aria-hidden="true">
      {Array.from({ length: lines }).map((_, i) => (
        <div key={i} className="h-3 animate-pulse rounded bg-bg-card/60"
          style={{ width: `${88 - i * 12}%` }} />
      ))}
    </div>
  );
}

/** متنِ مرجع پشتِ بازشو — همان الگویِ `exec-detail-toggle`: لینکِ آبِی، بی‌علامت.
 *  چرا: مالک «کوتاه‌ترش بکن» را برایِ ارتفاعِ پنل می‌گوید، نه برایِ حذفِ توضیح؛
 *  پس توضیح می‌ماند ولی ازِ راهِ خواندنِ روزمره بیرون می‌رود. */
export function Note({ label, testId, children }: {
  label: string; testId: string; children: ReactNode;
}) {
  return (
    <details className="text-3xs text-text-muted" data-testid={testId}>
      <summary className="cursor-pointer font-bold text-accent-blue">{label}</summary>
      <div className="mt-1 leading-5">{children}</div>
    </details>
  );
}
