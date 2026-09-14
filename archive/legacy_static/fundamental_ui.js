/* ══════════════════════════════════════════════════════════════════════════
   Fundamental Insights UI — «تحلیل کامل» (تب #tabFund در #chartModal)
   ──────────────────────────────────────────────────────────────────────────
   v9.8.1 فاز ۰ (interface freeze): این دامنه از static/app.js جدا شد تا
   مالکیتش یکتا باشد و ویرایش موازی روی app.js تصادم نکند.

   رابط تثبیتشده (مصرفکنندهها در app.js):
     · loadFundamentalData(symbol)   ← openAnalysis()
     · switchModalTab('fund'|'tech') ← openAnalysis() و دکمههای تب مودال
     · fmtMcap(v) / fmtBil(v)        ← renderScreenerTable()

   وابستگی به بیرون (فقط خواندن؛ اینجا تعریف نمیشوند):
     · fmtMoney() و formatNumber() ← app.js (fmtBil روی fmtMoney سوار است)
   ══════════════════════════════════════════════════════════════════════════ */

// mcap به ریال است → همت = /1e13 (1 همت = 1e12 تومان = 1e13 ریال)
function fmtMcap(v) {
    if (!v || v <= 0) return '—';
    const h = v / 1e13; // همت
    if (h >= 0.01) return h.toLocaleString('fa-IR', { maximumFractionDigits: 2 }) + ' همت';
    return (v / 1e10).toLocaleString('fa-IR', { maximumFractionDigits: 2 }) + ' میلیارد تومان';
}

