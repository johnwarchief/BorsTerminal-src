// features/technical/components/SidebarActiveLevels.tsx -- تب ۳ سایدبار: ترازها و حد ضرر نماد فعال
// فقط نمایشِ دادهٔ سمت سرور (تحلیل FTS) و مقادیر محاسبه‌شده در صفحه؛ بدون fetch.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import { SETUP_FA } from '../lib/levels';

export type ActiveLevelsView = {
  symbol: string;
  zone3340: { lo: number | null; hi: number | null } | null;
  zone61870: { lo: number | null; hi: number | null } | null;
  baseLevel: number | null;
  ma100: number | null;
  swingLow: number | null;
  stop5pct: number | null;
  keyLevels: { type: string; price: number }[];
  stopLoss: number | null;
  lastClose: number | null;
  setups: string[];
  direction: 'bullish' | 'bearish' | 'neutral' | null;
};

const DIR_FA = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی' } as const;

function price(p: number | null | undefined): string {
  return p == null || !Number.isFinite(p) ? '-' : toFaDigits(Math.round(p).toLocaleString('en-US'));
}

function zone(lo: number | null | undefined, hi: number | null | undefined): string {
  if (lo == null || hi == null) return 'بدون داده';
  return `${price(lo)} تا ${price(hi)}`;
}

function Row({ label, value, tone }: { label: string; value: string; tone?: 'green' | 'red' | 'blue' | 'yellow' }) {
  const color = tone === 'green' ? 'text-accent-green' : tone === 'red' ? 'text-accent-red' : tone === 'blue' ? 'text-accent-blue' : tone === 'yellow' ? 'text-accent-yellow' : 'text-text-primary';
  return (
    <div className="flex items-center justify-between gap-2 border-b border-[var(--hairline)] py-1.5 last:border-b-0">
      <dt className="text-[11px] text-text-secondary">{label}</dt>
      <dd className={`num text-xs font-bold ${color}`}>{value}</dd>
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
  const keyRes = active.keyLevels.find((k) => k.type === 'resistance');
  const keySup = active.keyLevels.find((k) => k.type === 'support');

  return (
    <div className="flex flex-col gap-3" data-testid="sidebar-levels">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-sm font-black text-text-primary">{active.symbol}</span>
        {active.direction ? <Badge tone={active.direction === 'bullish' ? 'green' : active.direction === 'bearish' ? 'red' : 'gray'}>{DIR_FA[active.direction]}</Badge> : null}
        {active.setups.length > 0 ? <Badge tone="blue">{toFaDigits(active.setups.length)} ستاپ</Badge> : null}
      </div>

      {active.setups.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {active.setups.map((s) => (
            <Badge key={s} tone="blue">{SETUP_FA[s] ?? s}</Badge>
          ))}
        </div>
      ) : null}

      <dl className="rounded-xl border border-border-c bg-bg-card/40 px-2.5">
        <Row label="کمربند ۳۳-۴۰٪ (لگاریتمی)" value={zone(active.zone3340?.lo, active.zone3340?.hi)} tone="blue" />
        <Row label="کمربند طلایی ۶۱.۸-۷۰٪" value={zone(active.zone61870?.lo, active.zone61870?.hi)} tone="blue" />
        <Row label="تراز مبنا (کف موج ۱.۰)" value={price(active.baseLevel)} />
        <Row label="خط ماژور MA(100)" value={price(active.ma100)} />
        <Row label="آخرین کف سوینگ" value={price(active.swingLow)} />
        <Row label="حد ضرر نوسان‌گیر (−۵٪)" value={price(active.stop5pct)} tone="red" />
        {active.stopLoss != null ? <Row label="حد ضرر سیگنال (MA14)" value={price(active.stopLoss)} tone="red" /> : null}
        {keyRes ? <Row label="مقاومت (خط آبی جت)" value={price(keyRes.price)} tone="green" /> : null}
        {keySup ? <Row label="حمایت ماژور" value={price(keySup.price)} tone="green" /> : null}
        <Row label="آخرین پایانی" value={price(active.lastClose)} />
      </dl>

      <p className="text-[10px] leading-4 text-text-muted">
        مرجع: FTS_SPEC بخش اول (بندهای ۳ و ۵). زون‌ها/ستاپ‌ها از تحلیل سمت سرور؛ حد ضرر نوسان‌گیر ۵٪ زیر آخرین کف سوینگ روند صعودی.
      </p>
    </div>
  );
}
