/* mstat.js — v9.7.5 فاز ۱: داشبورد «وضعیت بازار»
   همه‌چیز از /api/mstat/* محلی (market.db) خوانده می‌شود؛ دیگر چیزی از
   tradersarena.ir پروکسی نمی‌شود. یک درخواستِ board برای کل تب، تا هر
   بارِ رندر یک round-trip باشد (خط قرمز: رندر روان بدون افت فریم). */

var MS_TIMER = null;
var MS_STATE = { mode: 'cum', group: 'eq_all', industry: '', sort: 'clock',
                 desc: true, cltab: 'all', data: null, watch: null, busy: false };

/* ---------- قالب‌بندی اعداد ---------- */
function msNum(v, dec) {
  if (v === null || v === undefined || !isFinite(v)) return '<span class="ms-neu">—</span>';
  return Number(v).toLocaleString('fa-IR', { minimumFractionDigits: dec || 0,
                                             maximumFractionDigits: dec === undefined ? 0 : dec });
}
function msSigned(v, dec) {           /* مثبت سبز / منفی قرمز */
  if (v === null || v === undefined || !isFinite(v)) return '<span class="ms-neu">—</span>';
  var cls = v > 0 ? 'ms-pos' : (v < 0 ? 'ms-neg' : 'ms-neu');
  var s = Number(Math.abs(v)).toLocaleString('fa-IR', { maximumFractionDigits: dec === undefined ? 1 : dec });
  return '<span class="' + cls + '">' + (v < 0 ? '−' + s : (v > 0 ? '+' + s : s)) + '</span>';
}
function msPct(v, dec) {
  if (v === null || v === undefined || !isFinite(v)) return '<span class="ms-neu">—</span>';
  return msSigned(v, dec === undefined ? 2 : dec) + '<span class="ms-neu">٪</span>';
}
function msEsc(s) {
  return String(s === null || s === undefined ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function msEl(id) { return document.getElementById(id); }
function msSet(id, html) { var e = msEl(id); if (e) e.innerHTML = html; }

/* ---------- دریافت و رندر ---------- */
async function msRefresh(force) {
  if (MS_STATE.busy) return;                       /* polling روی polling سوار نشود */
  MS_STATE.busy = true;
  var st = msEl('msStatus');
  if (st) st.textContent = '⏳ در حال محاسبه…';
  try {
    var url = '/api/mstat/board?group=' + encodeURIComponent(MS_STATE.group) + '&limit=120';
    var j = await fetch(url, { cache: 'no-store' }).then(function (r) { return r.json(); });
    if (!j || j.status !== 'ok') {
      if (st) st.textContent = '⚠️ ' + msEsc(j && j.message || 'خطا');
      return;
    }
    MS_STATE.data = j;
    msRender(j);
    if (!MS_STATE.watch) msLoadWatchlist();
    var a = (j.summary && j.summary.asof) || {};
    var hh = String(a.h_even || 0).padStart(6, '0');
    if (st) st.textContent = '✓ محلی از بانک · ' + (a.d_even || '') + ' · '
      + hh.slice(0, 2) + ':' + hh.slice(2, 4);
  } catch (e) {
    console.warn('[mstat]', e);
    if (st) st.textContent = '⚠️ خطای اتصال';
  } finally {
    MS_STATE.busy = false;
  }
}

function msRender(j) {
  msRenderMacro(j.smartmoney);
  msRenderHealth(j.summary);
  msRenderSummary(j.summary);
  msRenderSmartFlow(j.smartmoney);
  msRenderThermo(j.thermometer);
  msDrawHistogram('msHisto12', j.histogram && j.histogram.histo12);
  msDrawHistogram('msHisto7', j.histogram && j.histogram.histo7);
  msSet('msHistoNote', j.histogram
    ? ('معامله‌شده: ' + msNum(j.histogram.total) + ' نماد · بی‌بازدهی: ' + msNum(j.histogram.nodata)
       + (j.histogram.not_traded ? ' · بدون معامله (شمرده نشد): ' + msNum(j.histogram.not_traded) : ''))
    : '');
  msRenderDepth(j.depth);
  msRenderQueueSplit(j.depth);
  msRenderPhases(j.phases);
  msRenderClient(j.clientsplit);
  msRenderIndustries(j.industries);
  msRenderGrid(j.mainwatch);
  msDrawTimelines(j.timeline);
}

/* ---------- v9.8.0: بنر شاخص نقدینگی کلان (سند FTS ص۳) ---------- */
function msRenderMacro(sm) {
  var m = sm && sm.macro;
  if (!m) {
    msSet('msMacroHemat', '<span class="ms-neu">—</span>');
    msSet('msMacroLabel', '—');
    return;
  }
  msSet('msMacroHemat', msNum(m.value_hemat, 1));
  var lb = msEl('msMacroLabel');
  if (lb) {
    lb.className = 'ms-health ' + m.state;
    lb.textContent = (m.state === 'good' ? '🟢' : m.state === 'bad' ? '🔴' : '🟡')
      + ' وضعیت: ' + m.label;
    lb.title = 'قانون FTS صفحهٔ ۳: ≥ ' + msNum(m.good_min, 0) + ' همت مساعد · ≤ '
      + msNum(m.bad_max, 0) + ' همت نامساعد';
  }
  /* هشدار ۸۰٪ — «فرصت پایش برای ورود (FTS)» */
  var w = sm.watch_entry || {}, wEl = msEl('msMacroWatch');
  if (wEl) {
    wEl.className = 'ms-watch' + (w.active ? '' : ' hidden');
    msSet('msMacroWatchSub', w.active
      ? (msNum(w.bearish_pct, 1) + '٪ نمادهای معامله‌شده منفی/صف فروش‌اند (آستانهٔ '
         + msNum(w.rule_pct, 0) + '٪) — ' + msNum(w.bearish) + ' از ' + msNum(w.known) + ' نماد')
      : (w.bearish_pct === null || w.bearish_pct === undefined
          ? 'شمار منفی‌ها هنوز معنا ندارد (بازار بدون معامله)'
          : 'منفی/صف فروش: ' + msNum(w.bearish_pct, 1) + '٪ — هنوز به آستانهٔ '
            + msNum(w.rule_pct, 0) + '٪ نرسیده'));
  }
  msSet('msMacroMeta', 'کل بازار (با بلوک‌های صندوق درآمد ثابت): '
    + msNum(m.value_hemat_all_market, 2) + ' همت · مبنای داوری: سهام، حق تقدم و ص.سهامی');
}

/* ---------- v9.8.0: نشانگر جریان پول هوشمند (سهام ⇄ درآمد ثابت) ---------- */
function msRenderSmartFlow(sm) {
  var f = sm && sm.flow;
  var eqEl = msEl('msFlowEqVal'), fxEl = msEl('msFlowFixedVal');
  if (!f || !eqEl || !fxEl) return;
  eqEl.innerHTML = msSigned(f.eq_flow_b_toman, 1);
  eqEl.style.color = f.eq_inflow ? 'var(--accent-green)' : 'var(--accent-red)';
  fxEl.innerHTML = msSigned(f.fixed_flow_b_toman, 1);
  fxEl.style.color = f.fixed_outflow ? 'var(--accent-red)' : 'var(--accent-green)';
  /* نوار دوسویه: وسط = صفر؛ ورود به راستِ مرکز (سبز)، خروج به چپ (قرمز) */
  var mx = Math.max(Math.abs(f.eq_flow_b_toman || 0), Math.abs(f.fixed_flow_b_toman || 0), 1);
  var bar = function (id, v) {
    var el = msEl(id);
    if (!el) return;
    var fill = el.querySelector('.ms-flow-fill');
    if (!fill) return;
    var pct = Math.min(100, 100 * Math.abs(v || 0) / mx / 2);
    fill.style.width = pct.toFixed(1) + '%';
    fill.className = 'ms-flow-fill ' + ((v || 0) > 0 ? 'in' : 'out');
  };
  bar('msFlowEqBar', f.eq_flow_b_toman);
  bar('msFlowFixedBar', f.fixed_flow_b_toman);
  msSet('msFlowEqDir', (f.eq_inflow ? '🟢 ورود پول خرد' : '🔴 خروج پول خرد')
    + ' · ارزش معاملات ' + msNum(f.eq_value_b_toman, 0) + ' م.تومان');
  msSet('msFlowFixedDir', (f.fixed_outflow ? '🟢 خروج از درآمد ثابت (به سود سهام)'
    : '🔴 ماندگاری/ورود به درآمد ثابت') + ' · ارزش ' + msNum(f.fixed_value_b_toman, 0) + ' م.تومان');
  var badge = msEl('msFlowBadge');
  if (badge) {
    if (f.ideal_fts) {
      badge.className = 'ms-health good';
      badge.textContent = '✅ جریان نقدینگی: حالت ایده‌آل FTS';
      badge.title = 'ورود هم‌زمان پول به سهام و خروج آن از صندوق‌های درآمد ثابت — پول از سودِ امن به ریسک می‌رود';
    } else {
      badge.className = 'ms-health mid';
      badge.textContent = '⇄ جریان هم‌سو';
      badge.title = 'ورود به سهام و خروج از درآمد ثابت هم‌زمان رخ نداده است';
    }
  }
  msSet('msFlowNote', 'قانون FTS: ورود پول خرد به «سهام و حق‌تقدم» هم‌زمان با خروج آن از «صندوق‌های '
    + 'درآمد ثابت» یعنی پول از پناهگاه امن بی‌ریسک به ریسک می‌آید — '
    + (f.ideal_fts ? 'این وضعیت اکنون برقرار است.'
                   : 'این وضعیت اکنون برقرار نیست. (سهام/حق‌تقدم: '
                     + msSigned(f.sr_flow_b_toman, 1) + ' م.تومان)'));
}

/* ---------- گام ۱: برچسب سلامت کلان ---------- */
function msRenderHealth(sm) {
  var el = msEl('msHealth');
  if (!el) return;
  var h = sm && sm.health;
  if (!h) { el.className = 'ms-health'; el.textContent = '—'; return; }
  el.className = 'ms-health ' + h.state;
  el.textContent = (h.state === 'good' ? '🟢' : h.state === 'bad' ? '🔴' : '🟡')
    + ' ' + h.label + ' · ' + msNum(h.value_hemat, 1) + ' همت';
  el.title = 'ارزش معاملات ' + msNum(h.value_hemat, 2) + ' همت — مبنای «'
    + (h.basis === 'eq_all' ? 'سهام، حق تقدم و ص.سهامی' : 'کل بازار') + '»\n'
    + 'کل بازار (با بلوک‌های صندوق درآمد ثابت): ' + msNum(h.value_hemat_all_market, 2) + ' همت\n'
    + 'قانون FTS صفحهٔ ۳: ≥ ' + msNum(h.good_min, 0) + ' همت مساعد · ≤ ' + msNum(h.bad_max, 0) + ' همت نامساعد';
}

/* ---------- گام ۱: جدول نه‌سطری خلاصه ---------- */
function msRenderSummary(sm) {
  var tb = document.querySelector('#msSummary tbody');
  if (!tb) return;
  var rows = (sm && sm.rows) || [];
  if (!rows.length) { tb.innerHTML = '<tr><td colspan="8" class="ms-empty">داده‌ای نیست</td></tr>'; return; }
  tb.innerHTML = rows.map(function (r) {
    var pow = (r.buy_power === null || r.buy_power === undefined)
      ? '<span class="ms-neu" title="سرانهٔ فروش صفر بود — نسبت ساختنی نیست">—</span>'
      : '<span class="' + (r.buy_power_up ? 'ms-pos' : 'ms-neg') + '">'
        + msNum(r.buy_power, 2) + (r.buy_power_up ? ' ▲' : ' ▼') + '</span>';
    return '<tr' + (r.key === 'all' ? ' class="ms-cat-total"' : '') + '>'
      + '<td title="' + msEsc(r.label) + '">' + msEsc(r.label) + '</td>'
      + '<td class="num ms-neu" title="معامله‌شده / کل نمادهای این دسته">'
        + msNum(r.traded) + '/' + msNum(r.symbols) + '</td>'
      + '<td class="num">' + msNum(r.volume_b_shares, 2) + '</td>'
      + '<td class="num">' + msNum(r.value_b_toman, 0) + '</td>'
      + '<td class="num">' + msNum(r.pc_buy_m_toman, 1) + '</td>'
      + '<td class="num">' + msNum(r.pc_sell_m_toman, 1) + '</td>'
      + '<td class="num">' + pow + '</td>'
      + '<td class="num">' + msSigned(r.money_flow_b_toman, 1) + '</td>'
      + '</tr>';
  }).join('');
}

/* ---------- گام ۲.۲: دماسنج مثبت/منفی ---------- */
function msRenderThermo(t) {
  var host = msEl('msThermo');
  if (!host) return;
  if (!t) { host.innerHTML = '<div class="ms-empty">داده‌ای نیست</div>'; return; }
  var pos = t.positive || 0, neg = t.negative || 0, zero = t.zero || 0;
  var tot = Math.max(pos + neg + zero, 1);
  var w = function (n) { return (100 * n / tot).toFixed(2); };
  var html = '<div class="ms-thermo">'
    + '<div class="g" style="width:' + w(pos) + '%" title="نمادهای مثبت">' + msNum(pos) + '</div>'
    + (zero ? '<div class="z" style="width:' + w(zero) + '%" title="صفر/بدون تغییر">' + msNum(zero) + '</div>' : '')
    + '<div class="r" style="width:' + w(neg) + '%" title="نمادهای منفی">' + msNum(neg) + '</div>'
    + '</div><div class="ms-hint">مثبت ' + msNum(t.positive_pct, 1) + '٪ · منفی ' + msNum(t.negative_pct, 1) + '٪'
    + (t.nodata ? ' · بی‌داده ' + msNum(t.nodata) : '')
    + (t.not_traded ? ' · بدون معامله ' + msNum(t.not_traded) : '') + '</div>';
  if (t.entry_opportunity) {
    html += '<div class="ms-hint"><span class="ms-pos">⚡ فرصت ورود (متدولوژی FTS)</span> — '
      + msNum(t.negative_pct, 1) + '٪ نمادها منفی‌اند، از آستانهٔ '
      + msNum(t.entry_rule_pct, 0) + '٪ گذشته است.</div>';
  }
  host.innerHTML = html;
}

/* ---------- بومِ روان: مقیاس با devicePixelRatio، یک بار طراحی ---------- */
function msCanvas(id) {
  var cv = msEl(id);
  if (!cv) return null;
  var dpr = window.devicePixelRatio || 1;
  var w = cv.clientWidth || 640, h = cv.clientHeight || 160;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
  }
  var ctx = cv.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, h);
  return { ctx: ctx, w: w, h: h };
}
function msFa(n) {
  return String(n).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[+d]; });
}

