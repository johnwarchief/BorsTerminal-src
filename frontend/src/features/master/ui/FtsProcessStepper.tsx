// features/master/ui/FtsProcessStepper.tsx — چهار گامِ قیف به‌عنوانِ مسیرِ اصلیِ صفحه
//
// تاریخچۀ رأی‌ها (تا کسی دوباره همان اشتباه را نکند):
//  • ۱۴۰۵-۰۷-۱۹ — کارت‌هایِ ۸×۸ با سطرِ دوم «navigationِ بزرگ» خوانده شد و به چهار
//    برچسبِ فشرده رسیدیم.
//  • ۱۴۰۵-۰۷-۲۱ — همان برچسب‌ها ریز بودند (text-2xs، بی‌عدد).
//  • مأموریتِ ۲۰۲۶-۱۰-۱۸ — مسیر باید *خوانا* باشد: شمارۀ گام، عنوان، توضیحِ
//    یک‌خطی، وضعیت، ورودی/خروجی، و این‌که گامِ جاری کدام است و گامِ بعدی کدام.
// سازش: قدِ دو سطری درِ هر خانه (نه کارتِ بلند، نه برچسبِ ۱۱ پیکسلی)، دو ردیف درِ
// ۱۳۶۶ و یک ردیف درِ ≥۱۲۸۰، و وضعیت با *متن* — رنگ تنها راه تشخیص نیست.
//
// هیچ عددی اینجا حساب نمی‌شود: `counts` همان `countsِ` پاسخِ موتور است که جدول هم
// می‌خواند (یک کلیدِ کوئری، یک درخواست). ورودیِ هر گام = عبوریِ گامِ پیشین درِ
// همان ترتیبِ `flow`، و ورودیِ گامِ اول = جامعۀ غربالگری.
import { Link } from 'react-router';
import { toFaDigits } from '@shared/lib/fmt';
import type { FunnelFlow, FunnelStageKey, StageSummary } from '../lib/ftsFunnel';
import { stageOrderOf } from '../lib/ftsFunnel';

export const FUNNEL_STAGES = [
  { key: 'tape' as FunnelStageKey, index: 1, short: 'S', title: 'تابلوخوانی', page: 'گام ۱' },
  { key: 'technical' as FunnelStageKey, index: 2, short: 'T', title: 'تکنیکال', page: 'گام ۲' },
  { key: 'fundamental' as FunnelStageKey, index: 3, short: 'F', title: 'بنیادی', page: 'گام ۳' },
  { key: 'handover' as FunnelStageKey, index: 4, short: 'M', title: 'تحویل و جمع‌بندی', page: 'گام ۴' },
] as const;

/** یک خطِ توضیح، به زبانِ خودِ برنامه — نه آستانه، نه ادعایِ روشِ تازه. */
const STAGE_DESC: Record<FunnelStageKey, string> = {
  tape: 'فیلترهایِ تابلو رویِ جامعۀ غربالگری',
  technical: 'گیتِ روندِ هفتگی + شرط‌هایِ انتخابیِ شما',
  fundamental: 'پنج شاخصِ بنیادی',
  handover: 'فهرستِ نهایی برایِ پیگیری',
};

/** ترتیبِ تب‌ها از `flowِ` پاسخِ موتور می‌آید، نه از یک فهرستِ دوم: درِ
 *  استراتژیِ «تکنیکال‌محور» گامِ تکنیکال گامِ ۱ است و تابلوخوانی گامِ ۲.
 *  شمارۀ هر تب هم همان‌جا بازنویسی می‌شود تا «گام ۲» دو معنی ندهد. */
export function funnelStagesFor(flow: FunnelFlow = 'tape_first') {
  const order = stageOrderOf(flow);
  return order.map((key, i) => {
    const base = FUNNEL_STAGES.find((s) => s.key === key) ?? FUNNEL_STAGES[0];
    return { ...base, index: i + 1, page: `گام ${toFaDigits(i + 1)}` };
  });
}

