let marketData = [];          // دادهٔ بازار (از /api/market) — بعد از استریپ 1-118 دوباره تعریف شد
let filteredData = [];        // پس از فیلترها
let sortCol = '';
let sortAsc = false;
let refreshInterval;
let activeFilters = new Set();

// تبدیل میلادی → جلالی (در استریپ 1-118 حذف شد ولی updateMarketDateInfo استفاده میکند)
function gregorianToJalaaliParts(gy, gm, gd) {
    const j = Jalaali.toJalaali(gy, gm, gd);
    return { jy: j.jy, jm: j.jm, jd: j.jd };
}
let screenerData = [];
let filteredScreenerData = [];
let screenerNextFetch = 0;   // throttle: at most one /api/screener per 60s
let lastNewCnt = -1;         // compare extra.new from sync status
let prevCodalActive = false; // detect sync-completion transition
let sortColScreener = 'score';
let sortAscScreener = false;

/* ========== STATE: یک سیستم واحد برای نگهداشتن همهٔ تنظیمات کاربر (بین اجراها) ==========
   همهٔ چیزهایی که کاربر تنظیم میکند: فونت، فیلترها، ستونها، ترتیب آنها، تم،
   سایدبار، فیلترهای سفارشی، کشدش و ... در localStorage زیر یک کلید ذخیره میشود. */
const STATE_KEY = 'bors_state_v2';
let _STATE = null;
function stGet(k, def) {
    try {
        if (_STATE === null) _STATE = JSON.parse(localStorage.getItem(STATE_KEY) || '{}') || {};
    } catch (e) { _STATE = {}; }
    return (k in _STATE) ? _STATE[k] : def;
}
function stSet(k, v) {
    try {
        if (_STATE === null) _STATE = JSON.parse(localStorage.getItem(STATE_KEY) || '{}') || {};
        _STATE[k] = v;
        localStorage.setItem(STATE_KEY, JSON.stringify(_STATE));
    } catch (e) {}
}
// v9.7: حذف یک کلید از همان بلاوب.
// بدون این تابع کدها localStorage.removeItem('tech_...') می‌زدند که هیچ‌وقت
// وجود نداشته (داده داخل bors_state_v2 است) → «پاک شد» فقط ظاهری بود.
function stDel(k) {
    try {
        if (_STATE === null) _STATE = JSON.parse(localStorage.getItem(STATE_KEY) || '{}') || {};
        delete _STATE[k];
        localStorage.setItem(STATE_KEY, JSON.stringify(_STATE));
    } catch (e) {}
}
// مهاجرت آسان: کلیدهای قدیمی localStorage → STATE

function _stMigrate(oldKey, newKey, raw) {
    if (stGet(newKey, null) !== null) return;
    try {
        const v = localStorage.getItem(oldKey);
        if (v !== null && raw) stSet(newKey, v);
        else if (v !== null) stSet(newKey, JSON.parse(v));
    } catch (e) {}
}

function applyFontScale(v) {
    // فونت سراسری برنامه (documentElement) — مقیاس نسبی، اعمال روی همه‌چیز
    document.documentElement.style.fontSize = (v / 100 * 16) + 'px';
    const el = document.getElementById('fontScaleVal');
    if (el) el.innerText = v + '%';
    document.querySelectorAll('[id^="fontScaleNum_"]').forEach(function (n) { n.value = v + '%'; });
    try { stSet('fontScale', v); } catch (e) {}
    // هماهنگی استپرهای فونت (فقط fontScaleNum_*) — اسلایدرهای ثانیه/دقیقه نباید دست بخورند
}
function setFontForView(view) {
    // فونت جدا برای هر تب (STATE per view)
    let v = 100;
    try {
        v = parseInt(stGet('fontScale_' + view, localStorage.getItem('fontScale_' + view) || '100'), 10);
        stSet('fontScale_' + view, v);
    } catch (e) {}
    if (isNaN(v) || v < 60 || v > 130) v = 100;
    applyFontScale(v);
}

