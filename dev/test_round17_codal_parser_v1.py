#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Round 17: general CODAL composition parser.

Covers the formats that matter:
  * amount after the label + million-rial unit (Farak/كلر)
  * amount before the label (older structured letters)
  * narrative stage paid-cash (وپاسار)
  * a missing component that does not sum to the total stays UNPARSED,
    never a silent zero.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
os.chdir(ROOT)

import codal_share_type as C  # noqa: E402

P = F = 0


def ck(cond, msg, detail=""):
    global P, F
    if cond:
        P += 1
        print("  ok   %s" % msg)
    else:
        F += 1
        print("  FAIL %s%s" % (msg, ("   ← %s" % (detail,)) if detail else ""))


# Real Farak registration letter (public CODAL body).
farak = C.clean(open(os.path.join(ROOT, "dev", "fixtures",
                                  "codal_farak_2021-03-31.html"),
                     encoding="utf-8").read())
c = C.composition(farak)
ck(C.classify(c) == "RESERVE_ONLY",
   "Farak: revaluation-only capital increase", c)
ck(c["capital_increase"] == 8064632 and c["revaluation"] == 8064632,
   "Farak: total increase and revaluation amounts", c)
ck(c["paid_cash"] == 0 and "paid_cash" in c.get("derived", []),
   "Farak: blank paid cash is derived from the exact total, not assumed", c)
ck(c.get("complete") is True and c.get("unit") == "million_rial",
   "Farak: composition complete with the document unit", c)

# Modern after-label format (كلر-style synthetic excerpt).
modern = ("افزایش سرمایۀ شرکت از مبلغ 655,000 میلیون ریال بهمبلغ 7,364,331 "
          "میلیون ریال ( از محل سود انباشته مبلغ 1195000 میلیون ریال ، "
          "از محل مازاد تجدید ارزیابی دارایی ها مبلغ 5514331 میلیون ریال "
          "و از آورده نقدی با سلب حق تقدم از سهامداران فعلی مبلغ میلیون ریال )")
c = C.composition(modern)
ck(C.classify(c) == "RESERVE_ONLY" and c["retained"] == 1195000
   and c["revaluation"] == 5514331 and c["paid_cash"] == 0,
   "modern after-label composition is parsed, not shifted", c)

# Older before-label format.
old = ("مبلغ افزایش سرمایه 1000 ریال از محل آورده نقدی سهامداران 1000 ریال")
c = C.composition(old)
ck(c["paid_cash"] == 1000 and C.classify(c) == "PAID_IN",
   "older before-label paid cash still parses", c)

# Narrative stage paid-cash (وپاسار-style synthetic excerpt).
stage = ("مرحله سوم افزایش سرمایه از مبلغ 272,969,000,000,000 ریال "
         "به مبلغ 322,969,000,000,000 ریال از محل آورده نقدی سهامداران")
c = C.composition(stage)
ck(c["paid_cash"] == 50000000000000 and C.classify(c) == "PAID_IN",
   "narrative stage paid cash is extracted and classified PAID_IN", c)

# Incomplete composition: the components do not sum to the total.
bad = ("افزایش سرمایۀ شرکت از مبلغ 100,000 میلیون ریال بهمبلغ 101,000 "
       "میلیون ریال ( از محل سود انباشته مبلغ 500 میلیون ریال و "
       "از آورده نقدی با سلب حق تقدم از سهامداران فعلی مبلغ میلیون ریال )")
c = C.composition(bad)
ck(c["paid_cash"] is None and c.get("complete") is False
   and C.classify(c) == "UNPARSED",
   "missing component that cannot be derived is not a silent zero", c)

print()
print("result: %d pass, %d fail" % (P, F))
print("%d/%d" % (P, P + F))
sys.exit(0 if F == 0 else 1)
