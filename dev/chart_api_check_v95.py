"""
v9.5 — گارد سازگاری با KLineCharts v10
--------------------------------------------------
هر کلیدی که کد ما به کتابخانه می‌دهد باید در خودِ باندل وجود داشته باشد.
این تست دقیقاً همان چیزی است که باگ‌های «بی‌صدا بی‌اثر» را گرفت:
  • candle.candle.*   (در v10 وجود ندارد — صحیح: candle.bar.*)
  • styles.yAxis.type (هیچ‌جا خوانده نمی‌شود — صحیح: overrideYAxis({name}))
  • crosshair.mode:'strong_magnet' (کلید ناموجود)
  • rvToggleLogScale (تابع ناموجود)
اجرا:  python dev/chart_api_check_v95.py
"""
import io, re, sys, os

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

BUNDLE = 'archive/legacy_static/vendor/klinecharts.min.js'
OUR_JS = ['archive/legacy_static/tech_365.js', 'archive/legacy_static/tech_rtv.js', 'archive/legacy_static/tech_tools.js']


def read(p):
    return io.open(p, encoding='utf-8', errors='replace').read()


bundle = read(BUNDLE)
ours = {p: read(p) for p in OUR_JS}

# نسخهٔ باندل را بخوان و ثابتش کن
m = re.search(r'version=function\(\)\{return"([\d.]+)"\}', bundle)
version = m.group(1) if m else '?'

checks = []


def chk(name, cond):
    checks.append((name, bool(cond)))


chk('bundle is KLineCharts 10.0.3', version == '10.0.3')

# --- ۱) registry واقعی محور عمودی ---
reg = re.search(r'ri=\{normal:.*?logarithm:', bundle)
chk('yAxis registry {normal,percentage,logarithm}', reg)
chk('styles.yAxis.type is NOT a real key', 'yAxis.type' not in bundle)

# --- ۲) کلید رنگ کندل ---
chk('candle style key is "bar"', re.search(r'bar:\{compareRule', bundle))
chk('candle.candle does not exist', not re.search(r'candle:\{candle:', bundle))

# --- ۳) API عمومی که استفاده می‌کنیم ---
for api in ['overrideYAxis', 'overrideXAxis', 'setStyles', 'getStyles',
            'setSymbol', 'createOverlay', 'removeOverlay', 'overrideOverlay',
            'getOverlays', 'getYAxes', 'resetData', 'setDataLoader']:
    chk('public API .%s()' % api, ('prototype.%s=' % api) in bundle)

# --- ۴) enum های معتبر ---
chk('compareRule "current_open" exists', '"current_open"' in bundle)
chk('overlay mode "weak_magnet" exists', '"weak_magnet"' in bundle)
chk('"strong_magnet" is NOT in bundle', 'strong_magnet' not in bundle)
chk('candle pane id is "candle_pane"', '"candle_pane"' in bundle)
chk('overlay horizontalStraightLine exists', '"horizontalStraightLine"' in bundle)

def strip_comments(src):
    """حذف /* */ و // تا توضیحاتِ خودمان باعث خطای کاذب نشوند."""
    src = re.sub(r'/\*.*?\*/', ' ', src, flags=re.S)
    src = re.sub(r'(?m)//.*$', ' ', src)
    return src


# --- ۵) کد ما نباید کلیدهای مرده را زنده صدا بزند ---
DEAD = {
    r'candle:\s*\{\s*candle:': 'candle.candle.* (v10 uses candle.bar)',
    r"yAxis:\s*\{\s*type:": 'styles.yAxis.type (never read by v10)',
    r"crosshair:\s*\{\s*mode:": 'styles.crosshair.mode (not a style)',
    r'rvToggleLogScale\b': 'rvToggleLogScale (function does not exist)',
    r'yAxis:\s*\{\s*precision:': 'styles.yAxis.precision (use setSymbol)',
}
for pat, why in DEAD.items():
    for f, src in ours.items():
        live = strip_comments(src)
        chk('%s: no live %s' % (os.path.basename(f), why.split(' ')[0]),
            not re.search(pat, live))

