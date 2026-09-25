#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/data_age_release_guard.py — سنِ دادهٔ ریلیز سنجیده می‌شود، نه حدس.

چرا (DATA-AGE-1): هیچ مرحله‌ای در زنجیرهٔ ریلیز نمی‌دانست دیتابیسِ در حالِ
انتشار چند روزه است. `market.db.lzma` بی‌آنکه کسی سنش را ببیند از ریپو
می‌آید (CI هرگز داده نمی‌سازد) و `codal.db.lzma` از «تازه‌ترین ریلیزی که
دارد» جلو برده می‌شود — یعنی اسنپ‌شاتِ سه‌ماههٔ کدال می‌توانست ماه‌ها با هر
نسخهٔ جدید منتشر شود و دکمهٔ «بروزرسانی دیتابیس کدال» همان را بدهد.

این گارد دو طبقه را می‌بندد و هیچ‌کدام به market.db نیاز ندارد:
  ۱) رفتاری: با دیتابیس‌هایِ کوچکِ ساختگی، خودِ scripts/check_release_db.py
     اجرا می‌شود و کدِ خروج/پیام‌هایش بررسی می‌گردد (کهنه=هشدار، ساختارِ
     خراب=خطا، منبعِ کهنه‌تر از baseline=ردِ بسته‌بندی، دادهٔ نامعلوم=هرگز
     صفر نه رد، و اینکه --pack واقعاً به تابعِ pack می‌رسد);
  ۲) سیم‌کشی: release.ps1 و release.yml و publish_github_release.py باید
     همان اعداد را بخوانند و گزارش کنند.

نکتهٔ مهمِ طراحی که تست‌ها قفلش می‌کنند: «نداشتَنِ داده» هیچ‌وقت با «صفر
روز» یا «مردود» یکی نمی‌شود. جدولِ غایب یا stampِ NULL باید AGE_UNKNOWN
بدهد و ریلیز را نبندد؛ وگرنه یک باگِ کوچکِ داده، منتشرکردن را فلج می‌کند.

خروج: ۰ اگر همه درست، ۱ در غیر این صورت.
اجرا:  python dev/data_age_release_guard.py
"""
import ast
import io
import lzma
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CHECK = os.path.join(ROOT, "scripts", "check_release_db.py")
PASS = FAIL = 0


def ck(cond, label, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print("  FAIL  %s %s" % (label, extra))


def read(rel):
    with io.open(os.path.join(ROOT, rel), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- fixture
DDL = """
  CREATE TABLE instruments(ins_code TEXT);
  CREATE TABLE daily_prices(ins_code TEXT, d_even INT, fetched_at TEXT);
  CREATE TABLE market_totals(d_even INT, market_value REAL, updated_at TEXT);
  CREATE TABLE codal_notices(tracing_no INT, fetched_at TEXT);
  CREATE TABLE financial_statements(id INTEGER PRIMARY KEY);
