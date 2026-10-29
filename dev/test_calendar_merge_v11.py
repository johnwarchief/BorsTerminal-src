# -*- coding: utf-8 -*-
"""dev/test_calendar_merge_v11.py — Task 7: Cat 6 merge + client calendar asset.

Proves, with temp files only (no network, no CODAL, no ADB, no live DB):

  1) ``merge_calendar`` de-duplicates by (symbol, cat, date, title), keeps the
     old event object, preserves new events, updates ``meta.fetchedAt`` and
     recomputes ``meta.count``;
  2) empty old/new inputs are safe, and identical titles on different dates
     stay distinct;
  3) ``calendar_fetcher --merge`` path helper merges into an existing cache
     instead of replacing it;
  4) ``api.chart._cal_cache_events`` reads ``WORK_DIR/calendar.json`` first,
     falls back to the static path, and invalidates its cache on path+mtime;
  5) the orchestrator calls ``_fetch_calendar`` only on a non-dry-run run
     after a successful validation/merge, never on dry-run or validation
     failure, and a calendar failure only warns (``ok`` unchanged).

Run:  python dev/test_calendar_merge_v11.py
"""
import json
import os
import shutil
import sqlite3
import sys
import tempfile

try:                       # Persian/UTF-8 output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from pathlib import Path    # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))

import calendar_fetcher as cf          # noqa: E402
import codal_fetcher as codal_fetcher  # noqa: E402
import codal_auto_update as A          # noqa: E402
import api.chart as chart              # noqa: E402
import api._sync_codal as sync_mod     # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    return bool(cond)


TMP = tempfile.mkdtemp(prefix="calendar_merge_v11_")


# ── 1) merge_calendar ────────────────────────────────────────────────────────
def event(symbol, date, title, tid=1, **extra):
    ev = {"asset_symbol_trade": symbol, "date_time": date,
          "event_title": title, "description": title, "event_type_id": tid,
          "report_id": "%s-%s" % (symbol, date)}
    ev.update(extra)
    return ev


