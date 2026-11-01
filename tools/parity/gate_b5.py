#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""گیتِ B5: مسیرهایِ پورت‌شدهٔ کاربر شامل واچ‌لیست و مرکزِ اعلان‌ها.

شامل دو بخشِ سنجش:
۱. B-G1 (Read Parity):
   برابریِ خواندنیِ `GET /api/watchlist`، `GET /api/notifications/sources`،
   و `GET /api/notifications/feed` با تمام فیلترهای since، levels، symbol و limit،
   به همراه سنجش مسیر اعلام‌شدهٔ `GET /api/watchlist/matrix` (Go ۵۰۱ / Py ۲۰۰).
۲. B-G2 (Write Parity):
   برابریِ رفتاری و سطربه‌سطرِ نوشتن روی جدول `user_watchlists` در `user.db`
   برای متدهای `POST /api/watchlist` و `DELETE /api/watchlist/{symbol}`،
   با بررسی دقیق کلید نرمال، املاهای عربی/فارسی و پاک‌سازیِ گام‌به‌گام.

قواعدِ شکست‌ناپذیر:
- بانک‌هایِ اصلی ریشه هرگز لمس نمی‌شوند (root_before == root_after).
- اجرای تست فقط روی کپی‌های موقتی در پوشهٔ ایزوله.
- مقایسهٔ مو‌به‌مو با تلورانس عددی صفر (delta_zero).
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base                                        # noqa: E402
import gate_b2a as engine                                     # noqa: E402

ROOT = base.ROOT
GO = base.GO
CASES = os.path.join(HERE, "cases_b5.json")
OUT = os.environ.get("BORS_B5_OUT") or os.path.join(ROOT, "_audit", "parity", "B5.json")
CONTRACT = (os.environ.get("BORS_B5_CONTRACT")
            or os.path.join(ROOT, "_audit", "parity", "B5-contract.json"))
GO_PORT = int(os.environ.get("BORS_B5_GO_PORT", "8310"))
PY_PORT = int(os.environ.get("BORS_B5_PY_PORT", "8311"))
ROOT_DBS = engine.ROOT_DBS

ROLES_SQL = {
    "notice_symbol": (
        "SELECT symbol FROM codal_notices"
        " WHERE symbol IS NOT NULL AND trim(symbol) != ''"
        " GROUP BY symbol HAVING COUNT(*) >= 5"
        " ORDER BY COUNT(*) DESC LIMIT 1"
    ),
}
PLACEHOLDERS = ("notice_symbol",)

B5_READ_ROUTES = {
    "/api/watchlist",
    "/api/notifications/sources",
    "/api/notifications/feed",
}


def pick_port(preferred, taken):
    for port in range(preferred, preferred + engine.PORT_SCAN):
        if port in taken:
            continue
        if base.port_free(port):
            return port
    raise RuntimeError("no free port near %d" % preferred)


def read_roles(db_path, roles_sql):
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    out = {}
    try:
        for role, sql in roles_sql.items():
            try:
                row = con.execute(sql).fetchone()
            except sqlite3.Error:
                row = None
            out[role] = str(row[0]) if row and row[0] is not None else None
    finally:
        con.close()
    return out


def build_cases(spec, roles):
    kept, dropped, declared = [], [], []
    for case in spec["cases"]:
        path, missing = case["path"], None
        for ph in PLACEHOLDERS:
            if "{%s}" % ph in path and not roles.get(ph):
                missing = ph
                break
        if missing:
            dropped.append("%s (role %s has no data)" % (case["name"], missing))
            continue
        for key, val in roles.items():
            if val:
                path = path.replace("{%s}" % key, urllib.parse.quote(val, safe=""))
        row = {"name": case["name"], "method": case.get("method", "GET"),
               "path": path, "exclude": case.get("exclude") or []}
        if case.get("declared"):
            declared.append(dict(row, note=case["declared"],
                                 require_key=case.get("require_key") or ""))
        else:
            kept.append(row)
    return kept, dropped, declared


