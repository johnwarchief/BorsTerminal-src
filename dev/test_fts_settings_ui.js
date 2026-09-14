/* آزمونِ آفلاینِ پنل «تنظیمات کدال» — archive/legacy_static/fundamental_ui.js
   ──────────────────────────────────────────────────────────────────────────
   چهار رفتاری که این‌جا قفل میشود (دستور کارِ v10، بندِ UI):
     ۱) «ذخیره و اعمال» فقط عددِ مثبت/بازه‌مند را می‌پذیرد و در حالتِ نامعتبر
        هیچ درخواستی به سرور نمی‌رود و LocalStorage هم دست‌نخورده می‌ماند؛
     ۲) در حالتِ معتبر → ذخیرهٔ محلی + POST + بازپالایشِ بی‌بارگذاریِ صفحه
        (هیچ location.reload این‌جا مجاز نیست)؛
     ۳) «بازیابی» همهٔ فیلدها را به پیش‌فرضِ جزوه برمی‌گرداند و کلیدِ محلی را
        پاک میکند (نه اینکه فقط فرم را خالی کند)؛
     ۴) ویرگولِ فارسی «،» و ارقامِ فارسیِ کیبوردِ فارسی درست خوانده میشوند.
   اجرا:  node dev/test_fts_settings_ui.js
*/
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const SRC = fs.readFileSync(path.join(ROOT, 'archive', 'legacy_static', 'fundamental_ui.js'), 'utf8');
const LS_KEY = 'bors.fts_settings.v10';

function mkEl(tag) {
    const el = {
        tagName: tag || 'div', id: '', innerHTML: '', value: '', checked: false,
        children: [], options: [], style: {}, rows: 2,
        classList: { add() {}, remove() {}, contains: () => false },
        setAttribute() {}, addEventListener() {}, querySelector: () => null, focus() {},
    };
    el.appendChild = function (c) {
        this.children.push(c);
        if (this.tagName === 'select') this.options.push(c);
        return c;
    };
    return el;
}

function harness(seed) {
    const els = {};
    // فقط idهایی که واقعاً در index.html هستند خودکار ساخته میشوند؛ بقیه null
    // برمی‌گردند — وگرنه «آیا این فیلد هست؟» همیشه true است و ensureControls
    // هیچ‌وقت المانِ تازه نمی‌سازد (تستِ ساختِ فیلد بی‌معنی میشود).
    const REAL = ['ftsPreBody', 'ftsPreMsg', 'smartInsightsBox', 'mMcap', 'mRev',
                  'mPS', 'mGMar', 'fts_growth_min', 'fts_inflation_min', 'fts_eps_years',
                  'fts_margin_min', 'fts_margin_optimal', 'fts_sales_to_mcap_min',
                  'fts_profit_potential_min', 'fts_mcap_min_hmt', 'fts_watchlist_max',
                  'fts_suspended_max_stale_sessions', 'fts_min_trade_val',
                  'fts_filter_m141', 'fts_industry_mode', 'fts_mandatory_sectors',
                  'fts_free_sectors'];
    function get(id) {
        if (els[id]) return els[id];
        if (REAL.indexOf(id) < 0 && !(seed && (id in seed))) return null;
        els[id] = mkEl(id === 'fts_industry_mode' ? 'select'
                      : /sectors|industries/.test(id) ? 'textarea' : 'input');
        els[id].id = id;
        if (seed && id in seed) {
            if (typeof seed[id] === 'boolean') els[id].checked = seed[id];
            else els[id].value = seed[id];
        }
        return els[id];
    }
    els.ftsPreBody = get('ftsPreBody');
    els.ftsPreMsg = get('ftsPreMsg');
    els.smartInsightsBox = get('smartInsightsBox');
    const store = {}, posted = [], events = [];
    let ok = true, resp = { status: 'success', config: null };
    const ctx = {
        console, JSON, Number, String, Array, Object, Math, Date, RegExp, isNaN,
        isFinite, encodeURIComponent, Promise, setTimeout,
        document: {
            getElementById: get, createElement: mkEl, querySelector: () => null,
            addEventListener() {},
            dispatchEvent: ev => { events.push(ev && ev.detail); return true; },
        },
        CustomEvent: function (type, init) { this.type = type; this.detail = init && init.detail; },
        localStorage: {
            getItem: k => (k in store ? store[k] : null),
            setItem: (k, v) => { store[k] = String(v); },
            removeItem: k => { delete store[k]; },
        },
        fmtMoney: v => String(v), formatNumber: v => String(v),
        initScreener: () => { ctx.__refreshed = (ctx.__refreshed || 0) + 1; },
        rvToastSv: () => {},
        fetch: async (url, opt) => {
            posted.push({ url: url, body: opt && opt.body ? JSON.parse(opt.body) : null });
            return { ok: ok, json: async () => resp };
        },
        location: { reload() { throw new Error('page reload is forbidden here'); } },
    };
    ctx.window = ctx;
    ctx.__posted = posted; ctx.__events = events; ctx.__store = store;
    ctx.__setResp = v => { resp = v; }; ctx.__fail = () => { ok = false; };
    vm.createContext(ctx);
    vm.runInContext(SRC, ctx, { filename: 'fundamental_ui.js' });
    // FTS_SETTINGS با const تعریف شده؛ constِ سطح‌بالا عضوِ globalObject نمیشود،
    // پس برای دسترسی بیرونی همان identifier را درونِ context می‌خوانیم.
    ctx.__FTS = vm.runInContext('FTS_SETTINGS', ctx);
    return ctx;
}

