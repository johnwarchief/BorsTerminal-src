/** tools/screen_chips_probe.mts — سنجشِ زنده: چیپ‌هایِ تابلو غربالگری را می‌سازند؟
 *
 * چرا: رأیِ مالک ۱۴۰۵-۰۷-۲۰ چهار چیز می‌خواهد که هیچ‌کدام با jsdom ثابت نمی‌شود:
 *   ۱) کلیکِ چیپ درِ نوارِ تابلو، همان زنجیره را به `POST /api/funnel` ببرد؛
 *   ۲) کلیدِ «اشتراک/اجتماع» منطقِ درخواست را عوض کند و شمارِ عبوریِ سرور هم عوض شود؛
 *   ۳) پیش‌نمایِ هاورِ روندگیر/نوسان‌گیر فهرستِ فیلترها را بگوید؛
 *   ۴) ستون‌های «نشانه» و «دلیل» دیگر «تأیید» و «همۀ فیلترهایِ زنجیره» نباشند.
 *
 * اجرا (JEV_CHROME و JEV_BROWSER_DIR مثلِ بقیۀ probeها):
 *   node --experimental-strip-types tools/screen_chips_probe.mts --url http://127.0.0.1:8005
 */
import { pathToFileURL } from 'node:url';
import { writeFileSync } from 'node:fs';

const PKG = process.env.JEV_BROWSER_DIR ??
  'C:/Users/PCMOD/.cline/plugins/_installed/official/jev-browser-b15ae305f536/package';
const imp = (rel: string) => import(pathToFileURL(`${PKG}/${rel}`).href);
const arg = (n: string, f = '') => {
  const i = process.argv.indexOf(`--${n}`);
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : f;
};
const BASE = arg('url', 'http://127.0.0.1:8005').replace(/\/$/, '');
const OUT = arg('out', '_audit/screen_chips_probe.json');
const SHOT = arg('shot', '_audit/screen_chips_probe.png');

const { chromium } = await imp('node_modules/playwright/index.mjs');
const browser = await chromium.launch({ executablePath: process.env.JEV_CHROME });
const ctx = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const page = await ctx.newPage();
const consoleErrors: string[] = [];
// بدنهٔ درخواست از لایۀ شبکه خوانده می‌شود (مطمئن‌تر از جایگزینیِ window.fetch درِ
// صفحه؛ همان‌جا که `requestfailed`/cancel هم دیده می‌شود).
const sentBodies: Array<Record<string, unknown>> = [];
page.on('console', (m) => { if (m.type() === 'error') consoleErrors.push(m.text().slice(0, 200)); });
page.on('request', (r) => {
  if (!r.url().includes('/api/funnel') || r.method() !== 'POST') return;
  try { sentBodies.push(JSON.parse(r.postData() ?? '{}') as Record<string, unknown>); }
  catch { sentBodies.push({ unparsed: (r.postData() ?? '').slice(0, 80) }); }
  console.log('   ↦', JSON.stringify(sentBodies[sentBodies.length - 1]).slice(0, 150));
});
// حالتِ تمیز: منطقِ ذخیره‌شدۀ دورِ قبل نباید درِ این سنجش أثر بگذارد.
await ctx.addInitScript(() => {
  try { localStorage.setItem('bors.screen.logic.v1', 'and'); } catch { /* بی‌localStorage */ }
});
// هر بدنهٔ `POST /api/funnel` درِ خودِ صفحه ثبت می‌شود — همان چیزی که کاربر می‌فرستد.
await page.addInitScript(() => {
  sessionStorage.setItem('bors_auth_session', 'true');
});

