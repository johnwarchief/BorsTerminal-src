#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/undef_name_guard.py -- هیچ نامِ تعریف‌نشده‌ای در کدِ منتشرشده نماند.

چرا: `dev/struct_check.py` با عنوان «structure / undefined-names» ساعت‌ها بود
«ok» می‌داد، در حالی که درِ `api/fundamental.py` دو نام تعریف‌نشده وجود داشت و
پانصدِ واقعی می‌داد:

  File "api/fundamental.py", line 2182, in get_fundamental
      if probe:
  NameError: name 'probe' is not defined

این شاخه فقط برای نمادهایی اجرا می‌شود که l_val18شان با «ض» شروع می‌شود — یعنی
قراردادهای اختیار معامله (۱٬۰۴۹ ردیفِ زنده). کاربری که کارتِ بنیادیِ یک قرارداد
اختیار را باز می‌کرد ۵۰۰ می‌گرفت. گناه دوم همان‌جا بود: `th["eps_years"]` در سطرِ
۲۲۲۳، که وقتی ind["2"] مقدارِ years_required ندارد می‌ترکد. هیچ‌کدام در تست نبود،
چون شاخه‌های شرطیِ نایابِ یک endpoint را هیچ تستِ واحدی پوشش نمی‌دهد.

روش: symtable — همان چیزی که پایتون برای ساختنِ bytecode به کار می‌برد. برای هر
scope، نامی که «ارجاع شده» ولی درِ همان scope پارامتر/assignment/import نشده و آزادِ
(closure) بیرونی هم نیست و درِ سطحِ ماژول و builtins هم پیدا نمی‌شود، تعریف‌نشده
است. پوچ‌گرا نیست: ماژولی که `from x import *` دارد skipping می‌شود، چون آن‌جا
نام‌های سطحِ ماژول از دید symtable پنهان‌اند.
"""
import ast
import builtins
import glob
import os
import symtable
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BI = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__builtins__", "__spec__", "__loader__"}

# اینها عمداً بی‌نام‌بررسی می‌مانند: کدِ ابزارِ موقت و اسکریپت‌هایِ dev/ که
# منتشر نمی‌شوند. کدِ ریلیز (app/api/موتورها) همیشه بررسی می‌شود.
SKIP_GLOB = ("dev/", "scripts/", "tools/", "_audit/", "test_", "conftest")

failed = 0
scanned = 0


def has_star_import(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name == "*":
                    return True
    return False


def undefined(path, src):
    try:
        tree = ast.parse(src, path)
    except SyntaxError as e:
        return ["%s: SyntaxError %s" % (path, e.msg)], True
    if has_star_import(tree):
        return [], None  # skipping: نام‌هایِ star-import از symtable پنهان می‌مانند
    st = symtable.symtable(src, path, "exec")
    module_names = {s.get_name() for s in st.get_symbols()}
    out = []

    def walk(tbl):
        for sym in tbl.get_symbols():
            name = sym.get_name()
            if (sym.is_referenced() and not sym.is_assigned() and not sym.is_parameter()
                    and not sym.is_imported() and not sym.is_free()
                    and name not in module_names and name not in BI):
                out.append("%s: '%s' در scope '%s' تعریف نشده" % (path, name, tbl.get_name()))
        for child in tbl.get_children():
            walk(child)

    walk(st)
    return out, False


def signature(node):
    """(نام‌هایِ لازم به ترتیب, قابل‌سنجش بودن) برایِ یک def.

    لازم = پارامتری که مقدارِ پیش‌فرض ندارد. def باِ `*args` یا `**kwargs`
    سنجیده *نمی‌شود*: با آن‌ها هر شمارۀ کم می‌تواند درست باشد و گاردِسرخ‌کننده،
    گاردِ بی‌اعتبار است.
    """
    a = node.args
    if a.vararg is not None or a.kwarg is not None:
        return None, False
    ordered = [x.arg for x in list(a.posonlyargs) + list(a.args)]
    n_def = len(a.defaults)
    required = ordered[: len(ordered) - n_def] if n_def else ordered
    return required, True


def file_defs(tree):
    """نام → امضاهایِ آن نام، درِ *همین* فایل.

    دو چیز اینجا عمداً ماژولی است:
    • `_col` درِ `codal_units.py` و `_col` درِ `api/chart.py` دو تابعِ جدا با دو
      امضایِ جداند. نسخهٔ نخستِ این سنجان سراسری بود و ده اسباتِ کاذب داد.
    • فراخوانِ nested (`def _settled(level, above)` داخلِ یک تابعِ دیگر) باِ
      keyword سنجیده می‌شود؛ شمارشِ صرفِ موقعیتی هم اسباتِ کاذب می‌ساخت.
    """
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            required, ok = signature(node)
            if not ok or not required:
                continue
            out.setdefault(node.name, []).append(required)
    return out


def visible_arity(rel, tree, defs_by_module):
    """امضاها چیزی که درِ این فایل *دیده می‌شود*: defهایِ خودش + importهایِ حل‌شدنی.

    `from ._core import sym_pred` درِ `api/chart.py` به `api/_core.py` و
    `from x import y` به `x.py` گره می‌خورد. ماژولِ حل‌ناشدنی (stdlib، وابستگیِ
    بیرونی، یا star-import) داوری نمی‌شود — بی‌این، هر نامِ هم‌نامِ جهانی سرخ می‌شد.
    """
    visible = dict(file_defs(tree))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = _module_path(rel, node, defs_by_module)
            if mod is None:
                continue
            src_defs = defs_by_module.get(mod)
            if not src_defs:
                continue
            for a in node.names:
                if a.name == "*":
                    return None          # star-import: چیزی را تضمین نداریم
                nm = a.asname or a.name
                if nm not in visible and nm in src_defs:
                    visible[nm] = src_defs[nm]
    return visible


def uncovered(call, sigs):
    """نام‌هایِ لازمی که هیچ امضایِ این نام نمی‌تواند ازِ این فراخوان بگیرد.

    «هیچ امضا» عمدی است: اگر *یکی* از تعریف‌هایِ هم‌نام بپذیرد، ایرادی نیست —
    فقط وقتی همه رد می‌کنند، فراخوان کهن‌مدل است.
    """
    if any(k.arg is None for k in call.keywords):
        return None                      # **kwargsِ باز: قابلِ داوری نیست
    if any(isinstance(x, ast.Starred) for x in call.args):
        return None
    kw_names = {k.arg for k in call.keywords if k.arg is not None}
    best = None
    for required in sigs:
        # پارامترهایِ posonly پس ازِ اولین keyword پر نمی‌شوند؛ اینجا همه را
        # positional-or-keyword می‌گیریم و `_settled(last_low, above=False)` هم
        # پوشش‌داده‌شده حساب می‌شود (نسخۀ اولِ این سنجان آن را اسباتِ کاذب داد).
        covered = set(required[:len(call.args)]) | kw_names
        missing = [r for r in required if r not in covered]
        if not missing:
            return []                    # یک امضا کافی است ⇒ ایرادی نیست
        if best is None or len(missing) < len(best):
            best = missing
    return best or []


def _module_path(rel, node, defs_by_module):
    """مسیرِ فایلِ ماژولِ importشده، نسبی بهِ ریشۀ ریپو؛ یا None."""
    lvl = node.level or 0
    base = node.module or ""
    if lvl:
        d = os.path.dirname(rel).replace("\\", "/").split("/")
        d = d[: len(d) - lvl + 1] if lvl > 1 else d
        parts = [x for x in ("/".join(d).split("/") if d else []) if x]
    else:
        parts = []
    tail = [x for x in base.split(".") if x]
    cand = "/".join(parts + tail)
    for path in (cand + ".py", cand + "/__init__.py"):
        if path in defs_by_module:
            return path
    for path in defs_by_module:
        if path.endswith("/" + "/".join(tail) + ".py") or path == "/".join(tail) + ".py":
            return path
    return None


def stale_arity(rel, tree, visible):
    """فراخوانِ نامِ معلوم که هیچ امضایِ آن نامِ آرگومانِ لازم را نمی‌پوشاند.

    درِ ادغامِ System 2 (۱۴۰۵-۰۷-۲۸) دقیقاً همین رخ داد: `api/_core.py` دو
    پارامترِ تازه گرفت (`sym_pred(conn, col, symbol, domain)`) و System 1 هر ۹
    فراخوان را تازه کرد، اما دو فراخوانِ توابعِ خودِ System 2 کهنه ماند. TypeError
    درِ `except Exception: return []` بلعیده شد و مسیرِ دفترِ تعدیل بی‌صدا
    «بی‌داده» شد. نام‌بررسی این را *نمی‌گیرد*، چون نام هست و فقط شکلِ فراخوان
    کهنه است.

    دو اسباتِ کاذبی که این نسخه رد می‌کند: هم‌نامِ دو ماژول (`_col`) و
    keyword-شدۀ nested (`_settled(last_low, above=False)`).
    """
    if not visible:
        return []
    hits = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
            continue
        sigs = visible.get(node.func.id)
        if not sigs:
            continue
        missing = uncovered(node, sigs)
        if missing:
            hits.append("%s:%d: %s(...) پارامتر(های)ِ لازمِ «%s» را نمی‌دهد"
                        % (rel, node.lineno, node.func.id, ", ".join(missing)))
    return hits


def main():
    global failed, scanned
    targets = ["app.py", "bors_config.py", "bors_entry.py", "bors_minisign.py",
               "codal_fetcher.py", "fts_engine.py", "mstat_engine.py", "tape_flags.py",
               "watchlist_stack.py", "watchlist_store.py", "bootstrap_first_run.py"]
    # ستونِ فقراتِ اجرا و ربات (مأموریتِ ۱۴۰۵-۰۷-۲۳): این ماژول‌ها سالِ پیش به
    # فهرستِ دستی اضافه نشدند، پس «۰ ایراد» دربارهٔ آن‌ها *سکوت* بود نه تأیید —
    # همان الگویی که درِ `guard-fixtures-hide-a-dead-branch` ثبت شده.
    targets += ["execution_contract.py", "execution_service.py", "execution_mock.py",
                "execution_timing.py", "execution_latency.py", "execution_ledger.py",
                "trade_sim.py", "backtest_engine.py", "paper_trading.py", "bot_signals.py",
                "price_basis.py", "candle_contract.py", "codal_periods.py",
                "codal_pipeline.py", "codal_units.py", "client_split.py",
                "funnel_engine.py", "funnel_registry.py", "funnel_tech_scan.py",
                "confidence_engine.py", "tape_flag_history.py", "market_state.py",
                "symbol_identity.py"]
    targets += [p.replace(os.sep, "/") for p in glob.glob(os.path.join(ROOT, "api", "*.py"))]

    problems = []
    parsed = []
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        if any(g in rel for g in SKIP_GLOB):
            continue
        src = open(path, encoding="utf-8").read()
        rel_slash = rel.replace(os.sep, "/")
        found, hard = undefined(rel_slash, src)
        scanned += 1
        if hard:
            problems.append(found[0])
        problems.extend(found)
        try:
            parsed.append((rel_slash, ast.parse(src, rel_slash)))
        except SyntaxError:
            pass

    # سنجانِ دوم: شکلِ فراخوان (امضایِ عوض‌شده‌ای که یک ادغامِ متعارض بازمی‌گرداند)
    # ماژول‌به‌ماژول، باِ importهایِ حل‌شدنی — نسخهٔ سراسری ده اسباتِ کاذب داد.
    defs_by_module = {rel: file_defs(tree) for rel, tree, _src in parsed}
    arity_hits = []
    resolvable = 0
    for rel, tree, _src in parsed:
        vis = visible_arity(rel, tree, defs_by_module)
        if vis:
            resolvable += 1
        arity_hits.extend(stale_arity(rel, tree, vis))
    if arity_hits:
        for h in arity_hits[:25]:
            print("  FAIL شکلِ فراخوان: %s" % h)
        problems.extend(arity_hits)
    else:
        print("  ok   %d ماژول باِ امضایِ حل‌شدنی: هیچ فراخوانِ کهن‌مدل (آرگومانِ کم) نیست" % resolvable)

    if problems:
        failed = len(problems)
        for p in problems[:25]:
            print("  FAIL %s" % p)
        if len(problems) > 25:
            print("  … و %dِ دیگر" % (len(problems) - 25))
    else:
        print("  ok   %d ماژولِ منتشرشده: هیچ نامِ تعریف‌نشده‌ای نیست" % scanned)

    # خودسنجی: همین گارد باید شکستِ واقعیِ ۱٫۰٫۴۱ را بگیرد، وگرنه مثل
    # struct_check بی‌صدا «ok» می‌گوید.
    buggy = ('def f(conn):\n'
             '    m = re.search("x", "y")\n'
             '    if probe:\n'
             '        return probe\n')
    found, _ = undefined("synthetic.py", buggy)
    ok_synth = any("'probe'" in x for x in found)
    if not ok_synth:
        failed += 1
        print("  FAIL خودسنجی: گارد نامِ تعریف‌نشدهٔ ساختگی را نگرفت (پوچ شده)")
    else:
        print("  ok   خودسنجی: 'probe' ساختگی گرفته شد")

    clean, _ = undefined("synthetic2.py", 'def g(a):\n    return a + 1\n')
    if clean:
        failed += 1
        print("  FAIL خودسنجی: روی کدِ سالم هم خطا می‌دهد: %s" % clean)
    else:
        print("  ok   خودسنجی: کدِ سالم بی‌خطا می‌ماند")

    # closure و star-import باید پوچ‌گرا نباشند/هشدار ندهند
    closure, _ = undefined("synthetic3.py",
                           'def outer():\n    x = 1\n    def inner():\n        return x\n    return inner\n')
    if closure:
        failed += 1
        print("  FAIL خودسنجی: متغیرِ بستری (closure) را متهم کرد: %s" % closure)
    else:
        print("  ok   خودسنجی: closure بی‌اتهام است")

    # خودسنجیِ سنجانِ شکلِ فراخوان: همین باگِ ادغام (۱۴۰۵-۰۷-۲۸) باید گرفته شود،
    # وگرنه «۰ ایراد» درِ این سنجه هم سکوت است نه تأیید. دو شکل کاربُرد می‌شود:
    # همان‌فایلی و **cross-module** (شکلِ واقعیِ sym_pred: امضا درِ `api/_core.py`
    # و فراخوانِ کهنه درِ `api/chart.py`).
    planted_same = ('def sym_pred(conn, col, symbol, domain=None):\n'
                    '    return col, [symbol]\n'
                    'def _use(symbol, conn):\n'
                    '    return sym_pred("l_val18", symbol)\n')
    t_same = ast.parse(planted_same, "planted.py")
    got = stale_arity("planted.py", t_same, visible_arity("planted.py", t_same,
                                                          {"planted.py": file_defs(t_same)}))
    if not got:
        failed += 1
        print("  FAIL خودسنجی: فراخوانِ کهن‌مدلِ همان‌فایلی گرفته نشد (سنسور پوچ است)")
    else:
        print("  ok   خودسنجی: کهن‌مدلِ همان‌فایلی گرفته شد")

    core = ('def sym_pred(conn, col, symbol, domain=None):\n'
            '    return col, [symbol]\n')
    caller = ('from ._core import sym_pred\n'
              'def _ledger(symbol, conn):\n'
              '    return sym_pred("l_val18", symbol)\n')
    t_core = ast.parse(core, "api/_core.py")
    t_call = ast.parse(caller, "api/chart.py")
    defs = {"api/_core.py": file_defs(t_core), "api/chart.py": file_defs(t_call)}
    got_x = stale_arity("api/chart.py", t_call, visible_arity("api/chart.py", t_call, defs))
    if not got_x:
        failed += 1
        print("  FAIL خودسنجی: کهن‌مدلِ cross-module (from ._core import) گرفته نشد — "
              "همان شکلِ واقعیِ باگِ chart.py")
    else:
        print("  ok   خودسنجی: کهن‌مدلِ cross-module گرفته شد (%s)" % got_x[0].split(": ", 1)[-1])

    # پوچ‌گراییِ اول: همان نام با آرگومانِ درست
    ok_caller = ('from ._core import sym_pred\n'
                 'def _use(symbol, conn):\n'
                 '    return sym_pred(conn, "l_val18", symbol, "board")\n')
    t_ok = ast.parse(ok_caller, "api/ok.py")
    defs_ok = {"api/_core.py": file_defs(t_core), "api/ok.py": file_defs(t_ok)}
    if stale_arity("api/ok.py", t_ok, visible_arity("api/ok.py", t_ok, defs_ok)):
        failed += 1
        print("  FAIL خودسنجی: فراخوانِ درست را متهم کرد")
    else:
        print("  ok   خودسنجی: فراخوانِ درستِ sym_pred بی‌اتهام است")

    # پوچ‌گراییِ سوم: پارامترِ keyword-شده باید پوشش‌داده‌شده شمارد
    kw_src = ("def _settled(level, above):\n"
              "    return above\n"
              "def g(x):\n"
              "    return _settled(x, above=False)\n")
    t_kw = ast.parse(kw_src, "kw.py")
    if stale_arity("kw.py", t_kw, visible_arity("kw.py", t_kw, {"kw.py": file_defs(t_kw)})):
        failed += 1
        print("  FAIL خودسنجی: آرگومانِ keyword را «کم» شمرد (اسباتِ کاذب)")
    else:
        print("  ok   خودسنجی: آرگومانِ keyword پوشش‌داده‌شده شمارد")

    # پوچ‌گراییِ دوم (همان چیزی که نسخهٔ سراسری را بی‌اعتبار کرد): دو ماژول با
    # `_col` هم‌نام و دو امضایِ جدا؛ هیچ‌کدام نباید متهم شود.
    m_a = ('def _col(conn, name):\n    return name\n'
           'def a(c):\n    return _col(c, "x")\n')
    m_b = ('def _col(name):\n    return name\n'
           'def b():\n    return _col("y")\n')
    t_a, t_b = ast.parse(m_a, "a_mod.py"), ast.parse(m_b, "b_mod.py")
    defs_hom = {"a_mod.py": file_defs(t_a), "b_mod.py": file_defs(t_b)}
    hom = (stale_arity("a_mod.py", t_a, visible_arity("a_mod.py", t_a, defs_hom))
           + stale_arity("b_mod.py", t_b, visible_arity("b_mod.py", t_b, defs_hom)))
    if hom:
        failed += 1
        print("  FAIL خودسنجی: هم‌نامِ دو ماژول را متهم کرد: %s" % hom)
    else:
        print("  ok   خودسنجی: هم‌نامِ دو ماژول (اسباتِ کاذبِ نسخهٔ سراسری) بی‌اتهام است")

    print("\nundef-name guard: %d ماژول، %d ایراد" % (scanned, failed))
    print("UNDEF NAME GUARD " + ("OK" if not failed else "FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
