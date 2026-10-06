// features/master/routes/StrategyTreePage.tsx -- صفحه نقشه راه و درخت تصمیم‌گیری FTS
// بر پایه چارت ۴ صفحه‌ای و جزوه دوره نوسان‌گیری و سرمایه‌گذاری FTS (عرفان نصرتی)
// مهندسی معکوس FTS: انتخاب سبک -> تابلوخوانی (S) -> تکنیکال (T) -> بنیادی (F) -> تحویل -> مدیریت سرمایه (صفحه ۴)

import { useMemo, useState, useRef, useEffect } from 'react';
import { toFaDigits, fmtInt } from '@shared/lib/fmt';
import { matchFa } from '@shared/lib/normalizeFa';
import { ftsScoreOf } from '@contracts/fundamental';
import { useParams } from 'react-router';
import { useSymbolStore } from '@shared/stores/symbolStore';
import { getActiveSignals, useSignalStore } from '@shared/stores/signalStore';
import { useMarketCloses } from '@features/portfolio/api/usePortfolio';
import { useMarketFeed } from '@features/market/api/useMarketFeed';
import { useFtsPlan } from '@features/master/api/useFtsPlan';
import { useFtsFunnel } from '../api/useFtsFunnel';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import {
  useTreeFlowStore,
  TREE_FLOW_LABEL,
  TREE_FLOW_HINT,
} from '../stores/treeFlowStore';
import { runStrictGates, definiteDecision } from '../lib/strictGates';
import { evaluateFtsPipeline } from '../lib/ftsPipelineEvaluator';
import { buildCanonicalStrategyGraph } from '../lib/strategyGraphModel';
import { StrategyGraphRenderer, type StrategyLayoutMode } from '../components/StrategyGraphRenderer';
import { StrategyStageCandidateTable } from '../components/StrategyStageCandidateTable';
import type { FunnelStageKey } from '../lib/ftsFunnel';

type PresetMode = 'swing' | 'trend' | 'hourglass' | 'custom';

