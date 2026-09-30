// _audit/probe_num_bidi.mts -- آیا «۳۷.۰۲ همت» در متنِ راست‌به‌چپ بدون .num به‌هم می‌ریزد؟
// سه حالت رویِ یک رشتهٔ واقعی از دروازۀ «ورود به بازار» رندر و اندازه‌گیری می‌شود.
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 900, height: 400 } });

const S = '۳ نشستِ اخیر: ۳۷.۰۲ همت · ۴۱.۱۱ همت · ۳۹.۲ همت';
await p.setContent(`<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8">
<style>
body{font-family:Vazirmatn,Tahoma,sans-serif;background:#111;color:#eee;font-size:15px}
.num{direction:ltr;unicode-bidi:isolate;font-variant-numeric:tabular-nums;display:inline-block}
.iso{unicode-bidi:isolate}
div{margin:8px 0;padding:6px;border:1px solid #333}
</style></head><body>
<div id="a">${S}</div>
<div id="b"><span class="num">${S}</span></div>
<div id="c"><span class="iso">${S}</span></div>
</body></html>`);

const order = await p.evaluate(() => {
  const firstDigits = (id: string) => {
    const el = document.getElementById(id)!;
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const runs: string[] = [];
    while (walker.nextNode()) {
      const t = walker.currentNode.textContent ?? '';
      const m = t.match(/[۰-۹][۰-۹.٪]*/g);
      if (m) runs.push(...m);
    }
    return runs;
  };
  const rectOf = (id: string, needle: string) => {
    const el = document.getElementById(id)!;
    const range = document.createRange();
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const i = (node.textContent ?? '').indexOf(needle);
      if (i >= 0) {
        range.setStart(node, i);
        range.setEnd(node, i + needle.length);
        const r = range.getBoundingClientRect();
        return { left: Math.round(r.left), right: Math.round(r.right) };
      }
    }
    return null;
  };
  const rows = ['a', 'b', 'c'].map((id) => {
    const el = document.getElementById(id)!;
    return {
      id,
      text: el.textContent ?? '',
      first_number: rectOf(id, '۳۷.۰۲'),
      last_number: rectOf(id, '۳۹.۲'),
      box_left: Math.round(el.getBoundingClientRect().left),
      box_right: Math.round(el.getBoundingClientRect().right),
    };
  });
  return { rows, note: 'اگر left(۳۷.۰۲) > left(۳۹.۲) باشد، ترتیبِ دیداریِ عدد اول سمت راست نشسته (راست‌به‌چپِ درست)' };
});
await p.screenshot({ path: '_audit/num_bidi.png' });
console.log(JSON.stringify(order, null, 1));
await b.close();