def template_of(path):
    pure = path.split("?", 1)[0]
    return pure


def content_checks(py_url, cases):
    by_name = {c["name"]: c["path"] for c in cases}
    problems = []

    def body_of(name):
        path = by_name.get(name)
        return engine.get_json(py_url + path)[1] if path else None

    srcs = body_of("notifications-sources")
    if not srcs or srcs.get("status") != "ok" or not (srcs.get("sources") or []):
        problems.append("notifications-sources empty: %r" % (srcs,))

    feed_def = body_of("notifications-feed-default")
    if not feed_def or feed_def.get("status") != "ok" or feed_def.get("count", 0) <= 0:
        problems.append("notifications-feed-default empty: %r" % (feed_def,))

    feed_sym = body_of("notifications-feed-symbol")
    if not feed_sym or feed_sym.get("status") != "ok" or feed_sym.get("count", 0) <= 0:
        problems.append("notifications-feed-symbol empty: %r" % (feed_sym,))

    return problems


def declared_probe(py_url, go_url, declared):
    rows, problems = [], []
    for case in declared:
        py_status, py_body = engine.get_json(py_url + case["path"])
        go_status, go_body = engine.get_json(go_url + case["path"])
        want_go = 501
        want_py = 200
        want_key = case.get("require_key") or ""
        py_keys = sorted((py_body or {}).keys())
        key_seen = bool(want_key) and want_key in (py_body or {})
        ok = (go_status == want_go and (go_body or {}).get("code") == "NOT_PORTED"
              and py_status == want_py and key_seen and bool(want_key))
        rows.append({"name": case["name"], "path": case["path"], "py": py_status,
                     "go": go_status, "go_code": (go_body or {}).get("code"),
                     "expect_py": want_py, "require_key": want_key,
                     "key_seen": key_seen, "py_keys": py_keys,
                     "ok": ok, "note": case["note"]})
        if not ok:
            problems.append("%s: py=%r (want %d) go=%r/%r key=%r seen=%r keys=%r"
                            % (case["name"], py_status, want_py, go_status,
                               (go_body or {}).get("code"), want_key, key_seen, py_keys))
    return rows, problems


