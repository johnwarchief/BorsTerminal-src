// In-page probe for the M2 updater acceptance run. It drives the shell's real
// tiny.app.update API (TinyJS runtime, not a harness stand-in) against a
// loopback manifest and reports every step to the external collector.
(function () {
  if (window.__borsM2UpdateProbe) return;
  window.__borsM2UpdateProbe = true;

  var COLLECTOR = 'http://127.0.0.1:__BORS_COLLECTOR__/probe';
  var RUN = String(Date.now()) + '-' + Math.random().toString(36).slice(2, 8);

  function post(kind, extra) {
    var body = { kind: kind, run_id: RUN, url: location.href, at_ms: Date.now() };
    if (extra) for (var k in extra) body[k] = extra[k];
    try {
      fetch(COLLECTOR, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify(body),
      }).catch(function () {});
    } catch (e) { /* collector unavailable must not affect the page */ }
  }

  function sleep(ms) {
    return new Promise(function (r) { setTimeout(r, ms); });
  }

  async function waitFor(fn, timeout, label) {
    var end = Date.now() + timeout;
    while (Date.now() < end) {
      var v = false;
      try { v = fn(); } catch (e) { v = false; }
      if (v) return v;
      await sleep(200);
    }
    throw new Error('timeout: ' + label);
  }

  async function run() {
    post('m2_update_started', { origin: location.origin });
    try {
      await waitFor(function () {
        return window.tiny && window.tiny.app && window.tiny.app.update;
      }, 180000, 'tiny.app.update');
      var info = await window.tiny.app.info();
      post('m2_update_info', { info: info });
      var checked = await window.tiny.app.update.check();
      post('m2_update_check', { result: checked });
      if (!checked || !checked.available) {
        post('m2_update_no_update', { result: checked });
        return;
      }
      post('m2_update_install_begin', { latest: checked.latest, notes: checked.notes || null });
      try {
        var returned = await window.tiny.app.update.install();
        post('m2_update_install_returned', { result: returned });
      } catch (e) {
        post('m2_update_install_error', {
          error: String(e && e.stack || e).slice(0, 1200),
          message: String(e && e.message || e).slice(0, 600),
        });
      }
    } catch (e) {
      post('m2_update_probe_error', {
        error: String(e && e.stack || e).slice(0, 1200),
        message: String(e && e.message || e).slice(0, 600),
      });
    }
  }

  run();
})();
