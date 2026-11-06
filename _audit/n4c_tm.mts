  // ── فازِ ت: درختِ استراتژی در مسیرِ معکوس — همان ورودی، همان نتیجه، نماد به نماد ──
  const tCases: { id: string; keys: string[] }[] = [
    ...CHIP_ORDER.map((k) => ({ id: k, keys: [k] })),
    { id: 'roobi+noqteh', keys: ['f_roobi', 'f_noqteh'] },
    { id: 'clock+jet', keys: ['f_clock', 'f_jet'] },
  ];
  let anyShownT = false;
  for (const tc of tCases) {
    const item: Record<string, unknown> = {
      name: tc.id,
      keys: tc.keys,
      armOk: false,
      badge: null,
      bCollected: [],
      tree: null,
      drawerPresent: false,
      drawerClosed: false,
      drawerTotal: null,
      t1: false,
      t2: false,
      t3: false,
      t2Bad: [],
      t2OnlyDrawer: [],
      t2OnlyBoard: [],
      statusHist: {},
      ok: false,
    };
    try {
      await gotoMarket();
      const arm = await setChipsExactly(tc.keys);
      item.armOk = arm.ok;
      const badge = await waitBadgeStable();
      item.badge = badge;
      if (!badge) throw new Error('badge not stable');
      if ((badge[0] ?? 0) > 0) anyShownT = true;
      const bSet = await collectBoard(badge[0] ?? 0);
      item.bCollected = [...bSet].sort();
      await gotoMaster();
      await ensurePressed('funnel-mode-reverse', true);
      await gotoTreePage();
      try {
        await selectTreePreset(TREE_CUSTOM);
      } catch {}
      await sleep(700);
      const tn = await waitTreeStable();
      item.tree = tn;
      const drawerPresent = await openTapeDrawer();
      item.drawerPresent = drawerPresent;
      if (tc.id === tCases[0].id) {
        await page.screenshot({ path: `${DIR}/funnel_parity_t_drawer.png` });
      }
      const dr = await readTapeDrawerRaw();
      item.drawerTotal = dr ? dr.total : null;
      item.drawerClosed = await closeTapeDrawer();
      const t1 = !!tn && tn.big === badge[0] && tn.input === badge[0] && tn.universe === badge[0];
      const dsyms = dr ? dr.rows.map((r) => norm(r.sym)) : [];
      let t2: boolean;
      if ((badge[0] ?? 0) === 0) {
        t2 = !drawerPresent || dr === null || dr.rows.length === 0;
      } else {
        t2 =
          !!dr &&
          dr.total === bSet.size &&
          setEq(asSet(dsyms), bSet) &&
          dr.rows.every((r) => r.status === 'PASS' || (r.status === 'UNAVAILABLE' && nz(r.why).length > 0));
      }
      const t3 = badge[1] === freeze.frozenCount;
      const hist: Record<string, number> = {};
      if (dr) for (const r of dr.rows) hist[String(r.status)] = (hist[String(r.status)] ?? 0) + 1;
      item.t2Bad = dr
        ? dr.rows
            .filter((r) => !(r.status === 'PASS' || (r.status === 'UNAVAILABLE' && nz(r.why).length > 0)))
            .map((r) => ({ sym: norm(r.sym), status: r.status, why: r.why }))
        : [];
      item.t2OnlyDrawer = dr ? diff(asSet(dsyms), bSet) : [];
      item.t2OnlyBoard = dr ? diff(bSet, asSet(dsyms)) : [];
      item.statusHist = hist;
      item.t1 = t1;
      item.t2 = t2;
      item.t3 = t3;
      ck(`ت<D1>-${tc.id}`, t1, { tree: tn, badgeShown: badge[0] });
      ck(`ت<D2>-${tc.id}`, t2, { badgeShown: badge[0], drawerPresent, drawerTotal: dr ? dr.total : null, rows: dr ? dr.rows.length : 0, statusHist: hist, onlyDrawer: item.t2OnlyDrawer, onlyBoard: item.t2OnlyBoard });
      ck(`ت<D3>-${tc.id}`, t3, { badgeTotal: badge[1], frozenCount: freeze.frozenCount });
    } catch (e) {
      item.err = String(e);
    }
    item.ok = item.armOk === true && item.t1 === true && item.t2 === true && item.t3 === true && !item.err;
    T_ITEMS.push(item);
  }
  ck('ت<D0>', anyShownT, { anyShown: anyShownT });

  // ── فازِ م: پریست<Z>های قیف — فیلترها همان نتیجهٔ تابلو، پریست فقط چیدمانِ مراحل ──
  const u0Size = u0.size;
  for (const p of ['trend', 'swing', 'hourglass']) {
    const pair = M_PAIRS[p];
    const item: Record<string, unknown> = {
      preset: p,
      keys: pair,
      armOk: false,
      badge: null,
      collected: [],
      revOk: false,
      revOk2: false,
      presetOk: false,
      chainOk: false,
      techSettled: null,
      m1: false,
      m2: false,
      m3: false,
      m4: false,
      leakOk: false,
      restoreOk: false,
      ok: false,
    };
    try {
      await gotoMarket();
      const arm = await setChipsExactly(pair);
      item.armOk = arm.ok;
      const badge = await waitBadgeStable();
      item.badge = badge;
      if (!badge) throw new Error('badge not stable');
      const mSet = await collectBoard(badge[0] ?? 0);
      item.collected = [...mSet].sort();
      await gotoMaster();
      item.revOk = await ensurePressed('funnel-mode-reverse', true);
      item.revOk2 = (await pressOf('funnel-mode-reverse')) === 'true';
      item.presetOk = await ensurePressed(`funnel-preset-${p}`, true);
      const chainOk = await waitChainKeys(K[p]);
      item.chainOk = chainOk;
      item.techSettled = !(await settleTech());
      await sleep(400);
      const s = await waitStableSnap(`m_${p}`);
      const gotSet = s ? new Set(CHIP_ORDER.filter((kk) => s.chips[kk] === true)) : new Set<string>();
      const m1 =
        !!s &&
        arm.ok &&
        item.revOk === true &&
        item.revOk2 === true &&
        item.presetOk === true &&
        chainOk &&
        setEq(gotSet, asSet(pair)) &&
        s.chips.f_legal === false &&
        s.door.boardScope === u0Size &&
        s.door.total === mSet.size &&
        s.chipInput === mSet.size &&
        s.stages.tape.countBadge === mSet.size;
      const m2 = !!s && s.door.total === s.counts.universe && s.counts.universe === s.chipInput && s.chipInput === mSet.size;
      const m3 = !!s && setEq(asSet(s.stages.tape.main), mSet);
      const s4 = await waitCovStable();
      const m4 =
        !!s4 &&
        s4.coverage1.universe === mSet.size &&
        s4.counts.universe === mSet.size &&
        (mSet.size === 0 ? s4.coverage2.raw == null : s4.coverage2.wanted === Math.min(mSet.size, 60) && s4.coverage2.resolved === s4.coverage1.live);
      item.m1 = m1;
      item.m2 = m2;
      item.m3 = m3;
      item.m4 = m4;
      ck(`م<D1>-${p}`, m1, {
        gotChips: [...gotSet].sort(),
        boardScope: s ? s.door.boardScope : null,
        u0Size,
        doorTotal: s ? s.door.total : null,
        chipInput: s ? s.chipInput : null,
        tapeBadge: s ? s.stages.tape.countBadge : null,
        mSetSize: mSet.size,
      });
      ck(`م<D2>-${p}`, m2, { doorTotal: s ? s.door.total : null, countsUniverse: s ? s.counts.universe : null, chipInput: s ? s.chipInput : null, mSetSize: mSet.size });
      ck(`م<D3>-${p}`, m3, {
        tapeMain: s ? s.stages.tape.main.length : null,
        mSetSize: mSet.size,
        onlyTape: s ? diff(asSet(s.stages.tape.main), mSet) : [],
        onlyBoard: s ? diff(mSet, asSet(s.stages.tape.main)) : [],
      });
      ck(`م<D4>-${p}`, m4, { coverage1: s4 ? s4.coverage1 : null, coverage2: s4 ? s4.coverage2 : null, mSetSize: mSet.size, beyond: s4 ? s4.coverage1.beyond : null });
      let leakOk = false;
      let restoreOk = false;
      let leakDetail: Record<string, unknown> = { skipped: true };
      if (s) {
        let clicked = false;
        try {
          await clickT('funnel-tape-chip-f_legal');
          clicked = true;
        } catch {}
        await sleep(700);
        await settleTech();
        const post = await waitStableSnap(`m_${p}_leak`);
        leakOk =
          clicked &&
          !!post &&
          post.chips.f_legal === true &&
          keysEqual(post.keys, s.keys) &&
          nz(post.doorText) === nz(s.doorText) &&
          post.chipInput === s.chipInput &&
          post.counts.universe === s.counts.universe &&
          setEq(asSet(post.stages.tape.main), asSet(s.stages.tape.main));
        if (clicked) {
          try {
            await clickT('funnel-tape-chip-f_legal');
          } catch {}
          await sleep(500);
          restoreOk = (await pressOf('funnel-tape-chip-f_legal')) === 'false';
        }
        leakDetail = {
          clicked,
          leakOk,
          restoreOk,
          preUniverse: s.counts.universe,
          postUniverse: post ? post.counts.universe : null,
          preTape: s.stages.tape.main.length,
          postTape: post ? post.stages.tape.main.length : null,
          preDoor: s.door.total,
          postDoor: post ? post.door.total : null,
        };
      }
      ck(`م<D5>-${p}`, leakOk && restoreOk, leakDetail);
      item.leakOk = leakOk;
      item.restoreOk = restoreOk;
      item.ok = m1 && m2 && m3 && m4 && leakOk && restoreOk;
    } catch (e) {
      item.err = String(e);
    }
    M_ITEMS.push(item);
  }

  await gotoMarket();
  const offM6 = await setChipsExactly([]);
  const shownM6 = await waitShownIs(u0Size);
  const colM6 = await collectBoard(u0Size);
  const m6ok = offM6.ok && !!shownM6 && setEq(colM6, u0);
  ck('م<D6>', m6ok, { offOk: offM6.ok, shown: shownM6, equalsU0: setEq(colM6, u0), onlyAfter: diff(colM6, u0), onlyBefore: diff(u0, colM6) });

  (report.notes as string[]).push(
    'فریزِ داده: یک لحظه از api/market (rev و شمارِ ردیف) برایِ هر دو سطح بازپخش شد؛ درستیِ خودِ ابزار در فازِ ب آزموده شد.',
    'در حالتِ معکوس، عبورِ فیلترها ساختاری است و «زنده<Z>ماندن» را ثابت نمی<Z>کند؛ صفرهای واقعی فقط در فازِ ب اثبات می<Z>شوند.',
    'پوششِ تکنیکال در فازِ م فقط شمارشی است و سقفِ <D6><D0> «راستی<Z>آزمایی<Z>نشده» می<Z>ماند؛ ناهمسانیِ چیپ و پریست در م<D5> ثبت شد.',
  );