# --- ۶) هر تابع rvX که tech_365 صدا می‌زند باید جایی تعریف شده باشد ---
alljs = '\n'.join(read(p) for p in
                  ['archive/legacy_static/tech_rtv.js', 'archive/legacy_static/app.js',
                   'archive/legacy_static/tech_tools.js', 'archive/legacy_static/tech_365.js',

                   'static/calendar/calendar.js', 'archive/legacy_static/selection.js'])
for fn in sorted(set(re.findall(r'\brv([A-Z]\w*)\s*\(', ours['archive/legacy_static/tech_365.js']))):
    name = 'rv' + fn
    chk('called %s() is defined' % name,
        re.search(r'function\s+%s\s*\(' % name, alljs) or
        re.search(r'%s\s*=\s*(function|async)' % name, alljs))

# --- ۷) v9.6 — نوع قیمت باید کاملاً از تعدیل مستقل باشد ---
def func_body(src, name):
    """بدنهٔ یک تابع را با شمارش براکت برمی‌گرداند (روی کدِ بدون کامنت)."""
    i = src.find('function %s(' % name)
    if i < 0:
        return None
    j = src.find('{', i)
    d = 0
    for k in range(j, len(src)):
        if src[k] == '{':
            d += 1
        elif src[k] == '}':
            d -= 1
            if d == 0:
                return src[i:k + 1]
    return src[i:]


def flat(s):
    return re.sub(r'\s+', '', s or '')


t365 = strip_comments(ours['archive/legacy_static/tech_365.js'])
rtv = strip_comments(ours['archive/legacy_static/tech_rtv.js'])

# باگ اصلی: دراپ‌داون نوع قیمت، دکمهٔ «تعدیل عملکردی» را روشن/خاموش می‌کرد
_ap = func_body(t365, 'btsApplyPriceType')
chk('btsApplyPriceType() exists', _ap)
chk('btsApplyPriceType never writes rv.adj', _ap is not None and 'rv.adj' not in _ap)
chk('btsApplyPriceType never refetches (no rvLoad)', _ap is not None and 'rvLoad' not in _ap)
chk('btsApplyPriceType never calls rvToggleAdj', _ap is not None and 'rvToggleAdj' not in _ap)
chk('btsApplyPriceType never resyncs adj chip',
    _ap is not None and 'rvSyncAdjChip' not in _ap)

_tp = func_body(rtv, 'rvTogglePriceType')
chk('rvTogglePriceType never writes rv.adj', _tp is not None and 'rv.adj' not in _tp)
chk('rvTogglePriceType never calls rvSyncAdjChip',
    _tp is not None and 'rvSyncAdjChip' not in _tp)

_arr = re.search(r'var BTS_PRICE_TYPES\s*=\s*\[(.*?)\];', t365, re.S)
chk('BTS_PRICE_TYPES carries no adj field', _arr and 'adj' not in _arr.group(1))

chk('rvRerender() defined', re.search(r'function\s+rvRerender\s*\(', rtv))
chk('rvBuildSeries() defined', re.search(r'function\s+rvBuildSeries\s*\(', rtv))
# rvRestoreOverlays خودش رسم‌های قبلی را حذف نمی‌کند؛ اگر قبل از آن
# removeOverlay نشود، هر بازترسیم رسم‌ها را دو‌تا می‌کند.
_rr = func_body(rtv, 'rvRerender')
chk('rvRerender clears overlays before restoring',
    _rr is not None and -1 < _rr.find('removeOverlay') < _rr.find('rvRestoreOverlays'))
_bs = func_body(t365, 'btsBuildPriceSelect')
chk('price select guards event propagation',
    _bs is not None and 'stopImmediatePropagation' in _bs)

# --- ۸) v9.6 — فرم پیش‌شرط‌ها: ساختار Input-Group بدون همپوشانی ---
htm = re.sub(r'<!--.*?-->', ' ', read('archive/legacy_static/index.html'), flags=re.S)
_n = len(re.findall(r'<input[^>]*class="fts-inp"[^>]*>', htm))
_w = len(re.findall(r'<span class="fts-field">\s*<input[^>]*class="fts-inp"', htm))
chk('every fts input sits inside .fts-field (%d/%d)' % (_w, _n), _n >= 10 and _n == _w)