/* ---------- گام ۲.۱ / ۳.۳: میله‌های توزیع با تعداد بالای میله ---------- */
function msDrawHistogram(id, bars) {
  var c = msCanvas(id);
  if (!c) return;
  var ctx = c.ctx, W = c.w, H = c.h;
  if (!bars || !bars.length) {
    ctx.fillStyle = '#64748b'; ctx.font = '11px Vazirmatn,sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('داده‌ای برای توزیع نیست', W / 2, H / 2); return;
  }
  var pad = 6, bottom = 40, top = 16;
  var max = Math.max.apply(null, bars.map(function (b) { return b.count; })) || 1;
  var bw = (W - pad * 2) / bars.length;
  var COL = { neg: 'rgba(239,68,68,.78)', pos: 'rgba(34,197,94,.78)', neu: 'rgba(148,163,184,.55)' };
  ctx.textAlign = 'center';
  bars.forEach(function (b, i) {
    var hgt = Math.round((H - bottom - top) * (b.count / max));
    var x = pad + i * bw, y = H - bottom - hgt;
    ctx.fillStyle = COL[b.color] || COL.neu;
    ctx.fillRect(x + 1.5, y, Math.max(bw - 3, 2), hgt);
    ctx.fillStyle = b.count ? '#e2e8f0' : '#475569';
    ctx.font = '9px Vazirmatn,sans-serif';
    ctx.fillText(msFa(b.count), x + bw / 2, y - 3);
    ctx.save();
    ctx.translate(x + bw / 2, H - bottom + 9);
    ctx.rotate(-Math.PI / 3.4);
    ctx.fillStyle = '#94a3b8'; ctx.font = '8px Vazirmatn,sans-serif'; ctx.textAlign = 'right';
    ctx.fillText(b.label, 0, 0);
    ctx.restore();
  });
  ctx.strokeStyle = 'rgba(148,163,184,.25)';
  ctx.beginPath(); ctx.moveTo(0, H - bottom); ctx.lineTo(W, H - bottom); ctx.stroke();
}

