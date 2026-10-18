// _audit/ra365_job_tools.js — استخراجِ **فقط‌خواندنیِ** مرجع (رهاورد ۳۶۵) برایِ ماتریسِ چارت
// چرا بی‌کلیک: درِ حسابِ مالک AutoSave روشن است؛ کلیک رویِ ابزارِ رسم یا افزودنِ اندیکاتور،
// نمودارِ خودِ مالک را عوض می‌کند. پس اینجا هیچِ کلیکِ تعاملی نمی‌کنیم — فقطِ DOMِ
// نوارابزار/فریم‌ها را می‌خوانیم و اسکرین‌شات می‌گیریم. اگر آیتمی درِ DOM نبود، صریح
// «درِ DOM دیده نشد» ثبت می‌شود؛ ازِ حافظه پر نمی‌شود.
// هیچِ رمز/کوکی/token خوانده یا نوشته نمی‌شود (توکن فقط درِ حافظهٔ evaluate می‌ماند).
const PROBE_TOOLS = () => {
  const txt = (e) => (e ? (e.textContent || '').replace(/\s+/g, ' ').trim() : '');
  const q = (s, r) => { try { return Array.from((r || document).querySelectorAll(s)); } catch { return []; } };
  const uniq = (a) => [...new Set(a.filter(Boolean))];
  // نوارابزارِ TradingView: هر دکمه معمولاً title/aria-label/data-name دارد؛Flyoutها
  // هم درِ DOM هستند (display:none) پس بی‌کلیک هم قابلِ خواندن‌اند.
  const btns = q('button, [role="button"], [data-name], [title], [aria-label]');
  const named = btns.map((b) => ({
    name: b.getAttribute && (b.getAttribute('data-name') || ''),
    title: b.getAttribute && (b.getAttribute('title') || ''),
    aria: b.getAttribute && (b.getAttribute('aria-label') || ''),
    cls: String(b.className || '').slice(0, 70),
    text: txt(b).slice(0, 40),
    visible: !!(b.offsetParent !== null || (b.getClientRects && b.getClientRects().length)),
  }));
  const groups = q('[class*="group" i],[class*="flyout" i],[class*="subToolbar" i],[class*="drawer" i],[class*="tools" i]')
    .map((g) => ({ cls: String(g.className || '').slice(0, 80), n: g.querySelectorAll('button,[role="button"]').length }));
  return {
    url: location.href,
    title: document.title,
    canvases: q('canvas').length,
    svgs: q('svg').length,
    frames: (window.frames ? window.frames.length : 0),
    buttonsTotal: btns.length,
    drawingNames: uniq(named.filter((x) => /draw|trend|line|ray|channel|fib|pitch|fork|rect|triangle|brush|arrow|text|note|price|measure|parallel|gann|elliott|abcd|quad|speed|longpos|shortpos|cross|cursor|magnet|lock/i
      .test((x.name || '') + ' ' + (x.title || '') + ' ' + (x.aria || ''))).map((x) => (x.name || x.title || x.aria || x.text))).slice(0, 160),
    timeFrameTexts: uniq(q('select, [role="listbox"], [role="menuitem"], [data-value], button')
      .map((e) => txt(e)).filter((s) => /^(۱|1|۳|3|۵|5|۱۵|15|۳۰|30|۶۰|6۰|۱۲۰|240|روزانه|هفتگی|ماهانه|D|W|M|1D|1W|1M|۱ دقیقه|۵ دقیقه|۱۵ دقیقه|ساعته)/.test(s) && s.length < 24)).slice(0, 40),
    axisLike: uniq(q('[class*="axis" i],[class*="priceAxis" i],[class*="timeAxis" i],[class*="scale" i]')
      .map((e) => String(e.className || '').slice(0, 60))).slice(0, 30),
    scaleTexts: uniq(q('button,[role="button"],[title],aria-label'.split(',')[0] ? 'button,[role="button"],[title]' : 'button')
      .map((e) => (e.getAttribute('title') || txt(e))).filter((s) => /خطی|لگاریتم|log|linear|درصد|autoscale|اندازه|تنظیمِ خودکار/i.test(s))
      .slice(0, 20)),
    groupShapes: groups.filter((g) => g.n > 0).slice(0, 40),
    // فهرستِ کاملِ نام‌هایِ data-name (TradingView همین را برایِ هر ابزار می‌گذارد)
    allDataNames: uniq(named.map((x) => x.name).filter(Boolean)).slice(0, 220),
  };
};

module.exports = async ({ page, ctx, shot, say, probe }) => {
  const out = { frames: [], notes: [] };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 90000 }).catch((e) => out.notes.push('goto: ' + String(e).slice(0, 90)));
  await page.waitForTimeout(22000);
  say('صفحه: ' + page.url());
  const hostProbe = await probe();
  out.host = { url: hostProbe.url, canvases: hostProbe.canvases, svgs: hostProbe.svgs, loginButtonPresent: hostProbe.loginButtonPresent, toolbarItems: (hostProbe.toolbarItems || []).slice(0, 40) };
  out.shot = await shot('ra365_tools_host');

  // هر فریم (ازجملۀِ iframeِ چارت) جدا خوانده می‌شود؛ بی‌کلیک.
  for (const f of page.frames()) {
    const u = f.url();
    if (/^(about:|chrome:)/.test(u)) continue;
    try {
      const r = await f.evaluate(PROBE_TOOLS);
      out.frames.push({ url: u.slice(0, 120), name: f.name(), buttonsTotal: r.buttonsTotal, canvases: r.canvases,
        allDataNames: r.allDataNames, drawingNames: r.drawingNames, timeFrameTexts: r.timeFrameTexts,
        axisLike: r.axisLike, scaleTexts: r.scaleTexts, groupShapes: r.groupShapes });
      say('frame ' + (f.name() || '(main)') + ' | دکمه=' + r.buttonsTotal + ' | data-name=' + r.allDataNames.length + ' | drawing=' + r.drawingNames.length);
    } catch (e) {
      out.frames.push({ url: u.slice(0, 120), name: f.name(), error: String(e).slice(0, 140) });
      say('frame ' + (f.name() || '(main)') + ' بی‌خوانش: ' + String(e).slice(0, 70));
    }
  }
  out.notes.push('بی‌هیچِ کلیکِ تعاملی: فقطِ DOM خوانده شد (AutoSaveِ حسابِ مالک درخطرِ تغییر نگذارد).');
  out.notes.push('اگر ابزاری درِ DOM نبود، یعنی flyoutش lazy render است؛ درِ آنصورت ' + 'به‌جایِ حدس، N/A ثبت می‌شود (سنجشِ بعدی با hover، نه کلیکِ ابزار).');
  return out;
};
