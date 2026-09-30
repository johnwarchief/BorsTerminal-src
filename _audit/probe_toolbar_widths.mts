// _audit/probe_toolbar_widths.mts -- نوارِ فیلترِ تابلو در عرض‌های مختلف چند خط می‌شود؟
// پیش از ساختنِ هر «Dynamic Toolbar» باید عدد داشته باشیم: اورفلو، تعدادِ سطرِ wrap،
// و اینکه کدام کنترل واقعاً از کادر بیرون می‌زند.
const { pathToFileURL } = await import('node:url');
const PKG = process.env.JEV_BROWSER_DIR ?? 'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);
const b = await chromium.launch({ executablePath: process.env.JEV_CHROME, args: ['--no-sandbox'] });
const WIDTHS = (process.env.PROBE_WIDTHS ?? '1440,1280,1120,960,860').split(',').map(Number);
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
await p.goto('http://127.0.0.1:8002/#/market', { waitUntil: 'domcontentloaded' });
await p.waitForTimeout(35000);

const rows = [];
for (const w of WIDTHS) {
  await p.setViewportSize({ width: w, height: 900 });
  await p.waitForTimeout(2500);
  rows.push(
    await p.evaluate((width: number) => {
      const bar = document.querySelector('[data-testid="market-filters"]') as HTMLElement | null;
      const all = [...document.querySelectorAll('[data-testid="market-filters"] *')] as HTMLElement[];
      const lines = new Set<number>();
      let clipped = [] as string[];
      for (const el of all) {
        if (!el.textContent?.trim() || el.children.length) continue;
        const r = el.getBoundingClientRect();
        if (r.width > 0) lines.add(Math.round(r.top));
        const pr = (el.parentElement ?? el) as HTMLElement;
        if (pr.scrollWidth - pr.clientWidth > 2 && clipped.length < 4) {
          clipped.push(`${(el.textContent || '').trim().slice(0, 14)}(+${pr.scrollWidth - pr.clientWidth}px)`);
        }
      }
      const de = document.documentElement;
      return {
        width,
        found: !!bar,
        bar_h: bar ? Math.round(bar.getBoundingClientRect().height) : null,
        text_lines: lines.size,
        doc_overflow_x: de.scrollWidth - de.clientWidth,
        clipped: clipped.slice(0, 4),
      };
    }, w),
  );
}
console.log(JSON.stringify(rows, null, 1));
await b.close();
