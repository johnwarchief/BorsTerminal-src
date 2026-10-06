// features/master/components/StrategyGraphRenderer.tsx
// رندرر یکپارچه، پیشرفته و روان درخت استراتژی FTS
// پشتیبانی از هر دو چیدمان فلوچارت (Flow) و مداری (Orbit) با جابه‌جایی نرم، بزرگ‌نمایی، جابه‌جایی و پنل بازرسی
import React, { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useUiStore } from '@shared/stores/uiStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import type { CanonicalStrategyGraph, StrategyGraphNode } from '../lib/strategyGraphModel';
import { computeFlowLayout, computeOrbitLayout, type GraphLayoutResult } from '../lib/strategyGraphLayouts';

export type StrategyLayoutMode = 'flow' | 'orbit';

export interface StrategyGraphRendererProps {
  graph: CanonicalStrategyGraph;
  layoutMode: StrategyLayoutMode;
  symbol?: string;
  onNodeSelect?: (node: StrategyGraphNode) => void;
  selectedNodeId?: string | null;
}

const STAGE_THEME: Record<string, { border: string; bg: string; text: string; glow: string; icon: string }> = {
  selection: { border: 'border-accent-yellow', bg: 'bg-accent-yellow/10', text: 'text-accent-yellow', glow: 'rgba(234,179,8,0.25)', icon: '⏱️' },
  tape: { border: 'border-accent-yellow', bg: 'bg-accent-yellow/10', text: 'text-accent-yellow', glow: 'rgba(234,179,8,0.25)', icon: '⏱️' },
  technical: { border: 'border-accent-blue', bg: 'bg-accent-blue/10', text: 'text-accent-blue', glow: 'rgba(56,189,248,0.25)', icon: '📈' },
  fundamental: { border: 'border-accent-green', bg: 'bg-accent-green/10', text: 'text-accent-green', glow: 'rgba(34,197,94,0.25)', icon: '🏛️' },
  delivery: { border: 'border-emerald-500', bg: 'bg-emerald-500/10', text: 'text-emerald-400', glow: 'rgba(16,185,129,0.25)', icon: '📦' },
  capital: { border: 'border-accent-red', bg: 'bg-accent-red/10', text: 'text-accent-red', glow: 'rgba(239,68,68,0.25)', icon: '⚖️' },
  master: { border: 'border-neon-cyan', bg: 'bg-neon-cyan/10', text: 'text-neon-cyan', glow: 'rgba(6,182,212,0.25)', icon: '⚖️' },
};

