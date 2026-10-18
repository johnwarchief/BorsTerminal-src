// _audit/ra365_job_chart_inventory.js -- شمارشِ ابزارها/افسانه/محور درِ چارتِ ره‌آورد، فقط با خواندن
// قاعده: هیچ کلیکِ رسمِ ابزار، هیچ افزودنِ اندیکاتور، هیچ ذخیره‌ای. فقط DOM + اسکرین‌شات +
// (در صورت نیاز) تغییرِ تایم‌فریم/تعدیل/مقیاس که «نمایش» است نه «نوشتن» — و وضعیتِ پیشین ثبت می‌شود.
// خروجیِ مهم: شمارشِ ترسیم‌هایِ ازپیش‌وجودِ مالک درِ هر نماد؛ نمادی که ترسمی دارد درِ آزمونِ رسم
// کنار گذاشته می‌شود (دستورِ مالک).

const FRAME_PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => { try { return Array.from(document.querySelectorAll(s)); } catch { return []; } };
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  // ابزارهای ترسیمِ TradingView: دکمه‌هایِ نوارِ کناری با title/data-name
  const toolSel = 'div[class*="toolbar"] button, .chart-container button, button[data-name], button[title]';
  const tools = uniq(q(toolSel).map((b) => (b.getAttribute('title') || b.getAttribute('data-name') || b.getAttribute('aria-label') || txt(b) || '').trim())
    .filter((s) => s && s.length > 1 && s.length < 70));
  // محورِ قیمت: سلول‌هایِ جدولِ محور (اعدادِ واقعیِ مرجع برایِ نگاشتِ پیکسل)
  const axisTables = q('table[class*="axis"], div[class*="axis"] table, .chart-markup-table');
  const axisCells = uniq(axisTables.map((t) => txt(t)).filter(Boolean)).slice(0, 6);
  // افسانۀ اندیکاتورها (EMA(10) …، RSI …) — همان چیزی که کاربر می‌بیند
  const legends = uniq(q('[class*="legend" i], [class*="Legend" i]').map(txt).filter((s) => s && s.length > 2 && s.length < 260)).slice(0, 25);
  // سربرگِ OHLC نماد
  const header = uniq(q('[class*="header" i], [class*="title" i], [class*="symbol" i]').map(txt).filter((s) => s && /O|H|L|C|۰-۹|\d/.test(s) && s.length < 200)).slice(0, 12);
  // ترسیم‌هایِ ازپیش‌وجود (فقط شمارش)
  const drawingCounts = {
    drawingRoots: q('[class*="drawing" i]').length,
    svgGroups: q('svg g[class*="mark" i], svg g[data-drawing-id], svg g[class*="figure" i]').length,
    priceLines: q('[class*="priceLine" i], [class*="price-line" i]').length,
  };
  const scaleToggles = uniq(q('body *').filter((e) => e.childElementCount === 0).map(txt).filter((s) => /^(log|linear|auto|عملکردی|بدون تعدیل|بدونِ تعدیل|آخرین قیمت)$/i.test(s || '')).slice(0, 12));
  return {
    href: location.href.slice(0, 120),
    nodes: q('body *').length,
    canvases: q('canvas').length,
    svgs: q('svg').length,
    tools,
    axisTexts: axisCells,
    legends,
    header,
    drawingCounts,
    scaleToggles,
  };
};

module.exports = async ({ page, shot, probe, say }) => {
  const rep = { frames: [], page: null, before: {} };
  const IDS = { 453: 'فولاد', 462: 'وبملت', 599: 'ولانا' };
  for (const [id, sym] of Object.entries(IDS)) {
    await page.goto(`https://rahavard365.com/asset/${id}/chart`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForTimeout(22000);
    const top = await probe();
    const entry = {
      id, sym, title: top.title, url: top.url,
      loginButtonPresent: top.loginButtonPresent,
      gate: top.paywallOrGate,
      toolbarItemsTop: top.toolbarItems.slice(0, 40),
      axisLikeTexts: top.axisLikeTexts,
      jalaliDates: top.jalaliDates,
      sample: top.visibleTextSample.slice(0, 300),
      frames: [],
    };
    for (const f of page.frames()) {
      try {
        const r = await f.evaluate(FRAME_PROBE);
        if (r && (r.nodes > 30 || r.tools.length)) entry.frames.push(r);
      } catch { /* فریمِ بسته/کراس‌اورجین */ }
    }
    rep.frames.push(entry);
    say(`${sym}(${id}): topNodes=${top.nodes} frames=${entry.frames.length} tools=${entry.frames.reduce((a, x) => a + x.tools.length, 0)} drawings=${JSON.stringify(entry.frames.map((x) => x.drawingCounts))}`);
    if (id === '453') rep.shotFolad = await shot('ra365_folad_chart_full');
  }
  return rep;
};
