// features/technical/components/SidebarActiveLevels.tsx -- تب ۳ سایدبار: ترازها و حد ضرر نماد فعال
// فقط نمایشِ خروجیِ موتور سرور (/api/fts/{symbol})؛ هیچ عددی اینجا بازتولید نمی‌شود.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import { CONTEXT_FA, EXIT_SIGNAL_FA, SETUP_FA, STOP_BASIS_FA } from '../lib/levels';
import { verdictMeta } from './FtsBadgeStrip';

export type ActiveLevelsView = {
  symbol: string;
  /** پیلود تحلیلی سرور؛ null یعنی هنوز تحلیل این نماد نرسیده */
  fts: FtsAnalysisData | null;
  /** میانگین ۱۰۰ بستهٔ آخر (خط ماژور) — null با تاریخچهٔ کوتاه‌تر از ۱۰۰ کندل */
  ma100: number | null;
  lastClose: number | null;
  setups: string[];
  /** «زمینه»ها (کمربند فیبو و…) — ستاپِ ورود نیستند، برای همین جدا نمایش داده می‌شوند */
  context: string[];
  /** زمینهٔ ناظر/رویداد از canonicalِ TSETMC. رأیِ تازه‌ای نیست و درِ هیچ فرمولی
   *  نمی‌نشیند؛ اگر ردیفِ تابلو نرسد null است (نه «سالم»). */
  boardFlags?: {
    stopped?: string | null;
    stopSince?: string | null;
    supervised?: boolean | null;
    recentEvents?: string[] | null;
  } | null;
  direction: 'bullish' | 'bearish' | 'neutral' | null;
};

const DIR_FA = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;

function price(p: number | null | undefined): string {
  return p == null || !Number.isFinite(p) ? 'بدون داده' : toFaDigits(Math.round(p).toLocaleString('en-US'));
}

function zone(lo: number | null | undefined, hi: number | null | undefined): string {
  if (lo == null || hi == null) return 'بدون داده';
  return `${price(lo)} تا ${price(hi)}`;
}

function Row({
  label,
  value,
  tone,
  title,
  testId,
}: {
  label: string;
  value: string;
  tone?: 'green' | 'red' | 'blue' | 'yellow' | 'muted' | 'gray';
  title?: string;
  testId?: string;
}) {
  const color =
    tone === 'green'
      ? 'text-accent-green'
      : tone === 'red'
        ? 'text-accent-red'
        : tone === 'blue'
          ? 'text-accent-blue'
          : tone === 'yellow'
            ? 'text-accent-yellow'
            : tone === 'gray'
              ? 'text-text-secondary'
              : tone === 'muted'
                ? 'text-text-muted'
                : 'text-text-primary';
  return (
    <div
      data-testid={testId}
      title={title}
      className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-1.5 last:border-b-0"
    >
      <dt className="shrink-0 text-[11px] text-text-secondary">{label}</dt>
      <dd className={`num truncate text-xs font-bold ${color}`}>{value}</dd>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="px-0.5 text-[10px] font-bold text-text-muted">{title}</span>
      <dl className="rounded-xl border border-border-c bg-bg-card/40 px-2.5">{children}</dl>
    </div>
  );
}

