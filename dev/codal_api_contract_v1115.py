#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dev/codal_api_contract_v1115.py — گاردِ لایۀ HTTPِ بنیادی (کارت + سلامتِ کدال).

چرا این گارد جدا لازم بود: گاردِ `dev/codal_scheduler_v1103.py:352` وجودِ
اندپوینتِ سلامت را با **خواندنِ متنِ `api/fundamental.py`** بررسی می‌کرد
(`"/api/sync/codal/pipeline" in src`). آن بررسی با اینکه اندپوینت ۵۰۰ می‌دهد،
پاسخِاش یک خانۀ schemaِ رابطِ کاربر را کم دارد، یا اصلاً در `app.routes` ثبت
نشده باشد هم سبز می‌ماند. پنج گاردِ دیگر (`v1100`…`v1104`) منطقِ موتور و دفترِ
کار را می‌سنجند؛ هیچ‌کدام درخواستِ HTTP نمی‌فرستاد و هیچ‌کدام پاسخ را با
schemaِ zodِ رابط نمی‌سنجید. تا پیش از این فایل، «API دادهٔ معتبر و
قابل‌ردیابی می‌دهد» در این مخزن اجرا‌نشده بود.

این گارد همان را روی سیم می‌سنجد، روی بانکِ موقتِ کوچک با schemaِ **خودِ**
`codal_fetcher` (create_schema + migrate_schema) و بی‌شبکه:
  ۱) کارتِ بنیادی ۲۰۰ می‌دهد و هر پنج شاخص به‌صورت دیکشنریِ سه‌حاله می‌رسد؛
  ۲) ردپا (`source`، `unit`، `unit_note`، `ref_tracing_no`) پس از JSON‌سازی
     زنده می‌ماند — همان چیزی که کارتِ UI چاپ می‌کند؛
  ۳) خانۀ لازمِ `FtsCardSchema` در پاسخ هست **و** در فایلِ رابط هم نامش هست،
     پس تغییرِ نام در یکِ طرف قرمز می‌شود؛
  ۴) غایب ≠ صفر روی سیم: نبودِ گزارشِ ماهانه `null` می‌شود نه `0`، نبودِ ارزشِ
     بازار `data_gap` است نه رأیِ رد؛
  ۵) نمادِ ناشناخته ۴۰۴ می‌دهد نه ۵۰۰ و نه `status: success`ِ تهی؛
  ۶) سلامتِ کدال: خانۀ schemaِ رابط در پاسخ‌اند، شمارنده‌ها از جدول می‌آیند،
     چرخۀ شکست‌خورده هرگز «موفق» گزارش نمی‌شود، `data_epoch` با عوض‌شدنِ داده
     عوض می‌شود، و آندر‌پوینت در `app.routes` ثبت است (نه در متنِ فایل)؛
  ۷) دام‌هایِ منفی: هر چهار سنجشِ بالا رویِ پاسخِ عمداً معیوب هم باید قرمز
     شوند، وگرنه سنسور کور است.