// Fundamental Insights UI implementation
async function loadFundamentalData(symbol, months) {
    window.__fundSymbol = symbol || '';     // «اعمالِ فوری» پنل همین کارت را تازه میکند
    try {
        const res = await fetch(`/api/fundamental/${encodeURIComponent(symbol)}`);
        const json = await res.json();

        // نبود داده → پیام روشن (دکمهٔ «تحلیل کامل» هیچ‌وقت از جدول حذف نمی‌شود)
        if (!res.ok || json.detail || json.status === 'error') {
            const nb = document.getElementById('smartInsightsBox');
            if (nb) nb.innerHTML = '<div style="background:rgba(244,63,94,.08); border:1px solid rgba(244,63,94,.35); '
                + 'border-radius:10px; padding:12px 14px; margin-bottom:12px; font-size: 0.8125rem; line-height:2.1;">'
                + '⛔ <b>دادهٔ بنیادی برای «' + (symbol || '—') + '» یافت نشد.</b><br>'
                + '<span style="color:var(--text-secondary); font-size: 0.75rem;">این نماد صورت‌مالی ثبت‌شدهٔ کدال ندارد '
                + '(صندوق / حق تقدم / قرارداد / نماد متوقف) یا در پایگاه داده نیست. '
                + 'برای بررسی وضعیت هفتگی و ثبت تصمیم، از دکمهٔ «📊 تکنیکال» استفاده کنید.</span></div>';
            return;
        }

        const m = json.metrics || {};
        // ارزش بازار: عدد + منبع. اگر تابلو عددی ندارد، «—» با دلیل — نه صفر.
        document.getElementById('mMcap').innerText =
            (m.mcap > 0 ? fmtMcap(m.mcap) : 'بدون ارزش بازار') +
            (m.mcap > 0 && m.mcap_stale ? ' (قدیمی)' : '');
        document.getElementById('mMcap').title = m.mcap > 0
            ? ('منبع: ' + (m.mcap_source || 'تابلوی TSETMC') +
               (m.mcap_asof ? ' · نشست ' + m.mcap_asof : ''))
            : ('ارزش بازار از تابلو خوانده نشد: ' + (m.mcap_error || '—'));
        document.getElementById('mRev').innerText = m.annual_sales_bt ? fmtBil(m.annual_sales_bt * 1e9) : '—';
        document.getElementById('mPS').innerText = m.sales_to_mcap != null ? `Sales/Mcap: ${m.sales_to_mcap}` : '—';
        document.getElementById('mGMar').innerText = m.gross_margin != null ? `${m.gross_margin}%` : '—';

        const box = document.getElementById('smartInsightsBox');
        const mo = json.methodology || {}, th = mo.thresholds || {};
        const thrTxt = [
            th.monetary_growth_min != null ? 'رشد ریالی ≥ ' + th.monetary_growth_min + '٪' : '',
            th.volume_growth_min != null ? 'رشد فیزیکی ≥ ' + th.volume_growth_min + '٪' : '',
            th.eps_years ? 'EPS ↑ ' + th.eps_years + ' سال' : '',
            th.margin_min != null ? 'حاشیه ≥ ' + th.margin_min + '٪' : '',
            th.sales_to_mcap_min != null ? 'فروش÷ارزش ≥ ' + th.sales_to_mcap_min + '×' : '',
            th.potential_min != null ? 'پتانسیل سود ≥ ' + th.potential_min + '٪' : '',
        ].filter(Boolean).join('  ·  ');
        box.innerHTML = '<h3 style="margin-bottom:5px; color:var(--accent-blue); border-bottom:1px solid var(--border-color); padding-bottom:8px;">✅ چک‌لیست ۵ لایهٔ استراتژی FTS' +
            (mo.version ? ` <span style="font-size:0.6875rem; font-weight:700; color:#000; background:var(--accent-blue); border-radius:6px; padding:1px 7px; margin-right:6px;">${mo.version}</span>` : '') +
            '</h3>' +
            `<div style="display:flex; gap:8px; align-items:center; margin-bottom:6px; font-size:0.75rem; color:var(--text-secondary); flex-wrap:wrap;">
                <span style="font-weight:800; color:${json.score >= 4 ? '#10b981' : json.score >= 3 ? '#eab308' : '#f43f5e'};">امتیاز ${json.score} / 5</span>
                <span>·</span><span>${json.verdict || ''}</span>
                <span>·</span><span>گروه: ${json.sector || '—'}</span>
                <span>·</span><span>طبقه: ${(json.profile && json.profile.label) || '—'}</span>
            </div>` +
            (thrTxt ? `<div style="font-size:0.6875rem; color:var(--text-secondary); margin-bottom:12px; opacity:.85;">آستانه‌های فعال: ${thrTxt}</div>` : '');

        // خلاصهٔ پنج‌لایه — «داده نیست» رنگِ خاکستری دارد، نه قرمز (قرمز = مردود)
        const NOD = '#64748b';
        const cell = (lbl, val, color, sub) =>
            `<div style="background:var(--bg-primary); border:1px solid var(--border-color); border-radius:8px; padding:8px 10px;">
                <div style="font-size: 0.6562rem; color:var(--text-secondary);">${lbl}</div>
                <div style="font-size: 0.8125rem; font-weight:800; color:${color || 'var(--text-primary)'}; direction:ltr; text-align:left;">${val}</div>
                ${sub ? `<div style="font-size: 0.625rem; color:var(--text-secondary); margin-top:2px;">${sub}</div>` : ''}
            </div>`;
        const pct1 = v => (v == null ? '—' : Number(v).toFixed(1) + '٪');
        const ge = (v, t) => (v == null ? NOD : (v >= t ? '#10b981' : '#f43f5e'));
        const P = json.passes || {};
        const g1a = (m.monetary_growth_pct != null ? m.monetary_growth_pct : m.growth_pct);
        const g1b = (m.volume_growth_pct != null ? m.volume_growth_pct : m.real_growth_pct);
        const gmCol = (m.gross_margin == null ? NOD
                     : m.gross_margin >= (th.margin_ideal != null ? th.margin_ideal : 30) ? '#10b981'
                     : m.gross_margin >= (th.margin_min != null ? th.margin_min : 20) ? '#eab308' : '#f43f5e');
        const pm5 = { free: 'آزاد / بورس‌کالا', mandatory: 'دستوری', neutral: 'بی‌طرف' }[json.pricing_mode];
        const summ = document.createElement('div');
        summ.style.cssText = 'display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:16px;';
        // جدول بنیادی: دورهٔ ناقص سطر را حذف نمیکند — «-» و سطرِ قرمز
        const faD = s => String(s).replace(/[0-9]/g, d => '۰۱۲۳۴۵۶۷۸۹'[+d]);
        const drow = (json.details && json.details['۲'] && json.details['۲'].period_row) || null;
        const epsCells = (drow && drow.cells) ||
            (m.eps_series || []).map(v => (v == null ? '-' : formatNumber(v)));
        const epsAny = epsCells.some(c => c !== '-');
        const epsPart = !!(drow && drow.red) || (!!m.eps_partial && epsAny);
        summ.innerHTML =
            cell('۱الف رشد ریالی', pct1(g1a), ge(g1a, th.monetary_growth_min != null ? th.monetary_growth_min : 60),
                 '≥ ' + (th.monetary_growth_min != null ? th.monetary_growth_min : 60) + '٪' + (g1a == null ? ' · شکاف داده' : '')) +
            cell('۱ب رشد فیزیکی', pct1(g1b), ge(g1b, th.volume_growth_min != null ? th.volume_growth_min : 0),
                 m.quantity_verified ? 'تناژ/تعداد گزارش‌شده' : 'تعدیل تورمی (بدون تناژ)') +
            cell(epsPart ? '۲ روند EPS (تنها ' + faD(m.eps_available || epsCells.filter(c => c !== '-').length) + ' دوره موجود است)' : '۲ روند EPS',
                 epsAny ? epsCells.join(' → ') : 'داده کم',
                 P['2_eps_trend'] ? '#10b981' : (epsAny ? '#f43f5e' : NOD),
                 (th.eps_years || 3) + ' سال صعودی' +
                 (m.eps_projected_year != null ? ' · برآورد ' + m.eps_projected_year : '')) +
            cell('۳ حاشیه ناخالص', m.gross_margin != null ? pct1(m.gross_margin) : 'نامرتبط',
                 gmCol, '≥ ' + (th.margin_min != null ? th.margin_min : 20) + '٪ · ایده‌آل ' +
                 (th.margin_ideal != null ? th.margin_ideal : 30) + '٪') +
            cell('۴ فروش÷ارزش · پتانسیل',
                 (m.sales_to_mcap != null ? m.sales_to_mcap.toFixed(2) + '×' : '—') + ' · ' + pct1(m.profit_potential_pct),
                 (P['4_sales_to_mcap'] || P['4b_profit_potential']) ? '#10b981'
                     : (m.sales_to_mcap == null && m.profit_potential_pct == null) ? NOD : '#f43f5e',
                 '≥ ' + (th.sales_to_mcap_min != null ? th.sales_to_mcap_min : 1) + '× · ≥ ' +
                 (th.potential_min != null ? th.potential_min : 33) + '٪ 〔م=' + (m.months_used || '—') +
                 ' ×' + (m.scale_factor || 1) + '〕') +
            cell('۵ رژیم قیمت‌گذاری', pm5 || '—',
                 pm5 == null ? NOD : (P['5_industry'] ? '#10b981' : '#f43f5e'),
                 'حالت پنل: ' + ((json.thresholds || {}).industry_mode || '—'));
        box.appendChild(summ);

        // شکاف داده — چه چیزی کم است و چطور بسته میشود
        const gaps = json.data_gaps || [];
        if (gaps.length) {
            const gw = document.createElement('div');
            gw.style.cssText = 'background:rgba(100,116,139,0.10); border:1px dashed rgba(148,163,184,.55); border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size:0.75rem; line-height:2.0;';
            gw.innerHTML = '<b style="color:#94a3b8;">🔎 شکافِ داده (این لایه‌ها داوری نشدند، نه اینکه مردود شدند)</b>' +
                gaps.map(g => `<div style="margin-top:4px;">• <b>${g.layer}</b> — ${g.why || 'بدون دلیل'}
                    <div style="color:var(--text-secondary); font-size:0.6875rem;">🛠 ${g.fix || '—'}</div></div>`).join('');
            box.appendChild(gw);
        }

        // حذف خودکار از غربالگری
        if (json.excluded) {
            const xd = document.createElement('div');
            xd.style.cssText = 'background:rgba(244,63,94,0.08); border:1px solid rgba(244,63,94,0.4); border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size:0.8125rem; color:#f43f5e;';
            xd.innerHTML = '⛔ حذف خودکار از خروجی FTS — ' + (json.exclusion_reasons || []).join(' · ');
            box.appendChild(xd);
        }


        // ارجاع نماد اصلی برای قراردادها/ناقص‌ها
        if (json.ref_symbol) {
            const rd = document.createElement('div');
            rd.style.cssText = 'background:rgba(250,204,21,0.08); border:1px solid rgba(250,204,21,0.35); border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size: 0.8125rem;';
            rd.innerHTML = `💡 ${json.ref_reason || 'این نماد تحلیل مستقل ندارد'} — <b>${json.ref_symbol}</b>` +
                `<button onclick="openAnalysis('${json.ref_symbol}', '${json.ref_symbol}'); document.getElementById('smartInsightsModal').classList.remove('active');" style="margin-right:10px; padding:4px 12px; border-radius:8px; border:none; background:var(--accent-blue); color:#000; font-weight:700; cursor:pointer;">📊 تحلیل کامل ${json.ref_symbol}</button>`;
            box.appendChild(rd);
        } else if (json.fs_count === 0) {
            const rd = document.createElement('div');
            rd.style.cssText = 'background:rgba(250,204,21,0.08); border:1px solid rgba(250,204,21,0.35); border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size: 0.8125rem;';
            rd.innerHTML = '⚠️ <b>صورت مالی در کدال برای این نماد موجود نیست</b> — شامل صندوق‌ها/قراردادها/حق تقدم‌ها. تحلیل ۵ شاخصی فقط برای نمادهای دارای صورت مالی معنا دارد.';
            box.appendChild(rd);
        }

        (json.insights || []).forEach(item => {
            const div = document.createElement('div');
            div.className = `insight-item ${item.type}`;
            div.style.marginBottom = '10px';
            const isStep = item.step && item.step !== '۰';
            let detBtn = '', detPanel = '';
            if (isStep && json.details && json.details[item.step]) {
                detBtn = `<button onclick="toggleInsightDetail(this)" style="margin-top:5px; padding:3px 12px; border-radius:7px; border:1px solid var(--border-color); background:rgba(56,189,248,0.1); color:var(--accent-blue); cursor:pointer; font-family:inherit; font-size: 0.6875rem;">📋 جزئیات (فرمول و منبع)</button>`;
                const dd = json.details[item.step];
                const SC = { pass: '#10b981', fail: '#f43f5e', warn: '#eab308', nodata: '#64748b', na: '#64748b' };
                const SI = { pass: '✅', fail: '🚫', warn: '⚠️', nodata: '⬜', na: '➖' };
                // سطر جدولِ شاخص ۲ — در حالتِ ناقص عنوان و همهٔ سلول‌ها قرمز،
                // و دورهٔ ناموجود با علامت «-» (هرگز سطر حذف نمیشود).
                const pr = dd.period_row;
                const prHtml = pr ? `<table dir="rtl" style="width:100%; border-collapse:collapse; font-size:0.75rem; margin-bottom:8px;">
                    <tr>
                        <td style="border:1px solid ${pr.red ? 'rgba(244,63,94,.55)' : 'var(--border-color)'}; padding:5px 8px; text-align:right; font-weight:800;${pr.red ? ' color:red;' : ''}">${pr.label}</td>
                        ${(pr.periods || []).map(p => `<td dir="ltr" style="border:1px solid ${pr.red ? 'rgba(244,63,94,.55)' : 'var(--border-color)'}; padding:5px 8px; text-align:center;${pr.red ? ' color:red; font-weight:800;' : ''}">${p.missing ? '-' : p.value}<div style="font-size:0.625rem; opacity:.65; font-weight:400;">${p.year}</div></td>`).join('')}
                    </tr></table>` : '';
                const strip = (dd.subchecks || []).map(s => `
                    <div style="border:1px solid var(--border-color); border-right:3px solid ${SC[s.state] || SC.nodata}; border-radius:7px; padding:6px 9px; background:rgba(15,23,42,.35);">
                        <div style="font-size:0.6562rem; color:var(--text-secondary);">${SI[s.state] || ''} ${s.label}</div>
                        <div style="font-size:0.7813rem; font-weight:800; color:${SC[s.state] || 'inherit'};" dir="ltr">${s.value || '—'}</div>
                        <div style="font-size:0.625rem; color:var(--text-secondary);">آستانه: ${s.threshold || '—'}</div>
                        ${s.detail ? `<div style="font-size:0.625rem; color:var(--text-secondary); opacity:.85; margin-top:2px;">${s.detail}</div>` : ''}
                    </div>`).join('');
                detPanel = `<div class="insight-detail" style="display:none; margin-top:8px; padding:10px 12px; background:var(--bg-primary); border:1px solid var(--border-color); border-radius:8px; font-size: 0.75rem; line-height:1.9;">
                    ${prHtml}
                    ${strip ? `<div style="display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:6px; margin-bottom:8px;">${strip}</div>` : ''}
                    <div style="color:var(--text-secondary);"><b style="color:var(--accent-blue);">🧮 فرمول:</b> ${dd.formula || '—'}</div>
                    <div style="color:var(--text-secondary);"><b style="color:var(--accent-green);">🗂 منبع:</b> ${dd.source || '—'}</div>
                    <div style="color:var(--text-secondary);"><b style="color:var(--accent-yellow);">📐 محاسبه:</b> ${dd.calc || '—'}</div>
                    ${dd.what ? `<div style="color:var(--text-secondary);"><b style="color:#a78bfa;">💡 نکته:</b> ${dd.what}</div>` : ''}
                </div>`;
            }
            div.innerHTML = `
                <div style="font-size: 0.75rem; opacity: 0.9; margin-bottom: 4px;">${isStep ? 'شاخص ' + item.step + ': ' : ''}<strong>${item.title}</strong></div>
                <div style="font-size: 0.875rem; font-weight: 700;">${item.text}</div>
                ${detBtn}${detPanel}
            `;
            box.appendChild(div);
        });

        // toggle جزئیات
        window.toggleInsightDetail = function(btn) {
            const p = btn.nextElementSibling;
            if (p) p.style.display = p.style.display === 'none' ? 'block' : 'none';
        };

        // جزییات ثانویه — خارج از پنج محور غربالگری
        const secObj = json.secondary || {};
        const secKeys = Object.keys(secObj);
        if (secKeys.length) {
            const sw = document.createElement('div');
            sw.style.cssText = 'margin-top:14px; padding:10px 12px; background:var(--bg-primary); border:1px dashed var(--border-color); border-radius:8px; font-size:0.7188rem; color:var(--text-secondary); line-height:1.9;';
            sw.innerHTML = '<b style="color:#a78bfa;">📎 جزییات ثانویه (خارج از غربالگری پنج‌محوره)</b><br>' +
                secKeys.map(k => `• ${k}: ${secObj[k]}`).join('<br>');
            box.appendChild(sw);
        }

        // جدول صورت‌های مالی سالانهٔ مرجع — پشتوانهٔ دقیق اعداد
        if (json.history && json.history.length) {
            const h = document.createElement('div');
            h.style.marginTop = '18px';
            h.innerHTML = '<h4 style="margin:12px 0 8px; color:var(--accent-blue);">📚 صورت‌های مالی سالانهٔ مرجع (۱۲ماهه — شرکت اصلی)</h4>';
            let rows = json.history.map(r => `
                <tr>
                    <td style="color:#38bdf8; font-weight:700;">${r.period_end}</td>
                    <td dir="ltr">${r.revenue ? fmtBil(r.revenue) : '—'}</td>
                    <td dir="ltr">${r.gross_profit ? fmtBil(r.gross_profit) : '—'}</td>
                    <td dir="ltr" style="color:${r.net_profit >= 0 ? '#4ade80' : '#f43f5e'};">${r.net_profit ? fmtBil(r.net_profit) : '—'}</td>
                    <td dir="ltr">${r.eps != null ? formatNumber(r.eps) : '—'}</td>
                    <td style="font-size: 0.6875rem;">${r.audited ? '✅ حسابرسی‌شده' : '⚠️ حسابرسی‌نشده'}</td>
                    <td style="font-size: 0.6875rem;">${r.consolidated ? 'تلفیقی' : 'اصلی'}</td>
                </tr>`).join('');
            h.innerHTML += `<table style="width:100%; border-collapse:collapse; font-size: 0.75rem;">
                <thead><tr style="color:#94a3b8; font-size: 0.6875rem;">
                    <th style="text-align:right;">پایان دوره</th><th>فروش (میلیارد)</th><th>سود ناخالص</th><th>سود خالص</th><th>EPS</th><th>حسابرسی</th><th>سطح</th>
                </tr></thead><tbody>${rows}</tbody></table>`;
            box.appendChild(h);
        }
    } catch (e) {
        console.error(e);
    }
}

