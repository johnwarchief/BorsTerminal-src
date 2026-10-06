// features/master/lib/strategyGraphLayouts.ts
// موتورهای چیدمان هندسی نقشه راه FTS (Roadmap Flowchart & Concentric Orbit Layout Engines)
// محاسبه قطعی مختصات در دو نمای نقشه راه (Roadmap) و مداری (Orbit) منطبق بر چارت ۴ صفحه‌ای:
// [S: انتخاب و تابلو] -> [T: تکنیکال] -> [F: بنیادی] -> [Delivery: تحویل] -> [Capital: سرمایه و استراتژی]

import type { CanonicalStrategyGraph, StrategyGraphNode, StrategyStageKey } from './strategyGraphModel';

export interface LayoutedNode {
  id: string;
  x: number;
  y: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
  radius?: number;
  angleDeg?: number;
  depth: number;
  data: StrategyGraphNode;
}

export interface LayoutedEdge {
  id: string;
  sourceId: string;
  targetId: string;
  d: string;
  isActive: boolean;
  status: StrategyGraphNode['status'];
}

export interface GraphLayoutResult {
  nodes: LayoutedNode[];
  nodeMap: Map<string, LayoutedNode>;
  edges: LayoutedEdge[];
  bounds: {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
    width: number;
    height: number;
  };
}

/**
 * ۱. موتور چیدمان نقشه راه (Roadmap Flowchart Engine)
 * جریان متوالی مراحل FTS به ترتیب چارت ۴ صفحه‌ای از راست به چپ (RTL):
 * [S: تابلوخوانی ص ۳] ➔ [T: تکنیکال ص ۲] ➔ [F: بنیادی ص ۱] ➔ [تحویل نهایی] ➔ [مدیریت سرمایه و استراتژی ص ۴]
 */
export function computeFlowLayout(graph: CanonicalStrategyGraph): GraphLayoutResult {
  const nodes: LayoutedNode[] = [];
  const nodeMap = new Map<string, LayoutedNode>();

  const COL_WIDTH = 250;
  const COL_GAP = 60;
  const NODE_HEIGHT = 76;
  const ROOT_HEIGHT = 68;
  const NODE_GAP_Y = 16;
  const PAD_X = 50;
  const PAD_Y = 40;

  // ترتیب ستون‌ها در RTL: ستون ۰ راست‌ترین، ستون ۴ چپ‌ترین
  const STAGE_ORDER: StrategyStageKey[] = ['selection', 'technical', 'fundamental', 'delivery', 'capital'];

  // دسته‌بندی گره‌ها بر حسب مرحله
  const stageNodes: Record<StrategyStageKey, StrategyGraphNode[]> = {
    selection: [],
    technical: [],
    fundamental: [],
    delivery: [],
    capital: [],
  };

  for (const n of graph.nodes) {
    if (n.type === 'root') continue;
    if (n.stage in stageNodes) {
      stageNodes[n.stage].push(n);
    }
  }

  // مرتب‌سازی داخل هر ستون: هدر استیج اول، سپس شاخه‌ها و شروط
  for (const key of STAGE_ORDER) {
    stageNodes[key].sort((a, b) => {
      if (a.type === 'stage') return -1;
      if (b.type === 'stage') return 1;
      return a.depth - b.depth;
    });
  }

  // محاسبه ابعاد کلی
  const totalStagesW = STAGE_ORDER.length * (COL_WIDTH + COL_GAP) - COL_GAP;
  const rootNode = graph.nodeMap.get(graph.rootId);
  const rootY = PAD_Y;
  const rootW = 340;
  const rootX = PAD_X + (totalStagesW - rootW) / 2;

  if (rootNode) {
    const lNode: LayoutedNode = {
      id: rootNode.id,
      x: rootX,
      y: rootY,
      width: rootW,
      height: ROOT_HEIGHT,
      centerX: rootX + rootW / 2,
      centerY: rootY + ROOT_HEIGHT / 2,
      depth: 0,
      data: rootNode,
    };
    nodes.push(lNode);
    nodeMap.set(lNode.id, lNode);
  }

  // محاسبه موقعیت ستون‌ها در چیدمان RTL
  // ستون ۰ (انتخاب/تابلو) در سمت راست‌ترین موقعیت قرار می‌گیرد
  const startStagesY = rootY + ROOT_HEIGHT + 45;

  STAGE_ORDER.forEach((stageKey, colIdx) => {
    // محاسبه موقعیت X از راست به چپ
    // colIdx = 0 (selection) => x = totalStagesW - (0+1)*COL_WIDTH ...
    const stageX = PAD_X + (STAGE_ORDER.length - 1 - colIdx) * (COL_WIDTH + COL_GAP);

    let currentY = startStagesY;
    const items = stageNodes[stageKey];

    items.forEach((item) => {
      const h = item.type === 'stage' ? 84 : NODE_HEIGHT;
      const lNode: LayoutedNode = {
        id: item.id,
        x: stageX,
        y: currentY,
        width: COL_WIDTH,
        height: h,
        centerX: stageX + COL_WIDTH / 2,
        centerY: currentY + h / 2,
        depth: item.depth,
        data: item,
      };
      nodes.push(lNode);
      nodeMap.set(lNode.id, lNode);

      currentY += h + NODE_GAP_Y;
    });
  });

  // محاسبه یال‌ها و اتصالات
  const edges: LayoutedEdge[] = [];

  for (const edge of graph.edges) {
    const sourceNode = nodeMap.get(edge.source);
    const targetNode = nodeMap.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    let pathD = '';
    const isActive = graph.activePathEdgeIds.has(edge.id);

    // ۱. اتصال از ریشه به هدر مراحل
    if (sourceNode.data.type === 'root') {
      const startX = sourceNode.centerX;
      const startY = sourceNode.y + sourceNode.height;
      const endX = targetNode.centerX;
      const endY = targetNode.y;
      const midY = (startY + endY) / 2;
      pathD = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;
    }
    // ۲. اتصال بین مراحل اصلی نقشه راه (S -> T -> F -> Delivery -> Capital)
    else if (edge.type === 'active_flow') {
      // در RTL جریان از راست به چپ است: خروجی از لبه سمت چپ گره راست به لبه سمت راست گره بعدی
      const startX = sourceNode.x; // لبه چپ گره مبدا
      const startY = sourceNode.centerY;
      const endX = targetNode.x + targetNode.width; // لبه راست گره مقصد
      const endY = targetNode.centerY;
      const midX = (startX + endX) / 2;
      pathD = `M ${startX} ${startY} C ${midX} ${startY}, ${midX} ${endY}, ${endX} ${endY}`;
    }
    // ۳. اتصال‌های سلسله‌مراتبی عمودی درون هر ستون
    else {
      const startX = sourceNode.centerX;
      const startY = sourceNode.y + sourceNode.height;
      const endX = targetNode.centerX;
      const endY = targetNode.y;
      const midY = (startY + endY) / 2;
      pathD = `M ${startX} ${startY} C ${startX} ${midY}, ${endX} ${midY}, ${endX} ${endY}`;
    }

    edges.push({
      id: edge.id,
      sourceId: edge.source,
      targetId: edge.target,
      d: pathD,
      isActive,
      status: targetNode.data.status,
    });
  }

  // محاسبه محدوده نهایی بوم (Bounds)
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const n of nodes) {
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x + n.width > maxX) maxX = n.x + n.width;
    if (n.y + n.height > maxY) maxY = n.y + n.height;
  }

  minX -= PAD_X;
  minY -= PAD_Y;
  maxX += PAD_X;
  maxY += PAD_Y;

  return {
    nodes,
    nodeMap,
    edges,
    bounds: {
      minX,
      minY,
      maxX,
      maxY,
      width: Math.max(800, maxX - minX),
      height: Math.max(600, maxY - minY),
    },
  };
}

