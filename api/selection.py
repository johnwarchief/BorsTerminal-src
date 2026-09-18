"""Portfolio decision store (accept / reject / monitor / pending).

Split verbatim out of app.py (v9.8.1 modularisation).
Every statement is byte-for-byte identical to app.py; only the route
decorators changed from @app.<verb> to @router.<verb>.
Audit map of source line spans: MIGRATED_LINES.txt
"""
from ._core import get_db, get_user_db, sym_pred
from .watchlist import ASSET_KIND_BY_MODE, PORTFOLIO_MAX, PORTFOLIO_MIN, PORTFOLIO_WEIGHT_CAP_PCT, SELECTION_STATUSES
from fastapi import APIRouter
import datetime


router = APIRouter()


def _sel_to_dict(r) -> dict:
    d = {k: r[k] for k in r.keys()}
    d["asset_kind"] = d.get("asset_kind") or ASSET_KIND_BY_MODE.get(
        (d.get("pricing_mode") or "").strip().lower(), "")
    return d

@router.get("/api/selection/portfolio")
def get_selection_portfolio():
    """تصمیمات سبد: سبد نهایی (accept) + رادار زیر نظر (monitor) + شمارش وضعیتها."""
    try:
        conn = get_user_db()
        try:
            rows = conn.execute(
                "SELECT * FROM selection_decisions ORDER BY updated_at DESC").fetchall()
        finally:
            conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

    decisions = [_sel_to_dict(r) for r in rows]
    counts = {"accept": 0, "reject": 0, "monitor": 0, "pending": 0}
    for d in decisions:
        if d.get("status") in counts:
            counts[d.get("status")] += 1

    accepted = [d for d in decisions if d.get("status") == "accept"]
    # وزن: اگر کاربر وزن دستی ثبت کرده همان، وگرنه پیشنهاد وزن مساوی سبد.
    eq = round(100.0 / len(accepted), 1) if accepted else 0.0
    for d in accepted:
        w = float(d.get("weight_pct") or 0)
        d["weight_eff_pct"] = round(w if w > 0 else eq, 1)
        d["weight_manual"] = bool(w > 0)
        d["over_cap"] = d["weight_eff_pct"] > PORTFOLIO_WEIGHT_CAP_PCT
    sum_w = round(sum(d["weight_eff_pct"] for d in accepted), 1)
    kinds = {"dollar": 0, "rial": 0, "mixed": 0}
    for d in accepted:
        k = d.get("asset_kind") or ""
        kinds[k if k in ("dollar", "rial") else "mixed"] += 1

    return {
        "status": "success",
        "decisions": decisions,
        "portfolio": accepted,
        "monitor": [d for d in decisions if d.get("status") == "monitor"],
        "counts": counts,
        "limits": {
            "min": PORTFOLIO_MIN, "max": PORTFOLIO_MAX,
            "weight_cap_pct": PORTFOLIO_WEIGHT_CAP_PCT,
            "equal_weight_pct": eq, "sum_weight_pct": sum_w,
        },
        "kind_mix": kinds,
    }

@router.post("/api/selection/decision")
def post_selection_decision(payload: dict = None):
    """ثبت/بروزرسانی تصمیم روی یک نماد (upsert با کلید نماد).

    وضعیت `pending` یعنی «انصراف از تصمیم» → رکورد حذف میشود تا بج جدول
    به حالت «بررسی‌نشده» برگردد (به‌جای نگه‌داشتن ردیف بی‌اثر).
    """
    if not payload:
        return {"status": "error", "message": "بدون داده"}
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return {"status": "error", "message": "نماد ارسال نشده"}
    status = str(payload.get("status") or "").strip().lower()
    if status not in SELECTION_STATUSES:
        return {"status": "error", "message": "وضعیت نامعتبر: " + status}

    def _num(key, cast, default=0):
        v = payload.get(key)
        if v in (None, ""):
            return cast(default)
        try:
            return cast(float(v))
        except (TypeError, ValueError):
            return cast(default)

    rec = {
        "symbol": symbol,
        "name": str(payload.get("name") or "")[:120],
        "status": status,
        "reason": str(payload.get("reason") or "")[:200],
        "note": str(payload.get("note") or "")[:500],
        "stop_loss": str(payload.get("stop_loss") or "")[:120],
        "asset_kind": str(payload.get("asset_kind") or "")[:10],
        "weight_pct": _num("weight_pct", float),
        "price": _num("price", float),
        "score": _num("score", int),
        "pricing_mode": str(payload.get("pricing_mode") or "")[:20],
        "sector": str(payload.get("sector") or "")[:80],
        "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    try:
        conn = get_user_db()
        try:
            _pred, _params = sym_pred("symbol", symbol)
            if status == "pending":
                conn.execute(f"DELETE FROM selection_decisions WHERE {_pred}", _params)
            else:
                conn.execute("""
                    INSERT INTO selection_decisions
                        (symbol, name, status, reason, note, stop_loss, asset_kind,
                         weight_pct, price, score, pricing_mode, sector, updated_at)
                    VALUES (:symbol, :name, :status, :reason, :note, :stop_loss, :asset_kind,
                            :weight_pct, :price, :score, :pricing_mode, :sector, :updated_at)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name=excluded.name, status=excluded.status, reason=excluded.reason,
                        note=excluded.note, stop_loss=excluded.stop_loss,
                        asset_kind=excluded.asset_kind, weight_pct=excluded.weight_pct,
                        price=excluded.price, score=excluded.score,
                        pricing_mode=excluded.pricing_mode, sector=excluded.sector,
                        updated_at=excluded.updated_at
                """, rec)
            conn.commit()
            row = conn.execute(f"SELECT * FROM selection_decisions WHERE {_pred} ORDER BY updated_at DESC LIMIT 1",
                               _params).fetchone()
        finally:
            conn.close()
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}

    return {"status": "success",
            "decision": (_sel_to_dict(row) if row else None),
            "symbol": symbol, "saved_status": status}

@router.delete("/api/selection/decision/{symbol}")
def delete_selection_decision(symbol: str):
    """پاک کردن تصمیم یک نماد (بازگشت به «بررسی‌نشده»)."""
    try:
        conn = get_user_db()
        try:
            _pred, _params = sym_pred("symbol", symbol)
            cur = conn.execute(f"DELETE FROM selection_decisions WHERE {_pred}", _params)
            conn.commit()
            n = cur.rowcount
        finally:
            conn.close()
        return {"status": "success", "deleted": n}
    except Exception as e:
        return {"status": "error", "message": str(e)[:200]}