function fmtBil(v) {
    // متابعت از numFmt: 'raw' = عدد خام کدال (میلیون ریال)؛ 'jooze' = حذف ۴ رقم از راست (میلیارد تومان)
    return fmtMoney(v);
}

function switchModalTab(tabId) {
    const tTech = document.getElementById('tabTech');
    const tFund = document.getElementById('tabFund');
    if (tTech) tTech.style.display = tabId === 'tech' ? 'block' : 'none';
    if (tFund) tFund.style.display = tabId === 'fund' ? 'block' : 'none';
    const bTech = document.getElementById('tabBtnTech');
    const bFund = document.getElementById('tabBtnFund');
    if (bTech) {
        bTech.style.background = tabId === 'tech' ? 'var(--accent-blue)' : 'rgba(56, 189, 248, 0.15)';
        bTech.style.color = tabId === 'tech' ? '#000' : 'var(--accent-blue)';
    }
    if (bFund) {
        bFund.style.background = tabId === 'fund' ? 'var(--accent-blue)' : 'rgba(56, 189, 248, 0.15)';
        bFund.style.color = tabId === 'fund' ? '#000' : 'var(--accent-blue)';
    }
}

/* ══════════════════════════════════════════════════════════════════════════
   پنل «پیش‌شرط‌های ۵ شاخص» — اعتبارسنجی، LocalStorage و بازپالایش بی‌بارگذاری
   ──────────────────────────────────────────────────────────────────────────
   چرا این‌جا و نه در app.js: مالکیتِ دامنهٔ بنیادی با همین فایل است (v9.8.1
   interface freeze) و handlerهای inline در index.html به نامِ جهانی
   `saveFtsConfig`/`loadFtsConfig` وصل‌اند؛ پس همان نام‌ها بازنویسی میشوند و
   نه دکمه‌ای عوض میشود نه index.html.
   رفتار:
     · «ذخیره و اعمال» → اعتبارسنجی (فقط عددِ مثبت) → LocalStorage
       → POST /api/fts/config → بازپالایشِ بی‌بارگذاریِ صفحه
     · «بازیابی» (loadFtsConfig(true)) → بازگشتِ تمیزِ همهٔ فیلدها به
       پیش‌فرض‌هایِ جزوه؛ سرور هم همان مقادیر را می‌گیرد
     · بازکردنِ پنل (loadFtsConfig()) → سرور، و رویش LocalStorage اگر هست
   ══════════════════════════════════════════════════════════════════════════ */