css = strip_comments(read('archive/legacy_static/styles.css'))
_f = re.search(r'\.fts-field\s*\{([^}]*)\}', css)
chk('.fts-field is a flex input-group', _f and 'display:flex' in flat(_f.group(1)))
_u = re.search(r'\.fts-unit\s*\{([^}]*)\}', css)
chk('.fts-unit has no absolute positioning', _u and 'position' not in _u.group(1))

# --- ۹) v9.6 — تقویم تمام‌عرض ---
ccss = strip_comments(read('static/calendar/calendar.css'))
_sh = re.search(r'\.cal-shell\s*\{([^}]*)\}', ccss)
chk('calendar shell is full-width', _sh and 'max-width:100%' in flat(_sh.group(1)))
chk('calendar shell has no pixel cap', _sh and not re.search(r'max-width:\s*\d{3,}px', _sh.group(1)))
_ce = re.search(r'\.cal-cell\s*\{([^}]*)\}', ccss)
chk('day cells keep min-height >= 120px', _ce and re.search(r'min-height:\s*12[0-9]px', _ce.group(1)))
_ev = re.search(r'\.cal-evs\s*\{([^}]*)\}', ccss)
chk('event list scrolls inside day cell', _ev and 'overflow-y:auto' in flat(_ev.group(1)))

# --- ۱۰) v9.7 — رفع انعکاس Bidi در برچسب‌های FTS ---
# علامت‌های جهت‌دار (≥ / ≤) در کنار متن فارسی طبق الگوریتم Bidi جابه‌جا یا
# برعکس رندر می‌شوند. راه‌حل ریشه‌ای «حذف خودِ علامت» است، نه دور زدنش با
# علامت پنهان؛ پس هیچ برچسبی نباید هیچ‌کدام از این چهار نشانه را داشته باشد.
_names = re.findall(r'<span class="fts-name[^"]*">([^<]*)</span>', htm)
chk('no directional math sign in any fts label', bool(_names) and not any(
    s in n for n in _names for s in ('≥', '≤', '>=', '<=', '÷')))
chk('fts labels carry the plain-worded v9.7 titles',
    all(x in ' '.join(_names) for x in
        ['رشد فروش نقطه‌به‌نقطه', 'تورم سالانه (مبنا)',
         'سال متوالی سودآوری (بدون زیان)', 'حاشیه سود ناخالص',
         'حاشیه ایده‌آل (امتیاز کامل)', 'پتانسیل سود ناخالص']))

# بریدگی «پتانسیل سود ناخال...» دقیقاً از nowrap+ellipsis می‌آمد → شکست خط لازم است
_f2 = re.search(r'\.fts-name\s*\{([^}]*)\}', css)
_fname = flat(_f2.group(1)) if _f2 else ''
chk('.fts-name allows line wrapping', bool(_fname) and 'white-space:normal' in _fname)
chk('.fts-name no longer ellipsizes', 'text-overflow' not in _fname and 'nowrap' not in _fname)

# --- ۱۱) v9.7 — دو پارامتر کمکی: ماده ۱۴۱ و نقدشوندگی ---
chk('checkbox #fts_filter_m141 present', 'id="fts_filter_m141"' in htm)
chk('#fts_min_trade_val present', 'id="fts_min_trade_val"' in htm)
chk('min_trade_val carries the همت/میلیارد badge',
    re.search(r'id="fts_min_trade_val"[^>]*>\s*<span class="fts-unit">همت/میلیارد<', htm))
# v9.8.1: handlers moved verbatim into api/*.py + bors_config.py.
app_src = '\n'.join(
    read(p) for p in ['app.py', 'bors_config.py', 'bors_flags.py']
    + [os.path.join('api', f) for f in sorted(os.listdir('api'))
       if f.endswith('.py')])