function toggleExportMenu() {
    const m = document.getElementById('exportMenu');
    if (m) m.style.display = m.style.display === 'none' ? 'block' : 'none';
}
function downloadExport(fmt) {
    const m = document.getElementById('exportMenu');
    if (m) m.style.display = 'none';
    // شناسایی تب فعال: بازار یا کدال؟ rows درست را بفرست
    const inScreener = document.getElementById('screenerView') && document.getElementById('screenerView').style.display !== 'none';
    const rows = inScreener ? buildScreenerRows(filteredScreenerData || []) : buildMarketRows(filteredData || []);
    fetch('/api/export', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ fmt, title: inScreener ? 'screener' : 'market', rows })
    }).then(r => {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.blob();
    }).then(blob => {
        if (!blob || blob.size === 0) throw new Error('پاسخ خالی');
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'borsagent_' + (inScreener ? 'screener' : 'market') + '.' + (fmt === 'docx' ? 'docx' : fmt);
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    }).catch(e => {
        // fallback: CSV ساده (همیشه کار میکند) — جلوگیری از دانلود json
        const csv = rows.map(r => r.map(c => '"' + String(c === null || c === undefined ? '' : c).replace(/"/g, '""') + '"').join(',')).join('\n');
        const blob = new Blob(['\ufeff' + csv], { type: 'text/csv;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'borsagent_fallback_' + Date.now() + '.csv';
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    });
}

function buildScreenerRows(data) {
    const head = ['نماد','نام','صنعت','۱ رشد فروش٪','۲ روند EPS','۳ حاشیه ناخالص٪',
                  '۴ فروش÷ارزش','۴ پتانسیل سود٪','۵ نوع قیمت‌گذاری','ارزش(همت)','امتیاز /۵','حذف‌شده'];
    const rows = [head];
    const MODEFA = { free: 'آزاد/بورس کالا', mandatory: 'دستوری', neutral: 'خنثی' };
    data.slice(0, 5000).forEach(r => {
        rows.push([
            r.symbol, r.name || '', r.sector_name || '',
            r.rev_growth != null ? r.rev_growth.toFixed(1) : '—',
            r.eps_series ? r.eps_series.join(' → ') : 'بدون داده',
            r.gross_margin != null ? r.gross_margin.toFixed(1) : '—',
            r.sales_to_mcap != null ? r.sales_to_mcap.toFixed(2) : '—',
            r.profit_potential_pct != null ? r.profit_potential_pct.toFixed(1) : '—',
            MODEFA[r.pricing_mode] || '—',
            r.mcap > 0 ? (r.mcap / 1e13).toFixed(2) : '—',
            r.score ?? '', r.excluded ? (r.exclusion_reasons || 'بله') : '—'
        ]);
    });
    rows.push(['تعداد ردیف', data.length]);
    return rows;
}

function buildMarketRows(data) {
    const head = ['نماد','نام','صنعت','آخرین','پایانی','تغییر٪','P/E','EPS','حجم','ارزش(همت)','تعداد معاملات'];
    const rows = [head];
    data.slice(0, 5000).forEach(r => {
        rows.push([
            r.symbol, r.name || '', r.sector_name || '',
            r.p_last ?? '', r.p_closing ?? '', r.percent_change ?? '',
            r.pe ?? '', r.eps ?? '', r.q_tot_tran ?? '',
            r.q_tot_cap ? (r.q_tot_cap / 1e12).toFixed(2) : '', r.z_tot_tran ?? ''
        ]);
    });
    rows.push(['...']);
    rows.push(['تعداد ردیف', data.length]);
    return rows;
}

function downloadSymbolReport(symbol) {
    // گزارش کامل تحلیل یک نماد (متریک + شاخص‌ها + تاریخچه) — با fallback GET
    fetch('/api/fundamental/' + encodeURIComponent(symbol))
        .then(r => r.json())
        .then(j => {
            if (!j || j.status === 'error' || !j.insights) {
                throw new Error(j && j.message ? j.message : 'داده نیامد');
            }
            const rows = [['گزارش', 'تحلیل کامل ' + symbol]];
            if (j.metrics) {
                rows.push(['ارزش بازار (همت)', j.metrics.mcap ? (j.metrics.mcap / 1e13).toFixed(2) : '—']);
                rows.push(['فروش (میلیون ریال)', j.metrics.revenue ?? '—']);
                rows.push(['حاشیه ناخالص ٪', j.metrics.gross_margin ?? '—']);
                rows.push(['ROE ٪', j.metrics.roe ?? '—']);
                rows.push(['نسبت P/S', j.metrics.ps ?? '—']);
                rows.push(['تعداد صورت‌های مالی', j.fs_count ?? 0]);
            }
            rows.push(['']);
            rows.push(['شاخص', 'نتیجه']);
            (j.insights || []).forEach(i => rows.push(['شاخص ' + (i.step || '—'), (i.title || '') + ' | ' + String(i.text || '').replace(/<br>/g, ' ⏎ ').replace(/<[^>]+>/g, '')]));
            if (j.history && j.history.length) {
                rows.push(['']);
                rows.push(['تاریخچه صورت‌های مالی:', '']);
                rows.push(['دوره', 'فروش', 'سود ناخالص', 'سود خالص', 'EPS', 'اطلاعیه']);
                (j.history || []).forEach(h => rows.push([
                    h.period_end || '', h.revenue ?? '', h.gross_profit ?? '', h.net_profit ?? '', h.eps ?? '', '#' + (h.tracing_no || '')
                ]));
            }
            return fetch('/api/export', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ fmt: 'xlsx', title: 'analysis_' + symbol, rows })
            }).then(r => {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.blob();
            }).then(blob => {
                if (!blob || blob.size === 0) throw new Error('خالی');
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'borsagent_analysis_' + symbol + '.xlsx';
                document.body.appendChild(a);
                a.click();
                a.remove();
                URL.revokeObjectURL(url);
            });
        })
        .catch(() => {
            // fallback: GET سرور
            const a = document.createElement('a');
            a.href = '/api/export?fmt=xlsx&view=fundamental&symbol=' + encodeURIComponent(symbol);
            a.download = '';
            document.body.appendChild(a);
            a.click();
            a.remove();
        });
}

/* ---------- فیلترهای سفارشی (فرمول کاربر — همان لحظه) ---------- */
let customFilters = [];
try { customFilters = JSON.parse(stGet('customFilters', localStorage.getItem('customFilters')) || '[]'); } catch (e) {}

function addCustomFilter() {
    const nameEl = document.getElementById('customFilterName');
    const exprEl = document.getElementById('customFilterExpr');
    const emojiEl = document.getElementById('customFilterEmoji');
    const name = (nameEl.value || '').trim();
    const expr = (exprEl.value || '').trim();
    const emoji = (emojiEl.value || '').trim() || '🧪';
    if (!name || !expr) { alert('نام و فرمول را وارد کن'); return; }
    // اعتبارسنجی: فقط فیلدهای مجاز و عملگرها (ضد تزریق)
    const allowed = /^[a-z_0-9><=&\s|().>%+.-]+$/i;
    if (!allowed.test(expr)) { alert('فرمول فقط می‌تواند: فیلدها + اعداد + > < >= <= == && || | ( ) باشد'); return; }
    customFilters.push({ id: 'cf' + Date.now(), name, expr, emoji });
    saveCustomFilters();
    nameEl.value = ''; exprEl.value = ''; emojiEl.value = '';
    renderCustomFilters();
    applyFilters();
}

function removeCustomFilter(id) {
    const f = customFilters.find(x => x.id === id);
    if (!f) return;
    // تایید قبل از حذف همیشگی
    if (!confirm(`مطمئنی می‌خوای فیلتر «${f.name}» رو برای همیشه حذف کنی؟`)) return;
    customFilters = customFilters.filter(x => x.id !== id);
    saveCustomFilters();
    renderCustomFilters();
    applyFilters();
    rvToastSv('✕ فیلتر حذف شد: ' + f.name);
}

function saveCustomFilters() {
    try { stSet('customFilters', JSON.stringify(customFilters)); } catch (e) {}
}

function renderCustomFilters() {
    const list = document.getElementById('customFiltersList');
    if (!list) return;
    list.innerHTML = customFilters.map(f =>
        `<div style="display:flex; align-items:center; gap:6px; padding:5px 8px; background:rgba(56,189,248,0.08); border:1px solid var(--border-color); border-radius:7px; font-size: 0.7188rem;">
            <input type="checkbox" checked onchange="toggleCustomFilter('${f.id}', this)" style="accent-color:var(--accent-blue);">
            <span style="flex:1; color:var(--text-primary);">${f.emoji} <b>${f.name}</b> <span style="color:var(--text-secondary); font-size: 0.6562rem; direction:ltr;">${f.expr}</span></span>
            <button onclick="removeCustomFilter('${f.id}')" style="border:none; background:rgba(239,68,68,0.15); color:#f43f5e; border-radius:5px; padding:2px 8px; cursor:pointer; font-family:inherit;">✕</button>
        </div>`).join('');
}

function toggleCustomFilter(id, cb) {
    const f = customFilters.find(x => x.id === id);
    if (f) f.active = cb.checked;
    saveCustomFilters();
    applyFilters();
}

// ارزیابی امن فرمول: تبدی‌ل یک‌ای به شرط JS
function evalCustomFilter(f, row) {
    try {
        const fields = ['p_last','p_closing','percent_change','pe','eps','mcap','vol_ratio','z_tot_tran','price_min','price_max','buy_power_i','sell_power_i','q_tot_tran'];
        let expr = f.expr.replace(/&&/g, '&&').replace(/\|\|/g, '||');
        // شکافتن منطقی به زیرعبارت‌ها (برای امنیت)
        const parts = expr.split(/(&&|\|\|)/);
        let acc = null;
        let op = null;
        for (const part of parts) {
            const t = part.trim();
            if (t === '&&') { op = '&&'; continue; }
            if (t === '||') { op = '||'; continue; }
            const m = t.match(/^\s*([a-z_][a-z0-9_]*)\s*(>=|<=|==|>|<)\s*([-0-9.]+)\s*$/i);
            if (!m) return false;
            const val = row[m[1].toLowerCase()];
            if (val === null || val === undefined) return false;
            const num = parseFloat(m[3]);
            const cond = m[2] === '>=' ? val >= num : m[2] === '<=' ? val <= num : m[2] === '==' ? val == num : m[2] === '>' ? val > num : val < num;
            acc = acc === null ? cond : (op === '&&' ? (acc && cond) : (acc || cond));
            op = null;
        }
        return !!acc;
    } catch (e) { return false; }
}

function initCustomFilters() {
    renderCustomFilters();
    customFilters.forEach(f => { if (f.active === undefined) f.active = true; });
}

/* ---------- درگ-جابجایی ستون‌ها (هر دو جدول بازار/کدال) ---------- */
function initColDrag(tableId) {
    const table = document.getElementById(tableId);
    const thead = table ? table.querySelector('thead tr') : null;
    if (!thead) return;
    let srcIdx = -1;
    Array.from(thead.children).forEach(th => {
        th.draggable = true;
        th.addEventListener('dragstart', e => {
            srcIdx = Array.from(thead.children).indexOf(th);
            th.style.opacity = '0.4';
            e.dataTransfer.effectAllowed = 'move';
            try { e.dataTransfer.setData('text/plain', String(srcIdx)); } catch (err) {}
        });
        th.addEventListener('dragend', () => { th.style.opacity = ''; });
        th.addEventListener('dragover', e => e.preventDefault());
        th.addEventListener('drop', e => {
            e.preventDefault();
            const dstIdx = Array.from(thead.children).indexOf(th);
            if (srcIdx < 0 || srcIdx === dstIdx) { srcIdx = -1; return; }
            _swapCols(table, thead, srcIdx, dstIdx);
            srcIdx = -1;
        });
    });
}

/* جابجایی ستون srcIdx → dstIdx در thead و همه ردیف‌ها + ذخیره ترتیب */
function _swapCols(table, thead, srcIdx, dstIdx) {
    const srcTh = thead.children[srcIdx];
    const dstTh = thead.children[dstIdx];
    if (dstIdx > srcIdx) thead.insertBefore(srcTh, dstTh.nextSibling);
    else thead.insertBefore(srcTh, dstTh);
    const tbody = table.querySelector('tbody');
    if (tbody) Array.from(tbody.querySelectorAll('tr')).forEach(tr => {
        const cells = Array.from(tr.children).filter(td => !td.hasAttribute('colspan'));
        if (cells.length <= Math.max(srcIdx, dstIdx)) return;
        const srcTd = cells[srcIdx], dstTd = cells[dstIdx];
        if (dstIdx > srcIdx) tr.insertBefore(srcTd, dstTd.nextSibling);
        else tr.insertBefore(srcTd, dstTd);
    });
    // ذخیره ترتیب بر اساس کلید ستون (data-col یا متن تیتر)
    try {
        const keyOf = el => el.dataset.col || el.textContent.trim().replace(/[↕↑↓]/g, '');
        stSet('colOrder_' + table.id, JSON.stringify(
            Array.from(thead.children).map(keyOf)
        ));
    } catch (err) {}
    try { rebuildColgroup(table.id); } catch (e) {}
    if (typeof applyColShow === 'function') applyColShow();
}

/* بازیابی ترتیب ذخیره‌شده بعد از هر re-render جدول */
function applyColOrder(tableId) {
    const table = document.getElementById(tableId);
    const thead = table ? table.querySelector('thead tr') : null;
    if (!thead) return;
    let order = [];
    try { order = JSON.parse(stGet('colOrder_' + tableId, localStorage.getItem('colOrder_' + tableId)) || '[]'); } catch (e) {}
    if (!order.length) return;
    const keyOf = el => el.dataset.col || el.textContent.trim().replace(/[↕↑↓]/g, '');
    // ترتیب فعلی
    const cur = Array.from(thead.children).map(keyOf);
    // برای هر کلید مقصد، ایندکس فعلی را به ایندکس دلخواه برسان (از چپ به راست)
    for (let want = 0; want < order.length; want++) {
        const key = order[want];
        const haveIdx = cur.indexOf(key);
        if (haveIdx < 0 || haveIdx === want) continue;
        _swapCols(table, thead, haveIdx, want);
        cur.splice(want, 0, cur.splice(haveIdx, 1)[0]);
    }
}

function toggleSidebar() {
    const sb = document.querySelector('.sidebar');
    const mc = document.querySelector('.main-content');
    const rz = document.querySelector('.sidebar-resizer');
    const collapsed = sb.classList.toggle('collapsed');
    if (mc) {
        mc.classList.toggle('sidebar-collapsed', collapsed);
        // margin یک‌جا ست میشود (بدون انیمیشن) — reflow فقط یک بار
        if (collapsed) mc.style.marginRight = '0px';
        else mc.style.marginRight = sb.getBoundingClientRect().width + 'px';
    }
    if (rz) rz.classList.toggle('sidebar-collapsed', collapsed);
    // چارت بعد از اتمام لغزش سایدبار یک‌بار resize میشود (نه هر فریم)
    setTimeout(() => { try { if (typeof rv !== 'undefined' && rv.chart) rv.chart.resize(); } catch (e) {} }, 220);
}

/* ---------- درگ‌گیر عرض سایدبار (مثل VS Code) ---------- */
function initSidebarResizer() {
    const rz = document.querySelector('.sidebar-resizer');
    if (!rz) return;
    rz.addEventListener('mousedown', (e) => {
        e.preventDefault();
        const sb = document.querySelector('.sidebar');
        const mc = document.querySelector('.main-content');
        const startX = e.clientX, startW = sb.getBoundingClientRect().width;
        let raf = 0, pendingW = startW;
        // حین درگ: فقط عرض سایدبار (fixed) و موقعیت دستگیره — بدون margin محتوا،
        // بدون ریفلو جدول/چارت → درگ ۱۰۰٪ نرم. اعمال نهایی در mouseup یک‌بار.
        const move = (ev) => {
            pendingW = Math.max(200, Math.min(430, startW + (startX - ev.clientX)));
            if (raf) return;
            raf = requestAnimationFrame(() => {
                raf = 0;
                sb.style.width = pendingW + 'px';
                rz.style.right = pendingW + 'px';
            });
        };
        const up = () => {
            if (raf) { cancelAnimationFrame(raf); raf = 0; }
            sb.style.width = pendingW + 'px';
            rz.style.right = pendingW + 'px';
            if (mc) mc.style.marginRight = pendingW + 'px';   // یک reflow، در انتها
            try { stSet('sidebarWidth', String(pendingW)); } catch (err) {}
            setTimeout(() => { try { if (typeof rv !== 'undefined' && rv.chart) rv.chart.resize(); } catch (e) {} }, 60);
            document.removeEventListener('mousemove', move);
            document.removeEventListener('mouseup', up);
        };
        document.addEventListener('mousemove', move);
        document.addEventListener('mouseup', up);
    });
}

function initSidebarWidth() {
    try {
        const w = parseInt(stGet('sidebarWidth', localStorage.getItem('sidebarWidth') || '260'), 10);
        if (w >= 200 && w <= 430) {
            const sb = document.querySelector('.sidebar');
            const rz = document.querySelector('.sidebar-resizer');
            const mc = document.querySelector('.main-content');
            if (sb) sb.style.width = w + 'px';
            if (rz) rz.style.right = w + 'px';
            if (mc) mc.style.marginRight = w + 'px';
            document.documentElement.style.setProperty('--sbw', w + 'px');
        }
    } catch (e) {}
}

function toggleTheme() {
    const html = document.documentElement;
    const next = html.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    html.setAttribute('data-theme', next);
    try { stSet('theme', next); } catch (e) { try { localStorage.setItem('theme', next); } catch (e2) {} }
    if (typeof rvApplyTheme === 'function') rvApplyTheme();
}
function initThemeState() {
    try {
        const saved = stGet('theme', localStorage.getItem('theme')) || 'dark';
        document.documentElement.setAttribute('data-theme', saved === 'light' ? 'light' : 'dark');
    } catch (e) {}
}

function toggleSection(secId) {
    const body = document.getElementById(secId + 'Body');
    const tog = document.getElementById(secId + 'Toggle');
    if (!body) return;
    const open = body.style.display !== 'none';
    body.style.display = open ? 'none' : 'block';
    if (tog) tog.textContent = open ? '▸' : '▾';
    try { stSet('secOpen_' + secId, !open); } catch (e) {}
    if (!open && secId === 'cfSection') renderCustomFilters();  // بعد از باز شدن، لیست فیلترها
}
function initSectionState() {
    ['cfSection', 'fltSection'].forEach(secId => {
        try {
            const open = stGet('secOpen_' + secId, false);
            const body = document.getElementById(secId + 'Body');
            if (body && open) {
                body.style.display = 'block';
                const tog = document.getElementById(secId + 'Toggle');
                if (tog) tog.textContent = '▾';
            }
        } catch (e) {}
    });
}

let syncPollTimer = null;
let syncOverlayStart = 0;
let marketRefreshTimer = null;
let pollBgTimer = null;   // poll پس‌زمینه (۵ ثانیه) — فقط یک نمونه؛ sync آن را می‌بندد
let _psBusy = false;      // v9.7.8 — گارد in-flight برای pollSyncStatus (ضد انباشت درخواست در شلوغی استارت)
let _arBusy = false;      // v9.7.8 — گارد in-flight برای autoRefreshTick

function showSyncOverlay() {
    // Disable buttons to prevent accidental restarts
    const btnC = document.getElementById('btnSyncCodal');
    const btnM = document.getElementById('btnSyncMarket');
    if (btnC) { btnC.disabled = true; btnC.style.opacity = '0.5'; }
    if (btnM) { btnM.disabled = true; btnM.style.opacity = '0.5'; }
    
    document.getElementById('syncOverlay').style.display = 'flex';
    const mini = document.getElementById('miniSyncStatus');
    if (mini) mini.style.display = 'none';
    
    if (syncPollTimer) { clearInterval(syncPollTimer); syncPollTimer = null; }
    if (pollBgTimer) { clearInterval(pollBgTimer); pollBgTimer = null; }
    syncPollTimer = setInterval(pollSyncStatus, 1000);
    syncOverlayStart = Date.now();
    updateSyncElapsed();
    pollSyncStatus();
}

function hideSyncOverlay() {
    if (syncPollTimer) { clearInterval(syncPollTimer); syncPollTimer = null; }
    if (marketRefreshTimer) { clearInterval(marketRefreshTimer); marketRefreshTimer = null; }
    document.getElementById('syncOverlay').style.display = 'none';
    const mini = document.getElementById('miniSyncStatus');
    if (mini) mini.style.display = 'none';
    // poll پس‌زمینه را (اگر نبود) دوباره بساز — clear-before-set
    if (!pollBgTimer) { pollBgTimer = setInterval(pollSyncStatus, 5000); }
    
    // Re-enable buttons
    const btnC = document.getElementById('btnSyncCodal');
    const btnM = document.getElementById('btnSyncMarket');
    if (btnC) { btnC.disabled = false; btnC.style.opacity = '1'; }
    if (btnM) { btnM.disabled = false; btnM.style.opacity = '1'; }
}

function minimizeSyncOverlay() {
    document.getElementById('syncOverlay').style.display = 'none';
    document.getElementById('miniSyncStatus').style.display = 'flex';
}

function restoreSyncOverlay() {
    document.getElementById('syncOverlay').style.display = 'flex';
    document.getElementById('miniSyncStatus').style.display = 'none';
}

function faNum(n) {
    try { return Number(n).toLocaleString('fa-IR'); } catch (e) { return String(n); }
}

function renderCodalScanInfo(s) {
    const box = document.getElementById('codalScanInfo');
    const ex = document.getElementById('syncExtra');
    if (!box && !ex) return;
    const extra = s.extra || {};
    const total = s.total || 0, cur = s.current || 0;
    const remaining = Math.max(0, total - cur);
    const v2 = s.v2ray || {};
    const lift = v2.ban_lift || s.ban_until || '';
    const inBackoff = s.phase === 'codal_backoff' ||
                      (lift && (s.detail || '').indexOf('مسدودی') >= 0);
    const lines = [];
    let net;
    if (v2.mode === 'node') {
        net = '⚡ اتصال از <strong>سرور واسط</strong>' + (v2.upstream ? ` (${v2.upstream}) — آیپی شما پنهان است، بن دیرتر میافتد` : '');
    } else if (v2.mode === 'direct') {
        net = '🔌 <strong>اتصال مستقیم</strong> — از آیپی خودتان؛ احتمال بلاک زودتر';
    } else {
        net = '🛰️ وضعیت اتصال: نامشخص';
    }
    if (inBackoff && lift) net += ` — 🛑 <strong>بلاک شدیم</strong>؛ احتمالاً ساعت <strong>${faNum(lift)}</strong> ادامه میدهیم`;
    else if (inBackoff) net += ' — 🛑 بلاک شدیم؛ منتظر رفع مسدودی';
    lines.push(net);
    // نماد فعلی + مرحله استخراج (جزییات بیشتر)
    if (s.symbol && s.symbol !== '-') {
        let symLine = `🔍 نماد فعلی: <strong>${s.symbol}</strong>`;
        if (s.detail) symLine += ` — ${s.detail}`;
        lines.push(symLine);
    }
    if (total > 0) {
        let p = `⏳ پیشرفت کدال: <strong>${faNum(cur)}</strong> از <strong>${faNum(total)}</strong> — <strong>${faNum(remaining)}</strong> مرحله مانده`;
        if (s.symbol && s.symbol !== '-') p += ` · نماد فعلی: ${s.symbol}`;
        lines.push(p);
        const parts = [];
        if (extra.done != null) parts.push(`✅ از قبل کامل: ${faNum(extra.done)}`);
        if (extra.new != null) parts.push(`🆕 اطلاعات جدید: ${faNum(extra.new)}`);
        if (extra.empty != null) parts.push(`🚫 بدون اطلاعیه: ${faNum(extra.empty)}`);
        if (extra.blocked > 0) parts.push(`🛑 بلاک در این نمادها: ${faNum(extra.blocked)}`);
        if (parts.length) lines.push(parts.join(' · '));
    }
    const html = lines.join('<br>');
    if (box) {
        if (s.active || s.phase === 'codal_stopped') { box.style.display = 'block'; box.innerHTML = html; }
        else box.style.display = 'none';
    }
    if (ex) ex.innerHTML = html;
}

async function pollSyncStatus() {
    if (_psBusy) return;   // نمونهٔ پیشین هنوز برنگشته — درخواست دوم روی هم انباشته نشود
    _psBusy = true;
    try {
        const res = await fetch('/api/sync/status');
        const json = await res.json();
        if (json.status !== 'success') return;
        const s = json.sync;
        document.getElementById('syncStage').innerText = s.stage || '...';
        const detailParts = [];
        if (s.phase) detailParts.push(s.phase);
        if (s.symbol && s.symbol !== '-') detailParts.push(`نماد: ${s.symbol}`);
        if (s.detail) detailParts.push(s.detail);
        document.getElementById('syncDetail').innerText = detailParts.join(' — ') || 'در حال پردازش...';
        const pct = Math.min(100, Math.max(0, s.percent || 0));
        document.getElementById('syncBar').style.width = pct + '%';
        document.getElementById('syncCount').innerText = `${s.current || 0} / ${s.total || 0}`;
        const remain = Math.max(0, (s.total || 0) - (s.current || 0));
        // بهبود وضعیت: رنگ پیشرفت + متن هوشمند (در حال انجام / مکث / انجام شده)
        const bar = document.getElementById('syncBar');
        const stoppedOrPaused = (s.phase === 'codal_stopped' || s.phase === 'codal_paused');
        if (!s.active && pct >= 100) bar.style.background = '#10b981';          // ✅ تمام شد
        else if (stoppedOrPaused) bar.style.background = '#f59e0b';            // ⏸️ مکث/توقف
        else bar.style.background = 'var(--accent-blue, #38bdf8)';             // ⚡ در حال پیشرفت
        const miniTxt = !s.active && pct >= 100
            ? '✅ اسکن کامل شد'
            : stoppedOrPaused
                ? `⏸️ متوقف — ${pct}%`
                : `⏳ ${pct}%${s.total ? ` · ${faNum(remain)} مونده` : ''}`;
        document.getElementById('miniSyncText').innerText = `کدال: ${miniTxt}`;
        // Always-visible header badge: node / direct / ban-until (plain-language)
        const vb = document.getElementById('codalV2Badge');
        if (vb) {
            const v2 = s.v2ray || {};
            const lift = v2.ban_lift || s.ban_until || '';
                        let txt;
            if (s.phase === 'codal_paused') txt = '⏸️ کدال: مکث (متوقف موقت)';
            else if (s.phase === 'codal_stopped') txt = '⏹️ کدال: متوقفشده';
            else if (v2.mode === 'node') txt = '🛰️ کدال: اتصال از سرور واسط' + (v2.upstream ? ` (${v2.upstream})` : '');
            else if (v2.mode === 'direct') txt = '🛰️ کدال: اتصال مستقیم';
            else txt = '🛰️ کدال: —';
            if (lift) txt += ` · 🛑 بلاک، ادامه ~${faNum(lift)}`;
            vb.innerText = txt;
        }
        // Codal control buttons: pause / resume / stop (visible while active;
        // resume also shown when the scan was stopped by the user)
        const isPaused = (s.phase || '') === 'codal_paused';
        const isStopped = (s.phase || '') === 'codal_stopped';
        setCodalBtn('codalCtrlBtns', !!s.active || isStopped);
        setCodalBtn('btnCodalPause', !!s.active && !isPaused);
        setCodalBtn('btnCodalResume', (!!s.active && isPaused) || isStopped);
        setCodalBtn('btnCodalStop', !!s.active);
        renderCodalScanInfo(s);
        // تشخیص باگ: آیا codal_fetcher واقعاً اجرا میشود؟ sync_status.json فریز شده؟
        try {
            const dres = await fetch('/api/sync/diagnose');
            const djson = await dres.json();
            if (djson.status === 'success') {
                const d = djson.diag;
                const diagEl = document.getElementById('syncDiag');
                const warns = [];
                if (s.active && !d.codal_process_running)
                    warns.push('⚠️ همگامسازی در UI فعال نشان میدهد ولی پروسهٔ کدال در حال اجرا نیست — احتمالاً کرش کرده');
                if (d.status_frozen)
                    warns.push(`⚠️ وضعیت از ${faNum(d.status_file_age_sec)} ثانیه پیش فریز شده — پروسه هنگ کرده`);
                if (d.codal_process_running && !s.active && d.phase !== 'codal_stopped')
                    warns.push('⚠️ پروسهٔ کدال در حال اجراست ولی UI آن را نشان نمیدهد — صبر کنید یا ریاستارت کنید');
                if (!d.adb_device && d.adb_found)
                    warns.push('📱 adb پیدا شد ولی گوشی متصل نیست — چرخش IP کار نمیکند');
                if (d.adb_device && d.adb_found && d.phase && d.detail && d.detail.indexOf('۴۲۹') >= 0)
                    warns.push('🔄 چرخش IP با گوشی فعال — منتظر آیپی تازه (۸۰ ثانیه)...');
                if (d.adb_device && d.adb_found && !(d.adb_tether_up))
                    warns.push('📱 گوشی متصل است ولی USB Tethering روشن نیست — از Settings گوشی روشن کنید تا چرخش IP مؤثر باشد');
                if (warns.length) {
                    diagEl.style.display = 'block';
                    diagEl.innerHTML = warns.join('<br>');
                } else {
                    diagEl.style.display = 'none';
                }
            }
        } catch (e) { /* diagnose optional */ }
        // Refresh screener when new data appeared (extra.new grew) or sync completed
        const newCnt = (s.extra && s.extra.new) != null ? s.extra.new : -1;
        if (newCnt >= 0 && newCnt !== lastNewCnt) {
            lastNewCnt = newCnt;
            if (newCnt > 0) initScreener(true);
        } else if (prevCodalActive && !s.active) {
            initScreener(true); // sync finished — new FS rows may exist
        }
        prevCodalActive = !!s.active;
        // Hide when both channels report done/idle and nothing is running
        if (!s.active && (s.stage === 'done' || s.stage === 'idle') && pct >= 100) {
            document.getElementById('syncDetail').innerText = '✅ ' + (s.detail || 'بروزرسانی کامل شد.');
            setTimeout(hideSyncOverlay, 1500);
        }
        // Passive visibility: show the mini badge whenever ANY sync is running
        const mini = document.getElementById('miniSyncStatus');
        const overlay = document.getElementById('syncOverlay');
        if (s.active) {
            const overlayVisible = overlay && overlay.style.display === 'flex';
            if (!overlayVisible && mini && mini.style.display !== 'flex') mini.style.display = 'flex';
        } else if (mini) {
            mini.style.display = 'none';
        }
    } catch (e) {
        console.error('poll sync status failed:', e);
    } finally { _psBusy = false; }
}

function updateSyncElapsed() {
    if (!syncPollTimer) return; // Stop only when sync is truly done
    const secs = Math.floor((Date.now() - syncOverlayStart) / 1000);
    const mm = String(Math.floor(secs / 60)).padStart(2, '0');
    const ss = String(secs % 60).padStart(2, '0');
    const el = document.getElementById('syncElapsed');
    if (el) el.innerText = `${mm}:${ss}`;
    setTimeout(updateSyncElapsed, 1000);
}

async function triggerMarketSync() {
    showSyncOverlay();
    await fetch('/api/sync/market', {method: 'POST'});
    showMarketSyncDetails();
    // بعد از شروع، جدول را هر ۱۰ ثانیه رفرش کن تا داده جدید بیاید
    // v9.7.8 — گارد in-flight: هنگام نوشتن سینک، /api/market ده‌ها ثانیه طول می‌کشد؛
    // بدون گارد، تایمر ۱۰ثانیه روی پاسخ‌های آهسته سوار شده و شلوغی سرور را بدتر می‌کند.
    if (marketRefreshTimer) { clearInterval(marketRefreshTimer); marketRefreshTimer = null; }
    let mrtBusy = false;
    marketRefreshTimer = setInterval(() => {
        if (mrtBusy) return;
        mrtBusy = true;
        fetch('/api/market').then(r => r.json()).then(j => {
            if (j.status === 'success') {
                marketData = j.data; populateSectors(); applyFilters();
                updateMarketDateInfo(j.meta, j.live_count, j.fossil_count);   // 🐛 تاریخ/ساعت هم آپدیت شود
            }
        }).catch(() => {}).finally(() => { mrtBusy = false; });
    }, 10000);
}
async function triggerCodalSync(mode) {
    showSyncOverlay();
    // راهنمای اول-اجرا: چرا ممکن است بلاک شوی (یک بار)
    try {
        if (!localStorage.getItem('adbHintShown')) {
            localStorage.setItem('adbHintShown', '1');
            setTimeout(() => {
                const btn = document.querySelector('.icon-btn[onclick*="openAdbGuide"]');
                if (btn) {
                    const r = btn.getBoundingClientRect();
                    const tip = document.createElement('div');
                    tip.id = 'adbHintTip';
                    tip.style.cssText = 'position:fixed; top:' + (r.bottom + 10) + 'px; left:' + (r.left + 20) + 'px; z-index:9999; background:var(--bg-card,#0f172a); border:1px solid var(--accent-blue); color:var(--text-primary); border-radius:10px; padding:12px 16px; font-size: 0.7812rem; max-width:300px; box-shadow:0 10px 28px rgba(0,0,0,.5); line-height:1.9;';
                    tip.innerHTML = '<b style="color:var(--accent-blue);">❓ چرا ممکن است بلاک شوم؟</b><br>' +
                        'کدال تعداد درخواستها را محدود میکند؛ وقتی IP تو زیاد درخواست بدهد، ~۶۰-۹۰ دقیقه مسدود میشود (۴۲۹).' +
                        '<br><b style="color:var(--accent-green);">راه حل:</b> روی همین <b>❓</b> بزن تا راهنمای اتصال گوشی + چرخش خودکار IP (ADB) را ببینی — اسکن خودش با IP تازه ادامه مییابد.' +
                        '<div style="margin-top:8px; text-align:left;"><button onclick="openAdbGuide(); this.closest(\'#adbHintTip\').remove()" style="border:none; background:var(--accent-blue); color:#000; font-weight:700; padding:6px 14px; border-radius:7px; cursor:pointer; font-family:inherit;">باز کن 🚀</button></div>';
                    document.body.appendChild(tip);
                    setTimeout(() => { const t = document.getElementById('adbHintTip'); if (t) t.remove(); }, 12000);
                }
            }, 1200);
        }
    } catch (e) {}
    await fetch('/api/sync/codal?mode=' + (mode || 'update'), {method: 'POST'});
    rvToastSv((mode === 'optimized') ? '⚡ شروع شد (حالت بهینه)' : '🔄 شروع شد');
}

/* Confirmation: درجا شروع نکن — ابتدا توضیحی + تیک همانجا */
/* ---------- شروع دستی (پنل): درجا شروع نکن — پنل باز کن + تیک همانجا ---------- */
function toggleCodalStartPanel() {
    const p = document.getElementById('codalStartPanel');
    if (p) p.style.display = (p.style.display === 'none' || !p.style.display) ? 'block' : 'none';
    updateCodalStartHint();
}
function updateCodalStartHint() {
    const h = document.getElementById('codalStartHint');
    if (!h) return;
    h.textContent = codalMode() === 'optimized'
        ? '⚡ حالت بهینه: فقط دادهٔ تغییرپذیر (۶× کمتر درخواست، بدون بلاک IP)'
        : '🔄 فید سراسری: همهٔ گزارشهای جدید بعد از آخرین تاریخ DB';
}
function codalModeChanged() { updateCodalStartHint(); }
function startCodalRun(mode) {
    const p = document.getElementById('codalStartPanel');
    if (p) p.style.display = 'none';
    triggerCodalSync(mode);
}

/* ---------- Toast جهانی ---------- */
function rvToastSv(msg) {
    let t = document.getElementById('globalToast');
    if (!t) {
        t = document.createElement('div');
        t.id = 'globalToast';
        t.style.cssText = 'position:fixed; bottom:18px; left:50%; transform:translateX(-50%); z-index:99999; background:var(--bg-secondary); border:1px solid var(--border-accent); color:var(--text-primary); border-radius:10px; padding:12px 20px; font-size: 0.8125rem; font-weight:600; box-shadow:0 12px 30px rgba(0,0,0,.5); max-width:540px; text-align:center; transition:opacity .3s; backdrop-filter:blur(4px);';
        document.body.appendChild(t);
    }
    t.textContent = msg;
    t.style.opacity = '1';
    clearTimeout(t._h);
    t._h = setTimeout(() => { t.style.opacity = '0'; }, 4200);
}

/* ---------- Pipeline v6: دکمه‌های update/discover + loading + toast ---------- */
async function syncPipeline(kind, btn) {
    // UI FEEDBACK: disable + label تغییر (loading state)
    const idle = btn.dataset.idle || btn.innerHTML;
    if (!btn.dataset.idle) btn.dataset.idle = btn.innerHTML;
    btn.disabled = true;
    btn.style.opacity = .6;
    btn.innerHTML = (kind === 'discover') ? '⏳ در حال دریافت نمادهای جدید...' : '⏳ در حال به روزرسانی داده‌های موجود...';
    try {
        const url = (kind === 'discover') ? '/api/sync/discover' : '/api/sync/update-existing';
        const r = await fetch(url, {method: 'POST', headers: {'Accept': 'application/json'}});
        const j = await r.json();
        if (j.status === 'ok' || j.status === 'running') {
            const n = j.updated || j.limit || 0;
            rvToastSv(`✓ ${kind === 'discover' ? 'کشف' : 'آپدیت'} موفق: ${n} نماد ${kind === 'discover' ? 'کاوش شد' : 'پردازش شد'}${j.delta ? ` (${j.delta} جدید)` : ''}`);
        } else {
            rvToastSv(`⚠️ ${j.detail || j.message || 'خطا'}`);
        }
        // poll job status بعد از چند ثانیه
        setTimeout(async () => {
            try {
                const pr = await fetch('/api/sync/pipeline');
                const pj = await pr.json();
                const job = (pj.jobs || {})[kind];
                if (job && job.status === 'running') rvToastSv(`⏳ ${kind === 'discover' ? 'کشف' : 'آپدیت'} در پس‌زمینه ادامه دارد...`);
            } catch (e) {}
        }, 5000);
    } catch (e) {
        rvToastSv('⚠️ ارتباط با سرور برقرار نشد');
    } finally {
        btn.disabled = false;
        btn.style.opacity = 1;
        btn.innerHTML = btn.dataset.idle || idle;
    }
}
function codalMode() {
    const el = document.getElementById('codalModeOptimized');
    return (el && el.checked) ? 'optimized' : 'update';
}
function initCodalModeState() {
    // کاربر خواست: تیک بهینه هر اجرا خاموش (خودکار روشن نشود) — بدون STATE
    try {
        const cb = document.getElementById('codalModeOptimized');
        if (cb) {
            cb.checked = false;
            const el = document.getElementById('btnSyncCodal');
            if (el) el.classList.toggle('active-mode', false);
        }
    } catch (e) {}
}

function setCodalBtn(id, show) {
    const el = document.getElementById(id);
    if (el) el.style.display = show ? '' : 'none';
}

/* وضعیت اتصال کدال (برای علامت سوال بزرگ در تب کدال) */
async function updateCodalConnStatus() {
    const btn = document.getElementById('codalConnBtn');
    if (!btn) return;
    try {
        const r = await fetch('/api/sync/diagnose');
        const j = await r.json();
        const running = j.codal_process_running === true;
        btn.style.background = running ? 'rgba(16,185,129,.15)' : 'rgba(239,68,68,.12)';
        btn.style.borderColor = running ? 'rgba(16,185,129,.4)' : 'rgba(239,68,68,.4)';
        btn.style.color = running ? 'var(--accent-green)' : '#ef4444';
        btn.title = running
            ? '🟢 اسکن کدال در حال اجراست — دکمه برای راهنمای ADB/بلاک '
            : '🔴 اسکن کدال متوقف است — شرایط اتصال: ' + ((j.adb_found ? 'ADB ✓' : 'ADB ✗') + (j.adb_enabled ? ' · چرخش IP فعال' : ''));
    } catch (e) {}
}

async function codalControl(cmd) {
    try {
        await fetch('/api/codal/control', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({cmd})
        });
    } catch (e) { console.error('codal control failed:', e); }
}