export function funnelStagePath(stage: FunnelStageKey, preset?: string, symbol?: string | null) {
  const q = new URLSearchParams({ stage });
  if (preset) q.set('preset', preset);
  if (symbol) q.set('symbol', symbol);
  return `/master?${q.toString()}`;
}

type StageStatus = { text: string; icon: string; tone: string; hint: string };

/** پنج حالتِ جدا — «در انتظار» با «تکمیل‌شده بی‌عبوری» یکی نیست، و «سنجشِ ناتمام»
 *  با «رد» یکی نیست. متن + نشان، تا رنگ تنها حاملِ معنا نماند. */
function stageStatus(s: StageSummary | undefined, state: 'ready' | 'loading' | 'error'): StageStatus {
  if (state === 'error') {
    return { text: 'دارای خطا', icon: '!', tone: 'border-accent-red/60 bg-accent-red/15 text-accent-red',
      hint: 'داوریِ این گام از سرور نرسید — شمارشِ این گام بی‌مدرک است' };
  }
  if (!s) {
    return state === 'loading'
      ? { text: 'در حال اجرا', icon: '◌', tone: 'border-accent-blue/50 bg-accent-blue/10 text-accent-blue',
        hint: 'اولین پاسخِ این گام هنوز نیامده' }
      : { text: 'در انتظار', icon: '○', tone: 'border-border-c bg-bg-primary/60 text-text-secondary',
        hint: 'هنچ داوری‌ای برایِ این گام ثبت نشده' };
  }
  if (s.pending > 0 || s.unavailable > 0) {
    return { text: 'سنجشِ ناتمام', icon: '◐',
      tone: 'border-accent-yellow/60 bg-accent-yellow/15 text-accent-yellow',
      hint: `${toFaDigits(s.pending)} نماد هنوز داوری نشده`
        + (s.unavailable ? ` · ${toFaDigits(s.unavailable)} بی‌منبع` : '') };
  }
  return { text: s.pass > 0 ? 'تکمیل‌شده' : 'تکمیل‌شده · بی‌عبوری', icon: '✓',
    tone: s.pass > 0
      ? 'border-accent-green/60 bg-accent-green/15 text-accent-green'
      : 'border-border-c bg-bg-primary/60 text-text-secondary',
    hint: `${toFaDigits(s.pass)} عبوری · ${toFaDigits(s.reject)} رد` };
}

