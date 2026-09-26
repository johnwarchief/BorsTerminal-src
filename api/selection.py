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

try:
    import mstat_engine as _mstat
except Exception:      # بانک/موتور در مسیر بسته غایب باشد → روت‌ها ۵۰۰ نمی‌شوند
    _mstat = None


router = APIRouter()


def _asset_classes(symbols):
    """(طبقه، زیرگونهٔ صندوق) برای هر نماد، از همان classifyِ تابلو.

    #106: جملهٔ «۷۰٪ صندوق طلا — هدف ۴۵٪» باید از همان طبقه‌بندیِ جدولِ بازار
    بیاید؛ نگاشتِ دوبارهٔ «طلا/نقره/درآمد ثابت» در فرانت یعنی دومینِ پیاده‌سازیِ
    همان قانون، و اختلافِ دو پیاده‌سازی دقیقاً همان چیزی است که در فیلترهای
    تابلوخوانی عددِ غلط ساخت. نمادِ بی‌سطر ⇒ None (حدس نمی‌زنیم).
    """
    want = {s for s in (symbols or []) if s}
    if not want or _mstat is None:
        return {}
    try:
        conn = get_db()
    except Exception:
        return {}
    try:
        ph = ",".join("?" * len(want))
        out = {}
        for sym, name, sector, ptype in conn.execute(
            f"SELECT l_val18, l_val30, sector_name, paper_type FROM instruments"
            f" WHERE l_val18 IN ({ph})", tuple(want)):
            cls, kind = _mstat.classify(ptype, name or "", sym or "", sector or "")
            out[sym] = {"cls": cls, "kind": kind, "sector_name": sector or ""}
        return out
    except Exception:
        return {}
    finally:
        conn.close()


@router.get("/api/selection/symbols")
def get_selection_symbols(q: str = "", limit: int = 40):
    """جستجوی نماد برای «افزودن دارایی به سبد» — نماد + نام + صنعت + قیمت + طبقه.

    فقط سهام و صندوق؛ اختیار/اوراق/حق‌تقدم قابل نگهداری در سبدِ هدف نیستند، پس
    در فهرست نمی‌آیند (نه این‌که ته‌ی لیست بیفتند). قیمت = p_last و در نبودش
    p_closing؛ هیچ‌کدام نبود ⇒ null، و فرانت «قیمت را خودتان وارد کنید» می‌گوید.
    """
    term = (q or "").strip()
    if not term or _mstat is None:
        return {"status": "success", "count": 0, "data": []}
    n_term = _mstat._norm(term)
    cap = max(1, min(int(limit or 40), 100))
    try:
        conn = get_db()
    except Exception as e:
        return {"status": "error", "message": str(e)[:200], "data": []}
    rows = []
    try:
        # فیلترِ سمتِ SQL با norm_fa (همان تابعِ نوشتارِ یکسانِ جدولِ بازار):
        # بی‌فیلتر، هر کلیدواژه کلِ instruments را ورق می‌زد.
        for sym, name, sector, ptype, p_last, p_close in conn.execute(
            """SELECT i.l_val18, i.l_val30, i.sector_name, i.paper_type,
                      m.p_last, m.p_closing
                 FROM instruments i
                 LEFT JOIN market_watch m
                        ON m.ins_code = i.ins_code
                       AND m.d_even = (SELECT MAX(d_even) FROM market_watch)
                WHERE i.l_val18 IS NOT NULL AND i.l_val18 <> ''
                  AND (instr(norm_fa(i.l_val18), ?) > 0 OR instr(norm_fa(i.l_val30), ?) > 0)
                ORDER BY length(norm_fa(i.l_val18)), i.l_val18
                LIMIT ?""", (n_term, n_term, cap * 4)):
            cls, kind = _mstat.classify(ptype, name or "", sym or "", sector or "")
            # اختیار/اوراق/حق‌تقدم داراییِ قابل‌نگهداری در سبدِ هدف نیستند؛
            # نبودِ طبقه هم «سهام» فرض نمی‌شود — فقط دو طبقهٔ شناخته‌شده می‌آیند.
            if cls not in (_mstat.PAPER_STOCK, _mstat.PAPER_FUND):
                continue
            px = _pos(p_last) or _pos(p_close)
            rows.append({"symbol": sym, "name": (name or "").strip(),
                         "sector_name": sector or "", "cls": cls, "kind": kind,
                         "price": px})
            if len(rows) >= cap:
                break
    except Exception as e:
        return {"status": "error", "message": str(e)[:200], "data": []}
    finally:
        conn.close()
    return {"status": "success", "count": len(rows), "query": term, "data": rows}



# فیلدهایی که در POSTِ جزئی (فقط وضعیت/یادداشت) باید از رکوردِ موجود حفظ شوند.
# weight_pct این‌جا نیست: فراخواننده‌ها آن را صریح می‌فرستند و ۰ یعنی «وزنِ دستی
# نمی‌خواهم» — وگرنه لغوِ وزنِ دستی هرگز ذخیره نمی‌شد.
_KEEP_IF_ABSENT = ("name", "asset_kind", "price", "qty", "score", "pricing_mode", "sector")


def _sel_to_dict(r) -> dict:
    d = {k: r[k] for k in r.keys()}
    d["asset_kind"] = d.get("asset_kind") or ASSET_KIND_BY_MODE.get(
        (d.get("pricing_mode") or "").strip().lower(), "")
    return d


