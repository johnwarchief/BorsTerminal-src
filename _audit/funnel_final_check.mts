// _audit/funnel_final_check.mts — بند ۳۰ و ۳۱ِ مأموریت: سنجشِ زنده + evidence
//
// سه viewport واقعی (۱۳۶۶×۷۶۸ / ۱۹۲۰×۱۰۸۰ / ۳۶۰×۸۰۰) و هجده گامِ کلیک‌شدنی:
// ورود → تابلو → سه سیستم → افزودن/جابه‌جایی/حذفِ فیلتر → ذخیره و بازخوانی →
// سطر → گام‌هایِ تکنیکال/بنیادی/تحویل → بازرِس → بازگشت و حفظِ گام.
//
// چرا درِ خودِ صفحه نمی‌نویسیم «PASS»: هر گام عدد و متنِ خودش را درِ JSON
// می‌گذارد (pageOverflowX، بریدگیِ جدول، شمارِ دلیل‌هایِ دیدنی، ترتیبِ زنجیره)
// و هشدارها/خطاها با stack کامل ثبت می‌شوند. قضاوتِ «درست است یا نه» با مالک است.
//
//   node --experimental-strip-types _audit/funnel_final_check.mts \
//        --url http://127.0.0.1:5173/ --widths 1366,1920,360
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const { chromium } = await import(pathToFileURL(`${PKG}/node_modules/playwright/index.mjs`).href);

const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:5173/');
const WIDTHS = (arg('widths', '1366,1920,360')).split(',').map((w) => Number.parseInt(w, 10));
const HEIGHTS: Record<number, number> = { 1366: 768, 1920: 1080, 360: 800 };

// هر console.error/warn با stackِ خودش — React این پیام را با «کدامِ کامپوننت»
// می‌فرستد و بی stack فقط متنش برایِ علت‌یابیِ «به‌هنگامِ رندر» بی‌فایده است.
const HOOK = () => {
  const w: any[] = ((window as any).__consoleShots ||= []);
  for (const kind of ['warn', 'error'] as const) {
    const orig = console[kind];
    console[kind] = (...a: unknown[]) => {
      w.push({
        kind,
        text: a.map((x) => (typeof x === 'string' ? x : String(x))).join(' ').slice(0, 600),
        stack: String(new Error('shot').stack).split('\n').slice(1, 14).join(' | '),
      });
      return (orig as Function).apply(console, a as never);
    };
  }
  try { localStorage.setItem('bors.onboarding-seen', '1'); } catch { /* jsdom-less */ }
};

const browser = await chromium.launch({ headless: true, executablePath: process.env.JEV_CHROME || undefined });
const report: Record<string, unknown> = { base: BASE, at: new Date().toISOString(), viewports: {} };