/* ---------- نوار مقایسه‌ای ---------- */
function msBarRow(label, val, max, txt, color, title) {
  var pctv = max > 0 ? Math.min(100, 100 * (val || 0) / max) : 0;
  return '<div class="ms-bar-row"' + (title ? ' title="' + msEsc(title) + '"' : '') + '><span>' + label + '</span>'
    + '<span class="ms-bar-track"><span class="ms-bar-fill" style="width:' + pctv.toFixed(1)
    + '%;background:' + color + '"></span></span>'
    + '<span class="num" style="text-align:end">' + txt + '</span></div>';
}

/* ---------- گام ۲.۳: ارزش ۵ خط اول و صف‌ها ---------- */
function msRenderDepth(d) {
  var host = msEl('msDepth');
  if (!host) return;
  if (!d) { host.innerHTML = '<div class="ms-empty">داده‌ای نیست</div>'; return; }
  if (!d.depth_available) {
    host.innerHTML = '<div class="ms-hint">🟡 عمقِ سفارش در این بانک نیست؛ همگام‌سازیِ '
      + '۹٫۷٫۵ به بعد آن را از blDs می‌گیرد. تا «بروزرسانی» بعدی، به‌جای صفرِ '
      + 'گمراه‌کننده خالی می‌ماند.</div>';
    return;
  }
  var mxV = Math.max(d.buy_queue_b_toman || 0, d.sell_queue_b_toman || 0, 1);
  var nTot = Math.max((d.buy_queue_count || 0) + (d.sell_queue_count || 0), 1);
  host.innerHTML =
    msBarRow('🛒 خرید ۵ خط', d.buy_queue_b_toman, mxV, msNum(d.buy_queue_b_toman, 0),
             'rgba(34,197,94,.8)', 'ارزش سفارش‌های خرید پنج خط اول (میلیارد تومان)') +
    msBarRow('🏷 فروش ۵ خط', d.sell_queue_b_toman, mxV, msNum(d.sell_queue_b_toman, 0),
             'rgba(239,68,68,.8)', 'ارزش سفارش‌های فروش پنج خط اول (میلیارد تومان)') +
    msBarRow('صف خرید', d.buy_queue_count, nTot, msNum(d.buy_queue_count) + ' نماد',
             'rgba(34,197,94,.65)', 'نمادهایی که کل سمتِ فروشِ دفتر خالی است') +
    msBarRow('صف فروش', d.sell_queue_count, nTot, msNum(d.sell_queue_count) + ' نماد',
             'rgba(239,68,68,.65)', 'نمادهایی که کل سمتِ خریدِ دفتر خالی است') +
    '<div class="ms-hint">نسبت ارزش خرید به فروش ۵ خط: '
    + (d.ratio === null || d.ratio === undefined ? '<span class="ms-neu">—</span>'
       : '<span class="' + (d.ratio >= 1 ? 'ms-pos' : 'ms-neg') + '">' + msNum(d.ratio, 2) + '</span>')
    + ' · ' + msNum(d.symbols_with_depth) + ' نماد با عمق ثبت‌شده</div>';
}