_d = app_src[app_src.find('FTS_DEFAULTS = {'):]
_d = _d[:_d.find('\n}')]
chk('filter_m141 declared in FTS_DEFAULTS', '"filter_m141"' in _d)
chk('min_trade_val declared in FTS_DEFAULTS', '"min_trade_val"' in _d)
ajs = read('archive/legacy_static/app.js')
chk('app.js treats filter_m141 as bool, not parseFloat',
    re.search(r"FTS_BOOL_KEYS\s*=\s*\[[^\]]*'filter_m141'", ajs))
chk('app.js reads .checked for bool keys', 'el.checked = !!c[k]' in ajs)
chk('app.js always sends the bool key (unchecked must persist)',
    re.search(r"payload\[k\]\s*=\s*!!el\.checked", ajs))
chk('min_trade_val wired into numeric FTS_KEYS',
    re.search(r"FTS_KEYS\s*=\s*\[[^\]]*'min_trade_val'", ajs))
eng = read('fts_engine.py')
chk('fts_engine computes m141_map', 'def m141_map(' in eng)
chk('fts_engine computes avg_trade_value_hmt', 'def avg_trade_value_hmt(' in eng)
chk('m141 actually excludes in both scan paths', eng.count('cfg.get("filter_m141")') >= 2)
chk('liquidity threshold actually excludes in both paths',
    eng.count('cfg.get("min_trade_val"') >= 2)

# --- ۱۲) v9.7 — تفکیک واقعی «آخرین قیمت» از «قیمت پایانی» ---
chk('backend reads the <LAST> column by header name', "get('<LAST>'" in app_src)
chk('backend emits last on every /api/chart candle', '"close": c, "last": last}' in app_src)
chk('chart-db live bar sourced from market_watch.p_last', 'm.p_last' in app_src)
chk('rvToKLine accepts a price field',
    re.search(r'function\s+rvToKLine\s*\(\s*candles,\s*factors,\s*field\s*\)', rtv))
chk('rvToKLine falls back to close when last is missing', 'c.last > 0' in rtv)
chk('rvBuildSeries passes the field down',
    re.search(r'rvToKLine\(rv\._rawC,\s*rv\.adj \? rv\._rawF : null,\s*fld\)', rtv))
chk('rvBuildSeries records the active field', 'rv._seriesField = fld' in rtv)
chk('btsPriceField() defined', re.search(r'function\s+btsPriceField\s*\(', t365))
_ap2 = func_body(t365, 'btsApplyPriceType')
chk('btsApplyPriceType rerenders when the series field changes',
    _ap2 is not None and 'rv._seriesField' in _ap2 and 'btsPriceField' in _ap2)
chk('btsApplyPriceType STILL never writes rv.adj', _ap2 is not None and 'rv.adj' not in _ap2)
chk('btsApplyPriceType STILL never refetches', _ap2 is not None and 'rvLoad' not in _ap2)

# --- ۱۳) v9.7 — نوار شناور: ضخامت ۱..۴ و اولویت لایه‌ها ---
_tt = strip_comments(ours['archive/legacy_static/tech_tools.js'])
chk('stroke width cycles 1..4 (5px removed)', '%4+1' in _tt and '%5+1' not in _tt)
chk('floating toolbar has Move Up', 'data-act="up"' in _tt)
chk('floating toolbar has Move Down', 'data-act="down"' in _tt)
chk('rvLayerShift drives zLevel through overrideOverlay',
    re.search(r'overrideOverlay\(\{\s*id:\s*\w+\.id,\s*zLevel:', _tt))
chk('rvLayerShift normalises ties before swapping', re.search(r'var lv = all\.map\(', _tt))
chk('zLevel persisted on save', 'zLevel: o.zLevel' in rtv)
chk('zLevel restored on reload', 'zLevel: s.zLevel' in rtv)

