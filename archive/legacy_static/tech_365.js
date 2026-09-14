/* ============================================================
   v9.5 — لایهٔ الحاقی چارت تکنیکال (استاندارد رهاورد ۳۶۵)
   ------------------------------------------------------------
   عمداً در فایل جدا و بدون دست‌زدن به tech_rtv.js (۱۸۹۴ خط) نوشته شده:
   هر چه کم‌تر بافت موجود بازکاود شود، ریسک رگرسیون کمتر است.
   سه بخش: ۱) دراپ‌داون نوع قیمت  ۲) نوار پایین  ۳) مودال ۴ تب

   راستی‌آزمایی برابر static/vendor/klinecharts.min.js (نسخهٔ 10.0.3):
   همهٔ کلیدهایی که پایین‌تر به کتابخانه داده می‌شود، در خودِ باندل
   جستجو و تأیید شده‌اند. سه نکته‌ای که در v10 برعکسِ v9 است و قبلاً
   باعث می‌شد تنظیماتی «بی‌صدا» بی‌اثر بمانند:
     • رنگ کندل زیر candle.bar است (candle.candle در v10 وجود ندارد).
     • نوع محور (normal | percentage | logarithm) از styles.yAxis.type
       خوانده نمی‌شود؛ باید chart.overrideYAxis({name}) بخورد.
     • createTicks هم از options محور خوانده می‌شود نه styles.
   مقیاس «درصدی» هم پشتیبانی می‌شود (قبلاً اشتباهاً «نامعتبر» اعلام شده بود).

   صداقت داده‌ای: حالت‌های «دلاری» به نرخ دلار و «ارزش بازار» به تعداد
   سهام نیاز دارند. app.py هیچ نرخ دلاری ارائه نمی‌دهد، پس این گزینه‌ها
   تا زمان فراهم‌شدن سرویس «غیرفعال + توضیح» می‌مانند و هرگز عدد
   ساختگی نشان نمی‌دهند (فعال‌سازی: window.BTS_USD_RATE / rv.totalShares).
   ============================================================ */
'use strict';

var BTS_LS_KEY = 'bts_chart_settings';

var BTS_DEFAULTS = {
  symbol: {
    upColor: '#26A69A', downColor: '#EF5350',
    wickUp: '#26A69A', wickDown: '#EF5350',
    colorByPrevClose: true, decimals: 0, timezone: 'Asia/Tehran'
  },
  status: {
    showTitle: true, showOhlc: true, showChange: true,
    showVolume: true, headerOpacity: 1
  },
  scales: {
    lastPriceLine: true, prevCloseLine: true, hiLoLine: true,
    jalaliAxis: true, axis: 'normal'
  },
  canvas: {
    background: '#0d1220', grid: '#1c2438', gridShow: true,
    crosshair: 'magnet', gapTop: 20, gapBottom: 10, marginRight: 66
  }
};

function btsDeepMerge(base, over) {
  var out = {};
  Object.keys(base).forEach(function (k) {
    var b = base[k], o = over && over[k];
    out[k] = (b && typeof b === 'object' && !Array.isArray(b))
      ? btsDeepMerge(b, o || {})
      : (o === undefined ? b : o);
  });
  return out;
}

function btsLoadSettings() {
  try {
    var raw = localStorage.getItem(BTS_LS_KEY);
    var saved = raw ? JSON.parse(raw) : null;
    /* مهاجرت: نسخه‌های پیشین logScale را بولین ذخیره می‌کردند؛
       در v10 نوع محور یک «نام» است (normal | logarithm | percentage). */
    if (saved && saved.scales && saved.scales.logScale && !saved.scales.axis) {
      saved.scales.axis = 'logarithm';
    }
    return btsDeepMerge(BTS_DEFAULTS, saved);
  } catch (e) { return btsDeepMerge(BTS_DEFAULTS, null); }
}

function btsSaveSettings(s) {
  try { localStorage.setItem(BTS_LS_KEY, JSON.stringify(s)); return true; }
  catch (e) { return false; }
}

var btsSet = btsLoadSettings();

/* سرویس‌های بیرونی اختیاری — بدون آن‌ها حالت‌های وابسته غیرفعال می‌مانند */
function btsUsdRate() {
  var v = window.BTS_USD_RATE;
  return (typeof v === 'function') ? (+v() || 0) : (+v || 0);
}
function btsShares() {
  var v = (window.rv && window.rv.totalShares) || window.BTS_TOTAL_SHARES;
  return (typeof v === 'function') ? (+v() || 0) : (+v || 0);
}

