// features/master/routes/StrategyTreePage.tsx -- صفحه جامع درخت استراتژی FTS (۴ چارت در یک نما)
// بر پایه جزوه دوره نوسان‌گیری و سرمایه‌گذاری به سبک FTS (عرفان نصرتی) و چارت‌های درختی
import { useMemo, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { useFtsPlan } from '@features/master/api/useFtsPlan';
import { ObsidianStrategyGraph } from '../components/ObsidianStrategyGraph';
import {
  evaluateFtsPipeline,
  type StrategyHorizon,
  HORIZON_LABELS,
} from '../lib/ftsPipelineEvaluator';
import { runStrictGates, definiteDecision } from '../lib/strictGates';

type PresetMode = 'swing' | 'trend' | 'hourglass' | 'custom';
type ViewMode = 'obsidian' | 'grid' | 'both';

export default function StrategyTreePage() {
  const symbol = useSymbolStore((s) => s.symbol);
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const [selectedPreset, setSelectedPreset] = useState<PresetMode>('swing');
  const [viewMode, setViewMode] = useState<ViewMode>('both');

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
  const fundScore = typeof inputs.fundamental?.score === 'number' ? inputs.fundamental.score : null;

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
        tape: ['tape_clock', 'tape_breakout', 'tape_volume'],
        stop: ['stop_trend'],
        exit: ['exit_half'],
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
      const setupKey = nodeId.replace('setup_', '') as any;
      setCustomSetup(setupKey);
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

  return (
    <div className="flex flex-col gap-5 p-3 sm:p-5 max-w-[1700px] mx-auto w-full">
      {/* ۱. سربرگ و نوار کنترل */}
      <div className="glass-panel relative overflow-hidden rounded-2xl border border-border-c p-5 bg-bg-card/40 shadow-xl">
        <div className="pointer-events-none absolute -end-16 -top-16 h-48 w-48 rounded-full bg-accent-blue/15 blur-3xl" aria-hidden />

        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-accent-blue/20 text-lg font-black text-accent-blue shadow-[0_0_12px_rgba(56,189,248,0.25)]">
                🌳
              </span>
              <h1 className="text-base sm:text-lg font-black text-text-primary">
                نقشه راه و درخت جامع استراتژی FTS
              </h1>
              <span className="rounded-full border border-accent-blue/40 bg-accent-blue/10 px-2.5 py-0.5 text-2xs font-bold text-accent-blue">
                ۴ چارت در یک نما
              </span>
            </div>
            <p className="text-xs text-text-muted leading-relaxed">
              بر پایه آموزه‌های رسمی دوره نوسان‌گیری و سرمایه‌گذاری FTS (عرفان نصرتی)؛ با انتخاب هر استراتژی، مسیرهای مجاز روشن و بقیه کمرنگ می‌شوند.
            </p>
          </div>

          {/* نشانگر نماد فعال و دکمه تطبیق */}
          <div className="flex flex-wrap items-center gap-2.5">
            {symbol ? (
              <div className="flex items-center gap-2 rounded-xl border border-border-c bg-bg-primary/80 px-3 py-1.5 text-xs">
                <span className="text-text-muted">نماد فعال:</span>
                <strong className="text-accent-blue font-black">{symbol}</strong>
                {currentPrice && (
                  <span className="text-text-secondary font-mono">({toFaDigits(currentPrice)} ریال)</span>
                )}
                <button
                  type="button"
                  onClick={handleSyncWithSymbol}
                  className="rounded-lg bg-accent-blue/15 border border-accent-blue/40 px-2 py-0.5 text-2xs font-bold text-accent-blue hover:bg-accent-blue hover:text-black transition-colors"
                >
                  ⚡ تطبیق درخت با {symbol}
                </button>
              </div>
            ) : (
              <div className="text-2xs text-text-muted rounded-xl border border-border-c bg-bg-primary/60 px-3 py-1.5">
                نمادی انتخاب نشده؛ درخت به عنوان راهنمای کلان استراتژی در دسترس است.
              </div>
            )}
          </div>
        </div>

        {/* سوییچر سبک معامله / حالت بازی (Persona & Game Switcher) + سوییچ نحوه نما */}
        <div className="mt-4 pt-4 border-t border-border-c/60 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs font-bold text-text-secondary">سبک و مسیر بازی:</span>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              <button
                type="button"
                onClick={() => setSelectedPreset('swing')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                  selectedPreset === 'swing'
                    ? 'border-accent-blue bg-accent-blue/20 text-accent-blue shadow-[0_0_12px_rgba(56,189,248,0.25)]'
                    : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
                }`}
              >
                <span>⚡</span>
                <span>شخص نوسان‌گیر (زیر ۳ ماه)</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedPreset('trend')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                  selectedPreset === 'trend'
                    ? 'border-accent-green bg-accent-green/20 text-accent-green shadow-[0_0_12px_rgba(34,197,94,0.25)]'
                    : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
                }`}
              >
                <span>📈</span>
                <span>شخص روندگیر (بالای ۳ ماه)</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedPreset('hourglass')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                  selectedPreset === 'hourglass'
                    ? 'border-accent-yellow bg-accent-yellow/20 text-accent-yellow shadow-[0_0_12px_rgba(234,179,8,0.25)]'
                    : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
                }`}
              >
                <span>⏳</span>
                <span>استراتژی ساعت شنی (۳ تا ۱۰ ساله)</span>
              </button>

              <button
                type="button"
                onClick={() => setSelectedPreset('custom')}
                className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                  selectedPreset === 'custom'
                    ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan shadow-[0_0_12px_rgba(6,182,212,0.25)]'
                    : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
                }`}
              >
                <span>🛠</span>
                <span>مسیر سفارشی (انتخاب دستی)</span>
              </button>
            </div>
          </div>

          {/* سوییچ نما: نمودار شبکه ابسیدین vs نمای گرید ۴ چارت */}
          <div className="flex items-center gap-1 rounded-xl border border-border-c/70 bg-bg-primary/90 p-1 ms-auto">
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
              onClick={() => setViewMode('both')}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                viewMode === 'both'
                  ? 'bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan shadow-[0_0_8px_rgba(6,182,212,0.25)]'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🔀</span>
              <span>ترکیبی (هر دو)</span>
            </button>
          </div>
        </div>
      </div>

      {/* ۲. نمودار شبکه تعاملی سبک ابسیدین (Obsidian Strategy Graph) */}
      {(viewMode === 'obsidian' || viewMode === 'both') && (
        <ObsidianStrategyGraph
          selectedPreset={selectedPreset}
          onSelectPreset={setSelectedPreset}
          symbol={symbol}
          activeCustomNodes={activeCustomNodeIds}
          onToggleCustomNode={handleToggleCustomNode}
        />
      )}

      {/* ۳. چارت درختی ۴ مرحله‌ای بصری و ستونی (Unified 4-Stage Tree Column Grid) */}
      {(viewMode === 'grid' || viewMode === 'both') && (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* ═══════════ فاز ۱: بنیادی F (۵ شاخص FTS) ═══════════ */}
        <div className="glass-panel rounded-2xl border border-border-c/80 bg-bg-card/30 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-green/20 text-xs font-black text-accent-green">
                F
              </span>
              <h2 className="text-xs font-black text-text-primary">
                ۱. فیلتر بنیادی (۵ شاخص کدال)
              </h2>
            </div>
            <span className="text-3xs rounded bg-bg-primary px-1.5 py-0.5 text-text-muted">
              چارت صفحه ۱
            </span>
          </div>

          <div className="space-y-2">
            {/* شاخص سوپربنیادی ۵ از ۵ */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomFund('super');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.fund.includes('fund_super')
                  ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">💎 سوپربنیادی (امتیاز ۵ از ۵)</strong>
                <span className="text-3xs text-accent-green font-bold">عالی</span>
              </div>
              <ul className="text-2xs text-text-muted space-y-0.5 leading-relaxed">
                <li>● رشد فروش ماهانه کدال نسبت به پارسال &gt; ۴۰٪</li>
                <li>● سودآوری ۳ ساله (EPS صعودی)</li>
                <li>● حاشیه سود ناخالص &gt; ۳۰٪ (حداقل ۲۰٪)</li>
                <li>● نسبت فروش ۳ ماهه × ۴ به ارزش بازار</li>
                <li>● صنایع دلاری/جهانی بدون قیمت‌گذاری دستوری</li>
              </ul>
            </div>

            {/* بنیادی خوب ۴ از ۵ */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomFund('good');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.fund.includes('fund_good')
                  ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">بنیادی مطلوب (۴ از ۵ FTS)</strong>
                <span className="text-3xs text-accent-blue font-bold">تایید روندی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                رشد فروش و سودآوری ۳ ساله مثبت، حاشیه سود بالای ۲۰٪؛ مناسب برای ورود روندی بالای ۳ ماه.
              </p>
            </div>

            {/* بنیادی متوسط ۳ از ۵ */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomFund('medium');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.fund.includes('fund_medium')
                  ? 'border-accent-yellow bg-accent-yellow/15 shadow-[0_0_12px_rgba(234,179,8,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">بنیاد متوسط (۳ از ۵ FTS)</strong>
                <span className="text-3xs text-accent-yellow font-bold">صرفاً نوسانی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                فاقد سودآوری ۳ ساله اما دارای رشد فروش فصلی؛ صرفاً نوسان‌گیری با ستاپ جت مجاز است.
              </p>
            </div>

            {/* رد بنیادی */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomFund('weak');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.fund.includes('fund_weak')
                  ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-accent-red">⛔ رد بنیادی (زیر ۳ از ۵ یا زیان‌ده)</strong>
                <span className="text-3xs text-accent-red font-bold">توقف</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                صنایع مشمول نرخ‌گذاری دستوری شدید (خودرو/قطعات) یا افت شدید حاشیه سود به زیر ۲۰٪.
              </p>
            </div>
          </div>
        </div>

        {/* ═══════════ فاز ۲: تکنیکال دو زمانه T ═══════════ */}
        <div className="glass-panel rounded-2xl border border-border-c/80 bg-bg-card/30 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-neon-cyan/20 text-xs font-black text-neon-cyan">
                T
              </span>
              <h2 className="text-xs font-black text-text-primary">
                ۲. فیلتر تکنیکال ۲ زمانه
              </h2>
            </div>
            <span className="text-3xs rounded bg-bg-primary px-1.5 py-0.5 text-text-muted">
              چارت صفحه ۲
            </span>
          </div>

          <div className="space-y-2">
            {/* شاخه هفتگی صعودی */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomWeekly('up');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.weekly.includes('tech_weekly_up') || activeNodes.weekly.includes('tech_weekly_hourglass')
                  ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">تایم هفتگی صعودی (تایید ماژور)</strong>
                <span className="text-3xs text-accent-green font-bold">مجوز ورود</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                تشکیل سقف‌ها و کف‌های بالاتر؛ شرط لازم برای ورود به ستاپ‌های روزانه.
              </p>
            </div>

            {/* ستاپ جت روزانه */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomSetup('jet');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.setup.includes('setup_jet')
                  ? 'border-neon-cyan bg-neon-cyan/15 shadow-[0_0_12px_rgba(6,182,212,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-neon-cyan">🚀 استراتژی جت (Jet Breakout)</strong>
                <span className="text-3xs text-neon-cyan font-bold">ستاپ پرتاب</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                عبور از سقف تاریخی یا مقاومت استاتیک با کندل پرقدرت؛ تا ۳ روز فرصت ورود پله‌ای وجود دارد.
              </p>
            </div>

            {/* ستاپ فیبوناچی و پولبک */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomSetup('fib');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.setup.includes('setup_fib')
                  ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-accent-blue">ستاپ فیبوناچی ۳۳-۴۰ و ۶۱.۸-۷۰</strong>
                <span className="text-3xs text-accent-blue font-bold">پله‌های ورود</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                پله اول در تراز ۳۳ تا ۴۰ فیبو، پله دوم در تراز ۶۱.۸ تا ۷۰ درصد؛ اصلاح سالم در روند صعودی.
              </p>
            </div>

            {/* ستاپ CHoCH و کف دوقلو */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomSetup('choch');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.setup.includes('setup_choch') || activeNodes.setup.includes('setup_double_bottom')
                  ? 'border-purple-500 bg-purple-500/15 shadow-[0_0_12px_rgba(168,85,247,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">تغییر ساختار CHoCH / کف دوقلو</strong>
                <span className="text-3xs text-purple-400 font-bold">بازگشتی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                شکست آخرین سقف در روند نزولی یا شکست خط گردن کف دوقلو با پولبک.
              </p>
            </div>

            {/* ریجکت هفتگی */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomWeekly('reject');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.weekly.includes('tech_weekly_reject')
                  ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-accent-red">ریجکت هفتگی (Reject صلب)</strong>
                <span className="text-3xs text-accent-red font-bold">وتو</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                روند هفتگی نزولی یا خنثی؛ طبق صفحه ۲ جزوه هرگونه ورود اکیداً ممنوع و ریجکت است.
              </p>
            </div>
          </div>
        </div>

        {/* ═══════════ فاز ۳: تابلوخوانی و غربالگری S ═══════════ */}
        <div className="glass-panel rounded-2xl border border-border-c/80 bg-bg-card/30 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-yellow/20 text-xs font-black text-accent-yellow">
                S
              </span>
              <h2 className="text-xs font-black text-text-primary">
                ۳. تابلوخوانی و زمان‌سنج (S)
              </h2>
            </div>
            <span className="text-3xs rounded bg-bg-primary px-1.5 py-0.5 text-text-muted">
              چارت صفحه ۳
            </span>
          </div>

          <div className="space-y-2">
            {/* الگوی ساعت */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomTape('clock');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.tape.includes('tape_clock')
                  ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">⏰ الگوی ساعت FTS</strong>
                <span className="text-3xs text-accent-green font-bold">زمان‌سنج ورود</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                قیمت آخرین معامله بیش از ۱٪ بالاتر از قیمت پایانی (بهترین حالت: پایانی منفی و آخرین مثبت)؛ احتمال بالای بازگشایی مثبت فردا.
              </p>
            </div>

            {/* حجم مشکوک ۳ برابری */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomTape('suspicious_vol');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.tape.includes('tape_volume')
                  ? 'border-neon-cyan bg-neon-cyan/15 shadow-[0_0_12px_rgba(6,182,212,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-neon-cyan">حجم مشکوک (۳ برابر میانگین)</strong>
                <span className="text-3xs text-neon-cyan font-bold">ورود پول هوشمند</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                حجم معاملات امروز حداقل ۳ برابر میانگین ۲۱ روزه ماهانه؛ نشانه ورود کدهای درشت و دست‌به‌دست شدن سهم.
              </p>
            </div>

            {/* خروج از باکس رنج */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomTape('box_break');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.tape.includes('tape_breakout')
                  ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">خروج از باکس رنج (Breakout)</strong>
                <span className="text-3xs text-accent-blue font-bold">آغاز موج</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                شکست سقف باکس رنج با کندل پرقدرت + رشد حجم معاملات + ورود پول و الگوی ساعت.
              </p>
            </div>

            {/* کف‌روبی و خشک کردن سهم */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomTape('floor_sweep');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.tape.includes('tape_floor_sweep')
                  ? 'border-purple-500 bg-purple-500/15 shadow-[0_0_12px_rgba(168,85,247,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">کف‌روبی صف فروش / خشک کردن</strong>
                <span className="text-3xs text-purple-400 font-bold">جمع‌آوری</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                سهم صف فروش است اما سفارش‌های خرید قوی در حال بلعیدن صف هستند؛ یا فروشنده‌ها کاملاً خشک شده‌اند.
              </p>
            </div>
          </div>
        </div>

        {/* ═══════════ فاز ۴: مدیریت سرمایه و پلن خروج ═══════════ */}
        <div className="glass-panel rounded-2xl border border-border-c/80 bg-bg-card/30 p-4 space-y-3">
          <div className="flex items-center justify-between border-b border-border-c/60 pb-2.5">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-accent-blue/20 text-xs font-black text-accent-blue">
                M
              </span>
              <h2 className="text-xs font-black text-text-primary">
                ۴. مدیریت سرمایه و خروج
              </h2>
            </div>
            <span className="text-3xs rounded bg-bg-primary px-1.5 py-0.5 text-text-muted">
              چارت صفحه ۴
            </span>
          </div>

          <div className="space-y-2">
            {/* حد ضرر نوسان‌گیر */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomStop('ma14_fixed5');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.stop.includes('stop_swing')
                  ? 'border-accent-red bg-accent-red/15 shadow-[0_0_12px_rgba(239,68,68,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">حد ضرر صلب نوسان‌گیر</strong>
                <span className="text-3xs text-accent-red font-bold">استاپ تکنیکالی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                تشکیل یک کندل کامل زیر میانگین متحرک ۱۴ (MA=14) یا افت ۵٪ زیر نقطه ورود یا آخرین کف صعودی؛ خروج بی‌چون‌وچرا.
              </p>
            </div>

            {/* حد ضرر روندگیر */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomStop('codal_fund');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.stop.includes('stop_trend')
                  ? 'border-accent-green bg-accent-green/15 shadow-[0_0_12px_rgba(34,197,94,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-text-primary">حد ضرر بنیادی روندگیر</strong>
                <span className="text-3xs text-accent-green font-bold">کدال و فصلی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                شخص روندگیر حد ضرر تکنیکالی ندارد؛ حد ضرر در صورت‌های مالی است: توقف رشد فروش ماهانه یا افت حاشیه سود به زیر ۲۰٪.
              </p>
            </div>

            {/* استراتژی ساعت شنی */}
            <div
              onClick={() => {
                setSelectedPreset('custom');
                setCustomStop('hourglass_deep');
              }}
              className={`cursor-pointer rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.stop.includes('stop_hourglass')
                  ? 'border-accent-yellow bg-accent-yellow/15 shadow-[0_0_12px_rgba(234,179,8,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35 hover:opacity-75'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-accent-yellow">اهرم ساعت شنی (۲ تا ۴ برابر)</strong>
                <span className="text-3xs text-accent-yellow font-bold">کف تاریخی</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                سهام بزرگ بنیادی در تایم هفتگی زیر MA=52 و RSI زیر ۷ در اشباع عمیق؛ خرید سنگین پله‌ای به دید ۳ تا ۱۰ ساله.
              </p>
            </div>

            {/* قانون ذخیره سود ۵۰٪ */}
            <div
              className={`rounded-xl border p-3 transition-all duration-200 ${
                activeNodes.exit.includes('exit_half')
                  ? 'border-accent-blue bg-accent-blue/15 shadow-[0_0_12px_rgba(56,189,248,0.2)] opacity-100 scale-[1.01]'
                  : 'border-border-c/60 bg-bg-primary/60 opacity-35'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <strong className="text-xs font-black text-accent-blue">قانون ذخیره سود ۵۰٪ FTS</strong>
                <span className="text-3xs text-accent-blue font-bold">خروج اصل پول</span>
              </div>
              <p className="text-2xs text-text-muted leading-relaxed">
                در برخورد با مقاومت اول R1 یا سقف موج، ۵۰٪ سهم فروخته می‌شود تا اصل سرمایه آزاد شده و ادامه معامله بدون ریسک شود.
              </p>
            </div>
          </div>
        </div>
      </div>
    )}

      {/* ۳. کارت جامع دستورالعمل و خلاصه پلن اجرایی استراتژی (Strategy Playbook Summary) */}
      <div className="glass-panel rounded-2xl border border-border-c p-5 bg-bg-card/40 shadow-xl space-y-3">
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

        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 text-2xs">
          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3">
            <span className="text-text-muted block mb-1">۱. شرط ورود و زمان‌سنج:</span>
            <p className="text-text-primary font-medium leading-relaxed">
              {selectedPreset === 'swing'
                ? 'شکست مقاومت استاتیک با ستاپ جت یا تراز ۳۳-۴۰ فیبو + تایید الگوی ساعت یا حجم ۳ برابری.'
                : selectedPreset === 'trend'
                  ? 'روند هفتگی صعودی + تایید ۵ شاخص بنیادی کدال + ورود پول حقیقی از صندوق درآمد ثابت.'
                  : selectedPreset === 'hourglass'
                    ? 'نماد سوپربنیادی شاخص‌ساز در تایم هفتگی زیر MA-52 و اشباع عمیق RSI زیر ۷.'
                    : 'ترکیب سفارشی شاخص‌های انتخاب‌شده در درخت بالا.'}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3">
            <span className="text-text-muted block mb-1">۲. حد ضرر و مدیریت ریسک:</span>
            <p className="text-accent-red font-bold leading-relaxed">
              {selectedPreset === 'swing'
                ? 'تشکیل یک کندل کامل زیر MA-14 یا افت ۵٪ زیر نقطه ورود (خروج قطعی).'
                : selectedPreset === 'trend'
                  ? 'حد ضرر بنیادی در صورت‌های مالی فصلی کدال (افت رشد فروش یا حاشیه سود).'
                  : selectedPreset === 'hourglass'
                    ? 'بدون حد ضرر نوسانی کوتاه‌مدت؛ پله‌بندی سنگین در افت‌های هیجانی بازار.'
                    : 'پایبندی به حد ضرر انتخاب‌شده در گام چهارم.'}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3">
            <span className="text-text-muted block mb-1">۳. هدف سود و خروج ۵۰٪:</span>
            <p className="text-accent-green font-bold leading-relaxed">
              {selectedPreset === 'swing'
                ? 'خروج کامل در مقاومت اول R1 یا خروج ۵۰٪ جهت آزادسازی اصل سرمایه.'
                : selectedPreset === 'trend'
                  ? 'خروج ۵۰٪ در سقف مقاومت ماژور اول و نگهداری ۵۰٪ سود تا سقف سوم یا تغییر ساختار.'
                  : selectedPreset === 'hourglass'
                    ? 'نگهداری ۳ تا ۱۰ ساله و خروج در سقف تاریخی بعد از چرخه‌های صعودی بازار.'
                    : 'خروج ۵۰٪ در اولین سد مقاومتی سهم.'}
            </p>
          </div>

          <div className="rounded-xl border border-border-c/60 bg-bg-primary/70 p-3">
            <span className="text-text-muted block mb-1">۴. وزن و سقف مجاز سبد:</span>
            <p className="text-text-primary font-medium leading-relaxed">
              {selectedPreset === 'swing'
                ? 'حداکثر ۲ تا ۳.۵ درصد کل پورتفوی به هر تک‌سهم نوسانی.'
                : selectedPreset === 'trend'
                  ? 'وزن ۵ تا ۱۰ درصد برای هر تک‌سهم بنیادی (سقف هر صنعت ۲۰٪).'
                  : selectedPreset === 'hourglass'
                    ? 'اهرم خرید ۲ تا ۴ برابری نسبت به پله عادی؛ تا ۲۰٪ سبد در نمادهای مادر.'
                    : 'رعایت سقف ۲۰٪ صنعت و سقف ۷۰٪ کل دارایی در بورس.'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