/* ---------- بروزرسانی خودکار تابلو (فقط ساعات بازار) ---------- */
function isMarketOpen() {
    // بازار ایران: شنبه تا چهارشنبه، ۹:۰۰ تا ۱۲:۳۰
    const now = new Date();
    const iran = new Date(now.getTime() + (3.5 * 3600 * 1000));
    const wd = (iran.getDay() + 1) % 7; // شنبه=0، یکشنبه=1 … جمعه=6
    const mins = iran.getHours() * 60 + iran.getMinutes();
    return wd <= 4 && mins >= 540 && mins <= 750; // 9:00 … 12:30
}

async function autoRefreshTick() {
    if (_arBusy) return;   // چرخهٔ پیشین (واکشی تابلو + sync-state + POST) تمام نشده — تیک موازی نزن
    _arBusy = true;
    try {
        if (!stGet('autoRefresh', true)) return;
        if (document.hidden) return;    // تب مخفی: کاری نکن (باکاران است برای بازار بسته)
        if (!isMarketOpen()) return;   // خارج ساعت: کاری نکن
        // فقط بعد از گذشت بازه (۱..۵۹ ثانیه) رفرش بزن
        const iv = getAutoRefreshInterval();
        const last = (Date.now() - (parseInt(localStorage.getItem('lastAutoRefreshTs') || '0', 10) || 0));
        if (last < iv * 1000) return;
        localStorage.setItem('lastAutoRefreshTs', String(Date.now()));
        await initMarket();
        // اگر دادهٔ تابلو کهنهتر از ۲× بازه بود، سینک زنده هم بزن (فقط در ساعات باز)
        try {
            const st = await (await fetch('/api/market/sync-state')).json();
            const old = st.last && st.last.last_update;
            const stale = old ? (Date.now() - new Date(old.replace(' ', 'T')).getTime()) > (getAutoRefreshInterval() * 2 * 1000) : true;
            if (stale && !st.running) {
                await fetch('/api/sync/market', { method: 'POST' });
            }
        } catch (e) {}
    } catch (e) {} finally { _arBusy = false; }
}

function getAutoRefreshUnit() {
    try { return stGet('autoRefreshUnit', 'sec'); } catch (e) { return 'sec'; }
}
function getAutoRefreshInterval() {
    try {
        const u = getAutoRefreshUnit();
        let v = parseInt(stGet('autoRefreshInterval', '30'), 10) || 30;
        if (u === 'min') return Math.min(Math.max(v, 1), 30) * 60;
        return Math.min(Math.max(v, 1), 59);
    } catch (e) { return 30; }
}
/* v9.1 — پرکردن نوار اسلایدر: درصد موقعیت دستگیره را در --ar-p می‌نویسد.
   در RTL نوار از سمت راست (min) پر می‌شود؛ گرادیان CSS همین را لحاظ کرده است. */
function paintSlider(inp) {
    if (!inp) return;
    const mn = parseFloat(inp.min), mx = parseFloat(inp.max), v = parseFloat(inp.value);
    const p = (mx > mn) ? ((v - mn) / (mx - mn)) * 100 : 0;
    inp.style.setProperty('--ar-p', Math.max(0, Math.min(100, p)).toFixed(1) + '%');
}
function onSecSlider(v) {
    v = parseInt(v, 10) || 30;
    const val = document.getElementById('autoRefreshVal');
    const sv = document.getElementById('autoRefreshSecVal');
    const inp = document.getElementById('autoRefreshSec');
    if (inp) inp.value = v;
    if (val) { val.textContent = v + ' ثانیه'; val.style.color = '#2dd4bf'; }
    if (sv) sv.textContent = v;
    paintSlider(inp);
    try { stSet('autoRefreshUnit', 'sec'); stSet('autoRefreshInterval', String(v)); } catch (e) {}
}
function onMinSlider(v) {
    v = parseInt(v, 10) || 5;
    const val = document.getElementById('autoRefreshVal');
    const mv = document.getElementById('autoRefreshMinVal');
    const inp = document.getElementById('autoRefreshMin');
    if (inp) inp.value = v;
    if (val) { val.textContent = v + ' دقیقه'; val.style.color = '#60a5fa'; }
    if (mv) mv.textContent = v;
    paintSlider(inp);
    try { stSet('autoRefreshUnit', 'min'); stSet('autoRefreshInterval', String(v)); } catch (e) {}
}

function setupAutoRefresh() {
    if (refreshInterval) clearInterval(refreshInterval);
    refreshInterval = setInterval(autoRefreshTick, 1000);   // تیک ۱ ثانیهای — دقت بازهٔ ۱ثانیهای
}