/**
 * ۲. موتور چیدمان مداری (Concentric Radial / Orbit Engine)
 * نمایش دقیق همین گراف کانونی FTS در حلقه‌های مداری متحدالمرکز بر پایه مختصات قطبی:
 * - مدار ۰ (مرکز): هسته و سبک FTS
 * - مدار ۱ (شعاع ۱۹۰px): ۵ مرحله اصلی (تابلو S، تکنیکال T، بنیادی F، تحویل، سرمایه)
 * - مدار ۲ (شعاع ۳۸۰px): شاخه‌های اصلی هر مرحله
 * - مدار ۳ (شعاع ۵۵۰px): شروط، الگوها و قوانین جزئی
 */
export function computeOrbitLayout(graph: CanonicalStrategyGraph): GraphLayoutResult {
  const nodes: LayoutedNode[] = [];
  const nodeMap = new Map<string, LayoutedNode>();

  const CENTER_X = 700;
  const CENTER_Y = 600;

  const R1 = 195;
  const R2 = 385;
  const R3 = 560;

  // ۱. نود مرکزی در مدار صفر
  const rootNode = graph.nodeMap.get(graph.rootId);
  if (rootNode) {
    const rootW = 170;
    const rootH = 76;
    const lNode: LayoutedNode = {
      id: rootNode.id,
      x: CENTER_X - rootW / 2,
      y: CENTER_Y - rootH / 2,
      width: rootW,
      height: rootH,
      centerX: CENTER_X,
      centerY: CENTER_Y,
      radius: 0,
      angleDeg: 0,
      depth: 0,
      data: rootNode,
    };
    nodes.push(lNode);
    nodeMap.set(lNode.id, lNode);
  }

  // زوایای ۵ مرحله اصلی بر اساس جهت ساعتگرد فارسی / RTL
  const STAGE_ANGLES: Record<StrategyStageKey, number> = {
    selection: 30, // بالا-راست (شروع)
    technical: 105, // پایین-راست
    fundamental: 180, // پایین
    delivery: 255, // پایین-چپ
    capital: 325, // بالا-چپ (پایان)
  };

  const STAGE_ORDER: StrategyStageKey[] = ['selection', 'technical', 'fundamental', 'delivery', 'capital'];

  for (const stageKey of STAGE_ORDER) {
    const stageRootId = graph.stageRoots[stageKey];
    const stageNode = graph.nodeMap.get(stageRootId);
    if (!stageNode) continue;

    const baseAngle = STAGE_ANGLES[stageKey];
    const rad = (baseAngle * Math.PI) / 180;
    const stageCx = CENTER_X + R1 * Math.cos(rad);
    const stageCy = CENTER_Y + R1 * Math.sin(rad);

    const w = 150;
    const h = 64;

    const lNode: LayoutedNode = {
      id: stageNode.id,
      x: stageCx - w / 2,
      y: stageCy - h / 2,
      width: w,
      height: h,
      centerX: stageCx,
      centerY: stageCy,
      radius: R1,
      angleDeg: baseAngle,
      depth: 1,
      data: stageNode,
    };
    nodes.push(lNode);
    nodeMap.set(lNode.id, lNode);

    // توزیع فرزندان این مرحله در مدار ۲ و مدار ۳
    const children = stageNode.childrenIds
      .map((cid) => graph.nodeMap.get(cid))
      .filter((c): c is StrategyGraphNode => !!c && c.type !== 'stage');
    const childCount = children.length;

    if (childCount > 0) {
      const spanAngle = 55;
      const angleStep = childCount > 1 ? spanAngle / (childCount - 1) : 0;
      const startAngle = baseAngle - spanAngle / 2;

      children.forEach((child, idx) => {
        if (nodeMap.has(child.id)) return;
        const cAngle = startAngle + idx * angleStep;
        const cRad = (cAngle * Math.PI) / 180;
        const childCx = CENTER_X + R2 * Math.cos(cRad);
        const childCy = CENTER_Y + R2 * Math.sin(cRad);

        const cw = 145;
        const ch = 60;

        const cNode: LayoutedNode = {
          id: child.id,
          x: childCx - cw / 2,
          y: childCy - ch / 2,
          width: cw,
          height: ch,
          centerX: childCx,
          centerY: childCy,
          radius: R2,
          angleDeg: cAngle,
          depth: 2,
          data: child,
        };
        nodes.push(cNode);
        nodeMap.set(cNode.id, cNode);

        // فرزندان عمق ۳ در مدار ۳
        const grandChildren = child.childrenIds
          .map((gcid) => graph.nodeMap.get(gcid))
          .filter((gc): gc is StrategyGraphNode => !!gc && gc.type !== 'stage');

        if (grandChildren.length > 0) {
          const gcSpan = 22;
          const gcStep = grandChildren.length > 1 ? gcSpan / (grandChildren.length - 1) : 0;
          const gcStart = cAngle - gcSpan / 2;

          grandChildren.forEach((gc, gIdx) => {
            if (nodeMap.has(gc.id)) return;
            const gcAngle = gcStart + gIdx * gcStep;
            const gcRad = (gcAngle * Math.PI) / 180;
            const gcCx = CENTER_X + R3 * Math.cos(gcRad);
            const gcCy = CENTER_Y + R3 * Math.sin(gcRad);

            const gcw = 135;
            const gch = 54;

            const gcNode: LayoutedNode = {
              id: gc.id,
              x: gcCx - gcw / 2,
              y: gcCy - gch / 2,
              width: gcw,
              height: gch,
              centerX: gcCx,
              centerY: gcCy,
              radius: R3,
              angleDeg: gcAngle,
              depth: 3,
              data: gc,
            };
            nodes.push(gcNode);
            nodeMap.set(gcNode.id, gcNode);
          });
        }
      });
    }
  }

  // محاسبه یال‌های مداری
  const edges: LayoutedEdge[] = [];

  for (const edge of graph.edges) {
    const sourceNode = nodeMap.get(edge.source);
    const targetNode = nodeMap.get(edge.target);
    if (!sourceNode || !targetNode) continue;

    const isActive = graph.activePathEdgeIds.has(edge.id);

    // خط مستقیم یا منحنی نرم بین مرکز گره‌ها در مدار
    const startX = sourceNode.centerX;
    const startY = sourceNode.centerY;
    const endX = targetNode.centerX;
    const endY = targetNode.centerY;

    const midX = (startX + endX) / 2;
    const midY = (startY + endY) / 2;

    const pathD = `M ${startX} ${startY} Q ${midX} ${midY} ${endX} ${endY}`;

    edges.push({
      id: edge.id,
      sourceId: edge.source,
      targetId: edge.target,
      d: pathD,
      isActive,
      status: targetNode.data.status,
    });
  }

  // محاسبه محدوده بوم مداری
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;

  for (const n of nodes) {
    if (n.x < minX) minX = n.x;
    if (n.y < minY) minY = n.y;
    if (n.x + n.width > maxX) maxX = n.x + n.width;
    if (n.y + n.height > maxY) maxY = n.y + n.height;
  }

  minX -= 50;
  minY -= 50;
  maxX += 50;
  maxY += 50;

  return {
    nodes,
    nodeMap,
    edges,
    bounds: {
      minX,
      minY,
      maxX,
      maxY,
      width: Math.max(900, maxX - minX),
      height: Math.max(900, maxY - minY),
    },
  };
}
