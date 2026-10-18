// _audit/ra365_job_tools2.js — فهرستِ **تک‌تکِ ابزارها** درِ هر گروهِ نوارِ رسمِ رهاورد،
// با شاهدِ قابل‌بررسیِ «بی‌اثری» رویِ چارتِ مالک.
//
// چرا نسخهٔ قبلِ این فایل قابلِ اتکا نبود (این نکته درِ گزارش هم می‌آید):
//   ۱) ادعایِ بی‌اثری برِ `removeAllDrawingTools` سوار بود، ولی عنوانِ آن دکمه درِ این
//      build هیچِ رقمی ندارد → شمارش `null` شد و `null === null` «بی‌تغییر» گزارش کرد.
//      آن اثبات نبود؛ سبزِ بی‌محتوا.
//   ۲) SNAP همهٔ [title]هایِ دیدنیِ فریم را می‌گرفت، پس هر گروه ~۶۰ آیتم می‌داد درحالی‌که
//      خودِ نوارِ ثابت هم ~۶۰ آیتم دارد → فهرستِ flyout ازِ فهرستِ کل جدا نبود.
// راه‌حلِ این دور: **diff** نسبت به baseline برایِ محتوایِ flyout، و شاهدِ مستقلِ
// «درختِ اشیاء» (`showObjectsTree`) برایِ بی‌اثری — اگر پیش و پس ازِ کاوش تعدادِ اشیاء
// یکی بماند، ثابت می‌شود کاوش چیزی نساخته و اندیکاتوری اضافه نکرده.
// کاوش فقط با caret و Escape: هیچِ ابزارِ رسم انتخاب نمی‌شود.
// هیچِ رمز/کوکی/token خوانده یا ذخیره نمی‌شود.
const uniq = (a) => [...new Set(a.filter(Boolean))];

const SNAP = () => {
  const vis = (e) => { try { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; } catch { return false; } };
  const out = [];
  document.querySelectorAll('[data-name],[title],[aria-label]').forEach((e) => {
    if (!vis(e)) return;
    const n = e.getAttribute('data-name') || '';
    const t = (e.getAttribute('title') || e.getAttribute('aria-label') || '').trim().slice(0, 70);
    if (n || t) out.push((n ? n + ' :: ' : '') + t);
  });
  return { items: out, nodes: document.querySelectorAll('*').length };
};

// درختِ اشیاء = فهرستِ چیزهایی که واقعاً رویِ چارت‌اند (کندل/اندیکاتور/ابزارِ رسم)
const OPEN_TREE = () => {
  const btn = document.querySelector('[data-name="showObjectsTree"]');
  if (!btn) return { present: false };
  btn.click();
  return { present: true };
};

// توجه: تابع‌هایی که به `frame.evaluate` می‌روند باید **خودبسا** باشند؛ `uniq` ماژول
// درِ context صفحۀ Playwright وجود ندارد (خطایِ همین دور: ReferenceError: uniq).
const READ_TREE = () => {
  const nodes = Array.from(document.querySelectorAll(
    '[class*="objects-tree" i] *, [class*="study" i][class*="item" i], [role="tree"] *, [role="treeitem"], [role="menuitem"]'));
  const texts = [...new Set(nodes.map((e) => (e.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 60)))]
    .filter((s) => s.length > 1 && s.length < 60);
  return { count: texts.length, texts: texts.slice(0, 40) };
};

const GROUPS = () => [...new Set(Array.from(document.querySelectorAll('[data-name]'))
  .map((e) => e.getAttribute('data-name'))
  .filter((n) => /^linetool-group-/.test(n) || /^(date-ranges-menu|time-zone-menu|save-load-menu)$/.test(n)))];

