// features/master/ui/TradeBlueprint.tsx -- ماشین‌حساب برنامهٔ معاملاتی و DCA
// ارزش ریالی (تومان) و تعداد برگهٔ هر پله بر مبنای سقف وزن صنعت؛ ورود جت؛ حد ضرر؛ نسبت R/R؛
// سوییچ اهرم ساعت شنی؛ سقف رژیم جنگی؛ خروج ۵۰٪؛ و اکشن‌های «ثبت پله در سبد» / «واچ‌لیست تحت نظر».
// نبود داده ⇒ «بدون داده» صادقانه (Circuit Breaker).
import { useState } from 'react';
import { useNavigate } from 'react-router';
import { Badge } from '@shared/components/Badge';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { useSaveBasketDecision } from '@features/portfolio/api/useSymbolBasket';
import { toman, type BlueprintResult } from '../lib/dcaCalc';
import { DEFAULT_ASSUMED_CAPITAL, fa0, fa1 } from '../lib/fmtNum';
import type { HourglassSwitch } from '../lib/strictGates';
import type { HalfExitPlan } from '../lib/managementSummary';
import { useCapitalStore } from '../stores/capitalStore';

export type TradeBlueprintProps = {
  symbol: string;
  plan: BlueprintResult;
  hourglass: HourglassSwitch;
  halfExit: HalfExitPlan;
  superFundamental: boolean;
  warRegime: boolean;
  /** سرمایهٔ نمایش‌داده‌شده فرضی است؟ (کاربر چیزی ثبت نکرده) */
  assumedCapital: boolean;
  onToggleWarRegime: (v: boolean) => void;
  horizon?: 'swing' | 'trend' | 'hourglass';
};