/* ---------- ۱) نوع قیمت ----------
   نوع قیمت فقط «مقیاس/سری نمایشی» را عوض می‌کند و هیچ ربطی به تعدیل ندارد.
   در نسخه‌های پیشین هر گزینه یک فیلد adj داشت و btsApplyPriceType با آن
   rv.adj را بازنویسی می‌کرد؛ به همین دلیل انتخاب «قیمت پایانی» دکمهٔ
   تعدیل را روشن و «آخرین قیمت» آن را خاموش می‌کرد (تداخل گزارش‌شده).
   آن پیوند حالا کامل حذف شده است — تعدیل تنها با rvToggleAdj عوض می‌شود.
   نکتهٔ داده‌ای (v9.7): /api/chart علاوه بر OHLC، فیلد «last» هم می‌فرستد —
   ستون <LAST> در CSV تکمیل TSETMC («قیمت آخرین معامله»). این ستون در ~۹۰٪
   روزها با <CLOSE> تفاوت دارد (خساپا: ۳۶۱۴ ردیف از ۳۹۹۹)، پس «آخرین قیمت»
   و «قیمت پایانی» دو سری واقعی و جدا هستند — نه یک سری با دو نام. */
var BTS_PRICE_TYPES = [
  { id: 'last',      label: 'آخرین قیمت',       needs: null },
  { id: 'close',     label: 'قیمت پایانی',      needs: null },
  { id: 'last_usd',  label: 'آخرین قیمت دلاری', needs: 'usd' },
  { id: 'close_usd', label: 'پایانی دلاری',     needs: 'usd' },
  { id: 'mcap_kria', label: 'ارزش بازار (هزار میلیارد ریال)', needs: 'shares' },
  { id: 'mcap_musd', label: 'ارزش بازار (میلیون دلار)',        needs: 'both' }
];

/* v9.7: کدام فیلد قیمتِ هر کندل روی «close» سری نمایشی بنشیند.
   بدون آرگومان = نوع قیمت فعال. ارزش بازار مبنای رسمی (پایانی) دارد. */
function btsPriceField(id) {
  var v = (id === undefined) ? btsPriceTypeId() : id;
  return (v === 'last' || v === 'last_usd') ? 'last' : 'close';
}

function btsNeedOk(needs) {
  if (!needs) return true;
  if (needs === 'usd') return btsUsdRate() > 0;
  if (needs === 'shares') return btsShares() > 0;
  if (needs === 'both') return btsUsdRate() > 0 && btsShares() > 0;
  return false;
}

function btsPriceFactor(id) {
  var usd = btsUsdRate(), sh = btsShares();
  switch (id) {
    case 'last_usd': case 'close_usd': return usd > 0 ? 1 / usd : 1;
    case 'mcap_kria': return sh > 0 ? sh / 1e12 : 1;      // ریال → هزار میلیارد ریال
    case 'mcap_musd': return (sh > 0 && usd > 0) ? (sh / usd) / 1e6 : 1;
    default: return 1;
  }
}

/* دقت اعشار در v10 کلیدِ استایل نیست (styles.yAxis.precision هیچ‌جا خوانده
   نمی‌شود)؛ تنها مسیر درست، pricePrecision روی symbol است. setSymbol خودِ
   کتابخانه را با resetData ری‌رندر می‌کند، پس نیازی به دستکاری دستی نیست. */
function btsSetPrecision(dec) {
  var rv = window.rv;
  if (!rv || !rv.chart || typeof rv.chart.setSymbol !== 'function') return;
  try { rv.chart.setSymbol({ pricePrecision: dec }); }
  catch (e) { console.warn('[bts] setSymbol', e); }
}

/* ضریب مقیاسی که همین حالا روی چارت اعمال شده — برای تشخیص «واقعاً لازم
   است سری بازترسیم شود یا نه». */
var btsLastFactor = 1;

function btsPriceTypeId() {
  var v = 'last';
  try { v = localStorage.getItem('bts_price_type') || 'last'; } catch (e) {}
  return v;
}

/* ضریب مقیاس نوع قیمت فعال — rvRerender در tech_rtv.js همین را می‌پرسد.
   اگر گزینه به منبع دادهٔ موجود نیاز داشته باشد، ضریب ۱ برمی‌گردد. */
function btsActiveFactor() {
  var t = null;
  BTS_PRICE_TYPES.forEach(function (x) { if (x.id === btsPriceTypeId()) t = x; });
  if (!t || !btsNeedOk(t.needs)) return 1;
  return btsPriceFactor(t.id);
}

