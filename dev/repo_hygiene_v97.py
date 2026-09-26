"""repo_hygiene_v97.py — گارد پاک‌سازی v9.7.1

چهار چیز را قفل می‌کند تا بازنویسی‌های بعدی، کد مردهٔ حذف‌شده را زنده نکنند و
ساختار پوشه‌ها را نشکنند:

  ۱) توابع مردهٔ JS/Py که حذف شدند برنگردند (و ارجاع جدیدی برایشان ساخته نشود).
  ۲) فایل‌های اسکرچ/خروجی/وضعیت-زمان‌اجرا دوباره track نشوند.
  ۳) اسکریپت‌های منتقل‌شده به scripts/ هنوز ROOT را به ریشهٔ مخزن حل می‌کنند
     (این همان چیزی است که با جابه‌جایی ساکت می‌شکند).
  ۴) هر بسته‌ای که در src/ مستقیم import می‌شود، در package.json هم اعلام
     شده باشد (گام ۹ — klinecharts هشت‌جا import می‌شد ولی فقط peer بود).

اجرا:  python dev/repo_hygiene_v97.py
"""
import io
import json
import os
import re
import subprocess
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)

CHECKS = []


def ck(label, cond, detail=''):
    CHECKS.append((bool(cond), label, detail))


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except OSError:
        return ''


def git(*a):
    return subprocess.run(['git'] + list(a), capture_output=True, text=True,
                          encoding='utf-8', errors='replace').stdout


# ── ۱. توابع مردهٔ JS ────────────────────────────────────────────────────
DEAD_JS = {
    'archive/legacy_static/app.js': ['onFontSlider', 'faDigits', 'confirmCodalStart',
                      'setAutoRefreshInterval', 'clearAllFilters', 'missingReason',
                      'openCodalSettings', 'closeCodalSettings'],
    'archive/legacy_static/tech_rtv.js': ['rvRenderChart', 'rvTogglePriceScaleMenu', 'rvSetScaleType',
                           'rvResetPriceScale', 'rvToggleScaleSide', 'rvToggleAutoScale',
                           'rvFibExtStart', 'rvFibRecalc', 'rvRailHide', 'rvLockAll',
                           'rvToggleMagnet', 'rvZoomFit', 'rvFocusSearch', 'rvReplay',
                           'rvFullscreen', 'rvShareChart', 'rvPublishChart', 'rvToolFa',
                           'rvAutoSaveStatus', 'rvFontMenu', 'rvToggleItvMenu'],
    'archive/legacy_static/tech_tools.js': ['FIBS_EXT'],
}
# کل مخزن (JS + HTML) — فراخوان می‌تواند از onclick هم بیاید.
CORPUS_JS = [p for p in git('ls-files').split()
             if p.endswith(('.js', '.html')) and '/vendor/' not in '/' + p]
CORPUS_TXT = {p: read(p) for p in CORPUS_JS}

for path, names in DEAD_JS.items():
    src = read(path)
    for nm in names:
        ck('%s: %s حذف مانده' % (os.path.basename(path), nm),
           not re.search(r'\bfunction\s+%s\s*\(' % re.escape(nm), src))
        callers = [p for p, t in CORPUS_TXT.items()
                   if p != path and re.search(r'\b%s\s*\(' % re.escape(nm), t)]
        ck('%s: هیچ فراخوان باقی نمانده' % nm, not callers, ','.join(callers))

# rvRerender جایگزین rvRenderChart است و باید زنده بماند.
ck('rvRerender (جایگزین) هنوز تعریف شده',
   'function rvRerender(' in read('archive/legacy_static/tech_rtv.js'))
ck('rvRerender از tech_365 صدا زده می‌شود', 'rvRerender' in read('archive/legacy_static/tech_365.js'))

# ── ۲. توابع مردهٔ پایتون ────────────────────────────────────────────────
# v9.8.1: the monolith's bodies live in api/*.py + bors_config.py now,
# so the dead-code sweep must cover the whole backend, not just app.py.
BACKEND_PY = ['app.py', 'bors_config.py', 'bors_flags.py'] + [
    os.path.join('api', f) for f in sorted(os.listdir('api'))
    if f.endswith('.py')] if os.path.isdir('api') else ['app.py']
