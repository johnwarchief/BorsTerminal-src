#!/usr/bin/env python3
"""Prove the bytes pushed to GitHub are the bytes the manifest measured.

Two independent comparisons per tracked manifest entry:
  1. disk sha256/size == the manifest's recorded value (what the report claims)
  2. git hash-object(disk) == the blob OID at HEAD (what GitHub actually stores)

Comparison 2 goes through git's own clean filter, so a CRLF/LF content filter
cannot manufacture a false drift the way hashing `git show` output would.
Section 5 lists licensed inputs that live outside git; reported, not skipped.
"""
import hashlib
import io
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LOGS = os.path.join(HERE, "logs")
MAN = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3",
                   "ARTIFACTS-SHA256.txt")


def git(*args):
    r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True)
    return r.returncode, r.stdout


def main(skip_payload=False):
    rc, out = git("ls-tree", "-r", "--name-only", "HEAD")
    if rc != 0:
        sys.exit("FATAL: git ls-tree failed")
    tracked = set(out.decode("utf-8").splitlines())

    rows = []
    section = 0
    with io.open(MAN, encoding="utf-8") as fh:
        for line in fh:
            line = line.rstrip("\n")
            if line.startswith("# --- section"):
                section = int(line.split("section", 1)[1].strip().split()[0])
                continue
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 2)
            if len(parts) == 3:
                rel = parts[2].split("#", 1)[0].strip()
                rows.append((section, parts[0], int(parts[1]), rel,
                             "(payload)" in parts[2]))

    ok = 0
    problems = []
    untracked = []
    sec5 = []
    for sec, want_sha, want_size, rel, is_payload in rows:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if sec == 5:
            if not os.path.exists(path):
                sec5.append((rel, "ABSENT", "recorded-only, not re-measured"))
                continue
            if is_payload:
                if skip_payload:
                    sec5.append((rel, "PRESENT", "payload decompression skipped"))
                    continue
                import gzip
                h = hashlib.sha256()
                n = 0
                with gzip.open(path, "rb") as fh:
                    while True:
                        chunk = fh.read(1 << 20)
                        if not chunk:
                            break
                        h.update(chunk)
                        n += len(chunk)
                got, size = h.hexdigest(), n
            else:
                with io.open(path, "rb") as fh:
                    b = fh.read()
                got, size = hashlib.sha256(b).hexdigest(), len(b)
            if got == want_sha and size == want_size:
                sec5.append((rel, "PRESENT", "re-measured OK (%s)"
                             % ("payload" if is_payload else "container")))
            else:
                sec5.append((rel, "PRESENT", "DRIFT"))
                problems.append("LICENSED INPUT DRIFT %s recorded=%s/%d"
                                " measured=%s/%d"
                                % (rel, want_sha[:16], want_size,
                                   got[:16], size))
            continue
        if rel not in tracked:
            untracked.append(rel)
            continue
        if not os.path.exists(path):
            problems.append("tracked but missing on disk: %s" % rel)
            continue
        with io.open(path, "rb") as fh:
            disk = fh.read()
        got_disk = hashlib.sha256(disk).hexdigest()
        if got_disk != want_sha or len(disk) != want_size:
            problems.append("DISK DRIFT %s recorded=%s/%d disk=%s/%d"
                            % (rel, want_sha[:16], want_size,
                               got_disk[:16], len(disk)))
            continue
        rc, oid = git("rev-parse", "HEAD:" + rel)
        if rc != 0:
            problems.append("rev-parse failed: %s" % rel)
            continue
        rc, hobj = git("hash-object", "--path", rel, path)
        if rc != 0:
            problems.append("hash-object(file) failed: %s" % rel)
            continue
        a = oid.decode().strip()
        b = hobj.decode().strip()
        if a != b:
            problems.append("COMMIT DRIFT %s head_blob=%s disk_blob=%s"
                            % (rel, a[:16], b[:16]))
        else:
            ok += 1

    print("tracked_entries_verified=%d problems=%d" % (ok, len(problems)))
    print("manifest_entries_not_tracked_at_HEAD=%d" % len(untracked))
    for rel in untracked:
        print("  UNTRACKED %s" % rel)
    print("section5_licensed_inputs=%d" % len(sec5))
    for rel, state, note in sec5:
        print("  %s %s — %s" % (state, rel, note))
    for p in problems:
        print("  PROBLEM %s" % p)
    return 1 if problems else 0


def selftest():
    """Prove the verifier can fail: corrupt one recorded hash, expect a problem."""
    global MAN
    with io.open(MAN, encoding="utf-8") as fh:
        original = fh.read()
    lines = original.splitlines(True)
    targets = []
    for i, ln in enumerate(lines):
        if ln.startswith("#") or not ln.strip():
            continue
        parts = ln.split(None, 2)
        if len(parts) != 3:
            continue
        sec = None
        for j in range(i, -1, -1):
            if lines[j].startswith("# --- section"):
                sec = int(lines[j].split("section", 1)[1].strip().split()[0])
                break
        if sec in (1, 2, 3, 4) and "DISK" not in str(targets):
            targets.append(("tracked", i, sec))
        if sec == 5 and "(container)" in ln and "PRESENT" in ln:
            targets.append(("licensed", i, sec))
    picked = {}
    for kind, i, sec in targets:
        picked.setdefault(kind, (i, sec))
    if len(picked) < 2:
        print("SELFTEST FAIL: could not find both a tracked and a licensed row")
        return 1
    failures = 0
    for kind, (i, sec) in picked.items():
        bad = list(lines)
        parts = bad[i].split(None, 2)
        flipped = ("0" if parts[0][0] != "0" else "1") + parts[0][1:]
        bad[i] = bad[i].replace(parts[0], flipped, 1)
        tmp = os.path.join(LOGS, "selftest-manifest-%s.txt" % kind)
        with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(bad))
        MAN = tmp
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = main(skip_payload=True)
        text = buf.getvalue()
        want = "DISK DRIFT" if kind == "tracked" else "LICENSED INPUT DRIFT"
        seen = rc == 1 and want in text
        print("SELFTEST %s: rc=%d expected_signal=%r seen=%s -> %s"
              % (kind, rc, want, seen, "OK" if seen else "FAIL"))
        if not seen:
            failures += 1
            print(text)
        os.remove(tmp)
    MAN = os.path.join(ROOT, "docs", "opportunity-center", "phase49-3",
                       "ARTIFACTS-SHA256.txt")
    print("SELFTEST %d/%d controls behaved as expected"
          % (len(picked) - failures, len(picked)))
    return 1 if failures else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    raise SystemExit(main())