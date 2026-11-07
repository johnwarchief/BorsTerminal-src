#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""مقایسهٔ ۱۰ نماد بنیادی بین FastAPI پایتون و Go (فقط خواندن)."""
import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request

DEFAULT = ["فولاد", "خساپا", "وبصادر", "شپنا", "همراه",
           "فارس", "کگل", "خودرو", "شبندر", "تاپیکو"]


def get(base, path):
    url = base.rstrip("/") + path
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, None


def diff(a, b, path="", out=None):
    out = [] if out is None else out
    # JSON یک نوعِ عدد دارد؛ int/floatِ پایتون و Go با یک مقدارِ عددی برابرند
    # (۴۰ و ۴۰٫۰ همان ۴۰ است). تنها bool از این قاعده بیرون می‌ماند.
    if (isinstance(a, (int, float)) and not isinstance(a, bool)
            and isinstance(b, (int, float)) and not isinstance(b, bool)):
        if a != b:
            out.append("%s: %r != %r" % (path, a, b))
        return out
    if type(a) is not type(b):
        out.append("%s: type %s != %s" % (path, type(a).__name__, type(b).__name__))
        return out
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                out.append("%s.%s: missing in python" % (path, k))
            elif k not in b:
                out.append("%s.%s: missing in go" % (path, k))
            else:
                diff(a[k], b[k], "%s.%s" % (path, k), out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append("%s: length %d != %d" % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diff(a[i], b[i], "%s[%d]" % (path, i), out)
    elif a != b:
        out.append("%s: %r != %r" % (path, a, b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--python", default="http://127.0.0.1:8101")
    ap.add_argument("--go", default="http://127.0.0.1:8103")
    ap.add_argument("--symbols", default=",".join(DEFAULT))
    args = ap.parse_args()
    symbols = [s.strip() for s in args.symbols.split(",") if s.strip()]
    failed = 0
    checked = 0
    for sym in symbols:
        for path in ("/api/fundamental/%s" % urllib.parse.quote(sym),
                     "/api/fundamental/%s/quarters" % urllib.parse.quote(sym)):
            py_status, py = get(args.python, path)
            go_status, go = get(args.go, path)
            if py_status == 404 and go_status == 404:
                continue
            if py_status != go_status or py is None or go is None:
                print("FAIL %s status python=%s go=%s" % (path, py_status, go_status))
                failed += 1
                continue
            d = diff(py, go)
            checked += 1
            if d:
                failed += 1
                print("FAIL %s (%d diff)" % (path, len(d)))
                for line in d[:20]:
                    print("  " + line)
            else:
                print("PASS %s" % path)
    print("%d checked, %d failed" % (checked, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
