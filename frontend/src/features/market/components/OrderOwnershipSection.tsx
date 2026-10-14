// features/market/components/OrderOwnershipSection.tsx -- سفارش‌ها و تغییرِ مالکیت (صفحۀ ۹)
//
// چهار پنلِ مرجع در دو مفهومِ کاملاً جدا می‌نشینند و همین جداسازی دلیلِ وجودِ
// این فایل است:
//
// · «حجم سفارشات خرید/فروش» = ماندهٔ دفترِ سفارش (buy_q_vol / sell_q_vol).
//   این با «حجم معامله» (q_tot_tran) یکی نیست و هرگز جای هم نمی‌نشینند؛ برایِ
//   همین هر دو عدد کنارِ هم و با یکایِ خودشان چاپ می‌شوند تا خواننده ببیند
//   کدام کوچک‌تر است (معمولاً بله — سفارشِ مانده کمتر از گردشِ انجام‌شده).
// · «تغییرِ مالکیت حقیقی/حقوقی» = جابه‌جاییِ *سهم* بینِ دو گروه
//   (buy_n_vol − sell_n_vol) و درصدش از سهامِ شرکت. این نه «خالصِ ورودِ پول»
//   است (ریالی، درِ clientsplit) و نه «سرانه» (ریال بر نفر). هر سه عددِ متفاوتی
//   هستند و مرجع پنلِ جدا دارد.
//
// منبعِ نرسیده با علت می‌آید (`no_source`) و پنل بی‌عدد می‌ماند.
import { toFaDigits } from '@shared/lib/fmt';
import { StatusError, StatusLoading, StatusNoData, StatusSection, SourceNotice } from './StatusShell';
import { RankedPanelCard } from './RankedPanels';
import { TONE_CLASS, toneOf } from '../lib/tones';
import type { OrderFlowsFeed, OwnershipFeed } from '../api/useMarketPanels';

function BigStat({
  testId,
  label,
  value,
  unit,
  tone,
  hint,
}: {
  testId: string;
  label: string;
  value: number | null | undefined;
  unit: string;
  tone?: unknown;
  hint?: string;
}) {
  const shown = typeof value === 'number' && Number.isFinite(value);
  return (
    <div
      data-testid={testId}
      title={hint}
      className="flex min-w-0 flex-col gap-0.5 rounded-lg border border-border-c bg-bg-card px-2 py-1.5"
    >
      <span className="text-3xs text-text-muted">{label}</span>
      <span className={`num text-sm font-black ${tone ? TONE_CLASS[toneOf(tone)].text : 'text-text-primary'}`}>
        {shown ? toFaDigits(value.toFixed(1)) : '—'}
      </span>
      <span className="num-text text-3xs text-text-muted">{unit}</span>
    </div>
  );
}

export function OrdersPanel({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: OrderFlowsFeed;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <StatusSection
      testId="ms-orders"
      title="حجم سفارشات خرید و فروش"
      hint="ماندهٔ دفترِ سفارش — با حجمِ معاملهٔ انجام‌شده یکی نیست"
      asof={data?.asof}
      badge={data ? `مبنا: ${data.basis}` : undefined}
    >
      {isError && !data ? (
        <StatusError testId="ms-orders" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <StatusLoading testId="ms-orders" />
      ) : !data?.orders_available ? (
        <>
          <StatusNoData
            testId="ms-orders"
            text="دفترِ سفارش در این بانک پر نشده — پنل «سفارش» بی‌منبع عدد نمی‌سازد."
          />
          <SourceNotice testId="ms-orders" items={data?.no_source} />
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            <BigStat
              testId="ms-orders-buy"
              label="سفارش خرید"
              value={data?.totals?.buy_order_m_share}
              unit={data?.unit ?? ''}
              tone="pos"
              hint="Σ buy_q_vol — ماندهٔ خرید"
            />
            <BigStat
              testId="ms-orders-sell"
              label="سفارش فروش"
              value={data?.totals?.sell_order_m_share}
              unit={data?.unit ?? ''}
              tone="neg"
              hint="Σ sell_q_vol — ماندهٔ فروش"
            />
            <BigStat
              testId="ms-orders-exec"
              label="معاملهٔ انجام‌شده"
              value={data?.totals?.executed_m_share}
              unit={data?.unit ?? ''}
              hint="q_tot_tran — حجمِ معامله، نه سفارش"
            />
            <BigStat
              testId="ms-orders-ratio"
              label="نسبتِ خرید به فروش"
              value={data?.totals?.buy_sell_ratio}
              unit="×"
              tone={(data?.totals?.buy_sell_ratio ?? 0) >= 1 ? 'pos' : 'neg'}
              hint="buy_q_vol ÷ sell_q_vol"
            />
          </div>
          <p className="num-text text-3xs text-text-muted" data-testid="ms-orders-note">
            {data?.totals?.order_vs_executed_note} · {toFaDigits(data?.symbols_with_orders ?? 0)} نماد
            دفترِ سفارش دارد از {toFaDigits(data?.symbols_in_scope ?? 0)} نمادِ دامنه.
          </p>
          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
            {data?.buy_panels ? <RankedPanelCard panel={data.buy_panels} testId="ms-orders-buy-panel" /> : null}
            {data?.sell_panels ? (
              <RankedPanelCard panel={data.sell_panels} testId="ms-orders-sell-panel" />
            ) : null}
          </div>
          <SourceNotice testId="ms-orders" items={data?.no_source} />
        </>
      )}
    </StatusSection>
  );
}

