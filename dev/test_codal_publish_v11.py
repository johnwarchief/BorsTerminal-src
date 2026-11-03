# -*- coding: utf-8 -*-
"""dev/test_codal_publish_v11.py — Task 5: publish to the stable data tag.

Proves, against a fake ``gh`` python script (no network, no token, temp files):

  1) ``publish(..., dry_run=True)`` returns ``uploaded False`` / ``dry_run True``
     and never executes ``gh``;
  2) a live ``publish`` uploads ``codal.db.lzma``, ``codal.db.lzma.sig``,
     ``codal.meta.json`` and ``calendar.json`` with
     ``release upload data-codal ... --clobber`` and fills ``last_good/``;
  3) a missing tag is created first as a prerelease
     (``release create data-codal ... --prerelease``);
  4) ``rollback`` re-uploads exactly the last-known-good set;
  5) ``keep_last_good`` skips missing files instead of crashing;
  6) a failed ``gh`` call surfaces as ``uploaded False`` + ``error``
     (never swallowed), and no last-good is recorded;
  7) calendar resolution: explicit arg > ``WORK_DIR/calendar.json`` >
     ``static/calendar/cache.json``, included only when the file exists.

``BORS_GH`` is set to ``"<python>" "<fake-gh>"``.  The quotes matter on
Windows: POSIX ``shlex.split`` treats an unquoted ``\\`` as an escape and
would turn ``C:\\Python\\python.exe`` into ``C:Pythonpython.exe``.

Run:  python dev/test_codal_publish_v11.py
"""
import json
import os
import shutil
import sys
import tempfile

try:                       # Persian/UTF-8 output on a cp1252 Windows console
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)

import scripts.publish_codal_snapshot as P  # noqa: E402

CHECKS = []


def ck(cond, msg):
    CHECKS.append((bool(cond), msg))
    return bool(cond)


# ── fake gh ───────────────────────────────────────────────────────────────
# Appends one JSON array per invocation to args.txt.  rc for each release
# subcommand is controlled by FAKE_GH_*_RC so failure paths are testable.
FAKE_SRC = (
    "import json, os, sys\n"
    "with open(%r, 'a', encoding='utf-8') as fh:\n"
    "    fh.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    "kind = ' '.join(sys.argv[1:3])\n"
    "rc = 0\n"
    "if kind == 'release view':\n"
    "    rc = int(os.environ.get('FAKE_GH_VIEW_RC', '0'))\n"
    "elif kind == 'release create':\n"
    "    rc = int(os.environ.get('FAKE_GH_CREATE_RC', '0'))\n"
    "elif kind == 'release upload':\n"
    "    rc = int(os.environ.get('FAKE_GH_UPLOAD_RC', '0'))\n"
    "if rc:\n"
    "    sys.stderr.write('fake gh forced failure: ' + kind + '\\n')\n"
    "sys.exit(rc)\n"
)

