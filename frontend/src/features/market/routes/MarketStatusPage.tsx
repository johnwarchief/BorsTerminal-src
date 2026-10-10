// features/market/routes/MarketStatusPage.tsx -- صفحۀ مستقل «وضعیت بازار»
//
// چرا صفحه و نه کارتِ توی تابلو: مالک رأی داد که وضعیتِ بازار باید از ناوبری
// باز شود. نوارِ «وضعیت بازار» بالایِ تابلو می‌ماند (پاسِ سریعِ همان نشست)، و
// اینجا همان داده در نقشِ پخش‌شده می‌نشیند: نبض، توزیعِ درصد، تفکیکِ مشتری،
// فازهای نشست، نمودارهای درون‌روز، صنایع و نمادهای زیرِ نظر.
// هیچ بلوکی عددِ ساختگی نمی‌سازد: هر کدام loading / error / بی‌داده دارد.
import { MarketStatusPanel } from '../components/MarketStatusPanel';
import { MarketStatusTicker } from '../components/MarketStatusTicker';
import { MarketPulseBar } from '../components/MarketPulseBar';
import { TimelineCharts } from '../components/MicroChartsDrawer';
import {
  BreadthHistogram,
  ClientSplitPanel,
  MarketPhasePanel,
  SessionPhasesPanel,
} from '../components/MarketStatusPanels';
import { IndustriesTable, MainWatchTable } from '../components/MarketStatusTables';
import { useMarketPulse } from '../api/useMarketPulse';
import {
  useMstatClientSplit,
  useMstatHistogram,
  useMstatPhases,
  useMstatSessionPhase,
} from '../api/useMarketStatusFeed';

export default function MarketStatusPage() {
  const { data: pulse, isLoading: pulseLoading } = useMarketPulse();
  const histo = useMstatHistogram();
  const split = useMstatClientSplit();
  const phases = useMstatPhases();
  const sessionPhase = useMstatSessionPhase();

  return (
    <div className="flex w-full max-w-none flex-col gap-2" data-testid="market-status-page">
      <MarketStatusPanel />
      <MarketStatusTicker pulse={pulse} histogram={histo.data} split={split.data} />
      <MarketPulseBar pulse={pulse ?? null} isLoading={pulseLoading} />

      {/* بند ۵ مأموریت: پیش از هر حکمی، خودِ مرحلِ نشست و اینکه چه چیزی در این
          مرحل معنا دارد. تنها منبعش وضعیتِ رسمیِ خودِ بازار است. */}
      <MarketPhasePanel
        data={sessionPhase.data}
        isLoading={sessionPhase.isLoading}
        isError={sessionPhase.isError}
        onRetry={() => void sessionPhase.refetch()}
      />

      <div className="grid grid-cols-1 gap-2 xl:grid-cols-3">
        <BreadthHistogram
          data={histo.data}
          isLoading={histo.isLoading}
          isError={histo.isError}
          onRetry={() => void histo.refetch()}
        />
        <ClientSplitPanel
          data={split.data}
          isLoading={split.isLoading}
          isError={split.isError}
          onRetry={() => void split.refetch()}
        />
        <SessionPhasesPanel
          data={phases.data}
          isLoading={phases.isLoading}
          isError={phases.isError}
          onRetry={() => void phases.refetch()}
        />
      </div>

      <div className="glass-panel flex min-w-0 flex-col gap-2 rounded-xl border border-border-c p-2.5">
        <h3 className="text-2xs font-black text-text-primary">نمودارهای درون‌روزِ همین نشست</h3>
        <TimelineCharts />
      </div>

      {/* دو جدول نه‌تایی‌ستون در ۱۳۶ پیکسل کنارِ هم فشرده می‌شوند؛ فقط روی
          نمایشگرِ عریض دو ستونه‌اند. */}
      <div className="grid grid-cols-1 gap-2 2xl:grid-cols-2">
        <IndustriesTable />
        <MainWatchTable />
      </div>
    </div>
  );
}
