  // ── فازِ ب: تابلو، مستقل — چیپِ تک، ترکیبِ AND، رهیابِ صفر، بازنشانی، بی هیچ قیف ──
  await gotoMarket();
  await sleep(700);
  await page.screenshot({ path: `${DIR}/funnel_parity_board.png` });

  ck('ب<D0>', freeze.ok && freeze.frozenCount > 0, { ok: freeze.ok, count: freeze.frozenCount, rev: freeze.frozenRev, status: freeze.frozenStatus, err: freeze.err });

  const chips0 = await readChips();
  const cen0 = chipCensus(chips0.texts);
  const chipsBijective = chips0.total === 7 && cen0.extra.length === 0 && cen0.keys.length === 7 && new Set(cen0.keys).size === 7;
  ck('ب<D1>', chipsBijective, { total: chips0.total, keys: cen0.keys, extra: cen0.extra });

  const liveOn = await ensurePressed('live-only-toggle', true);
  const suffixOn = await ensurePressed('numeric-suffix-toggle', true);
  const prefs2 = await readPrefs();
  const prefsClean = prefs2.search === '' && prefs2.sectorSeen && prefs2.sector === '';
  ck('ب<D2>', liveOn && suffixOn && prefsClean, { liveOn, suffixOn, search: prefs2.search, sector: prefs2.sector, sectorSeen: prefs2.sectorSeen });

  const off = await setChipsExactly([]);
  const badge0 = await waitBadgeStable();
  const u0 = await collectBoard(badge0 && badge0[0] != null ? badge0[0] : 0);
  const removedVsFrozen = diff(frozenSyms, u0);
  const b3ok =
    off.ok && !!badge0 && badge0[0] != null && badge0[0] > 0 && badge0[1] === freeze.frozenCount && u0.size === badge0[0] && isSubset(u0, frozenSyms);
  ck('ب<D3>', b3ok, {
    chipsOffOk: off.ok,
    badge: badge0,
    u0Size: u0.size,
    frozenCount: freeze.frozenCount,
    subsetOfFrozen: isSubset(u0, frozenSyms),
    offFrozenCount: removedVsFrozen.length,
    offFrozenSample: removedVsFrozen.slice(0, 80),
  });

  const b4 = await page.evaluate(async () => {
    const enc = new TextEncoder();
    const ft = await (await fetch('api/market')).text();
    const dt = await (await fetch('api/market/delta?since=1')).text();
    let fullN = 0;
    let fullRev: number | null = null;
    let deltaStatus: string | null = null;
    try {
      const j = JSON.parse(ft) as { rev?: number; data?: unknown[] };
      fullN = Array.isArray(j.data) ? j.data.length : 0;
      fullRev = typeof j.rev === 'number' ? j.rev : null;
    } catch {}
    try {
      const j = JSON.parse(dt) as { status?: string };
      deltaStatus = typeof j.status === 'string' ? j.status : null;
    } catch {}
    return { fullN, fullRev, fullBytes: enc.encode(ft).length, deltaStatus };
  });
  const b4ok =
    b4.fullN === freeze.frozenCount &&
    b4.fullRev === freeze.frozenRev &&
    b4.fullBytes === freeze.bodyBytes &&
    (freeze.frozenRev == null || b4.deltaStatus === 'unchanged') &&
    freeze.fullReplay > 0 &&
    (freeze.frozenRev == null || freeze.deltaBlocked > 0);
  ck('ب<D4>', b4ok, { ...b4, frozenCount: freeze.frozenCount, frozenRev: freeze.frozenRev, bodyBytes: freeze.bodyBytes, fullReplay: freeze.fullReplay, deltaBlocked: freeze.deltaBlocked });

  const singles: Record<string, Set<string>> = {};
  for (const k of CHIP_ORDER) {
    const arm = await setChipsExactly([k]);
    const badge = await waitBadgeStable();
    const cur = await readChips();
    const tFound = cur.texts.find((t) => chipKeyOf(t.text) === k);
    const chipText = tFound ? tFound.text : null;
    const cm = chipText ? chipText.match(CHIP_COUNT_RE) : null;
    const pm = chipText ? chipText.match(PLUS_RE) : null;
    const chipCount = cm ? numOf(cm[1]) : null;
    const plus = pm ? numOf(pm[1]) : null;
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    singles[k] = col;
    const countOk = chipCount === null ? !!badge && badge[0] === 0 : !!badge && chipCount === badge[0];
    const ok = arm.ok && !!badge && badge[0] != null && col.size === badge[0] && isSubset(col, u0) && countOk;
    B_ITEMS.push({
      focus: 'single',
      key: k,
      ok,
      armOk: arm.ok,
      badgeShown: badge ? badge[0] : null,
      badgeTotal: badge ? badge[1] : null,
      collected: [...col].sort(),
      chipCount,
      chipText,
      plus,
      subsetOfU0: isSubset(col, u0),
      removedVsU0: diff(u0, col),
      extraVsU0: diff(col, u0),
    });
  }

  let unionAll = new Set<string>();
  for (const k of CHIP_ORDER) unionAll = uni(unionAll, singles[k]);
  const combos: { id: string; keys: string[] }[] = [
    { id: 'roobi+noqteh', keys: ['f_roobi', 'f_noqteh'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
    { id: 'roobi+clock', keys: ['f_roobi', 'f_clock'] },
    { id: 'clock+jet+susp', keys: ['f_clock', 'f_jet', 'f_susp'] },
  ];
  for (const cb of combos) {
    const arm = await setChipsExactly(cb.keys);
    const badge = await waitBadgeStable();
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    let expect = singles[cb.keys[0]];
    for (let i = 1; i < cb.keys.length; i++) expect = inter(expect, singles[cb.keys[i]]);
    const s0 = singles[cb.keys[0]];
    const s1 = singles[cb.keys[1]];
    const disc = unionAll.size > expect.size || s0.size === 0 || s1.size === 0 || setEq(s0, s1);
    const ok = arm.ok && !!badge && badge[0] != null && setEq(col, expect) && col.size === badge[0] && disc;
    B_ITEMS.push({
      focus: 'combo',
      id: cb.id,
      keys: cb.keys,
      ok,
      armOk: arm.ok,
      badgeShown: badge ? badge[0] : null,
      badgeTotal: badge ? badge[1] : null,
      collected: [...col].sort(),
      expected: [...expect].sort(),
      discriminator: disc,
      onlyBoard: diff(col, expect),
      onlyExpected: diff(expect, col),
    });
  }

  const ladder: { id: string; keys: string[] }[] = [
    { id: 'clock', keys: ['f_clock'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
    { id: 'clock+jet+susp', keys: ['f_clock', 'f_jet', 'f_susp'] },
  ];
  const ladderSets: Set<string>[] = [];
  for (const st of ladder) {
    const arm = await setChipsExactly(st.keys);
    const badge = await waitBadgeStable();
    const col = badge ? await collectBoard(badge[0] ?? 0) : new Set<string>();
    ladderSets.push(col);
  }
  const ladderOk = ladderSets.length === 3 && ladderSets.every((c, i) => i === 0 || isSubset(c, ladderSets[i - 1]));
  ck('ب<D7>', ladderOk && monotone(ladderSets.map((c) => c.size)), {
    sizes: ladderSets.map((c) => c.size),
    subset: ladderSets.map((c, i) => (i === 0 ? null : isSubset(c, ladderSets[i - 1]))),
  });

  const arm7b = await setChipsExactly(['f_clock']);
  const badge7b = await waitBadgeStable();
  const col7b = badge7b ? await collectBoard(badge7b[0] ?? 0) : new Set<string>();
  const b7bok = arm7b.ok && setEq(col7b, ladderSets[0]);
  ck('ب<D7>ب', b7bok, { sizeRecheck: col7b.size, sizeFirst: ladderSets[0].size, onlyRecheck: diff(col7b, ladderSets[0]), onlyFirst: diff(ladderSets[0], col7b) });

  await setChipsExactly(['f_clock']);
  await clickT('filters-reset');
  const shown8 = await waitShownIs(u0.size);
  const col8 = await collectBoard(u0.size);
  const live8 = (await pressOf('live-only-toggle')) === 'true';
  const suffix8 = (await pressOf('numeric-suffix-toggle')) === 'true';
  const cen8 = chipCensus((await readChips()).texts);
  const b8ok = !!shown8 && setEq(col8, u0) && live8 && suffix8 && cen8.pressed.length === 0 && cen8.extra.length === 0;
  ck('ب<D8>', b8ok, {
    shown: shown8,
    resetEqualsU0: setEq(col8, u0),
    liveOnly: live8,
    numericSuffixHidden: suffix8,
    pressedAfterReset: cen8.pressed,
    extra: cen8.extra,
    onlyAfter: diff(col8, u0),
    onlyBefore: diff(u0, col8),
  });