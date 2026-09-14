/* ══════════════════════════════════════════════════════════════════════════
   v9.0 — سازوکار تصمیم‌گیری سبد: Accept / Reject / Monitor
   منبع حقیقت: جدول selection_decisions در market.db (از راه /api/selection/*)
   وابستگی‌های اختیاری (همه با guard): rv.sym، rvToast، switchView
   ══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  var STATUS_META = {
    pending: { label: 'بررسی‌نشده', color: '#94a3b8', bg: 'rgba(148,163,184,.14)', icon: '○' },
    accept:  { label: 'تایید',      color: '#10b981', bg: 'rgba(16,185,129,.16)',  icon: '✔' },
    reject:  { label: 'رد',         color: '#f43f5e', bg: 'rgba(244,63,94,.16)',   icon: '✖' },
    monitor: { label: 'زیر نظر',    color: '#eab308', bg: 'rgba(234,179,8,.16)',   icon: '◔' }
  };
  var KIND_LABEL = { dollar: 'دلاری', rial: 'ریالی', '': 'نامشخص' };

  // دلایل فلوچارت استراتژی — کلید همان رشتهٔ ذخیره‌شده در دیتابیس است
  var REASONS = {
    reject:  ['هفتگی نزولی/خنثی', 'سقف دوقلو', 'واگرایی منفی RSI', 'دیگر…'],
    monitor: ['انتظار شکست سقف', 'انتظار پولبک', 'الگوی ساعت', 'دیگر…'],
    accept:  ['شکست سقف با حجم', 'پولبک سالم به حمایت', 'الگوی ساعت کامل‌شده']
  };
  var SL_HINTS = ['زیر MA14 نوسانی', 'کف ماژور'];

  var SEL = {
    map: {},                                  // symbol -> decision record
    rows: {},                                 // symbol -> آخرین ردیف اسکرینر (بافت FTS)
    counts: { accept: 0, reject: 0, monitor: 0, pending: 0 },
    limits: { min: 5, max: 7, weight_cap_pct: 20, equal_weight_pct: 0, sum_weight_pct: 0 },
    kindMix: { dollar: 0, rial: 0, mixed: 0 },
    loaded: false, saving: false
  };
  window.SEL = SEL;

  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function toast(msg) {
    if (typeof rvToast === 'function') { try { rvToast(msg); return; } catch (e) {} }
    console.log(msg);
  }
  function el(id) { return document.getElementById(id); }

  /* ─────────── بارگذاری از بک‌اند ─────────── */
  SEL.load = function () {
    return fetch('/api/selection/portfolio', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.status !== 'success') throw new Error((j && j.message) || 'خطا');
        SEL.map = {};
        (j.decisions || []).forEach(function (d) { if (d && d.symbol) SEL.map[d.symbol] = d; });
        SEL.counts = j.counts || SEL.counts;
        SEL.limits = j.limits || SEL.limits;
        SEL.kindMix = j.kind_mix || SEL.kindMix;
        SEL.loaded = true;
        SEL.paint();
        return j;
      })
      .catch(function (e) { console.warn('SEL.load', e); });
  };

  /* بافت FTS هر نماد (نام/صنعت/حالت قیمت/امتیاز) از جدول بنیادی قرض گرفته می‌شود */
  SEL.remember = function (rows) {
    (rows || []).forEach(function (r) {
      if (r && r.symbol) SEL.rows[String(r.symbol)] = r;
    });
  };
  SEL.ctx = function (symbol) {
    var r = SEL.rows[symbol] || SEL.map[symbol] || {};
    return {
      name: r.name || '', sector: r.sector_name || r.sector || '',
      pricing_mode: r.pricing_mode || '', score: r.score || 0, price: r.price || 0
    };
  };

  /* ─────────── غنی‌سازی بافت FTS از بک‌اند ───────────
     اگر کاربر بدون باز کردن جدول بنیادی روی چارت تصمیم بگیرد، pricing_mode و
     امتیاز در دسترس نیستند؛ با یک فراخوانی /api/fts/{symbol} گرفته می‌شوند تا
     ستون «نوع سهم (دلاری/ریالی)» و «امتیاز» در سبد خالی نماند. */
  SEL.enrich = function (symbol, c) {
    if (c.pricing_mode || c.score) return Promise.resolve(c);
    return fetch('/api/fts/' + encodeURIComponent(symbol))
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (j) {
        var d = (j && j.data) || {};
        if (d.pricing_mode || d.score) {
          c.pricing_mode = d.pricing_mode || '';
          c.score = d.score || 0;
          c.sector = d.sector || c.sector;
          SEL.rows[symbol] = { symbol: symbol, name: c.name, sector_name: c.sector,
                               pricing_mode: c.pricing_mode, score: c.score };
        }
        return c;
      })
      .catch(function () { return c; });
  };

  /* ─────────── ثبت تصمیم ─────────── */
  SEL.set = function (symbol, status, extra) {
    if (!symbol) { toast('⚠️ نمادی انتخاب نشده است'); return Promise.resolve(null); }
    if (SEL.saving) return Promise.resolve(null);
    SEL.saving = true;
    return SEL.enrich(symbol, SEL.ctx(symbol)).then(function (c) {
      var body = {
        symbol: symbol, status: status,
        name: (extra && extra.name) || c.name,
        sector: (extra && extra.sector) || c.sector,
        pricing_mode: (extra && extra.pricing_mode) || c.pricing_mode,
        score: (extra && extra.score != null) ? extra.score : c.score,
        price: (extra && extra.price != null) ? extra.price : c.price,
        reason: (extra && extra.reason) || '',
        note: (extra && extra.note) || '',
        stop_loss: (extra && extra.stop_loss) || '',
        asset_kind: (extra && extra.asset_kind) || '',
        weight_pct: (extra && extra.weight_pct != null) ? extra.weight_pct : 0
      };
      return fetch('/api/selection/decision', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.status !== 'success') throw new Error((j && j.message) || 'ناموفق');
        if (status === 'pending') delete SEL.map[symbol];
        else SEL.map[symbol] = j.decision || body;
        // شمارنده‌ها از خودِ map بازمحاسبه می‌شوند (وگرنه بج «سبد من (n/7)» کهنه می‌ماند)
        var cnt = { accept: 0, reject: 0, monitor: 0, pending: 0 };
        Object.keys(SEL.map).forEach(function (s) {
            var st = SEL.map[s] && SEL.map[s].status;
            if (cnt[st] !== undefined) cnt[st]++;
        });
        SEL.counts = cnt;
        SEL.paint();
        var m = STATUS_META[status] || STATUS_META.pending;
        toast((status === 'reject' ? '🔴 ' : status === 'accept' ? '🟢 ' : status === 'monitor' ? '🟡 ' : '○ ')
              + symbol + ' → ' + m.label);
        return j;
      })
    })
      .catch(function (e) { toast('⚠️ ذخیرهٔ تصمیم ناموفق بود: ' + e.message); })
      .then(function (x) { SEL.saving = false; return x; });
  };

  /* ─────────── بج رنگی برای جدول بنیادی ─────────── */
  SEL.badge = function (symbol) {
    var d = SEL.map[symbol];
    var st = (d && d.status) || 'pending';
    var m = STATUS_META[st] || STATUS_META.pending;
    var tip = esc(st === 'pending' ? 'هنوز تصمیمی ثبت نشده'
      : (m.label + (d.reason ? ' — ' + d.reason : '') + (d.stop_loss ? ' | حد ضرر: ' + d.stop_loss : '')));
    return '<span data-sel="' + esc(symbol) + '" title="' + tip + '" style="display:inline-block;'
      + 'padding:2px 9px;border-radius:20px;font-size:.655rem;font-weight:800;white-space:nowrap;'
      + 'color:' + m.color + ';background:' + m.bg + ';border:1px solid ' + m.color + '55;">'
      + m.icon + ' ' + m.label + '</span>';
  };
  SEL.statusOf = function (symbol) {
    var d = SEL.map[symbol];
    return (d && d.status) || 'pending';
  };

  /* ─────────── v9.1 اقدام سریع از داخل جدول‌ها (تابلوخوانی / بنیادی) ───────────
     بدون باز کردن چارت: سهمِ دارای حجم مشکوک یا الگوی ساعت را یک‌کلیک
     به «زیر نظر» (واچ‌لیست) یا «تایید»/«رد» می‌برد. */
  var qaEl = null;
  function closeQa() { if (qaEl) { qaEl.remove(); qaEl = null; } }
  SEL._closeQa = closeQa;
  SEL._qaOpen = function () { return !!qaEl; };

  SEL.quick = function (symbol, name, status) {
    if (!symbol) return Promise.resolve(null);
    if (status === 'pending') return SEL.set(symbol, 'pending');
    var reason = status === 'monitor' ? 'اقدام سریع از تابلو'
               : status === 'accept'  ? 'اقدام سریع از تابلو'
               : status === 'reject'  ? 'اقدام سریع از تابلو' : '';
    return SEL.set(symbol, status, { name: name || '', reason: reason });
  };

  SEL.quickMenu = function (symbol, name, anchor) {
    var same = qaEl && qaEl.getAttribute('data-for') === symbol;
    closeQa();
    if (same) return;                       // کلیک دوم روی همان ردیف = بستن
    if (!symbol) return;
    var cur = SEL.statusOf(symbol);
    var items = [
      { st: 'accept',  label: 'تایید سبد' },
      { st: 'monitor', label: 'زیر نظر / واچ‌لیست' },
      { st: 'reject',  label: 'رد' },
      { st: 'pending', label: 'حذف تصمیم' }
    ];
    qaEl = document.createElement('div');
    qaEl.className = 'qa-menu';
    qaEl.setAttribute('data-for', symbol);
    var head = '<div style="padding:4px 9px 6px; font-size:.66rem; color:var(--text-secondary,#94a3b8);">'
             + esc(symbol) + (name ? ' · ' + esc(name) : '') + '</div>';
    qaEl.innerHTML = head + items.map(function (it) {
      var m = STATUS_META[it.st] || STATUS_META.pending;
      return '<button type="button" data-st="' + it.st + '">'
        + '<span class="qa-dot" style="background:' + m.color + ';"></span>'
        + m.icon + ' ' + m.label
        + (it.st === cur ? '<span style="margin-right:auto; opacity:.65;">✓</span>' : '')
        + '</button>';
    }).join('');
    document.body.appendChild(qaEl);
    var r = (anchor || document.body).getBoundingClientRect();
    var w = qaEl.offsetWidth, h = qaEl.offsetHeight;
    qaEl.style.top = Math.max(8, Math.min(window.innerHeight - h - 8, r.bottom + 5)) + 'px';
    qaEl.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.right - w)) + 'px';
    Array.prototype.forEach.call(qaEl.querySelectorAll('button'), function (b) {
      b.onclick = function (ev) {
        ev.stopPropagation();
        var st = b.getAttribute('data-st');
        closeQa();
        SEL.quick(symbol, name, st);
      };
    });
  };


  /* ─────────── نوار تصمیم بالای چارت ─────────── */
  SEL.currentSymbol = function () {
    try { if (typeof rv !== 'undefined' && rv && rv.sym) return String(rv.sym); } catch (e) {}
    var i = el('rvSymInput');
    return (i && i.value) ? String(i.value).trim() : '';
  };

  SEL.paint = function () {
    // ۱) بج‌های جدول بنیادی + جدول تابلوخوانی (v9.1)
    try {
      document.querySelectorAll('[data-selcell]').forEach(function (td) {
        var sym = td.getAttribute('data-selcell');
        var html = SEL.badge(sym);
        // اگر داخل سلول میزبان جداگانه‌ای هست، فقط همان را بازنویسی کن
        // (تا دکمهٔ اقدام سریع کنار بج از بین نرود)
        var host = td.querySelector('[data-selbadge]');
        if (host) host.innerHTML = html; else td.innerHTML = html;
        var qa = td.querySelector('.qa-btn');
        if (qa) qa.dataset.st = SEL.statusOf(sym);
      });
    } catch (e) {}
    // ۲) نوار تصمیم
    try { SEL.syncBar(); } catch (e) {}
    // ۳) شمارنده‌های سبد
    try {
      var n = SEL.counts.accept || 0;
      document.querySelectorAll('[data-selcount]').forEach(function (b) {
        b.textContent = '🧺 سبد من (' + n + '/' + (SEL.limits.max || 7) + ')';
      });
    } catch (e) {}
    // ۴) اگر مودال سبد باز است، تازه‌سازی شود
    try {
      var pm = el('portfolioModal');
      if (pm && pm.classList.contains('active')) SEL.renderPortfolio();
    } catch (e) {}
  };

  SEL.syncBar = function () {
    var bar = el('selBar');
    if (!bar) return;
    var sym = SEL.currentSymbol();
    bar.style.display = sym ? 'flex' : 'none';
    if (!sym) return;
    var st = SEL.statusOf(sym), m = STATUS_META[st], c = SEL.ctx(sym);
    var lbl = el('selBarSym');
    if (lbl) {
      lbl.innerHTML = '<b style="color:var(--accent-blue,#38bdf8);font-size:.82rem;">' + esc(sym) + '</b>'
        + (c.name ? '<span style="color:var(--text-secondary,#94a3b8);font-size:.68rem;"> ' + esc(c.name) + '</span>' : '')
        + ' <span style="padding:2px 8px;border-radius:20px;font-size:.64rem;font-weight:800;color:'
        + m.color + ';background:' + m.bg + ';border:1px solid ' + m.color + '55;">'
        + m.icon + ' ' + m.label + '</span>';
    }
    ['reject', 'monitor', 'accept'].forEach(function (s) {
      var b = el('selBtn_' + s);
      if (!b) return;
      var on = (st === s);
      b.style.outline = on ? '2px solid ' + STATUS_META[s].color : 'none';
      b.style.opacity = on ? '1' : '.82';
      b.title = on ? ('وضعیت فعلی همین نماد: ' + STATUS_META[s].label)
                   : (STATUS_META[s].label + ' برای ' + sym);
    });
  };

  /* ─────────── پاپ‌اور دلیل / حد ضرر ─────────── */
  var popEl = null;
  function closePop() { if (popEl) { popEl.remove(); popEl = null; } }
  SEL.closePop = closePop;

  function fld(label, inner) {
    return '<div style="font-size:.66rem;color:var(--text-secondary,#94a3b8);margin:8px 0 3px;">'
      + label + '</div>' + inner;
  }
  var INP = 'width:100%;padding:6px;border-radius:6px;font-size:.72rem;font-family:inherit;'
    + 'background:var(--bg-primary,#121826);border:1px solid var(--border-color,#2a3450);'
    + 'color:var(--text-primary,#e2e8f0);';

  SEL.openPop = function (status, anchor) {
    var sym = SEL.currentSymbol();
    if (!sym) { toast('⚠️ اول یک نماد را در چارت باز کنید'); return; }
    closePop();
    popEl = document.createElement('div');
    popEl.style.cssText = 'position:fixed;z-index:9999;direction:rtl;text-align:right;'
      + 'background:var(--bg-card,#232c40);border:1px solid var(--border-color,#2a3450);'
      + 'border-radius:10px;box-shadow:0 12px 34px rgba(0,0,0,.5);';
    var meta = STATUS_META[status], reasons = REASONS[status] || [];
    var h = '<div style="padding:10px 12px;min-width:268px;max-width:300px;">'
      + '<div style="font-size:.73rem;font-weight:800;color:' + meta.color + ';">'
      + meta.icon + ' ' + meta.label + ' — ' + esc(sym) + '</div>'
      + fld('دلیل', '<select id="selPopReason" style="' + INP + '">'
          + reasons.map(function (r) { return '<option value="' + esc(r) + '">' + esc(r) + '</option>'; }).join('')
          + '</select>');
    if (status === 'accept') {
      h += fld('حد ضرر', '<div style="display:flex;gap:5px;">'
          + '<select id="selPopSlHint" style="' + INP + 'flex:1;">'
          + SL_HINTS.map(function (r) { return '<option value="' + esc(r) + '">' + esc(r) + '</option>'; }).join('')
          + '<option value="__custom">عدد دلخواه…</option></select>'
          + '<input id="selPopSl" dir="ltr" placeholder="۱٬۴۲۰" style="width:92px;' + INP + '"></div>');
    }
    h += fld('یادداشت (اختیاری)', '<input id="selPopNote" style="' + INP + '" placeholder="…»>')
      + '<div style="display:flex;gap:6px;margin-top:11px;">'
      + '<button id="selPopOk" style="flex:1;padding:7px;border:none;border-radius:7px;cursor:pointer;'
      + 'font-family:inherit;font-size:.74rem;font-weight:800;background:' + meta.color + ';color:#06121b;">ثبت</button>'
      + '<button id="selPopNo" style="padding:7px 12px;border:1px solid var(--border-color,#2a3450);'
      + 'border-radius:7px;background:transparent;color:var(--text-secondary,#94a3b8);cursor:pointer;'
      + 'font-family:inherit;font-size:.74rem;">انصراف</button></div></div>';
    popEl.innerHTML = h;
    document.body.appendChild(popEl);

    var r = (anchor || document.body).getBoundingClientRect();
    var w = popEl.offsetWidth, ht = popEl.offsetHeight;
    popEl.style.top = Math.max(8, Math.min(window.innerHeight - ht - 8, r.bottom + 6)) + 'px';
    popEl.style.left = Math.max(8, Math.min(window.innerWidth - w - 8, r.right - w)) + 'px';

    var no = el('selPopNo'), ok = el('selPopOk');
    if (no) no.onclick = closePop;
    if (ok) ok.onclick = function () {
      var reason = (el('selPopReason') || {}).value || '';
      var sl = '';
      if (status === 'accept') {
        var hint = (el('selPopSlHint') || {}).value || '';
        var custom = ((el('selPopSl') || {}).value || '').trim();
        sl = (hint === '__custom') ? custom : (custom ? hint + ' (' + custom + ')' : hint);
      }
      var note = ((el('selPopNote') || {}).value || '').trim();
      closePop();
      SEL.set(sym, status, { reason: reason, stop_loss: sl, note: note });
    };
  };


  /* ─────────── مودال «سبد نهایی من (۵–۷ سهم)» ─────────── */
  SEL.openPortfolio = function () {
    var m = el('portfolioModal');
    if (!m) return;
    m.classList.add('active');
    SEL.renderPortfolio();
  };
  SEL.closePortfolio = function () {
    var m = el('portfolioModal');
    if (m) m.classList.remove('active');
  };

  function warn(txt, color, bg) {
    if (!txt) return '';
    return '<div style="padding:7px 11px;border-radius:8px;font-size:.72rem;font-weight:700;'
      + 'margin-bottom:8px;color:' + color + ';background:' + bg + ';border:1px solid ' + color + '55;">'
      + txt + '</div>';
  }
  function kindOf(d) {
    return d.asset_kind || (d.pricing_mode === 'free' ? 'dollar'
      : (d.pricing_mode === 'mandatory' ? 'rial' : ''));
  }

  SEL.renderPortfolio = function () {
    var body = el('portfolioBody');
    if (!body) return;
    var list = [];
    Object.keys(SEL.map).forEach(function (s) {
      var d = SEL.map[s];
      if (d && d.status === 'accept') list.push(d);
    });
    list.sort(function (a, b) { return (b.score || 0) - (a.score || 0); });

    var cap = SEL.limits.weight_cap_pct || 20, mn = SEL.limits.min || 5, mx = SEL.limits.max || 7;
    var eq = list.length ? Math.round(100 / list.length * 10) / 10 : 0;
    var eff = list.map(function (d) { return parseFloat(d.weight_pct) > 0 ? parseFloat(d.weight_pct) : eq; });
    var sum = Math.round(eff.reduce(function (a, b) { return a + b; }, 0) * 10) / 10;
    var mix = { dollar: 0, rial: 0, mixed: 0 };
    list.forEach(function (d) { var k = kindOf(d); mix[k === 'dollar' || k === 'rial' ? k : 'mixed']++; });

    var strip = '';
    if (list.length && list.length < mn) strip += warn('⚠️ سبد کامل نیست — ' + (mn - list.length) + ' سهم دیگر تا حدِ پایین ' + mn + ' لازم است', '#eab308', 'rgba(234,179,8,.10)');
    if (list.length > mx) strip += warn('⛔ بیش از سقف ' + mx + ' سهم — ' + (list.length - mx) + ' سهم باید حذف شوند', '#f43f5e', 'rgba(244,63,94,.10)');
    if (list.length >= mn && list.length <= mx) strip += warn('✅ تعداد سبد در بازهٔ مجاز ' + mn + '–' + mx + ' است', '#10b981', 'rgba(16,185,129,.10)');
    // مجموع وزن فقط وقتی معنا دارد که آرایش سبد بسته شده باشد: یا چند سهم،
    // یا حداقل یک وزن دستی (تک‌سهمِ ۲۵٪ یعنی ۷۵٪ نقد — همین باید هشدار بخورد)
    var hasManual = list.some(function (d) { return parseFloat(d.weight_pct) > 0; });
    if (list.length && (list.length > 1 || hasManual) && Math.abs(sum - 100) > 0.6) strip += warn('⚠️ مجموع وزن‌ها ' + sum + '٪ است (باید ۱۰۰٪)', '#eab308', 'rgba(234,179,8,.10)');
    var over = eff.filter(function (w) { return w > cap; }).length;
    if (over) strip += warn('⛔ ' + over + ' سهم بیش از سقف وزن ' + cap + '٪ دارند', '#f43f5e', 'rgba(244,63,94,.10)');

    var head = '<div style="display:flex;gap:10px;flex-wrap:wrap;font-size:.7rem;color:var(--text-secondary,#94a3b8);margin-bottom:9px;">'
      + '<span>🧺 <b style="color:#10b981;">' + list.length + '</b> سهم تاییدشده</span><span>·</span>'
      + '<span>💵 دلاری <b>' + mix.dollar + '</b></span><span>·</span>'
      + '<span>🇮🇷 ریالی <b>' + mix.rial + '</b></span>'
      + (mix.mixed ? '<span>·</span><span>❔ نامشخص <b>' + mix.mixed + '</b></span>' : '')
      + '<span>·</span><span>وزن مساوی پیشنهادی: <b>' + eq + '٪</b></span>'
      + '<span>·</span><span>مجموع وزن: <b>' + sum + '٪</b></span></div>';

    if (!list.length) {
      body.innerHTML = strip + head + '<div style="padding:26px;text-align:center;color:var(--text-muted,#787b86);font-size:.78rem;">'
        + 'هنوز سهمی تایید نشده است.<br>در تب «تکنیکال»، روی چارتِ نماد دکمهٔ 🟢 تایید را بزنید.</div>';
      return;
    }

    var rows = list.map(function (d, i) {
      var k = kindOf(d), w = eff[i], isOver = w > cap;
      var symJs = esc(d.symbol).replace(/'/g, '');
      return '<tr style="border-bottom:1px solid var(--border-color,#2a3450);">'
        + '<td style="padding:5px 6px;font-weight:800;color:var(--accent-blue,#38bdf8);cursor:pointer;" '
        + 'data-chart="' + symJs + '" data-cname="' + esc(d.name || '') + '" title="باز کردن چارت">' + esc(d.symbol) + '</td>'
        + '<td style="padding:5px 6px;font-size:.68rem;color:var(--text-secondary,#94a3b8);max-width:130px;'
        + 'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">' + esc(d.name || '') + '</td>'
        + '<td style="padding:5px 6px;"><select data-kind="' + symJs + '" style="padding:3px 5px;border-radius:5px;'
        + 'font-size:.68rem;font-family:inherit;background:var(--bg-primary,#121826);'
        + 'border:1px solid var(--border-color,#2a3450);color:var(--text-primary,#e2e8f0);">'
        + ['dollar', 'rial', ''].map(function (o) {
            return '<option value="' + o + '"' + (o === k ? ' selected' : '') + '>' + KIND_LABEL[o] + '</option>';
          }).join('') + '</select></td>'
        + '<td style="padding:5px 6px;"><input type="number" min="0" max="100" step="0.5" '
        + 'value="' + (parseFloat(d.weight_pct) > 0 ? parseFloat(d.weight_pct) : '') + '" placeholder="' + eq + '" '
        + 'data-weight="' + symJs + '" dir="ltr" style="width:58px;padding:3px 5px;border-radius:5px;font-size:.68rem;'
        + 'background:var(--bg-primary,#121826);border:1px solid ' + (isOver ? '#f43f5e' : 'var(--border-color,#2a3450)')
        + ';color:' + (isOver ? '#f43f5e' : 'var(--text-primary,#e2e8f0)') + ';"></td>'
        + '<td style="padding:5px 6px;font-size:.68rem;color:#eab308;">' + esc(d.stop_loss || '—') + '</td>'
        + '<td style="padding:5px 6px;font-size:.68rem;color:var(--text-secondary,#94a3b8);">' + esc(d.reason || d.note || '—') + '</td>'
        + '<td style="padding:5px 6px;font-weight:800;font-size:.7rem;color:' + (d.score >= 4 ? '#10b981' : '#94a3b8') + ';">' + (d.score || 0) + '/۵</td>'
        + '<td style="padding:5px 6px;"><button data-drop="' + symJs + '" title="خروج از سبد" style="border:none;'
        + 'background:rgba(244,63,94,.15);color:#f43f5e;border-radius:5px;padding:3px 8px;cursor:pointer;'
        + 'font-family:inherit;font-size:.68rem;">✖</button></td></tr>';
    }).join('');

    body.innerHTML = strip + head
      + '<table style="width:100%;border-collapse:collapse;text-align:right;">'
      + '<thead><tr style="font-size:.66rem;color:var(--text-muted,#787b86);">'
      + '<th style="padding:4px 6px;">نماد</th><th style="padding:4px 6px;">نام</th>'
      + '<th style="padding:4px 6px;">نوع</th><th style="padding:4px 6px;">وزن٪</th>'
      + '<th style="padding:4px 6px;">حد ضرر</th><th style="padding:4px 6px;">دلیل</th>'
      + '<th style="padding:4px 6px;">امتیاز</th><th style="padding:4px 6px;"></th>'
      + '</tr></thead><tbody>' + rows + '</tbody></table>';
    SEL.bindPortfolioInputs();
  };

  /* ورودی‌های مودال سبد — با change روی وزن/نوع، همان رکورد به‌روز می‌شود */
  SEL.bindPortfolioInputs = function () {
    var body = el('portfolioBody');
    if (!body) return;
    body.querySelectorAll('[data-drop]').forEach(function (b) {
      b.onclick = function () { SEL.set(b.getAttribute('data-drop'), 'pending'); };
    });
    body.querySelectorAll('[data-chart]').forEach(function (t) {
      t.onclick = function () {
        SEL.fromPortfolioChart(t.getAttribute('data-chart'), t.getAttribute('data-cname'));
      };
    });
    body.querySelectorAll('[data-weight]').forEach(function (inp) {
      inp.onchange = function () {
        var s = inp.getAttribute('data-weight'), d = SEL.map[s];
        if (!d) return;
        SEL.set(s, 'accept', {
          weight_pct: parseFloat(inp.value) || 0, name: d.name, sector: d.sector,
          pricing_mode: d.pricing_mode, asset_kind: d.asset_kind,
          stop_loss: d.stop_loss, reason: d.reason, note: d.note, score: d.score, price: d.price
        });
      };
    });
    body.querySelectorAll('[data-kind]').forEach(function (sc) {
      sc.onchange = function () {
        var s = sc.getAttribute('data-kind'), d = SEL.map[s];
        if (!d) return;
        SEL.set(s, 'accept', {
          asset_kind: sc.value, name: d.name, sector: d.sector, pricing_mode: d.pricing_mode,
          weight_pct: d.weight_pct, stop_loss: d.stop_loss, reason: d.reason,
          note: d.note, score: d.score, price: d.price
        });
      };
    });
  };

  SEL.fromPortfolioChart = function (sym, name) {
    SEL.closePortfolio();
    try { if (typeof gotoChart === 'function') { gotoChart(sym, name); return; } } catch (e) {}
    try { if (typeof switchView === 'function') switchView('tech'); } catch (e) {}
    var i = el('rvSymInput');
    if (i) { i.value = sym; try { if (typeof rvLoad === 'function') rvLoad(sym); } catch (e) {} }
  };

  /* ─────────── راه‌اندازی ─────────── */
  var lastSym = '\u0000';
  SEL.watch = function () {
    var s = SEL.currentSymbol();
    if (s !== lastSym) { lastSym = s; SEL.syncBar(); }
  };

  SEL.init = function () {
    // دکمه‌های نوار تصمیم
    ['reject', 'monitor', 'accept'].forEach(function (st) {
      var b = el('selBtn_' + st);
      if (b) b.onclick = function (ev) { ev.stopPropagation(); SEL.openPop(st, b); };
    });
    var pf = el('selBtn_portfolio');
    if (pf) pf.onclick = function () { SEL.openPortfolio(); };
    var x = el('portfolioClose');
    if (x) x.onclick = SEL.closePortfolio;
    var mask = el('portfolioModal');
    if (mask) mask.addEventListener('click', function (ev) { if (ev.target === mask) SEL.closePortfolio(); });

    // بستن پاپ‌اور / منوی سریع با کلیک بیرون یا Esc
    document.addEventListener('mousedown', function (ev) {
      if (popEl && !popEl.contains(ev.target)) closePop();
      // کلیک روی خودِ دکمهٔ ⚑ را به handler کلیک بسپار (برای سوییچ باز/بسته)
      var onBtn = ev.target && ev.target.closest && ev.target.closest('.qa-btn');
      if (qaEl && !qaEl.contains(ev.target) && !onBtn) closeQa();
    }, true);
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') { closePop(); closeQa(); SEL.closePortfolio(); }
    });

    // همگام‌سازی نوار با تغییر نماد چارت (rvLoad در tech_rtv.js تعریف شده است)
    try {
      if (typeof window.rvLoad === 'function' && !window.rvLoad.__selPatched) {
        var orig = window.rvLoad;
        window.rvLoad = function () {
          var r = orig.apply(this, arguments);
          setTimeout(SEL.watch, 60);
          return r;
        };
        window.rvLoad.__selPatched = true;
      }
    } catch (e) {}
    setInterval(SEL.watch, 1200);   // شبکهٔ اطمینان (تغییر نماد از مسیرهای دیگر)

    SEL.load().then(SEL.syncBar);
  };

  /* ═════════════ v9.7.3 — واچ‌لیست + ماتریس «تایید سه‌گانه» ═════════════
     ستون‌های ماتریس هیچ‌وقت این‌جا محاسبه نمی‌شوند؛ از /api/watchlist/matrix
     می‌آیند (منبع حقیقت: confidence_engine + fts_engine). این‌جا فقط نمایش. */

  // آینهٔ fts_engine.norm_fa — تا ستارهٔ ☆/★ روی دو نوشتارِ یک نماد
  // («داريك» عربی و «داریک» فارسی) یکی بسوزد. اگر norm_fa عوض شد، این هم باید
  // عوض شود؛ گاردِ dev/watchlist_matrix_v973.py همین قرارداد را می‌سنجد.
  function nfa(s) {
    return String(s == null ? '' : s)
      .replace(/\u064a/g, '\u06cc').replace(/\u0643/g, '\u06a9')
      .replace(/\u0649/g, '\u06cc').replace(/\u200c/g, '');
  }

  // VETOED حذف شد: در v9.7.4 وتوی سخت جایش را به «تحت نظر» (WATCH) داد —
  // سهمِ دارای هشدار از لیست بیرون نمی‌رود، فقط amber می‌شود.
  var VERDICT = {
    CONFIRMED:    { fa: 'تایید سه‌گانه', c: '#10b981', bg: 'rgba(16,185,129,.16)' },
    PROBABLE:     { fa: 'احتمال قوی',    c: '#38bdf8', bg: 'rgba(56,189,248,.14)' },
    WATCH:        { fa: 'تحت نظر',       c: '#f59e0b', bg: 'rgba(245,158,11,.14)'  },
    WEAK:         { fa: 'ضعیف',          c: '#eab308', bg: 'rgba(234,179,8,.14)'  },
    INSUFFICIENT: { fa: 'داده ناکافی',   c: '#94a3b8', bg: 'rgba(148,163,184,.14)' }
  };
  var ST = {
    pass:   { mark: '✔', c: '#10b981', fa: 'تایید' },
    warn:   { mark: '⚠', c: '#f59e0b', fa: 'هشدار منعطف' },
    fail:   { mark: '✖', c: '#f43f5e', fa: 'رد' },
    nodata: { mark: '–', c: '#787b86', fa: 'بی‌داده' }
  };

  var WL = { list: [], key: {}, rows: [], meta: null, busy: false };
  window.WL = WL;

  WL.has = function (symbol) { return !!WL.key[nfa(symbol)]; };

  WL.load = function () {
    return fetch('/api/watchlist', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.status !== 'success') throw new Error((j && j.message) || 'خطا');
        WL.list = j.data || [];
        WL.key = {};
        WL.list.forEach(function (w) { if (w && w.symbol) WL.key[nfa(w.symbol)] = w; });
        WL.paintStars();
        return j;
      })
      .catch(function (e) { console.warn('WL.load', e); });
  };

  // جدول اسکرینر هر بار از نو ساخته می‌شود، پس برچسب ستاره‌ها را جدا می‌پکِشیم
  WL.paintStars = function () {
    document.querySelectorAll('[data-watch]').forEach(function (b) {
      var on = WL.has(b.getAttribute('data-watch'));
      b.textContent = on ? '📌 پین‌شده' : '☆ واچ';
      b.style.color = on ? '#f59e0b' : '';
    });
    // v9.7.6 — پین به بالا: جدول تابلو باید بعد از هر تغییر واچ‌لیست دوباره
    // مرتب شود (فقط وقتی داده هست و تب تابلو قابل‌مشاهده است — بی‌صدا و debounce)
    try {
      if (typeof applyFiltersDebounced === 'function' && typeof marketData !== 'undefined'
          && marketData && marketData.length) applyFiltersDebounced();
    } catch (e) {}
  };

  // سقفِ واچ‌لیست از «تنظیمات کدال» می‌آید (LocalStorage → پنل). پیش‌فرضِ
  // جزوه ۵۰ سهم است؛ سرور هم همان را در /api/watchlist/matrix اعمال میکند،
  // ولی این‌جا کاربر *همان لحظه* می‌فهمد چرا اضافه نمیشود — نه بعد از رفرش.
  var WL_CAP_FALLBACK = 50;
  function wlCap() {
    try {
      if (typeof FTS_SETTINGS !== 'undefined') {
        var s = FTS_SETTINGS.loadLS();
        if (s && s.watchlist_max > 0) return s.watchlist_max | 0;
      }
    } catch (e) {}
    if (WL.meta && WL.meta.limit > 0) return WL.meta.limit | 0;
    return WL_CAP_FALLBACK;
  }
  WL.cap = wlCap;

  WL.toggle = function (symbol, name) {
    if (!symbol || WL.busy) return;
    WL.busy = true;
    var known = WL.has(symbol);
    var delSym = known ? (WL.key[nfa(symbol)].symbol || symbol) : symbol;
    if (!known && WL.list.length >= wlCap()) {
      WL.busy = false;
      toast('⛔ واچ‌لیست پر است (' + WL.list.length + '/' + wlCap() +
            ') — از «تنظیمات کدال» سقف را بالا ببرید یا سهمی را بردارید');
      return;
    }
    var p = known
      ? fetch('/api/watchlist/' + encodeURIComponent(delSym), { method: 'DELETE' })
            .then(function (r) { return r.json(); })
      : fetch('/api/watchlist', {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ symbol: symbol,
                                 name: (SEL.ctx(symbol) || {}).name || name || '' })
        }).then(function (r) { return r.json(); });
    Promise.resolve(p).then(function (j) {
      if (!j || j.status !== 'success') throw new Error((j && j.message) || 'ناموفق');
      toast(known ? ('☆ ' + symbol + ' از واچ‌لیست حذف شد')
                  : ('★ ' + symbol + ' به واچ‌لیست اضافه شد'));
      return WL.load().then(WL.refresh);
    }).catch(function (e) {
      toast('⚠️ ' + ((e && e.message) ? e.message : 'خطا'));
    }).then(function () { WL.busy = false; });
  };

  WL.refresh = function () {
    if (!WL.list.length) { WL.rows = []; WL.render(); return Promise.resolve(null); }
    return fetch('/api/watchlist/matrix', { headers: { 'Accept': 'application/json' } })
      .then(function (r) { return r.json(); })
      .then(function (j) {
        if (!j || j.status !== 'success') throw new Error((j && j.message) || 'خطا');
        WL.rows = j.rows || [];
        WL.meta = j;
        WL.render();
        return j;
      })
      .catch(function (e) { console.warn('WL.refresh', e); WL.render(); });
  };

  function stMark(state) {
    var s = ST[state] || ST.nodata;
    return '<span dir="ltr" title="' + s.fa + '" style="font-weight:900;color:'
      + s.c + ';">' + s.mark + '</span>';
  }

  WL.render = function () {
    var card = el('watchMatrixCard'), body = el('watchMatrixBody');
    if (!card || !body) return;
    card.style.display = WL.list.length ? '' : 'none';
    var m = el('watchMatrixMeta');
    if (m) {
      var a = (WL.meta && WL.meta.asof) || {};
      m.textContent = WL.list.length
        ? (WL.list.length + ' نماد · تکنیکال ' + (a.tech || '—')
           + ' · تابلو ' + (a.tape || '—') + ' · بنیاد ' + (a.fund || '—'))
        : '';
    }
    if (!WL.rows.length) {
      body.innerHTML = '<tr><td colspan="8" style="text-align:center;">'
        + 'واچ‌لیست خالی است — روی ☆ واچ در جدول بنیادی بزنید.</td></tr>';
      return;
    }
    body.innerHTML = WL.rows.map(function (r) {
      var v = VERDICT[r.verdict] || VERDICT.INSUFFICIENT;
      var st = r.states || {};
      var symJs = esc(r.symbol).replace(/'/g, '');
      // دلیلِ هر warn از conf_reasons می‌آید؛ یادداشتِ تجمیعیِ «هشدارها» حذف
      // می‌شود وگرنه یک متن دو بار در tooltip تکرار می‌شود.
      var tips = (r.conf_reasons || []).concat((r.notes || []).filter(function (n) {
        return String(n).indexOf('هشدارها') !== 0;
      })).join(' · ');
      return '<tr>'
        + '<td style="font-weight:800;color:#38bdf8;cursor:pointer;" data-chart="'
        + symJs + '" title="باز کردن چارت">' + esc(r.symbol) + '</td>'
        + '<td style="font-size:.6875rem;color:#94a3b8;max-width:150px;overflow:hidden;'
        + 'text-overflow:ellipsis;white-space:nowrap;">'
        + esc(r.watch_name || r.db_symbol || '') + '</td>'
        + '<td style="text-align:center;">' + stMark(st.tech) + '</td>'
        + '<td style="text-align:center;">' + stMark(st.tape) + '</td>'
        + '<td style="text-align:center;">' + stMark(st.fund) + '</td>'
        + '<td style="text-align:center;white-space:nowrap;"><span class="sel-badge" '
        + 'style="color:' + v.c + ';background:' + v.bg + ';border:1px solid ' + v.c
        + '55;padding:2px 8px;border-radius:999px;font-size:.66rem;font-weight:800;" '
        + 'title="' + esc(r.verdict) + (tips ? (' — ' + tips) : '') + '">'
        + esc(r.verdict) + ' · ' + esc(v.fa) + '</span></td>'
        + '<td dir="ltr" style="text-align:center;font-weight:800;font-size:.72rem;" '
        + 'title="' + esc(String(r.conf_count)) + ' ستون تایید از '
        + esc(String(r.coverage)) + ' ستونِ دارای داده">'
        + esc(String(r.conf_count)) + '/' + esc(String(r.coverage)) + '</td>'
        + '<td style="text-align:center;white-space:nowrap;">'
        + '<button class="op-btn op-btn--tech" onclick="event.stopPropagation(); gotoChart(\''
        + symJs + '\', \'' + esc(r.watch_name || '') + '\')">📊</button>'
        + '<button class="op-btn" onclick="event.stopPropagation(); WL.toggle(\''
        + symJs + '\')">✖</button></td></tr>';
    }).join('');
  };

  WL.boot = function () { WL.load().then(WL.refresh); };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(SEL.init, 250);
      setTimeout(WL.boot, 400);
    });
  } else {
    setTimeout(SEL.init, 250);
    setTimeout(WL.boot, 400);
  }
})();