function toggleAutoRefresh(cb) {
    try { stSet('autoRefresh', cb.checked); } catch (e) {}
    const lbl = document.getElementById('autoRefreshLabel');
    if (lbl) lbl.textContent = cb.checked ? 'بروزرسانی خودکار' : 'بروزرسانی خودکار خاموش';
}

function initAutoRefreshState() {
    try {
        const cb = document.getElementById('autoRefreshCb');
        if (cb) { cb.checked = stGet('autoRefresh', true); }
        const u = getAutoRefreshUnit();
        const v = parseInt(stGet('autoRefreshInterval', u === 'min' ? '5' : '30'), 10) || (u === 'min' ? 5 : 30);
        const sec = document.getElementById('autoRefreshSec');
        const min = document.getElementById('autoRefreshMin');
        if (sec) sec.value = String(Math.min(Math.max(u === 'sec' ? v : 30, 1), 59));
        if (min) min.value = String(Math.min(Math.max(u === 'min' ? v : 5, 1), 30));
        if (u === 'min') onMinSlider(min ? min.value : '5'); else onSecSlider(sec ? sec.value : '30');
        paintSlider(sec); paintSlider(min);   // نوار هر دو اسلایدر از همان ابتدا پر باشد
    } catch (e) {}
}

function toggleFilter(f, btn) {
    if(activeFilters.has(f)) {
        activeFilters.delete(f);
        btn.classList.remove('active-filter');
    } else {
        activeFilters.add(f);
        btn.classList.add('active-filter');
    }
    try { stSet('activeFilters', Array.from(activeFilters)); } catch (e) {}
    applyFilters();
}

/* حذف فیلتر اصلی (builtin) — با تایید، از STATE و نمایش */
function removeBuiltinFilter(ev, id) {
    ev.stopPropagation();
    if (!confirm('مطمئنی می‌خوای این فیلتر رو برای همیشه حذف کنی؟')) return;
    try {
        const hidden = JSON.parse(stGet('hiddenBuiltinFilters', '[]') || '[]');
        if (!hidden.includes(id)) hidden.push(id);
        stSet('hiddenBuiltinFilters', JSON.stringify(hidden));
    } catch (e) {}
    const btn = ev.target.closest('.btn-filter');
    if (btn) btn.style.display = 'none';
    activeFilters.delete(id);
    applyFilters();
    rvToastSv('✕ فیلتر حذف شد');
}
function applyHiddenBuiltinFilters() {
    try {
        const hidden = JSON.parse(stGet('hiddenBuiltinFilters', '[]') || '[]');
        hidden.forEach(id => {
            const btn = Array.from(document.querySelectorAll('.btn-filter')).find(b => b.getAttribute('onclick') && b.getAttribute('onclick').includes("'" + id + "'"));
            if (btn) btn.style.display = 'none';
        });
    } catch (e) {}
}

function toggleFossilView(cb) {
    let show = cb.checked;
    try { stSet('showFossils', show); } catch (e) {}
    applyFilters();
}

/* 🧹 حذف همهٔ فیلترها (سازمانی + سفارشی) — دکمه‌ها و نشانگرها را هم ریست می‌کند */
/* v9.7.6 — ضد ریس کانسی: سه فراخوان (بوت، ورود به تب تابلو، رفرش خودکار،
   بوت‌استرپ پورتفوی) ممکن است همزمان initMarket را صدا بزنند و marketData/ tbody
   را با هم بازنویسی کنند → single-flight: هر فراخوان هم‌زمان همان Promise در حال اجرا را
   می‌گیرد؛ بعد از پایان، قفل آزاد می‌شود تا رفرش بعدی واقعاً واکشی کند. */
let _initMarketP = null;
function initMarket() {
    if (_initMarketP) return _initMarketP;
    _initMarketP = _initMarketRun().finally(() => { _initMarketP = null; });
    return _initMarketP;
}
/* v9.7.8 — تلاش مجدد کران‌دار برای جدول خالی (سناریوی tipیک شروع برنامه: همگام‌سازی
   اولیهٔ تابلو روی سرور هنوز در جریان است). زنجیرهٔ setTimeout — بدون حلقهٔ باز:
   هر ۱۵ ثانیه، حداکثر ۲۰ نمونه؛ به‌محض آمدن داده یا رسیدن به سقف متوقف می‌شود. */
let _emptyRetryTimer = null;
let _emptyRetryN = 0;
function _clearEmptyRetry() {
    if (_emptyRetryTimer) { clearTimeout(_emptyRetryTimer); _emptyRetryTimer = null; }
    _emptyRetryN = 0;
}
function _schedEmptyRetry() {
    if (_emptyRetryTimer || _emptyRetryN >= 20) return;
    _emptyRetryN++;
    _emptyRetryTimer = setTimeout(() => {
        _emptyRetryTimer = null;
        if (Array.isArray(marketData) && marketData.length) { _clearEmptyRetry(); return; }
        initMarket();   // single-flight: هرگز موازی با واکشی دیگر اجرا نمی‌شود
    }, 15000);
}
async function _initMarketRun() {
    // بازیابی همهٔ state از STATE (فیلترها، جستجو، ستونها)
    try {
        const fa = stGet('activeFilters', []);
        if (Array.isArray(fa)) {
            fa.forEach(f => activeFilters.add(f));
            document.querySelectorAll('.btn-filter').forEach(btn => {
                const f = btn.dataset.filter || btn.onclick.toString().match(/toggleFilter\('([^']+)'/)?.[1];
                if (f && activeFilters.has(f)) btn.classList.add('active-filter');
            });
        }
        const q = stGet('marketSearch', '');
        const sym = document.getElementById('symbolSearch');
        if (sym && q) sym.value = q;
        const sf = document.getElementById('showFossils');
        if (sf) sf.checked = stGet('showFossils', true);
    } catch (e) {}
    // بازیابی نمایش ستون‌ها از STATE
    try {
        const st = JSON.parse(stGet('tsetmcCols', localStorage.getItem('tsetmcCols')) || '{}');
        document.querySelectorAll('.colshow-cb').forEach(cb => {
            if (st[cb.dataset.col] !== undefined) cb.checked = !!st[cb.dataset.col];
        });
    } catch (e) {}
    // نشانگر لودینگ: شروع واکشی
    const tbodyEl = document.getElementById('marketTableBody');
    if (tbodyEl) tbodyEl.innerHTML = '<tr><td colspan="14" style="text-align:center; padding:28px; color:var(--text-muted,#64748b);">⏳ در حال دریافت داده‌های بازار...</td></tr>';
    try {
        // v9.7.6 — سقف ۴۰ ثانیه: سرور/Bازار که معلق بماند، لودر ابدی نمی‌سازد
        const ctl = new AbortController();
        const tmo = setTimeout(() => ctl.abort(), 40000);
        let res;
        try { res = await fetch('/api/market', { cache: 'no-store', signal: ctl.signal }); }
        finally { clearTimeout(tmo); }
        const json = await res.json();
        if (json.status === 'success' && Array.isArray(json.data)) {
            marketData = json.data;
            filteredData = marketData.slice();
            if (marketData.length) {
                _clearEmptyRetry();
                populateSectors();
                updateMarketDateInfo(json.meta, json.live_count, json.fossil_count);
            } else {
                // v9.7.8 — جدول خالی ≠ خطای شبکه: سینک اولیهٔ استارت‌آپ هنوز تمام نشده.
                // پیام روشن به‌جای اسپینر ابدی + تلاش مجدد کران‌دار (کارت‌نبودن loop).
                populateSectors();
                updateMarketDateInfo(json.meta, json.live_count, json.fossil_count);
                if (tbodyEl) tbodyEl.innerHTML = '<tr><td colspan="14" style="text-align:center; padding:28px; color:var(--text-muted,#64748b);">⏳ همگام‌سازی اولیهٔ بازار روی سرور در جریان است — جدول به‌صورت خودکار پر می‌شود…</td></tr>';
                _schedEmptyRetry();
            }
        } else {
            console.warn('initMarket: پاسخ نامعتبر از /api/market', json && json.status);
            marketData = [];
            filteredData = [];
            if (tbodyEl) tbodyEl.innerHTML = '<tr><td colspan="14" style="text-align:center; padding:28px; color:#f43f5e;">⚠️ داده‌ای از سرور دریافت نشد (وضعیت: ' + (json && json.status || 'نامشخص') + ') — تلاش خودکار مجدد در جریان است</td></tr>';
            _schedEmptyRetry();
        }
    } catch (e) {
        console.error('initMarket: خطا در واکشی داده بازار', e);
        marketData = [];
        filteredData = [];
        if (tbodyEl) tbodyEl.innerHTML = '<tr><td colspan="14" style="text-align:center; padding:28px; color:#f43f5e;">⚠️ خطا در دریافت داده‌های بازار — تلاش خودکار چندباره فعال است؛ در صورت عجله «🔄 بروزرسانی زنده تابلو» را بزنید</td></tr>';
        _schedEmptyRetry();
    } finally {
        // همیشه لودر را حذف کن: اگر دادهٔ معتبر رسید جدول رندر شود؛ وگرنه همان پیام خطا می‌ماند
        if (marketData && marketData.length) {
            applyFilters();
        }
    }
}

/* ===== v9.7.6 — پیش‌نمایش غنی نماد (تابلوخوانی) =====
   هاور ≥۳۵۰ms روی هر ردیف → کارت شناورِ کامل از دادهٔ موجود در marketData
   (بدون هیچ درخواست شبکه)؛ خروج موس/اسکرول/کلیک آن را می‌بندد. */
(function rvSymHover() {
    let card = null, timer = null, cur = null;
    const FLAGS = { f_roobi: '🧹 روبی', f_susp: '🔥 حجم مشکوک', f_clock: '⏰ الگوی ساعت', f_jet: '🚀 جت', f_noqteh: '🎯 نقطه‌زنی' };
    function n(v) { try { return Number(v).toLocaleString('fa-IR'); } catch (e) { return '—'; } }
    function cell(k, v, color) {
        return `<div class="sh-k">${k}</div><div class="sh-v"${color ? ` style="color:${color}"` : ''} dir="ltr">${v}</div>`;
    }
    function build(row) {
        const ch = Number(row.percent_change || 0);
        const c = ch >= 0 ? '#10b981' : '#f43f5e';
        const flags = ['f_roobi', 'f_susp', 'f_clock', 'f_jet', 'f_noqteh'].filter(k => row[k]).map(k => FLAGS[k]);
        const pe = Number(row.pe || 0), eps = Number(row.eps || 0);
        const vr = (row.vol_ratio === null || row.vol_ratio === undefined || isNaN(row.vol_ratio)) ? null : Number(row.vol_ratio);
        let inWl = false; try { inWl = !!(window.WL && WL.has(row.symbol)); } catch (e) {}
        return `<div class="sh-head"><b style="color:var(--accent-blue,#38bdf8)">${row.symbol || ''}</b>`
            + `<span class="sh-name">${row.name || ''}</span>${inWl ? '<span class="sh-pin">📌</span>' : ''}</div>`
            + (row.sector_name ? `<div class="sh-sector">${row.sector_name}</div>` : '')
            + `<div class="sh-grid">`
            + cell('آخرین', n(row.p_last))
            + cell('تغییر', (ch >= 0 ? '+' : '') + ch.toFixed(1) + '%', c)
            + cell('پایانی', n(row.p_closing))
            + cell('معاملات', n(row.q_tot_tran))
            + cell('P/E', pe > 0 ? pe.toFixed(2) : '—')
            + cell('EPS', eps !== 0 ? n(eps) : '—')
            + cell('حجم/میانگین', vr === null ? '—' : vr.toFixed(2) + 'x', vr !== null && row.suspicious_vol ? '#f43f5e' : '')
            + cell('ارزش', n(row.q_tot_cap))
            + `</div>`
            + (flags.length ? `<div class="sh-flags">${flags.join(' · ')}</div>` : '');
    }
    function show(row, rect) {
        if (!card) { card = document.createElement('div'); card.id = 'symHoverCard'; document.body.appendChild(card); }
        card.innerHTML = build(row);
        card.style.display = 'block';
        const w = 292, h = card.offsetHeight || 180;
        let left = Math.min(Math.max(8, rect.left + 12), window.innerWidth - w - 10);
        let top = rect.bottom + 6;
        if (top + h > window.innerHeight - 8) top = Math.max(8, rect.top - h - 6);
        card.style.left = left + 'px'; card.style.top = top + 'px';
    }
    function hide() { clearTimeout(timer); timer = null; cur = null; if (card) card.style.display = 'none'; }
    document.addEventListener('mouseover', function (e) {
        const tr = e.target && e.target.closest ? e.target.closest('#marketTableBody tr[data-sym]') : null;
        if (!tr || tr === cur) return;
        if (e.target.closest && e.target.closest('button')) return;   // روی دکمه‌ها پیش‌نمایش نده
        cur = tr; clearTimeout(timer);
        timer = setTimeout(function () {
            const sym = tr.getAttribute('data-sym');
            // marketData یک let سراسری است (روی window نیست) → دسترسی مستقیم با گارد
            const arr = (typeof marketData !== 'undefined' && Array.isArray(marketData)) ? marketData : [];
            const row = arr.find(r => r.symbol === sym);
            if (row) show(row, tr.getBoundingClientRect());
        }, 350);
    });
    document.addEventListener('mouseout', function (e) {
        const tr = e.target && e.target.closest ? e.target.closest('#marketTableBody tr[data-sym]') : null;
        if (tr && !tr.contains(e.relatedTarget)) hide();
    });
    window.addEventListener('scroll', hide, true);
    document.addEventListener('click', hide);
})();

// تاریخ و زمان معاملات به شمسی: "📅 ۱۴۰۵/۰۶/۰۷ — معاملات ۹:۰۰ تا ۱۲:۳۰ | آخرین بروزرسانی ۲۰:۳۸"
function updateMarketDateInfo(meta, live_count, fossil_count) {
    const el = document.getElementById('marketDateInfo');
    if (!el) return;
    if (!meta) { el.textContent = '📅 تاریخ بازار در دسترس نیست'; return; }
    let d = meta.d_even;
    if (d && d > 20260000) {
        const s = String(d);
        const gy = parseInt(s.slice(0, 4), 10), gm = parseInt(s.slice(4, 6), 10), gd = parseInt(s.slice(6, 8), 10);
        // d_even تاریخ میلادی است (قرارداد TSETMC جدید: 20260829 = 29 Aug 2026)
        const g = gregorianToJalaaliParts(gy, gm, gd);
        const parts = `${g.jy}/${String(g.jm).padStart(2, '0')}/${String(g.jd).padStart(2, '0')}`;
        const h = meta.h_even || 0;
        const hh = String(Math.floor(h / 10000)).padStart(2, '0');
        const mm = String(Math.floor(h % 10000 / 100)).padStart(2, '0');
        let html = `📅 <b>${parts}</b>`;
        let tip = `معاملات ۹:۰۰ تا ۱۲:۳۰`;
        if (meta.last_sync) {
            const m = String(meta.last_sync).match(/^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})/);
            if (m) {
                const g = gregorianToJalaaliParts(parseInt(m[1]), parseInt(m[2]), parseInt(m[3]));
                html += ` · ⏱ ${m[4]}:${m[5]}`;
                tip += ` | آخرین آپدیت: ${g.jm}/${g.jd} ${m[4]}:${m[5]}`;
            }
        }
        if (hh) { html += ` · 🕐 ${hh}:${mm}`; tip += ` | آخرین معامله: ${hh}:${mm}`; }
        if (typeof live_count !== 'undefined' && live_count) {
            html += ` · 🟢 ${live_count}` + (fossil_count ? ` · 💤 ${fossil_count}` : '');
            tip += ` | 🟢 ${live_count} نماد فعال` + (fossil_count ? ` | 💤 ${fossil_count} خارج از تابلو` : '');
        }
        el.innerHTML = html;
        el.title = tip;
    } else {
        el.textContent = '📅 تاریخ بازار در دسترس نیست';
    }
}

function formatNumber(num) {
    if (num == null || isNaN(num)) return '—';
    const useMB = document.getElementById('formatMBToggle') && document.getElementById('formatMBToggle').checked;
    const fa = (n, d) => Number(n).toLocaleString('fa-IR', { maximumFractionDigits: d });
    if (!useMB) return fa(num, 0);
    if (Math.abs(num) >= 1e9) return fa(num / 1e9, 2) + ' B';
    if (Math.abs(num) >= 1e6) return fa(num / 1e6, 2) + ' M';
    return fa(num, 0);
}