اجرا:  python dev/codal_api_contract_v1115.py     (۰ = سبز، ۱ = رد)
"""
import json
import os
import sqlite3
import sys
import tempfile

os.environ["BORS_CODAL_OFFLINE"] = "1"
os.environ["BORS_NO_FETCH_LOOPS"] = "1"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)

from fastapi import FastAPI                                  # noqa: E402
from fastapi.testclient import TestClient                     # noqa: E402

import api._core as CORE                                     # noqa: E402
import api.fundamental as FUND                               # noqa: E402
import codal_fetcher as CF                                   # noqa: E402
import codal_periods as CP                                   # noqa: E402
import codal_units as CU                                     # noqa: E402
import fts_engine as FE                                      # noqa: E402

PASS = FAIL = 0


def ck(cond, label, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("ok   %s" % label)
    else:
        FAIL += 1
        print("FAIL %s %s" % (label, str(detail)[:170]))
    return bool(cond)


# ── ۱) بستر: بانکِ موقت با اسکیماِ خودِ تولیدی ──────────────────────────────
TMP = tempfile.mkdtemp(prefix="bors_fund_api_")
DB = os.path.join(TMP, "market.db")

_TITLES = {
    "annual": "صورت‌های مالی  سال مالی منتهی به ۱۴۰۳/۱۲/۲۹ (حسابرسی شده)",
    "annual_new": "صورت‌های مالی  سال مالی منتهی به ۱۴۰۴/۱۲/۲۹ (حسابرسی شده)",
}


def _build_db():
    c = sqlite3.connect(DB)
    CF.create_schema(c)
    CF.migrate_schema(c)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS instruments (
            ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT,
            sector_name TEXT, updated_at TEXT, total_shares REAL);
        CREATE TABLE IF NOT EXISTS market_watch (
            ins_code TEXT, symbol TEXT, d_even TEXT, market_cap REAL,
            market_cap_src TEXT, allowed_min REAL, allowed_max REAL,
            p_closing REAL);
        CREATE TABLE IF NOT EXISTS daily_prices (
            ins_code TEXT, d_even TEXT, market_cap REAL, market_cap_src TEXT);
        """)
    # خودروآزمون: کامل — سه سال صورتِ مالی + ماهانه با مخرج + ارزشِ بازارِ تابلو
    # بی‌ماههآزمون: فقط صورتِ مالی (شاخص ۱ باید بگوید «قابل محاسبه نبود»)
    # بی‌تابلوآزمون: ماهانه دارد ولی ردیفِ market_watch ندارد (شاخص ۴ data_gap)
    c.executemany("INSERT INTO instruments (ins_code,l_val18,l_val30,sector_name,updated_at)"
                  " VALUES (?,?,?,?,?)",
                  [("X1", "خودروآزمون", "خودروآزمون", "خودروساز", "2026-10-16"),
                   ("X2", "بی‌ماههآزمون", "بی‌ماههآزمون", "سایر", "2026-10-16"),
                   ("X3", "بی‌تابلوآزمون", "بی‌تابلوآزمون", "سایر", "2026-10-16")])
    c.executemany("INSERT INTO market_watch (ins_code,symbol,d_even,market_cap,"
                  "market_cap_src,allowed_min,allowed_max) VALUES (?,?,?,?,?,?,?)",
                  [("X1", "خودروآزمون", "14050725", 5_000_000_000_000.0,
                    "tse_raw", 1.0, 9000.0)])
    fs = []
    for y, tno, rev in ((1402, 1001, 6_000_000.0), (1403, 1002, 9_000_000.0),
                        (1404, 1003, 12_000_000.0)):
        pe = "140%d/12/29" % (y - 1400)
        fs.append((tno, "خودروآزمون", "شرکت آزمون خودرویی (پ.س.)", _TITLES["annual"],
                   pe, rev, rev * 0.25, rev * 0.12, rev * 0.08, 40_000_000.0,
                   25_000_000.0, 1_200_000.0, 2_000.0, "میلیون ریال"))
    for tno, sym, rev in ((1004, "بی‌ماههآزمون", 4_000_000.0),
                          (1005, "بی‌تابلوآزمون", 3_000_000.0)):
        fs.append((tno, sym, "شرکت آزمون %s (پ.س.)" % sym, _TITLES["annual_new"],
                   "1404/12/29", rev, rev * 0.30, rev * 0.15, rev * 0.10,
                   10_000_000.0, 6_000_000.0, 1_000_000.0, 1_500.0, "میلیون ریال"))
    c.executemany("INSERT INTO financial_statements (tracing_no,symbol,company_name,"
                  "title,period_end,revenue,gross_profit,operating_profit,net_profit,"
                  "total_assets,total_equity,capital,basic_eps,unit)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", fs)
    ms = []
    for m in (10, 11, 12):
        tno = 2000 + m
        ms.append((tno, "خودروآزمون", "گزارش فعالیت ماهانه", "1404/0%d/31" % m if m < 10
                   else "1404/%02d/31" % m, 1404, m, 1_400_000.0, 1_400_000.0 * m,
                   900_000.0, 900_000.0 * m))
        ms.append((tno + 100, "بی‌تابلوآزمون", "گزارش فعالیت ماهانه",
                   "1404/%02d/31" % m, 1404, m, 500_000.0, 500_000.0 * m,
                   400_000.0, 400_000.0 * m))
    c.executemany("INSERT INTO monthly_sales (tracing_no,symbol,title,period_end,year,"
                  "month,monthly_revenue,ytd_revenue,monthly_revenue_prev,ytd_revenue_prev)"
                  " VALUES (?,?,?,?,?,?,?,?,?,?)", ms)
    c.commit()
    return c


