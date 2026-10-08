# -*- coding: utf-8 -*-
"""funnel_engine.py — داورِ canonicalِ قیف FTS (بک‌اند، تنها نسخه).

چرا این فایل هست: تا پیش از این «حکمِ نهاییِ قیف» درِ مرورگر ساخته می‌شد
(`frontend/src/features/master/lib/ftsFunnel.ts` → `buildFunnel`) و بک‌اند فقط
پرچم و پنج شاخص خام می‌داد. رأیِ مالک (۱۴۰-۰۷-۱۶): یک داورِ canonical درِ
بک‌اند؛ فرانت فقط نمایشِ همان حکم.

قراردادِ این ماژول (هیچ‌کدام مذاکره‌پذیر نیست):

  ۱) ورودیِ خام = ردیف‌هایِ تابلو (با پرچم‌هایِ `tape_flags`) + ردیف‌هایِ
     اسکرینر (با i1..i5 و `tech_*`). هیچ فرمولِ فیلتر یا آستانه‌ای اینجا
     دوباره نوشته نمی‌شود — فقط *خواندن* ستونی که موتورِ دیگر ساخته.
  ۲) زنجیره **اشتراکِ ترتیبی** است، نه OR:
        U ∩ F1  F2 ∩ F3   و هر F رویِ بازماندۀ قبلی.
     ترتیبِ کاربر درِ شمارشِ هر مرحله («ورودی → ماندگار → حذف‌شده») و درِ
     traceِ هر نماد ثبت می‌شود، حتی اگر مجموعۀ نهایی تصادفاً یکی شود.
  ۳) تکنیکال: اول هفتگی. نزولی ⇒ رد، خنثی ⇒ رد، صعودی ⇒ آنگاه روزانه.
     «سنجیده نشد» رد نیست (PENDING). ستاپ‌ها (جت/فیب/CHoCH/کف دوقلو) شاهداند
     و هیچ‌وقت وتوی هفتگی را نمی‌شکنند — رأیِ صریحِ مالک.
  ۴) بنیادی سه حالت: hard (هر پنج) / standard (I1∧I2I3 بلاکر، I4/I5 شاهد)
     / exception. بی‌داده هیچ‌وقت pass نمی‌شود. I4/I5 شکستِ بلاکر را جبران
     نمی‌کنند.
  ۵) استثنا فقط صریح و ثبت‌شده است، و هرگز canonical را بازنویسی نمی‌کند:
        canonical = REJECT   و   effective = PASS WITH EXCEPTION
     با برچسبِ «استثنای بنیادی: I2» + زمانِ اعمال درِ trace.
  ۶) تحویل: بازمانده‌ها، رتبه‌بندیِ شفاف با داده‌هایِ موجود — هیچ وزنِ ساختگی
     و هیچ scoreِ اختراعی نیست: (حکمِ نهایی → بی‌استثنا → امتیازِ بنیادیِ موجود
     → امتیازِ تکنیکالِ موجود → رتبۀ رسمیِ بک‌اند → نماد).
  ۷) سقفِ پنهان ممنوع: هیچ slice/LIMIT درِ این فایل نیست. هرچه ورودی باشد
     همان پردازش می‌شود؛ کم‌کردنِ جامععه وظیفۀ فراخوان نیست.

خروجی `evaluate()` یک دیکشنریِ JSON-پذیر است که عیناً درِ `/api/funnel` می‌نشیند
و فرانت بدونِ هیچ داوریِ تازه‌ای نمایشش می‌دهد.
"""
from __future__ import annotations

import time
from typing import Any, Iterable

import funnel_registry as REG

ENGINE_VERSION = "1"

# وضعیت‌هایِ چهارحالته — همان معنا درِ کلِ قیف (UNAVAILABLE ≠ REJECT).
PASS, REJECT, PENDING, UNAVAILABLE = "pass", "reject", "pending", "unavailable"
# پنجمین وضعیتِ رسمی: مرحلۀ بعدی اجرا نشده چون مرحلۀ قبل نماد را رد کرده.
# این «سنجیده نشد» نیس — یک حکمِ قطعیِ زنجیره‌ای است و درِ trace هم همین‌طور
# نوشته می‌شود (رأیِ مالک: «هیچ نمادی نباید با وضعیت سنجیده نشده خارج شود»).
NOT_REQUIRED = "not_required"
STATUSES = (PASS, REJECT, PENDING, UNAVAILABLE, NOT_REQUIRED)

# ستونِ پرچمِ هر فیلتر درِ ردیفِ تابلو — نام‌ها از رجیستری می‌آیند، نه از
# یک فهرستِ دستیِ دیگر.
FLAG_OF = {f.filter_id: f.filter_id for f in REG.FILTERS}


