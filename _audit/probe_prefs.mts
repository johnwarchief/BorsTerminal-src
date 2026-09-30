import { pathToFileURL } from 'node:url';
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/master', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(16000);
console.log(JSON.stringify(await p.evaluate(() => {
  const sec = (id: string) => document.querySelector(`[data-testid="${id}"]`)?.closest('section')?.getAttribute('data-testid') ?? null;
  const h = (id: string) => Math.round(document.querySelector(`[data-testid="${id}"]`)?.getBoundingClientRect().height ?? -1);
  return {
    prefs_owner: sec('funnel-prefs'), tape_owner: sec('funnel-tape-prefs'), gate_owner: sec('funnel-tech-gate'),
    prefs_count: document.querySelectorAll('[data-testid="funnel-prefs"]').length,
    headerH: { tape: h('funnel-tape-prefs'), fund: h('funnel-prefs') },
    overflowX_any: Array.from(document.querySelectorAll('[data-testid^="funnel-stage-"]')).filter((e) => (e as HTMLElement).scrollWidth > (e as HTMLElement).clientWidth + 2).map((e) => e.getAttribute('data-testid')),
  };
}), null, 1));
await b.close();
