// features/master/routes/StrategyTreePage.tsx -- صفحه جامع درخت استراتژی FTS (۴ چارت در یک نما)
// بر پایه جزوه دوره نوسان‌گیری و سرمایه‌گذاری به سبک FTS (عرفان نصرتی) و چارت‌های درختی
import { useMemo, useState, useRef, useEffect } from 'react';
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { ftsScoreOf } from '@contracts/fundamental';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useFtsPlan } from '@features/master/api/useFtsPlan';
import { ObsidianStrategyGraph } from '../components/ObsidianStrategyGraph';
import { EliteFunnelHub } from '../ui/EliteFunnelHub';
import { FtsFunnelStages } from '../ui/FtsFunnelStages';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import { runStrictGates, definiteDecision } from '../lib/strictGates';
import { evaluateFtsPipeline, type PipelineStep } from '../lib/ftsPipelineEvaluator';

type PresetMode = 'swing' | 'trend' | 'hourglass' | 'custom';
type ViewMode = 'obsidian' | 'grid' | 'both' | 'funnel';

/** رنگ/برچسب وضعیت زندهٔ هر گیت FTS از خروجی evaluateFtsPipeline */
const LIVE_STATUS_STYLE: Record<PipelineStep['status'], { dot: string; text: string; label: string; ring: string }> = {
  pass: { dot: 'bg-accent-green', text: 'text-accent-green', label: 'تایید', ring: 'border-accent-green/50 bg-accent-green/10' },
  wait: { dot: 'bg-accent-yellow', text: 'text-accent-yellow', label: 'در انتظار', ring: 'border-accent-yellow/50 bg-accent-yellow/10' },
  fail: { dot: 'bg-accent-red', text: 'text-accent-red', label: 'رد / وتو', ring: 'border-accent-red/50 bg-accent-red/10' },
};