def _why_of(row: dict) -> list[dict]:
    """دفترچۀ ردیف‌محورِ دلیل‌ها (همان ردیفِ ورودی، کلیدِ زیرخطی)."""
    key = "_funnel_why"
    if key not in row:
        row[key] = []
    return row[key]  # type: ignore[no-any-return]


def _tri(v: Any) -> bool | None:
    """سه‌حالۀ صادقانه: 1/0/«نبود» ⇒ True/False/None (هیچ‌چیز pass نیست)."""
    if v is None or v == "" or v == "—":
        return None
    if isinstance(v, str):
        s = v.strip().lower()
        if s in ("1", "true", "yes", "آری", "✓"):
            return True
        if s in ("0", "false", "no", "خیر", "✗"):
            return False
        return None
    return bool(v)


def _num(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f


# ── ۱) تابلوخوانی: اشتراکِ ترتیبیِ زنجیره ─────────────────────────────────
def tape_stage(rows: list[dict], chain: tuple[str, ...],
               params: dict[str, dict[str, Any]] | None = None) -> dict:
    """U ∩ F1  F2 … با شمارۀ واقعیِ هر مرحله رویِ بازماندۀ مرحلۀ قبل."""
    params = params or {}
    survivors = list(rows)
    steps: list[dict] = []
    dropped: dict[str, list[str]] = {}
    for fid in chain:
        f = REG.BY_ID.get(fid)
        if f is None:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
        flag = FLAG_OF[fid]
        before = len(survivors)
        matched: list[dict] = []
        removed: list[str] = []
        unmeasured: list[str] = []
        for r in survivors:
            sym = str(r.get("symbol") or "")
            v = _tri(r.get(flag))
            if v is False:
                removed.append(sym)
            else:
                # True ماند؛ None هم حذف نمی‌شود ولی «سنجیده نشد» برچسب
                # می‌گیرد — قانونِ مالک: UNAVAILABLE ≠ REJECT.
                matched.append(r)
                if v is None:
                    unmeasured.append(sym)
        dropped[fid] = removed
        for r in survivors:
            if _tri(r.get(flag)) is False:
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": REJECT, "reason_code": f"TAPE_{fid.upper()}_NO_MATCH",
                                   "human_reason": f"{f.name} — نشانه در این نماد نیست",
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
            elif _tri(r.get(flag)) is None:
                _why_of(r).append({"stage": "tape", "seq": len(steps) + 1, "filter_id": fid,
                                   "status": UNAVAILABLE, "reason_code": f"TAPE_{fid.upper()}_UNMEASURED",
                                   "human_reason": f"{f.name} — پرچم این نماد ساخته نشده",
                                   "input_count": before, "output_count": len(matched),
                                   "source": f.source_file, "formula_version": f.formula_version})
        steps.append({
            "stage": "tape",
            "seq": len(steps) + 1,
            "filter_id": fid,
            "label": f.name,
            "input_count": before,
            "matched_count": len(matched),
            "removed_count": before - len(matched),
            "unmeasured_count": len(unmeasured),
            "parameter_set": params.get(fid) or {p.param_id: p.value for p in f.params if p.value is not None},
            "source_ref": f"{f.source_file}#{f.source_sha256}",
            "formula_version": f.formula_version,
            "backend_impl": f.backend_impl,
            # سه‌حالته و افتراقی: چیزی حذف شده (reject)، هیچ‌چیز حذف نشده ولی
            # بعضی پرچم‌ها ساخته نشده‌اند (pending)، یا همه‌چیز سنجیده و خورده شده.
            "status": REJECT if removed else (PENDING if unmeasured else PASS),
        })
        survivors = matched
    return {"survivors": survivors, "steps": steps, "dropped": dropped}


# ── ۲) تکنیکال: هفتگی اول، بعد روزانه ─────────────────────────────────────
BRANCH_OF = {
    "up": "جت / پولبک",
    "down": "فیبوناچی / CHoCH",
    "range": "کف دوقلو / آخرین ساختار حمایت-مقاومت",
}


def technical_stage(rows: list[dict]) -> dict:
    """گیتِ روند — داور همان `trend.matrix` بک‌اند است، نه محاسبۀ دوباره."""
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        w = (r.get("tech_trend_w") or "").strip() or None
        d = (r.get("tech_trend_d") or "").strip() or None
        mat = (r.get("tech_matrix_decision") or "").strip() or None
        why: list[dict[str, str]] = []
        if not (w or d or mat):
            status = UNAVAILABLE
            why.append({"code": "TECH_UNMEASURED", "text": "تکنیکال این نماد سنجیده نشده"})
        elif mat == "UNKNOWN":
            # کمتر از دو پیوتِ کاملِ هفتگی: رأی دادن درِ اینجا یعنی حدس زدن.
            status = PENDING
            why.append({"code": "WEEKLY_UNMEASURED", "text": "هفتگی به اندازهٔ کافی پیوت ندارد"})
        elif w == "down":
            status = REJECT
            why.append({"code": "WEEKLY_TREND_DOWN", "text": "روند هفتگی نزولی — وتوی قطعی"})
        elif w == "range":
            status = REJECT
            why.append({"code": "WEEKLY_TREND_NEUTRAL", "text": "روند هفتگی خنثی — وتوی قطعی"})
        elif w == "up":
            status = PASS
            why.append({"code": "WEEKLY_TREND_UP", "text": "روند هفتگی صعودی"})
            why.append({"code": "DAILY_BRANCH",
                        "text": f"روزانه {d or '—'} ⇒ شاخهٔ {BRANCH_OF.get(d or '', '—')}"})
        else:
            status = PENDING
            why.append({"code": "WEEKLY_UNCLASSIFIED", "text": "هفتگی دسته‌بندی نشده"})
        # ستاپ‌ها شاهداند: هیچ‌وقت وتوی هفتگی را نمی‌شکنند (رأیِ مالک).
        evidence = [k for k in ("tech_jet", "tech_choch_bull", "tech_double_bottom", "tech_range_break")
                    if _tri(r.get(k)) is True]
        counts[status] += 1
        if status == PASS:
            kept.append(r)
        else:
            dropped.append(sym)
        steps.append({
            "stage": "technical", "symbol": sym, "status": status,
            "weekly": w, "daily": d, "branch": BRANCH_OF.get(d or "", None),
            "matrix": mat, "evidence": evidence,
            "points": _num(r.get("tech_points")) if r.get("tech_points") is not None else None,
            "why": why,
        })
    return {"survivors": kept, "decisions": steps, "counts": counts, "dropped": dropped}


# ── ۳) بنیادی: سه حالتِ سخت‌گیری، بلاکرهایِ واقعی ──────────────────────────
BLOCKERS = ("i1", "i2", "i3")
SUPPORTING = ("i4", "i5")
IND_LABEL = {"i1": "I1 رشد فروش", "i2": "I2 EPS سه‌ساله", "i3": "I3 حاشیه سود ناخالص",
             "i4": "I4 فروش ۱۲ماه ÷ ارزش بازار", "i5": "I5 نرخ‌گذاری"}


def fundamental_stage(rows: list[dict], mode: str = "standard",
                      exceptions: dict[str, list[str]] | None = None,
                      now: int | None = None) -> dict:
    """I1∧I2∧I3 بلاکر (standard)، هر پنج (hard)، استثنایِ صریح (exception).

    canonical هرگز عوض نمی‌شود؛ فقط `effective` با برچسب جابه‌جا می‌شود.
    """
    exceptions = exceptions or {}
    now = now or int(time.time())
    kept, steps, dropped = [], [], []
    counts = {PASS: 0, REJECT: 0, PENDING: 0, UNAVAILABLE: 0}
    for r in rows:
        sym = str(r.get("symbol") or "")
        marks = {k: _tri(r.get(f"{k}_pass")) for k in (*BLOCKERS, *SUPPORTING)}
        detail = [{
            "indicator": k.upper(), "label": IND_LABEL[k], "status": marks[k],
            "value": _num(r.get({"i1": "rev_growth", "i2": "eps_last", "i3": "gross_margin",
                                 "i4": "sales_to_mcap"}.get(k, "") or "_")),
            "threshold": r.get({"i1": "growth_min", "i3": "margin_min", "i4": "sales_to_mcap_min"}.get(k, "") or "_"),
            "as_of": r.get("as_of"), "source": "codal",
        } for k in (*BLOCKERS, *SUPPORTING)]
        missing = [k for k in BLOCKERS if marks[k] is None]
        blocked = [k for k in BLOCKERS if marks[k] is False]
        support_missing = [k for k in SUPPORTING if marks[k] is None]
        why: list[dict[str, str]] = []
        if mode == "hard":
            fail = [k for k in (*BLOCKERS, *SUPPORTING) if marks[k] is False]
            miss = [k for k in (*BLOCKERS, *SUPPORTING) if marks[k] is None]
            if fail:
                status = REJECT
                why += [{"code": f"FUND_{k.upper()}_REJECT", "text": f"{IND_LABEL[k]} تأیید نشده"} for k in fail]
            elif miss:
                status = PENDING
                why += [{"code": f"FUND_{k.upper()}_MISSING", "text": f"{IND_LABEL[k]} سنجیده نشده"} for k in miss]
            else:
                status = PASS
        else:  # standard و exception هر دو canonical را یکسان می‌سنجند
            if blocked:
                status = REJECT
                why += [{"code": f"FUND_{k.upper()}_REJECT",
                         "text": f"{IND_LABEL[k]} زیرِ کف — بلاکرِ جزوه"} for k in blocked]
            elif missing:
                status = PENDING
                why += [{"code": f"FUND_{k.upper()}_MISSING",
                         "text": f"{IND_LABEL[k]} گزارشش نرسیده — رد نیست، سنجیده نشده"} for k in missing]
            elif support_missing and mode == "hard":
                status = PENDING
            else:
                status = PASS
        canonical = status
        granted = [k.upper() for k in exceptions.get(sym, []) if k.upper() in ("I1", "I2", "I3")]
        effective = status
        if mode == "exception" and status == REJECT and granted:
            failed = {k.upper() for k in blocked}
            if failed and failed <= set(granted):
                # فقط بلاکرهایِ واقعاً‌ردشده بخشوده می‌شوند؛ بی‌این، استثنا
                # جایِ هر چیزی را می‌گرفت.
                effective = PASS
                why.append({"code": "EXCEPTION_APPLIED",
                            "text": "استثنای بنیادی: " + "، ".join(sorted(granted))})
        if status == PASS and support_missing:
            why.append({"code": "FUND_SUPPORT_MISSING",
                        "text": "شاهدِ بنیادی کامل نیست: " + "، ".join(k.upper() for k in support_missing)})
        counts[status] += 1
        row_out = dict(r)
        row_out["_fund_canonical"] = canonical
        row_out["_fund_effective"] = effective
        row_out["_fund_exceptions"] = sorted(granted) if effective == PASS and granted else []
        if effective == PASS:
            kept.append(row_out)
        else:
            dropped.append(sym)
        steps.append({
            "stage": "fundamental", "symbol": sym, "mode": mode,
            "canonical": canonical, "effective": effective,
            "exceptions": row_out["_fund_exceptions"],
            "score": _num(r.get("score")), "primary_score": _num(r.get("primary_score")),
            "indicators": detail, "why": why,
        })
    return {"survivors": kept, "decisions": steps, "counts": counts, "dropped": dropped}


# ── ۴) تحویل: رتبۀ شفاف با دادهٔ موجود ───────────────────────────────────
def handover_stage(rows: list[dict], tape: dict, tech: dict, fund: dict,
                   assembly_vetoed: Iterable[str] = ()) -> dict:
    """بهترین‌ها اول — بی‌scoreِ ساختگی. ترتیبِ ثابت و بازتولیدشدنی."""
    veto = {str(s) for s in assembly_vetoed}
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    rank_by = {str(r.get("symbol")): i for i, r in enumerate(rows)}
    out = []
    for r in rows:
        sym = str(r.get("symbol") or "")
        f = fund_by.get(sym) or {}
        t = tech_by.get(sym) or {}
        exc = f.get("exceptions") or []
        out.append({
            "symbol": sym,
            "name": r.get("name") or "",
            "final": REJECT if sym in veto else PASS,
            "exception": bool(exc),
            "fund_score": _num(r.get("score")),
            "tech_points": _num(r.get("tech_points")),
            "backend_rank": rank_by.get(sym),
            "weekly": t.get("weekly"), "daily": t.get("daily"), "branch": t.get("branch"),
            "exceptions": exc,
            "assembly_veto": sym in veto,
            "why": ([{"code": "ASSEMBLY_VETO", "text": "وتوی مجمع — زمان‌بندیِ ورود"}]
                    if sym in veto else list(t.get("why") or []) + list(f.get("why") or [])),
            "chain": [s["filter_id"] for s in tape["steps"]],
        })
    # ترتیبِ ترجیحیِ مالک: حکمِ نهایی → بی‌استثنا → قدرتِ بنیادی → شواهدِ
    # تکنیکال → رتبۀ رسمیِ بک‌اند → نماد (برایِ پایداری). هیچ وزنِ پنهانی نیست.
    out.sort(key=lambda e: (e["final"] != PASS, e["exception"],
                            -(e["fund_score"] if e["fund_score"] is not None else -1),
                            -(e["tech_points"] if e["tech_points"] is not None else -1),
                            e["backend_rank"] if e["backend_rank"] is not None else 10 ** 9,
                            e["symbol"]))
    for i, e in enumerate(out, 1):
        e["display_rank"] = i
    return {"entries": out, "counts": {
        PASS: sum(1 for e in out if e["final"] == PASS),
        REJECT: sum(1 for e in out if e["final"] == REJECT),
        "exception": sum(1 for e in out if e["exception"]),
    }}


# ── نمایش ──────────────────────────────────────────────────────────────────
# این بلوک فقط «ستون‌هایی که جدول می‌خواند» را از همان ردیفِ ورودی برمی‌دارد.
# هیچ قیاسِ آستانه‌ای درِ آن نیست؛ اگر روزی چیزی شبیه `if x > th` اینجا ظاهر شد،
# آن یک داورِ دوم است نه نمایش.
_LABEL_OF = {"f_clock": "ساعت", "f_susp": "مشکوک", "f_jet": "جت", "f_roobi": "کف‌روب",
             "f_noqteh": "نقطه", "f_smart": "پول هوشمند", "f_legal": "کد به کد"}


def _display(r: dict, *, patterns: list[str] | None = None,
             status: dict[str, str] | None = None,
             why: dict[str, list[dict]] | None = None,
             chain: tuple[str, ...] = ()) -> dict:
    """یک ردیفِ آمادهِ رندر برایِ جدول — با traceِ همان نماد."""
    sym = str(r.get("symbol") or "")
    return {
        "symbol": sym,
        "name": r.get("name") or "",
        "sector": r.get("sector_name") or r.get("sector") or "",
        "last": _num(r.get("p_last")),
        "closing": _num(r.get("p_closing")),
        "change_pct": _num(r.get("percent_change")),
        "vol_ratio": _num(r.get("vol_ratio")),
        "patterns": patterns if patterns is not None
        else [_LABEL_OF[f] for f in REG.filter_ids() if _tri(r.get(f)) is True],
        "status": status or {},
        "why": why or {},
        "chain": list(chain),
        "score": _num(r.get("score")),
        "primary_score": _num(r.get("primary_score")),
        "weekly": r.get("tech_trend_w"), "daily": r.get("tech_trend_d"),
        "branch": BRANCH_OF.get(str(r.get("tech_trend_d") or ""), None),
        "matrix": r.get("tech_matrix_decision"),
        "tech_status": r.get("tech_status"),
        "tech_points": _num(r.get("tech_points")),
        "evidence": [k for k in ("tech_jet", "tech_choch_bull", "tech_double_bottom",
                                 "tech_range_break") if _tri(r.get(k)) is True],
        "fib_zone": r.get("tech_fib_zone"),
        "hourglass": _tri(r.get("tech_hourglass_active")),
        "inds": {k: _tri(r.get(f"{k}_pass")) for k in (*BLOCKERS, *SUPPORTING)},
        "ind_values": {"i1": _num(r.get("rev_growth")), "i2": _num(r.get("eps_last")),
                       "i3": _num(r.get("gross_margin")), "i4": _num(r.get("sales_to_mcap"))},
        "pricing_mode": r.get("pricing_mode"),
        "excluded": bool(r.get("excluded")),
        "exclusion_reasons": r.get("exclusion_reasons") or "",
        "assembly_veto": _tri(r.get("assembly_veto")) is True,
        "assembly_why": r.get("assembly_why") or "",
        "as_of": r.get("as_of"),
        "is_live": r.get("is_live"),
        # رتبۀ رسمیِ بک‌اند همان است که اسکرینر ساخته؛ اینجا فقط حمل می‌شود.
        "rank": r.get("_backend_rank"),
    }


# ── حلقۀ اصلی ─────────────────────────────────────────────────────────────
def resolve_chain(preset: str, custom: Iterable[str] | None) -> tuple[str, ...]:
    p = REG.PRESET_BY_ID.get(preset)
    if p is None:
        raise KeyError(f"presetِ ناشناخته: {preset}")
    if p.preset_id != "custom":
        return p.chain
    chain = tuple(custom or ())
    for fid in chain:
        if fid not in REG.BY_ID:
            raise KeyError(f"فیلترِ ناشناخته درِ زنجیره: {fid}")
    return chain


def status_matrix(joined: list[dict], tape: dict, tech: dict, fund: dict,
                  hand: dict) -> tuple[dict, dict]:
    """وضعیتِ هر چهار گام برایِ **تک‌تکِ** نمادهایِ جامعۀ ورودی.

    قاعدۀ مالک: هیچ نمادی گم نمی‌شود و هیچ «سنجیده نشده»ای بی‌دلیل نیست. دو
    دلیلِ مجاز و افتراقی وجود دارد:
      UNAVAILABLE                 منبعی برایِ سنجشِ آن گام نیست (مثلاً پوششِ کدال)
      NOT_REQUIRED                گامِ قبل نماد را رد کرده، پس این گام اجرا نمی‌شود
    جمعِ شمارشِ هر گام باید دقیقاً با جامعۀ ورودی بخواند؛ گاردِ
    `dev/funnel_engine_v1.py` همین را می‌بندد.
    """
    survivors = {str(r.get("symbol") or "") for r in tape["survivors"]}
    dropped_first: dict[str, dict] = {}
    for step in tape["steps"]:
        for sym in tape["dropped"].get(step["filter_id"], []):
            dropped_first.setdefault(sym, step)
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    hand_by = {e["symbol"]: e for e in hand["entries"]}

    matrix: dict[str, dict[str, dict]] = {}
    coverage: dict[str, dict[str, int]] = {
        "tape": {k: 0 for k in STATUSES}, "technical": {k: 0 for k in STATUSES},
        "fundamental": {k: 0 for k in STATUSES}, "handover": {k: 0 for k in STATUSES},
    }

    def code_of(decisions: dict, sym: str) -> str:
        w = (decisions.get(sym) or {}).get("why") or []
        return w[0].get("code", "") if w else ""

    for r in joined:
        sym = str(r.get("symbol") or "")
        t = tech_by.get(sym)
        f = fund_by.get(sym)
        h = hand_by.get(sym)
        step = dropped_first.get(sym)
        if step is not None:
            tape_st = {"status": REJECT,
                       "reason_code": f"TAPE_{step['filter_id'].upper()}_NO_MATCH",
                       "human_reason": f"{step['label']} — نشانه در این نماد نیست",
                       "stage_ref": step["source_ref"]}
        elif sym in survivors:
            tape_st = {"status": PASS, "reason_code": "TAPE_PASSED",
                       "human_reason": "همۀ فیلترهایِ زنجیره را خورده شده"}
        else:
            tape_st = {"status": UNAVAILABLE, "reason_code": "TAPE_NO_FLAG",
                       "human_reason": "پرچم این نماد در این نشست ساخته نشده"}

        if tape_st["status"] != PASS:
            tech_st = {"status": NOT_REQUIRED,
                       "reason_code": "NOT_REQUIRED_AFTER_TAPE_REJECT",
                       "human_reason": "تابلو نماد را رد کرده؛ تکنیکال اجرا نمی‌شود"}
        elif t is None:
            tech_st = {"status": UNAVAILABLE, "reason_code": "TECH_NO_VERDICT",
                       "human_reason": "سریِ تکنیکال برای این نماد ساخته نشد"}
        else:
            tech_st = {"status": t["status"],
                       "reason_code": code_of(tech_by, sym) or "TECH_PASSED",
                       "human_reason": " · ".join(w["text"] for w in (t.get("why") or []))}

        if tech_st["status"] in (REJECT, UNAVAILABLE, NOT_REQUIRED):
            why_stage = "تابلو" if tape_st["status"] != PASS else "تکنیکال"
            fund_st = {"status": NOT_REQUIRED,
                       "reason_code": f"NOT_REQUIRED_AFTER_{'TAPE' if tape_st['status'] != PASS else 'TECHNICAL'}_"
                                      + ("REJECT" if tech_st["status"] in (REJECT, NOT_REQUIRED) and tape_st["status"] == PASS else "STOP"),
                       "human_reason": f"{why_stage} نماد را رد کرده؛ بنیادی اجرا نمی‌شود"}
        elif f is None:
            fund_st = {"status": UNAVAILABLE, "reason_code": "FUND_NO_CODAL_COVERAGE",
                       "human_reason": "پوشش کدال این نماد در اسکرینر نیست"}
        else:
            fund_st = {"status": f["effective"],
                       "reason_code": code_of(fund_by, sym) or "FUND_PASSED",
                       "human_reason": " · ".join(w["text"] for w in (f.get("why") or [])),
                       "canonical": f["canonical"], "exceptions": f.get("exceptions") or []}

        if h is not None:
            hand_st = {"status": h["final"],
                       "reason_code": (h.get("why") or [{}])[0].get("code", "")
                                      or ("ASSEMBLY_VETO" if h.get("assembly_veto") else "FINAL_PASS"),
                       "human_reason": " · ".join(w["text"] for w in (h.get("why") or [])),
                       "display_rank": h.get("display_rank")}
        else:
            prior = [tape_st["status"], tech_st["status"], fund_st["status"]]
            if REJECT in prior:
                hand_st = {"status": REJECT, "reason_code": "NOT_ELIGIBLE_AFTER_PRIOR_REJECT",
                           "human_reason": "در گامِ پیشین رد شده"}
            elif PENDING in prior:
                hand_st = {"status": PENDING, "reason_code": "WAITING_FOR_DATA",
                           "human_reason": "در انتظارِ داده/گزارش"}
            else:
                hand_st = {"status": UNAVAILABLE, "reason_code": "NO_FINAL_SOURCE",
                           "human_reason": "منبعی برای حکم نهایی نبود"}

        row = {"tape": tape_st, "technical": tech_st, "fundamental": fund_st, "handover": hand_st}
        matrix[sym] = row
        for stage, cell in row.items():
            coverage[stage][cell["status"]] = coverage[stage].get(cell["status"], 0) + 1
    return matrix, coverage


def _view(joined: list[dict], tape: dict, tech: dict, fund: dict, hand: dict,
          chain: tuple[str, ...]) -> dict:
    """ردیف‌هایِ آمادهٔ رندر برایِ هر چهار گام + خطِ زمانِ هر نماد.

    هیچ داوریِ تازه‌ای درِ این تابع نیست: وضعیتِ هر نماد از همان تصمیمی خوانده
    می‌شود که سه گامِ قبل گرفته‌اند. جایی که تصمیمی ثبت نشده `unavailable`
    می‌نشیند، نه `pass`.
    """
    tech_by = {d["symbol"]: d for d in tech["decisions"]}
    fund_by = {d["symbol"]: d for d in fund["decisions"]}
    hand_by = {e["symbol"]: e for e in hand["entries"]}
    tape_surv = {str(r.get("symbol") or "") for r in tape["survivors"]}
    dropped_at: dict[str, dict] = {}
    for step in tape["steps"]:
        for sym in tape["dropped"].get(step["filter_id"], []):
            dropped_at.setdefault(sym, step)

    entries: dict[str, list[dict]] = {"tape": [], "technical": [], "fundamental": [], "handover": []}
    timeline: dict[str, list[dict]] = {}
    for r in joined:
        sym = str(r.get("symbol") or "")
        t = tech_by.get(sym)
        f = fund_by.get(sym)
        h = hand_by.get(sym)
        tape_status = PASS if sym in tape_surv else REJECT if sym in dropped_at else PENDING
        why = list(r.get("_funnel_why") or [])
        st = {"tape": tape_status,
              "technical": (t or {}).get("status", UNAVAILABLE if sym in tape_surv else PENDING),
              "fundamental": (f or {}).get("effective", UNAVAILABLE if t and t["status"] == PASS else PENDING),
              "handover": (h or {}).get("final", UNAVAILABLE if f and f["effective"] == PASS else PENDING)}
        human = {"tape": next((w["human_reason"] for w in reversed(why) if w.get("stage") == "tape"),
                              "همهٔ فیلترهای زنجیره را رد کرده" if tape_status == PASS else ""),
                 "technical": " · ".join(w["text"] for w in (t or {}).get("why") or []),
                 "fundamental": " · ".join(w["text"] for w in (f or {}).get("why") or []),
                 "handover": " · ".join(w["text"] for w in (h or {}).get("why") or [])}
        codes = {"tape": [w.get("reason_code", "") for w in why if w.get("stage") == "tape"],
                 "technical": [w["code"] for w in (t or {}).get("why") or []],
                 "fundamental": [w["code"] for w in (f or {}).get("why") or []],
                 "handover": [w["code"] for w in (h or {}).get("why") or []]}
        for stage_key in ("tape", "technical", "fundamental", "handover"):
            if stage_key == "tape" and sym not in tape_surv and sym not in dropped_at:
                continue  # هرگز نرسیده به این گام
            if stage_key == "technical" and t is None:
                continue
            if stage_key == "fundamental" and f is None:
                continue
            if stage_key == "handover" and h is None and st["fundamental"] != PASS:
                continue
            entries[stage_key].append(_display(
                r, patterns=None,
                status={stage_key: st[stage_key]},
                why={stage_key: [{"code": c, "text": human[stage_key]} for c in codes[stage_key] if c]},
                chain=chain))
        step_rows = [{"stage": "universe", "status": PASS, "reason_code": "IN_UNIVERSE",
                      "human_reason": "در جامعۀ این نشست", "input_count": len(joined),
                      "output_count": len(joined), "source": "api/market", "timestamp": None}]
        for sp in tape["steps"]:
            hit = next((w for w in why if w.get("stage") == "tape" and w.get("seq") == sp["seq"]), None)
            step_rows.append({
                "stage": f"tape:{sp['filter_id']}", "seq": sp["seq"],
                "status": (PASS if sym in tape_surv or
                           all(sym not in tape["dropped"].get(x["filter_id"], []) for x in tape["steps"][:sp["seq"]])
                           else REJECT),
                "reason_code": (hit or {}).get("reason_code", "TAPE_PASSED"),
                "human_reason": (hit or {}).get("human_reason", f"{sp['label']} — خورده شد"),
                "input_count": sp["input_count"], "output_count": sp["matched_count"],
                "source": sp["source_ref"], "formula_version": sp["formula_version"],
                "filter_id": sp["filter_id"], "label": sp["label"],
                "parameter_set": sp["parameter_set"], "timestamp": None})
        for key, dec in (("technical", t), ("fundamental", f), ("handover", h)):
            if not dec:
                continue
            w0 = (dec.get("why") or [{}])[0]
            step_rows.append({
                "stage": key, "status": dec.get("effective") or dec.get("status") or dec.get("final") or PENDING,
                "reason_code": w0.get("code", ""), "human_reason": w0.get("text", ""),
                "input_count": None, "output_count": None,
                "source": "funnel_engine", "timestamp": None})
        timeline[sym] = step_rows
    return {"entries": entries, "timeline": timeline}


def evaluate(board_rows: list[dict], screen_rows: list[dict], *,
             preset: str = "trend", custom_chain: Iterable[str] | None = None,
             fund_mode: str = "standard",
             params: dict[str, dict[str, Any]] | None = None,
             exceptions: dict[str, list[str]] | None = None,
             as_of: int | None = None) -> dict:
    """قیفِ کامل رویِ کلِ جامعۀ ورودی. هیچ جایی slice نمی‌زند."""
    as_of = as_of or int(time.time())
    screen_by = {str(r.get("symbol") or ""): r for r in screen_rows}
    for i, r in enumerate(screen_rows):
        r["_backend_rank"] = i  # ترتیبِ خودِ /api/screener (screener.py:440)
    chain = resolve_chain(preset, custom_chain)

    # تابلوخوانی رویِ ردیفِ خودِ تابلو؛ ردیفِ اسکرینر به همان نماد می‌چسبد تا
    # مراحلِ بعدی از یک منبعِ واحدِ عدد بخوانند.
    # جامع = نماد، نه ردیف. دو ردیفِ هم‌نام درِ تابلو (املایِ دوگانه یا نوشتۀ
    # تکراری) دو نماد نیستند؛ بی‌این یکی‌کردن، matrix (کلیدش نماد) از coverage
    # (شمارشِ ردیف) کم می‌شد و جمعِ وضعیت‌ها با جامعۀ واقعی نمی‌خواند.
    seen: dict[str, dict] = {}
    dupes = 0
    for r in board_rows:
        sym = str(r.get("symbol") or "").strip().replace("ي", "ی").replace("ك", "ک")
        if not sym:
            continue
        if sym in seen:
            dupes += 1
            continue
        scr = screen_by.get(sym) or screen_by.get(str(r.get("symbol") or "")) or {}
        row = dict(r)
        row["symbol"] = sym
        for k, v in scr.items():
            row.setdefault(k, v)
        seen[sym] = row
    joined = list(seen.values())

    tape = tape_stage(joined, chain, params)
    tech = technical_stage(tape["survivors"])
    fund = fundamental_stage(tech["survivors"], fund_mode, exceptions, now=as_of)
    view_rows = joined
    hand = handover_stage(fund["survivors"], tape, tech, fund,
                          assembly_vetoed=[str(r.get("symbol") or "") for r in joined
                                           if _tri(r.get("assembly_veto")) is True])

    view = _view(view_rows, tape, tech, fund, hand, chain)
    matrix, coverage = status_matrix(joined, tape, tech, fund, hand)
    return {
        "status": "success",
        "engine_version": ENGINE_VERSION,
        "ruleset_version": REG.RULESET_VERSION,
        "as_of": as_of,
        "preset": preset,
        "chain": list(chain),
        "fund_mode": fund_mode,
        "universe": {"board": len(board_rows), "screened": len(screen_rows),
                     "joined": len(joined), "duplicate_rows": dupes},
        "stages": {
            "tape": {"steps": tape["steps"],
                     "input": len(joined), "matched": len(tape["survivors"]),
                     "removed": len(joined) - len(tape["survivors"])},
            "technical": {"counts": tech["counts"], "matched": len(tech["survivors"])},
            "fundamental": {"counts": fund["counts"], "matched": len(fund["survivors"]),
                            "mode": fund_mode},
            "handover": {"counts": hand["counts"], "matched": len(hand["entries"])},
        },
        "handover": hand["entries"],
        "entries": view["entries"],
        "timeline": view["timeline"],
        "status_matrix": matrix,
        "coverage": coverage,
        "trace": {
            "tape_dropped": {k: v for k, v in tape["dropped"].items() if v},
            "technical": tech["decisions"],
            "fundamental": fund["decisions"],
        },
        "registry": REG.as_json(),
    }
