const { chromium } = require('playwright');

const EV = 'D:/BorsTerminal-worktrees/4axes-main-integration/.superpowers/sdd/2026-11-06-workspace2-pattern-spotlight-kronos/evidence';

(async () => {
  const browser = await chromium.launch({ channel: 'msedge', headless: true, args: ['--no-proxy-server'] });
  for (const [width, height] of [[1366, 768], [1920, 1080]]) {
    const context = await browser.newContext({ viewport: { width, height }, reducedMotion: 'reduce', locale: 'fa-IR' });
    const page = await context.newPage();
    await page.goto('http://[::1]:5181/#/technical/%D9%81%D9%88%D9%84%D8%A7%D8%AF', { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="workspace-shell"]', { timeout: 30000 });
    await page.waitForTimeout(2500);

    const measure = async () => page.evaluate(() => {
      const dock = document.querySelector('[data-testid="workspace-dock"]');
      const chart = document.querySelector('[data-testid="panel-chart"]');
      const panels = Array.from(document.querySelectorAll('[data-testid^="panel-"]')).map((n) => n.getAttribute('data-testid'));
      const topbar = document.querySelector('[data-testid="workspace-topbar"]');
      return {
        panelCount: panels.length,
        panels,
        chartShare: dock && chart ? chart.getBoundingClientRect().width / dock.getBoundingClientRect().width : null,
        topbarScroll: topbar ? { scrollWidth: topbar.scrollWidth, clientWidth: topbar.clientWidth } : null,
      };
    });

    const analysis = await measure();
    await page.screenshot({ path: `${EV}/e1-analysis-${width}x${height}.png` });

    await page.click('[data-testid="workspace-mode-scan"]');
    await page.waitForTimeout(800);
    const scan = await measure();
    await page.screenshot({ path: `${EV}/e1-scan-${width}x${height}.png` });

    await page.click('[data-testid="workspace-mode-research"]');
    await page.waitForTimeout(800);
    const research = await measure();
    await page.screenshot({ path: `${EV}/e1-research-${width}x${height}.png` });

    if (width === 1366) {
      await page.keyboard.press('Control+k');
      await page.waitForTimeout(400);
      await page.screenshot({ path: `${EV}/e1-palette-1366x768.png` });
      await page.keyboard.press('Escape');
      await page.waitForTimeout(200);

      await page.click('[data-testid="layout-menu-btn"]');
      await page.fill('[data-testid="layout-name-input"]', 'چیدمان شاهد ۱۳۶۶');
      await page.click('[data-testid="layout-save-btn"]');
      await page.waitForTimeout(300);
      await page.click('[data-testid="layout-menu-btn"]');
      await page.waitForTimeout(300);
      await page.screenshot({ path: `${EV}/e1-layout-menu-1366x768.png` });
      await page.keyboard.press('Escape');
    }

    console.log(JSON.stringify({ width, height, analysis, scan, research }));
    await context.close();
  }
  await browser.close();
})().catch((error) => { console.error(error); process.exit(1); });