# --- ۱۴) v9.7 — برچسب نسخه ---
_raw_html = read('archive/legacy_static/index.html')
# به‌جای پینِ «همیشه v=9.7.xِ دستی» (که هر ریلی را می‌شکست): همهٔ ارجاع‌های
# /static/* باید یک نسخهٔ واحد داشته باشند، آن نسخه کفِ لازم را رد کند، و
# هیچ نسخهٔ قدیمی‌ای جا نمانده باشد.
_vers = set(re.findall(r'/static/[^"]*[?&]v=(\d+\.\d+\.\d+)', _raw_html))
chk('all /static refs share ONE cache-bust version (%s)' % sorted(_vers), len(_vers) == 1)
_cur = next(iter(_vers)) if len(_vers) == 1 else (0, 0, 0)
chk('cache-bust version >= 9.7.5 (is %s)' % _cur,
    tuple(int(x) for x in _cur.split('.')) >= (9, 7, 5))
for _stale in ('v=9.7.0', 'v=9.7.1', 'v=9.7.2', 'v=9.7.3', 'v=9.7.4', 'v=9.7.5'):
    chk('no stale %s left in index.html' % _stale, _stale not in _raw_html)
chk('mstat.js is actually loaded (v9.7.5 فاز ۱)', 'mstat.js' in _raw_html)

# --- ۱۵) v9.7 — اصلاحات ممیزی ابزارهای رسم ---
_ap = strip_comments(read('archive/legacy_static/app.js'))
_rtv = strip_comments(rtv)

chk('stDel exists (single storage blob means removeItem cannot reach its keys)',
    re.search(r'function stDel\(\s*k\s*\)', _ap))
chk('stDel deletes from _STATE and re-persists the blob',
    re.search(r'function stDel\([\s\S]{0,400}?delete _STATE\[k\][\s\S]{0,200}?localStorage\.setItem\(STATE_KEY', _ap))
chk('rvClearAll clears through stDel, not raw localStorage',
    re.search(r'function rvClearAll\([\s\S]{0,600}?stDel\(\'tech_\'', _rtv))
chk('no live localStorage.removeItem of a stSet-owned key',
    not re.search(r'localStorage\.removeItem\(\s*[\'"]tech_', _rtv + _ap + _tt))
# حذف با کیبورد باید مثل دکمهٔ 🗑 ذخیره را به‌روز کند، وگرنه رسم برمی‌گردد
_kb = re.search(r'const selId = info && info\.overlay[\s\S]{0,500}?return;', _rtv)
chk('Delete/Backspace path re-saves overlays after removal',
    bool(_kb) and 'rvSaveOverlays()' in _kb.group(0))
chk('rvDrawDelete re-saves overlays', re.search(
    r'function rvDrawDelete\([\s\S]{0,400}?rvSaveOverlays\(\)', _rtv))
chk('rvDeleteLast re-saves overlays', re.search(
    r'function rvDeleteLast\([\s\S]{0,900}?rvSaveOverlays\(\)', _rtv))

# هر شش دکمهٔ نوار شناور باید هندلر .onclick داشته باشد (dispatch با case نیست)
for _a in ['gear', 'up', 'down', 'lock', 'del', 'close']:
    chk('toolbar action "%s" is wired' % _a,
        re.search(r'data-act="%s"[\s\S]{0,14}?\.onclick\s*=' % _a, _tt))
chk('lock button persists the new lock state',
    re.search(r'data-act="lock"[\s\S]{0,14}?\.onclick[\s\S]{0,500}?rvSaveOverlays\(\)', _tt))
chk('lock goes through overrideOverlay',
    re.search(r'overrideOverlay\(\{ id: last\.id, lock: nl \}\)', _tt))
chk('stroke style offers solid/dashed/dotted with dashedValue',
    all(t in _tt for t in ['ممتد', 'خط‌چین', 'نقطه‌چین', 'dashedValue']))

# --- ۱۶) v9.7.1 — بدهی فنی tech_panel + باگ مقیاس + ریس بارگذاری چارت ---
chk('static/tech_panel.js is gone', not os.path.exists('archive/legacy_static/tech_panel.js'))
chk('lightweight-charts bundle is gone',
    not os.path.exists('archive/legacy_static/lightweight-charts.standalone.production.js'))
chk('index.html no longer references tech_panel', 'tech_panel' not in _raw_html)
chk('index.html no longer carries #techWindow markup', 'techWindow' not in _raw_html)
chk('no live LightweightCharts reference in first-party JS',
    not re.search(r'\bLightweightCharts\b', _ap + rtv + t365 + _tt))