const report: Record<string, unknown> = { base: BASE, checks: [] as string[] };
const check = (name: string, ok: boolean, detail = '') => {
  (report.checks as string[]).push(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`);
  console.log(`${ok ? '  ok  ' : ' FAIL '} ${name}${detail ? ` — ${String(detail).slice(0, 160)}` : ''}`);
};

// ۱) نوارِ تابلو: هفت چیپ با شمارشِ واقعی + کلیدِ اشتراک/اجتماع
await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForSelector('[data-testid="quick-filters-bar"]', { timeout: 45_000 }).catch(() => {});
await page.waitForTimeout(6000);
const chips = await page.evaluate(() => {
  const bar = document.querySelector('[data-testid="quick-filters-bar"]');
  const texts = Array.from(bar?.querySelectorAll('button') ?? []).map((b) => b.innerText.trim());
  const logic = document.querySelector('[data-testid="screen-logic-toggle"]') as HTMLButtonElement | null;
  return {
    tape: texts.filter((t) => /الگوی ساعت|حجم مشکوک|جت|کف‌روبی|نقطه|پول هوشمند|کد به کد/.test(t)).length,
    logicText: logic?.innerText?.trim() ?? null,
    logicDisabled: logic ? logic.disabled : null,
  };
});
report.chips = chips;
check('هفت چیپِ فیلتر رویِ نوارِ تابلو است', chips.tape === 7, `یافت‌شده: ${chips.tape}`);
check('کلیدِ اشتراک/اجتماع بی‌انتخاب غیرفعال است', chips.logicDisabled === true && chips.logicText === 'اشتراک',
  JSON.stringify(chips));

const clickChip = async (label: string) => {
  const el = page.locator(`[data-testid="quick-filters-bar"] button:has-text("${label}")`).first();
  await el.click({ timeout: 8000 });
  await page.waitForTimeout(700);
};
await clickChip('حجم مشکوک');
await clickChip('کف‌روبی');
const after = await page.evaluate(() => {
  const logic = document.querySelector('[data-testid="screen-logic-toggle"]') as HTMLButtonElement | null;
  return { disabled: logic?.disabled ?? null, text: logic?.innerText?.trim() ?? null,
           title: logic?.getAttribute('title') ?? null };
});
report.logicAfterChips = after;
check('با دو چیپِ روشن، کلید فعال و راهنمایش شمارۀ واقعی را می‌گوید',
  after.disabled === false && (after.title ?? '').includes('۲'), JSON.stringify(after));

// ۲) قیف همان انتخاب را می‌فرستد و «اجتماع» شمارِ سرور را عوض می‌کند
await page.goto(`${BASE}/#/master?stage=tape`, { waitUntil: 'domcontentloaded' });
let cursor = sentBodies.length;
for (let i = 0; i < 30 && sentBodies.length === cursor; i++) await page.waitForTimeout(2000);
const body1 = sentBodies[sentBodies.length - 1] ?? null;
report.requestAnd = body1;
const b1 = body1 as { chain?: string[]; logic?: string; preset?: string } | null;
check('درخواستِ قیف همان دو چیپ را درِ chain می‌برد',
  JSON.stringify(b1?.chain ?? []) === JSON.stringify(['f_susp', 'f_roobi']), JSON.stringify(b1?.chain));
check('منطقِ پیش‌فرضِ درخواست اشتراک است', b1?.logic === 'and', String(b1?.logic));

const passAnd = await page.evaluate(() => {
  const rows = document.querySelectorAll('[data-testid="funnel-stage-tape"] tbody tr');
  return rows.length;
});
report.domRowsAnd = passAnd;

await page.goto(`${BASE}/#/market`, { waitUntil: 'domcontentloaded' });
await page.waitForTimeout(3000);
await page.locator('[data-testid="screen-logic-toggle"]').click({ timeout: 8000 });
await page.waitForTimeout(600);
cursor = sentBodies.length;
await page.goto(`${BASE}/#/master?stage=tape`, { waitUntil: 'domcontentloaded' });
for (let i = 0; i < 30 && sentBodies.length === cursor; i++) await page.waitForTimeout(2000);
const body2 = sentBodies[sentBodies.length - 1] ?? null;
report.requestOr = body2;
check('کلیکِ کلید، «or» را به موتور می‌فرستد',
  (body2 as { logic?: string } | null)?.logic === 'or', JSON.stringify(body2));
const orRows = await page.evaluate(() => document.querySelectorAll('[data-testid="funnel-stage-tape"] tbody tr').length);
report.domRowsOr = orRows;
// مقایسه رویِ شمارِ خودِ سرور، نه ردیفِ DOM (جدول مجازی‌شده است و سقفِ پنجره دارد).
const serverCmp = await page.evaluate(async () => {
  const call = async (logic: string) => {
    const r = await fetch('/api/funnel', {
      method: 'POST', headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ preset: 'trend', chain: ['f_susp', 'f_roobi'], logic,
                             fund_mode: 'standard', exceptions: {}, drop_suffix: true }),
    });
    const j = await r.json();
    return { matched: j?.stages?.tape?.matched, echoed: j?.tape_logic, input: j?.stages?.tape?.input };
  };
  return { and: await call('and'), or: await call('or') };
});
report.serverCmp = serverCmp;
check('موتور هم دو منطق را مهر می‌کند و اجتماع عبوریِ کم‌از‌اشتراک ندارد',
  serverCmp.and.echoed === 'and' && serverCmp.or.echoed === 'or'
  && (serverCmp.or.matched ?? -1) >= (serverCmp.and.matched ?? 0)
  && (serverCmp.or.matched ?? 0) > (serverCmp.and.matched ?? 0),
  JSON.stringify(serverCmp));

