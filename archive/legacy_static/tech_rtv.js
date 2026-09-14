
/* ============================================================
   تب تکنیکال — KLineChart v10 (مهاجرت از lightweight-charts)
   پالت v9.7.6 — تم تیره فین‌تک هماهنگ با پنل‌ها:
   bg #0d1117 | grid rgba(255,255,255,.04) | text #8b949e
   up #10b981 | down #f43f5e | محور زمان ۲۸px
   ابزارها: بایند مستقیم به KLineChart.createOverlay native
   ============================================================ */
'use strict';

/* ---------- پالت فین‌تک دارک (فینال — هماهنگ با CSS متغیرهای برنامه) ---------- */
var RTV_THEME = {
  grid: 'rgba(255,255,255,0.04)', text: '#8b949e', paneBg: '#0d1117',
  toolBg: '#161b22', up: '#10b981', down: '#f43f5e',
  font: 'IRANSansX, sans-serif'
};

var rv = {
  sym: null, data: [], itv: 'D', adj: 1, logScale: false,
  tool: null, chart: null, symCache: [], hintTimer: null,
  lastRendered: []
};

function rvEl(id) { return document.getElementById(id); }
function rvToast(msg) {
  var t = rvEl('rvTimeInfo');
  if (t) {
    t.textContent = msg;
    clearTimeout(rv.hintTimer);
    rv.hintTimer = setTimeout(function () { t.textContent = '—'; }, 6000);
    return;
  }
  /* fallback: پیام شناور کوتاه روی چارت (المنت rvTimeInfo وجود ندارد) */
  var f = rvEl('rvToastFloater');
  if (!f) {
    f = document.createElement('div');
    f.id = 'rvToastFloater';
    f.style.cssText = 'position:absolute;top:52px;right:16px;z-index:9999;background:#1c2333;color:#e5e9f2;border:1px solid #2c3548;border-radius:8px;padding:7px 14px;font-size:12.5px;font-family:Vazirmatn,sans-serif;box-shadow:0 6px 18px rgba(0,0,0,.35);opacity:0;transition:opacity .25s;pointer-events:none;white-space:nowrap;direction:rtl;';
    var box = rvEl('rvChartBox') || document.body;
    box.style.position = box.style.position || 'relative';
    box.appendChild(f);
  }
  f.textContent = msg;
  f.style.opacity = '1';
  clearTimeout(rv.hintTimer);
  rv.hintTimer = setTimeout(function () { f.style.opacity = '0'; }, 2500);
}

/* ---------- داده: /api/chart → KLineChart data ---------- */
async function rvFetch(sym) {

  const r = await fetch('/api/chart/' + encodeURIComponent(sym), { cache: 'no-store' });
  const j = await r.json();
  if (!j || !j.candles || !j.candles.length) return null;
  const c = j.candles.slice().reverse();           // صعودی
  const f = (j.factors || []).slice().reverse();   // هم‌راستا
  // حجم: از volumes (API جدا میدهد) → به کندل‌ها merge
  const volMap = new Map((j.volumes || []).map(v => [v.time, v.value]));
  c.forEach(k => { k.volume = volMap.get(k.time) || 0; });
  // v10.1 — payload کامل /api/chart خودش «fts» را دارد (try/except محافظت‌شده در
  // بک‌اند). نگه‌داشتنش یعنی نشان‌های FTS بی‌درنگ و بی‌یک درخواست اضافه، هم‌زمان
  // با خودِ کندل‌ها رندر می‌شوند؛ /api/fts بعداً فقط تازه‌سازی است.
  return { candles: c, factors: f, adjustEvents: j.adjustEvents || [], fts: j.fts || null };
}

/* ---------- واحد زمان (v8.7 FIX-3) ----------
   سند KLineChart v10 صریح است: «timestamp must be a millisecond timestamp».
   پیش از این اصلاح، سه واحد متفاوت قاطی شده بود: کندل‌ها میلی‌ثانیه، اما bucket
   هفتگی/ماهانه (خط ۹۶) و نقاط overlay (خط ۸۹۵) و formatter (خط ۱۶۲) ثانیه — که
   باعث می‌شد کندل‌های تجمیع‌شده بیرون دامنهٔ داده بیفتند و رسم‌های خودکار
   (سطوح/اوردربلاک) به جای غلطی قفل شوند.
   مبنای روز = «ظهر UTC» همان تاریخ: Date.UTC(y, m-1, d, 12). دلیل ظهر: آنگاه هم
   getUTCDate() و هم getDate() همان روز را برمی‌گردانند، پس آف‌بای‌وانِ تقویمی
   (برچسب محور یک روز عقب‌تر) حذف می‌شود و نتیجه به منطقهٔ زمانی سیستم بی‌ربط است. */
function rvDayTs(yyyy, mm, dd) { return Date.UTC(yyyy, mm - 1, dd, 12); }
function rvDateToTs(s) {                       // 'YYYY-MM-DD' → میلی‌ثانیه (ظهر UTC)
  const m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(String(s));
  if (!m) { const t = Date.parse(s); return isNaN(t) ? 0 : t; }
  return rvDayTs(+m[1], +m[2], +m[3]);
}

function rvToKLine(candles, factors, field) {
  // v9.7: «آخرین قیمت» و «قیمت پایانی» دو سری واقعاً متفاوت‌اند (بک‌اند ستون
  // <LAST> را از CSV تکمیل‌شده می‌آورد). field='last' → closeِ کندل، آخرین
  // معامله می‌شود؛ open/high/low همان‌ها می‌مانند (آخرین معامله همیشه داخل
  // بازهٔ روز است). بدون فیلدِ معتبر، احتیاطاً به پایانی برمی‌گردد.
  const useLast = (field === 'last');
  // time: 'YYYY-MM-DD' → timestamp میلی‌ثانیه (ظهر UTC) — توضیح بالا
  return candles.map((c, i) => {
    const fac = (factors && factors[i]) ? (factors[i].factor || 1) : 1;
    const cl = (useLast && c.last != null && c.last > 0) ? c.last : c.close;
    return {
      timestamp: rvDateToTs(c.time),
      open: c.open * fac, high: c.high * fac, low: c.low * fac, close: cl * fac,
      volume: c.volume || 0
    };
  });
}

/* ---------- تجمیع تایم‌فریم (مثل رهاورد): D/W/M با همان کندل‌های روزانه ---------- */
function rvAggregate(data, itv) {
  if (itv === 'D' || !data.length) return data;
  const buckets = new Map();
  for (const c of data) {
    const dt = new Date(c.timestamp);
    let key;
    if (itv === 'W') {
      // هفتهٔ بازار ایران: شنبه شروع می‌شود (JS: getUTCDay → 0=Sun..6=Sat؛ شنبه=0)
      const offset = (dt.getUTCDay() + 1) % 7;
      const base = new Date(dt);
      base.setUTCDate(dt.getUTCDate() - offset);
      key = base.toISOString().slice(0, 10);
    } else if (itv === 'M') {
      // ماه شمسی (ابتدا از جلالی)
      const y = dt.getUTCFullYear(), m = dt.getUTCMonth() + 1, d = dt.getUTCDate();
      const j = gregorianToJalaaliParts(y, m, d);
      const g0 = Jalaali.toGregorian(j.jy, j.jm, 1);
      key = g0.gy + '-' + String(g0.gm).padStart(2, '0') + '-01';
    } else {
      continue; // 'H' و غیره — فعلاً پشتیبانی نمی‌شود (بدون دادهٔ ساعتی)
    }
    if (!buckets.has(key)) {
      // v8.7 FIX-3: بدون «/ 1000» — واحد میلی‌ثانیه (ظهر UTC) مثل بقیهٔ دادهٔ چارت
      buckets.set(key, { timestamp: rvDateToTs(key), open: c.open, high: c.high, low: c.low, close: c.close, volume: c.volume || 0 });
    } else {
      const b = buckets.get(key);
      b.high = Math.max(b.high, c.high);
      b.low = Math.min(b.low, c.low);
      b.close = c.close;
      b.volume = (b.volume || 0) + (c.volume || 0);
    }
  }

  return [...buckets.values()].sort((a, b) => a.timestamp - b.timestamp);

}