CONN = _build_db()
CONN.close()

# درزهایِ اتصال: اندپوینت‌ها DB_PATH را از bors_config در namespace خود نگه می‌دارند
CORE.DB_PATH = DB
FUND.DB_PATH = DB

app = FastAPI()
app.include_router(FUND.router)
client = TestClient(app, raise_server_exceptions=False)


# ── ۲) سنجه‌ها (قابلِ استفادۀ دوباره برایِ دام‌هایِ منفی) ───────────────────
CARD_REQUIRED_TOP = ["status", "symbol", "score", "verdict", "applicable", "passes",
                     "indicators", "profile", "metrics", "data_gaps", "thresholds",
                     "history", "fs_count"]
HEALTH_REQUIRED_TOP = ["queue", "instruments", "dirty_symbols", "incomplete_extractions",
                       "undated_notices", "data_epoch", "last_data_update",
                       "last_successful_sync", "last_attempt", "offline_gate",
                       "worker", "lock", "catchup", "cadence"]


def check_card_provenance(body):
    """ردپا پس از JSON‌سازی زنده مانده؟ (منبع + واحد + شناسۀ اطلاعیه)"""
    ind = body.get("indicators") or {}
    i1 = (ind.get("1") or {}).get("monetary") or {}
    i3 = ind.get("3") or {}
    if not (str(i1.get("source") or "").strip() and "unit" in i1
            and str(i1.get("unit_note") or "").strip()):
        return False
    if i3.get("margin_pct") is not None and i3.get("ref_tracing_no") is None:
        return False
    if i3.get("unit") is not None and i3.get("unit") not in CU.SCALES:
        return False
    return True


def check_gap_is_not_zero(body):
    """شاخصِ بی‌داده باید None+data_gap باشد، نه صفرِ قطعی."""
    i1 = ((body.get("indicators") or {}).get("1") or {}).get("monetary") or {}
    return (i1.get("data_gap") is True and i1.get("monetary_pct") is None
            and bool(str(i1.get("reason") or "").strip()))


def check_route_registered(registered, path):
    return path in registered


def registered_paths(app):
    """جدولِ مسیرهایِ واقعیِ همان اپ — از selfِ فریم‌ورک، نه از متنِ فایل.

    `app.routes` در این نسخۀ Starlette هر routerِ الحاق‌شده را یکِ شی می‌کند
    (نه یکِ مسیرِ باز)، پس شمارۀ مسیر از `openapi()` خوانده می‌شود؛ همان چیزی
    که اگر مسیر ثبت نشده باشد، آن را ندارد.
    """
    try:
        return set((app.openapi() or {}).get("paths", {}))
    except Exception:
        return set()


# ── ۳) کارت بنیادی روی HTTP ─────────────────────────────────────────────────
print("\n── ۳) کارت بنیادی روی لایۀ HTTP ──")
r = client.get("/api/fundamental/خودروآزمون")
ck(r.status_code == 200, "A1 کارت روی HTTP بیست‌ام می‌دهد", r.status_code)
card = r.json() if r.status_code == 200 else {}
ck(card.get("status") == "success", "A2 پاسخ با status: success می‌آید", card.get("status"))
ind = card.get("indicators") or {}
ck(all(k in ind and isinstance(ind[k], dict) for k in ("1", "2", "3", "4", "5")),
   "A3 هر پنج شاخص در پاسخ هستند", sorted(ind.keys()))
