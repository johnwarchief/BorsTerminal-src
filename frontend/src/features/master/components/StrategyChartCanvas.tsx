// features/master/components/StrategyChartCanvas.tsx — بومِ مشترکِ چهار چارت FTS.
//
// هرچه اینجا رسم می‌شود از `strategyChartLayout` و `ftsChartModel` می‌آید؛
// هیچ گره/یال/متنِ تازه‌ای ساخته نمی‌شود. بوم فقط نمای یک Zone (چهار صفحهٔ
// مستقل) یا نمای ادغام‌شدهٔ چهار Zone با سه یالِ مستند (نقشهٔ جامع) است.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toFaDigits } from '@shared/lib/fmt';
import {
  ZONE_BY_KEY, refEdges,
  type FtsChartModel, type FtsZone,
} from '../lib/ftsChartModel';
import {
  VIEW_W, VIEW_H, defaultCollapsedForMaster, layoutStrategyChart,
  type ChartLayout, type LayoutNode,
} from '../lib/strategyChartLayout';

const TONE: Record<FtsZone, { border: string; text: string; soft: string; edge: string }> = {
  F: { border: 'border-emerald-500/50', text: 'text-emerald-400', soft: 'bg-emerald-500/10', edge: '#10b981' },
  T: { border: 'border-sky-500/50', text: 'text-sky-400', soft: 'bg-sky-500/10', edge: '#38bdf8' },
  S: { border: 'border-amber-500/50', text: 'text-amber-400', soft: 'bg-amber-500/10', edge: '#f59e0b' },
  M: { border: 'border-rose-500/50', text: 'text-rose-400', soft: 'bg-rose-500/10', edge: '#ef4444' },
};

type View = { scale: number; tx: number; ty: number };
const MIN_SCALE = 0.3;
const MAX_SCALE = 2.6;