DEAD_PY = {
    'BACKEND': ['_fmt_bil', '_invalidate_market_cache', '_fs_count'],
    'codal_fetcher.py': ['_safe_get', '_process_one'],
    'tests/auto_ui_stress_test.py': ['probe_endpoints'],
}
for path, names in DEAD_PY.items():
    files = BACKEND_PY if path == 'BACKEND' else [path]
    src = '\n'.join(read(f) for f in files)
    for nm in names:
        ck('backend: def %s حذف مانده' % nm,
           not re.search(r'^\s*def\s+%s\s*\(' % re.escape(nm), src, re.M))

ck('confluence.py حذف شده', not os.path.exists('confluence.py'))

# route تکراری /api/market/sync-state نباید برگردد
# v9.8.1: app.py is the shim; the route is registered in api/*.py.
BACKEND_ALL = '\n'.join(read(f) for f in BACKEND_PY)
n_sync_state = len(re.findall(r'@(?:app|router)\.get\("/api/market/sync-state"\)',
                              BACKEND_ALL))
ck('sync-state فقط یک route دارد', n_sync_state == 1, 'count=%d' % n_sync_state)


# ── ۳. فایل‌های زائد نباید دوباره track شوند ─────────────────────────────
NEVER_TRACKED = ['_test_fts.txt', 'fts_v8_test_report.txt', 'syn3.txt',
                 '.phase1_backup_dir.txt', 'ex_test.xlsx', 'confluence.py',
                 'rahavard_intrinsic.json', 'sb_config.json', 'sync_summary.json',
                 'archive/legacy_static/klinecharts.min.js', 'dev/camo_test.png', 'dev/task1.log',
                 'dev/test_fts_v8.py', 'dev/dom_test.js', 'dev/serve_check_v91.py']
tracked = set(git('ls-files').split())
for f in NEVER_TRACKED:
    ck('%s track نیست' % f, f not in tracked)

# هیچ فایل track‌شده‌ای نباید ignore شده باشد
ignored_tracked = [l for l in git('ls-files', '-i', '-c',
                                  '--exclude-standard').split('\n') if l.strip()]
ck('هیچ فایل track‌شده‌ای ignore نشده', not ignored_tracked,
   ','.join(ignored_tracked))

# ── ۴. ساختار پوشه‌ها ────────────────────────────────────────────────────
MUST_EXIST = ['app.py', 'test_tsetmc.py', 'fts_engine.py', 'codal_fetcher.py',
              'notifier.py', 'bootstrap_first_run.py',
              'start_dashboard.py', 'bors_entry.py', 'archive/legacy_static/index.html',
              'REPO_MAP.md', 'dev/run_all_tests.py', 'scripts/build_exe.py']
for f in MUST_EXIST:
    ck('%s سرِ جایش است' % f, os.path.exists(f))

# ── ۵. اسکریپت‌های scripts/ باید ROOT را به ریشهٔ مخزن حل کنند ───────────
for f in sorted(git('ls-files', 'scripts').split()):
    if not f.endswith('.py'):
        continue
    m = re.search(r'^(?:ROOT|HERE)\s*=\s*os\.path\.dirname\((.*)\)\s*(?:#.*)?$',
                  read(f), re.M)
    if not m:
        continue
    # دو dirname تو در تو == ریشهٔ مخزن، چون فایل داخل scripts/ است
    ck('%s به ریشهٔ مخزن می‌رسد' % os.path.basename(f),
       m.group(1).startswith('os.path.dirname(os.path.abspath'),
       'نیاز به dirname(dirname(__file__))')

# ── ۶. test_tsetmc با نام پروسه سنجیده می‌شود → جابه‌جا/تغییرنام نشود ────
# v9.8.1: app.py is the shim; constants consolidated into bors_config.py.
app_src = read('app.py')
cfg_src = read('bors_config.py')
ck('backend هنوز test_tsetmc را import می‌کند',
   'import test_tsetmc' in BACKEND_ALL)
ck('backend زنده‌بودن را با نام پروسه می‌سنجد',
   '_count_procs("test_tsetmc")' in BACKEND_ALL
   or "match 'test_tsetmc'" in BACKEND_ALL)

# ── ۷. ثابت‌های مسیر باید تجمیع شده باشند (یک تعریف هر کدام) ─────────────
for const in ['APP_DIR', 'STATUS_PATH', 'MARKET_STATUS_PATH', 'CONTROL_PATH',
              'FTS_CONFIG_PATH', '_ADB_CFG']:
    n = len(re.findall(r'^%s\s*=' % const, cfg_src, re.M))
    ck('%s دقیقاً یک تعریف دارد (bors_config.py)' % const, n == 1,
       'count=%d' % n)