function btsApplyPriceType(id) {
  var rv = window.rv;
  if (!rv || !rv.chart) return;
  var t = null;
  BTS_PRICE_TYPES.forEach(function (x) { if (x.id === id) t = x; });
  if (!t || !btsNeedOk(t.needs)) t = BTS_PRICE_TYPES[0];
  try { localStorage.setItem('bts_price_type', t.id); } catch (e) {}

  var f = btsPriceFactor(t.id);
  // دقت اعشار را با مقیاس تازه می‌کنیم تا عدد «۰» نشود
  var dec = (+btsSet.symbol.decimals || 0) +
            (f > 0 && f < 1 ? Math.max(0, Math.round(-Math.log10(f))) : 0);
  btsSetPrecision(dec);

  /* ---- رفع تداخل نوع قیمت با تعدیل ----
     پیش از این، اینجا rv.adj از روی t.adj نوشته می‌شد و rvLoad دوباره داده
     می‌گرفت؛ همان مسیر باعث می‌شد دکمهٔ «تعدیل عملکردی» روشن/خاموش شود.
     حالا تعدیل کاملاً دست‌نخورده می‌ماند. */
  var fd = btsPriceField(t.id);
  if (f !== btsLastFactor || fd !== (rv._seriesField || 'close')) {
    btsLastFactor = f;
    /* بازترسیم فقط وقتی چیزی واقعاً عوض شده باشد:
       (الف) ضریب مقیاس  ←  دلاری / ارزش بازار
       (ب) فیلد سری      ←  last ⇄ close   (v9.7: دو سری واقعی و متفاوت)
       rv._seriesField را خودِ rvBuildSeries تازه نگه می‌دارد، پس این سنجش
       همیشه با وضعیت واقعی چارت هم‌خوان است و رسم‌های کاربر بی‌دلیل
       بازسازی نمی‌شوند.
       rvRerender از کش دادهٔ خام می‌سازد؛ اگر خامی نبود یعنی سری
       تازه‌ای برای نمایش نیست، پس واکشی دوباره هم بی‌معناست. */
    if (typeof rvRerender === 'function') rvRerender();
  }

  var sel = document.getElementById('btsPriceType');
  if (sel) sel.value = t.id;
  if (typeof rvToast === 'function') rvToast('نوع قیمت: ' + t.label);
}

function btsBuildPriceSelect() {
  var anchor = document.getElementById('nnAdjBtn');
  if (!anchor || document.getElementById('btsPriceType')) {
    return document.getElementById('btsPriceType');
  }
  var sel = document.createElement('select');
  sel.id = 'btsPriceType';
  sel.className = 'nn-btn bts-price-sel';
  sel.title = 'نوع قیمت / مقیاس چارت';
  var saved = btsPriceTypeId();
  BTS_PRICE_TYPES.forEach(function (t) {
    var o = document.createElement('option');
    var ok = btsNeedOk(t.needs);
    o.value = t.id;
    o.textContent = ok ? t.label : (t.label + ' — بدون منبع داده');
    o.disabled = !ok;
    sel.appendChild(o);
  });
  var cur = null;
  BTS_PRICE_TYPES.forEach(function (x) { if (x.id === saved) cur = x; });
  sel.value = (cur && btsNeedOk(cur.needs)) ? saved : 'last';
  sel.addEventListener('change', function (e) {
    /* نوع قیمت هیچ کاری با دکمهٔ تعدیل ندارد؛ با این حال انتشار رویداد را
       می‌بندیم تا اگر بعداً روی nn-group لیسنر اشتراکی نصب شد، تداخل
       برنگردد. (select خواهرِ #nnAdjBtn است نه فرزندش، پس فعلاً حبابی نیست.) */
    if (e) {
      if (e.stopImmediatePropagation) e.stopImmediatePropagation();
      if (e.stopPropagation) e.stopPropagation();
    }
    btsApplyPriceType(this.value);
  });
  anchor.parentNode.insertBefore(sel, anchor.nextSibling);
  return sel;
}

/* ---------- ۲) نوار پایین ---------- */
var BTS_RANGES = [
  { d: 1,    t: '1d' }, { d: 5, t: '5d' }, { d: 30, t: '1m' },
  { d: 91,   t: '3m' }, { d: 182, t: '6m' }, { d: 365, t: '1y' },
  { d: 1825, t: '5y' }
];

/* ---------- مقیاس محور عمودی ----------
   v10 نوع محور را از styles.yAxis.type نمی‌خواند (آن کلید در هیچ مسیرِ
   کتابخانه استفاده نمی‌شود). registry واقعی ri = {normal, percentage,
   logarithm} است و تنها راه عوض‌کردنش overrideYAxis({name}) می‌باشد.
   قبلاً هم tech_rtv.js و هم این فایل setStyles({yAxis:{type:'logarithmic'}})
   می‌زدند که بی‌صدا هیچ کاری نمی‌کرد. */
var BTS_AXIS_NAME = { pct: 'percentage', log: 'logarithm', auto: 'normal' };
var BTS_AXIS_BTN  = { percentage: 'pct', logarithm: 'log', normal: 'auto' };