def _pos(v):
    """عددِ مثبتِ معتبر؛ غیرعدد/صفر/منفی ⇒ None (نه صفرِ قابل‌محاسبه)."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if f > 0 else None


def _weights(accepted):
    """وزنِ هر ردیف + منشأش.

    اولویت با «قیمت × تعداد» است (#106 PORT-1): وزنِ ریالی واقعی، نه حدسِ
    کاربر. اما این مسیر فقط وقتی معتبر است که *همهٔ* ردیف‌ها ارزش داشته باشند؛
    جمعِ بخشی از ردیف‌ها مخرجِ کوچکی می‌سازد و وزنِ بقیه را بزرگ‌نمایی می‌کند —
    پس با یک ردیفِ بی‌تعداد، کل سبد به وزنِ دستی/مساوی برمی‌گردد و
    value_missing_count همان را به UI می‌گوید. هیچ‌وقت ارزشِ غایب صفر
    حساب نمی‌شود.
    """
    for d in accepted:
        p, q = _pos(d.get("price")), _pos(d.get("qty"))
        d["value_toman"] = round(p * q) if (p and q) else None

    priced = [d for d in accepted if d["value_toman"]]
    total_value = sum(d["value_toman"] for d in priced) if accepted else 0
    value_ok = bool(accepted) and len(priced) == len(accepted)
    eq = round(100.0 / len(accepted), 1) if accepted else 0.0

    for d in accepted:
        if value_ok:
            d["weight_eff_pct"] = round(d["value_toman"] / total_value * 100, 1)
            d["weight_source"] = "value"
        else:
            w = _pos(d.get("weight_pct"))
            d["weight_eff_pct"] = round(w, 1) if w else eq
            d["weight_source"] = "manual" if w else "equal"
        d["weight_manual"] = d["weight_source"] == "manual"
        d["over_cap"] = d["weight_eff_pct"] > PORTFOLIO_WEIGHT_CAP_PCT

    return {
        "eq": eq,
        "total_value": total_value if value_ok else None,
        "value_missing_count": len(accepted) - len(priced),
        "weight_source": "value" if value_ok else (
            "manual" if any(d["weight_source"] == "manual" for d in accepted) else "equal"),
    }

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
    # طبقهٔ دارایی از همان classifyِ جدولِ بازار (نه یک نگاشتِ دوباره در فرانت).
    classes = _asset_classes([d.get("symbol") for d in decisions])
    for d in decisions:
        d["asset_class"] = classes.get(d.get("symbol") or "")
    # وزن: ارزشِ ردیف (قیمت × تعداد) اگر برای همه معلوم باشد، وگرنه وزنِ دستیِ
    # کاربر و در نهایت پیشنهادِ وزنِ مساوی. (توضیح کامل در _weights.)
    wmeta = _weights(accepted)
    eq, sum_w = wmeta["eq"], round(sum(d["weight_eff_pct"] for d in accepted), 1)
    kinds = {"dollar": 0, "rial": 0, "mixed": 0}
    for d in accepted:
        k = d.get("asset_kind") or ""
        kinds[k if k in ("dollar", "rial") else "mixed"] += 1

    # ترکیب فعلی به تفکیکِ طبقه — همان جملهٔ «طلا و سکه ۷۰٪ از سبد».
    # فقط ردیفی که وزن *و* طبقه دارد جمع بسته می‌شود؛ class_missing_count می‌گوید
    # چند ردیف خارج از این جمع‌اند تا ترکیبِ ناقص، ترکیبِ کامل خوانده نشود.
    mix, missing = {}, 0
    for d in accepted:
        ac = d.get("asset_class")
        if not ac:
            missing += 1
            continue
        key = ac["kind"] if ac["cls"] == _mstat.PAPER_FUND else ac["cls"]
        mix[key] = round(mix.get(key, 0.0) + d["weight_eff_pct"], 1)

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
            "weight_source": wmeta["weight_source"],
            "portfolio_value_toman": wmeta["total_value"],
            "value_missing_count": wmeta["value_missing_count"],
            "class_mix_pct": mix, "class_missing_count": missing,
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
        # #106: «تعداد» با «قیمت» ضرب می‌شود تا وزن از خودِ سبد بیاید. ۰ یعنی
        # «ثبت نشده» (نه «صفر سهم»)؛ در ادامه اگر کلید نیامده باشد حفظ می‌شود.
        "qty": _num("qty", float),
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
                # Patch-semantics برایِ فیلدهایِ هویتی/ریالی: فراخواننده‌ای که
                # فقط وضعیت یا یادداشت می‌فرستد (دیالوگ فشردهٔ جدول، «ثبت پله»ٔ
                # تب ایجنت ارشد) نباید قیمت/تعداد/نامِ ثبت‌شده را صفر کند.
                # صفرِ *صریح* همچنان پاک‌کردن حساب می‌شود. تک‌کوئری روی کلیدِ اصلی.
                cur = conn.execute(
                    f"SELECT * FROM selection_decisions WHERE {_pred}", _params).fetchone()
                if cur:
                    prev = dict(cur)
                    for k in _KEEP_IF_ABSENT:
                        if k not in payload or payload.get(k) in (None, ""):
                            if prev.get(k) is not None:
                                rec[k] = prev[k]
                conn.execute("""
                    INSERT INTO selection_decisions
                        (symbol, name, status, reason, note, stop_loss, asset_kind,
                         weight_pct, price, qty, score, pricing_mode, sector, updated_at)
                    VALUES (:symbol, :name, :status, :reason, :note, :stop_loss, :asset_kind,
                            :weight_pct, :price, :qty, :score, :pricing_mode, :sector, :updated_at)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name=excluded.name, status=excluded.status, reason=excluded.reason,
                        note=excluded.note, stop_loss=excluded.stop_loss,
                        asset_kind=excluded.asset_kind, weight_pct=excluded.weight_pct,
                        price=excluded.price, qty=excluded.qty, score=excluded.score,
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
