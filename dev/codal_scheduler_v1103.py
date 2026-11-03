#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_scheduler_v1103.py — گاردِ بندِ ۶: زمان‌بندی مستقل از رابط + catch-up.

چه چیزی بدونِ این گارد «باورکردنی» به نظر می‌رسد و دروغ است:

  * «برنامه خودش داده می‌گیرد» ⇒ باید ثابت شود چرخه به بازبودنِ تبِ بنیادی ربطی
    ندارد، و چند تب / چند فراخوانیِ استارت چند worker نمی‌سازد.
  * «timer گذاشتیم» ⇒ چراغِ بیدارباش باید از **خودِ صف و checkpoint** بیاید
    (وقتِ تلاشِ دوباره، عقب‌ماندگی، فاصلۀ مجازِ پاسِ شبکه) نه یک عددِ ثابت.
  * «بعد از قطعی جبران می‌کند» ⇒ `catchup_state` نباید وقتی هیچ چرخۀ موفقی
    سابقه ندارد «چند روز عقبیم» را بسازد.
  * «worker مستقل داریم» ⇒ دريچۀ فرمانی باید رویِ بانکِ ایزوله کار کند.
  * خزندۀ دستی و worker خودکار رویِ یکِ IP ⇒ `crawler_busy` باید پاسِ شبکه را
    موکول کند، وگرنه ۴۲۹/بن نصیبِ کاربر می‌شود.

**دو لایۀ امنیتِ شبکه** — اعتراف: اجرایِ اولِ همین گارد، چون `network=None`
خودش «کشف واجب است» را تصمیم گرفت، یکِ پاسِ واقعی به کدال زد و از راهِ ADB خواست
IP بچرخاند (همان کاری که قراردادِ مخزن برایِ آزمونِ یکِ گارد ممنوع می‌کند).
پیش از آن، «تزریقِ stub» تنها لایه بود و از راهِ subprocess رد می‌شد. حالا:
  ۱) `BORS_CODAL_OFFLINE=1` درِ خودِ `worker_once` — `network=True` و `force`
     هم نمی‌توانند ردش کنند؛
  ۲) tripwire رویِ `CF.fetch_page`/`CF.make_session` که با هر تماسِ بیرونی
     منفجر می‌شود، نه سکوت.
بانکِ عملیاتی `market.db` هرگز باز نمی‌شود؛ همه رویِ `:memory:` یا کپیِ موقت.

