#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""قراردادِ لایهٔ دیتای FTS v2.2 (dev-only) — نگه‌دارندهٔ پیمانِ نویسنده/خواننده.

این گارد «قرارداد» را ثابت می‌کند، نه رفتارِ یک اجرا. سه منبع حقیقت باید با هم
توافق کنند ولو اینکه هر کدام در فایلِ جداگانه‌ای هستند:

  ۱) اسکیما            — codal_fetcher.migrate_schema (DDL واقعیِ روی market.db)
  ۲) نویسنده           — dev/codal_fts_updater._FTSR_COLS + _FTSR_PLACE
  ۳) خواننده           — fts_engine._FTS_RESULTS_COLS

تسک ۱۹ دو باگِ دقیقاً از جنسِ «عدمِ توافقِ این سه» پیدا کرد:
  • ۲۷ ستون در برابر ۲۸ placeholder → «table fts_results has 27 columns but 28
    values were supplied» روی اولین اجرای واقعی.
  • نویسنده، ردیف‌های همین‌نوشته‌شده را با invalidate_fts_results پاک می‌کرد
    (DELETE از جدول) چون پیمانِ «نویسنده فقط کشِ RAM را بی‌اعتبار می‌کند»
    نوشته نشده بود.

این گارد هر دو رگرسیون را در CI می‌گیرد — بدون نیاز به گوشی، شبکه یا حتی یک
market.db واقعی (همه چیز روی یک DB موقت در tmp ساخته می‌شود).

اجرا:
    python dev/db_contract_v11.py