ck('dirname(abspath(__file__)) فقط برای APP_DIR است',
   len(re.findall(r'os\.path\.dirname\(os\.path\.abspath\(__file__\)\)',
                  cfg_src)) == 1,
   'فقط تعریف APP_DIR مجاز است')

# ── ۸. market.db باید کنار EXE/CWD بماند ─────────────────────────────────
ck('DB_PATH نسبی به market.db (نه data/) حل می‌شود',
   ('DB_PATH = _resolve_market_db()' in cfg_src) and
   ('market.db' in cfg_src) and ('data/market.db' not in cfg_src.replace('WORK_DIR', '')),
   'باید از _resolve_market_db() استفاده کند و به data/ نپردازد')
ck('bors_entry.py market.db را کنار EXE می‌خواهد', 'market.db' in read('bors_entry.py'))

# ── ۹. importِ بسته باید در package.json اعلام شده باشد ──────────────────
# klinecharts هشت‌جا مستقیم import می‌شد ولی فقط به‌عنوانِ peerِِ بسته‌ای
# دیگر در node_modules بود (DEPS-1). npm آن را روزِ اول می‌سازد و فردا
# نمی‌سازد؛ «در CI سبز بود» چیزی را اثبات نمی‌کند چون lockfile هرجفت را
# نگه می‌دارد. اعلامِ صریح تنها راهِ درست است.
_pkg = json.loads(read(os.path.join('frontend', 'package.json')))
_declared = set(_pkg.get('dependencies', {})) | set(_pkg.get('devDependencies', {}))
_paths = json.loads(re.sub(r'^\s*//.*$', '',
                           read(os.path.join('frontend', 'tsconfig.json')), flags=re.M)
                    )['compilerOptions']['paths']
# کلیدِ alias در tsconfig به شکل «@shared/*» است؛ پسوندِ star می‌رود و خودِ
# @shared هم باید شمرده شود (@contracts/index).
_aliases = {k.split('*')[0].rstrip('/') for k in _paths}
_BUILTIN = {'fs', 'path', 'os', 'url', 'util', 'events', 'crypto', 'http', 'https',
            'stream', 'assert', 'buffer', 'child_process', 'module', 'process', 'vm', 'zlib'}
# فقط «from '…'»، «import '…'» و فراخوانیِ import()/require() — نه هر «from»ی
# که وسط یک عبارتِ type‌ی می‌آید.
_SPEC_RE = re.compile(r"""\b(?:from|import)\s+['"]([^'"\n]+)['"]"""
                      r"""|\b(?:import|require)\(\s*['"]([^'"\n]+)['"]\s*\)""")


def _bare_specifiers(src):
    for m in _SPEC_RE.finditer(src):
        yield m.group(1) or m.group(2)


_undeclared = {}
for _root, _dirs, _files in os.walk(os.path.join('frontend', 'src')):
    _dirs[:] = [d for d in _dirs if d != 'node_modules']
    for _f in _files:
        if not _f.endswith(('.ts', '.tsx')):
            continue
        _path = os.path.join(_root, _f)
        for _spec in _bare_specifiers(read(_path)):
            if _spec.startswith(('.', '/', '#')) or _spec.startswith('node:'):
                continue
            _name = '/'.join(_spec.split('/')[:2]) if _spec.startswith('@') else _spec.split('/')[0]
            if _name.split('/')[0] in _aliases or _name in _BUILTIN or _name in _declared:
                continue
            _undeclared.setdefault(_name, _path)
ck('هر importِ بسته‌ای در package.json اعلام شده باشد',
   not _undeclared,
   ', '.join('%s←%s' % (n, f) for n, f in sorted(_undeclared.items())))

passed = sum(1 for ok, _, _ in CHECKS if ok)
for ok, label, detail in CHECKS:
    if not ok:
        print('FAIL  %s %s' % (label, ('| ' + detail) if detail else ''))
print('%d/%d passed' % (passed, len(CHECKS)))
print('REPO HYGIENE OK' if passed == len(CHECKS) else 'REPO HYGIENE FAILED')
sys.exit(0 if passed == len(CHECKS) else 1)