export function SidebarActiveLevels({ active }: { active: ActiveLevelsView }) {
  if (!active.symbol) {
    return (
      <p className="p-1 text-xs text-text-muted" data-testid="sidebar-levels-empty">
        نمادی انتخاب نشده؛ از تب «دیده‌بان» یک نماد برگزین.
      </p>
    );
  }

  const fts = active.fts;
  const l1 = fts?.exit_engine?.l1 ?? null;
  const basis = l1?.stop_basis ? (STOP_BASIS_FA[l1.stop_basis] ?? null) : null;
  const ma14State =
    l1?.ma14_exit === true
      ? { tone: 'red' as const, text: 'خروج تأیید شد' }
      : l1?.ma14_exit_pending === true
        ? { tone: 'yellow' as const, text: 'کندل اول زیر' }
        : l1?.ma14 != null
          ? { tone: 'green' as const, text: 'داخل روند' }
          : { tone: 'muted' as const, text: 'بدون داده' };
  const signals = (fts?.exit_engine?.signals ?? []).map((s) => EXIT_SIGNAL_FA[s] ?? s);
  const verdict = verdictMeta(fts?.exit_engine?.verdict);
  const neckline = fts?.double_bottom?.neckline ?? null;
  const floor = fts?.point_hunt?.floor_price ?? null;

  return (
    <div className="flex flex-col gap-2" data-testid="sidebar-levels">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-black text-text-primary">{active.symbol}</span>
        {active.direction ? (
          <Badge tone={active.direction === 'bullish' ? 'green' : active.direction === 'bearish' ? 'red' : 'gray'}>
            {DIR_FA[active.direction]}
          </Badge>
        ) : null}
        {active.setups.length > 0 ? <Badge tone="blue">{toFaDigits(active.setups.length)} ستاپ</Badge> : null}
      </div>

      {l1?.stop_hit ? (
        <p className="rounded-lg bg-accent-red/15 px-2 py-1 text-[11px] font-bold text-accent-red" data-testid="levels-stop-hit">
          پایانیِ امروز زیرِ حد ضرر رفته است
        </p>
      ) : null}

      <Section title="حد ضرر به تفکیک سبک">
        <Row
          testId="levels-stop-swing"
          label="نوسان‌گیر"
          value={price(l1?.hard_stop)}
          tone="red"
          title={basis ? `۵٪ ${basis}` : 'حد ضرر سخت از سرور نرسید'}
        />
        <Row
          testId="levels-stop-trend"
          label="روندگیر MA(14)"
          value={`${price(l1?.ma14)} · ${ma14State.text}`}
          tone={ma14State.tone}
          title="جزوه: میانگین متحرک با دورهٔ ۱۴ — هر وقت بدنهٔ کندل کامل زیر آن بسته شد، سیگنال خروج"
        />
        <Row
          testId="levels-stop-fund"
          label="بنیادی"
          value="بدون حد ضرر قیمتی"
          tone="muted"
          title="حکم ۸: تعقیبِ روندِ بنیادی با گزارش‌های فصلی کدال انجام می‌شود، نه با خطِ قیمتی"
        />
      </Section>

      <Section title="موتور خروج FTS">
        <Row
          testId="levels-exit-verdict"
          label="حکم"
          value={verdict.label}
          tone={verdict.tone}
          title={signals.length ? `لایه‌های فعال: ${signals.join(' · ')}` : 'هیچ لایهٔ خروجی فعال نیست'}
        />
        {signals.length > 0 ? (
          <div className="flex flex-wrap gap-1 py-1.5">
            {signals.map((s) => (
              <Badge key={s} tone="yellow">
                {s}
              </Badge>
            ))}
          </div>
        ) : null}
      </Section>

      <Section title="ترازها">
        <Row
          label="کمربند ۳۳–۴۰٪ (لگاریتمی)"
          value={zone(fts?.fib?.zone_33_40?.lo, fts?.fib?.zone_33_40?.hi)}
          tone="blue"
          title={fts?.fib?.zone_33_40?.in_zone ? 'پایانیِ امروز داخل این کمربند است' : 'پایانیِ امروز بیرون از این کمربند'}
        />
        <Row
          label="کمربند طلایی ۶۱.۸–۷۰٪"
          value={zone(fts?.fib?.zone_618_70?.lo, fts?.fib?.zone_618_70?.hi)}
          tone="blue"
          title={fts?.fib?.zone_618_70?.in_zone ? 'پایانیِ امروز داخل این کمربند است' : 'پایانیِ امروز بیرون از این کمربند'}
        />
        <Row label="تراز مبنا (کف موج ۱.۰)" value={price(fts?.fib?.retrace_base_low)} />
        {active.ma100 != null ? <Row label="خط ماژور MA(100)" value={price(active.ma100)} /> : null}
        {fts?.jet?.resistance != null ? (
          <Row
            label="مقاومت (پلکان جت)"
            value={price(fts.jet.resistance)}
            tone={fts.jet.active ? 'green' : undefined}
            title={fts.jet.active ? 'ستاپ جت فعال: پایانی بالای پلکان مقاومت' : 'پلکان هشت‌نقطه‌ایِ مقاومت'}
          />
        ) : null}
        {floor != null ? <Row label="کف کانال (شکار نقطه)" value={price(floor)} /> : null}
        {neckline != null ? <Row label="خط یقهٔ دابل‌باتم" value={price(neckline)} /> : null}
        <Row label="آخرین پایانی" value={price(active.lastClose)} />
      </Section>

      {active.setups.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {active.setups.map((s) => (
            <Badge key={s} tone="blue">
              {SETUP_FA[s] ?? s}
            </Badge>
          ))}
        </div>
      ) : null}

      {active.context.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1" data-testid="sidebar-fts-context">
          <span className="text-[10px] text-text-muted">زمینه:</span>
          {active.context.map((c) => (
            <Badge key={c} tone="gray">
              {CONTEXT_FA[c] ?? c}
            </Badge>
          ))}
        </div>
      ) : null}

      {/* زمینهٔ ناظر/رویداد (TSETMC): فقط اطلاعِ همان چیزی که درِ Inspector کامل
          خوانده می‌شود. نه ستاپِ ورود است، نه رأی، نه وزنِ تازه. */}
      {active.boardFlags && (active.boardFlags.stopped || active.boardFlags.supervised
        || (active.boardFlags.recentEvents?.length ?? 0) > 0) ? (
        <div className="flex flex-wrap items-center gap-1" data-testid="sidebar-board-context">
          <span className="text-[10px] text-text-muted">از تابلو:</span>
          {active.boardFlags.stopped ? (
            <Badge tone="red" title={`متوقف از ${toFaDigits(active.boardFlags.stopSince ?? '')} — جزئیات درِ Inspector`}>
              متوقف
            </Badge>
          ) : null}
          {active.boardFlags.supervised ? (
            <Badge tone="yellow" title="زیرِ نظرِ سازمان — جزئیات درِ Inspector">
              نظارت
            </Badge>
          ) : null}
          {(active.boardFlags.recentEvents ?? []).map((e) => (
            <Badge key={e} tone="blue" title="رویدادِ شرکتیِ مبدأ (TSETMC)">
              {e}
            </Badge>
          ))}
        </div>
      ) : null}

      <p className="text-[10px] leading-4 text-text-muted">
        همهٔ اعداد از تحلیلِ سرورِ همین نماد است (FTS_SPEC بخش اول، بندهای ۳ و ۵). قیمت خریدِ سبد در حد ضرر لحاظ
        می‌شود؛ اگر نماد در سبد نباشد، مبنای حد ضرر کف ۲۰ نشستِ اخیر است.
      </p>
    </div>
  );
}