three = [v for v in card.get("passes", {}).values() if v in (True, False, None)]
ck(len(three) == len(card.get("passes", {})),
   "A4 رأی‌ها سه‌حالۀ واقعی‌اند (هیچ خانۀ دیگری جا نمی‌شود)",
   card.get("passes"))
ck(check_card_provenance(card),
   "A5 ردپایِ منبع/واحد/شمارۀِ ردّ پس از JSON زنده می‌ماند",
   json.dumps(ind.get("1", {}), ensure_ascii=False)[:150])
src_ui = open(os.path.join(ROOT, "frontend/src/features/fundamental/api/useFtsCard.ts"),
              encoding="utf-8").read()
missing_ui = [k for k in CARD_REQUIRED_TOP if ('%s:' % k) not in src_ui]
missing_api = [k for k in CARD_REQUIRED_TOP if k not in card]
ck(not missing_ui and not missing_api,
   "A6 خانۀ لازمِ FtsCardSchema هم در پاسخ هست هم در schemaِ رابط",
   {"in_response": missing_api, "in_ui_schema": missing_ui})
m = card.get("metrics") or {}
ck(m.get("mcap") and m.get("mcap_source") and m.get("mcap_hmt"),
   "A7 ارزشِ بازار با منبعش می‌آید (ضربِ دستی در کار نیست)",
   {k: m.get(k) for k in ("mcap", "mcap_source", "mcap_hmt")})

# غایب ≠ صفر، روی دو سناریویِ جدا
r2 = client.get("/api/fundamental/بی‌ماههآزمون")
c2 = r2.json() if r2.status_code == 200 else {}
ck(r2.status_code == 200 and check_gap_is_not_zero(c2),
   "B1 نبودِ گزارشِ ماهانه = null + data_gap، نه صفر و نه رأیِ ساختگی",
   json.dumps(((c2.get("indicators") or {}).get("1") or {}).get("monetary") or {},
              ensure_ascii=False)[:170])
g1 = ((c2.get("indicators") or {}).get("1") or {}).get("monetary") or {}
ck(bool(str(g1.get("remediation") or "").strip()),
   "B2 کارِ قابل‌انجام هم در پاسخ است (remediation)، نه فقط علتِ شکست",
   g1.get("remediation"))

r3 = client.get("/api/fundamental/بی‌تابلوآزمون")
c3 = r3.json() if r3.status_code == 200 else {}
v4 = (c3.get("indicators") or {}).get("4") or {}
ck(r3.status_code == 200 and v4.get("data_gap") is True
   and v4.get("sales_to_mcap") is None and (c3.get("metrics") or {}).get("sales_to_mcap") is None,
   "B3 بی‌ارزشِ بازار = شاخصِ قابل‌محاسبه‌نبود، نه «بازارِ صفر»",
   {k: v4.get(k) for k in ("data_gap", "sales_to_mcap", "available", "reason")})
ck("تابلو" in str(v4.get("reason") or ""),
   "B4 علتِ شاخص ۴ به منبعِ درست (تابلو) برمی‌گردد، نه گزارشِ ماهانه",
   str(v4.get("reason"))[:120])

r4 = client.get("/api/fundamental/نمادِ-وجود-ندارد")
ck(r4.status_code == 404,
   "B5 نمادِ ناشناخته ۴۰۴ می‌دهد (نه ۵۰۰، نه successِ تهی)",
   (r4.status_code, str(r4.text)[:80]))

