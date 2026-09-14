/* drawing_math.js — تبدیل از Verdant drawing_math.ts (نهایت‌نگر reverse-eng)
   Coordinate model: {time_t (unix s), price, offset} — pixel conversion در renderer */
/**
 * drawing_math.ts — Pure, zero-network re-implementations of the drawing-tool math
 * used by Nahayat Negar's chart engine (TradingView Charting Library semantics).
 *
 * Coordinate model (matches captured save JSON):
 *   point = { time_t, price, offset?: integer bar offset }
 * All geometry is computed in time/price space; pixel conversion is left to the renderer.
 */



var EPS = 1e-12;

/* ------------------------------------------------------------------ */
/* Price-scale math (linear vs log)                                    */
/* ------------------------------------------------------------------ */

/** TradingView log-scale coordinate formula (saved axis state: logFormula). */
function logY(price, min, max, height,
                     coordOffset = 1e-4, logicalOffset = 4) {
  var lo = Math.log(Math.max(min, EPS));
  var hi = Math.log(Math.max(max, EPS));
  var v = Math.log(Math.max(price, EPS));
  var t = (v - lo) / (hi - lo || 1);
  return (t * (height - logicalOffset)) + coordOffset;
}

/** Linear coordinate (normalized 0..1 → pixels). */
function linearY(price, min, max, height) {
  var t = (price - min) / ((max - min) || 1);
  return t * height;
}

/** Interpolate a price between two anchor prices. Used by Fib tools. */
function interpolate(p1, p2, coeff, logScale = false) {
  if (!logScale || p1 <= 0 || p2 <= 0) return p2 + (p1 - p2) * coeff;
  var l1 = Math.log(p1), l2 = Math.log(p2);
  return Math.exp(l2 + (l1 - l2) * coeff);
}

/* ------------------------------------------------------------------ */
/* Trend Line                                                          */
/* ------------------------------------------------------------------ */


function trendLine(a, b) {
  var dt = b.time_t - a.time_t;
  var k = dt === 0 ? 0 : (b.price - a.price) / dt;
  return { slopePerSec: k, yAt: (t) => a.price + k * (t - a.time_t) };
}

/* ------------------------------------------------------------------ */
/* Parallel Channel (3 points: start, end, width anchor)               */
/* ------------------------------------------------------------------ */


function parallelChannel(p0, p1, p2) {
  var base = trendLine(p0, p1);
  var delta = p2.price - base.yAt(p2.time_t); // vertical offset at P2
  var shift = (g, d) => ({
    slopePerSec: g.slopePerSec, yAt: (t) => g.yAt(t) + d,
  });
  var upper = shift(base, delta);
  var mid = shift(base, delta / 2);
  return { lower: base, upper, mid };
}

/* ------------------------------------------------------------------ */
/* Fibonacci Retracement (2 points) / Extension (3 points)             */
/* ------------------------------------------------------------------ */

var DEFAULT_FIB_LEVELS = [
  { coeff: 0,     color: '#787B86', visible: true },
  { coeff: 0.236, color: '#F23645', visible: false },
  { coeff: 0.382, color: '#81c784', visible: false },
  { coeff: 0.5,   color: '#4caf50', visible: false },
  { coeff: 0.618, color: '#089981', visible: true },
  { coeff: 0.786, color: '#64b5f6', visible: true },
  { coeff: 1,     color: '#787B86', visible: true },
  { coeff: 1.618, color: '#2962FF', visible: false },
  { coeff: 2.618, color: '#F23645', visible: false },
  { coeff: 3.618, color: '#9c27b0', visible: false },
];

/** Retracement level prices between swing P1 (start) → P2 (end). */
function fibRetracement(p1, p2,
                               levels = DEFAULT_FIB_LEVELS,
                               logScale = false) {
  return levels.map(l => ({ ...l, price: interpolate(p1.price, p2.price, l.coeff, logScale) }));
}

/** Trend-based extension: project swing A→B from anchor C. */
function fibExtension(a, b, c,
                             levels = DEFAULT_FIB_LEVELS,
                             logScale = false) {
  var ab = b.price - a.price;
  var logMode = logScale && a.price > 0 && b.price > 0 && c.price > 0;
  return levels.map(l => {
    if (!logMode) return { ...l, price: c.price + ab * l.coeff };
    var la = Math.log(a.price), lb = Math.log(b.price), lc = Math.log(c.price);
    return { ...l, price: Math.exp(lc + (lb - la) * l.coeff) };
  });
}