اجرا:  PYTHONIOENCODING=utf-8 python dev/codal_scheduler_v1103.py
خروجی: «N passed / M failed»، exit 0 یا 1
"""
from __future__ import annotations

import datetime
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ["BORS_CODAL_OFFLINE"] = "1"          # پیش از import: درِ خودِ worker

import codal_fetcher as CF                    # noqa: E402
import codal_pipeline as PL                   # noqa: E402

PASS = FAIL = 0
TMP = tempfile.mkdtemp(prefix="bors_sched_v1103_")


def _digits(n, width=2):
    return "".join(chr(0x06F0 + int(d)) for d in str(n).zfill(width))


FS_TITLE = ("صورت‌های مالی  سال مالی منتهی به " + _digits(1405, 4) +
            "/" + _digits(3) + "/" + _digits(31) + " (حسابرسی شده)")


def ck(ok, what, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("PASS %s" % what)
    else:
        FAIL += 1
        print("FAIL %s%s" % (what, ("   ← " + str(detail)) if detail else ""))


def tripwire():
    """هیچ دربی به بیرون باز نشود — با ترکیدن، نه با سکوت."""
    def _boom(*a, **k):
        raise AssertionError("network call reached inside an offline guard")
    CF.fetch_page = _boom
    CF.make_session = _boom
    CF.rotate_ip_via_adb = lambda *a, **k: False
    CF._jitter = lambda *a, **k: None


def fresh_db(path=None):
    c = sqlite3.connect(path or ":memory:", timeout=60, isolation_level=None)
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    c.execute("CREATE TABLE IF NOT EXISTS instruments (ins_code TEXT PRIMARY KEY,"
              " l_val18 TEXT, l_val30 TEXT, paper_type INTEGER)")
    return c


def fake_status(phase="codal_sync", age_s=30, name=None):
    """sync_status.jsonِ ساختگی درِ مسیرِ موقت (همان شکلِ `write_progress`)."""
    p = os.path.join(TMP, "sync_status_%s.json" % (name or age_s))
    ts = datetime.datetime.now() - datetime.timedelta(seconds=age_s)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"stage": "codal", "phase": phase,
                   "ts": ts.isoformat(timespec="seconds")}, f, ensure_ascii=False)
    return p


def add_notice(c, tn, sym, title=FS_TITLE, pub="1405/07/20 10:00:00"):
    c.execute("INSERT OR REPLACE INTO codal_notices (tracing_no, symbol,"
              " company_name, title, letter_code, publish_date, sent_date, url,"
              " fetched_at, pdf_url, excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tn, sym, sym, title, "1", pub, pub,
               "https://codal.ir/L/Detail/%d" % tn, "2026-10-14 00:00:00", "", ""))


def main() -> int:
    tripwire()
    ck(PL.offline_gate() is True,
       "BORS_CODAL_OFFLINE=1 خوانده می‌شود (دربۀ آفلاین درِ خودِ worker است)")

    # ── ۱) چراغِ بیدارباش از خودِ وضعیت، نه عددِ ثابت ─────────────────────
    c = fresh_db()
    w = PL.next_wakeup(c, now="2026-10-14 06:00:00")
    ck(w["reason"] in ("discovery-due", "idle") and w["seconds"] >= PL.CADENCE_MIN_S,
       "صفِ خالی + بدونِ پاسِ پیشین ⇒ «کشف واجب است»، بی‌صبریِ بی‌حد", w)
    PL.enqueue(c, [(1, "fs")])
    w2 = PL.next_wakeup(c, now="2026-10-14 06:00:00")
    ck(w2["reason"] == "backlog" and w2["seconds"] <= PL.CADENCE_BACKLOG_S,
       "کارِ بازیابی‌شدنی ⇒ بیدارباشِ زودتر از چرخۀ عادی", w2)
    PL.claim(c, "w1", limit=1, now="2026-10-14 06:00:00")
    PL.mark_failed(c, 1, error_kind="network", last_error="429",
                   now="2026-10-14 06:00:00")
    w3 = PL.next_wakeup(c, now="2026-10-14 06:00:00")
    ck(w3["reason"] == "retry-at" and w3["at"] <= "2026-10-14 06:02:00",
       "خطای شبکه ⇒ بیدارباش هیچ‌وقت دیرتر از `next_attempt_at` نیست", w3)
    PL.cursor_set(c, PL.CURSOR_LAST_NETWORK, "2026-10-14 05:59:00")
    w4 = PL.next_wakeup(c, now="2026-10-14 06:00:00")
    ck(w4["seconds"] > PL.CADENCE_MIN_S,
       "پاسِ شبکه تازه بوده ⇒ فاصلۀ مجاز رعایت می‌شود (بی‌انباشتِ درخواست)", w4)

    # ── ۲) خزندۀ دستی و worker خودکار رویِ یکِ IP نمی‌جنگند ────────────────
    b = PL.crawler_busy(status_path=fake_status(age_s=30))
    ck(b["busy"] is True and b["phase"] == "codal_sync",
       "فازِ تازهٔ «codal_sync» ⇒ خزنده در کار است، پاسِ شبکه موکول می‌شود", b)
    b2 = PL.crawler_busy(status_path=fake_status(age_s=7200, name="old"),
                         max_age_s=900)
    ck(b2["busy"] is False, "فازِ کهنه (۲ ساعت پیش) ⇒ «در کار نیست»", b2)
    b3 = PL.crawler_busy(status_path=os.path.join(TMP, "nothing.json"))
    ck(b3["busy"] is False, "فایلِ نبود ⇒ بی‌ادعا آزاد", b3)
    p_bad = os.path.join(TMP, "broken.json")
    open(p_bad, "w", encoding="utf-8").write("{نه json")
    b4 = PL.crawler_busy(status_path=p_bad)
    ck(b4["busy"] is False and b4["reason"] == "unreadable",
       "پاسخِ غیرقابل‌تفسیر ⇒ «آزاد» با علتِ ثبت‌شده، نه کرش", b4)

    # ── ۳) پنجرۀ معاملاتی از خودِ قواعدِ برنامه (نه تعریفِ دوم) ─────────────
    ck(PL.market_in_session(datetime.datetime(2026, 10, 14, 10, 30)) is True,
       "چهارشنبه ۱۰:۳۰ ⇒ بازار باز (همان `mstat_engine.in_trading_session`)")
    ck(PL.market_in_session(datetime.datetime(2026, 10, 14, 15, 0)) is False,
       "چهارشنبه ۱۵:۰۰ ⇒ بسته")
    ck(PL.market_in_session(datetime.datetime(2026, 10, 15, 10, 30)) is False,
       "پنجشنبه ⇒ تعطیل (همان قاعدۀ weekendِ خودِ برنامه)")

    # ── ۴) محاسبۀ سنگین درِ ساعتِ بازار موکول می‌شود، داده گم نمی‌شود ───────
    c2 = fresh_db()
    PL.dirty_mark(c2, "فولاد", "financial_statements", reason="test")
    n_before = PL.dirty_count(c2)
    r_open = PL.worker_once(conn=c2, now="2026-10-14 10:30:00", network=False,
                            busy={"busy": True, "reason": "manual-crawler"})
    ck(r_open.get("recalc_deferred") is True,
       "بازار باز ⇒ محاسبۀ مجددِ سنگین به چرخۀ بعد موکول می‌شود", r_open)
    ck(PL.dirty_count(c2) == n_before and n_before > 0,
       "و نمادِ علامت‌خورده درِ صفِ تازه‌سازی **می‌ماند** (چیزی گم نمی‌شود)",
       (n_before, PL.dirty_count(c2)))
    r_closed = PL.worker_once(conn=c2, now="2026-10-16 20:00:00", network=False,
                              busy={"busy": False, "reason": "idle"})
    ck(r_closed.get("recalc_deferred") is False,
       "بیرونِ نشست ⇒ محاسبه موکولِ چرخۀ بعد نمی‌شود", r_closed)

    # ── ۵) دربه‌دیوارِ آفلاین: حتی باخواستِ زمان‌بند، شبکه نمی‌رود ──────────
    trips = []
    real_disc = PL.discover_auto
    PL.discover_auto = lambda *a, **k: (trips.append("discover_auto"),
                                        {"found": 0, "enqueued": 0, "items": [],
                                         "floors": {}})[1]
    try:
        c3 = fresh_db()
        rw = PL.worker_once(conn=c3, now="2026-10-14 20:00:00", network=None,
                            busy={"busy": False, "reason": "idle"})
        ck(not trips and rw.get("network") is False,
           "با network=None که خودش «کشف واجب است» را تصمیم می‌گیرد: صفرِ درخواست",
           (trips, rw.get("network"), rw.get("skipped")))
        add_notice(c3, 500, "خودرو")
        PL.enqueue(c3, [(500, "fs")], reason="seed")
        rf = PL.worker_once(conn=c3, now="2026-10-14 20:05:00", network=True,
                            force=True, busy={"busy": False, "reason": "idle"})
        ck(not trips and rf.get("network") is False,
           "network=True و force هم از دربِ آفلاین رد نمی‌شود",
           (trips, rf.get("network")))
        ck(rf.get("failed", 0) >= 1,
           "و کارِ صف بی‌شبکه «شکستِ ثبت‌شده» می‌گیرد، نه دادهٔ ساختگی",
           {k: rf.get(k) for k in ("processed", "failed", "done")})
    finally:
        PL.discover_auto = real_disc
    cz = fresh_db()
    r0 = PL.worker_once(conn=cz, now="2026-10-14 20:00:00", network=False,
                        busy={"busy": False, "reason": "idle"})
    ck(r0.get("skipped") == "nothing-to-do",
       "هیچ کارِ باز و بدونِ شبکه ⇒ چرخه نمی‌نشیند (دروغِ «sync شد» نیست)", r0)
    ck(int(cz.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]) == 0,
       "و هیچ رکوردِ چرخۀ ساختگی درِ گزارش نوشته نمی‌شود")

    # ── ۶) پس از قطعی/خاموشی: catch-up از checkpoint، بی‌ساختنِ عدد ─────────
    st0 = PL.catchup_state(fresh_db(), now="2026-10-14 20:00:00")
    ck(st0["never_synced"] is True and st0["gap_seconds"] is None,
       "بانکی که هرگز موفق نبوده ⇒ never_synced، نه «صفر ثانیه عقب»", st0)
    c4 = fresh_db()
    add_notice(c4, 501, "فولاد")
    PL.enqueue(c4, [(501, "fs")], reason="three-days-outage")
    st1 = PL.catchup_state(c4, now="2026-10-14 20:00:00")
    ck(st1["retryable"] == 1 and st1["queued"] == 1 and st1["never_synced"] is True,
       "عقب‌ماندۀ سه‌روزه از خودِ صف خوانده می‌شود (قابلِ بازیابی)", st1)
    r1 = PL.worker_once(conn=c4, now="2026-10-14 20:00:00", budget=2,
                        network=False, busy={"busy": False, "reason": "idle"})
    ck(r1.get("processed", 0) >= 1 and r1.get("failed", 0) >= 1,
       "چرخۀ بازیابی کارِ معوق را برمی‌دارد و شکست را ثبت می‌کند", r1)
    row = dict(c4.execute("SELECT state, attempts, next_attempt_at, error_kind"
                          " FROM codal_extracted WHERE tracing_no=501").fetchone())
    ck(row["state"] in ("failed", "unresolved") and row["attempts"] >= 1
       and row["error_kind"] == "network",
       "شکستِ شبکه: حالت، شمارِ تلاش و علت درِ رکورد می‌ماند", row)
    ck(bool(row["next_attempt_at"]) and PL._to_dt(row["next_attempt_at"]),
       "و بیدارباش بعدی زمان‌دار است (نه چرخشِ بی‌پایان رویِ یکِ کار)",
       row["next_attempt_at"])

    # ── ۷) رشتۀ زمان‌بند: یکی به‌ازایِ پروسه، بی‌انباشت ─────────────────────
    dbp = os.path.join(TMP, "worker.db")
    fresh_db(dbp).close()

    def _factory():
        return fresh_db(dbp)

    real_busy = PL.crawler_busy
    PL.crawler_busy = lambda **kw: {"busy": True, "reason": "test-guard"}
    try:
        s1 = PL.start_worker(dbp, owner="t1", conn_factory=_factory, tick_s=1)
        s2 = PL.start_worker(dbp, owner="t2", conn_factory=_factory, tick_s=1)
        ck(s1.get("started") is True and s2.get("started") is False
           and s2.get("reason") == "already-running",
           "فراخوانیِ دومِ استارت رشتۀ دوم نمی‌سازد (چند تب ⇒ چند worker نیست)",
           (s1.get("started"), s2.get("started"), s2.get("reason")))
        ck(s2.get("owner") == "t1", "و مالکِ worker نخست عوض نمی‌شود",
           s2.get("owner"))
        ck(PL.worker_status()["running"] is True,
           "وضعیتِ رشتۀ زمان‌بند قابلِ خواندن است", PL.worker_status())
        PL.stop_worker(timeout_s=3)
        ck(PL.worker_status()["running"] is False,
           "توقف با stop event انجام می‌شود (رشتۀ daemon سرِ کار نمی‌ماند)",
           PL.worker_status())
    finally:
        PL.crawler_busy = real_busy

    # ── ۸) دريچۀ فرمانی (همان چیزی که Task Scheduler اجرا می‌کند) ──────────
    cli_db = os.path.join(TMP, "cli.db")
    cc = fresh_db(cli_db)
    add_notice(cc, 777, "شپنا")
    cc.execute("INSERT INTO codal_extracted (tracing_no, kind, state, attempts,"
               " updated_at) VALUES (777,'fs','queued',0,'2026-10-14 00:00:00')")
    cc.close()
    env = dict(os.environ, PYTHONIOENCODING="utf-8", BORS_CODAL_OFFLINE="1")

    def cli(args):
        r = subprocess.run([sys.executable,
                            os.path.join(ROOT, "codal_pipeline.py"),
                            "--db", cli_db, "--json"] + list(args),
                           capture_output=True, text=True, env=env, timeout=180,
                           cwd=ROOT)
        lines = [x for x in (r.stdout or "").splitlines() if x.startswith("{")]
        payload = json.loads(lines[-1]) if lines else {}
        return r, payload

    for args, need in ((["--status"], ("queue", "instruments", "worker")),
                       (["--catchup"], ("never_synced", "retryable")),
                       (["--once", "--network", "off"], ("skipped", "network"))):
        r, payload = cli(args)
        ck(r.returncode == 0 and all(k in payload for k in need),
           "CLI: `python codal_pipeline.py %s --json` رویِ بانکِ ایزوله"
           % " ".join(args[:1]),
           {"rc": r.returncode, "err": (r.stderr or "")[-160:],
            "keys": sorted(payload)[:6]})
    r_once, pl = cli(["--once"])
    ck(pl.get("network") is False,
       "CLIِ بی‌`--network off` هم شبکه نمی‌زند (دربه‌دیوار از env می‌آید)",
       {k: pl.get(k) for k in ("network", "processed", "failed", "skipped")})
    h = cli(["--status"])[1]
    ck(h["queue"]["retryable"] >= 1,
       "کارِ معوقِ بانکِ ایزوله از راهِ CLI هم دیده می‌شود", h["queue"])
    ck(h.get("last_data_update") is None,
       "بدونِ چرخۀ موفق، «تازگیِ داده» ساخته نمی‌شود", h.get("last_data_update"))

    # ── ۹) سلامت: شمارشِ ابزار، حالتِ worker و تازگیِ داده یک‌جا ────────────
    c5 = fresh_db()
    c5.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, paper_type)"
               " VALUES ('1','آوا','آواپارس',1)")
    PL.discover_instruments(c5)
    PL.enqueue(c5, [(900, "fs")])
    PL.claim(c5, "w9", limit=1)
    PL.mark_done(c5, 900, ok=True)
    hh = PL.health(c5, worker_key="")
    ck(hh["instruments"]["ledger"] == 1 and
       hh["instruments"]["no_fundamental"] == 1,
       "سلامتِ خط شمارشِ Universe را از دفتر می‌خواند", hh["instruments"])
    ck(hh["queue"]["done"] >= 1 and hh.get("worker", {}).get("running") is False,
       "حالتِ worker و صف با هم درِ یکِ پاسخ‌اند (UI یکِ منبع دارد)",
       (hh["queue"], hh["worker"]))
    ck(bool(hh.get("data_epoch")) and bool(hh.get("last_data_update")),
       "تازگیِ داده از زمانِ واقعیِ پردازش می‌آید (شکستِ cache در Stage 8)",
       (hh.get("data_epoch"), hh.get("last_data_update")))

    # ── ۱۰) کنترلِ منفی: چراغِ ثابت نبودن + دربه‌دیوارِ واقعی ───────────────
    a = PL.next_wakeup(fresh_db(), now="2026-10-14 06:00:00")
    b_ = PL.next_wakeup(c4, now="2026-10-14 06:00:00")
    ck((a["seconds"], a["reason"]) != (b_["seconds"], b_["reason"]),
       "دامِ سنسور: دو وضعیتِ مختلف ⇒ دو چراغِ مختلف", (a, b_))
    ck("BORS_CODAL_OFFLINE" in open(os.path.join(ROOT, "codal_pipeline.py"),
                                    encoding="utf-8").read(),
       "دربۀ آفلاین درِ خودِ `codal_pipeline.py` است، نه فقط درِ گارد")

    # ── ۱۱) پاسخِ سلامتِ رابط: هشت شمارشِ الزامی، یک‌جا ────────────────────
    c6 = fresh_db()
    c6.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, paper_type)"
               " VALUES ('7','ناپیدا','ناپیدا',1)")
    PL.discover_instruments(c6)
    add_notice(c6, 1200, "فولاد")
    PL.enqueue(c6, [(1200, "fs")])
    PL.claim(c6, "w11", limit=1)
    PL.mark_failed(c6, 1200, error_kind="network", last_error="429")
    sp = PL.status_payload(c6, now="2026-10-14 20:00:00")
    need = ("last_successful_sync", "last_attempt", "queue", "instruments",
            "incomplete_extractions", "last_data_update", "worker", "cadence",
            "catchup", "dirty_symbols", "undated_notices", "offline_gate")
    ck(all(k in sp for k in need),
       "پاسخِ سلامت شمارش‌هایِ الزامیِ بندِ ۸ را دارد (بی‌ساختنِ عدد)",
       [k for k in need if k not in sp])
    ck(sp["queue"]["failed"] == 1 and sp["queue"]["retryable"] == 1,
       "کارِ شکست‌خورده درِ صف شمرده می‌شود (نه درِ «موفق»)", sp["queue"])
    ck(sp["last_successful_sync"] is None,
       "چرخۀ شکست‌خورده هرگز «آخرین sync موفق» نمی‌شود",
       sp["last_successful_sync"])
    ck(sp["instruments"]["no_fundamental"] == 1,
       "شکافِ پوشش از دفترِ ابزار خوانده می‌شود", sp["instruments"])
    ck(sp["offline_gate"] is True and
       sp["cadence"]["seconds"] >= PL.CADENCE_MIN_S,
       "دربه‌دیوار و چراغِ چرخۀ بعدی هم درِ پاسخ‌اند",
       (sp["offline_gate"], sp["cadence"]))
    import codal_periods as _CP
    # دو ردیفِ بی‌دورۀ واقعی می‌کاریم تا شمارشِ پاسخ از خودِ ردیف‌ها بیاید، نه از
    # تعدادِ کلیدهای دیکشنری. دامِ پیشین `len(undated_counts())` را به خودش
    # می‌داد (۳ == ۳) و با صفربودنِ بی‌دوره‌ها هم سبز می‌ماند — یعنی سنسور کور بود.
    for _tno in (1301, 1302):
        c6.execute("INSERT INTO financial_statements (tracing_no, symbol, company_name,"
                   " title, period_end, revenue, unit) VALUES (?,'بی‌دوره','شرکت بی‌دوره'"
                   ",'صورت مالی میاندورهای',NULL,1000.0,'میلیون ریال')", (_tno,))
    c6.commit()
    want_undated = int(c6.execute("SELECT (SELECT COUNT(*) FROM financial_statements WHERE %s)"
                                  " + (SELECT COUNT(*) FROM monthly_sales WHERE %s)"
                                  % (_CP.UNDATED_SQL, _CP.UNDATED_SQL)).fetchone()[0])
    sp = PL.status_payload(c6, now="2026-10-14 20:00:00")
    ck(sp["undated_notices"] == want_undated == 2,
       "شمارشِ «بی‌دوره» شمارِ ردیف‌هایِ واقعی است، نه تعدادِ کلیدهای دیکشنری",
       (sp["undated_notices"], want_undated, len(_CP.undated_counts(c6))))
    c6.execute("DELETE FROM financial_statements WHERE tracing_no=1301")
    c6.commit()
    ck(PL.status_payload(c6, now="2026-10-14 20:00:00")["undated_notices"] == 1,
       "دامِ سنسور: با حذفِ یکِ ردیفِ بی‌دوره، پاسخ یکِ واحد پایین می‌آید")
    src = open(os.path.join(ROOT, "api", "fundamental.py"),
               encoding="utf-8").read()
    ck("/api/sync/codal/pipeline" in src and "status_payload" in src,
       "اندپوینتِ رابطِ کاربر وجود دارد و همان payload را می‌دهد")


    print("\n%d passed / %d failed" % (PASS, FAIL))
    return 1 if FAIL else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        import shutil
        shutil.rmtree(TMP, ignore_errors=True)
