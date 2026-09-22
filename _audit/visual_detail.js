// Pinpoint the exact overflowing/clipped elements per route.
const { chromium } = require('playwright-core');
const fs = require('fs');

const ROUTES = [
  { name: 'fundamental', url: 'http://localhost:8001/#/fundamental' },
  { name: 'technical', url: 'http://localhost:8001/#/technical' },
];

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true,
    args: ['--no-first-run', '--no-default-browser-check'] });
  const out = {};

  for (const r of ROUTES) {
    const ctx = await browser.newContext({ viewport: { width: 768, height: 900 } });
    const page = await ctx.newPage();
    await page.goto(r.url, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(4000);
    const needsLogin = await page.locator('input[placeholder="admin"]').count().catch(() => 0);
    if (needsLogin > 0) {
      await page.locator('input[placeholder="admin"]').fill('admin');
      await page.locator('input[type="password"]').first().fill('bors123');
      await page.getByRole('button', { name: /ورود به ایستگاه/i }).click();
      await page.waitForTimeout(8000);
      await page.goto(r.url, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(4000);
    }

    out[r.name] = await page.evaluate(() => {
      const vw = document.documentElement.clientWidth;
      const res = { vw, overflow: [], clipped: [] };
      document.querySelectorAll('*').forEach(el => {
        const rct = el.getBoundingClientRect();
        const cls = (el.className || '').toString();
        // only report the widest offenders, not every nested child
        if (rct.width > vw + 2 && (rct.left < 0 || rct.right > vw + 2)) {
          if (el.children.length > 0) {
            res.overflow.push({ tag: el.tagName, cls: cls.slice(0, 70),
              left: Math.round(rct.left), right: Math.round(rct.right),
              w: Math.round(rct.width),
              txt: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 40) });
          }
        }
        if (el.children.length === 0) {
          const t = (el.textContent || '').trim();
          if (t.length < 3) return;
          const s = getComputedStyle(el);
          if ((s.overflow === 'hidden' || s.textOverflow === 'ellipsis') &&
              el.scrollWidth > el.clientWidth + 1) {
            res.clipped.push({ txt: t.slice(0, 34), cls: cls.slice(0, 46),
              sw: el.scrollWidth, cw: el.clientWidth });
          }
        }
      });
      // de-duplicate overflow by class
      const seen = new Set();
      res.overflow = res.overflow.filter(o => {
        const k = o.cls + o.w;
        if (seen.has(k)) return false;
        seen.add(k);
        return true;
      }).slice(0, 10);
      res.clipped = res.clipped.slice(0, 14);
      return res;
    });
    await ctx.close();
  }

  fs.writeFileSync('_visual_detail.json', JSON.stringify(out, null, 1), 'utf-8');
  for (const [name, r] of Object.entries(out)) {
    console.log('\n=== %s (vw %d) ===' % (name, r.vw));
    console.log('overflow:');
    r.overflow.forEach(o => console.log('  %-6s w=%-5d left=%-5d %s | %s',
      o.tag, o.w, o.left, o.cls.slice(0, 46), o.txt));
    console.log('clipped:');
    r.clipped.forEach(c => console.log('  %-34s sw=%-5d cw=%-5d %s', c.txt, c.sw, c.cw, c.cls.slice(0, 30)));
  }
  await browser.close();
}

main().catch(e => { console.error('FATAL', e); process.exit(1); });