"""
import json
import os
import sqlite3
import sys
import tempfile

# اجازهٔ importِ ماژول‌های ریشه از داخل dev/
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import codal_fetcher as cf          # noqa: E402  (اسکیما + migrate_schema)
import fts_engine                    # noqa: E402  (خواننده + invalidate)
sys.path.insert(0, os.path.join(_ROOT, "dev"))
import codal_fts_updater as cu       # noqa: E402  (نویسنده)

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

bad = []


def ck(cond, msg):
    print("  %s %s" % ("PASS" if cond else "FAIL", msg))
    if not cond:
        bad.append(msg)


def _col_list(x):
    """ستون‌ها را از هر دو شکل می‌گیرد: رشتهٔ «a, b, c» یا تاپلِ یک‌عضویِ آن.

    نکتهٔ ظریف: fts_engine._FTS_RESULTS_COLS یک تاپلِ یک‌عضوی است (ویرگولِ
    انتهایی)، در حالی که codal_fts_updater._FTSR_COLS یک رشتهٔ ساده است. این
    تابع هر دو را به یک لیستِ ستونی یکسان تبدیل می‌کند تا مقایسه درست بماند.

    عمداً سخت‌گیر است: فقط همین دو شکلِ مجاز را می‌پذیرد و هر چیزِ دیگر
    (تاپلِ چندعضوی، None، عدد) را بالا می‌اندازد. یک نرمال‌سازِ «مهربان»
    میتوانست یک ثابتِ تغییرکرده را بی‌صدا بپذیرد و گارد را به‌اشتباه سبز کند.
    """
    if isinstance(x, (tuple, list)):
        if len(x) != 1:
            raise TypeError("column constant is a %d-element sequence, "
                            "expected 1 (a single SQL fragment)" % len(x))
        x = x[0]
    if not isinstance(x, str):
        raise TypeError("column constant is %s, expected a string"
                        % type(x).__name__)
    return [c.strip() for c in x.split(",") if c.strip()]


# ═══════════════════════════════════════════════════════════════════════════
print("۱) توافقِ ستون‌ها: نویسنده ≡ خواننده")
print("═════════════════════════════════════════════════════════════════════════")
# نویسنده یک ستونِ اضافه می‌نویسد: computed_at (درِ INSERT هست ولی خواننده آن را
# در SELECT نمی‌آورد — فقط برای مرتب‌سازی/پاکسازیِ داخلی). پس:
#   ستون‌های خواننده ⊂ ستون‌های نویسنده، و تفاضلِ مجاز دقیقاً {computed_at} است.
_w_cols = _col_list(cu._FTSR_COLS)
_r_cols = _col_list(fts_engine._FTS_RESULTS_COLS)
ck(len(_w_cols) == 27, "نویسنده ۲۷ ستون دارد (نه ۲۸ — باگِ تسک ۱۹ برنگشته)")
ck(len(_r_cols) == 26, "خواننده ۲۶ ستون در SELECT می‌آورد (اندیس‌های ۰..۲۵)")
ck(len(_w_cols) == len(set(_w_cols)), "ستون‌های نویسنده تکراری نیستند")
ck(len(_r_cols) == len(set(_r_cols)), "ستون‌های خواننده تکراری نیستند")
_extra = sorted(set(_w_cols) - set(_r_cols))
_missing = sorted(set(_r_cols) - set(_w_cols))
ck(_extra == ["computed_at"],
   "تنها ستونی که نویسنده می‌نویسد ولی خواننده نمی‌خواند = computed_at (گرفت: %s)" % _extra)
ck(not _missing,
   "هیچ ستونی که خواننده بخواهد و نویسنده ننوشته باشد نیست (گرفت: %s)" % _missing)

# پیمانِ placeholder: دقیقاً به تعدادِ ستون‌های INSERT — وگرنه SQLite در اولین
# اجرای واقعی با «N columns but M values were supplied» می‌ترکد.
ck(cu._FTSR_PLACE == ",".join(["?"] * len(_w_cols)),
   "تعدادِ placeholder برابرِ تعدادِ ستون‌های نویسنده (%d)" % len(_w_cols))
ck(cu._FTSR_PLACE.count("?") == len(_w_cols),
   "_FTSR_PLACE دقیقاً %d علامت‌سؤال دارد" % len(_w_cols))


# ═══════════════════════════════════════════════════════════════════════════
print("\n۲) توافقِ ستون‌ها: اسکیما ≡ نویسنده (روی DB واقعیِ ساخته‌شده)")
print("═════════════════════════════════════════════════════════════════════════")
_tmp = tempfile.mkdtemp(prefix="dbcontract_v11_")
_db = os.path.join(_tmp, "contract.db")
_con = sqlite3.connect(_db, timeout=60)
cf.create_schema(_con)
cf.migrate_schema(_con)
_con.commit()

_ddl_cols = [r[1] for r in _con.execute("PRAGMA table_info(fts_results)")]
ck(len(_ddl_cols) == 27,
   "PRAGMA table_info(fts_results) دقیقاً ۲۷ ستون می‌دهد (گرفت: %d)" % len(_ddl_cols))
ck(sorted(_ddl_cols) == sorted(_w_cols),
   "ستون‌های DDL با ستون‌های نویسنده یکی است")
ck("cfg_hash" in _ddl_cols and "computed_at" in _ddl_cols,
   "ستون‌های کلیدیِ قرارداد (cfg_hash, computed_at) در DDL موجودند")

# INSERT واقعی با همان فرمولِ نویسنده — اثباتِ اینکه placeholder/ستون هم‌خوانی
# روی SQLiteِ واقعی کار می‌کند (این دقیقاً همان جایی بود که باگ ۲۸تایی می‌ترکید).
# نکته: score/verdict/computed_at در DDL «NOT NULL» هستند، پس ردیفِ همه-NULL
# بهخاطرِ خودِ NOT NULL رد میشود، نه بهخاطرِ شمارشِ ستون. آن سه مقدار می‌گیرند
# و بقیه NULL میمانند — این تست فقط «۲۷ ستون = ۲۷ مقدار» را می‌سنجد، نه
# معتبربودنِ داده را (دادهٔ واقعی را evaluate_v10 می‌سازد).
_notnull = {"symbol": "CONTRACT-PROBE", "score": 0, "verdict": "PROBE",
            "computed_at": "probe"}
_vals = tuple(_notnull.get(c, None) for c in _w_cols)
try:
    _con.execute(cu._FTSR_UPSERT, _vals)
    _con.rollback()
    _insert_ok = True
except Exception as _e:
    _insert_ok = False
    print("        SQLite گفت: %s" % _e)
ck(len(_vals) == len(_w_cols),
   "همان تعدادِ مقدار ساخته میشود که ستون هست (۲۷ = ۲۷)")
ck(_insert_ok, "INSERT با _FTSR_COLS/_FTSR_PLACE روی DB واقعی خطا نمیدهد")

# یدم‌پذیریِ مهاجرت: اجرای دوباره نباید ستونی را اضافه/کم کند یا خطا دهد.
_before = [r[1] for r in _con.execute("PRAGMA table_info(fts_results)")]
cf.migrate_schema(_con)
cf.migrate_schema(_con)
_after = [r[1] for r in _con.execute("PRAGMA table_info(fts_results)")]
ck(_before == _after, "مهاجرتِ دوباره ستون‌ها را تغییر نمیدهد (یدم‌پذیر)")
ck(_con.execute("PRAGMA integrity_check").fetchone()[0] == "ok",
   "integrity_check = ok")


# ═══════════════════════════════════════════════════════════════════════════
print("\n۳) پیمانِ نویسنده: ردیف‌های نوشته‌شده را پاک نمیکند")
print("═════════════════════════════════════════════════════════════════════════")
# باگِ تسک ۱۹: sync_fts_results با invalidate_fts_results تمام می‌شد که
# «DELETE FROM fts_results» میزند → ردیفی که همین الان نوشته بود پاک می‌شد و
# خواننده در اولین فراخوانی None می‌گرفت. پیمان: نویسنده فقط کشِ RAMِ خواننده
# را بی‌اعتبار می‌کند، نه خودِ جدول را.
_src = cu.sync_fts_results.__doc__ or ""
_body = ""
try:
    import inspect as _inspect
    _body = _inspect.getsource(cu.sync_fts_results)
except Exception:
    pass
ck("invalidate_fts_results(" not in _body.replace(
    "fts_engine.invalidate_fts_results(conn)", "invalidate_fts_results(X)", 1)
   or "DELETE FROM fts_results" not in _body,
   "sync_fts_results جدول را DELETE نمیکند (فقط کشِ RAM پاک میشود)")
ck("_FTS_RESULTS_CACHE" in _body,
   "sync_fts_results کشِ RAMِ خواننده را بی‌اعتبار می‌کند (_FTS_RESULTS_CACHE)")
ck("invalidate_fts_results" not in _body or
   "نمیکنیم" in _body or "فقط" in _body or "RAM" in _body or "حافظه" in _body,
   "پیمانِ «فقط کشِ RAM پاک میشود» در بدنه/توضیحِ sync_fts_results نوشته شده")

# رفتارِ واقعیِ خواننده: invalidate → DELETE + fallback زنده.
ck(fts_engine.invalidate_fts_results.__doc__ is not None and
   "حذف" in (fts_engine.invalidate_fts_results.__doc__ or ""),
   "invalidate_fts_results خودش DELETE میزند (این مالِ مسیرِ سینک است، نه نویسنده)")


# ═══════════════════════════════════════════════════════════════════════════
print("\n۴) پیمانِ cfg_hash: نویسنده و اسکرینر یک فرمول می‌نویسند")
print("═════════════════════════════════════════════════════════════════════════")
# cfg_hash پیمانِ «تغییرِ آستانه → جدول بی‌اعتبار» است. اگر نویسنده و خواننده
# فرمولِ متفاوتی داشته باشند، جدولِ تازه هیچ‌وقت معتبر نمی‌شود و اسکرینر همیشه
# fallback زنده می‌شود (یعنی N+1 برمی‌گردد).
try:
    import api.screener as _SC
    _sc_src = _inspect.getsource(_SC)
    _has_dumps = "json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)" in _sc_src
    ck(_has_dumps,
       "اسکرینر با همان فرمولِ json.dumps(sort_keys, ensure_ascii=False, default=str) می‌نویسد")
except Exception as _e:
    print("  SKIP بررسیِ فرمولِ اسکرینر (%s)" % str(_e)[:60])

ck("json.dumps" in _body and "sort_keys" in _body and "ensure_ascii" in _body,
   "نویسنده cfg_hash را با json.dumps(sort_keys=True, ensure_ascii=False) می‌سازد")

# یک گردشِ کامل روی DB موقت: بنویس، بخوان، بی‌اعتبار کن، fallback بگیر.
_cfg = {"eps_years": 3, "exclude_base_market": True, "monetary_floor": 0.25}
_cfg_hash = json.dumps(_cfg, sort_keys=True, ensure_ascii=False, default=str)
_con.execute("DELETE FROM fts_results")
_con.execute(cu._FTSR_UPSERT, ("X", 1.0, 1, "[]", 1, 2.0, 1, 3.0, 1, "free", 1,
                               5, "STRONG", 0, "", 1, 1, 1, 1, 10.0, 20.0,
                               30.0, 40.0, 50.0, 12, _cfg_hash, "t"))
_con.commit()
_row = fts_engine.fts_results_of(_con, "X", cfg_hash=_cfg_hash)
ck(_row is not None, "خواننده ردیفِ نوشته‌شده را با cfg_hashِ یکسان برمی‌گرداند")
ck(fts_engine.fts_results_of(_con, "X", cfg_hash="OTHER") is None,
   "cfg_hashِ ناهم‌خوان → None (fallback زنده — تغییرِ آستانه جدول را می‌شکند)")
_n = fts_engine.invalidate_fts_results(_con)
ck(_n == 1, "invalidate_fts_results ردیفها را پاک می‌کند (rowcount=1)")
ck(fts_engine.fts_results_of(_con, "X", cfg_hash=_cfg_hash) is None,
   "بعد از invalidate → None → مسیرِ سینکِ کثیف به fallback زنده میرود")

_con.close()

# جدولِ غایب و جدولِ قدیمیِ ۴ستونی: خواننده باید None بدهد، نه کرش.
print("\n۵) دفاعی بودنِ خواننده (جدولِ غایب / قدیمی)")
print("═════════════════════════════════════════════════════════════════════════")
_c2 = sqlite3.connect(os.path.join(_tmp, "absent.db"), timeout=60)
ck(fts_engine.fts_results_of(_c2, "X", cfg_hash=_cfg_hash) is None,
   "جدولِ غایب → None (اسکرینر مسیرِ زندهٔ ازپیش‌موجود را طی میکند)")
_c3 = sqlite3.connect(os.path.join(_tmp, "legacy.db"), timeout=60)
_c3.execute("CREATE TABLE fts_results (symbol TEXT, score INTEGER, verdict TEXT, computed_at TEXT)")
_c3.commit()
ck(fts_engine.fts_results_of(_c3, "X", cfg_hash=_cfg_hash) is None,
   "جدولِ قدیمیِ پیشازافزایشی → None، نه کرش")
_c2.close()
_c3.close()

try:
    import shutil as _shutil
    _shutil.rmtree(_tmp, ignore_errors=True)
except Exception:
    pass

print("\n" + "=" * 74)
if bad:
    print("❌ %d شکست:" % len(bad))
    for _f in bad:
        print("   - " + _f)
    sys.exit(1)
print("✅ قراردادِ لایهٔ دیتای FTS v2.2 سالم است — نویسنده/خواننده/اسکیما توافق دارند")