export function FtsProcessStepper({
  active,
  preset,
  symbol,
  counts,
  inputs,
  flow = 'tape_first',
  state = 'ready',
  universe = 0,
}: {
  active: FunnelStageKey;
  preset?: string;
  symbol?: string | null;
  counts?: Partial<Record<FunnelStageKey, StageSummary>>;
  /** `stages[k].input` ازِ همان پاسخِ موتور. بی‌این، رابط خودش «عبوریِ گامِ پیشین»
   *  را زنجیره می‌کرد و با عددِ خودِ موتور نمی‌خواند (fixture: تابلو ۳ عبور،
   *  ولی تکنیکال `input: 4`) — دو منبعِ عدد برایِ یک خط. */
  inputs?: Partial<Record<FunnelStageKey, number>>;
  flow?: FunnelFlow;
  state?: 'ready' | 'loading' | 'error';
  /** جامعۀ غربالگری — تنها ورودیِ گامِ اول، و فقط وقتی موتور ورودی ندهد */
  universe?: number;
}) {
  const stages = funnelStagesFor(flow);
  const activeIdx = Math.max(0, stages.findIndex((s) => s.key === active));
  const next = stages[activeIdx + 1];
  const inputOf = (key: FunnelStageKey, i: number) => {
    const fromApi = inputs?.[key];
    if (typeof fromApi === 'number') return fromApi;
    if (i === 0) return universe;
    return counts?.[stages[i - 1].key]?.pass ?? 0;
  };
  return (
    <nav aria-label="مراحل غربالگری FTS" data-testid="fts-process-stepper" className="w-full">
      <ol className="grid grid-cols-1 gap-1.5 sm:grid-cols-2 xl:grid-cols-4">
        {stages.map((stage, i) => {
          const sum = counts?.[stage.key];
          const st = stageStatus(sum, state);
          const isActive = stage.key === active;
          const isDone = i < activeIdx;
          const input = inputOf(stage.key, i);
          const output = sum?.pass ?? 0;
          const badgeText = state === 'error' ? '!'
            : (!sum && state === 'loading' ? '…' : toFaDigits(output));
          const badgeTone = state === 'error' ? 'text-accent-red' : '';
          return (
            <li key={stage.key} className="min-w-0">
              <Link
                to={funnelStagePath(stage.key, preset, symbol)}
                aria-current={isActive ? 'step' : undefined}
                data-testid={`fts-step-${stage.key}`}
                title={`${stage.page}: ${stage.title} — ${st.hint}`}
                className={`flex h-full flex-col gap-1 rounded-xl border px-3 py-2 transition-colors ${
                  isActive
                    ? 'border-accent-blue bg-accent-blue/15 ring-1 ring-accent-blue/40'
                    : 'border-border-c bg-bg-card/60 hover:border-accent-blue/50 hover:bg-bg-card'
                }`}
              >
                <span className="flex items-center gap-2">
                  <span aria-hidden
                        className={`num grid h-5 w-5 shrink-0 place-items-center rounded-md border text-2xs font-black ${
                          isActive ? 'border-accent-blue/60 bg-accent-blue/20 text-accent-blue'
                                   : 'border-border-c bg-bg-primary/70 text-text-secondary'}`}>
                    {toFaDigits(stage.index)}
                  </span>
                  <span className={`min-w-0 truncate text-sm font-black ${
                    isActive ? 'text-accent-blue' : 'text-text-primary'}`}>
                    {stage.title}
                  </span>
                  {isActive
                    ? <span className="ms-auto shrink-0 rounded-md border border-accent-blue/50
                                      bg-accent-blue/15 px-1.5 py-0.5 text-2xs font-black text-accent-blue"
                           data-testid={`fts-step-current-${stage.key}`}>گام جاری</span>
                    : isDone
                      ? <span className="ms-auto shrink-0 text-2xs font-bold text-text-muted"
                              title="از این گام گذشته‌اید">گذشته</span>
                      : null}
                </span>
                <span className="text-2xs leading-4 text-text-secondary">{STAGE_DESC[stage.key]}</span>
                <span className="mt-auto flex flex-wrap items-center gap-x-2 gap-y-1">
                  <span data-testid={`fts-step-status-${stage.key}`}
                        className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-2xs font-bold ${st.tone}`}>
                    <span aria-hidden>{st.icon}</span>{st.text}
                  </span>
                  <span className="num inline-flex items-center gap-1 text-2xs font-bold text-text-secondary"
                        data-testid={`fts-step-flow-${stage.key}`}
                        title={sum
                          ? `ورودیِ این گام ${toFaDigits(input)} نماد، عبوری ${toFaDigits(output)}`
                          : 'شمارشِ این گام هنوز ازِ سرور نرسیده'}>
                    <span data-testid={`fts-step-in-${stage.key}`}>{toFaDigits(input)}</span>
                    <span aria-hidden>←</span>
                    {/* سه حالتِ جدا (قفلِ آزمونِ ۱۴۰۵-0۷-۲۱): «…» یعنی بی‌شمارش،
                        «!» یعنی خطا، و عدد یعنی عدد — صفرِ عبوری باِ «هنوز
                        نرسیده» یکی نشود. */}
                    <span className={`text-text-primary ${badgeTone}`}
                          data-testid={`fts-step-count-${stage.key}`}>
                      {badgeText}
                    </span>
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
      <p className="mt-1 text-2xs text-text-secondary" data-testid="fts-stepper-next">
        {next
          ? <>گامِ بعدی: <b className="text-text-primary">{next.title}</b> — {STAGE_DESC[next.key]}</>
          : <>آخرین گام همین است: {stages[activeIdx]?.title ?? ''} — فهرستِ نهاییِ پیگیری</>}
      </p>
    </nav>
  );
}
