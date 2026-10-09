#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""v9.7.3 — گارد واچ‌لیست کاربر + ماتریس تایید سه‌گانه (watchlist_store.py).

چرا این تست متولد شد: ستون بنیادیِ موتور تایید، به fts_engine وابسته است و
fts_engine تا دیروز با باگِ نوشتار عربی/فارسی، یک نماد را «بی‌داده» و همان
نماد را در اسکرینر «پر امتیاز» نشان می‌داد. اگر واچ‌لیست روی کلیدِ خام ساخته
می‌شد، همان شرکت دو ردیف ذخیره می‌گرفت و ماتریس دو داوری متفاوت نشان می‌داد.
پس این فایل هم CRUD را قفل می‌کند و هم «دو املا = یک ردیف = یک داوری» را.

سه چیز دیگری که قفل می‌کند:
  ۱) ماتریس read-only است: هیچ INSERT/CREATE در مسیرش نیست (فقط جدول انتخاب
     کاربر نوشته می‌شود، آن هم در مسیر add/remove، نه در /api/watchlist/matrix).
  ۲) ضدِN+1: build_ctx و bulk_scan هر دو «یک‌بار» برای کل واچ‌لیست اجرا شوند.
  ۳) قرارداد norm_fa بین پایتون و selection.js حفظ شود (ستارهٔ ☆/★ سمت کلاینت
     هم باید «داريك» و «داریک» را یکی ببیند).

