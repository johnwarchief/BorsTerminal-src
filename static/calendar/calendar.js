/* =====================================================================
   BorsTerminal — Calendar Tab UI (v1.0)
   ---------------------------------------------------------------------
   تقویم جلالی ماهانه/هفتگی رویدادهای بازار سرمایه
   - مستقل از هسته: فقط به #calView مانت میشود
   - وابستگی: jalaali-js (از قبل لودشده) + calendarService.js
   ===================================================================== */
(function () {
  'use strict';

  var J = window.Jalaali;
  var FA_MONTHS = ['فروردین', 'اردیبهشت', 'خرداد', 'تیر', 'مرداد', 'شهریور', 'مهر', 'آبان', 'آذر', 'دی', 'بهمن', 'اسفند'];
  var FA_DAYS = ['شنبه', 'یکشنبه', 'دوشنبه', 'سه‌شنبه', 'چهارشنبه', 'پنجشنبه', 'جمعه'];

  var state = {
    view: 'month',            // month | week | day
    jy: 0, jm: 0,             // ماه جاری تقویم (جلالی)
    weekStart: null,          // Date — شنبه هفته جاری در نمای هفتگی
    day: null,                // Date — روز انتخابی در نمای لیستی
    filters: { cat: 'all', symbol: '', industry: 'all', q: '' },
    selected: null            // رویداد انتخاب‌شده برای پاپ‌آور
  };

  function el(id) { return document.getElementById(id); }
  function pad(x) { return String(x).padStart(2, '0'); }
  function jOf(date) { return J.toJalaali(date.getFullYear(), date.getMonth() + 1, date.getDate()); }
  function gOf(jy, jm, jd) { var g = J.toGregorian(jy, jm, jd); return new Date(g.gy, g.gm - 1, g.gd); }
  function faNum(n) { return String(n).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[d]; }); }

  /* ---------- رندر کلی ---------- */
  function render() {
    var root = el('calView');
    if (!root || root.dataset.built) { updateAll(); return; }
    root.dataset.built = '1';
    root.innerHTML =

      '<div class="cal-shell">' +
      '  <div class="cal-toolbar">' +
      '    <div class="cal-nav">' +
      '      <button class="cal-btn" id="calPrev" title="قبلی">›</button>' +
      '      <button class="cal-btn cal-today" id="calToday">امروز</button>' +
      '      <button class="cal-btn" id="calNext" title="بعدی">‹</button>' +
      '      <h2 class="cal-title" id="calTitle"></h2>' +
      '    </div>' +
      '    <div class="cal-modes">' +
      '      <button class="cal-btn cal-mode" data-v="month">ماه</button>' +
      '      <button class="cal-btn cal-mode" data-v="week">هفته</button>' +
      '      <button class="cal-btn cal-mode" data-v="day">نمایش لیستی روز</button>' +
      '    </div>' +
      '    <div class="cal-filters">' +
      '      <select id="calCat" class="cal-select"><option value="all">همه رویدادها</option></select>' +
      '      <input id="calSym" class="cal-input" placeholder="نماد..." style="width:90px">' +
      '      <select id="calInd" class="cal-select"><option value="all">همه صنعت‌ها</option></select>' +
      '      <input id="calQ" class="cal-input" placeholder="جستجو در رویدادها..." style="width:150px">' +
      '    </div>' +
      '  </div>' +
      '  <div class="cal-legend" id="calLegend"></div>' +
      '  <div class="cal-body" id="calBody"></div>' +
      '  <div class="cal-detail" id="calDetail" style="display:none"></div>' +
      '</div>';

    el('calPrev').onclick = function () { nav(-1); };
    el('calNext').onclick = function () { nav(1); };
    el('calToday').onclick = function () { var j = jOf(new Date()); state.jy = j.jy; state.jm = j.jm; state.weekStart = satOf(new Date()); updateAll(); };
    root.querySelectorAll('.cal-mode').forEach(function (b) {
      b.onclick = function () { state.view = b.dataset.v; if (state.view === 'week' && !state.weekStart) state.weekStart = satOf(new Date()); updateAll(); };
    });
    el('calCat').onchange = function () { state.filters.cat = this.value; updateAll(); };
    el('calInd').onchange = function () { state.filters.industry = this.value; updateAll(); };
    el('calSym').oninput = debounce(function () { state.filters.symbol = el('calSym').value.trim(); updateAll(); }, 250);
    el('calQ').oninput = debounce(function () { state.filters.q = el('calQ').value.trim(); updateAll(); }, 250);

    var j = jOf(new Date());
    state.jy = j.jy; state.jm = j.jm; state.weekStart = satOf(new Date());
    var dd = new Date(); dd.setHours(0, 0, 0, 0); state.day = dd;
    document.addEventListener('mousedown', closeDetail);
  }

  function debounce(fn, ms) { var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); }; }
  function satOf(d) { var x = new Date(d); x.setHours(0, 0, 0, 0); x.setDate(x.getDate() - ((x.getDay() + 1) % 7)); return x; }

  function nav(dir) {
    if (state.view === 'month') {
      var m = state.jm + dir;
      if (m < 1) { state.jm = 12; state.jy--; } else if (m > 12) { state.jm = 1; state.jy++; } else state.jm = m;
    } else if (state.view === 'week') {
      var w = new Date(state.weekStart); w.setDate(w.getDate() + dir * 7); state.weekStart = w;
    } else {
      var dd = new Date(state.day); dd.setDate(dd.getDate() + dir); state.day = dd;
    }
    updateAll();
  }

  function updateAll() {
    renderLegend();
    if (state.view === 'month') el('calTitle').textContent = FA_MONTHS[state.jm - 1] + ' ' + faNum(state.jy);
    else if (state.view === 'week') el('calTitle').textContent = 'هفته ' + faNum(jOf(state.weekStart).jd) + ' ' + FA_MONTHS[jOf(state.weekStart).jm - 1] + ' تا ' + faNum(jOf(new Date(state.weekStart.getTime() + 6 * 864e5)).jd) + ' ' + FA_MONTHS[jOf(new Date(state.weekStart.getTime() + 6 * 864e5)).jm - 1];
    else { var dj = jOf(state.day); el('calTitle').textContent = FA_DAYS[(state.day.getDay() + 1) % 7] + ' ' + faNum(dj.jd) + ' ' + FA_MONTHS[dj.jm - 1] + ' ' + faNum(dj.jy); }
    document.querySelectorAll('#calView .cal-mode').forEach(function (b) { b.classList.toggle('on', b.dataset.v === state.view); });
    renderBody();
  }

  function renderLegend() {
    var lg = el('calLegend');
    if (!lg) return;
    lg.innerHTML = window.CalService.CAT_ORDER.map(function (k) {
      var c = window.CalService.CATS[k];
      return '<span class="cal-leg"><i class="cal-dot cal-cat-' + k + '"></i>' + c.fa + '</span>';
    }).join('') + '<span class="cal-count" id="calCount"></span>';
  }

  function renderIndustryOptions() {
    var sel = el('calInd');
    if (!sel || sel.options.length > 1) return;
    var list = window.CalService.industries();
    if (!list.length) return;
    list.forEach(function (i) { var o = document.createElement('option'); o.value = i; o.textContent = i; sel.appendChild(o); });
  }

  /* ---------- بدنه: ماه/هفته ---------- */
  function renderBody() {
    var body = el('calBody');
    if (!body) return;
    var events = window.CalService.query(state.filters);
    var head = '<div class="cal-grid cal-head-row">' + FA_DAYS.map(function (d) { return '<div class="cal-hd">' + d + '</div>'; }).join('') + '</div>';
    if (state.view === 'day') {
      body.innerHTML = '<div class="cal-daylist">' + dayList(events) + '</div>';
      var cnt2 = el('calCount');
      if (cnt2) cnt2.textContent = faNum(events.filter(function (e) { return e.date === dayKey(state.day); }).length) + ' رویداد در این روز';
      bindDayClicks();
      return;
    }
    var cells = state.view === 'month' ? monthCells(events) : weekCells(events);
    body.innerHTML = head + '<div class="cal-grid ' + (state.view === 'month' ? 'cal-month' : 'cal-week') + '">' + cells.html + '</div>';
    var cnt = el('calCount');
    if (cnt) cnt.textContent = faNum(cells.count) + ' رویداد در ' + (state.view === 'month' ? 'این ماه' : 'این هفته');
    bindDayClicks();
  }

  function dayKey(date) { return date.getFullYear() + '-' + pad(date.getMonth() + 1) + '-' + pad(date.getDate()); }

  function monthCells(events) {
    var byDay = {};
    var from = gOf(state.jy, state.jm, 1);
    var dim = J.jalaaliMonthLength(state.jy, state.jm);
    var to = gOf(state.jy, state.jm, dim); to.setHours(23, 59, 59);
    // ماه‌های مجاور برای خانه‌های خالی
    events.forEach(function (e) { (byDay[e.date] = byDay[e.date] || []).push(e); });
    var offset = (from.getDay() + 1) % 7; // شنبه=0
    var html = '';
    var disp = 0;
    // خانه‌های ماه قبل (مات) — v1.4
    var pjy = state.jm === 1 ? state.jy - 1 : state.jy;
    var pjm = state.jm === 1 ? 12 : state.jm - 1;
    var dimPrev = J.jalaaliMonthLength(pjy, pjm);
    for (var i = 0; i < offset; i++) {
      var jdPrev = dimPrev - offset + 1 + i;
      var gPrev = gOf(pjy, pjm, jdPrev);
      html += '<div class="cal-cell cal-out" data-date="' + dayKey(gPrev) + '"><div class="cal-daynum">' + faNum(jdPrev) + '</div></div>';
    }
    var todayJ = jOf(new Date());
    for (var d = 1; d <= dim; d++) {
      var g = gOf(state.jy, state.jm, d);
      var key = dayKey(g);
      var evs = byDay[key] || [];
      disp += evs.length;
      var isToday = (todayJ.jy === state.jy && todayJ.jm === state.jm && todayJ.jd === d);
      var isFri = g.getDay() === 5;
      html += '<div class="cal-cell' + (isToday ? ' cal-today-cell' : '') + (isFri ? ' cal-fri' : '') + '" data-date="' + key + '">' +
        '<div class="cal-daynum">' + faNum(d) + '</div>' +
        /* v9.6: سقف ۴ به ۱۲ رسید تا اسکرول داخلی سلول معنا پیدا کند؛
           اگر باز هم بیشتر بود، چیپ «+N رویداد» مودال آن روز را باز می‌کند. */
        '<div class="cal-evs">' + evs.slice(0, 12).map(evChip).join('') +
        (evs.length > 12 ? '<span class="cal-more">+' + faNum(evs.length - 12) + ' رویداد</span>' : '') + '</div></div>';
    }
    // تکمیل ردیف آخر با روزهای ماه بعد (مات) — v1.4
    var total = offset + dim;
    var trail = (Math.ceil(total / 7) * 7) - total;
    var njy = state.jm === 12 ? state.jy + 1 : state.jy;
    var njm = state.jm === 12 ? 1 : state.jm + 1;
    for (var t = 1; t <= trail; t++) {
      var gNext = gOf(njy, njm, t);
      html += '<div class="cal-cell cal-out" data-date="' + dayKey(gNext) + '"><div class="cal-daynum">' + faNum(t) + '</div></div>';
    }
    return { html: html, count: disp };
  }

  function weekCells(events) {
    var byDay = {};
    events.forEach(function (e) { (byDay[e.date] = byDay[e.date] || []).push(e); });
    var html = '';
    var disp = 0;
    var todayKey = dayKey(new Date());
    for (var i = 0; i < 7; i++) {
      var g = new Date(state.weekStart.getTime() + i * 864e5);
      var key = dayKey(g);
      var j = jOf(g);
      var evs = (byDay[key] || []).sort(function (a, b) { return a.ms - b.ms; });
      disp += evs.length;
      html += '<div class="cal-cell cal-weekcell' + (key === todayKey ? ' cal-today-cell' : '') + '" data-date="' + key + '">' +
        '<div class="cal-daynum">' + faNum(j.jd) + ' ' + FA_MONTHS[j.jm - 1] + '</div>' +
        '<div class="cal-evs">' + evs.map(evChipFull).join('') + '</div></div>';
    }
    return { html: html, count: disp };
  }

  function evChip(e) {
    return '<span class="cal-ev cal-cat-' + e.cat + '" data-ev="' + e.id + '" title="' + esc(e.symbol + ' — ' + e.title) + '">' +
      (e.time ? '<i class="cal-ev-t">' + faNum(e.time) + '</i>' : '') +
      '<b>' + esc(e.symbol || '•') + '</b> ' + esc(short(e.title, 24)) + '</span>';
  }
  function evChipFull(e) {
    return '<div class="cal-ev cal-evf cal-cat-' + e.cat + '" data-ev="' + e.id + '">' +
      '<span class="cal-ev-time">' + faNum(e.time) + '</span><b>' + esc(e.symbol || '—') + '</b><span>' + esc(e.title) + '</span></div>';
  }
  function short(t, n) { t = String(t); return t.length > n ? t.slice(0, n) + '…' : t; }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }

  function bindDayClicks() {
    document.querySelectorAll('#calBody .cal-ev').forEach(function (chip) {
      chip.onclick = function (ev) {
        ev.stopPropagation();
        var id = chip.dataset.ev;
        var e = window.CalService.events.find(function (x) { return x.id === id; });
        if (e) showDetail(e, chip);
      };
    });
    // v1.4 — کلیک «+X رویداد» → مودال لیست کامل همان روز
    document.querySelectorAll('#calBody .cal-more').forEach(function (m) {
      m.onclick = function (ev) {
        ev.stopPropagation();
        openDayModal(m.closest('.cal-cell').dataset.date);
      };
    });
    // v1.4 — کلیک روزهای ماه قبل/بعد → پرش به آن ماه
    document.querySelectorAll('#calBody .cal-out').forEach(function (c) {
      c.onclick = function () {
        var j = jOf(new Date(c.dataset.date + 'T00:00:00'));
        state.jy = j.jy; state.jm = j.jm;
        updateAll();
      };
    });
  }

  /* ---------- v1.4 — نمای لیستی روز ---------- */
  function dayList(events) {
    var key = dayKey(state.day);
    var evs = events.filter(function (e) { return e.date === key; }).sort(function (a, b) { return (a.time || '').localeCompare(b.time || ''); });
    if (!evs.length) return '<div class="cal-empty-day">رویدادی برای این روز ثبت نشده است</div>';
    return evs.map(function (e) {
      var c = window.CalService.CATS[e.cat];
      return '<div class="cal-ls cal-cat-' + e.cat + '" data-ev="' + e.id + '">' +
        '<div class="cal-ls-time">' + faNum(e.time || '--:--') + '</div>' +
        '<div class="cal-ls-body">' +
        '<div class="cal-ls-top"><b>' + esc(e.symbol || '—') + '</b><span class="cal-ls-cat">' + esc(c.fa) + '</span></div>' +
        '<div class="cal-ls-title">' + esc(e.title) + '</div>' +
        (e.link ? '<a class="cal-ls-link" href="' + esc(e.link) + '" target="_blank" rel="noopener">مشاهده اطلاعیه در کدال ↗</a>' : '') +
        '</div></div>';
    }).join('');
  }

  /* ---------- v1.4 — مودال همه رویدادهای یک روز ---------- */
  function openDayModal(dateKey) {
    var old = document.getElementById('calDayModal');
    if (old) old.remove();
    var evs = window.CalService.events.filter(function (e) { return e.date === dateKey; })
      .sort(function (a, b) { return (a.time || '').localeCompare(b.time || ''); });
    var d = new Date(dateKey + 'T00:00:00');
    var j = jOf(d);
    var modal = document.createElement('div');
    modal.id = 'calDayModal';
    modal.innerHTML = '<div class="cal-dm-back"></div><div class="cal-dm-card">' +
      '<div class="cal-dm-head"><b>' + FA_DAYS[(d.getDay() + 1) % 7] + ' ' + faNum(j.jd) + ' ' + FA_MONTHS[j.jm - 1] + ' ' + faNum(j.jy) +
      ' — ' + faNum(evs.length) + ' رویداد</b><button class="cal-dm-x">✕</button></div>' +
      '<div class="cal-dm-list">' +
      (evs.length ? evs.map(function (e) {
        var c = window.CalService.CATS[e.cat];
        return '<div class="cal-ls cal-cat-' + e.cat + '" data-ev="' + e.id + '">' +
          '<div class="cal-ls-time">' + faNum(e.time || '--:--') + '</div>' +
          '<div class="cal-ls-body"><div class="cal-ls-top"><b>' + esc(e.symbol || '—') + '</b>' +
          '<span class="cal-ls-cat">' + esc(c.fa) + '</span></div>' +
          '<div class="cal-ls-title">' + esc(e.title) + '</div>' +
          (e.link ? '<a class="cal-ls-link" href="' + esc(e.link) + '" target="_blank" rel="noopener">اطلاعیه در کدال ↗</a>' : '') +
          '</div></div>';
      }).join('') : '<div class="cal-empty-day">بدون رویداد</div>') +
      '</div></div>';
    document.body.appendChild(modal);
    modal.querySelector('.cal-dm-x').onclick = function () { modal.remove(); };
    modal.querySelector('.cal-dm-back').onclick = function () { modal.remove(); };
    modal.querySelectorAll('.cal-ls').forEach(function (row) {
      row.onclick = function (ev) {
        if (ev.target.tagName === 'A') return;
        var e = window.CalService.events.find(function (x) { return x.id === row.dataset.ev; });
        if (e) { modal.remove(); var chip = document.querySelector('#calBody .cal-ev[data-ev="' + e.id + '"]') || document.body; showDetail(e, chip); }
      };
    });
  }
  function closeDetail(ev) {
    var d = el('calDetail');
    if (d && !d.contains(ev.target) && !ev.target.closest('.cal-ev')) d.style.display = 'none';
  }

  function showDetail(e, anchor) {
    var d = el('calDetail');
    var dt = new Date(e.ms);
    var j = jOf(dt);
    d.innerHTML = '<div class="cal-detail-card cal-cat-' + e.cat + '">' +
      '<div class="cal-detail-head"><span class="cal-cat-badge">' + esc(window.CalService.CATS[e.cat].fa) + '</span>' +
      '<button class="cal-detail-x">✕</button></div>' +
      '<h3>' + esc(e.title) + '</h3>' +
      '<div class="cal-detail-meta">' +
      '<span>📅 ' + faNum(j.jd) + ' ' + FA_MONTHS[j.jm - 1] + ' ' + faNum(j.jy) + (e.time ? ' — ⏰ ' + faNum(e.time) : '') + '</span>' +
      (e.symbol ? '<span>🏢 نماد: <b>' + esc(e.symbol) + '</b></span>' : '') +
      (window.CalService.industries()[e.symbol] ? '<span>🏭 صنعت: ' + esc(window.CalService.industries()[e.symbol]) + '</span>' : '') +
      '</div>' +
      (e.desc ? '<pre class="cal-detail-desc">' + esc(e.desc) + '</pre>' : '') +
      /* v9.7.6 — پل به نمودار تکنیکال: نماد را لود کن و همان روزِ رویداد را وسطِ
         چارت بیاور (rvOpenSymbolAt در tech_rtv.js — مارکر 📅 همان روز flash می‌کند). */
      (e.symbol ? '<button class="cal-detail-chart" type="button">📈 نمایش روی نمودار</button>' : '') +
      '</div>';
    d.style.display = 'block';
    var ar = anchor.getBoundingClientRect(), rr = d.getBoundingClientRect();
    d.querySelector('.cal-detail-x').onclick = function () { d.style.display = 'none'; };
    var ob = d.querySelector('.cal-detail-chart');
    if (ob) ob.onclick = function (ev) {
      if (ev && ev.stopPropagation) ev.stopPropagation();
      var iso = e.date || new Date(e.ms).toISOString().slice(0, 10);
      d.style.display = 'none';
      if (typeof window.rvOpenSymbolAt === 'function') window.rvOpenSymbolAt(e.symbol, iso);
      else if (typeof window.gotoChart === 'function') window.gotoChart(e.symbol);
    };
    var left = Math.min(Math.max(8, ar.left), window.innerWidth - rr.width - 8);
    var top = ar.bottom + 6;
    if (top + rr.height > window.innerHeight - 8) top = Math.max(8, ar.top - rr.height - 6);
    d.style.left = left + 'px'; d.style.top = top + 'px'; d.style.right = 'auto';
  }

  /* ---------- init عمومی (بعد از لود دیتا) ---------- */
  function initOptions() {
    var sel = el('calCat');
    if (sel && sel.options.length <= 1) {
      window.CalService.CAT_ORDER.forEach(function (k) {
        var o = document.createElement('option'); o.value = k; o.textContent = window.CalService.CATS[k].fa; sel.appendChild(o);
      });
    }
    renderIndustryOptions();
  }

  window.calTabInit = function () {
    render();
    return window.CalService.load().then(function () {
      initOptions();
      updateAll();
    });

/* ---------- v9.7.7 — تکمیل IPO Watch و فیلتر «فقط واچ‌لیست من» ---------- */
function renderIpoWatch() {
    var ipoEvents = window.CalService.events.filter(function(e) { return e.cat === 'ipo'; });
    var container = document.getElementById('calIpoWatch');
    if (!container) {
        container = document.createElement('div');
        container.id = 'calIpoWatch';
        container.style.cssText = 'margin-top:12px;padding:8px;background:var(--bg-card);border-radius:6px;font-size:0.75rem;';
        var body = document.getElementById('calBody');
        if (body) body.appendChild(container);
    }
    if (ipoEvents.length === 0) {
        container.innerHTML = '<span style="color:var(--text-muted);">هیچ عرضه اولیه‌ای در دسترس نیست.</span>';
        return;
    }
    var html = '<strong>📌 IPO Watch</strong><ul style="list-style:none;padding:4px 0;margin:0;">';
    ipoEvents.slice(0, 10).forEach(function(e) {
        html += '<li style="padding:2px 0;border-bottom:1px solid var(--border-color);">' +
                e.symbol + ' — ' + e.title +
                '</li>';
    });
    html += '</ul>';
    container.innerHTML = html;
}

/* فیلتر «فقط واچ‌لیست من» */
var filterWatchlistOnly = false;
function toggleWatchlistFilter() {
    filterWatchlistOnly = !filterWatchlistOnly;
    updateAll();
}

/* پچ کردن تابع updateAll برای اعمال فیلتر */
var origUpdateAll = window.updateAll;
window.updateAll = function() {
    if (origUpdateAll) origUpdateAll();
    renderIpoWatch();
    // اگر فیلتر واچ‌لیست فعال است، رویدادها را فیلتر کن (در render اصلی پیاده‌سازی شود)
};
  };

  /* ورود به تب: سوییچ ویو + مقداردهی تنبل (بدون دستکاری switchView هسته) */
  window.calTabOpen = function (btn) {
    window.switchView('cal', btn);
    if (window.calTabInit) window.calTabInit();
  };
})();
