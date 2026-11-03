// _audit/ra365_job_tools3.js — شمارِ کاملِ ابزارها درِ هر گروهِ رسم، **بی‌هیچِ تعامل**.
// چرا دورهای قبل بی‌نتیجه بود: SNAP فقط عنصرهای *دیدنی* را می‌گرفت و flyout درِ حالتِ
// بسته دیدنی نیست؛ پس «۲ آیتم» که می‌آمد محتوایِ گروه نبود. دورِ caret هم برایِ بعضی
// گروه‌ها رویِ خودِ دکمه می‌افتاد (احتمالِ فعال‌شدنِ ابزار) و اثباتِ بی‌اثری‌اش سنجیده
// نشد — که بعداً با خوانشِ منفعل ra365_job_verify_clean.js بررسی و پاک گزارش شد.
// این روش بی‌ریسک‌تر است: آرایۀِ DOM معمولاً همهٔ linetoolها را (حتی display:none) نگه
// می‌دارد، پس با برداشتنِ فیلترِ visibility و خواندنِ data-nameهایِ `linetool-*` کل
// کاتالوگ بی‌کلیک درمی‌آید. اگر باز هم چیزی نبود، صریح «درِ DOM نیست» ثبت می‌شود.
const CATALOG = () => {
  const all = Array.from(document.querySelectorAll('[data-name]'));
  const byName = {};
  all.forEach((e) => {
    const n = e.getAttribute('data-name') || '';
    if (!n) return;
    const t = (e.getAttribute('title') || e.getAttribute('aria-label') || (e.textContent || '').trim() || '').slice(0, 70);
    if (!byName[n]) byName[n] = { titles: [], visible: false };
    if (t && !byName[n].titles.includes(t)) byName[n].titles.push(t);
    try { const r = e.getBoundingClientRect(); if (r.width > 1 && r.height > 1) byName[n].visible = true; } catch (e) { /* hidden */ }
  });
  const keys = Object.keys(byName).sort();
  return {
    total: keys.length,
    linetools: keys.filter((k) => /^linetool-/.test(k)).map((k) => k + ' :: ' + byName[k].titles.slice(0, 2).join(' | ') + (byName[k].visible ? ' [visible]' : ' [hidden]')),
    groups: keys.filter((k) => /^linetool-group-/.test(k)).map((k) => k + ' :: ' + byName[k].titles.slice(0, 2).join(' | ')),
    drawControls: keys.filter((k) => /magnet|lock|hide|remove|draw|measure|zoom|objects|cursor/i.test(k)).map((k) => k + ' :: ' + byName[k].titles.slice(0, 2).join(' | ')),
    intervals: keys.filter((k) => /interval|resolution|date-range|time-zone/i.test(k)).map((k) => k + ' :: ' + byName[k].titles.slice(0, 2).join(' | ')),
    scales: keys.filter((k) => /log|percentage|auto|scale|axis/i.test(k)).map((k) => k + ' :: ' + byName[k].titles.slice(0, 2).join(' | ')),
    otherSample: keys.filter((k) => !/^(linetool-|legend|pane)/.test(k)).slice(0, 90),
  };
};

module.exports = async ({ page, shot, say }) => {
  const out = { notes: [] };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 90000 })
    .catch((e) => out.notes.push('goto: ' + String(e).slice(0, 90)));
  await page.waitForTimeout(24000);
  let frame = page.frames().find((f) => /tradingview/.test(f.name() || ''));
  if (!frame) {
    for (const f of page.frames()) {
      const ok = await f.evaluate(() => !!document.querySelector('[data-name="removeAllDrawingTools"]')).catch(() => false);
      if (ok) { frame = f; break; }
    }
  }
  if (!frame) { out.notes.push('فریمِ چارت پیدا نشد'); return out; }
  const c = await frame.evaluate(CATALOG);
  out.catalog = c;
  say('دکمه/برچسبِ data-name درِ DOM: ' + c.total + ' | linetool: ' + c.linetools.length);
  c.groups.forEach((g) => say('  GROUP ' + g));
  c.linetools.forEach((t) => say('  TOOL  ' + t));
  c.drawControls.forEach((t) => say('  CTRL  ' + t));
  c.intervals.forEach((t) => say('  TIME  ' + t));
  c.scales.forEach((t) => say('  SCALE ' + t));
  out.shot = await shot('ra365_tools3_passive');
  out.notes.push('بی‌کلیک و بی‌hover: فقطِ DOM خوانده شد (فیلترِ visibility برداشته شد تا flyoutهایِ پنهان هم شمرده شوند).');
  out.notes.push('اگر شمارِ linetool کمتر ازِ شمارِ گروه×ابزارِ انتظار بود، یعنی flyout lazy render است و درِ DOM نیست — N/A، نه حدس.');
  return out;
};
