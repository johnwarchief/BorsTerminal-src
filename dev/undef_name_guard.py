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


def main():
    global failed, scanned
    targets = ["app.py", "bors_config.py", "bors_entry.py", "bors_minisign.py",
               "codal_fetcher.py", "fts_engine.py", "mstat_engine.py", "tape_flags.py",
               "watchlist_stack.py", "watchlist_store.py", "bootstrap_first_run.py"]
    targets += [p.replace(os.sep, "/") for p in glob.glob(os.path.join(ROOT, "api", "*.py"))]

    problems = []
    for rel in targets:
        path = os.path.join(ROOT, rel)
        if not os.path.isfile(path):
            continue
        if any(g in rel for g in SKIP_GLOB):
            continue
        src = open(path, encoding="utf-8").read()
        found, hard = undefined(rel.replace(os.sep, "/"), src)
        scanned += 1
        if hard:
            problems.append(found[0])
        problems.extend(found)

    if problems:
        failed = len(problems)
        for p in problems[:25]:
            print("  FAIL %s" % p)
        if len(problems) > 25:
            print("  … و %یِ دیگر" % (len(problems) - 25))
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

    print("\nundef-name guard: %d ماژول، %d ایراد" % (scanned, failed))
    print("UNDEF NAME GUARD " + ("OK" if not failed else "FAILED"))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
