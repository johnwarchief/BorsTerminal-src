// _audit/ra365_job_tools.js -- دفترِ واژگانِ رابطِ چارتِ ره‌آورد (فقط خواندن؛ هیچ کلیکِ سازنده‌ای)
// هدف: فهرستِ کاملِ ابزارهایِ ترسیم + اندیکاتورهایِ فعال + وضعیتِ تعدیل/مقیاس/تایم‌فریم، آن‌طور
// که درِ DOMِ ویجتِ TradingView نوشته شده. این واژگان بعداً مبنایِ شمارشِ مرحلۀ ۴ (ابزارها) و
// مرحلۀ ۵ (اندیکاتورها) است. هیچ ابزاری انتخاب/رسم نمی‌شود و هیچ چیدمانی ذخیره نمی‌شود.
const CHART_PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => { try { return Array.from(document.querySelectorAll(s)); } catch { return []; } };
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  // واژگانِ TradingView: هر چه data-name دارد (دکمه‌هایِ ابزار، منوها، آیتم‌هایِ فیبو و…)
  const dataNames = uniq(q('[data-name]').map((e) => e.getAttribute('data-name')));
  const drawingish = uniq(
    q('[class*="drawing" i], [class*="shape" i], [class*="trend" i], [class*="fib" i], [class*="channel" i], [class*="pitchfork" i]')
      .map((e) => (e.getAttribute('class') || '').trim().slice(0, 90))
  ).slice(0, 40);
  // نوارِ ابزارِ ترسیم (معمولاً ستونِ چپ/راستِ چارت)
  const toolbars = q('[class*="toolbar" i]').map((t) => ({
    cls: (t.getAttribute('class') || '').slice(0, 70),
    items: uniq(Array.from(t.querySelectorAll('[data-name], button, [role="button"]')).map((b) => b.getAttribute('data-name') || b.getAttribute('title') || txt(b)).filter(Boolean).slice(0, 60)),
  })).slice(0, 12);
  // وضعیتِ فعلیِ نمایش: تعدیل، مقیاس، تایم‌فریم، افسانۀ اندیکاتورها
  const state = {
    adjustmentOptions: uniq(q('body *').filter((e) => e.childElementCount === 0).map(txt).filter((s) => /^(عملکردی|بدون تعدیل|بدونِ تعدیل|آخرین قیمت)$/.test(s || ''))),
    scaleButtons: uniq(q('[data-name*="log" i], [data-name*="linear" i], [class*="log" i]').map((e) => (e.getAttribute('data-name') || '') + '|' + (e.getAttribute('class') || '').slice(0, 40)).filter((s) => s !== '|')).slice(0, 20),
    legendRows: uniq(q('[class*="legend" i]').map(txt).filter((s) => s && s.length > 4 && s.length < 300)).slice(0, 20),
    intervalText: uniq(q('[data-name*="interval" i]').map((e) => txt(e) || e.getAttribute('data-name')).filter(Boolean)).slice(0, 10),
    autoSaveState: uniq(q('body *').filter((e) => e.childElementCount === 0).map(txt).filter((s) => /saved|AutoSave|ذخیره/i.test(s || '')).slice(0, 6)),
  };
  // محورِ قیمت و تاریخ (اعدادِ واقعیِ مرجع)
  const axis = {
    priceCells: uniq(q('table[class*="axis" i] td, [class*="axis" i] table td, .chart-markup-table td').map(txt).filter(Boolean)).slice(0, 80),
    timeCells: uniq(q('[class*="time" i] table td, [class*="axis" i] + table td').map(txt).filter(Boolean)).slice(0, 40),
  };
  // شمارشِ ترسیم‌هایِ موجود رویِ چارت (برایِ اینکه نمادهایِ دست‌خورده شناسایی شوند)
  const drawings = {
    shapeGroups: q('svg g[class*="shape" i], svg g[data-name*="drawing" i], svg g[data-name*="shape" i]').length,
    pathsInPanes: q('.pane-marks path, [class*="pane" i] svg path').length,
    priceLines: q('[class*="priceLine" i], [data-name*="price-line" i]').length,
    dataNamesForDrawings: uniq(q('[data-name]').map((e) => e.getAttribute('data-name')).filter((n) => /trend|fib|channel|pitchfork|line|rect|shadow|note|text|cross|ray|parallel/i.test(n))).slice(0, 60),
  };
  return {
    href: location.href.slice(0, 100),
    nodes: q('body *').length,
    canvases: q('canvas').length,
    dataNames,
    drawingish,
    toolbars,
    state,
    axis,
    drawings,
  };
};

module.exports = async ({ page, shot, probe, say }) => {
  const rep = { symbols: [] };
  const IDS = { 453: 'فولاد', 462: 'وبملت', 599: 'ولانا' };
  for (const [id, sym] of Object.entries(IDS)) {
    await page.goto(`https://rahavard365.com/asset/${id}/chart`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForTimeout(24000);
    const entry = { id, sym, frames: [] };
    for (const f of page.frames()) {
      try {
        const r = await f.evaluate(CHART_PROBE);
        if (r && r.canvases >= 3) entry.frames.push(r); // فریمِ اصلیِ چارت (ویجتِ TradingView)
      } catch { /* کراس‌اورجین/بسته */ }
    }
    rep.symbols.push(entry);
    const main = entry.frames[0] || { dataNames: [], drawings: {}, state: {} };
    say(`${sym}(${id}): chartFrames=${entry.frames.length} dataNames=${(main.dataNames || []).length} shapes=${(main.drawings || {}).shapeGroups} paths=${(main.drawings || {}).pathsInPanes}`);
    if (id === '453') rep.shotFolad = await shot('ra365_folad_tools_state');
  }
  return rep;
};
