/**
 * tools/ra_live_probe.mts — مهندسیِ معکوسِ زندهٔ چارت ره‌آورد با jev-browser
 *
 * چرا این ابزار: Qoder Browser Connector داخلِ iframeِ `blob:` چارت ره‌آورد را نمی‌بیند
 * (درختِ دسترس‌پذیری روی گرهٔ «Financial Chart» می‌ایستد) و evaluate_script روی این
 * سایت به دلیل CSP مقدار `{}` برمی‌گرداند. Chromium ایزولهٔ jev-browser با
 * page.frames() به فریم‌های هم‌ریشه (blob: همان origin) دسترسی دارد؛ پس اینجا
 * همان DOMِ واقعیِ ابزارها و دیالوگ‌ها خوانده می‌شود — نه حدس از باندل.
 *
 * هیچ لاگینی اینجا نیست: نشستِ تازهٔ بی‌نام کاربر. بنابراین هیچ چیزی روی حساب
 * کاربر یا روی ترسیم‌های ذخیره‌شدۀ نمادی ذخیره نمی‌شود.
 *
 *   node --experimental-strip-types tools/ra_live_probe.mts --action frames
 *   node --experimental-strip-types tools/ra_live_probe.mts --action toolbar
 *   node --experimental-strip-types tools/ra_live_probe.mts --action indicators
 *   node --experimental-strip-types tools/ra_live_probe.mts --action settings
 */
import { mkdirSync, writeFileSync } from 'node:fs';
import { pathToFileURL } from 'node:url';

const PKG =
  process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const { chromium } = await imp('node_modules/playwright/index.mjs');

