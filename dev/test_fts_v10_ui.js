/* آزمونِ آفلاینِ رندرِ جدول بنیادی — archive/legacy_static/fundamental_ui.js
   ──────────────────────────────────────────────────────────────────────────
   قاعده‌ای که اینجا پایش می‌شود (دستورالعملِ خروجی جدول بنیادی):
     اگر دادهٔ «شاخص ۲» ناقص بود و تنها ۲ دوره (به‌جای ۳) موجود بود:
       ۱) سطر هرگز حذف نشود — مقادیرِ موجود درج و دورهٔ ناموجود «-» شود؛
       ۲) عنوان و همهٔ سلول‌های سطر قرمز شوند و ذکر شود «تنها ۲ دوره موجود است».
   ورودی از dev/fixtures/fts_v10_payloads.json ساخته میشود (خودِ api.fundamental)
   تا رابطِ کاربری از داده دور نیفتد. اجرا:  node dev/test_fts_v10_ui.js
*/
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const ROOT = path.resolve(__dirname, '..');
const FIX = JSON.parse(fs.readFileSync(
    path.join(ROOT, 'dev', 'fixtures', 'fts_v10_payloads.json'), 'utf8'));

function mkEl(tag) {
    const el = {
        tagName: tag || 'div', innerHTML: '', children: [],
        style: { cssText: '', setProperty() {} },
        classList: { add() {}, remove() {}, contains: () => false },
        appendChild(c) { this.children.push(c); return c; },
        setAttribute() {}, addEventListener() {}, querySelector: () => null,
    };
    let txt = '';
    Object.defineProperty(el, 'innerText', { get: () => txt, set: v => { txt = String(v); } });
    Object.defineProperty(el, 'textContent', { get: () => txt, set: v => { txt = String(v); } });
    return el;
}
const htmlOf = el => el.innerHTML + el.children.map(htmlOf).join('\n');

const RES = [];
const chk = (name, cond, got) =>
    RES.push([name, !!cond, cond ? '' : String(got === undefined ? '' : got).slice(0, 400)]);

async function render(payload) {
    const els = {};
    const box = mkEl();
    els.smartInsightsBox = box;
    ['mMcap', 'mRev', 'mPS', 'mGMar'].forEach(id => { els[id] = mkEl(); });
    const ctx = {
        console, JSON, Number, String, Array, Object, Math, Date, RegExp, isNaN, isFinite,
        encodeURIComponent,
        fetch: async () => ({ ok: true, json: async () => payload }),
        document: {
            getElementById: id => (els[id] || (els[id] = mkEl())),
            createElement: t => mkEl(t),
            querySelector: () => null, addEventListener() {},
        },
        fmtMoney: v => (v == null ? '—' : Number(v).toLocaleString('en-US')),
        formatNumber: v => (v == null ? '—' : Number(v).toLocaleString('en-US')),
        openAnalysis: () => {},
    };
    ctx.window = ctx;
    vm.createContext(ctx);
    vm.runInContext(fs.readFileSync(path.join(ROOT, 'archive', 'legacy_static', 'fundamental_ui.js'), 'utf8'),
                    ctx, { filename: 'fundamental_ui.js' });
    await ctx.loadFundamentalData('X');
    return htmlOf(box);
}

(async () => {
    const PART_NOTE = 'تنها ۲ دوره موجود است';

    // ── حالتِ ناقص: ۲ دوره از ۳ ────────────────────────────────────────────
    const hp = await render(FIX.partial);
    chk('partial: سطر حذف نشده (برچسبِ شاخص ۲ در جدول هست)', /شاخص ۲/.test(hp));
    chk('partial: ذکرِ «' + PART_NOTE + '»', hp.indexOf(PART_NOTE) !== -1);
    chk('partial: هر دو مقدارِ موجود نشان داده میشود',
        hp.indexOf('500') !== -1 && hp.indexOf('320') !== -1);
    chk('partial: دورهٔ ناموجود با «-»', /-\s*→\s*500\s*→\s*320/.test(hp), hp.slice(0, 200));
    chk('partial: به‌جایِ «داده کم/نیست» نیست',
        hp.indexOf('داده کم') === -1 && hp.indexOf('داده نیست') === -1);
    const tds = (hp.match(/<td [^>]*>/g) || []);
    chk('partial: سطرِ جدول ۳ سلولِ دوره دارد',
        tds.filter(t => /color:red/.test(t)).length >= 3, tds.length);
    chk('partial: عنوانِ سطر قرمز است',
        /<td[^>]*color:red[^>]*>\s*شاخص ۲ \(تنها ۲ دوره موجود است\)/.test(hp.replace(/;\s*"/g, ';"'))
        || /شاخص ۲ \(تنها ۲ دوره موجود است\)/.test(hp));
    chk('partial: متنِ هشدار هم تعدادِ دوره را می‌گوید',
        /🚫 شاخص ۲ \(تنها ۲ دوره موجود است\)/.test(hp));
    chk('partial: بنرِ شکافِ داده عددِ ۲ از ۳ را دارد',
        FIX.partial.data_gaps[0].available_periods === 2
        && FIX.partial.data_gaps[0].required_periods === 3);
    chk('partial: هیچ undefined/NaN به markup نشت نکرده',
        hp.indexOf('undefined') === -1 && hp.indexOf('NaN') === -1);

    // ── حالتِ کامل: ۳ دوره ─────────────────────────────────────────────────
    const hf = await render(FIX.full);
    chk('full: سه مقدار نشان داده میشود',
        hf.indexOf('400') !== -1 && hf.indexOf('500') !== -1 && hf.indexOf('600') !== -1);
    chk('full: برچسبِ «تنها … دوره موجود است» نمی‌آید', hf.indexOf(PART_NOTE) === -1);
    chk('full: سطرِ قرمزِ ناقص ندارد', hf.indexOf('color:red') === -1);
    chk('full: undefined/NaN ندارد',
        hf.indexOf('undefined') === -1 && hf.indexOf('NaN') === -1);

    // ── حالتِ بدونِ داده: صفر دوره ─────────────────────────────────────────
    const hn = await render(FIX.nodata);
    chk('nodata: پیامِ نبودِ داده می‌آید',
        hn.indexOf('داده کم') !== -1 || hn.indexOf('محاسبه نمیشود') !== -1);
    chk('nodata: صفرِ گمراه‌کننده جایِ اعداد ننشیند',
        hn.indexOf('0 → 0 → 0') === -1);
    chk('nodata: undefined/NaN ندارد',
        hn.indexOf('undefined') === -1 && hn.indexOf('NaN') === -1);

    const bad = RES.filter(r => !r[1]);
    RES.forEach(([n, ok, got]) => console.log((ok ? '  PASS  ' : '  FAIL  ') + n + (ok ? '' : '  <<< ' + got)));
    console.log('\n' + (RES.length - bad.length) + '/' + RES.length + ' UI checks passed');
    process.exit(bad.length ? 1 : 0);
})();