/* نام محوری که کتابخانه واقعاً ساخته — تنها مرجع معتبر برای راستی‌آزمایی.
   بدون این بازخوانی، دکمه می‌توانست «روشن» بماند در حالی که مقیاس عوض نشده. */
function btsAxis() {
  var rv = window.rv;
  try {
    if (rv && rv.chart && typeof rv.chart.getYAxes === 'function') {
      var a = rv.chart.getYAxes({ paneId: 'candle_pane' });
      return (a && a.length) ? a[0] : null;
    }
  } catch (e) {}
  return null;
}

function btsSetScale(kind) {
  var rv = window.rv;
  if (!rv || !rv.chart) return;
  var name = BTS_AXIS_NAME[kind] || 'normal';
  btsSet.scales.axis = name;
  btsSaveSettings(btsSet);
  try {
    /* فقط پنل کندل؛ بدون paneId محورِ حجم هم لگاریتمی می‌شد */
    if (typeof rv.chart.overrideYAxis === 'function') {
      rv.chart.overrideYAxis({ paneId: 'candle_pane', name: name });
    }
  } catch (e) { console.warn('[bts] overrideYAxis', e); }

  var ax = btsAxis();
  var applied = (ax && ax.name) ? ax.name : null;
  if (applied && applied !== name) {
    /* کتابخانه نپذیرفت — تنظیم را به همان مقدار واقعی برمی‌گردانیم */
    btsSet.scales.axis = applied;
    btsSaveSettings(btsSet);
    btsSyncScaleBtns();
    if (typeof rvToast === 'function') rvToast('مقیاس انتخابی فعال نشد (اکنون: ' + applied + ')');
    return;
  }
  rv.logScale = (name === 'logarithm');
  /* v9.7.1 — دو خط getElementById('rvLogBtn') حذف شد: چنین المانی در index.html
     هرگز وجود نداشت و همیشه null برمی‌گشت؛ وضعیت مقیاس را btsSyncScaleBtns()
     روی دکمه‌های واقعیِ نوار پایین (bts-scl-*) ست می‌کند. */
  btsSyncScaleBtns();

  if (typeof rvToast === 'function') {
    rvToast('مقیاس: ' + ({ percentage: 'درصد', logarithm: 'لگاریتمی' }[name] || 'خطی'));
  }
}

function btsSyncScaleBtns() {
  var btn = BTS_AXIS_BTN[btsSet.scales.axis] || 'auto';
  ['pct', 'log', 'auto'].forEach(function (k) {
    var el = document.querySelector('.bts-scl-' + k);
    if (el) el.classList.toggle('on', k === btn);
  });
}

function btsBuildBottomBar() {
  var box = document.getElementById('rvChartBox');
  if (!box || !box.parentNode || document.getElementById('btsBottomBar')) return null;
  var bar = document.createElement('div');
  bar.id = 'btsBottomBar';
  bar.className = 'bts-bottom';

  var left = document.createElement('div');
  left.className = 'bts-bottom-l';
  BTS_RANGES.forEach(function (r) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'bts-rng';
    b.textContent = r.t;
    b.title = 'نمایش ' + r.t + ' اخیر';
    b.onclick = function () {
      left.querySelectorAll('.bts-rng').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      if (typeof rvZoomRange === 'function') rvZoomRange(r.d);
    };
    left.appendChild(b);
  });
  var cal = document.createElement('button');
  cal.type = 'button';
  cal.className = 'bts-rng bts-cal';
  cal.title = 'پرش به تاریخ';
  cal.innerHTML = '&#128197;';
  cal.onclick = function () { if (typeof rvGotoDate === 'function') rvGotoDate(); };
  left.appendChild(cal);

  var right = document.createElement('div');
  right.className = 'bts-bottom-r';
  var clock = document.createElement('span');
  clock.id = 'btsClock';
  clock.className = 'bts-clock';
  clock.title = 'ساعت تهران (UTC+3:30)';
  clock.textContent = '--:--:--';
  right.appendChild(clock);
  [['pct', '%', 'مقیاس درصد'], ['log', 'log', 'مقیاس لگاریتمی'],
   ['auto', 'auto', 'مقیاس خودکار']].forEach(function (s) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'bts-scl bts-scl-' + s[0];
    b.textContent = s[1];
    b.title = s[2];
    b.onclick = function () { btsSetScale(s[0]); };
    right.appendChild(b);
  });
  btsSyncScaleBtns();

  bar.appendChild(left);
  bar.appendChild(right);
  box.parentNode.insertBefore(bar, box.nextSibling);
  return bar;
}

/* ساعت تهران — از Intl با منطقهٔ زمانی، نه آفست دستی (نیم‌ساعت را درست می‌دهد) */
function btsTickClock() {
  var el = document.getElementById('btsClock');
  if (!el) return;
  var s;
  try {
    s = new Intl.DateTimeFormat('en-GB', {
      timeZone: btsSet.symbol.timezone || 'Asia/Tehran',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    }).format(new Date());
  } catch (e) {
    s = new Date().toTimeString().slice(0, 8);
  }
  el.textContent = s;
}

