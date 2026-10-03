# -*- coding: utf-8 -*-
"""_audit/build_strategy_map.py -- بازسازیِ `ObsidianStrategyGraph.tsx` رویِ مدلِ تازه

بافتِ این بازنویسیِ کور نیست: سه بخشِ متنیِ بزرگ (نوارِ ابزار، پلاکِ نماد، پنلِ
بازرسی + ویرایشگرِ زندهٔ ۱۵ پارامتر) **عیناً** از فایلِ پیشین برمی‌دارند چون
متن/آستانه‌هایشان رأیِ جزوه است (قیدِ مالک: بدونِ دلیل عوض نشود). آنچه عوض می‌شود
فقط تولیدِ گره‌ها و چیدمانِ بوم است: مختصاتِ دستیِ ۴۶ گره و ۶۲/۵۸ یالِ بستۀ
جریان‌محور جایشان را به درختِ محاسبه‌شدهٔ «چهار صفحۀ چاپی» می‌دهند.

`docs/CHART-FOUR-PAGES-PARITY.md` و `docs/fts-notes/FTS_CHART3_extracted_text.txt`
منبعِ سطربه‌سطرِ هر Zone‌اند؛ هیچ رابطۀ تازه‌ای درِ این فایل ساخته نمی‌شود.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMP = os.path.join(ROOT, "frontend", "src", "features", "master", "components", "ObsidianStrategyGraph.tsx")

HEAD = """// features/master/components/ObsidianStrategyGraph.tsx -- نقشۀ استراتژی FTS: چهار صفحۀ چاپی در یک بوم
// این کامپوننت فقط **رندر** است. داده از `lib/ftsChartModel` (درختِ سطرهایِ خودِ
// چهار صفحۀ جزوه) و چیدمان از `lib/ftsChartLayout` (محاسبه‌شده، بی‌مختصِ دستی)
// می‌آید. پرست (swing/trend/hourglass/custom) و جهتِ جریان هیچ‌کدام توپولوژی را
// نمی‌سازند: فقط ریلِ روشن را رویِ همین نقشۀ ثابت جابه‌جا می‌کنند.
//
// چهار Zone با جایگاهِ ثابت، راست‌به‌چپ و به ترتیبِ صفحۀ چاپی:
//   F (صفحۀ ۱، راست‌ترین) ➔ T (۲) ➔ S (۳) ➔ M (۴، چپ‌ترین)
// و رابطۀ بینِ صفحه‌ها تنها همان سه وابستگی است که خودِ صفحۀ ۴ اعلام می‌کند
// (مهندسی معکوس: ۱ تابلو ۲ تکنیکال ۳ بنیادی) — بدونِ هستۀ پرکُنکشن.
//
// متن/آستانه/قاعدهٔ گره‌ها، پنلِ بازرسی و ویرایشگرِ زندهٔ پارامترها از نسخۀ
// پیشین عیناً منتقل شده‌اند (بازسازیِ بصری، نه بازنویسیِ منطق). Source of Truth
// داوری همچنان بک‌اند/پایتون است.
import React, { useMemo, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import { useUiStore } from '@shared/stores/uiStore';
import { useStrategyParamsStore } from '../stores/strategyParamsStore';
import { useMediaQuery } from '@shared/lib/useMediaQuery';
import { useTreeFlowStore, isFlowRunning } from '../stores/treeFlowStore';
import {
  ZONE_BY_KEY,
  activeIdsForPreset,
  ancestorsOf,
  buildFtsChartModel,
  railOrder,
  refEdges,
  type FtsPreset,
  type FlowDirection,
} from '../lib/ftsChartModel';
import { HEADER_H, layoutMap, refPath } from '../lib/ftsChartLayout';

export type { FlowDirection, FtsChartNode } from '../lib/ftsChartModel';
/** سازۀ پیشینِ یال‌ها (`getGraphLinks`) به مدلِ داده منتقل شد؛ از همین‌جا هم
 *  درِ دسترس است تا مصرف‌کننده‌هایِ موجود نشکنند. */
export { getModelLinks as getGraphLinks } from '../lib/ftsChartModel';

"""

TAIL_HEAD = """
const NORMAL_OPACITY = 1;

export function ObsidianStrategyGraph({
  selectedPreset,
  symbol,
  activeCustomNodes = [],
  onToggleCustomNode,
  symbolPhaseStatus,
  symbolLevels,
}: ObsidianStrategyGraphProps) {
  // ۱. پشتیبانی کامل از تم روشن / تاریک
  const theme = useUiStore((s) => s.theme);
  const isLight = theme === 'light';

  // ۲. استور پارامترهای شخصی‌سازی استراتژی
  const { params, updateParam, resetParam, resetAll } = useStrategyParamsStore();

  // ۳. حالت جهت جریان (پیش‌فرض: مهندسی معکوس FTS) — فقط ریل، نه توپولوژی
  const [flowDirection, setFlowDirection] = useState<FlowDirection>('reverse');

  // ۴. مدلِ چهار صفحۀ چاپی + چیدمانِ محاسبه‌شده
  const model = useMemo(() => buildFtsChartModel(params), [params]);
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());
  const layout = useMemo(() => layoutMap(model, collapsed), [model, collapsed]);
  const refs = useMemo(() => refEdges(model), [model]);

  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [selectedNodeId, setSelectedNodeId] = useState<string>('tape_volume');
  const [searchQuery, setSearchQuery] = useState('');
  const [zoom, setZoom] = useState(1);
  // حرکتِ رویِ مسیر با CSS انجام می‌شود. اینکه بدود یا نه را تنظیمِ
  // درون‌برنامه تعیین می‌کند (fts.tree.flow.v1، پیش‌فرض «همیشه»)، نه
  // ترجیعِ سیستم: پنجرۀ بومیِ برنامه آن ترجیع را از ویندوز می‌گیرد و
  // درخت را بی‌حرکت می‌کرد.
  const treeFlowMode = useTreeFlowStore((s) => s.mode);
  const systemReduce = useMediaQuery('(prefers-reduced-motion: reduce)');
  const flowOn = isFlowRunning(treeFlowMode, systemReduce);
  const [pan, setPan] = useState({ x: 0, y: 0 });

  const isDraggingRef = useRef(false);
  const lastMousePos = useRef({ x: 0, y: 0 });
  const svgContainerRef = useRef<HTMLDivElement>(null);

  // ریلِ پرست جاری: گره‌هایِ روشن + جدّهایشان تا ریشۀ همان Zone
  const railSet = useMemo(
    () => activeIdsForPreset(selectedPreset, model, activeCustomNodes),
    [selectedPreset, model, activeCustomNodes],
  );

  // جست‌وجو کلِ مسیر را روشن می‌کند: هر گرهٔ خورده + همهٔ جدّهایش
  const searchSet = useMemo(() => {
    const q = searchQuery.trim();
    if (!q) return null;
    const set = new Set<string>();
    for (const n of model.nodes) {
      const hay = n.label + ' ' + n.fullTitle + ' ' + n.description + ' ' + n.ruleFormula + ' ' + n.badge;
      if (hay.includes(q)) for (const a of ancestorsOf(model, n.id)) set.add(a);
    }
    return set;
  }, [searchQuery, model]);

  // هاور: فقط همسایه (والد + فرزندان + هم‌نام‌ها) و مسیرِ بالایی روشن می‌ماند
  const focusSet = useMemo(() => {
    if (!hoveredNodeId) return null;
    const set = new Set<string>(ancestorsOf(model, hoveredNodeId));
    set.add(hoveredNodeId);
    for (const c of model.childrenOf.get(hoveredNodeId) ?? []) set.add(c);
    const node = model.byId.get(hoveredNodeId);
    for (const r of node?.refs ?? []) set.add(r);
    return set;
  }, [hoveredNodeId, model]);

  const emphasis = focusSet ?? searchSet;

  const isLit = (id: string) => {
    if (emphasis) return emphasis.has(id);
    return railSet.size === 0 || railSet.has(id);
  };

  // گره‌هایِ هرجای نقشه که با پرستِ فعلی یا جست‌وجو روشن‌اند — سرِ Zone هم از همین
  // شمار می‌کند تا «کجا از این صفحه درِ مسیرِ من است» یک‌نگاه دیده شود.
  const litCountByZone = useMemo(() => {
    const acc: Record<string, number> = { F: 0, T: 0, S: 0, M: 0 };
    for (const n of model.nodes) {
      if (n.kind === 'leaf' && railSet.has(n.id)) acc[n.zone] += 1;
    }
    return acc;
  }, [model, railSet]);

  const inspectedNode = model.byId.get(selectedNodeId) ?? model.byId.get('tape_volume') ?? model.nodes[0];
  const inspectedAccent = inspectedNode.color || ZONE_BY_KEY[inspectedNode.zone].accentDark;

  // وابستگی‌هایِ بین‌صفحه‌ای به ترتیبِ ریل؛ هر گام یا همسایه است (فلشِ کوتاهِ
  // میانِ دو سربرگ) یا از سرِ نقشه برمی‌گردد (کمانِ زیرِ بوم) — نه خطِ کجِ عبوری.
  const railSteps = useMemo(() => {
    const order = railOrder(flowDirection);
    const slotOf = new Map(layout.zones.map((z) => [z.key, z.slot]));
    const out: { id: string; from: string; to: string; arc: boolean; lit: boolean }[] = [];
    for (let i = 0; i + 1 < order.length; i += 1) {
      const a = order[i];
      const b = order[i + 1];
      out.push({
        id: 'rail_' + a + '_' + b,
        from: a,
        to: b,
        arc: Math.abs((slotOf.get(a) ?? 0) - (slotOf.get(b) ?? 0)) > 1,
        lit: litCountByZone[a] > 0 && litCountByZone[b] > 0,
      });
    }
    return out;
  }, [flowDirection, layout, litCountByZone]);

  // کنترل حرکت بوم با ماوس (Pan) بدون لرزش
  const handleMouseDown = (e: React.MouseEvent) => {
    if (
      (e.target as HTMLElement).tagName.toLowerCase() === 'input' ||
      (e.target as HTMLElement).tagName.toLowerCase() === 'button'
    ) {
      return;
    }
    isDraggingRef.current = true;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!isDraggingRef.current) return;
    const dx = e.clientX - lastMousePos.current.x;
    const dy = e.clientY - lastMousePos.current.y;
    lastMousePos.current = { x: e.clientX, y: e.clientY };
    setPan((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  };

  const handleMouseUp = () => {
    isDraggingRef.current = false;
  };

  const handleWheel = (e: React.WheelEvent) => {
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.08 : 0.92;
    setZoom((z) => Math.min(Math.max(z * factor, 0.55), 1.9));
  };

  const handleResetView = () => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const toggleCollapse = (id: string) => {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const phaseOfZone = (k: string) => symbolPhaseStatus?.find((p) => p.k === k);

  return (
    <div
      className={`flex flex-col w-full rounded-2xl border transition-colors duration-200 overflow-hidden shadow-2xl ${
        isLight
          ? 'bg-slate-50 border-slate-300 text-slate-900 shadow-slate-200/80'
          : 'bg-[#070b16] border-border-c/80 text-text-primary shadow-black/60'
      }`}
    >
"""

CANVAS = """
      {/* ۲. بومِ نقشه: چهار Zone با جایگاهِ ثابت، هر یک درختِ سطرهایِ خودِ چارت */}
      {/* بوم هیچ‌وقت کوچک‌تر از یک‌به‌یک نمی‌شود؛ تنگ‌جا اسکرول افقی می‌خورد،
          نه اینکه نوشته‌ها ریز شوند (بازخورد مالک: «تا نیاز به زوم نباشد»). */}
      <div className="w-full overflow-x-auto overflow-y-hidden">
      <div
        ref={svgContainerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        onWheel={handleWheel}
        className="relative mx-auto w-full select-none cursor-grab active:cursor-grabbing"
        style={{
          minWidth: layout.width,
          aspectRatio: `${layout.width} / ${layout.height}`,
          maxWidth: Math.round(layout.width * 1.32),
        }}
      >
        <svg
          viewBox={`0 0 ${layout.width} ${layout.height}`}
          className="w-full h-full"
          preserveAspectRatio="xMidYMid meet"
          data-testid="obsidian-strategy-canvas"
          data-tree-flow-running={flowOn ? '1' : '0'}
        >
          <defs>
            {/* الگوی بهینه‌شدهٔ بوم جهت کارایی روان و مصرف کم در سیستم‌های معمولی */}
            <pattern id="gridPatternFts" width="60" height="60" patternUnits="userSpaceOnUse">
              <rect width="60" height="60" fill="none" stroke={isLight ? 'rgba(148, 163, 184, 0.18)' : 'rgba(51, 65, 85, 0.25)'} strokeWidth="0.5" />
            </pattern>
            <marker id="railHeadRev" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={isLight ? '#0284c7' : '#38bdf8'} />
            </marker>
            <marker id="railHeadDim" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={isLight ? '#94a3b8' : '#475569'} />
            </marker>
          </defs>

          <rect x="0" y="0" width={layout.width} height={layout.height} fill={isLight ? '#f8fafc' : '#070b16'} />
          <rect x="0" y="0" width={layout.width} height={layout.height} fill="url(#gridPatternFts)" opacity={isLight ? 0.5 : 0.7} />

          {/* لایه متحرک و زوم‌پذیر */}
          <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`} transform-origin={`${Math.round(layout.width / 2)} ${Math.round(layout.height / 2)}`}>
            {/* فلش راهنما در بالای بوم جهت نشان دادن جریان راست به چپ (RTL) */}
            <g className="rtl-direction-banner pointer-events-none opacity-85">
              <rect
                x={Math.round(layout.width / 2 - 190)}
                y="6"
                width="380"
                height="24"
                rx="6"
                fill={isLight ? '#e2e8f0' : '#1e293b'}
                stroke={isLight ? '#cbd5e1' : '#334155'}
                strokeWidth="0.8"
              />
              <text
                x={Math.round(layout.width / 2)}
                y="22"
                textAnchor="middle"
                className={`text-[10px] font-black ${isLight ? 'fill-slate-700' : 'fill-slate-300'}`}
              >
                {flowDirection === 'reverse'
                  ? '⬅️ جریان مهندسی معکوس (RTL): شروع از تابلوخوانی ➔ خروج در چپ'
                  : '⬅️ جریان مستقیم تحلیلی (RTL): شروع از بنیادی ➔ خروج در چپ'}
              </text>
            </g>

            {/* چهار Zone: سربرگِ ثابت + بدنهٔ رنگیِ همان صفحۀ چاپی */}
            <g className="zone-frames">
              {layout.zones.map((zone) => {
                const meta = ZONE_BY_KEY[zone.key];
                const accent = isLight ? meta.accentLight : meta.accentDark;
                const phase = phaseOfZone(zone.key);
                const phaseColor = !phase
                  ? null
                  : phase.status === 'pass'
                    ? isLight ? '#059669' : '#10b981'
                    : phase.status === 'wait'
                      ? isLight ? '#d97706' : '#f59e0b'
                      : isLight ? '#dc2626' : '#ef4444';
                const zoneLit = litCountByZone[zone.key] > 0;
                const yHead = HEADER_H - 16;
                return (
                  <g key={zone.key}>
                    <rect
                      x={zone.x}
                      y={yHead}
                      width={zone.w}
                      height={zone.y + zone.h - yHead + 8}
                      rx="14"
                      fill={accent}
                      fillOpacity={isLight ? (zoneLit ? 0.08 : 0.04) : (zoneLit ? 0.06 : 0.03)}
                      stroke={accent}
                      strokeOpacity={zoneLit ? 0.55 : 0.28}
                      strokeWidth={zoneLit ? 1.6 : 1.1}
                    />
                    <rect
                      x={zone.x}
                      y={yHead}
                      width={zone.w}
                      height="30"
                      rx="8"
                      fill={isLight ? '#ffffff' : '#0b1329'}
                      fillOpacity={isLight ? 0.96 : 0.85}
                      stroke={accent}
                      strokeOpacity="0.5"
                      strokeWidth="1.1"
                    />
                    <text
                      x={zone.x + zone.w - 10}
                      y={yHead + 19}
                      textAnchor="end"
                      fill={accent}
                      className="text-[13px] font-black"
                    >
                      {meta.title}
                    </text>
                    <text
                      x={zone.x + 10}
                      y={yHead + 19}
                      textAnchor="start"
                      fill={isLight ? '#64748b' : '#94a3b8'}
                      className="text-[9px] font-bold"
                    >
                      {meta.sub}
                    </text>
                    {phase && (
                      <g>
                        <title>{`${zone.key}: ${phase.label}`}</title>
                        <circle cx={zone.x + zone.w - 2} cy={yHead + 8} r="4" fill={phaseColor ?? '#64748b'} />
                      </g>
                    )}
                  </g>
                );
              })}
            </g>

            {/* سه وابستگیِ بین‌صفحه‌ای که خودِ چارت اعلام می‌کند — نه بیشتر.
                گام‌هایِ همسایه فلشِ کوتاهِ میانِ سربرگ‌ها، و گامی که از سرِ
                نقشه برمی‌گردد کمانِ زیرِ بوم است (هیچ خطِ کجِ عبوری). */}
            <g className="zone-rail">
              {railSteps.map((step) => {
                const a = layout.zones.find((z) => z.key === step.from);
                const b = layout.zones.find((z) => z.key === step.to);
                if (!a || !b) return null;
                const y = HEADER_H - 1;
                let d: string;
                if (step.arc) {
                  const yy = layout.height - 10;
                  d = `M ${a.x + a.w / 2} ${y + 26} L ${a.x + a.w / 2} ${yy} L ${b.x + b.w / 2} ${yy} L ${b.x + b.w / 2} ${y + 26}`;
                } else {
                  const fromRight = a.slot < b.slot;
                  const sx = fromRight ? a.x - 2 : a.x + a.w + 2;
                  const ex = fromRight ? b.x + b.w + 6 : b.x - 6;
                  d = `M ${sx} ${y + 15} L ${ex} ${y + 15}`;
                }
                const strokeColor = step.lit
                  ? (isLight ? '#0284c7' : '#38bdf8')
                  : (isLight ? '#94a3b8' : '#475569');
                const strokeWidth = step.lit ? 2.4 : 1.2;
                const pathData = d;
                return (
                  <g key={step.id}>
                    {step.lit && (
                      <path
                        d={pathData}
                        fill="none"
                        stroke={strokeColor}
                        strokeWidth={strokeWidth + 2.6}
                        strokeOpacity={0.16}
                        className="fts-path-flow"
                      />
                    )}
                    <path
                      d={pathData}
                      fill="none"
                      stroke={strokeColor}
                      strokeWidth={strokeWidth}
                      strokeOpacity={step.lit ? 0.95 : 0.45}
                      markerEnd={step.lit ? 'url(#railHeadRev)' : 'url(#railHeadDim)'}
                    />
                        {/* سه دانه که رویِ همان منحنی **جابه‌جا** می‌شوند (رأیِ pilot #60:
                            گزینهٔ c). حرکت با `animateMotion` است چون «تبدیل» است نه لی‌اوت:
                            سنجشِ ۱۴۰۵-۰۷-۰۹ خط‌چینِ متحرکِ CSS را ۱۰۱۴ لی‌اوت در ۱۲ ثانیه
                            نشان داد. فقط رویِ گام‌هایِ روشنِ ریل می‌دوند (حداکثر سه مسیر)
                            و نفسِ حرکت بلند است ({COMET_DUR_S} ثانیه). خاموش‌کردنش دو کلید
                            دارد: تنظیمِ «جریانِ مسیر» (flowOn — دانه‌ها اصلاً ساخته
                            نمی‌شوند) و پنجرهٔ پنه؛ بی‌حرکتیِ موس نه. */}
                        {step.lit && flowOn &&
                          Array.from({ length: COMET_N }).map((_, i) => (
                            <circle
                              key={i}
                              data-testid="tree-flow-comet"
                              r="3.6"
                              fill={strokeColor}
                              className="fts-comet"
                            >
                              <animateMotion
                                dur={`${COMET_DUR_S}s`}
                                repeatCount="indefinite"
                                begin={`${(-((COMET_DUR_S / COMET_N) * i)).toFixed(2)}s`}
                                path={pathData}
                                rotate="0"
                              />
                            </circle>
                          ))}
                  </g>
                );
              })}
            </g>

            {/* آرنجِ رابطۀ درختی: فقط والد ➔ فرزندِ همان صفحۀ چاپی */}
            <g className="tree-links">
              {layout.links.map((l) => {
                const lit = isLit(l.source) && isLit(l.target);
                return (
                  <path
                    key={l.id}
                    d={l.d}
                    fill="none"
                    stroke={isLight ? '#64748b' : '#475569'}
                    strokeOpacity={lit ? 0.95 : emphasis || railSet.size ? 0.22 : 0.5}
                    strokeWidth={lit ? 1.9 : 1.1}
                  />
                );
              })}
            </g>

            {/* خط‌چینِ «هم‌نام»: گونۀ یک مفهوم درِ صفحۀ دیگر. پیش‌فرض پنه است تا
                بوم شلوغ نشود؛ فقط با انتخاب یا هاورِ آن گره دیده می‌شود. */}
            <g className="ref-links" pointerEvents="none">
              {(() => {
                const anchor = hoveredNodeId ?? selectedNodeId;
                return refs.filter((r) => r.source === anchor || r.target === anchor);
              })().map((r) => {
                const a = layout.rowById.get(r.source);
                const b = layout.rowById.get(r.target);
                if (!a || !b) return null;
                return (
                  <path
                    key={r.id}
                    d={refPath(a, b)}
                    fill="none"
                    stroke={isLight ? '#a855f7' : '#c084fc'}
                    strokeOpacity="0.75"
                    strokeWidth="1.3"
                    strokeDasharray="4 4"
                  />
                );
              })}
            </g>

            {/* سطرهایِ گره: سرِ شاخه = برچسبِ باریکِ تورفتۀ چارت، برگ = کارت */}
            <g className="nodes-layer">
              {layout.rows.map((row) => {
                const node = model.byId.get(row.id);
                if (!node) return null;
                const meta = ZONE_BY_KEY[node.zone];
                const accent = node.color || (isLight ? meta.accentLight : meta.accentDark);
                const lit = isLit(row.id);
                const isSelected = row.id === selectedNodeId;
                const onRail = railSet.has(row.id);
                const kids = (model.childrenOf.get(row.id) ?? []).length;
                const dim = lit ? NORMAL_OPACITY : emphasis || railSet.size ? 0.3 : 0.86;
                const toggleCustom = () => {
                  if (selectedPreset === 'custom' && onToggleCustomNode && node.kind === 'leaf') {
                    onToggleCustomNode(row.id);
                  }
                };
                return (
                  <g
                    key={row.id}
                    opacity={dim}
                    onPointerEnter={() => setHoveredNodeId(row.id)}
                    onPointerLeave={() => setHoveredNodeId((cur) => (cur === row.id ? null : cur))}
                    onClick={() => {
                      setSelectedNodeId(row.id);
                      toggleCustom();
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    <title>{node.fullTitle}</title>
                    {row.kind === 'head' ? (
                      <>
                        <text
                          x={row.right - 2}
                          y={row.midY + 4}
                          textAnchor="end"
                          fill={accent}
                          className="text-[11px] font-black"
                        >
                          {node.label}
                        </text>
                        {kids > 0 && (
                          <g
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleCollapse(row.id);
                            }}
                          >
                            <rect
                              x={row.right + 2}
                              y={row.y + 1}
                              width="16"
                              height="16"
                              rx="4"
                              fill={isLight ? '#e2e8f0' : '#111a2e'}
                              stroke={isLight ? '#cbd5e1' : '#334155'}
                              strokeWidth="0.8"
                            />
                            <text
                              x={row.right + 10}
                              y={row.y + 13}
                              textAnchor="middle"
                              fill={isLight ? '#475569' : '#94a3b8'}
                              className="text-[9px] font-black"
                            >
                              {collapsed.has(row.id) ? '＋' : '−'}
                            </text>
                            <title>{collapsed.has(row.id) ? 'باز کردن شاخه' : 'بستن شاخه'}</title>
                          </g>
                        )}
                      </>
                    ) : (
                      <>
                        {isSelected && (
                          <rect
                            x={row.x - 3}
                            y={row.y - 3}
                            width={row.w + 6}
                            height={row.h + 6}
                            rx="13"
                            fill="none"
                            stroke={accent}
                            strokeOpacity="0.85"
                            strokeWidth="1.6"
                          />
                        )}
                        <rect
                          x={row.x}
                          y={row.y}
                          width={row.w}
                          height={row.h}
                          rx="10"
                          fill={isLight ? '#ffffff' : '#0b1329'}
                          fillOpacity={isLight ? 0.98 : 0.94}
                          stroke={onRail || isSelected ? accent : isLight ? '#cbd5e1' : 'rgba(71, 85, 105, 0.85)'}
                          strokeWidth={onRail || isSelected ? 2 : 1.1}
                        />
                        <text
                          x={row.right - 9}
                          y={row.midY + 4}
                          textAnchor="end"
                          fill={isLight ? '#0f172a' : '#f8fafc'}
                          className="text-[11.5px] font-black"
                        >
                          {node.label}
                        </text>
                        {node.origin === 'program' && (
                          <rect
                            x={row.x + 6}
                            y={row.midY - 3}
                            width="6"
                            height="6"
                            rx="1.5"
                            fill="none"
                            stroke={isLight ? '#a855f7' : '#c084fc'}
                            strokeWidth="1.2"
                          >
                            <title>{'افزونۀ منطقِ برنامه — سطرِ خودِ جزوه نیست'}</title>
                          </rect>
                        )}
                      </>
                    )}
                  </g>
                );
              })}
            </g>
          </g>
        </svg>
      </div>
      </div>

      {/* راهنمایِ فشردهٔ زیرِ بوم: خوانشِ نقشه، نه صفحۀ دومِ توضیح */}
      <div
        className={`flex flex-wrap items-center gap-x-4 gap-y-1 border-t px-4 py-1.5 text-3xs font-bold ${
          isLight ? 'bg-white border-slate-200 text-slate-500' : 'bg-bg-primary/70 border-border-c/60 text-text-muted'
        }`}
      >
        <span>▸ هر ستون یک صفحۀ چاپیِ جزوه است (۱ تا ۴، راست به چپ)</span>
        <span>▸ رابطۀ درونِ ستون = سطرِ والد و فرزندِ همان چارت</span>
        <span>▸ فلش‌هایِ بالا = سه وابستگیِ اعلام‌شدۀ صفحۀ ۴ (مهندسی معکوس)</span>
        <span className="text-purple-500 dark:text-neon-cyan">▸ خط‌چین = هم‌نامِ یک مفهوم درِ صفحۀ دیگر</span>
        <span>▸ ◇ = افزونۀ برنامۀ FTS، سطرِ جزوه نیست</span>
        <span>▸ روشن/خاموش فقط با پرست و جهتِ جریان — توپولوژی ثابت</span>
      </div>

"""

PATCHES = [
    # (old, new) — اصلاحِ ارجاعِ پنلِ بازرسی به میدان‌هایِ مدلِ تازه
    ("""              {inspectedNode.category === 'fund'
                ? 'F'
                : inspectedNode.category === 'tech'
                  ? 'T'
                  : inspectedNode.category === 'tape'
                    ? 'S'
                    : inspectedNode.category === 'money'
                      ? 'M'
                      : '★'}""",
     """              {inspectedNode.zone}"""),
    ("رکن: {inspectedNode.stageName}", "رکن: {ZONE_BY_KEY[inspectedNode.zone].stageName}"),
    ("selectedPreset === 'custom' && inspectedNode.stage > 0 && onToggleCustomNode",
     "selectedPreset === 'custom' && inspectedNode.kind === 'leaf' && onToggleCustomNode"),
    ("backgroundColor: `${inspectedNode.color}22`,", "backgroundColor: `${inspectedAccent}22`,"),
    ("border: `1.5px solid ${inspectedNode.color}77`,", "border: `1.5px solid ${inspectedAccent}77`,"),
    ("color: inspectedNode.color,", "color: inspectedAccent,"),
]

PROPS_SEG = (992, 1016)
TOOLBAR_SEG = (1212, 1348)
PLAQUE_SEG = (1350, 1396)
PANEL_SEG = (1712, 2347)


def main():
    src = io.open(COMP, encoding="utf-8", newline="").read()
    if src.startswith("// features/master/components/ObsidianStrategyGraph.tsx -- نقشۀ"):
        print("بوم بازنویسی‌شده — اول بکاپِ _audit/_graph_backup.tsx را برگردان")
        return 1
    lines = src.split("\n")
    for a, b in (PROPS_SEG, TOOLBAR_SEG, PLAQUE_SEG, PANEL_SEG):
        assert b <= len(lines), (a, b, len(lines))

    def seg(a, b):
        return "\n".join(lines[a - 1:b])

    props = seg(992, 1007)
    comets = seg(1009, 1016)
    # پروپ‌ها دست‌نخورده می‌مانند؛ فقط نوعِ پرست از مدلِ تازه می‌آید
    props = props.replace("selectedPreset: 'swing' | 'trend' | 'hourglass' | 'custom';",
                          "selectedPreset: FtsPreset;")
    out = "\n".join([HEAD, props, "", comets, "", TAIL_HEAD, seg(*TOOLBAR_SEG), "", seg(*PLAQUE_SEG), "",
                     CANVAS.rstrip(), seg(*PANEL_SEG).lstrip("\n")])
    for old, new in PATCHES:
        if old not in out:
            print("پیوندِ اصلاحی یافت نشد:", old[:60])
            return 1
        out = out.replace(old, new)
    io.open(COMP, "w", encoding="utf-8", newline="\n").write(out)
    print("بازسازی شد:", os.path.relpath(COMP, ROOT), "— خط:", out.count("\n") + 1)
    return 0


_UNUSED = """"""

if __name__ == "__main__":
    sys.exit(main())