/* ---------- گام ۳.۱: تفکیک سه‌گانهٔ صف‌ها ---------- */
function msRenderQueueSplit(d) {
  var host = msEl('msQueueSplit');
  if (!host) return;
  if (!d || !d.depth_available) {
    host.innerHTML = '<div class="ms-empty">دادهٔ عمق موجود نیست</div>'; return;
  }
  function grp(title, s, color) {
    s = s || {};
    var parts = [['عادی', s.normal | 0], ['کمتر از حجم مبنا', s.below_base | 0],
                 ['بدون معامله', s.no_trade | 0]];
    var tot = Math.max(parts.reduce(function (a, p) { return a + p[1]; }, 0), 1);
    return '<div style="margin:6px 0"><div style="font-size:.6875rem;margin-bottom:2px;color:'
      + color + '">' + title + ' · ' + msNum(tot) + ' نماد</div>'
      + '<div class="ms-thermo" style="height:16px">'
      + parts.map(function (p) {
          return p[1] ? '<div style="width:' + (100 * p[1] / tot).toFixed(2)
            + '%;background:' + color + '" title="' + p[0] + ': ' + msNum(p[1]) + '">'
            + msNum(p[1]) + '</div>' : '';
        }).join('') + '</div>'
      + '<div class="ms-hint">' + parts.map(function (p) { return p[0] + ' ' + msNum(p[1]); }).join(' · ')
      + (s.base_unknown ? ' · <span class="ms-neu">مبنا نامعلوم ' + msNum(s.base_unknown) + '</span>' : '')
      + '</div></div>';
  }
  host.innerHTML = grp('🛒 صف‌های خرید', d.buy, 'rgba(34,197,94,.9)')
                 + grp('🏷 صف‌های فروش', d.sell, 'rgba(239,68,68,.9)');
}

/* ---------- گام ۳.۲: چرخش وضعیت‌ها ---------- */
function msRenderPhases(p) {
  var host = msEl('msPhases');
  if (!host) return;
  if (!p) { host.innerHTML = '<div class="ms-empty">داده‌ای نیست</div>'; return; }
  if (!p.ready) {
    host.innerHTML = '<div class="ms-hint">برای شمارشِ چرخشِ صف‌ها دست‌کم دو نقطهٔ '
      + 'زمانی در یک نشست لازم است؛ اکنون ' + msNum(p.points) + ' نقطه ثبت شده‌است. '
      + 'با هر polling یک نقطه افزوده می‌شود.</div>';
    return;
  }
  var cell = function (x, color) {
    return '<div style="display:flex;justify-content:space-between;padding:3px 0">'
      + '<span style="color:' + color + '">' + msEsc(x.label) + '</span>'
      + '<b class="num">' + msNum(x.count) + '</b></div>';
  };
  host.innerHTML = '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">'
    + '<div><div class="ms-tlcap">تضعیف → فروش</div>'
    + (p.red || []).map(function (x) { return cell(x, 'var(--accent-red)'); }).join('') + '</div>'
    + '<div><div class="ms-tlcap">تقویت → خرید</div>'
    + (p.green || []).map(function (x) { return cell(x, 'var(--accent-green)'); }).join('') + '</div></div>'
    + '<div class="ms-hint">بر پایهٔ ' + msNum(p.points) + ' نقطهٔ زمانیِ همین نشست</div>';
}