for (const width of WIDTHS) {
  const height = HEIGHTS[width] ?? 900;
  const ctx = await browser.newContext({ viewport: { width, height } });
  await ctx.addInitScript(() => sessionStorage.setItem('bors_auth_session', 'true'));
  await ctx.addInitScript(HOOK as never);
  const page = await ctx.newPage();
  const r: Record<string, unknown> = { viewport: { width, height }, steps: {} as Record<string, unknown> };
  const steps = r.steps as Record<string, unknown>;
  // زمان/حجمِ هر درخواستِ قیف — بند ۳۵ (benchmark) از همین‌جا خوانده می‌شود
  const reqs: Array<{ url: string; ms: number; bytes: number }> = [];
  const t0 = new Map<string, number>();
  page.on('request', (req: any) => { if (String(req.url()).includes('/api/funnel')) t0.set(req.url(), Date.now()); });
  page.on('requestfinished', async (req: any) => {
    const url = String(req.url());
    if (!url.includes('/api/funnel') || !t0.has(url)) return;
    let bytes = 0;
    try { const b = await req.response()!.body(); bytes = b.length; } catch { /* bodyِِ streamشده در دسترس نیست */ }
    reqs.push({ url: url.replace(/^https?:\/\/[^/]+/, ''), ms: Date.now() - (t0.get(url) ?? 0), bytes });
  });
  try {
    await page.goto(`${BASE}#/master`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('[data-testid="fts-funnel-workspace"]', { timeout: 60_000 });
    await page.waitForSelector('[data-testid="funnel-stage-tape"]', { timeout: 60_000 });
    // پاسخِ first funnel باید واقعاً رسیده باشد (universe غیرصفر) — بی‌این،
    // هر شمارشی رویِ صفحۀ خالی خوانده می‌شد و «۰» را به‌جایِ عددِ بازار می‌گفت.
    await page.waitForFunction(() => {
      const el = document.querySelector('[data-testid="funnel-universe-screening"]');
      return el ? !/: *۰+$/.test((el.textContent ?? '').trim()) : false;
    }, undefined, { timeout: 90_000 });

    const ov = () => page.evaluate(() => ({
      overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));
    steps.enter_default = await page.evaluate(() => ({
      tape: !!document.querySelector('[data-testid="funnel-stage-tape"]'),
      technicalShown: !!document.querySelector('[data-testid="funnel-stage-technical"]'),
      active: document.querySelector('[data-testid="fts-process-stepper"] [aria-current="step"]')
        ?.getAttribute('data-testid') ?? null,
    }));

    const countsLine = () => page.evaluate(() =>
      (document.querySelector('[data-testid="funnel-counts"]')?.textContent ?? '').replace(/\s+/g, ' ').trim());
    for (const mode of ['swing', 'trend', 'custom']) {
      await page.click(`[data-testid="funnel-mode-${mode}"]`);
      // ۲۵۰ms بعد: جدول نباید به «universe: ۰» برگردد (keepPreviousData)
      await page.waitForTimeout(250);
      steps[`switch_${mode}_immediate`] = await countsLine();
      await page.waitForTimeout(1_400);
      steps[`mode_${mode}`] = await page.evaluate(() => ({
        pressed: document.querySelector('[data-testid^="funnel-mode-"]')
          ? Array.from(document.querySelectorAll('[data-testid^="funnel-mode-"]'))
              .filter((el) => !['funnel-mode-reverse', 'funnel-mode-review'].includes(el.getAttribute('data-testid')!))
              .map((el) => `${el.getAttribute('data-testid')}=${el.getAttribute('aria-pressed')}`)
          : null,
        builder: !!document.querySelector('[data-testid="funnel-custom-builder"]'),
      }));
    }

    // زنجیره: افزودن → جابه‌جایی → حذف → ذخیره → بازخوانی
    await page.click('[data-testid="funnel-mode-custom"]');
    await page.waitForTimeout(500);
    await page.click('[data-testid="funnel-chain-add"]');
    await page.waitForSelector('[data-testid="funnel-chain-menu"]', { timeout: 15_000 });
    // رجیستری یک پرس‌وجویِ جداست؛ بی‌صبر‌کردن تا نشستنش، فهرستِ خالیِ «هیچ
    // فیلتری نیست» خوانده می‌رفت و گام‌هایِ بعدی رویِ صفر اجرا می‌شدند.
    await page.waitForSelector('[data-testid^="funnel-chain-pick-"]', { timeout: 30_000 });
    steps.registry_choices = await page.evaluate(() =>
      Array.from(document.querySelectorAll('[data-testid^="funnel-chain-pick-"]'))
        .map((el) => el.getAttribute('data-testid')!.replace('funnel-chain-pick-', '')));
    for (const id of (steps.registry_choices as string[]).slice(0, 2)) {
      await page.click(`[data-testid="funnel-chain-pick-${id}"]`);
      // زنجیره عوض شد ⇒ پرسشِ تازه از موتور؛ شمارشِ کنارِ چیپ از همان پاسخ می‌آید
      try {
        await page.waitForSelector(`[data-testid="funnel-chain-count-${id}"]`, { timeout: 45_000 });
      } catch { /* شمارش نیامد — درِ خودِ JSON ثبت می‌شود، پنهان نمی‌ماند */ }
      await page.click('[data-testid="funnel-chain-add"]');
      await page.waitForTimeout(300);
    }
    // منو را ببند: درِ عرضِ ۳۶۵ پنجاهِ مطلقِ منو رویِ دکمه‌هایِ همان سرخط
    // می‌افتد و کلیکِ بعدی مسدود می‌شود (این خودِ UI هم همین‌طور است).
    if (await page.locator('[data-testid="funnel-chain-menu"]').count()) {
      await page.click('[data-testid="funnel-chain-add"]');
      await page.waitForTimeout(250);
    }
    const readChain = () => page.evaluate(() =>
      Array.from(document.querySelectorAll('[data-testid^="funnel-chain-f_"]'))
        .map((el) => el.getAttribute('data-testid')!.replace('funnel-chain-', '')));
    steps.chain_before = await readChain();
    const second = (steps.chain_before as string[])[1];
    if (second) {
      await page.click(`[data-testid="funnel-chain-up-${second}"]`);
      try { await page.waitForTimeout(1_400); } catch { /* همان بالا */ }
      steps.chain_after_reorder = await readChain();
      steps.counts_after_reorder = await page.evaluate(() =>
        Array.from(document.querySelectorAll('[data-testid^="funnel-chain-count-"]'))
          .map((el) => `${el.getAttribute('data-testid')!.replace('funnel-chain-count-', '')}:${el.textContent}`));
    }
    try {
      await page.waitForFunction(() => !/: *۰+$/.test((document.querySelector('[data-testid="funnel-universe-screening"]')?.textContent ?? '').trim()),
                                 undefined, { timeout: 60_000 });
    } catch { /* ثبتِ خودِ عدد درِ steps.table کافی است */ }
    steps.table = await page.evaluate(() => {
      const box = document.querySelector('[data-testid="funnel-stage-tape"]');
      const tb = box?.querySelector('table');
      return {
        tableWidth: tb ? Math.round(tb.getBoundingClientRect().width) : null,
        boxWidth: box ? Math.round(box.getBoundingClientRect().width) : null,
        domRows: box ? box.querySelectorAll('tbody tr').length : 0,
        headerCount: document.querySelectorAll('[data-testid="funnel-counts"] span').length,
        counts: (document.querySelector('[data-testid="funnel-counts"]')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
        ruled: Array.from(document.querySelectorAll('[data-testid^="funnel-ruled-"]'))
          .map((el) => `${el.getAttribute('data-testid')!.replace('funnel-ruled-', '')}:${el.textContent}`),
      };
    });
    steps.reasons = await page.evaluate(() => {
      const cells = Array.from(document.querySelectorAll('[data-testid^="funnel-why-"]'));
      const seen = cells.filter((el) => (el.textContent ?? '').trim().length > 1);
      return { rendered: cells.length, withReason: seen.length, sample: seen.slice(0, 3).map((el) => el.textContent) };
    });
    const first = (steps.chain_before as string[])[0];
    if (first) {
      await page.click(`[data-testid="funnel-chain-remove-${first}"]`);
      await page.waitForTimeout(900);
      steps.chain_after_remove = await readChain();
    }
    await page.fill('[data-testid="funnel-chain-name"]', 'سنجشِ نهایی');
    await page.click('[data-testid="funnel-chain-save"]');
    await page.waitForTimeout(400);
    steps.saved = await page.evaluate(() =>
      Array.from(document.querySelectorAll('[data-testid^="funnel-chain-load-"]'))
        .map((el) => el.getAttribute('data-testid')!.replace('funnel-chain-load-', '')));
    await page.click('[data-testid="funnel-chain-reset"]');
    await page.waitForTimeout(700);
    steps.chain_after_reset = await readChain();
    await page.click('[data-testid="funnel-chain-load-سنجشِ نهایی"]');
    await page.waitForTimeout(1_500);
    steps.chain_after_load = await readChain();

    for (const st of ['technical', 'fundamental', 'handover']) {
      await page.click(`[data-testid="fts-step-${st}"]`);
      await page.waitForTimeout(2_200);
      steps[`stage_${st}`] = await page.evaluate(() => {
        const box = document.querySelector(`[data-testid="funnel-stage-${document.querySelector('[data-testid="fts-process-stepper"] [aria-current="step"]')?.getAttribute('data-testid')?.replace('fts-step-', '') ?? 'tape'}"]`);
        return {
          active: document.querySelector('[data-testid="fts-process-stepper"] [aria-current="step"]')?.getAttribute('data-testid') ?? null,
          renderedRows: box ? box.querySelectorAll('tbody tr').length : 0,
          ruled: box ? (box.querySelector('[data-testid^="funnel-ruled-"]')?.textContent ?? '').trim() : null,
          notRequired: box ? (box.querySelector('[data-testid^="funnel-not-required-"]')?.textContent ?? '').trim() : null,
          coverage: (document.querySelector('[data-testid="funnel-tech-coverage"]')?.textContent ?? '').replace(/\s+/g, ' ').trim(),
        };
      });
      steps[`stage_${st}_overflow`] = await ov();
    }

    // سطر → بازرِس → بازگشت و حفظِ گام
    await page.click('[data-testid="fts-step-technical"]');
    await page.waitForTimeout(1_800);
    const rowBtn = page.locator('[data-testid="funnel-stage-technical"] tbody tr button').first();
    const symText = (await rowBtn.textContent())?.trim() ?? '';
    await rowBtn.click();
    await page.waitForTimeout(2_500);
    steps.row_click = await page.evaluate(() => ({
      href: location.href.slice(0, 120),
      inspectorStages: Array.from(document.querySelectorAll('[data-testid^="inspector-stage-"]'))
        .map((el) => `${el.getAttribute('data-testid')!.replace('inspector-stage-', '')}:${el.getAttribute('data-stage-state') ?? ''}`),
    }));
    steps.row_click.clicked = symText;
    await page.goBack();
    await page.waitForTimeout(2_500);
    steps.back = await page.evaluate(() => ({
      href: location.href.slice(0, 120),
      active: document.querySelector('[data-testid="fts-process-stepper"] [aria-current="step"]')?.getAttribute('data-testid') ?? null,
      technicalShown: !!document.querySelector('[data-testid="funnel-stage-technical"]'),
    }));

    r.overflowX = (await ov()).overflowX;
    r.funnel_requests = reqs;
    r.console = await page.evaluate(() => (window as any).__consoleShots ?? []);
    r.screenshot = `funnel_final_${width}.png`;
    await page.screenshot({ path: `_audit/funnel_final_${width}.png`, fullPage: false });
  } catch (e) {
    r.error = String(e).slice(0, 400);
    try {
      r.console = await page.evaluate(() => (window as any).__consoleShots ?? []);
    } catch { /* صفحه بسته است */ }
  }
  (report.viewports as Record<string, unknown>)[String(width)] = r;
  await ctx.close();
}

await browser.close();
mkdirSync('_audit', { recursive: true });
const out = arg('out', '_audit/funnel_final_all.json');
writeFileSync(out, JSON.stringify(report, null, 1), 'utf-8');
for (const width of WIDTHS) {
  const v = (report.viewports as Record<string, any>)[String(width)];
  const c = (v.console ?? []) as any[];
  console.log(`${width}: overflowX=${v.overflowX} console(err/warn)=${c.filter((x) => x.kind === 'error').length}/${c.filter((x) => x.kind === 'warn').length} error=${v.error ?? '-'}`);
}
console.log(`written ${out}`);