export function StrategyChartCanvas({
  model, mode, zone, focus, onFocusChange, activeIds,
  selectedId, onSelect,
}: {
  model: FtsChartModel;
  mode: 'zone' | 'master';
  zone?: FtsZone;
  focus: FtsZone | null;
  onFocusChange: (z: FtsZone | null) => void;
  activeIds: Set<string>;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}) {
  const svgRef = useRef<SVGSVGElement | null>(null);
  const drag = useRef<{ x: number; y: number; tx: number; ty: number } | null>(null);
  const [view, setView] = useState<View>({ scale: 1, tx: 0, ty: 0 });
  const [collapsed, setCollapsed] = useState<Set<string>>(
    () => (mode === 'master' ? defaultCollapsedForMaster(model) : new Set()),
  );

  useEffect(() => {
    setCollapsed(mode === 'master' ? defaultCollapsedForMaster(model) : new Set());
  }, [mode, zone, focus, model]);

  const layout = useMemo(
    () => layoutStrategyChart(model, { mode, zone, focus, collapsed }),
    [model, mode, zone, focus, collapsed],
  );

  const fit = useCallback(() => {
    const s = Math.min((VIEW_W - 80) / layout.width, (VIEW_H - 80) / layout.height, 1);
    setView({
      scale: s,
      tx: (VIEW_W - layout.width * s) / 2,
      ty: (VIEW_H - layout.height * s) / 2,
    });
  }, [layout.width, layout.height]);

  useEffect(() => { fit(); }, [fit]);

  const zoom = (factor: number) => {
    setView((v) => {
      const scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, v.scale * factor));
      const cx = VIEW_W / 2;
      const cy = VIEW_H / 2;
      return { scale, tx: cx - (cx - v.tx) * (scale / v.scale), ty: cy - (cy - v.ty) * (scale / v.scale) };
    });
  };

  const reset = () => setView({ scale: 1, tx: 0, ty: 0 });

  // چرخ ماوس روی خودِ بوم، نه روی صفحه؛ listener غیر passive تا اسکرول نگیرد.
  useEffect(() => {
    const el = svgRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const r = el.getBoundingClientRect();
      if (r.width <= 0) return;
      const k = VIEW_W / r.width;
      const x = (e.clientX - r.left) * k;
      const y = (e.clientY - r.top) * k;
      setView((v) => {
        const scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, v.scale * (e.deltaY < 0 ? 1.1 : 0.9)));
        return { scale, tx: x - (x - v.tx) * (scale / v.scale), ty: y - (y - v.ty) * (scale / v.scale) };
      });
    };
    el.addEventListener('wheel', onWheel, { passive: false });
    return () => el.removeEventListener('wheel', onWheel);
  }, []);

  const nodeById = useMemo(() => new Map(layout.nodes.map((n) => [n.node.id, n])), [layout.nodes]);
  const dashed = useMemo(() => {
    if (!selectedId) return [];
    return refEdges(model).filter((e) => {
      if (e.source !== selectedId && e.target !== selectedId) return false;
      return nodeById.has(e.source) && nodeById.has(e.target);
    });
  }, [model, selectedId, nodeById]);

  const onPointerDown = (e: React.PointerEvent<SVGSVGElement>) => {
    if ((e.target as Element).closest('button')) return;
    drag.current = { x: e.clientX, y: e.clientY, tx: view.tx, ty: view.ty };
    e.currentTarget.setPointerCapture(e.pointerId);
  };
  const onPointerMove = (e: React.PointerEvent<SVGSVGElement>) => {
    if (!drag.current || !svgRef.current) return;
    const r = svgRef.current.getBoundingClientRect();
    if (r.width <= 0) return;
    const k = VIEW_W / r.width;
    setView((v) => ({
      ...v,
      tx: drag.current!.tx + (e.clientX - drag.current!.x) * k,
      ty: drag.current!.ty + (e.clientY - drag.current!.y) * k,
    }));
  };
  const onPointerUp = (e: React.PointerEvent<SVGSVGElement>) => {
    drag.current = null;
    if (e.currentTarget.hasPointerCapture(e.pointerId)) e.currentTarget.releasePointerCapture(e.pointerId);
  };

  return (
    <div className="flex min-w-0 flex-col gap-1">
      <div className="flex flex-wrap items-center gap-1 rounded-xl border border-border-c bg-bg-primary/90 p-1.5 shadow-sm"
        data-testid="strategy-chart-toolbar">
        <button type="button" data-testid="chart-zoom-in" onClick={() => zoom(1.2)}
          className="rounded-lg border border-border-c px-2 py-1 text-xs font-black text-text-secondary hover:text-accent-blue" title="بزرگ‌نمایی">＋</button>
        <button type="button" data-testid="chart-zoom-out" onClick={() => zoom(1 / 1.2)}
          className="rounded-lg border border-border-c px-2 py-1 text-xs font-black text-text-secondary hover:text-accent-blue" title="کوچک‌نمایی">−</button>
        <button type="button" data-testid="chart-fit" onClick={fit}
          className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-text-secondary hover:text-accent-blue" title="جا دادن کل نقشه در قاب">Fit</button>
        <button type="button" data-testid="chart-reset" onClick={reset}
          className="rounded-lg border border-border-c px-2 py-1 text-2xs font-bold text-text-secondary hover:text-accent-blue" title="بازگشت به نمای اولیه">Reset</button>
        <span className="num px-1 text-2xs font-black text-text-muted" data-testid="chart-zoom-value">
          {toFaDigits(Math.round(view.scale * 100))}٪
        </span>
        {mode === 'master' ? (
          <div className="ms-auto flex flex-wrap items-center gap-1" role="group" aria-label="تمرکز روی یک بخش">
            <button type="button" data-testid="chart-focus-all" onClick={() => onFocusChange(null)}
              className={`rounded-lg border px-2 py-1 text-2xs font-bold ${!focus ? 'border-accent-blue/60 bg-accent-blue/15 text-accent-blue' : 'border-border-c text-text-muted'}`}>
              همه
            </button>
            {(Object.keys(TONE) as FtsZone[]).map((z) => (
              <button key={z} type="button" data-testid={`chart-focus-${z}`} onClick={() => onFocusChange(z)}
                className={`rounded-lg border px-2 py-1 text-2xs font-black ${focus === z ? `${TONE[z].border} ${TONE[z].text} ${TONE[z].soft}` : 'border-border-c text-text-muted'}`}>
                {z}
              </button>
            ))}
          </div>
        ) : null}
      </div>

      <div
        className="relative h-[68vh] min-h-[480px] w-full overflow-hidden rounded-2xl border border-border-c bg-[radial-gradient(circle_at_1px_1px,var(--border-c)_1px,transparent_0)] bg-[length:22px_22px]"
      data-testid="strategy-chart-canvas"
      data-mode={mode}
      data-zone={mode === 'zone' ? zone : ''}
      data-zoom={Math.round(view.scale * 100)}
      data-selected={selectedId ?? ''}
    >
      <svg
        ref={svgRef}
        viewBox={`0 0 ${VIEW_W} ${VIEW_H}`}
        className="h-full w-full touch-none select-none"
        role="img"
        aria-label={mode === 'master' ? 'نقشهٔ جامع FTS — چهار چارت و سه وابستگیِ مستند' : `چارت ${ZONE_BY_KEY[zone ?? 'F'].title}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        data-testid="strategy-chart-svg"
      >
        <defs>
          {(Object.keys(TONE) as FtsZone[]).map((z) => (
            <marker key={z} id={`arrow-${z}`} viewBox="0 0 10 10" refX="9" refY="5"
              markerWidth="6" markerHeight="6" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill={TONE[z].edge} />
            </marker>
          ))}
          <marker id="arrow-zone" viewBox="0 0 10 10" refX="9" refY="5"
            markerWidth="7" markerHeight="7" orient="auto-start-reverse">
            <path d="M 0 0 L 10 5 L 0 10 z" fill="#60a5fa" />
          </marker>
        </defs>
        <g transform={`translate(${view.tx} ${view.ty}) scale(${view.scale})`}>
          {layout.lanes.map((lane) => (
            <g key={lane.zone} data-testid={`chart-lane-${lane.zone}`}>
              <rect x={lane.x} y={0} width={lane.width} height={lane.height} rx={20}
                fill={TONE[lane.zone].edge} opacity={0.035} />
              <text x={lane.x + lane.width / 2} y={24} textAnchor="middle"
                fill={TONE[lane.zone].edge} fontSize={16} fontWeight={900}>
                {ZONE_BY_KEY[lane.zone].title} · {ZONE_BY_KEY[lane.zone].sub}
              </text>
              <text x={lane.x + lane.width / 2} y={46} textAnchor="middle"
                fill="currentColor" opacity={0.6} fontSize={11}>
                {ZONE_BY_KEY[lane.zone].stageName} · ارجاع: چارت صفحهٔ {toFaDigits(ZONE_BY_KEY[lane.zone].page)}
              </text>
            </g>
          ))}

          {layout.edges.map((edge) => {
            const active = activeIds.has(edge.source) && activeIds.has(edge.target);
            if (edge.kind === 'zone') {
              return (
                <g key={edge.id} data-testid={`strategy-zone-edge-${edge.id}`}>
                  <path d={edge.path} fill="none" stroke="#60a5fa" strokeWidth={2.2}
                    strokeDasharray="7 4" markerEnd="url(#arrow-zone)" opacity={0.85} />
                </g>
              );
            }
            return (
              <path key={edge.id} d={edge.path} fill="none"
                stroke={TONE[edge.sourceZone].edge}
                strokeWidth={active ? 2 : 1.1}
                opacity={active ? 0.9 : 0.38}
                markerEnd={`url(#arrow-${edge.sourceZone})`}
                data-testid={`strategy-tree-edge-${edge.id}`} />
            );
          })}

          {dashed.map((e) => {
            const a = nodeById.get(e.source);
            const b = nodeById.get(e.target);
            if (!a || !b) return null;
            return (
              <path key={e.id}
                d={`M ${a.x + a.w} ${a.y + a.h / 2} C ${a.x + a.w + 40} ${a.y}, ${b.x - 40} ${b.y}, ${b.x} ${b.y + b.h / 2}`}
                fill="none" stroke="#94a3b8" strokeWidth={1.2} strokeDasharray="4 4" opacity={0.8}
                data-testid={`strategy-ref-edge-${e.id}`} />
            );
          })}

          {layout.nodes.map((n) => (
            <NodeCard key={n.node.id} box={n} collapsed={collapsed.has(n.node.id)}
              selected={selectedId === n.node.id}
              active={activeIds.has(n.node.id)}
              onSelect={onSelect}
              onToggle={(id) => setCollapsed((prev) => {
                const next = new Set(prev);
                if (next.has(id)) next.delete(id); else next.add(id);
                return next;
              })} />
          ))}
        </g>
      </svg>

      <div className="pointer-events-none absolute inset-x-2 bottom-2 flex flex-wrap items-center justify-between gap-1 text-3xs text-text-muted">
        <span>کشیدن = جابه‌جایی · چرخ ماوس = بزرگ‌نمایی · گره = جزئیات</span>
        <span>مسیر روشن = پرستِ فعال · خط‌چین = هم‌زادِ مفهومی · فلشِ آبی = وابستگیِ مستندِ چارت ۴</span>
      </div>
      </div>
    </div>
  );
}