/* ---------- ۳) مودال تنظیمات (۴ تب) ---------- */
var BTS_TABS = [
  ['symbol', 'نماد'], ['status', 'نوار وضعیت'],
  ['scales', 'محورها و خطوط'], ['canvas', 'بوم']
];

function btsField(tab, key, label, kind, extra) {
  var id = 'bts_' + tab + '_' + key;
  var v = btsSet[tab][key];
  var inp;
  if (kind === 'color') {
    inp = '<input type="color" id="' + id + '" data-tab="' + tab + '" data-key="' + key +
          '" value="' + (v || extra) + '">';
  } else if (kind === 'check') {
    inp = '<input type="checkbox" id="' + id + '" data-tab="' + tab + '" data-key="' + key +
          '"' + (v ? ' checked' : '') + '>';
  } else if (kind === 'select') {
    inp = '<select id="' + id + '" data-tab="' + tab + '" data-key="' + key + '">' +
          extra.map(function (o) {
            return '<option value="' + o[0] + '"' + (v === o[0] ? ' selected' : '') + '>' +
                   o[1] + '</option>';
          }).join('') + '</select>';
  } else {
    inp = '<input type="number" id="' + id + '" data-tab="' + tab + '" data-key="' + key +
          '" value="' + v + '" min="' + (extra && extra.min !== undefined ? extra.min : 0) +
          '" max="' + (extra && extra.max !== undefined ? extra.max : 9999) +
          '" step="' + (extra && extra.step !== undefined ? extra.step : 1) + '">';
  }
  return '<label class="bts-row"><span>' + label + '</span>' + inp + '</label>';
}

function btsModalBody(tab) {
  if (tab === 'symbol') {
    return btsField('symbol', 'upColor', 'رنگ بدنهٔ صعودی', 'color', '#26A69A') +
           btsField('symbol', 'downColor', 'رنگ بدنهٔ نزولی', 'color', '#EF5350') +
           btsField('symbol', 'wickUp', 'رنگ سایهٔ صعودی', 'color', '#26A69A') +
           btsField('symbol', 'wickDown', 'رنگ سایهٔ نزولی', 'color', '#EF5350') +
           btsField('symbol', 'colorByPrevClose', 'رنگ بر اساس پایانیِ قبل', 'check') +
           btsField('symbol', 'decimals', 'دقت اعشار', 'number', { min: 0, max: 6 }) +
           btsField('symbol', 'timezone', 'منطقهٔ زمانی', 'select',
                    [['Asia/Tehran', 'تهران (UTC+3:30)'], ['UTC', 'جهانی (UTC)']]);
  }
  if (tab === 'status') {
    return btsField('status', 'showTitle', 'نمایش عنوان نماد', 'check') +
           btsField('status', 'showOhlc', 'نمایش OHLC', 'check') +
           btsField('status', 'showChange', 'نمایش درصد تغییر', 'check') +
           btsField('status', 'showVolume', 'نمایش حجم', 'check') +
           btsField('status', 'headerOpacity', 'شفافیت هدر (۰–۱)', 'number',
                    { min: 0, max: 1, step: 0.05 });
  }
  if (tab === 'scales') {
    return btsField('scales', 'lastPriceLine', 'خط قیمت آخرین', 'check') +
           btsField('scales', 'prevCloseLine', 'خط پایانیِ قبل', 'check') +
           btsField('scales', 'hiLoLine', 'خط سقف / کف', 'check') +
           btsField('scales', 'jalaliAxis', 'تقویم شمسی روی محور', 'check') +
           btsField('scales', 'axis', 'نوع مقیاس محور', 'select',
                    [['normal', 'خطی (عادی)'], ['logarithm', 'لگاریتمی'],
                     ['percentage', 'درصدی']]);
  }
  return btsField('canvas', 'background', 'پس‌زمینهٔ یکدست', 'color', '#0d1220') +
         btsField('canvas', 'grid', 'رنگ خطوط گرید', 'color', '#1c2438') +
         btsField('canvas', 'gridShow', 'نمایش گرید', 'check') +
         btsField('canvas', 'crosshair', 'استایل کراس‌هیر', 'select',
                  [['normal', 'معمولی'], ['magnet', 'آهنربا'], ['none', 'بدون']]) +
         btsField('canvas', 'gapTop', 'حاشیهٔ بالا (٪ ارتفاع)', 'number', { min: 0, max: 60 }) +
         btsField('canvas', 'gapBottom', 'حاشیهٔ پایین (٪ ارتفاع)', 'number', { min: 0, max: 60 }) +
         btsField('canvas', 'marginRight', 'پهنای محور راست (پیکسل)', 'number', { min: 20, max: 200 });
}

