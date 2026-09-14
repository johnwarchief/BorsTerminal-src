/* ══════════════════════════════════════════════════════════════════════════
   Portfolio Workstation FTS — کارتابل سبد (#portfolioView)
   ──────────────────────────────────────────────────────────────────────────
   v9.8.1 فاز ۰ (interface freeze): کل بلوک سبد از static/app.js جدا شد.

   مالکیت: سقف درگیری، موازنهٔ سبد، نردبان حد ضرر پویا، ماتریس تاییدیههای
   سهگانه [بنیادی][تابلو][تکنیکال] و هر چیز مرتبط با pf*.
   ذخیرهسازی: localStorage (کلید bors_portfolio_v1) + همگامسازی اختیاری با
   /api/watchlist.

   رابط تثبیتشده (مصرفکننده در app.js):
     · initPortfolio()   ← switchView('portfolio')

   وابستگی به بیرون (فقط خواندن؛ اینجا تعریف نمیشوند):
     · rvToastSv()، fetch به /api/watchlist و /api/market ← app.js
   ══════════════════════════════════════════════════════════════════════════ */

/* ════════════════════════════════════════════════════════════════════
   💼 Portfolio Workstation FTS (v9.7.6)
   کارتابل مدیریت سرمایه: سقف درگیری، موازنه سبد، نردبان حد ضرر پویا
   و ماتریس تاییدیه‌های سه‌گانه [بنیادی][تابلو][تکنیکال].
   ذخیره‌سازی: localStorage (کلید bors_portfolio_v1) + همگام‌سازی اختیاری
   با /api/watchlist (همان endpoint موجود).
   ════════════════════════════════════════════════════════════════════ */

const PF_KEY = 'bors_portfolio_v1';
const PF_MODE_KEY = 'bors_pf_mode_v1';
let pfState = { positions: [], cash: 0, total_capital: 0 };
let pfMode = 'swing';   // 'swing' | 'trend'
let pfWatchlistCache = [];   // برای همگامی ★ از تابلو

