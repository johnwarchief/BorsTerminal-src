// features/master/components/ObsidianStrategyGraph.tsx -- نقشۀ استراتژی FTS: چهار صفحۀ چاپی در یک بوم
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
export { getGraphLinks } from '../lib/ftsChartModel';


export interface ObsidianStrategyGraphProps {
  selectedPreset: FtsPreset;
  symbol?: string;
  activeCustomNodes?: string[];
  onToggleCustomNode?: (nodeId: string) => void;
  /** پلاک نماد (#222): وضعیتِ هر چهار فاز + سطوحِ ورود/خروجِ همان سهم، رویِ نقشه */
  symbolPhaseStatus?: { k: string; status: 'pass' | 'wait' | 'fail'; label: string }[];
  symbolLevels?: {
    price: number | null;
    entry: number | null;
    support: number | null;
    resistance: number | null;
    hardStop: number | null;
    exitVerdict?: string | null;
  };
}

/** دانه‌هایِ جاده: جابه‌جاییِ واقعی رویِ همان منحنی، نه سوسوی درجا.
 *  حرکت با SMIL (`animateMotion`) انجام می‌شود چون «تبدیل» است نه لی‌اوت:
 *  سنجشِ ۱۴۰۵-۰۷-۰۹ (رأیِ pilot: گزینهٔ c، اطمینان ۰٫۸، ریسک ۰٫۲۸) خط‌چینِ
 *  متحرکِ CSS را ۱۰۱۴ لی‌اوت در ۱۲ ثانیه و نبضِ opacity را ۲۴۹ نشان داد —
 *  ولی مالک انیمیشنی را که جابه‌جایی ندارد «حذف‌شده» می‌شمارد. پس دانه
 *  حرکت می‌کند، به‌شرطِ اینکه تعدادِ مسیر کم و نفسِ حرکت بلند بماند. */
