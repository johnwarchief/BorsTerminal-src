"""گارد سازگاریِ چارت — معماریِ فعلی (React + klinecharts@10 npm)
--------------------------------------------------------------
جانشینِ `chart_api_check_v95`. آن گارد باندلِ vendoredِ رابطۀ legacy
(`archive/legacy_static/*`) را می‌سنجید که بازنشسته شده و در مخزن نیست؛ پس خودش
روی `FileNotFoundError` می‌مرد. طبقِ رأیِ مالک (۱۴۰۵-۰۷-۱۷) گاردِ کُهنه **حذف
نمی‌شود**؛ با آزمونِ واقعیِ همان چیزی که امروز رندر می‌شود جایگزین می‌شود.

چیزی که راستاً نگهبانی می‌کند (همان روحِ «کلیدِ ما باید در کتابخانه باشد»):
  ۱) نسخۀ npmِ `klinecharts` با سورسِ `package.json` یک majors باشد (driftِ نسخه
     همان کلاسِ باگِ «بی‌صدا بی‌اثر» را برمی‌گرداند).
  ۲) هر نامی که کدِ ما از `klinecharts` import می‌کند در `.d.ts` کتابخانه
     واقعاً export شده باشد. اگر ارتقا/تغییرِ نام این APIها را بردارد، اینجا
     قرمز می‌شود — نه اینکه چارت درِ مرورگر بی‌صدا بشکند.
  ۳) مسیرِ legacyِ مُرده برگردد و هیچ سورسِ درون‌برنامه‌ای به آن ارجاع ندهد
     (تا گاردِ بعدی دوباره روی فایلِ غایب نمیرد).
  ۴) نشانه‌هایِ روشنِ باگ‌هایِ legacy (candle.candle.* / rvToggleLogScale /
     crosshair mode 'strong_magnet') به‌عنوان کدِ زنده برنگردند.

این گارد شبکه/DB لازم ندارد و رویِ cloneِ تازه (بدونِ build) هم می‌دود.
اجرا:  python dev/chart_api_check_v95.py
"""
import glob
import io
import json
import os
import re
import sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

FE = os.path.join('frontend', 'node_modules', 'klinecharts')
PKG_JSON = os.path.join('frontend', 'package.json')

checks = []


def chk(name, cond):
    checks.append((name, bool(cond)))


def read(p):
    if not os.path.exists(p):
        return ''
    return io.open(p, encoding='utf-8', errors='replace').read()


def strip_block_comments(s):
    s = re.sub(r'/\*.*?\*/', '', s, flags=re.S)
    return re.sub(r'//.*', '', s)


# ── ۱) نسخۀ npm ↔ package.json ──────────────────────────────────────────────
pkg = {}
try:
    pkg = json.loads(read(PKG_JSON) or '{}')
except Exception:
    pkg = {}
declared = (pkg.get('dependencies', {}).get('klinecharts')
            or pkg.get('devDependencies', {}).get('klinecharts') or '')
installed_pkg = {}
try:
    installed_pkg = json.loads(read(os.path.join(FE, 'package.json')) or '{}')
except Exception:
    installed_pkg = {}
installed = installed_pkg.get('version', '')


def major(v):
    m = re.search(r'(\d+)', v or '')
    return m.group(1) if m else None


chk('klinecharts installed (%s)' % (installed or 'MISSING'), bool(installed))
chk('package.json declares klinecharts (%s)' % (declared or 'MISSING'), bool(declared))
chk('installed major == declared major (v10)',
    major(installed) is not None and major(installed) == major(declared))

# ── ۲) هر نامِ import‌شده باید در .d.ts خروجی داشته باشد ────────────────────
dts = read(os.path.join(FE, 'dist', 'index.d.ts'))
# هر نامی که کتابخانه export می‌کند: توابع/ثابت‌ها و typeها/interfaceها (کدِ ما
# typeها را گاهی بدونِ کلیدواژهٔ `type` import می‌کند؛ آن‌ها واقعی‌اند نه گم‌شده).
exported = set(re.findall(
    r'export\s+(?:declare\s+)?(?:function|const|var|class|interface|type|enum|namespace)\s+(\w+)',
    dts))

imported = set()
for src in glob.glob(os.path.join('frontend', 'src', '**', '*.ts*'), recursive=True):
    txt = strip_block_comments(read(src))
    for m in re.finditer(r'import\s*\{([^}]*)\}\s*from\s*[\'"]klinecharts[\'"]', txt):
        for raw in m.group(1).split(','):
            tok = raw.strip()
            if not tok or tok.startswith('type '):
                continue  # importِ نوع با `export declare function` سنجیده نمی‌شود
            imported.add(tok.split()[-1])

missing = sorted(imported - exported)
chk('کد ما از klinecharts نامِ ناشناخته import نمی‌کند (missing=%s)' % (missing or 'none'),
    not missing)
# APIهایِ ستونِ این موتور باید همان‌جا باشند (اثباتِ مثبتِ سنسور):
for name in ('init', 'dispose', 'registerOverlay', 'registerIndicator'):
    chk('klinecharts exports %s()' % name, name in exported)
    chk('source imports %s from klinecharts' % name, name in imported)

# ── ۳) مسیرِ legacyِ مُرده برنگردد و ارجاعِ زنده نداشته باشد ──────────────────
chk('archive/legacy_static/vendor/klinecharts.min.js is gone',
    not os.path.exists(os.path.join('archive', 'legacy_static', 'vendor', 'klinecharts.min.js')))
# فقط سورسِ اپ (bک‌اند و رابطۀ React): این‌ها اگر به bundleِ مُرده ارجاع دهند، درِ
# runtime می‌میرند. dev/ و خودِ همین گارد حق دارند در کامنت مسیرِ بازنشسته را نام
# ببرند، پس بیرونِ این اسکن‌اند.
first_party = []
for base in ('api', os.path.join('frontend', 'src')):
    first_party += glob.glob(os.path.join(base, '**', '*'), recursive=True)
refs = [p for p in first_party
        if os.path.isfile(p) and p.endswith(('.py', '.ts', '.tsx', '.js'))
        and 'legacy_static' in strip_block_comments(read(p))]
chk('no shipped source reads legacy_static (%s)' % (refs[:3] or 'none'), not refs)

# ── ۴) نشانه‌هایِ باگِ «بی‌صدا بی‌اثر» در رابطۀ زنده برنگردند ─────────────────
tech_src = strip_block_comments(
    '\n'.join(read(p) for p in
              glob.glob(os.path.join('frontend', 'src', 'features', 'technical', '**', '*.ts*'),
                        recursive=True)))
chk('no candle.candle.* (v10 is candle.bar.*)', 'candle.candle' not in tech_src)
chk('no rvToggleLogScale (dead v9 helper)', 'rvToggleLogScale' not in tech_src)
chk("no crosshair mode 'strong_magnet' (not a v10 key)", 'strong_magnet' not in tech_src)

# ── کنترلِ منفی: سنسورِ «نامِ گم‌شده» باید واقعاً گم را ببیند ──────────────────
# اگر این خط سبز شود یعنی `missing` بیرونی تشخیص می‌دهد، نه اینکه همیشه خالی است.
canary = sorted(({'init', 'this_api_does_not_exist'}) - exported)
chk('negative control: sensor flags a genuinely-absent export',
    'this_api_does_not_exist' in canary and 'init' not in canary)

fails = [n for n, ok in checks if not ok]
for n, ok in checks:
    print('  %s %s' % ('PASS' if ok else 'FAIL', n))
print('\n%d/%d passed' % (len(checks) - len(fails), len(checks)))
sys.exit(1 if fails else 0)