/* چرا PE/EPS این نماد نیست؟ (TSETMC برای ابزارهای غیرسهامی EPS اعلام نمیکند) */
function epsWhy(name) {
    const n = name || '';
    if (/صندوق|ص\.س|ص س|سرمایه قرار|«ص/.test(n)) return 'صندوق: بدون EPS';
    if (/مرابحه/.test(n)) return 'مرابحه: بدون EPS';
    if (/اخزا|اسناد|اوراق|خزانه|گواهی/.test(n)) return 'اوراق: بدون EPS';
    if (/حق.*تقدم|ح /.test(n)) return 'حق تقدم: بدون EPS';
    if (/اختیار|آتی|اجاره ریلی/.test(n)) return 'مشتقه: بدون EPS';
    if (/کالا/.test(n)) return 'بورس کالا: بدون EPS';
    if (/تسهیلات/.test(n)) return 'تسهیلات: بدون EPS';
    return 'بدون EPS (TSETMC)';
}

function populateSectors() {
    const sectorSelect = document.getElementById('sectorFilter');
    if (!sectorSelect) return;
    // بازنشانی تکراری (هر refresh نباید آپشنها دوباره add شود)
    const prevValue = sectorSelect.value;
    sectorSelect.innerHTML = '<option value="">گروه صنعت: همه گروهها</option>';
    const sectors = [...new Set(marketData.map(d => d.sector_name).filter(Boolean))].sort();
    sectors.forEach(s => {
        const opt = document.createElement('option');
        opt.value = s;
        opt.innerText = s;
        sectorSelect.appendChild(opt);
    });
    if (prevValue && [...sectorSelect.options].some(o => o.value === prevValue)) {
        sectorSelect.value = prevValue; // انتخاب قبلی حفظ شود
    }
}

function applyFilters() {
    const query = document.getElementById('symbolSearch').value.toLowerCase().trim();
    try { stSet('marketSearch', query); } catch (e) {}
    const sectorSelect = document.getElementById('sectorFilter');
    const sector = sectorSelect ? sectorSelect.value : '';
    
    // Get ALL checkboxes (11 TSETMC asset types)
    const activeAssets = Array.from(document.querySelectorAll('.asset-cb:checked')).map(cb => cb.value);
    const tradeState = document.querySelector('input[name="tradeState"]:checked') ? document.querySelector('input[name="tradeState"]:checked').value : 'all';
    
    filteredData = marketData.filter(d => {
        // خارج از تابلو: فقط اگر چک‌باکس فعال است
        if (d.is_live === false) {
            let showF = true;
            try { showF = stGet('showFossils', true); } catch (e) {}
            if (!showF) return false;
        }
        if (tradeState === 'traded' && d.q_tot_tran === 0) return false;
        const matchQuery = d.symbol.toLowerCase().includes(query) || (d.name && d.name.toLowerCase().includes(query));
        const matchSector = sector === '' || d.sector_name === sector;
        
        // TSETMC Asset Type Classification (robust — سمت راست به چپ اولویت)
        const name = (d.name || '').replace(/\u200c/g, '').replace(/ي/g, 'ی');
        const sym = (d.symbol || '').replace(/\u200c/g, '').toUpperCase();
        const sec = (d.sector_name || '').replace(/\u200c/g, '');
        let assetType = 'stock';

        if (sym.startsWith('ض') || (sym.startsWith('ط') && !sym.startsWith('طال'))) assetType = 'option';
        else if (name.includes('صندوق') || name.includes('ETF') || sec.includes('صندوق سرمايه')) assetType = 'fund';
        else if (sym.startsWith('اخزا') || sym.startsWith('اراد') || sym.startsWith('افاد') || sym.startsWith('گام') || name.includes('اوراق') || name.includes('اسناد') || sec.includes('اوراق تامين')) assetType = 'bond';
        else if (sym.endsWith('ح') || name.includes('حق تقدم')) assetType = 'right';
        else if (sym.startsWith('تسه') || sym.startsWith('تملی') || name.includes('تسهیلات')) assetType = 'teseh';
        else if (sym.startsWith('طال') || sym.includes('TAL')) assetType = 'tal';
        else if (name.includes('آتی') && /[0-9]$/.test(sym)) assetType = 'ati';
        else if (sec.includes('کالا') || sym.includes('سلف') || name.includes('سلف')) assetType = 'kala';
        else if (sec.includes('انرژی') || sec.includes('برق') || name.includes('انرژی')) assetType = 'energy';
        else if (Number(d.board) === 2) assetType = 'payeh';

        // سهام = بازار بورس، فرابورس-پایه = بازار فرابورس (تفکیک با d.board)
        const matchAsset = assetType === 'stock' ? activeAssets.includes('stock')
            : assetType === 'payeh' ? activeAssets.includes('payeh')
            : activeAssets.includes(assetType);
        
        // Combinable Quick Filters (ALL must pass if active)
        let matchQuick = true;
        if(activeFilters.has('f_roobi') && !d.f_roobi) matchQuick = false;
        if(activeFilters.has('f_susp') && !d.f_susp) matchQuick = false;
        if(activeFilters.has('f_clock') && !d.f_clock) matchQuick = false;
        if(activeFilters.has('f_jet') && !d.f_jet) matchQuick = false;
        if(activeFilters.has('f_noqteh') && !d.f_noqteh) matchQuick = false;
        // فیلترهای سفارشی کاربر — با هم AND (all active custom)
        const activeCustoms = window.customFilters ? customFilters.filter(f => f.active !== false) : [];
        for (const cf of activeCustoms) {
            if (!evalCustomFilter(cf, d)) matchQuick = false;
        }

        return matchQuery && matchSector && matchAsset && matchQuick;
    });
    
    if (sortCol) doSortLogic();
    else renderTable(filteredData);
}

/* ---------- debounce: تایپ در جستجو یا toggle فیلترها نباید رندر سنگین جدول را در هر keystroke اجرا کند ---------- */
let _applyDebounce = null;
function applyFiltersDebounced() {
    clearTimeout(_applyDebounce);
    _applyDebounce = setTimeout(applyFilters, 220);
}

function handleSort(colKey) {
    if (Date.now() - (window.__colDragTs || 0) < 500) return;   // کلیکِ بی‌هدف بعد از درگ = سورت نکن
    if (sortCol === colKey) {
        sortAsc = !sortAsc;
    } else {
        sortCol = colKey;
        sortAsc = false; // default to descending first for financial data
    }
    updateSortIndicators(colKey);
    doSortLogic();
}

function updateSortIndicators(activeCol) {
    // نشانگر ↑/↓ روی هدر فعال، حذف از بقیه
    const arrow = sortAsc ? '↑' : '↓';
    document.querySelectorAll('#marketTable th').forEach(th => {
        const oc = th.getAttribute('onclick') || '';
        // v9.1: هدرهای غیرقابل‌مرتب‌سازی (فیلترها/وضعیت/عملیات) پیک ↕ نمی‌گیرند
        if (oc.indexOf('handleSort(') === -1) return;
        const label = th.textContent.replace(/[↕↑↓]/g, '').trim();
        th.textContent = label + (oc.includes(`'${activeCol}'`) ? ' ' + arrow : ' ↕');
    });
}

// Robust value parser: handles commas ("1,500"), M/B suffixes ("1.5 M", "2.3 B"),
// Persian digits ("۱٬۵۰۰"), and plain numbers. Returns a float (or original string for text cols).
function parseSortValue(v) {
    if (v === null || v === undefined || v === '') return -Infinity; // null → پایین جدول
    if (typeof v === 'number') return v;
    let s = String(v).trim();
    if (!s) return -Infinity;
    // Persian/Arabic digits -> ASCII
    s = s.replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
         .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));
    // strip thousands separators (comma and Persian ٬)
    const cleaned = s.replace(/[,\u066C\u060C]/g, '');
    // M/B/T suffixes
    let mult = 1;
    let m = cleaned.match(/^([-+]?[\d.]+)\s*([MBT]|میلیارد|میلیون|هزار)?$/i);
    if (m) {
        const num = parseFloat(m[1]);
        if (isNaN(num)) return NaN;
        const suf = (m[2] || '').toUpperCase();
        if (suf === 'B') mult = 1e9;
        else if (suf === 'M') mult = 1e6;
        else if (suf === 'T') mult = 1e12;
        else if (suf === 'هزار' || suf === 'K') mult = 1e3;
        else if (suf === 'میلیون') mult = 1e6;
        else if (suf === 'میلیارد') mult = 1e9;
        return num * mult;
    }
    return NaN; // not a numeric shape -> caller falls back to localeCompare
}

function doSortLogic() {
    // فسیل‌ها (غیرفعال) همیشه آخر — ال‌جیسیک ولی پشت سر همهٔ زنده‌ها
    const fossilA = a => (a.is_live === false) ? 1 : 0;
    filteredData.sort((a, b) => {
        const fa = fossilA(a), fb = fossilA(b);
        if (fa !== fb) return fa - fb;
        let valA = a[sortCol];
        let valB = b[sortCol];
        const numA = parseSortValue(valA);
        const numB = parseSortValue(valB);
        // null/empty → همیشه پایین جدول (در هر دو جهت صعودی/نزولی)
        if (numA === -Infinity || numB === -Infinity) {
            if (numA === numB) return 0;
            return numA === -Infinity ? 1 : -1;
        }
        // Both numeric -> numeric compare
        if (!isNaN(numA) && !isNaN(numB)) {
            return sortAsc ? numA - numB : numB - numA;
        }
        // Text -> Persian-aware locale compare
        const strA = String(valA === null || valA === undefined ? '' : valA).trim();
        const strB = String(valB === null || valB === undefined ? '' : valB).trim();
        return sortAsc ? strA.localeCompare(strB, 'fa') : strB.localeCompare(strA, 'fa');
    });
    renderTable(filteredData);
}

function renderTable(data) {
    const tbody = document.getElementById('marketTableBody'); tbody.innerHTML = '';
    const shown = data.length;
    document.getElementById('statShown').innerText = shown;
    document.getElementById('statTotal').innerText = marketData.length;
    // خلاصهٔ فیلترهای فعال
    const active = [];
    if (activeFilters.has('f_roobi')) active.push('🧹 کف روبی صف فروش');
    if (activeFilters.has('f_susp')) active.push('🔥 حجم مشکوک');
    if (activeFilters.has('f_clock')) active.push('⏰ الگوی ساعت');
    if (activeFilters.has('f_jet')) active.push('🚀 فیلتر جت');
    if (activeFilters.has('f_noqteh')) active.push('🎯 نقطه زنی');
    const statEl = document.getElementById('statSummary');
    if (statEl) {
        // شمارش توزیع فیلترها: چند نماد ۲+ فیلتر دارند
        const multi = data.filter(r => ['f_roobi','f_susp','f_clock','f_jet','f_noqteh'].filter(k => r[k]).length >= 2).length;
        const one = data.filter(r => ['f_roobi','f_susp','f_clock','f_jet','f_noqteh'].filter(k => r[k]).length === 1).length;
        statEl.innerText = (active.length ? ('فیلترهای فعال: ' + active.join(' | ') + ' · ') : '')
            + `📊 ${one} تکفیلتری · 🔥 ${multi} چندفیلتری (۲+)`;
    }
    const groupBy = false; // گروه‌بندی صنعتی حذف شد (باغبا بود)
    
    if (groupBy) {
        // بهینه‌سازی: ساخت HTML رشته‌ای یک‌جا (۱۰۰× سریع‌تر از ۴۰۰۰× appendChild)
        const groups = {};
        data.forEach(d => { const sec = d.sector_name || 'سایر'; if(!groups[sec]) groups[sec] = []; groups[sec].push(d); });
        let html = '';
        for (const [sec, items] of Object.entries(groups)) {
            html += `<tr><td colspan="13" style="background:var(--accent-blue); color:#fff; font-weight:bold; text-align:center;">${sec} (${items.length})</td></tr>`;
            for (const row of items) html += createRowHtml(row);
        }
        tbody.innerHTML = html;
    } else {
        // v9.7.6 — پین واچ‌لیست: نمادهای ستاره‌دار همیشه بالای جدول (sort پایدار —
        // ترتیب ستون/فیلتر بین بقیهٔ ردیف‌ها دست‌نخورده می‌ماند)
        let view = data;
        try {
            if (window.WL && WL.list && WL.list.length) {
                view = data.slice().sort((a, b) => (WL.has(b.symbol) ? 1 : 0) - (WL.has(a.symbol) ? 1 : 0));
            }
        } catch (e) {}
        let html = '';
        view.slice(0, 200).forEach(row => html += createRowHtml(row));
        tbody.innerHTML = html;
    }
    applyColShow();
    applyColOrder('marketTable');
}

/* ---------- نمایش/مخفی ستون‌ها — با CSS داینامیک (بدون loop روی سلول‌ها) ---------- */

function _colKeyOf(el) { return el.dataset.col || el.textContent.trim().replace(/[↕↑↓]/g, ''); }
function rebuildColgroup(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const cg = table.querySelector('colgroup');
    if (!cg) return;
    let saved = {};
    try { saved = JSON.parse(stGet('colw_' + tableId, '{}') || '{}'); } catch (e) {}
    const ths = Array.from(table.querySelectorAll('thead th'));
    const visible = ths.filter(function (th) { return th.style.display !== 'none' && !th.matches('[style*="display: none"]') && getComputedStyle(th).display !== 'none'; });
    cg.innerHTML = '';
    visible.forEach(function (th, k) {
        const col = document.createElement('col');
        const w = saved[_colKeyOf(th)];
        const pct = th.getAttribute('data-w');           // v9.1: پهنای نسبی اعلام‌شده در HTML
        if (w) col.style.width = w + 'px';
        else if (pct) col.style.width = pct + '%';
        else col.style.width = (k === visible.length - 1) ? '' : 'auto';
        cg.appendChild(col);
    });
    table.style.width = '100%';
}
function applyColShow() {
    // یک <style> واحد در <head>؛ موتور CSS بومی مخفی‌سازی را انجام می‌دهد
    // (قبلاً برای هر td/th style.display دستی ست می‌شد — O(rows×cols) و بسیار کند)
    let styleEl = document.getElementById('colShowStyle');
    if (!styleEl) {
        styleEl = document.createElement('style');
        styleEl.id = 'colShowStyle';
        document.head.appendChild(styleEl);
    }
    let css = '';
    let anyHidden = false;
    document.querySelectorAll('.colshow-cb').forEach(cb => {
        if (!cb.checked) {
            anyHidden = true;
            const col = cb.dataset.col;
            css += `#marketTable th[data-col="${col}"], #marketTable td.c-${col} { display: none !important; }\n`;
        }
    });
    styleEl.textContent = css;
    try {
        const st = {};
        document.querySelectorAll('.colshow-cb').forEach(cb => st[cb.dataset.col] = cb.checked);
        stSet('tsetmcCols', JSON.stringify(st));
    } catch (e) {}
    // ستون مخفی‌شده باید از colgroup هم حذف شود، وگرنه px آن فضا رها میکند (صفحه خالی)
    try { rebuildColgroup('marketTable'); } catch (e) {}
    try { rebuildColgroup('screenerTable'); } catch (e) {}
}

/* ---------- ردیف جدول تابلوخوانی به‌صورت رشته (رندر یک‌جا) ----------
   v9.2: تابع مردهٔ createRow (نسخهٔ DOM‌ساز قدیمی با تک‌دکمهٔ «تحلیل») حذف شد؛
   createRowHtml تنها مسیر رندر است. */
