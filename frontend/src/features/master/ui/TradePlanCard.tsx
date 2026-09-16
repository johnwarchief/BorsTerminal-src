// features/master/ui/TradePlanCard.tsx -- کارت برنامه معاملاتی (Blueprint)
// حکم نهایی + پارامترهای قیمتی FTS با عدد دقیق ریالی + مدیریت سرمایه.
// داده فیبو/باکس فقط از /api/fts/{symbol} — بازتولید نمی‌شود (Circuit Breaker).
import { Badge } from '@shared/components/Badge';
import { fa1 } from '../lib/fmtNum';
import { rial, type TradePlan } from '../lib/tradePlanMath';

export const ACTION_FA = {
  strong_buy: 'ورود پله‌ای',
  buy: 'ورود پله‌ای',
  hold: 'نگهداری',
  watch: 'زیر نظر',
  reduce: 'خروج/ردشده',
  sell: 'خروج/ردشده',
  strong_sell: 'خروج/ردشده',
  no_data: 'بدون داده',
} as const;

const ACTION_TONE = {
  strong_buy: 'green',
  buy: 'green',
  hold: 'gray',
  watch: 'blue',
  reduce: 'red',
  sell: 'red',
  strong_sell: 'red',
  no_data: 'gray',
} as const;

function LevelRow({
  label,
  hint,
  lo,
  hi,
  tone,
}: {
  label: string;
  hint: string;
  lo: number | null;
  hi: number | null;
  tone: 'green' | 'blue' | 'yellow' | 'red';
}) {
  const has = lo != null || hi != null;
  const toneCls =
    tone === 'green' ? 'text-accent-green' : tone === 'blue' ? 'text-neon-cyan' : tone === 'yellow' ? 'text-accent-yellow' : 'text-accent-red';
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
      <div className="min-w-0">
        <div className="text-xs font-bold text-text-primary">{label}</div>
        <div className="text-2xs leading-4 text-text-muted">{hint}</div>
      </div>
      {/* واحد «ریال» بیرون از ایزولهٔ LTR اعداد می‌ماند تا ترتیب متن مخلوط RTL سالم بماند */}
      <div className={`text-start ${has ? toneCls : 'text-text-muted'}`}>
        {has ? (
          <>
            <span className="num">
              {hi != null && lo != null && hi !== lo ? `${rial(lo)} — ${rial(hi)}` : rial(lo ?? hi)}
            </span>{' '}
            <span className="text-2xs">ریال</span>
          </>
        ) : (
          <span className="text-xs">بدون داده</span>
        )}
      </div>
    </div>
  );
}

export function TradePlanCard({ symbol, action, plan }: { symbol: string; action: keyof typeof ACTION_FA; plan: TradePlan }) {
  return (
    <div className="glass-panel panel-in relative overflow-hidden p-4">
      <div className="pointer-events-none absolute -start-12 -top-12 h-32 w-32 rounded-full bg-neon-cyan/10 blur-3xl" aria-hidden />
      <div className="relative mb-3 flex flex-wrap items-center gap-2">
        <h3 className="text-sm font-black text-text-primary">برنامه معاملاتی {symbol}</h3>
        <Badge tone={ACTION_TONE[action]}>{ACTION_FA[action]}</Badge>
        <span className="text-2xs uppercase tracking-widest text-text-muted">Trade Execution Blueprint</span>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        <LevelRow label="پله اول (DCA 1)" hint="تراز فیبو ۳۳ تا ۴۰ درصد اصلاحی" lo={plan.step1?.lo ?? null} hi={plan.step1?.hi ?? null} tone="green" />
        <LevelRow label="پله دوم (DCA 2)" hint="تراز فیبو ۶۱.۸ تا ۷۰ درصد اصلاحی" lo={plan.step2?.lo ?? null} hi={plan.step2?.hi ?? null} tone="blue" />
        <LevelRow label="پله ورود ستاپ جت" hint="سقف استاتیک — شکست با حجم" lo={plan.breakout?.lo ?? null} hi={null} tone="yellow" />
        <LevelRow label="حد ضرر" hint={plan.stop.basis} lo={plan.stop.price} hi={null} tone="red" />
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--hairline)] pt-3">
        <Badge tone="blue">وزن هر پله: {fa1(plan.weight.pct)}٪ سرمایه</Badge>
        <span className="text-2xs leading-5 text-text-secondary">
          مدیریت سرمایه FTS: ۲ تا ۵ درصد سرمایه در هر پله بر اساس سطح ریسک داوری — مجموع پله‌ها و حد ضرر تصمیم خروج را می‌سازند.
        </span>
      </div>
    </div>
  );
}