function NodeCard({
  box, collapsed, selected, active, onSelect, onToggle,
}: {
  box: LayoutNode;
  collapsed: boolean;
  selected: boolean;
  active: boolean;
  onSelect: (id: string | null) => void;
  onToggle: (id: string) => void;
}) {
  const { node } = box;
  const tone = TONE[node.zone];
  const hasChildren = box.hiddenCount > 0;
  return (
    <foreignObject x={box.x} y={box.y} width={box.w} height={box.h} style={{ overflow: 'visible' }}>
      <div className="relative h-full w-full" style={{ direction: 'rtl' }}>
        <button
          type="button"
          data-testid={`strategy-node-${node.id}`}
          data-node-id={node.id}
          aria-pressed={selected}
          onClick={() => onSelect(node.id)}
          title={node.fullTitle}
          className={`h-full w-full rounded-xl border px-2 py-1 text-start transition-colors ${tone.border} ${
            selected ? `${tone.soft} ring-2 ring-accent-blue` : active ? tone.soft : 'bg-bg-card/95'
          } ${node.origin === 'program' ? 'border-dashed' : ''}`}
        >
          <span className="block truncate text-xs font-black leading-4 text-text-primary">{node.label}</span>
          <span className="mt-0.5 flex items-center justify-between gap-1 text-2xs font-bold text-text-muted">
            <span className={tone.text}>{node.zone} · {node.page}</span>
            <span>{node.origin === 'chart' ? 'چارت' : 'برنامه'}</span>
          </span>
          {active ? <span className={`mt-0.5 block text-2xs font-black ${tone.text}`}>مسیر روشن</span> : null}
        </button>
        {hasChildren ? (
          <button
            type="button"
            data-testid={`strategy-collapse-${node.id}`}
            aria-label={collapsed ? `بازکردن ${node.label}` : `بستن ${node.label}`}
            onClick={(e) => { e.stopPropagation(); onToggle(node.id); }}
            className="absolute -start-2 -top-2 grid h-5 min-w-5 place-items-center rounded-full border border-border-c bg-bg-primary px-1 text-3xs font-black text-text-secondary hover:text-accent-blue">
            {collapsed ? `+${toFaDigits(box.hiddenCount)}` : '−'}
          </button>
        ) : null}
      </div>
    </foreignObject>
  );
}

export type { ChartLayout };