function createRowHtml(row) {
    const c = row.percent_change >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
    const vr = (row.vol_ratio === null || row.vol_ratio === undefined || isNaN(row.vol_ratio)) ? null : Number(row.vol_ratio);
    let volBadge = '-', volBarClass = 'bar-green', volCellStyle = '';
    if (vr !== null && row.suspicious_vol) {
        volBadge = `<span class="susp-txt">🔥 ${vr.toFixed(1)}x</span>`;
        volBarClass = 'bar-red';
        volCellStyle = 'cell-susp';
    } else if (vr !== null && vr >= 1.5) {
        volBadge = `⚠️ ${vr.toFixed(1)}x`;
        volBarClass = 'bar-yellow';
    } else if (vr !== null) {
        volBadge = `${vr.toFixed(1)}x`;
        volBarClass = 'bar-green';
    }
    const volPct = vr === null ? 0 : Math.min(100, Math.round(vr * 20));
    const bp = Number(row.buy_power_i) || 0;
    const sp = Number(row.sell_power_i) || 0;
    const bpBarClass = bp >= sp * 1.5 ? 'bar-green' : (bp >= sp * 1.1 ? 'bar-yellow' : 'bar-red');
    // نوار همیشه رنگ اکسنت (نه currentColor = text-primary که در light مشکی میشود)
    const powerHtml = `
        <span class="cell-bar ${bpBarClass}">
            <span dir="ltr" style="font-weight:800; color:var(--accent-green);">${bp.toLocaleString('fa-IR')}</span>
            <span style="opacity:.55; font-size: 0.5625rem;">خرید</span>
        </span>
        <span class="cell-bar ${bpBarClass}">
            <span dir="ltr" style="font-weight:800; color:var(--accent-red);">${sp.toLocaleString('fa-IR')}</span>
            <span style="opacity:.55; font-size: 0.5625rem;">فروش</span>
        </span>`;
    const fbs = ['f_roobi','f_susp','f_clock','f_jet','f_noqteh'].filter(k => row[k]);
    const badgeHtml = fbs.map(k => ({ 'f_roobi':'🧹','f_susp':'🔥','f_clock':'⏰','f_jet':'🚀','f_noqteh':'🎯' }[k])).join(' ')
        || '<span style="opacity:.25; font-size: 0.625rem;">—</span>';
    const esc = s => String(s === null || s === undefined ? '' : s)
        .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    // همت: q_tot_cap به ریال است؛ همت = ÷ ۱۰^۱۲ — با toggle M/B
    const qcap = Number(row.q_tot_cap);
    const qcapStr = (qcap > 0) ? formatNumber(qcap) : '—';
    const symEsc = esc(row.symbol), nameEsc = esc(row.name || '');
    // v9.1: بج وضعیت سبد در جدول تابلوخوانی هم نمایش داده می‌شود
    // (data-st هم همین‌جا ست می‌شود؛ جدول هر چند ثانیه بازسازی می‌شود و
    //  SEL.paint فقط هنگام تصمیم اجرا می‌شود، وگرنه رنگ دکمهٔ ⚑ پر می‌کشد)
    let selBadge = '<span class="sel-badge" style="color:#94a3b8;background:rgba(148,163,184,.14);border:1px solid rgba(148,163,184,.33);">○ بررسی‌نشده</span>';
    let selSt = 'pending';
    try { if (window.SEL) { selBadge = SEL.badge(row.symbol); selSt = SEL.statusOf(row.symbol); } } catch (e) {}
    const fossil = row.is_live === false;
    const trClass = fossil ? 'fossil-row' : '';
    return `<tr style="cursor:pointer;" class="${trClass}" data-sym="${symEsc}">
        <td class="c-symbol" style="font-weight:800; color:var(--accent-blue);">${symEsc}</td>
        <td class="c-name" style="font-size: 0.6875rem; color:var(--text-secondary);">${nameEsc}</td>
        <td class="c-p_last" dir="ltr" style="font-weight:700;">${formatNumber(row.p_last)}</td>
        <td class="c-p_closing" dir="ltr" style="font-weight:700; color:${c};">${formatNumber(row.p_closing)}</td>
        <td class="c-percent_change" dir="ltr" style="font-weight:800; color:${c};">${row.percent_change >= 0 ? '+' : ''}${Number(row.percent_change || 0).toFixed(1)}%</td>
        <td class="c-pe">${(() => {
            const v = Number(row.pe || 0);
            if (v > 0) return `<span dir="ltr">${Number(v).toFixed(2)}</span>`;
            if (v < 0) return `<span dir="ltr" style="color:var(--accent-red);">${v.toFixed(2)}</span>`;
            return `<span dir="rtl" class="eps-why">${epsWhy(row.name)}</span>`;
        })()}</td>
        <td class="c-eps">${(() => {
            const v = Number(row.eps || 0);
            if (v > 0) return `<span dir="ltr">${v.toLocaleString('fa-IR')}</span>`;
            if (v < 0) return `<span dir="ltr" style="color:var(--accent-red);">${v.toLocaleString('fa-IR')}</span>`;
            return `<span dir="rtl" class="eps-why">${epsWhy(row.name)}</span>`;
        })()}</td>
        <td class="c-vol_ratio ${volCellStyle}" dir="ltr"><span class="cell-bar ${volBarClass}"><span>${volBadge}</span></span></td>
        <td class="c-buy_power" dir="ltr">${powerHtml}</td>
        <td class="c-q_tot_tran" dir="ltr">${formatNumber(row.q_tot_tran)}</td>
        <td class="c-q_tot_cap" dir="ltr">${qcapStr}</td>
        <td class="c-filters">${badgeHtml}</td>
        <td class="c-sel" data-selcell="${symEsc}" style="text-align:center; white-space:nowrap;">
            <span data-selbadge>${selBadge}</span><button class="qa-btn" data-st="${selSt}" title="ثبت سریع وضعیت سبد (تایید / زیر نظر / رد)" onclick="event.stopPropagation(); SEL.quickMenu('${symEsc}', '${nameEsc}', this)">⚑</button>
        </td>
        <td class="c-actions"><div class="op-cell">
            <button class="op-btn op-btn--tech" title="باز کردن چارت + نوار تصمیم Accept/Reject/Monitor" onclick="event.stopPropagation(); gotoChart('${symEsc}', '${nameEsc}')">📊 تکنیکال</button>
            <button class="op-btn op-btn--fund" onclick="event.stopPropagation(); openAnalysis('${symEsc}', '${nameEsc}')">🏛️ تحلیل کامل</button>
        </div></td>
    </tr>`;
}


// Screener Logic
async function initScreener(force) {
    const now = Date.now();
    if (!force && now < screenerNextFetch) return;
    screenerNextFetch = now + 60000; // refresh at most every 60s unless forced
    // بازیابی جستجوی کدال از STATE  (v9.1: فیلتر حداقل امتیاز کاملاً حذف شد)
    try {
        const q = stGet('screenerSearch', '');
        const si = document.getElementById('screenerSearch');
        if (si && q) si.value = q;
    } catch (e) {}
    try {
        const res = await fetch('/api/screener');
        const json = await res.json();
        if (json.status === 'success') {
            screenerData = json.data;
            filteredScreenerData = [...json.data];
            populateScreenerSectors(); // پر کردن گروه صنعت (سایدبار)
            applyScreenerSearch(); // جستجوی ذخیره‌شده را اعمال کن
            doSortScreenerLogic();
        }
    } catch (e) {
        console.error(e);
        screenerNextFetch = 0; // allow retry on next call
    }
}

function handleSortScreener(colKey) {
    if (sortColScreener === colKey) sortAscScreener = !sortAscScreener;
    else { sortColScreener = colKey; sortAscScreener = false; }
    try { stSet('screenerSort', JSON.stringify({ col: sortColScreener, asc: sortAscScreener })); } catch (e) {}
    const arrow = sortAscScreener ? '↑' : '↓';
    document.querySelectorAll('#screenerTable th').forEach(th => {
        const label = th.textContent.replace(/[↕↑↓]/g, '').trim();
        const isActive = th.getAttribute('onclick') && th.getAttribute('onclick').includes(`'${colKey}'`);
        th.textContent = label + (isActive ? ' ' + arrow : ' ↕');
    });
    doSortScreenerLogic();
}

function doSortScreenerLogic() {
    filteredScreenerData.sort((a, b) => {
        let va = a[sortColScreener]; let vb = b[sortColScreener];
        const na = parseSortValue(va), nb = parseSortValue(vb);
        // null/empty → همیشه پایین جدول (در هر دو جهت)
        if (na === -Infinity || nb === -Infinity) {
            if (na === nb) return 0;
            return na === -Infinity ? 1 : -1;
        }
        if (!isNaN(na) && !isNaN(nb)) {
            return sortAscScreener ? na - nb : nb - na;
        }
        const sa = String(va === null || va === undefined ? '' : va).trim();
        const sb = String(vb === null || vb === undefined ? '' : vb).trim();
        return sortAscScreener ? sa.localeCompare(sb, 'fa') : sb.localeCompare(sa, 'fa');
    });
    renderScreenerTable(filteredScreenerData);
}

function applyScreenerSearch() {
    const q = (document.getElementById('screenerSearch').value || '').trim();
    try { stSet('screenerSearch', q); } catch (e) {}
    // فیلتر نوع نماد (سایدبار — همان طبقه‌بندی تب بازار)
    const activeAssets = Array.from(document.querySelectorAll('.screener-asset-cb:checked')).map(cb => cb.value);
    // فیلتر گروه صنعت (سایدبار)
    const sectorSel = document.getElementById('screenerSectorFilter');
    const sector = sectorSel ? sectorSel.value : '';
    let base = screenerData;
    if (!q) {
        filteredScreenerData = [...base];
    } else {
        const ql = q.toLowerCase();
        filteredScreenerData = base.filter(r =>
            String(r.symbol || '').toLowerCase().includes(ql) ||
            String(r.name || '').includes(q) ||
            String(r.sector_name || '').includes(q));
    }
    // اعمال asset-type فیلتر
    if (activeAssets.length && activeAssets.length < 6) {
        filteredScreenerData = filteredScreenerData.filter(r => {
            const at = classifyScreenerAsset(r);
            return activeAssets.includes(at);
        });
    }
    // اعمال sector فیلتر
    if (sector) {
        filteredScreenerData = filteredScreenerData.filter(r => String(r.sector_name || '') === sector);
    }
    doSortScreenerLogic();
}

// پر کردن select گروه صنعت از داده‌ها (یک‌بار)
function populateScreenerSectors() {
    try {
        const sel = document.getElementById('screenerSectorFilter');
        if (!sel || sel.dataset.filled) return;
        const secs = [...new Set((screenerData || []).map(r => (r.sector_name || '').trim()).filter(Boolean))].sort();
        secs.forEach(s => {
            const o = document.createElement('option');
            o.value = s; o.textContent = s;
            sel.appendChild(o);
        });
        sel.dataset.filled = '1';
    } catch (e) {}
}

// دلیل نبودن داده — کوتاه و رنگی (به‌جای سلول خالی)
// طبقه‌بندی نوع نماد کدال (همان منطق فعلی بازار — TSETMC asset types)
function classifyScreenerAsset(d) {
    const name = (d.name || '').replace(/\u200c/g, '').replace(/ي/g, 'ی');
    const sym = (d.symbol || '').replace(/\u200c/g, '').toUpperCase();
    const sec = (d.sector_name || '').replace(/\u200c/g, '');
    if (sym.startsWith('ض') || (sym.startsWith('ط') && !sym.startsWith('طال'))) return 'option';
    if (sym.startsWith('حق') || (name && /حق تقدم|حق خرید|حق پذیره/.test(name))) return 'right';
    if (/(صندوق|بازارگردانی)/.test(name) || /صندوق/.test(sec) || /قابل معامله/.test(name)) return 'fund';
    if (/بورس کالا|بورس كالا/.test(sec) || /کالا/.test(name) && /بورس/.test(name)) return 'kala';
    if (/بازار پایه|سازمان یافته|فرابورس/.test(sec)) return 'payeh';
    return 'stock';
}

var numFmt = 'jooze'; // 'jooze' = حذف ۴ رقم از راست (میلیون ریال → میلیارد تومان) | 'raw' = خام کدال
try {
    var _nf = stGet('numFmt', localStorage.getItem('numFmt'));
    if (_nf === 'jooze' || _nf === 'raw') numFmt = _nf;
} catch (e) {}

function setNumFmt(v) {
    numFmt = (v === 'raw') ? 'raw' : 'jooze';
    try { stSet('numFmt', numFmt); } catch (e) {}
    // sync toggle جدید (جایگزین radio)
    const tg = document.getElementById('numFmtToggle');
    if (tg) tg.checked = (numFmt === 'jooze');
    if (typeof screenerData !== 'undefined') renderScreenerTable(screenerData);
}

// نمایش مبلغ: خام کدال (میلیون ریال) یا حذف ۴ رقم از راست (میلیون ریال → همت/میلیارد تومان)
// فرمول جزوه استاد: ۴ رقم از راست خط بزن و بخوان (÷۱۰۰۰۰)
function fmtMoney(v) {
    if (v == null || isNaN(v)) return '—';
    if (numFmt === 'raw') {
        return v.toLocaleString('fa-IR') + ' میلیون ریال';
    }
    const b = v / 10000;   // جزوه: میلیون ریال → میلیارد تومان
    if (b >= 1000) return (b / 1000).toLocaleString('fa-IR', { maximumFractionDigits: 1 }) + ' همت';
    if (b >= 1) return b.toLocaleString('fa-IR', { maximumFractionDigits: 2 }) + ' میلیارد تومان';
    // کمتر از یک میلیارد → میلیون تومان (همان «۴ رقم خط بزن» ولی ریز)
    return (b * 1000).toLocaleString('fa-IR', { maximumFractionDigits: 1 }) + ' میلیون تومان';
}