# دکمهٔ 📊 مودال تحلیل باید به موتور زنده برود، نه پنل مرده (ReferenceError).
# لنگر روی modalSymbol می‌گیرد: چند icon-btn در سند هست، ولی فقط همین یکی
# در هدر chartModal نمادِ بازِ مودال را به یک چارت می‌دهد.
_btn = re.search(r'<button class="icon-btn"[^>]*onclick="([^"]*modalSymbol[^"]*)"', htm)
chk('modal 📊 button found', _btn)
chk('modal 📊 button routes to gotoChart()', _btn and 'gotoChart(' in _btn.group(1))
chk('modal 📊 button no longer calls openTechPanel()',
    _btn and 'openTechPanel' not in _btn.group(1))


# rvSetScale: قبلاً rv.logScale را ست و بی‌درنگ rvToggleLog() می‌زد → دو تاگل → مقیاس برعکس
chk('rvToggleLog() removed (orphaned + double-toggling)',
    not re.search(r'function\s+rvToggleLog\s*\(', rtv))
_scl = func_body(rtv, 'rvSetScale')
chk('rvSetScale exists', _scl)
chk('rvSetScale never calls rvToggleLog (inverted-scale bug)',
    _scl is not None and 'rvToggleLog' not in _scl)
chk('rvSetScale delegates to btsSetScale', _scl is not None and 'btsSetScale' in _scl)
chk('rvSetScale persists the axis choice (works before chart exists)',
    _scl is not None and 'btsSet.scales.axis' in _scl)
chk('rvSetScale covers all three v10 axis names',
    _scl is not None and all(n in _scl for n in ('logarithm', 'percentage', 'normal')))
chk('btsSetScale verifies against the real axis (getYAxes)',
    'btsAxis()' in func_body(t365, 'btsSetScale'))

# gotoChart: دو rvLoad همزمان باعث جای‌گزینی نماد می‌شد
_gc = func_body(_ap, 'gotoChart')
chk('gotoChart() exists', _gc)
chk('gotoChart never calls rvLoad directly (double-load race)',
    _gc is not None and 'rvLoad(' not in _gc)
chk('gotoChart sets rv.sym BEFORE switchView',
    _gc is not None and -1 < _gc.find('rv.sym =') < _gc.find('switchView('))
# اسکرین‌شات مرورگر ثابت کرد مودال باز، چارت تازه‌باز شده را می‌پوشاند
chk('gotoChart closes the analysis modal',
    _gc is not None and 'closeModal()' in _gc)


# CSS یتیمِ پنل حذف‌شده
chk('no orphan .tech-* panel rules left in styles.css',
    not re.search(r'\.tech-(window|shell|head|chips?|body|chart|chart-sm|legend|msg|foot|stats|title|lbl)\b', css))

# --- ۱۷) v9.7.1 — دکوراسیون اپ نباید مثل رسم کاربر ذخیره/بازیابی شود ---
# btsPrevCloseLine یک overlay می‌ساخت بدون id؛ KLineCharts شناسهٔ تصادفی می‌زد،
# پس rvSaveOverlays آن را در بلاوب tech_<sym> می‌نوشت و هر reload یک نسخهٔ
# تکراری رویش می‌گذاشت (با CDP روی پروفایل تازه: ۱ قبل، ۲ بعد از reload).
chk('rvIsDecoration() exists and covers both prefixes',
    re.search(r'function\s+rvIsDecoration\s*\(', _rtv) and
    flat(func_body(_rtv, 'rvIsDecoration')).find("indexOf('auto_')===0") >= 0 and
    flat(func_body(_rtv, 'rvIsDecoration')).find("indexOf('bts_')===0") >= 0)

chk('btsPrevCloseLine gives the overlay a stable id',
    re.search(r"id:\s*BTS_PREV_CLOSE_ID", t365) and
    re.search(r"BTS_PREV_CLOSE_ID\s*=\s*'bts_prev_close_line'", t365))
