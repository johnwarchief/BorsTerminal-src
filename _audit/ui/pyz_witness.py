"""Read-only witness: does the frozen PYZ actually contain the backend modules?

Run from repo root after scripts/build_all.py. Prints one line per module and
exits non-zero if any expected module is absent from build/fts_terminal/PYZ-00.toc.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TOC = os.path.join(ROOT, "build", "fts_terminal", "PYZ-00.toc")

EXPECTED = [
    "app", "bors_config", "bors_flags",
    "api", "api.bot", "api.execution", "api.update", "api.market", "api.chart",
    "api._sync_market", "execution_easytrader", "execution_service",
    "execution_contract", "execution_mock", "execution_ledger", "execution_timing",
    "bot_signals", "paper_trading",
    "fts_engine", "funnel_engine", "funnel_registry", "funnel_tech_scan",
    "market_state", "market_phase", "market_universe", "mstat_engine",
    "codal_engine", "codal_fetcher", "codal_pipeline", "codal_periods", "codal_units",
    "candle_contract", "confidence_engine", "backtest_engine", "price_basis",
    "client_split", "notifications", "notifier",
]


def main():
    if not os.path.exists(TOC):
        print("NO TOC at", TOC)
        return 2
    src = open(TOC, encoding="utf-8", errors="replace").read()
    missing = []
    for m in EXPECTED:
        hit = ("'%s'" % m) in src or ('"%s"' % m) in src
        print(("OK   " if hit else "MISS ") + m)
        if not hit:
            missing.append(m)
    print("---")
    print("checked=%d missing=%d" % (len(EXPECTED), len(missing)))
    if missing:
        print("MISSING: " + ", ".join(missing))
        return 1
    # bors_entry scripted-است: درِ onedir داخل CArchive است نه PYZ، پس جدا سنجیده می‌شود.
    exe = os.path.join(ROOT, "dist", "BorsTerminal_Ultimate", "BorsTerminal_Ultimate.exe")
    if not os.path.exists(exe):
        print("NO EXE at", exe)
        return 1
    from PyInstaller.archive.readers import CArchiveReader
    entries = set(CArchiveReader(exe).toc)
    print(("OK   " if "bors_entry" in entries else "MISS ") + "bors_entry (CArchive entry script)")
    if "bors_entry" not in entries:
        return 1
    print("PYZ MODULE WITNESS OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
