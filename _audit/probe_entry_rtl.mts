// _audit/probe_entry_rtl.mts -- «ورود به بازار» (#61): جهت و ترازِ واقعیِ سطرِ حکم
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const p = await b.newPage({ viewport: { width: 1366, height: 1000 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto(process.env.PROBE_BASE ?? 'http://127.0.0.1:8002', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(40000);

const out = await p.evaluate(() => {
  const strip = document.querySelector('[data-testid="pulse-verdict"]') as HTMLElement | null;
  if (!strip) return { found: false };
  const cs = (el: Element) => {
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    return {
      dir: s.direction,
      align: s.textAlign,
      text: (el.textContent ?? '').trim().slice(0, 46),
      left: Math.round(r.left),
      right: Math.round(r.right),
    };
  };
  const row = strip.querySelector('div');
  const kids = row ? [...row.children].map(cs) : [];
  const gates = [...strip.querySelectorAll('[data-testid^="pulse-verdict-gate-"]')].slice(0, 3).map(cs);
  return {
    found: true,
    strip: cs(strip),
    row_dir: row ? getComputedStyle(row).direction : null,
    row_display: row ? getComputedStyle(row).display : null,
    first_line: kids,
    gates,
    html_head: strip.innerHTML.slice(0, 220),
  };
});
await p.locator('[data-testid="pulse-verdict"]').screenshot({ path: '_audit/entry_rtl_strip.png' }).catch(() => {});
console.log(JSON.stringify(out, null, 1));
await b.close();
