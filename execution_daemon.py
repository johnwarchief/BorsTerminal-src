# -*- coding: utf-8 -*-
"""execution_daemon.py — زمان‌بندِ محلیِ سرخطی، مستقل از UI و Qoder.

اجرایِ پیش‌فرض dry-run است: هیچ شبکه/مرورگری صدا زده نمی‌شود و هیچ سفارشی
فرستاده نمی‌شود. مسیر زنده تا تأیید قرارداد/نشست عمداً وصل نیست.

اجرا:
    python execution_daemon.py --once
    python execution_daemon.py --poll 0.5
    BorsTerminal_Ultimate.exe --schedule-daemon
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import bors_config
import execution_schedule as S
from execution_ledger import default_ledger


def build_runner(db_path: str | None = None, *, poll_s: float = 0.5,
                 max_lateness_s: float = 60.0):
    store = S.ScheduleStore(db_path or S.default_store_path(bors_config.WORK_DIR))
    calendar = S.LocalTradingCalendar(bors_config.DB_PATH)
    ledger = default_ledger()

    def _halted() -> tuple[bool, str]:
        return (True, ledger.kill_reason()) if ledger.halted() else (False, "")

    runner = S.ScheduleRunner(
        store, S.LocalFactsProvider(bors_config.DB_PATH, calendar),
        calendar=calendar, executor=S.DryRunExecutor(),
        halted=_halted,
        poll_s=poll_s, max_lateness_s=max_lateness_s,
        live_enabled=False, contract_verified=False)
    return store, runner


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="BorsTerminal schedule daemon (dry-run)")
    ap.add_argument("--db", default="")
    ap.add_argument("--poll", type=float, default=0.5)
    ap.add_argument("--max-lateness", type=float, default=60.0)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args(argv if argv is not None else sys.argv[1:])
    store, runner = build_runner(args.db or None, poll_s=args.poll,
                                 max_lateness_s=args.max_lateness)
    report = {"mode": "dry_run", "live_ready": False, "db": store.path,
              "readiness": S.readiness()}
    if args.once:
        report["recovered"] = runner.recover()
        report["tick"] = runner.tick()
        print(json.dumps(report, ensure_ascii=False))
        return 0
    report["recovered"] = runner.recover()
    runner.start()
    print(json.dumps({**report, "started": True}, ensure_ascii=False))
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        runner.stop()
        return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
