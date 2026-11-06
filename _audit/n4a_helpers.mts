  // ── ابزارهایِ مشترکِ فازهایِ ب/ت/م: چیپ<Z>ها، نشانِ شمار، ویرچوال<Z>اسکرول، درخت و در ──
  const nz = (s: unknown): string => norm(String(s ?? ''));
  const numOf = (t: string | null | undefined): number | null => {
    const m = nz(t).match(/[0-9<D0>-<D9>]+/);
    if (!m) return null;
    return /^[0-9]+$/.test(m[0]) ? Number(m[0]) : faNum(m[0]);
  };
  const CHIP_COUNT_RE = /\(([0-9<D0>-<D9>]+)\)/;
  const PLUS_RE = /\+\s*\(?([0-9<D0>-<D9>]+)/;
  const CHIP_ORDER: string[] = ['f_clock', 'f_susp', 'f_jet', 'f_roobi', 'f_noqteh', 'f_smart', 'f_legal'];
  const CHIP_SUB: Record<string, string> = {
    f_clock: 'ساعت',
    f_susp: 'حجم',
    f_jet: 'جت',
    f_roobi: 'روبی',
    f_noqteh: 'نقطه',
    f_smart: 'هوشمند',
    f_legal: 'حقوقی',
  };
  const chipKeyOf = (text: string): string | null => {
    const t = nz(text);
    for (const k of CHIP_ORDER) if (t.includes(CHIP_SUB[k])) return k;
    return null;
  };

  const readChips = async (): Promise<{ total: number; texts: { pressed: boolean; text: string }[] }> => {
    return await page.evaluate(() => {
      const bar = document.querySelector('[data-testid="quick-filters-bar"]');
      if (!bar) return { total: 0, texts: [] as { pressed: boolean; text: string }[] };
      const btns = Array.from(bar.querySelectorAll('button[aria-pressed]'));
      return {
        total: btns.length,
        texts: btns.map((b) => ({ pressed: b.getAttribute('aria-pressed') === 'true', text: (b.textContent || '').trim() })),
      };
    });
  };

  const chipCensus = (texts: { pressed: boolean; text: string }[]): { keys: string[]; pressed: string[]; extra: string[] } => {
    const keys: string[] = [];
    const pressed: string[] = [];
    const extra: string[] = [];
    for (const t of texts) {
      const k = chipKeyOf(t.text);
      if (k === null || keys.includes(k)) {
        extra.push(t.text);
        continue;
      }
      keys.push(k);
      if (t.pressed) pressed.push(k);
    }
    return { keys, pressed, extra };
  };

  const clickChipByKey = async (key: string): Promise<boolean> => {
    const sub = CHIP_SUB[key];
    return await page.evaluate((needle: string) => {
      const bar = document.querySelector('[data-testid="quick-filters-bar"]');
      if (!bar) return false;
      const btns = Array.from(bar.querySelectorAll('button[aria-pressed]'));
      const b = btns.find((x) => (x.textContent || '').includes(needle));
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    }, sub);
  };

  const setChipsExactly = async (want: string[], rounds = 4): Promise<{ ok: boolean; total: number; pressed: string[]; extra: string[] }> => {
    const wantSet = asSet(want);
    for (let r = 0; r < rounds; r++) {
      const cur = await readChips();
      const cen = chipCensus(cur.texts);
      const missing = CHIP_ORDER.filter((k) => wantSet.has(k) && !cen.pressed.includes(k));
      const unwanted = cen.pressed.filter((k) => !wantSet.has(k));
      if (missing.length === 0 && unwanted.length === 0) break;
      for (const k of unwanted) {
        await clickChipByKey(k);
        await sleep(180);
      }
      for (const k of missing) {
        await clickChipByKey(k);
        await sleep(180);
      }
    }
    const fin = await readChips();
    const cen = chipCensus(fin.texts);
    const ok = fin.total === 7 && cen.extra.length === 0 && cen.keys.length === 7 && new Set(cen.keys).size === 7 && setEq(asSet(cen.pressed), wantSet);
    return { ok, total: fin.total, pressed: cen.pressed, extra: cen.extra };
  };

  const readPrefs = async (): Promise<{ search: string | null; sector: string | null; sectorSeen: boolean }> => {
    return await page.evaluate(() => {
      const si = document.querySelector('[data-testid="filters-side"] input[aria-label="جستجوی نماد"]') as HTMLInputElement | null;
      const se = document.querySelector('[data-testid="quick-filters-bar"] select[aria-label="فیلتر صنعت"]') as HTMLSelectElement | null;
      return { search: si ? si.value : null, sector: se ? se.value : null, sectorSeen: !!se };
    });
  };

  const gotoMarket = async (): Promise<void> => {
    if (!page.url().startsWith('http')) {
      await page.goto(`${BASE}#/market`, { waitUntil: 'domcontentloaded' });
    } else {
      await page.evaluate(() => {
        location.hash = '#/market';
      });
    }
    await page.waitForSelector('[data-testid="market-filters-bar"]', { timeout: WAIT });
    await page.waitForSelector('[data-testid="tape-scroll"]', { timeout: WAIT });
    await sleep(350);
  };

  const boardBadgeRaw = async (): Promise<[number | null, number | null] | null> => {
    const raw = await page.evaluate(() => {
      const bar = document.querySelector('[data-testid="market-filters-bar"]');
      if (!bar) return null;
      const el = Array.from(bar.querySelectorAll('span')).find((s) => (s.getAttribute('title') || '').includes('فعال در جدول'));
      return el ? (el.textContent || '') : null;
    });
    if (raw === null) return null;
    const nums = faNums(raw);
    return [nums[0] ?? null, nums[1] ?? null];
  };

  const sameNums = (a: [number | null, number | null] | null, b: [number | null, number | null] | null): boolean =>
    !!a && !!b && a.length === b.length && a.every((x, i) => x === b[i]);

  const waitBadgeStable = async (tries = 40): Promise<[number | null, number | null] | null> => {
    let prev: [number | null, number | null] | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const cur = await boardBadgeRaw();
      const good = !!cur && cur[0] !== null && cur[1] !== null;
      if (good && prev && sameNums(cur, prev)) run += 1;
      else run = good ? 1 : 0;
      prev = good ? cur : null;
      if (run >= 3) return cur;
      await sleep(200);
    }
    return null;
  };

  const waitShownIs = async (target: number, tries = 30): Promise<[number | null, number | null] | null> => {
    for (let i = 0; i < tries; i++) {
      const cur = await boardBadgeRaw();
      if (cur && cur[0] === target && cur[1] === freeze.frozenCount) return cur;
      await sleep(200);
    }
    return null;
  };

  const collectBoard = async (target: number): Promise<Set<string>> => {
    const seen = new Set<string>();
    try {
      await page.setViewportSize({ width: 1632, height: 3600 });
      await sleep(250);
      for (let i = 0; i < 80; i++) {
        const step = await page.evaluate(() => {
          const syms: string[] = [];
          for (const r of Array.from(document.querySelectorAll('[data-testid="tape-row"]'))) {
            const sp = r.querySelector('span');
            const t = sp && sp.childNodes[0] ? (sp.childNodes[0].textContent || '').trim() : '';
            if (t) syms.push(t);
          }
          let atBottom = true;
          const sc = document.querySelector('[data-testid="tape-scroll"]') as HTMLElement | null;
          if (sc) {
            sc.scrollTop = sc.scrollTop + Math.max(120, Math.floor(sc.clientHeight * 0.9));
            atBottom = sc.scrollTop >= sc.scrollHeight - sc.clientHeight - 4;
          }
          return { syms, atBottom };
        });
        for (const s of step.syms) seen.add(norm(s));
        if (seen.size >= target) break;
        if (step.atBottom) break;
        await sleep(160);
      }
    } finally {
      await page.setViewportSize({ width: 1632, height: 950 });
      await sleep(150);
    }
    return seen;
  };

  const readFunnelRaw = async (): Promise<Snap | null> => {
    try {
      const raw = (await readState()) as RawState;
      if (!raw.stages.tape || !raw.stages.technical || !raw.stages.fundamental || !raw.stages.handover) return null;
      return makeState('adhoc', raw);
    } catch {
      return null;
    }
  };

  const snapSig = (s: Snap): string => JSON.stringify(s);

  const waitStableSnap = async (label: string, tries = 25): Promise<Snap | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const s = await readFunnelRaw();
      const sig = s ? snapSig(s) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && s) {
        (report.steps as Record<string, unknown>)[label] = s;
        return s;
      }
      await sleep(350);
    }
    return null;
  };

  const waitCovStable = async (tries = 25): Promise<Snap | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const s = await readFunnelRaw();
      const sig = s ? JSON.stringify({ c1: s.coverage1, c2: s.coverage2, counts: s.counts }) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && s) return s;
      await sleep(400);
    }
    return null;
  };

  const readTreeCard = async (): Promise<{ big: number | null; input: number | null; universe: number | null } | null> => {
    const raw = await page.evaluate(() => {
      const btn = Array.from(document.querySelectorAll('button[aria-label]')).find((b) => {
        const l = (b.getAttribute('aria-label') || '').replace(/\u200c/g, '');
        return l.includes('مشاهده') && l.includes('تابلو');
      });
      if (!btn) return null;
      let card: Element | null = btn;
      for (let i = 0; i < 5 && card; i++) {
        const t = (card.textContent || '').replace(/\u200c/g, '');
        if (t.includes('بازماندگان')) break;
        card = card.parentElement;
      }
      if (!card) return null;
      const bigEl = Array.from(card.querySelectorAll('span')).find((s) => /^[<D0>-<D9>]+$/.test((s.textContent || '').trim()));
      const big = bigEl ? (bigEl.textContent || '').trim() : null;
      const inEl = Array.from(card.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').includes('ورودی'));
      const input = inEl ? (inEl.textContent || '') : null;
      const uEl = Array.from(document.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').trim() === 'نماد فعال');
      const universe = uEl && uEl.previousElementSibling ? (uEl.previousElementSibling.textContent || '') : null;
      return { big, input, universe };
    });
    if (!raw) return null;
    return { big: numOf(raw.big), input: numOf(raw.input), universe: numOf(raw.universe) };
  };

  const waitTreeStable = async (tries = 25): Promise<{ big: number | null; input: number | null; universe: number | null } | null> => {
    let prev: string | null = null;
    let run = 0;
    for (let i = 0; i < tries; i++) {
      const cur = await readTreeCard();
      const good = !!cur && cur.big !== null && cur.universe !== null;
      const sig = good ? JSON.stringify(cur) : null;
      if (sig && prev && sig === prev) run += 1;
      else run = sig ? 1 : 0;
      prev = sig;
      if (run >= 3 && cur) return cur;
      await sleep(320);
    }
    return null;
  };

  const openTapeDrawer = async (): Promise<boolean> => {
    const hit = await page.evaluate(() => {
      const b = Array.from(document.querySelectorAll('button[aria-label]')).find((x) => {
        const l = (x.getAttribute('aria-label') || '').replace(/\u200c/g, '');
        return l.includes('مشاهده') && l.includes('تابلو');
      });
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    });
    if (!hit) return false;
    try {
      await page.waitForSelector('[data-testid="stage-candidate-drawer"]', { timeout: 15000 });
      return true;
    } catch {
      return false;
    }
  };

  const readTapeDrawerRaw = async (): Promise<{ total: number | null; rows: { sym: string; status: string | null; why: string }[] } | null> => {
    const raw = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="stage-candidate-drawer"]');
      if (!root) return null;
      const tEl = Array.from(root.querySelectorAll('span')).find((s) => (s.textContent || '').replace(/\u200c/g, '').includes('مجموع'));
      const totalText = tEl && tEl.parentElement ? (tEl.parentElement.textContent || '') : null;
      const rows: { sym: string; status: string | null; why: string }[] = [];
      for (const tr of Array.from(root.querySelectorAll('tbody tr'))) {
        const tds = Array.from(tr.querySelectorAll('td'));
        const first = tds[0] ? tds[0].querySelector('span') : null;
        const sym = first ? (first.textContent || '').trim() : '';
        let status: string | null = null;
        for (const td of tds) {
          const m = (td.textContent || '').match(/(PASS|REJECT|PENDING|UNAVAILABLE)/);
          if (m) {
            status = m[1];
            break;
          }
        }
        const why = tds.length > 0 ? (tds[tds.length - 1].textContent || '').trim() : '';
        rows.push({ sym, status, why });
      }
      return { totalText, rows };
    });
    if (!raw) return null;
    return { total: numOf(raw.totalText), rows: raw.rows };
  };

  const closeTapeDrawer = async (): Promise<boolean> => {
    const hit = await page.evaluate(() => {
      const root = document.querySelector('[data-testid="stage-candidate-drawer"]');
      if (!root) return false;
      const b = Array.from(root.querySelectorAll('button[aria-label]')).find((x) => (x.getAttribute('aria-label') || '').includes('بستن'));
      if (!b) return false;
      (b as HTMLElement).click();
      return true;
    });
    if (!hit) return false;
    return await waitGone('[data-testid="stage-candidate-drawer"]');
  };

  // ── فریزِ داده: یک لحظه از api/market، همان لحظه برایِ هر دو سطح ──
  const freeze: {
    ok: boolean;
    err: string | null;
    frozenRev: number | null;
    frozenStatus: string | null;
    frozenCount: number;
    bodyBytes: number;
    fullReplay: number;
    deltaBlocked: number;
  } = { ok: false, err: null, frozenRev: null, frozenStatus: null, frozenCount: 0, bodyBytes: 0, fullReplay: 0, deltaBlocked: 0 };
  let frozenText = '';
  const frozenSyms = new Set<string>();
  try {
    const fr = await fetch(new URL('api/market', BASE));
    if (!fr.ok) throw new Error('HTTP ' + fr.status);
    const ft = await fr.text();
    const fj = JSON.parse(ft) as { status?: string; rev?: number; data?: { symbol?: string }[] };
    const fdata = Array.isArray(fj.data) ? fj.data : [];
    freeze.frozenStatus = typeof fj.status === 'string' ? fj.status : null;
    freeze.frozenRev = typeof fj.rev === 'number' ? fj.rev : null;
    freeze.frozenCount = fdata.length;
    freeze.bodyBytes = Buffer.byteLength(ft, 'utf8');
    frozenText = ft;
    for (const row of fdata) {
      const sym = norm(row && row.symbol != null ? String(row.symbol) : '');
      if (sym) frozenSyms.add(sym);
    }
    freeze.ok = freeze.frozenCount > 0;
    if (!freeze.ok) freeze.err = 'snapshot empty (status=' + String(freeze.frozenStatus) + ')';
  } catch (e) {
    freeze.err = String(e);
  }
  if (freeze.ok) {
    await context.route(/\/api\/market(\?.*)?$/, async (route) => {
      freeze.fullReplay += 1;
      await route.fulfill({ status: 200, contentType: 'application/json; charset=utf-8', body: frozenText });
    });
    await context.route(/\/api\/market\/delta(\?.*)?$/, async (route) => {
      freeze.deltaBlocked += 1;
      await route.fulfill({
        status: 200,
        contentType: 'application/json; charset=utf-8',
        body: JSON.stringify({ status: 'unchanged', rev: freeze.frozenRev ?? 0, meta: null, count: freeze.frozenCount, live_count: null, fossil_count: null }),
      });
    });
  }
  report.freeze = freeze;

  // ── نتیجه<Z>های خامِ فازهایِ ب/ت/م برایِ گزارش ──
  const B_ITEMS: Record<string, unknown>[] = [];
  const T_ITEMS: Record<string, unknown>[] = [];
  const M_ITEMS: Record<string, unknown>[] = [];
  const M_PAIRS: Record<string, string[]> = {
    trend: ['f_roobi', 'f_noqteh'],
    swing: ['f_clock', 'f_jet', 'f_susp'],
    hourglass: ['f_roobi', 'f_clock'],
  };
  report.b_items = B_ITEMS;
  report.t_items = T_ITEMS;
  report.m_items = M_ITEMS;