def http_request(url: str, method: str, data: dict | str | None = None) -> tuple[int, dict | None]:
    headers = {"Content-Type": "application/json"}
    body_bytes = None
    if isinstance(data, dict):
        body_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    elif isinstance(data, str):
        body_bytes = data.encode("utf-8")

    req = urllib.request.Request(url, data=body_bytes, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            status = resp.status
            raw = resp.read().decode("utf-8")
            try:
                parsed = json.loads(raw)
            except Exception:
                parsed = None
            return status, parsed
    except urllib.error.HTTPError as e:
        status = e.code
        raw = e.read().decode("utf-8")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = None
        return status, parsed


def fetch_watchlist_db(db_path: str) -> list[dict]:
    con = sqlite3.connect("file:%s?mode=ro" % db_path.replace("\\", "/"), uri=True)
    try:
        cur = con.execute("SELECT symbol_norm, symbol, name, note FROM user_watchlists ORDER BY symbol_norm ASC")
        return [dict(zip(("norm", "symbol", "name", "note"), r)) for r in cur.fetchall()]
    finally:
        con.close()


def run_write_parity_suite(py_url: str, go_url: str, py_user_db: str, go_user_db: str) -> tuple[bool, list[dict], list[str]]:
    mutations = [
        {
            "name": "write-add-sym1",
            "method": "POST",
            "path": "/api/watchlist",
            "data": {"symbol": "رمپنا", "name": "مدیریت پروژه‌های نیروگاهی", "note": "نوت ۱"},
            "expect_status": 200,
            "check": lambda p, g: p.get("count") == g.get("count") == 1 and p.get("existed") == g.get("existed") is False,
        },
        {
            "name": "write-add-sym2-arabic",
            "method": "POST",
            "path": "/api/watchlist",
            "data": {"symbol": "داريك", "name": "صندوق داریک", "note": "صندوق"},
            "expect_status": 200,
            "check": lambda p, g: p.get("count") == g.get("count") == 2 and p.get("existed") == g.get("existed") is False,
        },
        {
            "name": "write-upsert-sym2-persian",
            "method": "POST",
            "path": "/api/watchlist",
            "data": {"symbol": "داریک", "name": "", "note": "نوت ویرایش‌شده"},
            "expect_status": 200,
            "check": lambda p, g: p.get("count") == g.get("count") == 2 and p.get("existed") == g.get("existed") is True,
        },
        {
            "name": "write-empty-payload",
            "method": "POST",
            "path": "/api/watchlist",
            "data": "",
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "error",
        },
        {
            "name": "write-empty-symbol",
            "method": "POST",
            "path": "/api/watchlist",
            "data": {"symbol": "   ", "name": "بی‌نماد"},
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "error" and p.get("message") == g.get("message"),
        },
        {
            "name": "write-invalid-symbol",
            "method": "POST",
            "path": "/api/watchlist",
            "data": {"symbol": "\u200c"},
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "error" and p.get("message") == g.get("message"),
        },
        {
            "name": "write-delete-sym2-arabic",
            "method": "DELETE",
            "path": "/api/watchlist/" + urllib.parse.quote("داريك"),
            "data": None,
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "success" and p.get("deleted") == g.get("deleted") == 1,
        },
        {
            "name": "write-delete-sym2-repeat",
            "method": "DELETE",
            "path": "/api/watchlist/" + urllib.parse.quote("داريك"),
            "data": None,
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "success" and p.get("deleted") == g.get("deleted") == 0,
        },
        {
            "name": "write-delete-sym1",
            "method": "DELETE",
            "path": "/api/watchlist/" + urllib.parse.quote("رمپنا"),
            "data": None,
            "expect_status": 200,
            "check": lambda p, g: p.get("status") == g.get("status") == "success" and p.get("deleted") == g.get("deleted") == 1,
        },
    ]

    steps = []
    problems = []

    for m in mutations:
        py_status, py_body = http_request(py_url + m["path"], m["method"], m["data"])
        go_status, go_body = http_request(go_url + m["path"], m["method"], m["data"])

        status_ok = (py_status == go_status == m["expect_status"])
        check_ok = m["check"](py_body or {}, go_body or {})

        # بررسی سطربه‌سطر دیتابیس user.db
        py_db_rows = fetch_watchlist_db(py_user_db)
        go_db_rows = fetch_watchlist_db(go_user_db)
        db_match = (py_db_rows == go_db_rows)

        step_ok = status_ok and check_ok and db_match
        steps.append({
            "name": m["name"],
            "method": m["method"],
            "path": m["path"],
            "py_status": py_status,
            "go_status": go_status,
            "status_ok": status_ok,
            "check_ok": check_ok,
            "db_match": db_match,
            "db_row_count": len(go_db_rows),
            "ok": step_ok,
        })

        if not step_ok:
            problems.append(
                f"{m['name']}: status_ok={status_ok} (py={py_status}, go={go_status}), "
                f"check_ok={check_ok}, db_match={db_match} (py_rows={len(py_db_rows)}, go_rows={len(go_db_rows)})"
            )

    all_passed = len(problems) == 0
    return all_passed, steps, problems


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    root_before = engine.root_fingerprint()
    if root_before["market.db"] is None:
        print("operational market.db is missing; nothing to freeze")
        return 2

    for target, out in (("./cmd/borsd", base.BORSD), ("./cmd/parity", base.PARITY)):
        rc, log = base.run(["go", "build", "-o", out, target], cwd=GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = base.run(["go", "test", "-count=1", "./..."], cwd=GO)
    if rc != 0:
        print(tests)
        return 2

    taken = set()
    go_port = pick_port(GO_PORT, taken)
    taken.add(go_port)
    py_port = pick_port(PY_PORT, taken)
    fell_back = (go_port, py_port) != (GO_PORT, PY_PORT)
    if fell_back:
        print("ports busy: using go=%d py=%d (requested %d/%d)"
              % (go_port, py_port, GO_PORT, PY_PORT))
    commit = base.run(["git", "rev-parse", "--short", "HEAD"])[1].strip()

    before_sidecars = base.sidecar_state()
    tmp = tempfile.mkdtemp(prefix="bors-b5-")
    go_dir = os.path.join(tmp, "go")
    py_dir = os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    result = 2
    frozen_ok = False
    try:
        for name in base.DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = base.snapshot_db(src, os.path.join(dst_dir, name))
                except Exception as err:                # noqa: BLE001
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        db_prints = base.db_fingerprint(os.path.join(go_dir, "market.db"))
        if db_prints != base.db_fingerprint(os.path.join(py_dir, "market.db")):
            print("the two market.db copies are not identical")
            return 2
        frozen_ok = True

        # اطمینان از ساخت جدول user_watchlists و حالت خالی اولیه در هر دو کپی
        for d in (py_dir, go_dir):
            con = sqlite3.connect(os.path.join(d, "user.db"))
            con.execute("""
            CREATE TABLE IF NOT EXISTS user_watchlists (
                symbol_norm TEXT PRIMARY KEY,
                symbol      TEXT NOT NULL DEFAULT '',
                name        TEXT DEFAULT '',
                note        TEXT DEFAULT '',
                added_at    TEXT DEFAULT ''
            );
            """)
            con.execute("CREATE INDEX IF NOT EXISTS ix_uwl_added ON user_watchlists(added_at);")
            con.execute("DELETE FROM user_watchlists;")
            con.commit()
            con.close()

        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(py_port), PYTHONIOENCODING="utf-8")
        redirect_ok, redirect_paths = engine.python_redirect_ok(py_dir, py_env)
        if not redirect_ok:
            return 2

        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, base.SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not base.wait_json("http://127.0.0.1:%d/openapi.json" % py_port, 90.0,
                              lambda b: True):
            print("python server did not become ready")
            return 2

        go_log = open(os.path.join(tmp, "go.log"), "w", encoding="utf-8")
        go_proc = subprocess.Popen(
            [base.BORSD, "--port", str(go_port), "--read-only", "--no-loops",
             "--db-dir", go_dir], cwd=ROOT, stdout=go_log, stderr=subprocess.STDOUT)
        procs.append((go_proc, go_log))
        if not base.wait_json("http://127.0.0.1:%d/healthz" % go_port, 15.0,
                              lambda b: b.get("status") == "ok"):
            print("go server did not become ready")
            return 2
        _, _, health_body = base.http_get("http://127.0.0.1:%d/healthz" % go_port)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % py_port
        go_url = "http://127.0.0.1:%d" % go_port

        with open(CASES, encoding="utf-8") as f:
            spec = json.load(f)
        roles = read_roles(os.path.join(py_dir, "market.db"), ROLES_SQL)
        cases, dropped, declared = build_cases(spec, roles)
        if not cases:
            print("no case survived the role lookup: %r" % (dropped,))
            return 2

        contract_cases = {"cases": cases, "db_sha256": db_prints["market.db"]}
        dynamic = os.path.join(tmp, "cases_b5_run.json")
        with open(dynamic, "w", encoding="utf-8") as f:
            json.dump(contract_cases, f, ensure_ascii=False)
        case_count = len(cases)

        # ۱) اجرای B-G1 (Read Parity):
        rc, log = base.run([base.PARITY, "--py", py_url, "--go", go_url,
                            "--cases", dynamic,
                            "--db", os.path.join(go_dir, "market.db"),
                            "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        with open(CONTRACT, encoding="utf-8") as f:
            contract = json.load(f)
        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count
        max_delta = max([c.get("max_delta") or 0.0 for c in contract["cases"]] or [0.0])
        delta_zero = max_delta == 0.0

        pairs = [(c.get("status_py"), c.get("status_go")) for c in contract["cases"]]
        allowed = {(200, 200), (422, 422)}
        expect_422 = set(c["name"] for c in spec["cases"]
                         if not c.get("declared") and (c.get("expect_status") == 422
                                                       or c["name"].endswith("-422")))
        got_422 = set(c["name"] for c in contract["cases"]
                      if (c.get("status_py"), c.get("status_go")) == (422, 422))
        statuses_ok = (bool(pairs) and all(p in allowed for p in pairs)
                       and got_422 == expect_422)
        wanted = sorted(c["name"] for c in cases)
        ran = sorted(c["name"] for c in contract["cases"])
        coverage_ok = wanted == ran
        failed_cases = [{"name": c["name"], "diffs": c.get("diffs") or []}
                        for c in contract["cases"] if not c.get("pass")]

        answered = set(template_of(c["path"]) for c in contract["cases"]
                       if c.get("status_go") == 200)
        routes_ok = B5_READ_ROUTES.issubset(answered)

        problems = content_checks(py_url, cases)
        declared_rows, declared_problems = declared_probe(py_url, go_url, declared)

        # ۲) اجرای B-G2 (Write Parity Suite):
        write_ok, write_steps, write_problems = run_write_parity_suite(
            py_url, go_url,
            os.path.join(py_dir, "user.db"),
            os.path.join(go_dir, "user.db")
        )

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(os.path.join(go_dir, "market.db")) == db_prints
        root_after = engine.root_fingerprint()
        root_untouched = root_before == root_after
        sidecar_problem = base.sidecar_problem(before_sidecars, base.sidecar_state())

        checks = {
            "contract": contract_ok,
            "delta_zero": delta_zero,
            "statuses_200_422": statuses_ok,
            "case_coverage": coverage_ok,
            "routes_read_covered": routes_ok,
            "content": not problems,
            "declared_measured": not declared_problems,
            "notice_roles": bool(roles.get("notice_symbol")),
            "write_parity_bg2": write_ok,
            "go_market_read_only": go_db_unchanged,
            "root_untouched": root_untouched,
            "frozen_copies": frozen_ok,
            "sidecar_untouched": not sidecar_problem,
        }

        payload = {
            "commit": commit,
            "python": sys.version.split()[0],
            "ports": {"py": py_port, "go": go_port, "preferred_py": PY_PORT,
                      "preferred_go": GO_PORT, "fell_back": fell_back},
            "roles": roles, "dropped_cases": dropped,
            "db": {"market_sha256": db_prints["market.db"],
                   "frozen_ok": frozen_ok, "go_market_unchanged": go_db_unchanged,
                   "root_before": root_before, "root_after": root_after,
                   "root_untouched": root_untouched},
            "sidecar": {"ok": not sidecar_problem, "problem": sidecar_problem or ""},
            "statuses": {"pairs": sorted("%s/%s" % p for p in set(pairs)),
                         "count_422": sum(1 for p in pairs if p == (422, 422)),
                         "ok": statuses_ok},
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count, "max_delta": max_delta,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok,
                         "failed_cases": failed_cases},
            "content_problems": problems,
            "declared": {"rows": declared_rows, "problems": declared_problems,
                         "ok": not declared_problems},
            "write_parity": {
                "ok": write_ok,
                "step_count": len(write_steps),
                "steps": write_steps,
                "problems": write_problems,
            },
            "answered_templates": sorted(answered),
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | max_delta=%s | write_steps=%d/%d | roles=%s"
              % (contract["passed"], case_count, max_delta,
                 sum(1 for s in write_steps if s["ok"]), len(write_steps),
                 dict((k, (v or "-")[:14]) for k, v in roles.items())))
        for row in failed_cases:
            print("FAILED %s: %s" % (row["name"], "; ".join(row["diffs"][:4])))
        for p in problems:
            print("CONTENT %s" % p)
        for p in declared_problems:
            print("DECLARED %s" % p)
        for p in write_problems:
            print("WRITE %s" % p)
        result = 0 if all(checks.values()) else 1
    finally:
        base.stop(procs)
        problem = base.sidecar_problem(before_sidecars, base.sidecar_state())
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        if result != 0:
            engine.dump_logs(tmp)
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