/** نوار وضعیت زندهٔ نماد در سرستون هر فیلتر — خروجی واقعی evaluateFtsPipeline */
function LiveColumnStatus({ step }: { step: PipelineStep }) {
  const s = LIVE_STATUS_STYLE[step.status];
  return (
    <div className={`flex items-start gap-2.5 rounded-xl border px-3 py-2 text-xs ${s.ring}`}>
      <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${s.dot}`} aria-hidden />
      <div className="min-w-0 space-y-1">
        <div className="flex items-center gap-2">
          <span className="font-black text-text-primary text-xs">وضعیت زنده سهم:</span>
          <span className={`font-black text-xs ${s.text}`}>{s.label}</span>
        </div>
        <p className="leading-relaxed text-text-secondary font-medium text-xs">{step.headline}</p>
        {step.evidence.length > 0 && (
          <p className="truncate text-text-muted text-2xs font-semibold" title={step.evidence.join(' · ')}>
            {step.evidence.join(' · ')}
          </p>
        )}
      </div>
    </div>
  );
}

export default function StrategyTreePage() {
  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);

  const [selectedPreset, setSelectedPreset] = useState<PresetMode>('swing');
  const [viewMode, setViewMode] = useState<ViewMode>('obsidian');
  const { params } = useStrategyParamsStore();

  // وضعیت جستجوی نماد
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // خوراک بازار برای اتوکامپلیت نماد
  const marketFeed = useMarketFeed();
  const marketRows = useMemo(() => marketFeed.data?.data ?? [], [marketFeed.data]);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.trim();
    return marketRows
      .filter((r) => r.symbol && (matchFa(r.symbol, q) || matchFa(r.name, q)))
      .slice(0, 8);
  }, [marketRows, searchQuery]);

  // بستن منوی نتایج با کلیک بیرون از اینپوت
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // انتخاب‌های سفارشی کاربر در هر مرحله
  const [customFund, setCustomFund] = useState<'super' | 'good' | 'medium' | 'weak'>('good');
  const [customWeekly, setCustomWeekly] = useState<'up' | 'reject'>('up');
  const [customSetup, setCustomSetup] = useState<'jet' | 'fib' | 'choch' | 'double_bottom' | 'point_hunt'>('jet');
  const [customTape, setCustomTape] = useState<'clock' | 'suspicious_vol' | 'box_break' | 'floor_sweep'>('clock');
  const [customStop, setCustomStop] = useState<'ma14_fixed5' | 'codal_fund' | 'hourglass_deep'>('ma14_fixed5');

  // داده‌های زنده نماد
  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const inputs = useMemo(() => (symbol ? getActiveSignals(symbol) : {}), [symbol, entry]);
  const closes = useMarketCloses();
  const ftsPlan = useFtsPlan(symbol);
  const currentPrice = (symbol ? closes.data?.get(symbol) : null) ?? null;
  const resistance = ftsPlan.data?.fts?.jet?.resistance ?? null;
  const support = ftsPlan.data?.fts?.fib?.zone_33_40?.lo ?? null;
  // امتیاز شمار شاخص‌های بنیادی ۰ تا ۵ (payload.score)
  const fundScore = ftsScoreOf(inputs.fundamental);

  const strict = useMemo(
    () =>
      runStrictGates(inputs, {
        inBasket: null,
        industryUsedPct: null,
        industryCapPct: 20,
        warRegime: false,
        symbolWeightPct: null,
      }),
    [inputs],
  );

  const decision = useMemo(() => definiteDecision(strict), [strict]);

  const evaluation = useMemo(
    () =>
      evaluateFtsPipeline({
        symbol: symbol || '',
        horizon: selectedPreset === 'custom' ? 'swing' : selectedPreset,
        inputs,
        strict,
        decision,
        currentPrice,
        resistancePrice: resistance,
        supportPrice: support,
        fundScore,
      }),
    [symbol, selectedPreset, inputs, strict, decision, currentPrice, resistance, support, fundScore],
  );

  // تطبیق خودکار با وضعیت واقعی نماد
  const handleSyncWithSymbol = () => {
    setSelectedPreset('custom');
    if (fundScore && fundScore >= 5) setCustomFund('super');
    else if (fundScore && fundScore >= 4) setCustomFund('good');
    else if (fundScore && fundScore >= 3) setCustomFund('medium');
    else setCustomFund('weak');

    if (strict.weekly.uptrend === false) setCustomWeekly('reject');
    else setCustomWeekly('up');

    setCustomSetup('jet');
    setCustomTape('clock');
    setCustomStop('ma14_fixed5');
  };

  // اعمال مستقیم نماد بر درخت به محض انتخاب از سرچ
  const handleSelectSymbol = (sym: string) => {
    setSymbol(sym);
    setSearchQuery('');
    setSearchOpen(false);
  };

  // تطبیق خودکار درخت — یک‌بار برای هر نماد، آن‌هم وقتی امتیاز بنیادی واقعاً
  // رسیده. پیش از این با هر refetchِ خوراک بازار/کارت دوباره اجرا می‌شد و
  // پریستِ دستیِ انتخاب‌شدهٔ کاربر را بی‌صدا به «جت/سفارشی» برمی‌گرداند.
  const lastAutoSync = useRef('');
  useEffect(() => {
    if (!symbol || fundScore == null) return;
    if (lastAutoSync.current === symbol) return;
    lastAutoSync.current = symbol;
    handleSyncWithSymbol();
  }, [symbol, fundScore]);

  // نگاشت وضعیت زندهٔ هر گیت به سرستونِ همان ستون (F/T/S/M)
  const stepsById = useMemo(() => {
    const m = {} as Record<PipelineStep['id'], PipelineStep | undefined>;
    if (!symbol) return m;
    for (const s of evaluation.steps) m[s.id] = s;
    return m;
  }, [symbol, evaluation]);

  // تعیین نودهای فعال بر مبنای پری‌ست یا نماد
  const activeNodes = useMemo(() => {
    if (selectedPreset === 'swing') {
      return {
        fund: ['fund_good', 'fund_medium'],
        weekly: ['tech_weekly_up'],
        setup: ['setup_jet', 'setup_fib'],
        tape: ['tape_clock', 'tape_volume'],
        stop: ['stop_swing'],
        exit: ['exit_half'],
      };
    }
    if (selectedPreset === 'trend') {
      return {
        fund: ['fund_super', 'fund_good'],
        weekly: ['tech_weekly_up'],
        setup: ['setup_fib', 'setup_choch', 'setup_jet'],
        // چارت ۳ (S: SELECTION) شاخۀ «فیلتر»ِ روندگیر را کف‌روبی و نقطه‌زنی
        // می‌داند، نه ساعت و شکستِ باکس که برایِ نوسان‌گیر است. گرهٔ نقطه‌زنی
        // هنوز درِ نقشۀ چهارچارتی ساخته نشده (کارِ باز) — پس فعلاً کف‌روبی.
        tape: ['tape_floor_sweep'],
        stop: ['stop_trend'],
        exit: ['exit_longterm'],
      };
    }
    if (selectedPreset === 'hourglass') {
      return {
        fund: ['fund_super'],
        weekly: ['tech_weekly_hourglass'],
        setup: ['setup_hourglass_deep'],
        tape: ['tape_floor_sweep', 'tape_clock'],
        stop: ['stop_hourglass'],
        exit: ['exit_longterm'],
      };
    }
    // حالت Custom
    return {
      fund: [`fund_${customFund}`],
      weekly: [customWeekly === 'up' ? 'tech_weekly_up' : 'tech_weekly_reject'],
      setup: [`setup_${customSetup}`],
      tape: [`tape_${customTape}`],
      stop: [customStop === 'ma14_fixed5' ? 'stop_swing' : customStop === 'codal_fund' ? 'stop_trend' : 'stop_hourglass'],
      exit: ['exit_half'],
    };
  }, [selectedPreset, customFund, customWeekly, customSetup, customTape, customStop]);

  // نودهای فعال در حالت سفارشی جهت ارسال به گراف ابسیدین
  const activeCustomNodeIds = useMemo(() => {
    const stopId =
      customStop === 'ma14_fixed5' ? 'stop_swing' : customStop === 'codal_fund' ? 'stop_trend' : 'stop_hourglass';
    const tapeId =
      customTape === 'suspicious_vol'
        ? 'tape_volume'
        : customTape === 'box_break'
          ? 'tape_breakout'
          : customTape === 'floor_sweep'
            ? 'tape_floor_sweep'
            : 'tape_clock';
    const weeklyId = customWeekly === 'up' ? 'tech_weekly_up' : 'tech_weekly_reject';

    return [
      `fund_${customFund}`,
      weeklyId,
      `setup_${customSetup}`,
      tapeId,
      stopId,
      'exit_half',
      'rule_rr',
    ];
  }, [customFund, customWeekly, customSetup, customTape, customStop]);

  // کلیک روی نودهای گراف در حالت سفارشی
  const handleToggleCustomNode = (nodeId: string) => {
    setSelectedPreset('custom');
    if (nodeId.startsWith('fund_')) {
      const fundKey = nodeId.replace('fund_', '') as 'super' | 'good' | 'medium' | 'weak';
      if (['super', 'good', 'medium', 'weak'].includes(fundKey)) setCustomFund(fundKey);
    } else if (nodeId === 'tech_weekly_up') {
      setCustomWeekly('up');
    } else if (nodeId === 'tech_weekly_reject') {
      setCustomWeekly('reject');
    } else if (nodeId.startsWith('setup_')) {
      const setupKey = nodeId.replace('setup_', '');
      const allowed = ['jet', 'fib', 'choch', 'double_bottom', 'point_hunt'] as const;
      if ((allowed as readonly string[]).includes(setupKey)) {
        setCustomSetup(setupKey as (typeof allowed)[number]);
      }
    } else if (nodeId === 'tape_clock') {
      setCustomTape('clock');
    } else if (nodeId === 'tape_volume') {
      setCustomTape('suspicious_vol');
    } else if (nodeId === 'tape_breakout') {
      setCustomTape('box_break');
    } else if (nodeId === 'tape_floor_sweep') {
      setCustomTape('floor_sweep');
    } else if (nodeId === 'stop_swing') {
      setCustomStop('ma14_fixed5');
    } else if (nodeId === 'stop_trend') {
      setCustomStop('codal_fund');
    } else if (nodeId === 'stop_hourglass') {
      setCustomStop('hourglass_deep');
    }
  };

  return (
    <div className="flex flex-col gap-4 p-3 sm:p-5 max-w-[1700px] mx-auto w-full">
      {/* ۱. نوار ابزار فشرده، سریع و سبک بالای نمودار (حذف نوار بزرگ و تکراری) */}
      <div className="rounded-2xl border border-border-c bg-bg-card/70 p-3 sm:p-4 shadow-sm flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* سمت راست: عنوان و جستجوی تعاملی نماد با اعمال زنده */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-blue/15 text-sm font-black text-accent-blue">
                🌳
              </span>
              <h1 className="text-xs sm:text-sm font-black text-text-primary">
                نقشه راه و درخت جامع استراتژی FTS
              </h1>
              <span className="hidden sm:inline-block rounded-full border border-accent-blue/40 bg-accent-blue/10 px-2 py-0.5 text-2xs font-bold text-accent-blue">
                ۴ چارت در یک نما
              </span>
            </div>

            {/* اینپوت جستجوی نماد با اتوکامپلیت */}
            <div ref={searchContainerRef} className="relative min-w-[210px] sm:min-w-[260px]">
              <div className="relative flex items-center">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => {
                    setSearchQuery(e.target.value);
                    setSearchOpen(true);
                  }}
                  onFocus={() => setSearchOpen(true)}
                  placeholder="🔍 جستجوی نماد یا شرکت..."
                  className="w-full rounded-xl border border-border-c bg-bg-primary px-3 py-1.5 pe-7 text-xs font-bold text-text-primary placeholder:text-text-muted focus:border-accent-blue focus:outline-none transition-colors"
                />
                {searchQuery && (
                  <button
                    type="button"
                    onClick={() => {
                      setSearchQuery('');
                      setSearchOpen(false);
                    }}
                    className="absolute end-2 text-text-muted hover:text-text-primary text-xs"
                    title="پاک کردن متن"
                  >
                    ✕
                  </button>
                )}
              </div>

              {/* نتایج دراپ‌داون */}
              {searchOpen && searchResults.length > 0 && (
                <div className="absolute z-50 mt-1 max-h-60 w-full overflow-y-auto rounded-xl border border-border-c bg-bg-card p-1 shadow-2xl">
                  {searchResults.map((r) => (
                    <button
                      key={r.symbol}
                      type="button"
                      onClick={() => handleSelectSymbol(r.symbol)}
                      className="flex w-full items-center justify-between rounded-lg px-2.5 py-1.5 text-xs hover:bg-accent-blue/15 transition-colors text-start"
                    >
                      <div className="flex items-center gap-2">
                        <span className="font-black text-accent-blue">{r.symbol}</span>
                        <span className="text-text-muted text-2xs truncate max-w-[130px]">{r.name}</span>
                      </div>
                      {r.p_closing && (
                        <span className="font-mono text-2xs text-text-secondary">
                          {toFaDigits(fmtInt(r.p_closing))} ریال
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* نشانگر نماد فعال و وضعیت عینی */}
            {symbol ? (
              <div className="flex items-center gap-2 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-2.5 py-1 text-xs">
                <span className="text-text-muted text-2xs">نماد فعال:</span>
                <strong className="text-accent-blue font-black">{symbol}</strong>
                {currentPrice && (
                  <span className="text-text-secondary font-mono text-2xs">({toFaDigits(fmtInt(currentPrice))} ریال)</span>
                )}
                {fundScore != null && (
                  <span className="rounded bg-accent-green/20 px-1.5 py-0.5 text-3xs font-black text-accent-green">
                    بنیادی {toFaDigits(fundScore)}/۵
                  </span>
                )}
                <button
                  type="button"
                  onClick={handleSyncWithSymbol}
                  className="rounded-md bg-accent-blue/20 px-1.5 py-0.5 text-3xs font-bold text-accent-blue hover:bg-accent-blue hover:text-black transition-colors"
                  title="تطبیق مجدد وضعیت سهم با درخت"
                >
                  ⚡ تطبیق
                </button>
                <button
                  type="button"
                  onClick={() => clearSymbol()}
                  aria-label="حذف نماد"
                  title="حذف نماد و نمایش راهنمای کلان"
                  className="ms-1 text-text-muted hover:text-accent-red text-xs font-bold"
                >
                  ✕
                </button>
              </div>
            ) : (
              <span className="text-2xs text-text-muted hidden md:inline-block">
                (راهنمای کلان — با سرچ نماد، وضعیت سهم روی درخت اعمال می‌شود)
              </span>
            )}
          </div>

          {/* سمت چپ: سوییچ نما */}
          <div className="flex items-center gap-1 rounded-xl border border-border-c/70 bg-bg-primary p-1 ms-auto">
            <button
              type="button"
              onClick={() => setViewMode('grid')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                viewMode === 'grid'
                  ? 'bg-accent-green/20 border border-accent-green/50 text-accent-green shadow-[0_0_8px_rgba(34,197,94,0.25)]'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <span>📊</span>
              <span>نمای گرید ۴ ستونه</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('obsidian')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                viewMode === 'obsidian'
                  ? 'bg-accent-blue/20 border border-accent-blue/50 text-accent-blue shadow-[0_0_8px_rgba(56,189,248,0.25)]'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🕸️</span>
              <span>نمودار شبکه ابسیدین</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('both')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                viewMode === 'both'
                  ? 'bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan shadow-[0_0_8px_rgba(6,182,212,0.25)]'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🔀</span>
              <span>ترکیبی</span>
            </button>
            <button
              type="button"
              onClick={() => setViewMode('funnel')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                viewMode === 'funnel'
                  ? 'bg-accent-amber/20 border border-accent-amber/50 text-accent-amber shadow-[0_0_8px_rgba(245,158,11,0.25)]'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🧲</span>
              <span>قیف انتخاب خودکار</span>
            </button>
          </div>
        </div>

        {/* سوییچر سبک معامله / مسیر بازی */}
        <div className="pt-2 border-t border-border-c/50 flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-text-secondary">سبک و مسیر بازی FTS:</span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            <button
              type="button"
              onClick={() => setSelectedPreset('swing')}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1 text-xs font-bold transition-all ${
                selectedPreset === 'swing'
                  ? 'border-accent-blue bg-accent-blue/20 text-accent-blue shadow-[0_0_10px_rgba(56,189,248,0.2)]'
                  : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              <span>⚡</span>
              <span>شخص نوسان‌گیر (زیر ۳ ماه)</span>
            </button>

            <button
              type="button"
              onClick={() => setSelectedPreset('trend')}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1 text-xs font-bold transition-all ${
                selectedPreset === 'trend'
                  ? 'border-accent-green bg-accent-green/20 text-accent-green shadow-[0_0_10px_rgba(34,197,94,0.2)]'
                  : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              <span>📈</span>
              <span>شخص روندگیر (بالای ۳ ماه)</span>
            </button>

            <button
              type="button"
              onClick={() => setSelectedPreset('hourglass')}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1 text-xs font-bold transition-all ${
                selectedPreset === 'hourglass'
                  ? 'border-accent-yellow bg-accent-yellow/20 text-accent-yellow shadow-[0_0_10px_rgba(234,179,8,0.2)]'
                  : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              <span>⏳</span>
              <span>استراتژی ساعت شنی (۳ تا ۱۰ ساله)</span>
            </button>

            <button
              type="button"
              onClick={() => setSelectedPreset('custom')}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1 text-xs font-bold transition-all ${
                selectedPreset === 'custom'
                  ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan shadow-[0_0_10px_rgba(6,182,212,0.2)]'
                  : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🛠</span>
              <span>مسیر سفارشی (انتخاب دستی)</span>
            </button>
          </div>
        </div>
      </div>

      {/* ۲. نمودار شبکه تعاملی سبک ابسیدین (Obsidian Strategy Graph) */}
      {(viewMode === 'obsidian' || viewMode === 'both') && (
        <ObsidianStrategyGraph
          selectedPreset={selectedPreset}
          symbol={symbol}
          activeCustomNodes={activeCustomNodeIds}
          onToggleCustomNode={handleToggleCustomNode}
          symbolPhaseStatus={symbol ? [
            { k: 'F', status: stepsById.fundamental?.status ?? 'wait', label: stepsById.fundamental?.headline ?? '' },
            { k: 'T', status: stepsById.technical?.status ?? 'wait', label: stepsById.technical?.headline ?? '' },
            { k: 'S', status: stepsById.tape?.status ?? 'wait', label: stepsById.tape?.headline ?? '' },
            { k: 'M', status: stepsById.master?.status ?? 'wait', label: stepsById.master?.headline ?? '' },
          ] : undefined}
          symbolLevels={symbol ? {
            price: currentPrice,
            entry: resistance ?? support,
            support,
            resistance,
            hardStop: ftsPlan.data?.fts?.exit_engine?.l1?.hard_stop ?? null,
            exitVerdict: ftsPlan.data?.fts?.exit_engine?.verdict ?? null,
          } : undefined}
        />
      )}

      {/* ۳. چارت درختی ۴ مرحله‌ای بصری و ستونی با فونت‌های درشت و کاملاً خوانا */}
      {(viewMode === 'grid' || viewMode === 'both') && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
          {/* ═══════════ فاز ۱: بنیادی F (۵ شاخص FTS) ═══════════ */}
          <div className="rounded-2xl border border-border-c/80 bg-bg-card/40 p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-green/20 text-xs font-black text-accent-green">
                  F
                </span>
                <h2 className="text-sm font-black text-text-primary">
                  ۱. فیلتر بنیادی (۵ شاخص کدال)
                </h2>
              </div>
              <span className="text-2xs font-bold rounded bg-bg-primary px-2 py-0.5 text-text-muted">
                چارت صفحه ۱
              </span>
            </div>

            {stepsById.fundamental && <LiveColumnStatus step={stepsById.fundamental} />}

            <div className="space-y-2.5">
              {/* شاخص سوپربنیادی ۵ از ۵ */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomFund('super');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.fund.includes('fund_super')
                    ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">💎 سوپربنیادی (امتیاز ۵ از ۵)</strong>
                  <span className="text-2xs text-accent-green font-black">عالی</span>
                </div>
                <ul className="text-xs text-text-secondary space-y-1 leading-relaxed font-medium">
                  <li>● ۱- رشد فروش ماهانه کدال نسبت به پارسال &gt; ۴۰٪ با تورم (الف: ریالی + ب: تولیدی)</li>
                  <li>● ۲- سابقه عملکرد ۳ ساله سودآوری (روند صعودی متوالی EPS هر سهم)</li>
                  <li>● ۳- حاشیه سود ناخالص مطلوب &gt; ۳۰٪ (حداقل کف ۲۰٪)</li>
                  <li>● ۴- نسبت فروش سالانه‌شده (تجمیعی × ۱۲÷م) به ارزش بازار (حداقل ۱ برابر یا پوشش &gt; ۴۰٪)</li>
                  <li>● ۵- صنایع آزاد و بورس کالا بدون قیمت‌گذاری دستوری</li>
                </ul>
              </div>

              {/* بنیادی مطلوب ۴ از ۵ */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomFund('good');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.fund.includes('fund_good')
                    ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">بنیادی مطلوب (۴ از ۵ FTS)</strong>
                  <span className="text-2xs text-accent-blue font-black">تایید روندی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  رشد فروش ماهانه کدال و روند صعودی EPS تایید، حاشیه ناخالص بالای ۲۰٪؛ مناسب برای ورود روندی بالای ۳ ماه.
                </p>
              </div>

              {/* بنیادی متوسط ۳ از ۵ */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomFund('medium');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.fund.includes('fund_medium')
                    ? 'border-accent-yellow bg-accent-yellow/15 shadow-[0_0_12px_rgba(234,179,8,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">بنیاد متوسط (۳ از ۵ FTS)</strong>
                  <span className="text-2xs text-accent-yellow font-black">صرفاً نوسانی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  فاقد سودآوری متوالی ۳ ساله اما دارای رشد فروش فصلی؛ صرفاً نوسان‌گیری سریع با ستاپ جت مجاز است.
                </p>
              </div>

              {/* رد بنیادی */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomFund('weak');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.fund.includes('fund_weak')
                    ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-accent-red">⛔ رد بنیادی (زیر ۳ از ۵ یا زیان‌ده)</strong>
                  <span className="text-2xs text-accent-red font-black">توقف / وتو</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  صنایع با نرخ‌گذاری دستوری شدید (خودرو/قطعات) یا افت شدید حاشیه سود به زیر ۲۰٪ یا زیان‌دهی؛ ورود ممنوع.
                </p>
              </div>
            </div>
          </div>

          {/* ═══════════ فاز ۲: تکنیکال دو زمانه T ═══════════ */}
          <div className="rounded-2xl border border-border-c/80 bg-bg-card/40 p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-neon-cyan/20 text-xs font-black text-neon-cyan">
                  T
                </span>
                <h2 className="text-sm font-black text-text-primary">
                  ۲. فیلتر تکنیکال ۲ زمانه
                </h2>
              </div>
              <span className="text-2xs font-bold rounded bg-bg-primary px-2 py-0.5 text-text-muted">
                چارت صفحه ۲
              </span>
            </div>

            {stepsById.technical && <LiveColumnStatus step={stepsById.technical} />}

            <div className="space-y-2.5">
              {/* شاخه هفتگی صعودی */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomWeekly('up');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.weekly.includes('tech_weekly_up') || activeNodes.weekly.includes('tech_weekly_hourglass')
                    ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">تایم هفتگی صعودی (تایید ماژور)</strong>
                  <span className="text-2xs text-accent-green font-black">مجوز ورود</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  تشکیل سقف‌ها و کف‌های بالاتر در تایم هفتگی؛ شرط صلب اولیه و لازم برای ورود به ستاپ‌های روزانه.
                </p>
              </div>

              {/* ستاپ جت روزانه */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomSetup('jet');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.setup.includes('setup_jet')
                    ? 'border-neon-cyan bg-neon-cyan/15 shadow-[0_0_12px_rgba(6,182,212,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-neon-cyan">🚀 استراتژی جت (Jet Breakout)</strong>
                  <span className="text-2xs text-neon-cyan font-black">ستاپ پرتاب</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  عبور از سقف تاریخی یا مقاومت استاتیک با کندل پرقدرت؛ تا ۳ روز فرصت ورود پله‌ای وجود دارد.
                </p>
              </div>

              {/* ستاپ فیبوناچی و پولبک */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomSetup('fib');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.setup.includes('setup_fib')
                    ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-accent-blue">ستاپ فیبوناچی ۳۳-۴۰ و ۶۱.۸-۷۰</strong>
                  <span className="text-2xs text-accent-blue font-black">پله‌های ورود</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  پله اول در تراز ۳۳ تا ۴۰ فیبو، پله دوم در تراز ۶۱.۸ تا ۷۰ درصد؛ اصلاح سالم در روند صعودی.
                </p>
              </div>

              {/* ستاپ CHoCH و کف دوقلو */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomSetup('choch');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.setup.includes('setup_choch') || activeNodes.setup.includes('setup_double_bottom')
                    ? 'border-purple-500 bg-purple-500/15 shadow-[0_0_12px_rgba(168,85,247,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">تغییر ساختار CHoCH / کف دوقلو</strong>
                  <span className="text-2xs text-purple-400 font-black">بازگشتی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  شکست آخرین سقف در روند نزولی یا شکست خط گردن (Neckline) کف دوقلو با پولبک و تثبیت ۲ روزه.
                </p>
              </div>

              {/* ریجکت هفتگی */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomWeekly('reject');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.weekly.includes('tech_weekly_reject')
                    ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-accent-red">ریجکت هفتگی (Reject صلب)</strong>
                  <span className="text-2xs text-accent-red font-black">وتو</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  روند هفتگی نزولی یا خنثی؛ طبق صفحه ۲ و ۷ جزوه هرگونه ورود اکیداً ممنوع و وتوی صلب است.
                </p>
              </div>
            </div>
          </div>

          {/* ═══════════ فاز ۳: تابلوخوانی و غربالگری S ═══════════ */}
          <div className="rounded-2xl border border-border-c/80 bg-bg-card/40 p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-yellow/20 text-xs font-black text-accent-yellow">
                  S
                </span>
                <h2 className="text-sm font-black text-text-primary">
                  ۳. تابلوخوانی و زمان‌سنج (S)
                </h2>
              </div>
              <span className="text-2xs font-bold rounded bg-bg-primary px-2 py-0.5 text-text-muted">
                چارت صفحه ۳
              </span>
            </div>

            {stepsById.tape && <LiveColumnStatus step={stepsById.tape} />}

            <div className="space-y-2.5">
              {/* الگوی ساعت */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomTape('clock');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.tape.includes('tape_clock')
                    ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">⏰ الگوی ساعت FTS</strong>
                  <span className="text-2xs text-accent-green font-black">زمان‌سنج ورود</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  قیمت آخرین معامله بیش از ۱٪ بالاتر از قیمت پایانی (ایده‌آل: پایانی منفی و آخرین مثبت)؛ احتمال بالای بازگشایی مثبت فردا.
                </p>
              </div>

              {/* حجم مشکوک ۳ برابری */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomTape('suspicious_vol');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.tape.includes('tape_volume')
                    ? 'border-neon-cyan bg-neon-cyan/15 shadow-[0_0_12px_rgba(6,182,212,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-neon-cyan">حجم مشکوک (۳ برابر میانگین)</strong>
                  <span className="text-2xs text-neon-cyan font-black">ورود پول هوشمند</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  حجم معاملات امروز حداقل ۳ برابر میانگین ۲۱ روزه ماهانه؛ نشانه ورود کدهای درشت و دست‌به‌دست شدن سهم.
                </p>
              </div>

              {/* خروج از باکس رنج */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomTape('box_break');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.tape.includes('tape_breakout')
                    ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">خروج از باکس رنج (Breakout)</strong>
                  <span className="text-2xs text-accent-blue font-black">آغاز موج</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  شکست سقف باکس رنج با کندل پرقدرت + رشد حجم معاملات + پر شدن حجم مبنا و الگوی ساعت.
                </p>
              </div>

              {/* کف‌روبی و خشک کردن سهم */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomTape('floor_sweep');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.tape.includes('tape_floor_sweep')
                    ? 'border-purple-500 bg-purple-500/15 shadow-[0_0_12px_rgba(168,85,247,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">کف‌روبی صف فروش / جمع‌آوری</strong>
                  <span className="text-2xs text-purple-400 font-black">جمع‌آوری کف</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  سهم در صف فروش یا کف قیمت است اما سفارش‌های خرید قوی در حال بلعیدن صف هستند و فروشنده‌ها کاملاً خشک شده‌اند.
                </p>
              </div>
            </div>
          </div>

          {/* ═══════════ فاز ۴: مدیریت سرمایه و پلن خروج ═══════════ */}
          <div className="rounded-2xl border border-border-c/80 bg-bg-card/40 p-4 space-y-3 shadow-sm">
            <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
              <div className="flex items-center gap-2">
                <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-blue/20 text-xs font-black text-accent-blue">
                  M
                </span>
                <h2 className="text-sm font-black text-text-primary">
                  ۴. مدیریت سرمایه و خروج
                </h2>
              </div>
              <span className="text-2xs font-bold rounded bg-bg-primary px-2 py-0.5 text-text-muted">
                چارت صفحه ۴
              </span>
            </div>

            {stepsById.master && <LiveColumnStatus step={stepsById.master} />}

            <div className="space-y-2.5">
              {/* حد ضرر نوسان‌گیر */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomStop('ma14_fixed5');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.stop.includes('stop_swing')
                    ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">حد ضرر صلب نوسان‌گیر</strong>
                  <span className="text-2xs text-accent-red font-black">استاپ تکنیکالی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  تشکیل یک کندل کامل زیر میانگین متحرک ۱۴ (MA=14) یا افت ۵٪ زیر نقطه ورود یا آخرین کف صعودی؛ خروج بی‌چون‌وچرا.
                </p>
              </div>

              {/* حد ضرر روندگیر */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomStop('codal_fund');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.stop.includes('stop_trend')
                    ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-text-primary">حد ضرر بنیادی روندگیر</strong>
                  <span className="text-2xs text-accent-green font-black">کدال و فصلی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  شخص روندگیر حد ضرر تکنیکالی ندارد؛ حد ضرر در صورت‌های مالی است: توقف رشد فروش ماهانه، افت حاشیه سود به زیر ۲۰٪ یا نزولی شدن EPS.
                </p>
              </div>

              {/* استراتژی ساعت شنی */}
              <div
                onClick={() => {
                  setSelectedPreset('custom');
                  setCustomStop('hourglass_deep');
                }}
                className={`cursor-pointer rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.stop.includes('stop_hourglass')
                    ? 'border-accent-yellow bg-accent-yellow/15 shadow-[0_0_12px_rgba(234,179,8,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40 hover:opacity-80'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-accent-yellow">اهرم ساعت شنی (۲ تا ۴ برابر)</strong>
                  <span className="text-2xs text-accent-yellow font-black">کف تاریخی</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  سهام بزرگ بنیادی در تایم هفتگی زیر MA=52 و RSI زیر ۷ در اشباع عمیق؛ خرید سنگین پله‌ای به دید ۳ تا ۱۰ ساله.
                </p>
              </div>

              {/* قانون ذخیره سود ۵۰٪ */}
              <div
                className={`rounded-xl border p-3.5 transition-all duration-200 ${
                  activeNodes.exit.includes('exit_half')
                    ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-accent-blue">قانون ذخیره سود ۵۰٪ FTS</strong>
                  <span className="text-2xs text-accent-blue font-black">خروج اصل پول</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  در برخورد با مقاومت اول R1 یا سقف موج، ۵۰٪ سهم فروخته می‌شود تا اصل سرمایه آزاد شده و ادامه معامله بدون ریسک شود.
                </p>
              </div>

              {/* خروج در سقف سوم کانال صعودی */}
              <div
                className={`rounded-xl border p-3.5 transition-all duration-200 ${
                  selectedPreset === 'swing' || selectedPreset === 'trend'
                    ? 'border-orange-500/70 bg-orange-500/10 opacity-100'
                    : 'border-border-c/60 bg-bg-primary/60 opacity-40'
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <strong className="text-sm font-black text-orange-400">🏔️ خروج در سقف سوم (صفحه ۴)</strong>
                  <span className="text-2xs text-orange-400 font-black">خروج ۱۰۰٪</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  برخورد به سقف سوم کانال یا خط روند (فاصله {toFaDigits(params.thirdPeakWeeklyPct)}٪ هفتگی یا {toFaDigits(params.thirdPeakDailyPct)}٪ روزانه)؛ خروج کامل از سهم.
                </p>
              </div>

              {/* سقف کل دارایی در بورس و شرایط جنگی */}
              <div className="rounded-xl border border-border-c/70 bg-bg-primary/70 p-3.5 space-y-1">
                <div className="flex items-center justify-between mb-1">
                  <strong className="text-sm font-black text-accent-yellow">🏛️ قانون سبد دارایی</strong>
                  <span className="text-2xs text-accent-yellow font-black">مدیریت کلان</span>
                </div>
                <p className="text-xs text-text-secondary leading-relaxed font-medium">
                  سقفِ ورودِ کل دارایی به بورس در شرایط عادی {toFaDigits(params.maxTotalPortfolioCapPct)}٪ (تئوریِ جزوه ۷۰٪) و در شرایط جنگی {toFaDigits(params.warConditionCapPct)}٪ ±۱۰٪؛ باقیِ دارایی طلا و درآمد ثابت.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ۳.۵ قیف انتخاب خودکار (#225/#224) — چهار مرحلۀ متحرکِ جزوه (تابلو ←
          تکنیکال ← بنیادی ← تحویل) و زیرِ همان‌ها هستۀ EliteFunnelHub با
          تب‌هایِ ۵۰/۱۰/سبد؛ کلیکِ هر سطر نماد را انتخاب می‌کند و وضعیتِ زنده
          روی درخت/گرید در همان صفحه اعمال می‌شود. */}
      {viewMode === 'funnel' && (
        <>
          <FtsFunnelStages preset={selectedPreset} />
          <EliteFunnelHub />
        </>
      )}

      {/* ۴. کارت جامع دستورالعمل و خلاصه پلن اجرایی استراتژی (Strategy Playbook Summary) */}
      <div className="rounded-2xl border border-border-c p-4 sm:p-5 bg-bg-card/50 shadow-sm space-y-3">
        <div className="flex items-center justify-between border-b border-border-c/60 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-base">📋</span>
            <h3 className="text-xs sm:text-sm font-black text-text-primary">
              دستورالعمل اجرایی استراتژی انتخاب‌شده: {
                selectedPreset === 'swing'
                  ? 'پلن نوسان‌گیری سریع FTS (ستاپ جت / فیبو)'
                  : selectedPreset === 'trend'
                    ? 'پلن سهامداری و روندگیری FTS (بنیادی ۵ شاخصه)'
                    : selectedPreset === 'hourglass'
                      ? 'پلن سرمایه‌گذاری ساعت شنی FTS (اهرم خرید در کف هفتگی)'
                      : 'پلن سفارشی معامله‌گر'
              }
            </h3>
          </div>
          <span className="rounded-full bg-accent-blue/15 border border-accent-blue/30 px-2.5 py-0.5 text-2xs font-bold text-accent-blue">
            آماده اجرا در بورس ایران
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-xs">
          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3.5 space-y-1">
            <span className="text-text-muted block text-2xs font-bold">۱. شرط ورود و زمان‌سنج:</span>
            <p className="text-text-primary font-medium leading-relaxed">
              {selectedPreset === 'swing'
                ? `شکست مقاومت استاتیک با ستاپ جت (${toFaDigits(params.jetStabilizationDays)} روزه) یا فیبو + تایید الگوی ساعت (${toFaDigits(params.clockPriceDiffPct)}٪) یا حجم ${toFaDigits(params.minVolumeRatio)}×.`
                : selectedPreset === 'trend'
                  ? `روند هفتگی صعودی + تایید ۵ شاخص بنیادی کدال (حاشیه > ${toFaDigits(params.minGrossMarginPct)}٪) + ورود پول حقیقی.`
                  : selectedPreset === 'hourglass'
                    ? `نماد سوپربنیادی در تایم هفتگی زیر MA-52 و اشباع عمیق RSI زیر ${toFaDigits(params.hourglassWeeklyRsi)}.`
                    : 'ترکیب سفارشی شاخص‌ها و پارامترهای ویرایش‌شده در بالا.'}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3.5 space-y-1">
            <span className="text-text-muted block text-2xs font-bold">۲. حد ضرر و مدیریت ریسک:</span>
            <p className="text-accent-red font-bold leading-relaxed">
              {selectedPreset === 'swing'
                ? `تشکیل یک کندل کامل زیر MA-${toFaDigits(params.stopLossMaPeriod)} یا افت ${toFaDigits(params.stopLossFixedPct)}٪ زیر نقطه ورود (خروج قطعی).`
                : selectedPreset === 'trend'
                  ? `حد ضرر بنیادی در صورت‌های مالی کدال (افت حاشیه سود به زیر ${toFaDigits(params.minGrossMarginPct)}٪ یا افت فروش).`
                  : selectedPreset === 'hourglass'
                    ? 'بدون حد ضرر نوسانی کوتاه‌مدت؛ پله‌بندی سنگین در افت‌های هیجانی بازار.'
                    : 'پایبندی به حد ضرر تعیین‌شده در پنل پارامترها.'}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3.5 space-y-1">
            <span className="text-text-muted block text-2xs font-bold">۳. هدف سود و خروج ۵۰٪ / سقف ۳:</span>
            <p className="text-accent-green font-bold leading-relaxed">
              {selectedPreset === 'swing'
                ? `خروج ۵۰٪ در R1 + خروج کامل در سقف ۳ کانال یا اخطار واگرایی منفی RSI.`
                : selectedPreset === 'trend'
                  ? `خروج ${toFaDigits(params.exitHalfPct)}٪ در مقاومت ماژور اول و نگهداری مابقی تا سقف سوم یا تغییر ساختار.`
                  : selectedPreset === 'hourglass'
                    ? 'نگهداری ۳ تا ۱۰ ساله و خروج در سقف تاریخی بعد از چرخه‌های صعودی کلان.'
                    : `خروج ${toFaDigits(params.exitHalfPct)}٪ در اولین سد مقاومتی.`}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3.5 space-y-1">
            <span className="text-text-muted block text-2xs font-bold">۴. قوانین سبد دارایی و شرایط جنگ:</span>
            <p className="text-text-primary font-medium leading-relaxed">
              {selectedPreset === 'swing'
                ? `تک‌سهم حداکثر ${toFaDigits(params.singleStockMaxWeightPct)}٪ (سقف صنعت ${toFaDigits(params.maxIndustryWeightPct)}٪) | سقف کل بورس ${toFaDigits(params.maxTotalPortfolioCapPct)}٪ (جنگ: ${toFaDigits(params.warConditionCapPct)}٪).`
                : selectedPreset === 'trend'
                  ? `وزن ۵ تا ۱۰ درصد برای هر تک‌سهم بنیادی (سقف صنعت ${toFaDigits(params.maxIndustryWeightPct)}٪) | سقف کل بورس ${toFaDigits(params.maxTotalPortfolioCapPct)}٪.`
                  : selectedPreset === 'hourglass'
                    ? `اهرم خرید ${toFaDigits(params.hourglassLeverageMultiplier)} برابری نسبت به پله عادی؛ تا ${toFaDigits(params.maxIndustryWeightPct)}٪ سبد در نمادهای مادر.`
                    : `رعایت سقف ${toFaDigits(params.maxIndustryWeightPct)}٪ صنعت و نسبت R/R حداقل ${toFaDigits(params.minRiskRewardRatio)}.`}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