tmp = tempfile.mkdtemp(prefix="codal_pub_")
try:
    args_log = os.path.join(tmp, "args.txt")
    fake_gh = os.path.join(tmp, "fake gh.py")      # space proves quoting works
    with open(fake_gh, "w", encoding="utf-8") as f:
        f.write(FAKE_SRC % args_log)

    os.environ["BORS_GH"] = '"%s" "%s"' % (sys.executable, fake_gh)
    P.LAST = os.path.join(tmp, "last_good")

    lzma = os.path.join(tmp, "codal.db.lzma")
    sig = lzma + ".sig"
    meta = os.path.join(tmp, "codal.meta.json")
    cal = os.path.join(tmp, "calendar.json")
    for path, payload in ((lzma, b"lzma-bytes"), (sig, b"sig-bytes"),
                          (meta, b'{"schema_version": 1}'),
                          (cal, b'{"events": []}')):
        with open(path, "wb") as f:
            f.write(payload)

    def calls():
        if not os.path.isfile(args_log):
            return []
        with open(args_log, encoding="utf-8") as f:
            return [json.loads(ln) for ln in f if ln.strip()]

    def clear_calls():
        if os.path.exists(args_log):
            os.remove(args_log)

    def upload_calls():
        return [c for c in calls() if c[:3] == ["release", "upload", "data-codal"]]

    # ── 0) BORS_GH parses on Windows (quoted paths) ─────────────────────
    ck(P._gh() == [sys.executable, fake_gh],
       "BORS_GH parses to [python, fake gh] (got %r)" % (P._gh(),))

    # ── 1) dry run: no gh call, truthful result ────────────────────────
    clear_calls()
    r = P.publish(lzma, sig, meta, tag="data-codal", dry_run=True,
                  calendar=cal)
    ck(r.get("uploaded") is False, "dry-run uploaded is False (%r)" % (r,))
    ck(r.get("dry_run") is True, "dry-run dry_run is True (%r)" % (r,))
    ck(r.get("tag") == "data-codal", "dry-run echoes tag (%r)" % (r,))
    ck(calls() == [], "dry-run made no gh call (got %r)" % (calls(),))
    ck(not os.path.exists(P.LAST), "dry-run did not create last_good/")

    # ── 2) live publish: view + upload + last_good ─────────────────────
    clear_calls()
    r2 = P.publish(lzma, sig, meta, tag="data-codal", dry_run=False,
                   calendar=cal)
    ck(r2.get("uploaded") is True, "live uploaded is True (%r)" % (r2,))
    ck(r2.get("dry_run") is False, "live dry_run is False")
    live = calls()
    ups = upload_calls()
    ck(len(ups) == 1, "live made exactly one upload call (%r)" % (live,))
    ck(not [c for c in live if c[:3] == ["release", "create", "data-codal"]],
       "live did not create an existing tag (%r)" % (live,))
    if ups:
        up = ups[0]
        ck(up[:3] == ["release", "upload", "data-codal"],
           "upload argv starts with release upload data-codal (%r)" % (up,))
        ck("--clobber" in up, "upload argv has --clobber (%r)" % (up,))
        ck(P.REPO in up, "upload argv names the distribution repo (%r)" % (up,))
        for path in (lzma, sig, meta, cal):
            ck(path in up, "upload argv includes %s (%r)"
               % (os.path.basename(path), up))
        ck(len([t for t in up if t in (lzma, sig, meta, cal)]) == 4,
           "upload argv carries all four assets once (%r)" % (up,))
    ck(os.path.isdir(P.LAST), "live created last_good/")
    want = {os.path.basename(p): p for p in (lzma, sig, meta, cal)}
    got = set(os.listdir(P.LAST)) if os.path.isdir(P.LAST) else set()
    ck(got == set(want), "last_good/ holds the uploaded set (%r)" % (got,))
    for name, src in want.items():
        dst = os.path.join(P.LAST, name)
        same = (os.path.isfile(dst)
                and open(dst, "rb").read() == open(src, "rb").read())
        ck(same, "last_good/%s matches the uploaded bytes" % name)

    # ── 3) missing tag: create prerelease, then upload ─────────────────
    clear_calls()
    os.environ["FAKE_GH_VIEW_RC"] = "1"
    try:
        r3 = P.publish(lzma, sig, meta, tag="data-codal", calendar=cal)
    finally:
        os.environ.pop("FAKE_GH_VIEW_RC", None)
    ck(r3.get("uploaded") is True,
       "missing tag is still published (%r)" % (r3,))
    made = [c for c in calls() if c[:3] == ["release", "create", "data-codal"]]
    ck(len(made) == 1, "missing tag triggers one release create (%r)" % (calls(),))
    if made:
        ck("--prerelease" in made[0],
           "created tag is a prerelease (%r)" % (made[0],))
        ck(P.REPO in made[0], "create names the distribution repo (%r)"
           % (made[0],))
    ck(len(upload_calls()) == 1, "upload still follows the create (%r)" % (calls(),))
    ck(r3.get("created_tag") is True, "result reports created_tag (%r)" % (r3,))

    # ── 4) rollback re-uploads the last-known-good set ─────────────────
    clear_calls()
    r4 = P.rollback("data-codal")
    ck(r4.get("rolled_back") is True, "rollback reports success (%r)" % (r4,))
    rb = upload_calls()
    ck(len(rb) == 1, "rollback made exactly one upload call (%r)" % (calls(),))
    lg = {n: os.path.join(P.LAST, n) for n in want}
    if rb:
        ck(rb[0][:3] == ["release", "upload", "data-codal"],
           "rollback argv starts with release upload data-codal (%r)" % (rb[0],))
        ck("--clobber" in rb[0], "rollback argv has --clobber (%r)" % (rb[0],))
        for name, path in lg.items():
            ck(path in rb[0], "rollback uploads last_good/%s (%r)"
               % (name, rb[0]))
        ck(len([t for t in rb[0] if t in lg.values()]) == 4,
           "rollback uploads all four last-good files once (%r)" % (rb[0],))

    # ── 5) keep_last_good tolerates missing files ──────────────────────
    missing = os.path.join(tmp, "does-not-exist.bin")
    kept = None
    crash = None
    try:
        kept = P.keep_last_good([missing, sig])
        empty = P.keep_last_good([])
    except Exception as e:             # noqa: BLE001 — must not raise
        crash = e
        empty = None
    ck(crash is None, "keep_last_good does not crash on missing files (%r)"
       % (crash,))
    ck(kept == [os.path.join(P.LAST, "codal.db.lzma.sig")],
       "keep_last_good skips the missing file (got %r)" % (kept,))
    ck(empty == [], "keep_last_good([]) returns [] (got %r)" % (empty,))
    ck(not os.path.exists(os.path.join(P.LAST, "does-not-exist.bin")),
       "keep_last_good did not invent the missing file")

    # ── 6) failed upload surfaces an error, no last-good write ─────────
    clear_calls()
    before = set(os.listdir(P.LAST))
    stats_before = {n: os.path.getmtime(os.path.join(P.LAST, n))
                    for n in before}
    os.environ["FAKE_GH_UPLOAD_RC"] = "1"
    try:
        r5 = P.publish(lzma, sig, meta, tag="data-codal", calendar=cal)
    finally:
        os.environ.pop("FAKE_GH_UPLOAD_RC", None)
    ck(r5.get("uploaded") is False, "failed upload returns uploaded False (%r)"
       % (r5,))
    ck(isinstance(r5.get("error"), str) and r5["error"],
       "failed upload returns a non-empty error (%r)" % (r5,))
    stats_after = {n: os.path.getmtime(os.path.join(P.LAST, n))
                   for n in os.listdir(P.LAST)}
    ck(stats_after == stats_before,
       "failed upload leaves last_good/ untouched")

    # ── 7) failed tag create surfaces an error ─────────────────────────
    clear_calls()
    os.environ["FAKE_GH_VIEW_RC"] = "1"
    os.environ["FAKE_GH_CREATE_RC"] = "1"
    try:
        r6 = P.publish(lzma, sig, meta, tag="data-codal", calendar=cal)
    finally:
        os.environ.pop("FAKE_GH_VIEW_RC", None)
        os.environ.pop("FAKE_GH_CREATE_RC", None)
    ck(r6.get("uploaded") is False, "failed create returns uploaded False (%r)"
       % (r6,))
    ck("create" in (r6.get("error") or "").lower(),
       "failed create names the failing step (%r)" % (r6,))
    ck(not upload_calls(), "failed create never uploads (%r)" % (calls(),))

    # ── 8) calendar resolution order ───────────────────────────────────
    # a) explicit path wins (already proven in 2); a missing explicit path
    #    must not silently pick another calendar.
    r7 = P.publish(lzma, sig, meta, dry_run=True,
                   calendar=os.path.join(tmp, "missing-calendar.json"))
    ck(len(r7.get("files") or []) == 3,
       "missing explicit calendar is omitted (%r)" % (r7.get("files"),))

    # b) WORK_DIR/calendar.json when no argument is given.
    work = os.path.join(tmp, "work")
    os.makedirs(work)
    work_cal = os.path.join(work, "calendar.json")
    with open(work_cal, "wb") as f:
        f.write(b'{"events": ["work"]}')
    old_work = P.WORK_DIR
    P.WORK_DIR = work
    try:
        r8 = P.publish(lzma, sig, meta, dry_run=True)
    finally:
        P.WORK_DIR = old_work
    ck(work_cal in (r8.get("files") or []),
       "WORK_DIR/calendar.json is picked up (%r)" % (r8.get("files"),))

    # c) static/calendar/cache.json as the last resort.
    empty_work = os.path.join(tmp, "empty_work")
    os.makedirs(empty_work)
    static_cal = os.path.join(P.ROOT, "static", "calendar", "cache.json")
    P.WORK_DIR = empty_work
    try:
        r9 = P.publish(lzma, sig, meta, dry_run=True)
    finally:
        P.WORK_DIR = old_work
    if os.path.isfile(static_cal):
        ck(r9.get("calendar") == static_cal,
           "static/calendar/cache.json is the last-resort calendar (%r)"
           % (r9.get("calendar"),))
        ck(len(r9.get("files") or []) == 4,
           "static fallback plans four files (%r)" % (r9.get("files"),))
        # the cache.json fallback is still published under calendar.json
        clear_calls()
        P.WORK_DIR = empty_work
        try:
            r9b = P.publish(lzma, sig, meta)
        finally:
            P.WORK_DIR = old_work
        ups9 = upload_calls()
        ck(r9b.get("uploaded") is True,
           "static fallback publishes live (%r)" % (r9b,))
        ck(bool(ups9) and any(os.path.basename(t) == "calendar.json"
                              for t in ups9[0]),
           "cache.json fallback is uploaded as calendar.json (%r)" % (ups9,))
        ck(os.path.isfile(os.path.join(P.LAST, "calendar.json")),
           "last_good stores the fallback as calendar.json")
    else:
        ck(len(r9.get("files") or []) == 3,
           "no calendar anywhere means three files (%r)"
           % (r9.get("files"),))

    # ── 9) rollback without last-good is an error, not a fake success ──
    old_last = P.LAST
    P.LAST = os.path.join(tmp, "empty_last")
    try:
        clear_calls()
        r10 = P.rollback("data-codal")
    finally:
        P.LAST = old_last
    ck(r10.get("rolled_back") is False,
       "rollback without last-good returns rolled_back False (%r)" % (r10,))
    ck(isinstance(r10.get("error"), str) and r10["error"],
       "rollback without last-good explains itself (%r)" % (r10,))
    ck(calls() == [], "rollback without last-good made no gh call (%r)"
       % (calls(),))
finally:
    shutil.rmtree(tmp, ignore_errors=True)

failed = [m for ok, m in CHECKS if not ok]
print("%d PASS / %d FAIL" % (len(CHECKS) - len(failed), len(failed)))
for m in failed:
    print("FAIL: %s" % m)
if failed:
    sys.exit(1)
print("OK publish dry-run/live (fake gh)")
