// features/master/ui/ExplainableAuditBox.tsx -- باکس ممیزی شروط و دلایل توقف
// [دلایل توقف و ممیزی شروط] (Explainable Decision Audit)
// تحلیل صادقانه، شفاف و بازاری: چرا ورود مجاز نیست؟ سد پیش‌رو چیست؟ مقاومت استاتیک چقدر فاصله دارد؟
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { fa0, fa1 } from '../lib/fmtNum';
import type { DefiniteDecision, StrictGatesResult } from '../lib/strictGates';

export type ExplainableAuditBoxProps = {
  symbol: string;
  isVeto: boolean;
  decision: DefiniteDecision;
  strict: StrictGatesResult;
  currentPrice?: number | null;
  resistancePrice?: number | null;
  supportPrice?: number | null;
  fundScore?: number | null;
  compact?: boolean;
};

export function ExplainableAuditBox({
  symbol: _symbol,
  isVeto,
  decision,
  strict,
  currentPrice,
  resistancePrice,
  supportPrice,
  fundScore,
  compact = false,
}: ExplainableAuditBoxProps) {
  const blockers = strict.gates.filter((g) => g.state !== 'passed');
  const allPassed = decision.allGatesPassed;

  // محاسبه فاصله تا مقاومت
  const cur = currentPrice != null && currentPrice > 0 ? currentPrice : null;
  const res = resistancePrice != null && resistancePrice > 0 ? resistancePrice : null;
  const distRials = cur != null && res != null ? res - cur : null;
  const distPct = cur != null && distRials != null ? (distRials / cur) * 100 : null;
  const isNearResistance = distPct != null && distPct > 0 && distPct < 5;

  const borderTone = isVeto
    ? 'border-accent-red/50 bg-accent-red/5'
    : allPassed
      ? 'border-accent-green/50 bg-accent-green/5'
      : 'border-accent-yellow/50 bg-accent-yellow/5';

  return (
    <section
      aria-label="دلایل توقف و ممیزی شروط"
      className={`glass-panel relative overflow-hidden rounded-xl border p-4 ${borderTone}`}
    >
      {/* سربرگ */}
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-[var(--hairline)] pb-2.5">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-md bg-bg-card text-xs font-black text-accent-blue">
            ⚖
          </span>
          <h3 className="text-xs font-black text-text-primary">
            دلایل توقف و ممیزی شروط (Explainable Decision Audit)
          </h3>
        </div>
        <div className="flex items-center gap-2">
          {isVeto ? (
            <Badge tone="red">ورود مسدود (توقف در فیلترها)</Badge>
          ) : allPassed ? (
            <Badge tone="green">ورود مجاز (هر ۴ فیلتر سبز)</Badge>
          ) : (
            <Badge tone="yellow">در انتظار تریگر</Badge>
          )}
          {fundScore != null && (
            <span className="num text-2xs font-bold text-text-muted">
              نمره بنیاد: {toFaDigits(fundScore)}
            </span>
          )}
        </div>
      </div>

      {/* ۳ بخش تشریحی بازارمحور */}
      <div className={`grid gap-3 ${compact ? 'grid-cols-1' : 'grid-cols-1 md:grid-cols-3'}`}>
        {/* ۱. چرایی وضعیت ورود */}
        <div className="rounded-lg border border-[var(--hairline)] bg-bg-secondary/40 p-2.5">
          <div className="mb-1 text-2xs font-black text-text-secondary">
            ۱. چرا ورود مجاز یا متوقف است؟
          </div>
          <p className="text-2xs leading-5 text-text-primary">
            {isVeto
              ? `${decision.label}: تا رفع موانع و ثبت تاییدیه فیلترهای بنیاد و تکنیکال، نمره تجمیعی فاقد اعتبار است و ورود روندی اکیداً متوقف می‌باشد.`
              : allPassed
                ? 'تمامی فیلترهای ۴گانه (بنیاد، تکنیکال، تابلو و سبد) هم‌پوشانی دارند؛ شرایط ورود پله‌ای طبق پلن معاملاتی مجاز است.'
                : decision.reason}
          </p>
        </div>

        {/* ۲. سد پیش‌رو و ممیزی فیلترها */}
        <div className="rounded-lg border border-[var(--hairline)] bg-bg-secondary/40 p-2.5">
          <div className="mb-1 text-2xs font-black text-text-secondary">
            ۲. سد پیش‌رو چیست؟
          </div>
          {blockers.length === 0 ? (
            <p className="text-2xs leading-5 text-accent-green font-bold">
              هیچ سدی در فیلترهای ۴گانه مشاهده نمی‌شود؛ مسیر حرکت هموار است.
            </p>
          ) : (
            <ul className="flex flex-col gap-1 text-2xs leading-5 text-text-primary">
              {blockers.map((b) => (
                <li key={b.id} className="flex items-start gap-1">
                  <span className="text-accent-red font-bold shrink-0">●</span>
                  <span>
                    <strong className="text-text-primary">{b.label}:</strong> {b.reason}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>

        {/* ۳. مقاومت استاتیک و حد ضرر */}
        <div className="rounded-lg border border-[var(--hairline)] bg-bg-secondary/40 p-2.5">
          <div className="mb-1 text-2xs font-black text-text-secondary">
            ۳. مقاومت استاتیک و فاصله
          </div>
          <div className="flex flex-col gap-1 text-2xs leading-5 text-text-primary">
            {res != null && cur != null ? (
              distRials != null && distRials > 0 ? (
                <>
                  <div>
                    مقاومت اول:{' '}
                    <strong className="num text-text-primary">{fa0(res)} ریال</strong>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <span>فاصله:</span>
                    <strong className="num text-accent-blue">{fa0(distRials)} ریال</strong>
                    <span className="num font-bold text-accent-yellow">({fa1(distPct ?? 0)}٪)</span>
                  </div>
                  {isNearResistance ? (
                    <span className="text-accent-red font-bold">
                      ⚠ هشدار: فاصله کمتر از ۵٪ به مقاومت؛ ریسک بازگشت بالا و R/R نامساعد.
                    </span>
                  ) : (
                    <span className="text-text-muted">
                      فاصله تا سد مقاومت برای معامله کفایت می‌کند.
                    </span>
                  )}
                </>
              ) : (
                <div>
                  قیمت ({fa0(cur)} ریال) در تراز مقاومت ({fa0(res)} ریال) یا بالاتر از آن است.
                </div>
              )
            ) : res != null ? (
              <div>
                تراز مقاومت استاتیک:{' '}
                <strong className="num text-text-primary">{fa0(res)} ریال</strong>
              </div>
            ) : (
              <span className="text-text-muted">
                مقاومت استاتیک ثبت‌نشده؛ مبنا تارگت پیش‌فرض ستاپ (+۲۰٪) است.
              </span>
            )}

            {supportPrice != null && (
              <div className="mt-1 border-t border-[var(--hairline)] pt-1 text-text-muted">
                کف حمایتی / حد ضرر:{' '}
                <span className="num font-bold text-accent-red">{fa0(supportPrice)} ریال</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