اجرا:  python dev/watchlist_matrix_v973.py
"""
import ast
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return cond


def fn_body(src, name):
    m = re.search(r'\ndef %s\(.*?(?=\ndef |\Z)' % re.escape(name), src, re.S)
    body = m.group(0) if m else ''
    return re.sub(r'"""[\s\S]*?"""|#[^\n]*', '', body)


STORE = 'watchlist_store.py'
ck(os.path.exists(STORE), '%s exists' % STORE)
src = io.open(STORE, encoding='utf-8').read() if os.path.exists(STORE) else ''

# ---------- گارد ۱: خلوص و مرز مسئولیت ----------
ck(not re.search(r'^\s*(from|import)\s+(fastapi|starlette|uvicorn|httpx|requests)\b',
                 src, re.M),
   'watchlist_store has no HTTP import (CRUD stays in api/watchlist.py)')
ck('confidence_engine' in src and 'import confidence_engine' in src,
   'matrix delegates pillar math to confidence_engine (no re-implementation)')
mbody = fn_body(src, 'matrix')
ck('bulk_scan' not in mbody and 'scan_symbol' not in mbody,
   'matrix does not call FTS directly (goes through confidence_engine.fund_map)')
ck('build_ctx' in mbody and 'fund_rows' in mbody,
   'matrix builds ctx once and passes fund_rows into triple_many (anti-N+1 wiring)')

# confidence_engine باید همچنان بی‌نوشتن بماند؛ جدول جدید نباید به آن نشت کند
cesrc = io.open('confidence_engine.py', encoding='utf-8').read()
ck(not re.search(r'\bCREATE\s+(TABLE|INDEX)\b', cesrc, re.I)
   and 'user_watchlists' not in cesrc,
   'confidence_engine stays schema-free and does not touch user_watchlists')
ck(not re.search(r'\bconn\.(execute|executescript)\(\s*["\'](INSERT|UPDATE|DELETE)',
                 cesrc),
   'confidence_engine still writes no rows')

# ---------- گارد ۲: routeها در api/watchlist.py و read-only بودنِ ماتریس ----------
# v9.8.1: routes live in api/watchlist.py as @router.<verb>; _core.py
# provisions user_watchlists inside get_db().
appsrc = io.open(os.path.join('api', 'watchlist.py'),
                 encoding='utf-8').read()
coresrc = io.open(os.path.join('api', '_core.py'),
                  encoding='utf-8').read()
for verb, path, fname in (
        ('get', '/api/watchlist', 'get_watchlist'),
        ('post', '/api/watchlist', 'post_watchlist'),
        ('delete', '/api/watchlist/{symbol}', 'delete_watchlist'),
        ('get', '/api/watchlist/matrix', 'get_watchlist_matrix')):
    ck(re.search(r'@router\.%s\("%s"\)\s*\ndef %s\(' % (verb, re.escape(path), fname), appsrc),
       'route %s %s -> %s() is registered' % (verb.upper(), path, fname))
rb = fn_body(appsrc, 'get_watchlist_matrix')
ck(not re.search(r'INSERT|UPDATE|CREATE|DROP', rb, re.I),
   '/api/watchlist/matrix body contains no write statement')
ck('isinstance(symbols, str)' in rb,
   'matrix route guards the Query sentinel (direct call must read the table, '
   'not judge the literal repr of Query(None))')
ck('watchlist_store.matrix' in rb,
   'matrix route is a thin wrapper over watchlist_store.matrix')
ck(re.search(r'watchlist_store\.ensure_table', coresrc),
   'get_db() provisions user_watchlists idempotently (same pattern as selection_decisions)')

# ---------- گارد ۳: قرارداد norm_fa بین پایتون و JS ----------
js = io.open(os.path.join('archive/legacy_static', 'selection.js'), encoding='utf-8').read()
mjs = re.search(r'function nfa\(s\)\s*\{([\s\S]*?)\n\s*\}', js)
ck(bool(mjs), 'selection.js defines nfa() mirroring norm_fa')
if mjs:
    body = mjs.group(1)
    pairs = re.findall(r'replace\(/\\u([0-9a-f]{4})/g,\s*.\\u([0-9a-f]{4}).', body)
    jmap = {int(a, 16): int(b, 16) for a, b in pairs}
    probe = ['\u064a', '\u0643', '\u0649']
    import fts_engine
    ok = all(ord(fts_engine.norm_fa(c)) == jmap.get(ord(c), ord(c)) for c in probe)
    ck(ok, 'JS nfa() maps the same codepoints as fts_engine.norm_fa: %s'
       % {hex(k): hex(v) for k, v in sorted(jmap.items())})
    ck('\\u200c' in body, 'JS nfa() also strips ZWNJ like norm_fa')
    ck('WL.has' in js and 'nfa(' in js,
       'watch star uses the normalized key (one star for both spellings)')
ck('watchMatrixBody' in io.open(os.path.join('archive/legacy_static', 'index.html'),
                                encoding='utf-8').read(),
   'index.html carries the matrix table skeleton for WL.render()')


# ---------- گارد ۴: CRUD روی یک بانکِ موقت (market.db هرگز نوشته نمی‌شود) ----------
# DDL در حالت تراکنشِ قدیمیِ پایتون «ضمنی commit» می‌کند؛ اگر این بخش روی
# market.db اجرا شود، جدول برای همیشه ساخته می‌شود. پس بانکِ دورریختنی.
import watchlist_store as W            # noqa: E402

TMP = os.path.join(tempfile.gettempdir(), 'uwl_guard_v973.db')
if os.path.exists(TMP):
    os.remove(TMP)
t = sqlite3.connect(TMP)
t.row_factory = sqlite3.Row
W.ensure_table(t)
W.ensure_table(t)
ck(True, 'ensure_table is idempotent (second call does not raise)')
cols = {r[1] for r in t.execute("PRAGMA table_info(user_watchlists)")}
ck({'symbol_norm', 'symbol', 'name', 'note', 'added_at'} <= cols,
   'user_watchlists columns: %s' % sorted(cols))
ck(W.count(t) == 0, 'fresh table is empty')

W.add(t, 'داریک', name='دارایی یک', note='یادداشت آ')
W.add(t, 'وبملت', name='بانک ملت')
n_after_two = W.count(t)
W.add(t, 'داريك', name='با املا عربی', note='یادداشت ب')   # همان شرکت، امضای دیگر
ck(W.count(t) == n_after_two,
   'adding the Arabic spelling of a stored symbol updates, not duplicates '
   '(%d -> %d rows)' % (n_after_two, W.count(t)))
row = W.get(t, 'داریک')
ck(row and row['norm'] == 'داریک' and row['note'] == 'یادداشت ب',
   'stored row keeps the normalized key and the newest note: %s' % row)
ck(W.add(t, '') is None and W.add(t, None) is None and W.add(t, '   ') is None,
   'blank/None/whitespace-only symbol is refused without writing')
ck(W.add(t, '\u200c') is None, 'ZWNJ-only symbol normalizes to empty and is refused')
long = W.add(t, 'خ گ تر', note='ن' * 900)
ck(long and len(long['note']) <= W.MAX_NOTE,
   'note is clamped to %d chars (got %d)' % (W.MAX_NOTE, len(long['note'])))
ck(W.remove(t, 'خ گ تر') == 1, 'remove resolves the same normalized key')
ck(W.remove(t, 'وبملت') == 1 and W.remove(t, 'وبملت') == 0,
   'remove deletes once then reports 0 (idempotent)')
ck(W.count(t) == 1, 'one row left after removals: %d' % W.count(t))
t.close()

# ---------- گارد ۵: ماتریس روی market.db واقعی (فقط‌خواندنی) ----------
DB = 'market.db'


def digest(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()[:16]


STATES = {'pass', 'warn', 'fail', 'nodata'}
VERDICTS = {'CONFIRMED', 'PROBABLE', 'WATCH', 'WEAK', 'INSUFFICIENT'}

if not os.path.exists(DB):
    ck(True, 'market.db missing -> live matrix section SKIPPED (static guards ran)')
else:
    # کپیِ یکدست: اپِ نصب‌شده درِ ساعتِ بازار هر ۹۰ ثانیه market.db را سینک
    # می‌کند؛ بی‌این snapshot، «deterministic» و «byte-identical» رقابتِ با آن
    # سینکِ بیرونی را می‌سنجیدند نه بی‌نوشتیِ سوئیت را (شاهد ۱۴۰۵-۰۷-۱۳
    # ۰۹:۳۶: h0=55eb→h1=9668 بی‌آنکه سوئیت چیزی بنویسد). backupِ آنلاینِ
    # sqlite بی‌قفل می‌گیرد و بی‌تغییرِ بانکِ اصلی تمام می‌شود.
    import tempfile
    SNAP = os.path.join(tempfile.gettempdir(), 'bors_wl_snap_%d.db' % os.getpid())
    _src = sqlite3.connect('file:%s?mode=ro' % DB, uri=True)
    _dst = sqlite3.connect(SNAP)
    with _src:
        _src.backup(_dst)
    _dst.close()
    _src.close()
    DB = SNAP
    h0, m0 = digest(DB), os.path.getmtime(DB)
    conn = sqlite3.connect('file:%s?mode=ro' % DB.replace('\\', '/'), uri=True)
    conn.row_factory = sqlite3.Row

    # نمادهایِ برخوردِ نوشتاری (همان ۳۶ گروهی که باگ از آن‌ها می‌آمد)
    groups = {}
    for tbl in ('financial_statements', 'monthly_sales'):
        for (v,) in conn.execute("SELECT DISTINCT symbol FROM %s" % tbl):
            if v:
                groups.setdefault(W.fts_engine.norm_fa(v), set()).add(v)
    coll = {k: sorted(v) for k, v in groups.items() if len(v) > 1}
    ck(len(coll) > 0, 'market.db still carries mixed-script symbol pairs (%d groups)'
       % len(coll))

    def counted(fn):
        seen = []
        conn.set_trace_callback(seen.append)
        try:
            out = fn()
        finally:
            conn.set_trace_callback(None)
        return len(seen), seen, out

    probe = [s for g in list(coll.values())[:8] for s in g]
    probe += ['وبملت', 'نماد_وجود_ندارد_زدی']
    n_mx, sqls, mx = counted(lambda: W.matrix(conn, symbols=probe))
    ck(mx['status'] == 'success' and mx['count'] == len(probe),
       'matrix returns one row per requested symbol (%d/%d)' % (mx['count'], len(probe)))
    ck(json.dumps(mx, ensure_ascii=False, default=str), 'matrix is JSON-serializable')
    ck(all(r['states'][k] in STATES for r in mx['rows'] for k in ('tech', 'tape', 'fund')),
       'every pillar state is exactly pass|warn|fail|nodata')
    ck(all(r['verdict'] in VERDICTS for r in mx['rows']),
       'every verdict is one of the five public states')
    ck(all('vetoed' not in r for r in mx['rows']),
       'no vetoes in the public matrix (v9.7.4 soft warnings)')
    ck(all(r['verdict'] != 'CONFIRMED' or 'warn' not in r['states'].values()
           for r in mx['rows']), 'a warned pillar never yields CONFIRMED')
    ck(all(0 <= r['conf_count'] <= 3 and 0 <= r['coverage'] <= 3 for r in mx['rows']),
       'conf_count/coverage stay within the three pillars')

    def _floats(o):
        if isinstance(o, dict):
            for v in o.values():
                for w in _floats(v):
                    yield w
        elif isinstance(o, (list, tuple)):
            for v in o:
                for w in _floats(v):
                    yield w
        elif isinstance(o, float):
            yield o
    ck(all(math.isfinite(v) for r in mx['rows'] for v in _floats(r)),
       'no NaN/Inf leaks into the matrix (would serialize to invalid JSON)')

    # ضدِN+1: اضافه‌شدنِ نماد نباید کوئری را خطیِ بزرگ کند
    n_small, _, _ = counted(lambda: W.matrix(conn, symbols=probe[:1]))
    n_big, _, _ = counted(lambda: W.matrix(conn, symbols=probe))
    marginal = (n_big - n_small) / float(max(len(probe) - 1, 1))
    ck(marginal < 8.0,
       'marginal queries/symbol through the matrix = %.2f (1 symbol=%d, %d symbols=%d)'
       % (marginal, n_small, len(probe), n_big))
    ck(sum(1 for s in sqls if 'total_equity' in s) <= 2,
       'market-wide m141 query is not rebuilt per symbol (saw %d)'
       % sum(1 for s in sqls if 'total_equity' in s))

    # دوطرفه: دو نوشتارِ یک شرکت باید یک داوری بدهند
    bad = []
    for k, sp in list(coll.items())[:10]:
        r2 = W.matrix(conn, symbols=sp)['rows']
        sig = {(r['states']['tech'], r['states']['tape'], r['states']['fund'],
                r['verdict']) for r in r2}
        if len(sig) != 1:
            bad.append((k, sorted(sig)))
    ck(not bad, 'both spellings of the same instrument get the same verdict: %s' % bad[:2])

    ck(W.matrix(conn, symbols=probe)['rows'] == mx['rows'],
       'identical input produces identical matrix (deterministic)')
    ck(W.matrix(conn, symbols=[])['count'] == 0,
       'empty symbol list short-circuits to zero rows (no ctx built)')
    ck(W.matrix(conn, symbols=['نماد_وجود_ندارد_زدی'])['rows'][0]['verdict']
       == 'INSUFFICIENT',
       'an unknown symbol abstains (INSUFFICIENT) instead of a hard rejection')
    conn.close()
    h1, m1 = digest(DB), os.path.getmtime(DB)
    ck(h0 == h1 and m0 == m1,
       'market.db byte-identical after the whole suite (%s -> %s)' % (h0, h1))
    os.remove(SNAP)


# ---- 1405-07-17: ONE market-cap basis for I4 and for the sidebar ----
# The guard's snapshot copy is already deleted at this point, and these three
# assertions are about the *schema/code contract*, so they read market.db
# read-only (same bytes the suite just verified byte-for-byte).
import confidence_engine as CE
_mc = sqlite3.connect('file:market.db?mode=ro', uri=True)
try:
    _m = CE.mcap_map(_mc)
    ck(bool(_m), "mcap_map builds the canonical market cap for the whole market once (no N+1)")
    _pairs = _mc.execute(
        "SELECT m.market_cap, i.ins_code, m.allowed_min, m.allowed_max "
        "FROM market_watch m JOIN instruments i ON i.ins_code=m.ins_code "
        "WHERE m.d_even=(SELECT MAX(d_even) FROM market_watch) "
        "AND m.market_cap > 0 LIMIT 400").fetchall()
    # Only the rows that PASS the single dead-band gate must equal the official
    # column. The gated ones legitimately fall back to the last valid
    # daily_prices cap — that is the canonical hierarchy, not a second formula.
    def _gated(amin, amax):
        return (float(amin or 0) > 0 and float(amax or 0) > 0 and float(amax) <= float(amin))
    _ok = [(raw, ic) for raw, ic, amin, amax in _pairs if not _gated(amin, amax)]
    _gated_n = len(_pairs) - len(_ok)
    _bad = [ic for raw, ic in _ok if abs((_m.get(ic) or 0.0) - float(raw)) > 0.005 * float(raw)]
    ck(not _bad, "I4's denominator IS the board's official column on every row the "
       "dead-band gate accepts (%d accepted, %d gated→history, %d differ)"
       % (len(_ok), _gated_n, len(_bad)))
    _fbody = io.open("confidence_engine.py", encoding="utf-8").read()
    _fbody = _fbody.split("def conf_fund(", 1)[1].split(chr(10) + "def ", 1)[0]
    ck('watch.get("p_closing")) * _f(' not in _fbody and '"mcap"' in _fbody,
       "conf_fund no longer derives p_closing x total_shares locally; one answer per symbol")
    _board = io.open("api/market.py", encoding="utf-8").read()
    # این بند در اصل توکن `@MCAP@` را می‌پایست؛ آن توکن عمداً بازنشسته شد، چون دو
    # مصرف‌کنندۀ متنِ این SQL را با regex از فایلِ منبع می‌گیرند و *مستقیم اجرا*
    # می‌کنند (`dev/board_hist_cache_v1056.py`، `tools/tape_formula_parity.py`) و
    # SQLِ بی‌اجرا آن‌ها را می‌شکند. پس حالا خودِ قراردادِ تازه پین می‌شود:
    # ۱) ستونِ مبنایِ ساید همان `fts_engine.mcap_bulk_expr` است (یک فرمول، نه داورِ دوم)
    # ۲) متنِ پایه باید *قابل‌اجرا* بماند (placeholderِ CAST) و توکن برنگردد.
    ck("mcap_bulk_expr(conn" in _board,
       "the sidebar's market cap IS fts_engine.mcap_bulk_expr (the very expression I4 "
       "divides by) — two surfaces, one formula, no second judge")
    ck("CAST(NULL AS REAL) AS mcap" in _board and "@MCAP@" not in _board,
       "the board SQL stays executable (placeholder, not a token) — the two tools that "
       "regex-and-run it keep working")
finally:
    _mc.close()

n_bad = sum(1 for ok, _ in CHECKS if not ok)
for ok, msg in CHECKS:
    print('  %s %s' % ('PASS' if ok else 'FAIL', msg))
print('\n%d checks, %d failed' % (len(CHECKS), n_bad))
sys.exit(1 if n_bad else 0)

os.remove(TMP)