const FTS_SETTINGS = (function () {
  // پیش‌فرض‌هایِ جزوه — آینهٔ bors_config.FTS_DEFAULTS + FTS_V10_DEFAULTS.
  const DEFAULTS = {
    growth_min: 40.0, inflation_min: 58.0, eps_years: 3, margin_min: 20.0,
    margin_optimal: 30.0, sales_to_mcap_min: 1.0, profit_potential_min: 30.0,
    mcap_min_hmt: 0.0, watchlist_max: 50, suspended_max_stale_sessions: 3,
    min_trade_val: 0.0, filter_m141: false,
    industry_mode: 'Exclude_Mandatory_Pricing',
    mandatory_sectors: ['خودرو', 'دارو', 'نیروگاه', 'غذا', 'لاستیک', 'شوینده', 'بیمه'],
    free_sectors: ['سیمان', 'پتروشیمی', 'شیمیایی', 'فلزات', 'کانی', 'کاشی', 'سرامیک',
                   'کانه', 'معادن', 'نفت', 'محصولات فلزی'],
    v10_sales_to_mcap_min: 0.33, v10_monetary_growth_min: 60.0,
    include_industries: [], exclude_industries: []
  };
  // بازهٔ مجازِ هر عدد — «مثبت بودن» همان‌جا که معنا دارد ≥0 است، نه >0:
  // صفر یعنی «این فیلتر خاموش است» و باید قابلِ تنظیم بماند.
  const NUM = {
    growth_min: [0, 1000], inflation_min: [0, 1000], margin_min: [0, 100],
    margin_optimal: [0, 100], sales_to_mcap_min: [0, 1000],
    profit_potential_min: [0, 1000], mcap_min_hmt: [0, 1e9], min_trade_val: [0, 1e9],
    v10_sales_to_mcap_min: [0, 1000], v10_monetary_growth_min: [0, 1000]
  };
  const INT = { eps_years: [1, 12], watchlist_max: [1, 500],
                suspended_max_stale_sessions: [1, 20] };
  const LIST = ['mandatory_sectors', 'free_sectors', 'include_industries',
                'exclude_industries'];
  const BOOL = ['filter_m141'];
  const STR = ['industry_mode'];
  const MODES = ['Exclude_Mandatory_Pricing', 'Rank_Only', 'Include_Industries',
                 'Exclude_Industries'];
  const LS_KEY = 'bors.fts_settings.v10';

  function node(id) { return document.getElementById('fts_' + id); }

  // «،» فارسی و «,» لاتین هر دو جداکننده‌اند؛ فاصله trim؛ نوشتهٔ خالی حذف.
  function parseList(raw) {
    return String(raw == null ? '' : raw)
      .replace(/\u060c/g, ',').split(',')
      .map(function (s) { return s.trim(); })
      .filter(function (s) { return s.length; });
  }
  // ارقامِ فارسی/عربی هم پذیرفته میشوند (کاربر با کیبوردِ فارسی تایپ میکند).
  function toNumber(raw) {
    const s = String(raw == null ? '' : raw).trim()
      .replace(/[\u06F0-\u06F9]/g, function (d) { return String(d.charCodeAt(0) - 0x06F0); })
      .replace(/[\u0660-\u0669]/g, function (d) { return String(d.charCodeAt(0) - 0x0660); })
      .replace(/[٬،]/g, '').replace(/\s/g, '');
    if (!s.length) return null;                 // تهی = «همان پیش‌فرض بماند»
    if (!/^-?\d+(\.\d+)?$/.test(s)) return NaN; // هر چیزِ دیگر → نامعتبر
    return Number(s);
  }
  function read() {
    const out = {};
    Object.keys(NUM).forEach(function (k) {
      const el = node(k); if (!el) return;
      const v = toNumber(el.value);
      if (v !== null) out[k] = v;
    });
    Object.keys(INT).forEach(function (k) {
      const el = node(k); if (!el) return;
      const v = toNumber(el.value);
      if (v !== null) out[k] = Math.round(v);
    });
    LIST.forEach(function (k) {
      const el = node(k); if (!el) return;
      out[k] = parseList(el.value);
    });
    BOOL.forEach(function (k) {
      const el = node(k); if (!el) return;
      out[k] = !!el.checked;
    });
    STR.forEach(function (k) {
      const el = node(k); if (!el) return;
      if (el.value) out[k] = String(el.value);
    });
    return out;
  }


  function validate(vals) {
    const errs = {};
    Object.keys(NUM).forEach(function (k) {
      if (!(k in vals)) return;
      const v = vals[k];
      if (typeof v !== 'number' || isNaN(v)) errs[k] = 'عددِ معتبر نیست';
      else if (v < 0) errs[k] = 'عددِ منفی مجاز نیست';
      else if (v > NUM[k][1]) errs[k] = 'باید ≤ ' + NUM[k][1] + ' باشد';
    });
    Object.keys(INT).forEach(function (k) {
      if (!(k in vals)) return;
      const v = vals[k];
      if (typeof v !== 'number' || isNaN(v)) errs[k] = 'عددِ صحیح لازم است';
      else if (v < INT[k][0] || v > INT[k][1])
        errs[k] = 'باید بین ' + INT[k][0] + ' و ' + INT[k][1] + ' باشد';
    });
    if ('industry_mode' in vals && MODES.indexOf(vals.industry_mode) < 0)
      errs.industry_mode = 'حالتِ شناخته‌شده‌ای نیست';
    if (vals.margin_optimal != null && vals.margin_min != null &&
        vals.margin_optimal < vals.margin_min)
      errs.margin_optimal = 'حاشیهٔ ایده‌آل نمی‌تواند زیرِ کف باشد';
    return errs;
  }
  function paintErrors(errs) {
    Object.keys(NUM).concat(Object.keys(INT)).concat(LIST).concat(STR).forEach(function (k) {
      const el = node(k);
      if (el) el.style.borderColor = errs[k] ? '#ef4444' : '';
    });
    const bad = Object.keys(errs);
    const msg = document.getElementById('ftsPreMsg');
    if (msg && bad.length) {
      msg.style.color = '#ef4444';
      msg.textContent = '✕ ' + bad.map(function (k) { return k + ': ' + errs[k]; }).join(' · ');
    }
    return bad.length;
  }
  // فقط کلیدهایی که در vals هستند نوشته میشوند — تا «overlayِ محلی روی
  // پاسخِ سرور» بقیهٔ فیلدها را به پیش‌فرضِ JS برنگرداند.
  function writeForm(vals) {
    Object.keys(vals || {}).forEach(function (k) {
      const el = node(k);
      if (!el) return;
      const v = vals[k];
      if (BOOL.indexOf(k) >= 0) el.checked = !!v;
      else if (LIST.indexOf(k) >= 0) el.value = (v || []).join('، ');
      else el.value = (v === null || v === undefined) ? DEFAULTS[k] : v;
    });
  }
  // «بازیابی» = همهٔ فیلدها، حتی آنهایی که کاربر هرگز ندیده، به جزوه برگردند
  function writeDefaults() { writeForm(DEFAULTS); }
  function loadLS() {
    try { return JSON.parse(localStorage.getItem(LS_KEY) || '{}') || {}; }
    catch (e) { return {}; }
  }
  function saveLS(vals) {
    try { localStorage.setItem(LS_KEY, JSON.stringify(vals)); return true; }
    catch (e) { return false; }                            // private-mode/پر
  }
  function clearLS() { try { localStorage.removeItem(LS_KEY); } catch (e) {} }

  // دو حالتِ Include/Exclude و فیلدهایِ تازه — بی‌دست‌زدن به index.html
  function ensureControls() {
    const sel = node('industry_mode');
    if (sel) {
      const txt = { Include_Industries: 'فقط صنایعِ «شامل» بمانند (Include)',
                    Exclude_Industries: 'صنایعِ «مستثنی» را حذف کن (Exclude)' };
      MODES.forEach(function (m) {
        if (!txt[m]) return;
        const have = [].slice.call(sel.options).some(function (o) { return o.value === m; });
        if (!have) {
          const o = document.createElement('option');
          o.value = m; o.textContent = txt[m]; sel.appendChild(o);
        }
      });
    }
    const body = document.getElementById('ftsPreBody');
    if (!body) return;
    [['v10_sales_to_mcap_min', 'کفِ فروش÷ارزش (کارت بنیادی)', '×', '0.01'],
     ['v10_monetary_growth_min', 'رشد ریالیِ چک ۱الف (کارت بنیادی)', '٪', '5'],
     ['include_industries', 'صنایع شامل — فقط اینها بمانند (ویرگول جدا)', '', ''],
     ['exclude_industries', 'صنایع مستثنی — اینها حذف شوند (ویرگول جدا)', '', '']
    ].forEach(function (w) {
      if (node(w[0])) return;
      const lab = document.createElement('label');
      lab.className = 'fts-lbl fts-lbl--stack';
      const nm = document.createElement('span');
      nm.className = 'fts-name'; nm.textContent = w[1]; lab.appendChild(nm);
      const wrap = document.createElement('span'); wrap.className = 'fts-field';
      let inp;
      if (LIST.indexOf(w[0]) >= 0) {
        inp = document.createElement('textarea');
        inp.className = 'fts-inp fts-ta'; inp.rows = 2; inp.spellcheck = false;
        inp.placeholder = 'مثلاً: خودرو، دارو';
      } else {
        inp = document.createElement('input');
        inp.type = 'number'; inp.className = 'fts-inp'; inp.min = '0'; inp.step = w[3];
      }
      inp.id = 'fts_' + w[0];
      wrap.appendChild(inp);
      if (w[2]) {
        const u = document.createElement('span');
        u.className = 'fts-unit'; u.textContent = w[2]; wrap.appendChild(u);
      }
      lab.appendChild(wrap);
      body.appendChild(lab);
    });
  }

  return { DEFAULTS: DEFAULTS, LS_KEY: LS_KEY, MODES: MODES, read: read,
           validate: validate, paintErrors: paintErrors, writeForm: writeForm,
           writeDefaults: writeDefaults,
           loadLS: loadLS, saveLS: saveLS, clearLS: clearLS, parseList: parseList,
           toNumber: toNumber, ensureControls: ensureControls };
})();