module.exports = async ({ page, shot, say }) => {
  const res = { groups: [], notes: [], screenshots: [] };
  await page.goto('https://rahavard365.com/asset/453/chart', { waitUntil: 'domcontentloaded', timeout: 90000 })
    .catch((e) => res.notes.push('goto: ' + String(e).slice(0, 90)));
  await page.waitForTimeout(24000);

  let frame = page.frames().find((f) => /tradingview/.test(f.name() || ''));
  if (!frame) {
    for (const f of page.frames()) {
      const ok = await f.evaluate(() => !!document.querySelector('[data-name="removeAllDrawingTools"]')).catch(() => false);
      if (ok) { frame = f; break; }
    }
  }
  if (!frame) { res.notes.push('فریمِ چارت پیدا نشد'); return res; }
  say('فریمِ چارت: ' + (frame.name() || '(main)'));

  await frame.evaluate(OPEN_TREE);
  await page.waitForTimeout(1300);
  res.tree_before = await frame.evaluate(READ_TREE);
  await page.keyboard.press('Escape');
  await page.waitForTimeout(900);
  res.baseline = await frame.evaluate(SNAP);
  say('درختِ اشیاء پیش ازِ کاوش: ' + res.tree_before.count + ' | baselineِ دیدنی: ' + res.baseline.items.length);

  const names = await frame.evaluate(GROUPS);
  res.group_names = names;
  say('گروه‌ها (' + names.length + '): ' + names.join(', '));

  for (const g of names) {
    const rec = { name: g, new_items: [], dom_delta: null, error: null };
    try {
      const btn = frame.locator(`[data-name="${g}"]`).first();
      if (!(await btn.count())) { rec.error = 'locator نیست'; res.groups.push(rec); continue; }
      const caret = btn.locator('[class*="caret" i],[class*="wrap" i]').last();
      const target = (await caret.count()) ? caret : btn;
      await target.click({ timeout: 5000 }).catch(async () => { await target.hover({ timeout: 3000 }); });
      await page.waitForTimeout(1400);
      const after = await frame.evaluate(SNAP);
      const seen = new Set(res.baseline.items);
      // آنچه فقط درِ حالتِ بازِ این گروه دیدنی شده = محتوایِ flyout
      rec.new_items = after.items.filter((s) => !seen.has(s)).slice(0, 60);
      rec.dom_delta = after.nodes - res.baseline.nodes;
      await page.keyboard.press('Escape');
      await page.waitForTimeout(700);
    } catch (e) {
      rec.error = String(e).slice(0, 120);
      await page.keyboard.press('Escape').catch(() => {});
    }
    say('  ' + g + ' → تازه=' + rec.new_items.length + (rec.error ? '  ERR ' + rec.error.slice(0, 50) : ''));
    res.groups.push(rec);
  }

  await frame.evaluate(OPEN_TREE);
  await page.waitForTimeout(1300);
  res.tree_after = await frame.evaluate(READ_TREE);
  await page.keyboard.press('Escape');
  res.unchanged = (res.tree_before.count === res.tree_after.count);
  // هشدارِ روش‌شناسی: اگر سلکتورِ درخت هیچِ عنصری نگیرد، count دو طرف ۰ می‌ماند و
  // «بی‌تغییر» به‌صورتِ بی‌محتوا سبز می‌شود — همان دامی که دورِ قبل با null افتاد.
  // پس اثبات فقط وقتی معتبر است که شمارِ غیرصفر و برابر باشد.
  res.proof_meaningful = res.unchanged && res.tree_before.count > 0;
  say('درختِ اشیاء پس ازِ کاوش: ' + res.tree_after.count + ' | بی‌تغییر: ' + res.unchanged +
    ' | اثبات معتبر (غیرصفر و برابر): ' + res.proof_meaningful);
  if (!res.unchanged) {
    res.notes.push('هشدار: شمارِ درختِ اشیاء عوض شد (پیش=' + res.tree_before.count +
      ' پس=' + res.tree_after.count + ') — کاوش باید بی‌اثر می‌بود؛ نتیجهٔ این دور ' +
      'قابلِ اتکا نیست و چارتِ مالک باید بازبینی شود.');
  }
  res.shot = await shot('ra365_tools2_after');
  res.notes.push('کاوش فقط با caret و Escape؛ هیچِ ابزارِ رسم انتخاب نشد؛ بی‌افزودنِ اندیکاتور.');
  res.notes.push('tree texts: ' + JSON.stringify(res.tree_before.texts || []).slice(0, 400));
  return res;
};