export default function StrategyTreePage() {
  const { symbol: routeSymbol } = useParams();
  const storedSymbol = useSymbolStore((s) => s.symbol);
  const symbol = routeSymbol ?? storedSymbol;
  const setSymbol = useSymbolStore((s) => s.setSymbol);
  const clearSymbol = useSymbolStore((s) => s.clearSymbol);

  const [selectedPreset, setSelectedPreset] = useState<PresetMode>('swing');
  const [layoutMode, setLayoutMode] = useState<StrategyLayoutMode>('flow');
  const params = useStrategyParamsStore((s) => s.params);

  // وضعیت کشوی جدول کاندیداهای هر مرحله
  const [activeStageDrawer, setActiveStageDrawer] = useState<FunnelStageKey | null>(null);

  // هوک قیف کانونی FTS برای دریافت کاندیداهای زنده هر مرحله
  const { funnel, loading: funnelLoading } = useFtsFunnel();

  // وضعیت جستجوی نماد
  const [searchQuery, setSearchQuery] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const searchContainerRef = useRef<HTMLDivElement>(null);

  // خوراک بازار برای اتوکامپلیت نماد
  const marketFeed = useMarketFeed();
  const marketRows = useMemo(() => marketFeed.data?.data ?? [], [marketFeed.data]);

  const treeFlow = useTreeFlowStore((st) => st.mode);
  const setTreeFlow = useTreeFlowStore((st) => st.setMode);

  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.trim();
    return marketRows
      .filter((r) => r.symbol && (matchFa(r.symbol, q) || matchFa(r.name, q)))
      .slice(0, 8);
  }, [marketRows, searchQuery]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // داده‌های زنده نماد
  const entry = useSignalStore((s) => (symbol ? s.bus[symbol] : undefined));
  const inputs = useMemo(() => (symbol ? getActiveSignals(symbol) : {}), [symbol, entry]);
  const closes = useMarketCloses();
  const ftsPlan = useFtsPlan(symbol);
  const currentPrice = (symbol ? closes.data?.get(symbol) : null) ?? null;
  const resistance = ftsPlan.data?.fts?.jet?.resistance ?? null;
  const support = ftsPlan.data?.fts?.fib?.zone_33_40?.lo ?? null;
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

  // اعمال مستقیم نماد بر درخت به محض انتخاب از سرچ
  const handleSelectSymbol = (sym: string) => {
    setSymbol(sym);
    setSearchQuery('');
    setSearchOpen(false);
  };

  // ساخت گراف کانونی FTS
  const canonicalGraph = useMemo(
    () =>
      buildCanonicalStrategyGraph({
        params,
        selectedPreset,
        steps: evaluation.steps,
        symbol,
        searchQuery,
      }),
    [params, selectedPreset, evaluation.steps, symbol, searchQuery],
  );

  // آمار مرحله‌به‌مرحله کاهش Universe از داده‌های زنده
  const stageStats = useMemo(() => {
    const universeCount = funnel.total;
    const tapeStage = funnel.stages.tape;
    const techStage = funnel.stages.technical;
    const fundStage = funnel.stages.fundamental;
    const handoverStage = funnel.stages.handover;

    return {
      universeCount,
      tape: {
        total: tapeStage?.entries.length ?? 0,
        pass: tapeStage?.summary.pass ?? 0,
        reject: tapeStage?.summary.reject ?? 0,
      },
      technical: {
        total: techStage?.entries.length ?? 0,
        pass: techStage?.summary.pass ?? 0,
        reject: techStage?.summary.reject ?? 0,
      },
      fundamental: {
        total: fundStage?.entries.length ?? 0,
        pass: fundStage?.summary.pass ?? 0,
        reject: fundStage?.summary.reject ?? 0,
      },
      handover: {
        total: handoverStage?.entries.length ?? 0,
        pass: handoverStage?.summary.pass ?? 0,
      },
    };
  }, [funnel]);

  return (
    <div className="flex flex-col gap-3 sm:gap-4 p-3 sm:p-5 max-w-[1700px] mx-auto w-full">
      {/* ۱. نوار ابزار اصلی بالای نقشه راه */}
      <div className="rounded-2xl border border-border-c bg-bg-card/80 p-3 sm:p-4 shadow-sm flex flex-col gap-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {/* سمت راست: عنوان و جستجوی تعاملی نماد */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-accent-blue/15 text-sm font-black text-accent-blue">
                🗺️
              </span>
              <div>
                <h1 className="text-xs sm:text-sm font-black text-text-primary">
                  نقشه راه و درخت جامع استراتژی FTS
                </h1>
                <p className="text-3xs text-text-muted">
                  ۴ چارت در یک نما · مهندسی معکوس: سبک ➔ تابلو (S) ➔ تکنیکال (T) ➔ بنیادی (F) ➔ تحویل ➔ سرمایه
                </p>
              </div>
            </div>

            {/* جعبه جستجوی تعاملی نماد */}
            <div ref={searchContainerRef} className="relative">
              <input
                type="text"
                placeholder="جستجوی نماد برای تطبیق زنده..."
                value={searchQuery}
                onFocus={() => setSearchOpen(true)}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setSearchOpen(true);
                }}
                className="h-8 w-44 sm:w-56 rounded-xl border border-border-c bg-bg-primary px-2.5 text-xs text-text-primary placeholder:text-text-muted focus:border-border-accent focus:outline-none transition-all"
              />
              {searchOpen && searchResults.length > 0 && (
                <div className="absolute top-9 start-0 z-50 w-60 rounded-xl border border-border-c bg-bg-card shadow-xl overflow-hidden py-1">
                  {searchResults.map((r) => (
                    <button
                      key={r.symbol}
                      type="button"
                      onClick={() => handleSelectSymbol(r.symbol)}
                      className="w-full px-3 py-1.5 text-start hover:bg-bg-secondary flex items-center justify-between text-xs transition-colors"
                    >
                      <span className="font-black text-accent-blue">{r.symbol}</span>
                      <span className="text-2xs text-text-muted truncate max-w-[120px]">{r.name}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* نماد انتخاب‌شده جاری */}
            {symbol ? (
              <div className="flex items-center gap-1.5 rounded-xl border border-accent-blue/40 bg-accent-blue/10 px-2.5 py-1 text-2xs font-black text-accent-blue">
                <span>نماد فعال:</span>
                <span className="text-xs">{symbol}</span>
                {currentPrice != null && (
                  <span className="font-mono text-text-secondary">({fmtInt(currentPrice)})</span>
                )}
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
                (راهنمای کلان استراتژی — با سرچ نماد، وضعیت سهم روی نقشه راه اعمال می‌شود)
              </span>
            )}
          </div>

          {/* سمت چپ: تنظیمات نمایش و چیدمان */}
          <div className="flex items-center gap-2 flex-wrap ms-auto">
            {/* جریانِ مسیر */}
            <div
              className="flex items-center gap-1 rounded-xl border border-border-c/70 bg-bg-primary p-1"
              role="group"
              aria-label="جریانِ مسیرِ درخت"
              data-testid="tree-flow-toggle"
              title={TREE_FLOW_HINT[treeFlow]}
            >
              <span className="px-1 text-2xs text-text-muted font-bold">جریانِ مسیر:</span>
              {(['always', 'system', 'off'] as const).map((m) => (
                <button
                  key={m}
                  type="button"
                  onClick={() => setTreeFlow(m)}
                  aria-pressed={treeFlow === m}
                  data-testid={`tree-flow-${m}`}
                  className={`rounded-lg px-2 py-0.5 text-2xs font-bold transition-all ${
                    treeFlow === m
                      ? 'bg-accent-cyan/20 border border-accent-cyan/50 text-accent-cyan'
                      : 'text-text-muted hover:text-text-primary'
                  }`}
                >
                  {TREE_FLOW_LABEL[m]}
                </button>
              ))}
            </div>

            {/* سوییچر چیدمان: نقشه راه (Roadmap) یا مداری (Orbit) */}
            <div
              className="flex items-center gap-1 rounded-xl border border-border-c/70 bg-bg-primary p-1"
              role="group"
              aria-label="چیدمان نقشه راه استراتژی"
            >
              <button
                type="button"
                onClick={() => setLayoutMode('flow')}
                aria-pressed={layoutMode === 'flow'}
                data-testid="tree-layout-flow"
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                  layoutMode === 'flow'
                    ? 'bg-accent-blue/20 border border-accent-blue/50 text-accent-blue shadow-xs'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                <span>🔀</span>
                <span>نقشه راه FTS</span>
              </button>
              <button
                type="button"
                onClick={() => setLayoutMode('orbit')}
                aria-pressed={layoutMode === 'orbit'}
                data-testid="tree-layout-orbit"
                className={`flex items-center gap-1 rounded-lg px-2.5 py-1 text-2xs font-black transition-all ${
                  layoutMode === 'orbit'
                    ? 'bg-neon-cyan/20 border border-neon-cyan/50 text-neon-cyan shadow-xs'
                    : 'text-text-muted hover:text-text-primary'
                }`}
              >
                <span>🪐</span>
                <span>چیدمان مداری (Orbit)</span>
              </button>
            </div>
          </div>
        </div>

        {/* سوییچر سبک معامله — نوسان‌گیر / روندگیر / ساعت شنی / سفارشی */}
        <div className="pt-2 border-t border-border-c/50 flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-text-secondary" data-testid="tree-preset-label">
            انتخاب سبک معامله:
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 w-full sm:w-auto">
            <button
              type="button"
              onClick={() => setSelectedPreset('swing')}
              className={`flex items-center gap-1.5 rounded-xl border px-3 py-1.5 text-xs font-bold transition-all ${
                selectedPreset === 'swing'
                  ? 'border-accent-blue bg-accent-blue/20 text-accent-blue shadow-[0_0_10px_rgba(56,189,248,0.25)] font-black'
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
                  ? 'border-accent-green bg-accent-green/20 text-accent-green shadow-[0_0_10px_rgba(34,197,94,0.25)] font-black'
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
                  ? 'border-accent-yellow bg-accent-yellow/20 text-accent-yellow shadow-[0_0_10px_rgba(234,179,8,0.25)] font-black'
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
                  ? 'border-neon-cyan bg-neon-cyan/20 text-neon-cyan shadow-[0_0_10px_rgba(6,182,212,0.25)] font-black'
                  : 'border-border-c/70 bg-bg-primary text-text-muted hover:text-text-primary'
              }`}
            >
              <span>🛠</span>
              <span>مسیر سفارشی (انتخاب دستی)</span>
            </button>
          </div>
        </div>
      </div>

      {/* ۲. نوار تعاملی غربالگری مرحله‌به‌مرحله و کاهش Universe (Funnel Progression Bar) */}
      <div className="rounded-2xl border border-border-c/90 bg-bg-card p-3 shadow-xs">
        <div className="flex items-center justify-between pb-2 mb-2 border-b border-border-c/60 flex-wrap gap-2">
          <div className="flex items-center gap-2">
            <span className="text-xs font-black text-text-primary">
              📊 کاهش کاندیداها در قیف FTS (Stage-by-Stage Universe Reduction)
            </span>
            <span className="text-3xs text-text-muted">
              {funnelLoading ? 'در حال تازه‌سازی خوراک...' : 'محاسبه‌شده بر اساس داده‌های زنده بازار و کدال'}
            </span>
          </div>
          <span className="text-2xs font-mono font-bold text-text-muted">
            کل Universe بازار: {toFaDigits(stageStats.universeCount)} نماد
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
          {/* مرحله ۱: تابلوخوانی S */}
          <div className="flex flex-col justify-between rounded-xl border border-accent-yellow/40 bg-accent-yellow/5 p-2.5">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-2xs font-black text-accent-yellow flex items-center gap-1">
                  <span>⏱️</span>
                  <span>گام ۱: تابلوخوانی (S)</span>
                </span>
                <span className="rounded bg-bg-card px-1.5 py-0.5 text-3xs font-bold text-text-muted border border-border-c">
                  ص ۳ چارت
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-1.5 font-mono">
                <span className="text-lg font-black text-text-primary">
                  {toFaDigits(stageStats.tape.total)}
                </span>
                <span className="text-3xs text-text-muted font-sans">نماد واجد شرایط تابلو</span>
              </div>
              <div className="text-3xs text-text-secondary mt-1 space-x-1 space-x-reverse font-medium">
                <span className="text-accent-green font-bold">تایید: {toFaDigits(stageStats.tape.pass)}</span>
                <span>·</span>
                <span className="text-accent-red font-bold">رد: {toFaDigits(stageStats.tape.reject)}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveStageDrawer('tape')}
              className="mt-2.5 w-full rounded-lg bg-accent-yellow/15 hover:bg-accent-yellow hover:text-black text-accent-yellow py-1 text-2xs font-black transition-colors"
            >
              مشاهده کاندیداهای تابلو ➔
            </button>
          </div>

          {/* مرحله ۲: تکنیکال T */}
          <div className="flex flex-col justify-between rounded-xl border border-accent-blue/40 bg-accent-blue/5 p-2.5">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-2xs font-black text-accent-blue flex items-center gap-1">
                  <span>📈</span>
                  <span>گام ۲: تکنیکال ۲ زمانه (T)</span>
                </span>
                <span className="rounded bg-bg-card px-1.5 py-0.5 text-3xs font-bold text-text-muted border border-border-c">
                  ص ۲ چارت
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-1.5 font-mono">
                <span className="text-lg font-black text-text-primary">
                  {toFaDigits(stageStats.technical.total)}
                </span>
                <span className="text-3xs text-text-muted font-sans">نماد عبوری به تکنیکال</span>
              </div>
              <div className="text-3xs text-text-secondary mt-1 space-x-1 space-x-reverse font-medium">
                <span className="text-accent-green font-bold">تایید هفتگی: {toFaDigits(stageStats.technical.pass)}</span>
                <span>·</span>
                <span className="text-accent-red font-bold">وتو: {toFaDigits(stageStats.technical.reject)}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveStageDrawer('technical')}
              className="mt-2.5 w-full rounded-lg bg-accent-blue/15 hover:bg-accent-blue hover:text-black text-accent-blue py-1 text-2xs font-black transition-colors"
            >
              مشاهده کاندیداهای تکنیکال ➔
            </button>
          </div>

          {/* مرحله ۳: بنیادی F */}
          <div className="flex flex-col justify-between rounded-xl border border-accent-green/40 bg-accent-green/5 p-2.5">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-2xs font-black text-accent-green flex items-center gap-1">
                  <span>🏛️</span>
                  <span>گام ۳: بنیادی ۵ شاخص (F)</span>
                </span>
                <span className="rounded bg-bg-card px-1.5 py-0.5 text-3xs font-bold text-text-muted border border-border-c">
                  ص ۱ چارت
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-1.5 font-mono">
                <span className="text-lg font-black text-text-primary">
                  {toFaDigits(stageStats.fundamental.total)}
                </span>
                <span className="text-3xs text-text-muted font-sans">نماد عبوری به بنیادی</span>
              </div>
              <div className="text-3xs text-text-secondary mt-1 space-x-1 space-x-reverse font-medium">
                <span className="text-accent-green font-bold">تایید کدال: {toFaDigits(stageStats.fundamental.pass)}</span>
                <span>·</span>
                <span className="text-accent-red font-bold">رد: {toFaDigits(stageStats.fundamental.reject)}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveStageDrawer('fundamental')}
              className="mt-2.5 w-full rounded-lg bg-accent-green/15 hover:bg-accent-green hover:text-black text-accent-green py-1 text-2xs font-black transition-colors"
            >
              مشاهده کاندیداهای بنیادی ➔
            </button>
          </div>

          {/* مرحله ۴: تحویل نهایی Delivery */}
          <div className="flex flex-col justify-between rounded-xl border border-emerald-500/40 bg-emerald-500/5 p-2.5">
            <div>
              <div className="flex items-center justify-between">
                <span className="text-2xs font-black text-emerald-400 flex items-center gap-1">
                  <span>📦</span>
                  <span>تحویل نهایی (Delivery)</span>
                </span>
                <span className="rounded bg-bg-card px-1.5 py-0.5 text-3xs font-bold text-text-muted border border-border-c">
                  ص ۴ چارت
                </span>
              </div>
              <div className="mt-2 flex items-baseline gap-1.5 font-mono">
                <span className="text-lg font-black text-emerald-400">
                  {toFaDigits(stageStats.handover.total)}
                </span>
                <span className="text-3xs text-text-muted font-sans">نماد نهایی آماده معامله</span>
              </div>
              <div className="text-3xs text-emerald-400/80 mt-1 font-medium">
                آماده تصمیم‌گیری کاربر، سبدچینی و مدیریت سرمایه
              </div>
            </div>
            <button
              type="button"
              onClick={() => setActiveStageDrawer('handover')}
              className="mt-2.5 w-full rounded-lg bg-emerald-500/20 hover:bg-emerald-500 hover:text-black text-emerald-400 py-1 text-2xs font-black transition-colors"
            >
              مشاهده تحویل نهایی ➔
            </button>
          </div>
        </div>
      </div>

      {/* ۳. بوم تعاملی گراف استراتژی FTS (نقشه راه یا چیدمان مداری) */}
      <div className="w-full">
        <StrategyGraphRenderer
          graph={canonicalGraph}
          layoutMode={layoutMode}
          symbol={symbol}
        />
      </div>

      {/* ۴. کشوی جدول کاندیداهای هر مرحله (Expandable Stage Candidate Table) */}
      {activeStageDrawer && (
        <StrategyStageCandidateTable
          stageKey={activeStageDrawer}
          stageTitle={
            activeStageDrawer === 'tape'
              ? 'غربالگری اول: تابلوخوانی و جریان نقدینگی (S)'
              : activeStageDrawer === 'technical'
              ? 'غربالگری دوم: تحلیل تکنیکال دو زمانه (T)'
              : activeStageDrawer === 'fundamental'
              ? 'غربالگری سوم: ارزیابی بنیادی ۵ شاخصه کدال (F)'
              : 'تحویل نهایی FTS به معامله‌گر (Delivery)'
          }
          stagePage={
            activeStageDrawer === 'tape'
              ? 'چارت صفحه ۳'
              : activeStageDrawer === 'technical'
              ? 'چارت صفحه ۲'
              : activeStageDrawer === 'fundamental'
              ? 'چارت صفحه ۱'
              : 'چارت صفحه ۴'
          }
          stageDescription={
            activeStageDrawer === 'tape'
              ? 'نمادهایی که در این نشست فیلترهای سبک انتخابی (ساعت، حجم مشکوک یا کف‌روبی) را پاس کرده‌اند.'
              : activeStageDrawer === 'technical'
              ? 'فیلتر روند هفتگی صعودی و ستاپ‌های روزانه؛ وتوی هفتگی نماد را از چرخه خارج می‌کند.'
              : activeStageDrawer === 'fundamental'
              ? 'بررسی ۵ شاخص کدال شامل رشد فروش، EPS سه ساله، حاشیه سود، نسبت فروش به ارزش بازار و چشم‌انداز صنعت.'
              : 'نمادهای تاییدشده نهایی بدون وتوی مجمع عمومی؛ آماده بررسی معامله‌گر، مدیریت سرمایه و پله‌بندی.'
          }
          candidates={activeStageDrawer ? funnel.stages[activeStageDrawer]?.entries ?? [] : []}
          selectedSymbol={symbol}
          onSelectSymbol={(sym) => {
            setSymbol(sym);
            setActiveStageDrawer(null);
          }}
          isOpen={true}
          onClose={() => setActiveStageDrawer(null)}
        />
      )}
    </div>
  );
}