/* ---------- نمودار خطی/مساحتیِ عمومیِ تایم‌لاین ---------- */
function msLineChart(id, labels, series) {
  var c = msCanvas(id);
  if (!c) return;
  var ctx = c.ctx, W = c.w, H = c.h;
  var n = labels.length;
  if (!n || !series.some(function (s) { return s.data && s.data.length; })) {
    ctx.fillStyle = '#64748b'; ctx.font = '11px Vazirmatn,sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(n ? 'مقداری برای ترسیم نیست' : 'منتظر نقطهٔ دومِ تایم‌لاین…', W / 2, H / 2);
    return;
  }
  var padL = 40, padR = 8, padT = 10, padB = 18;
  var vals = [];
  series.forEach(function (s) { (s.data || []).forEach(function (v) { if (v !== null && isFinite(v)) vals.push(v); }); });
  if (!vals.length) {
    ctx.fillStyle = '#64748b'; ctx.font = '11px Vazirmatn,sans-serif'; ctx.textAlign = 'center';
    ctx.fillText('بی‌داده', W / 2, H / 2); return;
  }
  var lo = Math.min.apply(null, vals.concat([0])), hi = Math.max.apply(null, vals.concat([0]));
  if (hi === lo) { hi = lo + 1; }
  var X = function (i) { return padL + (W - padL - padR) * (n === 1 ? 0.5 : i / (n - 1)); };
  var Y = function (v) { return padT + (H - padT - padB) * (1 - (v - lo) / (hi - lo)); };
  // شبکه و خطِ صفر
  ctx.strokeStyle = 'rgba(148,163,184,.14)'; ctx.fillStyle = '#64748b';
  ctx.font = '8px Vazirmatn,sans-serif'; ctx.textAlign = 'left';
  for (var g = 0; g <= 3; g++) {
    var vv = lo + (hi - lo) * g / 3, yy = Y(vv);
    ctx.beginPath(); ctx.moveTo(padL, yy); ctx.lineTo(W - padR, yy); ctx.stroke();
    ctx.fillText(Math.abs(vv) >= 1000 ? msFa(Math.round(vv / 1000) * 1000) : msFa(Math.round(vv * 10) / 10), 2, yy + 3);
  }
  if (lo < 0 && hi > 0) {
    ctx.strokeStyle = 'rgba(148,163,184,.5)';
    ctx.beginPath(); ctx.moveTo(padL, Y(0)); ctx.lineTo(W - padR, Y(0)); ctx.stroke();
  }
  series.forEach(function (s) {
    var pts = [];
    (s.data || []).forEach(function (v, i) { if (v !== null && isFinite(v)) pts.push([X(i), Y(v)]); });
    if (!pts.length) return;
    if (s.fill) {
      ctx.beginPath(); ctx.moveTo(pts[0][0], Y(Math.max(lo, 0)));
      pts.forEach(function (p) { ctx.lineTo(p[0], p[1]); });
      ctx.lineTo(pts[pts.length - 1][0], Y(Math.max(lo, 0)));
      ctx.closePath(); ctx.fillStyle = s.fill; ctx.fill();
    }
    ctx.beginPath(); ctx.strokeStyle = s.color; ctx.lineWidth = s.lineWidth || 1.6;
    pts.forEach(function (p, i) { i ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); });
    ctx.stroke(); ctx.lineWidth = 1;
    if (pts.length < 20) { ctx.fillStyle = s.color;
      pts.forEach(function (p) { ctx.beginPath(); ctx.arc(p[0], p[1], 2, 0, 6.284); ctx.fill(); }); }
  });
  ctx.fillStyle = '#64748b'; ctx.textAlign = 'center'; ctx.font = '9px Vazirmatn,sans-serif';
  /* v9.8.0: تیک‌های محورِ زمانِ ترازشده — تا ۶ برچسب با گامِ یکنواخت؛ سه
     برچسبِ ثابتِ قبلی روی نقطه‌های میانیِ دیده‌ نمی‌شد و ترازِ پنج نمودار
     را نمی‌شد سنجید. */
  var tstep = Math.max(1, Math.ceil((n - 1) / 5));
  for (var k = 0; k < n; k += tstep) {
    if (labels[k]) ctx.fillText(msFa(labels[k]), X(k), H - 5);
  }
  if (n > 1 && (n - 1) % tstep !== 0 && labels[n - 1]) {
    ctx.fillText(msFa(labels[n - 1]), X(n - 1), H - 5);   /* آخرین نقطه همیشه دیده شود */
  }
  if (series.length > 1) {                        /* راهنمای کوچک */
    var lx = padL + 4;
    series.forEach(function (s) {
      ctx.fillStyle = s.color; ctx.fillRect(lx, padT - 6, 7, 3);
      ctx.fillStyle = '#94a3b8'; ctx.textAlign = 'left'; ctx.font = '8px Vazirmatn,sans-serif';
      ctx.fillText(s.title || '', lx + 9, padT - 2);
      lx += 18 + (ctx.measureText(s.title || '').width);
    });
  }
}

/* ---------- گام ۴: پنج تایم‌لاین ---------- */
function msDrawTimelines(tl) {
  var note = msEl('msTlNote');
  if (note) {
    note.textContent = tl
      ? ((tl.mode === 'inst' ? 'نحله: لحظه‌ای' : 'نحله: مجموع (تجمعی)') + ' · '
         + msNum(tl.points) + ' نقطه' + (tl.note ? ' · ' + tl.note : ''))
      : '';
  }
  var ser = (tl && tl.series) || {};
  var T = ser.t || [];
  msLineChart('msTlFlow', T, [
    { data: ser.flow_eq_bt, color: '#22c55e', fill: 'rgba(34,197,94,.18)', title: 'سهام و ص.سهامی' },
    { data: ser.flow_fixed_bt, color: '#f472b6', fill: 'rgba(244,114,182,.14)', title: 'درآمد ثابت' }]);
  msLineChart('msTlPosNeg', T, [
    { data: ser.pos, color: '#22c55e', title: 'مثبت' },
    { data: ser.neg, color: '#ef4444', title: 'منفی' }]);
  msLineChart('msTlOrders', T, [
    { data: ser.bq_bt, color: '#22c55e', fill: 'rgba(34,197,94,.15)', title: 'سفارش خرید' },
    { data: ser.sq_bt, color: '#ef4444', fill: 'rgba(239,68,68,.12)', title: 'سفارش فروش' }]);
  msLineChart('msTlPerCap', T, [
    { data: ser.pc_buy, color: '#22c55e', title: 'سرانه خرید' },
    { data: ser.pc_sell, color: '#ef4444', title: 'سرانه فروش' }]);
  msLineChart('msTlQueues', T, [
    { data: ser.bq_n, color: '#22c55e', title: 'صف خرید' },
    { data: ser.sq_n, color: '#ef4444', title: 'صف فروش' }]);
}

