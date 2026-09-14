// features/technical/components/FtsTrendPanel.tsx -- کارت تحلیل ساختاری FTS
// روند چند تایم فریمی با سقف/کف پیوت، کمربند های فیبو، ستاپ های برگشتی و
// جزئیات چهار لایه موتور خروج — همه از تحلیل سمت سرور، بدون محاسبه محلی.
import { Badge } from '@shared/components/Badge';
import { toFaDigits, fmtPct } from '@shared/lib/fmt';
import type { FtsAnalysisData } from '../api/useFtsAnalysis';
import { TREND_FA, trendTone, verdictMeta } from './FtsBadgeStrip';

function Row({ label, value, tone }: { label: string; value: string; tone?: 'green' | 'red' | 'yellow' | 'gray' }) {
  const color =
    tone === 'green'
      ? 'text-accent-green'
      : tone === 'red'
        ? 'text-accent-red'
        : tone === 'yellow'
          ? 'text-accent-yellow'
          : 'text-text-primary';
  return (
    <div className="flex justify-between">
      <dt className="text-text-secondary">{label}</dt>
      <dd className={`num font-bold ${color}`}>{value}</dd>
    </div>
  );
}

function fmtPrice(p: number | null | undefined): string {
  return p == null ? '-' : toFaDigits(p.toFixed(0));
}

/** نشان ستاپ های برگشتی: جت/دابل باتم/جعبه رنج/شکار نقطه */
export function setupBadgesOf(f: FtsAnalysisData): { label: string; tone: 'green' | 'blue' | 'gray' }[] {
  const out: { label: string; tone: 'green' | 'blue' | 'gray' }[] = [];
  if (f.jet?.active) out.push({ label: 'جت (شکست مقاومت)', tone: 'green' });
  if (f.double_bottom?.active) out.push({ label: 'دابل باتم', tone: 'green' });
  if (f.range_box?.active) out.push({ label: 'شکست جعبه رنج', tone: 'green' });
  if (f.point_hunt?.active) out.push({ label: 'شکار نقطه', tone: 'blue' });
  if (f.choch?.bullish) out.push({ label: 'CHoCH صعودی', tone: 'green' });
  if (f.choch?.bearish) out.push({ label: 'CHoCH نزولی', tone: 'gray' });
  return out;
}