function pfLoad() {
    try { pfState = JSON.parse(localStorage.getItem(PF_KEY) || '{}'); } catch (e) {}
    if (!pfState || typeof pfState !== 'object') pfState = { positions: [], cash: 0, total_capital: 0 };
    if (!Array.isArray(pfState.positions)) pfState.positions = [];
    // پاکسازی رکوردهای معیوب نسخه قبل: symbol آبجکتی → رشته (رفع [object Object])
    let pfFixUp = false;
    const pfClean = [];
    pfState.positions.forEach(p => {
        if (!p || typeof p !== 'object') { pfFixUp = true; return; }
        let sym = p.symbol;
        if (sym && typeof sym === 'object') { sym = sym.symbol || sym.name || ''; pfFixUp = true; }
        sym = String(sym || '').trim();
        if (!sym || pfClean.find(x => x.symbol === sym)) { pfFixUp = true; return; }
        p.symbol = sym;
        pfClean.push(p);
    });
    pfState.positions = pfClean;
    if (pfFixUp) pfSave();
    try { pfMode = localStorage.getItem(PF_MODE_KEY) || 'swing'; } catch (e) { pfMode = 'swing'; }
}
function pfSave() {
    try { localStorage.setItem(PF_KEY, JSON.stringify(pfState)); } catch (e) {}
}
function pfSetMode(mode) {
    pfMode = mode;
    try { localStorage.setItem(PF_MODE_KEY, mode); } catch (e) {}
    const sw = document.getElementById('pfModeSwing');
    const tr = document.getElementById('pfModeTrend');
    if (sw) sw.classList.toggle('active', mode === 'swing');
    if (tr) tr.classList.toggle('active', mode === 'trend');
    pfRender();
}
function pfQuickAdd() {
    const inp = document.getElementById('pfQuickAdd');
    if (!inp) return;
    const sym = (inp.value || '').trim();
    if (!sym) return;
    if (pfState.positions.find(p => p.symbol === sym)) {
        rvToastSv('⚠️ ' + sym + ' از قبل در پورتفوی هست');
        inp.value = '';
        return;
    }
    pfState.positions.push({
        symbol: sym,
        qty: 0,
        avg_price: 0,
        // پله‌های ورود: [{price, qty, date}]
        ladders: [],
        target: 0,
        note: '',
        added_at: Date.now(),
    });
    pfSave();
    inp.value = '';
    pfRender();
    rvToastSv('➕ ' + sym + ' به پورتفوی اضافه شد');
}
function pfRemovePos(symbol) {
    if (!confirm('حذف «' + symbol + '» از پورتفوی؟')) return;
    pfState.positions = pfState.positions.filter(p => p.symbol !== symbol);
    pfSave();
    pfRender();
    rvToastSv('🗑 ' + symbol + ' از پورتفوی حذف شد');
}
function pfExportCSV() {
    if (!pfState.positions.length) { rvToastSv('پورتفوی خالی است'); return; }
    const rows = [['symbol','qty','avg_price','current','pnl_pct','sl','tp','rr','mode','note']];
    pfState.positions.forEach(p => {
        const live = pfGetLivePrice(p.symbol);
        const sl = pfComputeSL(p, pfMode);
        const tp = p.target || 0;
        const pnl = live && p.avg_price > 0 ? ((live - p.avg_price) / p.avg_price * 100) : 0;
        const rr = (tp > 0 && sl > 0 && p.avg_price > 0) ? ((tp - p.avg_price) / Math.max(0.0001, p.avg_price - sl)).toFixed(2) : '';
        rows.push([p.symbol, p.qty||0, p.avg_price||0, live||'', pnl.toFixed(2), sl||'', tp||'', rr, pfMode, (p.note||'').replace(/[\n,]/g,' ')]);
    });
    const csv = '\uFEFF' + rows.map(r => r.join(',')).join('\n');  // BOM برای اکسل فارسی
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'portfolio_fts.csv';
    document.body.appendChild(a); a.click(); document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/* دریافت قیمت لحظه‌ای از cache بازار (در همان session از /api/market لود شده).
   اگر پیدا نشد، 0 برمی‌گرداند (نه NaN — تا R/R بی‌معنا نشود). */
function pfGetLivePrice(symbol) {
    try {
        if (Array.isArray(marketData) && marketData.length) {
            const r = marketData.find(x => x.symbol === symbol)
                   || marketData.find(x => x.symbol && x.symbol.indexOf(symbol) === 0);
            if (r) {
                const v = Number(r.p_last || r.p_closing || r.last_price || 0);
                if (v > 0) return v;
            }
        }
        // تلاش برای استفاده از marketData موجود در همان صفحه (tape)
        if (Array.isArray(window.marketData) && window.marketData.length) {
            const r = window.marketData.find(x => x.symbol === symbol);
            if (r) {
                const v = Number(r.p_last || r.p_closing || r.last_price || 0);
                if (v > 0) return v;
            }
        }
    } catch (e) {}
    return 0;
}

/* نردبان حد ضرر پویا:
   - swing: ۵٪ زیر آخرین کف (اگر avg_price موجود)؛ در نبود داده، ۵٪ زیر avg
   - trend: ۷٪ زیر avg_price (روندگیر تحریم بیشتر دارد)؛ اگر avg نبود، همان swing
   بازگشت: عدد SL (تومان) — 0 یعنی نامعتبر. */
function pfComputeSL(p, mode) {
    const avg = Number(p && p.avg_price) || 0;
    if (avg <= 0) return 0;
    if (mode === 'trend') {
        return Math.round(avg * 0.93);
    }
    return Math.round(avg * 0.95);
}

/* ماتریس تاییدیه‌های سه‌گانه FTS:
   - بنیادی: P/E (از فیلتر کدال)، حاشیه سود
   - تابلو: قدرت خریدار، سرانه، ورود پول حقیقی
   - تکنیکال: MA14/RSI/MACD — در این نسخه با fallback ساده
   خروجی: { fund: 'pass'|'warn'|'fail'|'nodata', tape: ..., tech: ..., reasons: {fund, tape, tech} } */
function pfComputeFTS(p) {
    const out = { fund: 'nodata', tape: 'nodata', tech: 'nodata', reasons: { fund: '—', tape: '—', tech: '—' } };
    try {
        const r = (Array.isArray(marketData) && marketData.length) ? marketData.find(x => x.symbol === p.symbol) : null;
        if (r) {
            // تابلو: قدرت خریدار حقیقی (فیلد واقعی API: buyer_power)
            const pp = Number(r.buyer_power || r.individual_buy_power || (Number(r.buy_n_vol || 0) > 0 ? Number(r.buy_n_vol || 0) / Number(r.sell_n_vol || 1) : 0)) || 0;
            if (pp > 1.0) { out.tape = 'pass'; out.reasons.tape = 'قدرت خریدار حقیقی: ' + pp.toFixed(2) + ' (مثبت)'; }
            else if (pp > 0) { out.tape = 'warn'; out.reasons.tape = 'قدرت خریدار: ' + pp.toFixed(2) + ' (ضعیف)'; }
            else if (pp === 0) { out.tape = 'nodata'; out.reasons.tape = 'دادهٔ تابلو موجود نیست'; }
            else { out.tape = 'fail'; out.reasons.tape = 'قدرت خریدار منفی: ' + pp.toFixed(2); }

            // تکنیکال: ساده — بررسی روند کوتاه‌مدت با تغییر ٪
            const ch = Number(r.percent_change) || 0;
            if (ch >= 2) { out.tech = 'pass'; out.reasons.tech = 'تغییر ٪ روز: +' + ch.toFixed(2) + '٪ — روند مثبت'; }
            else if (ch >= 0) { out.tech = 'warn'; out.reasons.tech = 'تغییر ٪ روز: ' + ch.toFixed(2) + '٪ — خنثی'; }
            else { out.tech = 'fail'; out.reasons.tech = 'تغییر ٪ روز: ' + ch.toFixed(2) + '٪ — منفی'; }
        }
        // بنیادی: اگر در screener اطلاعاتی از این نماد هست
        if (Array.isArray(window.filteredScreenerData) && window.filteredScreenerData.length) {
            const fs = window.filteredScreenerData.find(x => x.symbol === p.symbol);
            if (fs) {
                const pe = Number(fs.pe) || 0;
                if (pe > 0 && pe < 10) { out.fund = 'pass'; out.reasons.fund = 'P/E = ' + pe.toFixed(2) + ' — ارزان'; }
                else if (pe > 0 && pe < 20) { out.fund = 'warn'; out.reasons.fund = 'P/E = ' + pe.toFixed(2) + ' — متوسط'; }
                else if (pe > 0) { out.fund = 'fail'; out.reasons.fund = 'P/E = ' + pe.toFixed(2) + ' — گران'; }
            }
        }
    } catch (e) {}
    return out;
}

/* همگام‌سازی پورتفوی با واچ‌لیست (★ از تابلو → پورتفوی پیشنهادی).
   هر ★ در واچ‌لیست اگر در پورتفوی نباشد، به‌صورت خام (qty=0) اضافه می‌شود. */
async function pfSyncFromWatchlist() {
    try {
        const r = await fetch('/api/watchlist');
        if (!r.ok) return;
        const j = await r.json();
        const arr = j.data || j.rows || j.watchlist || j.items || [];
        if (!Array.isArray(arr)) return;
        pfWatchlistCache = arr;
        let added = 0;
        arr.forEach(s => {
            // API ممکن است رشته یا آبجکت {symbol,name,...} بدهد → نرمال‌سازی
            let sym = (typeof s === 'string') ? s : (s && (s.symbol || s.name)) || '';
            const nm = (s && typeof s === 'object' && s.name) ? String(s.name).trim() : '';
            sym = String(sym || '').trim();
            if (!sym) return;
            const ex = pfState.positions.find(p => p.symbol === sym);
            if (ex) { if (nm && !ex.name) { ex.name = nm; pfDirty(); } return; }
            pfState.positions.push({ symbol: sym, name: nm, qty: 0, avg_price: 0, ladders: [], target: 0, note: 'از واچ‌لیست', added_at: Date.now() });
            added++;
        });
        if (added) { pfSave(); pfRender(); rvToastSv('⭐ ' + added + ' نماد از واچ‌لیست همگام شد'); }
    } catch (e) { console.warn('pfSyncFromWatchlist', e); }
}
function pfDirty() { try { localStorage.setItem(PF_KEY, JSON.stringify(pfState)); } catch (e) {} }

let pfLastSync = 0;
async function initPortfolio() {
    pfLoad();
    // سینک با واچ‌لیست حداکثر هر ۶۰ ثانیه (ضد اسپم شبکه با هر بار ورود به تب)
    if (Date.now() - pfLastSync > 60000) { pfLastSync = Date.now(); pfSyncFromWatchlist(); }
    // بوت‌استرپ قیمت زنده: اگر جدول بازار لود نشده، یک‌بار بی‌صدا واکشی و ویجت‌ها را تازه کن
    if (!Array.isArray(marketData) || marketData.length === 0) {
        Promise.resolve(initMarket()).then(() => { pfRender(); }).catch(() => {});
    }
    pfRender();

    // اعمال حالت روی دکمه‌ها بدون رندر دوباره
    const sw = document.getElementById('pfModeSwing');
    const tr = document.getElementById('pfModeTrend');
    if (sw) sw.classList.toggle('active', pfMode === 'swing');
    if (tr) tr.classList.toggle('active', pfMode === 'trend');
}

/* ثبت سرمایه کل — مبنای محاسبه سقف درگیری FTS */
function pfUpdateCapital(v) {
    const n = parseFloat(String(v).replace(/[^\d.]/g, ''));
    pfState.total_capital = (isNaN(n) || n < 0) ? 0 : n;
    pfSave();
    pfRender();
}

/* محاسبه و رندر سقف درگیری، موازنه سبد، هشدارها و جدول پوزیشن‌ها */
function pfRender() {
    const tbody = document.getElementById('pfTbody');
    if (!tbody) return;

    // ۱. سرمایهٔ فعال: پوزیشن واچ‌لیستی با qty=0 یک واحد کاغذی حساب می‌شود ← ویجت بر مبنای قیمت زنده
    let totalMV = 0;
    pfState.positions.forEach(p => {
        const price = pfGetLivePrice(p.symbol) || Number(p.avg_price) || 0;
        const q = Number(p.qty) || 0;
        totalMV += (q > 0 ? q : 1) * price;
    });
    const totalCap = Number(pfState.total_capital) || 0;
    const hasCap = totalCap > 0;
    const activePct = hasCap ? (totalMV / totalCap * 100) : 0;
    const capInp = document.getElementById('pfTotalCap');
    if (capInp && document.activeElement !== capInp) capInp.value = totalCap ? String(totalCap) : '';
    const pctEl = document.getElementById('pfActivePct');
    if (pctEl) {
        pctEl.textContent = (hasCap && pfState.positions.length) ? activePct.toFixed(1) + '٪' : '—';
        pctEl.style.color = !hasCap ? 'var(--text-muted)' : (activePct > 85 ? '#f43f5e' : (activePct > 70 ? '#f59e0b' : '#10b981'));
    }
    const barEl = document.getElementById('pfActiveBar');
    if (barEl) {
        barEl.style.width = (hasCap ? Math.min(100, activePct) : 0) + '%';
        barEl.style.background = activePct > 85 ? 'linear-gradient(90deg,#f43f5e,#fb7185)' : (activePct > 70 ? 'linear-gradient(90deg,#f59e0b,#fbbf24)' : 'linear-gradient(90deg,#10b981,#22c55e)');
    }
    const capAlert = document.getElementById('pfCapAlert');
    if (capAlert) {
        if (!pfState.positions.length) capAlert.textContent = '— هنوز پوزیشنی ثبت نشده —';
        else if (!hasCap) capAlert.innerHTML = '<span style="color:var(--text-secondary);">ℹ برای محاسبهٔ سقف درگیری، سرمایهٔ کل را وارد کنید</span>';
        else if (activePct > 85) capAlert.innerHTML = '<span style="color:#f43f5e;">⚠ بحرانی — درگیری بالای ۸۵٪؛ در شرایط بحرانی سقف باید ۱۰–۲۰٪ باشد</span>';
        else if (activePct > 70) capAlert.innerHTML = '<span style="color:#f59e0b;">⚠ احتیاط — بالای ۷۰٪؛ تا تثبیت بازار، پوزیشن جدید باز نکنید</span>';
        else capAlert.innerHTML = '<span style="color:#10b981;">✅ در محدودهٔ امن (سقف عادی ۷۰٪)</span>';
    }

    // ۲. موازنه سبد — تفکیک هر محور از ۱۰۰٪ (دلاری↔ریالی و بزرگ↔چابک مستقل نرمال می‌شوند)
    let dollarMV = 0, rialMV = 0, largeMV = 0, smallMV = 0;
    const dollarSectors = ['فلزات اساسی','پتروشیمی','پالایشیها','سیمان','کانی‌های فلزی','فلزی'];
    const rialSectors = ['غذایی','دارویی','رایانه','خودرو','بانک','سرمایه‌گذاری'];
    pfState.positions.forEach(p => {
        const price = pfGetLivePrice(p.symbol) || Number(p.avg_price) || 0;
        const q = Number(p.qty) || 0;
        const mv = (q > 0 ? q : 1) * price;
        const r = (Array.isArray(marketData) && marketData.length) ? marketData.find(x => x.symbol === p.symbol) : null;
        // یکسان‌سازی ی/ک عربی ← فارسی (API با ی عربی می‌فرستد: «فلزات اساسي»)
        const sec = r && r.sector_name ? String(r.sector_name).replace(/\u064A/g, '\u06CC').replace(/\u0643/g, '\u06A9') : '';
        if (dollarSectors.some(s => sec.includes(s))) dollarMV += mv;
        else if (rialSectors.some(s => sec.includes(s))) rialMV += mv;
        // طبقه‌بندی بزرگ/چابک بر مبنای ارزش معاملات روز (q_tot_cap) — نبود field مارکت‌کپ در API
        const cap = r && r.q_tot_cap ? Number(r.q_tot_cap) : 0;
        if (cap >= 1e12) { largeMV += mv; } else { smallMV += mv; }
    });
    const ratio = (v, w) => (v + w) > 0 ? (v / (v + w) * 100) : 0;
    const setPct = (idPct, idBar, pct) => {
        const pEl = document.getElementById(idPct); if (pEl) pEl.textContent = pct.toFixed(1) + '٪';
        const bEl = document.getElementById(idBar); if (bEl) bEl.style.width = Math.min(100, pct) + '%';
    };
    setPct('pfDollarPct', 'pfDollarBar', ratio(dollarMV, rialMV));
    setPct('pfRialPct', 'pfRialBar', ratio(rialMV, dollarMV));
    setPct('pfLargePct', 'pfLargeBar', ratio(largeMV, smallMV));
    setPct('pfSmallPct', 'pfSmallBar', ratio(smallMV, largeMV));

    // ۳. هشدارهای FTS
    const alertsEl = document.getElementById('pfAlerts');
    if (alertsEl) {
        if (!pfState.positions.length) {
            alertsEl.innerHTML = '<div class="pf-alert-item pf-alert-ok">— پورتفوی خالی است —</div>';
        } else {
            const fails = [];
            pfState.positions.forEach(p => {
                const fts = pfComputeFTS(p);
                const fc = ['fund','tape','tech'].filter(k => fts[k] === 'fail').length;
                if (fc >= 2) fails.push(p.symbol + ' (' + fc + ' فاکتور قرمز)');
            });
            alertsEl.innerHTML = fails.length === 0
                ? '<div class="pf-alert-item pf-alert-ok">✅ همه پوزیشن‌ها در محدوده امن</div>'
                : fails.map(s => '<div class="pf-alert-item pf-alert-fail">⚠ ' + s + '</div>').join('');
        }
    }

    // ۴. جدول پوزیشن‌ها
    if (!pfState.positions.length) {
        tbody.innerHTML = '<tr><td colspan="11" class="ms-empty">پورتفوی خالی است. نمادی اضافه کنید.</td></tr>';
        return;
    }
    let html = '';
    pfState.positions.forEach((p, idx) => {
        const live = pfGetLivePrice(p.symbol);
        const avg = Number(p.avg_price) || 0;
        const pnl = (live > 0 && avg > 0) ? ((live - avg) / avg * 100) : 0;
        const sl = pfComputeSL(p, pfMode);
        const tp = Number(p.target) || 0;
        const rr = (tp > 0 && sl > 0 && avg > 0) ? ((tp - avg) / Math.max(0.0001, avg - sl)) : 0;
        const fts = pfComputeFTS(p);
        const tag = (k, label) => {
            const v = fts[k], r = fts.reasons[k];
            return '<span class="pf-tag pf-tag-' + v + '" title="' + (r || '').replace(/"/g,'&quot;') + '">' + label + ': ' + v + '</span>';
        };
        const pnlColor = pnl > 0 ? 'var(--accent-green)' : (pnl < 0 ? 'var(--accent-red)' : 'var(--text-muted)');
        html += '<tr>'
            + '<td><b style="color:var(--accent-blue);">' + p.symbol + '</b>' + (p.name ? '<div style="font-size:0.62rem;color:var(--text-secondary);margin-top:2px;">' + p.name + '</div>' : '') + '</td>'
            + '<td class="num"><input type="number" class="pf-cell-input" value="' + (avg||'') + '" onchange="pfUpdateField(' + idx + ',\'avg_price\',this.value)" placeholder="میانگین"></td>'
            + '<td class="num"><input type="text" class="pf-cell-input" value="' + (p.qty||'') + '" onchange="pfUpdateField(' + idx + ',\'qty\',this.value)" placeholder="تعداد"></td>'
            + '<td class="num">' + (live ? live.toLocaleString('fa-IR') : '<span style="color:var(--text-muted)">—</span>') + '</td>'
            + '<td class="num" style="color:' + pnlColor + ';">' + (pnl ? pnl.toFixed(2) + '٪' : '—') + '</td>'
            + '<td class="num">' + (sl ? sl.toLocaleString('fa-IR') : '<span style="color:var(--text-muted)">—</span>') + '</td>'
            + '<td class="num"><input type="number" class="pf-cell-input" value="' + (tp||'') + '" onchange="pfUpdateField(' + idx + ',\'target\',this.value)" placeholder="تارگت"></td>'
            + '<td class="num"><b style="color:' + (rr >= 2 ? 'var(--accent-green)' : (rr >= 1 ? '#f59e0b' : '#f43f5e')) + ';">' + (rr ? rr.toFixed(2) : '—') + '</b></td>'
            + '<td class="pf-fts-cell">' + tag('fund','بنیادی') + ' ' + tag('tape','تابلو') + ' ' + tag('tech','تکنیکال') + '</td>'
            + '<td><input type="text" class="pf-cell-input" value="' + (p.note||'').replace(/"/g,'&quot;') + '" onchange="pfUpdateField(' + idx + ',\'note\',this.value)" placeholder="یادداشت…"></td>'
            + '<td><button class="ms-chipbtn" onclick="pfRemovePos(\'' + p.symbol + '\')" title="حذف">🗑</button></td>'
            + '</tr>';
    });
    tbody.innerHTML = html;
}

function pfUpdateField(idx, key, val) {
    if (!pfState.positions[idx]) return;
    if (key === 'avg_price' || key === 'qty' || key === 'target') {
        const n = parseFloat(val);
        pfState.positions[idx][key] = (isNaN(n) || n < 0) ? 0 : n;
    } else {
        pfState.positions[idx][key] = val;
    }
    pfSave();
    pfRender();
}
