// _audit/ra365_job_capture.js -- گرفتنیِ پاسخِ دادۀِ چارت از خودِ ره‌آورد + عوض‌کردنِ تایم‌فریم با دکمۀ «W»
// چرا: خواندنِ عدد با crosshair رویِ canvas دقیق نیست (legend تکان نخورد). اینجا همان JSON را
// می‌خوانیم که خودِ رابطِ ره‌آورد برای رسمِ کندل‌ها می‌گیرد — دادۀِ مرجع، از نشستِ لاگین‌شده،
// نه از تریدرز آرنا. همزمان وضعیتِ تعدیلِ انتخاب‌شده (نه فهرستِ گزینه‌ها) را می‌خوانیم.
// فقط خواندن + یک کلیکِ تایم‌فریم و یک کلیکِ مقیاس؛ هیچ ترسمی نه.
const HEADERS_PROBE = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s) => { try { return Array.from(document.querySelectorAll(s)); } catch { return []; } };
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  // تریگرِ انتخابِ تعدیل: المانی که متنش یکی از سه گزینه است و داخلِ دکمه/سِلکت است
  const adjTriggers = q('button, [role="button"], [role="combobox"], [class*="select" i], [class*="Select" i]')
    .map(txt).filter((s) => /^(عملکردی|بدون تعدیل|آخرین قیمت)$/.test(s || ''));
  const ivTriggers = q('button, [role="button"], [class*="menu" i]').map(txt).filter((s) => /^(D|W|M|1D|1W|1M|240|60)$/.test(s || ''));
  return {
    adjustmentSelected: uniq(adjTriggers).slice(0, 4),
    intervalTriggers: uniq(ivTriggers).slice(0, 8),
    scalePressed: q('[data-name="logarithm"], [data-name="percentage"], [data-name="auto"]')
      .map((e) => e.getAttribute('data-name') + '|' + (e.getAttribute('class') || '').replace(/\s+/g, ' ').slice(0, 60)).slice(0, 6),
    legend: q('[data-name="legend"]').map(txt).filter(Boolean).slice(0, 3),
  };
};

module.exports = async ({ page, shot, say }) => {
  const bodies = [];
  page.on('response', async (r) => {
    try {
      const u = r.url();
      if (!/rahavard365\.com/.test(u)) return;
      const ct = (r.headers()['content-type'] || '');
      if (!/json/.test(ct)) return;
      if (!/chart|candle|price|history|series|asset|instrument|tech|quote|market-data/i.test(u)) return;
      const j = await r.json().catch(() => null);
      if (j == null) return;
      const s = JSON.stringify(j);
      bodies.push({ url: u.slice(0, 200), status: r.status(), bytes: s.length, head: s.slice(0, 1500), topKeys: Object.keys(j).slice(0, 12) });
    } catch { /* بی‌صدا */ }
  });

  const rep = { bodies: [], steps: [] };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 90000 });
  await page.waitForTimeout(20000);

  let frame = null;
  for (const f of page.frames()) {
    try { const n = await f.evaluate(() => document.querySelectorAll('canvas').length); if (n >= 3) { frame = f; break; } } catch { /* بعدی */ }
  }
  if (!frame) return { error: 'no chart frame', bodies };
  rep.before = await frame.evaluate(HEADERS_PROBE);
  say('before: ' + JSON.stringify({ adj: rep.before.adjustmentSelected, iv: rep.before.intervalTriggers, legend: (rep.before.legend[0] || '').slice(0, 90) }));

  // دکمۀِ تایم‌فریم: همان «W» که درِ نوارِ ابزار است (کلاسِ button- دارد، نه title- که legend است)
  const btns = await frame.$$('button, [role="button"], [class*="button-"]');
  let clicked = null;
  for (const b of btns) {
    const t = ((await b.textContent().catch(() => '')) || '').replace(/\s+/g, ' ').trim();
    const cls = (await b.getAttribute('class').catch(() => '')) || '';
    if (/^[DWMAH]$/.test(t) && /button-/.test(cls)) { await b.click({ timeout: 4000 }).catch(() => {}); clicked = t; break; }
  }
  await page.waitForTimeout(2000);
  rep.steps.push('interval button clicked: ' + clicked);
  // آیتمِ 1D درِ منویِ باز شده
  let picked = null;
  for (const el of await frame.$$('[class*="menu"] *, [class*="item"] *, [role="menuitem"]')) {
    const t = ((await el.textContent().catch(() => '')) || '').replace(/\s+/g, ' ').trim();
    if (t === '1D') { await el.click({ timeout: 4000 }).catch(() => {}); picked = t; break; }
  }
  rep.steps.push('1D picked: ' + picked);
  await page.waitForTimeout(14000);
  rep.afterInterval = await frame.evaluate(HEADERS_PROBE);
  say('after interval: ' + JSON.stringify({ iv: rep.afterInterval.intervalTriggers, legend: (rep.afterInterval.legend[0] || '').slice(0, 90) }));

  // مقیاسِ log (دستورِ مالک) — اگر روشن نباشد
  if (!/logarithm/.test(JSON.stringify(rep.afterInterval.scalePressed || ''))) {
    const lb = await frame.$('[data-name="logarithm"]');
    if (lb) { await lb.click({ timeout: 4000 }).catch(() => {}); rep.steps.push('log clicked'); await page.waitForTimeout(3000); }
  }
  rep.shot = await shot('ra365_folad_daily_capture');
  rep.bodies = bodies.slice(0, 40);
  rep.bodyUrls = [...new Set(bodies.map((b) => b.url.split('?')[0]))].slice(0, 25);
  say('captured bodies: ' + bodies.length + ' | distinct urls: ' + rep.bodyUrls.length);
  return rep;
};