/* ---------- گام ۵.۱ / ۲.۴: تفکیک حقیقی و حقوقی ---------- */
var MS_CL_TABS = [['all', 'بازار'], ['eq_funds', 'سهام و ص.سهامی'], ['stock', 'سهام'],
                  ['eq_fund', 'ص.سهامی'], ['fixed', 'ص.درآمدثابت'], ['top50', '۵۰ نماد بزرگ'],
                  ['lev', 'ص.اهرمی'], ['gold', 'ص.طلا'], ['silver', 'ص.نقره']];

function msRenderClient(cs) {
  var tabs = msEl('msClTabs');
  if (tabs) {
    tabs.innerHTML = MS_CL_TABS.map(function (t) {
      return '<button class="ms-tab' + (MS_STATE.cltab === t[0] ? ' active' : '') + '" '
        + 'onclick="msSetClTab(\'' + t[0] + '\')">' + t[1] + '</button>';
    }).join('');
  }
  var tb = document.querySelector('#msClTable tbody');
  if (!tb) return;
  if (!cs) { tb.innerHTML = '<tr><td colspan="7" class="ms-empty">داده‌ای نیست</td></tr>'; return; }
  var row = function (nm, o, color) {
    return '<tr><td style="color:' + color + '">' + nm + '</td>'
      + '<td class="num">' + msNum(o.buy_count) + '</td>'
      + '<td class="num">' + msNum(o.buy_b_toman, 0) + '</td>'
      + '<td class="num"><b>' + (o.buy_pct === null ? '—' : msNum(o.buy_pct, 1) + '٪') + '</b></td>'
      + '<td class="num"><b>' + (o.sell_pct === null ? '—' : msNum(o.sell_pct, 1) + '٪') + '</b></td>'
      + '<td class="num">' + msNum(o.sell_b_toman, 0) + '</td>'
      + '<td class="num">' + msNum(o.sell_count) + '</td></tr>';
  };
  tb.innerHTML = row('حقیقی', cs.retail || {}, 'var(--accent-green)')
    + row('حقوقی', cs.institutional || {}, 'var(--accent-blue)')
    + '<tr><td colspan="7" class="ms-hint">قدرت خرید حقیقی '
    + (cs.power === null ? '—' : '<span class="' + (cs.power >= 1 ? 'ms-pos' : 'ms-neg') + '">'
       + msNum(cs.power, 2) + '</span>')
    + ' · ورود پول ' + msSigned(cs.money_flow_b_toman, 1) + ' میلیارد تومان · '
    + msNum(cs.symbols) + ' نماد</td></tr>';
}

