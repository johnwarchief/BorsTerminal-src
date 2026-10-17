/** چه چیزی واقعاً ردیف‌ها را در DOM نشان می‌دهد؟ (تشخصی، نه ابزار مأموریت) */
import { createRequire } from 'node:module';
const req = createRequire('C:/Users/Johnkallnaya/Desktop/Borsterminal/.worktrees/system2-ui/frontend/index.js');
const { chromium } = req('playwright-core');
const BASE = process.argv[2] || 'http://127.0.0.1:8020';
const browser = await chromium.launch({
  executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe' });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
const page = await ctx.newPage();
await page.goto(BASE + '/#/market', { waitUntil: 'networkidle' });
await page.waitForTimeout(6000);
const info = await page.evaluate(() => {
  const all = document.querySelectorAll('*');
  const byTag: Record<string, number> = {};
  for (const el of all) byTag[el.tagName] = (byTag[el.tagName] ?? 0) + 1;
  const canvases = Array.from(document.querySelectorAll('canvas'))
    .map((c) => ({ w: c.width, h: c.height, cls: (c.className || '').slice(0, 60) }));
  const dataAttrs = new Set<string>();
  for (const el of all) for (const a of Array.from(el.attributes))
    if (a.name.startsWith('data-')) dataAttrs.add(a.name);
  return { total: all.length, byTag, canvases, dataAttrs: Array.from(dataAttrs).slice(0, 40),
    bodyText: document.body.innerText.slice(0, 300) };
});
console.log(JSON.stringify(info, null, 1));
await browser.close();