"""


def make_db(path, day=20260101, synced="2026-01-01 09:00:00", full=True, fs_rows=1500):
    """دیتابیسِ کوچکِ همان شکلِ market.db؛ full=False یعنی ساختارِ خراب."""
    if os.path.exists(path):
        os.remove(path)
    c = sqlite3.connect(path)
    if full:
        c.executescript(DDL)
        c.execute("INSERT INTO daily_prices VALUES('x',?,?)", (day, synced))
        c.execute("INSERT INTO market_totals VALUES(?,?,?)", (day, 1.0, synced))
        c.execute("INSERT INTO codal_notices VALUES(1,?)", (synced,))
        c.executemany("INSERT INTO financial_statements DEFAULT VALUES", [()] * fs_rows)
    else:
        c.execute("CREATE TABLE instruments(ins_code TEXT)")
    c.commit()
    c.close()


def make_baseline(dst, day, synced):
    tmp = dst + ".src"
    make_db(tmp, day=day, synced=synced)
    with open(tmp, "rb") as f:
        raw = f.read()
    os.remove(tmp)
    with open(dst, "wb") as f:
        f.write(lzma.compress(raw, preset=1))


def run(args, cwd):
    p = subprocess.run([sys.executable, CHECK] + args, cwd=cwd,
                       capture_output=True, text=True, encoding="utf-8")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def behavior(work):
    """تست‌های رفتاری رویِ دیتابیس‌هایِ ساختگی (بدونِ bank)."""
    # ۱) کهنه: هشدار، ولی rc=0 (ریلیزِ صرفاً UI یا تعطیلات نباید بسته شود)
    d = os.path.join(work, "stale")
    os.makedirs(d)
    make_db(os.path.join(d, "market.db"))
    rc, out = run([], d)
    ck(rc == 0 and "AGE_STALE src.last_trading_day" in out and "STALE_COUNT=4" in out,
       "stale is a warning, not an abort", "rc=%d" % rc)
    rc2, out2 = run(["--strict"], d)
    ck(rc2 == 1 and "STRICT: stale stamps" in out2, "--strict turns it into an error",
       "rc=%d" % rc2)

    # ۲) ساختارِ خراب: هیچ‌وقت با «کهنه» بخشیده نمی‌شود
    d2 = os.path.join(work, "broken")
    os.makedirs(d2)
    make_db(os.path.join(d2, "market.db"), full=False)
    for flag in ([], ["--strict"], ["--pack"]):
        rc, out = run(flag, d2)
        ck(rc == 1 and "SRC_INCOMPLETE" in out and "PACK" not in out.replace("PACK_REFUSED", ""),
           "broken structure aborts %s" % (flag or "plain"), "rc=%d" % rc)

    # ۳) منبعِ کهنه‌تر از baseline = ردِ بسته‌بندی، بدونِ دست‌زدنِ فایل
    d3 = os.path.join(work, "regress")
    os.makedirs(d3)
    make_db(os.path.join(d3, "market.db"), day=20260101, synced="2026-01-01 09:00:00")
    bl = os.path.join(d3, "market.db.lzma")
    make_baseline(bl, 20260901, "2026-09-01 09:00:00")
    before = open(bl, "rb").read()
    rc, out = run(["--pack"], d3)
    ck(rc == 1 and "PACK_REFUSED" in out, "older source refuses to overwrite baseline",
       "rc=%d" % rc)
    ck(open(bl, "rb").read() == before, "refused pack left the baseline bytes intact")
    ck(not os.path.exists(bl + ".bak") and not os.path.exists(bl + ".new"),
       "refused pack created no .bak/.new")

    # ۴) منبعِ تازه‌تر: بسته می‌شود، نسخهٔ قبل حفظ می‌شود، round-trip می‌خورد
    make_db(os.path.join(d3, "market.db"), day=20260920, synced="2026-09-20 09:00:00")
    rc, out = run(["--pack"], d3)
    ck(rc == 0 and "round-trip OK" in out and "freshness src=" in out
       and os.path.exists(bl + ".bak"), "newer source packs and keeps .bak",
       "rc=%d" % rc)

    # ۵) --pack باید واقعاً به pack() برسد (یک بار main فقط validate می‌کرد)
    ck("[pack]" in out or "round-trip OK" in out, "--pack reaches pack(), not just validate()")

    # ۶) شکلِ CI: baseline هست، market.db نیست
    d5 = os.path.join(work, "ci")
    os.makedirs(d5)
    make_baseline(os.path.join(d5, "market.db.lzma"), 20260920, "2026-09-20 09:00:00")
    rc, out = run(["--baseline"], d5)
    ck(rc == 0 and "BASELINE_OK" in out and "BASELINE_KEY" in out
       and "SOURCE_KEY" not in out, "--baseline works with no market.db (CI shape)",
       "rc=%d" % rc)

    # ۷) baselineِ غایب: هشدار، نه شکست (بعضی checkoutها فایل ندارند)
    d6 = os.path.join(work, "empty")
    os.makedirs(d6)
    rc, out = run(["--baseline"], d6)
    ck(rc == 0 and "BASELINE_MISSING" in out, "missing baseline is reported, rc=0",
       "rc=%d" % rc)

    # ۸) stampِ نامعلوم/جدولِ غایب: هرگز ۰ روز و هرگز «کهنه» نمی‌شود
    d7 = os.path.join(work, "unknown")
    os.makedirs(d7)
    t = os.path.join(d7, "t.db")
    c = sqlite3.connect(t)
    c.executescript("""CREATE TABLE instruments(i TEXT);CREATE TABLE daily_prices(d INT,f TEXT);
                       CREATE TABLE market_totals(d INT,u TEXT);CREATE TABLE codal_notices(t INT,f TEXT);""")
    c.executemany("INSERT INTO daily_prices VALUES(NULL,NULL)", [()] * 3)
    c.commit()
    c.close()
    with open(t, "rb") as f:
        raw = f.read()
    os.remove(t)
    with open(os.path.join(d7, "market.db.lzma"), "wb") as f:
        f.write(lzma.compress(raw, preset=1))
    rc, out = run(["--baseline"], d7)
    ck("AGE_UNKNOWN" in out and "AGE_OK" not in out and "days=0.0" not in out,
       "unknown stamps print AGE_UNKNOWN, never 0", out.splitlines()[:4])
    ck("STALE_COUNT=0" in out, "unknown is never counted as stale")
    ck(rc == 1 and "BASELINE_INCOMPLETE" in out,
       "a baseline missing financial_statements does fail", "rc=%d" % rc)


def wiring():
    """سیم‌کشیِ زنجیره: اسکریپت‌هایِ انتشار باید همین سن را بخوانند."""
    chk = read("scripts/check_release_db.py")
    keys = set(re.findall(r'\("([a-z_]+)",\s*"SELECT', chk))
    ck(keys == {"last_trading_day", "market_synced_at", "market_totals_at",
                "codal_synced_at"}, "STAMPS covers the four Gregorian clocks", keys)

    block = chk[chk.find("STAMPS = ("):chk.find("_EPOCH")]
    for jalali in ("period_end", "publish_date", "monthly_sales"):
        ck(jalali not in block, "age never uses the Jalali field %s" % jalali)

    ps = read("release.ps1")
    ck("scripts\\check_release_db.py --pack" in ps, "release.ps1 still packs via the script")
    ck("scripts\\check_release_db.py --baseline" in ps,
       "release.ps1 reports the committed baseline when market.db is absent")
    ck("restored previous baseline" not in ps,
       "the pack abort message no longer claims a restore that never happens")

    yml = read(".github/workflows/release.yml")
    ck("check_release_db.py --baseline" in yml, "CI runs the baseline age check")
    ck("::warning::[data-age]" in yml and "AGE_STALE" in yml,
       "CI maps stale lines to annotations")
    ck("BASELINE_(OK|INCOMPLETE" in yml,
       "CI notices when the step produced no verdict at all")

    pub = read("scripts/publish_github_release.py")
    ck("CODAL_MAX_AGE_DAYS" in pub and "_days_since(src.get(\"published_at\"))" in pub,
       "the publisher reports the age of the carried-forward codal.db.lzma")
    ck("_codal_age_line(_snapshot_age_days(path)" in pub,
       "the real snapshot age is read from the downloaded bytes, not the release date")
    m = re.search(r"CODAL_MAX_AGE_DAYS\s*=\s*(\d+)", pub)
    lim = re.search(r'\("codal_synced_at",\s*"[^"]+",\s*"[^"]+",\s*(\d+)\)', chk)
    ck(bool(m and lim and m.group(1) == lim.group(1)),
       "one codal age limit is shared by both scripts",
       "publisher=%s checker=%s" % (m and m.group(1), lim and lim.group(1)))


def helper_semantics(work):
    """_days_since را بدونِ importکردنِ اسکریپتِ انتشار می‌سنجیم (ورودش عوارض دارد)."""
    pub_src = read("scripts/publish_github_release.py")
    tree = ast.parse(pub_src)
    ns = {"os": os}
    got = set()
    for n in tree.body:
        if isinstance(n, ast.FunctionDef) and n.name in ("_days_since", "_snapshot_age_days"):
            exec(compile(ast.Module(body=[n], type_ignores=[]), "<guard>", "exec"), ns)
            got.add(n.name)
    ck(got == {"_days_since", "_snapshot_age_days"},
       "both age helpers are top-level functions (extractable without import side effects)")
    if "_days_since" not in ns:
        return
    f = ns["_days_since"]
    ck(f(None) is None and f("garbage") is None, "unreadable date -> None, never 0")
    ck(abs(f("2026-09-20T12:00:00Z") - f("2026-09-20 12:00:00")) < 1e-6,
       "Z and naive UTC parse the same")
    ck(f("2020-01-01T00:00:00Z") > 2000, "an old release reads as old")

    if "_snapshot_age_days" in ns:
        g = ns["_snapshot_age_days"]
        snapdir = os.path.join(work, "snap")
        os.makedirs(snapdir, exist_ok=True)
        p = os.path.join(snapdir, "codal.db.lzma")
        empty = os.path.join(snapdir, "empty.db")
        c = sqlite3.connect(empty)
        c.execute("CREATE TABLE codal_notices(tracing_no INT, fetched_at TEXT)")
        c.commit()
        c.close()
        with open(empty, "rb") as fh:
            raw = fh.read()
        os.remove(empty)
        with open(p, "wb") as fh:
            fh.write(lzma.compress(raw, preset=1))
        ck(g(p) is None, "a snapshot with no fetched_at reads as unknown, not fresh")
        c = sqlite3.connect(empty)
        c.executescript("CREATE TABLE codal_notices(tracing_no INT, fetched_at TEXT);"
                        "INSERT INTO codal_notices VALUES(1,'2026-01-01 09:00:00')")
        c.commit()
        c.close()
        with open(empty, "rb") as fh:
            raw = fh.read()
        with open(p, "wb") as fh:
            fh.write(lzma.compress(raw, preset=1))
        age = g(p)
        ck(age is not None and age > 200, "the snapshot age comes from fetched_at",
           "age=%s" % age)


def main():
    work = tempfile.mkdtemp(prefix="data_age_guard_")
    try:
        behavior(work)
        helper_semantics(work)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    wiring()
    print("data_age_release_guard: %d passed, %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
