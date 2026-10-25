/* Research-only viewer. No production bundle, no network, no trading action. */
(() => {
  'use strict';

  const DETECTOR_FA = {
    doji: 'دوجی',
    bullish_engulfing: 'پوشای صعودی',
    bearish_engulfing: 'پوشای نزولی',
    hammer: 'چکش',
    shooting_star: 'ستارهٔ ثاقب',
    double_top: 'سقف دوقلو',
    double_bottom: 'کف دوقلو',
    ascending_triangle: 'مثلث صعودی',
    descending_triangle: 'مثلث نزولی',
    symmetrical_triangle: 'مثلث متقارن',
    rising_wedge: 'گوهٔ صعودی',
    falling_wedge: 'گوهٔ نزولی',
    higher_high: 'سقف بالاتر',
    higher_low: 'کف بالاتر',
    lower_high: 'سقف پایین‌تر',
    lower_low: 'کف پایین‌تر',
    bos_bullish: 'شکست ساختار صعودی',
    bos_bearish: 'شکست ساختار نزولی',
    liquidity_sweep_high: 'شکار نقدینگی بالا',
    liquidity_sweep_low: 'شکار نقدینگی پایین',
  };
  const FAMILY_FA = {
    candlestick: 'کندلی',
    chart_structure: 'ساختار نمودار',
    market_structure: 'ساختار بازار',
  };
  const BIAS_FA = { bullish: 'صعودی', bearish: 'نزولی', neutral: 'خنثی', mixed: 'ترکیبی' };
  const ROLE_FA = { candle: 'کندل', high: 'سقف', low: 'کف', peak: 'قله', trough: 'دره' };
  const TF_FA = { D: 'روزانه', W: 'هفتگی', M: 'ماهانه' };
  const MODE_FA = { adjusted: 'تعدیل‌شده', raw: 'خام' };

  const state = {
    data: null,
    symbol: null,
    timeframe: 'D',
    mode: 'adjusted',
    detector: '',
    method: 'latest',
    tab: 'events',
    selectedEvent: null,
    selectedGroup: null,
    renderToken: 0,
    seriesKey: null,
  };

  const el = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat('fa-IR', { maximumFractionDigits: 2 });
  const nfAxis = new Intl.NumberFormat('fa-IR', { notation: 'compact', maximumFractionDigits: 1 });
  let jalaliFmt = null;
  try {
    jalaliFmt = new Intl.DateTimeFormat('fa-IR-u-ca-persian', {
      year: 'numeric', month: '2-digit', day: '2-digit', timeZone: 'UTC',
    });
  } catch (_) {
    jalaliFmt = null;
  }

  function faNum(value) {
    return value === null || value === undefined || !Number.isFinite(Number(value))
      ? '—'
      : nf.format(Number(value));
  }
  function faIndex(value) {
    return Number.isFinite(Number(value)) ? new Intl.NumberFormat('fa-IR').format(Number(value)) : '—';
  }
  function formatDate(iso) {
    if (!iso) return '—';
    try {
      return jalaliFmt ? jalaliFmt.format(new Date(`${String(iso).slice(0, 10)}T00:00:00Z`)) : String(iso);
    } catch (_) {
      return String(iso);
    }
  }
  function escapeHtml(text) {
    return String(text ?? '')
      .replaceAll('&', '&amp;')
      .replaceAll('<', '&lt;')
      .replaceAll('>', '&gt;')
      .replaceAll('"', '&quot;')
      .replaceAll("'", '&#39;');
  }
  function biasClass(bias) {
    if (bias === 'bullish') return 'bull';
    if (bias === 'bearish') return 'bear';
    if (bias === 'mixed') return 'mixed';
    return 'neutral';
  }
  function detectorFa(id) { return DETECTOR_FA[id] || id; }
  function familyFa(id) { return FAMILY_FA[id] || id; }
  function biasFa(id) { return BIAS_FA[id] || id; }

  function populateSymbols() {
    const select = el('symbol');
    const symbols = [...state.data.symbols].sort((a, b) => a.symbol.localeCompare(b.symbol));
    select.innerHTML = symbols
      .map((s) => `<option value="${escapeHtml(s.symbol)}">${escapeHtml(s.symbol)}</option>`)
      .join('');
    state.symbol = symbols[0]?.symbol ?? null;
    select.value = state.symbol;
  }

  function populateDetectors() {
    const select = el('detector');
    select.innerHTML = '<option value="">همه</option>' + Object.keys(DETECTOR_FA)
      .map((id) => `<option value="${id}">${DETECTOR_FA[id]}</option>`)
      .join('');
  }

  function symbolEntry() {
    return state.data.symbols.find((s) => s.symbol === state.symbol) || null;
  }
  function seriesEntry() {
    const entry = symbolEntry();
    return entry?.timeframes?.[state.timeframe] || null;
  }
  function currentEvents(series) {
    if (!series) return [];
    return (state.mode === 'adjusted' ? series.events : series.rawEvents) || [];
  }
  function currentBars(series) {
    if (!series) return [];
    return (state.mode === 'adjusted' ? series.adjusted : series.raw) || [];
  }

  function resetSelection() {
    state.selectedEvent = null;
    state.selectedGroup = null;
  }

  function selectEvent(key) {
    state.selectedEvent = key;
    renderDetail();
    renderEventList();
    renderGroups();
    draw();
  }
  function selectGroup(id) {
    state.selectedGroup = id;
    state.selectedEvent = null;
    renderDetail();
    renderEventList();
    renderGroups();
    draw();
  }

  function seriesKeyOf(series) {
    return `${state.symbol}|${state.timeframe}|${state.mode}`;
  }

  function renderAll() {
    const token = ++state.renderToken;
    state.seriesKey = null;
    el('eventPanel').innerHTML = '<div class="empty">در حال خواندن سری…</div>';
    el('detail').innerHTML = '<div class="empty">—</div>';
    el('saliencePanel').innerHTML = '<div class="empty">—</div>';
    el('groupPanel').innerHTML = '<div class="empty">—</div>';
    clearCanvas('در حال خواندن سری…');
    const series = seriesEntry();
    if (!series) {
      el('seriesKey').textContent = `${state.symbol} · ${TF_FA[state.timeframe]} · سری موجود نیست`;
      el('footer').innerHTML = '<span class="warn">این ترکیب نماد/تایم‌فریم در داده نیست.</span>';
      return;
    }
    state.seriesKey = seriesKeyOf(series);
    const events = currentEvents(series);
    const bars = currentBars(series);
    const entry = symbolEntry();
    const first = bars[0]?.[0] ?? '—';
    const last = bars[bars.length - 1]?.[0] ?? '—';
    el('seriesKey').textContent =
      `${state.symbol} · ${TF_FA[state.timeframe]} · ${MODE_FA[state.mode]} · ` +
      `${faIndex(bars.length)} کندل · ${faIndex(events.length)} رویداد · ${formatDate(last)}`;
    const combined = entry?.combinedAvailable === true ? 'زنجیرهٔ تعدیل تأییدشده'
      : entry?.combinedAvailable === false ? 'بدون زنجیرهٔ تعدیل تأییدشده' : 'وضعیت تعدیل نامعلوم';
    el('footer').innerHTML =
      `<span>${escapeHtml(entry?.sector || 'صنعت نامعلوم')}</span>` +
      `<span>${escapeHtml(entry?.liquidityBand || '—')}</span>` +
      `<span>${escapeHtml(combined)}</span>` +
      `<span>منبع تعدیل: ${escapeHtml(entry?.adjustSource || '—')}</span>` +
      `<span>${formatDate(first)} تا ${formatDate(last)}</span>` +
      (series.adjustedError ? `<span class="warn">خطای اسکن تعدیل‌شده: ${escapeHtml(series.adjustedError)}</span>` : '') +
      (series.rawError ? `<span class="warn">خطای اسکن خام: ${escapeHtml(series.rawError)}</span>` : '') +
      `<span>${escapeHtml(state.data.meta.disclaimer)}</span>`;

    renderDetectorOptions(events);
    if (token !== state.renderToken) return;
    draw();
    renderEventList();
    renderGroups();
    renderSalience();
    renderDetail();
    window.__ceViewerState = {
      seriesKey: state.seriesKey,
      symbol: state.symbol,
      timeframe: state.timeframe,
      mode: state.mode,
      barCount: bars.length,
      eventCount: events.length,
      groupCount: state.mode === 'adjusted' ? (series.salience?.groups?.length ?? 0) : 0,
      selectedEvent: state.selectedEvent,
      selectedGroup: state.selectedGroup,
      provisionalCount: state.mode === 'adjusted' ? (series.provisional?.length ?? 0) : 0,
    };
  }

  function renderDetectorOptions(events) {
    const select = el('detector');
    const present = new Set(events.map((e) => e.detector));
    for (const option of select.options) {
      if (!option.value) continue;
      option.hidden = !present.has(option.value);
    }
    if (state.detector && !present.has(state.detector)) {
      state.detector = '';
      select.value = '';
    }
  }

  function filteredEvents(events) {
    let filtered = state.detector ? events.filter((e) => e.detector === state.detector) : events;
    if (state.selectedGroup) {
      const group = currentGroup();
      const keys = new Set(group?.eventKeys || []);
      filtered = filtered.filter((e) => keys.has(e.key));
    }
    return [...filtered].sort((a, b) => b.confirmedAtIndex - a.confirmedAtIndex);
  }

  function currentGroup() {
    const series = seriesEntry();
    if (!series || state.mode !== 'adjusted') return null;
    return series.salience?.groups?.find((g) => g.id === state.selectedGroup) || null;
  }

  function renderEventList() {
    const series = seriesEntry();
    const events = currentEvents(series);
    const filtered = filteredEvents(events);
    const panel = el('eventPanel');
    el('selectionNote').textContent = state.selectedGroup
      ? `گروه انتخاب‌شده: ${faIndex(filtered.length)} رویداد`
      : `${faIndex(filtered.length)} از ${faIndex(events.length)} رویداد`;
    if (filtered.length === 0) {
      panel.innerHTML = '<div class="empty">رویدادی با این فیلتر نیست.</div>';
      return;
    }
    const groupKeys = new Set(currentGroup()?.eventKeys || []);
    const shown = filtered.slice(0, 300);
    panel.innerHTML = shown.map((event) => {
      const selected = state.selectedEvent === event.key;
      const muted = state.selectedGroup && !groupKeys.has(event.key);
      const anchors = event.anchors.map((a) =>
        `<span class="anchor">${escapeHtml(ROLE_FA[a.role] || a.role)} #${faIndex(a.index)} · ${faNumber(a.price)} · تأیید ${formatDate(a.time)}</span>`,
      ).join('');
      return `<div class="event${selected ? ' selected' : ''}${muted ? ' muted' : ''}" data-event="${escapeHtml(event.key)}">` +
        `<div class="event-head"><span class="detector">${escapeHtml(detectorFa(event.detector))}</span>` +
        `<span class="badge ${biasClass(event.bias)}">${biasFa(event.bias)}</span>` +
        `<span class="badge">${escapeHtml(familyFa(event.family))}</span>` +
        `<span class="badge">تأیید ${formatDate(event.confirmedAt)} · #${faIndex(event.confirmedAtIndex)}</span>` +
        (event.level !== null && event.level !== undefined ? `<span class="badge">سطح ${faNumber(event.level)}</span>` : '') +
        `</div><div class="event-meta">شروع #${faIndex(event.startIndex)} · ${faIndex(event.anchors.length)} لنگر</div>` +
        `<div class="anchors">${anchors}</div></div>`;
    }).join('') + (filtered.length > shown.length
      ? `<div class="empty">${faIndex(filtered.length - shown.length)} رویداد قدیمی‌تر نمایش داده نشد؛ فیلتر آشکارساز را محدود کنید.</div>`
      : '');
    panel.querySelectorAll('.event').forEach((node) => {
      node.addEventListener('click', () => selectEvent(node.dataset.event));
    });
  }
  function faNumber(value) { return faNum(value); }

  function orderedGroups(series) {
    if (!series?.salience) return [];
    const order = series.salience.order?.[state.method] || [];
    const byId = new Map(series.salience.groups.map((g) => [g.id, g]));
    return order.map((id) => byId.get(id)).filter(Boolean);
  }

  function groupCard(group, rank) {
    const selected = state.selectedGroup === group.id;
    const detectors = group.detectors.map(detectorFa).join(' · ');
    const levels = group.levels?.length ? `سطح: ${group.levels.map(faNum).join(' / ')}` : 'بدون سطح صریح';
    return `<div class="group${selected ? ' selected' : ''}" data-group="${escapeHtml(group.id)}">` +
      `<div class="group-head"><span class="rank">${faIndex(rank + 1)}</span>` +
      `<span class="detector">${escapeHtml(detectors)}</span>` +
      `<span class="badge ${biasClass(group.bias)}">${biasFa(group.bias)}</span>` +
      `<span class="badge">${faIndex(group.eventKeys.length)} رویداد</span>` +
      `<span class="badge">${faIndex(group.sharedAnchorIndices.length)} لنگر مشترک</span></div>` +
      `<div class="event-meta">آخرین تأیید ${formatDate(group.latestConfirmedAtIndex === null ? null : groupLatestIso(group))} · ` +
      `عمر ${faIndex(group.ageBars)} کندل · ${levels}</div>` +
      `<div class="event-meta">لنگرها: ${group.anchorIndices.map((i) => `#${faIndex(i)}`).join(' · ')}</div></div>`;
  }
  function groupLatestIso(group) {
    const series = seriesEntry();
    const events = currentEvents(series);
    const event = events.find((e) => e.key === group.newestEventKey);
    return event?.confirmedAt ?? null;
  }

  function renderGroups() {
    const panel = el('groupPanel');
    const series = seriesEntry();
    if (state.mode !== 'adjusted') {
      panel.innerHTML = '<div class="empty">سالینس فقط برای سری تعدیل‌شده محاسبه شده است.</div>';
      return;
    }
    const groups = orderedGroups(series);
    if (!groups.length) {
      panel.innerHTML = '<div class="empty">گروهی نیست.</div>';
      return;
    }
    panel.innerHTML = groups.map((g, i) => groupCard(g, i)).join('');
    panel.querySelectorAll('.group').forEach((node) => {
      node.addEventListener('click', () => {
        state.selectedGroup = state.selectedGroup === node.dataset.group ? null : node.dataset.group;
        state.selectedEvent = null;
        renderEventList();
        renderGroups();
        renderSalience();
        renderDetail();
        draw();
      });
    });
  }

  function renderSalience() {
    const rule = el('rule');
    const panel = el('saliencePanel');
    const series = seriesEntry();
    if (state.mode !== 'adjusted') {
      rule.textContent = 'سالینس فقط برای سری تعدیل‌شده است.';
      panel.innerHTML = '<div class="empty">برای دیدن گروه‌ها سری تعدیل‌شده را انتخاب کنید.</div>';
      return;
    }
    const rules = series?.salience?.rules || state.data.meta.salienceRules || {};
    rule.textContent = rules[state.method] || '—';
    const groups = orderedGroups(series);
    if (!groups.length) {
      panel.innerHTML = '<div class="empty">گروهی نیست.</div>';
      return;
    }
    panel.innerHTML = groups.slice(0, 80).map((g, i) => groupCard(g, i)).join('') +
      (groups.length > 80 ? `<div class="empty">${faIndex(groups.length - 80)} گروه دیگر نمایش داده نشد.</div>` : '');
    panel.querySelectorAll('.group').forEach((node) => {
      node.addEventListener('click', () => {
        state.selectedGroup = state.selectedGroup === node.dataset.group ? null : node.dataset.group;
        state.selectedEvent = null;
        renderEventList();
        renderGroups();
        renderSalience();
        renderDetail();
        draw();
      });
    });
  }

  function renderDetail() {
    const panel = el('detail');
    const series = seriesEntry();
    if (!series) {
      panel.innerHTML = '<div class="empty">سری موجود نیست.</div>';
      return;
    }
    const events = currentEvents(series);
    if (state.selectedEvent) {
      const event = events.find((e) => e.key === state.selectedEvent);
      if (!event) {
        panel.innerHTML = '<div class="empty">رویداد انتخاب‌شده در این سری نیست.</div>';
        return;
      }
      const levelAnchor = event.anchors.find((a) => (a.role === 'high' || a.role === 'low'));
      const timingIssues = [];
      for (const anchor of event.anchors) {
        const confirmed = anchor.confirmedAtIndex ?? anchor.index;
        if (confirmed > event.confirmedAtIndex) {
          timingIssues.push(`لنگر #${faIndex(anchor.index)} پس از رویداد تأیید شده است.`);
        }
      }
      if ((event.detector === 'bos_bullish' || event.detector === 'bos_bearish' ||
           event.detector === 'liquidity_sweep_high' || event.detector === 'liquidity_sweep_low') &&
          levelAnchor && (levelAnchor.confirmedAtIndex ?? levelAnchor.index) >= event.confirmedAtIndex) {
        timingIssues.push('سطح در همان کندل رویداد تأیید شده است، نه پیش از آن.');
      }
      panel.innerHTML =
        `<div class="event-head"><span class="detector">${escapeHtml(detectorFa(event.detector))}</span>` +
        `<span class="badge ${biasClass(event.bias)}">${biasFa(event.bias)}</span>` +
        `<span class="badge">${escapeHtml(familyFa(event.family))}</span></div>` +
        `<div class="event-meta">کندل تأیید: #${faIndex(event.confirmedAtIndex)} · ${formatDate(event.confirmedAt)}</div>` +
        `<div class="event-meta">کندل شروع ساختار: #${faIndex(event.startIndex)}</div>` +
        (event.level !== null && event.level !== undefined
          ? `<div class="event-meta">سطح/مرز رویداد: ${faNumber(event.level)}</div>` : '') +
        `<div class="anchors" style="margin-top:10px">` +
        event.anchors.map((a) =>
          `<span class="anchor">${escapeHtml(ROLE_FA[a.role] || a.role)} #${faIndex(a.index)} · ` +
          `قیمت ${faNumber(a.price)} · تأیید ${formatDate(a.time)} · ایندکس تأیید ${faIndex(a.confirmedAtIndex ?? a.index)}</span>`,
        ).join('') + '</div>' +
        (timingIssues.length
          ? `<div class="warn" style="margin-top:8px">${timingIssues.map(escapeHtml).join('<br>')}</div>`
          : `<div class="event-meta" style="margin-top:8px">همهٔ لنگرها در زمان رویداد یا پیش از آن قابل‌دانستن بوده‌اند.</div>`) +
        `<div class="event-meta" style="margin-top:8px">این رویداد پژوهشی است؛ نه سیگنال رسمی و نه احتمال موفقیت.</div>`;
      return;
    }
    const group = currentGroup();
    if (group) {
      panel.innerHTML =
        `<div class="event-head"><span class="detector">گروه سالینس</span>` +
        `<span class="badge ${biasClass(group.bias)}">${biasFa(group.bias)}</span>` +
        `<span class="badge">${faIndex(group.eventKeys.length)} رویداد</span></div>` +
        `<div class="event-meta">آخرین تأیید: ${formatDate(groupLatestIso(group))} · عمر ${faIndex(group.ageBars)} کندل</div>` +
        `<div class="event-meta">آشکارسازها: ${group.detectors.map((d) => escapeHtml(detectorFa(d))).join(' · ')}</div>` +
        `<div class="event-meta">لنگرهای مشترک: ${group.sharedAnchorIndices.map((i) => `#${faIndex(i)}`).join(' · ') || '—'}</div>` +
        `<div class="event-meta">سطوح: ${group.levels.length ? group.levels.map(faNumber).join(' / ') : '—'}</div>` +
        `<div class="event-meta" style="margin-top:8px">گروه‌بندی فقط بر پایهٔ لنگر مشترک است؛ ترتیب، امتیاز احتمال نیست.</div>`;
      return;
    }
    panel.innerHTML =
      `<div class="empty">یک رویداد از فهرست یا یک گروه را انتخاب کنید تا لنگرها، زمان تأیید و سطح دیده شود.</div>` +
      `<div class="event-meta">${escapeHtml(state.data.meta.disclaimer)}</div>`;
  }

  // ---- canvas ----
  let canvas = null;
  let ctx = null;
  let geometry = null;

  function setupCanvas() {
    canvas = el('chart');
    ctx = canvas.getContext('2d');
  }
  function resizeCanvas() {
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.max(1, Math.floor(rect.width * dpr));
    canvas.height = Math.max(1, Math.floor(rect.height * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  function clearCanvas(message) {
    if (!ctx) return;
    resizeCanvas();
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0b1220';
    ctx.fillRect(0, 0, w, h);
    if (message) {
      ctx.fillStyle = '#93a4bf';
      ctx.font = '13px Vazirmatn, Segoe UI, Tahoma, sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(message, w / 2, h / 2);
    }
  }

  function draw() {
    if (!canvas || !ctx) return;
    resizeCanvas();
    const series = seriesEntry();
    if (!series) { clearCanvas('سری موجود نیست'); return; }
    const bars = currentBars(series);
    const events = currentEvents(series);
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = '#0b1220';
    ctx.fillRect(0, 0, w, h);
    if (bars.length === 0) {
      ctx.fillStyle = '#93a4bf';
      ctx.textAlign = 'center';
      ctx.fillText('کندلی نیست', w / 2, h / 2);
      return;
    }
    const pad = { top: 22, right: 70, bottom: 28, left: 12 };
    const chartW = Math.max(1, w - pad.left - pad.right);
    const chartH = Math.max(1, h - pad.top - pad.bottom);
    let maxP = -Infinity;
    let minP = Infinity;
    for (const bar of bars) {
      if (bar[2] > maxP) maxP = bar[2];
      if (bar[3] < minP) minP = bar[3];
    }
    const selected = events.find((e) => e.key === state.selectedEvent);
    if (selected) {
      for (const anchor of selected.anchors) {
        maxP = Math.max(maxP, anchor.price);
        minP = Math.min(minP, anchor.price);
      }
      if (selected.level !== null && selected.level !== undefined) {
        maxP = Math.max(maxP, selected.level);
        minP = Math.min(minP, selected.level);
      }
    }
    if (!(maxP > minP)) { maxP += 1; minP -= 1; }
    const margin = (maxP - minP) * 0.04;
    maxP += margin;
    minP -= margin;
    const step = chartW / bars.length;
    const xAt = (i) => pad.left + (i + 0.5) * step;
    const yAt = (price) => pad.top + ((maxP - price) / (maxP - minP)) * chartH;
    geometry = { pad, chartW, chartH, step, xAt, yAt, bars, maxP, minP };

    // grid and axis
    ctx.font = '10px Vazirmatn, Segoe UI, Tahoma, sans-serif';
    ctx.textBaseline = 'middle';
    ctx.textAlign = 'left';
    for (let i = 0; i <= 4; i += 1) {
      const price = maxP - ((maxP - minP) * i) / 4;
      const y = yAt(price);
      ctx.strokeStyle = '#1b2a44';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad.left, y + 0.5);
      ctx.lineTo(pad.left + chartW, y + 0.5);
      ctx.stroke();
      ctx.fillStyle = '#7f91ad';
      ctx.fillText(nfAxis.format(price), pad.left + chartW + 8, y);
    }
    // date labels
    ctx.textAlign = 'center';
    ctx.fillStyle = '#7f91ad';
    for (let i = 0; i < 5; i += 1) {
      const index = Math.min(bars.length - 1, Math.round(((bars.length - 1) * i) / 4));
      ctx.fillText(formatDate(bars[index][0]), xAt(index), h - 10);
    }

    // candles
    const bodyW = Math.max(1, Math.min(7, step * 0.65));
    for (let i = 0; i < bars.length; i += 1) {
      const [date, open, high, low, close] = bars[i];
      const up = close >= open;
      const x = xAt(i);
      ctx.strokeStyle = up ? '#10b981' : '#f43f5e';
      ctx.fillStyle = up ? '#10b981' : '#f43f5e';
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, yAt(high));
      ctx.lineTo(x, yAt(low));
      ctx.stroke();
      const top = yAt(Math.max(open, close));
      const bottom = yAt(Math.min(open, close));
      const height = Math.max(1, bottom - top);
      ctx.fillRect(x - bodyW / 2, top, bodyW, height);
      if (bars.length <= 30) {
        ctx.save();
        ctx.fillStyle = '#7f91ad';
        ctx.font = '9px Vazirmatn, Segoe UI, Tahoma, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(formatDate(date), x, h - 10);
        ctx.restore();
      }
    }

    // provisional swings (separate, dashed)
    if (state.mode === 'adjusted') {
      ctx.save();
      ctx.setLineDash([3, 3]);
      ctx.strokeStyle = '#f59e0b';
      ctx.lineWidth = 1;
      for (const point of (series.provisional || []).slice(-20)) {
        if (point.index < 0 || point.index >= bars.length) continue;
        const x = xAt(point.index);
        const y = yAt(point.price);
        ctx.beginPath();
        ctx.moveTo(x, y - 4);
        ctx.lineTo(x + 4, y);
        ctx.lineTo(x, y + 4);
        ctx.lineTo(x - 4, y);
        ctx.closePath();
        ctx.stroke();
      }
      ctx.restore();
    }

    // event markers
    const groupKeys = new Set(currentGroup()?.eventKeys || []);
    for (const event of events) {
      if (event.confirmedAtIndex < 0 || event.confirmedAtIndex >= bars.length) continue;
      const bar = bars[event.confirmedAtIndex];
      const x = xAt(event.confirmedAtIndex);
      const above = event.bias === 'bullish';
      const y = above ? yAt(bar[3]) + 10 : yAt(bar[2]) - 10;
      const color = event.bias === 'bullish' ? '#10b981' : event.bias === 'bearish' ? '#f43f5e' : '#f59e0b';
      const isSelected = state.selectedEvent === event.key;
      const inGroup = state.selectedGroup ? groupKeys.has(event.key) : true;
      ctx.globalAlpha = inGroup ? 1 : 0.15;
      ctx.fillStyle = color;
      ctx.beginPath();
      if (above) {
        ctx.moveTo(x, y + 4);
        ctx.lineTo(x - 4, y - 4);
        ctx.lineTo(x + 4, y - 4);
      } else {
        ctx.moveTo(x, y - 4);
        ctx.lineTo(x - 4, y + 4);
        ctx.lineTo(x + 4, y + 4);
      }
      ctx.closePath();
      ctx.fill();
      if (isSelected) {
        ctx.strokeStyle = '#60a5fa';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.beginPath();
        ctx.arc(x, y, 9, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.globalAlpha = 1;
    }

    // selected event evidence
    if (selected) {
      const x = xAt(selected.confirmedAtIndex);
      ctx.save();
      ctx.strokeStyle = '#60a5fa';
      ctx.setLineDash([5, 4]);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(x, pad.top);
      ctx.lineTo(x, pad.top + chartH);
      ctx.stroke();
      ctx.setLineDash([]);
      for (const anchor of selected.anchors) {
        if (anchor.index < 0 || anchor.index >= bars.length) continue;
        const ax = xAt(anchor.index);
        const ay = yAt(anchor.price);
        ctx.fillStyle = '#60a5fa';
        ctx.beginPath();
        ctx.arc(ax, ay, 3.5, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = '#60a5fa';
        ctx.beginPath();
        ctx.moveTo(ax, ay);
        ctx.lineTo(x, yAt(selected.level ?? bars[selected.confirmedAtIndex][4]));
        ctx.stroke();
      }
      if (selected.level !== null && selected.level !== undefined) {
        const ly = yAt(selected.level);
        ctx.strokeStyle = '#60a5fa';
        ctx.setLineDash([8, 5]);
        ctx.beginPath();
        ctx.moveTo(pad.left, ly);
        ctx.lineTo(pad.left + chartW, ly);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = '#93c5fd';
        ctx.textAlign = 'left';
        ctx.font = '10px Vazirmatn, Segoe UI, Tahoma, sans-serif';
        ctx.fillText(`سطح ${faNumber(selected.level)}`, pad.left + 4, ly - 5);
      }
      ctx.restore();
    }
  }

  function bind() {
    el('symbol').addEventListener('change', (e) => {
      state.symbol = e.target.value;
      resetSelection();
      renderAll();
    });
    el('timeframe').addEventListener('change', (e) => {
      state.timeframe = e.target.value;
      resetSelection();
      renderAll();
    });
    el('mode').addEventListener('change', (e) => {
      state.mode = e.target.value;
      resetSelection();
      renderAll();
    });
    el('detector').addEventListener('change', (e) => {
      state.detector = e.target.value;
      state.selectedGroup = null;
      renderEventList();
      draw();
    });
    el('method').addEventListener('change', (e) => {
      state.method = e.target.value;
      renderGroups();
      renderSalience();
    });
    el('tabEvents').addEventListener('click', () => {
      state.tab = 'events';
      el('tabEvents').classList.add('active');
      el('tabGroups').classList.remove('active');
      el('eventPanel').style.display = '';
      el('groupPanel').style.display = 'none';
    });
    el('tabGroups').addEventListener('click', () => {
      state.tab = 'groups';
      el('tabGroups').classList.add('active');
      el('tabEvents').classList.remove('active');
      el('eventPanel').style.display = 'none';
      el('groupPanel').style.display = '';
    });
    el('tabDetail').addEventListener('click', () => {});
    window.addEventListener('resize', () => draw());
  }

  async function boot() {
    setupCanvas();
    bind();
    try {
      const response = await fetch('./viewer-data.json', { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      state.data = await response.json();
      populateSymbols();
      populateDetectors();
      renderAll();
    } catch (error) {
      clearCanvas('خواندن viewer-data.json ناموفق بود');
      el('footer').innerHTML = `<span class="warn">${escapeHtml(error.message)} — فایل را کنار index.html بگذارید و با یک سرور محلی باز کنید.</span>`;
    }
  }

  window.__ceViewer = {
    renderAll,
    setSymbol: (symbol) => {
      const select = el('symbol');
      if (![...select.options].some((o) => o.value === symbol)) return false;
      select.value = symbol;
      state.symbol = symbol;
      resetSelection();
      renderAll();
      return true;
    },
    setTimeframe: (timeframe) => {
      el('timeframe').value = timeframe;
      state.timeframe = timeframe;
      resetSelection();
      renderAll();
      return true;
    },
    setMode: (mode) => {
      el('mode').value = mode;
      state.mode = mode;
      resetSelection();
      renderAll();
      return true;
    },
    selectGroup: (id) => {
      state.selectedGroup = id;
      state.selectedEvent = null;
      renderEventList();
      renderGroups();
      renderSalience();
      renderDetail();
      draw();
    },
    selectEvent: (key) => selectEvent(key),
    state: () => window.__ceViewerState,
  };

  boot();
})();
