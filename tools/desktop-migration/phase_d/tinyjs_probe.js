// In-page probe for TinyJS (no CDP). Injected through app.window('app').eval()
// by the prototype backend, it reports only what the live page exposes:
// Navigation/Resource Timing, DOM state, chart payload entries and rAF deltas.
// There is no JS-heap or paint-timing claim here.
//
// Placeholder __BORS_COLLECTOR__ is replaced by the shell with a local port.
(function () {
  if (window.__borsPhaseDProbe) return;
  window.__borsPhaseDProbe = true;

  var COLLECTOR = 'http://127.0.0.1:__BORS_COLLECTOR__/probe';
  var SYMBOL = 'فولاد';
  var RUN = String(Date.now()) + '-' + Math.random().toString(36).slice(2, 8);
  var out = {
    probe: 'phase_d_tinyjs/1',
    run_id: RUN,
    started_at: Date.now(),
    url_at_attach: location.href,
    events: {},
    states: {},
    resources: [],
    errors: [],
    metrics: {},
  };

  function post(obj) {
    try {
      fetch(COLLECTOR, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify(obj),
      }).catch(function () {});
    } catch (e) { /* collector unavailable must not affect the page */ }
  }

  function emit(name, extra) {
    if (out.events[name]) return out.events[name];
    var e = {
      epoch_ms: Date.now(),
      perf_ms: Math.round(performance.now() * 10) / 10,
      time_origin: performance.timeOrigin,
      url: location.href,
    };
    if (extra) for (var k in extra) e[k] = extra[k];
    out.events[name] = e;
    post({ kind: 'event', run_id: RUN, name: name, event: e });
    return e;
  }

  function sleep(ms) {
    return new Promise(function (r) { setTimeout(r, ms); });
  }

  async function pauseForShot(name) {
    if (!window.__BORS_VISUAL__) return 'skipped';
    var end = Date.now() + 25000;
    while (Date.now() < end) {
      try {
        var r = await fetch(COLLECTOR.replace('/probe', '/ack?stage=' + encodeURIComponent(name)),
                            { cache: 'no-store' });
        if (r.ok) {
          var j = await r.json();
          if (j && j.stage === name) return true;
        }
      } catch (e) { /* collector may not be there yet */ }
      await sleep(200);
    }
    return false;
  }

  async function waitFor(fn, timeout, label) {
    var end = Date.now() + timeout;
    while (Date.now() < end) {
      var v = false;
      try { v = fn(); } catch (e) { v = false; }
      if (v) return v;
      await sleep(100);
    }
    throw new Error('timeout: ' + label);
  }

  function setInput(sel, value) {
    var el = document.querySelector(sel);
    if (!el) return false;
    var setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
    setter.call(el, value);
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function rows() {
    return document.querySelectorAll('[data-testid="tape-row"]').length;
  }

  function chartEntries() {
    return performance.getEntriesByType('resource')
      .filter(function (e) { return e.name.indexOf('/api/chart/') >= 0; })
      .map(function (e) {
        return {
          name: e.name.replace(location.origin, ''),
          duration_ms: Math.round(e.duration * 10) / 10,
          status: e.responseStatus == null ? null : e.responseStatus,
          transfer: e.transferSize == null ? null : e.transferSize,
          encoded: e.encodedBodySize == null ? null : e.encodedBodySize,
          decoded: e.decodedBodySize == null ? null : e.decodedBodySize,
        };
      });
  }

  function apiResources() {
    return performance.getEntriesByType('resource')
      .filter(function (e) { return e.name.indexOf('/api/') >= 0; })
      .map(function (e) {
        return {
          name: e.name.replace(location.origin, ''),
          start_ms: Math.round(e.startTime * 10) / 10,
          duration_ms: Math.round(e.duration * 10) / 10,
          status: e.responseStatus == null ? null : e.responseStatus,
          transfer: e.transferSize == null ? null : e.transferSize,
          encoded: e.encodedBodySize == null ? null : e.encodedBodySize,
          decoded: e.decodedBodySize == null ? null : e.decodedBodySize,
          initiator: e.initiatorType || null,
        };
      });
  }

  function captureMetrics(name) {
    var m = { rss_note: 'process tree sampled by Python' };
    if (performance.memory) {
      m.browser_reported_heap = {
        used: performance.memory.usedJSHeapSize,
        total: performance.memory.totalJSHeapSize,
        limit: performance.memory.jsHeapSizeLimit,
        note: 'performance.memory; not a CDP heap snapshot',
      };
    }
    out.metrics[name] = m;
  }

  async function scrollProbe() {
    var best = null;
    var bestRange = 0;
    var all = document.querySelectorAll('*');
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      var range = el.scrollHeight - el.clientHeight;
      if (range > bestRange && el.clientHeight > 200) {
        bestRange = range;
        best = el;
      }
    }
    if (!best) return { available: false };
    var deltas = [];
    var last = performance.now();
    var frames = 0;
    var startScroll = best.scrollTop;
    await new Promise(function (resolve) {
      function step(now) {
        deltas.push(now - last);
        last = now;
        frames++;
        best.scrollTop = startScroll + (bestRange * frames) / 45;
        if (frames >= 45) resolve();
        else requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    });
    var sorted = deltas.slice().sort(function (a, b) { return a - b; });
    var pct = function (p) {
      return sorted.length ? Math.round(sorted[Math.min(sorted.length - 1, Math.floor(p * sorted.length))] * 10) / 10 : null;
    };
    best.scrollTop = startScroll;
    return {
      available: true,
      frames: frames,
      range_px: bestRange,
      p50_ms: pct(0.5),
      p95_ms: pct(0.95),
      max_ms: Math.round(sorted[sorted.length - 1] * 10) / 10,
      note: 'programmatic scroll on the largest scrollable element; rAF deltas only',
    };
  }

  window.addEventListener('error', function (e) {
    out.errors.push({ kind: 'pageerror', text: String(e.message || e).slice(0, 500), at_ms: Date.now() });
  });
  window.addEventListener('unhandledrejection', function (e) {
    out.errors.push({ kind: 'unhandledrejection', text: String(e.reason || e).slice(0, 500), at_ms: Date.now() });
  });

  async function run() {
    try {
      post({ kind: 'started', run_id: RUN, at: Date.now(), url: location.href });
      await waitFor(function () { return document.readyState !== 'loading'; }, 30000, 'document');
      if (window.__BORS_VISUAL__ && document.head) {
        // Capture-only: entrance animations froze some panels at opacity 0 in
        // PrintWindow; screenshots must show the settled UI, not a paused frame.
        var st = document.createElement('style');
        st.id = 'bors-visual-settle';
        st.textContent = '.panel-in{animation:none!important;opacity:1!important;transform:none!important}';
        document.head.appendChild(st);
      }
      var nav = (performance.getEntriesByType('navigation') || [])[0];
      emit('app_document_ready', nav ? {
        nav_start_ms: Math.round(nav.startTime * 10) / 10,
        dom_content_loaded_ms: Math.round(nav.domContentLoadedEventEnd * 10) / 10,
        load_event_ms: Math.round(nav.loadEventEnd * 10) / 10,
      } : {});
      captureMetrics('app_document_ready');

      var login = await waitFor(function () {
        return document.querySelector('input[autocomplete="username"]')
          || document.querySelector('[data-testid="fts-funnel-workspace"]')
          || document.querySelector('[data-testid="master-breadcrumb"]')
          || document.querySelector('[data-testid="market-page"]');
      }, 60000, 'login-or-app');

      var hasLogin = !!document.querySelector('input[autocomplete="username"]');
      if (hasLogin) {
        emit('login_ready');
        setInput('input[autocomplete="username"]', 'admin');
        setInput('input[autocomplete="current-password"]', 'bors123');
        out.states.login_values = Array.prototype.map.call(document.querySelectorAll('input'), function (i) {
          return { type: i.type, value: i.value };
        });
        var btn = document.querySelector('button[type="submit"]');
        if (!btn) throw new Error('login submit button missing');
        btn.click();
        emit('login_submit');
      } else {
        emit('login_skipped');
      }

      await waitFor(function () {
        return document.querySelector('[data-testid="fts-funnel-workspace"]')
          || document.querySelector('[data-testid="master-breadcrumb"]')
          || document.querySelector('[data-testid="master-open-funnel"]');
      }, 60000, 'master-ready');
      emit('master_ready');
      captureMetrics('master_ready');

      emit('market_nav_begin');
      location.hash = '#/market';
      await waitFor(function () { return document.querySelector('[data-testid="market-page"]'); }, 30000, 'market-page');
      await waitFor(function () { return rows() > 0; }, 90000, 'market-rows');
      emit('market_rows_visible', { rows: rows() });
      out.states.market_pause_ack = await pauseForShot('market_rows_visible');
      await sleep(1000);
      out.states.market_rows_after_1s = rows();
      out.states.board_freshness = (function () {
        var el = document.querySelector('[data-testid="freshness-badge"]');
        return el ? el.textContent.replace(/\s+/g, ' ').trim() : null;
      })();
      out.states.market_scroll = await scrollProbe();
      captureMetrics('market_ready');
      await sleep(2000);

      emit('technical_nav_begin');
      location.hash = '#/technical/' + encodeURIComponent(SYMBOL);
      await waitFor(function () { return document.querySelector('[data-testid="chart-area"]'); }, 30000, 'chart-area');
      await waitFor(function () {
        var chart = document.querySelector('[data-testid="chart-area"]');
        var canvas = chart && chart.querySelector('canvas');
        var fresh = document.querySelector('[data-testid="fts-layer-freshness"]');
        var text = (fresh && fresh.textContent) || '';
        var okEntry = chartEntries().some(function (e) {
          return (e.status === 200 || e.status === null) && (e.decoded || 0) > 1000;
        });
        return !!canvas && canvas.width > 0 && canvas.height > 0
          && /[۰-۹0-9]+\s*کندل/.test(text) && okEntry;
      }, 90000, 'technical-ready');
      var freshEl = document.querySelector('[data-testid="fts-layer-freshness"]');
      var freshText = (freshEl && freshEl.textContent || '').trim();
      var canvas = document.querySelector('[data-testid="chart-area"] canvas');
      emit('technical_ready', {
        chart_host: document.querySelector('[data-testid="ffc-chart-host"]') ? 'ffc'
          : document.querySelector('[data-testid="nn-chart-host"]') ? 'nn' : 'other',
        freshness: freshText,
        bars: (freshText.match(/([۰-۹0-9]+)\s*کندل/) || [])[1] || null,
        last_bar: (freshText.match(/آخرین کندل:\s*([^·]+)/) || [])[1] ? (freshText.match(/آخرین کندل:\s*([^·]+)/) || [])[1].trim() : null,
        canvas: canvas ? { w: canvas.width, h: canvas.height } : null,
        chart_api: chartEntries(),
      });
      out.states.technical_pause_ack = await pauseForShot('technical_ready');
      captureMetrics('technical_ready');

      if (window.__BORS_D3_CHECKS__) {
        var d3 = { timeframe: {}, adjustment: {}, symbol_switch: {} };
        var tfBtn = document.querySelector('[data-testid="timeframe-W"]');
        if (tfBtn) {
          tfBtn.click();
          await sleep(1200);
          var active = document.querySelector('[data-testid="timeframe-W"]');
          var cw = document.querySelector('[data-testid="chart-area"] canvas');
          d3.timeframe = {
            switched_to: 'W',
            active: !!(active && /active/.test(active.className)),
            canvas: cw ? { w: cw.width, h: cw.height } : null,
          };
          var dBtn = document.querySelector('[data-testid="timeframe-D"]');
          if (dBtn) dBtn.click();
          await sleep(800);
        } else {
          d3.timeframe = { error: 'timeframe-W missing' };
        }

        var adjBtn = Array.prototype.find.call(document.querySelectorAll('button'), function (b) {
          return b.getAttribute('title') === 'نوع تعدیل قیمت';
        });
        if (adjBtn) {
          var beforeText = adjBtn.textContent.replace(/\s+/g, ' ').trim();
          adjBtn.click();
          await sleep(300);
          var rawItem = Array.prototype.find.call(document.querySelectorAll('.nn-dropdown-item'), function (it) {
            return it.textContent.indexOf('خام (بدون تعدیل)') >= 0;
          });
          if (rawItem) {
            rawItem.click();
            await sleep(1200);
            var afterBtn = Array.prototype.find.call(document.querySelectorAll('button'), function (b) {
              return b.getAttribute('title') === 'نوع تعدیل قیمت';
            });
            var cw2 = document.querySelector('[data-testid="chart-area"] canvas');
            d3.adjustment = {
              before: beforeText,
              after: afterBtn ? afterBtn.textContent.replace(/\s+/g, ' ').trim() : null,
              canvas: cw2 ? { w: cw2.width, h: cw2.height } : null,
            };
            out.states.d3 = d3;
            emit('d3_raw_mode', { label: d3.adjustment.after, canvas: d3.adjustment.canvas });
            await pauseForShot('d3_raw_mode');
            // restore the default functional series for the remaining pages
            if (afterBtn) {
              afterBtn.click();
              await sleep(250);
              var combItem = Array.prototype.find.call(document.querySelectorAll('.nn-dropdown-item'), function (it) {
                return it.textContent.indexOf('عملکردی') >= 0;
              });
              if (combItem) combItem.click();
              await sleep(800);
            }
          } else {
            d3.adjustment = { error: 'raw item missing', before: beforeText };
          }
        } else {
          d3.adjustment = { error: 'adjustment button missing' };
        }

        if (window.__BORS_SYMBOL2__) {
          var other = window.__BORS_SYMBOL2__;
          location.hash = '#/technical/' + encodeURIComponent(other);
          try {
            await waitFor(function () {
              var badge = document.querySelector('.nn-symbol-badge');
              return badge && badge.textContent.indexOf(other) >= 0
                && document.querySelector('[data-testid="chart-area"] canvas');
            }, 60000, 'symbol-switch');
            await waitFor(function () {
              var f = document.querySelector('[data-testid="fts-layer-freshness"]');
              return f && /[۰-۹0-9]+\s*کندل/.test(f.textContent || '');
            }, 90000, 'symbol-switch-fts');
            var ce = chartEntries();
            d3.symbol_switch = {
              symbol: other,
              toolbar: document.querySelector('.nn-symbol-badge').textContent.replace(/\s+/g, ' ').trim(),
              freshness: (document.querySelector('[data-testid="fts-layer-freshness"]') || {}).textContent || null,
              last_chart_api: ce.length ? ce[ce.length - 1] : null,
            };
          } catch (e) {
            d3.symbol_switch = { symbol: other, error: String(e).slice(0, 300) };
          }
          if (!d3.symbol_switch.error) {
            out.states.d3 = d3;
            emit('d3_symbol2_ready', { toolbar: d3.symbol_switch.toolbar });
            await pauseForShot('d3_symbol2_ready');
          }
          location.hash = '#/technical/' + encodeURIComponent(SYMBOL);
          await sleep(1200);
        }
        out.states.d3 = d3;
        emit('d3_checks_done');
      }
      await sleep(2500);

      emit('fundamental_nav_begin');
      location.hash = '#/fundamental/' + encodeURIComponent(SYMBOL);
      await waitFor(function () { return document.querySelector('[data-testid="fundamental-page"]'); }, 30000, 'fundamental-page');
      await waitFor(function () {
        return document.querySelector('[data-testid="fts-strategy-summary"]')
          || document.querySelector('[data-testid="holding-pnav-panel"]');
      }, 90000, 'fundamental-data');
      emit('fundamental_ready');
      (function () {
        function box(el) {
          if (!el) return null;
          var r = el.getBoundingClientRect();
          return {
            text: (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 1200),
            rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
            visible: r.width > 0 && r.height > 0,
          };
        }
        out.states.fundamental = {
          summary: box(document.querySelector('[data-testid="fts-strategy-summary"]')),
          holding: box(document.querySelector('[data-testid="holding-pnav-panel"]')),
          scroll_y: window.scrollY,
          page_text: (document.querySelector('[data-testid="fundamental-page"]') || {}).textContent
            ?.replace(/\s+/g, ' ').trim().slice(0, 2500) || null,
        };
      })();
      captureMetrics('fundamental_ready');
      out.states.fundamental_pause_ack = await pauseForShot('fundamental_ready');
      await sleep(2000);

      if (window.__BORS_D3_CHECKS__) {
        emit('market_status_nav_begin');
        location.hash = '#/market-status';
        try {
          await waitFor(function () {
            return document.querySelector('[data-testid="market-status-panel"]');
          }, 45000, 'market-status-panel');
          await sleep(2500);
          var mp = document.querySelector('[data-testid="market-status-panel"]');
          var txt = (mp ? mp.textContent : '').replace(/\s+/g, ' ').trim();
          out.states.market_status = {
            text: txt.slice(0, 2500),
            panels: document.querySelectorAll('[data-testid^="market-status"]').length,
            resources: apiResources().filter(function (r) {
              return /market\/|status|indices|tedpix|sync-state/i.test(r.name || '');
            }).slice(-20),
          };
          emit('market_status_ready', { panels: out.states.market_status.panels });
          await pauseForShot('market_status_ready');
        } catch (e) {
          out.states.market_status = { error: String(e).slice(0, 300) };
        }
      }

      out.resources = apiResources();
      out.finished_at = Date.now();
      out.ok = !out.errors.length;
      post({ kind: 'final', run_id: RUN, payload: out });
    } catch (e) {
      out.errors.push({ kind: 'probe', text: String(e && e.stack || e).slice(0, 800), at_ms: Date.now() });
      out.resources = apiResources();
      out.finished_at = Date.now();
      out.ok = false;
      post({ kind: 'final', run_id: RUN, payload: out });
    }
  }

  run();
})();
