// features/market/lib/treemapLayout.ts -- چیدمانِ squarified treemap (خالص، آزمون‌پذیر)
//
// چرا الگوریتم و نه یک شبکهٔ ساده: در مرجع، سطحِ هر مستطیل از «معیار» می‌آید
// (ارزش معاملات، حجم، ارزش بازار، تعداد). شبکهٔ هم‌اندازه آن نسبت را دروغ
// می‌گوید و ستون‌به‌ستونِ عمودی هم برایِ مقادیرِ پراکنده (یک نماد ۳۰٪ بازار،
// بعدی ۰٫۲٪) نسبتِ ظاهریِ فاجعه می‌سازد. squarified (Bruls/Hijikama/Wijk)
// مربع‌مانندترین تقسیمِ ممکن را می‌دهد و متنِ داخلِ خانه خوانا می‌ماند.
//
// سه چیزِ عمدی:
// · ورودیِ بی‌قدر (size ≤ 0 یا NaN) حذف می‌شود، نه صفر — خانهٔ صفر هیچ پیکسلی
//   ندارد و کاربر فکر می‌کند نماد حذف شده؛ شمارششان در `dropped` می‌آید تا
//   پنل بگوید «N نمادِ بی‌معامله در این چیدمان نیست».
// · خروجی بر حسبِ ۰..۱ نرمال است؛ تبدیل به پیکسل کارِ کامپوننت است تا تست به
//   اندازهٔ صفحه وابسته نماند و resize همان داده را دوباره بچیند.
// · مساحتِ هر خانه = مقدار ÷ جمعِ مقادیر، **دقیق**. اگر این شکست، نقشه همان
//   دروغی را می‌گوید که کل پنل برایِ فرارِ از آن ساخته شده — و screenshot هیچ
//   تستِ مرورگری‌ای آن را نمی‌گیرد. لذا درِ spec دو شاهدِ مستقل دارد: جمعِ
//   مساحت = ۱ و همپوشانی = صفر.
//
// نگاشتِ مختصات: چپ‌به‌راست درِ SVG. جهتِ *خواندن* صفحه rtl است ولی صفحهٔ
// نقشه یک بومِ هندسی است؛ آینه‌کردنش نسبت‌ها را عوض نمی‌کند فقط بصریِ آشنا را
// می‌شکند. برچسب‌ها هر دو جهت را نگه می‌دارند.

export type TreemapItem = { key: string; value: number };
export type TreemapRect = { key: string; x: number; y: number; w: number; h: number };

/** بدترین نسبتِ aspect در یک ردیف: هرچه کوچک‌تر، خانه‌ها مربعی‌تر */
function worstOf(areas: number[], side: number): number {
  let sum = 0;
  let min = Infinity;
  let max = 0;
  for (const a of areas) {
    if (a <= 0) continue;
    sum += a;
    if (a < min) min = a;
    if (a > max) max = a;
  }
  if (sum <= 0 || min <= 0 || side <= 0) return Infinity;
  const s2 = sum * sum;
  const side2 = side * side;
  return Math.max((side2 * max) / s2, s2 / (side2 * min));
}

/**
 * چیدمانِ squarified روی مستطیلِ [0,1]×[0,1].
 * `items` اگر نزولی نبود اینجا مرتب می‌شود: ترتیبِ ورودی حقِ کاربر نسبت به
 * ظاهرِ نقشه نیست و الگوریتم به نزولی بودن حساس است.
 */
export function squarify(items: TreemapItem[]): { rects: TreemapRect[]; dropped: number } {
  const raw = items ?? [];
  const usable = raw.filter(
    (i) => typeof i.value === 'number' && Number.isFinite(i.value) && i.value > 0 && i.key,
  );
  const dropped = raw.length - usable.length;
  if (!usable.length) return { rects: [], dropped };

  const total = usable.reduce((a, i) => a + i.value, 0);
  if (!(total > 0)) return { rects: [], dropped: raw.length };

  // مساحت‌ها رویِ مربعِ واحد: Σ areas = ۱، پس هر خانه دقیقاً سهمش را می‌گیرد.
  const cells = [...usable]
    .sort((a, b) => b.value - a.value)
    .map((i) => ({ key: i.key, area: i.value / total }));

  const rects: TreemapRect[] = [];
  let x = 0;
  let y = 0;
  let w = 1;
  let h = 1;
  let i = 0;

  while (i < cells.length) {
    const shorter = Math.min(w, h);
    // ردیف را تا جایی که «بدترین aspect» بهتر می‌شود جلو می‌بریم.
    const rowAreas = [cells[i].area];
    let rowSum = cells[i].area;
    let currentWorst = worstOf(rowAreas, shorter);
    let j = i + 1;
    while (j < cells.length) {
      const nextSum = rowSum + cells[j].area;
      const nextWorst = worstOf([...rowAreas, cells[j].area], shorter);
      if (nextWorst <= currentWorst) {
        rowAreas.push(cells[j].area);
        rowSum = nextSum;
        currentWorst = nextWorst;
        j++;
      } else break;
    }

    // ضخامتِ نوار = مساحتِ ردیف ÷ ضلعِ موازی‌اش؛ ارتفاعِ هر خانه = مساحت ÷ ضخامت.
    const thickness = Math.min(rowSum / shorter, w > 0 && h > 0 ? (w >= h ? w : h) : 1);
    if (w >= h) {
      let cy = y;
      for (let k = i; k < j; k++) {
        const cellH = thickness > 0 ? cells[k].area / thickness : 0;
        rects.push({ key: cells[k].key, x, y: cy, w: thickness, h: cellH });
        cy += cellH;
      }
      x += thickness;
      w = Math.max(0, 1 - x);
    } else {
      let cx = x;
      for (let k = i; k < j; k++) {
        const cellW = thickness > 0 ? cells[k].area / thickness : 0;
        rects.push({ key: cells[k].key, x: cx, y, w: cellW, h: thickness });
        cx += cellW;
      }
      y += thickness;
      h = Math.max(0, 1 - y);
    }
    i = j;
  }
  return { rects: rects.map(clip01), dropped };
}

function clip01(r: TreemapRect): TreemapRect {
  const bound = (v: number) => Math.min(1, Math.max(0, v));
  const x = bound(r.x);
  const y = bound(r.y);
  return { key: r.key, x, y, w: bound(r.x + r.w) - x, h: bound(r.y + r.h) - y };
}

/** کوچک‌ترین خانه‌ای که هنوز متنِ خوانا جا می‌گیرد (پیکسل) — زیرِ آن فقط رنگ می‌ماند */
export const TREEMAP_LABEL_MIN_W = 34;
export const TREEMAP_LABEL_MIN_H = 20;