/* ── «ذخیره و اعمال» / «بازیابی» — بازنویسیِ handlerهای app.js ─────────────
   بنیادِ کار: index.html این دو نامِ جهانی را با onclick صدا می‌زند و
   fundamental_ui.js بعد از app.js بارگذاری میشود (خط ۹۵۷ و ۹۶۲)، پس همین
   بازنویسی کافی است — نه markup عوض میشود نه app.js که مالکیتِ مشترک دارد.
   رفتارِ app.js (POST به /api/fts/config و initScreener) حفظ میشود و رویش
   اعتبارسنجی + LocalStorage + رویدادِ بازپالایش می‌آید.                        */
(function () {
  const _origLoad = window.loadFtsConfig;      // app.js: GET /api/fts/config

  function setMsg(color, text) {
    const msg = document.getElementById('ftsPreMsg');
    if (!msg) return;
    msg.style.color = color;
    msg.textContent = text;
  }

  // بازپالایش بی‌بارگذاریِ صفحه: جدول بنیادی + کارتِ باز + فهرستِ سبد
  function reapply() {
    try {
      document.dispatchEvent(new CustomEvent('fts-settings-applied',
        { detail: FTS_SETTINGS.read() }));
    } catch (e) {}
    try { if (typeof initScreener === 'function') initScreener(true); } catch (e) {}
    try {
      const sym = (typeof STATE !== 'undefined' && STATE && STATE.selectedSymbol) ||
                  (typeof window !== 'undefined' && window.__fundSymbol) || '';
      if (sym && typeof loadFundamentalData === 'function') loadFundamentalData(sym);
    } catch (e) {}
  }

  window.saveFtsConfig = async function () {
    FTS_SETTINGS.ensureControls();
    const vals = FTS_SETTINGS.read();
    const errs = FTS_SETTINGS.validate(vals);
    if (FTS_SETTINGS.paintErrors(errs)) {
      setMsg('#ef4444', '✕ ذخیره نشد — ' + Object.keys(errs).length + ' فیلد نامعتبر است');
      return { status: 'error', errors: errs };
    }
    // فیلدِ خالی = «همان پیش‌فرضِ جزوه»؛ پس پیش‌فرض‌ها زیرِ مقدارهایِ فرم
    // چیده میشوند و **همهٔ** کلیدها می‌روند — وگرنه یک کلیدِ حذف‌شده روی
    // سرور مقدارِ کهنهٔ fts_thresholds.json را نگه می‌داشت و دو منبعِ حقیقت
    // (فرم و فایل) از هم واگرا می‌ماند.
    const body = Object.assign({}, FTS_SETTINGS.DEFAULTS, vals);
    const stored = FTS_SETTINGS.saveLS(body);
    if (!stored) setMsg('#eab308', '⚠ LocalStorage پر شد؛ فقط روی سرور ذخیره میشود');
    let res = null;
    try {
      const r = await fetch('/api/fts/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      res = await r.json();
    } catch (e) { res = null; }
    if (!res || res.status !== 'success') {
      const srv = res && res.errors
        ? ' · ' + Object.keys(res.errors).map(function (k) { return k + ': ' + res.errors[k]; }).join(' · ')
        : '';
      setMsg('#ef4444', '✕ سرور نپذیرفت' + srv + ' — تنظیمات محلی ماند، سرور نه');
      return res || { status: 'error' };
    }
    if (res.config) FTS_SETTINGS.writeForm(res.config);   // نرمال‌شدهٔ سرور
    setMsg('#22c55e', '✓ ذخیره و اعمال شد (محلی + سرور) — بدون بارگذاریِ دوباره');
    if (typeof rvToastSv === 'function') { try { rvToastSv('📐 پیش‌شرط‌ها اعمال شد'); } catch (e) {} }
    reapply();
    return res;
  };

  // force=true یعنی دکمهٔ «بازیابی» → پیش‌فرض‌هایِ جزوه، نه خواندنِ دوبارهٔ سرور
  window.loadFtsConfig = async function (force) {
    FTS_SETTINGS.ensureControls();
    if (!force) {
      if (_origLoad) { try { await _origLoad(false); } catch (e) {} }
      const ls = FTS_SETTINGS.loadLS();
      if (Object.keys(ls).length) FTS_SETTINGS.writeForm(ls);
      return;
    }
    FTS_SETTINGS.clearLS();
    FTS_SETTINGS.writeDefaults();
    FTS_SETTINGS.paintErrors({});
    setMsg('#38bdf8', '↺ پیش‌فرض‌هایِ جزوه در فرم نشسته شد…');
    try {
      const r = await fetch('/api/fts/config', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(FTS_SETTINGS.DEFAULTS)
      });
      const j = await r.json();
      if (j && j.status === 'success') {
        FTS_SETTINGS.writeForm(j.config);
        setMsg('#22c55e', '✓ همهٔ فیلدها به پیش‌فرضِ جزوه برگشت و اعمال شد');
        reapply();
      } else {
        setMsg('#ef4444', '✕ سرور پیش‌فرض‌ها را نپذیرفت — فرم محلی بازگشت');
      }
    } catch (e) {
      setMsg('#ef4444', '✕ خطای ارتباط — فرم محلی به پیش‌فرض برگشت، سرور دست‌نخورده');
    }
  };
})();