for _fn in ['rvSaveOverlays', 'rvPersistTech', 'rvRestoreOverlays']:
    _b = func_body(rtv, _fn)
    chk('%s filters decorations through rvIsDecoration' % _fn,
        _b is not None and 'rvIsDecoration' in _b)
chk('no live startsWith(\'auto_\') left in tech_rtv.js',
    "startsWith('auto_')" not in _rtv)

# --- ۱۸) v9.7.2 — همگام‌سازی پرچم مقیاس، پاک‌سازی CSS یتیم، دورهٔ اندیکاتورها ---
# ۱۸-الف) rv.logScale در مسیر لود بازنویسی نمی‌شد؛ بعد از reload محور لگاریتمی
# بود ولی پرچم false می‌ماند و همان مقدار نادرست در tech_<sym> ذخیره می‌شد.
_ap365 = func_body(t365, 'btsApplySettings')
chk('btsApplySettings exists', _ap365)
chk('btsApplySettings syncs rv.logScale on load',
    _ap365 is not None and 'rv.logScale' in _ap365)
chk('the sync trusts the axis the library actually built (btsAxis), not the request',
    _ap365 is not None and 'btsAxis()' in _ap365)
chk('rv.logScale is derived from the logarithm axis name',
    _ap365 is not None and "'logarithm'" in _ap365)

# ۱۸-ب) ۹ کلاس یتیمی که در v9.7.1 شناسایی شدند باید برنگردند.
_orphan9 = ['tv-pop-bar', 'tv-pop-btns', 'tv-pop-title', 'tv5-badge', 'tv5-danger',
            'tv5-sym', 'tv5-sym-name', 'tv5-tfs', 'tv5-tools']
chk('the 9 orphan CSS classes stay deleted from styles.css',
    not re.search(r'\.(' + '|'.join(_orphan9) + r')\b', css))
# قانون‌های هم‌خانواده که هنوز زنده‌اند و نباید حذف می‌شدند:
chk('.tv-pop / .tv-pop-body survived the cleanup (still referenced)',
    '.tv-pop {' in css and '.tv-pop-body' in css)
chk('.tv5-tf / .tv5-btn survived the cleanup (still referenced)',
    '.tv5-tf {' in css and '.tv5-btn {' in css)

# ۱۸-پ) دورهٔ پیش‌فرض اندیکاتورها: RSI هفتگی ۷ / روزانه ۱۴، EMA ۲۰-۵۰-۲۰۰، BOLL ۲۰-۲
chk('RTV_IND_DEFAULTS exists', 'RTV_IND_DEFAULTS' in rtv)
_dfl = func_body(rtv, 'rvIndParams')
chk('rvIndParams() exists to resolve per-timeframe params', _dfl)
chk('rvIndToggle applies calcParams from rvIndParams',
    'rvIndParams(' in func_body(rtv, 'rvIndToggle'))
chk('rvIndSyncParams re-applies periods after a timeframe switch',
    'rvIndSyncParams' in func_body(rtv, 'rvLoad'))
chk('rvIndSyncParams uses overrideIndicator (not createIndicator)',
    'overrideIndicator' in func_body(rtv, 'rvIndSyncParams'))
chk('rvIndSyncParams skips no-op overrides (guards pane churn)',
    'calcParams' in func_body(rtv, 'rvIndSyncParams'))
chk('RSI weekly period is 7', re.search(r"W:\s*7", rtv) is not None)
chk('RSI daily period stays 14', re.search(r"D:\s*14", rtv) is not None)
chk('EMA defaults are 20/50/200', re.search(r"EMA:\s*\{\s*fixed:\s*\[\s*20,\s*50,\s*200\s*\]", rtv) is not None)
chk('BOLL defaults are 20/2', re.search(r"BOLL:\s*\{\s*fixed:\s*\[\s*20,\s*2\s*\]", rtv) is not None)

fails = [n for n, ok in checks if not ok]


for n, ok in checks:
    print('  %s %s' % ('PASS' if ok else 'FAIL', n))
print('\n%d checks, %d failed' % (len(checks), len(fails)))
sys.exit(1 if fails else 0)
