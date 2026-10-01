import { pathToFileURL } from 'node:url';
const PKG = 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ ...(process.env.JEV_CHROME ? { executablePath: process.env.JEV_CHROME } : {}) });
const p = await b.newPage({ viewport: { width: 1366, height: 900 } });
await p.addInitScript(() => { try { sessionStorage.setItem('bors_auth_session','true'); } catch {} });
await p.goto('http://127.0.0.1:8013/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF', { waitUntil: 'load' });
await p.waitForTimeout(9000);
console.log(JSON.stringify(await p.evaluate(() => {
  const bar = document.querySelector('.nn-top-toolbar') as HTMLElement;
  const cs = getComputedStyle(bar);
  const kids = Array.from(bar.children).map((el) => {
    const r = (el as HTMLElement).getBoundingClientRect();
    const s = getComputedStyle(el as HTMLElement);
    return { cls: (el as HTMLElement).className.slice(0,28), display: s.display, pos: s.position,
             ml: s.marginLeft, mr: s.marginRight, fl: s.flex,
             rect: [Math.round(r.left), Math.round(r.top), Math.round(r.width)] };
  });
  return { toolbar: { display: cs.display, dir: cs.direction, justify: cs.justifyContent, gap: cs.gap, w: Math.round(bar.getBoundingClientRect().width) }, kids };
}), null, 1));
await b.close();