try:
    from calendar_merge import merge_calendar

    old_ev = event("فولاد", "2026-11-01T09:00:00+03:30", "آگهی دعوت به مجمع")
    new_dup = dict(old_ev, description="duplicate")
    new_ev = event("فولاد", "2026-11-02T09:00:00+03:30", "تصمیمات مجمع")
    old = {"meta": {"fetchedAt": "2026-10-01T00:00:00Z", "count": 1,
                    "industries": {"فولاد": "فلزات اساسي"}, "jmonths": ["1405/07"]},
           "token": "token-old-round1", "events": [old_ev]}
    new = {"meta": {"fetchedAt": "2026-10-28T12:00:00Z", "count": 2,
                    "industries": {"فولاد": "فلزات اساسي", "تست": "سایر"},
                    "jmonths": ["1405/08"]},
           "token": "token-new-round1", "events": [new_dup, new_ev]}
    merged = merge_calendar(old, new)
    ck(len(merged["events"]) == 2,
       "merge: duplicate removed, old+new kept (count=%d)" % len(merged["events"]))
    ck(merged["events"][0] is old_ev,
       "merge: duplicate keeps the old event object")
    ck(merged["events"][0].get("report_id") == old_ev["report_id"],
       "merge: old event fields are not overwritten by the duplicate")
    ck(any(e is new_ev for e in merged["events"]), "merge: new event preserved")
    ck(merged["meta"]["count"] == 2,
       "merge: meta.count recomputed (%r)" % merged["meta"].get("count"))
    ck(merged["meta"]["fetchedAt"] == "2026-10-28T12:00:00Z",
       "merge: meta.fetchedAt updated (%r)" % merged["meta"].get("fetchedAt"))
    ck(merged["meta"]["industries"].get("تست") == "سایر"
       and merged["meta"]["industries"].get("فولاد") == "فلزات اساسي",
       "merge: industries are additive, not replaced")
    ck(merged["meta"]["jmonths"] == ["1405/07", "1405/08"],
       "merge: jmonths union (%r)" % (merged["meta"].get("jmonths"),))
    ck(merged.get("token") == "token-old-round1",
       "merge: token survives (old token, not silently dropped) (%r)"
       % merged.get("token"))
    token_fallback = merge_calendar({"events": [], "meta": {}},
                                    {"events": [], "meta": {}, "token": "t-new"})
    ck(token_fallback.get("token") == "t-new",
       "merge: token falls back to the new payload when old has none (%r)"
       % token_fallback.get("token"))

    empty = merge_calendar({}, {})
    ck(empty["events"] == [] and empty["meta"]["count"] == 0,
       "merge: empty old/new -> no events, count 0 (%r)" % (empty,))
    empty_old = merge_calendar({}, {"events": [old_ev], "meta": {}})
    ck(len(empty_old["events"]) == 1 and empty_old["meta"]["count"] == 1,
       "merge: empty old + new event works")
    empty_new = merge_calendar(old, {"events": [], "meta": {"fetchedAt": "X"}})
    ck(len(empty_new["events"]) == 1 and empty_new["meta"]["count"] == 1,
       "merge: empty new keeps old event and recount")
    ck(empty_new["meta"]["fetchedAt"] == "X",
       "merge: empty new still updates fetchedAt")

    same_title_other_date = event("فولاد", "2026-12-01T09:00:00+03:30",
                                  old_ev["event_title"])
    distinct = merge_calendar({"events": [old_ev], "meta": {}},
                              {"events": [same_title_other_date], "meta": {}})
    ck(len(distinct["events"]) == 2,
       "merge: same title on a different date is distinct (count=%d)"
       % len(distinct["events"]))
    other_cat = event("فولاد", "2026-11-01T09:00:00+03:30",
                      old_ev["event_title"], tid=3)
    cat_distinct = merge_calendar({"events": [old_ev], "meta": {}},
                                  {"events": [other_cat], "meta": {}})
    ck(len(cat_distinct["events"]) == 2,
       "merge: same title/date but different category is distinct (count=%d)"
       % len(cat_distinct["events"]))

    # M1 fix: distinct CodAL letters sharing (symbol, cat, date, title) survive.
    letter_title = "آگهی دعوت به مجمع عمومی عادی بطور فوق العاده"
    letter_a = event("فساپ", "2026-09-23T10:00:00+03:30", letter_title,
                     report_id="r1602402")
    letter_b = event("فساپ", "2026-09-23T10:00:00+03:30", letter_title,
                     report_id="r1602422")
    letters = merge_calendar({"events": [letter_a], "meta": {}},
                             {"events": [letter_b, dict(letter_b)], "meta": {}})
    ck(len(letters["events"]) == 2,
       "merge: same title/date/cat, different report_id both survive (count=%d)"
       % len(letters["events"]))
    ck(sum(1 for e in letters["events"] if e.get("report_id") == "r1602422") == 1,
       "merge: identical duplicate collapses once under the report_id key")
    bare = {"asset_symbol_trade": "فساپ", "date_time": "2026-09-23T10:00:00+03:30",
            "event_title": letter_title, "cat": "6"}
    bare_merged = merge_calendar({"events": [bare], "meta": {}},
                                 {"events": [dict(bare, description="dup")], "meta": {}})
    ck(len(bare_merged["events"]) == 1,
       "merge: rows without report_id/event_type_id keep the 4-tuple fallback")

    # ── 2) calendar_fetcher --merge file helper ─────────────────────────────
    cache_path = os.path.join(TMP, "cache.json")
    with open(cache_path, "w", encoding="utf-8") as fh:
        json.dump(old, fh, ensure_ascii=False)
    payload = {"meta": {"fetchedAt": "2026-10-28T12:00:00Z", "count": 1,
                        "industries": {}, "jmonths": ["1405/08"]},
               "token": None, "events": [new_ev]}
    kept = cf.merge_payload_with_cache(payload, cache_path)
    ck(len(kept["events"]) == 2,
       "fetcher --merge: existing cache is merged, not replaced (count=%d)"
       % len(kept["events"]))
    with open(cache_path, "r", encoding="utf-8") as fh:
        on_disk = json.load(fh)
    ck(len(on_disk["events"]) == 1,
       "fetcher --merge: helper does not write (main owns the atomic write)")

    # I1 fix: an existing-but-unreadable cache must NOT be replaced.
    corrupt_cases = [
        ("invalid-json", b'{"events": [ '),
        ("non-dict", json.dumps([1, 2, 3]).encode("utf-8")),
        ("non-list-events", json.dumps({"events": {"a": 1}}).encode("utf-8")),
    ]
    for name, blob in corrupt_cases:
        bad = os.path.join(TMP, "bad_%s.json" % name)
        with open(bad, "wb") as fh:
            fh.write(blob)
        try:
            cf.merge_payload_with_cache(payload, bad)
            raised = False
        except cf.CacheMergeError:
            raised = True
        ck(raised, "fetcher --merge: %s cache aborts with CacheMergeError" % name)
        with open(bad, "rb") as fh:
            ck(fh.read() == blob,
               "fetcher --merge: %s cache left byte-identical" % name)

    # main(): the abort exits non-zero before any write; success still merges.
    real_out, real_fetch, real_ind = cf.OUT, cf.fetch_month, cf.load_industries
    real_argv = sys.argv
    try:
        cf.fetch_month = lambda *_a, **_k: [new_ev]
        cf.load_industries = lambda *_a, **_k: {}
        sys.argv = ["calendar_fetcher.py", "--cats", "6", "--months", "1", "--merge"]

        corrupt_main = os.path.join(TMP, "corrupt_main.json")
        with open(corrupt_main, "wb") as fh:
            fh.write(b'{"events": [ ')          # partially written cache
        before = open(corrupt_main, "rb").read()
        cf.OUT = Path(corrupt_main)
        rc = cf.main()
        ck(rc == 1, "fetcher main: corrupt cache -> non-zero exit (%r)" % (rc,))
        ck(open(corrupt_main, "rb").read() == before,
           "fetcher main: corrupt cache file is byte-identical after abort")

        good_main = os.path.join(TMP, "good_main.json")
        with open(good_main, "w", encoding="utf-8") as fh:
            json.dump(old, fh, ensure_ascii=False)
        cf.OUT = Path(good_main)
        rc = cf.main()
        with open(good_main, "r", encoding="utf-8") as fh:
            written = json.load(fh)
        ck(rc in (0, None), "fetcher main: --merge succeeds (%r)" % (rc,))
        ck(len(written["events"]) == 2,
           "fetcher main: calls the merge helper and keeps old+new (count=%d)"
           % len(written["events"]))
    finally:
        cf.OUT, cf.fetch_month, cf.load_industries = real_out, real_fetch, real_ind
        sys.argv = real_argv

    # Source wiring: the fetcher must actually call the merge helper; the
    # orchestrator must pass the fetched calendar asset to publish.
    import inspect
    fetch_src = inspect.getsource(cf.main)
    ck("args.merge" in fetch_src and "merge_payload_with_cache(" in fetch_src,
       "source: calendar_fetcher.main calls merge_payload_with_cache under --merge")
    run_src = inspect.getsource(A.run)
    ck('calendar_path = (result.get("calendar") or {}).get("path")' in run_src,
       "source: orchestrator derives the calendar path from the fetch result")
    ck("calendar=calendar_path" in run_src,
       "source: orchestrator passes calendar=calendar_path to publish")

    # ── 3) chart loader: WORK_DIR/calendar.json first, static fallback ──────
    work = os.path.join(TMP, "work")
    os.makedirs(work)
    work_cal = os.path.join(work, "calendar.json")
    static_cal = os.path.join(TMP, "static_cache.json")
    work_ev = event("کاربر", "2026-11-03T09:00:00+03:30", "رویدادِ WORK_DIR")
    static_ev = event("استاتیک", "2026-11-04T09:00:00+03:30", "رویدادِ static")
    with open(work_cal, "w", encoding="utf-8") as fh:
        json.dump({"events": [work_ev]}, fh, ensure_ascii=False)
    with open(static_cal, "w", encoding="utf-8") as fh:
        json.dump({"events": [static_ev]}, fh, ensure_ascii=False)

    real_work = chart.WORK_DIR
    real_static = chart._CAL_CACHE_PATH
    real_cache = dict(chart._cal_cache)
    try:
        chart.WORK_DIR = work
        chart._CAL_CACHE_PATH = static_cal
        chart._cal_cache.clear()
        chart._cal_cache.update({"mtime": 0.0, "events": []})
        got = chart._cal_cache_events()
        ck(len(got) == 1 and got[0]["asset_symbol_trade"] == "کاربر",
           "chart: WORK_DIR/calendar.json wins when present (%r)"
           % [e.get("asset_symbol_trade") for e in got])
        ck(chart._cal_cache_path() == work_cal,
           "chart: helper returns the chosen WORK_DIR path")

        # Path+mtime key: rewrite the same file → new events, not stale cache.
        newer = event("کاربر", "2026-11-05T09:00:00+03:30", "رویدادِ تازه")
        with open(work_cal, "w", encoding="utf-8") as fh:
            json.dump({"events": [newer]}, fh, ensure_ascii=False)
        st = os.stat(work_cal)
        os.utime(work_cal, ns=(st.st_atime_ns, st.st_mtime_ns + 1_000_000))
        got = chart._cal_cache_events()
        ck(got and got[0].get("event_title") == "رویدادِ تازه",
           "chart: cache invalidates on path+mtime change (%r)"
           % [e.get("event_title") for e in got])

        os.remove(work_cal)
        chart._cal_cache.clear()
        chart._cal_cache.update({"mtime": 0.0, "events": []})
        got = chart._cal_cache_events()
        ck(len(got) == 1 and got[0]["asset_symbol_trade"] == "استاتیک",
           "chart: falls back to static cache when WORK_DIR file is absent (%r)"
           % [e.get("asset_symbol_trade") for e in got])

        # M3 fix: a malformed WORK_DIR asset warns and falls back — no raise.
        for label, blob in (("non-list events", '{"events": {"a": 1}}'),
                            ("invalid json", "{not json")):
            with open(work_cal, "w", encoding="utf-8") as fh:
                fh.write(blob)
            chart._cal_cache.clear()
            chart._cal_cache.update({"mtime": 0.0, "events": []})
            got = chart._cal_cache_events()
            ck(len(got) == 1 and got[0]["asset_symbol_trade"] == "استاتیک",
               "chart: malformed WORK_DIR (%s) falls back to static (%r)"
               % (label, [e.get("asset_symbol_trade") for e in got]))
        with open(work_cal, "w", encoding="utf-8") as fh:
            json.dump({"events": [work_ev, "bad", 42]}, fh, ensure_ascii=False)
        chart._cal_cache.clear()
        chart._cal_cache.update({"mtime": 0.0, "events": []})
        got = chart._cal_cache_events()
        events_for = chart._cal_events_for("کاربر")
        ck(len(got) == 1 and isinstance(got[0], dict) and isinstance(events_for, list),
           "chart: non-dict events filtered; symbol lookup does not raise (%r)"
           % (got,))
    finally:
        chart.WORK_DIR = real_work
        chart._CAL_CACHE_PATH = real_static
        chart._cal_cache.clear()
        chart._cal_cache.update(real_cache)

    # ── 4) orchestrator: calendar only after a successful non-dry-run ───────
    FS_COLS = ("tracing_no", "symbol", "title", "period_end", "revenue",
               "gross_profit", "url", "publish_date")

    def insert_fs(path, row):
        conn = sqlite3.connect(path)
        conn.execute("INSERT INTO financial_statements (%s) VALUES (%s)"
                     % (",".join(FS_COLS), ",".join("?" * len(FS_COLS))),
                     [row[c] for c in FS_COLS])
        conn.commit()
        conn.close()

    def make_main(path):
        conn = sqlite3.connect(path)
        codal_fetcher.create_schema(conn)
        codal_fetcher.migrate_schema(conn)
        conn.close()
        insert_fs(path, {"tracing_no": 1, "symbol": "BASE", "title": "base",
                         "period_end": "1405/06/31", "revenue": 100.0,
                         "gross_profit": 50.0, "url": "https://codal.ir/fs/1",
                         "publish_date": "1405/07/01"})

    def make_fetch(revenue=200.0, gross_profit=90.0):
        def fake_fetch(db_path):
            insert_fs(db_path, {"tracing_no": 9001, "symbol": "NEW",
                                "title": "new", "period_end": "1405/06/31",
                                "revenue": revenue, "gross_profit": gross_profit,
                                "url": "https://codal.ir/fs/9001",
                                "publish_date": "1405/07/02"})
        return fake_fetch

    def boom(*_a, **_k):
        raise AssertionError("production step must not run in this path")

    def fake_run_cmd(argv, timeout):
        if argv and os.path.abspath(argv[-1]) == os.path.abspath(A.SNAPSHOT_LZMA):
            with open(A.SNAPSHOT_LZMA + ".sig", "wb") as fh:
                fh.write(b"sig")
        return None

    def fake_snapshot(_db, lzma, meta):
        with open(lzma, "wb") as fh:
            fh.write(b"lzma")
        with open(meta, "w", encoding="utf-8") as fh:
            json.dump({"latest_financial_period": "1405/06/31"}, fh)
        return {"latest_financial_period": "1405/06/31"}

    real_merge = sync_mod._apply_codal_merge
    sync_mod._apply_codal_merge = lambda *_a, **_k: None
    try:
        def fresh_env(name):
            d = os.path.join(TMP, name)
            os.makedirs(d)
            main = os.path.join(d, "market.db")
            make_main(main)
            A.STATUS = os.path.join(d, "codal_auto_status.json")
            A.LOCK = os.path.join(d, "codal_auto.lock")
            A.PAUSE = os.path.join(d, "codal_auto_pause")
            A.SNAPSHOT_LZMA = os.path.join(d, "codal.db.lzma")
            A.SNAPSHOT_META = os.path.join(d, "codal.meta.json")
            A.publish = boom
            A.build_snapshot = boom
            A._run_cmd = boom
            return main, os.path.join(d, "market.db.staging")

        calls = []
        calendar_asset = os.path.join(TMP, "published_calendar.json")

        def spy_ok():
            calls.append(1)
            return {"ok": True, "error": None, "path": calendar_asset}

        # dry-run: never called
        main, staging = fresh_env("dry_run")
        A._fetch = make_fetch()
        A._fetch_calendar = spy_ok
        r = A.run(dry_run=True, db_path=main, staging_dir=staging)
        ck(r["ok"] is True, "orchestrator dry-run: ok True")
        ck(calls == [], "orchestrator dry-run: calendar not called (%r)" % calls)

        # validation failure: never called
        main, staging = fresh_env("negative")
        A._fetch = make_fetch(revenue=-5.0, gross_profit=-10.0)
        A._fetch_calendar = spy_ok
        r = A.run(dry_run=False, db_path=main, staging_dir=staging)
        ck(r["ok"] is False, "orchestrator negative: ok False")
        ck(calls == [],
           "orchestrator validation failure: calendar not called (%r)" % calls)

        # successful non-dry-run: called exactly once, after merge
        main, staging = fresh_env("success")
        A._fetch = make_fetch()
        A._fetch_calendar = spy_ok
        A.build_snapshot = fake_snapshot
        A._run_cmd = fake_run_cmd
        pub_kwargs = []

        def fake_publish(*_a, **kw):
            pub_kwargs.append(kw)
            return {"uploaded": True}

        A.publish = fake_publish
        r = A.run(dry_run=False, db_path=main, staging_dir=staging)
        ck(r["ok"] is True, "orchestrator success: ok True (%r)" % (r["errors"],))
        ck(r["published"] is True, "orchestrator success: published True")
        ck(calls == [1], "orchestrator success: calendar called once (%r)" % calls)
        ck(pub_kwargs and pub_kwargs[-1].get("calendar") == calendar_asset,
           "orchestrator success: publish gets the exact fetched calendar asset "
           "(%r)" % (pub_kwargs,))

        # calendar failure is a warning only: ok/published unchanged
        main, staging = fresh_env("calendar_fail")
        A._fetch = make_fetch()
        A._fetch_calendar = lambda: {"ok": False, "error": "net down"}
        A.build_snapshot = fake_snapshot
        A._run_cmd = fake_run_cmd
        pub_kwargs = []
        A.publish = fake_publish
        r = A.run(dry_run=False, db_path=main, staging_dir=staging)
        ck(r["ok"] is True, "orchestrator calendar failure: ok stays True")
        ck(r["published"] is True,
           "orchestrator calendar failure: publish still happens")
        ck(any("calendar" in w for w in r.get("warnings") or []),
           "orchestrator calendar failure: warning recorded (%r)"
           % (r.get("warnings"),))
        ck(pub_kwargs and pub_kwargs[-1].get("calendar") is None,
           "orchestrator calendar failure: publish falls back (calendar None) (%r)"
           % (pub_kwargs,))
    finally:
        sync_mod._apply_codal_merge = real_merge

    failed = [m for ok, m in CHECKS if not ok]
    if failed:
        print("\nFAILED %d/%d" % (len(failed), len(CHECKS)))
        raise SystemExit(1)
    print("\nOK calendar merge (%d checks)" % len(CHECKS))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
