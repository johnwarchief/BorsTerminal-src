/* =====================================================================
   BorsTerminal — Calendar Service (v1.0)
   ---------------------------------------------------------------------
   لایه دیتای مستقل تب تقویم:
   - منبع اصلی: static/calendar/cache.json (خروجی dev/calendar_fetcher.py)
   - کش مرورگر: localStorage با TTL
   - fallback زنده: /api/calendar/events (بک‌اند داخلی در صورت اضافه شدن)
   - نرمال‌سازی رویدادها + دسته‌بندی مشتق از عنوان/توضیح
   ===================================================================== */
(function () {
  'use strict';

  var CACHE_KEY = 'borsCalCacheV1';
  var TTL = 6 * 3600 * 1000; // ۶ ساعت

  /* دسته‌ها: کلید → برچسب/رنگ (رنگ در CSS با cal-cat-*) */
  var CATS = {
    assembly:        { fa: 'مجامع عادی',          match: function (t, d, tid) { return tid === 1; } },
    assemblyExtra:   { fa: 'مجامع فوق‌العاده',     match: function (t, d, tid) { return tid === 2; } },
    assemblyChange:  { fa: 'لغو/تغییر زمان مجمع',  match: function () { return false; } },
    dividend:        { fa: 'پرداخت سود نقدی',      match: function (t, d, tid) { return tid === 3; } },
    capitalIncrease: { fa: 'افزایش سرمایه',        match: function (t) { return /افزایش\s*سرمایه/.test(t); } },
    ipo:             { fa: 'عرضه‌های اولیه',        match: function (t) { return /عرضه\s*اولیه|عرضه\s*در\s*بازار/.test(t); } },
    bondMaturity:    { fa: 'سررسید اوراق/اخزا',    match: function (t) { return /سررسید|اخزا|اوراق/.test(t); } },
    other:           { fa: 'سایر رویدادها',        match: function () { return true; } }
  };
  var CAT_ORDER = ['assembly', 'assemblyExtra', 'assemblyChange', 'dividend',
                   'capitalIncrease', 'ipo', 'bondMaturity', 'other'];

  var S = {
    raw: null,        // دیتای خام cache.json
    events: [],       // نرمال‌شده
    industries: {},   // نماد → صنعت (اختیاری از meta.industries)
    loaded: false,
    loading: null,
    lastFetch: 0
  };

  function classify(title, desc, typeId) {
    var t = (title || '') + ' ' + (desc || '');
    // v9.2 — یکسان‌سازی نوشتار: «فوقالعاده» بدون نیم‌فاصله و «پذيرش» با ی عربی
    // وگرنه تطبیق نمی‌شدند (همان کلاس باگی که fts_engine.norm_fa حل کرده بود).
    t = t.replace(/\u200c/g, '').replace(/\u064a/g, '\u06cc').replace(/\u0643/g, '\u06a9');
    var tid = Number(typeId) || 0;
    // v1.1 — «لغو/تغییر زمان مجمع» باید پیش از بررسی tid سنجیده شود؛ این نامه‌ها
    // هم Category=6 (مجامع) می‌آیند و وگرنه به‌اشتباه «مجمع عادی/فوق‌العاده» می‌شوند
    if (/لغو|عدم برگزاری|به تعویق|تغییر زمان|انتقال مجمع|موافقت با تغییر/.test(t)) return 'assemblyChange';
    if (tid === 1) return 'assembly';
    if (tid === 2) return 'assemblyExtra';
    if (tid === 3) return 'dividend';
    if (/سررسید|اخزا|صکوک|اوراق\s*(مرابحه|اجاره|بدهی|مشارکت|مشتقه|گامپ|سلف)/.test(t)) return 'bondMaturity';
    // v9.2 — واژگان رسمی کدال برای عرضه اولیه. نامه‌های Category=4 با عنوان
    // «امیدنامه پذیرش در بورس / فرابورس ایران» می‌آیند و قدیماً به «سایر» می‌افتادند.
    if (/عرضه\s*اولیه|عرضه\s*در\s*بازار|پذیره\s*نویسی|نشریه\s*عرضه|امیدنامه\s*پذیرش|پذیرش\s*در\s*(بورس|فرابورس|فابورس)/.test(t)) return 'ipo';
    if (/افزایش\s*سرمایه/.test(t)) return 'capitalIncrease';
    return 'other';
  }

  function normalize(rawEvents) {
    return (rawEvents || []).map(function (e, i) {
      var dt = e.date_time || e.datetime || e.date || '';
      var ms = Date.parse(dt) || 0;
      var d = new Date(ms);
      var pad = function (x) { return String(x).padStart(2, '0'); };
      var title = e.event_title || e.title || e.name || 'رویداد';
      var desc = e.description || e.desc || '';
      var sym = e.asset_symbol_trade || e.symbol || '';
      return {
        id: e.report_id ? 'r' + e.report_id : 'e' + i,
        typeId: Number(e.event_type_id) || 0,
        cat: classify(title, desc, Number(e.event_type_id) || 0),
        title: title,
        desc: desc,
        symbol: sym,
        symbolId: e.asset_id || '',
        ms: ms,
        date: isNaN(ms) ? '' : d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()),
        time: (e.event_time) || (dt && /T\d{2}:\d{2}/.test(dt) ? dt.slice(dt.indexOf('T') + 1, dt.indexOf('T') + 6) : ''),
        reportId: e.report_id || '',
        link: e.link || e.url || ''
      };
    }).filter(function (e) { return e.ms > 0; })
      .sort(function (a, b) { return a.ms - b.ms; });
  }

  function ingest(json) {
    S.raw = json;
    S.events = normalize((json && (json.events || json.data)) || []);
    S.industries = (json && json.meta && json.meta.industries) || {};
    S.loaded = true;
    S.lastFetch = Date.now();
    try {
      localStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), json: json }));
    } catch (e) { /* quota */ }
  }

  function loadLocal() {
    try {
      var raw = localStorage.getItem(CACHE_KEY);
      if (!raw) return false;
      var o = JSON.parse(raw);
      if (!o || !o.json || Date.now() - o.at > TTL) return false;
      ingest(o.json);
      return true;
    } catch (e) { return false; }
  }

  /* واکشی: کش استاتیک → localStorage → بک‌اند داخلی (اختیاری) */
  function load(force) {
    if (S.loading) return S.loading;
    S.loading = new Promise(function (resolve) {
      var done = function (src) { S.loading = null; resolve(src); };
      if (!force && S.loaded) return done('memory');
      if (!force && loadLocal()) return done('local');
      fetch('/static/calendar/cache.json?_=' + Date.now())
        .then(function (r) { if (!r.ok) throw 0; return r.json(); })
        .then(function (j) { ingest(j); done('cache.json'); })
        .catch(function () {
          // تلاش برای بک‌اند داخلی (در صورت اضافه شدن به آینده)
          fetch('/api/calendar/events')
            .then(function (r) { if (!r.ok) throw 0; return r.json(); })
            .then(function (j) { ingest(j); done('api'); })
            .catch(function () {
              if (loadLocal()) return done('local-stale');
              ingest({ events: [] }); done('empty');
            });
        });
    });
    return S.loading;
  }

  /* واکشی زنده از منبع (فقط در صورت وجود پروکسی داخلی — CORS مرورگر اجازه مستقیم نمیدهد) */
  function refreshLive(fromISO, toISO) {
    var q = '/api/calendar/events?from=' + encodeURIComponent(fromISO) + '&to=' + encodeURIComponent(toISO);
    return fetch(q).then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) { ingest(j); return j; });
  }

  /* فیلترها: { cat, symbol, industry, fromMs, toMs, q } */
  function query(f) {
    f = f || {};
    return S.events.filter(function (e) {
      if (f.cat && f.cat !== 'all' && e.cat !== f.cat) return false;
      if (f.symbol && (e.symbol || '').indexOf(f.symbol) === -1) return false;
      if (f.industry && f.industry !== 'all' && (S.industries[e.symbol] || '') !== f.industry) return false;
      if (f.q) {
        var hay = (e.title + ' ' + e.symbol + ' ' + e.desc).toLowerCase();
        if (hay.indexOf(String(f.q).toLowerCase()) === -1) return false;
      }
      if (f.fromMs && e.ms < f.fromMs) return false;
      if (f.toMs && e.ms > f.toMs) return false;
      return true;
    });
  }

  function industries() {
    var set = {};
    Object.keys(S.industries).forEach(function (k) { set[S.industries[k]] = 1; });
    return Object.keys(set).sort();
  }

  window.CalService = {
    CATS: CATS, CAT_ORDER: CAT_ORDER,
    load: load, refreshLive: refreshLive, query: query, industries: industries,
    get events() { return S.events; },
    get meta() { return (S.raw && S.raw.meta) || {}; },
    get isLoaded() { return S.loaded; }
  };
})();