function renderScreenerTable(data) {
    const tbody = document.getElementById('screenerTableBody');
    // v9.0: بافت FTS هر نماد به سازوکار سبد داده می‌شود (نام/صنعت/حالت قیمت/امتیاز)
    try { if (window.SEL) SEL.remember(data); } catch (e) {}
    document.getElementById('screenerStatShown').innerText = data.length;
    document.getElementById('screenerStatTotal').innerText = screenerData.length;
    const live = data.filter(r => !r.excluded);
    const high = live.filter(r => r.score >= 4).length;
    const neutral = live.filter(r => r.score >= 2 && r.score < 4).length;
    const low = live.filter(r => r.score < 2).length;
    const dropped = data.length - live.length;
    document.getElementById('screenerStatSummary').innerText =
        `🟢 ${high} امتیاز بالا | 🟡 ${neutral} متوسط | 🔴 ${low} ضعیف | ⛔ ${dropped} حذف‌شده`;
    // رندر رشته‌ای یک‌جا (مثل renderTable) — جایگزین ۱۵۰× createElement/appendChild
    const MODE = { free: ['آزاد / بورس کالا', '#10b981'],
                   mandatory: ['دستوری', '#f43f5e'],
                   neutral: ['خنثی', '#94a3b8'] };
    let html = '';
    data.slice(0, 150).forEach(row => {
        const symbol = String(row.symbol).replace(/'/g, "\\'");
        const name = String(row.name || '').replace(/'/g, "\\'");

        let scoreColor = '#94a3b8';
        if (row.score >= 4) scoreColor = '#10b981';
        else if (row.score <= 1) scoreColor = '#f43f5e';

        // ۱) رشد فروش تجمیعی
        let growthTxt = '<span style="font-size:0.5625rem;color:#787b86;">بدون داده</span>', growthColor = '';
        if (row.rev_growth != null && !isNaN(row.rev_growth)) {
            growthTxt = row.rev_growth.toFixed(1) + '%';
            if (row.growth_excellent) growthColor = '#10b981';
            else if (row.growth_pass) growthColor = '#4ade80';
            else if (row.rev_growth >= 0) growthColor = '#94a3b8';
            else growthColor = '#f43f5e';
        }
        // ۲) روند EPS سالانهٔ حسابرسی‌شدهٔ غیرتلفیقی
        let epsTxt, epsColor;
        if (row.i2_pass) { epsTxt = (row.eps_series || []).join(' → '); epsColor = '#10b981'; }
        else if (row.eps_data_gap) { epsTxt = 'بدون داده'; epsColor = '#787b86'; }
        else { epsTxt = (row.eps_series || []).join(' → ') || '—'; epsColor = '#f43f5e'; }
        // ۳) حاشیه ناخالص
        const gmTxt = row.gross_margin != null ? row.gross_margin.toFixed(1) + '%' : '—';
        const gmColor = row.i3_pass ? (row.margin_optimal ? '#10b981' : '#4ade80')
                      : (row.gross_margin == null ? '#787b86' : '#f43f5e');
        // ۴) فروش÷ارزش بازار و پتانسیل سود
        const s2mTxt = row.sales_to_mcap != null ? row.sales_to_mcap.toFixed(2) : '—';
        const s2mColor = row.i4_pass ? '#10b981' : (row.sales_to_mcap == null ? '#787b86' : '#f43f5e');
        const potTxt = row.profit_potential_pct != null ? row.profit_potential_pct.toFixed(1) + '%' : '—';
        // ۵) نوع قیمت‌گذاری
        const md = MODE[row.pricing_mode] || MODE.neutral;
        // v9.0: بج وضعیت سبد (بررسی‌نشده / تایید / رد / زیر نظر)
        let selBadge = '<span style="font-size:.66rem;color:#94a3b8;">○ بررسی‌نشده</span>';
        let selSt = 'pending';
        try { if (window.SEL) { selBadge = SEL.badge(row.symbol); selSt = SEL.statusOf(row.symbol); } } catch (e) {}
        // v9.7.3: ستارهٔ واچ‌لیست (کلیدِ مقایسه در selection.js نرمال است، پس
        // «داريك» و «داریک» یکی حساب می‌شوند — همان باگی که سمت سرور رفع شد)
        let watchOn = false;
        try { watchOn = !!(window.WL && WL.has(row.symbol)); } catch (e) {}
        const watchBtn = `<button class="op-btn${watchOn ? ' op-btn--pinned' : ''}" title="پین/حذف از واچ‌لیست — پین‌شده‌ها بالای تابلو می‌مانند" `
            + `data-watch="${symbol}" onclick="event.stopPropagation(); WL.toggle('${symbol}', '${name}')">`
            + (watchOn ? '📌 پین‌شده' : '☆ واچ') + `</button>`;

        html += `<tr${row.excluded ? ' style="opacity:0.45;"' : ''}>
            <td style="font-weight: 800; color: #38bdf8;">${row.symbol}${row.excluded ? ' ⛔' : ''}</td>
            <td style="color: #94a3b8; font-size: 0.6875rem;">${row.name}</td>
            <td>${row.sector_name || '-'}</td>
            <td dir="ltr" style="color:${growthColor}">${growthTxt}</td>
            <td dir="ltr" style="font-size:0.6875rem; color:${epsColor}">${epsTxt}</td>
            <td dir="ltr" style="color:${gmColor}">${gmTxt}</td>
            <td dir="ltr" style="color:${s2mColor}">${s2mTxt}</td>
            <td dir="ltr">${potTxt}</td>
            <td style="color:${md[1]}; font-size:0.6875rem;">${md[0]}</td>
            <td dir="ltr" style="font-size: 0.6875rem; color:${row.mcap > 1e13 ? '#10b981' : ''}">${row.mcap > 0 ? fmtMcap(row.mcap) : '—'}</td>
            <td style="font-weight:900; font-size: 1rem; color:${scoreColor}">${row.score} / 5</td>
            <td data-selcell="${symbol}" style="text-align:center; white-space:nowrap;"><span data-selbadge>${selBadge}</span><button class="qa-btn" data-st="${selSt}" title="ثبت سریع وضعیت سبد (تایید / زیر نظر / رد)" onclick="event.stopPropagation(); SEL.quickMenu('${symbol}', '${name}', this)">⚑</button></td>
            <td><div class="op-cell">
                ${watchBtn}
                <button class="op-btn op-btn--tech" title="باز کردن چارت + نوار تصمیم Accept/Reject/Monitor" onclick="gotoChart('${symbol}', '${name}')">📊 تکنیکال</button>
                <button class="op-btn op-btn--fund" onclick="openAnalysis('${symbol}', '${name}')">🏛️ تحلیل کامل</button>
            </div></td>
        </tr>`;
    });
    tbody.innerHTML = html;
    applyColOrder('screenerTable');
}

async function openAnalysis(symbol, name) {
    document.getElementById('modalSymbol').innerText = symbol;
    document.getElementById('modalName').innerText = name;
    document.getElementById('chartModal').classList.add('active');
    switchModalTab('fund');  // تحلیل کامل = بنیادی؛ نمودار در پنل تکنیکال
    await loadFundamentalData(symbol);
}

// باز کردن خودکار مودال از URL: ?open=نماد (برای تست/اشتراک‌گذاری)
// پارامترهای اختیاری: &interval=W|M &adjust=1|0 &scale=log|linear
window.addEventListener('load', function() {
    var p = new URLSearchParams(location.search);
    var m = p.get('open');
    if (m) {
        openAnalysis(m, '').then(function() {
            var iv = p.get('interval');
            if (iv && typeof rvSetInterval === 'function') rvSetInterval(iv);
            var adj = p.get('adjust');
            if (adj !== null && typeof rvSetAdjust === 'function') rvSetAdjust(adj === '1');
            var sc = p.get('scale');
            if (sc && typeof rvSetScale === 'function') rvSetScale(sc);
        }).catch(function() {});
    }
});

function closeModal() {
    document.getElementById('chartModal').classList.remove('active');
}

/* ── تحلیل کامل (بنیادی) به static/fundamental_ui.js منتقل شد ───────────
   fmtMcap / fmtBil / loadFundamentalData / switchModalTab آنجا تعریف
   میشوند تا app.js فقط پوستهٔ ناوبری، routing و plumbing همگامسازی بماند. */

/* شورت‌کات به تب تکنیکال جدید (rv) — نماد مشخص را لود می‌کند */
function gotoChart(symbol, name) {
    try {
        /* v9.7.1 — rv.sym را «پیش از» switchView ست کن.
           switchView('tech') خودش rvInit() → rvLoad(rv.sym) را می‌زند.
           قبلاً اینجا یک rvLoad(symbol) هم اضافه صدا زده می‌شد و دو rvLoad
           همزمان می‌افتاد؛ هر کدام که دیرتر پاسخ می‌گرفت نماد را جایگزین
           می‌کرد (نماد اشتباه/چشمک‌زدن چارت هنگام باز کردن از مودال). */
        if (typeof rv !== 'undefined' && rv) rv.sym = symbol;
        switchView('tech');
        /* مودال تحلیل را ببند: وگرنه بک‌دراپِ تمام‌صفحه روی چارت تازه‌باز شده
           می‌ماند و کاربر فقط یک پردهٔ تیره می‌بیند (تأییدشده با اسکرین‌شات). */
        try { closeModal(); } catch (e) {}
        rvToastSv('📊 ' + (name || symbol) + ' — چارت تکنیکال');

    } catch (e) { console.warn('gotoChart', e); }
}


function switchView(viewId, btn) {
    // ورود به تب تابلوخوانی: فقط اگر داده‌ای لود نشده واکشی کن (ضد اسپم شبکه)
    if (viewId === 'market' && (!Array.isArray(marketData) || marketData.length === 0)) {
        initMarket();
    }
    // ورود به تب پورتفوی FTS: لود از localStorage + رندر (سینک واچ‌لیست rate-limited)
    if (viewId === 'portfolio') {
        initPortfolio();
    }
    document.querySelectorAll('.view-panel').forEach(p => p.style.display = 'none');
    document.getElementById(viewId + 'View').style.display = (viewId === 'tech') ? 'flex' : 'block';
    
    document.querySelectorAll('.nav-item').forEach(b => b.classList.remove('active'));
    if (btn) btn.classList.add('active');
    else {
        const _el = document.querySelector('.nav-item[onclick*="' + viewId + '"]');
        if (_el) _el.classList.add('active');
    }
    
    // تنظیمات TSETMC فقط در پنل تابلو؛ تنظیمات کدال فقط در پنل کدال
    const tsetmcPanel = document.getElementById('tsetmcSettingsPanel');
    if (tsetmcPanel) tsetmcPanel.style.display = (viewId === 'market') ? 'flex' : 'none';
    const codalPanel = document.getElementById('codalSettingsPanel');
    if (codalPanel) codalPanel.style.display = (viewId === 'screener') ? 'flex' : 'none';
    // v7.3: تب وضعیت بازار — ورود → refresh + polling شروع
    if (viewId === 'mstat') {
      msRefresh(true);
      const saved = (typeof stGet === 'function') ? stGet('msPollSec', '60') : '60';
      const sel = document.getElementById('msPoll');
      if (sel) sel.value = saved;
      msSetPoll(saved);
    } else if (MS_TIMER) { clearInterval(MS_TIMER); MS_TIMER = null; }
    
    if (viewId === 'screener') {
        initScreener(); // always refresh on entry (throttled 60s) — new FS rows appear
    }
    // علامت سوال بزرگ (وضعیت اتصال کدال) — فقط در تب کدال
    const connBtn = document.getElementById('codalConnBtn');
    if (connBtn) {
        connBtn.style.display = (viewId === 'screener') ? '' : 'none';
        if (viewId === 'screener') updateCodalConnStatus();
    }
    if (viewId === 'tech') {
        rvInit();
    }
    // فونت: هر تب مقدار خودش
    setFontForView(viewId);
}

/* ============ وضعیت بازار — وضعیت مالکیت (v9.8.1 فاز ۰) =============
   کل داشبوردِ وضعیت بازار در static/mstat.js است: همان msRefresh/msSetPoll
   که switchView صدا میزند، از /api/mstat/* محلی (market.db) بهجای
   پروکسیِ tradersarena.ir. اینجا عمداً «هیچ» تعریفی نمیآید تا دو نسخه از
   یک تابع در یک اسکوپ جهانی نداشته باشیم. تنها مصرفکنندهٔ بیرونی همین
   switchView('mstat') است (msRefresh / msSetPoll / MS_TIMER)؛ پس رابط
   تثبیتشدهٔ این دامنه دقیقاً همین سه نام است و افزودن چیز دیگر ممنوع.
*/

function initFontScale() {
    try {
        const v = parseInt(localStorage.getItem('fontScale') || '100', 10);
        if (!isNaN(v) && v >= 80 && v <= 130) {
            const el = document.getElementById('fontScale');
            if (el) el.value = v;
            applyFontScale(v);
        }
    } catch (e) {}
}

/* ---------- راهنمای اول-اجرا + toggle چرخش IP (ADB) ---------- */
async function fetchAdbState() {
  try { const r = await fetch('/api/adb/state'); return await r.json() || {}; }
  catch (e) { return {}; }
}
async function openAdbGuide() {
  const d = await fetchAdbState();
  const tg = document.getElementById('adbEnableToggle');
  if (tg) tg.checked = !!d.enabled;
  const st = document.getElementById('adbGuideStatus');
  if (st) {
    if (d.phone) st.innerHTML = '✅ <b>گوشی متصل است</b> — چرخش IP فعال و آماده؛ هر مسدودی (429) با گرفتن IP تازه از اپراتور رد میشود و اسکن ادامه مییابد.';
    else if (d.adb_found) st.innerHTML = '⚠️ <b>adb نصب است ولی گوشی وصل نیست.</b> مراحل «راه‌اندازی گوشی» را انجام بده، سپس دوباره روی ❓ بزن تا وضعیت تایید شود.';
    else st.innerHTML = '📵 <b>adb پیدا نشد.</b> فایل platform-tools را دانلود و در <code>C:\adb\platform-tools</code> استخراج کن، سپس دوباره راهنما را باز کن.';
  }
  document.getElementById('adbModal').classList.add('active');
}
function closeAdbGuide() {
  document.getElementById('adbModal').classList.remove('active');
  fetch('/api/adb/set', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ seen: true }) }).catch(() => {});
}
async function setAdbToggle() {
  const on = document.getElementById('adbEnableToggle').checked;
  try { await fetch('/api/adb/set', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: on, seen: true }) }); } catch (e) {}
  const st = document.getElementById('adbGuideStatus');
  if (st && on) st.innerHTML = '✅ <b>چرخش IP روشن شد.</b> گوشی را وصل و مراحل را دنبال کن؛ سپس این راهنما را دوباره باز کن تا تایید شود.';
  if (st && !on) st.innerHTML = '🔴 <b>چرخش IP خاموش شد.</b> اسکن به حالت صبر نرمال برمیگردد — در صورت بن طولانی، گزینه‌های پوکسی باقی میمانند.';
}
(function initAdbGuide() {
  fetchAdbState().then(d => { if (d && !d.seen) setTimeout(openAdbGuide, 900); });
})();

/* ---------- جزئیات بروزرسانی تابلو بازار ----------
   v9.7.8 — رفع حلقهٔ استارت: این پولر قبلاً setInterval دو‌ثانیه‌ای بود و تا
   پایان سینک، نمونه‌هایش روی سرور شلوغ انباشته می‌شد (هر sync-state اسکن
   پروسهٔ سرور می‌زند → اشباع اتصال‌های مرورگر و قفل‌شدن واکشی تابلو). حالا:
   گارد in-flight + زنجیرهٔ setTimeout (نمونهٔ بعدی فقط بعد بازگشت قبلی) +
   backoff ۶ ثانیه در خطا + ددلاین ۲۰ دقیقه (وضعیت فریزشدهٔ سرور پولر
   ابدی نمی‌سازد). */
let _msdTimer = null;
let _msdBusy = false;
let _msdDeadline = 0;
const _MSD_MAX_MS = 20 * 60 * 1000;

function _msdStop() {
    if (_msdTimer) { clearTimeout(_msdTimer); _msdTimer = null; }
    _msdDeadline = 0;
}
function _msdSchedule(delay) {
    if (_msdTimer) clearTimeout(_msdTimer);
    _msdTimer = setTimeout(pollMarketSyncState, delay);
}
function _msdEnsurePoll() {
    // زنجیره، نه interval: اگر نمونه‌ای زمان‌بندی‌شده یا جاری است، دومی شروع نشود
    if (_msdTimer || _msdBusy) return;
    pollMarketSyncState();
}

async function pollMarketSyncState() {
  if (_msdBusy) return {};             // نمونهٔ پیشین برنگشته — درخواست روی هم انباشته نمی‌شود
  _msdBusy = true;
  try {
    const r = await fetch('/api/market/sync-state');
    const d = await r.json();
    const box = document.getElementById('marketSyncDetails');
    if (!box || !d) { _msdStop(); return d; }
    const last = d.last || {};
    if (d.running && !_msdDeadline) _msdDeadline = Date.now() + _MSD_MAX_MS;
    if (d.running && Date.now() < _msdDeadline) {
      box.style.display = 'block';
      document.getElementById('msdTitle').innerText = '📊 در حال بروزرسانی زنده تابلو...';
      const p = Math.max(2, Math.min(100, Number(last.percent) || 0));
      document.getElementById('msdBar').style.width = p + '%';
      const phaseMap = { 'fetch_sectors': 'دریافت گروههای صنعتی', 'fetch_marketwatch': 'دریافت تابلوخوانی کل بازار', 'fetch_clienttype': 'دریافت حقیقی/حقوقی', 'parse': 'پردازش نمادها', 'save': 'ذخیره در پایگاه', 'start': 'راهاندازی' };
      document.getElementById('msdMeta').innerText = (last.current || 0) + ' / ' + (last.total || 0) + ' · ' + Math.round(last.elapsed || 0) + 's';
      document.getElementById('msdDetail').innerHTML = 'مرحله: <b>' + (phaseMap[last.phase] || last.phase || '—') + '</b>' + (last.detail ? ' — ' + last.detail : '');
      _msdSchedule(2000);              // نمونهٔ بعدی ۲ ثانیه بعد از پایان همین نمونه
    } else if (d.running) {
      // ددلاین ۲۰ دقیقه تمام — احتمالاً وضعیت سمت سرور فریز شده؛ چرخه عمداً بسته می‌شود
      _msdStop();
      box.style.display = 'block';
      document.getElementById('msdTitle').innerHTML = '⏳ <b>بروزرسانی تابلو بیش از ۲۰ دقیقه طول کشیده</b>';
      document.getElementById('msdBar').style.width = '30%';
      document.getElementById('msdBar').style.background = 'var(--accent-yellow, #eab308)';
      document.getElementById('msdMeta').innerText = 'چندخوانی وضعیت خودکار متوقف شد (ضد حلقهٔ باز)';
      document.getElementById('msdDetail').innerText = 'اگر پیشرفتی دیده نمی‌شود، لاگ سرور را ببینید یا «🔄 بروزرسانی زنده تابلو» را دوباره بزنید';
    } else {
      _msdStop();
      const t = last.ts ? last.ts.slice(11, 16) : (last.ts ? last.ts.slice(0, 16) : '—');
      const isErr = (last.phase === 'error');
      document.getElementById('msdTitle').innerHTML = isErr ? '⚠️ <b>خطا در بروزرسانی تابلو</b>' : '✅ <b>بروزرسانی تابلو (آخرین)</b>';
      document.getElementById('msdBar').style.width = isErr ? '30%' : '100%';
      document.getElementById('msdBar').style.background = isErr ? 'var(--accent-red)' : 'var(--accent-green)';
      document.getElementById('msdMeta').innerText = (last.total || 0) + ' نماد · ' + t;
      document.getElementById('msdDetail').innerText = (last.detail || '—') + (last.elapsed ? ' · مدت: ' + Math.round(last.elapsed) + ' ثانیه' : '');
    }
    return d;
  } catch (e) {
    // شلوغی/قطع شبکه: backoff ۶ ثانیه تا ددلاین؛ وگرنه چرخه بسته می‌شود (ضد حلقهٔ خطا)
    if (_msdDeadline && Date.now() < _msdDeadline) _msdSchedule(6000);
    else _msdStop();
    return {};
  } finally { _msdBusy = false; }
}
function showMarketSyncDetails() { _msdEnsurePoll(); }
function closeMarketSyncDetails() {
  const b = document.getElementById('marketSyncDetails');
  if (b) b.style.display = 'none';
  _msdStop();
}
window.addEventListener('load', () => { pollMarketSyncState(); });

