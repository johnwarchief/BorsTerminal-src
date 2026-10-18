// _audit/ra365_job_verify_clean.js — بررسیِ **منفعلِ** وضعِ چارتِ مالک پس ازِ کاوشِ قبلی.
// چرا لازم شد: درِ کاوشِ ابزارها، برایِ بعضی گروه‌ها caret یافت نشد و کد به‌عنوانِ fallback
// رویِ خودِ دکمهٔ گروه کلیک کرد — یعنی ممکن است یکِ ابزارِ رسم **فعال** شده باشد (بدونِ
// رسم، ولی با احتمالِ ماندنِ درِ preference). اثباتِ بی‌اثری با درختِ اشیاء هم بی‌محتوا شد
// (سلکتور ۰ گرفت). پس این دور هیچِ کلیکِ دیگری نمی‌کند و فقط می‌خواند:
//   • legend = فهرستِ چیزهایی که واقعاً رویِ چارت اعمال شده‌اند (کندل + اندیکاتورها)
//   • شمارِ ابزارهایِ رسمِ فعال ازِ عنوانِ دکمه‌ها، و هر متنِ «ابزارِ رسم فعال است»
//   • یکِ اسکرین‌شات برایِ دیدنِ خودِ چارت
// بی‌کلیک، بی‌تغییر. بی‌خواندنِ هیچِ credential.
const READ = () => {
  const vis = (e) => { try { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; } catch { return false; } };
  const txt = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const legend = [...new Set(Array.from(document.querySelectorAll('[data-name="legend-source-title"],[data-name="legend-series-item"],[class*="legendSource" i]'))
    .map(txt).filter((s) => s && s.length < 70))];
  const active = Array.from(document.querySelectorAll('[class*="active" i],[aria-pressed="true"],[data-active="true"]'))
    .filter(vis)
    .map((e) => ({ n: e.getAttribute('data-name') || '', t: (e.getAttribute('title') || txt(e)).slice(0, 60) }))
    .filter((x) => /linetool|draw|cursor|measure|magnet|lock/i.test(x.n + ' ' + x.t))
    .slice(0, 20);
  const removeBtn = document.querySelector('[data-name="removeAllDrawingTools"]');
  return {
    url: location.href,
    legend,
    activeDrawingish: active,
    removeBtnTitle: removeBtn ? (removeBtn.getAttribute('title') || removeBtn.getAttribute('aria-label') || '(بی‌عنوان)') : 'absent',
    removeBtnText: removeBtn ? txt(removeBtn).slice(0, 60) : '',
    canvasCount: document.querySelectorAll('canvas').length,
    // هر متنِ هشدارِ «حالتِ رسم فعال است» که درِ صفحه دیدنی باشد
    drawModeHints: [...new Set(Array.from(document.querySelectorAll('body *'))
      .filter((e) => e.childElementCount === 0 && vis(e))
      .map(txt)
      .filter((s) => s && s.length < 90 && /حالتِ رسم|ابزارِ رسم|drawing mode|drawing tool/i.test(s)))].slice(0, 10),
  };
};

module.exports = async ({ page, shot, say }) => {
  const out = { frames: [], notes: [] };
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
  out.frames.push({ name: frame.name(), ...(await frame.evaluate(READ)) });
  const f = out.frames[0];
  say('legend: ' + JSON.stringify(f.legend));
  say('remove button: ' + f.removeBtnTitle + ' | text: ' + f.removeBtnText);
  say('ابزارِ activeِ رسم‌مانند: ' + JSON.stringify(f.activeDrawingish));
  say('راهنمایِ حالتِ رسم درِ صفحه: ' + JSON.stringify(f.drawModeHints));
  out.shot = await shot('ra365_verify_clean');
  out.notes.push('این دور هیچِ کلیک/کاردِ ماوسی نکرد؛ فقطِ DOM خوانده و اسکرین‌شات گرفته شد.');
  out.verdict = (f.legend.length <= 2 && f.activeDrawingish.length === 0)
    ? 'پاک: فقطِ سریِ کندل درِ legend و هیچِ ابزارِ رسمِ فعالی دیدنی نیست'
    : 'نیازمندِ بازبینیِ انسانی: legend یا ابزارِ فعال غیرمنتظره دارد (' + f.legend.length + '/' + f.activeDrawingish.length + ')';
  say('verdict: ' + out.verdict);
  return out;
};
