/* =====================================================================
   BorsTerminal TechV2 — v8.4 «آیکون‌های واقعی نهایت‌نگر + پاریتی کامل نوار ابزار»
   ---------------------------------------------------------------------
   - v8.4: iconSvg اول از NN_ICONS (استخراج زنده DOM نهایت‌نگر — static/vendor/nn_icons/)
     بعد RTV_ICONS (پکیج رسمی klinecharts) و در نهایت آیکون دست‌ساز استفاده می‌کند
   - ۸ گروه ابزار با ترتیب و نام فارسی دقیقاً مطابق فلایاوت‌های نهایت‌نگر:
     1) Cursors (۴)  2) Trend Lines (۱۴)  3) Gann & Fibonacci (۱۹)
     4) Geometric Shapes (۱۲)  5) Annotation (۱۵)  6) Patterns (۱۴)
     7) Prediction & Measurement (۱۰)  8) Font Icons
   - ~۳۵ overlay سفارشی (registerOverlay) برای ابزارهای غایب
   - فلایاوت با hover (مثل نهایت‌نگر) + کلیک برای پین
   - منوی اندیکاتورها به سبک نهایت‌نگر (دیالوگ + جستجو + لیست تخت)
   - پاک‌کن (eraser)، ماندن در حالت رسم، اندازه‌گیری در هدر
   ===================================================================== */
