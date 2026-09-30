// _audit/probe_detail_bidi_ab.mts -- A/B زنده: شروعِ دیداریِ `detail` با .num و با .num-text
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);

const ab = await p.evaluate(() => {
  const chips = [...document.querySelectorAll('[data-testid^="pulse-verdict-gate-"]')] as HTMLElement[];
  const measure = (el: HTMLElement) => {
    // «اولین کاراکترِ دیداری» = نزدیک‌ترینruns به لبۀ راست در متنِ راست‌به‌چپ
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const runs: { text: string; left: number; right: number }[] = [];
    while (walker.nextNode()) {
      const node = walker.currentNode;
      const t = node.textContent ?? '';
      if (!t.trim()) continue;
      const r = document.createRange();
      r.setStart(node, 0);
      r.setEnd(node, Math.min(1, t.length));
      const box = r.getBoundingClientRect();
      runs.push({ text: t.slice(0, 14), left: Math.round(box.left), right: Math.round(box.right) });
    }
    return runs;
  };
  const target = chips.find((c) => (c.textContent ?? '').includes('۳ نشستِ اخیر')) as HTMLElement | undefined;
  if (!target) return { error: 'چیپِ «روندِ اخیر» پیدا نشد' };
  const span = [...target.querySelectorAll('span')].find((s) => (s.textContent ?? '').includes('۳ نشستِ اخیر:')) as HTMLElement;
  const before = { cls: span.className, runs: measure(span) };
  span.className = 'num text-2xs font-black text-text-secondary';
  const withNum = { cls: span.className, runs: measure(span) };
  span.className = 'num-text text-2xs font-black text-text-secondary';
  const withNumText = { cls: span.className, runs: measure(span) };
  return { before, withNum, withNumText };
});
console.log(JSON.stringify(ab, null, 1));
await b.close();
