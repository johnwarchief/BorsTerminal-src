# -*- coding: utf-8 -*-
"""dev/mstat_value_source_semantics_v1.py — provenanceِ ارزشِ کلاینت.

«محاسبه‌شده» با «بومی» یکی نیست و ترکیبِ چند ردیف نباید native جا زده شود.
خالص/بی‌DB؛ فقط تابعِ تصمیمِ سطحِ تجمیع را می‌سنجد.
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import mstat_engine as E  # noqa: E402

CHECKS = []
FAILS = []


def ck(label, cond, detail=""):
    CHECKS.append(bool(cond))
    print(("  ok   " if cond else "  FAIL ") + label +
          (("  <- " + str(detail)) if not cond and detail else ""))
    if not cond:
        FAILS.append(label)


def main():
    ck("no client rows -> None", E._value_source_of(set()) is None)
    ck("all native -> native", E._value_source_of({"native"}) == "native")
    ck("native + reconstructed -> mixed",
       E._value_source_of({"native", "reconstructed"}) == "mixed")
    ck("mixed alone -> mixed", E._value_source_of({"mixed"}) == "mixed")
    ck("native + mixed -> mixed", E._value_source_of({"native", "mixed"}) == "mixed")
    ck("all reconstructed -> reconstructed",
       E._value_source_of({"reconstructed"}) == "reconstructed")
    ck("no hidden native fallback for empty",
       E._value_source_of(set()) != "native")
    print("\n%d/%d passed" % (len(CHECKS) - len(FAILS), len(CHECKS)))
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