/* ------------------------------------------------------------------ */
/* Andrews Pitchfork (3 points: P pivot, R, S) + Schiff variants       */
/* ------------------------------------------------------------------ */


/**
 * Classic pitchfork: median starts at P and passes through the midpoint of R–S;
 * upper/lower parallels pass through R and S respectively.
 * v8.8-FIX-4c — تعریفِ دقیقِ هر واریانت (قبلاً schiff/schiff2 no-op بودند):
 *   schiff  : مبدا «فقط در قیمت» ۵۰٪ به سمت mid(R,S) می‌رود (زمان ثابت می‌ماند).
 *             شیفتِ محوری بی‌فایده بود؛ midpoint(P,midRS) روی خودِ خط میانه است،
 *             پس شیب تغییر نمی‌کرد و خروجی با classic یکی می‌شد.
 *   schiff2 : همان Schiff با ضریب ۲۵٪ (Modified Schiff).
 *   inside  : میانه از نقطهٔ دوم (R) به سمت mid(P,S) می‌رود؛ ریل‌ها از P و S می‌گذرند،
 *             پس میانه دقیقاً نصف‌النصفِ دو ریل است («داخل» مثلث P-R-S).
 */
function pitchfork(p, r, s,
                          variant = 'classic') {
  var midRS = {
    time_t: (r.time_t + s.time_t) / 2,
    price: (r.price + s.price) / 2,
  };
  var origin = p, anchor = midRS, railA = s, railB = r;
  if (variant === 'schiff') {
    origin = { time_t: p.time_t, price: p.price + (midRS.price - p.price) * 0.50 };
  } else if (variant === 'schiff2') {
    origin = { time_t: p.time_t, price: p.price + (midRS.price - p.price) * 0.25 };
  } else if (variant === 'inside') {
    origin = r;
    anchor = { time_t: (p.time_t + s.time_t) / 2, price: (p.price + s.price) / 2 };
    railA = s; railB = p;
  }
  var median = trendLine(origin, anchor);
  var shiftThrough = (pt) => ({
    slopePerSec: median.slopePerSec,
    yAt: (t) => median.yAt(t) + (pt.price - median.yAt(pt.time_t)),
  });
  return { median, upper: shiftThrough(railA), lower: shiftThrough(railB) };
}

/* ------------------------------------------------------------------ */
/* Rectangle / Price-Time Box                                          */
/* ------------------------------------------------------------------ */


function rectangle(a, b) {
  return {
    minTime: Math.min(a.time_t, b.time_t), maxTime: Math.max(a.time_t, b.time_t),
    minPrice: Math.min(a.price, b.price), maxPrice: Math.max(a.price, b.price),
  };
}

/* ------------------------------------------------------------------ */
/* Snapping helper (magnet mode)                                       */
/* ------------------------------------------------------------------ */


/** Magnet: snap a raw point to the nearest OHLC value of the candle under the cursor. */
function snapToCandle(t, price, candles, toleranceTime) {
  var best = null;
  var bestDt = Infinity;
  for (var c of candles) {
    // v8.8-FIX-7 — rvToKLine/klinecharts «timestamp» می‌دهد نه «time»؛ با c.time مقدار
    // undefined می‌شد و Math.abs(NaN) < Infinity همیشه false → هرگز snap نمی‌شد.
    var ct = (c.timestamp !== undefined) ? c.timestamp : c.time;
    if (ct === undefined) continue;
    var dt = Math.abs(ct - t);
    if (dt < bestDt) { bestDt = dt; best = c; }
  }
  if (!best || bestDt > toleranceTime) return { time_t: t, price };
  var ohlc = [best.open, best.high, best.low, best.close]
    .reduce((acc, v) => (Math.abs(v - price) < Math.abs(acc - price) ? v : acc));
  return { time_t: best.timestamp !== undefined ? best.timestamp : best.time, price: ohlc, offset: 0 };
}

window.DrawingMath = { logY, linearY, interpolate, trendLine, parallelChannel, fibRetracement, fibExtension, pitchfork, rectangle, snapToCandle, DEFAULT_FIB_LEVELS };
