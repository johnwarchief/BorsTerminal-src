// _audit/ra365_job_tools4.js — محتوایِ هر گروهِ رسم با **hoverِ خالص** (بی‌کلیک).
// شواهدِ این دور تا اینجا (ra365_tools3.json): درِ حالتِ بسته، هیچِ `linetool-*` تکی درِ
// DOM نیست؛ فقطِ ۸ `linetool-group-*` هست → flyout lazy render است. پس شمارِ ابزارها با
// کلیکِ کورکورانه یا با حدس ازِ حافظه جایز نیست.
// چرا hover امن است: hover هیچِ ابزاری را انتخاب نمی‌کند (انتخاب نیازمندِ click/keydown
// است)، پس نه حالتِ رسم عوض می‌شود نه چیزی رسم می‌شود. برایِ اطمینان، پس ازِ کاوش همان
// خوانشِ منفعلِ را (legend + ابزارِ فعال) دوباره انجام می‌دهیم و درِ خروجی می‌نویسیم.
const SNAP_ALL = () => {
  const list = Array.from(document.querySelectorAll('[data-name^="linetool-"]'))
    .filter((e) => !/^linetool-group-/.test(e.getAttribute('data-name') || ''))
    .map((e) => {
      const vis = (() => { try { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; } catch { return false; } })();
      const t = (e.getAttribute('title') || e.getAttribute('aria-label') || (e.textContent || '').trim() || '').slice(0, 70);
      return (e.getAttribute('data-name') || '') + ' :: ' + t + (vis ? ' [visible]' : ' [in-DOM,hidden]');
    });
  return { tools: [...new Set(list)], nodes: document.querySelectorAll('*').length };
};

const HEALTH = () => {
  const txt = (e) => (e.textContent || '').replace(/\s+/g, ' ').trim();
  const vis = (e) => { try { const r = e.getBoundingClientRect(); return r.width > 1 && r.height > 1; } catch { return false; } };
  return {
    legend: [...new Set(Array.from(document.querySelectorAll('[data-name="legend-source-title"],[data-name="legend-series-item"],[class*="legendSource" i]')).map(txt).filter((s) => s && s.length < 70))],
    activeDrawingish: Array.from(document.querySelectorAll('[class*="active" i],[aria-pressed="true"]')).filter(vis)
      .map((e) => (e.getAttribute('data-name') || '') + ' :: ' + (e.getAttribute('title') || txt(e)).slice(0, 50))
      .filter((s) => /linetool|draw|measure|cursor/i.test(s)).slice(0, 12),
    drawModeHints: [...new Set(Array.from(document.querySelectorAll('body *')).filter((e) => e.childElementCount === 0 && vis(e)).map(txt)
      .filter((s) => s && s.length < 90 && /حالتِ رسم|drawing mode/i.test(s)))].slice(0, 6),
  };
};

module.exports = async ({ page, shot, say }) => {
  const res = { groups: [], notes: [] };
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

  res.health_before = await frame.evaluate(HEALTH);
  res.baseline = await frame.evaluate(SNAP_ALL);
  say('پیش ازِ کاوش — legend: ' + JSON.stringify(res.health_before.legend) + ' | linetool درِ DOM: ' + res.baseline.tools.length);

  const groups = await frame.evaluate(() => [...new Set(Array.from(document.querySelectorAll('[data-name^="linetool-group-"]')).map((e) => e.getAttribute('data-name')))]);
  res.group_names = groups;
  for (const g of groups) {
    const rec = { name: g, tools: [], error: null };
    try {
      const el = frame.locator(`[data-name="${g}"]`).first();
      await el.hover({ timeout: 6000 });
      await page.waitForTimeout(1800);
      // caret/expand هم اگر جدا هست، با hover باز می‌شود (کلیک نمی‌کنیم)
      const caret = el.locator('[class*="caret" i],[class*="button" i]').last();
      if (await caret.count()) { await caret.hover({ timeout: 2500 }).catch(() => {}); await page.waitForTimeout(1500); }
      const snap = await frame.evaluate(SNAP_ALL);
      const base = new Set(res.baseline.tools);
      rec.tools = snap.tools.filter((t) => !base.has(t)).slice(0, 60);
      await page.mouse.move(10, 10);
      await page.waitForTimeout(600);
    } catch (e) { rec.error = String(e).slice(0, 110); }
    say('  ' + g + ' → ابزارِ تازه=' + rec.tools.length + (rec.error ? '  ERR ' + rec.error.slice(0, 45) : ''));
    res.groups.push(rec);
  }

  res.health_after = await frame.evaluate(HEALTH);
  res.clean = (res.health_after.legend.length === res.health_before.legend.length &&
               res.health_after.activeDrawingish.length === 0 && res.health_after.drawModeHints.length === 0);
  say('پس ازِ کاوش — legend: ' + JSON.stringify(res.health_after.legend) + ' | تمیز: ' + res.clean);
  res.shot = await shot('ra365_tools4_hover');
  res.notes.push('کاوش فقط با hover و جابه‌جاییِ ماوس به گوشه؛ هیچِ کلیکِ ابزاری انجام نشد.');
  return res;
};