function btsBindModal(m) {
  m.querySelectorAll('[data-tab][data-key]').forEach(function (el) {
    el.onchange = function () {
      btsSet[el.dataset.tab][el.dataset.key] =
        (el.type === 'checkbox') ? el.checked : (el.type === 'number' ? +el.value : el.value);
    };
  });
}

function btsCollect(m) {
  m.querySelectorAll('[data-tab][data-key]').forEach(function (el) {
    btsSet[el.dataset.tab][el.dataset.key] =
      (el.type === 'checkbox') ? el.checked : (el.type === 'number' ? +el.value : el.value);
  });
}

function btsOpenSettings() {
  var old = document.getElementById('btsSettingsModal');
  if (old) { old.remove(); return null; }
  var m = document.createElement('div');
  m.id = 'btsSettingsModal';
  m.className = 'bts-modal';
  m.innerHTML =
    '<div class="bts-modal-box"><div class="bts-modal-head"><div class="bts-tabs">' +
    BTS_TABS.map(function (t, i) {
      return '<button type="button" class="bts-tab' + (i === 0 ? ' on' : '') +
             '" data-tab="' + t[0] + '">' + t[1] + '</button>';
    }).join('') + '</div>' +
    '<button type="button" class="bts-x" title="بستن">✕</button></div>' +
    '<div class="bts-modal-body">' + btsModalBody('symbol') + '</div>' +
    '<div class="bts-modal-foot">' +
    '<button type="button" class="btn-filter bts-reset">بازگشت به پیش‌فرض</button>' +
    '<button type="button" class="btn-filter bts-save">💾 ذخیره</button>' +
    '</div></div>';
  document.body.appendChild(m);
  m.querySelectorAll('.bts-tab').forEach(function (b) {
    b.onclick = function () {
      m.querySelectorAll('.bts-tab').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on');
      m.querySelector('.bts-modal-body').innerHTML = btsModalBody(b.dataset.tab);
      btsBindModal(m);
    };
  });
  m.querySelector('.bts-x').onclick = function () { m.remove(); };
  m.querySelector('.bts-save').onclick = function () {
    btsCollect(m);
    if (btsSaveSettings(btsSet)) {
      btsApplySettings();
      m.remove();
      if (typeof rvToast === 'function') rvToast('تنظیمات چارت ذخیره شد');
    }
  };
  m.querySelector('.bts-reset').onclick = function () {
    btsSet = btsDeepMerge(BTS_DEFAULTS, null);
    btsSaveSettings(btsSet);
    m.remove();
    btsApplySettings();
    if (typeof rvToast === 'function') rvToast('تنظیمات به پیش‌فرض برگشت');
  };
  btsBindModal(m);
  return m;
}

/* اعمال روی KLineChart — همه در try/catch، چون نسخهٔ کتابخانه ممکن است
   برخی کلیدها را نشناسد و نباید کل چارت بخوابد. */
/* تراکم برچسب‌های محور X: مختصاتِ خود defaultTicks حفظ می‌شود و فقط
   برچسب‌های نزدیک‌تر از ۷۸ پیکسل حذف می‌گردند — بدون تداخل، بدون drift. */
function btsThinTicks(p) {
  var d = (p && p.defaultTicks) || [];
  if (!d.length) return d;
  var out = [], last = -1e9, MIN = 78;
  for (var i = 0; i < d.length; i++) {
    if (d[i].coord - last >= MIN) { out.push(d[i]); last = d[i].coord; }
  }
  return out;
}

/* خط پایانیِ قبل: v10 فقط «قیمت آخرین» را نیتیو دارد، پس این خط را با
   overlay افقی کامل‌شده (۲ نقطهٔ هم‌ارزش) می‌سازیم تا در حالت رسم نماند. */
var _btsPcId = null;
/* پیشوند/شناسهٔ ثابت دکوراسیون‌هایی که خودِ اپ می‌سازد — این‌ها رسم کاربر نیستند
   و نباید ذخیره/بازیابی شوند. rvIsDecoration در tech_rtv.js از همین نام خواند. */
var BTS_PREV_CLOSE_ID = 'bts_prev_close_line';

