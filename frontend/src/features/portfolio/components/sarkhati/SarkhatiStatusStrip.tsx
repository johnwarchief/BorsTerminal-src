// features/portfolio/components/sarkhati/SarkhatiStatusStrip.tsx — خطِ وضعیتِ
// همیشه‌دیدنیِ تبِّ «سرخطی»
//
// هرچی اینجا هست ازِ `/api/execution/status` و `/api/execution/connect` است.
// دو چیز عمداً **نیست**:
//  • «نتیجۀ آخرین عملیات» — آن خط درِ همان مؤلفه‌ای است که عمل را انجام داده
//    (پنلِ سفارش، کارتِ پیگیری). نوشتنِ دوباره‌اش اینجا یعنی دو خوانش از یکِ
//    پاسخ، همان بیماری‌ای که درِ «نبض بازار» دیدیم.
//  • رنگِ «متصل» بی‌شاهد: نشستِ بدل باِ `live_enabled: false` خاکستری می‌ماند.
import { Badge } from '@shared/components/Badge';
import { toFaDigits } from '@shared/lib/fmt';
import type { TradingGate } from '../../lib/orderClient';

const MODE_LABEL: Record<string, string> = {
  mock: 'بدلِ سرویس (mock)',
  dry_run: 'مسیرِ بی‌ترافیک (dry_run)',
  live: 'واقعی (live)',
  paper: 'کاغذی (paper)',
  backtest: 'بک‌تست',
};

type ModeCell = { implemented?: boolean | null; active?: boolean | null;
  door?: string | null; can_reach_broker?: boolean | null };

export function SarkhatiStatusStrip({ gate }: { gate: TradingGate }) {
  const st = gate.status;
  const modes = (st?.mode_matrix ?? {}) as Record<string, ModeCell>;
  const caps = gate.caps;
  return (
    <div className="glass-panel flex flex-col gap-1.5 rounded-2xl p-2.5"
      data-testid="sarkhati-status-strip"
      data-session={gate.sessionState}
      data-live={st?.live_enabled === true ? 'true' : 'false'}
      data-halted={gate.halted ? 'true' : 'false'}>
      <div className="flex flex-wrap items-center gap-1.5">
        <Badge tone={gate.endpointPresent ? (gate.canTrade ? 'green' : 'yellow') : 'gray'}>
          {gate.endpointPresent
            ? `سرویسِ اجرا: ${st?.adapter ?? '—'}${gate.dryRun ? ' · بدل' : ''}`
            : 'سرویسِ اجرا نیست'}
        </Badge>
        <Badge tone={gate.sessionState === 'connected'
          ? (st?.live_enabled === true ? 'green' : 'gray')
          : gate.sessionState === 'expired' || gate.sessionState === 'auth_failed' ? 'yellow'
            : gate.sessionState === 'unknown' ? 'gray' : 'red'}>
          {st?.session?.account_label
            ? `${String(st.session.account_label)} · نشستِ ${gate.sessionState === 'connected' && st.live_enabled !== true ? 'بدل' : 'زنده'}`
            : 'نشست'}
        </Badge>
        <Badge tone={gate.halted ? 'red' : 'gray'}>
          {gate.halted ? `توقفِ اضطراری${st?.kill_reason ? `: ${st.kill_reason}` : ''}` : 'مسیر باز است'}
        </Badge>
        {st?.nothing_will_leave_the_machine === true ? (
          <Badge tone="green" title="از پاسخِ خودِ سرویس، نه از متنِ رابط">
            هیچ درخواستی از این ماشین بیرون نمی‌رود
          </Badge>
        ) : null}
        {st?.wire_hypothesis === true ? (
          <Badge tone="yellow" title="سیمِ سفارش از پنج منبعِ عمومی استخراج شده و علیه کارگزاری تأیید نشده">
            سیم: فرضیۀ تأییدنشده
          </Badge>
        ) : null}
      </div>

      <p className="text-3xs leading-4 text-text-secondary" data-testid="sarkhati-gate-reason">
        {gate.canTrade
          ? 'دروازۀ اجرا باز است؛ پیش‌فرود، سقف‌ها و عبارتِ تأیید را خودِ سرویس نگه می‌دارد.'
          : gate.reason}
      </p>

      <div className="flex flex-wrap gap-1.5" data-testid="sarkhati-mode-chips" role="group"
        aria-label="حالت‌هایِ اجرا">
        {Object.entries(MODE_LABEL).map(([key, label]) => {
          const m = modes[key] ?? {};
          const tone = m.active === true ? 'green' : m.implemented === true ? 'gray' : 'red';
          return (
            <span key={key} className="inline-flex" data-testid={`sarkhati-mode-${key}`}
              title={m.implemented === true
                ? `پیاده‌شده · دروازۀ ${m.door ?? '—'}${typeof m.can_reach_broker === 'boolean' ? ` · به کارگزاری می‌رسد: ${m.can_reach_broker ? 'بله' : 'خیر'}` : ''}`
                : 'درِ این نسخه پیاده نشده است'}>
              <Badge tone={tone}>
                {label}: {m.active === true ? 'فعال' : m.implemented === true ? 'خاموش' : 'نیست'}
              </Badge>
            </span>
          );
        })}
      </div>

      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-0.5 text-3xs text-text-muted"
        data-testid="sarkhati-counters">
        <span>دفترِ اجرا: <span className="num text-text-primary">{toFaDigits(String(st?.ledger_size ?? 0))}</span> رکورد</span>
        <span>زمان‌بندیِ در انتظار: <span className="num text-text-primary">{toFaDigits(String(st?.scheduled_pending ?? 0))}</span></span>
        <span>رخدادِ ماندگار: <span className="num text-text-primary">{toFaDigits(String(st?.durable_events ?? 0))}</span></span>
        <span>بازیابیِ پسِ restart: <span className="num text-text-primary">{toFaDigits(String(st?.recovered_after_restart ?? 0))}</span></span>
        <span>دورۀِ تأیید: <span className="num text-text-primary">{toFaDigits(String(st?.confirm_epoch ?? 0))}</span></span>
        <span>لغو: <span className="num text-text-primary">{caps?.cancel === true ? 'مجاز' : 'مجاز نیست'}</span></span>
      </div>

      {(st?.blocked_on ?? []).length > 0 ? (
        <ul className="flex flex-col gap-0.5 text-3xs text-accent-yellow"
          data-testid="sarkhati-blockers"
          aria-label="چرا دروازۀ اجرایِ واقعی بسته است">
          {(st?.blocked_on ?? []).map((b) => (<li key={b}>· {b}</li>))}
        </ul>
      ) : null}
    </div>
  );
}