# ── ۴) سلامتِ خطِ کدال روی HTTP ─────────────────────────────────────────────
print("\n── ۴) سلامتِ خطِ کدال روی لایۀ HTTP ──")
REGISTERED = registered_paths(app)
ck(check_route_registered(REGISTERED, "/api/sync/codal/pipeline")
   and check_route_registered(REGISTERED, "/api/fundamental/{symbol}"),
   "C1 اندپوینت‌ها در جدولِ مسیرهایِ واقعیِ اپ ثبت‌اند (نه در متنِ فایل)",
   sorted(REGISTERED))
h = client.get("/api/sync/codal/pipeline")
ck(h.status_code == 200, "C2 سلامت بیست‌ام می‌دهد", h.status_code)
hb = h.json() if h.status_code == 200 else {}
ck(hb.get("status") != "error", "C3 سلامت خطا گزارش نمی‌کند", hb.get("message"))
miss = [k for k in HEALTH_REQUIRED_TOP if k not in hb]
src_health = open(os.path.join(ROOT, "frontend/src/features/fundamental/api/useCodalHealth.ts"),
                  encoding="utf-8").read()
miss_ui = [k for k in HEALTH_REQUIRED_TOP if ('%s:' % k) not in src_health]
ck(not miss and not miss_ui, "C4 هر خانۀ schemaِ رابط در پاسخ هست",
   {"in_response": miss, "in_ui_schema": miss_ui})
q = hb.get("queue") or {}
ck(isinstance(q.get("total"), (int, float)) and q.get("done", 0) == 0,
   "C5 شمارنده‌ها از جدولِ کار می‌آیند (بانکِ تازه = هیچ کاری انجام نشده)", q)

# دو دورۀ ثبت‌شده: پاک، سپس خطا‌دار. «موفق» باید همان پاک بماند.
c = sqlite3.connect(DB)
c.execute("INSERT INTO pipeline_runs (cycle, worker, started_at, finished_at,"
          " processed, done, failed) VALUES ('discovery','w1',"
          "'2026-10-16T08:00:00','2026-10-16T08:00:05',4,4,0)")
c.commit()
c.close()
h_ok = client.get("/api/sync/codal/pipeline").json()
ck((h_ok.get("last_successful_sync") or {}).get("at") == "2026-10-16T08:00:05",
   "C6a چرخۀ پاک «آخرین همگام‌سازیِ موفق» می‌سازد", h_ok.get("last_successful_sync"))

c = sqlite3.connect(DB)
c.execute("INSERT INTO pipeline_runs (cycle, worker, started_at, finished_at,"
          " processed, done, failed, error) VALUES ('discovery','w2',"
          "'2026-10-16T09:00:00','2026-10-16T09:00:09',0,0,1,'429 blocked')")
c.commit()
c.close()
h2 = client.get("/api/sync/codal/pipeline").json()
ck((h2.get("last_successful_sync") or {}).get("at") == "2026-10-16T08:00:05",
   "C6b چرخۀ خطا‌دار جایگزینِ «موفق» نمی‌شود و آن را نمی‌پاشد",
   {"last_ok": h2.get("last_successful_sync"), "last_attempt": (h2.get("last_attempt") or {}).get("started_at")})
ck((h2.get("last_attempt") or {}).get("error") == "429 blocked",
   "C6c خطای آخرین تلاش درِ پاسخ می‌ماند (بی‌صدا موفق نمی‌شود)",
   h2.get("last_attempt"))
ck((h2.get("queue") or {}).get("failed", 0) >= 0 and (h2.get("catchup") or {}).get("failed", 0) >= 0,
   "C7 شمارشِ کارِ شکست‌خورده در پاسخ می‌ماند (صف و catchup هر دو)",
   {"queue": h2.get("queue"), "catchup": h2.get("catchup")})