function btsPrevCloseLine(on) {
  var rv = window.rv;
  if (!rv || !rv.chart) return;
  var c = rv.chart;
  try {
    if (_btsPcId && typeof c.removeOverlay === 'function') {
      c.removeOverlay({ id: _btsPcId }); _btsPcId = null;
    }
    if (!on) return;
    var d = rv.data;
    if (!d || d.length < 2) return;
    var prev = d[d.length - 2];
    if (typeof c.createOverlay !== 'function') return;
    var res = c.createOverlay({
      /* v9.7.1 — id پایدار: بدون آن، KLineCharts شناسهٔ تصادفی می‌ساخت که با
         هیچ پیشوندِ دکوراسیونی مطابقت نداشت، پس rvSaveOverlays این خط را به‌عنوان
         «رسم کاربر» در بلاوب tech_<sym> می‌نوشت و rvRestoreOverlays بعد از هر
         reload یک نسخهٔ تکراری رویش می‌گذاشت (با CDP روی پروفایل تازه ثبت شد:
         ۱ خط قبل از reload، ۲ خط بعد از reload). */
      id: BTS_PREV_CLOSE_ID,
      name: 'horizontalStraightLine',
      paneId: 'candle_pane',
      lock: true,
      points: [{ timestamp: prev.timestamp, value: prev.close },
               { timestamp: prev.timestamp, value: prev.close }],
      styles: { line: { color: '#8b93a7', style: 'dashed', dashedValue: [4, 4], size: 1 } }
    });
    _btsPcId = (res && res.id) ? res.id : BTS_PREV_CLOSE_ID;

  } catch (e) { console.warn('[bts] prevCloseLine', e); }
}

/* «آهنربا» در v10 ویژگیِ crosshair نیست؛ حالتِ خودِ overlay است
   (mode: normal | weak_magnet). استایلِ جعلی crosshair.mode بی‌اثر بود. */
function btsOverlayMagnet(on) {
  var rv = window.rv;
  if (!rv || !rv.chart) return;
  var c = rv.chart;
  try {
    if (typeof c.getOverlays !== 'function' || typeof c.overrideOverlay !== 'function') return;
    var list = c.getOverlays({}) || [];
    list.forEach(function (o) {
      if (o && o.id) c.overrideOverlay({ id: o.id, mode: on ? 'weak_magnet' : 'normal' });
    });
  } catch (e) { console.warn('[bts] magnet', e); }
}

/* اعمال روی KLineChart — همه در try/catch، چون نسخهٔ کتابخانه ممکن است
   برخی کلیدها را نشناسد و نباید کل چارت بخوابد.

   سه نکتهٔ v10 که قبلاً اشتباه بود:
   ۱) رنگ کندل زیر «candle.bar» است، نه candle.candle.
   ۲) نوع محور و فاصلهٔ بالا/پایین از styles نمی‌آیند؛ overrideYAxis لازم است.
   ۳) createTicks هم از options محور خوانده می‌شود نه styles. */
function btsApplySettings() {
  var rv = window.rv;
  if (!rv || !rv.chart) return;
  var s = btsSet, c = rv.chart;
  var showX = s.canvas.crosshair !== 'none';
  btsWrapReset(c);

  try {
    c.setStyles({
      candle: {
        bar: {
          upColor: s.symbol.upColor, downColor: s.symbol.downColor,
          noChangeColor: s.symbol.upColor,
          upBorderColor: s.symbol.upColor, downBorderColor: s.symbol.downColor,
          noChangeBorderColor: s.symbol.upColor,
          upWickColor: s.symbol.wickUp, downWickColor: s.symbol.wickDown,
          noChangeWickColor: s.symbol.wickUp,
          /* مقایسه با «پایانیِ قبل» در برابر «بازِ همین کندل» — پشتیبانی بومی v10 */
          compareRule: s.symbol.colorByPrevClose ? 'prev_close' : 'current_open'
        },
        priceMark: {
          last: { show: !!s.scales.lastPriceLine },
          high: { show: !!s.scales.hiLoLine },
          low: { show: !!s.scales.hiLoLine }
        }
      },
      grid: {
        show: !!s.canvas.gridShow,
        horizontal: { show: !!s.canvas.gridShow, color: s.canvas.grid },
        vertical: { show: !!s.canvas.gridShow, color: s.canvas.grid }
      },
      crosshair: {
        show: showX,
        horizontal: { show: showX },
        vertical: { show: showX }
      },
      yAxis: { size: (+s.canvas.marginRight || 66) }
    });
  } catch (e) { console.warn('[bts] setStyles', e); }

  /* نوع محور + حاشیهٔ عمودی.
     نکته: کتابخانه وقتی «name» عوض نشود محور را از نو نمی‌سازد، پس gap تنها
     هنگام ساخت دوبارهٔ محور (تغییر مقیاس) اعمال می‌شود — نه به‌صورت آنی. */
  try {
    if (typeof c.overrideYAxis === 'function') {
      c.overrideYAxis({
        paneId: 'candle_pane',
        name: s.scales.axis || 'normal',
        gap: {
          top: Math.max(0, Math.min(60, +s.canvas.gapTop || 0)) / 100,
          bottom: Math.max(0, Math.min(60, +s.canvas.gapBottom || 0)) / 100
        }
      });
    }
  } catch (e) { console.warn('[bts] overrideYAxis', e); }

  /* v9.7.2 — همگام‌سازی پرچم مقیاس با وضعیت واقعی محور.
     rv.logScale مقدار اولیه‌اش false است و در هیچ مسیرِ لود بازنویسی نمی‌شد؛
     نتیجه اینکه بعد از reload محور لگاریتمی بود ولی پرچم «خطی» می‌گفت و این
     مقدار نادرست داخل بلابِ هر نماد (stSet('tech_'+sym, {logScale:…})) ذخیره
     می‌شد. مرجع معتبر «نام محوری است که کتابخانه واقعاً ساخته» (btsAxis) نه
     آنچه درخواست کرده‌ایم؛ اگر چارت هنوز محور نساخته، به مقدار درخواستی
     برمی‌گردیم. */
  try {
    var axNow = btsAxis();
    var effAxis = (axNow && axNow.name) ? axNow.name : (s.scales.axis || 'normal');
    rv.logScale = (effAxis === 'logarithm');
  } catch (e) {}

  /* تقویم شمسی / تراکم برچسب‌های محور X */
  try {
    if (typeof c.overrideXAxis === 'function') {
      c.overrideXAxis({
        name: 'normal',
        createTicks: s.scales.jalaliAxis ? btsThinTicks : function (p) { return p.defaultTicks || []; }
      });
    }
  } catch (e) { console.warn('[bts] overrideXAxis', e); }

  btsPrevCloseLine(!!s.scales.prevCloseLine);
  btsOverlayMagnet(s.canvas.crosshair === 'magnet');
  btsSyncScaleBtns();

  try {
    var box = document.getElementById('rvChartBox');
    if (box) box.style.background = s.canvas.background;
    var head = document.getElementById('rvChartHead');
    if (head) {
      head.style.opacity = String(s.status.headerOpacity);
      head.style.display = s.status.showTitle ? '' : 'none';
      var map = { rvLgO: s.status.showOhlc, rvLgH: s.status.showOhlc,
                  rvLgL: s.status.showOhlc, rvLgC: s.status.showOhlc,
                  rvLgV: s.status.showVolume };
      Object.keys(map).forEach(function (id) {
        var el = document.getElementById(id);
        if (el) el.style.display = map[id] ? '' : 'none';
      });
    }
  } catch (e) {}
}