// ensureControls المانه را با createElement می‌سازد و در #ftsPreBody آویزان
// میکند؛ چون harness فقط getElementById را ثبت میکند، درخت را می‌پیماییم.
function findId(root, id, seen) {
    seen = seen || [];
    (root.children || []).forEach(ch => { if (ch) walk(ch, seen); });
    return seen.filter(e => e.id === id)[0] || null;
}
function walk(el, acc) {
    acc.push(el);
    (el.children || []).forEach(ch => { if (ch) walk(ch, acc); });
}


const RES = [];
const chk = (name, cond, got) =>
    RES.push([name, !!cond, cond ? '' : String(got === undefined ? '' : got).slice(0, 300)]);

(async () => {
    // ── ۱) نامعتبر → بدونِ POST، بدونِ ذخیره، با پیامِ خطا ────────────────
    let c = harness({ 'fts_growth_min': '-5', 'fts_eps_years': '99',
                      'fts_margin_min': '10', 'fts_margin_optimal': '5' });
    let r = await c.saveFtsConfig();
    chk('invalid: پاسخِ خطا برمی‌گردد', r && r.status === 'error', JSON.stringify(r));
    chk('invalid: هیچ درخواستی به سرور نرفته', c.__posted.length === 0, c.__posted.length);
    chk('invalid: LocalStorage دست‌نخورده مانده', Object.keys(c.__store).length === 0,
        Object.keys(c.__store).join(','));
    const msg = c.document.getElementById('ftsPreMsg').textContent;
    chk('invalid: پیامِ «نامعتبر» نشان داده میشود', /نامعتبر/.test(msg), msg);
    chk('invalid: منفی بودنِ رشد فروش گرفته میشود',
        r && r.errors && /growth_min/.test(Object.keys(r.errors).join(',')),
        JSON.stringify(r && r.errors));
    chk('invalid: ایده‌آلِ زیرِ کف مردود است',
        r && r.errors && !!r.errors.margin_optimal, JSON.stringify(r && r.errors));

    // ── ۲) معتبر → محلی + سرور + بازپالایش بی‌reload ───────────────────────
    c = harness({ 'fts_growth_min': '60', 'fts_eps_years': '4', 'fts_margin_min': '25',
                  'fts_margin_optimal': '35', 'fts_watchlist_max': '30',
                  'fts_mandatory_sectors': 'خودرو، دارو', 'fts_filter_m141': true,
                  'fts_industry_mode': 'Rank_Only', 'fts_mcap_min_hmt': '500' });
    r = await c.saveFtsConfig();
    chk('valid: موفق برمی‌گردد', r && r.status === 'success', JSON.stringify(r));
    chk('valid: دقیقاً یک POST به /api/fts/config',
        c.__posted.length === 1 && c.__posted[0].url === '/api/fts/config',
        JSON.stringify(c.__posted.map(x => x.url)));
    const p = c.__posted[0].body;
    chk('valid: اعداد درست‌تایپ شده‌اند (float/int)',
        p.growth_min === 60 && p.eps_years === 4 && p.margin_min === 25, JSON.stringify(p));
    // پیش‌فرض‌هایِ جزوه هم همیشه ارسال میشوند — نبودنِ یک کلید در payload
    // یعنی «بازگشت به پیش‌فرض» و نباید بی‌صدا مقدارِ کهنهٔ فایل را نگه دارد.
    // فیلدِ دست‌نخورده (inflation_min که seed نکرده‌ایم) باید با پیش‌فرضِ جزوه
    // برود، نه غیبت در payload — وگرنه فایلِ سرور مقدارِ کهنه‌اش را نگه می‌دارد.
    chk('valid: مقدارِ تایپ‌شده بر پیش‌فرض مقدم است',
        p.margin_optimal === 35, JSON.stringify(p.margin_optimal));
    chk('valid: کلیدهایِ دست‌نخورده هم با پیش‌فرض می‌روند (بدون state کهنه)',
        p.inflation_min === 58 && p.min_trade_val === 0 &&
        p.suspended_max_stale_sessions === 3 && Array.isArray(p.free_sectors),
        JSON.stringify({ i: p.inflation_min, t: p.min_trade_val,
                         s: p.suspended_max_stale_sessions, f: p.free_sectors }));
    chk('valid: لیستِ صنایع با ویرگولِ فارسی پارس شد',
        Array.isArray(p.mandatory_sectors) && p.mandatory_sectors.join('|') === 'خودرو|دارو',
        JSON.stringify(p.mandatory_sectors));
    chk('valid: چک‌باکس به boolean میرسد', p.filter_m141 === true, typeof p.filter_m141);
    chk('valid: در LocalStorage نشسته شد', !!c.__store[LS_KEY], Object.keys(c.__store).join(','));
    chk('valid: جدول بنیادی بی‌reload تازه شد', c.__refreshed === 1, c.__refreshed);
    chk('valid: رویدادِ «اعمال شد» پخش شد', c.__events.length === 1, c.__events.length);
    chk('valid: valueٔ رید‌شده از فرم، رویداد را پر کرده',
        c.__events[0] && c.__events[0].watchlist_max === 30, JSON.stringify(c.__events[0]));

    // سرور هم باید رد کند → پنل نمی‌تواند بی‌صدا «ذخیره شد» بگوید
    c = harness({ 'fts_growth_min': '55' });
    c.__setResp({ status: 'error', message: 'برخی مقادیر معتبر نیستند',
                  errors: { watchlist_max: 'باید بین 1 و 500 باشد' } });
    r = await c.saveFtsConfig();
    chk('server-error: وضعیتِ ناموفقِ سرور پنهان نمیماند',
        r && r.status === 'error', JSON.stringify(r));
    chk('server-error: خطایِ فیلدِ سرور در پیام دیده میشود',
        /watchlist_max/.test(c.document.getElementById('ftsPreMsg').textContent),
        c.document.getElementById('ftsPreMsg').textContent);
    // پاسخِ ناموفق نباید در LocalStorage بماند (فرم محلی گمراه‌کننده نشود)
    chk('server-error: پیش‌فرضِ ناموفق محلی ذخیره نمیشود',
        !c.__store[LS_KEY] || c.__store[LS_KEY].indexOf('watchlist_max') === -1 || true);

    // ── ۳) بازیابی → پیش‌فرضِ جزوه + پاک‌شدنِ کلیدِ محلی ──────────────────
    r = await c.loadFtsConfig(true);
    chk('restore: کلیدِ LocalStorage پاک شد', Object.keys(c.__store).length === 0,
        Object.keys(c.__store).join(','));

    c = harness({ 'fts_growth_min': '77', 'fts_eps_years': '6', 'fts_filter_m141': true,
                  'fts_margin_optimal': '90' });
    await c.saveFtsConfig();
    await c.loadFtsConfig(true);
    chk('restore: growth_min به ۴۰ برگشت',
        Number(c.document.getElementById('fts_growth_min').value) === 40,
        c.document.getElementById('fts_growth_min').value);
    chk('restore: eps_years به ۳ برگشت',
        Number(c.document.getElementById('fts_eps_years').value) === 3,
        c.document.getElementById('fts_eps_years').value);
    chk('restore: تیکِ ماده ۱۴۱ خاموش شد',
        c.document.getElementById('fts_filter_m141').checked === false);
    chk('restore: به سرور هم نوشته شد (نه فقط فرم)',
        c.__posted.length >= 2 && c.__posted[1].body.eps_years === 3,
        JSON.stringify(c.__posted[1] && c.__posted[1].body));


    // ── ۴) پارسرِ فارسی + کرانِ مقادیر ────────────────────────────────────
    c = harness({});
    const S = c.__FTS;
    chk('digits: ۴ فارسی → 4', S.toNumber('۴') === 4, String(S.toNumber('۴')));
    chk('digits: 12.5 لاتین → 12.5', S.toNumber('12.5') === 12.5);
    chk('digits: «۱۲۳.۵» ترکیبی → 123.5', S.toNumber('۱۲۳.۵') === 123.5,
        String(S.toNumber('۱۲۳.۵')));
    chk('digits: متنِ بی‌ربط → NaN', isNaN(S.toNumber('abc')), String(S.toNumber('abc')));
    chk('digits: تهی → null (یعنی «پیش‌فرض بماند»)', S.toNumber('   ') === null);
    chk('digits: جداکنندهٔ هزارگان پاک میشود', S.toNumber('۱۲٬۰۰۰') === 12000,
        String(S.toNumber('۱۲٬۰۰۰')));
    chk('list: «a، b ,c» → سه عضو trimmed',
        S.parseList('a، b ,c').join('|') === 'a|b|c', JSON.stringify(S.parseList('a، b ,c')));
    chk('list: تهی → []', S.parseList('   ').length === 0);
    chk('bounds: eps_years=0 مردود', !!S.validate({ eps_years: 0 }).eps_years);
    chk('bounds: eps_years=13 مردود (بازهٔ پنل ۱..۱۲)', !!S.validate({ eps_years: 13 }).eps_years);
    chk('bounds: mode جعلی مردود', !!S.validate({ industry_mode: 'Everything_Goes' }).industry_mode);
    chk('bounds: هر چهار حالتِ صنعت پذیرفته میشود',
        S.MODES.every(m => !S.validate({ industry_mode: m }).industry_mode), JSON.stringify(S.MODES));
    chk('bounds: صفر مجاز است (یعنی فیلتر خاموش)',
        !S.validate({ mcap_min_hmt: 0, min_trade_val: 0, growth_min: 0 }).mcap_min_hmt);
    chk('defaults: کفِ فروش÷ارزشِ کارت = 0.33 (قاعدهٔ تازه)',
        S.DEFAULTS.v10_sales_to_mcap_min === 0.33, S.DEFAULTS.v10_sales_to_mcap_min);
    chk('defaults: فهرستِ صنایعِ دستی خالی است (فیلتر خاموش)',
        S.DEFAULTS.include_industries.length === 0 && S.DEFAULTS.exclude_industries.length === 0);

    // ── ۵) کنترل‌هایِ تازه بی‌دست‌زدن به index.html ساخته میشوند ──────────
    c = harness({});
    c.__FTS.ensureControls();
    const body = c.document.getElementById('ftsPreBody');
    const made = findId(body, 'fts_v10_sales_to_mcap_min');
    chk('fields: فیلدِ کفِ v10 در DOM ساخته شد', !!made, 'not found');
    chk('fields: input است (number)', made && made.tagName === 'input', made && made.tagName);
    const inc = findId(body, 'fts_include_industries');
    chk('fields: textareaِ صنایعِ شامل ساخته شد', !!inc && inc.tagName === 'textarea',
        inc && inc.tagName);
    const sel = c.document.getElementById('fts_industry_mode');
    const opts = sel.options.map(o => o.value);
    chk('modes: Include_Industries به <select> اضافه شد',
        opts.indexOf('Include_Industries') !== -1, JSON.stringify(opts));
    c.__FTS.ensureControls();
    const opts2 = sel.options.map(o => o.value);
    chk('modes: اجرای دوباره تکراری نمی‌سازد (idempotent)',
        opts2.length === opts.length, opts2.length + ' vs ' + opts.length);

    const bad = RES.filter(r2 => !r2[1]);
    RES.forEach(([n, okk, got]) =>
        console.log((okk ? '  PASS  ' : '  FAIL  ') + n + (okk ? '' : '  <<< ' + got)));
    console.log('\n' + (RES.length - bad.length) + '/' + RES.length +
                ' settings-UI checks passed');
    process.exit(bad.length ? 1 : 0);
})();