# data_epoch = امضایِ تازگی که UI کشِ کارت را با آن می‌بَرد
epoch_before = h2.get("data_epoch")
c = sqlite3.connect(DB)
c.execute("INSERT INTO financial_statements (tracing_no,symbol,company_name,title,"
          "period_end,revenue,gross_profit,net_profit,total_equity,basic_eps,unit)"
          " VALUES (9100,'خودروآزمون','شرکت آزمون خودرویی (پ.س.)',?,"
          "'1405/06/31',15000000.0,4000000.0,1200000.0,26000000.0,2500.0,'میلیون ریال')",
          (_TITLES["annual_new"],))
c.commit()
c.close()
h3 = client.get("/api/sync/codal/pipeline").json()
ck(bool(epoch_before) and h3.get("data_epoch") != epoch_before,
   "C8 با عوض‌شدنِ دادهٔ صورتِ مالی، امضایِ تازگی عوض می‌شود",
   (epoch_before, h3.get("data_epoch")))

# «بی‌دوره» = شمارِ ردیف‌هایِ بی‌دوره، نه تعدادِ کلیدهای دیکشنریِ شمارش
c = sqlite3.connect(DB)
c.execute("INSERT INTO financial_statements (tracing_no,symbol,company_name,title,"
          "period_end,revenue,unit) VALUES (9200,'بی‌تاریخآزمون','شرکت بی‌تاریخ',"
          "?,NULL,700000.0,'میلیون ریال')", (_TITLES["annual_new"],))
c.commit()
want_und = c.execute("SELECT (SELECT COUNT(*) FROM financial_statements WHERE %s)"
                     " + (SELECT COUNT(*) FROM monthly_sales WHERE %s)"
                     % (CP.UNDATED_SQL, CP.UNDATED_SQL)).fetchone()[0]
dict_len = len(CP.undated_counts(c))
c.close()
h4 = client.get("/api/sync/codal/pipeline").json()
ck(h4.get("undated_notices") == want_und == 1,
   "C9 شمارشِ «بی‌دورۀ» HTTP == شمارِ ردیف‌ها (یکِ ردیفِ کارگذاری‌شده)",
   (h4.get("undated_notices"), want_und, dict_len))

# ── ۵) دام‌هایِ منفی: سنسور کور نیست ────────────────────────────────────────
print("\n── ۵) دام‌هایِ منفی ──")
# هر دام باید نشان دهد سنجشِ مربوطه بینِ پاسخِ سالم و پاسخِ معیوب فرق می‌گذارد؛
# سبزشدنِ بی‌تکیه برِ طرفِ سالم، خودش همان کوریِ سنسور است که گاردِ پیشین داشت.
broken = json.loads(json.dumps(card))
broken["indicators"]["3"]["margin_pct"] = 12.5
broken["indicators"]["3"]["ref_tracing_no"] = None
broken["indicators"]["1"]["monetary"]["source"] = ""
ck(check_card_provenance(card) and not check_card_provenance(broken),
   "N1 اگر ردفا بیفتد، A5 قرمز می‌شود (سنسورِ ردپا کور نیست)")
fake0 = json.loads(json.dumps(c2))
fake0["indicators"]["1"]["monetary"]["monetary_pct"] = 0.0
fake0["indicators"]["1"]["monetary"]["data_gap"] = False
ck(check_gap_is_not_zero(c2) and not check_gap_is_not_zero(fake0),
   "N2 اگر غایب به صفر تبدیل شود، B1 قرمز می‌شود (سنسورِ غایب کور نیست)")
ck(not check_route_registered(REGISTERED, "/api/sync/codal/نیامد"),
   "N3 مسیرِ ثبت‌نشده رد می‌شود (C1 با هر رشته‌ای سبز نمی‌ماند)")
same_a = client.get("/api/sync/codal/pipeline").json().get("data_epoch")
same_b = client.get("/api/sync/codal/pipeline").json().get("data_epoch")
ck(same_a == same_b,
   "N4 بی‌نوشتن، امضا ثابت می‌ماند (C8 از شانس سبز نمی‌شود)", (same_a, same_b))

print("\ncodal_api_contract_v1115: %d passed / %d failed" % (PASS, FAIL))
sys.exit(1 if FAIL else 0)