export function FtsTrendPanel({ data }: { data: FtsAnalysisData | null | undefined }) {
  if (!data) {
    return (
      <div className="glass-panel p-4">
        <h3 className="mb-2 text-sm font-black text-text-primary">تحلیل ساختاری FTS</h3>
        <p className="text-xs text-text-muted">در انتظار داده تحلیل...</p>
      </div>
    );
  }

  const t = data.trend;
  const fib = data.fib;
  const ex = data.exit_engine;
  const l1 = ex?.l1;
  const l4 = ex?.l4;
  const vm = verdictMeta(ex?.verdict);
  const setups = setupBadgesOf(data);

  return (
    <div className="glass-panel flex flex-col gap-3 p-4" data-testid="fts-trend-panel">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-black text-text-primary">تحلیل ساختاری FTS</h3>
        <Badge tone={vm.tone}>موتور خروج: {vm.label}</Badge>
      </div>

      {/* روند چند تایم فریمی با پیوت ها */}
      <div>
        <div className="mb-1.5 text-[11px] font-bold text-text-secondary">روند چند تایم فریمی (ساختار HH/HL)</div>
        <div className="grid grid-cols-3 gap-2">
          {(['D', 'W', 'M'] as const).map((k) => {
            const leg = t?.[k];
            const tr = leg?.trend ?? 'na';
            const tone = trendTone(tr);
            return (
              <div key={k} className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-2">
                <div className="mb-1 flex items-center justify-between">
                  <span className="text-[10px] text-text-muted">{k === 'D' ? 'روزانه' : k === 'W' ? 'هفتگی' : 'ماهانه'}</span>
                  <Badge tone={tone}>{TREND_FA[tr] ?? TREND_FA.na}</Badge>
                </div>
                <div className="flex flex-col gap-0.5 text-[10px] text-text-secondary">
                  <span className="flex justify-between">
                    <span>سقف اخیر</span>
                    <span className="num">{fmtPrice(leg?.last_high)}</span>
                  </span>
                  <span className="flex justify-between">
                    <span>سقف قبل</span>
                    <span className="num">{fmtPrice(leg?.prev_high)}</span>
                  </span>
                  <span className="flex justify-between">
                    <span>کف اخیر</span>
                    <span className="num">{fmtPrice(leg?.last_low)}</span>
                  </span>
                </div>
              </div>
            );
          })}
        </div>
        {t?.alignment === 'up' || t?.alignment === 'down' ? (
          <div className="mt-1.5">
            <Badge tone={t.alignment === 'up' ? 'green' : 'red'}>
              هم راستایی سه تایم فریم: {t.alignment === 'up' ? 'صعودی' : 'نزولی'}
            </Badge>
          </div>
        ) : null}
      </div>

      {/* کمربند های فیبوناچی */}
      <div>
        <div className="mb-1 text-[11px] font-bold text-text-secondary">کمربند های فیبوناچی (مقیاس لگاریتمی)</div>
        {fib ? (
          <div className="grid grid-cols-2 gap-2">
            <div
              className={`rounded-xl border p-2 ${
                fib.zone_33_40?.in_zone ? 'border-border-accent bg-accent-blue/10' : 'border-[var(--hairline)]'
              }`}
            >
              <div className="mb-0.5 flex items-center justify-between text-[10px]">
                <span className="text-text-secondary">اصلاح ۳۳-۴۰٪</span>
                {fib.zone_33_40?.in_zone ? <Badge tone="blue">داخل کمربند</Badge> : null}
              </div>
              <div className="num text-xs font-bold text-text-primary">
                {fmtPrice(fib.zone_33_40?.lo)} تا {fmtPrice(fib.zone_33_40?.hi)}
              </div>
            </div>
            <div
              className={`rounded-xl border p-2 ${
                fib.zone_618_70?.in_zone ? 'border-border-accent bg-accent-blue/10' : 'border-[var(--hairline)]'
              }`}
            >
              <div className="mb-0.5 flex items-center justify-between text-[10px]">
                <span className="text-text-secondary">کمربند طلایی ۶۱.۸-۷۰٪</span>
                {fib.zone_618_70?.in_zone ? <Badge tone="blue">داخل کمربند</Badge> : null}
              </div>
              <div className="num text-xs font-bold text-text-primary">
                {fmtPrice(fib.zone_618_70?.lo)} تا {fmtPrice(fib.zone_618_70?.hi)}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-[10px] text-text-muted">سقف/کف پیوت کافی برای کمربند وجود ندارد</p>
        )}
      </div>

      {/* ستاپ های فعال سمت سرور */}
      <div>
        <div className="mb-1 text-[11px] font-bold text-text-secondary">ستاپ های فعال (موتور سمت سرور)</div>
        {setups.length > 0 ? (
          <div className="flex flex-wrap gap-1">
            {setups.map((s) => (
              <Badge key={s.label} tone={s.tone}>
                {s.label}
              </Badge>
            ))}
          </div>
        ) : (
          <p className="text-[10px] text-text-muted">ستاپ فعالی از موتور سمت سرور گزارش نشده</p>
        )}
      </div>

      {/* جزئیات موتور خروج */}
      <div>
        <div className="mb-1 text-[11px] font-bold text-text-secondary">موتور خروج چهارلایه</div>
        <dl className="flex flex-col gap-1 text-xs">
          <Row
            label="حد ضرر سخت"
            value={fmtPrice(l1?.hard_stop)}
            tone={l1?.stop_hit ? 'red' : undefined}
          />
          <Row label="مبنای حد ضرر" value={l1?.stop_basis === 'swing_low' ? 'کف سوینگ' : l1?.stop_basis ?? '-'} />
          <Row label="MA14 تعقیبی" value={fmtPrice(l1?.ma14)} tone={l1?.ma14_exit ? 'red' : undefined} />
          <Row label="RSI" value={l4?.rsi == null ? '-' : toFaDigits(l4.rsi.toFixed(1))} tone={l4?.rsi_divergence ? 'yellow' : undefined} />
          {ex?.signals && ex.signals.length > 0 ? (
            <div className="mt-1 flex flex-wrap gap-1">
              {ex.signals.map((s) => (
                <Badge key={s} tone="yellow">
                  {s}
                </Badge>
              ))}
            </div>
          ) : null}
        </dl>
      </div>

      {/* شکار نقطه */}
      {data.point_hunt?.active ? (
        <div className="rounded-xl border border-[var(--hairline)] bg-bg-card/40 p-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-[11px] font-bold text-text-secondary">شکار نقطه (کف دایامتریک)</span>
            <Badge tone="blue">{toFaDigits(data.point_hunt.touches ?? 0)} لمس</Badge>
          </div>
          <dl className="flex flex-col gap-1 text-xs">
            <Row label="کف کانال" value={fmtPrice(data.point_hunt.floor_price)} />
          </dl>
        </div>
      ) : null}

      {/* فاصله تا جت و جعبه */}
      {data.jet?.resistance != null && !data.jet.active ? (
        <dl className="flex flex-col gap-1 text-xs">
          <Row
            label="مقاومت جت (آستانه شکست)"
            value={fmtPrice(data.jet.resistance)}
            tone={data.jet.ath ? 'yellow' : undefined}
          />
          <Row label="فاصله پایانی تا مقاومت" value={fmtPct(data.jet.pct_above_res)} tone={(data.jet.pct_above_res ?? 0) >= 0 ? 'green' : undefined} />
        </dl>
      ) : null}
    </div>
  );
}
