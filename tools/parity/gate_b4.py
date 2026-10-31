#!/usr/bin/env python
"""گیتِ B4a: سه مسیرِ پورت‌شدهٔ بنیادی/نوار رویِ دو کپیِ یخ‌زده.

همان قواعدِ B1/B2/B3: بانکِ عملیاتی با SQLite باز نمی‌شود (فقط کپیِ موقتی
mode=ro)، هر کپی quick_check می‌خورد، فقط PIDهایِ همین اسکریپت کشته می‌شوند، و
اثرانگشتِ (sha256، اندازه، mtime_ns) بانک‌هایِ ریشه پیش/پس مقایسه می‌شود.

چه چیزِ مخصوصِ B4:

* تاریخچۀ نوار از **user.db** می‌خواند، پس دو کپی باید هر دو بانک را داشته
  باشند و هر دو طرف همان کپی را ببینند (سایۀ root دست‌نخورده).
* پنج کیسِ «تعویقِ اعلام‌شده» درِ مقایسه نیستند: کارتِ پنج‌محور، `screen`،
  `months` و دو مسیرِ sync/codal. گیت وضعیتِ هر دو طرف را اندازه می‌گیرد و درِ
  شاهد می‌نویسد (پایتون ۲۰۰ یا ۴۲۲ / Go ۵۰۱) — نه فرضِ سبز، نه سبزِ بی‌آزمون.
* نقش‌ها درِ زمانِ اجرا از همان کپی برگزیده می‌شوند: نمادی که چند دورۀ
  میاندوره‌ایِ دوره‌دار دارد، نمادی که هیچ صورتِ مالی ندارد، و دو ins_code که
  واقعاً درِ `tape_flag_day` ردیف دارند. بی‌این، سه مسیرِ تازه با بدنهٔ تهی سبز
  می‌شدند.
* `write_error` درِ دو طرف باید null باشد: حالتِ پروسه است، نه داده (R8).

کدِ خروج: 0 سبز، 1 اندازه‌گیری شد و قرمز، 2 نتوانستیم اندازه بگیریم.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base                                        # noqa: E402
import gate_b2a as engine                                     # noqa: E402

ROOT = base.ROOT
GO = base.GO
CASES = os.path.join(HERE, "cases_b4.json")
OUT = os.environ.get("BORS_B4_OUT") or os.path.join(ROOT, "_audit", "parity", "B4.json")
CONTRACT = (os.environ.get("BORS_B4_CONTRACT")
            or os.path.join(ROOT, "_audit", "parity", "B4-contract.json"))
GO_PORT = int(os.environ.get("BORS_B4_GO_PORT", "8300"))
PY_PORT = int(os.environ.get("BORS_B4_PY_PORT", "8301"))
ROOT_DBS = engine.ROOT_DBS
LOG_TAIL_LINES = 60

# نقش‌ها از خودِ کپی خوانده می‌شوند. قیدِ «دوره‌دار» عینِ DATED_SQL است تا کیسِ
# فصلی رویِ ردیف‌هایی بیفتد که هر دو زبان واقعاً می‌خوانند.
ROLES_SQL = {
    "fs_rich": (
        "SELECT symbol FROM financial_statements"
        " WHERE period_end IS NOT NULL AND trim(period_end)"
        " GLOB '[0-9][0-9][0-9][0-9]/[0-9][0-9]/[0-9][0-9]'"
        " GROUP BY symbol HAVING COUNT(DISTINCT period_end) >= 4"
        " AND COUNT(DISTINCT COALESCE(period_months, -1)) >= 2"
        " ORDER BY COUNT(*) DESC LIMIT 1"),
    "fs_empty": (
        "SELECT i.l_val18 FROM instruments i"
        " WHERE i.l_val18 NOT IN (SELECT symbol FROM financial_statements)"
        " AND i.l_val18 IS NOT NULL AND trim(i.l_val18) != ''"
        " ORDER BY i.updated_at DESC LIMIT 1"),
}
TAPE_ROLES = {
    "tape_a": "SELECT ins_code FROM tape_flag_day GROUP BY ins_code"
              " ORDER BY COUNT(*) DESC, ins_code LIMIT 1",
    "tape_b": "SELECT ins_code FROM tape_flag_day GROUP BY ins_code"
              " ORDER BY COUNT(*) ASC, ins_code LIMIT 1",
}
PLACEHOLDERS = ("fs_rich", "fs_empty", "tape_a", "tape_b")

B4_ROUTES = {"/api/fundamental/sectors", "/api/fundamental/{symbol}/quarters",
             "/api/tape-history"}


def pick_port(preferred, taken):
    for port in range(preferred, preferred + engine.PORT_SCAN):
        if port in taken:
            continue
        if base.port_free(port):
            return port
    raise RuntimeError("no free port near %d" % preferred)


def read_roles(db_path, roles_sql):
    """نخستین مقدارِ هر نقش از همان کپیِ یخ‌زده (فقط mode=ro؛ ریشه هرگز باز نمی‌شود)."""
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
    """جایگزینیِ {role}؛ نقشی که نبود ⇒ کیسش حذف می‌شود و ثبت می‌گردد.

    کیس‌هایِ `declared` از مقایسه بیرون می‌مانند (سنجهٔ جدا دارند) ولی درِ شاهد
    ثبت می‌شوند تا حذفشان قابلِ بازخوانی باشد.
    """
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
            declared.append(dict(row, note=case["declared"]))
        else:
            kept.append(row)
    return kept, dropped, declared


def template_of(path):
    """مسیرِ اجرا را به الگویِ فهرستِ پایتون برمی‌گرداند (نماد ⇒ {symbol})."""
    pure = path.split("?", 1)[0]
    segs = [x for x in pure.split("/") if x]
    if len(segs) >= 3 and segs[0] == "api":
        head, tail = "/api/" + segs[1], segs[2:]
        if head in ("/api/fundamental", "/api/sync") and tail[0] in ("sectors", "screen",
                                                                    "fts-coverage", "pipeline"):
            return head + "/" + tail[0] if len(tail) == 1 else head + "/{symbol}"
        if head == "/api/fundamental" and len(tail) == 2 and tail[1] == "quarters":
            return "/api/fundamental/{symbol}/quarters"
        if len(tail) == 1:
            return head + "/{symbol}"
    return pure


def content_checks(py_url, cases):
    """هیچ کیسی نباید با بدنهٔ تهی سبز شده باشد؛ سنسور باید رأی را ببیند."""
    by_name = {c["name"]: c["path"] for c in cases}
    problems = []

    def body_of(name):
        path = by_name.get(name)
        return engine.get_json(py_url + path)[1] if path else None

    secs = body_of("sectors")
    if not secs or secs.get("status") != "success" or not (secs.get("sectors") or []):
        problems.append("sectors list is empty: %r" % (secs,))

    q = body_of("quarters-rich")
    if not q or q.get("status") != "success" or len(q.get("quarters") or []) < 4:
        problems.append("quarters-rich rows=%r" % ((q or {}).get("count"),))
    else:
        # یکِ ردیف باید همهٔ هفت کلیدِ عمومی را داشته باشد و gross_profit تهی
        # هرگز با net_profit پر نشود (#102).
        for row in q["quarters"]:
            for key in ("period_end", "period_months", "revenue", "gross_profit",
                        "operating_profit", "net_profit", "basic_eps", "publish_date"):
                if key not in row:
                    problems.append("quarters-rich row misses %s" % key)
                    break
        # `period_end` و `period_months` درِ _public_fields هستند؛ چیزی که نباید
        # بیرون بیاید ستون‌هایِ داخلیِ انتخابِ مرجع است.
        for key in ("title", "tracing_no", "report_kind", "months_source"):
            if key in (q["quarters"][0] or {}):
                problems.append("internal column %s leaked into the public row" % key)
    one = body_of("quarters-limit1")
    if not one or len(one.get("quarters") or []) != 1:
        problems.append("quarters-limit1 rows=%r (clamp must reach the reply)"
                        % ((one or {}).get("count"),))
    zero = body_of("quarters-clamp-zero")
    if not zero or len(zero.get("quarters") or []) != 1:
        problems.append("quarters-clamp-zero rows=%r want 1 (max(1,min(limit,40)))"
                        % ((zero or {}).get("count"),))
    high = body_of("quarters-clamp-high")
    if high and len(high.get("quarters") or []) > 40:
        problems.append("quarters-clamp-high rows=%d exceeds the 40 cap"
                        % len(high["quarters"]))
    empt = body_of("quarters-empty-symbol")
    if not empt or empt.get("status") != "success" or (empt.get("count") or 0) != 0:
        problems.append("quarters-empty-symbol count=%r" % ((empt or {}).get("count"),))

    tape = body_of("tape-two-codes")
    if tape:
        if len(tape.get("flags") or []) != 7:
            problems.append("tape flags=%r want seven" % (tape.get("flags"),))
        if len(tape.get("days") or []) == 0:
            problems.append("tape calendar is empty — no watched day in this copy")
        bs = tape.get("by_symbol") or {}
        if len(bs) != 2:
            problems.append("tape by_symbol=%d want the two requested codes" % len(bs))
        active = 0
        for per in bs.values():
            if len(per or {}) != 7:
                problems.append("tape symbol carries %d flags, want 7" % len(per or {}))
            for cell in (per or {}).values():
                for day in (cell.get("days") or {}).values():
                    if day.get("active"):
                        active += 1
                    if not isinstance(list((cell.get("days") or {}).keys() or [""])[0], str):
                        problems.append("tape day key is not a string")
        if active == 0:
            problems.append("no active flag cell in the whole reply — the sensor is blind")
    nod = body_of("tape-no-codes")
    if nod and (nod.get("by_symbol") or {}):
        problems.append("tape-no-codes must return an empty by_symbol")
    unk = body_of("tape-unknown-code")
    if unk:
        per = (unk.get("by_symbol") or {}).get("ISIN-NOT-HERE") or {}
        if len(per) != 7:
            problems.append("unknown code must still get seven flags, got %d" % len(per))
        for flag, cell in per.items():
            if cell.get("days") and any(d.get("active") for d in cell["days"].values()):
                problems.append("unknown code shows an active day for %s" % flag)
    d1 = body_of("tape-one-day")
    if d1 and len(d1.get("days") or []) > 1:
        problems.append("tape-one-day calendar=%r want one day" % (d1.get("days"),))
    d0 = body_of("tape-zero-days")
    dd = body_of("tape-clamp-high")
    if d0 and dd and d0.get("days") != dd.get("days"):
        problems.append("days=0 (reads as 20) and days=9999 (clamps to 120) must agree on"
                        " a four-day calendar: %r vs %r" % (d0.get("days"), dd.get("days")))
    dup = body_of("tape-dup-codes")
    if dup and len(dup.get("by_symbol") or {}) != 1:
        problems.append("repeated codes must collapse to one key, got %d"
                        % len(dup.get("by_symbol") or {}))
    for name in ("quarters-rich", "tape-two-codes"):
        b = body_of(name)
        if b is not None and b.get("write_error") is not None:
            problems.append("%s write_error=%r in a fresh process" % (name, b["write_error"]))
    return problems
def declared_probe(py_url, go_url, declared):
    """پنج کیسِ تعویق: وضعیتِ هر دو طرف اندازه می‌گیرد، نه فرض.

    انتظار: Go همیشه ۵۰۱ NOT_PORTED؛ پایتون ۲۰۰ (یا ۴۲۲ برایِ monthsِ بی‌مصرف).
    اگر روزی کارت پورت شد، این سنجه قرمز می‌شود و می‌گوید کیس باید به مقایسه
    برگردد — یعنی تعویقِ ما تاریخ‌انقضا دارد، نه حدسِ خاموش.
    """
    rows, problems = [], []
    for case in declared:
        py_status, py_body = engine.get_json(py_url + case["path"])
        go_status, go_body = engine.get_json(go_url + case["path"])
        want_go = 501
        want_py = 422 if case["name"].endswith("-422") else 200
        ok = (go_status == want_go and (go_body or {}).get("code") == "NOT_PORTED"
              and py_status == want_py)
        rows.append({"name": case["name"], "path": case["path"], "py": py_status,
                     "go": go_status, "go_code": (go_body or {}).get("code"),
                     "expect_py": want_py, "ok": ok, "note": case["note"]})
        if not ok:
            problems.append("%s: py=%r (want %d) go=%r/%r"
                            % (case["name"], py_status, want_py, go_status,
                               (go_body or {}).get("code")))
    return rows, problems


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
    tmp = tempfile.mkdtemp(prefix="bors-b4-")
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
        user_prints = base.db_fingerprint(os.path.join(go_dir, "user.db"))
        if user_prints != base.db_fingerprint(os.path.join(py_dir, "user.db")):
            print("the two user.db copies are not identical; tape-history would compare"
                  " different tape tables")
            return 2
        frozen_ok = True

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
        roles.update(read_roles(os.path.join(py_dir, "user.db"), TAPE_ROLES))
        cases, dropped, declared = build_cases(spec, roles)
        if not cases:
            print("no case survived the role lookup: %r" % (dropped,))
            return 2
        contract_cases = {"cases": cases, "db_sha256": db_prints["market.db"],
                          "user_sha256": user_prints.get("user.db")}
        dynamic = os.path.join(tmp, "cases_b4_run.json")
        with open(dynamic, "w", encoding="utf-8") as f:
            json.dump(contract_cases, f, ensure_ascii=False)
        case_count = len(cases)

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
                         if c["name"].endswith("-422") and not c.get("declared"))
        got_422 = set(c["name"] for c in contract["cases"]
                      if (c.get("status_py"), c.get("status_go")) == (422, 422))
        statuses_ok = (bool(pairs) and all(p in allowed for p in pairs)
                       and got_422 == expect_422)
        wanted = sorted(c["name"] for c in cases)
        ran = sorted(c["name"] for c in contract["cases"])
        coverage_ok = wanted == ran
        failed_cases = [{"name": c["name"], "diffs": c.get("diffs") or []}
                        for c in contract["cases"] if not c.get("pass")]

        # هر سه مسیرِ پورت‌شده باید درِ اجرا جواب داده باشند؛ بی‌این، حذفِ یکِ
        # کیس پوشش را بی‌صدا کم می‌کرد.
        answered = set(template_of(c["path"]) for c in contract["cases"]
                       if c.get("status_go") == 200)
        routes_ok = B4_ROUTES.issubset(answered)

        problems = content_checks(py_url, cases)
        declared_rows, declared_problems = declared_probe(py_url, go_url, declared)

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(os.path.join(go_dir, "market.db")) == db_prints
        go_user_unchanged = base.db_fingerprint(os.path.join(go_dir, "user.db")) == user_prints
        root_after = engine.root_fingerprint()
        root_untouched = root_before == root_after
        sidecar_problem = base.sidecar_problem(before_sidecars, base.sidecar_state())

        checks = {"contract": contract_ok, "delta_zero": delta_zero,
                  "statuses_200_422": statuses_ok, "case_coverage": coverage_ok,
                  "routes_3_of_3": routes_ok, "content": not problems,
                  "declared_measured": not declared_problems,
                  "tape_roles": all(roles.get(r) for r in ("tape_a", "tape_b")),
                  "quarters_roles": all(roles.get(r) for r in ("fs_rich", "fs_empty")),
                  "go_read_only": go_db_unchanged and go_user_unchanged,
                  "root_untouched": root_untouched, "frozen_copies": frozen_ok,
                  "sidecar_untouched": not sidecar_problem}
        payload = {
            "commit": commit,
            "python": sys.version.split()[0],
            "ports": {"py": py_port, "go": go_port, "preferred_py": PY_PORT,
                      "preferred_go": GO_PORT, "fell_back": fell_back},
            "roles": roles, "dropped_cases": dropped,
            "db": {"market_sha256": db_prints["market.db"],
                   "user_sha256": user_prints.get("user.db"),
                   "frozen_ok": frozen_ok, "go_market_unchanged": go_db_unchanged,
                   "go_user_unchanged": go_user_unchanged,
                   "root_before": root_before, "root_after": root_after,
                   "root_untouched": root_untouched},
            "sidecar": {"ok": not sidecar_problem, "problem": sidecar_problem or ""},
            "statuses": {"pairs": sorted("%s/%s" % p for p in set(pairs)),
                         "count_422": sum(1 for p in pairs if p == (422, 422)),
                         "ok": statuses_ok},
            "python_redirect": redirect_paths,
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count, "max_delta": max_delta,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok,
                         "failed_cases": failed_cases},
            "content_problems": problems,
            "declared": {"rows": declared_rows, "problems": declared_problems,
                         "ok": not declared_problems},
            "answered_templates": sorted(answered),
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | max_delta=%s | roles=%s"
              % (contract["passed"], case_count, max_delta,
                 dict((k, (v or "-")[:14]) for k, v in roles.items())))
        for row in failed_cases:
            print("FAILED %s: %s" % (row["name"], "; ".join(row["diffs"][:4])))
        for p in problems:
            print("CONTENT %s" % p)
        for p in declared_problems:
            print("DECLARED %s" % p)
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