const COMET_N = 3;
const COMET_DUR_S = 4.8;


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

      {/* ۱. نوار ابزار کنترل استراتژی، جستجو و تغییر جهت جریان
          backdrop-blur حذف شد: بالای SVGِ همیشه‌متحرک، هر فریم را مجبور به
          re-blur می‌کرد و گرافیک را بی‌دلیل درگیر می‌نمود (#221). جایش یک
          پس‌زمینهٔ نیمه‌شفافِ جامد نشست که همان خوانایی را می‌دهد. */}
      <div
        className={`flex flex-wrap items-center justify-between gap-3 border-b px-4 py-2.5 transition-colors ${
          isLight ? 'bg-white border-slate-200' : 'bg-bg-card border-border-c/60'
        }`}
      >
        {/* سوییچ جهت جریان: مهندسی معکوس نوسان‌گیری vs جریان مستقیم
            (سوییچرِ پیش‌فرضِ بازی در خودِ صفحه هست و این‌جا تکرار نشد) */}
        <div className="flex items-center gap-2 flex-wrap">
          <div
            className={`flex items-center rounded-xl p-0.5 border text-2xs font-bold transition-colors ${
              isLight ? 'bg-slate-200/70 border-slate-300' : 'bg-bg-primary/80 border-border-c/70'
            }`}
          >
            <button
              type="button"
              onClick={() => setFlowDirection('reverse')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition-all ${
                flowDirection === 'reverse'
                  ? isLight
                    ? 'bg-white text-sky-700 font-black shadow-sm'
                    : 'bg-accent-blue/30 text-accent-blue font-black shadow-[0_0_8px_rgba(56,189,248,0.3)]'
                  : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-text-muted hover:text-text-primary'
              }`}
              title="مهندسی معکوس نوسان‌گیری طبق صفحه ۴ و ۱۹ جزوه: تابلوخوانی ➔ تکنیکال ➔ بنیادی ➔ خروج"
            >
              <span>🔄</span>
              <span>مهندسی معکوس (نوسان‌گیری)</span>
            </button>

            <button
              type="button"
              onClick={() => setFlowDirection('classic')}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-lg transition-all ${
                flowDirection === 'classic'
                  ? isLight
                    ? 'bg-white text-emerald-700 font-black shadow-sm'
                    : 'bg-accent-green/30 text-accent-green font-black shadow-[0_0_8px_rgba(34,197,94,0.3)]'
                  : isLight
                    ? 'text-slate-600 hover:text-slate-900'
                    : 'text-text-muted hover:text-text-primary'
              }`}
              title="جریان کلاسیک تحلیلی: بنیادی کدال ➔ تکنیکال ➔ تابلوخوانی ➔ مدیریت سرمایه"
            >
              <span>📑</span>
              <span>جریان مستقیم (کلاسیک)</span>
            </button>
          </div>

          {/* فیلد جستجو */}
          <div className="relative">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="🔍 جستجو در قوانین و نودها..."
              className={`w-36 sm:w-44 rounded-lg border px-2.5 py-1 text-2xs transition-colors focus:outline-none ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-800 placeholder:text-slate-400 focus:border-sky-500'
                  : 'border-border-c/60 bg-bg-primary/70 text-text-primary placeholder:text-text-muted focus:border-accent-blue'
              }`}
            />
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery('')}
                className="absolute left-2 top-1 text-3xs text-text-muted hover:text-text-primary"
              >
                ✕
              </button>
            )}
          </div>

          {/* ابزارهای زوم و ریست */}
          <div className={`flex items-center gap-1 border-s ps-2 ${isLight ? 'border-slate-300' : 'border-border-c/50'}`}>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.min(z + 0.15, 1.9))}
              className={`h-6 w-6 rounded border text-xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="بزرگ‌نمایی"
            >
              +
            </button>
            <button
              type="button"
              onClick={() => setZoom((z) => Math.max(z - 0.15, 0.55))}
              className={`h-6 w-6 rounded border text-xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="کوچک‌نمایی"
            >
              −
            </button>
            <button
              type="button"
              onClick={handleResetView}
              className={`px-2 h-6 rounded border text-3xs font-bold transition-colors ${
                isLight
                  ? 'border-slate-300 bg-white text-slate-700 hover:bg-slate-100'
                  : 'border-border-c/60 bg-bg-primary text-text-secondary hover:text-text-primary'
              }`}
              title="بازنشانی زاویه دید"
            >
              ⊙ نما
            </button>
          </div>

          {/* دکمه بازنشانی تمام پارامترها به مقادیر رسمی جزوه */}
          <button
            type="button"
            onClick={() => {
              if (window.confirm('آیا مایلید تمام پارامترها و فرمول‌ها به مقادیر مرجع جزوه FTS بازنشانی شوند؟')) {
                resetAll();
              }
            }}
            className={`rounded-lg border px-2.5 py-1 text-3xs font-bold transition-colors ${
              isLight
                ? 'border-amber-400 bg-amber-50 text-amber-700 hover:bg-amber-100'
                : 'border-border-c/60 bg-bg-primary/60 text-accent-yellow hover:bg-accent-yellow/15'
            }`}
            title="بازنشانی کلیه تنظیمات به مقادیر استاندارد جزوه نصرتی"
          >
            ⟲ مرجع جزوه
          </button>
        </div>
      </div>

      {/* پلاکِ نماد (#222): وضعیتِ چهار فاز F/T/S/M و سطوحِ ورود/خروج، درست
          بالایِ بوم — همان شماره‌های evaluateFtsPipeline و /api/fts، نه محاسبهٔ دوم. */}
      {symbol && symbolPhaseStatus && symbolPhaseStatus.length > 0 && (
        <div
          data-testid="graph-symbol-plaque"
          className={`flex flex-wrap items-center gap-2.5 border-b px-4 py-2 text-2xs font-bold transition-colors ${
            isLight ? 'bg-slate-100/90 border-slate-200' : 'bg-bg-primary/80 border-border-c/60'
          }`}
        >
          <span className="font-black text-text-primary">پلاکِ {symbol}:</span>
          {symbolPhaseStatus.map((p) => {
            const c = p.status === 'pass'
              ? 'border-accent-green/50 bg-accent-green/15 text-accent-green'
              : p.status === 'wait'
                ? 'border-accent-yellow/50 bg-accent-yellow/15 text-accent-yellow'
                : 'border-accent-red/50 bg-accent-red/15 text-accent-red';
            return (
              <span
                key={p.k}
                title={`${p.label} — ${p.status === 'pass' ? 'تایید' : p.status === 'wait' ? 'در انتظار' : 'رد / وتو'}`}
                className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 ${c}`}
              >
                <span className="font-black">{p.k}</span>
                <span className="h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
              </span>
            );
          })}
          {symbolLevels && (
            <span className={`ms-auto inline-flex flex-wrap items-center gap-2 rounded-lg border px-2.5 py-1 font-mono tabular-nums ${
              isLight ? 'border-slate-300 bg-white text-slate-800' : 'border-border-c/70 bg-bg-card text-text-primary'
            }`}>
              <span title="قیمت آخرین معامله">قیمت: {symbolLevels.price != null ? toFaDigits(symbolLevels.price) : '—'}</span>
              <span title="ورود: شکست مقاومت جت یا پولبک به تاز حمایتی">
                ورود: {symbolLevels.entry != null ? toFaDigits(symbolLevels.entry) : '—'}
              </span>
              <span title="حمایت (تاز فیبو ۳۳-۴۰٪)">حمایت: {symbolLevels.support != null ? toFaDigits(symbolLevels.support) : '—'}</span>
              <span title="مقاومت (سقف جت)">مقاومت: {symbolLevels.resistance != null ? toFaDigits(symbolLevels.resistance) : '—'}</span>
              <span title="حد ضررِ موتور خروج (hard stop)">حدضرر: {symbolLevels.hardStop != null ? toFaDigits(symbolLevels.hardStop) : '—'}</span>
              {symbolLevels.exitVerdict && (
                <span title="حکمِ موتور خروج سرور" className="rounded bg-bg-secondary px-1.5 py-0.5 text-3xs text-text-secondary">
                  خروج: {symbolLevels.exitVerdict}
                </span>
              )}
            </span>
          )}
        </div>
      )}


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
          // یک‌به‌یک: کوچک‌تر نشود (بازخورد مالک) و بزرگ‌تر هم نشود تا قدِ
          // نقشه از دیدِ ۱۰۸۰ بیرون نزند؛ تنگ‌جا اسکرول افقی می‌خورد.
          width: layout.width,
          minWidth: layout.width,
          maxWidth: layout.width,
          aspectRatio: `${layout.width} / ${layout.height}`,
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
                  <g
                    key={zone.key}
                    data-zone-frame={zone.key}
                    data-zone-slot={zone.slot}
                    data-phase-status={phase?.status ?? 'none'}
                    data-lit-count={litCountByZone[zone.key]}
                  >
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
                      textAnchor="start"
                      fill={accent}
                      className="text-[13px] font-black"
                    >
                      {meta.title}
                    </text>
                    <text
                      x={zone.x + 10}
                      y={yHead + 19}
                      textAnchor="end"
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
                  // گامِ بازگشتی (F➔M در مهندسی معکوس) از شکافِ میانِ سربرگ‌ها
                  // برمی‌گردد — نه از پایینِ بوم، تا ساقۀ بلندِ عمودی نسازد.
                  d = `M ${a.x + a.w / 2} ${y + 22} Q ${(a.x + b.x + a.w) / 2} ${y + 40}, ${b.x + b.w / 2} ${y + 22}`;
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
                  <g key={step.id} data-rail-step={step.id} data-rail-arc={step.arc ? '1' : '0'} data-lit={step.lit ? '1' : '0'}>
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
                    data-tree-edge={l.id}
                    data-src={l.source}
                    data-dst={l.target}
                    data-lit={lit ? '1' : '0'}
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
                    data-ref-edge={r.id}
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
                    data-node-id={row.id}
                    data-node-zone={node.zone}
                    data-node-kind={row.kind}
                    data-origin={node.origin}
                    data-lit={lit ? '1' : '0'}
                    data-rail={onRail ? '1' : '0'}
                    data-collapsed={collapsed.has(row.id) ? '1' : '0'}
                    opacity={dim}
                    onPointerEnter={() => setHoveredNodeId(row.id)}
                    onPointerLeave={() => setHoveredNodeId((cur) => (cur === row.id ? null : cur))}
                    onClick={() => {
                      setSelectedNodeId(row.id);
                      toggleCustom();
                    }}
                    style={{ cursor: 'pointer' }}
                  >
                    {row.kind === 'head' ? (
                      <>
                        <text
                          x={row.right - 2}
                          y={row.midY + 4}
                          textAnchor="start"
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
                            data-collapse-toggle={row.id}
                          >
                            {/* دسترسِ ۱۶ واحدی در چپِ برچسبِ شاخه — بیرونِ ستون نمی‌زند */}
                            <rect
                              x={row.x - 19}
                              y={row.y}
                              width="17"
                              height={row.h}
                              rx="4"
                              fill={isLight ? '#e2e8f0' : '#111a2e'}
                              stroke={isLight ? '#cbd5e1' : '#334155'}
                              strokeWidth="0.8"
                            />
                            <text
                              x={row.x - 10.5}
                              y={row.midY + 4}
                              textAnchor="middle"
                              fill={isLight ? '#475569' : '#94a3b8'}
                              className="text-[10px] font-black"
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
                          textAnchor="start"
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
      {/* ۳. پنل جامع ویرایشگر پارامترها و بازرسی نود انتخاب‌شده (Interactive Parameter Editor) */}
      <div
        className={`border-t p-4 sm:p-5 transition-colors ${
          isLight ? 'bg-white border-slate-200 text-slate-800' : 'bg-bg-card border-border-c/80 text-text-primary'
        }`}
      >
        <div className="flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4">
          {/* سمت راست: مشخصات، فرمول و توضیحات نود */}
          <div className="flex items-start gap-3.5">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg font-black shadow-md"
              style={{
                backgroundColor: `${inspectedAccent}22`,
                border: `1.5px solid ${inspectedAccent}77`,
                color: inspectedAccent,
              }}
            >
              {inspectedNode.zone}
            </div>

            <div className="space-y-1.5">
              <div className="flex items-center gap-2 flex-wrap">
                <h3 className={`text-sm sm:text-base font-black ${isLight ? 'text-slate-900' : 'text-text-primary'}`}>
                  {inspectedNode.fullTitle}
                </h3>
                <span
                  className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                    isLight
                      ? 'bg-sky-50 text-sky-700 border-sky-200'
                      : 'bg-bg-primary text-accent-blue border-border-c'
                  }`}
                >
                  {inspectedNode.page}
                </span>
                <span
                  className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                    isLight
                      ? 'bg-slate-100 text-slate-600 border-slate-200'
                      : 'bg-bg-primary text-text-muted border-border-c'
                  }`}
                >
                  رکن: {ZONE_BY_KEY[inspectedNode.zone].stageName}
                </span>
                {symbol && (
                  <span
                    className={`rounded px-2 py-0.5 text-2xs font-bold border ${
                      isLight
                        ? 'bg-cyan-50 text-cyan-700 border-cyan-200'
                        : 'bg-bg-primary text-accent-cyan border-border-c'
                    }`}
                  >
                    نماد فعال: {symbol}
                  </span>
                )}
              </div>
              <p
                className={`text-xs max-w-3xl leading-relaxed font-medium ${
                  isLight ? 'text-slate-700' : 'text-text-secondary'
                }`}
              >
                {inspectedNode.description}
              </p>
              <div className="text-xs font-mono flex items-center gap-1.5 pt-0.5">
                <span className={`font-sans font-bold text-xs ${isLight ? 'text-slate-500' : 'text-text-muted'}`}>
                  فرمول و شرط قانون:
                </span>
                <span className={`font-bold ${isLight ? 'text-slate-900' : 'text-accent-blue'}`}>
                  {inspectedNode.ruleFormula}
                </span>
              </div>
            </div>
          </div>

          {/* سمت چپ: دکمه‌های اقدام سریع */}
          <div className="flex items-center gap-2 self-end lg:self-center shrink-0">
            {inspectedNode.editableParamKeys && inspectedNode.editableParamKeys.length > 0 && (
              <button
                type="button"
                onClick={() => {
                  inspectedNode.editableParamKeys?.forEach((k) => resetParam(k));
                }}
                className={`rounded-xl border px-3 py-1.5 text-2xs font-bold transition-all ${
                  isLight
                    ? 'border-amber-400 bg-amber-50 text-amber-800 hover:bg-amber-100'
                    : 'border-border-c/70 bg-bg-primary text-accent-yellow hover:bg-accent-yellow/15'
                }`}
                title="بازنشانی پارامترهای این نود به مقدار اصلی جزوه FTS"
              >
                ⟲ بازنشانی به جزوه
              </button>
            )}

            {selectedPreset === 'custom' && inspectedNode.kind === 'leaf' && onToggleCustomNode && (
              <button
                type="button"
                onClick={() => onToggleCustomNode(inspectedNode.id)}
                className={`rounded-xl px-3.5 py-1.5 text-2xs font-bold transition-all ${
                  activeCustomNodes.includes(inspectedNode.id)
                    ? isLight
                      ? 'bg-rose-100 border border-rose-500 text-rose-700'
                      : 'bg-accent-red/20 border border-accent-red text-accent-red'
                    : isLight
                      ? 'bg-emerald-100 border border-emerald-500 text-emerald-700'
                      : 'bg-accent-green/20 border border-accent-green text-accent-green'
                }`}
              >
                {activeCustomNodes.includes(inspectedNode.id) ? '✕ حذف از مسیر من' : '＋ فعال در مسیر من'}
              </button>
            )}
          </div>
        </div>

        {/* ۴. کنترل‌های تعاملی تغییر مقادیر و اعداد استراتژی (Live Parameter Sliders & Inputs) */}
        {inspectedNode.editableParamKeys && inspectedNode.editableParamKeys.length > 0 && (
          <div
            className={`mt-4 pt-3.5 border-t grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3.5 ${
              isLight ? 'border-slate-200' : 'border-border-c/60'
            }`}
          >
            {/* ۱. ضریب حجم مشکوک */}
            {inspectedNode.editableParamKeys.includes('minVolumeRatio') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ضریب حجم مشکوک:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.minVolumeRatio)} برابر
                  </span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="5.0"
                  step="0.1"
                  value={params.minVolumeRatio}
                  onChange={(e) => updateParam('minVolumeRatio', parseFloat(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵×</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۳.۰×</span>
                  <span>۵.۰×</span>
                </div>
              </div>
            )}

            {/* ۲. حداقل قدرت خریدار به فروشنده */}
            {inspectedNode.editableParamKeys.includes('minBuyerPower') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل قدرت خریدار:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.minBuyerPower)}
                  </span>
                </div>
                <input
                  type="range"
                  min="1.0"
                  max="2.5"
                  step="0.05"
                  value={params.minBuyerPower}
                  onChange={(e) => updateParam('minBuyerPower', parseFloat(e.target.value))}
                  className="w-full accent-cyan-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۰</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱.۲</span>
                  <span>۲.۵</span>
                </div>
              </div>
            )}

            {/* ۳. حداقل درصد اختلاف الگوی ساعت */}
            {inspectedNode.editableParamKeys.includes('clockPriceDiffPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل اختلاف ساعت:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.clockPriceDiffPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="0.5"
                  max="3.0"
                  step="0.1"
                  value={params.clockPriceDiffPct}
                  onChange={(e) => updateParam('clockPriceDiffPct', parseFloat(e.target.value))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۰.۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱.۰٪</span>
                  <span>۳.۰٪</span>
                </div>
              </div>
            )}

            {/* ۴. حداقل ارزش معاملات خرد بازار مساعد (همت) */}
            {inspectedNode.editableParamKeys.includes('marketLiquidityMinHemmat') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ارزش معاملات خرد بازار مساعد:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.marketLiquidityMinHemmat)} همت
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="40"
                  step="1"
                  value={params.marketLiquidityMinHemmat}
                  onChange={(e) => updateParam('marketLiquidityMinHemmat', parseInt(e.target.value, 10))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۵ همت</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰ همت</span>
                  <span>۴۰ همت</span>
                </div>
              </div>
            )}

            {/* ۵. دوره میانگین متحرک استاپ نوسان‌گیر */}
            {inspectedNode.editableParamKeys.includes('stopLossMaPeriod') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    دوره میانگین متحرک استاپ:
                  </span>
                  <span className="text-xs font-black text-rose-600 dark:text-accent-red font-mono">
                    MA-{toFaDigits(params.stopLossMaPeriod)}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[10, 14, 20].map((period) => (
                    <button
                      key={period}
                      type="button"
                      onClick={() => updateParam('stopLossMaPeriod', period)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.stopLossMaPeriod === period
                          ? isLight
                            ? 'bg-rose-100 border border-rose-500 text-rose-700'
                            : 'bg-accent-red/20 border border-accent-red text-accent-red'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      MA-{toFaDigits(period)} {period === 14 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۶. درصد حد ضرر ثابت از قیمت ورود */}
            {inspectedNode.editableParamKeys.includes('stopLossFixedPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    درصد حد ضرر ثابت:
                  </span>
                  <span className="text-xs font-black text-rose-600 dark:text-accent-red font-mono">
                    {toFaDigits(params.stopLossFixedPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="2.0"
                  max="10.0"
                  step="0.5"
                  value={params.stopLossFixedPct}
                  onChange={(e) => updateParam('stopLossFixedPct', parseFloat(e.target.value))}
                  className="w-full accent-rose-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۲٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۵٪</span>
                  <span>۱۰٪</span>
                </div>
              </div>
            )}

            {/* ۷. حداقل حاشیه سود ناخالص کدال */}
            {inspectedNode.editableParamKeys.includes('minGrossMarginPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل حاشیه سود ناخالص:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.minGrossMarginPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="40"
                  step="1"
                  value={params.minGrossMarginPct}
                  onChange={(e) => updateParam('minGrossMarginPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰٪ (سوپر ۳۰٪)</span>
                  <span>۴۰٪</span>
                </div>
              </div>
            )}

            {/* ۸. حداقل درصد رشد فروش ماهانه کدال */}
            {inspectedNode.editableParamKeys.includes('minMonthlySalesGrowthPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل رشد فروش ماهانه:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.minMonthlySalesGrowthPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="15"
                  max="60"
                  step="5"
                  value={params.minMonthlySalesGrowthPct}
                  onChange={(e) => updateParam('minMonthlySalesGrowthPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۴۰٪</span>
                  <span>۶۰٪</span>
                </div>
              </div>
            )}

            {/* ۹. درصدِ فروش در اولین سقف — جزوه: «سیگنال فروش ٪۵۰» */}
            {inspectedNode.editableParamKeys.includes('exitHalfPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    درصد فروش در اولین سقف:
                  </span>
                  <span className="text-xs font-black text-sky-600 dark:text-accent-blue font-mono">
                    {toFaDigits(params.exitHalfPct)}٪
                  </span>
                </div>
                <div className="grid grid-cols-4 gap-1.5">
                  {[30, 50, 70, 100].map((pct) => (
                    <button
                      key={pct}
                      type="button"
                      onClick={() => updateParam('exitHalfPct', pct)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.exitHalfPct === pct
                          ? isLight
                            ? 'bg-sky-100 border border-sky-500 text-sky-700'
                            : 'bg-accent-blue/20 border border-accent-blue text-accent-blue'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(pct)}٪ {pct === 50 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۱۰. آستانه سقف سوم خروج (هفتگی ۱۰٪ و روزانه ۵٪) */}
            {inspectedNode.editableParamKeys.includes('thirdPeakWeeklyPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    فاصله تا خط روند در سقف ۳:
                  </span>
                  <span className="text-xs font-black text-orange-600 dark:text-orange-400 font-mono">
                    هفتگی {toFaDigits(params.thirdPeakWeeklyPct)}٪ | روزانه {toFaDigits(params.thirdPeakDailyPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="5"
                  max="20"
                  step="1"
                  value={params.thirdPeakWeeklyPct}
                  onChange={(e) => updateParam('thirdPeakWeeklyPct', parseInt(e.target.value, 10))}
                  className="w-full accent-orange-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۵٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۱۰٪ هفتگی</span>
                  <span>۲۰٪</span>
                </div>
              </div>
            )}

            {/* ۱۱. سقف کل دارایی در بورس و شرایط جنگی */}
            {inspectedNode.editableParamKeys.includes('maxTotalPortfolioCapPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    سقف بورس عادی / جنگی:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.maxTotalPortfolioCapPct)}٪ / {toFaDigits(params.warConditionCapPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="40"
                  max="90"
                  step="5"
                  value={params.maxTotalPortfolioCapPct}
                  onChange={(e) => updateParam('maxTotalPortfolioCapPct', parseInt(e.target.value, 10))}
                  className="w-full accent-amber-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۴۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۷۰٪ بورس (۱۵٪ جنگی)</span>
                  <span>۹۰٪</span>
                </div>
              </div>
            )}

            {/* ۱۲. حداقل نسبت ریسک به ریوارد */}
            {inspectedNode.editableParamKeys.includes('minRiskRewardRatio') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    حداقل نسبت سود به ریسک:
                  </span>
                  <span className="text-xs font-black text-purple-600 dark:text-purple-400 font-mono">
                    {toFaDigits(params.minRiskRewardRatio)}
                  </span>
                </div>
                <input
                  type="range"
                  min="1.5"
                  max="3.5"
                  step="0.1"
                  value={params.minRiskRewardRatio}
                  onChange={(e) => updateParam('minRiskRewardRatio', parseFloat(e.target.value))}
                  className="w-full accent-purple-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱.۵</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">پیش‌فرضِ برنامه: ۲.۰</span>
                  <span>۳.۵</span>
                </div>
              </div>
            )}

            {/* ۱۳. سقف وزن سرمایه‌گذاری در هر صنعت */}
            {inspectedNode.editableParamKeys.includes('maxIndustryWeightPct') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    سقف سرمایه‌گذاری در صنعت:
                  </span>
                  <span className="text-xs font-black text-emerald-600 dark:text-accent-green font-mono">
                    {toFaDigits(params.maxIndustryWeightPct)}٪
                  </span>
                </div>
                <input
                  type="range"
                  min="10"
                  max="35"
                  step="5"
                  value={params.maxIndustryWeightPct}
                  onChange={(e) => updateParam('maxIndustryWeightPct', parseInt(e.target.value, 10))}
                  className="w-full accent-emerald-500 cursor-pointer"
                />
                <div className="flex items-center justify-between text-3xs text-text-muted">
                  <span>۱۰٪</span>
                  <span className="text-amber-600 dark:text-accent-yellow font-bold">جزوه: ۲۰٪</span>
                  <span>۳۵٪</span>
                </div>
              </div>
            )}

            {/* ۱۴. ضریب اهرم خرید کف ساعت شنی */}
            {inspectedNode.editableParamKeys.includes('hourglassLeverageMultiplier') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    ضریب اهرم خرید در کف:
                  </span>
                  <span className="text-xs font-black text-amber-600 dark:text-accent-yellow font-mono">
                    {toFaDigits(params.hourglassLeverageMultiplier)} برابر
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[2.0, 3.0, 4.0].map((mul) => (
                    <button
                      key={mul}
                      type="button"
                      onClick={() => updateParam('hourglassLeverageMultiplier', mul)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.hourglassLeverageMultiplier === mul
                          ? isLight
                            ? 'bg-amber-100 border border-amber-500 text-amber-700'
                            : 'bg-accent-yellow/20 border border-accent-yellow text-accent-yellow'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(mul)}× {mul === 3.0 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* ۱۵. فرصت روزهای تثبیت ستاپ جت */}
            {inspectedNode.editableParamKeys.includes('jetStabilizationDays') && (
              <div
                className={`rounded-xl border p-3 space-y-2 ${
                  isLight ? 'border-slate-200 bg-slate-50' : 'border-border-c/60 bg-bg-primary/60'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-2xs font-bold ${isLight ? 'text-slate-800' : 'text-text-primary'}`}>
                    فرصت تثبیت ستاپ جت:
                  </span>
                  <span className="text-xs font-black text-cyan-600 dark:text-neon-cyan font-mono">
                    {toFaDigits(params.jetStabilizationDays)} روز
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-1.5">
                  {[1, 3, 5].map((d) => (
                    <button
                      key={d}
                      type="button"
                      onClick={() => updateParam('jetStabilizationDays', d)}
                      className={`rounded-lg py-1 text-2xs font-bold transition-all ${
                        params.jetStabilizationDays === d
                          ? isLight
                            ? 'bg-cyan-100 border border-cyan-500 text-cyan-700'
                            : 'bg-neon-cyan/20 border border-neon-cyan text-neon-cyan'
                          : isLight
                            ? 'bg-white border border-slate-200 text-slate-600'
                            : 'bg-bg-primary border border-border-c/60 text-text-muted'
                      }`}
                    >
                      {toFaDigits(d)} روز {d === 3 ? '(جزوه)' : ''}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}