export function OwnershipPanel({
  data,
  isLoading,
  isError,
  onRetry,
}: {
  data?: OwnershipFeed;
  isLoading: boolean;
  isError: boolean;
  onRetry: () => void;
}) {
  return (
    <StatusSection
      testId="ms-ownership"
      title="تغییرِ مالکیت حقیقی و حقوقی"
      hint="جابه‌جاییِ سهم بینِ دو گروه — با «خالصِ ورودِ پول» و «سرانه» اشتباه نشود"
      asof={data?.asof}
      badge={data ? `مبنا: ${data.basis} · یکا: ${data.unit}` : undefined}
    >
      {isError && !data ? (
        <StatusError testId="ms-ownership" onRetry={onRetry} />
      ) : isLoading && !data ? (
        <StatusLoading testId="ms-ownership" />
      ) : !data?.symbols_with_client_data ? (
        <>
          <StatusNoData testId="ms-ownership" text="تفکیکِ مشتری برایِ این دامنه نرسیده است." />
          <SourceNotice testId="ms-ownership" items={data?.no_source} />
        </>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-1.5">
            <BigStat
              testId="ms-ownership-legal"
              label="خالصِ جابه‌جایی به حقوقی"
              value={data?.totals?.legal_net_m_share}
              unit="میلیون سهم"
              tone={(data?.totals?.legal_net_m_share ?? 0) >= 0 ? 'pos' : 'neg'}
              hint={data?.formula?.legal_net}
            />
            <BigStat
              testId="ms-ownership-real"
              label="خالصِ جابه‌جایی به حقیقی"
              value={data?.totals?.real_net_m_share}
              unit="میلیون سهم"
              tone={(data?.totals?.real_net_m_share ?? 0) >= 0 ? 'pos' : 'neg'}
              hint="قرینهٔ عددِ بالا درِ همین دامنه"
            />
          </div>
          {data?.client_data_lags_session ? (
            <p
              data-testid="ms-ownership-lag"
              className="rounded-lg border border-dashed border-accent-yellow/40 bg-accent-yellow/5 px-2 py-1 text-3xs text-text-secondary"
            >
              ردیفِ تفکیکِ مشتری به نشستِ پیشین می‌گردد — این عدد وضعیتِ همین امروز نیست.
            </p>
          ) : null}
          <div className="grid grid-cols-1 gap-2 xl:grid-cols-2">
            {data?.to_legal_panel ? (
              <RankedPanelCard panel={data.to_legal_panel} testId="ms-ownership-to-legal" />
            ) : null}
            {data?.to_real_panel ? (
              <RankedPanelCard panel={data.to_real_panel} testId="ms-ownership-to-real" />
            ) : null}
          </div>
          {data?.formula?.not_to_be_confused ? (
            <p className="num-text text-3xs text-text-muted" data-testid="ms-ownership-diff">
              {data.formula.not_to_be_confused} · مبنایِ درصد: {data.formula.pct_of_capital}
            </p>
          ) : null}
          <SourceNotice testId="ms-ownership" items={data?.no_source} />
        </>
      )}
    </StatusSection>
  );
}
