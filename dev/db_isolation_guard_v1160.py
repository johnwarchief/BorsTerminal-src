#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""db_isolation_guard_v1160 — تست‌ها نباید به دیتابیس عملیاتی برسند.

این گارد در subprocessهای جدا اجرا می‌شود (نه با import در همین process) تا
مسیرِ واقعیِ resolver دیده شود. هیچ فایل عملیاتی نوشته/بازنویسی نمی‌شود.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   " + label)
    else:
        FAIL += 1
        print("FAIL " + label + "  -> " + str(detail)[:240])


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for b in iter(lambda: f.read(1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def child(code, env, cwd=ROOT):
    return subprocess.run([sys.executable, '-c', code], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=60)


def main() -> int:
    tmp = tempfile.mkdtemp(prefix='dbiso_')
    iso = os.path.join(tmp, 'iso')
    os.makedirs(iso, exist_ok=True)
    open(os.path.join(iso, '.bors_test_isolation'), 'w').write('guard\n')
    no_marker = os.path.join(tmp, 'no-marker')
    os.makedirs(no_marker, exist_ok=True)
    base_env = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=ROOT)

    probe = ("import bors_config, json, sys;"
             "print(json.dumps({'work':bors_config.WORK_DIR,"
             "'db':bors_config.DB_PATH,'user':bors_config.USER_DB_PATH}))")
    env_iso = dict(base_env, BORS_TEST_ISOLATION='1', BORS_DATA_DIR=iso,
                   BORS_OPERATIONAL_ROOT=ROOT,
                   BORS_USER_DB=os.path.join(iso, 'user.db'),
                   BORS_INTENT_DB=os.path.join(iso, 'intents.db'))
    got = child(probe, env_iso)
    try:
        import json
        row = json.loads(got.stdout.strip().splitlines()[-1])
    except Exception:
        row = {}
    ck(got.returncode == 0
       and os.path.realpath(str(row.get('work', ''))) == os.path.realpath(iso)
       and os.path.realpath(str(row.get('db', ''))) ==
       os.path.realpath(os.path.join(iso, 'market.db'))
       and os.path.realpath(str(row.get('user', ''))) ==
       os.path.realpath(os.path.join(iso, 'user.db')),
       "همهٔ مسیرهایِ DB زیرِ BORS_DATA_DIR ایزوله resolve می‌شوند",
       {"rc": got.returncode, "out": got.stdout[-300:], "err": got.stderr[-300:]})

    got = child(probe, dict(base_env, BORS_TEST_ISOLATION='1',
                            BORS_DATA_DIR=ROOT, BORS_OPERATIONAL_ROOT=ROOT))
    ck(got.returncode != 0
       and ('marker' in (got.stderr or '') or 'operational worktree' in (got.stderr or '')),
       "مسیرِ عملیاتیِ worktree رد می‌شود",
       {"rc": got.returncode, "err": got.stderr[-300:]})
    fake_op = os.path.join(tmp, 'fake-operational')
    os.makedirs(fake_op, exist_ok=True)
    open(os.path.join(fake_op, '.bors_test_isolation'), 'w').write('fake\n')
    got = child(probe, dict(base_env, BORS_TEST_ISOLATION='1',
                            BORS_DATA_DIR=fake_op, BORS_OPERATIONAL_ROOT=fake_op))
    ck(got.returncode != 0 and 'operational worktree' in (got.stderr or ''),
       "مسیرِ عملیاتی حتی با marker هم رد می‌شود", got.stderr[-240:])

    got = child(probe, dict(base_env, BORS_TEST_ISOLATION='1', BORS_DATA_DIR=no_marker))
    ck(got.returncode != 0 and 'isolation marker' in (got.stderr or ''),
       "مسیرِ بدونِ marker رد می‌شود", got.stderr[-200:])

    got = child(probe, env_iso)
    try:
        import json
        row2 = json.loads(got.stdout.strip().splitlines()[-1])
    except Exception:
        row2 = {}
    ck(got.returncode == 0 and os.path.realpath(str(row2.get('db', ''))) ==
       os.path.realpath(os.path.join(iso, 'market.db')),
       "subprocess همان DB_PATHِ processِ والد را می‌بیند",
       got.stdout[-200:])

    # نوشتن در DB ایزوله؛ هشِ دیتابیسِ عملیاتیِ همین worktree نباید عوض شود.
    market = os.path.join(ROOT, 'market.db')
    before = sha(market) if os.path.isfile(market) else None
    if before:
        src = sqlite3.connect('file:%s?mode=ro' % market.replace(chr(92), '/'),
                              uri=True, timeout=30)
        dst = sqlite3.connect(os.path.join(iso, 'market.db'))
        src.backup(dst)
        dst.commit(); dst.close(); src.close()
        write = ("import bors_config, sqlite3, json;"
                 "c=sqlite3.connect(bors_config.DB_PATH);"
                 "c.execute('CREATE TABLE IF NOT EXISTS _isolation_probe(x)');"
                 "c.commit(); c.close(); print(bors_config.DB_PATH)")
        got = child(write, env_iso)
        after = sha(market)
        ck(got.returncode == 0 and before == after,
           "نوشتن در clone، هشِ market.db عملیاتی را تغییر نمی‌دهد",
           {"rc": got.returncode, "before": before[:16] if before else None,
            "after": after[:16] if after else None, "err": got.stderr[-160:]})
    else:
        ck(False, "market.db برایِ تستِ نوشتن موجود است", market)

    shutil.rmtree(tmp, ignore_errors=True)
    print("\n%d checks, %d failed" % (PASS + FAIL, FAIL))
    print("DB ISOLATION " + ("OK" if FAIL == 0 else "FAILED"))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
