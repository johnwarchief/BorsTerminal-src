#!/usr/bin/env python3
"""One normalization rule for symbol identity across ledgers and events."""
from __future__ import annotations

KEY_TABLE = str.maketrans({"\u064a": "\u06cc", "\u0643": "\u06a9", "\u0649": "\u06cc"})
KEY_SEPS = (" ", "\u00a0", "\u200c", "\u200f", "\u200e", "\u202f")


def key(text) -> str:
    s = "" if text is None else str(text)
    for sep in KEY_SEPS:
        s = s.replace(sep, "")
    return s.translate(KEY_TABLE).lower()


def load_instruments(con) -> dict:
    out = {}
    for r in con.execute(
            "SELECT ins_code,l_val18,l_val30,paper_type,isin,updated_at "
            "FROM instruments ORDER BY ins_code"):
        raw = r[1]
        if not raw or not str(raw).strip():
            continue
        k = key(raw)
        # 1 = preferred; the tuple is compared with ">", so the best row wins.
        cand = (1 if r[4] else 0, 1 if r[3] in (1, 2, 8) else 0,
                str(r[5] or ""), str(r[0]))
        cur = out.get(k)
        curk = (1 if cur and cur["isin"] else 0,
                1 if cur and cur["paper_type"] in (1, 2, 8) else 0,
                str(cur["updated_at"] or "") if cur else "",
                cur["ins_code"] if cur else "")
        if cur is None or cand > curk:
            out[k] = {"symbol": str(raw).strip(), "ins_code": str(r[0]),
                      "name": r[2], "paper_type": r[3], "isin": r[4],
                      "updated_at": r[5]}
    return out