const arg = (name: string, fallback = ''): string => {
  const i = process.argv.indexOf(`--${name}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : fallback;
};
const flag = (name: string): boolean => process.argv.includes(`--${name}`);
const ACTION = arg('action', 'frames');
const URL = arg('url', 'https://rahavard365.com/asset/167/chart');
const OUT = arg('out', '_audit/ra_live_probe.json');
const WAIT_MS = Number.parseInt(arg('wait', '25000'), 10);
const CHROME = process.env.JEV_CHROME ?? '';

const report: Record<string, unknown> = { action: ACTION, url: URL };

// نشستِ پایدار: پروفایلِ محوریِ خودمان (نه پروفایلِ کرومِ کاربر) تا لاگینِ ره‌آورد
// میان اجراها بماند. کاربر یک بار خودش لاگین می‌کند (--action open)، بعد
// پراب‌ها همان کوکی را می‌خوانند. بیرون از this repo جایی نوشته نمی‌شود.
const PROFILE = arg('profile', '_audit/ra-profile');
mkdirSync(PROFILE, { recursive: true });
const context = await chromium.launchPersistentContext(PROFILE, {
  // حالت open یعنی «پنجره را ببین و لاگین کن» — پس هدفول نیست.
  headless: !(flag('--show') || ACTION === 'open'),
  viewport: null,
  locale: 'fa-IR',
  args: ['--window-position=60,50', '--window-size=1560,920'],
  executablePath: CHROME || undefined,
});
const page = context.pages()[0] ?? (await context.newPage());
const errors: string[] = [];
page.on('pageerror', (e: { message: string }) => errors.push(`pageerror: ${e.message}`.slice(0, 160)));
page.on('requestfailed', (r: { url: () => string }) => errors.push(`reqfail: ${r.url().slice(0, 120)}`));

if (ACTION === 'open') {
  // پنجرۀ واقعی را باز می‌گذارد تا مالک خودش لاگین کند؛ هر ۱۵ ثانیه آدرس را چاپ
  // می‌کند تا وضعیت پیدا باشد. با Ctrl+C یا مهلتِ --minutes بسته می‌شود.
  const minutes = Number.parseInt(arg('minutes', '25'), 10);
  await page.goto(URL, { waitUntil: 'domcontentloaded' });
  await page.bringToFront();
  const log = (line: string) => {
    writeFileSync('_audit/ra_open.log', `${new Date().toISOString()} ${line}\n`, { flag: 'a' });
    console.log(line);
  };
  log(`RA_OPEN_WINDOW ${URL} (پروفایل: ${PROFILE})`);
  const until = Date.now() + minutes * 60_000;
  while (Date.now() < until) {
    await page.waitForTimeout(15_000);
    await page.bringToFront();
    log(`RA_URL ${page.url()}`);
  }
  await context.close();
  process.exit(0);
}

await page.goto(URL, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(WAIT_MS);

report.frames = page.frames().map((f: { name(): string; url(): string }) => ({
  name: f.name(),
  href: String(f.url()).slice(0, 160),
}));

/** همهٔ فریم‌هایی که چیزی شبیه چارت دارند (blob: یا charting_library) */
const chartFrames = page.frames().filter((f: { url(): string }) => {
  const h = String(f.url());
  return h.includes('blob:') || h.includes('charting') || h.includes('chart');
});
report.chartFrameCount = chartFrames.length;

const scan = async (fn: string, label: string) => {
  const out: Record<string, unknown> = {};
  // Playwright رشتهٔ عبارت را مستقیم evaluate می‌کند؛ new Function(...) با
  // toString به `[Function (anonymous)]` تبدیل می‌شود و نتیجه `{}` می‌گردد.
  const expr = `(function(){${fn}})()`;
  for (let i = 0; i < chartFrames.length; i++) {
    const f = chartFrames[i];
    const key = `frame${i}:${String(f.url()).slice(0, 40)}`;
    try {
      out[key] = await f.evaluate(expr);
    } catch (e) {
      out[key] = `ERR ${String((e as Error).message).slice(0, 140)}`;
    }
  }
  report[label] = out;
};

if (ACTION === 'sweep') {
  // جاروی کاملِ خواندنی: گزینه‌های تعدیل/نوع‌قیمت، سپس هر گروه ابزار ترسیم،
  // سپس دیالوگ اندیکاتورها و دیالوگ تنظیمات چارت. هیچ ترسمی ساخته/حذف نمی‌شود.
  const chart = chartFrames[chartFrames.length - 1];
  if (!chart) {
    report.sweep = 'no chart frame';
  } else {
    const readOptions = async (titleText: string) =>
      await chart.evaluate(
        `(function(){
          const host=[...document.querySelectorAll('[title]')].find(e=>(e.getAttribute('title')||'').includes(${JSON.stringify(titleText)}));
          if(!host) return null;
          const sel=host.querySelector('select');
          const opts=sel?[...sel.options].map(o=>o.textContent.trim()+' = '+o.value):null;
          return {html: host.textContent.replace(/\\s+/g,' ').trim().slice(0,300), opts};
        })()`,
      );
    report.adjustment = await readOptions('نوع تعدیل');
    report.priceType = await readOptions('نوع قیمت');

    // هر گروه نوار ابزار ترسیم: ساختارِ DOM همان گروه، **بی‌نیاز از هاور**.
    // چرا: flyout در TV فرزندِ خودِ گرهٔ گروه است و در DOM حضور دارد؛ فقط
    // پنهان است. هم هاور و هم دیفِ «گره‌های دیدنی» چیزی نو نمی‌دادند (#164).
    const flyouts = await chart.evaluate(
      `(function(){
        const out={};
        for(const g of document.querySelectorAll('[data-name^="linetool-group-"]')){
          const key=g.getAttribute('data-name');
          const items=new Set();
          for(const e of g.querySelectorAll('[data-name],[title]')){
            const nm=e.getAttribute('data-name')||'';
            if(!nm||nm===key||nm.startsWith('linetool-group-')) continue;
            const ti=(e.getAttribute('title')||'').trim().replace(/\\s+/g,' ').slice(0,50);
            items.add(nm+(ti?' @@ '+ti:''));
          }
          out[key]=[...items].slice(0,80);
        }
        return out;
      })()`,
    );
    report.drawingFlyouts = flyouts;
    const clickIn = async (dataName: string) =>
      chart.evaluate(
        `(function(){
          const e=document.querySelector('[data-name="${dataName}"]');
          if(!e) return 'missing';
          e.scrollIntoView(); e.click();
          return 'clicked';
        })()`,
      );
    // دیالوگ اندیکاتورها: دسته‌ها + نامِ همهٔ مطالعات (کلیکِ evaluate، چون
    // locator.click روی این دکمهٔ داخلِ blob: iframe تایم‌اوت می‌داد)
    try {
      report.indicatorsClick = await clickIn('open-indicators-dialog');
      await page.waitForTimeout(2800);
      report.indicatorsDialog = await chart.evaluate(
        `(function(){
          const txt=(e)=>(e.textContent||'').trim().replace(/\\s+/g,' ').slice(0,60);
          const dlg=[...document.querySelectorAll('[class*="dialog"]')].sort((a,b)=>b.textContent.length-a.textContent.length)[0];
          if(!dlg) return {err:'no dialog node'};
          const cats=[...dlg.querySelectorAll('.tab-widget-item, [class*="tab-widget"], [class*="category"]')].map(txt).filter(Boolean);
          const names=[...dlg.querySelectorAll('.item-row, [class*="item-row"], [class*="indicator-name"], [class*="item-"]')]
            .map(txt).filter(Boolean);
          return {cats:[...new Set(cats)].slice(0,40), names:[...new Set(names)].slice(0,400), text:dlg.textContent.replace(/\\s+/g,' ').slice(0,2500)};
        })()`,
      );
      await page.keyboard.press('Escape');
      await page.waitForTimeout(600);
      // دیالوگِ اندیکاتورها با یک Escape بسته نمی‌شود؛ اگر باز بماند، «بزرگ‌ترین
      // دیالوگ» در مرحلهٔ بعدی همان لیستِ مطالعات است و تب‌های تنظیمات غلط می‌آیند.
      report.indicatorsStillOpen = await chart.evaluate(
        `(function(){
          const d=[...document.querySelectorAll('[class*="dialog"]')].filter(e=>e.getClientRects().length&&(e.textContent||'').includes('Script name'));
          if(!d.length) return false;
          const b=[...d[0].querySelectorAll('button,[class*="close"]')].find(e=>/Close|بستن/i.test(e.getAttribute('aria-label')||e.textContent||''));
          if(b) b.click();
          return true;
        })()`,
      );
      await page.keyboard.press('Escape');
      await page.waitForTimeout(900);
    } catch (e) {
      report.indicatorsDialog = `ERR ${String((e as Error).message).slice(0, 120)}`;
    }

    // دیالوگ تنظیمات چارت — تک‌تکِ تب‌ها خوانده می‌شوند و در پایان با
    // Escape بسته می‌شود (هیچ گزینه‌ای تیک نمی‌خورد؛ فقط نگاه کردن).
    // دیالوگ از روی *عنوانش* انتخاب می‌شود، نه بزرگ‌ترین متن. (offsetParent
    // برای گرهٔ position:fixed نال است، پس با getClientRects زنده‌بودنش می‌سنجیم.)
    const SETTINGS = `(function(){
      return [...document.querySelectorAll('[class*="dialog"]')]
        .filter(e=>e.getClientRects().length&&/Chart settings|تنظیمات چارت/i.test(e.textContent||''))
        .sort((a,b)=>b.textContent.length-a.textContent.length)[0];
    })()`;
    try {
      report.propertiesClick = await clickIn('header-toolbar-properties');
      await page.waitForTimeout(2600);
      const tabTexts = await chart.evaluate(
        `(function(){
          const dlg=${SETTINGS};
          if(!dlg) return [];
          return [...dlg.querySelectorAll('[class*="tab"] [class*="title"], .tabbar-wrapper [class*="item"], [role="tab"]')]
            .map(e=>(e.textContent||'').trim().replace(/\\s+/g,' ')).filter(Boolean).slice(0,20);
        })()`,
      );
      const tabsOut: Record<string, unknown> = {};
      for (const label of [...new Set((tabTexts as string[]) ?? [])]) {
        try {
          await chart.evaluate(
            `(function(){
              const dlg=${SETTINGS};
              const t=[...dlg.querySelectorAll('[class*="tab"] [class*="title"], .tabbar-wrapper [class*="item"], [role="tab"]')]
                .find(e=>((e.textContent||'').trim().replace(/\\s+/g,' '))===${JSON.stringify(label)});
              if(t) t.click();
              return !!t;
            })()`,
          );
          await page.waitForTimeout(700);
          tabsOut[label] = await chart.evaluate(
            `(function(){
              const dlg=${SETTINGS};
              const body=[...dlg.querySelectorAll('[class*="tab-pane"], [class*="content"], form')].sort((a,b)=>b.textContent.length-a.textContent.length)[0]||dlg;
              const ctl=[...body.querySelectorAll('input,select,[class*="switch"],[class*="checkbox"]')].map(e=>({
                type:e.getAttribute('type')||e.tagName.toLowerCase(),
                val:e.getAttribute('value')||(e.getAttribute('class')||'').includes('checked')?'on':'',
              }));
              return {text:body.textContent.replace(/\\s+/g,' ').trim().slice(0,1400), controls:ctl.slice(0,40)};
            })()`,
          );
        } catch (e) {
          tabsOut[label] = `ERR ${String((e as Error).message).slice(0, 80)}`;
        }
      }
      report.chartPropertyTabs = tabsOut;
      await page.keyboard.press('Escape');
    } catch (e) {
      report.chartProperties = `ERR ${String((e as Error).message).slice(0, 120)}`;
    }
  }
  await page.screenshot({ path: OUT.replace(/\.json$/, '.png') });
  writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
  console.log('sweep written to', OUT);
  await context.close();
  process.exit(0);
}

if (ACTION === 'frames' || ACTION === 'toolbar' || ACTION === 'inventory') {
  // شمارش گره‌ها + کلیدهای کلاس/اتریبیوت که وجود دارند
  await scan(`
    const pick = (sel) => { try { return document.querySelectorAll(sel).length } catch (e) { return -1 } };
    const txt = (e) => (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 50);
    const titled = [...document.querySelectorAll('[title]')].map((e) => ({
      tag: e.tagName.toLowerCase(),
      title: e.getAttribute('title'),
      name: e.getAttribute('data-name'),
      cls: (typeof e.className === 'string' ? e.className : '').slice(0, 60),
      text: txt(e),
    }));
    const buttons = [...document.querySelectorAll('button')].map((e) => ({
      text: txt(e),
      title: e.getAttribute('title'),
      aria: e.getAttribute('aria-label'),
      cls: (typeof e.className === 'string' ? e.className : '').slice(0, 60),
    }));
    return {
      title: document.title,
      nodes: document.querySelectorAll('*').length,
      buttons: pick('button'),
      drawingsToolbar: pick('.drawing-main-toolbar-item, .main-toolbar-button, [data-name]'),
      category: pick('.category-item'),
      dialog: pick('[class*="dialog"]'),
      tabbar: pick('[class*="tab"]'),
      firstDataNames: [...document.querySelectorAll('[data-name]')].slice(0, 120).map(e => e.getAttribute('data-name')),
      titled,
      buttonList: buttons,
    };
  `, 'dom');
}

const clickInFrames = async (selector: string) => {
  for (const f of chartFrames) {
    try {
      const btn = f.locator(selector);
      if ((await btn.count()) > 0) {
        await btn.first().click({ timeout: 8000 });
        return true;
      }
    } catch (e) {
      report.lastClickError = String((e as Error).message).slice(0, 120);
    }
  }
  return false;
};

if (ACTION === 'indicators') {
  // دکمۀ «Indicators» را در همان فریم پیدا و کلیک کن، بعد فهرست مطالعات را بخوان
  await clickInFrames('button:has-text("Indicators"), button:has-text("اندیکاتور")');
  await page.waitForTimeout(4000);
  await scan(`
    const txt = (e) => (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 60);
    const cats = [...document.querySelectorAll('[class*="manage-indicators"], .tab-widget, [class*="tab"]')].map(txt).slice(0, 30);
    const studies = [...document.querySelectorAll('.item-_25C6mwm-, [class*="item-"][class*="indicator"], .category-window-item, [class*="study"] .item')]
      .map(txt).filter(Boolean).slice(0, 200);
    return { cats, studies, dialogText: (document.querySelector('[class*="dialog"]')?.textContent || '').replace(/\\s+/g, ' ').slice(0, 1500) };
  `, 'indicatorsDialog');
}

if (ACTION === 'settings') {
  await clickInFrames('[title="Chart settings"], [title="تنظیمات چارت"], button:has-text("Settings")');
  await page.waitForTimeout(3500);
  await scan(`
    const txt = (e) => (e.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 70);
    const tabs = [...document.querySelectorAll('[class*="tab"] [class*="title"], .tabbar-wrapper [class*="item"]')].map(txt).filter(Boolean);
    const labels = [...document.querySelectorAll('label')].map(txt).filter(Boolean).slice(0, 200);
    return { tabs: [...new Set(tabs)], labels, dialogText: (document.querySelector('[class*="dialog"]')?.textContent || '').replace(/\\s+/g, ' ').slice(0, 2500) };
  `, 'settingsDialog');
}

report.errors = errors.slice(0, 15);
mkdirSync(OUT.replace(/[^/]*$/, ''), { recursive: true });
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf8');
await page.screenshot({ path: OUT.replace(/\.json$/, '.png') });
console.log(JSON.stringify(report).slice(0, 6000));
await context.close();