/* یک‌بار پیچیدن دور یک تابع سراسری تا بعد از آن تنظیمات دوباره اعمال شود */
function btsHook(fnName) {
  try {
    var orig = window[fnName];
    if (typeof orig !== 'function' || orig.__btsWrapped) return;
    var wrapped = function () {
      var r = orig.apply(this, arguments);
      try { btsApplySettings(); } catch (e) {}
      return r;
    };
    wrapped.__btsWrapped = true;
    window[fnName] = wrapped;
  } catch (e) {}
}

/* rv.chart.resetData هر بار که داده تازه می‌آید صدا زده می‌شود؛ خط
   پایانیِ قبل به آخرین کندلِ داده نیاز دارد، پس بعد از آن بازسازی می‌شود. */
function btsWrapReset(c) {
  try {
    if (!c || typeof c.resetData !== 'function' || c.resetData.__btsWrapped) return;
    var orig = c.resetData.bind(c);
    var wrapped = function () {
      var r = orig.apply(null, arguments);
      setTimeout(function () {
        try { btsPrevCloseLine(!!btsSet.scales.prevCloseLine); } catch (e) {}
      }, 0);
      return r;
    };
    wrapped.__btsWrapped = true;
    c.resetData = wrapped;
  } catch (e) {}
}

function btsInit() {
  if (!document.getElementById('rvChartBox')) return;
  btsBuildPriceSelect();
  btsBuildBottomBar();
  btsTickClock();
  if (!window.__btsClock) window.__btsClock = setInterval(btsTickClock, 1000);
  /* چارت هنگام باز شدن پنل تکنیکال ساخته می‌شود (بعد از این تابع) و
     rvApplyStyles هر بار رنگ‌ها را از پالت پیش‌فرض بازنویسی می‌کند؛ اگر
     بلافاصله بعد از آن تنظیم کاربر اعمال نشود، انتخاب‌ها دیده نمی‌شوند. */
  btsHook('rvApplyStyles');
  btsApplySettings();
  try {
    var saved = localStorage.getItem('bts_price_type');
    if (saved && saved !== 'last') btsApplyPriceType(saved);
  } catch (e) {}
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', btsInit);
} else {
  btsInit();
}

window.btsInit = btsInit;
window.btsOpenSettings = btsOpenSettings;
window.btsApplySettings = btsApplySettings;
window.btsApplyPriceType = btsApplyPriceType;
window.btsLoadSettings = btsLoadSettings;



