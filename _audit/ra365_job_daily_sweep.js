// _audit/ra365_job_daily_sweep.js -- خواندنِ کندل‌هایِ روزانۀ مرجع با crosshair (بدونِ هیچ ترسمی)
// چرا: بانکِ محلی ما هیچ ردیفی برای شنبه 2026-10-10 ندارد (daily_prices از 20261007 مستقیم به
// 20261011 می‌پرد؛ فقط دو نماد از فیدِ published آن روز را دارند). مرجع باید بگوید آن روز
// معاملاتی بوده یا نه و OHLC اش چه بوده؛ همین یک روز کل کندلِ هفتگی و ساختارِ هفتگی را جابه‌جا
// می‌کند.
// روش: نخست «کشفِ بی‌کلیک» (کدام دکمه تایم‌فریم را دست‌کاری می‌کند)، سپس فقط اگر یک کاندیدای
// مطمئن بود به 1D می‌رویم، تعدیل را «عملکردی» و مقیاس را «log» می‌کنیم (دستورِ مالک)، نشانگرِ
// متقاطع را رویِ کندل‌هایِ آخر می‌بریم و legend را می‌خوانیم، و در پایان وضعیتِ پیشین را
// برمی‌گردانیم. هیچ ابزارِ رسمِ انتخاب نمی‌شود و هیچ اندیکاتوری اضافه/حذف نمی‌شود.

// وضعیتِ خواندنیِ چارت: legend، تعدیل، تایم‌فریم، مقیاس
const LEGEND = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => { try { return Array.from(document.querySelectorAll(s)); } catch { return []; } };
  return {
    rows: q('[data-name="legend"]').map(txt).filter(Boolean).slice(0, 4),
    adjustment: q('body *').filter((e) => e.childElementCount === 0).map(txt).filter((s) => /^(عملکردی|بدون تعدیل|آخرین قیمت)$/.test(s || '')).slice(0, 4),
    interval: q('[data-name="legend-source-interval"]').map(txt).filter(Boolean).slice(0, 2),
    scale: q('[data-name="logarithm"], [data-name="percentage"], [data-name="auto"]')
      .map((e) => e.getAttribute('data-name') + '=' + (e.getAttribute('aria-pressed') || (e.getAttribute('class') || '').replace(/\s+/g, ' ').slice(0, 40))).slice(0, 8),
    nodes: q('body *').length,
  };
};

// کشفِ بی‌کلیک: هر المانی که متنش شکلِ تایم‌فریم دارد + هویتش
const FIND_INTERVAL_BUTTONS = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const out = [];
  document.querySelectorAll('body *').forEach((e) => {
    const t = txt(e);
    if (!/^(\d+|[1-9])?(D|W|M|Y|H|R|T)\b$/.test(t) || t.length > 4) return;
    if (e.childElementCount > 0) return;
    const p = e.closest('[data-name], button, [role="button"]') || e;
    out.push({
      text: t,
      selfDataName: e.getAttribute('data-name') || null,
      parentDataName: p.getAttribute && p.getAttribute('data-name') || null,
      parentClass: ((p.getAttribute && p.getAttribute('class')) || '').replace(/\s+/g, ' ').slice(0, 70),
      tag: p.tagName.toLowerCase(),
    });
  });
  const seen = new Set();
  return out.filter((x) => { const k = x.text + '|' + (x.parentDataName || '') + '|' + x.parentClass; if (seen.has(k)) return false; seen.add(k); return true; }).slice(0, 25);
};

const clickByDataName = async (frame, name) => {
  const el = await frame.$(`[data-name="${name}"]`);
  if (!el) return false;
  await el.click({ timeout: 5000 }).catch(() => {});
  return true;
};

module.exports = async ({ page, shot, say }) => {
  const rep = { actions: [], symbols: {} };
  const IDS = { 453: 'فولاد', 462: 'وبملت', 599: 'ولانا' };
  for (const [id, sym] of Object.entries(IDS)) {
    await page.goto(`https://rahavard365.com/asset/${id}/chart`, { waitUntil: 'domcontentloaded', timeout: 90000 });
    await page.waitForTimeout(22000);
    let frame = null;
    for (const f of page.frames()) {
      try { const n = await f.evaluate(() => document.querySelectorAll('canvas').length); if (n >= 3) { frame = f; break; } } catch { /* بعدی */ }
    }
    if (!frame) { rep.symbols[sym] = { error: 'chart frame not found' }; continue; }
    const entry = { before: await frame.evaluate(LEGEND), candidates: await frame.evaluate(FIND_INTERVAL_BUTTONS), reads: [] };
    say(`${sym}: interval candidates = ${entry.candidates.map((c) => c.text + '@' + (c.parentDataName || c.parentClass)).join(' , ')}`);

    // فقط کاندیدایِ خودِ ویجتِ چارت (نه تبِ بازۀ زمانیِ date-range-tab-*)
    const cand = entry.candidates.find((c) => /^[1-9]+[DWMy]$/.test(c.text) && !/date-range/.test((c.parentDataName || '') + (c.parentClass || '')));
    if (cand) {
      const btn = (await frame.$('[data-name="interval-menu-button"]')) || (await frame.$(`[data-name="${cand.parentDataName}"]`));
      if (btn) {
        await btn.click({ timeout: 5000 }).catch(() => {});
        await page.waitForTimeout(1800);
        const got = await clickByDataName(frame, 'interval-dialog-input') || (await (async () => {
          const els = await frame.$$('[class*="menu"] span, [class*="item"] span, [role="menuitem"]');
          for (const el of els) {
            const t = ((await el.textContent().catch(() => '')) || '').trim();
            if (t === '1D') { await el.click({ timeout: 4000 }).catch(() => {}); return true; }
          }
          return false;
        })());
        rep.actions.push(`${sym}: بازکردنِ منویِ تایم‌فریم با «${cand.text}» + انتخابِ 1D = ${got}`);
        await page.waitForTimeout(9000);
      }
    } else {
      rep.actions.push(`${sym}: هیچ دکمۀِ تایم‌فریمِ مطمئنی کشف نشد؛ چارت درِ همان تایم‌فریمِ پیشین خوانده شد`);
    }
    entry.afterInterval = await frame.evaluate(LEGEND);

    // مقیاسِ لگاریتمی (دستورِ مالک)
    if (await clickByDataName(frame, 'logarithm')) rep.actions.push(`${sym}: مقیاسِ log روشن شد`);
    await page.waitForTimeout(2500);

    // sweep با نشانگرِ متقاطع
    const host = await frame.frameElement();
    const box = await host.boundingBox().catch(() => null);
    if (box) {
      const y = Math.round(box.y + box.height * 0.45);
      for (let i = 0; i < 16; i++) {
        const x = Math.round(box.x + box.width - 26 - i * 24);
        await page.mouse.move(x, y);
        await page.waitForTimeout(400);
        const lg = await frame.evaluate(LEGEND);
        entry.reads.push({ i, x, legend: lg.rows[0] || '', adjustment: lg.adjustment.join('/'), interval: lg.interval.join('/') });
      }
    } else entry.readsError = 'boundingBox unavailable';
    entry.after = await frame.evaluate(LEGEND);
    if (id === '453') entry.shot = await shot('ra365_folad_daily_sweep');
    rep.symbols[sym] = entry;
    say(`${sym}: reads=${entry.reads.length} interval=${entry.after.interval.join('/')} adj=${entry.after.adjustment.join('/')} first=${(entry.reads[0] || {}).legend || ''}`);
  }
  return rep;
};