(function () {
  'use strict';

  /* ============ 1) آیکون‌ها (SVG خطی 24×24 — stroke=currentColor) ============ */
  var IC = {
    cursor: '<path d="M6 3l12 7-5.5 1.5L10 18z" stroke-linejoin="round"/>',
    dot: '<circle cx="12" cy="12" r="2.2" fill="currentColor" stroke="none"/>',
    eraser: '<path d="M8 18L4.5 14.5a1.5 1.5 0 010-2.1l7.9-7.9a1.5 1.5 0 012.1 0l4 4a1.5 1.5 0 010 2.1L12 17H8z" stroke-linejoin="round"/><path d="M5 20h14"/>',
    trend: '<circle cx="6" cy="17" r="1.6" fill="currentColor" stroke="none"/><circle cx="18" cy="6" r="1.6" fill="currentColor" stroke="none"/><path d="M7.5 15.5L16.5 7.5"/>',
    arrowTool: '<path d="M5 19L17 7M17 7h-6M17 7v6" stroke-linejoin="round"/>',
    ray: '<circle cx="6" cy="17" r="1.6" fill="currentColor" stroke="none"/><path d="M8 15.5L20 4"/>',
    infoLine: '<circle cx="5" cy="18" r="1.6" fill="currentColor" stroke="none"/><circle cx="19" cy="5" r="1.6" fill="currentColor" stroke="none"/><path d="M6.5 16.5L17.5 6.5"/><path d="M4 13h6M14 10h6" stroke-dasharray="2 2"/>',
    extended: '<path d="M2 12h20"/><circle cx="6" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="18" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
    trendAngle: '<path d="M4 18L20 6"/><path d="M4 18a14 14 0 0114-12" stroke-dasharray="2 2" opacity=".5"/>',
    horzLine: '<path d="M3 12h18"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
    horzRay: '<circle cx="6" cy="12" r="1.5" fill="currentColor" stroke="none"/><path d="M8 12h13"/>',
    vertLine: '<path d="M12 3v18"/><circle cx="12" cy="12" r="1.5" fill="currentColor" stroke="none"/>',
    crossLine: '<path d="M3 12h18M12 3v18" opacity=".9"/>',
    channel: '<path d="M4 18L18 4M7 20L21 6"/>',
    regression: '<path d="M4 15L18 5M5 18L19 8M3 12L17 2" opacity=".95"/>',
    flatBottom: '<path d="M4 14l10-8M4 19h14" /><circle cx="18" cy="19" r="1.4" fill="currentColor" stroke="none"/>',
    disjoint: '<path d="M4 17L14 5M8 20L20 10"/>',
    fibRetrace: '<path d="M5 5h14M5 9h10M5 13h14M5 17h10M5 21h14"/>',
    fibExt: '<path d="M5 5h14M5 9h10M5 13h14M5 17h10M5 21h14"/><path d="M17 13h5m0 0l-2-2m2 2l-2 2"/>',
    pitchfork: '<path d="M4 20L12 6m0 0l-5-1.5M12 6l5-1.5M7 4.5L7 18m10-13.5V18"/>',
    schiff: '<path d="M6 20L12 7m0 0l-4-2M12 7l4-2M8 5V18m8-13V18"/>',
    fibChannel: '<path d="M4 20L20 4M4 15l10 0M4 10l14 0M4 5h18" opacity=".95"/>',
    fibTime: '<path d="M4 4v16M9 4v16M13 4v16M16 4v16M20 4v16" opacity=".95"/>',
    gannBox: '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 19L20 5"/>',
    gannFixed: '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 12h16M12 5v14"/>',
    gannComplex: '<rect x="4" y="5" width="16" height="14" rx="1"/><path d="M4 19L20 5M4 5l16 14M4 12h16M12 5v14"/>',
    gannFan: '<path d="M5 19L19 3M5 19l14-8M5 19l14-3M5 19l14 2M5 19L3 5M5 19l8-16"/>',
    fibFan: '<path d="M5 19L20 9M5 19l15-5M5 19l15-2M5 19l15 2"/>',
    fibCircles: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="5" opacity=".7"/><circle cx="12" cy="12" r="2.5" opacity=".5"/>',
    pitchfan: '<path d="M5 19L20 11M5 19l14-3M5 19l13-7M5 19l11-11"/>',
    spiral: '<path d="M12 12c0-1.5 2-1.5 2 0s-2 3-4 2-2.5-4.5 0-6 6-.5 6.5 3-2 6.5-6.5 6-8-4-7.5-9"/>',
    fibArcs: '<path d="M4 18a14 14 0 0114-13" /><path d="M8 18a10 10 0 0110-9" opacity=".7"/><path d="M12 18a6 6 0 016-5" opacity=".5"/>',
    fibWedge: '<path d="M4 19L12 4l8 15z"/><path d="M7 13h10" stroke-dasharray="2 2" opacity=".7"/>',
    brush: '<path d="M4 20c3 0 3-3 5-5l8-9 2 2-8 9c-2 2-5 2-7 3z" stroke-linejoin="round"/>',
    highlighter: '<path d="M6 16L14 5l4 3-8 11-5 1z" stroke-linejoin="round" stroke-width="2.4" opacity=".85"/>',
    rect: '<rect x="4" y="6" width="16" height="12" rx="1"/>',
    circleTool: '<circle cx="12" cy="12" r="8"/>',
    ellipseTool: '<ellipse cx="12" cy="12" rx="9" ry="5.5"/>',
    pathTool: '<path d="M4 18c2-6 5 2 8-4s5 2 8-4" stroke-linejoin="round"/>',
    bezierQ: '<path d="M4 18Q12 2 20 14" stroke-linejoin="round"/>',
    polyline: '<path d="M4 18l4-8 4 4 4-8 4 6" stroke-linejoin="round"/>',
    triangleTool: '<path d="M12 4l8 15H4z" stroke-linejoin="round"/>',
    rotatedRect: '<path d="M7 4l13 5-3 8L4 12z" stroke-linejoin="round"/>',
    arcTool: '<path d="M4 18a12 12 0 0116 0"/><path d="M4 18h16" stroke-dasharray="2 2" opacity=".4"/>',
    bezierC: '<path d="M4 18C8 4 16 4 20 14" stroke-linejoin="round"/>',
    textTool: '<path d="M5 5h14M12 5v14M9 19h6"/>',
    noteTool: '<path d="M5 4h14v10l-5 6H5z" stroke-linejoin="round"/><path d="M14 20v-6h5"/>',
    signpost: '<path d="M12 3v18"/><path d="M7 6h10l3 3-3 3H7z" stroke-linejoin="round"/>',
    callout: '<path d="M4 5h16v10H10l-4 5v-5H4z" stroke-linejoin="round"/>',
    balloon: '<path d="M12 3a6 6 0 016 6c0 4-4 7-6 7s-6-3-6-7a6 6 0 016-6z"/><path d="M12 16v4"/>',
    priceLabel: '<path d="M4 9h12l4 3-4 3H4z" stroke-linejoin="round"/>',
    arrowMarkUp: '<path d="M12 19V6M6 12l6-6 6 6" stroke-linejoin="round"/>',
    arrowMarkDown: '<path d="M12 5v13M6 12l6 6 6-6" stroke-linejoin="round"/>',
    arrowMarkLeft: '<path d="M19 12H6M12 6l-6 6 6 6" stroke-linejoin="round"/>',
    arrowMarkRight: '<path d="M5 12h13M12 6l6 6-6 6" stroke-linejoin="round"/>',
    flagMark: '<path d="M6 21V4"/><path d="M6 4h12l-3 4 3 4H6" stroke-linejoin="round"/>',
    patternAbcd: '<path d="M4 19l4-12 4 8 4-10 4 14" stroke-linejoin="round"/>',
    patternXabcd: '<path d="M3 19l4-13 4 9 4-11 4 15" stroke-linejoin="round"/>',
    patternCypher: '<path d="M4 18L9 6l5 8 6-10" stroke-linejoin="round"/>',
    patternTriangle: '<path d="M4 18l3-9 3 5 3-7 3 9 4-11" stroke-linejoin="round"/>',
    pattern3drives: '<path d="M3 19l3-8 3 5 3-9 3 6 3-11" stroke-linejoin="round"/>',
    patternHns: '<path d="M3 17l4-6 4 8 4-12 4 10" stroke-linejoin="round"/>',
    elliottImpulse: '<path d="M3 19l3-4 3 3 3-8 3 5 3-11" stroke-linejoin="round"/>',
    elliottTriangle: '<path d="M3 18l4-7 3 4 4-8 4 6 4-4" stroke-linejoin="round"/>',
    elliottTriple: '<path d="M3 18l3-6 3 3 3-7 3 4 4-8" stroke-linejoin="round"/>',
    elliottCorrection: '<path d="M3 16l4-8 3 6 4-10 3 12" stroke-linejoin="round"/>',
    elliottDouble: '<path d="M3 18l4-9 3 5 4-9 3 7" stroke-linejoin="round"/>',
    circleLines: '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="4.5" opacity=".6"/>',
    timeCycles: '<path d="M6 4v16M12 4v16M18 4v16" /><path d="M3 12h18" opacity=".35"/>',
    sineLine: '<path d="M3 12c2-6 4-6 6 0s4 6 6 0 4-6 6 0" stroke-linejoin="round"/>',
    rrLong: '<path d="M4 6h16v12H4z" opacity=".4"/><path d="M4 12h16"/><path d="M4 8.5h16" stroke="#089981"/><path d="M4 15.5h16" stroke="#F23645"/>',
    rrShort: '<path d="M4 6h16v12H4z" opacity=".4"/><path d="M4 12h16"/><path d="M4 8.5h16" stroke="#F23645"/><path d="M4 15.5h16" stroke="#089981"/>',
    predictionTool: '<path d="M4 19l6-6 4 3 6-9" stroke-dasharray="4 3" stroke-linejoin="round"/><path d="M20 7h-5m5 0v5"/>',
    dateRange: '<path d="M6 4v16M18 4v16"/><rect x="6" y="6" width="12" height="12" opacity=".25" fill="currentColor" stroke="none"/>',
    priceRange: '<path d="M4 6h16M4 18h16"/><rect x="6" y="6" width="12" height="12" opacity=".25" fill="currentColor" stroke="none"/>',
    datePriceRange: '<rect x="4" y="6" width="16" height="12" rx="1"/><path d="M7 12h10M12 9v6" opacity=".6"/>',
    barsPattern: '<path d="M6 6v12M10 9v9M14 5v13M18 8v10" stroke-linecap="round"/>',
    ghostFeed: '<rect x="4" y="6" width="16" height="12" rx="3" stroke-dasharray="3 3"/><path d="M8 12h8" stroke-dasharray="3 3"/>',
    projectionTool: '<path d="M4 18l5-5 4 2 5-7" stroke-linejoin="round"/><path d="M18 8l2 2m-2-2l-2 2" opacity=".7"/>',
    volumeProfile: '<path d="M6 5v14M10 7v10M14 4v16M18 9v6" stroke-linecap="round" opacity=".9"/>',
    measureTool: '<path d="M4 17L17 4l3 3L7 20z" stroke-linejoin="round"/><path d="M9 12l2 2M12 9l2 2M15 6l2 2"/>',
    groupIcon: ''
  };
  function iconSvg(name, size) {
    /* v8.4: اولویت آیکون واقعی نهایت‌نگر (28×28 از DOM سایت) → پکیج رسمی klinecharts → آیکون دست‌ساز */
    var nn = (typeof window.NN_ICONS !== 'undefined') && window.NN_ICONS[name];
    if (nn) return nn;
    var rtv = (typeof window.RTV_ICONS !== 'undefined') && window.RTV_ICONS[name];
    if (rtv) return rtv;
    return '<svg viewBox="0 0 24 24" width="' + (size || 16) + '" height="' + (size || 16) + '" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">' + (IC[name] || IC.trend) + '</svg>';
  }

  /* ============ 2) helpers مشترک برای overlayهای سفارشی ============ */
  function coords(e) { return e.coordinates || []; }
  function ovPts(e) { return (e.overlay && e.overlay.points) || []; }
  var TXT = { style: 'fill', size: 10, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' };
  var BLUE = '#2962ff', GRAY = '#787B86', GREEN = '#089981', RED = '#F23645', ORANGE = '#f59e0b';
  var BIG = 200000; // مختصات خیلی دور → خط نامحدود روی canvas (clip میشود)
  function line(a, b, st) { return { type: 'line', attrs: { coordinates: [a, b] }, styles: st || { color: BLUE, size: 1, style: 'solid' } }; }
  function dash(a, b, c) { return line(a, b, { color: (c || GRAY), size: 1, style: 'dashed', dashedValue: [4, 3] }); }
  function txt(x, y, t, color, size, align) {
    return { type: 'text', attrs: { x: x, y: y, text: String(t), align: align || 'left', baseline: 'bottom' }, styles: Object.assign({}, TXT, { color: color || GRAY, size: size || 10 }) };
  }
  function poly(points, st) { return { type: 'polygon', attrs: { points: points }, styles: st || { style: 'stroke', color: 'rgba(41,98,255,0.10)', borderColor: BLUE, borderSize: 1 } }; }

  /* ============ 3) رجیستر overlayهای سفارشی ============ */
  function reg(def) { try { window.klinecharts.registerOverlay(def); } catch (e) { console.warn('[rtv-tools] ' + def.name, e); } }

  function installOverlays() {
    if (!window.klinecharts) return;

    /* --- خط افقی/عمودی همزمان (Cross Line) --- */
    reg({ name: 'cross-line', totalStep: 2, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (!c.length) return [];
      var p = c[0];
      return [line({ x: p.x, y: p.y }, { x: BIG, y: p.y }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 4] }),
              line({ x: p.x, y: p.y }, { x: p.x, y: BIG }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 4] })];
    }});

    /* --- خط روند با جزئیات (Info Line): قیمت دو سر --- */
    reg({ name: 'info-line', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e), p = ovPts(e); if (c.length < 2 || p.length < 2) return [];
      var figs = [line(c[0], c[1]), { type: 'circle', attrs: { x: c[0].x, y: c[0].y, r: 3, r2: 3 }, styles: { style: 'fill', color: BLUE } },
                  { type: 'circle', attrs: { x: c[1].x, y: c[1].y, r: 3, r2: 3 }, styles: { style: 'fill', color: BLUE } }];
      figs.push(txt(c[0].x + 5, c[0].y - 4, p[0].value.toFixed(2), BLUE));
      figs.push(txt(c[1].x + 5, c[1].y - 4, p[1].value.toFixed(2), BLUE));
      return figs;
    }});

    /* --- روند رگرسیون (ساده: خط + دو کانال موازی) --- */
    reg({ name: 'regression-trend', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var dx = b.x - a.x, dy = b.y - a.y, L = Math.hypot(dx, dy) || 1;
      var nx = -dy / L * 26, ny = dx / L * 26;
      var ext = 1.08;
      var b2 = { x: a.x + dx * ext, y: a.y + dy * ext };
      var figs = [line(a, b2, { color: BLUE, size: 1.3 })];
      figs.push(dash({ x: a.x + nx, y: a.y + ny }, { x: b2.x + nx, y: b2.y + ny }, GRAY));
      figs.push(dash({ x: a.x - nx, y: a.y - ny }, { x: b2.x - nx, y: b2.y - ny }, GRAY));
      return figs;
    }});

    /* --- بالا/پایین مسطح (Flat Bottom): A→B روند + خط افقی در C --- */
    reg({ name: 'flat-bottom', totalStep: 4, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 3) return [];
      var a = c[0], b = c[1], p3 = c[2];
      var figs = [line(a, b)];
      figs.push(line({ x: p3.x, y: p3.y }, { x: Math.max(b.x, p3.x) + 60, y: p3.y }, { color: BLUE, size: 1 }));
      return figs;
    }});

    /* --- کانال واگرا (Disjoint Angle): A→B + خط موازی از C --- */
    reg({ name: 'disjoint-angle', totalStep: 4, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 3) return [];
      var a = c[0], b = c[1], p3 = c[2];
      var dx = b.x - a.x, dy = b.y - a.y;
      var ext = Math.max(0.6, 220 / (Math.hypot(dx, dy) || 1));
      return [line(a, { x: b.x + dx * ext * 0.5, y: b.y + dy * ext * 0.5 }),
              line({ x: p3.x - dx * 0.2, y: p3.y - dy * 0.2 }, { x: p3.x + dx * 0.9, y: p3.y + dy * 0.9 })];
    }});

    /* --- زاویه روند (Trend Angle) --- */
    reg({ name: 'trend-angle', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var ang = Math.atan2(a.y - b.y, b.x - a.x) * 180 / Math.PI;
      var figs = [line(a, { x: BIG, y: a.y - Math.tan(ang * Math.PI / 180) * (BIG - a.x) })];
      figs.push(txt(a.x + 8, a.y - 8, ang.toFixed(1) + '°', BLUE));
      return figs;
    }});

    /* --- پچ‌فورک‌ها: اندروز / شیف / شیف اصلاح‌شده / داخلی ---
       v8.8-FIX-4b — سه واریانت واقعاً متمایز + حذف پره‌های P→R / P→S
       • Schiff: مبدا فقط در «قیمت» (عمودی) جابه‌جا می‌شود. شیفتِ محوری بی‌فایده بود،
         چون midpoint(P,midRS) روی خودِ خط میانه می‌افتد → شیب هرگز عوض نمی‌شد (no-op).
       • Inside: میانه از نقطهٔ دوم (R) می‌گذرد و mid(P,S) را نصف می‌کند؛ ریل‌ها از P و S.
       • هر سه خط موازی‌اند؛ هیچ پره‌ای از مبدا به R/S کشیده نمی‌شود (پاریتی TV). */
    function makePitchfork(name, mode) {
      reg({ name: name, totalStep: 4, lock: true, createPointFigures: function (e) {
        var c = coords(e); if (c.length < 3) return [];
        var a = c[0], r = c[1], s = c[2];
        var midRS = { x: (r.x + s.x) / 2, y: (r.y + s.y) / 2 };
        var origin = a, anchor = midRS, railA = r, railB = s;
        if (mode === 'schiff')  origin = { x: a.x, y: a.y + (midRS.y - a.y) * 0.50 };
        if (mode === 'schiff2') origin = { x: a.x, y: a.y + (midRS.y - a.y) * 0.25 };
        if (mode === 'inside') {
          origin = r;
          anchor = { x: (a.x + s.x) / 2, y: (a.y + s.y) / 2 };
          railA = a; railB = s;
        }
        var dx = anchor.x - origin.x, dy = anchor.y - origin.y;
        if (dx === 0 && dy === 0) return [];   // هندسه نامعین
        var ext = 1.6, back = 0.25;
        function ray(q, size) {
          return line({ x: q.x - dx * back, y: q.y - dy * back },
                      { x: q.x + dx * ext,  y: q.y + dy * ext },
                      { color: BLUE, size: size, style: 'solid' });
        }
        return [ray(origin, 1.4), ray(railA, 1), ray(railB, 1)];
      }});
    }
    makePitchfork('pitchfork-andrews', 'andrews');
    makePitchfork('schiff-pitchfork', 'schiff');
    makePitchfork('schiff-pitchfork-2', 'schiff2');
    makePitchfork('inside-pitchfork', 'inside');

    /* --- کانال فیبوناچی: A→B روند؛ عرض کانال = فاصلهٔ عمودی C تا خط AB ---
       v8.8-FIX-3 — قبلاً «sy = p3.y + dy*(f-1)» بود: لنگر روی کلیکِ سوم با آفستِ
       کلِ ارتفاعِ پیکسلی AB. نتیجه: خط f=1 روی AB نمی‌نشست، عرض کانال بی‌معنی بود
       و جابه‌جایی C عمودی کانال را به‌هم می‌ریخت.
       استاندارد: y_f(x) = yAB(x) + W*f  که W = p3.y - yAB(p3.x)  → f=1 دقیقاً از C می‌گذرد. */
    reg({ name: 'fib-channel', totalStep: 4, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 3) return [];
      var a = c[0], b = c[1], p3 = c[2];
      var dx = b.x - a.x, dy = b.y - a.y;
      var m = dy / (dx || 1);                       // شیب خط AB (پیکسل/پیکسل)
      var yAB = function (x) { return a.y + m * (x - a.x); };
      var W = p3.y - yAB(p3.x);                     // عرض امضادار کانال
      var figs = [line(a, b)];
      var xFrom = Math.min(a.x, p3.x);
      var xTo = Math.max(b.x, p3.x) + Math.max(80, Math.abs(dx)) * 0.4;
      [0.382, 0.618, 1, 1.618, 2.618].forEach(function (f) {
        var y1 = yAB(xFrom) + W * f, y2 = yAB(xTo) + W * f;
        figs.push(line({ x: xFrom, y: y1 }, { x: xTo, y: y2 }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [5, 3] }));
        figs.push(txt(xTo + 4, y2, f, GRAY));
      });
      return figs;
    }});

    /* --- منطقه زمانی فیبوناچی + فیبو زمانی بر پایه روند --- */
    function makeFibTime(name) {
      reg({ name: name, totalStep: 3, lock: true, createPointFigures: function (e) {
        var c = coords(e), p = ovPts(e); if (c.length < 2) return [];
        var a = c[0], b = c[1];
        var figs = [];
        [0, 1, 1.618, 2.618, 4.236].forEach(function (f, i) {
          var x = a.x + (b.x - a.x) * f;
          figs.push(line({ x: x, y: 0 }, { x: x, y: BIG }, { color: i === 0 ? BLUE : GRAY, size: 1, style: i === 0 ? 'solid' : 'dashed', dashedValue: [4, 3] }));
          if (p.length > 1 && i > 0) {
            var days = Math.round((p[1].timestamp - p[0].timestamp) / 86400000 * f);
            figs.push(txt(x + 3, 30, f + ' (' + days + ' روز)', GRAY));
          }
        });
        return figs;
      }});
    }
    makeFibTime('fib-time-zone');
    makeFibTime('fib-time-based');

    /* --- باکس/مربع گن (دو variant دیگر) --- */
    reg({ name: 'gann-fixed', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var sz = Math.max(Math.abs(b.x - a.x), Math.abs(b.y - a.y));
      var x = a.x + (b.x < a.x ? -sz : sz * 0), w = sz, h = sz;
      var x0 = b.x < a.x ? a.x - sz : a.x, y0 = b.y < a.y ? a.y - sz : a.y;
      return [poly([{ x: x0, y: y0 }, { x: x0 + sz, y: y0 }, { x: x0 + sz, y: y0 + sz }, { x: x0, y: y0 + sz }]),
              line({ x: x0, y: y0 + sz }, { x: x0 + sz, y: y0 }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] })];
    }});
    reg({ name: 'gann-complex', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var x0 = Math.min(a.x, b.x), y0 = Math.min(a.y, b.y), w = Math.abs(b.x - a.x), h = Math.abs(b.y - a.y);
      var figs = [poly([{ x: x0, y: y0 }, { x: x0 + w, y: y0 }, { x: x0 + w, y: y0 + h }, { x: x0, y: y0 + h }])];
      [[{ x: x0, y: y0 + h }, { x: x0 + w, y: y0 }], [{ x: x0, y: y0 }, { x: x0 + w, y: y0 + h }],
       [{ x: x0 + w / 2, y: y0 }, { x: x0 + w / 2, y: y0 + h }], [{ x: x0, y: y0 + h / 2 }, { x: x0 + w, y: y0 + h / 2 }]].forEach(function (L, i) {
        figs.push(line(L[0], L[1], { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] }));
      });
      return figs;
    }});

    /* --- بادبزن گن: پرتوهای 1×1 ... 1×8 --- */
    reg({ name: 'gann-fan', totalStep: 2, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (!c.length) return [];
      var p = c[0], figs = [];
      var DX = 1600;
      [8, 4, 3, 2, 1, 0.5, 1 / 3, 0.25, 0.125].forEach(function (m, i) {
        var stl = (m === 1) ? { color: BLUE, size: 1.3 } : { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] };
        figs.push(line(p, { x: p.x + DX, y: p.y - DX * m }, stl));
        figs.push(line(p, { x: p.x + DX, y: p.y + DX * m }, stl));
      });
      return figs;
    }});

    /* --- بادبزن فیبوناچی (Speed Resistance Fan) ---
       v8.8-FIX-2 — ضریب جادویی «2.2» حذف شد.
       استاندارد: در x=B یک خط عمود گرفته و فاصلهٔ A..B روی آن به نسبت‌های فیبو
       تقسیم می‌شود؛ هر پرتو از A به آن تقسیم‌گاه می‌رود. پس:
         شیب(pertu f) = f * شیب(AB)      و      y_end = a.y + (b.y-a.y)*f*(DX/runX) */
    reg({ name: 'fib-speed-resistance-fan', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var runX = (b.x - a.x) || 1;
      var DX = Math.max(200, b.x - a.x) * 3;
      var figs = [line({ x: b.x, y: a.y }, { x: b.x, y: b.y }, { color: GRAY, size: 1, style: 'solid' })];
      [0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618].forEach(function (f) {
        var yEnd = a.y + (b.y - a.y) * f * (DX / runX);
        figs.push(line(a, { x: a.x + DX, y: yEnd }, { color: f === 0.5 || f === 1 ? BLUE : GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] }));
        figs.push(txt(a.x + DX + 4, yEnd, f, GRAY));
      });
      return figs;
    }});

    /* --- دایره‌های فیبوناچی --- */
    reg({ name: 'fib-circles', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var R = Math.hypot(b.x - a.x, b.y - a.y);
      var figs = [];
      [0.382, 0.5, 0.618, 1, 1.618].forEach(function (f) {
        figs.push({ type: 'arc', attrs: { x: a.x, y: a.y, r: Math.max(2, R * f), r2: Math.max(2, R * f), startAngle: 0, endAngle: Math.PI * 2 }, styles: { style: 'stroke', borderColor: f === 1 ? BLUE : GRAY, borderSize: 1, borderStyle: 'dashed', borderDashedValue: [4, 3] } });
      });
      return figs;
    }});

    /* --- پیچ‌فن (Pitchfan) --- */
    reg({ name: 'pitchfan', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var DX = Math.max(200, (b.x - a.x)) * 3;
      var figs = [line(a, b, { color: BLUE, size: 1, style: 'dashed', dashedValue: [4, 3] })];
      [0.382, 0.618, 1, 1.618].forEach(function (f) {
        figs.push(line(a, { x: a.x + DX, y: a.y + (b.y - a.y) * f * 2.2 }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] }));
      });
      return figs;
    }});

    /* --- مارپیچ فیبوناچی (تقریب چندضلعی) --- */
    reg({ name: 'fib-spiral', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var R0 = Math.max(6, Math.hypot(b.x - a.x, b.y - a.y) * 0.12);
      var PHI = 1.6180339;
      var figs = [], prev = null;
      for (var i = 0; i <= 110; i++) {
        var th = i * 0.12;
        var r = R0 * Math.pow(PHI, th / (Math.PI / 2));
        var p = { x: a.x + r * Math.cos(th), y: a.y + r * Math.sin(th) };
        if (prev) figs.push(line(prev, p, { color: GRAY, size: 1 }));
        prev = p;
        if (r > 3000) break;
      }
      return figs;
    }});

    /* --- کمان فیبوناچی (Speed Resistance Arcs) --- */
    reg({ name: 'fib-arcs', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var R = Math.hypot(b.x - a.x, b.y - a.y);
      var figs = [line(a, b, { color: GRAY, size: 1, style: 'dashed', dashedValue: [3, 3] })];
      [0.382, 0.5, 0.618, 1].forEach(function (f) {
        figs.push({ type: 'arc', attrs: { x: a.x, y: a.y, r: Math.max(2, R * f), r2: Math.max(2, R * f), startAngle: Math.PI, endAngle: Math.PI * 2 }, styles: { style: 'stroke', borderColor: f === 1 ? BLUE : GRAY, borderSize: 1 } });
      });
      return figs;
    }});

    /* --- گوه فیبوناچی --- */
    reg({ name: 'fib-wedge', totalStep: 4, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 3) return [];
      var a = c[0], b = c[1], p3 = c[2];
      var figs = [poly([a, b, p3], { style: 'stroke', color: 'rgba(41,98,255,0.06)', borderColor: BLUE, borderSize: 1 })];
      [0.382, 0.618].forEach(function (f) {
        var m1 = { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
        var m2 = { x: a.x + (p3.x - a.x) * f, y: a.y + (p3.y - a.y) * f };
        figs.push(dash(m1, m2, GRAY));
      });
      return figs;
    }});

    /* --- مستطیل چرخیده: A→B یال اول، C عرض --- */
    reg({ name: 'rotated-rect', totalStep: 4, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 3) return [];
      var a = c[0], b = c[1], p3 = c[2];
      var d = { x: a.x + (p3.x - b.x), y: a.y + (p3.y - b.y) };
      return [poly([a, b, p3, d], { style: 'stroke', color: 'rgba(41,98,255,0.10)', borderColor: BLUE, borderSize: 1 })];
    }});

    /* --- الگوها و امواج الیوت: چندضلعی با برچسب --- */
    function makePattern(name, labels) {
      reg({ name: name, totalStep: labels.length + 1, lock: true, createPointFigures: function (e) {
        var c = coords(e); if (c.length < 2) return [];
        var figs = [];
        for (var i = 0; i < c.length - 1; i++) figs.push(line(c[i], c[i + 1], { color: BLUE, size: 1.2 }));
        for (var j = 0; j < c.length; j++) figs.push(txt(c[j].x + 5, c[j].y - 5, labels[j] || (j + 1), BLUE, 10));
        return figs;
      }});
    }
    makePattern('pattern-xabcd', ['X', 'A', 'B', 'C', 'D']);
    makePattern('pattern-cypher', ['X', 'A', 'B', 'C']);
    makePattern('pattern-abcd', ['A', 'B', 'C', 'D']);
    makePattern('pattern-triangle', ['A', 'B', 'C', 'D', 'E']);
    makePattern('pattern-3drives', ['1', '2', '3', 'A', 'B', 'C']);
    makePattern('pattern-hns', ['1', '2', '3', '4', '5', '6', '7']);
    makePattern('elliott-impulse', ['0', '1', '2', '3', '4', '5']);
    makePattern('elliott-triangle', ['A', 'B', 'C', 'D', 'E']);
    makePattern('elliott-triple', ['W', 'X', 'Y', 'X', 'Z']);
    makePattern('elliott-correction', ['0', 'A', 'B', 'C']);
    makePattern('elliott-double', ['0', 'W', 'X', 'Y']);

    /* --- خطوط دایره‌ای / چرخه‌های زمانی / خطوط سینوسی --- */
    reg({ name: 'circle-lines', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var R = Math.hypot(b.x - a.x, b.y - a.y);
      return [0.382, 0.618, 1].map(function (f) {
        return { type: 'arc', attrs: { x: a.x, y: a.y, r: Math.max(2, R * f), r2: Math.max(2, R * f), startAngle: 0, endAngle: Math.PI * 2 }, styles: { style: 'stroke', borderColor: f === 1 ? BLUE : GRAY, borderSize: 1 } };
      });
    }});
    reg({ name: 'time-cycles', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var stepX = (b.x - a.x), figs = [];
      for (var k = 1; k <= 6; k++) {
        var x = a.x + stepX * k;
        figs.push(line({ x: x, y: 0 }, { x: x, y: BIG }, { color: k === 1 ? BLUE : GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] }));
      }
      return figs;
    }});
    reg({ name: 'sine-line', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var T = (b.x - a.x) || 100, amp = (b.y - a.y) || 40;
      var figs = [], prev = null;
      for (var i = 0; i <= 120; i++) {
        var x = a.x + T * i / 20;
        var y = a.y + amp * Math.sin(Math.PI * 2 * i / 20);
        var p = { x: x, y: y };
        if (prev) figs.push(line(prev, p, { color: BLUE, size: 1.2 }));
        prev = p;
      }
      return figs;
    }});

    /* --- موقعیت خرید/فروش (Risk/Reward) --- */
    function makeRR(name, isShort) {
      reg({ name: name, totalStep: 4, lock: true, createPointFigures: function (e) {
        var c = coords(e), p = ovPts(e); if (c.length < 3) return [];
        var entry = c[0], stop = c[1], tgt = c[2];
        var x0 = Math.min(entry.x, tgt.x), x1 = Math.max(entry.x, tgt.x) + 40;
        var figs = [];
        var yStop = stop.y, yTgt = tgt.y, yE = entry.y;
        figs.push({ type: 'rect', attrs: { x: x0, y: Math.min(yE, yTgt), width: x1 - x0, height: Math.abs(yTgt - yE) }, styles: { style: 'fill', color: isShort ? 'rgba(242,54,69,0.10)' : 'rgba(8,153,129,0.10)' } });
        figs.push({ type: 'rect', attrs: { x: x0, y: Math.min(yE, yStop), width: x1 - x0, height: Math.abs(yStop - yE) }, styles: { style: 'fill', color: isShort ? 'rgba(8,153,129,0.08)' : 'rgba(242,54,69,0.08)' } });
        figs.push(line({ x: x0, y: yE }, { x: x1, y: yE }, { color: BLUE, size: 1.2 }));
        figs.push(line({ x: x0, y: yStop }, { x: x1, y: yStop }, { color: RED, size: 1 }));
        figs.push(line({ x: x0, y: yTgt }, { x: x1, y: yTgt }, { color: GREEN, size: 1 }));
        var risk = Math.abs((p[1] ? p[1].value : 0) - (p[0] ? p[0].value : 0));
        var rew = Math.abs((p[2] ? p[2].value : 0) - (p[0] ? p[0].value : 0));
        var rr = risk > 0 ? (rew / risk).toFixed(2) : '—';
        figs.push(txt(x1 - 4, Math.min(yE, yTgt) - 4, 'R:R ' + rr, GREEN, 11, 'right'));
        return figs;
      }});
    }
    makeRR('rr-long', false);
    makeRR('rr-short', true);

    /* --- پیش‌بینی / برآورد --- */
    function makePred(name, labelTxt) {
      reg({ name: name, totalStep: 4, lock: true, createPointFigures: function (e) {
        var c = coords(e), p = ovPts(e); if (c.length < 3) return [];
        var a = c[0], b = c[1], p3 = c[2];
        var figs = [line(a, b, { color: BLUE, size: 1.2 })];
        figs.push(dash(b, p3, GRAY));
        figs.push({ type: 'tick', attrs: { x: p3.x, y: p3.y, direction: b.x > p3.x ? 'left' : 'right' }, styles: { style: { color: GRAY, size: 8 } } });
        if (p.length > 2) {
          var chg = ((p[2].value / (p[0].value || 1)) - 1) * 100;
          figs.push(txt(p3.x + 6, p3.y - 6, labelTxt + ' ' + (chg >= 0 ? '+' : '') + chg.toFixed(1) + '%', chg >= 0 ? GREEN : RED, 11));
        }
        return figs;
      }});
    }
    makePred('prediction-tool', '→');
    makePred('projection-tool', '');

    /* --- بازه زمانی / محدوده قیمتی / بازه زمان و قیمت --- */
    reg({ name: 'date-range', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e), p = ovPts(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var days = p.length > 1 ? Math.max(1, Math.round(Math.abs(p[1].timestamp - p[0].timestamp) / 86400000)) : 0;
      return [{ type: 'rect', attrs: { x: Math.min(a.x, b.x), y: 0, width: Math.abs(b.x - a.x), height: BIG }, styles: { style: 'fill', color: 'rgba(41,98,255,0.10)', borderColor: BLUE, borderSize: 1 } },
              txt((a.x + b.x) / 2, 24, days + ' روز', BLUE, 11, 'center')];
    }});
    reg({ name: 'price-range', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e), p = ovPts(e); if (c.length < 2 || p.length < 2) return [];
      var a = c[0], b = c[1];
      var chg = p[0].value ? ((p[1].value / p[0].value - 1) * 100) : 0;
      return [{ type: 'rect', attrs: { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) }, styles: { style: 'fill', color: chg >= 0 ? 'rgba(8,153,129,0.10)' : 'rgba(242,54,69,0.10)', borderColor: chg >= 0 ? GREEN : RED, borderSize: 1 } },
              txt(Math.min(a.x, b.x) + 6, Math.min(a.y, b.y) - 4, (chg >= 0 ? '+' : '') + chg.toFixed(2) + '% (' + Math.abs(p[1].value - p[0].value).toFixed(0) + ')', chg >= 0 ? GREEN : RED, 11)];
    }});
    reg({ name: 'date-price-range', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e), p = ovPts(e); if (c.length < 2 || p.length < 2) return [];
      var a = c[0], b = c[1];
      var chg = p[0].value ? ((p[1].value / p[0].value - 1) * 100) : 0;
      var days = Math.max(1, Math.round(Math.abs(p[1].timestamp - p[0].timestamp) / 86400000));
      return [{ type: 'rect', attrs: { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) }, styles: { style: 'fill', color: 'rgba(41,98,255,0.08)', borderColor: BLUE, borderSize: 1 } },
              txt((a.x + b.x) / 2, Math.min(a.y, b.y) - 4, days + ' روز | ' + (chg >= 0 ? '+' : '') + chg.toFixed(2) + '%', BLUE, 11, 'center')];
    }});

    /* --- الگوی داده‌ها / داده مجازی / نشانگر حجم --- */
    reg({ name: 'bars-pattern', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      return [{ type: 'rect', attrs: { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) }, styles: { style: 'fill', color: 'rgba(41,98,255,0.10)', borderColor: BLUE, borderSize: 1 } },
              txt((a.x + b.x) / 2, Math.min(a.y, b.y) - 4, 'الگوی داده‌ها', BLUE, 10, 'center')];
    }});
    reg({ name: 'ghost-feed', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      return [{ type: 'rect', attrs: { x: Math.min(a.x, b.x), y: Math.min(a.y, b.y), width: Math.abs(b.x - a.x), height: Math.abs(b.y - a.y) }, styles: { style: 'fill', color: 'rgba(120,123,134,0.06)', borderColor: GRAY, borderSize: 1, borderStyle: 'dashed' } },
              line({ x: Math.min(a.x, b.x), y: (a.y + b.y) / 2 }, { x: Math.max(a.x, b.x), y: (a.y + b.y) / 2 }, { color: GRAY, size: 1, style: 'dashed', dashedValue: [4, 3] })];
    }});
    /* --- پروفایل والیوم: هیستوگرام «واقعی» حجم در بازهٔ قیمتی انتخاب‌شده ---
       v8.8-FIX-6 — جدول ثابت [0.9,0.55,0.7,…] حذف شد (نمایشی و مستقل از داده بود).
       منبع: rv.data — همان آرایهٔ کندل‌های نمایش‌داده‌شده روی چارت (fallback:
       window.RV_VOL_SOURCE برای تست). پنجرهٔ زمانی از overlay.points (A..B) و
       پنجرهٔ قیمتی از دو سر انتخاب کاربر. حجم هر کندل به‌صورت یکنواخت روی بازهٔ
       Low..High آن بین سطل‌های قیمتی پخش می‌شود (رفتار استاندارد Volume Profile). */
    var VP_ROWS = 24;
    function vpSource() {
      // v8.8-FIX-6b — «rv.data = []» truthy است، پس `a || b` هرگز به fallback نمی‌رسید؛
      // باید صریحاً طول بررسی شود.
      if (window.rv && window.rv.data && window.rv.data.length) return window.rv.data;
      if (window.RV_VOL_SOURCE && window.RV_VOL_SOURCE.length) return window.RV_VOL_SOURCE;
      return null;
    }
    reg({ name: 'volume-profile-tool', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = coords(e), p = ovPts(e); if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var x0 = Math.min(a.x, b.x), w = Math.abs(b.x - a.x);
      var y0 = Math.min(a.y, b.y), h = Math.abs(b.y - a.y);
      var figs = [{ type: 'rect', attrs: { x: x0, y: y0, width: w, height: h }, styles: { style: 'stroke', color: 'transparent', borderColor: GRAY, borderSize: 1 } }];
      var data = vpSource(), i, r;
      if (!data || p.length < 2 || !w || !h) {
        figs.push(txt(x0 + 4, y0 + 12, data ? 'بازهٔ نامعتبر' : 'دادهٔ حجم در دسترس نیست', GRAY, 10));
        return figs;
      }
      var t0 = Math.min(p[0].timestamp, p[1].timestamp), t1 = Math.max(p[0].timestamp, p[1].timestamp);
      var loP = Math.min(p[0].value, p[1].value), hiP = Math.max(p[0].value, p[1].value);
      var span = (hiP - loP) || 1;
      var bins = [];
      for (i = 0; i < VP_ROWS; i++) bins.push(0);
      for (i = 0; i < data.length; i++) {
        var d = data[i]; if (!d) continue;
        var t = (d.timestamp !== undefined) ? d.timestamp : d.time;
        if (t === undefined || t < t0 || t > t1) continue;
        var vol = +d.volume || 0; if (vol <= 0) continue;
        var bLo = Math.min(d.low, d.high), bHi = Math.max(d.low, d.high);
        var lo = Math.max(bLo, loP), hi = Math.min(bHi, hiP);
        if (hi <= lo) continue;
        var share = vol * (hi - lo) / ((bHi - bLo) || 1);
        var r0 = Math.max(0, Math.floor((lo - loP) / span * VP_ROWS));
        var r1 = Math.min(VP_ROWS - 1, Math.floor((hi - loP) / span * VP_ROWS));
        var n = r1 - r0 + 1;
        for (r = r0; r <= r1; r++) bins[r] += share / n;
      }
      var mx = 0, poc = -1;
      for (i = 0; i < VP_ROWS; i++) if (bins[i] > mx) { mx = bins[i]; poc = i; }
      if (!(mx > 0)) {
        figs.push(txt(x0 + 4, y0 + 12, 'حجمی در این بازه نیست', GRAY, 10));
        return figs;
      }
      var bh = h / VP_ROWS;
      for (i = 0; i < VP_ROWS; i++) {
        if (!(bins[i] > 0)) continue;
        var bw = Math.max(1, w * (bins[i] / mx) * 0.92);
        var yy = y0 + h - bh * (i + 1);          // سطل ۰ = پایین‌ترین قیمت = کف کادر
        figs.push({ type: 'rect', attrs: { x: x0, y: yy, width: bw, height: Math.max(1, bh - 1) },
                    styles: { style: 'fill', color: i === poc ? 'rgba(245,158,11,0.85)' : 'rgba(41,98,255,0.35)' } });
      }
      figs.push(txt(x0 + 4, y0 - 3, 'POC ' + (loP + span * (poc + 0.5) / VP_ROWS).toFixed(2) + ' · ' + VP_ROWS + ' سطح', ORANGE, 10));
      return figs;
    }});

    /* --- یادداشت‌ها: متن ثابت / یادداشت / تابلو / نوشته راهنما / بالون / برچسب قیمت / یادداشت قیمت --- */
    function makeNote(name, defColor, radius) {
      reg({ name: name, totalStep: 2, lock: true, createPointFigures: function (e) {
        var c = coords(e), p = ovPts(e); if (!c.length) return [];
        var pt = c[0];
        var t = (e.overlay && e.overlay.styles && e.overlay.styles.text) || (p[0] ? p[0].value.toFixed(0) : name);
        return [txt(pt.x + 4, pt.y - 6, t, defColor, 12)];
      }});
    }
    makeNote('text-absolute', BLUE);
    makeNote('note-tool', ORANGE);
    makeNote('note-absolute', ORANGE);
    makeNote('signpost-tool', BLUE);
    makeNote('callout-tool', GREEN);
    makeNote('balloon-tool', '#e879f9');
    makeNote('price-label-tool', GREEN);
    makeNote('price-note-tool', ORANGE);

    /* --- فلش‌های جهت‌دار + پرچم + نقطه (تک‌نقطه‌ای) --- */
    function makeMark(name, glyph, color) {
      reg({ name: name, totalStep: 2, lock: true, createPointFigures: function (e) {
        var c = coords(e); if (!c.length) return [];
        var pt = c[0];
        return [{ type: 'text', attrs: { x: pt.x, y: pt.y, text: glyph, align: 'center', baseline: 'middle' }, styles: { style: 'fill', color: color, size: 15, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } }];
      }});
    }
    makeMark('arrow-mark-up', '▲', GREEN);
    makeMark('arrow-mark-down', '▼', RED);
    makeMark('arrow-mark-left', '◀', BLUE);
    makeMark('arrow-mark-right', '▶', BLUE);
    makeMark('flag-mark', '⚑', RED);
    reg({ name: 'dot-mark', totalStep: 2, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (!c.length) return [];
      return [{ type: 'circle', attrs: { x: c[0].x, y: c[0].y, r: 4, r2: 4 }, styles: { style: 'fill', color: BLUE } }];
    }});
    reg({ name: 'icon-stamp', totalStep: 2, lock: true, createPointFigures: function (e) {
      var c = coords(e); if (!c.length) return [];
      var st = (e.overlay && e.overlay.styles) || {};
      var g = st.text || '⭐';
      return [{ type: 'text', attrs: { x: c[0].x, y: c[0].y, text: g, align: 'center', baseline: 'middle' }, styles: { style: 'fill', color: '#f0f3fa', size: 18, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } }];
    }});
  }

  /* ============ 4) پیکربندی گروه‌ها — دقیقاً به ترتیب نهایت‌نگر ============ */
  /* هر ابزار: n=نام ابزار داخلی، fa=برچسب فارسی (متن فلایاوت نهایت‌نگر)،
     ov=نام overlay در klinecharts، st=استایل پیشفرض (اختیاری) */
  var GROUPS = [
    { id: 'cursors', title: 'مکان‌نماها', icon: 'cursor', tools: [
      { n: 'cursor', fa: 'مکان‌نما', ov: null },
      { n: 'dot', fa: 'نقطه', ov: 'dot-mark' },
      { n: 'arrow-cursor', fa: 'پیکان', ov: 'arrow', icon: 'arrowTool' },
      { n: 'eraser', fa: 'پاک‌کن', ov: null }
    ]},
    { id: 'trend', title: 'خطوط روند', icon: 'trend', tools: [
      { n: 'segment', fa: 'خط روند', ov: 'segment' },
      { n: 'arrow', fa: 'پیکان', ov: 'arrow', icon: 'arrowTool' },
      { n: 'rayLine', fa: 'نیم‌خط', ov: 'rayLine', icon: 'ray' },
      { n: 'info-line', fa: 'خط روند با جزئیات', ov: 'info-line', icon: 'infoLine' },
      { n: 'straightLine', fa: 'خط تمدید شده', ov: 'straightLine', icon: 'extended' },
      { n: 'trend-angle', fa: 'زاویه روند', ov: 'trend-angle', icon: 'trendAngle' },
      { n: 'horizontalStraightLine', fa: 'خط افقی', ov: 'horizontalStraightLine', icon: 'horzLine' },
      { n: 'horizontalRayLine', fa: 'نیم خط افقی', ov: 'horizontalRayLine', icon: 'horzRay' },
      { n: 'verticalStraightLine', fa: 'خط عمودی', ov: 'verticalStraightLine', icon: 'vertLine' },
      { n: 'cross-line', fa: 'خط افقی/عمودی', ov: 'cross-line', icon: 'crossLine' },
      { n: 'parallelStraightLine', fa: 'کانال', ov: 'parallelStraightLine', icon: 'channel' },
      { n: 'regression-trend', fa: 'روند رگرسیون', ov: 'regression-trend', icon: 'regression' },
      { n: 'flat-bottom', fa: 'بالا/پایین مسطح', ov: 'flat-bottom', icon: 'flatBottom' },
      { n: 'disjoint-angle', fa: 'کانال واگرا', ov: 'disjoint-angle', icon: 'disjoint' }
    ]},
    { id: 'gannfib', title: 'گان و فیبوناچی', icon: 'fibRetrace', tools: [
      { n: 'fibonacciLine', fa: 'اصلاحی فیبوناچی', ov: 'fibonacciLine' },
      { n: 'fib-extension', fa: 'فیبو اکسپنشن', ov: 'fib-extension', icon: 'fibExt' },
      { n: 'pitchfork', fa: 'چنگال اندروز', ov: 'pitchfork-andrews', icon: 'pitchfork' },
      { n: 'schiff-pitchfork', fa: 'شیف پیچ‌فورک', ov: 'schiff-pitchfork', icon: 'schiff' },
      { n: 'schiff-pitchfork-2', fa: 'شیف پیچ‌فورک اصلاح‌شده', ov: 'schiff-pitchfork-2', icon: 'schiff' },
      { n: 'inside-pitchfork', fa: 'پیچ‌فورک داخلی', ov: 'inside-pitchfork', icon: 'pitchfork' },
      { n: 'fib-channel', fa: 'کانال فیبوناچی', ov: 'fib-channel', icon: 'fibChannel' },
      { n: 'fib-time-zone', fa: 'منطقه زمانی فیبوناچی', ov: 'fib-time-zone', icon: 'fibTime' },
      { n: 'box', fa: 'باکس گن', ov: 'box' },
      { n: 'gann-fixed', fa: 'مربع ثابت گن', ov: 'gann-fixed', icon: 'gannFixed' },
      { n: 'gann-complex', fa: 'مربع گن', ov: 'gann-complex', icon: 'gannComplex' },
      { n: 'gann-fan', fa: 'بادبزن گن', ov: 'gann-fan', icon: 'gannFan' },
      { n: 'fib-speed-resistance-fan', fa: 'بادبزن فیبوناچی', ov: 'fib-speed-resistance-fan', icon: 'fibFan' },
      { n: 'fib-time-based', fa: 'فیبوناچی زمانی بر پایه روند', ov: 'fib-time-based', icon: 'fibTime' },
      { n: 'fib-circles', fa: 'دایره های فیبوناچی', ov: 'fib-circles', icon: 'fibCircles' },
      { n: 'pitchfan', fa: 'پیچ‌ فن', ov: 'pitchfan', icon: 'pitchfan' },
      { n: 'fib-spiral', fa: 'مارپیچ فیبوناچی', ov: 'fib-spiral', icon: 'spiral' },
      { n: 'fib-arcs', fa: 'کمان فیبوناچی', ov: 'fib-arcs', icon: 'fibArcs' },
      { n: 'fib-wedge', fa: 'گوه فیبوناچی', ov: 'fib-wedge', icon: 'fibWedge' }
    ]},
    { id: 'geometric', title: 'اشکال هندسی', icon: 'brush', tools: [
      { n: 'brush', fa: 'قلم', ov: 'brush' },
      { n: 'highlighter', fa: 'ماژیک', ov: 'brush', st: { line: { color: 'rgba(250, 204, 21, 0.35)', size: 14 } }, icon: 'highlighter' },
      { n: 'rect', fa: 'مستطیل', ov: 'rect' },
      { n: 'circle', fa: 'دایره', ov: 'circle', icon: 'circleTool' },
      { n: 'ellipse', fa: 'بیضی', ov: 'ellipse', icon: 'ellipseTool' },
      { n: 'path', fa: 'مسیر', ov: 'brush', icon: 'pathTool' },
      { n: 'bezier-quadro', fa: 'منحنی 1', ov: 'brush', icon: 'bezierQ' },
      { n: 'polyline', fa: 'چند ضلعی', ov: 'brush', icon: 'polyline' },
      { n: 'triangle', fa: 'مثلث', ov: 'triangle', icon: 'triangleTool' },
      { n: 'rotated-rect', fa: 'مستطیل چرخیده', ov: 'rotated-rect', icon: 'rotatedRect' },
      { n: 'arc', fa: 'کمان', ov: 'arc', icon: 'arcTool' },
      { n: 'bezier-cubic', fa: 'منحنی 2', ov: 'brush', icon: 'bezierC' }
    ]},
    { id: 'annotation', title: 'حاشیه‌نویسی', icon: 'textTool', tools: [
      { n: 'simpleAnnotation', fa: 'متن', ov: 'simpleAnnotation' },
      { n: 'text-absolute', fa: 'متن ثابت', ov: 'text-absolute' },
      { n: 'note-tool', fa: 'یادداشت', ov: 'note-tool', icon: 'noteTool' },
      { n: 'note-absolute', fa: 'یادداشت ثابت', ov: 'note-absolute', icon: 'noteTool' },
      { n: 'signpost-tool', fa: 'تابلو', ov: 'signpost-tool', icon: 'signpost' },
      { n: 'callout-tool', fa: 'نوشته راهنما', ov: 'callout-tool', icon: 'callout' },
      { n: 'balloon-tool', fa: 'بالون', ov: 'balloon-tool', icon: 'balloon' },
      { n: 'price-label-tool', fa: 'برچسب قیمت', ov: 'price-label-tool', icon: 'priceLabel' },
      { n: 'price-note-tool', fa: 'یادداشت قیمت', ov: 'price-note-tool', icon: 'noteTool' },
      { n: 'arrow-mark-right', fa: 'فلش', ov: 'arrow-mark-right', icon: 'arrowMarkRight' },
      { n: 'arrow-mark-left', fa: 'پیکان رو به چپ', ov: 'arrow-mark-left', icon: 'arrowMarkLeft' },
      { n: 'arrow-mark-up', fa: 'پیکان رو به بالا', ov: 'arrow-mark-up', icon: 'arrowMarkUp' },
      { n: 'arrow-mark-down', fa: 'پیکان رو به پایین', ov: 'arrow-mark-down', icon: 'arrowMarkDown' },
      { n: 'flag-mark', fa: 'علامت گذاری', ov: 'flag-mark', icon: 'flagMark' },
      { n: 'simpleTag', fa: 'برچسب', ov: 'simpleTag' }
    ]},
    { id: 'patterns', title: 'الگوها', icon: 'patternAbcd', tools: [
      { n: 'pattern-xabcd', fa: 'الگو XABCD', ov: 'pattern-xabcd', icon: 'patternXabcd' },
      { n: 'pattern-cypher', fa: 'الگوی سایفر', ov: 'pattern-cypher', icon: 'patternCypher' },
      { n: 'pattern-abcd', fa: 'الگوی ABCD', ov: 'pattern-abcd', icon: 'patternAbcd' },
      { n: 'pattern-triangle', fa: 'الگو مثلث', ov: 'pattern-triangle', icon: 'patternTriangle' },
      { n: 'pattern-3drives', fa: 'الگو Three Drives', ov: 'pattern-3drives', icon: 'pattern3drives' },
      { n: 'pattern-hns', fa: 'سر و شانه ها', ov: 'pattern-hns', icon: 'patternHns' },
      { n: 'elliott-impulse', fa: 'امواج جنبشی الیوت (12345)', ov: 'elliott-impulse', icon: 'elliottImpulse' },
      { n: 'elliott-triangle', fa: 'امواج الگوی مثلث الیوت (ABCDE)', ov: 'elliott-triangle', icon: 'elliottTriangle' },
      { n: 'elliott-triple', fa: 'امواج Triple Combo الیوت (WXYXZ)', ov: 'elliott-triple', icon: 'elliottTriple' },
      { n: 'elliott-correction', fa: 'موج بزرگ اصلاحی الیوت', ov: 'elliott-correction', icon: 'elliottCorrection' },
      { n: 'elliott-double', fa: 'امواج Double Combo الیوت (WXY)', ov: 'elliott-double', icon: 'elliottDouble' },
      { n: 'circle-lines', fa: 'خطوط دایره ای', ov: 'circle-lines', icon: 'circleLines' },
      { n: 'time-cycles', fa: 'چرخه‌های زمانی', ov: 'time-cycles', icon: 'timeCycles' },
      { n: 'sine-line', fa: 'خطوط سینوسی', ov: 'sine-line', icon: 'sineLine' }
    ]},
    { id: 'prediction', title: 'پیش‌بینی و اندازه‌گیری', icon: 'rr-long', tools: [
      { n: 'rr-long', fa: 'موقعیت خرید', ov: 'rr-long', icon: 'rrLong' },
      { n: 'rr-short', fa: 'موقعیت فروش', ov: 'rr-short', icon: 'rrShort' },
      { n: 'prediction-tool', fa: 'پیش بینی', ov: 'prediction-tool', icon: 'predictionTool' },
      { n: 'date-range', fa: 'بازه زمانی', ov: 'date-range', icon: 'dateRange' },
      { n: 'price-range', fa: 'محدوده قیمتی', ov: 'price-range', icon: 'priceRange' },
      { n: 'date-price-range', fa: 'بازه زمان و قیمت', ov: 'date-price-range', icon: 'datePriceRange' },
      { n: 'bars-pattern', fa: 'الگوی داده ها', ov: 'bars-pattern', icon: 'barsPattern' },
      { n: 'ghost-feed', fa: 'داده مجازی', ov: 'ghost-feed', icon: 'ghostFeed' },
      { n: 'projection-tool', fa: 'برآمدگی', ov: 'projection-tool', icon: 'projectionTool' },
      { n: 'volume-profile-tool', fa: 'نشانگر حجم', ov: 'volume-profile-tool', icon: 'volumeProfile' }
    ]},
    { id: 'icons', title: 'آیکون‌ها', icon: '', emoji: true, tools: [
      '⭐', '❤️', '🔥', '🚀', '💡', '⚠️', '✅', '❌', '👍', '👎', '🎯', '📌', '📊', '💰', '🔔', '😀', '😎', '🤔', '😴', '🎃', '🐳', '🐂', '🐻', '☀️', '🌙', '☁️', '⚡', '❄️'
    ].map(function (em) { return { n: 'icon-' + em, fa: em, ov: 'icon-stamp', st: { text: em } }; })}
  ];

  /* ============ 5) ساخت rail از پیکربندی + فلایاوت با hover ============ */
  var _pinGroup = null; // گروه پین‌شده با کلیک
  window.rtvBuildRail = function () {
    var rail = document.getElementById('rail');
    if (!rail) return;
    rail.innerHTML = '';
    // دکمه cursor بالای rail (مثل نهایت‌نگر جدا است)
    var cur = document.createElement('button');
    cur.className = 'tv5-tool rail-cursor-btn';
    cur.dataset.name = 'cursor';
    cur.title = 'مکان‌نما';
    cur.innerHTML = iconSvg('cursor', 28);
    cur.onclick = function (ev) { ev.stopPropagation(); rvSetTool('cursor', cur); };
    rail.appendChild(cur);
    var sep = document.createElement('div'); sep.className = 'tv5-sep'; rail.appendChild(sep);

    GROUPS.forEach(function (g) {
      var wrap = document.createElement('div');
      wrap.className = 'rail-group';
      var btn = document.createElement('button');
      btn.className = 'rail-btn tv5-tool';
      btn.title = g.title;
      btn.innerHTML = g.emoji ? '<span class="rail-emoji-btn">😀</span>' : iconSvg(g.icon, 28);
      var fly = document.createElement('div');
      fly.className = 'rail-flyout' + (g.emoji ? ' rail-flyout-grid' : '');
      g.tools.forEach(function (t) {
        var item = document.createElement('button');
        item.dataset.name = t.n;
        item.title = t.fa;
        item.innerHTML = (t.n.indexOf('icon-') === 0)
          ? '<span class="rail-emoji">' + t.fa + '</span>'
          : iconSvg(t.icon || t.n, 28) + '<span>' + t.fa + '</span>';
        item.addEventListener('click', function (ev) {
          ev.stopPropagation();
          selectToolInRail(t, item);
          closeAllFlyouts();
          _pinGroup = null;
        });
        fly.appendChild(item);
      });
      // v8.5: مثل نهایت‌نگر فلایاوت فقط با کلیک باز/بسته میشود (نه hover)
      // کلیک روی دکمه گروه → پین باز/بسته
      btn.addEventListener('click', function (ev) {
        ev.stopPropagation();
        var wasOpen = fly.classList.contains('open');
        closeAllFlyouts();
        _pinGroup = (!wasOpen) ? g.id : null;
        if (!wasOpen) openFlyout(wrap, fly);
      });
      wrap.appendChild(btn);
      wrap.appendChild(fly);
      rail.appendChild(wrap);
    });

    // v8.6: بخش پایین ریل مثل نهایت‌نگر — خط‌کش | ماندن در رسم | آهنربا | حذف همه
    var sep2 = document.createElement('div'); sep2.className = 'tv5-sep'; rail.appendChild(sep2);
    var ruler = document.createElement('button');
    ruler.className = 'tv5-tool rail-util-btn'; ruler.title = 'خط‌کش — اندازه‌گیری';
    ruler.innerHTML = iconSvg('measure', 28);
    ruler.onclick = function (ev) { ev.stopPropagation(); rvSetTool('ruler', ruler); };
    rail.appendChild(ruler);
    var stay = document.createElement('button');
    stay.className = 'tv5-tool rail-util-btn'; stay.title = 'ماندن در حالت رسم';
    stay.innerHTML = iconSvg('stay-draw', 28);
    stay.onclick = function (ev) { ev.stopPropagation(); rvToggleStayDraw(stay); };
    rail.appendChild(stay);
    var mag = document.createElement('button');
    mag.className = 'tv5-tool rail-util-btn'; mag.title = 'آهنربا — چسبیدن به قیمت (باز/بسته/سقف/کف)';
    mag.innerHTML = iconSvg('magnet', 28);
    mag.onclick = function (ev) {
      ev.stopPropagation();
      var on = !mag.classList.contains('active');
      mag.classList.toggle('active', on);
      /* v10: آهنربا روی خودِ overlay است (mode:'weak_magnet') و نه یک استایل
         crosshair؛ setStyles({crosshair:{mode}}) بی‌صدا دور ریخته می‌شد.
         وضعیت در btsSet ذخیره می‌شود تا مودال تنظیمات و رسم‌های بعدی هم
         همان را ببینند (wrapper در rvSetupChart هنگام createOverlay می‌خواندش). */
      try {
        if (typeof btsSet !== 'undefined' && btsSet && btsSet.canvas) {
          btsSet.canvas.crosshair = on ? 'magnet' : 'normal';
          if (typeof btsSaveSettings === 'function') btsSaveSettings(btsSet);
          if (typeof btsOverlayMagnet === 'function') btsOverlayMagnet(on);
        }
      } catch (e) {}
      rvToast(on ? '🧲 آهنربا فعال شد' : 'آهنربا غیرفعال شد');
    };
    rail.appendChild(mag);
    var delAll = document.createElement('button');
    delAll.className = 'tv5-tool rail-util-btn'; delAll.title = 'حذف همه رسم‌ها';
    delAll.innerHTML = iconSvg('remove-all', 28);
    delAll.onclick = function (ev) { ev.stopPropagation(); if (typeof rvClearAll === 'function') rvClearAll(); };
    rail.appendChild(delAll);

    // کلیک بیرون → بستن همه
    document.addEventListener('mousedown', function (ev) {
      if (!rail.contains(ev.target)) { closeAllFlyouts(); _pinGroup = null; }
    });
  };
  function closeAllFlyouts() {
    var rail = document.getElementById('rail');
    if (rail) rail.querySelectorAll('.rail-flyout').forEach(function (x) { x.classList.remove('open'); });
  }
  function openFlyout(wrap, fly) {
    closeAllFlyouts();
    var btn = wrap.querySelector('.rail-btn');
    fly.classList.add('open');
    var br = btn.getBoundingClientRect();
    var wr = wrap.getBoundingClientRect();
    // v8.6: مختصات نسبت به والد position:relative (باگ قبلی: br.top ویوپورتی بود → منو پایین‌تر از دکمه باز میشد)
    var t = br.top - wr.top - 4;
    var fh = fly.offsetHeight || 0;
    if (fh > 0) {
      var rail = document.getElementById('rail');
      var railR = rail ? rail.getBoundingClientRect() : { bottom: window.innerHeight - 8 };
      var maxT = railR.bottom - 8 - fh - wr.top;
      if (t > maxT) t = Math.max(0, maxT);
    }
    fly.style.left = (br.right + 6) + 'px';
    fly.style.top = Math.max(0, t) + 'px';
  }
  function selectToolInRail(t, item) {
    // پاک‌کن
    if (t.n === 'eraser') { startEraserMode(item); return; }
    if (t.n === 'cursor') { rvSetTool('cursor', item); return; }
    // استایل ویژه (ماژیک/آیکون‌ها)
    if (t.st) {
      window.__rvToolStyles = window.__rvToolStyles || {};
      window.__rvToolStyles[t.ov] = t.st;
    }
    rvSetTool(t.n, item);
    // سینگل-پوینت‌ها (مارک‌ها/آیکون‌ها): بعد از رسم به cursor برنگردند اگر StayDraw
    // (رفتار در rvSetTool انجام میشود)
  }

  /* ============ 6) پاک‌کن (Eraser) — کلیک روی هر رسم = حذف ============ */
  var _eraserActive = false;
  function startEraserMode(item) {
    _eraserActive = !_eraserActive;
    document.querySelectorAll('#rail .tv5-tool').forEach(function (b) { b.classList.remove('active'); });
    if (_eraserActive && item) item.classList.add('active');
    rvToast(_eraserActive ? '🧽 پاک‌کن فعال — روی رسم کلیک کن' : 'پاک‌کن غیرفعال');
  }
  function bindEraser() {
    var box = document.getElementById('rvChartBox');
    if (!box || box.dataset.eraser) return;
    box.dataset.eraser = '1';
    box.addEventListener('click', function (ev) {
      if (!_eraserActive || !rv.chart) return;
      try {
        var rect = box.getBoundingClientRect();
        var mx = ev.clientX - rect.left, my = ev.clientY - rect.top;
        var overs = (rv.chart.getOverlays() || []).filter(function (o) { return !(o.isDrawing && o.isDrawing()); });
        if (!overs.length) return;
        var best = null, bestD = 20;
        overs.forEach(function (o) {
          (o.points || []).forEach(function (p) {
            if (!p.timestamp || !p.value) return;
            var px = null;
            try { px = rv.chart.convertToPixel('both', { timestamp: p.timestamp, value: p.value }); } catch (e) { px = null; }
            if (!px) return;
            var d = Math.hypot((px.x !== undefined ? px.x : 0) - mx, (px.y !== undefined ? px.y : 0) - my);
            if (d < bestD) { bestD = d; best = o; }
          });
        });
        if (!best) best = overs[overs.length - 1]; // fallback: آخرین رسم
        rv.chart.removeOverlay({ id: best.id });
        if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
        rvToast('🧽 رسم حذف شد');
      } catch (e) { console.warn('[eraser]', e); }
    });
  }

  /* ============ 7) نگاشت ابزارها → overlay + استایل ============ */
  function extendMapping() {
    if (typeof RTV_TOOL_NAMES === 'object' && RTV_TOOL_NAMES) {
      GROUPS.forEach(function (g) {
        g.tools.forEach(function (t) {
          if (t.ov && !RTV_TOOL_NAMES[t.n]) RTV_TOOL_NAMES[t.n] = t.ov;
        });
      });
    }
  }

  /* ============ 8) منوی اندیکاتورها به سبک نهایت‌نگر ============ */
  /* دیالوگ: عنوان + بستن + جستجو + لیست تخت (نام انگلیسی مثل نهایت‌نگر + توضیح فارسی) */
  var IND_MAP = [
    ['MA', 'Moving Average', 'میانگین متحرک ساده'], ['EMA', 'Moving Average Exponential', 'میانگین نمایی'],
    ['SMA', 'Smoothed Moving Average', 'میانگین هموار'], ['BOLL', 'Bollinger Bands', 'باندهای بولینگر'],
    ['SAR', 'Parabolic SAR', 'پارابولیک سار'],
    ['RSI', 'Relative Strength Index', 'شاخص قدرت نسبی'], ['KDJ', 'Stochastic', 'استوکاستیک'],
    ['WR', 'Williams %R', 'ویلیامز'], ['CCI', 'Commodity Channel Index', 'کانال کالا'],
    ['DMI', 'Directional Movement', 'حرکت جهت‌دار'], ['MACD', 'MACD', 'مکدی'],
    ['ROC', 'Rate Of Change', 'نرخ تغییر'], ['MTM', 'Momentum', 'مومنتوم'],
    ['OBV', 'On Balance Volume', 'حجم تعادلی'], ['PVT', 'Price Volume Trend', 'روند حجم-قیمت'],
    ['VOL', 'Volume', 'حجم'], ['AO', 'Awesome Oscillator', 'اوسام اوسام'],
    ['AVP', 'Average Price', 'قیمت میانگین'], ['BRAR', 'BRAR', 'برار'],
    ['CR', 'CR Indicator', 'سی‌آر'], ['DMA', 'DMA', 'دی‌ام‌ای'],
    ['EMV', 'Ease Of Movement', 'سهولت حرکت'], ['PSY', 'Psychological Line', 'خط روانی'],
    ['TRIX', 'TRIX', 'تریکس'], ['VR', 'Volume Ratio', 'نسبت حجم'],
    ['BIAS', 'BIAS', 'بیاس']
  ];
  function buildIndDialog() {
    var p = document.getElementById('rvIndPanel');
    if (!p || p.dataset.built8) return;
    p.dataset.built8 = '1';
    p.innerHTML =
      '<div class="rv-ind-dialog">' +
      '  <div class="rv-ind-head"><b>اندیکاتورها</b><button class="rv-ind-close" title="بستن">✕</button></div>' +
      '  <div class="rv-ind-search"><input id="rvIndSearch" placeholder="جستجو" autocomplete="off"></div>' +
      '  <div class="rv-ind-cat">اندیکاتورها</div>' +
      '  <div class="rv-ind-list" id="rvIndList"></div>' +
      '</div>';
    var list = p.querySelector('#rvIndList');
    (window.RTV_IND_EXTRA || []).forEach(function (it) {
      var exists = IND_MAP.some(function (m) { return m[0] === it[0]; });
      if (!exists) IND_MAP.push(it);
    });
    IND_MAP.forEach(function (it) {
      var row = document.createElement('button');
      row.className = 'rv-ind-row';
      row.dataset.ind = it[0];
      row.innerHTML = '<span class="rv-ind-name">' + it[2] + '</span><span class="rv-ind-fa">' + it[0] + '</span><span class="rv-ind-check">✓</span>';
      row.addEventListener('click', function () {
        if (typeof rvIndToggle === 'function') rvIndToggle(it[0]);
        refreshIndRows();
      });
      list.appendChild(row);
    });
    var all = document.createElement('button');
    all.className = 'rv-ind-row rv-ind-removeall';
    all.innerHTML = '<span class="rv-ind-name">✖ حذف همه اندیکاتورها</span>';
    all.addEventListener('click', function () { if (typeof rvIndsRemoveAll === 'function') rvIndsRemoveAll(); refreshIndRows(); });
    list.appendChild(all);
    p.querySelector('.rv-ind-close').addEventListener('click', function () { p.style.display = 'none'; });
    p.querySelector('#rvIndSearch').addEventListener('input', function () {
      var q = this.value.trim().toLowerCase();
      list.querySelectorAll('.rv-ind-row[data-ind]').forEach(function (r) {
        var hit = r.textContent.toLowerCase().indexOf(q) >= 0;
        r.style.display = hit ? '' : 'none';
      });
    });
    refreshIndRows();
  }
  function refreshIndRows() {
    var added = (typeof rvIndsAdded !== 'undefined') ? rvIndsAdded : [];
    document.querySelectorAll('.rv-ind-row[data-ind]').forEach(function (r) {
      r.classList.toggle('on', added.indexOf(r.dataset.ind) >= 0);
    });
  }
  window.rvToggleIndPanel = function () {
    var p = document.getElementById('rvIndPanel');
    if (!p) return;
    if (p.style.display === 'block') { p.style.display = 'none'; return; }
    buildIndDialog();
    refreshIndRows();
    p.style.display = 'block';
    var s = document.getElementById('rvIndSearch');
    if (s) { s.value = ''; s.focus(); }
  };

  /* ماندن در حالت رسم (پاریتی نهایت‌نگر: drawginmode) */
  window.rvToggleStayDraw = function (btn) {
    window.RTV_STAY_DRAW = !window.RTV_STAY_DRAW;
    if (btn) btn.classList.toggle('active', !!window.RTV_STAY_DRAW);
    rvToast(window.RTV_STAY_DRAW ? '✏️ ماندن در حالت رسم: فعال' : 'ماندن در حالت رسم: غیرفعال');
  };

  /* ============ 8.7) v8.7 — اسم فارسی اندیکاتورها + ضربدر پن‌ها + دیالوگ تنظیمات فیبو ============ */
  function applyFaNames() {
    if (!window.klinecharts || typeof klinecharts.overrideIndicator !== 'function') return;
    var all = IND_MAP.slice();
    (window.RTV_IND_EXTRA || []).forEach(function (it) {
      if (!all.some(function (m) { return m[0] === it[0]; })) all.push(it);
    });
    all.forEach(function (it) {
      try { klinecharts.overrideIndicator({ name: it[0], shortName: it[2] }); } catch (e) {}
    });
  }

  /* ضربدر بستن پن اندیکاتور (سمت راست هر پن — مثل نهایت‌نگر) */
  window.rvSyncPaneCloseBtns = function () {
    var box = document.getElementById('rvChartBox');
    if (!box) return;
    var host = document.getElementById('rvPaneCloseBtns');
    if (!host) { host = document.createElement('div'); host.id = 'rvPaneCloseBtns'; box.appendChild(host); }
    host.innerHTML = '';
    var names = (typeof rvIndsAdded !== 'undefined') ? rvIndsAdded.slice() : [];
    if (names.indexOf('VOL') === -1) names.push('VOL'); // پن حجم پیشفرض
    names.slice().reverse().forEach(function (nm, k) {
      var b = document.createElement('button');
      b.className = 'rv-pane-close';
      b.title = 'بستن ' + nm;
      b.textContent = '✕';
      b.style.bottom = (26 + k * 100 + 50 - 12) + 'px';
      b.onclick = function (ev) {
        ev.stopPropagation();
        if (typeof rvIndToggle === 'function') rvIndToggle(nm);
        setTimeout(function () { rvSyncPaneCloseBtns(); }, 300);
      };
      host.appendChild(b);
    });
  };

  /* v8.9 — رنگِ اختصاصیِ هر سطح؛ کلید می‌تواند ضریب (0.786) یا درصدِ قدیمی ('78.6') باشد */
  window._rvSetLevelColor = function (key, val) {
    var last = (typeof _rvPopOverlay === 'function') ? _rvPopOverlay() : null;
    if (!last || typeof window.rvFibNormalizeLevels !== 'function') return;
    var c = window._rvFibKeyToCoeff(key);
    if (!isFinite(c)) return;
    var levels = window.rvFibNormalizeLevels(last.styles || {}).slice();
    var hit = null;
    for (var i = 0; i < levels.length; i++) if (Math.abs(levels[i].coeff - c) < 1e-9) { hit = levels[i]; break; }
    if (hit) hit.color = val; else levels.push({ coeff: c, color: val, visible: true });
    if (typeof _rvSetFibLevels === 'function') _rvSetFibLevels(levels);
  };

  /* ---------- قطعه‌های سازندهٔ پنجره ---------- */
  var RFD_PRESETS = [
    { id: '', label: 'قالب', coeffs: null },
    { id: 'std', label: 'استاندارد (۲۳ سطح)', coeffs: null },
    { id: 'ret', label: 'فقط بازگشتی ۰ تا ۱', coeffs: [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1] },
    { id: 'ext', label: 'فقط امتدادی ۱ تا .۷۶۴',
      coeffs: [1, 1.272, 1.414, 1.618, 2, 2.272, 2.414, 2.618, 3, 3.272, 3.414, 3.618, 4, 4.236, 4.414, 4.618, 4.764] },
    { id: 'deep', label: 'عمیق', coeffs: [0, 0.5, 0.618, 0.786, 1, 1.272, 1.414, 1.618, 2, 2.618, 3.618, 4.236, 4.764] }
  ];
  window.RFD_PRESETS = RFD_PRESETS;

  function rfdStyleSel(id, cur) {
    return '<select id="' + id + '">' +
      '<option value="solid"' + (cur === 'solid' ? ' selected' : '') + '>ممتد</option>' +
      '<option value="dashed"' + (cur === 'dashed' ? ' selected' : '') + '>خط‌چین</option>' +
      '<option value="dotted"' + (cur === 'dotted' ? ' selected' : '') + '>نقطه‌چین</option></select>';
  }
  function rfdSizeSel(id, cur) {
    var o = '';
    for (var n = 1; n <= 5; n++) o += '<option value="' + n + '"' + ((+cur || 1) === n ? ' selected' : '') + '>' + n + '</option>';
    return '<select id="' + id + '">' + o + '</select>';
  }
  /* هر ردیف = چک‌باکسِ فعال‌سازی + ورودیِ متنیِ ضریب + انتخابگرِ رنگ */
  function rfdGridHtml(levels) {
    return (levels || []).map(function (L, i) {
      return '<div class="rfd-cell' + (L.visible === false ? ' off' : '') + '">' +
        '<input type="checkbox" class="rfd-cb" data-i="' + i + '"' + (L.visible === false ? '' : ' checked') + '>' +
        '<input type="text" class="rfd-num" data-i="' + i + '" dir="ltr" inputmode="decimal" spellcheck="false" value="' + L.coeff + '">' +
        '<input type="color" class="rfd-col" data-i="' + i + '" title="رنگ سطح" value="' + (L.color || '#787B86') + '">' +
        '</div>';
    }).join('');
  }
  function rfdRow(id, label, checked, extra) {
    return '<div class="rfd-row"><label class="rfd-ck"><input type="checkbox" id="' + id + '"' +
      (checked ? ' checked' : '') + '> ' + label + '</label>' + (extra || '<span class="rfd-pad"></span>') + '</div>';
  }
  function rfdCardHtml(d) {
    return '<div class="rfd-card rfd-card--v2">' +
      '<div class="rfd-head"><b>تنظیمات فیبوناچی</b><button type="button" id="rfdX" title="بستن">✕</button></div>' +
      '<div class="rfd-body">' +
        '<div class="rfd-sec">خط</div>' +
        '<div class="rfd-row"><label class="rfd-ck"><input type="checkbox" id="rfdTrend"' + (d.trend ? ' checked' : '') + '> خط روند</label>' +
          '<span class="rfd-grp"><input type="color" id="rfdLineColor" value="' + d.lineColor + '" title="رنگ خط اصلی">' +
          rfdSizeSel('rfdLineSize', d.lineSize) + rfdStyleSel('rfdLineStyle', d.lineStyle) + '</span></div>' +
        '<div class="rfd-row"><span class="rfd-lbl">خط سطوح</span><span class="rfd-grp">' +
          rfdSizeSel('rfdLvSize', d.lvSize) + rfdStyleSel('rfdLvStyle', d.lvStyle) + '</span></div>' +
        rfdRow('rfdExtL', 'امتداد از چپ', d.extendLeft) +
        rfdRow('rfdExtR', 'امتداد از راست', d.extendRight) +
        '<div class="rfd-sec">سطوح</div>' +
        '<div class="rfd-grid" id="rfdGrid">' + rfdGridHtml(d.levels) + '</div>' +
        '<div class="rfd-sec">نمایش</div>' +
        rfdRow('rfdOne', 'استفاده از یک رنگ', d.oneColor,
          '<input type="color" id="rfdOneVal" value="' + d.oneColorValue + '">') +
        rfdRow('rfdBg', 'پس‌زمینه', d.fills,
          '<span class="rfd-grp"><input type="range" id="rfdAlpha" min="0" max="100" step="1" value="' +
          Math.round(d.bgOpacity * 100) + '"><span class="rfd-av" id="rfdAlphaV">' + Math.round(d.bgOpacity * 100) + '٪</span></span>') +
        rfdRow('rfdRev', 'معکوس', d.reverse) +
        rfdRow('rfdPrice', 'قیمت‌ها', d.showPrices) +
        rfdRow('rfdPct', 'سطوح', d.showPercents,
          '<select id="rfdPctMode"><option value="percent"' + (d.pctMode === 'percent' ? ' selected' : '') +
          '>درصدها</option><option value="coeff"' + (d.pctMode !== 'percent' ? ' selected' : '') + '>اعداد</option></select>') +
      '</div>' +
      '<div class="rfd-foot">' +
        '<select id="rfdPreset">' + RFD_PRESETS.map(function (p) {
          return '<option value="' + p.id + '"' + (p.id ? '' : ' selected') + '>' + p.label + '</option>';
        }).join('') + '</select>' +
        '<span class="rfd-spacer"></span>' +
        '<button type="button" class="rfd-btn" id="rfdCancel">لغو</button>' +
        '<button type="button" class="rfd-btn rfd-btn--ok" id="rfdOk">تایید</button>' +
      '</div>' +
      '</div>';
  }


  /* ============ v8.9 — پنجرهٔ تنظیمات فیبوناچی (بازنویسی کامل) ============
     الگو: پنجرهٔ «فیبو اکسپنشن» نهایت‌نگر — گریدِ دوسوتونهٔ سطوح با
     چک‌باکس + ورودیِ متنیِ ضریب + انتخابگرِ رنگِ اختصاصی، امتداد چپ/راست،
     معکوس، اسلایدرِ شفافیتِ پس‌زمینه، نمایشِ قیمت/درصد، بدنهٔ اسکرول‌شونده
     و دکمهٔ تایید/لغو.
     رفتار: binding دوطرفه — هر تغییر فوراً روی آرایهٔ سطوحِ overlay نوشته و
     چارت re-render می‌شود؛ «لغو» snapshotِ لحظهٔ باز شدن را برمی‌گرداند. */
  window.rvOpenFibDlg = function () {
    var last = (typeof _rvPopOverlay === 'function') ? _rvPopOverlay() : null;
    if (!last || typeof window.rvFibMergeLevels !== 'function') return;
    var targetId = last.id;
    window._rvPopOverlayId = targetId;
    var snapshot = JSON.parse(JSON.stringify(last.styles || {}));
    var st0 = snapshot, lineSt0 = st0.line || {}, lvLine0 = st0.levelLine || {};
    var draft = {
      levels: window.rvFibMergeLevels(st0),
      trend: st0.trend !== false,
      lineColor: lineSt0.color || '#2d8cf0',
      lineSize: lineSt0.size || 1,
      lineStyle: lineSt0.style || 'solid',
      lvSize: lvLine0.size || lineSt0.size || 1,
      lvStyle: lvLine0.style || lineSt0.style || 'solid',
      extendLeft: !!st0.extendLeft,
      extendRight: !!st0.extendRight,
      oneColor: !!st0.oneColor,
      oneColorValue: st0.oneColorValue || '#2962ff',
      fills: st0.fills !== false,
      bgOpacity: (typeof st0.bgOpacity === 'number') ? st0.bgOpacity : 0.10,
      reverse: !!st0.reverse,
      showPrices: st0.showPrices !== false,
      showPercents: st0.showPercents !== false,
      pctMode: st0.pctMode || 'coeff'
    };
    var old = document.getElementById('rvFibDlg');
    if (old) old.remove();
    var dlg = document.createElement('div');
    dlg.id = 'rvFibDlg';
    dlg.innerHTML = rfdCardHtml(draft);
    document.body.appendChild(dlg);
    var $ = function (id) { return dlg.querySelector('#' + id); };
    var grid = $('rfdGrid');

    function patchOf() {
      return {
        trend: draft.trend,
        line: {
          color: draft.lineColor, size: +draft.lineSize || 1, style: draft.lineStyle,
          dashedValue: draft.lineStyle === 'dashed' ? [4, 3] : draft.lineStyle === 'dotted' ? [1, 2] : []
        },
        levelLine: { size: +draft.lvSize || 1, style: draft.lvStyle },
        fibLevels: draft.levels.map(function (L) {
          return { coeff: L.coeff, color: L.color, visible: L.visible !== false };
        }),
        extendLeft: draft.extendLeft, extendRight: draft.extendRight,
        reverse: draft.reverse, fills: draft.fills, bgOpacity: draft.bgOpacity,
        oneColor: draft.oneColor, oneColorValue: draft.oneColorValue,
        showPrices: draft.showPrices, showPercents: draft.showPercents, pctMode: draft.pctMode,
        labels: draft.showPrices || draft.showPercents
      };
    }
    function applyLive() {
      window._rvPopOverlayId = targetId;
      if (typeof _rvApplyStyles === 'function') _rvApplyStyles(patchOf());
    }
    function close() {
      document.removeEventListener('keydown', onKey, true);
      if (dlg.parentNode) dlg.parentNode.removeChild(dlg);
    }
    function revert() {
      window._rvPopOverlayId = targetId;
      if (typeof _rvReplaceStyles === 'function') _rvReplaceStyles(snapshot);
      close();
    }
    function commit() {
      applyLive();
      if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
      close();
      if (typeof rvToast === 'function') rvToast('✓ تنظیمات فیبوناچی ذخیره شد');
    }
    function onKey(ev) { if (ev.key === 'Escape') { ev.preventDefault(); revert(); } }
    document.addEventListener('keydown', onKey, true);

    /* ---- خط ---- */
    $('rfdTrend').onchange = function () { draft.trend = this.checked; applyLive(); };
    $('rfdLineColor').oninput = function () { draft.lineColor = this.value; applyLive(); };
    $('rfdLineSize').onchange = function () { draft.lineSize = this.value; applyLive(); };
    $('rfdLineStyle').onchange = function () { draft.lineStyle = this.value; applyLive(); };
    $('rfdLvSize').onchange = function () { draft.lvSize = this.value; applyLive(); };
    $('rfdLvStyle').onchange = function () { draft.lvStyle = this.value; applyLive(); };
    /* ---- امتداد ---- */
    $('rfdExtL').onchange = function () { draft.extendLeft = this.checked; applyLive(); };
    $('rfdExtR').onchange = function () { draft.extendRight = this.checked; applyLive(); };
    /* ---- نمایش ---- */
    $('rfdOne').onchange = function () { draft.oneColor = this.checked; applyLive(); };
    $('rfdOneVal').oninput = function () { draft.oneColorValue = this.value; applyLive(); };
    $('rfdBg').onchange = function () { draft.fills = this.checked; applyLive(); };
    $('rfdAlpha').oninput = function () {
      draft.bgOpacity = (+this.value || 0) / 100;
      var lab = $('rfdAlphaV'); if (lab) lab.textContent = this.value + '٪';
      applyLive();
    };
    $('rfdRev').onchange = function () { draft.reverse = this.checked; applyLive(); };
    $('rfdPrice').onchange = function () { draft.showPrices = this.checked; applyLive(); };
    $('rfdPct').onchange = function () { draft.showPercents = this.checked; applyLive(); };
    $('rfdPctMode').onchange = function () { draft.pctMode = this.value; applyLive(); };

    /* ---- گریدِ سطوح: چک‌باکس / ضریبِ قابل‌ویرایش / رنگِ اختصاصی ---- */
    grid.addEventListener('change', function (ev) {
      var t = ev.target;
      if (!t || !t.dataset || t.dataset.i == null) return;
      var L = draft.levels[+t.dataset.i];
      if (!L) return;
      if (t.classList.contains('rfd-cb')) {
        L.visible = t.checked;
        if (t.closest) { var cell = t.closest('.rfd-cell'); if (cell) cell.classList.toggle('off', !t.checked); }
      } else if (t.classList.contains('rfd-col')) {
        L.color = t.value;
      } else return;
      applyLive();
    });
    grid.addEventListener('input', function (ev) {
      var t = ev.target;
      if (!t || !t.classList || !t.classList.contains('rfd-num')) return;
      var L = draft.levels[+t.dataset.i];
      if (!L) return;
      var v = (typeof window._rvFibParseCoeff === 'function')
        ? window._rvFibParseCoeff(t.value) : window._rvFibKeyToCoeff(t.value);
      if (!isFinite(v)) return;                 // حینِ تایپ؛ مقدارِ قبلی می‌ماند
      L.coeff = v;
      applyLive();
    });
    /* بلور/Enter: مقدارِ ناقص («۰.») به عددِ درستِ قبلی برمی‌گردد تا ورودیِ
       نیمه‌کاره روی چارت یک سطحِ سرگردان نسازد. */
    grid.addEventListener('change', function (ev) {
      var t = ev.target;
      if (!t || !t.classList || !t.classList.contains('rfd-num')) return;
      var L = draft.levels[+t.dataset.i];
      if (!L) return;
      t.value = String(L.coeff);
    });

    /* ---- قالب‌های آماده ---- */
    $('rfdPreset').onchange = function () {
      var want = this.value, p = null, i;
      for (i = 0; i < RFD_PRESETS.length; i++) if (RFD_PRESETS[i].id === want) p = RFD_PRESETS[i];
      var all = window.rvFibMergeLevels({});
      if (!p || !p.coeffs) draft.levels = all;
      else draft.levels = p.coeffs.map(function (c) {
        for (var j = 0; j < all.length; j++)
          if (Math.abs(all[j].coeff - c) < 1e-9) return { coeff: c, color: all[j].color, visible: true };
        return { coeff: c, color: '#787B86', visible: true };
      });
      grid.innerHTML = rfdGridHtml(draft.levels);
      applyLive();
      this.value = '';
    };

    /* ---- فوتر: تایید = ذخیره، لغو = بازگردانیِ وضعیتِ قبلی ---- */
    $('rfdOk').onclick = commit;
    $('rfdCancel').onclick = revert;
    $('rfdX').onclick = revert;
    dlg.addEventListener('mousedown', function (ev) { if (ev.target === dlg) revert(); });
  };

  /* ============ 9) init ============ */
  function boot() {
    installOverlays();
    try { applyFaNames(); } catch (e) {}
    try { setInterval(function () { if (typeof rvSyncPaneCloseBtns === 'function') rvSyncPaneCloseBtns(); }, 1500); } catch (e) {}
    extendMapping();
    if (typeof rvRailInit === 'function') {
      // فلایاوت‌های جدید: جایگزین rvRailInit قدیمی
      var oldInit = rvRailInit;
      rvRailInit = function () { window.rtvBuildRail(); bindEraser(); };
    } else {
      window.rtvBuildRail(); bindEraser();
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/* =====================================================================
   v8.1 — پاریتی عمیقتر با نهایت‌نگر:
   1) فیکس ابزارهای خراب (دایره/کمان) با overlay سفارشی
   2) اندیکاتورهای سفارشی: WMA/VWAP/ATR/MFI/ADX/StochRSI (+BBI در منو)
   3) پاپآپ تنظیمات رسم به سبک TV (نوار فشرده: ⚙ 🔒 🗑 ✕ + بدنه جمعشو)
   4) نوار تایم‌فریم پایین چارت (مثل نهایت‌نگر)
   5) تاریخ شمسی + بهروزرسانی OHLC با هاور روی کندل
   ===================================================================== */
(function () {
  'use strict';

  /* ---------- 1) دایره و کمان سفارشی ---------- */
  function fixBrokenTools() {
    if (!window.klinecharts) return;
    var K = window.klinecharts;
    // دایره: نقطه اول مرکز، نقطه دوم روی محیط
    // v8.8-FIX-5a — قبلاً r=|dx| و r2=|dy| بود → هر دایره‌ای که کاربر می‌کشید بیضی می‌شد
    function arcR(v) { return Math.max(2, v); }
    K.registerOverlay({ name: 'circle-tool', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = e.coordinates || []; if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var R = arcR(Math.hypot(b.x - a.x, b.y - a.y));   // شعاع = فاصلهٔ اقلیدسی مرکز تا نقطهٔ دوم
      return [{ type: 'arc', attrs: { x: a.x, y: a.y, r: R, r2: R, startAngle: 0, endAngle: Math.PI * 2 }, styles: { style: 'stroke', borderColor: '#2962ff', borderSize: 1 } }];
    }});
    // کمان: نیمدایره بالایی از A تا B
    // v8.8-FIX-5b — قبلاً بازهٔ زاویه ثابت [PI, 2PI] بود؛ کمان همیشه «تخت/افقی» می‌ماند
    // و تا وقتی محور AB افقی نبود نقطهٔ B را هرگز وصل نمی‌کرد. حالا بازه روی محور AB می‌چرخد.
    K.registerOverlay({ name: 'arc-tool', totalStep: 3, lock: true, createPointFigures: function (e) {
      var c = e.coordinates || []; if (c.length < 2) return [];
      var a = c[0], b = c[1];
      var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
      var r = arcR(Math.hypot(b.x - a.x, b.y - a.y) / 2);
      var th = Math.atan2(b.y - a.y, b.x - a.x);        // زاویهٔ محور A→B
      return [{ type: 'arc', attrs: { x: mx, y: my, r: r, r2: r, startAngle: th, endAngle: th + Math.PI }, styles: { style: 'stroke', borderColor: '#2962ff', borderSize: 1 } }];
    }});
    // نگاشت ابزارها به نامهای جدید
    if (window.RTV_TOOL_NAMES) {
      RTV_TOOL_NAMES['circle'] = 'circle-tool';
      RTV_TOOL_NAMES['arc'] = 'arc-tool';
    }
    // نام فارسی ابزارهای جدید (برای عنوان پاپآپ)
    if (window.RV_TOOL_FA) {
      RV_TOOL_FA['circle-tool'] = 'دایره';
      RV_TOOL_FA['arc-tool'] = 'کمان';
    }
  }

  /* ---------- 2) اندیکاتورهای سفارشی ---------- */
  function addIndicators() {
    if (!window.klinecharts) return;
    var K = window.klinecharts;
    function reg(def) { try { K.registerIndicator(def); } catch (e) { console.warn('[ind]', def.name, e); } }

    reg({ name: 'WMA', shortName: 'WMA(9)', calcParams: [9],
      figures: [{ key: 'wma', title: 'WMA: ', type: 'line' }],
      calc: function (dl, ind) {
        var p = ind.calcParams[0], out = [];
        dl.forEach(function (d, i) {
          if (i < p - 1) { out.push({}); return; }
          var s = 0, w = 0;
          for (var j = 0; j < p; j++) { var wt = p - j; s += dl[i - j].close * wt; w += wt; }
          out.push({ wma: w ? s / w : null });
        });
        return out;
      }});

    reg({ name: 'VWAP', shortName: 'VWAP', calcParams: [],
      figures: [{ key: 'vwap', title: 'VWAP: ', type: 'line' }],
      calc: function (dl) {
        var cp = 0, cv = 0, out = [];
        dl.forEach(function (d) {
          var tp = (d.high + d.low + d.close) / 3;
          var v = d.volume || 0;
          cp += tp * v; cv += v;
          out.push({ vwap: cv ? cp / cv : null });
        });
        return out;
      }});

    reg({ name: 'ATR', shortName: 'ATR(14)', calcParams: [14],
      figures: [{ key: 'atr', title: 'ATR: ', type: 'line' }],
      calc: function (dl, ind) {
        var p = ind.calcParams[0], out = [], trs = [];
        dl.forEach(function (d, i) {
          if (!i) { out.push({}); trs.push(d.high - d.low); return; }
          var tr = Math.max(d.high - d.low, Math.abs(d.high - dl[i - 1].close), Math.abs(d.low - dl[i - 1].close));
          trs.push(tr);
          if (i < p) { out.push({}); return; }
          var s = 0; for (var j = i - p + 1; j <= i; j++) s += trs[j];
          out.push({ atr: s / p });
        });
        return out;
      }});

    reg({ name: 'MFI', shortName: 'MFI(14)', calcParams: [14],
      figures: [{ key: 'mfi', title: 'MFI: ', type: 'line' }],
      calc: function (dl, ind) {
        var p = ind.calcParams[0], out = [];
        dl.forEach(function (d, i) {
          if (i < p) { out.push({}); return; }
          var pos = 0, neg = 0;
          for (var j = i - p + 1; j <= i; j++) {
            var tp = (dl[j].high + dl[j].low + dl[j].close) / 3;
            var tpPrev = (dl[j - 1].high + dl[j - 1].low + dl[j - 1].close) / 3;
            var mf = tp * (dl[j].volume || 0);
            if (tp > tpPrev) pos += mf; else if (tp < tpPrev) neg += mf;
          }
          out.push({ mfi: neg === 0 ? 100 : 100 - 100 / (1 + pos / neg) });
        });
        return out;
      }});

    reg({ name: 'ADX', shortName: 'ADX(14)', calcParams: [14],
      figures: [{ key: 'adx', title: 'ADX: ', type: 'line' }, { key: 'pdi', title: '+DI: ', type: 'line' }, { key: 'mdi', title: '-DI: ', type: 'line' }],
      calc: function (dl, ind) {
        var p = ind.calcParams[0], out = [], dxs = [];
        dl.forEach(function (d, i) {
          if (i < 2 * p) { out.push({}); dxs.push(null); return; }
          var spdm = 0, smdm = 0, str = 0;
          for (var j = i - p + 1; j <= i; j++) {
            var up = dl[j].high - dl[j - 1].high, dn = dl[j - 1].low - dl[j].low;
            spdm += (up > dn && up > 0) ? up : 0;
            smdm += (dn > up && dn > 0) ? dn : 0;
            str += Math.max(dl[j].high - dl[j].low, Math.abs(dl[j].high - dl[j - 1].close), Math.abs(dl[j].low - dl[j - 1].close));
          }
          var pdi = str ? 100 * spdm / str : 0, mdi = str ? 100 * smdm / str : 0;
          var dx = (pdi + mdi) ? 100 * Math.abs(pdi - mdi) / (pdi + mdi) : 0;
          dxs.push(dx);
          var sdx = 0; for (var k = dxs.length - p; k < dxs.length; k++) sdx += dxs[k] || 0;
          out.push({ adx: sdx / p, pdi: pdi, mdi: mdi });
        });
        return out;
      }});

    reg({ name: 'StochRSI', shortName: 'StochRSI(14)', calcParams: [14],
      figures: [{ key: 'k', title: 'K: ', type: 'line' }, { key: 'd', title: 'D: ', type: 'line' }],
      calc: function (dl, ind) {
        var p = ind.calcParams[0], out = [], rsis = [];
        dl.forEach(function (d, i) {
          if (i < 2 * p + 3) { out.push({}); rsis.push(null); return; }
          var g = 0, l = 0;
          for (var j = i - p + 1; j <= i; j++) { var ch = dl[j].close - dl[j - 1].close; if (ch > 0) g += ch; else l -= ch; }
          var rsi = l === 0 ? 100 : 100 - 100 / (1 + g / l);
          rsis.push(rsi);
          var mn = Infinity, mx = -Infinity;
          for (var q = rsis.length - p; q < rsis.length; q++) { var rv2 = rsis[q]; if (rv2 != null) { if (rv2 < mn) mn = rv2; if (rv2 > mx) mx = rv2; } }
          var k = (mx - mn) ? (rsi - mn) / (mx - mn) * 100 : 50;
          var d3 = null;
          if (out.length >= 2 && out[out.length - 1].k != null && out[out.length - 2].k != null)
            d3 = (out[out.length - 2].k + out[out.length - 1].k + k) / 3;
          out.push({ k: k, d: d3 });
        });
        return out;
      }});

    // ورود به لیست کلی اندیکاتورها (برای حذف همه و...)
    if (window.RTV_IND_LIST && RTV_IND_LIST.indexOf) {
      ['WMA', 'VWAP', 'ATR', 'MFI', 'ADX', 'StochRSI', 'BBI'].forEach(function (n) {
        if (RTV_IND_LIST.indexOf(n) < 0) RTV_IND_LIST.push(n);
      });
    }
    // ردیفهای منوی اندیکاتور (قبل از اولین ساخت دیالوگ)
    window.RTV_IND_EXTRA = [
      ['WMA', 'Weighted Moving Average', 'میانگین وزنی'],
      ['BBI', 'Bull And Bear Index', 'شاخص گاو و خرس'],
      ['VWAP', 'Volume Weighted Average Price', 'میانگین وزنی حجمی'],
      ['ATR', 'Average True Range', 'دامنه واقعی میانگین'],
      ['MFI', 'Money Flow Index', 'شاخص جریان پول'],
      ['ADX', 'Average Directional Index', 'میانگین شاخص جهت'],
      ['StochRSI', 'Stochastic RSI', 'استوکاستیک آراس‌آی']
    ];
  }

  /* ---------- 3-ب) اولویت لایه‌ها: Move Up / Move Down ----------
     KLineCharts v10 رسم‌ها را با zLevel صعودی مرتب می‌کند و به همان ترتیب
     روی هم می‌کشد؛ پس «بالا بردن» = zLevel بیشتر. خودِ
     overrideOverlay({id, zLevel}) هم _sortOverlays() را می‌زند و هم pane را
     redraw می‌کند (در باندل: shouldUpdate() → {sort:true} → _sortOverlays()).
     چون همهٔ رسم‌ها با zLevel=0 متولد می‌شوند، ابتدا کل مجموعه به ۰..n-1
     نرمال می‌شود وگرنه «جابه‌جایی» بین دو مقدار برابر بی‌اثر می‌ماند. */
  function rvLayerShift(dir) {
    if (typeof rv === 'undefined' || !rv.chart) return;
    var last = (typeof _rvPopOverlay === 'function') ? _rvPopOverlay() : null;
    if (!last) return;
    var all = [];
    try {
      all = rv.chart.getOverlays().filter(function (o) {
        return o && o.id && !(o.isDrawing && o.isDrawing());
      });
    } catch (e) { return; }
    all.sort(function (a, b) { return (a.zLevel || 0) - (b.zLevel || 0); });
    var i = -1;
    all.forEach(function (o, k) { if (o.id === last.id) i = k; });
    var j = i + dir;
    if (i < 0 || j < 0 || j >= all.length) {
      if (typeof rvToast === 'function')
        rvToast(dir > 0 ? 'این رسم از همه بالاتر است' : 'این رسم از همه پایین‌تر است');
      return;
    }
    var lv = all.map(function (_o, k) { return k; });
    var tmp = lv[i]; lv[i] = lv[j]; lv[j] = tmp;
    all.forEach(function (o, k) {
      try { rv.chart.overrideOverlay({ id: o.id, zLevel: lv[k] }); } catch (e) {}
    });
    if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
    if (typeof rvToast === 'function') rvToast(dir > 0 ? '▲ یک لایه بالا' : '▼ یک لایه پایین');
  }

  /* ---------- 3) پاپآپ رسم به سبک TV ---------- */
  function restyleDrawPopup() {
    if (typeof window.rvShowDrawFloat !== 'function') return;
    window.rvShowDrawFloat = function (overlayId) {
      if (overlayId) window._rvPopOverlayId = overlayId;
      var last = (typeof _rvPopOverlay === 'function') ? _rvPopOverlay() : null;
      if (!last) return;
      window._rvPopOverlayId = last.id;
      var pop = rvEl('rvDrawFloat');
      if (!pop) return;
      pop.style.display = 'block';
      var nm = last.name || '', st = last.styles || {}, lineSt = st.line || {};
      var rows = '';
      if (nm === 'fibonacciLine' || nm === 'fib-extension') {
        var lvOn = st.levels || {};
        rows += '<div class="dpr dpr-lv"><span>سطوح</span><div>';
        ['100', '78.6', '61.8', '50', '38.2', '23.6', '0'].forEach(function (p) {
          var ck = lvOn[p] === false ? '' : ' checked';
          rows += '<label class="dplv"><input type="checkbox"' + ck + ' onchange="rvFibToggleLevel(\'' + p + '\', this.checked)">' + p + '</label>';
        });
        rows += '</div></div>';
        rows += '<div class="dpr"><span>برچسب‌ها</span><input type="checkbox" ' + (st.labels === false ? '' : 'checked') + ' onchange="_rvApplyStyles({labels:this.checked})"></div>';
      }
      if (nm === 'rect' || nm === 'box' || nm === 'ellipse' || nm === 'circle-tool' || nm === 'triangle') {
        rows += '<div class="dpr"><span>پس‌زمینه</span><input type="checkbox" ' + (st.fill && st.fill.show ? 'checked' : '') + ' onchange="_rvApplyStyles({fill:{show:this.checked,color:\'rgba(45,140,240,.12)\'}})"></div>';
      }
      if (nm === 'simpleAnnotation' || nm === 'simpleTag' || nm === 'text-absolute' || nm === 'note-tool' || nm === 'note-absolute') {
        rows += '<div class="dpr"><span>متن</span><input type="text" value="' + ((st.text && st.text.text) || '') + '" onchange="_rvApplyStyles({text:{text:this.value}})" placeholder="یادداشت..."></div>';
      }
      if (nm.indexOf('Line') >= 0 || nm === 'segment' || nm === 'rayLine' || nm === 'ruler' || nm === 'arrow' || nm === 'cross-line' || nm === 'info-line') {
        var cs = lineSt.style || 'solid';
        rows += '<div class="dpr"><span>خط</span><select onchange="_rvApplyStyles({line:{style:this.value,dashedValue:this.value===\'dashed\'?[4,3]:this.value===\'dotted\'?[1,2]:[]}})">' +
          '<option value="solid"' + (cs === 'solid' ? ' selected' : '') + '>ممتد</option>' +
          '<option value="dashed"' + (cs === 'dashed' ? ' selected' : '') + '>خط‌چین</option>' +
          '<option value="dotted"' + (cs === 'dotted' ? ' selected' : '') + '>نقطه‌چین</option></select></div>';
      }
      var locked = !!last.lock;
      /* v8.5: قرص شناور مثل نهایت‌نگر — رنگ | ضخامت | تنظیمات | قفل | حذف | بستن */
      pop.innerHTML =
        '<div class="tv-pop">' +
        '<div class="draw-pill">' +
        '<input type="color" class="dp-color" title="رنگ" value="' + (lineSt.color || '#2d8cf0') + '" onchange="_rvApplyStyles({line:{color:this.value}})">' +
        '<button type="button" class="dp-width" title="ضخامت" data-w="' + (lineSt.size || 1) + '" onclick="var s=(+this.dataset.w)%4+1;this.dataset.w=s;this.textContent=s+\'px\';_rvApplyStyles({line:{size:s}})">' + (lineSt.size || 1) + 'px</button>' +
        '<button type="button" data-act="gear" title="تنظیمات بیشتر">⚙</button>' +
        '<button type="button" data-act="up" title="یک لایه بالا (Move Up)">▲</button>' +
        '<button type="button" data-act="down" title="یک لایه پایین (Move Down)">▼</button>' +
        '<button type="button" data-act="lock" title="' + (locked ? 'باز کردن قفل' : 'قفل رسم') + '">' + (locked ? '🔒' : '🔓') + '</button>' +
        '<button type="button" data-act="del" title="حذف">🗑</button>' +
        '<button type="button" data-act="close" title="بستن">✕</button>' +
        '</div>' +
        '<div class="tv-pop-body" style="display:none">' + rows + '</div></div>';
      pop.querySelector('[data-act="gear"]').onclick = function () {
        if (nm === 'fibonacciLine' || nm === 'fib-extension') { if (typeof rvOpenFibDlg === 'function') { rvOpenFibDlg(); return; } }
        var b = pop.querySelector('.tv-pop-body');
        b.style.display = (b.style.display === 'none') ? 'block' : 'none';
      };
      pop.querySelector('[data-act="lock"]').onclick = function () {
        var nl = !last.lock;
        try {
          rv.chart.overrideOverlay({ id: last.id, lock: nl });
          last.lock = nl;
          this.textContent = nl ? '🔒' : '🔓';
          this.title = nl ? 'باز کردن قفل' : 'قفل رسم';
          if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
        } catch (e) {}
      };
      pop.querySelector('[data-act="up"]').onclick = function () { rvLayerShift(1); };
      pop.querySelector('[data-act="down"]').onclick = function () { rvLayerShift(-1); };
      pop.querySelector('[data-act="del"]').onclick = function () { if (typeof rvDrawDelete === 'function') rvDrawDelete(); };
      pop.querySelector('[data-act="close"]').onclick = function () { if (typeof rvDrawFloatClose === 'function') rvDrawFloatClose(); };
    };
  }

  /* ---------- 4) نوار تایم‌فریم پایین چارت ---------- */
  function buildTfBar() {
    var main = document.querySelector('#techView .tv5-main');
    if (!main || main.querySelector('.rv-tfbar')) return;
    var bar = document.createElement('div');
    bar.className = 'rv-tfbar';
    [['D', '1D', 'روزانه'], ['W', '1W', 'هفتگی'], ['M', '1M', 'ماهانه']].forEach(function (tf) {
      var b = document.createElement('button');
      b.textContent = tf[1];
      b.title = tf[2];
      b.dataset.itv = tf[0];
      b.onclick = function () { rvSetItv(tf[0], b); };
      bar.appendChild(b);
    });
    main.appendChild(bar);
    syncTfBar();
    // sync با تغییر تایم‌فریم (از هر جایی)
    if (!window.rvSetItv.__tfWrapped) {
      var orig = window.rvSetItv;
      window.rvSetItv = function (itv, btn) {
        var r = orig.apply(this, arguments);
        syncTfBar(itv);
        return r;
      };
      window.rvSetItv.__tfWrapped = true;
    }
  }
  function syncTfBar(itv) {
    var cur = itv || (typeof rv !== 'undefined' && rv.itv) || 'D';
    document.querySelectorAll('.rv-tfbar button').forEach(function (b) {
      b.classList.toggle('on', b.dataset.itv === cur);
    });
    // sync دکمههای بالای هدر هم (باگ قدیمی: همیشه 1D روشن میماند)
    document.querySelectorAll('.tv5-tf[data-itv]').forEach(function (b) {
      b.classList.toggle('on', b.dataset.itv === cur);
    });
    // v8.2: chip تایم‌فریم هدر NN-مانند
    var chip = document.getElementById('nnTfBtn');
    if (chip && chip.firstChild && chip.firstChild.nodeValue) chip.firstChild.nodeValue = cur + ' ';
  }

  /* ---------- 5) هاور: تاریخ شمسی + OHLC زنده ---------- */
  function bindLegendHover() {
    if (typeof rv === 'undefined' || !rv.chart || rv.chart.__lgBound) return;
    var box = rvEl('rvChartBox');
    if (!box) return;
    rv.chart.__lgBound = true;
    // درج span تاریخ قبل از «باز»
    var head = rvEl('rvChartHead');
    var dspan = rvEl('rvLgD');
    if (head && !dspan) {
      dspan = document.createElement('span');
      dspan.id = 'rvLgD';
      dspan.className = 'rv-legend-item rv-legend-date';
      head.insertBefore(dspan, rvEl('rvLgO'));
    }
    function fmtDate(ts) {
      try {
        return new Intl.DateTimeFormat('fa-IR', { calendar: 'persian', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(ts));
      } catch (e) { return ''; }
    }
    function applyAt(idx) {
      var arr = rv.data || [];
      if (!arr.length) return;
      var i = (idx != null && idx >= 0 && idx < arr.length) ? idx : arr.length - 1;
      var c = arr[i];
      var set = function (id, lab, v) { var el = rvEl(id); if (el) el.innerHTML = lab + ': <b>' + _rvFmtNum(v) + '</b>'; };
      set('rvLgO', 'باز', c.open); set('rvLgH', 'سقف', c.high); set('rvLgL', 'کف', c.low);
      set('rvLgC', 'پایانی', c.close); set('rvLgV', 'حجم', c.volume);
      if (dspan) dspan.innerHTML = 'تاریخ: <b>' + fmtDate(c.timestamp) + '</b>';
      var cls = c.close >= c.open ? 'up' : 'down';
      ['rvLgO', 'rvLgH', 'rvLgL', 'rvLgC'].forEach(function (id) {
        var el = rvEl(id); if (el) { el.classList.remove('up', 'down'); el.classList.add(cls); }
      });
    }
    try {
      rv.chart.subscribeAction('onCrosshairChange', function (d) {
        if (!rv.chart || !d) return;
        var idx = null;
        if (d.x != null) {
          try { var px = rv.chart.convertFromPixel({ paneId: d.paneId || 'candle_pane', x: d.x }); idx = px ? px.dataIndex : null; } catch (e) {}
        }
        applyAt(idx);
      });
    } catch (e) {}
    box.addEventListener('mouseleave', function () { applyAt(null); });
  }

  /* ---------- init (poll تا چارت ساخته شود) ---------- */
  function wrapIndToggle() {
    if (typeof window.rvIndToggle !== 'function' || window.rvIndToggle.__wrapped) return;
    var orig = window.rvIndToggle;
    window.rvIndToggle = function () {
      var r = orig.apply(this, arguments);
      // klinecharts با createIndicator استایل چارت را ریست میکند — تم دوباره اعمال شود
      setTimeout(function () { if (typeof rvApplyTheme === 'function') rvApplyTheme(); }, 80);
      return r;
    };
    window.rvIndToggle.__wrapped = true;
  }
  function boot() {
    fixBrokenTools();
    addIndicators();
    restyleDrawPopup();
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      var ok = (typeof rv !== 'undefined' && rv.chart);
      if (ok || tries > 60) {
        clearInterval(t);
        if (ok) { buildTfBar(); bindLegendHover(); }
      }
    }, 500);
    // بعد از تعویض نماد/بازگشایی تب هم دوباره تلاش کن
    setInterval(function () {
      if (typeof rv === 'undefined' || !rv.chart) return;
      wrapIndToggle();
      buildTfBar(); bindLegendHover();
    }, 2000);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/* =====================================================================
   v8.2 — نوار بالای NN-مانند:
   TF-chip منو، نوع نمودار (کندل/توخالی/میله‌ای/خطی)، مقایسه نماد،
   undo/redo رسمها، ذخیره، فول‌اسکرین، عکس از چارت، قالب‌ها
   ===================================================================== */
(function () {
  'use strict';

  /* ---------- پاپآپ عمومی هدر ---------- */
  function nnPop(html, anchor) {
    var pop = document.getElementById('nnPop');
    if (!pop) return null;
    pop.innerHTML = html;
    pop.style.display = 'block';
    var r = anchor.getBoundingClientRect();
    pop.style.top = (r.bottom + 6) + 'px';
    var pw = pop.offsetWidth || 200;
    var left = r.left + r.width / 2 - pw / 2;
    left = Math.max(8, Math.min(left, window.innerWidth - pw - 8));
    pop.style.left = left + 'px';
    return pop;
  }
  function nnPopClose() {
    var pop = document.getElementById('nnPop');
    if (pop) { pop.style.display = 'none'; pop.innerHTML = ''; }
  }
  function toast(m) { if (typeof rvToast === 'function') rvToast(m); }

  /* ---------- 1) تایم‌فریم chip ---------- */
  function bindTfChip() {
    var btn = document.getElementById('nnTfBtn');
    if (!btn || btn.__bound) return;
    btn.__bound = true;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (document.getElementById('nnPop') && document.getElementById('nnPop').style.display === 'block') { nnPopClose(); return; }
      var cur = (typeof rv !== 'undefined' && rv.itv) || 'D';
      var items = [['D', '1D — روزانه'], ['W', '1W — هفتگی'], ['M', '1M — ماهانه']];
      var html = '<div class="nn-menu">' + items.map(function (it) {
        return '<button data-itv="' + it[0] + '" class="' + (it[0] === cur ? 'on' : '') + '">' + it[1] + (it[0] === cur ? ' ✓' : '') + '</button>';
      }).join('') + '</div>';
      var pop = nnPop(html, btn);
      if (!pop) return;
      pop.querySelectorAll('button[data-itv]').forEach(function (b) {
        b.addEventListener('click', function () {
          if (typeof rvSetItv === 'function') rvSetItv(b.dataset.itv, b);
          updateTfChip(b.dataset.itv);
          nnPopClose();
        });
      });
    });
  }
  function updateTfChip(itv) {
    var btn = document.getElementById('nnTfBtn');
    if (btn) btn.firstChild.nodeValue = itv + ' ';
  }

  /* ---------- 2) نوع نمودار (نامهای v10 این بیلد) ---------- */
  var CANDLE_TYPES = [['candle_solid', 'کندل'], ['candle_stroke', 'کندل توخالی'], ['ohlc', 'میله‌ای (OHLC)'], ['area', 'خطی (ناحیه)']];
  function bindCandleChip() {
    var btn = document.getElementById('nnCandleBtn');
    if (!btn || btn.__bound) return;
    btn.__bound = true;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var popEl = document.getElementById('nnPop');
      if (popEl && popEl.style.display === 'block') { nnPopClose(); return; }
      var cur = (typeof stGet === 'function') ? stGet('techCandleType', 'candle_solid') : 'candle_solid';
      var html = '<div class="nn-menu">' + CANDLE_TYPES.map(function (t) {
        return '<button data-ct="' + t[0] + '" class="' + (t[0] === cur ? 'on' : '') + '">' + t[1] + (t[0] === cur ? ' ✓' : '') + '</button>';
      }).join('') + '</div>';
      var pop = nnPop(html, btn);
      if (!pop) return;
      pop.querySelectorAll('button[data-ct]').forEach(function (b) {
        b.addEventListener('click', function () {
          applyCandleType(b.dataset.ct);
          if (typeof stSet === 'function') stSet('techCandleType', b.dataset.ct);
          nnPopClose();
        });
      });
    });
  }
  function applyCandleType(t) {
    if (typeof rv === 'undefined' || !rv.chart) return;
    if (!t || t === 'candle') t = 'candle_solid'; // نامهای قدیمی → v10
    try { rv.chart.setStyles({ candle: { type: t } }); } catch (e) {}
  }
  function wrapApplyTheme() {
    if (typeof window.rvApplyTheme !== 'function' || window.rvApplyTheme.__ct) return;
    var orig = window.rvApplyTheme;
    window.rvApplyTheme = function () {
      var r = orig.apply(this, arguments);
      setTimeout(function () {
        var t = (typeof stGet === 'function') ? stGet('techCandleType', 'candle') : 'candle';
        if (t !== 'candle') applyCandleType(t);
      }, 30);
      return r;
    };
    window.rvApplyTheme.__ct = true;
  }

  /* ---------- 3) مقایسه نماد ---------- */
  function registerCompareOverlay() {
    if (!window.klinecharts) return;
    try {
      window.klinecharts.registerOverlay({
        name: 'compare-line', totalStep: 2, lock: true, noAction: true,
        createPointFigures: function (e) {
          var c = e.coordinates || []; if (c.length < 2) return [];
          var figs = [];
          for (var i = 1; i < c.length; i++) figs.push({ type: 'line', attrs: { coordinates: [c[i - 1], c[i]] }, styles: { color: '#f59e0b', size: 1.5, style: 'solid' } });
          var p = (e.overlay && e.overlay.points) || [];
          var lbl = (e.overlay.styles && e.overlay.styles.label) || '';
          if (p.length > 1 && lbl) {
            figs.push({ type: 'text', attrs: { x: c[c.length - 1].x + 6, y: c[c.length - 1].y - 4, text: lbl, align: 'left', baseline: 'bottom' }, styles: { style: 'fill', color: '#f59e0b', size: 10, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } });
          }
          return figs;
        }
      });
    } catch (e) {}
  }
  function bindCompare() {
    var btn = document.getElementById('nnCompareBtn');
    if (!btn || btn.__bound) return;
    btn.__bound = true;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var popEl = document.getElementById('nnPop');
      if (popEl && popEl.style.display === 'block') { nnPopClose(); return; }
      var html = '<div class="nn-menu nn-form">' +
        '<div class="nn-form-title">مقایسه با نماد</div>' +
        '<input id="nnCmpSym" placeholder="مثلاً وبگرد یا فولاد" autocomplete="off">' +
        '<button id="nnCmpGo" class="nn-go">رسم خط مقایسه</button>' +
        '<button id="nnCmpDel" class="nn-del">حذف مقایسه</button>' +
        '</div>';
      var pop = nnPop(html, btn);
      if (!pop) return;
      var inp = pop.querySelector('#nnCmpSym');
      inp.focus();
      pop.querySelector('#nnCmpGo').addEventListener('click', function () { doCompare(inp.value.trim()); nnPopClose(); });
      inp.addEventListener('keydown', function (ev) { if (ev.key === 'Enter') { doCompare(inp.value.trim()); nnPopClose(); } });
      pop.querySelector('#nnCmpDel').addEventListener('click', function () {
        if (typeof rv !== 'undefined' && rv.chart) { rv.chart.removeOverlay({ name: 'compare-line' }); toast('مقایسه حذف شد'); if (typeof rvSaveOverlays === 'function') rvSaveOverlays(); }
        nnPopClose();
      });
    });
  }
  async function doCompare(sym) {
    if (!sym || typeof rv === 'undefined' || !rv.chart || !rv.sym) return;
    if (sym === rv.sym) { toast('نماد مقایسه با نماد اصلی یکی است'); return; }
    try {
      toast('در حال دریافت ' + sym + ' ...');
      var res = await rvFetch(sym);
      if (!res || !res.candles.length) { toast('داده برای «' + sym + '» پیدا نشد'); return; }
      var cmp = res.candles.map(function (c) { return { ts: rvDateToTs(c.time), close: c.close }; });  // v8.7 FIX-3: هم‌واحد با timestamp چارت
      cmp.sort(function (a, b) { return a.ts - b.ts; });
      var main = rv.chart.getDataList();
      if (main.length < 2) { toast('چارت اصلی آماده نیست'); return; }
      function cmpAt(ts) { // آخرین کندل روزانه <= ts
        var lo = 0, hi = cmp.length - 1, ans = -1;
        while (lo <= hi) { var mid = (lo + hi) >> 1; if (cmp[mid].ts <= ts) { ans = mid; lo = mid + 1; } else hi = mid - 1; }
        return ans;
      }
      var i0 = cmpAt(main[0].timestamp);
      if (i0 < 0) i0 = 0;
      var c0 = cmp[i0].close || 1;
      var N = Math.min(110, main.length);
      var step = Math.max(1, Math.floor(main.length / N));
      /* پاریتی نهایت‌نگر: درصد تغییر نماد مقایسه در باند قیمتی نماد اصلی نگاشت میشود
         تا خط همیشه در محدوده دید بماند (مقادیر خام ۳۱x میشوند و از چارت خارج) */
      var pctMin = Infinity, pctMax = -Infinity, pairs = [];
      for (var i = 0; i < main.length; i += step) {
        var j = cmpAt(main[i].timestamp);
        if (j >= 0) { var pc = cmp[j].close / c0 - 1; pairs.push([main[i].timestamp, pc]); if (pc < pctMin) pctMin = pc; if (pc > pctMax) pctMax = pc; }
      }
      if (pairs.length < 2) { toast('همپوشانی تاریخی کافی نیست'); return; }
      var mMin = Infinity, mMax = -Infinity;
      var rec = main.slice(Math.max(0, main.length - 250));   /* باند دیدپذیر اخیر نه کل تاریخ (وگرنه خط زیر محدوده دید میماند) */
      for (var i = 0; i < rec.length; i++) { var c = rec[i].close; if (c < mMin) mMin = c; if (c > mMax) mMax = c; }
      var band = (mMax - mMin) || 1, span = (pctMax - pctMin) || 1;
      var pts = pairs.map(function (pr) {
        return { timestamp: pr[0], value: mMin + ((pr[1] - pctMin) / span) * band };
      });
      var realPct = pairs[pairs.length - 1][1] * 100;
      var lbl = sym + ' ' + (realPct >= 0 ? '+' : '') + realPct.toFixed(1) + '%';
      rv.chart.removeOverlay({ name: 'compare-line' });
      rv.chart.createOverlay({ name: 'compare-line', points: pts, styles: { label: lbl } });
      toast('مقایسه با ' + sym + ' رسم شد');
    } catch (e) { toast('خطا در مقایسه: ' + String(e).slice(0, 50)); }
  }

  /* ---------- 4) undo / redo ---------- */
  var _hist = [], _redo = [];
  function shapeOf(o) {
    return { name: o.name, styles: o.styles || null, lock: !!o.lock,
      points: (o.points || []).map(function (p) { return { timestamp: p.timestamp, value: p.value }; }) };
  }
  function wrapHistory() {
    if (typeof rv === 'undefined' || !rv.chart || rv.chart.__hist) return;
    var ch = rv.chart; ch.__hist = true;
    var _co = ch.createOverlay.bind(ch);
    ch.createOverlay = function (opt) {
      var r = _co(opt);
      var id = (r && typeof r === 'string' || typeof r === 'number') ? r : null;
      _hist.push({ act: 'add', id: id, shape: shapeOf({ name: opt.name, styles: opt.styles, points: opt.points }) });
      if (_hist.length > 200) _hist.shift();
      _redo = [];
      return r;
    };
    var _rm = ch.removeOverlay.bind(ch);
    ch.removeOverlay = function (arg) {
      var overs = ch.getOverlays() || [];
      var batch = null;
      if (arg === undefined) {
        batch = overs.filter(function (o) { return !(o.isDrawing && o.isDrawing()); }).map(function (o) { return { act: 'remove', shape: shapeOf(o) }; });
      } else {
        var tgt = overs.find(function (o) {
          if (arg.id != null) return o.id === arg.id;
          if (arg.name) return o.name === arg.name && !(o.isDrawing && o.isDrawing());
          return false;
        });
        if (tgt) { batch = [{ act: 'remove', shape: shapeOf(tgt) }]; }
      }
      var r = _rm(arg);
      if (batch) { _hist = _hist.concat(batch); if (_hist.length > 400) _hist = _hist.slice(-400); _redo = []; }
      return r;
    };
    // wrap rvClearAll → همه رسمهای قبلی در history ثبت شوند (removeOverlay() بدون arg پوشش داده شد)
  }
  function undo() {
    if (!_hist.length) { toast('واگرد: چیزی نیست'); return; }
    var h = _hist.pop();
    if (h.act === 'add') {
      if (h.id) { rv.chart.removeOverlay({ id: h.id }); }
      else { rv.chart.removeOverlay({ name: h.shape.name }); }
      _redo.push({ act: 'add', shape: h.shape });
      toast('واگرد شد');
    } else {
      var nid = rv.chart.createOverlay({ name: h.shape.name, points: h.shape.points, styles: h.shape.styles || undefined });
      _redo.push({ act: 'remove', id: nid });
      toast('برگشت رسم حذفشده');
    }
    if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
  }
  function redo() {
    if (!_redo.length) { toast('بازانجام: چیزی نیست'); return; }
    var r = _redo.pop();
    if (r.act === 'add') {
      var nid = rv.chart.createOverlay({ name: r.shape.name, points: r.shape.points, styles: r.shape.styles || undefined });
      _hist.push({ act: 'add', id: nid, shape: r.shape });
      toast('بازانجام شد');
    } else {
      if (r.id) rv.chart.removeOverlay({ id: r.id });
      toast('حذف دوباره');
    }
    if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
  }

  /* ---------- 5) ذخیره / فول‌اسکرین / عکس ---------- */
  function bindActions() {
    var sv = document.getElementById('nnSaveBtn');
    if (sv && !sv.__bound) {
      sv.__bound = true;
      sv.addEventListener('click', function () {
        if (typeof rvSaveOverlays === 'function') { rvSaveOverlays(); toast('✓ رسم‌ها ذخیره شد'); }
      });
    }
    var fs = document.getElementById('nnFsBtn');
    if (fs && !fs.__bound) {
      fs.__bound = true;
      fs.addEventListener('click', function () {
        var box = document.getElementById('rvChartBox');
        if (!document.fullscreenElement) { (box || document.documentElement).requestFullscreen && (box || document.documentElement).requestFullscreen(); }
        else document.exitFullscreen();
      });
    }
    var sh = document.getElementById('nnShotBtn');
    if (sh && !sh.__bound) {
      sh.__bound = true;
      sh.addEventListener('click', function () {
        if (typeof rv === 'undefined' || !rv.chart) return;
        try {
          var url = rv.chart.getConvertPictureUrl(true, 'png');
          var a = document.createElement('a');
          a.href = url; a.download = (rv.sym || 'chart') + '_' + Date.now() + '.png';
          document.body.appendChild(a); a.click(); a.remove();
          toast('📷 عکس ذخیره شد');
        } catch (e) { toast('خطا در عکس: ' + String(e).slice(0, 40)); }
      });
    }
    var ub = document.getElementById('nnUndoBtn');
    if (ub && !ub.__bound) { ub.__bound = true; ub.addEventListener('click', undo); }
    var rb = document.getElementById('nnRedoBtn');
    if (rb && !rb.__bound) { rb.__bound = true; rb.addEventListener('click', redo); }
    // Ctrl+Z / Ctrl+Y
    if (!document.__nnKeys) {
      document.__nnKeys = true;
      document.addEventListener('keydown', function (e) {
        if ((e.ctrlKey || e.metaKey) && !e.shiftKey && e.key.toLowerCase() === 'z') { e.preventDefault(); undo(); }
        if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) { e.preventDefault(); redo(); }
      });
    }
  }

  /* ---------- 6) قالب‌ها ---------- */
  function bindTemplates() {
    var btn = document.getElementById('nnTplBtn');
    if (!btn || btn.__bound) return;
    btn.__bound = true;
    btn.addEventListener('click', function (e) {
      e.stopPropagation();
      var popEl = document.getElementById('nnPop');
      if (popEl && popEl.style.display === 'block') { nnPopClose(); return; }
      var names = [];
      try {
        var st = JSON.parse(localStorage.getItem('bors_state_v2') || '{}');
        names = Object.keys(st).filter(function (k) { return k.indexOf('techTpl_') === 0; }).map(function (k) { return k.slice(8); });
      } catch (err) {}
      var html = '<div class="nn-menu nn-form">' +
        '<div class="nn-form-title">قالب‌های ترسیم</div>' +
        '<input id="nnTplName" placeholder="نام قالب جدید">' +
        '<button id="nnTplSave" class="nn-go">ذخیره قالب از رسم‌های فعلی</button>' +
        (names.length ? '<div class="nn-form-sub">اعمال قالب:</div>' + names.map(function (n) {
          return '<div class="nn-tplrow"><button data-tpl="' + n + '">' + n + '</button><button class="nn-tpldel" data-tpldel="' + n + '" title="حذف">✕</button></div>';
        }).join('') : '<div class="nn-form-sub">قالبی ذخیره نشده</div>') +
        '</div>';
      var pop = nnPop(html, btn);
      if (!pop) return;
      pop.querySelector('#nnTplSave').addEventListener('click', function () {
        var nm = pop.querySelector('#nnTplName').value.trim();
        if (!nm) { toast('نام قالب را بنویس'); return; }
        if (typeof rv === 'undefined' || !rv.chart) return;
        var overs = (rv.chart.getOverlays() || []).filter(function (o) { return !(o.isDrawing && o.isDrawing()) && o.name !== 'compare-line'; });
        var shapes = overs.map(shapeOf);
        stSet('techTpl_' + nm, { shapes: shapes });
        toast('قالب «' + nm + '» ذخیره شد');
        nnPopClose();
      });
      pop.querySelectorAll('button[data-tpl]').forEach(function (b) {
        b.addEventListener('click', function () {
          var t = stGet('techTpl_' + b.dataset.tpl, null);
          if (!t || !t.shapes) { toast('قالب پیدا نشد'); return; }
          rv.chart.removeOverlay();
          t.shapes.forEach(function (s) {
            try { rv.chart.createOverlay({ name: s.name, points: s.points, styles: s.styles || undefined }); } catch (e2) {}
          });
          if (typeof rvSaveOverlays === 'function') rvSaveOverlays();
          toast('قالب «' + b.dataset.tpl + '» اعمال شد');
          nnPopClose();
        });
      });
      pop.querySelectorAll('button[data-tpldel]').forEach(function (b) {
        b.addEventListener('click', function () {
          try { var st = JSON.parse(localStorage.getItem('bors_state_v2') || '{}'); delete st['techTpl_' + b.dataset.tpldel]; localStorage.setItem('bors_state_v2', JSON.stringify(st)); } catch (e3) {}
          toast('قالب حذف شد');
          nnPopClose();
        });
      });
    });
  }

  /* ---------- init ---------- */
  function boot() {
    registerCompareOverlay();
    bindTfChip(); bindCandleChip(); bindCompare(); bindActions(); bindTemplates();
    var tries = 0;
    var t = setInterval(function () {
      tries++;
      if ((typeof rv !== 'undefined' && rv.chart) || tries > 40) {
        clearInterval(t);
        if (typeof rv !== 'undefined' && rv.chart) { wrapHistory(); wrapApplyTheme(); applyCandleType(stGet('techCandleType', 'candle_solid')); }
      }
    }, 500);
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
