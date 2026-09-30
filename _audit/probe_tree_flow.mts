// _audit/probe_tree_flow.mts -- آیا دانه‌های «جریان مسیر» واقعاً حرکت می‌کنند؟ (#60)
// فقط خواندنی: شمارِ المان‌هایِ انیمیشن‌دار و نمونه‌برداریِ opacityِ آن‌ها در چند لحظه.
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/strategy-tree', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(25000);

const flags = await p.evaluate(() => ({
  root: {
    flow: document.documentElement.dataset.treeFlow ?? null,
    running: document.documentElement.dataset.treeFlowRunning ?? null,
  },
  reduce: matchMedia('(prefers-reduced-motion: reduce)').matches,
  comets: document.querySelectorAll('.fts-comet').length,
  pathFlow: document.querySelectorAll('.fts-path-flow').length,
  cometAnim: (() => {
    const el = document.querySelector('.fts-comet');
    if (!el) return null;
    const s = getComputedStyle(el);
    return { name: s.animationName, dur: s.animationDuration, state: s.animationPlayState, fill: s.fill };
  })(),
}));

const samples: number[][] = [];
for (let i = 0; i < 6; i++) {
  samples.push(
    await p.evaluate(() =>
      [...document.querySelectorAll('.fts-comet')].slice(0, 6).map((e) => Number(getComputedStyle(e).opacity)),
    ),
  );
  await p.waitForTimeout(300);
}
const moving = samples[0].map((_, col) => new Set(samples.map((s) => s[col]?.toFixed(3))).size > 1);
console.log(JSON.stringify({ flags, samples, anyColumnChanged: moving.some(Boolean) }, null, 1));
await b.close();