/* ---------- استایل کامل (پالت رهاورد) ---------- */
function rvApplyStyles() {
  if (!rv.chart) return;
  rv.chart.setStyles({
    grid: {
      horizontal: { color: RTV_THEME.grid, style: 'solid' },
      vertical: { color: RTV_THEME.grid, style: 'solid' }
    },
    candle: {
      bar: { upColor: RTV_THEME.up, downColor: RTV_THEME.down,
             noChangeColor: '#888888', upBorderColor: RTV_THEME.up,
             downBorderColor: RTV_THEME.down, upWickColor: RTV_THEME.up,
             downWickColor: RTV_THEME.down },
      priceMark: { last: { upColor: RTV_THEME.up, downColor: RTV_THEME.down } },
      // FIX: tooltip بومی KLineChart (با {ticker} خام + OHLC زائد) باید بطور کامل
      // غیرفعال شود — ما legend سفارشی HTML داریم؛ showRule=always پیشفرض باعث
      // دوبلوچینی/overlap میشود. none = هیچ tooltip رسم نشود.
      tooltip: { showRule: 'none', showType: 'standard' }
    },
    indicator: { lastValueMark: { line: { color: RTV_THEME.text } } },
    xAxis: {
      axisLine: { color: RTV_THEME.grid }, tickLine: { color: RTV_THEME.grid },
      tickText: { color: RTV_THEME.text, family: RTV_THEME.font, size: 12 }
      /* v9.5: createTicks اینجا اثری نداشت (در v10 فقط از options محور خوانده
         می‌شود، نه styles) و «coord:0» همهٔ برچسب‌ها را روی x=0 می‌انباشت.
         برچسب شمسی از setFormatter.formatDate می‌آید و تراکم‌دهی درست در
         tech_365.js/btsThinTicks با overrideXAxis انجام می‌شود. */
    },
    yAxis: {
      axisLine: { color: RTV_THEME.grid }, tickLine: { color: RTV_THEME.grid },
      tickText: { color: RTV_THEME.text, family: RTV_THEME.font, size: 12 }
    },
    separator: { color: 'rgba(139,148,158,0.22)' },
    crosshair: {
      horizontal: { line: { color: '#8b949e', style: 'dashed', size: 1 } },
      vertical: { line: { color: '#8b949e', style: 'dashed', size: 1 } }
    }
  });
  // تاریخ شمسی روی محور X + tooltip (مثل رهاورد — ۱۴۰۵/.. )
  try {
    rv.chart.setFormatter({
      formatDate: function (p) {
        try {
          // v8.7 FIX-3: p.timestamp خودش میلی‌ثانیه است؛ «* 1000» تاریخ را به سال
          // ~۵۷٬۰۰۰ می‌برد. (این setFormatter روی نسخهٔ init پایین‌تر بازنویسی می‌کند
          //  پس مسیرِ فعال بود و تاریخ tooltip/محور را خراب می‌کرد.)
          const d = new Date(p && p.timestamp != null ? p.timestamp : 0);
          if (isNaN(d.getTime())) return '';
          const j = rvToJalaali(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
          return j.jy + '/' + String(j.jm).padStart(2, '0') + '/' + String(j.jd).padStart(2, '0');
        } catch (e) { return ''; }
      }
    });
  } catch (e) {}
}

function rvToJalaali(gy, gm, gd) {
  // کوچک: از Jalaali (jalaali-js) استفاده کن
  const j = Jalaali.toJalaali(gy, gm, gd);
  return { jy: j.jy, jm: j.jm, jd: j.jd };
}

/* ---------- برو به تاریخ (Go to date - مثل رهاورد) ---------- */
function rvGotoDate() {
  try {
    const raw = rvEl('rvGotoInput').value;
    if (!raw || !rv.data || !rv.data.length) return;
    let ts = null;
    if (/^[0-9]{4}$/.test(raw)) {
      ts = rv.data[0].timestamp;  // فقط سال → اول
    } else {
      // فرمت: YYYY-MM-DD میلادی یا 1400/3/31 شمسی
      if (raw.includes('/')) {
        const parts = raw.split('/').map(x => parseInt(x, 10));
        if (parts.length === 3 && parts[0] > 1300) {
          const g = Jalaali.toGregorian(parts[0], parts[1], parts[2]);
          ts = rvDateToTs(g.gy + '-' + String(g.gm).padStart(2, '0') + '-' + String(g.gd).padStart(2, '0'));
        }
      }
      if (ts === null) {
        // v8.7 FIX-3: میلی‌ثانیه — scrollToTimestamp هم ms می‌خواهد نه ثانیه
        const t2 = rvDateToTs(raw);
        if (t2) ts = t2;
      }
    }
    if (ts !== null) {
      rv.chart.scrollToTimestamp(ts);
      const j = rvToJalaali(new Date(ts).getUTCFullYear(), new Date(ts).getUTCMonth() + 1, new Date(ts).getUTCDate());
      rvToast('⏰ رفت به ' + j.jy + '/' + String(j.jm).padStart(2, '0') + '/' + String(j.jd).padStart(2, '0'));
    }
  } catch (e) { rvToast('برو به تاریخ: فرمت اشتباه'); }
}

/* ---------- تنظیمات مقیاس قیمت (مثل رهاورد — راست‌کلیک در TradingView) ---------- */
/* ---------- init: یکبار — بدون re-init (memory-safe) ----------
   v9.7.8 — کانتینر یکتای چارت = #rvChartBox (سطح بوم، #rvMainChart داخل همان باکس).
   همهٔ ارجاع‌های قدیمی #tvChartContainer حذف شده‌اند. اگر DOM باکس از ریشه
   بیرون رفته/جایگزین شده باشد، نسخهٔ قبلی چارت کامل .remove/destroy می‌شود
   و بعد چارت تازه ساخته می‌شود — هیچ‌وقت دو بوم روی هم نمی‌مانند (ضد نشت canvas). */
function rvDestroyChart() {
  var host = rv._host || rvEl('rvMainChart');
  try { if (host && window.klinecharts && klinecharts.dispose) klinecharts.dispose(host); } catch (e) {}
  rv.chart = null; rv._host = null; rv._dataLoaderRegistered = false;
  try {
    if (host) Array.prototype.forEach.call(host.children, function (n) {
      if (n.classList && n.classList.contains('klinecharts')) n.remove();   // حذف بوم نسخهٔ قبلی
    });
  } catch (e) {}
}
function rvSetupChart() {
  var box = rvEl('rvChartBox');
  var el = rvEl('rvMainChart');
  if (!el || (box && !box.contains(el))) { rvToast('⚠️ ظرف چارت (#rvChartBox) آماده نیست'); return; }
  if (rv.chart) {
    if (rv._host !== el || !document.body.contains(el)) rvDestroyChart();   // میزبان بیرون‌رفته → اول حذف، بعد ساخت
    else { try { rv.chart.resize(); } catch (e) {} return; }
  } else {
    // چارتی در حافظه نیست ولی میزبان آثار ساخت قبلی دارد → جاروب پیش از init
    try { if (window.klinecharts && klinecharts.dispose) klinecharts.dispose(el); } catch (e) {}
    try { Array.prototype.forEach.call(el.children, function (n) { if (n.classList && n.classList.contains('klinecharts')) n.remove(); }); } catch (e) {}
  }
  // ثبت locale فارسی (KLineChart پیش‌فرض فقط zh-CN/en-US دارد؛ بدون ثبت → tooltip کرش)
  try {
    klinecharts.registerLocale('fa-IR', {
      time: 'زمان: ', open: 'باز شدن: ', high: 'بیشترین: ', low: 'کمترین: ',
      close: 'بسته شدن: ', volume: 'حجم: ', turnover: 'بورس: ', change: 'تغییر: ',
      second: 'ثانیه', minute: 'دقیقه', hour: 'ساعت', day: 'روز',
      week: 'هفته', month: 'ماه', year: 'سال',
      explain: 'توضیح', override: 'جایگزینی', lock: 'قفل',
      unlock: 'باز کردن', lockAll: 'قفل همه', unlockAll: 'باز کردن همه',
      goto: 'رفتن', remove: 'حذف', removeAll: 'حذف همه', erase: 'پاک کردن', eraseAll: 'پاک کردن همه'
    });
  } catch (e) {}
  rv.chart = klinecharts.init(el, {
    locale: 'fa-IR',
    timezone: 'Asia/Tehran',
    // تاریخ شمسی: formatter.formatDate (API این نسخه — شیءای)
    formatter: {
      formatDate: function (o) {
        try {
          var ts = o && (o.timestamp != null ? o.timestamp : o.dateTime);
          var dt = new Date(ts);
          var j = rvToJalaali(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
          var tpl = (o && o.template) || '';
          if (tpl.indexOf('YYYY-MM-DD') === 0) return j.jy + '/' + String(j.jm).padStart(2, '0') + '/' + String(j.jd).padStart(2, '0');
          if (tpl.indexOf('YYYY-MM') === 0) return j.jy + '/' + String(j.jm).padStart(2, '0');
          if (tpl.indexOf('YYYY') === 0) return String(j.jy);
          return j.jy + '/' + String(j.jm).padStart(2, '0') + '/' + String(j.jd).padStart(2, '0');
        } catch (e) { try { return new Date(o.timestamp).toISOString().slice(0, 10); } catch (e2) { return ''; } }
      }
    },
    // فاز ۱ — مگنیت: نقاط رسم به High/Low/Close نزدیکترین کندل میچسبند (بدون drift پیکسلی)
    // aabb دقت را بیشتر میکند؛ customApi کامل نزنیم — پیشفرض کافی است
  });
  rv._host = el;   // اتصال نمونه به میزبان فعلی — مبنای تشخیص میزبان بی‌اعتبار در ساخت مجدد
  // v8.9-B2 — گارد دابل‌کلیک: روی ظرف چارت در فاز capture نصب می‌شود تا پیش از
  // هندلر bubble خودِ klinecharts روی المان داخلی اجرا شود (رج: rvInstallDblGuard)
  try { rvInstallDblGuard(el); } catch (e) {}
  try { rv.chart.setStyles({ candle: { tooltip: { showRule: 'none' } } }); } catch (e) {}
  try {
    /* مگنیت در v10 ویژگیِ crosshair نیست؛ روی خودِ overlay می‌نشیند
       (mode: 'normal' | 'weak_magnet'). کلید 'strong_magnet' در باندل وجود
       ندارد و setStyles({crosshair:{mode}}) بی‌صدا دور ریخته می‌شد.
       تنها راه مؤثر: تزریق mode هنگام ساخت overlay. */
    var _oc = rv.chart.createOverlay.bind(rv.chart);
    rv.chart.createOverlay = function (opt) {
      if (opt && typeof opt === 'object' && !Array.isArray(opt) && !opt.mode) {
        var want = (typeof btsSet !== 'undefined' && btsSet && btsSet.canvas)
          ? (btsSet.canvas.crosshair === 'magnet' ? 'weak_magnet' : 'normal')
          : 'weak_magnet';
        opt = Object.assign({}, opt, { mode: want });
      }
      return _oc(opt);
    };
  } catch (e) {}
  try {
    // فاز ۳ — انتخاب overlay: id را ذخیره کن (برای Delete/Backspace)
    rv.chart.setOverlayOptions && rv.chart.setOverlayOptions({});
  } catch (e) {}
  try {
    // v10: رویداد انتخاب از way of bindEvent — از chart.dom روی click resolve میکنیم
    rvBindDeleteKey();
  } catch (e) {}
  rvApplyStyles();
  // v7.3.11 — کلیک روی رسم → popup همان
  try {
    rv.chart.subscribeAction('onSelected', function (param) {
      var o = param && (param.overlay || param.instance);
      var id = o && o.id;
      if (id) rvShowDrawFloat(id);
    });
    // v8.5 — مثل نهایت‌نگر: بعد از اتمام هر رسم، قرص تنظیمات بالا-وسط ظاهر شود
    rv.chart.subscribeAction('onDrawEnd', function (param) {
      var o = param && (param.overlay || param.instance);
      if (o && o.id) rvShowDrawFloat(o.id);
    });
  } catch (e) {}
  /* v9.7.6 — اسکرول چرخ‌ماوس نرخ‌محدود (ضد فریز) +ResizeObserver (رفع «بی‌داده»
     ورود اول از تب مخفی: کانتینر تازه اندازه می‌گیرد و چارت reflow می‌شود) */
  try { rvInstallWheelZoom(el); } catch (e) {}
  try { rvAttachResize(el, box); } catch (e) {}

}

function rvRegisterDataLoader() {
  if (!rv.chart) return;
  // فاز ۲ — جلوگیری از double-register (لک حافظه/رفتار عجیب در سوئیچ نماد):
  if (rv._dataLoaderRegistered) {
    // نماد/داده عوض شده → فقط newData push کن (dataLoader getBars از rv.data میخواند)
    try { rv.chart.resetData(); } catch (e) {}
    return;
  }
  // KLineChart v10 قرارداد: getBars + subscribeBar (نه requestData)
  // مهم: _processDataLoad فقط وقتی symbol/period set شدهاند فراخوانی میشود
  // و tooltip از dataLoader.period میخواند → باید دقیقاً پر باشد
  // period.type باید یکی از کلیدهای dateFormat باشد (second/minute/hour/day/week/month/year)
  // '日線' در Le تعریف نشده → tooltip کرش میدهد
  var periodObj = { type: 'day', text: 'Day' };
  rv.chart.setDataLoader({
    symbol: { type: '普通', title: rv.sym || 'بورش‌اجنت' },
    period: periodObj,
    getBars: function (p) {
      try { p.callback(rv.data || []); } catch (e) {}
    },
    subscribeBar: function (p) {},
    unsubscribeBar: function () {}
  });
  rv.chart.setSymbol({ type: '普通', title: rv.sym || 'بورش‌اجنت' });
  try {
    rv.chart.setPeriod(periodObj);
  } catch (e) {}
  rv._dataLoaderRegistered = true;
}

/* ---------- بازترسیم از دادهٔ خام (بی‌واکشی شبکه) ----------
   rv._rawC / rv._rawF همیشه OHLC خام را نگه می‌دارند. هر بار که فقط
   «نمایش» عوض می‌شود (تعدیل، تایم‌فریم، نوع قیمت) سری از روی همان دادهٔ
   خام ساخته می‌شود، پس هیچ‌وقت ضریبی دو بار روی هم اعمال نمی‌گردد.
   قبلاً برای هر تغییر، rvLoad دوباره fetch می‌کرد و مسیر نوع قیمت
   ناخواسته rv.adj را هم عوض می‌کرد. */
function rvBuildSeries() {
  if (!rv._rawC || !rv._rawC.length) return false;
  /* v9.7: نوع قیمت مشخص می‌کند کدام فیلد قیمت روی «close» کندل بنشیند.
     این تنها تغییرِ «سری» است و هیچ ربطی به rv.adj (تعدیل) ندارد. */
  const fld = (typeof btsPriceField === 'function') ? btsPriceField() : 'close';
  rv._seriesField = fld;
  const daily = rvToKLine(rv._rawC, rv.adj ? rv._rawF : null, fld);
  let data = rvAggregate(daily, rv.itv);        // D/W/M (مثل رهاورد)
  const f = (typeof btsActiveFactor === 'function') ? btsActiveFactor() : 1;
  if (f && f !== 1) {
    data = data.map(c => ({
      timestamp: c.timestamp, volume: c.volume,
      open: c.open * f, high: c.high * f, low: c.low * f, close: c.close * f
    }));
  }
  rv.data = data;
  return true;
}

/* فقط سری فعال را دوباره به چارت بده. وضعیت تعدیل دست نمی‌خورد.
   اگر دادهٔ خامی نبود false برمی‌گرداند تا فراخواننده به rvLoad برگردد. */
function rvRerender() {
  if (!rvBuildSeries()) return false;
  if (!rv.chart) return false;
  /* ترتیب دقیقاً همان مسیرِ آزموده‌شدهٔ rvLoad است: اول پاک‌سازی صریح
     رسم‌ها، بعد ری‌فید داده، بعد بازگرداندن شکل‌های ذخیره‌شده و سطوح
     خودکار. پاک‌سازیِ اول لازم است چون rvRestoreOverlays خودش حذف
     نمی‌کند و بدون آن رسم‌ها دو‌تا می‌شدند. */
  try { rv.chart.removeOverlay(); rvOverlays = []; } catch (e) {}
  try { rv.chart.resetData(); } catch (e) {}
  rvRestoreOverlays();
  try { rvApplyAutoLevels(); } catch (e) {}
  /* v9.7.6 — removeOverlay() مارکرهای رویداد را هم پاک می‌کند؛ از لیستِ در
     حافظه بازساخته می‌شوند (بدون fetch دوباره). بدون این خط، هر تغییر
     تعدیل/نوع قیمت رویدادهای چارت را برای همیشه می‌برد. */
  try { rvApplyEventMarks(); } catch (e) {}
  try { rvUpdateLegend(); } catch (e) {}
  try { rvMaLegendSync(); } catch (e) {}   // v10.1 — چیپ‌های MA با داده‌ی تازه
  return true;
}


async function rvLoad(sym) {
  const d = await rvFetch(sym);
  if (!d) { rvToast('⚠️ داده برای ' + sym + ' موجود نیست'); try { rvCalPending = null; } catch (e) {} return; }
  rv.sym = sym;
  // فاز ۲: سوئیچ نماد — رسمهای نماد قبلی پاک شوند (ghost drawings نمیمانند)
  try {
    if (rv.chart) { rv.chart.removeOverlay(); rvOverlays = []; }
  } catch (e) {}
  rv._rawC = d.candles; rv._rawF = d.factors || [];   // خام و بی‌ضریب — مبنای بازترسیم
  rvBuildSeries();                                     // تعدیل + تجمیع + نوع قیمت
  const inSym = rvEl('rvSymInput');
  if (inSym) inSym.value = sym;
  const symEl = rvEl('rvChtSym');
  if (symEl) symEl.innerHTML = 'بورش‌اجنت 365 | ' + sym;
  rvUpdateLegend();   // OHLC + حجم (بالای چارت)
  // داده آماده است → چارت را init و dataLoader را ثبت کن (هر دو بعد از data)
  rvSetupChart();
  rvApplyTheme();
  rvRegisterDataLoader();
  rvRestoreOverlays();
  rvAttachPopupAll();
  rvApplyAutoLevels();   // سطوح کلیدی خودکار (وقتی تیک فعال است)
  try {
    if (!rv.chart.getIndicators({ name: 'VOL' }).length) rv.chart.createIndicator({ name: 'VOL', id: 'ind_VOL', isStack: false, calcParams: [21] });
    /* v10.1 — MA استاندارد FTS روی پن کندل: ۱۴ = تریلینگ استاپ لایه‌۱، ۵۲/۱۰۰ = مرجع‌های روند. createIndicator در klinecharts 10 فقط دو آرگومان دارد و paneId از خود آبجکت خوانده می‌شود؛ رنگ‌ها با تم چارت در rvApplyTheme هم‌آهنگ می‌شوند. */
    try {
      if (!rv.chart.getIndicators({ name: 'MA' }).length) {
        rv.chart.createIndicator({
          name: 'MA', id: 'ind_MA', paneId: 'candle_pane', calcParams: [14, 52, 100],
          styles: {
            lines: [
              { color: '#38bdf8', size: 1, style: 'solid' },
              { color: '#f59e0b', size: 1, style: 'solid' },
              { color: '#a78bfa', size: 1, style: 'solid' }
            ],
            tooltip: { showRule: 'none' }
          }
        }, true);
      }
    } catch (e) {}
    rvApplyEventMarks();   // v9.7.6 — رویدادهای تقویم روی چارت (📅) از /api/ma
    rvIndSyncParams();   // v9.7.2 — دورهٔ اندیکاتورهای فعال با تایم‌فریم تازه همگام شود
    rv.chart.setBarSpace(5); rv.chart.scrollToRealTime();
    /* v9.7.6 — «برو به تاریخ» که از تب تقویم درخواست شده، بعد از اسکرول
       پیش‌فرضِ انتها مصرف می‌شود (وگرنه scrollToRealTime بر آن غالب می‌شد). */
    try { rvCalConsumePending(); } catch (e) {}
  } catch (e) {}
  rvEl('rvChtScale').textContent = 'مقیاس: ' + (rv.itv === 'D' ? '1D' : rv.itv === 'W' ? '1W' : '1M');
  rvEl('rvChtTf').textContent = 'تایم فریم: ' + (rv.itv === 'D' ? 'روزانه' : rv.itv === 'W' ? 'هفتگی' : 'ماهانه');
  rvToast('✓ ' + sym);
  try { rvFtsEnsureDom(); rvMaLegendSync(); rvFtsLoad(sym, d.fts); } catch (e) {}   // v10 FTS badges + v10.1 چیپ‌ها/fts سریع
}

/* ---------- ابزارها: بایند مستقیم به createOverlay (native) ---------- */
function rvToolMenu(id, btn) {
  const d = rvEl('tvdrop_' + id);
  if (!d) return;
  // بستن بقیه
  document.querySelectorAll('.tv-drop').forEach(x => { if (x !== d) x.style.display = 'none'; });
  d.style.display = (d.style.display === 'flex') ? 'none' : 'flex';
  if (btn) {
    const r = btn.getBoundingClientRect();
    const tb = btn.closest('.draw-toolbar');
    if (tb) {
      const tbR = tb.getBoundingClientRect();
      d.style.top = (r.top - tbR.top) + 'px';
      d.style.left = (r.right - tbR.left + 4) + 'px';
    }
  }
}
function rvZoom(scale) {
  try {
    if (!rv.chart) return;
    rv.chart.zoomAtCoordinate(scale);
  } catch (e) {}
}
function rvMagnet(btn) {
  const on = btn && btn.classList.contains('rv-on');
  if (btn) btn.classList.toggle('rv-on', !on);
  rvToast(!on ? '🧲 مغناطیس: روشن (رسمها به نقاط میچسبند)' : '🧲 مغناطیس: خاموش');
}
function rvStayDraw(btn) {
  const on = btn && btn.classList.contains('rv-on');
  if (btn) btn.classList.toggle('rv-on', !on);
  rv.toastStay = !on;
  rvToast(!on ? '📌 حالت رسم ماندگار: روشن' : '📌 حالت رسم ماندگار: خاموش');
}
function rvObjectTree() {
  try {
    const overs = rv.chart ? rv.chart.getOverlays() : [];
    if (!overs.length) { rvToast('هیچ رسمی روی چارت نیست'); return; }
    rvToast('Object Tree: ' + overs.length + ' object — ' +
            overs.slice(0, 4).map(o => o.name).join(', ') +
            (overs.length > 4 ? ' و...' : ''));
  } catch (e) {}
}
/* =====================================================================
   v8.9 — مدلِ واحدِ سطوح فیبوناچی
   ---------------------------------------------------------------------
   قبلاً سطوح به‌صورتِ دو نقشهٔ متنیِ کلید-به-درصد (`styles.levels` /
   `styles.levelColors` با کلیدهایی مثل '78.6') و یک آرایهٔ ثابتِ ۷تایی
   داخلِ خودِ رندرر ذخیره می‌شدند. آن مدل «ضریبِ دلخواه» و «ترتیب» را
   نمی‌پذیرفت و پنجرهٔ تنظیمات هم فقط چک‌باکس متنی داشت.
   مدلِ جدید یک آرایهٔ مرتب است:
        styles.fibLevels = [{ coeff: 0.618, color: '#089981', visible: true }, …]
   و بقیهٔ تنظیمات روی خودِ overlay می‌نشینند:
        extendLeft / extendRight / reverse / fills / bgOpacity /
        showPrices / showPercents / pctMode / oneColor / oneColorValue /
        trend / levelLine{size,style}
   مسیرِ قدیمی (styles.levels) هنوز خوانده می‌شود تا رسم‌های ذخیره‌شدهٔ
   نسخه‌های قبل دقیقاً مثل قبل رندر شوند.
   ===================================================================== */

/* ۲۳ سطحِ پیش‌فرض — همان فهرستِ پنجرهٔ نهایت‌نگر/TradingView */
var FIB_DEFAULT_LEVELS = [
  { coeff: 0,     color: '#787B86', visible: true },
  { coeff: 0.236, color: '#F23645', visible: true },
  { coeff: 0.382, color: '#81c784', visible: true },
  { coeff: 0.5,   color: '#4caf50', visible: true },
  { coeff: 0.618, color: '#089981', visible: true },
  { coeff: 0.786, color: '#64b5f6', visible: true },
  { coeff: 1,     color: '#787B86', visible: true },
  { coeff: 1.272, color: '#2962FF', visible: false },
  { coeff: 1.414, color: '#F23645', visible: false },
  { coeff: 1.618, color: '#2962FF', visible: false },
  { coeff: 2,     color: '#9c27b0', visible: false },
  { coeff: 2.272, color: '#00BCD4', visible: false },
  { coeff: 2.414, color: '#FF9800', visible: false },
  { coeff: 2.618, color: '#F23645', visible: false },
  { coeff: 3,     color: '#787B86', visible: false },
  { coeff: 3.272, color: '#2962FF', visible: false },
  { coeff: 3.414, color: '#81c784', visible: false },
  { coeff: 3.618, color: '#9c27b0', visible: false },
  { coeff: 4,     color: '#64b5f6', visible: false },
  { coeff: 4.236, color: '#F23645', visible: false },
  { coeff: 4.414, color: '#00BCD4', visible: false },
  { coeff: 4.618, color: '#FF9800', visible: false },
  { coeff: 4.764, color: '#4caf50', visible: false }
];
window.FIB_DEFAULT_LEVELS = FIB_DEFAULT_LEVELS;

/* کلیدِ قدیمیِ درصدی ('100'، '78.6'، '0') و عددِ ضریب (0.786) هر دو پذیرفته
   می‌شوند تا فراخوان‌های موجود نشکنند. */
var RV_DIGIT_MAP = { '۰': 0, '۱': 1, '۲': 2, '۳': 3, '۴': 4, '۵': 5, '۶': 6, '۷': 7, '۸': 8, '۹': 9,
  '٠': 0, '١': 1, '٢': 2, '٣': 3, '٤': 4, '٥': 5, '٦': 6, '٧': 7, '٨': 8, '٩': 9 };
/* ارقامِ فارسی/عربی و ممیزِ «٫» به ارقامِ لاتین تبدیل می‌شوند؛ رابط کاربری راست‌به‌چپ است */
function _rvFibLatin(s) {
  return String(s).replace(/[۰-۹٠-٩]/g, function (ch) { return String(RV_DIGIT_MAP[ch]); })
                  .replace(/[٫٬]/g, '.');
}
function _rvFibNumStr(s) {
  var raw = _rvFibLatin(s).replace(/[^0-9.\-]/g, '');
  /* ورودیِ ناقصِ حینِ تایپ («»، «.»، «۰.»، «-») عدد نیست؛ NaN بدهد تا مقدارِ قبلی بماند */
  if (!raw || raw === '.' || raw === '-' || raw.charAt(raw.length - 1) === '.') return null;
  if ((raw.match(/\./g) || []).length > 1) return null;
  return raw;
}
function _rvFibKeyToCoeff(k) {
  if (typeof k === 'number') return isFinite(k) ? Math.round(k * 1e6) / 1e6 : NaN;
  var raw = _rvFibNumStr(k);
  if (raw === null) return NaN;
  var n = parseFloat(raw);
  if (!isFinite(n)) return NaN;
  if (n > 4) n = n / 100;               /* کلیدِ درصدیِ قدیمی ('61.8' → 0.618، '100' → 1) */
  return Math.round(n * 1e6) / 1e6;
}
window._rvFibKeyToCoeff = _rvFibKeyToCoeff;
/* ورودیِ متنیِ گریدِ دیالوگ همیشه «ضریب» خالص است: 0.618 → 0.618 و 5 → 5.
   بدونِ حدسِ درصدی، چون ستونِ ضریب همان چیزی را نشان می‌دهد که کشیده می‌شود. */
function _rvFibParseCoeff(s) {
  if (typeof s === 'number') return isFinite(s) ? Math.round(s * 1e6) / 1e6 : NaN;
  var raw = _rvFibNumStr(s);
  if (raw === null) return NaN;
  var n = parseFloat(raw);
  return isFinite(n) ? Math.round(n * 1e6) / 1e6 : NaN;
}
window._rvFibParseCoeff = _rvFibParseCoeff;

function _rvFibSame(a, b) { return Math.abs(a - b) < 1e-9; }

function _rvFibColorOf(coeff) {
  for (var i = 0; i < FIB_DEFAULT_LEVELS.length; i++)
    if (_rvFibSame(FIB_DEFAULT_LEVELS[i].coeff, coeff)) return FIB_DEFAULT_LEVELS[i].color;
  return '#787B86';
}

/* #rgb / #rrggbb / rgb() / rgba() → rgba() با آلفایِ دلخواه (نوارِ پس‌زمینه) */
function _rvRgba(col, alpha) {
  var a = Math.max(0, Math.min(1, isFinite(alpha) ? alpha : 0.1));
  var s = String(col || '').trim(), m;
  m = /^#?([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(s);
  if (m) {
    var h = m[1];
    if (h.length === 3) h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
    return 'rgba(' + parseInt(h.substr(0, 2), 16) + ',' + parseInt(h.substr(2, 2), 16) + ',' +
      parseInt(h.substr(4, 2), 16) + ',' + a + ')';
  }
  m = /rgba?\(([^)]+)\)/i.exec(s);
  if (m) {
    var p = m[1].split(',');
    if (p.length >= 3) return 'rgba(' + p[0].trim() + ',' + p[1].trim() + ',' + p[2].trim() + ',' + a + ')';
  }
  return 'rgba(120,123,134,' + a + ')';
}
window._rvRgba = _rvRgba;

/* خواندنِ آرایهٔ سطوح از هر دو نسلِ مدل؛ null یعنی «هیچ داده‌ای ذخیره نشده» */
function _rvFibReadRaw(st) {
  st = st || {};
  var out = [], i;
  if (Array.isArray(st.fibLevels) && st.fibLevels.length) {
    for (i = 0; i < st.fibLevels.length; i++) {
      var L = st.fibLevels[i];
      var c = (typeof L === 'number') ? L : _rvFibKeyToCoeff(L && L.coeff);
      if (!isFinite(c)) continue;
      out.push({ coeff: c, color: (L && L.color) || null, visible: !(L && L.visible === false) });
    }
    return out;
  }
  if (st.levels && typeof st.levels === 'object' && !Array.isArray(st.levels) && Object.keys(st.levels).length) {
    Object.keys(st.levels).forEach(function (k) {
      var cc = _rvFibKeyToCoeff(k);
      if (!isFinite(cc)) return;
      out.push({
        coeff: cc,
        color: (st.levelColors && st.levelColors[k]) || _rvFibColorOf(cc),
        visible: st.levels[k] !== false
      });
    });
    return out;
  }
  return null;
}

/* آرایهٔ «موثر» برایِ رندر — همان چیزی که روی چارت کشیده می‌شود */
function rvFibNormalizeLevels(st) {
  var raw = _rvFibReadRaw(st);
  if (raw) return raw;
  return FIB_DEFAULT_LEVELS.map(function (D) { return { coeff: D.coeff, color: D.color, visible: D.visible }; });
}
window.rvFibNormalizeLevels = rvFibNormalizeLevels;

/* آرایهٔ کاملِ گریدِ دیالوگ: همیشه ۲۳ ردیفِ پیش‌فرض + هر ضریبِ سفارشیِ خارج
   از فهرست. وضعیتِ دیدنی/رنگِ کاربر روی ردیفِ هم‌ضریب می‌نشیند. */
function rvFibMergeLevels(st) {
  var raw = _rvFibReadRaw(st) || [];
  var out = FIB_DEFAULT_LEVELS.map(function (D) {
    for (var i = 0; i < raw.length; i++)
      if (_rvFibSame(raw[i].coeff, D.coeff))
        return { coeff: D.coeff, color: raw[i].color || D.color, visible: raw[i].visible };
    return { coeff: D.coeff, color: D.color, visible: D.visible };
  });
  raw.forEach(function (R) {
    var known = false;
    for (var i = 0; i < FIB_DEFAULT_LEVELS.length; i++) if (_rvFibSame(FIB_DEFAULT_LEVELS[i].coeff, R.coeff)) known = true;
    if (!known) out.push({ coeff: R.coeff, color: R.color || _rvFibColorOf(R.coeff), visible: R.visible });
  });
  return out;
}
window.rvFibMergeLevels = rvFibMergeLevels;

/* برچسبِ هر سطح: «0.618» یا «61.8» — همان منوی «درصدها»ی پنجرهٔ مرجع */
function rvFibLevelLabel(L, pctMode) {
  if (pctMode === 'percent') return String(Math.round(L.coeff * 1000) / 10);
  return String(L.coeff);
}
window.rvFibLevelLabel = rvFibLevelLabel;


/* ---------- Hybrid: custom overlays (KLineChart registerOverlay — v10 API) ---------- */
// v7.4-fix2 — شرط قبلی (!includes('rect')) چون rect overlay بومی نیست همیشه true بود؛ حالا بدون شرط (re-register = override)
try {
  if (window.klinecharts) {
    window.klinecharts.registerOverlay({
      name: 'rect', totalStep: 3, lock: true,   // v8.8-FIX-5 — دو‌نقطه‌ای = totalStep 3 (قاعدهٔ کتابخانه: segment=3، priceLine=2). با 2 بعد از اولین کلیک complete می‌شد و coordinates[1] هرگز نمی‌رسید
      createPointFigures: function (e) {
        if (e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        var x = Math.min(a.x, b.x), y = Math.min(a.y, b.y);
        var w = Math.abs(b.x - a.x), h = Math.abs(b.y - a.y);
        return [{ type: 'rect', attrs: { x: x, y: y, width: w, height: h },
                  styles: { style: 'fill', color: 'rgba(41,98,255,0.15)', borderColor: '#2962ff', borderSize: 1 } }];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'ellipse', totalStep: 3, lock: true,   // v8.8-FIX-5 — دو‌نقطه‌ای
      createPointFigures: function (e) {
        if (e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        return [{ type: 'arc', attrs: { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2, r: Math.max(1, Math.abs(b.x - a.x) / 2), r2: Math.max(1, Math.abs(b.y - a.y) / 2), startAngle: 0, endAngle: Math.PI * 2 }, styles: { style: 'fill', color: 'rgba(41,98,255,0.18)', borderColor: '#2962ff', borderSize: 1 } }];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'triangle', totalStep: 3, lock: true,   // v8.8-FIX-5 — دو‌نقطه‌ای
      createPointFigures: function (e) {
        if (e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        return [{ type: 'polygon', attrs: { points: [{ x: a.x, y: b.y }, { x: b.x, y: b.y }, { x: (a.x + b.x) / 2, y: a.y }] }, styles: { style: 'fill', color: 'rgba(41,98,255,0.18)', borderColor: '#2962ff', borderSize: 1 } }];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'fib-extension', totalStep: 4, lock: true,
      createPointFigures: function (e) {
        // v7.4-fix2 — قیمت از overlay.points؛ نگاشت price→pixel با slope واقعی
        var coords = e.coordinates;
        var pts = (e.overlay && e.overlay.points) || [];
        if (!coords || coords.length < 2 || pts.length < 2) return [];
        var figs = [];
        var a = coords[0], b = coords[1], c = coords[2] || b;
        var pa = pts[0].value, pb = pts[1].value, pc = (pts[2] || pts[1]).value;
        var slope = (pb - pa) !== 0 ? (b.y - a.y) / (pb - pa) : 0;
        var yOf = function (v) { return a.y + (v - pa) * slope; };
        var x1 = Math.min(a.x, c.x), x2 = Math.max(a.x, c.x);
        var span = x2 - x1, xEnd = x2 + span * 0.15;
        [[0.382, '0.382'], [0.618, '0.618'], [1, '1'], [1.618, '1.618'], [2.618, '2.618']].forEach(function (lv) {
          // v8.8-FIX-1 — فرمول استاندارد: C + (B - A) * k
          // (فرمول قبلی pb + (pc - pb) * k بازهٔ B→C را ری‌تریس می‌کرد، یعنی تصویرِ وارونه؛
          //  با window.DrawingMath.fibExtension که خودش C+(B-A)*k است هم نمی‌خواند)
          var v = pc + (pb - pa) * lv[0];
          var y = yOf(v);
          figs.push({ type: 'line', attrs: { coordinates: [{ x: x1, y: y }, { x: xEnd, y: y }] }, styles: { color: '#787B86', size: 1, style: 'dashed', dashedValue: [4, 3] } });
          figs.push({ type: 'text', attrs: { x: x1 + 4, y: y - 3, text: lv[1] + '(' + v.toFixed(2) + ')', align: 'left', baseline: 'bottom' }, styles: { style: 'fill', color: '#787B86', size: 10, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } });
        });
        figs.push({ type: 'line', attrs: { coordinates: [a, b] }, styles: { color: '#2d8cf0', size: 1, style: 'solid' } });
        figs.push({ type: 'line', attrs: { coordinates: [b, c] }, styles: { color: '#2d8cf0', size: 1, style: 'dashed', dashedValue: [4, 3] } });
        return figs;
      }
    });
    window.klinecharts.registerOverlay({
      name: 'pitchfork', totalStep: 4, lock: true,
      createPointFigures: function (e) {
        if (e.coordinates.length < 3) return [];
        var p = e.coordinates[0], r = e.coordinates[1], s = e.coordinates[2];
        var midRS = { x: (r.x + s.x) / 2, y: (r.y + s.y) / 2 };
        // v8.8-FIX-4a — پچ‌فورک کلاسیک = دقیقاً سه خط موازی (میانه + دو ریل از R و S).
        // دو پرهٔ اضافی P→R و P→S حذف شدند: TV آن‌ها را نمی‌کشد و باعث می‌شدند
        // این ابزار با هیچ واریانت دیگری (andrews/schiff/inside) قابل‌تمایز نباشد.
        var dx = midRS.x - p.x, dy = midRS.y - p.y;
        if (dx === 0 && dy === 0) return [];   // سه نقطهٔ هم‌مکان → هندسه نامعین
        var ext = 1.6, back = 0.25;
        function ray(q, size) {
          return { type: 'line',
                   attrs: { coordinates: [
                     { x: q.x - dx * back, y: q.y - dy * back },
                     { x: q.x + dx * ext,  y: q.y + dy * ext } ] },
                   styles: { line: { color: '#2962ff', size: size } } };
        }
        return [ray(p, 1.5), ray(r, 1), ray(s, 1)];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'ruler', totalStep: 3, lock: true,
      createPointFigures: function (e) {
        if (!e.coordinates || e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        // v7.4-fix2 — قیمت از overlay.points؛ fallback پیکسی حذف شد (مقیاس غلط میداد)
        var pts = (e.overlay && e.overlay.points) || [];
        var pa = pts.length > 0 ? pts[0].value : 0;
        var pb = pts.length > 1 ? pts[1].value : 0;
        var dh = Math.round(pb - pa), dp = pa ? ((pb / pa - 1) * 100).toFixed(1) : '';
        var txt = dh + ' (' + dp + '%)';
        return [{ type: 'rect', attrs: { x: Math.min(a.x,b.x), y: Math.min(a.y,b.y), width: Math.abs(b.x-a.x), height: Math.abs(b.y-a.y) },
                  styles: { style: 'stroke', stroke: '#f59e0b', color: 'rgba(245,158,11,0.08)', borderColor: '#f59e0b', borderSize: 1, borderStyle: 'dashed' } },
                { type: 'text', attrs: { x: (a.x+b.x)/2, y: Math.min(a.y,b.y) - 14, text: txt },
                  styles: { style: 'fill', color: '#f59e0b', size: 11, family: 'Vazirmatn, sans-serif', weight: 700 } }];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'box', totalStep: 3, lock: true,
      createPointFigures: function (e) {
        if (e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        return [{ type: 'rect', attrs: { x: Math.min(a.x,b.x), y: Math.min(a.y,b.y), width: Math.abs(b.x-a.x), height: Math.abs(b.y-a.y) }, styles: { style: 'fill', color: 'rgba(41,98,255,0.08)', borderColor: '#2962ff', borderSize: 1, borderStyle: 'dashed' } }];
      }
    });
    window.klinecharts.registerOverlay({
      name: 'arrow', totalStep: 3, lock: true,   // v8.8-FIX-5 — دو‌نقطه‌ای
      createPointFigures: function (e) {
        if (e.coordinates.length < 2) return [];
        var a = e.coordinates[0], b = e.coordinates[1];
        return [{ type: 'line', attrs: { coordinates: [{ x: a.x, y: a.y }, { x: b.x, y: b.y }] }, styles: { line: { color: '#2962ff', size: 2 } } },
                { type: 'tick', attrs: { x: b.x, y: b.y, direction: a.x > b.x ? 'left' : 'right' }, styles: { style: { color: '#2962ff', size: 8 } } }];
      }
    });
    // === fibonacciLine TV-style: سطوح + برچسب قیمت/٪ + امتداد چپ/راست + معکوس ===
    // v7.4-fix2: v10 event فیلد points ندارد → قیمت از overlay.points
    // (باگ قبلی: e.points undefined → return [] بیصدا → فیبو هیچوقت رندر نمیشد)
    // v8.9 — بازنویسی کامل: سطوح از آرایهٔ styles.fibLevels (ضریب دلخواه + رنگ
    // اختصاصی + دیدنی)، به‌علاوهٔ extendLeft/extendRight/reverse/bgOpacity/
    // showPrices/showPercents/pctMode/oneColor/trend. بدون این فیلدها خروجی
    // دقیقاً مثل نسخهٔ قبل است (۷ سطح، همان هندسه، همان فرمت برچسب).
    window.klinecharts.registerOverlay({
      name: 'fibonacciLine', totalStep: 3, needDefaultPointFigure: true,
      createPointFigures: function (e) {
        var coords = e.coordinates;
        var pts = (e.overlay && e.overlay.points) || [];
        if (!coords || coords.length < 2 || pts.length < 2) return [];
        var A = coords[0], B = coords[1];
        var vA = pts[0].value, vB = pts[1].value;
        var st = (e.overlay && e.overlay.styles) || {};
        var lineSt = st.line || {};
        var lvSt = st.levelLine || {};
        var color = lineSt.color || '#2d8cf0';
        var size = lineSt.size || 1;
        function dashOf(kind) { return kind === 'dashed' ? [4, 3] : kind === 'dotted' ? [1, 2] : []; }
        var lvDash = dashOf(lvSt.style || lineSt.style || 'solid');
        var lvStyle = lvDash.length ? 'dashed' : 'solid';
        var lvSize = (typeof lvSt.size === 'number' && lvSt.size > 0) ? lvSt.size : size;
        var x1 = Math.min(A.x, B.x), x2 = Math.max(A.x, B.x);
        var span = Math.max(40, x2 - x1);
        /* امتداد: مرزِ پن از bounding.width؛ بدون bounding (تست/حالت قدیمی)
           امتدادِ نسبیِ دور استفاده می‌شود تا خط هرگز کوتاه نماند. */
        var paneW = (e.bounding && e.bounding.width) ? e.bounding.width : 0;
        var xStart = st.extendLeft ? 0 : x1;
        var xEnd = st.extendRight ? (paneW || (x2 + span * 50)) : (x2 + span * 0.12);
        var figs = [];
        var rev = !!st.reverse;
        var alpha = (typeof st.bgOpacity === 'number') ? st.bgOpacity : 0.10;
        var showFills = st.fills !== false;
        var legacyLabels = st.labels !== false;
        var showPrices = (st.showPrices === undefined) ? legacyLabels : (st.showPrices !== false);
        var showPercents = (st.showPercents === undefined) ? legacyLabels : (st.showPercents !== false);
        var pctMode = st.pctMode || 'coeff';
        var oneColor = st.oneColor ? (st.oneColorValue || color) : null;
        var levels = rvFibNormalizeLevels(st).slice().sort(function (a, b) { return b.coeff - a.coeff; });
        var yOf = function (c) { return rev ? (A.y + (B.y - A.y) * c) : (B.y + (A.y - B.y) * c); };
        var pOf = function (c) { return rev ? (vA + (vB - vA) * c) : (vB + (vA - vB) * c); };
        var prev = null;
        levels.forEach(function (L) {
          if (L.visible === false) return;
          var y = yOf(L.coeff), val = pOf(L.coeff);
          var lcolor = oneColor || L.color || color;
          // ناحیهٔ پرشدهٔ بین دو سطحِ مجاور (پاریتی نهایت‌نگر/TV)
          if (prev && showFills && y !== prev.y) {
            figs.push({ type: 'rect', attrs: { x: xStart, y: Math.min(prev.y, y), width: Math.max(1, xEnd - xStart), height: Math.abs(y - prev.y) },
                        styles: { style: 'fill', color: _rvRgba(prev.color, alpha) } });
          }
          figs.push({ type: 'line', attrs: { coordinates: [{ x: xStart, y: y }, { x: xEnd, y: y }] },
                      styles: { color: lcolor, size: lvSize, style: lvStyle, dashedValue: lvDash } });
          if (showPrices || showPercents) {
            var head = showPercents ? rvFibLevelLabel(L, pctMode) : '';
            var tail = showPrices ? val.toFixed(2) : '';
            // ‎ برای جلوگیری از وارونگی bidi در متن راست‌به‌چپ
            var txt = '‎' + (head && tail ? head + '(' + tail + ')' : (head || tail));
            figs.push({ type: 'text', attrs: { x: xStart + 4, y: y - 3, text: txt, align: 'left', baseline: 'bottom' },
                        styles: { style: 'fill', color: lcolor, size: 10, family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } });
          }
          prev = { y: y, color: lcolor };
        });
        if (st.trend !== false) {
          figs.push({ type: 'line', attrs: { coordinates: [A, B] },
                      styles: { color: st.trendColor || '#787b86', size: size, style: 'dashed', dashedValue: [4, 3] } });
        }
        return figs;
      }
    });

  }
} catch (e) { console.warn('[custom-overlays]', e); }

/* v7.3 — Fibonacci با DrawingMath (log-aware) — سطوح دقیق در هر مقیاس */
window.FIB_STD = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1, 1.618, 2.618];
window.FIB_COLORS = ['#787B86', '#F23645', '#81c784', '#4caf50', '#089981', '#64b5f6', '#787B86', '#2962FF', '#F23645'];
/* بعد از draw end، سطوح فیبو را با DrawingMath بازمحاسبه و بهصورت خطوط dashed میکشد */

// Hybrid rail: group toggling / bind flyout buttons / drag / hide
function rvRailInit() {
  const rail = rvEl('rail');
  if (!rail) return;
  // v8.6: کلیک گروه/آیتم‌ها در rtvBuildRail بایند میشود — اینجا فقط بستن بیرونی + grip
  // کلیک بیرون → بستن
  if (!rail.dataset.outside) {
    document.addEventListener('mousedown', function (ev) {
      if (!rail.contains(ev.target)) rail.querySelectorAll('.rail-flyout').forEach(x => x.classList.remove('open'));
    });
    rail.dataset.outside = '1';
  }
  // drag grip (اگر هست)
  var grip = rail.querySelector('.rail-grip');
  if (grip && !grip.dataset.drag) { grip.addEventListener('pointerdown', rvRailDragStart); grip.dataset.drag = '1'; }
}
var _rvRailDrag = null;
function rvRailDragStart(ev) {
  ev.preventDefault();
  var rail = rvEl('rail');
  if (!rail) return;
  var rect = rail.getBoundingClientRect();
  _rvRailDrag = { dx: ev.clientX - rect.left, dy: ev.clientY - rect.top };
  document.addEventListener('pointermove', rvRailDragMove);
  document.addEventListener('pointerup', rvRailDragEnd);
}
function rvRailDragMove(ev) {
  if (!_rvRailDrag || !rvEl('rail')) return;
  var rail = rvEl('rail');
  rail.style.left = (ev.clientX - _rvRailDrag.dx) + 'px';
  rail.style.top = (ev.clientY - _rvRailDrag.dy) + 'px';
}
function rvRailDragEnd() {
  _rvRailDrag = null;
  document.removeEventListener('pointermove', rvRailDragMove);
  document.removeEventListener('pointerup', rvRailDragEnd);
}

/* ---------- ابزارها: بایند مستقیم به createOverlay (native) ---------- */
var RTV_TOOL_NAMES = {
  'cursor': null,
  'segment': 'segment',
  'straightLine': 'straightLine',
  'rayLine': 'rayLine',
  'horizontalStraightLine': 'horizontalStraightLine',
  'verticalStraightLine': 'verticalStraightLine',
  'horizontalSegment': 'horizontalSegment',
  'verticalSegment': 'verticalSegment',
  'horizontalRayLine': 'horizontalRayLine',
  'verticalRayLine': 'verticalRayLine',
  'fibonacciLine': 'fibonacciLine',
  'parallelStraightLine': 'parallelStraightLine',
  'priceChannelLine': 'priceChannelLine',
  'priceLine': 'priceLine',
  'simpleAnnotation': 'simpleAnnotation',
  'simpleTag': 'simpleTag',
  'brush': 'brush',
  'fib-extension': 'fib-extension',
  'pitchfork': 'pitchfork',
  'ruler': 'ruler',
  'box': 'box',
  'rect': 'rect',
  'ellipse': 'ellipse',
  'triangle': 'triangle',
  'arrow': 'arrow'
};

var rvOverlays = [];  // شناسه‌های overlay (برای persistence)

/* ==================== B-2 FIX — دابل‌کلیک روی ابزارهای چندنقطه‌ای ====================
 * ریشهٔ باگ از واکاوی مستقیم static/klinecharts.min.js (شواهد: dev/_s3.txt و dev/_s5.txt):
 *
 *  1) هندلر mouseDoubleClickEvent (offset @120959) تنها overlay.forceComplete() را
 *     می‌زند (forceComplete = currentStep = -1) و هیچ نقطه‌ای ثبت نمی‌کند.
 *     همان‌جا _figureMouseClickEvent صدا زده می‌شود نه _figureMouseDoubleClickEvent؛
 *     پس overlay.onDoubleClick برای overlayِ *در حال ترسیم* هرگز فراخوانی نمی‌شود
 *     و تزریق onDoubleClick (فرض اولیهٔ ما) بی‌اثر بود.
 *  2) در _mouseUpHandler (offset @25535) اگر _clickCount>1 باشد فقط
 *     mouseDoubleClickEvent می‌رود و mouseClickEvent هرگز اجرا نمی‌شود؛ یعنی
 *     نقطه‌ای که آن mouseup باید ثبت می‌کرد جا می‌افتد.
 *  3) نتیجه: overlay با (totalStep-2) نقطه commit می‌شود. گارد
 *     «coordinates.length < N» در createPointFigures آرایهٔ خالی برمی‌گرداند
 *     → رسم نامرئی/خراب و درگیری حلقهٔ floatWait.
 *
 * راه‌حل: روی ظرف چارت در فاز capture (پیش از هندلر bubble خودِ vendor روی المان
 * داخلی) mouseupِ دومِ دابل‌کلیک را می‌گیریم. اگر نقاط هنوز کامل نشده‌اند،
 * forceCompleteِ ناقص را با stopPropagation بلعیده و فقط nextStep() می‌زنیم —
 * نقطهٔ معلق را mousemove از قبل دقیقاً زیر نما نوشته است.
 *
 * چرا ایمن است: have = currentStep و need = totalStep-1 و شرط ورود have<need است،
 * پس currentStep < totalStep-1؛ بنابراین nextStep() هرگز به شاخهٔ کامل‌شدن
 * نمی‌رود و commit داخلی vendor (progressOverlayComplete) بی‌صاحب نمی‌ماند.
 * نیز _resetClickTimeout() بعد از هر دابل‌کلیک _clickCount را صفر می‌کند، پس
 * بلوکه‌کردن یک mouseup شمارندهٔ داخلی را ناهمگام نمی‌کند.
 */
function rvDrawingOverlay() {
  if (!rv.chart) return null;
  var overs = [];
  try { overs = rv.chart.getOverlays() || []; } catch (e) { return null; }
  for (var i = 0; i < overs.length; i++) {
    var o = overs[i];
    if (o && typeof o.isDrawing === 'function' && o.isDrawing()) return o;
  }
  return null;
}

function rvInstallDblGuard(el) {
  if (!el || el.__rvDblGuard) return;                       // یک‌بار به ازای هر ظرف چارت
  el.__rvDblGuard = true;
  el.addEventListener('mouseup', function (ev) {
    try {
      if (!ev || ev.button !== 0 || ev.detail < 2) return;  // فقط کلیکِ دومِ دابل‌کلیک
      var ov = rvDrawingOverlay();
      if (!ov) return;                                      // چیزی در حال رسم نیست → رفتار پیش‌فرض
      var total = ov.totalStep | 0;
      if (total < 3) return;                                // تک‌نقطه‌ای‌ها را vendor درست می‌بندد
      var need = total - 1;                                 // تعداد نقاطی که ابزار می‌خواهد
      var have = ov.currentStep | 0;                        // نقاط ثبت/معلق (ایندکس ۰..currentStep-1)
      if (have >= need) return;                             // کامل است → بگذار vendor forceComplete کند
      ev.stopPropagation();                                 // جلوگیری از forceCompleteِ ناقصِ vendor
      if (typeof ov.nextStep !== 'function') return;
      ov.nextStep();                                        // ثبت نقطهٔ معلق زیر نما
      if (typeof rvToast === 'function') {
        var left = need - (ov.currentStep | 0);
        rvToast(left > 0
          ? '✓ نقطه ثبت شد — ' + left + ' نقطهٔ دیگر لازم است'
          : '✓ نقطه ثبت شد — با یک کلیک دیگر رسم بسته می‌شود');
      }
    } catch (e) { /* هرگز مسیر ماوس را نشکند */ }
  }, true);                                                 // ← capture: پیش از هندلر vendor
}

var rvFloatWait = null;   // v8.9-B2 — تک‌هندل تا جلوگیری از انباشتن interval های موازی

function rvSetTool(name, btn) {
  if (!rv.chart) return;
  // active-state: همهٔ دکمههای sidebar (tv5) + هر دکمه با data-name
  document.querySelectorAll('.tv5-tool, .tv-btn, .tv5-tf').forEach(b => b.classList.remove('active'));
  document.querySelectorAll('#rail .tv5-tool').forEach(b => b.classList.remove('active'));
  if (btn && btn.classList) btn.classList.add('active');
  // cursor: هیچ رسمی — فقط حالت نرمال
  if (name === 'cursor' || name === 'cross' || name === 'crosshair') {
    rv.tool = null;
    if (btn) btn.classList.add('active');
    rvToast('ابزار عادی (cursor)');
    return;
  }
  const overlayName = RTV_TOOL_NAMES[name];
  if (!overlayName) {
    rvToast('⚠️ ابزار \'' + name + '\' در KLineChart متأسفانه نیست');
    if (btn) btn.classList.add('active');
    return;
  }
  rv.tool = name;
  if (btn) btn.classList.add('active');
  try {
    var _rvToolSt = (window.__rvToolStyles && window.__rvToolStyles[overlayName]) || undefined;
    rv.chart.createOverlay({ name: overlayName, styles: _rvToolSt, onSelected: function (ctx) {
      if (ctx && ctx.overlay) rvShowDrawFloat(ctx.overlay.id);
    }});   // بدون points → حالت ترسیم (isDrawing)
    rvToast('📐 ' + (btn ? btn.title : name) + ' — نقاط را یکی‌یکی بگذار؛ دابل‌کلیک فقط با نقاطِ کامل رسم را می‌بندد (کلیک راست = لغو)');
    // v8.9-B2 — تک‌هندل: نسخهٔ قبل هر فراخوانی یک interval جدید می‌ساخت و پولرهای
    // موازی بعد از اتمام رسم، چند بار rvSaveOverlays و بازگشت به cursor را اجرا می‌کردند.
    if (rvFloatWait) { clearInterval(rvFloatWait); rvFloatWait = null; }
    const myTool = name;
    rvFloatWait = setInterval(function () {
      // چارت از بین رفته یا ابزار عوض شده → پولر باید بمیرد (رفع حلقهٔ بی‌پایان)
      if (!rv.chart || rv.tool !== myTool) { clearInterval(rvFloatWait); rvFloatWait = null; return; }
      var overs = [];
      try { overs = rv.chart.getOverlays() || []; }
      catch (e) { clearInterval(rvFloatWait); rvFloatWait = null; return; }
      if (!overs.length) return;                    // هنوز رسمی شروع نشده
      const drawing = overs.find(o => o.isDrawing && o.isDrawing());
      if (!drawing) {
        clearInterval(rvFloatWait); rvFloatWait = null;
        // v8.0 — «ماندن در حالت رسم» (پاریتی نهایت‌نگر): با toggle فعال میشود
        if (window.RTV_STAY_DRAW && rv.tool) { if (typeof rvSaveOverlays === 'function') rvSaveOverlays(); return; }
        // TV-parity: بعد از اتمام رسم، ابزار به cursor برمی‌گردد (کلیک بعدی = انتخاب رسم، نه رسم جدید)
        rv.tool = null;
        document.querySelectorAll('#rail .tv5-tool').forEach(function (b) { b.classList.remove('active'); });
        var cur = document.querySelector('#rail [data-name="cursor"]');
        if (cur) cur.classList.add('active');
        var done = rv.chart.getOverlays().filter(function (o) { return !(o.isDrawing && o.isDrawing()); });
        var last = done[done.length - 1];
        if (last) rvAttachPopupOnSelect(last.id);
        rvShowDrawFloat();
        rvSaveOverlays();
      }
    }, 350);
  } catch (e) {
    rvToast('خطا در ابزار: ' + (e && e.message));
  }
}

/* v8.0 — ذخیره از طریق stSet (هم‌مسیر با rvRestoreOverlays نسخهٔ برنده در خط ۸۶۷؛
   قبل از این، ذخیره در localStorage خام بود و restore آن را نمی‌خواند) */
/* v9.7.1 — دکوراسیون‌هایی که خودِ اپ می‌سازد (سطوح کلیدی خودکار، خط پایانیِ قبل)
   رسم کاربر نیستند. قبلاً فقط پیشوند 'auto_' فیلتر می‌شد، پس خطِ پایانیِ قبل —
   که btsPrevCloseLine بدون id می‌ساخت و KLineCharts برایش شناسهٔ تصادفی می‌زد —
   داخل بلاوب tech_<sym> ذخیره می‌شد و rvRestoreOverlays با هر reload یک نسخهٔ
   تکراری تولید می‌کرد. فیلتر روی «بازیابی» هم بلاوب‌های آلودهٔ موجود را خودترمیم
   می‌کند. */
function rvIsDecoration(id) {
  var s = String(id || '');
  return s.indexOf('auto_') === 0 || s.indexOf('bts_') === 0;
}

function rvSaveOverlays() {
  try {
    if (!rv.chart || !rv.sym || typeof stSet !== 'function') return;
    var overs = (rv.chart.getOverlays() || []).filter(function (o) {
      return !(o.isDrawing && o.isDrawing()) && !rvIsDecoration(o.id);
    });

    var shapes = overs.map(function (o) {
      return {
        id: o.id, name: o.name, lock: !!o.lock, zLevel: o.zLevel || 0,
        styles: o.styles || null,
        points: (o.points || []).map(function (p) { return { timestamp: p.timestamp, value: p.value }; })
      };
    });
    stSet('tech_' + rv.sym, { shapes: shapes, itv: rv.itv, adj: rv.adj, logScale: rv.logScale, ts: Date.now() });
    stSet('tech_last', rv.sym);
  } catch (e) {}
}
/* نسخهٔ قدیمی rvRestoreOverlays (localStorage خام) حذف شد — نسخهٔ stGet در خط ~۸۸۰ مرجع است */

function rvDeleteLast() {
  if (!rv.chart) return;
  try {
    // آخرین رسمِ رسمشده (غیرِ در حال رسم) را حذف کن — اگر همه رسم شدند، هیچی
    const overs = (rv.chart.getOverlays() || []).filter(o => !rvIsDecoration(o.id));   // v9.7.6 — دکوراسیون/مارکر 📅 حذف نشود
    if (!overs.length) { rvToast('هیچ رسمی وجود ندارد'); return; }
    // در حال ترسیم است؟ لغو کن
    const drawing = overs.find(o => o.isDrawing && o.isDrawing());
    if (drawing) { rv.chart.removeOverlay({ id: drawing.id }); rvToast('لغو رسم جاری'); return; }
    const last = overs[overs.length - 1];
    rv.chart.removeOverlay({ id: last.id });
    rvOverlays = rvOverlays.filter(id => id !== last.id);
    rvToast('✔ آخرین رسم حذف شد');
    rvSaveOverlays();
  } catch (e) { rvToast('حذف ناموفق: ' + (e && e.message)); }
}

function rvClearAll() {
  if (!rv.chart) return;
  try { rv.chart.removeOverlay(); } catch (e) {}
  rvOverlays = [];
  // v9.7: قبلاً localStorage.removeItem('tech_'+sym) بود؛ آن کلید هیچ‌وقت وجود
  // نداشت چون rvSaveOverlays از stSet (بلاوب bors_state_v2) استفاده میکند —
  // نتیجه: «همه حذف شدند» فقط ظاهری بود و رسم‌ها در بار بعدی برمی‌گشتند.
  if (typeof stDel === 'function') stDel('tech_' + rv.sym);
  else stSet('tech_' + rv.sym, null);
  rvToast('همهٔ رسم‌ها حذف شدند');
}

/* فاز ۳ — Delete/Backspace: overlay انتخابشده حذف شود (v10: chart.getClickOverlayInfo()) */
function rvBindDeleteKey() {
  document.addEventListener('keydown', function (e) {
    if (!rv.chart) return;
    if (e.key !== 'Delete' && e.key !== 'Backspace') return;
    // اگر در input هستیم، دخالت نکن
    const tag = (document.activeElement && document.activeElement.tagName) || '';
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    try {
      const info = (typeof rv.chart.getClickOverlayInfo === 'function')
        ? rv.chart.getClickOverlayInfo() : null;
      const selId = info && info.overlay && info.overlay.id;
      if (selId) {
        rv.chart.removeOverlay({ id: selId });
        rvOverlays = rvOverlays.filter(id => id !== selId);
        // v9.7: بدون این خط، رسمِ حذف‌شده با Delete/Backspace در localStorage
        // می‌ماند و بعد از عوض‌کردن نماد یا rvRerender دوباره ظاهر می‌شد.
        rvSaveOverlays();
        rvToast('🗑 رسم انتخابشده حذف شد');
        e.preventDefault();
        return;
      }
      // fallback: آخرین رسم
      if (rvOverlays.length) { rvDeleteLast(); e.preventDefault(); }
    } catch (err) {}
  });
}


/* ---------- persistence: overlays per symbol ---------- */
function rvPersistTech() {
  try {
    if (rv.sym && rv.chart) {
      const overs = rv.chart.getOverlays()
        .filter(o => !rvIsDecoration(o.id))   // سطوح خودکار را ذخیره نکن (هر بار fetch می‌شوند)

        .map(o => ({
          id: o.id, name: o.name, points: o.points,
          styles: o.styles || null, lock: !!o.lock
        }));
      stSet('tech_' + rv.sym, { shapes: overs, itv: rv.itv, adj: rv.adj, logScale: rv.logScale, ts: Date.now() });
      stSet('tech_last', rv.sym);
    }
  } catch (e) {}
}
function rvRestoreOverlays() {
  try {
    if (!rv.sym || !rv.chart) return;
    const st = stGet('tech_' + rv.sym, null);
    if (!st || !Array.isArray(st.shapes)) return;
    rvOverlays = [];
    st.shapes.forEach(s => {
      try {
        if (rvIsDecoration(s.id)) return;   // خودترمیم بلاوب‌های آلودهٔ نسخه‌های قبل
        if (s.points && s.points.length) {

          rv.chart.createOverlay({ id: s.id, name: s.name, points: s.points,
                                   lock: !!s.lock, zLevel: s.zLevel || 0 });
          rvOverlays.push(s.id);
          rvAttachPopupOnSelect(s.id);   // کلیک روی رسم بازیابی‌شده هم popup را باز کند
        }
      } catch (e) {}
    });
  } catch (e) {}
}

/* ---------- Auto-Levels: سطوح کلیدی + بلاکهای تقاضا/عرضه ---------- */
var rvAutoLevels = { on: false, ids: [] };

function rvAutoLevelsInit() {
  try { rvAutoLevels.on = !!stGet('tech_auto_levels', true); } catch (e) { rvAutoLevels.on = true; }
  const b = rvEl('rvAutoLevelsBtn');
  if (b) b.classList.toggle('rv-on', rvAutoLevels.on);
}

async function rvApplyAutoLevels(force) {
  if (!rvAutoLevels.on || !rv.sym || !rv.chart) return;
  try {
    // FIX: همیشه اول پاک کن (وقتی نماد عوض میشود، رسمهای قبلی نباید بمانند)
    rvRemoveAutoLevels(true);
    const r = await fetch('/api/chart/' + encodeURIComponent(rv.sym) + '/key-levels', { cache: 'no-store' });
    const j = await r.json();
    if (!j || !j.levels || !j.levels.length) return;
    const tsOf = (d) => rvDateToTs(d);   // v8.7 FIX-3: نقاط overlay هم میلی‌ثانیه می‌خواهند
    // سطحها: خط افقی (کینگل قویتر = رنگ سیرتر؟ ساده: high=کهربایی، low=آبی)
    j.levels.forEach(l => {
      const id = 'auto_lvl_' + tsOf(l.date) + '_' + l.price;
      var chg = l.kind === 'high' ? '#f59e0b' : '#38bdf8';
      try {
        rv.chart.createOverlay({
          id: id, name: 'horizontalStraightLine',
          points: [{ timestamp: tsOf(l.date), value: l.price }],
          lock: true,
          styles: { line: { color: chg, style: 'dashed', size: 1 } }
        });
        rvAutoLevels.ids.push(id);
      } catch (e) {}
    });
    // بلاکهای Order Block — چون این نسخهٔ KLineChart overlay مستطیل (rect) رسمی
    // ندارد، بلاک با ۴ خط segment رسم میشود: بالا/پایین/دو عمود.
    (j.blocks || []).forEach((b, i) => {
      const color = b.type === 'demand' ? '#10b981' : '#f43f5e';
      const P = (t, v) => ({ timestamp: tsOf(t), value: v });
      try {
        const lines = [
          ['blk_t', 'segment', [P(b.time_start, b.top), P(b.time_end, b.top)]],
          ['blk_b', 'segment', [P(b.time_start, b.bottom), P(b.time_end, b.bottom)]],
          ['blk_l', 'verticalSegment', [P(b.time_start, b.top), P(b.time_start, b.bottom)]],
          ['blk_r', 'verticalSegment', [P(b.time_end, b.top), P(b.time_end, b.bottom)]]
        ];
        lines.forEach(([suf, name, pts]) => {
          try {
            rv.chart.createOverlay({
              id: 'auto_blk' + i + '_' + b.type + '_' + suf, name: name,
              points: pts, lock: true,
              styles: { line: { color: color, style: 'dashed', size: 1 } }
            });
            rvAutoLevels.ids.push('auto_blk' + i + '_' + b.type + '_' + suf);
          } catch (e) {}
        });
      } catch (e) {}
    });
    rvToast('⚡ سطوح کلیدی: ' + j.levels.length + ' سطح + ' + (j.blocks || []).length + ' بلاک');
  } catch (e) { console.warn('[auto-levels]', e); }
}

function rvRemoveAutoLevels(silent) {
  if (rv.chart) {
    (rvAutoLevels.ids || []).forEach(id => { try { rv.chart.removeOverlay(id); } catch (e) {} });
  }
  rvAutoLevels.ids = [];
  if (!silent) rvToast('سطوح خودکار حذف شد');
}

function rvToggleAutoLevels() {
  rvAutoLevels.on = !rvAutoLevels.on;
  try { stSet('tech_auto_levels', rvAutoLevels.on); } catch (e) {}
  const b = rvEl('rvAutoLevelsBtn');
  if (b) b.classList.toggle('rv-on', rvAutoLevels.on);
  if (rvAutoLevels.on) rvApplyAutoLevels(true);
  else rvRemoveAutoLevels();
}

/* ---------- دکمه‌های پایین ---------- */
/* v9.7.1 — rvToggleLog حذف شد: هیچ دکمه‌ای به آن بند نبود و تنها فراخوانشش
   rvSetScale بود که خودش معیوب بود (دو بار تاگل → مقیاس برعکس). مسیر معتبر
   مقیاس، btsSetScale در tech_365.js است (ست‌کردن + راستی‌آزمایی با getYAxes).
   rv.axisName هم در همین تابع نوشته می‌شد و هیچ‌جا خوانده نمی‌شد؛ آن هم رفت. */

function rvToggleAdj() {
  rv.adj = rv.adj ? 0 : 1;
  var btn = rvEl('rvAdjBtn');
  if (btn) btn.classList.toggle('rv-on', !!rv.adj);
  // v8.6: چیپ نوع تعدیل در هدر (مثل نهایت‌نگر)
  var chip = rvEl('nnAdjBtn');
  if (chip) {
    chip.textContent = rv.adj ? 'تعدیل عملکردی' : 'بدون تعدیل';
    chip.classList.toggle('rv-on', !!rv.adj);
  }
  /* v9.6: دادهٔ خام در حافظه هست؛ تغییر تعدیل نیاز به واکشی دوباره ندارد.
     با rvRerender فقط سری بازسازی می‌شود (و اگر خامی نبود به rvLoad برمی‌گردد). */
  if (rv.sym && !rvRerender()) { rv.data = null; rvLoad(rv.sym); }
}
// v8.6 — سینک اولیه چیپ تعدیل با state ذخیره‌شده
function rvSyncAdjChip() {
  var chip = rvEl('nnAdjBtn');
  if (!chip) return;
  chip.textContent = rv.adj ? 'تعدیل عملکردی' : 'بدون تعدیل';
  chip.classList.toggle('rv-on', !!rv.adj);
}
function rvZoom(k) { if (rv.chart) rv.chart.zoomAtCoordinate(k, null); }
function rvZoomRange(n) {
  if (!rv.chart || !rv.data || !rv.data.length) return;
  // n = تعداد روز (مثل رهاورد) — با aggregation D/W/M تبدیل کن
  const factor = rv.itv === 'W' ? 7 : rv.itv === 'M' ? 30 : 1;
  const bars = Math.max(2, Math.round(n / factor));
  rv.chart.zoomAtDataIndex(1.5, Math.max(0, rv.data.length - bars));
}

/* ---------- جستجو (از قبل) ---------- */
var rvSearchIdx = -1;
var rvSymCacheReady = false;
async function rvEnsureSymCache() {
  if (rvSymCacheReady) return;
  try {
    const r = await fetch('/api/market', { cache: 'no-store' });
    const j = await r.json();
    rv.symCache = (j.data || []).map(x => x.symbol).filter(s => s).sort((a, b) => a.localeCompare(b));
  } catch (e) { rv.symCache = rv.symCache || []; }
  rvSymCacheReady = true;
}
async function rvOnSearch(q) {
  const drop = rvEl('rvSearchDrop');
  if (!drop) return;
  if (!Array.isArray(rv.symCache) || !rv.symCache.length) await rvEnsureSymCache();
  const qq = String(q || '').trim();
  let hits;
  if (qq.length < 1) {
    hits = rv.symCache.slice(0, 25);
  } else {
    // مثل رهاورد: نمادهایی که با متن شروع میشوند اول، بعد شامل
    const starts = rv.symCache.filter(s => s.startsWith(qq));
    const includes = rv.symCache.filter(s => s.includes(qq) && !s.startsWith(qq));
    hits = starts.concat(includes).slice(0, 25);
  }
  if (!hits.length) { drop.style.display = 'none'; return; }
  drop.innerHTML = '<div class="rv-search-head"><span>نماد</span><span>بازار</span></div>' + hits.map((s, i) =>
    `<div class="rv-search-item" data-i="${i}" onclick="rvPickSymbol('${s.replace(/'/g, "\\'")}')"><span class="rv-search-sym">${s}</span><span class="rv-search-chip">سهام · بورس</span></div>`).join('');
  drop.style.display = 'block';
  rvSearchIdx = -1;
}
function rvPickSymbol(s) {
  rvEl('rvSymInput').value = s;
  rvEl('rvSearchDrop').style.display = 'none';
  rvLoad(s);
}
function rvSearchKey(e) {
  if (e.key === 'Enter') {
    const items = document.querySelectorAll('#rvSearchDrop .rv-search-item');
    if (items.length) {
      if (rvSearchIdx >= 0 && items[rvSearchIdx]) items[rvSearchIdx].click();
      else items[0].click();
    }
    e.preventDefault();
  } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    const items = document.querySelectorAll('#rvSearchDrop .rv-search-item');
    if (!items.length) return;
    if (e.key === 'ArrowDown') rvSearchIdx = Math.min(rvSearchIdx + 1, items.length - 1);
    else rvSearchIdx = Math.max(rvSearchIdx - 1, 0);
    items.forEach((el, i) => el.style.background = i === rvSearchIdx ? 'rgba(56,189,248,.25)' : '');
  }
}

/* ---------- انتشار تحلیل / شیر ---------- */
/* v9.6 — این تابع هیچ‌جا فراخوانی نمی‌شد ولی همان تداخل نوع قیمت↔تعدیل را
   داشت: rv.adj را می‌نوشت و با rvSyncAdjChip دکمهٔ تعدیل را ری‌سنک می‌کرد.
   برای سازگاری نگه داشته شده، اما حالا به دراپ‌داون واقعی واگذار می‌کند و
   هرگز وضعیت تعدیل را عوض نمی‌کند. */
function rvTogglePriceType() {
  let t = 'close';
  try { t = stGet('techPriceType', 'close'); } catch (e) {}
  t = (t === 'last') ? 'close' : 'last';
  try { stSet('techPriceType', t); } catch (e) {}
  if (typeof btsApplyPriceType === 'function') { btsApplyPriceType(t); return; }
  if (rv.sym && !rvRerender()) { rv.data = null; rvLoad(rv.sym); }
  rvToast(t === 'close' ? '¥ نوع قیمت: پایانی' : '¥ نوع قیمت: آخرین');
}

/* ---------- تنظیمات چارت (نوع نمودار کامل + حجم) ---------- */
var rvChartMenuOpen = false;
function rvOpenChartSettings() {
  const m = rvEl('rvChartSettingsMenu');
  if (!m) return;
  if (rvChartMenuOpen) { m.style.display = 'none'; rvChartMenuOpen = false; return; }
  const cur = (rv.chart && rv.chart.getStyles && rv.chart.getStyles().candle) ? rv.chart.getStyles().candle.type : 'candle_solid';
  m.innerHTML = '<div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;">نوع نمودار (مثل رهاورد):</div>' +
    '<div style="display:flex;gap:5px;flex-wrap:wrap;flex-direction:column;">' +
    [
      ['candle_solid', '🕯 کندل (Candles)'],
      ['candle_stroke', '◌ کندل توخالی (Hollow)'],
      ['ohlc', '｜ میله‌ای (Bars/OHLC)'],
      ['candle_up_stroke', '🟩 کندل فقط-بالا'],
      ['candle_down_stroke', '🟥 کندل فقط-پایین'],
      ['area', '🏔 ناحیه (Area)']
    ].map(([v, lbl]) =>
      `<button class="rv-ind-add" style="text-align:right; ${cur === v ? 'background:var(--accent-blue); color:#000;' : ''}" onclick="rvSetChartType('${v}')">${lbl}</button>`).join('') +
    '</div>' +
    '<div style="font-size:11px;color:var(--text-secondary);margin:8px 0 4px;">حجم:</div>' +
    `<button class="rv-ind-add" onclick="rvToggleVolume()">📊 حجم ${rv.chart && rv.chart.getIndicators ? (rv.chart.getIndicators({ name: 'VOL' }).length ? 'روشن ✓' : 'خاموش') : 'خاموش'}</button>`;
  m.style.display = 'block';
  rvChartMenuOpen = true;
}
function rvSetChartType(type) {
  try { rv.chart.setStyles({ candle: { type: type } }); } catch (e) {}
  rvChartMenuOpen = false;
  const m = rvEl('rvChartSettingsMenu');
  if (m) m.style.display = 'none';
  const lbl = { candle_solid: 'کندل', candle_stroke: 'کندل توخالی', ohlc: 'میله‌ای', area: 'ناحیه', candle_up_stroke: 'کندل فقط-بالا', candle_down_stroke: 'کندل فقط-پایین' }[type] || type;
  rvToast('نوع نمودار: ' + lbl);
}
function rvToggleVolume() {
  try {
    const has = rv.chart.getIndicators({ name: 'VOL' }).length > 0;
    if (has) rv.chart.removeIndicator({ name: 'VOL' });
    else rv.chart.createIndicator({ name: 'VOL', id: 'ind_VOL', isStack: false, calcParams: [21] });
    rvToast(has ? 'حجم خاموش' : 'حجم روشن');
  } catch (e) {}
  rvOpenChartSettings();
}

/* ---------- نوار شناور رسم: بعد از اولین رسم ظاهر میشود ---------- */
var RV_TOOL_FA = {
  segment: 'خط روند', rayLine: 'پرتو', straightLine: 'خط امتداد',
  horizontalStraightLine: 'خط افقی', verticalStraightLine: 'خط عمودی',
  horizontalRayLine: 'پرتو افقی', verticalRayLine: 'پرتو عمودی',
  horizontalSegment: 'پاره‌خط افقی', verticalSegment: 'پاره‌خط عمودی',
  fibonacciLine: 'فیبوناچی بازگشتی', 'fib-extension': 'فیبوناچی امتدادی',
  parallelStraightLine: 'کانال موازی', priceChannelLine: 'کانال قیمتی',
  pitchfork: 'پیچفورک', rect: 'مستطیل', ellipse: 'دایره', triangle: 'مثلث',
  box: 'باکس گان', arrow: 'فلش', simpleAnnotation: 'یادداشت', simpleTag: 'برچسب',
  ruler: 'خطکش', brush: 'قلم', priceLine: 'خط قیمت'
};
var _rvPopOverlayId = null;
function _rvPopOverlay() {
  if (!rv.chart) return null;
  /* v9.7.6 — دکوراسیون خودکار (سطوح کلیدی، خط پایانی، مارکر رویداد 📅) رسم
     کاربر نیست؛ اگر آخرین overlay یک مارکر باشد پاپ‌آپِ ویرایش رسم روی آنها
     باز می‌شد (رنگ/حذف بی‌معنی). فیلتر روی همان rvIsDecoration. */
  var overs = (rv.chart.getOverlays() || []).filter(function (o) { return !rvIsDecoration(o.id); });
  if (_rvPopOverlayId) {
    var hit = overs.filter(function (o) { return o.id === _rvPopOverlayId; })[0];
    if (hit) return hit;
  }
  var done = overs.filter(function (o) { return !(o.isDrawing && o.isDrawing()); });
  return done.length ? done[done.length - 1] : null;
}
function _rvApplyStyles(patch) {
  var last = _rvPopOverlay();
  if (!last) return;
  var merged = JSON.parse(JSON.stringify(last.styles || {}));
  (function deep(dst, src) {
    Object.keys(src).forEach(function (k) {
      if (src[k] && typeof src[k] === 'object' && !Array.isArray(src[k]) && dst[k] && typeof dst[k] === 'object') deep(dst[k], src[k]);
      else dst[k] = src[k];
    });
  })(merged, patch);
  try {
    rv.chart.overrideOverlay({ id: last.id, styles: merged });
    last.styles = merged;
    rvSaveOverlays();
  } catch (e) { rvToast('اعمال نشد: ' + (e && e.message)); }
}
/* جایگزینیِ کاملِ styles (برخلاف _rvApplyStyles که ادغام می‌کند).
   klinecharts در overrideOverlay کلیدهای جدید را روی آبجکت قبلی merge می‌کند و
   هیچ‌وقت حذف نمی‌کند؛ برای «لغو» دیالوگ باید کل مرجع عوض شود. */
function _rvReplaceStyles(newStyles) {
  var last = _rvPopOverlay();
  if (!last) return;
  var s = JSON.parse(JSON.stringify(newStyles || {}));
  try {
    rv.chart.overrideOverlay({ id: last.id, styles: s });
    last.styles = s;
    rvSaveOverlays();
  } catch (e) { rvToast('اعمال نشد: ' + (e && e.message)); }
}
window._rvReplaceStyles = _rvReplaceStyles;
/* نوشتنِ آرایهٔ سطوح روی رسمِ انتخابی (تنها مسیرِ معتبر از v8.9 به بعد) */
function _rvSetFibLevels(levels) {
  var arr = (levels || []).map(function (L) {
    return { coeff: L.coeff, color: L.color || _rvFibColorOf(L.coeff), visible: L.visible !== false };
  });
  _rvApplyStyles({ fibLevels: arr });
  return arr;
}
window._rvSetFibLevels = _rvSetFibLevels;
function rvShowDrawFloat(overlayId) {
  if (overlayId) _rvPopOverlayId = overlayId;
  var last = _rvPopOverlay();
  if (!last) return;
  _rvPopOverlayId = last.id;
  var pop = rvEl('rvDrawFloat');
  if (!pop) return;
  pop.style.display = 'block';
  var nm = last.name || '';
  var st = last.styles || {};
  var lineSt = st.line || {};
  var rows = '';
  if (nm === 'fibonacciLine' || nm === 'fib-extension') {
    /* v8.9 — فهرستِ سطوح از مدلِ جدید خوانده می‌شود (ضریبِ دلخواه + ترتیب) */
    rows += '<div class="dpr dpr-lv"><span>سطوح</span><div>' + rvFibQuickRowsHtml(st) + '</div></div>';
    rows += '<div class="dpr"><span>برچسب‌ها</span><input type="checkbox" ' + (st.labels === false ? '' : 'checked') + ' onchange="_rvApplyStyles({labels:this.checked})"></div>';
  }
  if (nm === 'rect' || nm === 'box' || nm === 'ellipse' || nm === 'triangle') {
    rows += '<div class="dpr"><span>پس‌زمینه</span><input type="checkbox" ' + (st.fill && st.fill.show ? 'checked' : '') + ' onchange="_rvApplyStyles({fill:{show:this.checked,color:\'rgba(45,140,240,.12)\'}})"></div>';
  }
  if (nm === 'simpleAnnotation' || nm === 'simpleTag') {
    rows += '<div class="dpr"><span>متن</span><input type="text" value="' + ((st.text && st.text.text) || '') + '" onchange="_rvApplyStyles({text:{text:this.value}})" placeholder="یادداشت..."></div>';
  }
  if (nm.indexOf('Line') >= 0 || nm === 'segment' || nm === 'rayLine' || nm === 'ruler' || nm === 'arrow') {
    var cs = lineSt.style || 'solid';
    rows += '<div class="dpr"><span>خط</span><select onchange="_rvApplyStyles({line:{style:this.value,dashedValue:this.value===\'dashed\'?[4,3]:this.value===\'dotted\'?[1,2]:[]}})">' +
      '<option value="solid"' + (cs === 'solid' ? ' selected' : '') + '>ممتد</option>' +
      '<option value="dashed"' + (cs === 'dashed' ? ' selected' : '') + '>خط‌چین</option>' +
      '<option value="dotted"' + (cs === 'dotted' ? ' selected' : '') + '>نقطه‌چین</option></select></div>';
  }
  /* v8.5: قرص شناور مثل نهایت‌نگر — رنگ | ضخامت | تنظیمات | حذف | بستن */
  pop.innerHTML = '<div class="draw-popup-inner">' +
    '<div class="draw-pill">' +
    '<input type="color" class="dp-color" title="رنگ" value="' + (lineSt.color || '#2d8cf0') + '" onchange="_rvApplyStyles({line:{color:this.value}})">' +
    '<button type="button" class="dp-width" title="ضخامت" data-w="' + (lineSt.size || 1) + '" onclick="var s=(+this.dataset.w)%5+1;this.dataset.w=s;this.textContent=s+\'px\';_rvApplyStyles({line:{size:s}})">' + (lineSt.size || 1) + 'px</button>' +
    '<button type="button" class="dp-gear" title="تنظیمات بیشتر" onclick="this.closest(\'.draw-popup-inner\').classList.toggle(\'open-settings\')">⚙</button>' +
    '<button type="button" title="حذف همین رسم" onclick="rvDrawDelete()">🗑</button>' +
    '<button type="button" title="بستن" onclick="rvDrawFloatClose()">✕</button>' +
    '</div>' +
    '<div class="draw-popup-body">' + rows + '</div></div>';
}
function rvDrawFloatClose() {
  var p = rvEl('rvDrawFloat');
  if (p) p.style.display = 'none';
  _rvPopOverlayId = null;
}
function rvDrawDelete() {
  var last = _rvPopOverlay();
  if (!last) return;
  try { rv.chart.removeOverlay({ id: last.id }); } catch (e) {}
  rvDrawFloatClose();
  rvSaveOverlays();
  rvToast('رسم حذف شد');
}
/* ردیف‌های چک‌باکسِ سریعِ سطوح (نوار شناور) — از مدلِ جدید */
function rvFibQuickRowsHtml(st) {
  return rvFibNormalizeLevels(st).slice()
    .sort(function (a, b) { return b.coeff - a.coeff; })
    .map(function (L) {
      var ck = L.visible === false ? '' : ' checked';
      return '<label class="dplv"><input type="checkbox"' + ck + ' onchange="rvFibToggleLevel(' + L.coeff + ', this.checked)">' +
        rvFibLevelLabel(L, (st && st.pctMode) || 'coeff') + '</label>';
    }).join('');
}
window.rvFibQuickRowsHtml = rvFibQuickRowsHtml;
function rvFibToggleLevel(key, checked) {
  var last = _rvPopOverlay();
  if (!last) return;
  var levels = rvFibNormalizeLevels(last.styles || {}).slice();
  var c = _rvFibKeyToCoeff(key);
  if (!isFinite(c)) return;
  var hit = null;
  for (var i = 0; i < levels.length; i++) if (_rvFibSame(levels[i].coeff, c)) { hit = levels[i]; break; }
  if (hit) hit.visible = !!checked;
  else levels.push({ coeff: c, color: _rvFibColorOf(c), visible: !!checked });
  _rvSetFibLevels(levels);
}
function rvAttachPopupOnSelect(overlayId) {
  // کلیک روی رسم → باز شدن popup همان رسم
  try {
    rv.chart.overrideOverlay({ id: overlayId, onSelected: function (ctx) {
      if (ctx && ctx.overlay) rvShowDrawFloat(ctx.overlay.id);
    }});
  } catch (e) {}
}
function rvAttachPopupAll() {
  try {
    rv.chart.getOverlays().forEach(function (o) { rvAttachPopupOnSelect(o.id); });
  } catch (e) {}
}
function _rvLastOverlay() {
  if (!rv.chart) return null;
  const overs = rv.chart.getOverlays();
  const arr = overs.filter(o => !(o.isDrawing && o.isDrawing()));
  return arr.length ? arr[arr.length - 1] : null;
}
function rvDrawColor(color) {
  try {
    const last = _rvLastOverlay();
    if (!last) { rvToast('رسمی برای رنگآمیزی نیست'); return; }
    rv.chart.overrideOverlay({
      id: last.id,
      styles: { line: { color: color }, point: { color: color } }
    });
    const dot = rvEl('rvFpColorDot');
    if (dot) dot.style.background = color;
    rvToast('● رنگ خط: ' + color);
  } catch (e) { rvToast('رنگ: ' + (e && e.message)); }
}
function rvDrawWidth(size, btn) {
  try {
    const last = _rvLastOverlay();
    if (!last) { rvToast('رسمی برای ضخیم کردن نیست'); return; }
    rv.chart.overrideOverlay({
      id: last.id,
      styles: { line: { size: size } }
    });
    document.querySelectorAll('#rvFpWidth .rv-fp-w').forEach(b => b.classList.toggle('on', Number(b.dataset.w) === size));
    rvToast('ضخامت خط: ' + size + 'px');
  } catch (e) { rvToast('ضخامت: ' + (e && e.message)); }
}
function rvDrawStyle(style, btn) {
  try {
    const last = _rvLastOverlay();
    if (!last) { rvToast('رسمی برای تغییر سبک نیست'); return; }
    rv.chart.overrideOverlay({
      id: last.id,
      styles: { line: { style: style } }
    });
    document.querySelectorAll('.rv-fp-style').forEach(b => b.classList.toggle('on', b.dataset.style === style));
    rvToast(style === 'solid' ? 'خط ممتد' : 'خط چین');
  } catch (e) { rvToast('سبک: ' + (e && e.message)); }
}

/* ---------- Legend: OHLC + حجم (بالای چارت) ---------- */
function _rvFmtNum(v) {
  if (v === null || v === undefined || isNaN(v)) return '—';
  if (Math.abs(v) >= 1e9) return (v / 1e9).toFixed(2) + 'B';
  if (Math.abs(v) >= 1e6) return (v / 1e6).toFixed(2) + 'M';
  if (Math.abs(v) >= 1e3 && arguments[1] === 'vol') return (v / 1e3).toFixed(2) + 'K';
  return Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
function rvUpdateLegend() {
  if (!rv.data || !rv.data.length) return;
  const c = rv.data[rv.data.length - 1];   // آخرین کندل (بعد از aggregate)
  const up = c.close >= c.open;
  // مهم: innerHTML نه textContent — وگرنه <b> بهصورت رشتهٔ خام رندر میشود
  const set = (id, txt) => { const el = rvEl(id); if (el) el.innerHTML = txt; };
  set('rvLgO', 'باز: <b>' + _rvFmtNum(c.open) + '</b>');
  set('rvLgH', 'سقف: <b>' + _rvFmtNum(c.high) + '</b>');
  set('rvLgL', 'کف: <b>' + _rvFmtNum(c.low) + '</b>');
  set('rvLgC', ((rv._seriesField === 'last') ? 'آخرین: ' : 'پایانی: ')
      + '<b>' + _rvFmtNum(c.close) + '</b>');
  set('rvLgV', 'حجم: <b>' + _rvFmtNum(c.volume, 'vol') + '</b>');
  const cls = up ? 'up' : 'down';
  ['rvLgO', 'rvLgH', 'rvLgL', 'rvLgC'].forEach(id => {
    const el = rvEl(id);
    if (el) el.classList.remove('up', 'down');
  });
  ['rvLgO', 'rvLgH', 'rvLgL', 'rvLgC'].forEach(id => {
    const el = rvEl(id);
    if (el) el.classList.add(cls);
  });
}

/* ---------- AutoSave: ذخیره‌ی خودکار (نمایش زمان آخرین ذخیره در toast) ---------- */

/* ---------- فونت (سبک منو) ---------- */

/* ---------- تم (روشن/تاریک فقط چارت — جدا از تم برنامه، مثل رهاورد) ---------- */
function rvApplyTheme() {
  // v7.3.11 — TV-parity dark قفل (پالت رسمی TradingView)
  if (!rv.chart) return;
  // v8.1 — تم روشن/تاریک واقعی (روشن با پالت نهایت‌نگر)
  var _th = 'dark'; try { _th = stGet('techChartTheme', 'dark') || 'dark'; } catch (e) {}
  var T = (_th === 'light')
    ? { bg: '#ffffff', grid: '#f0f3fa', border: '#e0e3eb', scale: '#4a4b52', txt: '#131722', cross: '#9598a1',
        up: '#089981', down: '#f23645' }
    : { bg: '#0d1117', grid: 'rgba(255,255,255,0.04)', border: 'rgba(139,148,158,0.28)', scale: '#8b949e', txt: '#c9d1d9', cross: 'rgba(139,148,158,0.75)',
        up: '#10b981', down: '#f43f5e' };
  try {
    var box = rvEl('rvChartBox');
    if (box) { box.classList.add(_th === 'light' ? 'theme-light' : 'theme-dark'); box.classList.remove(_th === 'light' ? 'theme-dark' : 'theme-light'); }
    document.documentElement.setAttribute('data-chart-theme', _th);
  } catch (e) {}
  rv.chart.setStyles({
    grid: { horizontal: { color: T.grid, style: 'solid', show: true }, vertical: { color: T.grid, style: 'solid', show: false } },
    xAxis: { axisLine: { color: T.border }, tickLine: { color: T.border }, tickText: { color: T.scale, size: 12 } },
    yAxis: { axisLine: { color: T.border }, tickLine: { color: T.border }, tickText: { color: T.scale, size: 12 } },
    crosshair: {
      horizontal: { line: { color: T.cross, style: 'dashed', size: 1, dashedValue: [4, 3] },
                    text: { backgroundColor: T.bg, borderColor: T.cross, color: T.txt } },
      vertical:   { line: { color: T.cross, style: 'dashed', size: 1, dashedValue: [4, 3] },
                    text: { backgroundColor: T.bg, borderColor: T.cross, color: T.txt } } },
    separator: { color: T.border, size: 1 },
    candle: { type: 'candle_solid',
              bar: { upColor: T.up, downColor: T.down, noChangeColor: '#868993',
                     upBorderColor: T.up, downBorderColor: T.down, noChangeBorderColor: '#868993',
                     upWickColor: T.up, downWickColor: T.down, noChangeWickColor: '#868993' },
              priceMark: { high: { show: false }, low: { show: false }, last: { show: true } } },
    indicator: { tooltip: { title: { color: T.scale }, legend: { color: T.scale } } }
  });
  try {
    var vols = rv.chart.getIndicators({ name: 'VOL' });
    if (vols && vols.length) vols[0].setStyles({
      bars: [{ key: 'volume', baseKey: 'open', type: 'bar', style: 'bar',
               color: function (d) { return d && d.close >= d.open ? 'rgba(16,185,129,.55)' : 'rgba(244,63,94,.55)'; } }],
      tooltip: { title: { color: T.scale }, legend: { color: T.scale } } });
  } catch (e) {}
  /* v10.1 — رنگ خطوط MA استاندارد FTS با تم چارت هم‌آهنگ شود؛ در تم روشن
     تون رنگ‌های تیره تا روی سفید خوانا بمانند. چیپ‌های سربرگ هم از همین متغیرهای CSS
     رنگ می‌گیرند. */
  var MA_C = (_th === 'light')
    ? ['#2563eb', '#b45309', '#7c3aed']
    : ['#38bdf8', '#f59e0b', '#a78bfa'];
  try {
    var mas = rv.chart.getIndicators({ name: 'MA' });
    if (mas && mas.length) mas[0].setStyles({
      lines: [
        { color: MA_C[0], size: 1, style: 'solid' },
        { color: MA_C[1], size: 1, style: 'solid' },
        { color: MA_C[2], size: 1, style: 'solid' }
      ],
      tooltip: { showRule: 'none' }
    });
  } catch (e) {}
  try {
    document.documentElement.style.setProperty('--rv-ma-c1', MA_C[0]);
    document.documentElement.style.setProperty('--rv-ma-c2', MA_C[1]);
    document.documentElement.style.setProperty('--rv-ma-c3', MA_C[2]);
  } catch (e) {}
  var el = rvEl('rvMainChart');
  if (el) { el.style.background = T.bg; el.style.color = T.txt; }
  try { document.documentElement.style.setProperty('--rv-chart-bg', T.bg); } catch (e) {}
  /* v9.7.6 — ارتفاع محور زمان ۲۸px (پنل x_axis در v10 از setPaneOptions اندازه می‌گیرد) */
  try { rv.chart.setPaneOptions({ id: 'x_axis_pane', height: 28, minHeight: 28, dragEnabled: false }); } catch (e) {}
  /* جاروب تیره‌سازی اجباری: هر div/canvas داخلی با بک‌گراند روشن/خاکستری */
  try { rvDarkSweep(el, T); } catch (e) {}
}
function rvToggleChartTheme() {
  var theme = 'dark';
  try { theme = stGet('techChartTheme', 'dark'); } catch (e) {}
  theme = (theme === 'dark') ? 'light' : 'dark';
  try { stSet('techChartTheme', theme); } catch (e) {}
  rvApplyTheme();
  rvToast(theme === 'dark' ? '🌙 تم چارت: تاریک' : '☀️ تم چارت: روشن');
}

/* ---------- اندیکاتورها: پنل با لیست کامل KLineChart + حذف ---------- */
var rvIndsAdded = [];
var RTV_IND_LIST = ['MA', 'EMA', 'SMA', 'BOLL', 'SAR', 'CCI', 'DMI', 'OBV', 'PVT', 'KDJ', 'WR', 'ROC', 'BIAS', 'MACD', 'RSI', 'VOL', 'AO', 'AVP', 'BBIS', 'BRAR', 'CR', 'DMA', 'EMV', 'MTM', 'PSY', 'TRIX', 'VR'];
/* ---------- v9.7.2 — پیش‌فرض‌های اندیکاتور بر پایهٔ تایم‌فریم ----------
   RSI با دورهٔ ۱۴ روی کندل هفتگی خیلی کند است (۱۴ هفته ≈ ۳ ماه)، پس روی
   هفتگی ۷ می‌نشیند و روی روزانه همان ۱۴ می‌ماند. ماهانه عمداً ۱۴ مانده
   چون برای آن تایم‌فریم خواسته‌ای مطرح نشده بود — تغییرش حدس می‌بود.
   EMA و BOLL هم پیش‌فرض کتابخانه (EMA=[6,12,20] و BOLL=[20,2]) را override
   می‌کنند تا با استراتژی ترمینال هم‌راستا بمانند. */
var RTV_IND_DEFAULTS = {
  /* v10.1 — پنجره‌های MA استاندارد FTS در همه‌ٔ تایم‌فریم‌ها ثابت: MA14 تریلینگ استاپ لایه‌۱ موتور خروج است. */
  MA:   { fixed: [14, 52, 100] },
  EMA:  { fixed: [20, 50, 200] },
  BOLL: { fixed: [20, 2] },
  RSI:  { byItv: { D: 14, W: 7, M: 14 } }
};

/* پارامتر محاسبهٔ یک اندیکاتور برای تایم‌فریم فعلی؛ null یعنی دست نخورد. */
function rvIndParams(name) {
  var d = RTV_IND_DEFAULTS[name];
  if (!d) return null;
  if (d.byItv) {
    var p = d.byItv[(rv && rv.itv) || 'D'];
    if (p == null) p = d.byItv.D;
    return [p];
  }
  return d.fixed.slice();
}

/* بعد از سوییچ تایم‌فریم، دورهٔ اندیکاتورهای ازقبل‌ساخته بازاعمال می‌شود.
   بدون این، RSI که در حالت روزانه افزوده شده با همان ۱۴ روی هفتگی می‌ماند.
   rvIndsAdded تنها مرجع «افزوده‌شده‌ها» است و getIndicators راستی‌آزمایی
   می‌کند که پن واقعاً هنوز وجود دارد (rvRerender پن‌ها را حذف نمی‌کند). */
function rvIndSyncParams() {
  if (!rv.chart || typeof rv.chart.overrideIndicator !== 'function') return;
  rvIndsAdded.slice().forEach(function (n) {
    var cp = rvIndParams(n);
    if (!cp) return;
    try {
      var live = rv.chart.getIndicators({ name: n });
      if (!live || !live.length) return;
      if (String(live[0].calcParams) === String(cp)) return;   // بی‌تغییر => بی‌عمل
      rv.chart.overrideIndicator({ name: n, calcParams: cp });
    } catch (e) {}
  });
}

function rvToggleIndPanel() {
  const p = rvEl('rvIndPanel');
  if (!p) return;
  if (p.style.display === 'block') { p.style.display = 'none'; return; }
  if (!p.dataset.built) {
    // v7.3 — منوی نهایت‌نگر-style: دسته‌بندی + فارسی
    const CATS = [
      { title: '📏 میانگین متحرک', items: [['MA','Simple MA'],['EMA','Exponential MA'],['SMA','Smoothed MA'],['WMA','Weighted MA'],['DEMA','Double EMA'],['TEMA','Triple EMA'],['VWAP','VWAP']] },
      { title: '🌊 نوسان‌سنج', items: [['RSI','Relative Strength'],['KDJ','Stochastic'],['WR','Williams %R'],['CCI','Commodity Channel'],['ROC','Rate of Change'],['MTM','Momentum'],['AO','Awesome Osc'],['PSY','Psychological']] },
      { title: '📈 روند/باند', items: [['MACD','MACD'],['BOLL','Bollinger Bands'],['SAR','Parabolic SAR'],['DMI','Directional Mov'],['DMA','Different MA'],['TRIX','TRIX'],['EMV','Ease of Movement'],['PVT','Price Volume Trend'],['OBV','On Balance Vol'],['BRAR','BR/AR'],['CR','CR Indicator'],['VR','Volume Ratio'],['BIAS','BIAS'],['AVP','Avg Price'],['BBIS','Bollinger Width']] },
      { title: '📊 حجم', items: [['VOL','Volume']] },
    ];
    let html = '';
    CATS.forEach(cat => {
      html += `<div style="padding:6px 8px 2px; font-size:10px; color:var(--text-muted); border-bottom:1px solid var(--border-color);">${cat.title}</div>`;
      html += '<div style="display:flex;flex-wrap:wrap;gap:4px;padding:6px 8px;">';
      cat.items.forEach(([n, fa]) => {
        html += `<button class="rv-ind-add" style="font-size:10.5px; padding:4px 8px;" onclick="rvIndToggle('${n}')" id="indbtn_${n}" title="${fa}">${n}</button>`;
      });
      html += '</div>';
    });
    html += '<div style="padding:0 8px 8px;"><button class="rv-ind-add" style="background:rgba(244,63,94,.2); color:#f43f5e;" onclick="rvIndsRemoveAll()">✖ حذف همهٔ اندیکاتورها</button></div>';
    p.innerHTML = html;
    p.dataset.built = '1';
  }
  /* v9.7.6 — وضعیت دکمه‌ها با اندیکاتورهای واقعاً روی چارت همگام شود
     (MA و VOL پیش‌فرض در rvIndsAdded نیستند؛ بدون این، دکمه‌شان خاموش
     می‌درخشید در حالی که خط روی چارت فعال بود). */
  try {
    var live = (rv.chart ? (rv.chart.getIndicators({}) || []) : []).map(function (k) { return k.name; });
    document.querySelectorAll('#rvIndPanel .rv-ind-add').forEach(function (btn) {
      var nm = String(btn.id || '').replace('indbtn_', '');
      var on = live.indexOf(nm) >= 0 || rvIndsAdded.indexOf(nm) >= 0;
      btn.style.background = on ? 'var(--accent-blue)' : '';
      btn.style.color = on ? '#000' : '';
    });
  } catch (e) {}
  p.style.display = 'block';
}
function rvIndToggle(name) {
  if (!rv.chart) return;
  /* v9.7.6 — MA پیش‌فرض روی پن کندل ساخته می‌شود ولی در rvIndsAdded ثبت نشده
     (دوره‌اش ثابت و هم‌پنجره‌های /api/ma است). کلیک روی MA در این پنل باید همان
     خط را خاموش کند؛ قبلاً چون «پیگیری‌شده» نبود به شاخهٔ افزودن می‌رفت و
     createIndicator اندیکاتور دوم می‌ساخت یا null برمی‌گرداند. اگر روی چارت
     زنده است ولی پیگیری نشده، اول به فهرست اضافه‌اش کن تا شاخهٔ حذف اجرا شود. */
  try {
    if (rvIndsAdded.indexOf(name) < 0 && (rv.chart.getIndicators({ name: name }) || []).length) rvIndsAdded.push(name);
  } catch (e) {}
  const i = rvIndsAdded.indexOf(name);
  try {
    if (i >= 0) {
      rv.chart.removeIndicator({ name: name });
      rvIndsAdded.splice(i, 1);
    } else {
      var spec = { name: name, id: 'ind_' + name, isStack: false };
      var cp = rvIndParams(name);
      if (cp) spec.calcParams = cp;   // v9.7.2 — دورهٔ پیش‌فرض بر پایهٔ تایم‌فریم
      var r = rv.chart.createIndicator(spec);
      if (!r) { rvToast('اندیکاتور «' + name + '» در دسترس نیست'); return; }
      rvIndsAdded.push(name);
    }
  } catch (e) { rvToast('اندیکاتور ' + name + ': ' + e.message); }
  // v8.6: بعد از افزودن/حذف پن، چارت rebalance شود تا محور زمان از دید خارج نشود
  try { rv.chart.resize(); } catch (e2) {}
  if (typeof rvSyncPaneCloseBtns === 'function') setTimeout(rvSyncPaneCloseBtns, 350);
  const btn = rvEl('indbtn_' + name);
  if (btn) {
    const on = rvIndsAdded.indexOf(name) >= 0;
    btn.style.background = on ? 'var(--accent-blue)' : '';
    btn.style.color = on ? '#000' : '';
  }
}
function rvIndsRemoveAll() {
  if (!rv.chart) return;
  try {
    rvIndsAdded.slice().forEach(n => {
      try { rv.chart.removeIndicator({ name: n }); } catch (e) {}
    });
    rvIndsAdded = [];
  } catch (e) {}
  document.querySelectorAll('#rvIndPanel .rv-ind-add').forEach(btn => { btn.style.background = ''; btn.style.color = ''; });
  rvToast('همهٔ اندیکاتورها حذف شدند');
}

/* ---------- منوی تایم فریم (D/W/M) ---------- */
function rvSetItv(itv, btn) {
  rv.itv = itv;
  document.querySelectorAll('#rvItvMenu [data-itv]').forEach(b => b.classList.toggle('itv-on', b.dataset.itv === itv));
  const bmain = rvEl('rvItvBtn');
  if (bmain) bmain.textContent = itv;
  const m = rvEl('rvItvMenu');
  if (m) m.style.display = 'none';
  if (rv.sym) rvLoad(rv.sym);
  rvToast('تایم فریم: ' + (itv === 'D' ? 'روزانه' : itv === 'W' ? 'هفتگی' : 'ماهانه'));
}

// v8.6 — resize چارت بعد از سوییچ به تب تکنیکال (وگرنه canvas با سایز قدیمی میماند و محور زمان گم میشد)
(function () {
  var _orig = window.switchView;
  if (typeof _orig !== 'function' || _orig.__rvResized) return;
  window.switchView = function (v, btn) {
    var r = _orig.apply(this, arguments);
    if (v === 'tech' && rv && rv.chart) { [80, 500, 1500, 3000, 5000].forEach(function (d) { setTimeout(function () { try { rv.chart.resize(); } catch (e) {} try { rvApplyTheme(); } catch (e) {} try { rvRenderTimeStrip(); } catch (e) {} try { if (typeof rvSyncPaneCloseBtns === 'function') rvSyncPaneCloseBtns(); } catch (e) {} }, d); }); }
    return r;
  };
  window.switchView.__rvResized = true;
})();

// v8.7 — نوار تاریخ شمسی پایین چارت (کانوس axis در این build خالی رندر میشود → استریپ DOM)
function rvRenderTimeStrip() {
  try {
    const box = rvEl('rvChartBox');
    const el = rvEl('rvMainChart');
    if (!box || !el) return;
    let strip = document.getElementById('rvTimeAxis');
    if (!strip) {
      strip = document.createElement('div');
      strip.id = 'rvTimeAxis';
      box.appendChild(strip);
    }
    const d = (rv && rv.data) ? rv.data : [];
    if (!d.length) { strip.innerHTML = ''; return; }
    const n = d.length;
    const slots = Math.min(7, n);
    let html = '';
    for (let k = 0; k < slots; k++) {
      const i = Math.round(k * (n - 1) / Math.max(1, slots - 1));
      const dt = new Date(d[i].timestamp);
      const j = rvToJalaali(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
      const txt = j.jy + '/' + String(j.jm).padStart(2, '0') + '/' + String(j.jd).padStart(2, '0');
      html += '<span style="left:' + (k / Math.max(1, slots - 1) * 100).toFixed(2) + '%">' + txt + '</span>';
    }
    strip.innerHTML = html;
  } catch (e) {}
}
window.rvRenderTimeStrip = rvRenderTimeStrip;

/* ---------- اینت ---------- */
function rvInit() {
  // چارت با data-ready ساخته میشود؛ نه زودتر (reg با دادهٔ خالی رندر را قفل میکند)
  const last = (typeof stGet === 'function') ? stGet('tech_last', '') : '';
  rvAutoLevelsInit();
  rvRailInit();
  try { rvCalEventsInit(); } catch (e) {}   // v9.7.6 — وضعیت دکمهٔ 📅 رویدادها
  rvLoad(rv.sym || last || 'خساپا');
}

/* ---------- تنظیمات URL ?open=SYM&interval=D|W|M&adjust=1&scale=log (پشتیبانی) ---------- */
function rvSetInterval(iv) {
  if (iv !== 'D' && iv !== 'W' && iv !== 'M') return;
  rv.itv = iv;
  if (rv.sym) rvLoad(rv.sym);
}
function rvSetAdjust(on) {
  rv.adj = on ? 1 : 0;
  if (rv.sym) rvLoad(rv.sym);
}
function rvSetScale(mode) {
  /* v9.7.1 — باگ: قبلاً rv.logScale ست می‌شد و rvToggleLog() همان را بلافاصله
     معکوس می‌کرد؛ پس ?scale=log مقیاس «خطی» و ?scale=linear مقیاس «لگاریتمی»
     می‌داد (دقیقاً برعکسِ خواسته). حالا به مسیر معتبر tech_365 واگذار می‌شود:
     btsSet.scales.axis ست و ذخیره می‌گردد و btsApplySettings — که با
     btsHook('rvApplyStyles') به ساخت چارت بند است — آن را با overrideYAxis
     روی پنل کندل اعمال و با getYAxes راستی‌آزمایی می‌کند. */
  const name = (mode === 'log' || mode === 'logarithm') ? 'logarithm'
             : (mode === 'pct' || mode === 'percentage') ? 'percentage' : 'normal';
  const kind = name === 'logarithm' ? 'log' : (name === 'percentage' ? 'pct' : 'auto');
  try {
    if (typeof btsSet !== 'undefined' && btsSet && btsSet.scales) {
      btsSet.scales.axis = name;
      if (typeof btsSaveSettings === 'function') btsSaveSettings(btsSet);
    }
  } catch (e) {}
  rv.logScale = (name === 'logarithm');
  if (rv.chart && typeof btsSetScale === 'function') { btsSetScale(kind); return; }
  /* چارت هنوز ساخته نشده: مقدار ذخیره‌شده هنگام ساخت چارت اعمال می‌شود */
  try { if (typeof btsSyncScaleBtns === 'function') btsSyncScaleBtns(); } catch (e) {}
}


/* ---------- v9.7.6 — جاروب تم تیره: خنثی‌سازی بک‌گراند روشن/خاکستری لایه‌های داخلی ---------- */
function rvDarkSweep(root, T) {
  try {
    if (!root) return;
    var bg = (T && T.bg) || '#0d1117';
    root.querySelectorAll('div,canvas').forEach(function (n) {
      var c = getComputedStyle(n).backgroundColor || '';
      var m = /rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/.exec(c);
      if (!m) return;
      var a = (m[4] === undefined) ? 1 : parseFloat(m[4]);
      if (a <= 0.02) return;                    // شفاف →pane از ظرف رنگ می‌گیرد
      var lum = 0.2126 * (+m[1]) + 0.7152 * (+m[2]) + 0.0722 * (+m[3]);
      if (lum > 30) n.style.setProperty('background', bg, 'important');
    });
  } catch (e) {}
}

/* ---------- v9.7.6 — زوم چرخ‌ماوس نرخ‌محدود با rAF (رفع فریز اسکرول) ----------
   هندلر در فاز capture روی ظرف چارت نصب می‌شود: پیش از هندلر داخلی klinecharts
   اجرا، preventDefault می‌کند (صفحه زیر چارت اسکرول نمی‌شود) و انباشت deltaY را
   حداکثر یک‌بار در هر فریم به zoomAtCoordinate تبدیل می‌کند. */
function rvInstallWheelZoom(el) {
  if (!el || el._rvWheelZoom) return;
  el._rvWheelZoom = 1;
  var acc = 0, raf = 0, cx = 0, cy = 0;
  el.addEventListener('wheel', function (ev) {
    if (!rv.chart) return;
    ev.preventDefault();
    ev.stopPropagation();
    var r = el.getBoundingClientRect();
    cx = ev.clientX - r.left; cy = ev.clientY - r.top;
    acc += ev.deltaY;
    if (raf) return;
    raf = requestAnimationFrame(function () {
      raf = 0;
      var d = acc; acc = 0;
      if (!d || !rv.chart) return;
      var f = Math.exp(-d * 0.0016);            // zوم نمایی نرم؛ سقف‌دار ضدپرش
      if (f > 1.6) f = 1.6; else if (f < 0.62) f = 0.62;
      try { rv.chart.zoomAtCoordinate(f, { x: cx, y: cy }); } catch (e) {}
    });
  }, { passive: false, capture: true });
}

/* ---------- v9.7.6 — ResizeObserver: رفع اندازه‌ماندن canvas هنگام مخفی/ظاهر ----------
   v9.7.8 — ناظر روی خودِ باکس #rvChartBox هم نصب می‌شود؛ تغییر اندازهٔ بوم یا
   باکس (کانتینر یکتای چارت) یک reflow نرخ‌محدود (۶۰ms) می‌زند. */
function rvAttachResize(el, box) {
  box = box || rvEl('rvChartBox');
  if (!el || typeof ResizeObserver === 'undefined' || el._rvRO) return;
  el._rvRO = 1;
  var lastW = 0, lastH = 0, t = 0;
  var ro = new ResizeObserver(function () {
    clearTimeout(t);
    t = setTimeout(function () {
      if (!rv.chart) return;
      var w = el.clientWidth || (box ? box.clientWidth : 0);
      var h = el.clientHeight || (box ? box.clientHeight : 0);
      if (!w || !h) return;                     // مخفی است — صبر کن تا ظاهر شود
      if (w === lastW && h === lastH) return;
      lastW = w; lastH = h;
      try { rv.chart.resize(); } catch (e) {}
      try { rvApplyTheme(); } catch (e) {}
      try { rvRenderTimeStrip(); } catch (e) {}
    }, 60);
  });
  ro.observe(el);
  try { if (box && box !== el) ro.observe(box); } catch (e) {}
}

window.addEventListener('resize', () => { if (rv.chart) rv.chart.resize(); });

/* ═════════ v9.7.6 — رویدادهای تقویم روی چارت (📅) + پل تقویم ↔ نمودار ═════════
   داده از  GET /api/ma/<sym>  می‌آید:  events:[{date, ts, title, cat}, …]
   ts = «ظهر UTC» همان روز = دقیقاً مبنای timestamp کندل‌ها (توضیح خط ۶۱)، پس
   مارکر روی میلهٔ درست می‌نشیند و آف‌ست تقویمی ندارد.

   مارکر = overlay سفارشی «calEventMark» با id = auto_calev_<barTs>_<i>.
   پیشوند auto_ باعث می‌شود rvIsDecoration() آنها را «دکوراسیون» بداند:
     • داخل بلاوب رسم‌های نماد (tech_<sym>) ذخیره/بازیابی نمی‌شوند (تکراری نمی‌شوند)
     • با «حذف آخرین رسم» و «پاک‌کردن رسم‌ها» پاک نمی‌شوند
     • در rvRerender() بعد از removeOverlay() از روی همین کش بازساخته می‌شوند
   hover → تولتیپِ کاملِ رویداد، click → اسکرول به همان روز.
   دکمهٔ 📅 در هدر چارت روشن/خاموش است (کلید tech_cal_events). */
var RV_CAL_CATS = {
  assembly:        { c: '#f59e0b', ch: 'م', fa: 'مجمع عادی' },
  assemblyExtra:   { c: '#fb923c', ch: 'ف', fa: 'مجمع فوق‌العاده' },
  assemblyChange:  { c: '#a78bfa', ch: 'ل', fa: 'لغو/تغییر مجمع' },
  dividend:        { c: '#10b981', ch: 'س', fa: 'پرداخت سود نقدی (DPS)' },
  capitalIncrease: { c: '#38bdf8', ch: 'ا', fa: 'افزایش سرمایه' },
  ipo:             { c: '#f43f5e', ch: 'ع', fa: 'عرضهٔ اولیه' },
  bondMaturity:    { c: '#eab308', ch: 'د', fa: 'سررسید اوراق' },
  other:           { c: '#8b949e', ch: 'ر', fa: 'رویداد' }
};
function rvCalCat(cat) { return RV_CAL_CATS[cat] || RV_CAL_CATS.other; }

var rvCalMarks = { on: true, ids: [], list: null, sym: null, busy: false, mx: 0, my: 0, pop: null, timer: 0 };
var rvCalPending = null;   // { sym, ts } — درخواست «برو به این تاریخ» از تب تقویم

function _rvFaD(x) { return String(x).replace(/\d/g, function (d) { return '۰۱۲۳۴۵۶۷۸۹'[+d]; }); }
function _rvCalEsc(s) {
  return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
  });
}
function _rvCalFaDate(ts) {
  try {
    var d = new Date(+ts), j = rvToJalaali(d.getUTCFullYear(), d.getUTCMonth() + 1, d.getUTCDate());
    return _rvFaD(j.jy + '/' + ('0' + j.jm).slice(-2) + '/' + ('0' + j.jd).slice(-2));
  } catch (e) { return ''; }
}

/* ---------- ثبت overlay مارکر (registerOverlay خودش نسخهٔ قبلی را replace می‌کند) ---------- */
try {
  if (window.klinecharts && klinecharts.registerOverlay) {
    klinecharts.registerOverlay({
      name: 'calEventMark',
      totalStep: 2,                    // تک‌نقطه‌ای: قاعدهٔ کتابخانه = تعداد نقطه + ۱
      lock: true,                      // قابل درگ/جابه‌جایی نیست (داده‌محور است)
      needDefaultPointFigure: false,   // نقطهٔ پیش‌فرض (دایرهٔ آبی) نمی‌خواهیم
      createPointFigures: function (ev) {
        var cs = ev.coordinates || [];
        if (!cs.length) return [];
        var x = Math.round(cs[0].x), y = cs[0].y;
        var cal = ((ev.overlay && ev.overlay.styles) || {}).cal || {};
        var col = cal.c || '#8b949e', cy = y - 16, r = 7.5, f = [];
        if (cal.hi) f.push({ type: 'circle', attrs: { x: x, y: cy, r: r + 3.5 },
          styles: { style: 'stroke', color: '#ffffff', borderSize: 1.5, style1: 'dashed' } });
        f.push({ type: 'line', attrs: { coordinates: [{ x: x, y: y - 3 }, { x: x, y: cy + r - 1 }] },
          styles: { color: col, size: 1, style: 'solid' } });
        f.push({ type: 'circle', attrs: { x: x, y: cy, r: r },
          styles: { style: 'fill', color: col, borderSize: 1, borderColor: 'rgba(0,0,0,.5)' } });
        f.push({ type: 'text', attrs: { x: x, y: cy, text: cal.label || 'ر', align: 'center', baseline: 'middle' },
          styles: { style: 'fill', color: '#0b0f14', size: 10, weight: 'bold',
                    family: 'Vazirmatn, sans-serif', backgroundColor: 'transparent', borderColor: 'transparent' } });
        return f;
      },
      onMouseEnter: function (ev) { try { rvCalTipShow(ev && ev.overlay); } catch (e) {} },
      onMouseLeave: function () { try { rvCalTipHide(); } catch (e) {} },
      onClick: function (ev) { try { rvCalMarkClick(ev && ev.overlay); } catch (e) {} }
    });
  }
} catch (e) {}

/* ---------- نزدیک‌ترین میله به timestamp رویداد (binary search روی rv.data) ----------
   «بزرگ‌ترین tsِ ≤ رویداد»: در تایم‌فریم هفتگی/ماهانه کلیدِ میله شنبهٔ هفته یا
   اول‌ماه است و از روزِ رویداد کوچک‌تر، پس دقیقاً میلهٔ بازهٔ شاملِ آن روز
   برمی‌گردد. بیرونِ بازهٔ داده (بیش از ۴۵ روز فاصله از دو سر) → ‎-1 و آن
   رویداد رسم نمی‌شود (مارکر معلق بیرون چارت، گمراه‌کننده است). */
function _rvCalBarIndex(ts) {
  var d = rv.data || []; ts = +ts || 0;
  if (!d.length || !ts) return -1;
  var TOL = 45 * 864e5;
  if (ts < d[0].timestamp) return (d[0].timestamp - ts <= TOL) ? 0 : -1;
  var lo = 0, hi = d.length - 1;
  while (lo < hi) { var mid = (lo + hi + 1) >> 1; if (d[mid].timestamp <= ts) lo = mid; else hi = mid - 1; }
  return (ts - d[lo].timestamp > TOL) ? -1 : lo;
}

/* ---------- واکشی رویدادها از /api/ma/<sym> ---------- */
async function rvCalFetchEvents(sym) {
  var ctl = null;
  try { ctl = new AbortController(); setTimeout(function () { try { ctl.abort(); } catch (e) {} }, 12000); } catch (e) {}
  var r = await fetch('/api/ma/' + encodeURIComponent(sym) + '?days=730',
    { cache: 'no-store', signal: ctl ? ctl.signal : undefined });
  if (!r.ok) throw new Error('HTTP ' + r.status);
  var j = await r.json();
  if (!j || j.status !== 'ok') throw new Error((j && j.status) || 'payload نامعتبر');
  return Array.isArray(j.events) ? j.events : [];
}

/* ---------- پاک‌کردن مارکرهای فعلی (فقط id های خودمان) ---------- */
function rvCalClearMarks() {
  try {
    if (rv.chart) rvCalMarks.ids.forEach(function (id) { try { rv.chart.removeOverlay({ id: id }); } catch (e) {} });
  } catch (e) {}
  rvCalMarks.ids = [];
  rvCalTipHide();
}

/* ---------- ساختِ مارکرها از کش (بدون شبکه) — چند رویدادِ یک روز = یک مارکر ---------- */
function rvCalDrawMarks() {
  if (!rv.chart || rvCalMarks.sym !== rv.sym) return;   // نتیجهٔ کهنهٔ نماد قبلی
  rvCalClearMarks();
  var list = rvCalMarks.list || [], d = rv.data || [];
  if (!rvCalMarks.on || !list.length || !d.length) { rvCalSyncBtn(); return; }
  var groups = {}, n = 0;
  list.forEach(function (ev) {
    var i = _rvCalBarIndex(ev && ev.ts);
    if (i < 0) return;
    var k = d[i].timestamp;
    if (!groups[k]) groups[k] = { bar: d[i], evs: [] };
    groups[k].evs.push(ev);
  });
  Object.keys(groups).forEach(function (k) {
    var g = groups[k], first = rvCalCat(g.evs[0].cat), multi = g.evs.length > 1;
    var id = 'auto_calev_' + k + '_' + (n++);
    var title = multi
      ? (first.fa + ' و ' + _rvFaD(g.evs.length - 1) + ' رویداد دیگر در این روز')
      : String(g.evs[0].title || first.fa);
    try {
      rv.chart.createOverlay({
        id: id, name: 'calEventMark', paneId: 'candle_pane', groupId: 'cal_events',
        zLevel: 12, points: [{ timestamp: k, value: g.bar.high }],
        styles: { cal: { c: first.c, label: multi ? '✚' : first.ch, title: title, ts: +k, items: g.evs } }
      });
      rvCalMarks.ids.push(id);
    } catch (e) {}
  });
  rvCalSyncBtn();
}

/* ---------- ورودیِ اصلی: (با کش کار کن، در صورت نیاز یک‌بار fetch) ---------- */
async function rvApplyEventMarks(force) {
  if (!rv.chart || !rv.sym) return;
  rvCalTipHide();
  if (!rvCalMarks.on) { rvCalClearMarks(); rvCalSyncBtn(); return; }
  var sym = rv.sym;
  if (!force && rvCalMarks.sym === sym && rvCalMarks.list) { rvCalDrawMarks(); return; }
  if (rvCalMarks.busy) return;                       // یک واکشی هم‌زمان کافی است
  rvCalMarks.busy = true;
  var evs = null, err = null;
  try { evs = await rvCalFetchEvents(sym); } catch (e) { err = e; }
  rvCalMarks.busy = false;
  if (rv.sym !== sym) return;                        // نماد عوض شده → نتیجه بی‌اعتبار
  if (err) { rvCalSyncBtn(); return; }               // بی‌صدا؛ چارت نباید با رویداد بخوابد
  rvCalMarks.sym = sym; rvCalMarks.list = evs;
  rvCalDrawMarks();
}

/* ---------- تولتیپِ شناورِ رویداد (hover روی مارکر) ----------
   pointer-events:none → با عبور موس ناپدید نمی‌شود؛ جای it از mousemove خودِ
   صفحه گرفته می‌شود (رخدادِ overlay مختصاتِ موس نمی‌دهد). */
function rvCalTipEl() {
  if (rvCalMarks.pop && document.body.contains(rvCalMarks.pop)) return rvCalMarks.pop;
  var el = document.createElement('div');
  el.id = 'rvCalTip'; el.setAttribute('dir', 'rtl');
  el.style.cssText = 'position:fixed;z-index:9998;display:none;max-width:300px;background:#151b28;' +
    'color:#e6ebf5;border:1px solid #2f3a52;border-left:3px solid #38bdf8;border-radius:8px;padding:7px 10px;' +
    'font:11.5px/1.75 Vazirmatn,sans-serif;box-shadow:0 10px 26px rgba(0,0,0,.55);pointer-events:none;direction:rtl;';
  document.body.appendChild(el);
  rvCalMarks.pop = el;
  return el;
}
function rvCalTipShow(ov) {
  var cal = ov && ov.styles && ov.styles.cal;
  if (!cal) return;
  var items = cal.items || [];
  var rows = items.slice(0, 6).map(function (e) {
    var c = rvCalCat(e.cat);
    return '<div style="display:flex;gap:6px;align-items:baseline">' +
      '<span style="color:' + c.c + '">●</span><b style="font-weight:600">' + _rvCalEsc(c.fa) + '</b>' +
      '<span style="color:#a9b8d4;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + _rvCalEsc(e.title || '') + '</span>' +
      '<span style="margin-right:auto;color:#7d8aa5">' + _rvCalFaDate(e.ts) + '</span></div>';
  }).join('');
  var more = items.length > 6 ? '<div style="color:#7d8aa5">+ ' + _rvFaD(items.length - 6) + ' رویداد دیگر…</div>' : '';
  var el = rvCalTipEl();
  el.style.borderLeftColor = cal.c || '#38bdf8';
  el.innerHTML = '<div style="font-weight:700">' + _rvCalEsc(cal.title || '') +
    ' <span style="color:#7d8aa5;font-weight:400">' + _rvCalFaDate(cal.ts) + '</span></div>' + rows + more +
    '<div style="color:#5f6c85;margin-top:3px">کلیک = برو به این تاریخ</div>';
  el.style.display = 'block';
  rvCalTipMove();
}
function rvCalTipMove() {
  var el = rvCalMarks.pop;
  if (!el || el.style.display !== 'block') return;
  var w = el.offsetWidth || 240, h = el.offsetHeight || 70;
  var x = rvCalMarks.mx + 16, y = rvCalMarks.my + 18;
  if (x + w > window.innerWidth - 8) x = rvCalMarks.mx - w - 16;
  if (y + h > window.innerHeight - 8) y = rvCalMarks.my - h - 18;
  el.style.left = Math.max(6, x) + 'px';
  el.style.top = Math.max(6, y) + 'px';
}
function rvCalTipHide() { if (rvCalMarks.pop) rvCalMarks.pop.style.display = 'none'; }
try {
  document.addEventListener('mousemove', function (e) {
    rvCalMarks.mx = e.clientX; rvCalMarks.my = e.clientY;
    if (rvCalMarks.pop && rvCalMarks.pop.style.display === 'block') rvCalTipMove();
  }, { passive: true });
} catch (e) {}

/* ---------- flash: emphasisِ موقتِ یک روز (overlay عمودیِ محو شونده) ----------
   overrideOverlay برای تغییر رنگ به‌کار نمی‌رود: override در v10 آبجکت styles

   را in-place ادغام می‌کند و مقایسهٔ shouldUpdate هویتِ مرجع را تغییر نمی‌دهد،
   پس ممکن است بلافاصله بازترسیم نشود. overlay تازه همیشه رسم می‌شود. */
function rvCalFlash(ts) {
  if (!rv.chart) return;
  var i = _rvCalBarIndex(ts);
  if (i < 0) return;
  var bar = rv.data[i], id = 'auto_calhi_' + bar.timestamp;
  try {
    rv.chart.createOverlay({
      id: id, name: 'verticalSegment', paneId: 'candle_pane', zLevel: 6,
      points: [{ timestamp: bar.timestamp, value: bar.high }, { timestamp: bar.timestamp, value: bar.low }],
      styles: { line: { color: '#ffffff', size: 2, style: 'solid' } }
    });
  } catch (e) { return; }
  setTimeout(function () { try { if (rv.chart) rv.chart.removeOverlay({ id: id }); } catch (e) {} }, 2600);
}

/* ---------- دکمهٔ روشن/خاموش + وضعیت ---------- */
function rvCalSyncBtn() {
  var b = rvEl('rvBtnCalEvents');
  if (!b) return;
  var on = !!rvCalMarks.on;
  var n = (rvCalMarks.sym === rv.sym && rvCalMarks.list) ? rvCalMarks.list.length : 0;
  b.style.background = on ? 'rgba(56,189,248,.18)' : '';
  b.style.borderColor = on ? '#38bdf8' : '';
  b.style.color = on ? '#7dd3fc' : '';
  b.textContent = '📅 رویدادها' + (on && n ? ' (' + _rvFaD(n) + ')' : '');
  b.title = on
    ? 'نمایش رویدادهای تقویم (مجمع، سود، افزایش سرمایه، عرضه…) روی چارت — کلیک برای خاموش کردن'
    : 'نمایش رویدادهای تقویم روی چارت — کلیک برای روشن کردن';
}
function rvToggleEventMarks() {
  rvCalMarks.on = !rvCalMarks.on;
  try { if (typeof stSet === 'function') stSet('tech_cal_events', rvCalMarks.on ? 1 : 0); } catch (e) {}
  if (!rvCalMarks.on) { rvCalClearMarks(); rvCalSyncBtn(); return; }
  if (rvCalMarks.sym === rv.sym && rvCalMarks.list) rvCalDrawMarks(); else rvApplyEventMarks(true);
}
function rvCalEventsInit() {
  try { if (typeof stGet === 'function') rvCalMarks.on = stGet('tech_cal_events', 1) !== 0; } catch (e) {}
  rvCalSyncBtn();
}

/* ---------- کلیک روی مارکر → همان روز در وسط چارت + flash ---------- */
function rvCalMarkClick(ov) {
  var cal = ov && ov.styles && ov.styles.cal;
  if (!cal || !cal.ts) return;
  try { if (rv.chart.scrollToTimestamp) rv.chart.scrollToTimestamp(cal.ts, 300); } catch (e) {}
  setTimeout(function () { rvCalFlash(cal.ts); }, 380);
}

/* ---------- «برو به تاریخ» درخواست‌شده از تب تقویم ----------
   در انتهای rvLoad (بعد از scrollToRealTime) مصرف می‌شود تا اسکرول پیش‌فرضِ
   «انتهای serie» بر آن غالب نشود. */
function rvCalConsumePending() {
  var p = rvCalPending;
  if (!p) return;
  rvCalPending = null;
  if (!rv.chart) return;
  if (p.sym && rv.sym && p.sym !== rv.sym) return;
  var ts = +p.ts || 0;
  if (!ts) return;
  if (!rvCalMarks.on) { rvCalMarks.on = true; try { if (typeof stSet === 'function') stSet('tech_cal_events', 1); } catch (e) {} rvApplyEventMarks(); }
  try { rv.chart.scrollToTimestamp(ts, 300); } catch (e) { try { rv.chart.scrollToTimestamp(ts); } catch (e2) {} }
  setTimeout(function () { rvCalFlash(ts); }, 420);
  var ev = (rvCalMarks.list || []).filter(function (x) { return Math.abs((+x.ts || 0) - ts) <= 864e5; })[0];
  rvToast('📅 ' + _rvCalFaDate(ts) + (ev ? ' — ' + rvCalCat(ev.cat).fa : ''));
}

/* ---------- پلِ تقویم → چارت: «این رویداد را روی نمودار نشان بده» ----------
   الگو از gotoChart در app.js: rv.sym «پیش از» switchView ست می‌شود، چون
   switchView('tech') خودش rvInit() → rvLoad() را صدا می‌زند و دو rvLoad
   هم‌زمان نماد را می‌سوزاند. مقصدِ اسکرول در rvCalPending می‌نشیند و انتهای
   rvLoad آن را مصرف می‌کند؛ tick پایین فقط برای حالتی است که rvLoad اجرا نشود. */
function rvOpenSymbolAt(sym, isoDate) {
  sym = String(sym || '').trim();
  if (!sym) { rvToast('نماد نامشخص است'); return false; }
  var ts = rvDateToTs(isoDate) || 0;
  rvCalTipHide();
  rvCalPending = { sym: sym, ts: ts };
  try { rv.sym = sym; } catch (e) {}
  try {
    if (typeof switchView === 'function') switchView('tech'); else rvLoad(sym);
  } catch (e) { try { rvLoad(sym); } catch (e2) {} }
  var tries = 0;
  var tick = function () {
    if (++tries > 40 || !rvCalPending || rvCalPending.ts !== ts) return;   // مصرف شده
    if (rv.chart && rv.sym === sym && (rv.data || []).length && rvCalMarks.sym === sym) rvCalConsumePending();
    else setTimeout(tick, 300);
  };
  setTimeout(tick, 1200);
  return false;
}
window.rvOpenSymbolAt = rvOpenSymbolAt;   // از تقویم (calendar.js) صدا زده می‌شود
window.rvToggleEventMarks = rvToggleEventMarks;
window.rvApplyEventMarks = rvApplyEventMarks;

/* ---------- v10 FTS: نوار نشان‌های تحلیل تکنیکال (/api/fts) ----------
   موتور FTS بک‌اند: روند D/W/M، هم‌راستایی، کمربند فیبو، ستاپ جت، CHoCH،
   شکار نقطه، دابل‌باتم/جعبهٔ رنج و حکم چهارلایهٔ خروج. نشان‌ها هم در
   سربرگ چارت (#rvChartHead داخل #techView) و هم نوار تصمیم (#selBar)
   رندر می‌شوند؛ در #selBar فقط چکیدهٔ فشرده دیده می‌شود. */
function rvFtsTrendBadge(t) {
  if (t === 'up') return { cls: 'up', fa: 'صعودی 🟢' };
  if (t === 'down') return { cls: 'down', fa: 'نزولی 🔴' };
  if (t === 'range') return { cls: 'warn', fa: 'رنج 🟡' };
  return { cls: 'dim', fa: '—' };
}
function rvFtsBadgeHtml(cls, label, val, title) {
  /* v10.1 — جداکنده ": " بین برچسب و مقدار: [روزانه: صعودی 🟢] */
  return '<span class="fts-b ' + cls + '" title="' + (title || '') + '">' + label +
    (val ? ': <b>' + val + '</b>' : '') + '</span>';
}
function rvFtsSigFa(s) {
  var M = {
    ma14_watch: 'MA14 در کمین', ma14_trail: 'خروج MA14', stop_hard: 'حد ضرر',
    choch_break: 'شکست CHoCH', channel_break: 'شکست کانال', third_peak: 'سقف سوم',
    double_top: 'دابل‌تاپ', hs_break: 'سر و شانه', rsi_divergence: 'واگرایی RSI',
    rsi_rollover: 'چرخش RSI'
  };
  return M[s] || s || '';
}
function rvFtsRender(j) {
  var f = (j && j.fts) || null;
  var bar = rvEl('rvFtsBar');
  if (bar) {
    if (!f) { bar.innerHTML = rvFtsBadgeHtml('dim', 'FTS', '—'); }
    else {
      var tr = f.trend || {}, ex = f.exit_engine || {}, h = [];
      var d = rvFtsTrendBadge((tr.D || {}).trend), w = rvFtsTrendBadge((tr.W || {}).trend),
          m = rvFtsTrendBadge((tr.M || {}).trend);
      h.push(rvFtsBadgeHtml(d.cls, 'روزانه', d.fa, 'روند روزانه — ساختار سقف/کف'));
      h.push(rvFtsBadgeHtml(w.cls, 'هفتگی', w.fa, 'روند هفتگی'));
      h.push(rvFtsBadgeHtml(m.cls, 'ماهانه', m.fa, 'روند ماهانه'));
      if (tr.alignment === 'up' || tr.alignment === 'down')
        h.push(rvFtsBadgeHtml(tr.alignment === 'up' ? 'up' : 'down', 'هم‌راستا', '۳ تایم 🟢'));
      var fib = f.fib || {};
      if ((fib.zone_33_40 || {}).in_zone) h.push(rvFtsBadgeHtml('info', 'فیبو پله', '۳۳-۴۰٪', 'کمربند کم‌عمیق — ورود پس از ادامه‌ی روند'));
      if ((fib.zone_618_70 || {}).in_zone) h.push(rvFtsBadgeHtml('info', 'فیبو پله', '۶۱.۸-۷۰٪', 'کمربند طلایی — منطقه‌ی ورود اصلاحی'));
      if ((f.jet || {}).active) h.push(rvFtsBadgeHtml('up', 'جت', (f.jet.ath ? 'ATH ' : 'شکست ') + '🚀', 'شکست صعودی مقاومت مرجع با بدنه‌ی صعودی'));
      if ((f.choch || {}).bullish) h.push(rvFtsBadgeHtml('up', 'CHoCH', 'صعودی', 'تغییر کاراکتر ساختار به نفع صعودی‌ها'));
      if ((f.choch || {}).bearish) h.push(rvFtsBadgeHtml('down', 'CHoCH', 'نزولی', 'تغییر کاراکتر ساختار به زیان صعودی‌ها'));
      if ((f.point_hunt || {}).active) h.push(rvFtsBadgeHtml('info', 'نقطه‌زنی', (f.point_hunt.touches || 0) + ' لمس', 'لمس مکرر کف کانال — خرید در کف با حد ضرر کوتاه'));
      if ((f.double_bottom || {}).active) h.push(rvFtsBadgeHtml('up', 'دابل‌باتم', 'شکست یقه'));
      if ((f.range_box || {}).active) h.push(rvFtsBadgeHtml('up', 'شکست رنج', 'خروج از جعبه'));
      var v = ex.verdict;
      if (v === 'stop') h.push(rvFtsBadgeHtml('down', 'خروج', 'حد ضرر 🔴', 'حد ضرر سخت خورده شده — بستن پوزیشن'));
      else if (v === 'exit') h.push(rvFtsBadgeHtml('down', 'خروج', 'ساختاری 🔴', 'خروج تأییدشده‌ی ساختاری/الگویی'));
      else if (v === 'caution') h.push(rvFtsBadgeHtml('warn', 'هشدار', rvFtsSigFa((ex.signals || [])[0]), 'هشدار نرم — کاهش/پایش، نه خرید جدید'));
      else h.push(rvFtsBadgeHtml('dim', 'نگهداری', '🟢', 'هیچ سیگنال خروجی فعال نیست'));
      bar.innerHTML = h.join('');
    }
  }
  var sel = rvEl('selBarFts');
  if (sel) {
    if (!f) { sel.innerHTML = ''; }
    else {
      var t2 = rvFtsTrendBadge(((f.trend || {}).D || {}).trend);
      var ev = (f.exit_engine || {}).verdict;
      var evCls = (ev === 'stop' || ev === 'exit') ? 'down' : (ev === 'caution' ? 'warn' : 'dim');
      var evFa = ev === 'stop' ? 'حد ضرر 🔴' : ev === 'exit' ? 'خروج 🔴' : ev === 'caution' ? 'هشدار 🟡' : 'نگهداری 🟢';
      sel.innerHTML = rvFtsBadgeHtml(t2.cls, 'FTS', t2.fa) + ' ' + rvFtsBadgeHtml(evCls, 'خروج', evFa);
    }
  }
}
function rvFtsEnsureDom() {
  try {
    var head = rvEl('rvChartHead');
    if (head && !rvEl('rvFtsBar')) {
      var bar = document.createElement('span');
      bar.id = 'rvFtsBar'; bar.className = 'fts-bar';
      head.appendChild(bar);
    }
    /* v10.1 — چیپ‌های مقادیر MA استاندارد FTS در سربرگ چارت */
    if (head && !rvEl('rvMaLegend')) {
      var ml = document.createElement('span');
      ml.id = 'rvMaLegend'; ml.className = 'ma-legend';
      ml.title = 'میانگین‌های متحرک استاندارد FTS (14/52/100) — مقادیر آخرین روز';
      head.appendChild(ml);
    }
    /* v10.1 — دکمه‌ی «ℹ️ راهنمای FTS» در سربرگ چارت */
    if (head && !rvEl('rvFtsHelpBtn')) {
      var hb = document.createElement('button');
      hb.id = 'rvFtsHelpBtn'; hb.type = 'button'; hb.className = 'fts-help-btn';
      hb.innerHTML = 'ℹ️ راهنمای FTS';
      hb.title = 'راهنمای خطوط و نشان‌های تحلیل FTS';
      hb.onclick = function () { rvFtsHelpToggle(); };
      head.appendChild(hb);
    }
    /* v10.1 — کارت راهنما شناور روی بوم چارت */
    var box = rvEl('rvChartBox');
    if (box && !rvEl('rvFtsHelp')) {
      var card = document.createElement('div');
      card.id = 'rvFtsHelp';
      card.innerHTML =
        '<div class="fts-hlp-t">راهنمای FTS</div>' +
        '• خط <b style="color:var(--rv-ma-c1,#38bdf8)">آبی</b> = سقف ماژور استاتیک — تریگر تریلینگ استاپ «جت» و مانع مقاومت مهم.<br>' +
        '• خط <b style="color:#f43f5e">قرمز خط‌چین</b> = سقف/کف حساس اخیر — شکست آن CHoCH است.<br>' +
        '• <b>MA14</b> = تریلینگ استاپ موتور خروج — بسته‌شدن پایانی زیر آن = خروج تعقیبی.<br>' +
        '• <b>MA52 / MA100</b> = مرجع روند میان‌مدت و بلندمدت.<br>' +
        '• حجم: میانگین متحرک 21 روزه (MA21).<br>' +
        '<div class="fts-hlp-sub">نشان‌ها: روند D/W/M از ساختار سقف/کف؛ جت / فیبو پله / نقطه‌زنی = ستاپ‌های ورود؛ «خروج» حکم چهارلایه‌ی موتور FTS است.</div>';
      box.appendChild(card);
    }
    var selBar = rvEl('selBar');
    if (selBar && !rvEl('selBarFts')) {
      var s = document.createElement('span');
      s.id = 'selBarFts'; s.className = 'fts-bar sel-fts';
      var sym = rvEl('selBarSym');
      if (sym && sym.nextSibling) selBar.insertBefore(s, sym.nextSibling);
      else selBar.insertBefore(s, selBar.firstChild);
    }
  } catch (e) {}
}
/* v10.1 — چیپ‌های MA: آخرین SMA(14/52/100) از خود داده‌ی چارت محاسبه می‌شود
   (هم‌آهنگ خطوط klinecharts)؛ رنگ از متغیرهای --rv-ma-c* می‌آید (rvApplyTheme). */
function rvMaLegendSync() {
  var ml = rvEl('rvMaLegend');
  if (!ml) return;
  if (!rv.data || !rv.data.length) { ml.innerHTML = ''; return; }
  var closes = rv.data.map(function (c) { return c.close; });
  function sma(p) {
    if (closes.length < p) return null;
    var s = 0;
    for (var i = closes.length - p; i < closes.length; i++) s += closes[i];
    return s / p;
  }
  var chip = function (cls, label, v) {
    return (v == null) ? '' :
      '<span class="ma-chip ' + cls + '"><i></i>' + label + ' <b>' + _rvFmtNum(v) + '</b></span>';
  };
  ml.innerHTML = chip('c1', 'MA14 FTS', sma(14)) + chip('c2', 'MA52', sma(52)) + chip('c3', 'MA100', sma(100));
}
/* v10.1 — باز/بسته‌شدن کارت راهنمای FTS */
function rvFtsHelpToggle() {
  var c = rvEl('rvFtsHelp');
  if (!c) return;
  c.style.display = (c.style.display === 'block') ? 'none' : 'block';
}
window.rvFtsHelpToggle = rvFtsHelpToggle;
/* v10.1 — ftsNow = «fts» سواریفته در /api/chart (رندر بی‌درنگ بدون درخواست دوم)؛ سپس تازه‌سانی از
   /api/fts. پاسخ ناقص/خطا رندر فعلی را بازنویسی نمی‌کند؛ پاسخ کهنه با تغییر نماد دور ریخته می‌شود. */
async function rvFtsLoad(sym, ftsNow) {
  if (!sym) return;
  if (ftsNow && rv.sym === sym) {
    try { rvFtsRender({ status: 'success', fts: ftsNow }); } catch (e) {}
  }
  try {
    var r = await fetch('/api/fts/' + encodeURIComponent(sym), { cache: 'no-store' });
    var j = await r.json();
    if (rv.sym !== sym) return;          // نماد عوض شده — پاسخ کهنه دور ریخته شود
    if (!j || j.status !== 'success' || !j.fts) return;
    rvFtsRender(j);
  } catch (e) {}
}