function msSetClTab(t) {
  MS_STATE.cltab = t;
  fetch('/api/mstat/clientsplit?tab=' + encodeURIComponent(t), { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(msRenderClient).catch(function () {});
}

/* ---------- گام ۵.۳ + v9.8.0: رتبه‌بندی صنایع پیشرو (کلیک ⇒ فیلتر جدول پایین) ---------- */
function msRenderIndustries(ind) {
  var host = msEl('msInd');
  if (!host) return;
  var rows = (ind && ind.rows) || [];
  var rankTb = document.querySelector('#msIndRank tbody');
  /* --- کارت لیدر روز --- */
  var lead = msEl('msIndLeader');
  if (lead) {
    var lrow = null, i;
    for (i = 0; i < rows.length; i++) if (rows[i].leader) { lrow = rows[i]; break; }
    if (lrow) {
      lead.className = 'ms-leader';
      lead.innerHTML = '<span class="crown">👑</span><div><b>صنعت لیدر روز: '
        + msEsc(lrow.industry) + '</b><div class="ms-watch-sub">ارزش '
        + msNum(lrow.value_b_toman, 0) + ' م.تومان · ورود پول '
        + msSigned(lrow.flow_b_toman, 1) + ' م.تومان · مثبت '
        + msNum(lrow.positive) + '/' + msNum(lrow.negative) + ' منفی</div></div>';
    } else {
      lead.className = 'ms-leader hidden';
      lead.innerHTML = '';
    }
  }
  /* --- جدول رتبه‌بندی: ۸ صنعتِ پیشرو بر اساس ارزش + ورود پول --- */
  if (rankTb) {
    if (!rows.length) {
      rankTb.innerHTML = '<tr><td colspan="5" class="ms-empty">داده‌ای نیست</td></tr>';
    } else {
      rankTb.innerHTML = rows.slice(0, 8).map(function (r, idx) {
        var on = MS_STATE.industry === r.industry;
        var crown = r.leader ? ' <span class="ms-crown" title="صنعت لیدر روز">👑</span>' : '';
        return '<tr class="' + (r.leader ? 'ms-ind-lead' : (idx < 3 ? 'ms-ind-top' : '')) + '">'
          + '<td><span class="ms-rank-badge">' + msNum(idx + 1) + '</span></td>'
          + '<td title="' + msEsc(r.industry) + '"><a href="#" class="ms-ind-link' + (on ? ' active' : '')
          + '" onclick="msSetIndustry(\'' + msEsc(r.industry).replace(/'/g, '') + '\');return false;">'
          + msEsc(r.industry) + '</a>' + crown + '</td>'
          + '<td class="num">' + msNum(r.value_b_toman, 0) + '</td>'
          + '<td class="num">' + msSigned(r.flow_b_toman, 1) + '</td>'
          + '<td class="num"><span class="ms-pos">' + msNum(r.positive) + '</span>/'
          + '<span class="ms-neg">' + msNum(r.negative) + '</span></td></tr>';
      }).join('');
    }
  }
  if (!rows.length) { host.innerHTML = '<div class="ms-empty">داده‌ای نیست</div>'; return; }
  host.innerHTML = rows.map(function (r) {
    var on = MS_STATE.industry === r.industry;
    return '<div class="ms-ind' + (on ? ' active' : '') + '" '
      + 'onclick="msSetIndustry(\'' + msEsc(r.industry).replace(/'/g, '') + '\')" '
      + 'title="' + msEsc(r.industry) + '\nارزش ' + msNum(r.value_b_toman, 0)
      + ' میلیارد تومان · ورود پول ' + msNum(r.flow_b_toman, 1) + '\nمثبت ' + msNum(r.positive)
      + ' / منفی ' + msNum(r.negative) + ' از ' + msNum(r.symbols) + '">'
      + '<span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap;max-width:150px">'
      + msEsc(r.industry) + '</span>'
      + '<span class="num"><span class="ms-pos">' + msNum(r.positive) + '</span>/'
      + '<span class="ms-neg">' + msNum(r.negative) + '</span></span></div>';
  }).join('');
}
function msSetIndustry(name) {
  MS_STATE.industry = (MS_STATE.industry === name) ? '' : name;
  var b = msEl('msIndClear');
  if (b) {
    b.style.display = MS_STATE.industry ? '' : 'none';
    b.textContent = '✕ حذف فیلتر: ' + MS_STATE.industry;
  }
  msReloadMainwatch();
  if (MS_STATE.data) msRenderIndustries(MS_STATE.data.industries);
}
function msClearIndustry() { msSetIndustry(MS_STATE.industry); }

/* ---------- گام ۴: سوییچ مجموع / لحظه‌ای ---------- */
function msSetMode(m) {
  MS_STATE.mode = m;
  var a = msEl('msModeCum'), b = msEl('msModeInst');
  if (a) a.classList.toggle('active', m === 'cum');
  if (b) b.classList.toggle('active', m === 'inst');
  if (!MS_STATE.data) return;
  fetch('/api/mstat/timeline?mode=' + m, { cache: 'no-store' })
    .then(function (r) { return r.json(); })
    .then(function (tl) { MS_STATE.data.timeline = tl; msDrawTimelines(tl); })
    .catch(function () {});
}

/* ---------- گام ۵.۲: تابلوی نمادها ---------- */
var MS_COLS = [
  ['_basket', '🛒', '', 'افزودن/حذف از واچ‌لیست'],
  ['symbol', 'نماد', '', ''],
  ['vol_b_shares', 'حجم', 'vol', 'میلیارد سهم'],
  ['val_b_toman', 'ارزش', 'val', 'میلیارد تومان'],
  ['p_last', 'قیمت آخرین', 'pl', ''],
  ['pct_last', '٪ آخرین', 'pct_last', 'بازدهی آخرین معامله نسبت به دیروز'],
  ['p_closing', 'قیمت پایانی', 'pc', ''],
  ['pct_close', '٪ پایانی', 'pct', 'بازدهی قیمت پایانی نسبت به دیروز'],
  ['pc_buy', 'سرانه خرید', 'pcb', 'میلیون تومان به ازای هر خریدار حقیقی'],
  ['pc_sell', 'سرانه فروش', 'pcs', 'میلیون تومان به ازای هر فروشنده حقیقی'],
  ['power', 'قدرت خرید', 'pow', 'سرانه خرید ÷ سرانه فروش'],
  ['flow_b_toman', 'ورود پول', 'flow', 'میلیارد تومان؛ مثبت = ورود حقیقی'],
  ['dem_vol', 'حجم تقاضا', 'dv', 'حجم خط اول تقاضا (سهم)'],
  ['dem_px', 'قیمت تقاضا', 'dp', 'قیمت خط اول تقاضا (ریال)'],
  ['clock_pct', 'اختلاف آخرین/پایانی', 'clock',
   'الگوی ساعت: (آخرین − پایانی) ÷ پایانی — برای شکار، نزولی مرتب کن'],
];

function msGridHead() {
  var tr = msEl('msGridHead');
  if (!tr) return;
  tr.innerHTML = MS_COLS.map(function (c) {
    if (c[0] === '_basket') return '<th title="' + c[3] + '">' + c[1] + '</th>';
    var on = MS_STATE.sort === c[2];
    return '<th class="sortable' + (on ? ' sorted' : '') + '" title="' + (c[3] || c[1])
      + '" onclick="msSortBy(\'' + c[2] + '\')">' + c[1]
      + (on ? (MS_STATE.desc ? ' ↓' : ' ↑') : '') + '</th>';
  }).join('');
}
function msSortBy(k) {
  if (MS_STATE.sort === k) MS_STATE.desc = !MS_STATE.desc;
  else { MS_STATE.sort = k; MS_STATE.desc = (k === 'clock' || k === 'val' || k === 'flow'); }
  msReloadMainwatch();
}
function msReloadMainwatch() {
  var q = '/api/mstat/mainwatch?group=' + encodeURIComponent(MS_STATE.group)
    + '&industry=' + encodeURIComponent(MS_STATE.industry)
    + '&sort=' + encodeURIComponent(MS_STATE.sort)
    + '&desc=' + (MS_STATE.desc ? 'true' : 'false') + '&limit=120';
  fetch(q, { cache: 'no-store' }).then(function (r) { return r.json(); })
    .then(function (j) {
      if (j && j.status === 'ok') msRenderGrid(j);
      else msSet('msGridMeta', '⚠️ ' + msEsc(j && j.message || 'خطا'));
    }).catch(function () {});
}

function msRenderGrid(mw) {
  msGridHead();
  var tb = document.querySelector('#msGrid tbody');
  if (!tb) return;
  var rows = (mw && mw.rows) || [];
  msSet('msGridMeta', mw
    ? (msNum(mw.total) + ' نماد · نمایش ' + msNum(rows.length)
       + ' · نامزد الگوی ساعت ' + msNum(mw.clock_hits)) : '');
  if (!rows.length) {
    tb.innerHTML = '<tr><td colspan="15" class="ms-empty">هیچ نمادی با این فیلتر نیست</td></tr>';
    return;
  }
  var inW = MS_STATE.watch || {};
  tb.innerHTML = rows.map(function (r) {
    var on = !!inW[r.symbol];
    var qmark = { b: ' — 🟩 در صف خرید', s: ' — 🟥 در صف فروش' }[r.queue] || '';
    var basket = '<button class="ms-btn-basket' + (on ? ' in' : '') + '" '
      + 'onclick="msToggleWatch(\'' + msEsc(r.symbol) + '\', this)" '
      + 'title="' + (on ? 'حذف از واچ‌لیست' : 'افزودن به واچ‌لیست') + '">'
      + (on ? '★' : '🛒') + '</button>';
    var clk = (r.clock_pct === null || r.clock_pct === undefined)
      ? '<span class="ms-neu">—</span>'
      : '<span class="' + (r.clock_ok ? 'ms-pos' : 'ms-neu') + '"'
        + (r.clock_ok ? ' title="الگوی ساعت: آخرین ' + msNum(r.clock_pct, 2)
                       + '٪ بالای پایانی (قابل‌اتکا)"'
                       : ' title="زیر آستانهٔ تعداد معامله یا قیمت — قابل‌اتکا نیست"')
        + '>' + msNum(r.clock_pct, 2) + '٪</span>';
    return '<tr>'
      + '<td class="ms-td-basket">' + basket + '</td>'
      + '<td><a href="#" onclick="gotoChart(\'' + msEsc(r.symbol) + '\',\'' + msEsc(r.name)
      + '\');return false;" title="' + msEsc(r.name) + qmark + '"><b>'
      + msEsc(r.symbol) + '</b></a></td>'
      + '<td class="num">' + msNum(r.vol_b_shares, 3) + '</td>'
      + '<td class="num">' + msNum(r.val_b_toman, 0) + '</td>'
      + '<td class="num">' + (r.p_last === null ? '<span class="ms-neu">—</span>'
                                                : msNum(r.p_last, 0)) + '</td>'
      + '<td class="num">' + msPct(r.pct_last) + '</td>'
      + '<td class="num">' + msNum(r.p_closing, 0) + '</td>'
      + '<td class="num">' + msPct(r.pct_close) + '</td>'
      + '<td class="num">' + msNum(r.pc_buy, 1) + '</td>'
      + '<td class="num">' + msNum(r.pc_sell, 1) + '</td>'
      + '<td class="num">' + (r.power === null ? '<span class="ms-neu">—</span>'
          : '<span class="' + (r.power >= 1 ? 'ms-pos' : 'ms-neg') + '">'
            + msNum(r.power, 2) + '</span>') + '</td>'
      + '<td class="num">' + msSigned(r.flow_b_toman, 1) + '</td>'
      + '<td class="num">' + (r.dem_vol ? msNum(r.dem_vol, 0) : '<span class="ms-neu">—</span>') + '</td>'
      + '<td class="num">' + (r.dem_px ? msNum(r.dem_px, 0) : '<span class="ms-neu">—</span>') + '</td>'
      + '<td class="num">' + clk + '</td></tr>';
  }).join('');
}

/* ---------- دکمهٔ سبد ⇄ /api/watchlist ---------- */
async function msLoadWatchlist() {
  MS_STATE.watch = MS_STATE.watch || {};
  try {
    var j = await fetch('/api/watchlist', { cache: 'no-store' })
      .then(function (r) { return r.json(); });
    var list = (j && (j.data || j.rows || j.watchlist || j.items)) || [];
    var map = {};
    list.forEach(function (w) { if (w && w.symbol) map[String(w.symbol).trim()] = 1; });
    MS_STATE.watch = map;
    if (MS_STATE.data && MS_STATE.data.mainwatch) msRenderGrid(MS_STATE.data.mainwatch);
  } catch (e) { MS_STATE.watch = {}; }
}

async function msToggleWatch(sym, btn) {
  var have = MS_STATE.watch || (MS_STATE.watch = {});
  var adding = !have[sym];
  try {
    var r = await fetch(adding ? '/api/watchlist' : '/api/watchlist/' + encodeURIComponent(sym),
                        adding ? { method: 'POST', headers: { 'Content-Type': 'application/json' },
                                   body: JSON.stringify({ symbol: sym }), cache: 'no-store' }
                               : { method: 'DELETE', cache: 'no-store' });
    var j = await r.json();
    if (j.status !== 'success') throw new Error(j.message || 'failed');
    if (adding) have[sym] = 1; else delete have[sym];
    if (btn) {
      btn.classList.toggle('in', !!have[sym]);
      btn.textContent = have[sym] ? '★' : '🛒';
      btn.title = have[sym] ? 'حذف از واچ‌لیست' : 'افزودن به واچ‌لیست';
    }
    var st = msEl('msStatus');
    if (st) st.textContent = (have[sym] ? '★ ' : '🛒 ') + sym
      + (have[sym] ? ' به واچ‌لیست اضافه شد' : ' از واچ‌لیست حذف شد');
  } catch (e) {
    console.warn('[mstat watch]', e);
    var st2 = msEl('msStatus');
    if (st2) st2.textContent = '⚠️ واچ‌لیست به‌روز نشد';
  }
}

/* ---------- کنترل‌های تب ---------- */
function msSetGroup(g) { MS_STATE.group = g; msRefresh(true); }
function msSetPoll(v) {
  if (MS_TIMER) { clearInterval(MS_TIMER); MS_TIMER = null; }
  var sec = parseInt(v || '0', 10);
  if (typeof stGet === 'function') { try { sec = parseInt(v || stGet('msPollSec', '60'), 10); } catch (e) {} }
  if (sec > 0) MS_TIMER = setInterval(function () { msRefresh(false); }, sec * 1000);
}