export const StrategyGraphRenderer = memo(function StrategyGraphRenderer({
  graph,
  layoutMode,
  symbol,
  onNodeSelect,
  selectedNodeId: externalSelectedNodeId,
}: StrategyGraphRendererProps) {
  const theme = useUiStore((s) => s.theme);
  const isDark = theme !== 'light';
  const prefersReducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');

  const containerRef = useRef<HTMLDivElement>(null);
  const [internalSelectedId, setInternalSelectedId] = useState<string | null>('stage_selection');
  const activeSelectedId = externalSelectedNodeId !== undefined ? externalSelectedNodeId : internalSelectedId;

  // وضعیت‌های Zoom و Pan
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const dragStartRef = useRef({ x: 0, y: 0 });

  // محاسبه چیدمان فعال
  const layoutResult: GraphLayoutResult = useMemo(() => {
    if (layoutMode === 'orbit') {
      return computeOrbitLayout(graph);
    }
    return computeFlowLayout(graph);
  }, [graph, layoutMode]);

  // تنظیم دید اولیه متناسب با ابعاد کانتینر
  const fitView = useCallback(() => {
    if (!containerRef.current) return;
    const { clientWidth, clientHeight } = containerRef.current;
    const { width: bw, height: bh, minX, minY } = layoutResult.bounds;

    const scaleX = (clientWidth - 80) / bw;
    const scaleY = (clientHeight - 80) / bh;
    const fitScale = Math.min(Math.max(Math.min(scaleX, scaleY), 0.45), 1.2);

    const centerX = minX + bw / 2;
    const centerY = minY + bh / 2;

    const targetPanX = clientWidth / 2 - centerX * fitScale;
    const targetPanY = clientHeight / 2 - centerY * fitScale;

    setZoom(fitScale);
    setPan({ x: targetPanX, y: targetPanY });
  }, [layoutResult.bounds]);

  useEffect(() => {
    fitView();
  }, [layoutMode, fitView]);

  // تعاملات موس: Pan و Drag
  const handleMouseDown = (e: React.MouseEvent) => {
    // فقط کلیک چپ برای درگ
    if (e.button !== 0) return;
    isDraggingRef.current = true;
    dragStartRef.current = { x: e.clientX - pan.x, y: e.clientY - pan.y };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    setPan({
      x: e.clientX - dragStartRef.current.x,
      y: e.clientY - dragStartRef.current.y,
    });
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  // Zoom با چرخ موس
  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((prev) => Math.min(Math.max(prev * zoomFactor, 0.35), 2.5));
  };

  // ریست دید
  const resetView = () => {
    setZoom(1);
    fitView();
  };

  // انتخاب نود
  const handleNodeClick = (node: StrategyGraphNode, e: React.MouseEvent) => {
    e.stopPropagation();
    setInternalSelectedId(node.id);
    onNodeSelect?.(node);
  };

  // پارامترهای استراتژی و به‌روزرسانی
  const params = useStrategyParamsStore((s) => s.params);
  const updateParam = useStrategyParamsStore((s) => s.updateParam);
  const resetParam = useStrategyParamsStore((s) => s.resetParam);

  const selectedNode = activeSelectedId ? graph.nodeMap.get(activeSelectedId) : null;

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label="بوم گراف استراتژی FTS"
      data-testid="obsidian-strategy-canvas"
      className="relative w-full h-[640px] sm:h-[720px] rounded-2xl border border-border-c bg-bg-secondary/40 overflow-hidden select-none cursor-grab active:cursor-grabbing backdrop-blur-xs"
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onWheel={handleWheel}
    >
      {/* شبکه‌بندی پس‌زمینه (Blueprint Grid Pattern) */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-20" aria-hidden="true">
        <defs>
          <pattern id="strategy-grid" width="32" height="32" patternUnits="userSpaceOnUse">
            <path d="M 32 0 L 0 0 0 32" fill="none" stroke={isDark ? '#38bdf8' : '#0284c7'} strokeWidth="0.5" />
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#strategy-grid)" />
      </svg>

      {/* نوار کنترل شناور ناوبری (Zoom / Fit / Reset / Mode Indicator) */}
      <div className="absolute top-3 end-3 z-30 flex items-center gap-1.5 rounded-xl border border-border-c/80 bg-bg-card/90 p-1.5 shadow-md backdrop-blur">
        <button
          type="button"
          onClick={() => setZoom((z) => Math.min(z * 1.15, 2.5))}
          className="rounded-lg p-1.5 text-xs text-text-secondary hover:bg-bg-primary hover:text-accent-blue transition-colors"
          title="بزرگ‌نمایی (+)"
          aria-label="بزرگ‌نمایی"
        >
          🔍+
        </button>
        <button
          type="button"
          onClick={() => setZoom((z) => Math.max(z * 0.85, 0.35))}
          className="rounded-lg p-1.5 text-xs text-text-secondary hover:bg-bg-primary hover:text-accent-blue transition-colors"
          title="کوچک‌نمایی (-)"
          aria-label="کوچک‌نمایی"
        >
          🔍-
        </button>
        <button
          type="button"
          onClick={fitView}
          className="rounded-lg px-2 py-1 text-2xs font-bold text-text-secondary hover:bg-bg-primary hover:text-accent-blue transition-colors"
          title="تنظیم خودکار کادر (Fit)"
          aria-label="تنظیم خودکار کادر"
        >
          گستره ⛶
        </button>
        <button
          type="button"
          onClick={resetView}
          className="rounded-lg px-2 py-1 text-2xs font-bold text-text-secondary hover:bg-bg-primary hover:text-accent-blue transition-colors"
          title="بازنشانی بزرگ‌نمایی"
          aria-label="بازنشانی بزرگ‌نمایی"
        >
          {toFaDigits(Math.round(zoom * 100))}٪
        </button>
      </div>

      {/* برچسب نمای جاری در گوشه پایین */}
      <div className="absolute bottom-3 start-3 z-30 flex items-center gap-2 rounded-xl border border-border-c/80 bg-bg-card/85 px-3 py-1.5 text-2xs font-bold text-text-secondary shadow-sm backdrop-blur">
        <span className="h-2 w-2 rounded-full bg-accent-blue animate-pulse" />
        <span>حالت چیدمان: {layoutMode === 'flow' ? 'فلوچارت گام‌به‌گام FTS' : 'مدار منظومه‌ای هم‌مرکز'}</span>
        {symbol ? (
          <span className="ms-2 border-s border-border-c ps-2 text-accent-blue font-black">
            ردیابی مسیر نماد {symbol}
          </span>
        ) : null}
      </div>

      {/* بوم گراف اصلی با پشتیبانی از ترنزیشن نرم مختصات */}
      <div
        className="absolute inset-0 origin-top-left transition-transform duration-75 ease-out"
        style={{
          transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        }}
      >
        <svg
          data-testid="strategy-edges-svg"
          className="overflow-visible"
          width={layoutResult.bounds.width}
          height={layoutResult.bounds.height}
          style={{ position: 'absolute', top: 0, left: 0 }}
        >
          <defs>
            <marker id="arrowhead-active" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
              <polygon points="0 0, 7 3.5, 0 7" fill="#38bdf8" />
            </marker>
            <marker id="arrowhead-idle" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
              <polygon points="0 0, 6 3, 0 6" fill={isDark ? '#334155' : '#cbd5e1'} />
            </marker>
          </defs>

          {/* حلقه‌های مدار در حالت Orbit */}
          {layoutMode === 'orbit' && (
            <g className="orbit-rings opacity-30" aria-hidden="true">
              <circle cx="650" cy="550" r="185" fill="none" stroke="#38bdf8" strokeWidth="1" strokeDasharray="4 4" />
              <circle cx="650" cy="550" r="360" fill="none" stroke="#22c55e" strokeWidth="1" strokeDasharray="6 6" />
              <circle cx="650" cy="550" r="515" fill="none" stroke="#eab308" strokeWidth="1" strokeDasharray="6 6" />
            </g>
          )}

          {/* ۱. رسم تمام یال‌ها (Edges) */}
          <g className="edges-layer">
            {layoutResult.edges.map((edge) => {
              const isFlowing = edge.isActive;
              return (
                <g key={edge.id}>
                  {/* خط پایه یال */}
                  <path
                    d={edge.d}
                    fill="none"
                    stroke={isFlowing ? '#38bdf8' : isDark ? '#1e293b' : '#cbd5e1'}
                    strokeWidth={isFlowing ? 2.5 : 1.5}
                    strokeLinecap="round"
                    markerEnd={isFlowing ? 'url(#arrowhead-active)' : 'url(#arrowhead-idle)'}
                    className="transition-colors duration-200"
                  />
                  {/* خط متحرک در صورت فعال بودن مسیر جریان */}
                  {isFlowing && !prefersReducedMotion && (
                    <path
                      d={edge.d}
                      fill="none"
                      stroke="#22c55e"
                      strokeWidth="2.5"
                      strokeDasharray="8 12"
                      className="animate-dash"
                      opacity="0.85"
                    />
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        {/* ۲. رسم نودها به صورت المان‌های تعاملی با انیمیشن ترنزیشن */}
        <div className="nodes-layer relative" style={{ width: layoutResult.bounds.width, height: layoutResult.bounds.height }}>
          {layoutResult.nodes.map((ln) => {
            const node = ln.data;
            const isSelected = activeSelectedId === node.id;
            const isActive = graph.activePathNodeIds.has(node.id);
            const stageStyle = STAGE_THEME[node.stage] || STAGE_THEME.master;

            const isPassed = node.status === 'pass';
            const isFailed = node.status === 'fail';
            const isWait = node.status === 'wait';

            return (
              <div
                key={ln.id}
                role="button"
                tabIndex={0}
                onClick={(e) => handleNodeClick(node, e)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setInternalSelectedId(node.id);
                    onNodeSelect?.(node);
                  }
                }}
                className={`absolute cursor-pointer rounded-xl border p-2.5 transition-all select-none shadow-xs backdrop-blur ${
                  prefersReducedMotion ? '' : 'duration-300'
                } ${
                  isSelected
                    ? 'ring-2 ring-accent-blue border-accent-blue bg-bg-card/95 shadow-lg scale-102 z-20'
                    : isActive
                      ? 'border-border-accent bg-bg-card/85 hover:border-accent-blue'
                      : 'border-border-c/70 bg-bg-primary/80 opacity-80 hover:opacity-100 hover:border-border-accent'
                } ${
                  isPassed
                    ? 'border-accent-green/80 bg-accent-green/10'
                    : isFailed
                      ? 'border-accent-red/80 bg-accent-red/10'
                      : isWait
                        ? 'border-accent-yellow/80 bg-accent-yellow/10'
                        : ''
                }`}
                style={{
                  left: ln.x,
                  top: ln.y,
                  width: ln.width,
                  height: ln.height,
                }}
              >
                <div className="flex h-full flex-col justify-between">
                  {/* سربرگ نود: آیکون، عنوان و بج */}
                  <div className="flex items-center justify-between gap-1.5">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <span className="text-xs shrink-0">{stageStyle.icon}</span>
                      <span className="text-xs font-black text-text-primary truncate" title={node.label}>
                        {node.label}
                      </span>
                    </div>
                    {node.badge && (
                      <span className="rounded bg-bg-secondary px-1.5 py-0.2 text-3xs font-bold text-text-muted shrink-0">
                        {node.badge}
                      </span>
                    )}
                  </div>

                  {/* زیرعنوان و وضعیت لحظه‌ای */}
                  <div className="flex items-center justify-between gap-1 text-2xs">
                    <span className="text-text-muted truncate max-w-[80%]" title={node.subLabel}>
                      {node.subLabel || node.formula}
                    </span>
                    {node.status && node.status !== 'inactive' && (
                      <span
                        className={`h-2 w-2 rounded-full shrink-0 ${
                          isPassed
                            ? 'bg-accent-green shadow-[0_0_6px_#22c55e]'
                            : isFailed
                              ? 'bg-accent-red shadow-[0_0_6px_#ef4444]'
                              : isWait
                                ? 'bg-accent-yellow shadow-[0_0_6px_#eab308]'
                                : 'bg-accent-blue'
                        }`}
                      />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ۳. پنل بازرسی نود انتخاب‌شده (Inspection Drawer / Panel) */}
      {selectedNode && (
        <div
          data-testid="strategy-node-inspector"
          className="absolute bottom-3 end-3 z-40 max-w-[360px] w-full rounded-2xl border border-border-accent bg-bg-card/95 p-4 shadow-2xl backdrop-blur flex flex-col gap-3 animate-in fade-in slide-in-from-bottom-2 duration-150"
        >
          <div className="flex items-start justify-between gap-2 border-b border-border-c/60 pb-2">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="rounded-lg bg-accent-blue/15 px-2 py-0.5 text-2xs font-black text-accent-blue">
                  {STAGE_THEME[selectedNode.stage]?.icon} {selectedNode.badge || 'FTS'}
                </span>
                {selectedNode.page && (
                  <span className="rounded-lg bg-bg-primary px-1.5 py-0.5 text-3xs font-bold text-text-muted border border-border-c">
                    {selectedNode.page}
                  </span>
                )}
                <h3 className="text-sm font-black text-text-primary truncate">{selectedNode.label}</h3>
              </div>
              <p className="text-2xs text-text-muted mt-0.5">{selectedNode.subLabel}</p>
            </div>
            <button
              type="button"
              onClick={() => setInternalSelectedId(null)}
              className="text-text-muted hover:text-text-primary text-xs font-bold rounded-lg p-1"
              title="بستن پنل جزئیات"
              aria-label="بستن"
            >
              ✕
            </button>
          </div>

          {/* شرح کارکرد و منطق */}
          <div className="text-xs text-text-secondary leading-relaxed">
            <p>{selectedNode.description}</p>
          </div>

          {/* فرمول یا شرط کمی */}
          {selectedNode.formula && (
            <div className="rounded-xl border border-border-c bg-bg-primary/80 p-2.5 font-mono text-2xs text-accent-cyan">
              <div className="text-3xs uppercase tracking-wider text-text-muted mb-1 font-sans">شرط محاسباتی:</div>
              <div>{selectedNode.formula}</div>
            </div>
          )}

          {/* شواهد زنده در صورت وجود نماد */}
          {symbol && selectedNode.evidence && selectedNode.evidence.length > 0 && (
            <div className="rounded-xl border border-accent-blue/30 bg-accent-blue/5 p-2.5 text-2xs">
              <div className="font-bold text-accent-blue mb-1">شواهد زنده برای {symbol}:</div>
              <ul className="list-disc list-inside space-y-0.5 text-text-secondary font-medium">
                {selectedNode.evidence.map((ev, i) => (
                  <li key={i}>{ev}</li>
                ))}
              </ul>
            </div>
          )}

          {/* ویرایش زنده پارامترهای مرتبط با نود */}
          {selectedNode.editableParamKeys && selectedNode.editableParamKeys.length > 0 && (
            <div className="pt-2 border-t border-border-c/60 space-y-2">
              <div className="text-3xs font-bold uppercase tracking-wider text-text-muted">تنظیم پارامتر زنده:</div>
              {selectedNode.editableParamKeys.map((pKey) => {
                if (pKey === 'minVolumeRatio') {
                  return (
                    <div key={pKey} className="space-y-1">
                      <div className="flex justify-between text-2xs font-bold">
                        <span>ضریب حجم مشکوک:</span>
                        <div className="flex items-center gap-1.5">
                          <span className="text-amber-600 dark:text-accent-yellow font-bold text-3xs">جزوه: ۳.۰×</span>
                          <span className="font-mono text-accent-blue">{toFaDigits(params.minVolumeRatio)}×</span>
                        </div>
                      </div>
                      <input
                        type="range"
                        min="1.0"
                        max="5.0"
                        step="0.1"
                        value={params.minVolumeRatio}
                        onChange={(e) => updateParam('minVolumeRatio', parseFloat(e.target.value))}
                        className="w-full accent-accent-blue cursor-pointer h-1.5 rounded-lg bg-bg-secondary"
                      />
                    </div>
                  );
                }
                if (pKey === 'minBuyerPower') {
                  return (
                    <div key={pKey} className="space-y-1">
                      <div className="flex justify-between text-2xs font-bold">
                        <span>حداقل قدرت خریدار:</span>
                        <span className="font-mono text-accent-blue">{toFaDigits(params.minBuyerPower)}</span>
                      </div>
                      <input
                        type="range"
                        min="0.8"
                        max="3.0"
                        step="0.1"
                        value={params.minBuyerPower}
                        onChange={(e) => updateParam('minBuyerPower', parseFloat(e.target.value))}
                        className="w-full accent-accent-blue cursor-pointer h-1.5 rounded-lg bg-bg-secondary"
                      />
                    </div>
                  );
                }
                if (pKey === 'minFundScore') {
                  return (
                    <div key={pKey} className="space-y-1">
                      <div className="flex justify-between text-2xs font-bold">
                        <span>کف امتیاز بنیادی کدال:</span>
                        <span className="font-mono text-accent-green">{toFaDigits(params.minFundScore)} از ۵</span>
                      </div>
                      <input
                        type="range"
                        min="1"
                        max="5"
                        step="1"
                        value={params.minFundScore}
                        onChange={(e) => updateParam('minFundScore', parseInt(e.target.value, 10))}
                        className="w-full accent-accent-green cursor-pointer h-1.5 rounded-lg bg-bg-secondary"
                      />
                    </div>
                  );
                }
                if (pKey === 'singleStockMaxWeightPct') {
                  return (
                    <div key={pKey} className="space-y-1">
                      <div className="flex justify-between text-2xs font-bold">
                        <span>سقف مجاز تک‌سهم نوسانی:</span>
                        <span className="font-mono text-neon-cyan">{toFaDigits(params.singleStockMaxWeightPct)}٪</span>
                      </div>
                      <input
                        type="range"
                        min="1.0"
                        max="10.0"
                        step="0.5"
                        value={params.singleStockMaxWeightPct}
                        onChange={(e) => updateParam('singleStockMaxWeightPct', parseFloat(e.target.value))}
                        className="w-full accent-neon-cyan cursor-pointer h-1.5 rounded-lg bg-bg-secondary"
                      />
                    </div>
                  );
                }
                return null;
              })}

              <div className="flex justify-end pt-1">
                <button
                  type="button"
                  onClick={() => {
                    for (const pk of selectedNode.editableParamKeys || []) {
                      resetParam(pk);
                    }
                  }}
                  className="rounded-lg border border-border-c bg-bg-secondary px-2.5 py-1 text-3xs font-bold text-text-muted hover:text-text-primary hover:border-border-accent transition-colors"
                >
                  بازنشانی به جزوه
                </button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