export function TradeBlueprint({
  symbol,
  plan,
  hourglass,
  halfExit,
  superFundamental,
  warRegime,
  assumedCapital,
  onToggleWarRegime,
  horizon,
}: TradeBlueprintProps) {
  const navigate = useNavigate();
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const saveDecision = useSaveBasketDecision();
  const totalToman = useCapitalStore((s) => s.totalToman);
  const cashToman = useCapitalStore((s) => s.cashToman);
  const setTotalToman = useCapitalStore((s) => s.setTotalToman);
  const setCashToman = useCapitalStore((s) => s.setCashToman);
  const [draft, setDraft] = useState(totalToman > 0 ? String(totalToman) : String(DEFAULT_ASSUMED_CAPITAL));
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const onRegisterStep = async () => {
    setActionMsg(null);
    try {
      await saveDecision.mutateAsync({
        symbol,
        status: 'accept',
        weightPct: plan.effectiveStepWeightPct ?? 0,
        stopLoss: plan.stop.price,
        note: `ثبت پله از تب ایجنت ارشد${plan.effectiveStepWeightPct != null ? ` · وزن ${plan.effectiveStepWeightPct}٪` : ''}`,
      });
      setSymbol(symbol);
      setActionMsg('پله در سبد ثبت شد؛ به تب مدیریت پرتفوی منتقل می‌شوی.');
      navigate('/portfolio');
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : 'ثبت پله ناموفق بود.');
    }
  };

  const onAddWatch = async () => {
    setActionMsg(null);
    try {
      await saveDecision.mutateAsync({ symbol, status: 'monitor', note: 'واچ‌لیست تحت نظر از تب ایجنت ارشد' });
      setActionMsg('نماد در واچ‌لیست «زیر نظر» ثبت شد.');
    } catch (e) {
      setActionMsg(e instanceof Error ? e.message : 'ثبت واچ‌لیست ناموفق بود.');
    }
  };

  const busy = saveDecision.isPending;

  return (
    <section className="glass-panel relative overflow-hidden p-4" aria-label="برنامه معاملاتی و ماشین‌حساب DCA">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-black text-text-primary">ماشین‌حساب برنامهٔ معاملاتی و DCA</h3>
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone={assumedCapital ? 'yellow' : 'blue'}>
            {plan.hasCapital
              ? `${assumedCapital ? 'سرمایهٔ فرضی' : 'سرمایه'} ${toman(plan.capitalToman)} تومان`
              : 'سرمایه ثبت نشده'}
          </Badge>
          <Badge tone="gray">سقف صنعت {fa0(plan.industryCapPct)}٪</Badge>
          {plan.industryRemainingPct != null ? (
            <Badge tone={plan.industryRemainingPct > 0 ? 'green' : 'red'}>
              ظرفیت صنعت {fa1(plan.industryRemainingPct)}٪
            </Badge>
          ) : null}
        </div>
      </div>

      {/* ثبت سرمایه/نقدینگی + رژیم ریسک */}
      <div className="mb-3 flex flex-wrap items-end gap-2 rounded-xl border border-dashed border-border-c bg-bg-secondary/40 p-2">
        <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
          سرمایهٔ کل (تومان)
          <input
            type="number"
            min={0}
            step={1_000_000}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => setTotalToman(Number(draft))}
            aria-label="سرمایهٔ کل (تومان)"
            dir="ltr"
            placeholder={`پیش‌فرض ${DEFAULT_ASSUMED_CAPITAL}`}
            className="num w-40 rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-start text-xs text-text-primary outline-none focus:border-border-accent"
          />
        </label>
        <label className="flex flex-col gap-1 text-2xs font-bold text-text-secondary">
          نقدینگی آزاد (تومان)
          <input
            type="number"
            min={0}
            step={1_000_000}
            defaultValue={cashToman > 0 ? cashToman : ''}
            onBlur={(e) => setCashToman(Number(e.target.value))}
            aria-label="نقدینگی آزاد (تومان)"
            dir="ltr"
            placeholder="اختیاری"
            className="num w-40 rounded-lg border border-border-c bg-bg-secondary px-2 py-1.5 text-start text-xs text-text-primary outline-none focus:border-border-accent"
          />
        </label>
        <button
          type="button"
          onClick={() => onToggleWarRegime(!warRegime)}
          aria-pressed={warRegime}
          className={`rounded-full border px-3 py-1.5 text-2xs font-bold transition-colors duration-200 ${
            warRegime
              ? 'border-accent-red/50 bg-accent-red/15 text-accent-red'
              : 'border-border-c bg-bg-card text-text-secondary hover:text-text-primary'
          }`}
        >
          رژیم ریسک/جنگ {warRegime ? 'فعال' : 'غیرفعال'}
        </button>
        <span className="text-2xs leading-5 text-text-muted">
          {assumedCapital
            ? `سرمایهٔ فرضی پیش‌فرض ${toman(DEFAULT_ASSUMED_CAPITAL)} تومان در نظر گرفته شد تا پله‌ها فوراً محاسبه شوند؛ همین اینپوت قابل ویرایش آنی است.`
            : plan.industryRemainingPct != null
              ? 'ظرفیت باقی‌ماندهٔ صنعت و سقف ریسک، وزن هر پله را محدود می‌کند.'
              : 'وزن هر پله از سطح ریسک استخراج شده است.'}
        </span>
      </div>

      {warRegime ? (
        <div className="mb-3 rounded-xl border border-accent-red/40 bg-accent-red/10 px-3 py-2 text-2xs leading-5 text-accent-red">
          رژیم ریسک/جنگ فعال ⇒ سقف ورود به سهام ۱۰٪ تا ۲۰٪ کل سرمایه و هشدار پوشش طلا/دلار (۲ تا ۳ برابر ارزش بورسی) اعمال می‌شود.
        </div>
      ) : null}

      {/* پله‌ها: ارزش ریالی + تعداد برگه */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-xs">
          <thead>
            <tr className="bg-bg-card/70 text-start text-2xs uppercase tracking-wider text-text-secondary">
              <th className="px-3 py-2 font-bold">پله</th>
              <th className="px-3 py-2 font-bold">قیمت مرجع بازه</th>
              <th className="px-3 py-2 font-bold">وزن مؤثر</th>
              <th className="px-3 py-2 font-bold">مبلغ (تومان)</th>
              <th className="px-3 py-2 font-bold">تعداد برگه</th>
            </tr>
          </thead>
          <tbody>
            {plan.steps.map((s) => (
              <tr key={s.key} className="border-b border-[var(--hairline)] odd:bg-bg-secondary/40">
                <td className="px-3 py-2 font-bold text-text-primary">{s.label}</td>
                <td className="px-3 py-2">
                  {s.refPrice != null ? <span className="num text-text-secondary">{fa0(s.refPrice)}</span> : <span className="text-text-muted">بدون داده</span>}
                </td>
                <td className="px-3 py-2">
                  {s.weightPct != null ? <span className="num text-text-primary">{fa1(s.weightPct)}٪</span> : <span className="text-text-muted">—</span>}
                </td>
                <td className="px-3 py-2">
                  {s.amountToman != null ? <span className="num text-text-primary">{toman(s.amountToman)}</span> : <span className="text-text-muted">بدون داده</span>}
                </td>
                <td className="px-3 py-2">
                  {s.shares != null ? <span className="num text-text-primary">{fa0(s.shares)}</span> : <span className="text-text-muted">بدون داده</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* حد ضرر و R/R */}
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <div className="rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
          <div className="text-2xs font-bold text-text-primary">حد ضرر</div>
          <div className="text-2xs leading-5 text-text-secondary">{plan.stop.basis}</div>
          <div className="mt-0.5 flex flex-wrap items-center gap-2">
            <span className="num text-2xs text-text-muted">
              −۵٪ از ورود: {plan.stop.fromPct5 != null ? fa0(plan.stop.fromPct5) : 'بدون داده'}
            </span>
            <span className="num text-2xs text-text-muted">
              کف ماژور: {plan.stop.priceAction != null ? 'ثبت‌شده (کارت بالا)' : 'بدون داده'}
            </span>
          </div>
        </div>
        <div className="rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
          <div className="text-2xs font-bold text-text-primary">نسبت R/R</div>
          <div className="mt-0.5">
            {plan.rr != null ? (
              <span className="num text-sm font-black text-accent-green">{fa1(plan.rr)}</span>
            ) : (
              <span className="text-2xs text-text-muted">بدون داده (مقاومت/ورود ناقص)</span>
            )}
          </div>
          <div className="text-2xs leading-5 text-text-muted">
            {plan.resistance != null && plan.steps[0]?.refPrice != null && plan.resistance > plan.steps[0].refPrice
              ? `تا اولین مقاومت استاتیک (${fa0(plan.resistance)} ریال)`
              : 'بر مبنای تارگت پیش‌فرض ستاپ جت (+۲۰٪)'}
          </div>
        </div>
        <div className="rounded-xl border border-[var(--hairline)] bg-bg-secondary/40 px-3 py-2">
          <div className="text-2xs font-bold text-text-primary">
            {horizon === 'swing'
              ? 'افق زمانی نوسانی'
              : horizon === 'trend'
                ? 'افق زمانی روندی'
                : 'سوییچ اهرم ساعت شنی'}
          </div>
          <div className="mt-0.5 flex items-center gap-2">
            <span
              className={`inline-block h-2 w-2 rounded-full ${hourglass.active ? 'bg-accent-green shadow-[0_0_8px_var(--accent-green)]' : 'bg-border-c'}`}
              aria-hidden
            />
            <span className={`text-2xs font-bold ${hourglass.active ? 'text-accent-green' : 'text-text-muted'}`}>
              {hourglass.active ? 'روشن' : 'خاموش'}
              {hourglass.active && hourglass.volumeMultiple != null ? ` · حجم ${fa1(hourglass.volumeMultiple)}×` : ''}
            </span>
            {!superFundamental ? <Badge tone="gray">سوپر‌بنیادی نیست</Badge> : null}
          </div>
          <div className="text-2xs leading-5 text-text-muted">
            {horizon !== 'hourglass' && !superFundamental
              ? `سهم سوپربنیادی نیست؛ افق جاری: ${horizon === 'swing' ? 'کوتاه‌مدت نوسانی' : 'میان‌مدت روندی'}. سوییچ ساعت شنی غیرفعال است.`
              : hourglass.reason}
          </div>
        </div>
      </div>

      {/* خروج ۵۰٪ متناسب با افق استراتژی انتخابی */}
      <div
        className={`mt-3 rounded-xl border px-3 py-2 ${
          halfExit.active ? 'border-accent-green/40 bg-accent-green/10' : 'border-[var(--hairline)] bg-bg-secondary/40'
        }`}
      >
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-2xs font-black text-text-primary">
            {horizon === 'swing'
              ? 'پلن خروج نوسانی (تارگتِ اولین سقف، بدون نگهداری)'
              : horizon === 'hourglass'
                ? 'استراتژی ساعت شنی (افق بلندمدت)'
                : 'خروج ۵۰٪ (اصل پول + حفظ نیم سود)'}
          </span>
          <Badge tone={halfExit.active ? 'green' : 'gray'}>{halfExit.active ? 'فعال' : 'غیرفعال'}</Badge>
        </div>
        <p className="mt-0.5 text-2xs leading-5 text-text-secondary">{halfExit.text}</p>
      </div>

      {plan.notes.length > 0 ? (
        <ul className="mt-2 flex list-inside list-disc flex-col gap-0.5">
          {plan.notes.map((n, i) => (
            <li key={i} className="text-2xs leading-5 text-text-muted">
              {n}
            </li>
          ))}
        </ul>
      ) : null}

      {/* اکشن‌ها */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-[var(--hairline)] pt-3">
        <button
          type="button"
          onClick={onRegisterStep}
          disabled={busy}
          className="rounded-full border border-accent-green/40 bg-accent-green/15 px-3 py-1.5 text-2xs font-bold text-accent-green hover:bg-accent-green/25 disabled:opacity-60"
        >
          {saveDecision.isPending ? 'در حال ثبت…' : 'ثبت پله در سبد'}
        </button>
        <button
          type="button"
          onClick={onAddWatch}
          disabled={busy}
          className="rounded-full border border-border-c bg-bg-card px-3 py-1.5 text-2xs font-bold text-text-secondary hover:border-border-accent hover:text-text-primary disabled:opacity-60"
        >
          افزودن به واچ‌لیست تحت نظر
        </button>
        {actionMsg ? <span className="text-2xs font-bold text-accent-blue">{actionMsg}</span> : null}
      </div>
    </section>
  );
}
