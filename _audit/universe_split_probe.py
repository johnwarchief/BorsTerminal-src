# -*- coding: utf-8 -*-
"""سنجشِ تفکیکِ «جامعۀ تابلو / جامعۀ غربالگری» رویِ دادهٔ واقعی.

موقت است (زیر _audit/); خروجیِ عددی برایِ گزارشِ مالک.
"""
import json
import time
from collections import Counter

import funnel_engine as FE


def main():
    from api.funnel import _board_rows, _screen_rows

    t0 = time.time()
    board = _board_rows()
    screen = _screen_rows()
    print(f"board rows={len(board)} screen rows={len(screen)} build={time.time()-t0:.1f}s")
    if not board:
        print("NO BOARD DATA")
        return 1

    t1 = time.time()
    payload = FE.evaluate(board, screen, preset="trend", fund_mode="standard")
    print(f"evaluate={time.time()-t1:.1f}s")
    u = payload["universe"]
    print("universe:", json.dumps(u, ensure_ascii=False))
    market = u["market"]
    screening = u["screening"]
    excluded = u["excluded"]
    print(f"X(market)={market}  Y(screening)={screening}  Z(excluded)={excluded}  X==Y+Z? {market == screening + excluded}")

    # نمونه‌هایِ علتِ خروج
    reasons = Counter(e["reason_code"] for e in payload["exclusions"])
    print("exclusion reasons:", dict(reasons))
    print("coverage:", json.dumps(payload["coverage"], ensure_ascii=False))
    for stage, cov in payload["coverage"].items():
        tot = sum(cov.values())
        inside = tot - cov.get("not_in_universe", 0)
        print(f"  {stage}: sum={tot} (market={market}) بدونِ خارج‌ها={inside} (screening={screening})"
              f" -> {'OK' if tot == market and inside == screening else 'MISMATCH'}")

    # نمادهایِ خارج از جامعه: چندتا از آنها «امروز معامله داشتند»؟ (ثبوتِ اینکه
    # live ≠ «معامله داشت»: اگر نمونه‌ای حجمِ امروز داشت و خارج بود، رأیِ مالک
    # درست اجرا شده.)
    withvol = [e for e in payload["exclusions"] if (e.get("last") or 0) > 0][:8]
    print("نمونۀ خارج‌ها:", json.dumps(withvol[:6], ensure_ascii=False))
    print("نمونۀ داخل‌ها:", json.dumps([
        {"symbol": r.get("symbol"), "st": r.get("st_title"), "code": r.get("st_code"),
         "live": r.get("is_live"), "stop": r.get("stop_state")}
        for r in _rows(board)[:3]], ensure_ascii=False))

    # وضعیتِ هر گام درِ matrix برایِ یک نمادِ خارج از جامعه
    if payload["exclusions"]:
        sym = payload["exclusions"][0]["symbol"]
        print(f"matrix[{sym}]:", json.dumps(payload["status_matrix"][sym], ensure_ascii=False))
    print("timeline excluded sample:", json.dumps(
        (payload["timeline"] or {}).get((payload["exclusions"] or [{}])[0].get("symbol", "")),
        ensure_ascii=False)[:400])
    return 0


def _rows(board):
    out = []
    for r in board:
        if r.get("st_title"):
            out.append(r)
        if len(out) >= 3:
            break
    return out


if __name__ == "__main__":
    raise SystemExit(main())