/* ============================================================
   تنظیمات غربالگری کدال: حذف ۴ رقم از راست + فیلتر ستارهها
   + فیلتر شاخصهای استاد + نمایش ستونها
   ============================================================ */
/* v9.1: متغیر starFilter حذف شد */


function applyCodalFilters() {
    // ذخیرهٔ toggles
    const f = { cols: {} };
    ['fltGrowth','fltProfit','fltMargin','fltMcap','fltSector'].forEach(id => {
        const el = document.getElementById(id);
        if (el) f[id] = el.checked;
    });
    document.querySelectorAll('.col-cb').forEach(cb => { f.cols[cb.dataset.col] = cb.checked; });
    try { stSet('codalFilters', JSON.stringify(f)); } catch (e) {}

    var rows = screenerData || [];

    // فیلتر شاخصهای استاد (پنج محور)
    if (f.fltGrowth) rows = rows.filter(r => r.i1_pass);
    if (f.fltProfit) rows = rows.filter(r => r.i2_pass);
    if (f.fltMargin) rows = rows.filter(r => r.i3_pass);
    if (f.fltMcap) rows = rows.filter(r => r.i4_pass);
    if (f.fltSector) rows = rows.filter(r => r.pricing_mode === 'free');
    filteredScreenerData = rows;
    renderScreenerTable(filteredScreenerData);

    // نمایش/مخفی ستونها
    document.querySelectorAll('#screenerTable th').forEach(th => {
        const oc = th.getAttribute('onclick') || '';
        const m = oc.match(/handleSortScreener\('([a-z_]+)'\)/);
        if (!m) return;
        const col = m[1];
        const show = f.cols[col] !== false;
        th.style.display = show ? '' : 'none';
    });
    document.querySelectorAll('#screenerTableBody tr').forEach(tr => {
        const cells = tr.querySelectorAll('td');
        // cells همترتیب با th ها (بدون عملیات)
        const names = ['symbol', 'name', 'sector_name', 'rev_growth', 'eps_last', 'gross_margin',
                       'sales_to_mcap', 'profit_potential_pct', 'pricing_mode', 'mcap', 'score'];
        names.forEach((col, i) => {
            if (cells[i]) cells[i].style.display = (f.cols[col] !== false) ? '' : 'none';
        });
    });
}

/* ===== v7.3.15 — ریسایز ستون جدول (مثل اکسل) + کارت‌های تاشوی تنظیمات ===== */
function initColResize(tableId) {
    const table = document.getElementById(tableId);
    if (!table) return;
    const cg = table.querySelector('colgroup');
    if (!cg) return;
    const cols = cg.querySelectorAll('col');   // snapshot اولیه (برای grip ساختن)
    const ths = table.querySelectorAll('thead th');
    const liveCols = function () { return cg.querySelectorAll('col'); };  // rebuildColgroup کول‌ها را عوض میکند
    // بازیابی عرض‌های ذخیره‌شده
    function applySaved() { rebuildColgroup(tableId); }
    applySaved();
    ths.forEach(function (th, idx) {
        const oldGrip = th.querySelector('.col-grip');
        if (oldGrip) oldGrip.remove();          // idempotent: هر بار grip تازه با listener
        const grip = document.createElement('span');
        grip.className = 'col-grip';
        grip.title = 'برای تغییر عرض بکشید';
        th.appendChild(grip);
        grip.addEventListener('mousedown', function (e) {
            e.preventDefault(); e.stopPropagation();
            const visThs = Array.from(ths).filter(function (t) { return getComputedStyle(t).display !== 'none'; });
            const visIdx = visThs.indexOf(th);
            const liveC = liveCols();
            const col = liveC[visIdx];
            if (!col) return;
            // حالت اکسل: حین درگ هیچ layout ای انجام نمیشود — فقط خط راهنما (GPU)
            // عرض‌ها و جدول یک‌بار در mouseup اعمال/قفل میشوند
            const w0 = Math.round(th.getBoundingClientRect().width);
            const widthsArr = [];
            const startX = e.clientX;
            let pending = w0;
            // خط راهنمای عمودی
            let guide = document.getElementById('colGuide');
            if (!guide) {
                guide = document.createElement('div');
                guide.id = 'colGuide';
                document.body.appendChild(guide);
            }
            const gr = th.getBoundingClientRect();
            guide.style.cssText = 'position:fixed;top:' + Math.round(gr.top) + 'px;height:' + Math.round(gr.height + 400) + 'px;width:2px;background:#2d8cf0;z-index:99999;pointer-events:none;left:' + Math.round(gr.left) + 'px;';
            const move = function (ev) {
                pending = Math.max(40, Math.min(500, w0 + (startX - ev.clientX)));  // RTL: چپ = پهن‌تر
                guide.style.left = Math.round(gr.left - (pending - w0)) + 'px';     // RTL: لبهٔ ستون به چپ جابجا میشود
            };
            const up = function () {
                document.removeEventListener('mousemove', move);
                document.removeEventListener('mouseup', up);
                guide.remove();
                document.body.style.cursor = '';
                window.__colDragTs = Date.now();
                // ذخیره با کلیدِ این th و بازسازی colgroup (تطبیق با ترتیب/مخفی‌سازی)
                try {
                    const st = JSON.parse(stGet('colw_' + tableId, '{}') || '{}');
                    st[_colKeyOf(th)] = pending;
                    stSet('colw_' + tableId, JSON.stringify(st));
                } catch (err) {}
                rebuildColgroup(tableId);
            };
            document.body.style.cursor = 'col-resize';
            document.addEventListener('mousemove', move);
            document.addEventListener('mouseup', up);
        });
        grip.addEventListener('dblclick', function (e) {
            // دابل‌کلیک روی دستگیره = ریست همان ستون
            e.stopPropagation();
            try { const st = JSON.parse(stGet('colw_' + tableId, '{}')); delete st[_colKeyOf(th)]; stSet('colw_' + tableId, JSON.stringify(st)); } catch (err) {}
            rebuildColgroup(tableId);
        });
        // کنترل عددی: دابل‌کلیک روی خودِ سرستون = ورودی px (مثل اکسل — بدون اسکرول‌بار)
        th.addEventListener('dblclick', function (e) {
            if (e.target.closest('.col-grip')) return;
            if (Date.now() - (window.__colDragTs || 0) < 500) return;  // دو درگ پشت‌سرهم ≠ دابل‌کلیک
            e.stopPropagation();
            const cur = Math.round(th.getBoundingClientRect().width);
            const inp = document.createElement('input');
            inp.type = 'number'; inp.min = 40; inp.max = 500; inp.step = 10; inp.value = cur;
            inp.className = 'th-w-input';
            const oldText = th.innerHTML;
            th.innerHTML = '';
            th.appendChild(inp);
            inp.focus(); inp.select();
            const commit = function () {
                let w = parseInt(inp.value, 10);
                if (isNaN(w) || w < 40) w = cur;
                w = Math.min(500, w);
                th.innerHTML = oldText;
                initColResize(tableId);   // grip با listener بازسازی شود (idempotent)
                // تبدیل همه به px + اعمال
                try {
                    const st = JSON.parse(stGet('colw_' + tableId, '{}') || '{}');
                    st[_colKeyOf(th)] = w;
                    stSet('colw_' + tableId, JSON.stringify(st));
                } catch (err) {}
                rebuildColgroup(tableId);
                window.__colDragTs = Date.now();   // جلوی sort تصادفی
            };
            inp.addEventListener('blur', commit);
            inp.addEventListener('keydown', function (ev) {
                if (ev.key === 'Enter') { ev.preventDefault(); inp.blur(); }
                if (ev.key === 'Escape') { inp.value = cur; inp.blur(); }
                ev.stopPropagation();
            });
        });
    });
}
function initSidebarCards() {
    // هر کارت تنظیمات (فرزند مستقیم پنل‌ها) را تاشو کن: کلیک روی سطر اول = باز/بسته
    document.querySelectorAll('.sidebar-settings > div').forEach(function (card) {
        // بخش‌هایی که منطق باز/بستهٔ خودشان را دارند (cfSection/fltSection) دوتایی‌توگل نشوند
        if (card.querySelector('[id$="SectionBody"]')) return;
        card.classList.add('sb-card');
        if (card.dataset.folded) return;
        card.dataset.folded = '1';
        const head = card.firstElementChild;
        if (!head) return;
        head.classList.add('sb-card-head');
        const arr = document.createElement('span');
        arr.className = 'sb-fold-arr';
        arr.textContent = '▾';
        head.appendChild(arr);
        head.addEventListener('click', function (e) {
            if (e.target.closest('input,button,a,select')) return;   // کنترل‌های داخلی دست‌نخورده
            card.classList.toggle('sb-folded');
            arr.textContent = card.classList.contains('sb-folded') ? '◂' : '▾';
        });
    });
}

function stepFont(view, delta) {
    let v = 100;
    try { v = parseInt(stGet('fontScale_' + view, '100'), 10); } catch (e) {}
    if (isNaN(v)) v = 100;
    v = Math.max(60, Math.min(130, v + delta));
    try { stSet('fontScale_' + view, v); } catch (e) {}
    applyFontScale(v);
    const el = document.getElementById('fontScaleNum_' + view);
    if (el) el.value = v + '%';
}
function setFontNum(view, txt) {
    let v = parseInt(String(txt).replace(/[^\d]/g, ''), 10);
    if (isNaN(v)) return;
    v = Math.max(60, Math.min(130, v));
    try { stSet('fontScale_' + view, v); } catch (e) {}
    applyFontScale(v);
    const el = document.getElementById('fontScaleNum_' + view);
    if (el) el.value = v + '%';
}

/* ---------- پنل پیش‌شرط‌های ۵ شاخص (تنظیمات کدال) ---------- */
function toggleFtsPre() {
    const body = document.getElementById('ftsPreBody');
    const tog = document.getElementById('ftsPreToggle');
    if (!body) return;
    // v9.1: وضعیت باز/بسته با data-open خوانده می‌شود، نه displayِ inline
    // (نسخهٔ قبلی با markup تازه‌سازی‌شده گره می‌خورد و پنل بسته می‌ماند)
    const open = body.dataset.open === '1';
    body.dataset.open = open ? '0' : '1';
    body.style.display = open ? 'none' : 'flex';
    if (tog) tog.textContent = open ? '▸' : '▾';
    if (!open && !body.dataset.loaded) loadFtsConfig();
}
const FTS_KEYS = ['growth_min','inflation_min','eps_years','margin_min','margin_optimal',
                  'sales_to_mcap_min','profit_potential_min','mcap_min_hmt','watchlist_max',
                  'suspended_max_stale_sessions','min_trade_val'];
/* v9.7: چک‌باکس‌ها گروه جدا دارند — parseFloat(el.value) روی آن‌ها همیشه NaN می‌داد
   و تیک «ماده ۱۴۱» هرگز ذخیره نمی‌شد. */
const FTS_BOOL_KEYS = ['filter_m141'];
const FTS_LIST_KEYS = ['mandatory_sectors','free_sectors'];
const FTS_STR_KEYS = ['industry_mode'];
async function loadFtsConfig(force) {
    const msg = document.getElementById('ftsPreMsg');
    try {
        const r = await fetch('/api/fts/config', { headers: { 'Accept': 'application/json' } });
        const j = await r.json();
        if (!j || j.status !== 'success' || !j.config) {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = '✕ آستانه‌ها از سرور گرفته نشد'; }
            return;
        }
        const c = j.config;
        FTS_KEYS.forEach(k => {
            const el = document.getElementById('fts_' + k);
            if (el) el.value = c[k];
        });
        FTS_STR_KEYS.forEach(k => {
            const el = document.getElementById('fts_' + k);
            if (el) el.value = c[k];
        });
        FTS_BOOL_KEYS.forEach(k => {
            const el = document.getElementById('fts_' + k);
            if (el) el.checked = !!c[k];
        });
        FTS_LIST_KEYS.forEach(k => {
            const el = document.getElementById('fts_' + k);
            if (el) el.value = (c[k] || []).join('، ');
        });
        const body = document.getElementById('ftsPreBody');
        if (body) body.dataset.loaded = '1';
        if (msg && force) { msg.style.color = '#22c55e'; msg.textContent = '✓ مقادیر ذخیره‌شدهٔ سرور بازیابی شد'; }
    } catch (e) {
        console.warn('loadFtsConfig', e);
        if (msg) { msg.style.color = '#ef4444'; msg.textContent = '✕ خطای ارتباط با سرور'; }
    }
}
async function saveFtsConfig() {
    const payload = {};
    FTS_KEYS.forEach(k => {
        const el = document.getElementById('fts_' + k);
        if (el && el.value !== '') payload[k] = parseFloat(el.value);
    });
    FTS_BOOL_KEYS.forEach(k => {
        const el = document.getElementById('fts_' + k);
        // همیشه ارسال می‌شود؛ نبودِ کلید در payload یعنی بازگشت به پیش‌فرض
        if (el) payload[k] = !!el.checked;
    });
    FTS_STR_KEYS.forEach(k => {
        const el = document.getElementById('fts_' + k);
        if (el && el.value) payload[k] = el.value;
    });
    FTS_LIST_KEYS.forEach(k => {
        const el = document.getElementById('fts_' + k);
        if (el) payload[k] = el.value;
    });
    try {
        const r = await fetch('/api/fts/config', {method: 'POST',
            headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
        const j = await r.json();
        const msg = document.getElementById('ftsPreMsg');
        if (j.status === 'success') {
            if (msg) { msg.style.color = '#22c55e'; msg.textContent = '✓ ذخیره شد — جدول بنیادی با آستانه‌های جدید محاسبه میشود'; }
            rvToastSv('📐 پیش‌شرط‌ها ذخیره شد');
            try { initScreener(true); } catch (e) {}   // جدول بنیادی با آستانه‌های تازه
        } else {
            if (msg) { msg.style.color = '#ef4444'; msg.textContent = '✕ ' + (j.message || 'خطا'); }
        }
    } catch (e) {
        const msg = document.getElementById('ftsPreMsg');
        if (msg) { msg.style.color = '#ef4444'; msg.textContent = '✕ خطای ارتباط'; }
    }
}

/* ── کارتابل سبد (Portfolio Workstation FTS) به static/portfolio_ui.js ──
   منتقل شد: کل بلوک PF_KEY / pfState / pf* آنجا تعریف میشود تا مالکیت
   دامنهٔ سبد یکتا باشد و ویرایشهای موازی روی app.js تصادم نکنند. */

/* ============================================================
   v9.7.8 — بوت‌استرپ شروع برنامه (رفع باگ «دریافت داده‌های بازار گیر می‌کند»)
   نمایش پیش‌فرض #marketView (تابلو) است، ولی هیچ فراخوانی آغازین برای
   initMarket/بروزرسانی خودکار باقی نمانده بود → جدول روی پیام «در حال دریافت
   داده‌های بازار...» فریز می‌شد (ظاهرٍ حلقهٔ دریافت بی‌پایان).
   همهٔ فراخوان‌ها idempotent‌اند و initMarket خودش single-flight + سقف ۴۰s +
   تلاش مجدد کران‌دار است؛ پس تکرار این listener بی‌ضرر است.
   ============================================================ */
window.addEventListener('load', function () {
    try { initAutoRefreshState(); } catch (e) {}
    try { setupAutoRefresh(); } catch (e) {}
    try { applyHiddenBuiltinFilters(); } catch (e) {}
    try { renderCustomFilters(); } catch (e) {}
    try { initMarket(); } catch (e) {}   // واکشی اولیهٔ تابلو — قلب بوت
});