// ۳) پیش‌نمایِ هاور (هاورِ واقعی: Reactِ enter/leave را با رویدادِ بومیِ的合成 نمی‌سازند)
await page.locator('[data-testid="funnel-mode-trend"]').first().hover({ timeout: 8000 });
await page.waitForTimeout(700);
const preview = await page.evaluate(() =>
  document.querySelector('[data-testid="funnel-preset-preview-trend"]')?.innerText ?? null);
report.preview = preview;
check('هاور رویِ روندگیر فهرستِ فیلترها و انگیزه را نشان می‌دهد',
  !!preview && preview.includes('کف‌روبی') && preview.includes('نقطه زنی'), String(preview).slice(0, 120));

// ۴) نشانه/دلیل
const cols = await page.evaluate(() => {
  const rows = Array.from(document.querySelectorAll('[data-testid="funnel-stage-tape"] tbody tr')).slice(0, 12);
  const txt = (r: Element) => Array.from(r.querySelectorAll('td')).map((td) => td.innerText.trim());
  const cells = rows.map(txt);
  const flat = cells.join(' | ');
  return { sample: cells.slice(0, 4), saidConfirm: /تأیید/.test(flat), saidChain: flat.includes('همۀ فیلترهایِ زنجیره'),
           saidNoMark: flat.includes('بی‌نشانه') };
});
report.columns = cols;
check('«تأیید» و «همۀ فیلترهایِ زنجیره» ازِ جدولِ نشانه/دلیل بیرون رفتند',
  cols.saidConfirm === false && cols.saidChain === false, JSON.stringify(cols.sample?.[0] ?? []).slice(0, 160));

await page.screenshot({ path: SHOT, fullPage: false });
report.screenshot = SHOT;
report.consoleErrors = consoleErrors.slice(0, 8);
if (consoleErrors.length) console.log(`اخطارهایِ کنسول: ${consoleErrors.length}`, consoleErrors[0]);
writeFileSync(OUT, JSON.stringify(report, null, 1), 'utf-8');
const fails = (report.checks as string[]).filter((c) => c.startsWith('FAIL'));
console.log(`\n${(report.checks as string[]).length - fails.length}/${(report.checks as string[]).length} سبز — ${OUT}`);
await browser.close();
process.exit(fails.length ? 1 : 0);
