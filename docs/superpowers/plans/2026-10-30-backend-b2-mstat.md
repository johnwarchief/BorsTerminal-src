# B2-1 — پورتِ پنل‌هایِ «وضعیت بازار» به Go

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** یازده مسیرِ GETِ `/api/mstat/*` را با همان بدنۀ پایتون پورت کن؛ اعداد Δ=۰، رشته‌هایِ فاز عیناً یکسان، POST همچنان ۵۰۱.

**Architecture:** یک بستۀ `internal/mstat` که از `market.db` یک اسنپ‌شاتِ واحد می‌خواند، همان `enrich/_agg`هایِ `mstat_engine.py` را می‌سازد و هر پنل رویِ همان اسنپ‌شات محاسبه می‌شود. کشِ هر-حالت با TTL ۴۵ ثانیه، سقفِ کهنگیِ ۹۰ ثانیه، stale-while-revalidate و تک‌پروازگی — عیناً همان `_mstat_call`. مسیرها در `internal/httpapi` ثبت می‌شوند و `main` سرویس را سیم‌کشی می‌کند.

**Tech Stack:** Go 1.26، `modernc.org/sqlite`، `compress/zlib` + `encoding/base64` برایِ blobِ نقاطِ تایم‌لاین، و `strconv.FormatFloat` برایِ گردکردنِ `round()`ِ پایتون.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md` (§۸ مرحلۀ B2). این پلن نیمۀ اولِ B2 است: یازده پنل. نیمۀ دوم (B2-2) = `smart-money` + `board` و گیتِ نهاییِ ۱۳ مسیر. `mainwatch` در این پلن است چون به منطقِ حکم وابسته نیست و فقط پرچم‌هایِ B1 را منتقل می‌کند.

## Global Constraints

- نمودارِ بیرونی ممنوع: هیچ عددی از شبکهام‌آید؛ فقط `market.db`ِ کپی‌شده. گیت رویِ کپیِ یخ‌زده اجرا می‌شود و بانکِ عملیاتی هرگز با SQLite باز نمی‌شود.
- «بی‌داده ≠ صفر»: هر جا پایتون `None` می‌دهد، Go هم `null` بدهد. هیچ صفرِ جعلی اضافه نشود.
- هر گردکردنی عیناً `round()`ِ داخلیِ پایتون است: `pyround.Round` = `strconv.FormatFloat(x,'f',n,64)` → `ParseFloat` (در B1 رویِ ۲۴٬۹۰۰ ورودی صفر اختلاف داشت). هرگز `math.Round` یا `RoundToEven(x*10^n)/10^n` جایِ آن نگذارید.
- رشته‌هایِ فارسی مو‌به‌مو از `mstat_engine.py`/`market_phase.py` کپی می‌شوند (شاملِ نیم‌فاصله، «٪»، «−» U+2212 و «…»)؛ تایپِ دستی ممنوع. گارد: طلایی‌هایِ بایت‌به‌بایت.
- ترتیبِ آرایه‌ها دادهٔ قرارداد است (ردیف‌هایِ industries، gates، red/green، not_computable، rows) و باید حفظ شود.
- هیچ نوشتنی: مسیرهایِ GET فقط می‌خوانند. `POST /api/mstat/snapshot` پورت نمی‌شود و باید همان ۵۰۱ِ B0 را بدهد.
- `gofmt -l .` خالی، `go vet ./...` پاک، `go test -count=1 ./...` سبز پیش از هر کامیت.
- کامیت‌ها فارسی و با heredoc؛ هیچ بک‌تیک در پیام. فقط فایل‌هایِ نام‌برده stage شوند.
- `_audit/FTS_TREND_COMPARE.csv` و `tools/market_state_probe.mts` هرگز stage نشوند.

---

### Task 1: فیکسچر، اوراکلِ طلایی و گارد

**Files:**
- Create: `tools/parity/make_mstat_fixture.py`
- Create: `tools/parity/gen_mstat_golden.py`
- Create: `dev/test_mstat_fixture_v1121.py`
- Create: `backend-go/internal/mstat/testdata/fixture/{market.db,user.db}` (generated)
- Create: `backend-go/internal/mstat/testdata/golden/*.json` (generated)

**Interfaces:**
- Consumes: `tools/parity/make_board_fixture.py` (ماژول؛ فیکسچرِ تابلو را می‌سازد تا `/api/market` رویِ همان بانک کار کند و پرچم‌هایِ `mainwatch` واقعی باشند).
- Produces: فیکسچرِ قطعی + طلایی‌ها با این نام‌ها:
  `s1/{summary,histogram_all,histogram_eq_all,thermometer_all,thermometer_eq_all,depth_all,depth_eq_all,clientsplit_all,clientsplit_fixed,market_snapshot,phase,industries,timeline_cum,timeline_inst,phases,mainwatch_default,mainwatch_val}.json`
  `s2` (تایم‌لاینِ کهنه) فقط `timeline_cum.json` و `phases.json`؛ `s3` (بی‌وضعیتِ رسمی) فقط `phase.json` و `s4` (تعطیلی) فقط `phase.json`.

- [ ] **Step 1: Write the fixture builder**

فیکسچرِ B1 را می‌سازد و رویش چهار چیز اضافه می‌کند: ستون‌هایِ گم‌شدۀ `market_watch/instruments/client_type/daily_prices`، نه ردیفِ مخصوصِ mstat، و چهار جدولِ `market_index`/`market_totals`/`market_liquidity`/`mstat_snap`. نه ردیفِ mstat با اعدادِ دست‌حساب‌شدنی (جدولِ `EXTRA`).

```python
#!/usr/bin/env python
"""فیکسچرِ «وضعیت بازار» برایِ پورتِ Go — رویِ فیکسچرِ تابلو ساخته می‌شود.

چرا رویِ فیکسچرِ تابلو: `mainwatch` پرچم‌هایِ هفت‌گانه را از ردیف‌هایِ
`/api/market` می‌گیرد؛ اگر آن مسیر رویِ این بانک کار نکند، پرچم‌ها «unavailable»
می‌شود و پاریتیِ واقعی سنجیده نمی‌شود. پس همان DDL و seedِ B1 پایه است و فقط
ستون‌هایِ گم‌شده و جدول‌هایِ mstat رویش می‌نشیند.

خروجی: backend-go/internal/mstat/testdata/fixture/{market.db,user.db}
هیچ دادهٔ واقعی در آن نیست.
"""
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "parity"))
OUT = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
DAY = 20261014

# ستون‌هایِ market_watch که کوئریِ mstat می‌خواند و فیکسچرِ تابلو ندارد.
MW_ADD = [("total_shares", "REAL")]
INS_ADD = [("sector_code", "TEXT"), ("total_shares", "REAL"),
           ("base_vol", "REAL"), ("paper_type", "INTEGER")]
CT_ADD = [("buy_ddd_vol", "REAL"), ("buy_count_n", "REAL"), ("sell_count_n", "REAL")]
DP_ADD = [("q_tot_cap", "REAL")]

# (کد، نماد، نام، paper_type، صنعت، پایانی، دیروز، آخرین، حجم، ارزش، معاملات،
#  مبنا، تعدادِ سهام، کمینه/بیشینه/مجاز، عمقِ خرید(حجم،ارزش,تعداد)، عمقِ فروش)
# هر ردیف یک قاعدهٔ mstat را قفل می‌کند:
#  m1 فولاد   → +۱۱٫۱۱٪، صفِ خریدِ خالص، clock_pct منفی
#  m2 وبملت   → صفرِ واقعی، عمقِ دوطرفه
#  m3 حق‌تقدم → −۳٪ با صفِ فروش
#  m4 ص.سهامی → صفر، صفِ خرید
#  m5 ص.ثابت  → صفر، صفِ فروش
#  m6 اهرمی   → صفر، صفِ خرید
#  m7 طلا     → صفر، صفِ فروش
#  m8 نقره    → صفر، صفِ خرید
#  m9 اختیار  → کلاسِ other، حجمِ صفر (معامله‌نشده)
EXTRA = [
    ("m1", "فولاد۲", "شرکت فولاد دوم", 1, "فلزات اساسي", 1000.0, 900.0, 950.0,
     1e9, 1e13, 500.0, 1.0, 1e9, 900.0, 1100.0, 2e6, 2e9, 3.0, 0.0, 0.0, 0.0),
    ("m2", "وبملت۲", "بانك ملي دوم", 1, "بانكها و موسسات اعتباري", 500.0, 500.0, 505.0,
     2e9, 1e12, 100.0, 1.0, 5e8, 450.0, 550.0, 1e6, 5e8, 2.0, 1e6, 5e8, 1.0),
    ("m3", "حقا۲", "حق تقدم دوم", 4, "سرمایه گذاريها", 970.0, 1000.0, 960.0,
     1e8, 1e11, 10.0, 1.0, 1e8, 900.0, 1030.0, 0.0, 0.0, 0.0, 5e7, 5e10, 4.0),
    ("m4", "اوج۲", "صندوق س.اوج دماوند-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m5", "دينا۲", "صندوق س.درآمد ثابت دينا-د", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     0.0, 0.0, 0.0, 1e6, 1e9, 1.0),
    ("m6", "اهرم۲", "صندوق اهرم آگاه-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m7", "گلگشت۲", "صندوق سرمايه گذاري طلا گلگشت", 8,
     "صندوق سرمايه گذاري قابل معامله", 1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0,
     1.0, 1e8, 900.0, 1100.0, 0.0, 0.0, 0.0, 1e6, 1e9, 1.0),
    ("m8", "نقره۲", "صندوق نقره-س", 8, "صندوق سرمايه گذاري قابل معامله",
     1000.0, 1000.0, 1000.0, 1e8, 1e11, 5.0, 1.0, 1e8, 900.0, 1100.0,
     1e6, 1e9, 1.0, 0.0, 0.0, 0.0),
    ("m9", "ضهرم۲", "اختيارخ اهرم-۲", 6, "صندوق سرمايه گذاري قابل معامله",
     0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 1e8, 0.0, 0.0,
     0.0, 0.0, 0.0, 0.0, 0.0, 0.0),
]

# ارزشِ ریالیِ مبدأ (client_type_value) — فقط m1 و m3 «native» دارند تا هر سه
# حالتِ value_source پوشش بگیرد: m1 کامل native، m3 نیمه (mixed)، m2 هیچ.
CTV = [("m1", DAY, "native", 2e12, 5e11, 1e12, 2e11),
       ("m3", DAY, "native", 5e10, None, None, None)]

# (buy_i, buy_n, sell_i, sell_n, count_i, count_n, sell_count_i, sell_count_n)
CT = [("m1", 2e8, 5e7, 1e8, 2e7, 1000, 4, 1000, 3),
      ("m2", 1e8, 1e8, 2e8, 1e8, 200, 5, 400, 6),
      ("m3", 5e6, 0.0, 1e6, 0.0, 10, 0, 5, 0),
      ("m4", 4e6, 1e6, 2e6, 1e6, 20, 1, 10, 1),
      ("m5", 1e7, 9e7, 5e6, 8e7, 30, 2, 15, 2),
      ("m6", 3e6, 1e6, 4e6, 1e6, 12, 1, 8, 1),
      ("m7", 2e6, 2e6, 1e6, 1e6, 8, 1, 4, 1),
      ("m8", 1e6, 1e6, 1e6, 1e6, 5, 1, 5, 1),
      ("m9", 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0)]

# ارزشِ بازارِ رسمی: روزِ جاری زیرِ نصفِ تخمینِ تابلو است تا «رد شدن» آزموده شود؛
# روزِ قبل باورپذیر است. (ر.ک. market_total_rials)
TOTALS = [(DAY, 1e12), (20261013, 6.9e13)]

# ارزشِ معاملاتِ چند نشستِ اخیر (همت) — مبنایِ تداومِ سه‌نشستی.
LIQ = [(20261012, 9.5), (20261013, 12.0), (DAY, 18.0)]


def build_board_fixture(tmp):
    """فیکسچرِ B1 را در پوشۀ موقت می‌سازد و مسیرش را برمی‌گرداند."""
    import make_board_fixture as MBF
    MBF.OUT = tmp
    assert MBF.main() == 0
    return os.path.join(tmp, "market.db")


def add_columns(con, table, cols):
    have = {r[1] for r in con.execute("PRAGMA table_info(%s)" % table)}
    for name, typ in cols:
        if name not in have:
            con.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, typ))


def extend(con):
    for table, cols in (("market_watch", MW_ADD), ("instruments", INS_ADD),
                        ("client_type", CT_ADD), ("daily_prices", DP_ADD)):
        add_columns(con, table, cols)
    con.execute("CREATE TABLE market_index (d_even INTEGER PRIMARY KEY, idx_last REAL,"
                " idx_change REAL, idx_pct REAL, ew_last REAL, ew_change REAL,"
                " ew_pct REAL, z_tot_tran REAL, q_tot_cap REAL, q_tot_tran REAL,"
                " updated_at TEXT, market_state TEXT, market_state_title TEXT,"
                " activity_h_even INTEGER)")
    con.execute("CREATE TABLE market_totals (d_even INTEGER PRIMARY KEY,"
                " market_value REAL)")
    con.execute("CREATE TABLE market_liquidity (d_even INTEGER PRIMARY KEY,"
                " value_hemat REAL)")
    con.execute("CREATE TABLE mstat_snap (d_even INTEGER NOT NULL,"
                " h_even INTEGER NOT NULL, ts TEXT, agg TEXT,"
                " PRIMARY KEY (d_even, h_even))")
    # شاخصِ رسمی: نشستِ بستهٔ دیروز (۲۰۲۶۱۰۱۴ چهارشنبه است)؛ وضعیت F = بسته.
    con.execute("INSERT INTO market_index VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (DAY, 7153088.29, -103912.4, -1.43, 1929823.43, -9112.1, -0.47,
                 1.2e5, 6.4e13, 3.1e9, "2026-10-14 12:30:00", "F", "بسته",
                 123000))
    for d, v in TOTALS:
        con.execute("INSERT INTO market_totals VALUES (?,?)", (d, v))
    for d, v in LIQ:
        con.execute("INSERT INTO market_liquidity VALUES (?,?)", (d, v))
    # یک زیرساخت برایِ هر ردیفِ mstat، تا هر جفت‌کردن/پنجره سطر داشته باشد.
    for i, (ic, sym, nm, pt, sec, pcl, py, plst, vol, val, nt, bv, ts,
            amin, amax, bqv, bqval, bqcnt, sqv, sqval, sqcnt) in enumerate(EXTRA):
        con.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, sector_code,"
                    " sector_name, total_shares, base_vol, paper_type, updated_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?)",
                    (ic, sym, nm, "01" if pt != 8 else "68", sec, ts, bv, pt, "f"))
        con.execute("INSERT INTO market_watch (ins_code, d_even, h_even, p_closing,"
                    " p_last, price_yesterday, price_min, price_max, allowed_min,"
                    " allowed_max, price_first, q_tot_tran, q_tot_cap, z_tot_tran,"
                    " price_change, total_shares, buy_q_vol, buy_q_val, buy_q_cnt,"
                    " sell_q_vol, sell_q_val, sell_q_cnt, buy_q1_vol, buy_q1_px,"
                    " sell_q1_vol, sell_q1_px, buy_q1_cnt, fetched_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ic, DAY, 123000, pcl, plst, py, amin, amax, amin, amax, py,
                     vol, val, nt, pcl - py, ts, bqv, bqval, bqcnt, sqv, sqval,
                     sqcnt, 1e6, pcl, 1e6, pcl, 1.0, "f"))
        con.execute("INSERT INTO client_type VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (ic, DAY, *CT[i][1:5], 0.0, *CT[i][5:], "f"))
        # پیشینهٔ چهار نشست برایِ برآوردِ حجمِ مبنا (فقط m2 مبنا دارد).
        if ic == "m2":
            for d in (20261010, 20261011, 20261012, 20261013):
                con.execute("INSERT INTO daily_prices (ins_code, d_even, p_closing,"
                            " q_tot_tran, q_tot_cap) VALUES (?,?,?,?,?)",
                            (ic, d, 500.0, 1.5e9, 7.5e11))
    for ic, d, kind, *vals in CTV:
        con.execute("INSERT INTO client_type_value (ins_code, d_even, kind, buy_i_val,"
                    " buy_n_val, sell_i_val, sell_n_val) VALUES (?,?,?,?,?,?,?)",
                    (ic, d, kind, *vals))
    con.commit()


def seed_snaps(con, day=DAY, stale=False):
    """سه نقطۀ تایم‌لاین با وضعیتِ تک‌حرفی؛ دو نقطۀ آخر یک چرخش دارند."""
    import base64
    import json
    import zlib

    def blob(states):
        raw = json.dumps(states, separators=(",", ":")).encode()
        return base64.b64encode(zlib.compress(raw, 6)).decode()

    snap_day = day - 1 if stale else day
    pts = [
        (100000, {"val_bt": 10.0, "flow_eq_bt": 1.0, "flow_fixed_bt": -0.5, "pos": 4,
                  "neg": 3, "bq_bt": 2.0, "sq_bt": 1.0, "pc_buy": 120.0,
                  "pc_sell": 100.0, "bq_n": 2, "sq_n": 1, "st": blob({"m1": "b", "m2": "p"})}),
        (110000, {"val_bt": 20.0, "flow_eq_bt": 2.0, "flow_fixed_bt": -0.8, "pos": 5,
                  "neg": 2, "bq_bt": 3.0, "sq_bt": 1.5, "pc_buy": 130.0,
                  "pc_sell": 105.0, "bq_n": 3, "sq_n": 1, "st": blob({"m1": "s", "m2": "p"})}),
        (120000, {"val_bt": 30.0, "flow_eq_bt": 3.0, "flow_fixed_bt": -1.0, "pos": 6,
                  "neg": 1, "bq_bt": 4.0, "sq_bt": 2.0, "pc_buy": 140.0,
                  "pc_sell": 110.0, "bq_n": 4, "sq_n": 1, "st": blob({"m1": "s", "m2": "b"})}),
    ]
    for h, agg in pts:
        agg = dict(agg, d_even=snap_day, h_even=h)
        con.execute("INSERT INTO mstat_snap VALUES (?,?,?,?)",
                    (snap_day, h, "2026-10-14 %02d:%02d:00" % (h // 10000, (h // 100) % 100),
                     json.dumps(agg, separators=(",", ":"), ensure_ascii=False)))
    con.commit()


def main() -> int:
    import shutil
    import tempfile
    tmp = tempfile.mkdtemp(prefix="bors-mstat-fix-")
    try:
        build_board_fixture(tmp)
        con = sqlite3.connect(os.path.join(tmp, "market.db"))
        try:
            extend(con)
            seed_snaps(con)
        finally:
            con.close()
        os.makedirs(OUT, exist_ok=True)
        for name in ("market.db", "user.db"):
            shutil.copy2(os.path.join(tmp, name), os.path.join(OUT, name))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("mstat fixture ->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run it and check the fixture is deterministic**

Run: `PYTHONIOENCODING=utf-8 python tools/parity/make_mstat_fixture.py && sha256sum backend-go/internal/mstat/testdata/fixture/*.db`
Run it twice; the hashes must be identical (SQLite file bytes are deterministic for the same insert order; the user.db comes from the B1 builder, also deterministic).

Expected: two identical hash pairs.

- [ ] **Step 3: Write the golden oracle**

```python
#!/usr/bin/env python
"""اوراکلِ طلاییِ B2: بدنۀ واقعیِ پایتونِ پنل‌ها رویِ فیکسچر، برایِ تستِ Go.

ساعت تزریق می‌شود: تنها ورودیِ دیواریِ پنل‌ها `market_phase.from_db` است؛
`clock_now` هم در طلایی ثابت می‌ماند تا تستِ Go با همان لحظه بسنجد.
خروجی: backend-go/internal/mstat/testdata/golden/<scenario>/<route>.json
"""
import datetime
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIX = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
OUT = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "golden")
PIN = datetime.datetime(2026, 10, 28, 10, 30, 0)   # چهارشنبه، ۱۰:۳۰ تهران


class _Date(datetime.date):
    @classmethod
    def today(cls):
        return cls(PIN.year, PIN.month, PIN.day)


class _DateTime(datetime.datetime):
    @classmethod
    def now(cls, tz=None):
        return PIN


class _DT:
    date, datetime, time, timedelta = _Date, _DateTime, datetime.time, datetime.timedelta


def scenario(name, sql=()):
    """کپیِ فیکسچر + تغییراتِ صحنه، سپس بدنه‌هایِ پایتون."""
    tmp = tempfile.mkdtemp(prefix="bors-b2-golden-")
    for f in ("market.db", "user.db"):
        shutil.copy2(os.path.join(FIX, f), os.path.join(tmp, f))
    os.environ["BORS_DATA_DIR"] = tmp
    os.environ["BORS_NO_FETCH_LOOPS"] = "1"
    os.environ["BORS_CODAL_OFFLINE"] = "1"
    os.environ["BORS_CODAL_AUTO"] = "0"
    sys.path.insert(0, ROOT)
    import sqlite3
    con = sqlite3.connect(os.path.join(tmp, "market.db"))
    for stmt, args in sql:
        con.execute(stmt, args)
    con.commit()
    con.close()

    import market_phase as MP
    MP.datetime = _DT
    import api.market_status as MS
    MS._MSTAT_CACHE.clear()
    d = os.path.join(OUT, name)
    os.makedirs(d, exist_ok=True)

    def save(fname, obj):
        with open(os.path.join(d, fname), "w", encoding="utf-8", newline="\n") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")
        print(name, fname, len(json.dumps(obj, ensure_ascii=False)), "chars")

    save("summary.json", MS.mstat_summary())
    for g in ("all", "eq_all"):
        save("histogram_%s.json" % g, MS.mstat_histogram(group=g))
        save("thermometer_%s.json" % g, MS.mstat_thermometer(group=g))
        save("depth_%s.json" % g, MS.mstat_depth(group=g))
    for tab in ("all", "fixed"):
        save("clientsplit_%s.json" % tab, MS.mstat_clientsplit(tab=tab))
    save("market_snapshot.json", MS.mstat_market_snapshot())
    save("phase.json", MS.mstat_phase())
    save("industries.json", MS.mstat_industries())
    for mode in ("cum", "inst"):
        save("timeline_%s.json" % mode, MS.mstat_timeline(mode=mode))
    save("phases.json", MS.mstat_phases())
    save("mainwatch_default.json", MS.mstat_mainwatch())
    save("mainwatch_val.json", MS.mstat_mainwatch(sort="val", desc=False, limit=5))
    shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    import importlib
    # صحنهٔ ۱: پایه.
    scenario("s1")
    # صحنهٔ ۲: تایم‌لاینِ کهنه — نقطه‌هایِ mstat_snap از دیروز.
    importlib.reload(__import__("api.market_status", fromlist=["x"]))
    scenario("s2", [("UPDATE mstat_snap SET d_even = d_even - 1", ())])
    # صحنهٔ ۳: بی‌وضعیتِ رسمی — phase از تقویم می‌آید و «نامشخص» می‌شود.
    scenario("s3", [("UPDATE market_index SET market_state=NULL,"
                     " market_state_title=NULL", ())])
    # صحنهٔ ۴: تعطیلی — فعالیت رویِ جمعه اعلام شده.
    scenario("s4", [("UPDATE market_index SET d_even=20261016,"
                     " activity_h_even=123000", ())])
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**نکتهٔ اجباری:** `scenario` باید بینِ صحنه‌ها `MS._MSTAT_CACHE.clear()` کند (همان‌جا انجام می‌شود) و ماژول دوباره import شود تا `_MSTAT_BG/_MSTAT_WAIT` خالی باشند؛ `importlib.reload` در `main` برایِ همین است.

- [ ] **Step 4: Run the oracle**

Run: `PYTHONIOENCODING=utf-8 python tools/parity/gen_mstat_golden.py`
Expected: without exceptions; `backend-go/internal/mstat/testdata/golden/s1/` has 17 files؛ s2 دو فایل، s3 و s4 هرکدام یکی.

- [ ] **Step 5: Write the guard**

```python
#!/usr/bin/env python
"""گاردِ فیکسچر/طلاییِ B2 — چهار بررسی، بی‌شبکه.

۱) فیکسچر قطعی است (دو ساخت، همان sha256).
۲) طلایی‌ها با اجرایِ تازۀ اوراکل یکی‌اند.
۳) هر پنلِ سند در s1 حاضر است و ردیف‌هایش خالی نیست.
۴) شمارشِ سناریوها همان چهار صحنه است.
"""
import hashlib
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "fixture")
GOLD = os.path.join(ROOT, "backend-go", "internal", "mstat", "testdata", "golden")
ROUTES = ["summary", "histogram_all", "histogram_eq_all", "thermometer_all",
          "thermometer_eq_all", "depth_all", "depth_eq_all", "clientsplit_all",
          "clientsplit_fixed", "market_snapshot", "phase", "industries",
          "timeline_cum", "timeline_inst", "phases", "mainwatch_default",
          "mainwatch_val"]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def main() -> int:
    fails = []
    before = {n: sha(os.path.join(FIX, n)) for n in ("market.db", "user.db")}
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "parity",
                                                 "make_mstat_fixture.py")],
                   check=True, capture_output=True)
    after = {n: sha(os.path.join(FIX, n)) for n in ("market.db", "user.db")}
    if before != after:
        fails.append("fixture is not deterministic")
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "parity",
                                                 "gen_mstat_golden.py")],
                   check=True, capture_output=True)
    for name in ROUTES:
        p = os.path.join(GOLD, "s1", name + ".json")
        if not os.path.exists(p):
            fails.append("missing golden " + name)
            continue
        d = json.load(open(p, encoding="utf-8"))
        if not isinstance(d, dict) or d.get("status") != "ok":
            fails.append(name + ": status != ok")
        if name == "summary" and len(d.get("rows") or []) != 10:
            fails.append("summary must have 10 rows")
        if name == "industries" and not (d.get("rows") or []):
            fails.append("industries is empty")
    if not os.path.exists(os.path.join(GOLD, "s2", "timeline_cum.json")):
        fails.append("missing s2 timeline")
    for s in ("s3", "s4"):
        if not os.path.exists(os.path.join(GOLD, s, "phase.json")):
            fails.append("missing %s phase" % s)
    for f in fails:
        print("FAIL", f)
    print("mstat_fixture_v1121: %d failed" % len(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Register and run the guard**

In `dev/run_all_tests.py`, add the guard beside `test_board_fixture_v1120.py` with the same runner contract (exit code + summary line).

Run: `PYTHONIOENCODING=utf-8 python dev/test_mstat_fixture_v1121.py`
Expected: `mstat_fixture_v1121: 0 failed`.

- [ ] **Step 7: Commit**

```bash
git add tools/parity/make_mstat_fixture.py tools/parity/gen_mstat_golden.py \
        dev/test_mstat_fixture_v1121.py dev/run_all_tests.py \
        backend-go/internal/mstat/testdata/golden
git add -f backend-go/internal/mstat/testdata/fixture/market.db \
           backend-go/internal/mstat/testdata/fixture/user.db
git commit -F - <<'EOF'
test(go): فیکسچر و اوراکلِ طلاییِ پنل‌هایِ وضعیت بازار

- فیکسچر رویِ فیکسچرِ تابلو ساخته می‌شود تا /api/market رویِ همان بانک کار
  کند و پرچم‌هایِ mainwatch واقعی باشند، نه unavailable.
- نُه ردیفِ mstat هر شاخهٔ طبقه‌بندی و صف و value_source را قفل می‌کند؛ چهار
  صحنه: پایه، تایم‌لاینِ کهنه، بی‌وضعیتِ رسمی، تعطیلی.
- ساعت در اوراکل تزریق می‌شود تا clock_now هم طلایی و قابلِ سنجش باشد.
- گارد: قطعیتِ فیکسچر، تازگیِ طلایی‌ها، حضورِ هر پنل، شمارشِ سناریوها.
EOF
```

---

### Task 2: `pyround`، جدول‌هایِ ثابتِ تولیدشده و طبقه‌بندی

**Files:**
- Create: `backend-go/internal/pyround/pyround.go`, `pyround_test.go`
- Create: `tools/parity/extract_mstat_terms.py`
- Create: `backend-go/internal/mstat/terms_gen.go` (generated)
- Create: `backend-go/internal/mstat/classify.go`, `classify_test.go`
- Modify: `dev/test_mstat_fixture_v1121.py` (یک بررسیِ تازه: `terms_gen.go` هم‌ارزِ استخراجِ تازه)

**Interfaces:**
- Produces:
  `pyround.Round(x float64, n int) float64`
  `classify(paperType *int64, name, symbol, sector string) (cls, kind string)`
  `fundKind(name, symbol string) string`
  متغیرهایِ تولیدشده: `fundKindTerms`, `bondSymPrefix`, `bondName`, `bondSector`, `fundName`, `fundSector`, `tesehSector`, `bondWord`, `futuresWord`, `optionKeys`, `categoryRows`, `categoryLabels`, `clientTabs`, `histo12`, `histo7`, `transitions`, `termsSHA256`.

- [ ] **Step 1: Write the failing rounding test**

```go
package pyround

import (
	"math"
	"testing"
)

// برداشت‌ها مستقیم از CPython 3.14 گرفته شده‌اند (نه دست‌حساب): گردکردنِ
// round(x, n) رویِ همان دودوییِ float است، نه رویِ نمایشِ اعشاری.
func TestRoundMatchesCPython(t *testing.T) {
	cases := []struct {
		x    float64
		n    int
		want float64
	}{
		{2.675, 0, 3}, {2.675, 1, 2.7}, {2.675, 2, 2.67},
		{0.35, 1, 0.3}, {0.45, 1, 0.5}, {1.15, 1, 1.1}, {1.05, 1, 1.1}, {0.15, 1, 0.1},
		{2.5, 0, 2}, {3.5, 0, 4}, {-2.5, 0, -2},
		{1234.5675, 2, 1234.57}, {1234.5675, 3, 1234.568},
		{1e13 / 1e9, 3, 10000}, {0.0000005, 6, 0},
	}
	for _, c := range cases {
		if got := Round(c.x, c.n); got != c.want {
			t.Errorf("Round(%v,%d) = %v, want %v", c.x, c.n, got, c.want)
		}
	}
}

func TestRoundLeavesNonFinite(t *testing.T) {
	if !math.IsNaN(Round(math.NaN(), 2)) {
		t.Fatal("NaN must stay NaN")
	}
	if !math.IsInf(Round(math.Inf(1), 2), 1) {
		t.Fatal("Inf must stay Inf")
	}
}
```

Run: `cd backend-go && go test ./internal/pyround/`
Expected: FAIL — package does not exist.

- [ ] **Step 2: Write `pyround`**

```go
// Package pyround همان round()ِ داخلیِ پایتون است برایِ اسکالرهایِ float.
//
// چرا RoundToEven(x*10^n)/10^n کافی نیست: پایتون رویِ همان دودوییِ x درست
// گرد می‌کند، ولی ضرب و تقسیمِ اعشاری یک خطایِ دوم اضافه می‌کند (0.35 با
// rint می‌شود 0.4 و پایتون 0.3). FormatFloat('f', n) هم مثلِ CPython رویِ
// دودویی درست گرد می‌کند؛ رویِ ۲۴٬۹۰۰ ورودی (B1) صفر اختلاف داشت.
package pyround

import (
	"math"
	"strconv"
)

func Round(x float64, n int) float64 {
	if math.IsNaN(x) || math.IsInf(x, 0) {
		return x
	}
	v, err := strconv.ParseFloat(strconv.FormatFloat(x, 'f', n, 64), 64)
	if err != nil {
		return x
	}
	return v
}
```

- [ ] **Step 3: Write the constants extractor**

فهرست‌هایِ کلیدواژهٔ فارسی و جدول‌هایِ سطل/تب/چرخش **دست‌نویس نمی‌شوند**؛ از خودِ ماژولِ پایتون استخراج می‌شوند تا یک نویسهٔ جابه‌جا کلِ طبقه‌بندی را بی‌صدا عوض نکند.

```python
#!/usr/bin/env python
"""استخراجِ جدول‌هایِ ثابتِ mstat_engine به Go — تک‌منبع، بی‌دست‌نویسی.

خروجی: backend-go/internal/mstat/terms_gen.go
`--check` فقط مقایسه می‌کند و با اختلاف، exit 1 می‌دهد (گارد).
"""
import hashlib
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "backend-go", "internal", "mstat", "terms_gen.go")
sys.path.insert(0, ROOT)
import mstat_engine as M  # noqa: E402


def data():
    return {
        "fund_kinds": [[k, list(v)] for k, v in M._FUND_KINDS],
        "bond_sym_prefix": list(M._BOND_SYM_PREFIX),
        "bond_name": list(M._BOND_NAME),
        "bond_sector": list(M._BOND_SECTOR),
        "fund_name": list(M._FUND_NAME),
        "fund_sector": list(M._FUND_SECTOR),
        "teseh_sector": list(M._TESEH_SECTOR),
        "bond_word": list(M._BOND_WORD),
        "futures_word": list(M._FUTURES_WORD),
        "option_keys": list(M._OPTION_KEYS),
        "category_rows": [[k, v] for k, v in M.CATEGORY_ROWS],
        "client_tabs": [[k, v] for k, v in M.CLIENT_TABS],
        "histo12": [[k, l, lo, hi, c] for k, l, lo, hi, c in M.HISTO12],
        "histo7": [[k, l, lo, hi, c] for k, l, lo, hi, c in M.HISTO7],
        "transitions": [[a, b, l, c] for a, b, l, c in M._TRANS],
    }


def q(s):
    # json.dumps برایِ رشتهٔ Go هم معتبر است (فارسی Literal می‌ماند).
    return json.dumps(s, ensure_ascii=False)


def strs(xs):
    return "[]string{" + ", ".join(q(x) for x in xs) + "}"


def go_source(d, sha):
    out = []
    out.append("// Code generated by tools/parity/extract_mstat_terms.py; DO NOT EDIT.")
    out.append("package mstat")
    out.append("")
    out.append("// termsSHA256 اثرِ انگشتِ دادهٔ استخراج‌شده است؛ گارد آن را بازمی‌سازد.")
    out.append('const termsSHA256 = "%s"' % sha)
    out.append("")
    out.append("type fundKindTerm struct { Kind string; Keys []string }")
    out.append("type histoSpec struct { Key, Label string; Lo, Hi float64; Color string }")
    out.append("type transition struct { From, To, Label, Color string }")
    out.append("")
    out.append("var fundKindTerms = []fundKindTerm{")
    for kind, keys in d["fund_kinds"]:
        out.append("\t{%s, %s}," % (q(kind), strs(keys)))
    out.append("}")
    for name in ("bond_sym_prefix", "bond_name", "bond_sector", "fund_name",
                 "fund_sector", "teseh_sector", "bond_word", "futures_word",
                 "option_keys"):
        out.append("")
        out.append("var %s = %s" % (camel(name), strs(d[name])))
    out.append("")
    out.append("var categoryRows = []struct{ Key, Label string }{")
    for k, v in d["category_rows"]:
        out.append("\t{%s, %s}," % (q(k), q(v)))
    out.append("}")
    out.append("")
    out.append("var clientTabs = []struct{ Key, Label string }{")
    for k, v in d["client_tabs"]:
        out.append("\t{%s, %s}," % (q(k), q(v)))
    out.append("}")
    for name, key in (("histo12", "histo12"), ("histo7", "histo7")):
        out.append("")
        out.append("var %s = []histoSpec{" % name)
        for k, l, lo, hi, c in d[key]:
            out.append("\t{%s, %s, %s, %s, %s}," % (q(k), q(l), fmtnum(lo), fmtnum(hi), q(c)))
        out.append("}")
    out.append("")
    out.append("var transitions = []transition{")
    for a, b, l, c in d["transitions"]:
        out.append("\t{%s, %s, %s, %s}," % (q(a), q(b), q(l), q(c)))
    out.append("}")
    out.append("")
    return "\n".join(out)


def fmtnum(v):
    # 1e9 و 1e-9 و اعدادِ صحیح: Go همین را می‌پذیرد.
    return "1e9" if v == 1e9 else ("-1e9" if v == -1e9 else repr(float(v)))


def camel(s):
    parts = s.split("_")
    return parts[0] + "".join(p[:1].upper() + p[1:] for p in parts[1:])


def main(argv) -> int:
    d = data()
    canonical = json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    sha = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    src = go_source(d, sha)
    if "--check" in argv:
        with open(OUT, encoding="utf-8") as f:
            have = f.read()
        if have != src:
            print("terms_gen.go is stale; run tools/parity/extract_mstat_terms.py")
            return 1
        print("terms_gen.go ok")
        return 0
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)
    print("wrote", OUT, sha[:12])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
```

**قاعدهٔ نقلِ لفظی:** `M._FUND_KINDS` و بقیه در `mstat_engine.py` با `from __future__ import annotations` و بدونِ وابستگیِ بانکی import می‌شوند؛ اگر import خطا داد یعنی `sys.path` غلط است، نه اینکه جدول را دستی بنویسید.

- [ ] **Step 4: Generate and inspect**

Run: `PYTHONIOENCODING=utf-8 python tools/parity/extract_mstat_terms.py && gofmt -w backend-go/internal/mstat/terms_gen.go && go build ./...`
Expected: `terms_gen.go` ساخته می‌شود و بیلد پاس است (بدونِ منطقِ مصرف‌کننده هنوز هشدارِ unused نیست چون سطحِ بسته است؛ در Go متغیرِ بستهٔ استفاده‌نشده خطا نمی‌دهد).

Run: `PYTHONIOENCODING=utf-8 python tools/parity/extract_mstat_terms.py --check`
Expected: `terms_gen.go ok`.

- [ ] **Step 5: Write the failing classification test**

```go
package mstat

import "testing"

// برداشت‌ها از dev/mstat_local_v975.py و probes همان فایل؛ هر ردیف یک باگِ
// واقعیِ گذشته را قفل می‌کند.
func TestClassify(t *testing.T) {
	pt := func(v int64) *int64 { return &v }
	cases := []struct {
		name, symbol, sector string
		pt                   *int64
		wantCls, wantKind    string
	}{
		{"x", "y", "", pt(1), "stock", "stock"},
		{"x", "y", "", pt(2), "stock", "stock"},
		{"x", "y", "", pt(4), "right", "right"},
		{"اختيارخ اهرم", "ضهرم1", "", pt(6), "other", "other"},
		{"a", "b", "", nil, "other", "other"},
		{"صندوق س.درآمد ثابت دينا-د", "دينا", "", pt(8), "fund", "fixed"},
		{"صندوق اهرم آگاه-س", "اهرم", "", pt(8), "fund", "lev"},
		{"صندوق سرمايه گذاري طلا گلگشت", "گلگشت", "", pt(8), "fund", "gold"},
		{"صندوق نقره-س", "نقره", "", pt(8), "fund", "silver"},
		{"صندوق س.بخشي صنايع دانايان1-ب", "نبات", "", pt(8), "fund", "equity"},
		{"صندوق نامشخص-و", "ايكس", "", pt(8), "fund", "etf"},
		// نشتِ paperType: pt=8 برایِ سهامِ عادی — نام برنده است.
		{"شرکت فولاد مبارکه", "فولاد", "", pt(8), "stock", "stock"},
		// حق تقدم از نمادِ «ح» پایانی.
		{"حق تقدم ا", "حقا", "", pt(1), "right", "right"},
		// اوراق/صکوک از نام، بی‌ توجه به paperType.
		{"صكوك اجاره فولاد006", "صفولا", "", pt(1), "other", "other"},
		{"مشاركت ش كرج712-3ماهه", "شكرج", "", pt(1), "other", "other"},
		// «آتی» فقط با نمادِ عددپایان؛ «آتيه داده پرداز» سهام می‌ماند.
		{"قرارداد آتي سكه", "طلا12", "", pt(1), "other", "other"},
		{"آتيه داده پرداز", "آتيه", "", pt(1), "stock", "stock"},
		// تسهیلات مسکن فقط از سکتور.
		{"اوراق حق تقدم تسهیلات", "ضتسه", "اوراق حق تقدم", pt(1), "other", "other"},
	}
	for _, c := range cases {
		cls, kind := classify(c.pt, c.name, c.symbol, c.sector)
		if cls != c.wantCls || kind != c.wantKind {
			t.Errorf("classify(%v,%q,%q,%q) = %s/%s, want %s/%s",
				c.pt, c.name, c.symbol, c.sector, cls, kind, c.wantCls, c.wantKind)
		}
	}
}

func TestFundKindTailRules(t *testing.T) {
	if got := fundKind("صندوق س.درآمد ثابت دينا-د", "دينا"); got != "fixed" {
		t.Fatalf("‑د tail = %s", got)
	}
	if got := fundKind("صندوق س.بخشي دانايان-ب", "نبات"); got != "equity" {
		t.Fatalf("‑ب tail = %s", got)
	}
	// «معيار» نباید «عيار» (طلا) خوانده شود.
	if got := fundKind("صندوق س.كالاي ديباي معيار", "معيار"); got != "etf" {
		t.Fatalf("word boundary: %s", got)
	}
}
```

Run: `cd backend-go && go test ./internal/mstat/`
Expected: FAIL — `classify`/`fundKind` undefined.

- [ ] **Step 6: Write `classify.go`**

```go
package mstat

import (
	"strings"
	"unicode"
	"unicode/utf8"
)

const (
	paperStock = "stock"
	paperRight = "right"
	paperFund  = "fund"
)

// normalized همان _norm: ي/ى→ی، ك→ک، حذفِ نیم‌فاصله و ZWJ، trim.
var normalized = strings.NewReplacer(
	"\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9",
	"\u200C", "", "\u200D", "",
)

func norm(s string) string { return strings.TrimSpace(normalized.Replace(s)) }

// wordHit همان _word_hit: کلید باید از چپ مرزِ واژه داشته باشد.
func wordHit(name, key string) bool {
	rs, ks := []rune(name), []rune(key)
	if len(ks) == 0 {
		return false
	}
	for i := 0; i+len(ks) <= len(rs); i++ {
		if string(rs[i:i+len(ks)]) != key {
			continue
		}
		if i == 0 || !unicode.IsLetter(rs[i-1]) {
			return true
		}
	}
	return false
}

// wholeWord همان _whole_word: مرز از دو سو.
func wholeWord(name, key string) bool {
	rs, ks := []rune(name), []rune(key)
	if len(ks) == 0 {
		return false
	}
	for i := 0; i+len(ks) <= len(rs); i++ {
		if string(rs[i:i+len(ks)]) != key {
			continue
		}
		left := i == 0 || !unicode.IsLetter(rs[i-1])
		right := i+len(ks) >= len(rs) || !unicode.IsLetter(rs[i+len(ks)])
		if left && right {
			return true
		}
	}
	return false
}

func anySub(s string, keys []string) bool {
	for _, k := range keys {
		if strings.Contains(s, k) {
			return true
		}
	}
	return false
}

func fundKind(name, symbol string) string {
	full := name + " " + symbol
	for _, fk := range fundKindTerms {
		for _, k := range fk.Keys {
			if wordHit(full, k) {
				return fk.Kind
			}
		}
	}
	tail := strings.TrimRight(name, " \t\r\n")
	if strings.HasSuffix(tail, "-د") {
		return "fixed"
	}
	if strings.HasSuffix(tail, "-س") || strings.HasSuffix(tail, "-ب") {
		return "equity"
	}
	return "etf"
}

func isOption(name, symbol string) bool {
	full := name + " " + symbol
	return anySub(full, optionKeys)
}

func isFund(name, symbol, sector string) bool {
	n, c := norm(name), norm(sector)
	return anySub(n, fundName) || anySub(c, fundSector)
}

func isBond(symbol, name, sector string) bool {
	s, n, c := strings.ToUpper(norm(symbol)), norm(name), norm(sector)
	if hasAnyPrefix(s, bondSymPrefix) || anySub(n, bondName) || anySub(c, bondSector) {
		return true
	}
	for _, k := range bondWord {
		if wholeWord(n, k) {
			return true
		}
	}
	if s != "" {
		last, _ := utf8.DecodeLastRuneInString(s)
		if unicode.IsDigit(last) {
			for _, k := range futuresWord {
				if wholeWord(n, k) {
					return true
				}
			}
		}
	}
	return false
}

func hasAnyPrefix(s string, prefixes []string) bool {
	for _, p := range prefixes {
		if strings.HasPrefix(s, p) {
			return true
		}
	}
	return false
}

func isTeseh(sector string) bool { return anySub(norm(sector), tesehSector) }

func endsWithH(symbol string) bool {
	s := strings.ToUpper(norm(symbol))
	return s != "" && strings.HasSuffix(s, "ح")
}

// classify همان ترتیبِ assetType.ts: اختیار → صندوق → اوراق → تسهیلات →
// حق تقدم → paperType.
func classify(paperType *int64, name, symbol, sector string) (string, string) {
	if isOption(name, symbol) {
		return "other", "other"
	}
	if isFund(name, symbol, sector) {
		return paperFund, fundKind(name, symbol)
	}
	if isBond(symbol, name, sector) {
		return "other", "other"
	}
	if isTeseh(sector) {
		return "other", "other"
	}
	if endsWithH(symbol) || strings.Contains(norm(name), "حق تقدم") {
		return paperRight, "right"
	}
	if paperType == nil {
		return "other", "other"
	}
	switch *paperType {
	case 1, 2:
		return paperStock, "stock"
	case 4:
		return paperRight, "right"
	case 8:
		if isFund(name, symbol, sector) {
			return paperFund, fundKind(name, symbol)
		}
		if endsWithH(symbol) || strings.Contains(norm(name), "حق تقدم") {
			return paperRight, "right"
		}
		return paperStock, "stock"
	}
	return "other", "other"
}
```

**دقت:** `fundKind(name, symbol)` همان `fund_kind(l_val30, l_val18)` است — نام از `l_val30`، نماد از `l_val18`؛ جایشان را عوض نکنید.

- [ ] **Step 7: Run tests**

Run: `cd backend-go && go test ./internal/pyround/ ./internal/mstat/`
Expected: PASS.

- [ ] **Step 8: Add the extractor check to the guard**

در `dev/test_mstat_fixture_v1121.py` پیش از گزارش، این را اضافه کنید:

```python
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "parity",
                                                     "extract_mstat_terms.py"),
                        "--check"], capture_output=True, text=True)
    if r.returncode != 0:
        fails.append("terms_gen.go is stale")
```

Run: `PYTHONIOENCODING=utf-8 python dev/test_mstat_fixture_v1121.py`
Expected: `mstat_fixture_v1121: 0 failed`.

- [ ] **Step 9: Commit**

```bash
git add backend-go/internal/pyround backend-go/internal/mstat/terms_gen.go \
        backend-go/internal/mstat/classify.go backend-go/internal/mstat/classify_test.go \
        tools/parity/extract_mstat_terms.py dev/test_mstat_fixture_v1121.py
git commit -F - <<'EOF'
feat(go): گردکردنِ پایتونی و طبقه‌بندیِ ابزارهایِ وضعیت بازار

- pyround.Round همان round()ِ CPython است؛ پنج بردارِ مرزی (0.35/0.45/1.15/1.05/0.15)
  ثابت می‌کنند rint جوابِ دیگری می‌داد.
- جدول‌هایِ فارسی (کلیدواژه‌هایِ صندوق/اوراق/تسهیلات، سطل‌هایِ هیستوگرام،
  تب‌هایِ حقیقی-حقوقی، چرخش‌هایِ صف) از خودِ mstat_engine استخراج می‌شوند،
  نه دست‌نویس؛ گارد هم‌ارزیِ terms_gen.go را می‌سنجد.
- طبقه‌بندی با همان ترتیبِ اختیار → صندوق → اوراق → تسهیلات → حق تقدم →
  paperType و همان استثناهایِ ثبت‌شده (pt=8 برایِ سهامِ عادی، «آتی» با
  نمادِ عددپایان).
EOF
```

---

### Task 3: اسنپ‌شات، ارقامِ ریالیِ هر نماد و دسته‌ها

**Files:**
- Create: `backend-go/internal/mstat/frame.go`, `money.go`
- Create: `backend-go/internal/mstat/frame_test.go`, `money_test.go`
- Modify: `tools/parity/gen_mstat_golden.py` (افزودنِ `s1/enrich.json`)
- Test: مقایسهٔ `enrich.json` با `loadSnapshot` + `money`

**Interfaces:**
- Produces:
  `type Snapshot struct { AsOf AsOf; Rows []*Row; BaseEst map[string]float64; Depth bool }`
  `func loadSnapshot(db *sql.DB) (*Snapshot, error)`
  `type Row` با فیلدهایِ عددیِ `float64` که `NaN` یعنی NULL، و `CT/CTV` و `Cls/Kind/Pct/ClockPct`
  `func money(r *Row, baseEst map[string]float64) Money` با فیلدهایِ عددی که `NaN` یعنی null
  `func top50Codes(rows []*Row) map[string]bool`
  `func inCategory(r *Row, cat string, top50 map[string]bool) bool`
  `func jnum(v float64) any` (NaN → nil) و `func isNaN/isEmpty`

- [ ] **Step 1: Extend the oracle with the enrich dump**

در `scenario()` پیش از `shutil.rmtree`:

```python
    import mstat_engine as ME
    con2 = sqlite3.connect(os.path.join(tmp, "market.db"))
    try:
        erows, emeta = ME.enrich(con2)
        save("enrich.json", {"asof": emeta, "rows": [
            {"ins_code": r["ins_code"], "symbol": r["symbol"], "cls": r["cls"],
             "kind": r["kind"], "pct": r["pct"], "clock_pct": r["clock_pct"],
             "top50": r["_top50"], "m": dict(r["_m"])} for r in erows]})
    finally:
        con2.close()
```

Run: `PYTHONIOENCODING=utf-8 python tools/parity/gen_mstat_golden.py`
Expected: `s1/enrich.json` ساخته می‌شود؛ `asof` شاملِ `client_lag_days` و `depth` است.

- [ ] **Step 2: Write the failing snapshot test**

```go
package mstat

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
)

type enrichGolden struct {
	AsOf map[string]any `json:"asof"`
	Rows []struct {
		Code, Symbol, Cls, Kind string
		Pct, ClockPct           *float64
		Top50                   bool
		M                       map[string]any
	} `json:"rows"`
}

func openFixture(t *testing.T) *db.Handles {
	t.Helper()
	h, err := db.Open(filepath.Join("testdata", "fixture"), false)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	return h
}

// TestSnapshotMatchesGolden ردیف‌به‌ردیفِ enrich را با اوراکلِ پایتون می‌سنجد؛
// این تست فقط شکل را نمی‌بیند — هر یکایِ ریالی، VWAP، سرانه، قدرت، جریان،
// value_source و qstate را هم قفل می‌کند.
func TestSnapshotMatchesGolden(t *testing.T) {
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", "s1", "enrich.json"))
	if err != nil {
		t.Fatal(err)
	}
	var g enrichGolden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	h := openFixture(t)
	snap, err := loadSnapshot(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	if len(snap.Rows) != len(g.Rows) {
		t.Fatalf("rows = %d, want %d", len(snap.Rows), len(g.Rows))
	}
	for i, want := range g.Rows {
		got := snap.Rows[i]
		if got.Code != want.Code || got.Cls != want.Cls || got.Kind != want.Kind {
			t.Fatalf("row %d identity = %s/%s/%s, want %s/%s/%s", i, got.Code,
				got.Cls, got.Kind, want.Code, want.Cls, want.Kind)
		}
		if !eqPtr(got.Pct, want.Pct) {
			t.Fatalf("%s pct = %v, want %v", got.Code, show(got.Pct), show(want.Pct))
		}
		if !eqPtr(got.ClockPct, want.ClockPct) {
			t.Fatalf("%s clock_pct = %v, want %v", got.Code, show(got.ClockPct), show(want.ClockPct))
		}
		if got.Top50 != want.Top50 {
			t.Fatalf("%s top50 = %v", got.Code, got.Top50)
		}
		m := money(got, snap.BaseEst)
		checkMoney(t, got.Code, m, want.M)
	}
}

func eqPtr(a, b *float64) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func show(p *float64) any {
	if p == nil {
		return nil
	}
	return *p
}

func checkMoney(t *testing.T, code string, m Money, want map[string]any) {
	t.Helper()
	pairs := map[string]float64{
		"vol": m.Vol, "val": m.Val, "vwap": m.Vwap, "trades": m.Trades,
		"bq_val": m.BQVal, "sq_val": m.SQVal, "bq_vol": m.BQVol, "sq_vol": m.SQVol,
		"bq_cnt": m.BQCnt, "sq_cnt": m.SQCnt, "bq1_vol": m.BQ1Vol, "bq1_px": m.BQ1Px,
		"sq1_vol": m.SQ1Vol, "sq1_px": m.SQ1Px,
		"retail_buy": m.RetailBuy, "retail_sell": m.RetailSell,
		"inst_buy": m.InstBuy, "inst_sell": m.InstSell,
		"ddd_buy": m.DDDBuy, "pc_buy": m.PCBuy, "pc_sell": m.PCSell,
		"power": m.Power, "flow": m.Flow, "base": m.Base,
	}
	for k, got := range pairs {
		w, ok := want[k]
		if !ok {
			t.Fatalf("%s: golden has no key %s", code, k)
		}
		if w == nil {
			if !isNaN(got) {
				t.Fatalf("%s.%s = %v, want null", code, k, got)
			}
			continue
		}
		wf, _ := w.(float64)
		if isNaN(got) || got != wf {
			t.Fatalf("%s.%s = %v, want %v", code, k, got, wf)
		}
	}
	if want["value_source"] != m.ValueSource {
		t.Fatalf("%s value_source = %s, want %v", code, m.ValueSource, want["value_source"])
	}
	if want["qstate"] != m.QState {
		t.Fatalf("%s qstate = %s, want %v", code, m.QState, want["qstate"])
	}
	if want["has_ct"] != m.HasCT {
		t.Fatalf("%s has_ct = %v", code, m.HasCT)
	}
	for k, got := range map[string]int64{"n_buy_i": m.NBuyI, "n_sell_i": m.NSellI,
		"n_buy_n": m.NBuyN, "n_sell_n": m.NSellN} {
		if wf, _ := want[k].(float64); float64(got) != wf {
			t.Fatalf("%s.%s = %d, want %v", code, k, got, want[k])
		}
	}
	_ = math.NaN
}
```

**توجه:** JSONِ پایتون برایِ `None` مقدارِ `null` می‌دهد و `float(...)` برایِ اعدادِ صحیحِ مبلغ (مثلِ `trades` که float است) همان `float64` می‌ماند. اگر `want[k]` رشته یا bool بود، تست باید بشکند — همین مقصود است.

- [ ] **Step 3: Write `frame.go`**

```go
package mstat

import (
	"database/sql"
	"fmt"
	"math"
	"strconv"
	"strings"
)

type AsOf struct {
	DEven       *int64
	HEven       int64
	ClientDEven *int64
	ClientLag   *bool
	Depth       bool
}

type CTRow struct {
	BuyIVol, BuyNVol, BuyDDDVol, BuyCountI, BuyCountN float64
	SellIVol, SellNVol, SellCountI, SellCountN        float64
}

type CTVRow struct {
	BuyIVal, BuyNVal, SellIVal, SellNVal, BuyDDDVal float64
}

type Row struct {
	Code, Symbol, Name, SectorCode, SectorName string
	PClosing, PLast, PYest, PFirst              float64
	PMin, PMax, AllowedMin, AllowedMax          float64
	BuyQVol, BuyQVal, BuyQCnt                   float64
	SellQVol, SellQVal, SellQCnt                float64
	BuyQ1Vol, BuyQ1Px, SellQ1Vol, SellQ1Px      float64
	BuyQ1Cnt                                    float64
	QVol, QVal, NTrades, PriceChange            float64
	TotalShares, BaseVol                        float64
	HEven                                       int64
	HasHEven                                    bool
	PaperType                                   *int64
	Cls, Kind                                   string
	Pct, ClockPct                               *float64
	CT                                          *CTRow
	CTV                                         *CTVRow
	Top50                                       bool
}

type Snapshot struct {
	AsOf    AsOf
	Rows    []*Row
	BaseEst map[string]float64
	Depth   bool
}

func isNaN(v float64) bool { return math.IsNaN(v) }

func fnum(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case int:
		return float64(n)
	default:
		return math.NaN()
	}
}

func inum(v any) (int64, bool) {
	switch n := v.(type) {
	case int64:
		return n, true
	case float64:
		return int64(n), true
	case int:
		return int64(n), true
	default:
		return 0, false
	}
}

func text(v any) string {
	switch s := v.(type) {
	case string:
		return s
	case []byte:
		return string(s)
	default:
		return ""
	}
}

// div همان _div: مخرجِ صفر یا طرفِ نبود ⇒ nil (نه صفر).
func div(a, b float64) *float64 {
	if isNaN(a) || isNaN(b) || b == 0 {
		return nil
	}
	x := a / b
	return &x
}

// divF مقدارِ _div را با صفر جایگزین می‌کند (همان الگویِ پایتون که None را در
// جمعِ بعدی صفر می‌گیرد).
func divF(a, b float64) float64 {
	if d := div(a, b); d != nil {
		return *d
	}
	return 0
}

func pxNear(v, ref float64) bool {
	if isNaN(v) || isNaN(ref) {
		return false
	}
	return v > 0 && ref > 0 && (1.0/2.0) <= v/ref && v/ref <= 2.0
}

func pxInBand(r *Row, v, ref float64) bool {
	if isNaN(v) || isNaN(ref) || v <= 0 || ref <= 0 {
		return false
	}
	if r.AllowedMin > 0 && r.AllowedMax >= r.AllowedMin {
		if !(r.AllowedMin*0.999 <= v && v <= r.AllowedMax*1.001) {
			return false
		}
	}
	ratio := v / ref
	return 0.5 <= ratio && ratio <= 2.0
}

func hasDepthCol(db *sql.DB) bool {
	rows, err := db.Query("PRAGMA table_info(market_watch)")
	if err != nil {
		return false
	}
	defer rows.Close()
	for rows.Next() {
		var cid int
		var name, typ string
		var notnull, pk int
		var dflt any
		if err := rows.Scan(&cid, &name, &typ, &notnull, &dflt, &pk); err != nil {
			return false
		}
		if name == "buy_q_val" {
			return true
		}
	}
	return false
}

// loadSnapshot همان load_snapshot است: یک اسکن، بدونِ N+1.
func loadSnapshot(db *sql.DB) (*Snapshot, error) {
	var day sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&day); err != nil {
		return nil, fmt.Errorf("day: %w", err)
	}
	var dayArg any
	if day.Valid {
		dayArg = day.Int64
	}
	var hour sql.NullInt64
	if err := db.QueryRow("SELECT MAX(h_even) FROM market_watch WHERE d_even=?",
		dayArg).Scan(&hour); err != nil {
		return nil, fmt.Errorf("hour: %w", err)
	}
	var cday sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM client_type WHERE d_even<=?",
		dayArg).Scan(&cday); err != nil {
		return nil, fmt.Errorf("client day: %w", err)
	}
	depth := hasDepthCol(db)

	cols := `m.ins_code, i.l_val18, i.l_val30, i.sector_code, i.sector_name,
	         m.p_closing, m.p_last, m.price_yesterday, m.price_first,
	         m.price_min, m.price_max, m.allowed_min, m.allowed_max,`
	if depth {
		cols += ` m.buy_q_vol, m.buy_q_val, m.buy_q_cnt,
		          m.sell_q_vol, m.sell_q_val, m.sell_q_cnt,
		          m.buy_q1_vol, m.buy_q1_px, m.sell_q1_vol, m.sell_q1_px,
		          m.buy_q1_cnt,`
	}
	cols += ` m.q_tot_tran, m.q_tot_cap, m.z_tot_tran, m.price_change,
	          m.total_shares, i.base_vol, m.h_even, i.paper_type`
	rs, err := db.Query("SELECT "+cols+" FROM market_watch m"+
		" LEFT JOIN instruments i ON i.ins_code=m.ins_code WHERE m.d_even=?", dayArg)
	if err != nil {
		return nil, fmt.Errorf("snapshot: %w", err)
	}
	defer rs.Close()
	snap := &Snapshot{Depth: depth, BaseEst: map[string]float64{}}
	snap.AsOf = AsOf{DEven: nil, HEven: hour.Int64, ClientDEven: nil, Depth: depth}
	if day.Valid {
		d := day.Int64
		snap.AsOf.DEven = &d
	}
	if cday.Valid {
		c := cday.Int64
		snap.AsOf.ClientDEven = &c
	}
	if day.Valid && cday.Valid {
		v := strconv.FormatInt(day.Int64, 10) > strconv.FormatInt(cday.Int64, 10)
		snap.AsOf.ClientLag = &v
	}
	for rs.Next() {
		var vals []any
		colsN := 21
		if depth {
			colsN += 11
		}
		vals = make([]any, colsN)
		ptrs := make([]any, colsN)
		for i := range vals {
			ptrs[i] = &vals[i]
		}
		if err := rs.Scan(ptrs...); err != nil {
			return nil, err
		}
		r := &Row{
			Code: text(vals[0]), Symbol: strings.TrimSpace(text(vals[1])),
			Name: strings.TrimSpace(text(vals[2])),
			SectorCode: text(vals[3]), SectorName: text(vals[4]),
			PClosing: fnum(vals[5]), PLast: fnum(vals[6]), PYest: fnum(vals[7]),
			PFirst: fnum(vals[8]), PMin: fnum(vals[9]), PMax: fnum(vals[10]),
			AllowedMin: fnum(vals[11]), AllowedMax: fnum(vals[12]),
		}
		i := 13
		if depth {
			r.BuyQVol, r.BuyQVal, r.BuyQCnt = fnum(vals[i]), fnum(vals[i+1]), fnum(vals[i+2])
			r.SellQVol, r.SellQVal, r.SellQCnt = fnum(vals[i+3]), fnum(vals[i+4]), fnum(vals[i+5])
			r.BuyQ1Vol, r.BuyQ1Px = fnum(vals[i+6]), fnum(vals[i+7])
			r.SellQ1Vol, r.SellQ1Px = fnum(vals[i+8]), fnum(vals[i+9])
			r.BuyQ1Cnt = fnum(vals[i+10])
			i += 11
		}
		r.QVol, r.QVal, r.NTrades = fnum(vals[i]), fnum(vals[i+1]), fnum(vals[i+2])
		r.PriceChange, r.TotalShares, r.BaseVol = fnum(vals[i+3]), fnum(vals[i+4]), fnum(vals[i+5])
		if h, ok := inum(vals[i+6]); ok {
			r.HEven, r.HasHEven = h, true
		}
		if pt, ok := inum(vals[i+7]); ok {
			r.PaperType = &pt
		}
		r.Cls, r.Kind = classify(r.PaperType, r.Name, r.Symbol, r.SectorName)
		if !isNaN(r.PClosing) && !isNaN(r.PYest) && r.PClosing != 0 && r.PYest != 0 &&
			pxNear(r.PYest, r.PClosing) {
			if d := div(r.PClosing-r.PYest, r.PYest); d != nil {
				v := 100.0 * *d
				r.Pct = &v
			}
		}
		if !isNaN(r.PClosing) && !isNaN(r.PLast) && r.PClosing != 0 &&
			pxInBand(r, r.PLast, r.PClosing) {
			if d := div(r.PLast-r.PClosing, r.PClosing); d != nil {
				v := 100.0 * *d
				r.ClockPct = &v
			}
		}
		snap.Rows = append(snap.Rows, r)
	}
	if err := rs.Err(); err != nil {
		return nil, err
	}
	// client_type: کلید = ins_code؛ ردیفِ تکراری آخرین برنده است (dictِ پایتون).
	if cday.Valid {
		crs, err := db.Query(`SELECT ins_code, buy_i_vol, buy_n_vol, buy_ddd_vol,
		    buy_count_i, buy_count_n, sell_i_vol, sell_n_vol, sell_count_i,
		    sell_count_n FROM client_type WHERE d_even=?`, cday.Int64)
		if err != nil {
			return nil, fmt.Errorf("client_type: %w", err)
		}
		defer crs.Close()
		byCode := map[string]*CTRow{}
		for crs.Next() {
			var vals [10]any
			ptrs := make([]any, 10)
			for i := range vals {
				ptrs[i] = &vals[i]
			}
			if err := crs.Scan(ptrs...); err != nil {
				return nil, err
			}
			byCode[text(vals[0])] = &CTRow{
				BuyIVol: fnum(vals[1]), BuyNVol: fnum(vals[2]), BuyDDDVol: fnum(vals[3]),
				BuyCountI: fnum(vals[4]), BuyCountN: fnum(vals[5]),
				SellIVol: fnum(vals[6]), SellNVol: fnum(vals[7]),
				SellCountI: fnum(vals[8]), SellCountN: fnum(vals[9]),
			}
		}
		if err := crs.Err(); err != nil {
			return nil, err
		}
		for _, r := range snap.Rows {
			r.CT = byCode[r.Code]
		}
	}
	// client_type_value اختیاری است: بانکِ کهنه جدول را ندارد.
	if cday.Valid {
		if crs, err := db.Query(`SELECT ins_code, buy_i_val, buy_n_val, sell_i_val,
		    sell_n_val, buy_ddd_val FROM client_type_value WHERE d_even=?`, cday.Int64); err == nil {
			defer crs.Close()
			byCode := map[string]*CTVRow{}
			for crs.Next() {
				var vals [6]any
				ptrs := make([]any, 6)
				for i := range vals {
					ptrs[i] = &vals[i]
				}
				if err := crs.Scan(ptrs...); err != nil {
					break
				}
				byCode[text(vals[0])] = &CTVRow{
					BuyIVal: fnum(vals[1]), BuyNVal: fnum(vals[2]),
					SellIVal: fnum(vals[3]), SellNVal: fnum(vals[4]),
					BuyDDDVal: fnum(vals[5]),
				}
			}
			for _, r := range snap.Rows {
				r.CTV = byCode[r.Code]
			}
		}
	}
	snap.BaseEst = baseVolumeEstimate(db, dayArg)
	return snap, nil
}

// baseVolumeEstimate همان _base_volume_estimate: میانگینِ حداکثر ۴ نشستِ
// پیشین (بدونِ امروز) با شرطِ «حداقل دو مقدار».
func baseVolumeEstimate(db *sql.DB, dayArg any) map[string]float64 {
	out := map[string]float64{}
	rows, err := db.Query(`SELECT ins_code, q_tot_tran FROM daily_prices
	    WHERE d_even < ? AND q_tot_tran > 0
	      AND d_even >= (SELECT MIN(d_even) FROM (
	           SELECT DISTINCT d_even FROM daily_prices WHERE d_even < ?
	           ORDER BY d_even DESC LIMIT 4))
	    ORDER BY ins_code, d_even DESC`, dayArg, dayArg)
	if err != nil {
		return out
	}
	defer rows.Close()
	acc := map[string][]float64{}
	for rows.Next() {
		var code any
		var v any
		if err := rows.Scan(&code, &v); err != nil {
			return out
		}
		c := text(code)
		if len(acc[c]) < 4 {
			acc[c] = append(acc[c], fnum(v))
		}
	}
	for c, lst := range acc {
		if len(lst) >= 2 {
			sum := 0.0
			for _, x := range lst {
				sum += x
			}
			out[c] = sum / float64(len(lst))
		}
	}
	return out
}
```

- [ ] **Step 4: Write `money.go`**

```go
package mstat

import (
	"math"
	"sort"
)

type Money struct {
	Vol, Val, Vwap, Trades float64
	BQVal, SQVal           float64
	BQVol, SQVol, BQCnt    float64
	SQCnt                  float64
	BQ1Vol, BQ1Px          float64
	SQ1Vol, SQ1Px          float64
	HasCT                  bool
	RetailBuy, RetailSell  float64
	InstBuy, InstSell      float64
	ValueSource            string
	DDDBuy                 float64
	NBuyI, NSellI          int64
	NBuyN, NSellN          int64
	PCBuy, PCSell, Power   float64
	Flow                   float64
	Base                   float64
	QState                 string
}

func cget(ct *CTRow, v float64) float64 {
	if ct == nil {
		return 0
	}
	if isNaN(v) {
		return 0
	}
	return v
}

// money همان mstat_engine.money: ارزش هر گروه = مبدأ اگر بود، وگرنه حجم×VWAP.
func money(r *Row, baseEst map[string]float64) Money {
	m := Money{Vol: r.QVol, Val: r.QVal, Trades: r.NTrades, HasCT: r.CT != nil}
	ct := r.CT
	m.BQVal, m.SQVal = r.BuyQVal, r.SellQVal
	m.BQVol, m.SQVol = r.BuyQVol, r.SellQVol
	m.BQCnt, m.SQCnt = r.BuyQCnt, r.SellQCnt
	m.BQ1Vol, m.BQ1Px = r.BuyQ1Vol, r.BuyQ1Px
	m.SQ1Vol, m.SQ1Px = r.SellQ1Vol, r.SellQ1Px

	var vwap float64
	if d := div(r.QVal, r.QVol); d != nil && *d != 0 {
		vwap = *d
	} else if !isNaN(r.PClosing) && r.PClosing != 0 {
		vwap = r.PClosing
	}
	m.Vwap = vwap

	native := map[string]float64{}
	if r.CTV != nil {
		for name, v := range map[string]float64{
			"buy_i_val": r.CTV.BuyIVal, "buy_n_val": r.CTV.BuyNVal,
			"sell_i_val": r.CTV.SellIVal, "sell_n_val": r.CTV.SellNVal,
			"buy_ddd_val": r.CTV.BuyDDDVal,
		} {
			if !isNaN(v) {
				native[name] = v
			}
		}
	}
	got := 0
	pick := func(out string, nativeKey string, vol float64) {
		if v, ok := native[nativeKey]; ok {
			switch out {
			case "retail_buy":
				m.RetailBuy = v
			case "retail_sell":
				m.RetailSell = v
			case "inst_buy":
				m.InstBuy = v
			case "inst_sell":
				m.InstSell = v
			}
			got++
			return
		}
		v := cget(ct, vol) * vwap
		switch out {
		case "retail_buy":
			m.RetailBuy = v
		case "retail_sell":
			m.RetailSell = v
		case "inst_buy":
			m.InstBuy = v
		case "inst_sell":
			m.InstSell = v
		}
	}
	pick("retail_buy", "buy_i_val", ctVal(ct, func(c *CTRow) float64 { return c.BuyIVol }))
	pick("retail_sell", "sell_i_val", ctVal(ct, func(c *CTRow) float64 { return c.SellIVol }))
	pick("inst_buy", "buy_n_val", ctVal(ct, func(c *CTRow) float64 { return c.BuyNVol }))
	pick("inst_sell", "sell_n_val", ctVal(ct, func(c *CTRow) float64 { return c.SellNVol }))
	switch {
	case got == 4:
		m.ValueSource = "native"
	case got > 0:
		m.ValueSource = "mixed"
	default:
		m.ValueSource = "reconstructed"
	}
	if v, ok := native["buy_ddd_val"]; ok {
		m.DDDBuy = v
	} else {
		m.DDDBuy = cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyDDDVol })) * vwap
	}
	m.NBuyI = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyCountI })))
	m.NSellI = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.SellCountI })))
	m.NBuyN = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.BuyCountN })))
	m.NSellN = int64(cget(ct, ctVal(ct, func(c *CTRow) float64 { return c.SellCountN })))
	if v := div(m.RetailBuy, float64(m.NBuyI)); v != nil {
		m.PCBuy = *v
	} else {
		m.PCBuy = math.NaN()
	}
	if v := div(m.RetailSell, float64(m.NSellI)); v != nil {
		m.PCSell = *v
	} else {
		m.PCSell = math.NaN()
	}
	if v := div(m.PCBuy, m.PCSell); v != nil {
		m.Power = *v
	} else {
		m.Power = math.NaN()
	}
	m.Flow = m.RetailBuy - m.RetailSell
	if b, ok := baseEst[r.Code]; ok {
		m.Base = b
	} else {
		m.Base = math.NaN()
	}
	if !isNaN(r.BaseVol) && r.BaseVol > 1.0 {
		m.Base = r.BaseVol
	}
	m.QState = queueState(r, m)
	return m
}

func ctVal(ct *CTRow, f func(*CTRow) float64) float64 {
	if ct == nil {
		return math.NaN()
	}
	return f(ct)
}

func isEmpty(v float64) bool { return isNaN(v) || v == 0 }

func queueState(r *Row, m Money) string {
	if isNaN(m.BQVal) {
		return "x"
	}
	if m.BQVal > 0 && isEmpty(m.SQVal) {
		return "b"
	}
	if m.SQVal > 0 && isEmpty(m.BQVal) {
		return "s"
	}
	if r.Pct == nil {
		return "x"
	}
	switch {
	case *r.Pct > 0:
		return "p"
	case *r.Pct < 0:
		return "n"
	default:
		return "z"
	}
}

func top50Codes(rows []*Row) map[string]bool {
	type scored struct {
		cap  float64
		code string
	}
	list := []scored{}
	for _, r := range rows {
		if r.Cls != paperStock {
			continue
		}
		cap := r.TotalShares * r.PClosing
		if isNaN(cap) {
			continue
		}
		if cap > 0 {
			list = append(list, scored{cap, r.Code})
		}
	}
	sort.SliceStable(list, func(i, j int) bool {
		if list[i].cap != list[j].cap {
			return list[i].cap > list[j].cap
		}
		return list[i].code > list[j].code // tuple sortِ پایتون: tie با کدِ نزولی
	})
	out := map[string]bool{}
	for i, s := range list {
		if i >= 50 {
			break
		}
		out[s.code] = true
	}
	return out
}

func inCategory(r *Row, cat string, top50 map[string]bool) bool {
	cls, kind := r.Cls, r.Kind
	switch cat {
	case "all":
		return cls == paperStock || cls == paperRight ||
			(cls == paperFund && inStrings(kind, []string{"equity", "fof", "etf", "mixed", "fixed"}))
	case "bonds_other":
		if cls == paperStock || cls == paperRight {
			return false
		}
		if cls == paperFund {
			return !inStrings(kind, []string{"equity", "fof", "etf", "mixed", "fixed", "gold", "silver", "lev"})
		}
		return true
	case "eq_all":
		return cls == paperStock || cls == paperRight ||
			(cls == paperFund && inStrings(kind, []string{"equity", "fof", "etf", "mixed"}))
	case "stock_right":
		return cls == paperStock || cls == paperRight
	case "eq_fund":
		return cls == paperFund && inStrings(kind, []string{"equity", "mixed", "fof", "etf"})
	case "fixed_fund":
		return cls == paperFund && kind == "fixed"
	case "lev_fund":
		return cls == paperFund && kind == "lev"
	case "gold_fund":
		return cls == paperFund && kind == "gold"
	case "silver_fund":
		return cls == paperFund && kind == "silver"
	case "top50":
		return top50[r.Code]
	}
	return false
}

func inStrings(s string, xs []string) bool {
	for _, x := range xs {
		if s == x {
			return true
		}
	}
	return false
}

func jnum(v float64) any {
	if isNaN(v) {
		return nil
	}
	return v
}
```

- [ ] **Step 5: Run tests**

Run: `cd backend-go && go test ./internal/mstat/`
Expected: PASS. اگر مغایرت داشت، عددِ گزارش‌شده را با `enrich.json` بسنجید — نه اینکه تست را شل کنید.

- [ ] **Step 6: Commit**

```bash
git add backend-go/internal/mstat/frame.go backend-go/internal/mstat/money.go \
        backend-go/internal/mstat/frame_test.go backend-go/internal/mstat/money_test.go \
        tools/parity/gen_mstat_golden.py backend-go/internal/mstat/testdata/golden/s1/enrich.json
git commit -F - <<'EOF'
feat(go): اسنپ‌شات و ارقامِ ریالیِ هر نمادِ وضعیت بازار

- loadSnapshot همان تک‌کوئریِ پایتون است: روزِ تابلو، روزِ مشتریِ هم‌نشست،
  عمقِ اختیاری، و قابِ NaN برایِ NULL.
- money همان ارزشِ مبدأ/بازسازی با VWAP است؛ هر سه حالتِ native/mixed/
  reconstructed در طلایی پوشش دارد.
- top50 و دسته‌هایِ جدولِ خلاصه با همان دامنه‌هایِ تریدرزآرنا؛ tie-breakِ
  sortِ پایتون (کدِ نزولی) هم حفظ شده.
- تستِ enrich ردیف‌به‌ردیف با اوراکلِ پایتون: هر یکا، سرانه، قدرت، جریان،
  base و qstate.
EOF
```

---

### Task 4: تجمیع و صنایع

**Files:**
- Create: `backend-go/internal/mstat/agg.go`, `industries.go`
- Create: `backend-go/internal/mstat/agg_test.go`, `industries_test.go`

**Interfaces:**
- Consumes: `loadSnapshot`, `money`, `top50Codes`, `inCategory`, `pyround.Round`.
- Produces:
  `func enrich(snap *Snapshot) []*Row` (پرکردنِ `M` و `Top50`)
  `type Agg struct{...}` + `func aggOf(rows []*Row) *Agg` (فیلدهایِ نهایی رویِ struct)
  `func categoryBuckets(rows []*Row) map[string][]*Row`
  `func selectRows(rows []*Row, cat string) []*Row`
  `func industriesPanel(db *sql.DB) (map[string]any, error)`
  `func asOfMap(snap *Snapshot, top50, n int) map[string]any`

- [ ] **Step 1: Write the failing industries test against the golden**

```go
package mstat

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/parity"
)

func loadGolden(t *testing.T, scenario, name string) map[string]any {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("testdata", "golden", scenario, name+".json"))
	if err != nil {
		t.Fatal(err)
	}
	var v map[string]any
	if err := json.Unmarshal(raw, &v); err != nil {
		t.Fatal(err)
	}
	return v
}

// compareGolden تطبیقِ کاملِ بدنه با canonِ B1؛ استثناها فقط قراردادِ همین
// پنل‌اند (ساعتِ دیواری) و در فهرست صریح آمده‌اند.
func compareGolden(t *testing.T, name string, want, got map[string]any, exclude ...string) {
	t.Helper()
	res := parity.Compare(want, got, parity.Options{Exclude: exclude})
	if !res.Pass {
		for _, d := range res.Diffs {
			t.Errorf("%s: %s", name, d)
		}
		t.Fatalf("%s: %d diffs", name, len(res.Diffs))
	}
}

var pinnedNow = time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)

func TestIndustriesMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := industriesPanel(h.Market)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "industries", loadGolden(t, "s1", "industries"), got)
}
```

Run: `cd backend-go && go test ./internal/mstat/ -run 'Industries'`
Expected: FAIL — undefined.

- [ ] **Step 2: Write `agg.go`**

```go
package mstat

import "math"

type Agg struct {
	N, NTraded int
	Vol, Val   float64
	RB, RS     float64
	IB, IS     float64
	NBI, NSI   int64
	NBN, NSN   int64
	BQ, SQ     float64
	BQV, SQV   float64
	DepthN     int

	PCBuymt, PCSellmt float64 // NaN = None
	Power             float64
	FlowBT, VolBS     float64
	ValBT, ValHemat   float64
	BQBt, SQBt        float64
}

func enrich(snap *Snapshot) []*Row {
	top := top50Codes(snap.Rows)
	for _, r := range snap.Rows {
		r.M = money(r, snap.BaseEst)
		r.Top50 = top[r.Code]
	}
	return snap.Rows
}

func aggOf(rows []*Row) *Agg {
	a := &Agg{}
	for _, r := range rows {
		m := r.M
		if m.Val > 0 {
			a.NTraded++
		}
		a.Vol += m.Vol
		a.Val += m.Val
		a.RB += m.RetailBuy
		a.RS += m.RetailSell
		a.IB += m.InstBuy
		a.IS += m.InstSell
		a.NBI += m.NBuyI
		a.NSI += m.NSellI
		a.NBN += m.NBuyN
		a.NSN += m.NSellN
		if !isNaN(m.BQVal) {
			a.DepthN++
			a.BQ += m.BQVal
			a.SQ += zeroIfNaN(m.SQVal)
			a.BQV += zeroIfNaN(m.BQVol)
			a.SQV += zeroIfNaN(m.SQVol)
		}
	}
	a.N = len(rows)
	a.PCBuymt = nanDiv(div(a.RB, float64(a.NBI)), 1e7)
	a.PCSellmt = nanDiv(div(a.RS, float64(a.NSI)), 1e7)
	a.Power = nanDiv(div(a.PCBuymt, a.PCSellmt), 1)
	a.FlowBT = (a.RB - a.RS) / 1e10
	a.VolBS = a.Vol / 1e9
	a.ValBT = a.Val / 1e10
	a.ValHemat = a.ValBT / 1e3
	a.BQBt = a.BQ / 1e10
	a.SQBt = a.SQ / 1e10
	return a
}

func zeroIfNaN(v float64) float64 {
	if isNaN(v) {
		return 0
	}
	return v
}

// nanDiv همان _div(نتیجه, مخرج) است: None می‌ماند None.
func nanDiv(v *float64, denom float64) float64 {
	if v == nil || denom == 0 || math.IsNaN(*v) {
		return math.NaN()
	}
	return *v / denom
}

func categoryBuckets(rows []*Row) map[string][]*Row {
	out := make(map[string][]*Row, len(categoryRows))
	for _, c := range categoryRows {
		out[c.Key] = nil
	}
	for _, r := range rows {
		for _, c := range categoryRows {
			if c.Key == "top50" {
				if r.Top50 {
					out[c.Key] = append(out[c.Key], r)
				}
			} else if inCategory(r, c.Key, nil) {
				out[c.Key] = append(out[c.Key], r)
			}
		}
	}
	return out
}

func selectRows(rows []*Row, cat string) []*Row {
	out := []*Row{}
	if cat == "top50" {
		for _, r := range rows {
			if r.Top50 {
				out = append(out, r)
			}
		}
		return out
	}
	for _, r := range rows {
		if inCategory(r, cat, nil) {
			out = append(out, r)
		}
	}
	return out
}
```

**دقت:** `nanDiv(div(a.RB, float64(a.NBI)), 1e7)` عیناً `_div(_div(rb,nbi), M_TUMAN_FROM_RIAL)` است؛ اگر `nbi==0` نتیجه None می‌ماند. `Power` هم اگر یکی از دو سرانه None باشد None است.

- [ ] **Step 3: Write `industries.go`**

```go
package mstat

import (
	"database/sql"
	"sort"

	"borsterminal/backend/internal/pyround"
)

type industryBucket struct {
	name          string
	n, pos, neg   int
	val, flow     float64
	bq, sq        float64
	pctSum        float64
	nPct          int
}

func industriesPanel(db *sql.DB) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	by := map[string]*industryBucket{}
	order := []string{}
	for _, r := range rows {
		if r.Cls != paperStock && r.Cls != paperRight {
			continue
		}
		nm := r.SectorName
		if nm == "" {
			continue
		}
		b := by[nm]
		if b == nil {
			b = &industryBucket{name: nm}
			by[nm] = b
			order = append(order, nm)
		}
		b.n++
		if r.Pct != nil && *r.Pct > 0 {
			b.pos++
		} else if r.Pct != nil && *r.Pct < 0 {
			b.neg++
		}
		if r.Pct != nil {
			b.pctSum += *r.Pct
			b.nPct++
		}
		b.val += r.M.Val
		b.flow += r.M.Flow
		b.bq += zeroIfNaN(r.M.BQVal)
		b.sq += zeroIfNaN(r.M.SQVal)
	}
	type outRow struct {
		industry   string
		symbols    int
		positive   int
		negative   int
		avgPct     any
		valueBT    float64
		flowBT     any
		flowPct    any
		buyQueue   float64
		sellQueue  float64
		rankValue  int
		rankFlow   any
		leaderScore int
		leader     bool
	}
	out := make([]*outRow, 0, len(order))
	for _, nm := range order {
		b := by[nm]
		traded := b.val > 0
		var flow any
		var flowPct any
		if traded {
			flow = pyround.Round(b.flow/1e10, 1)
			flowPct = pyround.Round(100.0*b.flow/b.val, 2)
		}
		var avg any
		if b.nPct > 0 {
			avg = pyround.Round(b.pctSum/float64(b.nPct), 2)
		}
		out = append(out, &outRow{
			industry: nm, symbols: b.n, positive: b.pos, negative: b.neg,
			avgPct: avg, valueBT: pyround.Round(b.val/1e10, 1), flowBT: flow,
			flowPct: flowPct,
			buyQueue: pyround.Round(b.bq/1e10, 1), sellQueue: pyround.Round(b.sq/1e10, 1),
		})
	}
	byVal := append([]*outRow(nil), out...)
	sort.SliceStable(byVal, func(i, j int) bool { return byVal[i].valueBT > byVal[j].valueBT })
	rankVal := map[string]int{}
	for i, x := range byVal {
		rankVal[x.industry] = i + 1
	}
	byFlow := []*outRow{}
	for _, x := range out {
		if x.flowBT != nil && x.flowBT.(float64) > 0 {
			byFlow = append(byFlow, x)
		}
	}
	sort.SliceStable(byFlow, func(i, j int) bool {
		return byFlow[i].flowBT.(float64) > byFlow[j].flowBT.(float64)
	})
	rankFlow := map[string]int{}
	for i, x := range byFlow {
		rankFlow[x.industry] = i + 1
	}
	for _, x := range out {
		rv := rankVal[x.industry]
		rf, ok := rankFlow[x.industry]
		x.rankValue = rv
		if ok {
			x.rankFlow = rf
		}
		if ok {
			x.leaderScore = rv + rf
		} else {
			x.leaderScore = (rv) + (len(out) + 1)
		}
	}
	leader := ""
	if len(out) > 0 {
		cand := append([]*outRow(nil), out...)
		sort.SliceStable(cand, func(i, j int) bool { return cand[i].leaderScore < cand[j].leaderScore })
		top := cand[0]
		if top.rankValue <= 5 && top.rankFlow != nil && top.rankFlow.(int) <= 5 {
			leader = top.industry
		}
	}
	for _, x := range out {
		x.leader = x.industry == leader
	}
	sort.SliceStable(out, func(i, j int) bool {
		if out[i].valueBT != out[j].valueBT {
			return out[i].valueBT > out[j].valueBT
		}
		return flowVal(out[i]) > flowVal(out[j])
	})
	rowsOut := make([]map[string]any, 0, len(out))
	for _, x := range out {
		rowsOut = append(rowsOut, map[string]any{
			"industry": x.industry, "symbols": x.symbols,
			"positive": x.positive, "negative": x.negative,
			"avg_pct": x.avgPct, "value_b_toman": x.valueBT,
			"flow_b_toman": x.flowBT, "flow_pct_of_value": x.flowPct,
			"buy_queue_b_toman": x.buyQueue, "sell_queue_b_toman": x.sellQueue,
			"rank_value": x.rankValue, "rank_flow": x.rankFlow,
			"leader_score": x.leaderScore, "leader": x.leader,
		})
	}
	return map[string]any{"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"rows": rowsOut, "leader": nilIfEmpty(leader)}, nil
}

func flowVal(x *outRow) float64 {
	if x.flowBT == nil {
		return 0
	}
	return x.flowBT.(float64)
}

func nilIfEmpty(s string) any {
	if s == "" {
		return nil
	}
	return s
}
```

**دقت‌هایِ الزامی:**
- `leader_score`ِ پایتون: `(rv or len(out)) + (rf if rf else len(out)+1)` — یعنی `rv==0` هم جای‌گزین می‌شود؛ rank_value همیشه ≥۱ است پس `(rv)` کافی است. `rank_flow`ِ صفر ممکن نیست (شروع از ۱).
- `avg_pct` باید `None` باشد وقتی هیچ نمادی `pct` ندارد — نه ۰.
- ترتیبِ نهایی: `(-value_b_toman, -(flow_b_toman or 0))`؛ با `sort.SliceStable` و مقایسهٔ «بزرگ‌تر» در هر دو کلید.
- `leader` در پایتون رشته یا `None` است (نه `""`).

- [ ] **Step 4: Run the tests**

Run: `cd backend-go && go test ./internal/mstat/ -run 'Industries|Snapshot'`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/mstat/agg.go \
        backend-go/internal/mstat/industries.go backend-go/internal/mstat/agg_test.go \
        backend-go/internal/mstat/industries_test.go
git commit -F - <<'EOF'
feat(go): تجمیع و صنایعِ وضعیت بازار

- aggOf همان _agg است؛ Noneهایِ سرانه و قدرت NaN می‌مانند و در JSON null
  می‌شوند، نه صفر.
- industries رتبه‌بندیِ دومعیارهٔ FTS (ارزش + ورود پول) با همان قاعدهٔ لیدر و
  همان None برایِ صنعتِ بی‌معامله.
EOF
```

---

### Task 5: هیستوگرام، دماسنج، عمق و تفکیکِ حقیقی/حقوقی

**Files:**
- Create: `backend-go/internal/mstat/panels.go`
- Create: `backend-go/internal/mstat/panels_test.go`

**Interfaces:**
- Produces:
  `func histogramPanel(db *sql.DB, group string) (map[string]any, error)`
  `func thermometerPanel(db *sql.DB, group string) (map[string]any, error)`
  `func depthPanel(db *sql.DB, group string) (map[string]any, error)`
  `func clientSplitPanel(db *sql.DB, tab string) (map[string]any, error)`

- [ ] **Step 1: Write the failing golden tests**

```go
package mstat

import (
	"testing"
)

func TestPanelsMatchGolden(t *testing.T) {
	h := openFixture(t)
	cases := []struct {
		name string
		run  func() (map[string]any, error)
	}{
		{"histogram_all", func() (map[string]any, error) { return histogramPanel(h.Market, "all") }},
		{"histogram_eq_all", func() (map[string]any, error) { return histogramPanel(h.Market, "eq_all") }},
		{"thermometer_all", func() (map[string]any, error) { return thermometerPanel(h.Market, "all") }},
		{"thermometer_eq_all", func() (map[string]any, error) { return thermometerPanel(h.Market, "eq_all") }},
		{"depth_all", func() (map[string]any, error) { return depthPanel(h.Market, "all") }},
		{"depth_eq_all", func() (map[string]any, error) { return depthPanel(h.Market, "eq_all") }},
		{"clientsplit_all", func() (map[string]any, error) { return clientSplitPanel(h.Market, "all") }},
		{"clientsplit_fixed", func() (map[string]any, error) { return clientSplitPanel(h.Market, "fixed") }},
	}
	for _, c := range cases {
		got, err := c.run()
		if err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		compareGolden(t, c.name, loadGolden(t, "s1", c.name), got)
	}
}
```

Run: `cd backend-go && go test ./internal/mstat/ -run Panels`
Expected: FAIL — undefined.

- [ ] **Step 2: Write `panels.go`**

```go
package mstat

import (
	"database/sql"

	"borsterminal/backend/internal/pyround"
)

func hit(v, lo, hi float64) bool {
	if lo == -1e9 {
		return v <= hi
	}
	if hi == 1e9 {
		return v > lo
	}
	return lo < v && v <= hi
}

func tally(pcts []*float64, spec []histoSpec) []map[string]any {
	counts := make([]int, len(spec))
	for _, p := range pcts {
		if p == nil {
			continue
		}
		for i, b := range spec {
			if hit(*p, b.Lo, b.Hi) {
				counts[i]++
				break
			}
		}
	}
	out := make([]map[string]any, len(spec))
	for i, b := range spec {
		out[i] = map[string]any{"key": b.Key, "label": b.Label,
			"color": b.Color, "count": counts[i]}
	}
	return out
}

func histogramPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	sel := []*Row{}
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol > 0 {
			sel = append(sel, r)
		}
	}
	pcts := make([]*float64, 0, len(sel))
	known := 0
	for _, r := range sel {
		pcts = append(pcts, r.Pct)
		if r.Pct != nil {
			known++
		}
	}
	notTraded := 0
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol <= 0 {
			notTraded++
		}
	}
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "basis": "closing_vs_yesterday", "traded_only": true,
		"histo12": tally(pcts, histo12), "histo7": tally(pcts, histo7),
		"known": known, "nodata": len(pcts) - known, "total": len(sel),
		"not_traded": notTraded,
	}, nil
}

func thermometerPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	sel := []*Row{}
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol > 0 {
			sel = append(sel, r)
		}
	}
	pos, neg, flat := 0, 0, 0
	for _, r := range sel {
		switch {
		case r.Pct != nil && *r.Pct > 0:
			pos++
		case r.Pct != nil && *r.Pct < 0:
			neg++
		case r.Pct != nil && *r.Pct == 0:
			flat++
		}
	}
	known := pos + neg + flat
	var posPct, negPct any
	entry := false
	if known > 0 {
		p := pyround.Round(100.0*float64(pos)/float64(known), 1)
		n := pyround.Round(100.0*float64(neg)/float64(known), 1)
		posPct, negPct = p, n
		entry = n >= 80.0
	}
	notTraded := 0
	for _, r := range rows {
		if inCategory(r, group, nil) && r.M.Vol <= 0 {
			notTraded++
		}
	}
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "positive": pos, "negative": neg, "zero": flat,
		"nodata": len(sel) - known, "not_traded": notTraded,
		"positive_pct": posPct, "negative_pct": negPct,
		"entry_opportunity": entry, "entry_rule_pct": 80.0,
	}, nil
}

func depthPanel(db *sql.DB, group string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	sel := []*Row{}
	have := []*Row{}
	for _, r := range rows {
		if !inCategory(r, group, nil) {
			continue
		}
		sel = append(sel, r)
		if !isNaN(r.M.BQVal) {
			have = append(have, r)
		}
	}
	buyVal, sellVal := 0.0, 0.0
	for _, r := range have {
		buyVal += zeroIfNaN(r.M.BQVal)
		sellVal += zeroIfNaN(r.M.SQVal)
	}
	one := func(side string) map[string]any {
		normal, below, noTrade, unknown := 0, 0, 0, 0
		for _, r := range have {
			qv, opp := r.M.BQVal, r.M.SQVal
			if side == "sell" {
				qv, opp = r.M.SQVal, r.M.BQVal
			}
			if isEmpty(qv) || !isEmpty(opp) {
				continue
			}
			if r.M.Vol <= 0 {
				noTrade++
				continue
			}
			qvol := r.M.BQVol
			if side == "sell" {
				qvol = r.M.SQVol
			}
			base := r.M.Base
			if isNaN(base) || isNaN(qvol) {
				unknown++
			} else if qvol < base {
				below++
			} else {
				normal++
			}
		}
		return map[string]any{"normal": normal, "below_base": below,
			"no_trade": noTrade, "base_unknown": unknown}
	}
	bqCnt, sqCnt := 0, 0
	for _, r := range have {
		if r.M.QState == "b" {
			bqCnt++
		}
		if r.M.QState == "s" {
			sqCnt++
		}
	}
	var ratio any
	if sellVal != 0 {
		ratio = pyround.Round(buyVal/sellVal, 2)
	}
	_ = sel
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "depth_available": len(have) > 0,
		"symbols_with_depth": len(have),
		"buy_queue_b_toman":  pyround.Round(buyVal/1e10, 1),
		"sell_queue_b_toman": pyround.Round(sellVal/1e10, 1),
		"ratio": ratio, "buy_queue_count": bqCnt, "sell_queue_count": sqCnt,
		"buy": one("buy"), "sell": one("sell"),
	}, nil
}

var tabCat = map[string]string{
	"all": "all", "eq_funds": "eq_all", "stock": "stock_right", "eq_fund": "eq_fund",
	"fixed": "fixed_fund", "top50": "top50", "lev": "lev_fund",
	"gold": "gold_fund", "silver": "silver_fund",
}

func sideShare(retail, legal float64) any {
	if isNaN(retail) || isNaN(legal) || retail < 0 || legal < 0 {
		return nil
	}
	den := retail + legal
	if den <= 0 {
		return nil
	}
	return pyround.Round(100.0*retail/den, 1)
}

func complement(share any) any {
	if share == nil {
		return nil
	}
	return pyround.Round(100.0-share.(float64), 1)
}

func clientSplitPanel(db *sql.DB, tab string) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	cat, ok := tabCat[tab]
	if !ok {
		cat = "all"
	}
	a := aggOf(selectRows(rows, cat))
	rbuy := sideShare(a.RB, a.IB)
	rsell := sideShare(a.RS, a.IS)
	bt := func(v float64) float64 { return pyround.Round(v/1e10, 1) }
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"tab": tab, "symbols": a.N,
		"retail": map[string]any{
			"buy_count": a.NBI, "buy_b_toman": bt(a.RB), "buy_pct": rbuy,
			"sell_count": a.NSI, "sell_b_toman": bt(a.RS), "sell_pct": rsell,
		},
		"institutional": map[string]any{
			"buy_count": a.NBN, "buy_b_toman": bt(a.IB), "buy_pct": complement(rbuy),
			"sell_count": a.NSN, "sell_b_toman": bt(a.IS), "sell_pct": complement(rsell),
		},
		"pc_buy_m_toman":      nilOrRound(a.PCBuymt, 1),
		"pc_sell_m_toman":     nilOrRound(a.PCSellmt, 1),
		"power":               nilOrRound(a.Power, 2),
		"money_flow_b_toman":  pyround.Round(a.FlowBT, 1),
	}, nil
}
```

**دقت‌هایِ الزامی:**
- `sideShare` همان `client_split.side_share` است: مقدارِ منفی/NaN/None ⇒ None؛ مخرجِ صفر ⇒ None. جمعِ ارزش‌ها از `money()` می‌آید، پس `value_source` مسئولیتِ این لایه نیست.
- در `depthPanel` شرطِ پایتون `if not qv or opp: continue` است: `qv` صفر/None یا `opp` ناصفر ⇒ رد. `isEmpty` همین است.
- در `clientSplitPanel` اگر `tab` ناشناخته باشد پایتون `_TAB_CAT.get(tab,"all")` می‌دهد؛ اما نامِ `tab` در پاسخ همان مقدارِ خام است.
- `entry_rule_pct` عددِ ۸۰ است و از ثابتِ `ENTRY_OPPORTUNITY_NEG_PCT` می‌آید؛ در Go یک ثابت `const entryOpportunityNegPct = 80.0` در `panels.go` بگذارید و در هر دو پنل استفاده کنید.

- [ ] **Step 3: Run the tests**

Run: `cd backend-go && go test ./internal/mstat/ -run Panels`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend-go/internal/mstat/panels.go backend-go/internal/mstat/panels_test.go
git commit -F - <<'EOF'
feat(go): هیستوگرام، دماسنج، عمق و تفکیکِ حقیقی/حقوقی

- مرزهایِ سطل‌ها نیم‌باز/نیم‌بسته‌اند تا جمعِ میله‌ها از تعدادِ نمادها بیشتر
  نشود؛ سطل‌ها همیشه کامل‌اند.
- دماسنج فقط نمادهایِ معامله‌شده را می‌شمارد و سهمِ حقیقی/حقوقی را با همان
  کسرِ تک‌تعریف و همان None برایِ مخرجِ صفر می‌دهد.
- عمق «بی‌داده» را از «صفر» جدا می‌کند و سطلِ «مبنا نامعلوم» را نگه می‌دارد.
EOF
```

---

---

### Task 6: مرحلِ جلسه، شاخص/ارزشِ بازار، سلامتِ کلان و جدولِ خلاصه

**Files:**
- Create: `backend-go/internal/marketphase/marketphase.go`, `marketphase_test.go`
- Create: `backend-go/internal/mstat/market.go`, `summary.go`
- Create: `backend-go/internal/mstat/market_test.go`, `summary_test.go`

**Interfaces:**
- Produces:
  `marketphase.Resolve(officialState, officialTitle *string, activityDay, activityHEven *int64, updatedAt *string, boardDay *int64, now time.Time) Phase`
  `marketphase.FromDB(db *sql.DB, now time.Time) Phase`
  `func marketIndexSeries(db *sql.DB, limit int) []map[string]any`
  `func marketIndex(db *sql.DB) map[string]any`
  `func marketTotalRials(db *sql.DB) (float64, string)`
  `func macroHealthFrom(eq, all *Agg, totalRials float64, totalSource string, phase *marketphase.Phase, db *sql.DB) map[string]any`
  `func marketSnapshotPanel(db *sql.DB, now time.Time) (map[string]any, error)`
  `func summaryPanel(db *sql.DB, now time.Time) (map[string]any, error)`

- [ ] **Step 1: Write the failing phase test**

```go
package marketphase

import (
	"testing"
	"time"
)

func ip(v int64) *int64    { return &v }
func sp(v string) *string  { return &v }

var now = time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local) // چهارشنبه

func TestResolveBranches(t *testing.T) {
	cases := []struct {
		name    string
		state   *string
		title   *string
		act     *int64
		want    string
		source  string
		verdict bool
	}{
		{"closed past day", sp("F"), sp("بسته"), ip(20261014), Closed, "tsetmc_marketState", true},
		{"holiday friday", sp("F"), sp("بسته"), ip(20261016), Holiday, "tsetmc_marketState", true},
		{"no official", nil, nil, ip(20261014), Unknown, "none", false},
		{"today before open", sp("F"), sp("بسته"), ip(20261028), PreOpen, "tsetmc_marketState", false},
		{"today mid-session closed state", sp("F"), sp("بسته"), ip(20261028), Unknown, "tsetmc_marketState", false},
		{"official open by title", nil, sp("باز"), ip(20261028), Continuous, "tsetmc_marketState", true},
		{"unmapped state", sp("Z"), sp("چیز"), ip(20261014), Unknown, "tsetmc_marketState_unmapped", false},
	}
	for _, c := range cases {
		at := now
		if c.name == "today before open" {
			at = time.Date(2026, 10, 28, 8, 30, 0, 0, time.Local)
		}
		got := Resolve(c.state, c.title, c.act, ip(123000), sp("2026-10-14 12:30:00"), nil, at)
		if got.Phase != c.want || got.PhaseSource != c.source || got.VerdictAllowed != c.verdict {
			t.Errorf("%s: %s/%s/%v, want %s/%s/%v", c.name, got.Phase,
				got.PhaseSource, got.VerdictAllowed, c.want, c.source, c.verdict)
		}
		if got.ClockNow != at.Format("2006-01-02 15:04:05") {
			t.Errorf("%s clock_now = %s", c.name, got.ClockNow)
		}
	}
}

func TestResolveNotComputableOrder(t *testing.T) {
	got := Resolve(sp("F"), sp("بسته"), ip(20261028), ip(100000), nil, nil, now)
	want := []string{"realized_flow", "session_vs_threshold", "close_price_final"}
	if len(got.NotComputable) != len(want) {
		t.Fatalf("not_computable = %v", got.NotComputable)
	}
	for i := range want {
		if got.NotComputable[i] != want[i] {
			t.Fatalf("not_computable[%d] = %s, want %s", i, got.NotComputable[i], want[i])
		}
	}
}
```

Run: `cd backend-go && go test ./internal/marketphase/`
Expected: FAIL — package does not exist.

- [ ] **Step 2: Write `marketphase.go`**

```go
// Package marketphase تنها تعریفِ «جلسه در کدام مرحله است» — پورتِ
// market_phase.py. هیچ آستانه‌ای این‌جا ساخته نمی‌شود.
package marketphase

import (
	"database/sql"
	"strings"
	"time"
)

const (
	PreOpen    = "pre_open"
	Continuous = "continuous"
	Closed     = "closed"
	Holiday    = "holiday"
	Unknown    = "unknown"
)

var labels = map[string]string{
	PreOpen: "پیش از آغازِ معاملات", Continuous: "معاملات جاری",
	Closed: "پایانِ نشست", Holiday: "تعطیلِ رسمی", Unknown: "مرحل نامشخص",
}

// compOrder ترتیبِ کلیدها در not_computable است (dictِ پایتون ترتیب دارد).
var compOrder = []string{"realized_flow", "order_pressure", "session_vs_threshold", "close_price_final"}

var computable = map[string]map[string]bool{
	PreOpen:    {"realized_flow": false, "order_pressure": true, "session_vs_threshold": false, "close_price_final": false},
	Continuous: {"realized_flow": true, "order_pressure": true, "session_vs_threshold": true, "close_price_final": false},
	Closed:     {"realized_flow": true, "order_pressure": false, "session_vs_threshold": true, "close_price_final": true},
	Holiday:    {"realized_flow": true, "order_pressure": false, "session_vs_threshold": true, "close_price_final": true},
	Unknown:    {"realized_flow": false, "order_pressure": false, "session_vs_threshold": false, "close_price_final": false},
}

var whyNot = map[string]string{
	"realized_flow":        "هنوز معامله‌ای ثبت نشده؛ جمعِ صف با پولِ تحقق‌یافته یکی نیست",
	"session_vs_threshold": "جمعِ نشست کامل نشده، پس با آستانهِٔ تمام‌روز سنجیده نمی‌شود",
	"close_price_final":    "قیمت پایانیِ نهایی هنوز ساخته نشده",
	"order_pressure":       "دفترِ سفارشِ همین نشست در دسترس نیست",
}

type Phase struct {
	Phase              string          `json:"phase"`
	Label              string          `json:"label"`
	PhaseSource        string          `json:"phase_source"`
	Official           bool            `json:"official"`
	OfficialState      *string         `json:"official_state"`
	OfficialStateTitle *string         `json:"official_state_title"`
	SessionDay         *int64          `json:"session_day"`
	ActivityHEven      *int64          `json:"activity_h_even"`
	IsLive             bool            `json:"is_live"`
	VerdictAllowed     bool            `json:"verdict_allowed"`
	Computable         map[string]bool `json:"computable"`
	NotComputable      []string        `json:"not_computable"`
	WhyNot             map[string]string `json:"why_not"`
	DataUpdatedAt      *string         `json:"data_updated_at"`
	ClockNow           string          `json:"clock_now"`
	SessionStart       string          `json:"session_start"`
	SessionEnd         string          `json:"session_end"`
}

func daysIn(y int, m time.Month) int {
	return time.Date(y, m+1, 0, 0, 0, 0, 0, time.UTC).Day()
}

// dateFromDEven همان _d_even_to_date: تاریخِ معتبر یا «نیست».
func dateFromDEven(d int64) (time.Time, bool) {
	if d <= 0 {
		return time.Time{}, false
	}
	y := int(d / 10000)
	m := time.Month((d / 100) % 100)
	day := int(d % 100)
	if y < 1 || y > 9999 || m < 1 || m > 12 || day < 1 || day > daysIn(y, m) {
		return time.Time{}, false
	}
	return time.Date(y, m, day, 0, 0, 0, 0, time.UTC), true
}

func isTehranWeekend(d time.Time) bool {
	wd := d.Weekday()
	return wd == time.Thursday || wd == time.Friday
}

func minuteOfDay(t time.Time) int { return t.Hour()*60 + t.Minute() }

func Resolve(officialState, officialTitle *string, activityDay, activityHEven *int64,
	updatedAt *string, boardDay *int64, now time.Time) Phase {
	var st *string
	if officialState != nil {
		v := strings.ToUpper(strings.TrimSpace(*officialState))
		if v != "" {
			st = &v
		}
	}
	var title *string
	if officialTitle != nil {
		if v := strings.TrimSpace(*officialTitle); v != "" {
			title = &v
		}
	}
	var act *time.Time
	if activityDay != nil {
		if t, ok := dateFromDEven(*activityDay); ok {
			act = &t
		}
	}
	if act == nil && boardDay != nil {
		if t, ok := dateFromDEven(*boardDay); ok {
			act = &t
		}
	}
	today := time.Date(now.Year(), now.Month(), now.Day(), 0, 0, 0, 0, time.UTC)
	officialSeen := st != nil || title != nil
	officiallyClosed := (st != nil && *st == "F") || (title != nil && strings.Contains(*title, "بسته"))
	officiallyOpen := title != nil && strings.HasSuffix(*title, "باز")
	sameDay := act != nil && act.Equal(today)
	weekend := act != nil && isTehranWeekend(*act)

	var phase, source string
	switch {
	case officiallyOpen:
		phase, source = Continuous, "tsetmc_marketState"
	case officiallyClosed:
		hm := minuteOfDay(now)
		switch {
		case weekend:
			phase = Holiday
		case sameDay && hm < 9*60:
			phase = PreOpen
		case sameDay && hm < 12*60+30:
			phase = Unknown
		default:
			phase = Closed
		}
		source = "tsetmc_marketState"
	case officialSeen:
		phase, source = Unknown, "tsetmc_marketState_unmapped"
	default:
		hm := minuteOfDay(now)
		switch {
		case weekend:
			phase, source = Holiday, "calendar"
		case sameDay && hm < 9*60:
			phase, source = PreOpen, "calendar"
		case sameDay && hm >= 12*60+30:
			phase, source = Closed, "calendar"
		default:
			phase, source = Unknown, "none"
		}
	}
	comp := computable[phase]
	not := []string{}
	why := map[string]string{}
	for _, k := range compOrder {
		if !comp[k] {
			not = append(not, k)
			why[k] = whyNot[k]
		}
	}
	var sessionDay *int64
	if act != nil {
		d := int64(act.Year())*10000 + int64(act.Month())*100 + int64(act.Day())
		sessionDay = &d
	}
	var ah *int64
	if activityHEven != nil && *activityHEven != 0 {
		v := *activityHEven
		ah = &v
	}
	return Phase{
		Phase: phase, Label: labels[phase], PhaseSource: source,
		Official:      officialSeen && source == "tsetmc_marketState",
		OfficialState: st, OfficialStateTitle: title,
		SessionDay: sessionDay, ActivityHEven: ah,
		IsLive:         phase == Continuous,
		VerdictAllowed: phase == Continuous || phase == Closed || phase == Holiday,
		Computable:     comp, NotComputable: not, WhyNot: why,
		DataUpdatedAt: updatedAt, ClockNow: now.Format("2006-01-02 15:04:05"),
		SessionStart: "09:00", SessionEnd: "12:30",
	}
}

func FromDB(db *sql.DB, now time.Time) Phase {
	var d, ah sql.NullInt64
	var updated, ms, mst sql.NullString
	err := db.QueryRow(`SELECT d_even, updated_at, market_state, market_state_title,
	    activity_h_even FROM market_index ORDER BY d_even DESC LIMIT 1`).
		Scan(&d, &updated, &ms, &mst, &ah)
	var board sql.NullInt64
	_ = db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&board)
	var boardPtr *int64
	if board.Valid {
		v := board.Int64
		boardPtr = &v
	}
	if err != nil {
		return Resolve(nil, nil, nil, nil, nil, boardPtr, now)
	}
	var dPtr, ahPtr *int64
	if d.Valid {
		v := d.Int64
		dPtr = &v
	}
	if ah.Valid {
		v := ah.Int64
		ahPtr = &v
	}
	var uPtr, msPtr, mstPtr *string
	if updated.Valid {
		v := updated.String
		uPtr = &v
	}
	if ms.Valid {
		v := ms.String
		msPtr = &v
	}
	if mst.Valid {
		v := mst.String
		mstPtr = &v
	}
	return Resolve(msPtr, mstPtr, dPtr, ahPtr, uPtr, boardPtr, now)
}
```

- [ ] **Step 3: Write `market.go`**

```go
package mstat

import (
	"database/sql"
	"time"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

func optZero(v float64) any {
	if isNaN(v) || v == 0 {
		return nil
	}
	return v
}

// marketIndexSeries همان market_index_series؛ جدولِ نبود ⇒ nil.
func marketIndexSeries(db *sql.DB, limit int) []map[string]any {
	n := limit
	if n < 1 {
		n = 1
	}
	if n > 60 {
		n = 60
	}
	wide := `SELECT d_even, idx_last, idx_change, idx_pct, ew_last, ew_change,
	    ew_pct, z_tot_tran, q_tot_cap, q_tot_tran FROM market_index
	    ORDER BY d_even DESC LIMIT ?`
	rows, err := db.Query(wide, n)
	hasTotals := true
	if err != nil {
		rows, err = db.Query(`SELECT d_even, idx_last, idx_change, idx_pct,
		    ew_last, ew_change, ew_pct FROM market_index
		    ORDER BY d_even DESC LIMIT ?`, n)
		hasTotals = false
	}
	if err != nil {
		return nil
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var d sql.NullInt64
		vals := make([]sql.NullFloat64, 9)
		ptrs := []any{&d}
		for i := range vals {
			ptrs = append(ptrs, &vals[i])
		}
		if hasTotals {
			if err := rows.Scan(ptrs...); err != nil {
				return out
			}
		} else {
			if err := rows.Scan(ptrs[:8]...); err != nil {
				return out
			}
		}
		o := func(v sql.NullFloat64) any {
			if !v.Valid {
				return nil
			}
			return optZero(v.Float64)
		}
		m := map[string]any{
			"d_even": d.Int64,
			"last": o(vals[0]), "change": o(vals[1]), "pct": o(vals[2]),
			"ew_last": o(vals[3]), "ew_change": o(vals[4]), "ew_pct": o(vals[5]),
			"z_tot_tran": nil, "q_tot_cap": nil, "q_tot_tran": nil,
		}
		if hasTotals {
			m["z_tot_tran"] = o(vals[6])
			m["q_tot_cap"] = o(vals[7])
			m["q_tot_tran"] = o(vals[8])
		}
		out = append(out, m)
	}
	return out
}

func marketIndex(db *sql.DB) map[string]any {
	series := marketIndexSeries(db, 1)
	if len(series) == 0 {
		return nil
	}
	s := series[0]
	return map[string]any{
		"d_even": s["d_even"], "last": s["last"], "change": s["change"],
		"pct": s["pct"], "ew_last": s["ew_last"], "ew_change": s["ew_change"],
		"ew_pct": s["ew_pct"],
	}
}

// marketTotalRials همان market_total_rials: عددِ رسمی اگر باورپذیر باشد،
// وگرنه جمعِ dedupedِ تابلو، وگرنه صفر با منبعِ unavailable.
func marketTotalRials(db *sql.DB) (float64, string) {
	est := 0.0
	var sum sql.NullFloat64
	if err := db.QueryRow(`SELECT SUM(mc) FROM (SELECT MAX(market_cap) AS mc
	    FROM market_watch WHERE market_cap > 0
	    AND d_even = (SELECT MAX(d_even) FROM market_watch)
	    GROUP BY total_shares)`).Scan(&sum); err == nil && sum.Valid {
		est = sum.Float64
	}
	rows, err := db.Query(`SELECT d_even, market_value FROM market_totals
	    ORDER BY d_even DESC LIMIT 5`)
	if err == nil {
		defer rows.Close()
		vals := []float64{}
		for rows.Next() {
			var d sql.NullInt64
			var v sql.NullFloat64
			if rows.Scan(&d, &v) == nil && v.Valid && v.Float64 > 0 {
				vals = append(vals, v.Float64)
			}
		}
		if len(vals) > 0 {
			lo := est
			if lo <= 0 {
				lo = vals[0]
				for _, v := range vals {
					if v > lo {
						lo = v
					}
				}
			}
			lo *= 0.5
			for _, v := range vals {
				if v >= lo {
					return v, "tse_market_overview"
				}
			}
		}
	}
	if est > 0 {
		return est, "board_sum_deduped"
	}
	return 0, "unavailable"
}

func optional(f float64) any {
	if isNaN(f) {
		return nil
	}
	return f
}

func macroHealthFrom(eq, all *Agg, totalRials float64, totalSource string,
	ph *marketphase.Phase, db *sql.DB) map[string]any {
	var marketValue any
	if totalRials > 0 {
		marketValue = pyround.Round(totalRials/1e13, 1)
	}
	if ph != nil && !ph.VerdictAllowed {
		why := []string{}
		for _, k := range ph.NotComputable {
			if k == "order_pressure" {
				continue
			}
			why = append(why, ph.WhyNot[k])
		}
		return map[string]any{
			"value_hemat": nil, "state": "nodata", "label": ph.Label,
			"basis": "eq_all", "phase": ph.Phase, "phase_source": ph.PhaseSource,
			"phase_official": ph.Official, "session_day": ph.SessionDay,
			"why": why, "trade_value_all_market_hemat": nil,
			"market_value_hemat":  marketValue,
			"market_value_source": nilIfEmpty(totalSource),
			"excellent":           false, "good_min": 20.0, "bad_max": 10.0,
		}
	}
	if eq == nil || eq.NTraded == 0 {
		var lastSess, lastVal any
		if db != nil {
			var d sql.NullInt64
			var v sql.NullFloat64
			if db.QueryRow(`SELECT d_even, value_hemat FROM market_liquidity
			    WHERE value_hemat > 0 ORDER BY d_even DESC LIMIT 1`).
				Scan(&d, &v) == nil && d.Valid {
				lastSess = d.Int64
				lastVal = pyround.Round(v.Float64, 2)
			}
		}
		cause := "unknown"
		if ph != nil && ph.IsLive {
			cause = "no_trades_yet"
		}
		var phase, src any
		var day any
		if ph != nil {
			phase, src, day = ph.Phase, ph.PhaseSource, ph.SessionDay
		}
		return map[string]any{
			"value_hemat": nil, "state": "nodata", "label": "بدون داده",
			"basis": "eq_all", "cause": cause, "session_day": day,
			"phase": phase, "phase_source": src,
			"last_traded_session": lastSess, "last_value_hemat": lastVal,
			"trade_value_all_market_hemat": nil,
			"market_value_hemat":           marketValue,
			"market_value_source":          nilIfEmpty(totalSource),
			"excellent":                    false, "good_min": 20.0, "bad_max": 10.0,
		}
	}
	hemat := eq.ValHemat
	state, label := "mid", "متوسط"
	if hemat >= 20.0 {
		state, label = "good", "مساعد"
	} else if hemat <= 10.0 {
		state, label = "bad", "نامساعد"
	}
	out := map[string]any{
		"value_hemat": pyround.Round(hemat, 2), "state": state, "label": label,
		"basis": "eq_all", "excellent": hemat >= 50.0,
		"good_min": 20.0, "bad_max": 10.0, "excellent_min": 50.0,
		"trade_value_all_market_hemat": nil, "market_value_hemat": marketValue,
		"market_value_source": nilIfEmpty(totalSource),
	}
	if all != nil {
		out["trade_value_all_market_hemat"] = pyround.Round(all.ValHemat, 2)
	}
	if ph != nil {
		out["phase"] = ph.Phase
		out["phase_label"] = ph.Label
		out["phase_source"] = ph.PhaseSource
		out["phase_official"] = ph.Official
		out["session_day"] = ph.SessionDay
		out["session_is_live"] = ph.IsLive
	}
	return out
}

func macroHealth(db *sql.DB, now time.Time) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	ph := marketphase.FromDB(db, now)
	total, source := marketTotalRials(db)
	return macroHealthFrom(aggOf(selectRows(rows, "eq_all")), aggOf(rows),
		total, source, &ph, db), nil
}

func marketSnapshotPanel(db *sql.DB, now time.Time) (map[string]any, error) {
	series := marketIndexSeries(db, 2)
	var cur, prev map[string]any
	if len(series) > 0 {
		cur = series[0]
	}
	if len(series) > 1 {
		prev = series[1]
	}
	macro, err := macroHealth(db, now)
	if err != nil {
		return nil, err
	}
	var index any
	if cur != nil {
		index = map[string]any{
			"d_even": cur["d_even"], "last": cur["last"], "change": cur["change"],
			"pct": cur["pct"], "ew_last": cur["ew_last"],
			"ew_change": cur["ew_change"], "ew_pct": cur["ew_pct"],
		}
	}
	var tradeValue, volume, trades any
	var asof any = nil
	if cur != nil {
		asof = map[string]any{"d_even": cur["d_even"]}
		if v, ok := cur["q_tot_cap"].(float64); ok && v != 0 {
			tradeValue = pyround.Round(v/1e13, 2)
		}
		volume = cur["q_tot_tran"]
		trades = cur["z_tot_tran"]
	}
	retail := map[string]any{
		"value_hemat": macro["value_hemat"], "state": macro["state"],
		"label": macro["label"], "basis": macro["basis"],
		"cause": macro["cause"], "good_min": macro["good_min"],
		"bad_max": macro["bad_max"], "excellent_min": macro["excellent_min"],
	}
	return map[string]any{
		"status": "ok", "asof": asof, "index": index, "prev": prev,
		"market": map[string]any{
			"trade_value_hemat": tradeValue, "volume": volume, "trades": trades,
			"market_value_hemat": macro["market_value_hemat"],
		},
		"retail": retail,
	}, nil
}
```

**دقت‌ها:** `retail` فقط همان هشت کلید را دارد؛ `cause`/`excellent_min` در شاخهٔ عادی نیستند و باید `nil` باشند — دسترسی به mapِ غایب در Go همان nil می‌دهد. `prev` خودِ ردیفِ دومِ سری است (نه زیرمجموعه). `asof` وقتی `cur` نیست `null` است.

- [ ] **Step 4: Write `summary.go`**

```go
package mstat

import (
	"database/sql"
	"time"

	"borsterminal/backend/internal/marketphase"
	"borsterminal/backend/internal/pyround"
)

func asOfMap(snap *Snapshot, top50, n int) map[string]any {
	m := map[string]any{
		"h_even": snap.AsOf.HEven, "depth": snap.AsOf.Depth,
		"top50": top50, "n": n, "d_even": nil, "client_d_even": nil,
		"client_lag_days": nil,
	}
	if snap.AsOf.DEven != nil {
		m["d_even"] = *snap.AsOf.DEven
	}
	if snap.AsOf.ClientDEven != nil {
		m["client_d_even"] = *snap.AsOf.ClientDEven
	}
	if snap.AsOf.ClientLag != nil {
		m["client_lag_days"] = *snap.AsOf.ClientLag
	}
	return m
}

func summaryPanel(db *sql.DB, now time.Time) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	buckets := categoryBuckets(rows)
	out := make([]map[string]any, 0, len(categoryRows))
	for _, c := range categoryRows {
		a := aggOf(buckets[c.Key])
		out = append(out, map[string]any{
			"key": c.Key, "label": c.Label,
			"symbols": a.N, "traded": a.NTraded,
			"volume_b_shares":    pyround.Round(a.VolBS, 3),
			"value_b_toman":      pyround.Round(a.ValBT, 1),
			"pc_buy_m_toman":     nilOrRound(a.PCBuymt, 1),
			"pc_sell_m_toman":    nilOrRound(a.PCSellmt, 1),
			"buy_power":          nilOrRound(a.Power, 2),
			"buy_power_up":       !isNaN(a.Power) && a.Power >= 1.0,
			"money_flow_b_toman": pyround.Round(a.FlowBT, 1),
		})
	}
	ph := marketphase.FromDB(db, now)
	total, source := marketTotalRials(db)
	return map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"rows": out, "phase": ph,
		// conn=nil عینِ فراخوانِ پایتون در summary است: fallbackِ market_liquidity
		// فقط در macro_health (که market_snapshot صدایش می‌زند) فعال است.
		"health": macroHealthFrom(aggOf(buckets["eq_all"]), aggOf(buckets["all"]),
			total, source, &ph, nil),
	}, nil
}

func nilOrRound(v float64, n int) any {
	if isNaN(v) {
		return nil
	}
	return pyround.Round(v, n)
}
```

**توجه:** `now` در `summaryPanel` تزریق می‌شود تا طلاییِ `phase.clock_now` هم قابلِ سنجش باشد؛ در تولید `time.Now()` از سرویس می‌آید.

- [ ] **Step 5: Write the golden tests**

```go
func TestPhaseGoldens(t *testing.T) {
	h := openFixture(t)
	for _, s := range []string{"s1", "s3", "s4"} {
		got := marketphase.FromDB(h.Market, pinnedNow)
		want := loadGolden(t, s, "phase")
		compareGolden(t, s+" phase", want, toMap(t, got))
	}
}

func TestSummaryMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := summaryPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "summary", loadGolden(t, "s1", "summary"), got)
}

func TestMarketSnapshotMatchesGolden(t *testing.T) {
	h := openFixture(t)
	got, err := marketSnapshotPanel(h.Market, pinnedNow)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "market-snapshot", loadGolden(t, "s1", "market_snapshot"), got)
}
```

`toMap` را در `summary_test.go` بگذارید:

```go
func toMap(t *testing.T, v any) map[string]any {
	t.Helper()
	raw, err := json.Marshal(v)
	if err != nil {
		t.Fatal(err)
	}
	var m map[string]any
	if err := json.Unmarshal(raw, &m); err != nil {
		t.Fatal(err)
	}
	return m
}
```

Run: `cd backend-go && go test ./internal/marketphase/ ./internal/mstat/ -run 'Phase|Summary|Snapshot'`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend-go/internal/marketphase backend-go/internal/mstat/market.go \
        backend-go/internal/mstat/summary.go backend-go/internal/mstat/market_test.go \
        backend-go/internal/mstat/summary_test.go
git commit -F - <<'EOF'
feat(go): مرحلِ جلسه، شاخص و ارزشِ بازار، سلامتِ کلان و جدولِ خلاصه

- marketphase همان resolve/from_db است؛ پنج شاخهٔ مرحل و ترتیبِ
  not_computable با تستِ جدولی قفل شده‌اند.
- بازارِ رسمی (market_index/market_totals) تنها منبعِ شاخص و ارزش است؛ عددِ
  نصفه با همان قاعدهٔ باورپذیری رد می‌شود.
- سلامتِ کلان در مرحلِ بی‌اجازه «بدون داده» می‌دهد نه «نامساعد»، و causeِ
  «هنوز معامله‌ای نشده» را از آخرین نشستِ گردش‌دار جدا می‌کند.
- summary ده سطرِ ثابت با همان گردکردن و همان buy_power_up.
EOF
```

---
---

### Task 7: تایم‌لاین و شمارندهٔ چرخشِ صف‌ها

**Files:**
- Create: `backend-go/internal/mstat/timeline.go`, `timeline_test.go`

**Interfaces:**
- Produces:
  `func decodeStates(blob string) map[string]string`
  `func points(db *sql.DB) ([]map[string]any, error)`
  `func timelinePanel(db *sql.DB, mode string) (map[string]any, error)`
  `func phasesPanel(db *sql.DB) (map[string]any, error)`

- [ ] **Step 1: Write the failing tests**

```go
package mstat

import "testing"

func TestTimelineGoldens(t *testing.T) {
	h := openFixture(t)
	for _, mode := range []string{"cum", "inst"} {
		got, err := timelinePanel(h.Market, mode)
		if err != nil {
			t.Fatal(err)
		}
		compareGolden(t, "timeline_"+mode, loadGolden(t, "s1", "timeline_"+mode), got)
	}
	got, err := timelinePanel(h.Market, "cum")
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "s2 timeline", loadGolden(t, "s2", "timeline_cum"), got)
}

func TestPhasesGoldens(t *testing.T) {
	h := openFixture(t)
	for _, s := range []string{"s1", "s2"} {
		got, err := phasesPanel(h.Market)
		if err != nil {
			t.Fatal(err)
		}
		compareGolden(t, s+" phases", loadGolden(t, s, "phases"), got)
	}
}
```

Run: `cd backend-go && go test ./internal/mstat/ -run 'Timeline|Phases'`
Expected: FAIL — undefined.

- [ ] **Step 2: Write `timeline.go`**

```go
package mstat

import (
	"bytes"
	"compress/zlib"
	"database/sql"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"

	"borsterminal/backend/internal/pyround"
)

var seriesKeys = []string{"val_bt", "flow_eq_bt", "flow_fixed_bt", "pos", "neg",
	"bq_bt", "sq_bt", "pc_buy", "pc_sell", "bq_n", "sq_n"}

// decodeStates همان _dec_states: base64 → zlib → JSON؛ هر خطا ⇒ {}.
func decodeStates(blob string) map[string]string {
	out := map[string]string{}
	if blob == "" {
		return out
	}
	raw, err := base64.StdEncoding.DecodeString(blob)
	if err != nil {
		return out
	}
	zr, err := zlib.NewReader(bytes.NewReader(raw))
	if err != nil {
		return out
	}
	body, err := io.ReadAll(zr)
	_ = zr.Close()
	if err != nil {
		return out
	}
	_ = json.Unmarshal(body, &out)
	return out
}

func toF(v any) float64 {
	switch n := v.(type) {
	case float64:
		return n
	case int64:
		return float64(n)
	case json.Number:
		f, _ := n.Float64()
		return f
	default:
		return 0
	}
}

func hhmm(v any) string {
	h := int(toF(v))
	return fmt.Sprintf("%02d:%02d", h/10000, (h/100)%100)
}

// points همان _points: فقط پنجرهٔ رسمی ۰۸:۵۵–۱۳:۰۰، حداکثر ۲۴۰ نقطه.
func points(db *sql.DB) ([]map[string]any, error) {
	var day sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even) FROM mstat_snap").Scan(&day); err != nil || !day.Valid {
		return nil, nil
	}
	rows, err := db.Query(`SELECT h_even, agg FROM mstat_snap WHERE d_even=?
	    AND h_even>=? AND h_even<=? ORDER BY h_even`, day.Int64, 85500, 130005)
	if err != nil {
		return nil, err
	}
	defer rows.Close()
	out := []map[string]any{}
	for rows.Next() {
		var h sql.NullInt64
		var agg sql.NullString
		if err := rows.Scan(&h, &agg); err != nil {
			return nil, err
		}
		var j map[string]any
		if json.Unmarshal([]byte(agg.String), &j) != nil {
			continue
		}
		if _, ok := j["h_even"]; !ok {
			j["h_even"] = h.Int64
		}
		out = append(out, j)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}
	if len(out) > 240 {
		out = out[len(out)-240:]
	}
	return out, nil
}

func timelinePanel(db *sql.DB, mode string) (map[string]any, error) {
	pts, err := points(db)
	if err != nil {
		return nil, err
	}
	cum := map[string][]any{}
	for _, k := range seriesKeys {
		vals := make([]any, len(pts))
		for i, p := range pts {
			vals[i] = p[k]
		}
		cum[k] = vals
	}
	t := make([]string, len(pts))
	for i, p := range pts {
		t[i] = hhmm(p["h_even"])
	}
	instant := func(key string) []any {
		out := make([]any, 0, len(cum[key]))
		var prev any
		for _, v := range cum[key] {
			if v == nil {
				out = append(out, nil)
				continue
			}
			if prev == nil {
				out = append(out, nil)
			} else {
				out = append(out, pyround.Round(toF(v)-toF(prev), 2))
			}
			prev = v
		}
		if len(out) > 0 && len(pts) > 0 {
			out[0] = cum[key][0]
		}
		return out
	}
	ser := map[string]any{}
	if mode == "inst" {
		for _, k := range seriesKeys {
			ser[k] = instant(k)
		}
	} else {
		for _, k := range seriesKeys {
			ser[k] = cum[k]
		}
	}
	ser["t"] = t

	var day any
	if len(pts) > 0 {
		day = pts[0]["d_even"]
	}
	var board any
	{
		var b sql.NullInt64
		if err := db.QueryRow("SELECT MAX(d_even) FROM market_watch").Scan(&b); err == nil && b.Valid {
			board = b.Int64
		}
	}
	stale := false
	if day != nil && board != nil {
		stale = fmt.Sprint(int(toF(day))) != fmt.Sprint(board)
	}
	var note any
	if len(pts) < 2 {
		note = "برای تایم‌لاین دست‌کم به دو همگام‌سازی در یک نشست نیاز است"
	} else if stale {
		note = "این تایم‌لاین به نشستی غیر از آخرین نشستِ تابلو برمی‌گردد — وضعیتِ امروز نیست"
	}
	m := "cum"
	if mode == "inst" {
		m = "inst"
	}
	return map[string]any{
		"status": "ok", "mode": m, "ready": len(pts) >= 2, "points": len(pts),
		"day": day, "board_day": board, "stale": stale, "series": ser,
		"session_open": "08:55", "session_close": "13:00", "note": note,
	}, nil
}

func phasesPanel(db *sql.DB) (map[string]any, error) {
	pts, err := points(db)
	if err != nil {
		return nil, err
	}
	type pair struct{ a, b string }
	counts := map[pair]int{}
	for _, tr := range transitions {
		counts[pair{tr.From, tr.To}] = 0
	}
	for i := 1; i < len(pts); i++ {
		prevBlob, _ := pts[i-1]["st"].(string)
		curBlob, _ := pts[i]["st"].(string)
		prev := decodeStates(prevBlob)
		cur := decodeStates(curBlob)
		if len(prev) == 0 || len(cur) == 0 {
			continue
		}
		for ic, now := range cur {
			was := prev[ic]
			if was != "" && was != now {
				if _, ok := counts[pair{was, now}]; ok {
					counts[pair{was, now}]++
				}
			}
		}
	}
	red, green := []map[string]any{}, []map[string]any{}
	for _, tr := range transitions {
		item := map[string]any{"key": tr.From + ">" + tr.To, "label": tr.Label,
			"count": counts[pair{tr.From, tr.To}]}
		if tr.Color == "red" {
			red = append(red, item)
		} else {
			green = append(green, item)
		}
	}
	return map[string]any{"status": "ok", "points": len(pts), "ready": len(pts) >= 2,
		"red": red, "green": green}, nil
}
```

- [ ] **Step 3: Run the tests**

Run: `cd backend-go && go test ./internal/mstat/ -run 'Timeline|Phases'`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend-go/internal/mstat/timeline.go backend-go/internal/mstat/timeline_test.go
git commit -F - <<'CLOSE'
feat(go): تایم‌لاین و شمارندهٔ چرخشِ صف‌ها

- نقطه‌ها فقط از پنجرهٔ رسمی ۰۸:۵۵–۱۳:۰۰ و blobِ فشردهٔ وضعیت‌ها خوانده
  می‌شوند؛ حالتِ کهنه جدا اعلام می‌شود.
- mode=inst تفاوتِ نقطه‌هایِ متوالی است و نقطهٔ نخست خودش «جمعِ تا آن لحظه»
  می‌ماند — همان دو خوانشِ یک داده.
- چرخش فقط برایِ جفت‌هایِ ثبت‌شده و نمادهایی که در نقطهٔ پیشین بوده‌اند.
CLOSE
```

---

### Task 8: تابلوی نمادها (`mainwatch`) با پرچم‌هایِ تابلو

**Files:**
- Create: `backend-go/internal/mstat/mainwatch.go`, `mainwatch_test.go`
- Modify: `backend-go/internal/market/service.go` (متدِ `TapeFlags`)

**Interfaces:**
- Consumes: `enrich`, `selectRows`, `tabCat`, `pxNear`, `pxInBand`, `pyround.Round`.
- Produces:
  `type FlagSource interface{ TapeFlags() (map[string]map[string]bool, bool) }`
  `func mainwatchPanel(db *sql.DB, flags FlagSource, group, industry, sortKey string, desc bool, limit int) (map[string]any, error)`
  `func (s *market.Service) TapeFlags() (map[string]map[string]bool, bool)`
  `func normSymbol(s string) string` (strip + ي/ى→ی + ك→ک؛ بدونِ حذفِ نیم‌فاصله)

- [ ] **Step 1: Add `TapeFlags` to the market service**

در `backend-go/internal/market/service.go`:

```go
// TapeFlags پرچم‌هایِ هفت‌گانهٔ ردیف‌هایِ تابلو، کلید = نمادِ نرمال‌شده. منبعش
// همان کشِ /api/market است (همان مسیری که پایتون در _board_snapshot می‌رود)،
// پس هیچ فرمولِ دومی ساخته نمی‌شود.
//
// از cached() می‌گذرد، نه build(): ساختِ بی‌قید در هر درخواستِ mainwatch،
// تابلوِ ۵٬۵هزارردیفی را از نو می‌ساخت و همان چیزی می‌شد که کشِ mstat برایِ
// حذفش هست. cached() داغ ⇒ بی‌محاسبه؛ سرد ⇒ یک ساخت؛ داده تازه ⇒ همان رفتارِ
// STALE و بازسازیِ پس‌زمینه.
func (s *Service) TapeFlags() (map[string]map[string]bool, bool) {
	if _, _, _, err := s.cached(); err != nil {
		return nil, false
	}
	s.mu.Lock()
	byCode := s.byCode
	s.mu.Unlock()
	if byCode == nil {
		return nil, false
	}
	out := make(map[string]map[string]bool, len(byCode))
	keys := []string{"f_clock", "f_susp", "f_jet", "f_roobi", "f_noqteh", "f_smart", "f_legal"}
	for _, rec := range byCode {
		sym, _ := rec["symbol"].(string)
		if sym == "" {
			continue
		}
		key := strings.TrimSpace(symNorm.Replace(sym))
		flags := make(map[string]bool, 7)
		for _, k := range keys {
			b, _ := rec[k].(bool)
			flags[k] = b
		}
		out[key] = flags
	}
	return out, true
}
```

و در بالایِ همان فایل:

```go
var symNorm = strings.NewReplacer("\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9")
```

**دقت:** `f_*` در `dropFields` نیست، پس در بدنهٔ پیش‌فرض می‌ماند؛ و `cached()` همان کشی است که `/api/market` می‌بیند، پس این مسیر هیچ محاسبهٔ تازه‌ای نمی‌سازد. صفرِ پرچم یعنی «پرچم نیست»، نه «منبع نرسید» — آن حالت را `ok=false` می‌گوید.

- [ ] **Step 2: Write the failing test**

```go
package mstat

import (
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/market"
)

type stubFlags struct {
	m  map[string]map[string]bool
	ok bool
}

func (s stubFlags) TapeFlags() (map[string]map[string]bool, bool) { return s.m, s.ok }

func TestMainwatchGoldens(t *testing.T) {
	h := openFixture(t)
	// پرچم‌ها در طلایی از /api/marketِ پایتون رویِ همین فیکسچر می‌آیند؛ برایِ
	// تستِ Go همان نقشه را تزریق می‌کنیم (محاسبهٔ پرچم‌ها گیتِ B1 را دارد).
	base, ok := marketFlags(h)
	if !ok {
		t.Fatal("market service did not produce tape flags")
	}
	got, err := mainwatchPanel(h.Market, stubFlags{base, true}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "mainwatch", loadGolden(t, "s1", "mainwatch_default"), got)
	got2, err := mainwatchPanel(h.Market, stubFlags{base, true}, "eq_all", "", "val", false, 5)
	if err != nil {
		t.Fatal(err)
	}
	compareGolden(t, "mainwatch-val", loadGolden(t, "s1", "mainwatch_val"), got2)
	got3, err := mainwatchPanel(h.Market, stubFlags{nil, false}, "eq_all", "", "clock", true, 120)
	if err != nil {
		t.Fatal(err)
	}
	if got3["tape_flags_source"] != "unavailable" {
		t.Fatalf("unavailable source = %v", got3["tape_flags_source"])
	}
}
```

`marketFlags` در همان فایلِ تست:

```go
func marketFlags(h *db.Handles) (map[string]map[string]bool, bool) {
	svc := market.New(h, "")
	return svc.TapeFlags()
}
```

**نکته:** `market.New` رویِ همان فیکسچر `/api/market` را می‌سازد و `user.db`ِ کپی را می‌نویسد (همان side effectِ ثبتِ روزانه) — در محیطِ تست فیکسچر است، نه بانکِ عملیاتی. اگر این تست را رویِ فیکسچرِ مشترک اجرا می‌کنید، `user.db` را کپیِ موقت بدهید؛ الگویِ `fixtureCopy` در `internal/market/service_test.go` موجود است.

Run: `cd backend-go && go test ./internal/mstat/ -run Mainwatch`
Expected: FAIL — undefined.

- [ ] **Step 3: Write `mainwatch.go`**

```go
package mstat

import (
	"database/sql"
	"sort"
	"strings"

	"borsterminal/backend/internal/pyround"
)

type FlagSource interface {
	TapeFlags() (map[string]map[string]bool, bool)
}

var symNorm = strings.NewReplacer("\u064A", "\u06CC", "\u0649", "\u06CC", "\u0643", "\u06A9")

func normSymbol(s string) string { return strings.TrimSpace(symNorm.Replace(s)) }

var gridSortKeys = map[string]string{
	"vol": "vol_b_shares", "val": "val_b_toman", "pc": "p_closing",
	"pl": "p_last", "pct": "pct_close", "pct_last": "pct_last",
	"clock": "clock_pct", "pcb": "pc_buy", "pcs": "pc_sell",
	"pow": "power", "flow": "flow_b_toman", "dv": "dem_vol",
	"dp": "dem_px", "symbol": "symbol",
}

type gridRow struct {
	symbol, insCode, name, industry, cls, kind, queue string
	volB, valB, trades, flowB                         float64
	pLast, pClosing, pFirst, pMax, pMin               float64
	pctLast, pctClose, clockPct                       float64
	pcBuy, pcSell, power, demVol, demPx               float64
	hasPLast, hasPctLast, hasPctClose, hasClock       bool
	hasPCBuy, hasPCSell, hasPower, hasDemVol, hasDemPx bool
	depth, clockOK                                    bool
}

func (g *gridRow) get(col string) (float64, bool) {
	switch col {
	case "vol_b_shares":
		return g.volB, true
	case "val_b_toman":
		return g.valB, true
	case "p_closing":
		return g.pClosing, true
	case "p_last":
		return g.pLast, g.hasPLast
	case "pct_close":
		return g.pctClose, g.hasPctClose
	case "pct_last":
		return g.pctLast, g.hasPctLast
	case "clock_pct":
		return g.clockPct, g.hasClock
	case "pc_buy":
		return g.pcBuy, g.hasPCBuy
	case "pc_sell":
		return g.pcSell, g.hasPCSell
	case "power":
		return g.power, g.hasPower
	case "flow_b_toman":
		return g.flowB, true
	case "dem_vol":
		return g.demVol, g.hasDemVol
	case "dem_px":
		return g.demPx, g.hasDemPx
	}
	return 0, false
}

func (g *gridRow) toMap() map[string]any {
	m := map[string]any{
		"symbol": g.symbol, "ins_code": g.insCode, "name": g.name,
		"industry": g.industry, "cls": g.cls, "kind": g.kind,
		"vol_b_shares": pyround.Round(g.volB, 6), "trades": g.trades,
		"val_b_toman": pyround.Round(g.valB, 1),
		"p_last": nil, "p_closing": g.pClosing,
		"p_first": g.pFirst, "p_max": g.pMax, "p_min": g.pMin,
		"pct_last": nil, "pct_close": nil, "clock_pct": nil,
		"pc_buy": nil, "pc_sell": nil, "power": nil,
		"flow_b_toman": g.flowB, "dem_vol": nil, "dem_px": nil,
		"queue": g.queue, "depth": g.depth, "clock_ok": g.clockOK,
	}
	if g.hasPLast {
		m["p_last"] = g.pLast
	}
	if g.hasPctLast {
		m["pct_last"] = pyround.Round(g.pctLast, 2)
	}
	if g.hasPctClose {
		m["pct_close"] = pyround.Round(g.pctClose, 2)
	}
	if g.hasClock {
		m["clock_pct"] = pyround.Round(g.clockPct, 2)
	}
	if g.hasPCBuy {
		m["pc_buy"] = pyround.Round(g.pcBuy, 2)
	}
	if g.hasPCSell {
		m["pc_sell"] = pyround.Round(g.pcSell, 2)
	}
	if g.hasPower {
		m["power"] = pyround.Round(g.power, 2)
	}
	if g.hasDemVol {
		m["dem_vol"] = g.demVol
	}
	if g.hasDemPx {
		m["dem_px"] = g.demPx
	}
	return m
}

func mainwatchPanel(db *sql.DB, flags FlagSource, group, industry, sortKey string,
	desc bool, limit int) (map[string]any, error) {
	snap, err := loadSnapshot(db)
	if err != nil {
		return nil, err
	}
	rows := enrich(snap)
	cat := group
	if v, ok := tabCat[group]; ok {
		cat = v
	}
	grid := []*gridRow{}
	for _, r := range selectRows(rows, cat) {
		ind := strings.TrimSpace(r.SectorName)
		if industry != "" && ind != industry {
			continue
		}
		m := r.M
		okLast := !isNaN(r.PLast) && pxInBand(r, r.PLast, r.PClosing)
		g := &gridRow{
			symbol: r.Symbol, insCode: r.Code, name: r.Name, industry: ind,
			cls: r.Cls, kind: r.Kind,
			volB: m.Vol / 1e9, trades: m.Trades, valB: m.Val / 1e10,
			pClosing: zeroIfNaN(r.PClosing), pFirst: zeroIfNaN(r.PFirst),
			pMax: zeroIfNaN(r.PMax), pMin: zeroIfNaN(r.PMin),
			flowB: m.Flow / 1e10, queue: m.QState, depth: !isNaN(m.BQVal),
		}
		if okLast {
			g.pLast, g.hasPLast = r.PLast, true
		}
		if !isNaN(r.PYest) && r.PYest != 0 && okLast && pxNear(r.PYest, r.PClosing) {
			if d := div(r.PLast-r.PYest, r.PYest); d != nil {
				g.pctLast, g.hasPctLast = 100.0**d, true
			}
		}
		if r.Pct != nil {
			g.pctClose, g.hasPctClose = *r.Pct, true
		}
		if r.ClockPct != nil {
			g.clockPct, g.hasClock = *r.ClockPct, true
		}
		if !isNaN(m.PCBuy) {
			g.pcBuy, g.hasPCBuy = m.PCBuy/1e7, true
		}
		if !isNaN(m.PCSell) {
			g.pcSell, g.hasPCSell = m.PCSell/1e7, true
		}
		if !isNaN(m.Power) {
			g.power, g.hasPower = m.Power, true
		}
		if !isNaN(m.BQ1Vol) {
			g.demVol, g.hasDemVol = m.BQ1Vol, true
		}
		if !isNaN(m.BQ1Px) {
			g.demPx, g.hasDemPx = m.BQ1Px, true
		}
		g.clockOK = r.ClockPct != nil && *r.ClockPct >= 1.0 && m.Trades >= 30 &&
			zeroIfNaN(r.PClosing) >= 500.0
		grid = append(grid, g)
	}
	// مرتب‌سازی: clock فقط نامزدهایِ قابلِ‌اتکا را رتبه می‌دهد؛ symbol رشته‌ای
	// است و بقیه ستونِ عددی.
	if sortKey == "symbol" {
		// reverse=True در پایتون ترتیبِ هم‌ارزها را برنمی‌گرداند؛ پس دو جهت را
		// جدا نوشتیم، نه sort و بعد reverse (که هم‌ارزها را هم می‌چرخاند).
		sort.SliceStable(grid, func(i, j int) bool {
			if desc {
				return grid[i].symbol > grid[j].symbol
			}
			return grid[i].symbol < grid[j].symbol
		})
	} else {
		col := gridSortKeys[sortKey]
		if col == "" {
			col = "clock_pct"
		}
		key := func(g *gridRow) float64 {
			if sortKey == "clock" && !g.clockOK {
				if desc {
					return -1e18
				}
				return 1e18
			}
			v, ok := g.get(col)
			if !ok {
				if desc {
					return -1e18
				}
				return 1e18
			}
			return v
		}
		sort.SliceStable(grid, func(i, j int) bool {
			if desc {
				return key(grid[i]) > key(grid[j])
			}
			return key(grid[i]) < key(grid[j])
		})
	}
	// عینِ max(1, min(int(limit or 120), 4000)): صفر در پایتون «بی‌مقدار» است و
	// ۱۲۰ می‌شود، نه ۱؛ منفی به ۱ بسته می‌شود.
	if limit == 0 {
		limit = 120
	}
	if limit < 1 {
		limit = 1
	}
	if limit > 4000 {
		limit = 4000
	}
	if limit > len(grid) {
		limit = len(grid)
	}
	outRows := make([]map[string]any, 0, limit)
	for _, g := range grid[:limit] {
		outRows = append(outRows, g.toMap())
	}
	clockHits := 0
	for _, g := range grid {
		if g.clockOK {
			clockHits++
		}
	}
	out := map[string]any{
		"status": "ok", "asof": asOfMap(snap, len(top50Codes(snap.Rows)), len(rows)),
		"group": group, "industry": industry, "sort": sortKey,
		"sort_col": func() string {
			if c, ok := gridSortKeys[sortKey]; ok {
				return c
			}
			return "clock_pct"
		}(),
		"desc": desc, "total": len(grid), "clock_hits": clockHits,
		"clock_rule": map[string]any{"min_pct": 1.0, "min_trades": 30, "min_price": 500.0},
		"rows":       outRows,
	}
	if flags != nil {
		if m, ok := flags.TapeFlags(); ok {
			for _, row := range outRows {
				sym, _ := row["symbol"].(string)
				row["tape_flags"] = m[normSymbol(sym)]
			}
			out["tape_flags_source"] = "api/market"
		} else {
			out["tape_flags_source"] = "unavailable"
		}
	}
	return out, nil
}
```

**دقت‌ها:**
- `limit` در پایتون با `max(1, min(int(limit or 120), 4000))` بسته می‌شود؛ `limit=0` هم ۱ می‌شود — در Go همان بالا.
- `clock_hits` رویِ **همهٔ** `sel` شمرده می‌شود، نه فقط `rows[:limit]`.
- `symbol` خالی ⇒ `""` در مرتب‌سازی؛ `None` وجود ندارد چون symbol همیشه رشته است.
- وقتی `flags==nil` (مثلاً در تستِ واحدِ دیگر)، هیچ کلیدِ `tape_flags_source` اضافه نمی‌شود — پایتون هم در مسیرِ `_mstat.mainwatch` مستقیم این کلید را ندارد. مسیرِ روتر همیشه flags را می‌دهد.

- [ ] **Step 4: Run the tests**

Run: `cd backend-go && go test ./internal/mstat/ -run Mainwatch`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend-go/internal/mstat/mainwatch.go backend-go/internal/mstat/mainwatch_test.go \
        backend-go/internal/market/service.go
git commit -F - <<'CLOSE'
feat(go): تابلویِ نمادها با پرچم‌هایِ هفت‌گانهٔ تابلو

- mainwatch همان مرتب‌سازیِ ستون‌ها (شاملِ clock با ترمزهایِ معامله/قیمت) و
  همان limit و clock_rule را دارد؛ ردیف‌هایِ بی‌داده به انتهایِ فهرست می‌روند.
- پرچم‌ها از همان بدنهٔ /api/market منتقل می‌شوند (هیچ فرمولِ دومی ساخته
  نمی‌شود) و با نمادِ نرمال‌شده جفت می‌شوند؛ نبودِ منبع «unavailable» است،
  نه «پرچمی ندارد».
CLOSE
```

---

### Task 9: سرویسِ کشِ mstat، یازده هندلر و سیم‌کشیِ مسیرها

**Files:**
- Create: `backend-go/internal/datatoken/token.go`, `token_test.go`
- Modify: `backend-go/internal/market/service.go` (واگذاریِ `dataToken` به بستهٔ مشترک)
- Create: `backend-go/internal/mstat/service.go` (کش)، `handlers.go` (یازده مسیر)
- Create: `backend-go/internal/mstat/service_test.go`, `handlers_test.go`
- Modify: `backend-go/internal/httpapi/errors.go` (`UnprocessableAs`)، `server.go` (اینترفیسِ `Mstat` و ثبتِ مسیرها)، `server_test.go`
- Modify: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- Consumes: پنل‌هایِ Task 3–8، `marketphase.FromDB`، و `market.Service` به‌عنوانِ `FlagSource`.
- Produces:
  `func datatoken.FileToken(dataDir string) string`
  `func New(db *sql.DB, dataDir string, flags FlagSource) *Service`
  `type Options struct { TTL time.Duration; Inline, StaleOK bool }` (TTL صفر = پیش‌فرضِ ۴۵ثانیه؛ منفی = بی‌کش)
  `func (s *Service) Call(key string, fn func() (map[string]any, error), opt Options) map[string]any`
  `func (s *Service) Summary|Histogram|Thermometer|Depth|ClientSplit|MarketSnapshot|Phase|Mainwatch|Industries|Timeline|Phases(http.ResponseWriter, *http.Request)`
  `func httpapi.UnprocessableAs(w http.ResponseWriter, typ string, loc []string, msg string, input any)`
  `func httpapi.New(cfg config.Config, h *db.Handles, m Market, ms Mstat) http.Handler`

- [ ] **Step 1: Move the data token into a shared package**

`backend-go/internal/datatoken/token.go`:

```go
// Package datatoken نشانکِ «داده عوض شد» برایِ کش‌هایِ درون‌حافظه.
//
// هر سینکِ موفق market_sync.json را بازنویسی می‌کند، و tick_live هر ۵ ثانیه
// ردیف‌ها را در market.db (با WAL) کامیت می‌کند بی‌آنکه آن فایل را دست بزند؛
// پس فقط (mtime_ns, size)ِ market_sync.json کافی نیست و هر سه فایل باید در
// توکن باشند — همان نقشی که revision() و sync_count در پروسۀ پایتون داشتند.
// غایب ⇒ "-"، تا توکن پایدار بماند. فقط os.Stat: نه بازکردنِ SQLite، نه
// خواندنِ محتوا.
package datatoken

import (
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func FileToken(dataDir string) string {
	var b strings.Builder
	for _, name := range []string{"market_sync.json", "market.db", "market.db-wal"} {
		if b.Len() > 0 {
			b.WriteByte('|')
		}
		st, err := os.Stat(filepath.Join(dataDir, name))
		if err != nil {
			b.WriteByte('-')
			continue
		}
		b.WriteString(strconv.FormatInt(st.ModTime().UnixNano(), 10))
		b.WriteByte(':')
		b.WriteString(strconv.FormatInt(st.Size(), 10))
	}
	return b.String()
}
```

`token_test.go`:

```go
package datatoken

import (
	"os"
	"path/filepath"
	"testing"
)

// TestFileTokenTracksFiles سنسور را می‌سنجد، نه نتیجه را: توکنِ دایرکتوریِ تهی
// باید پایدار بماند و با نوشتنِ یکی از سه فایل عوض شود؛ وگرنه کشِ mstat
// («داده تازه است») هرگز کلید عوض نمی‌کند یا همیشه عوض می‌کند.
func TestFileTokenTracksFiles(t *testing.T) {
	dir := t.TempDir()
	empty := FileToken(dir)
	if empty != FileToken(dir) {
		t.Fatal("token of an empty dir is not stable")
	}
	if empty != "-|-|-" {
		t.Fatalf("empty dir token = %q", empty)
	}
	if err := os.WriteFile(filepath.Join(dir, "market_sync.json"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	one := FileToken(dir)
	if one == empty {
		t.Fatal("writing market_sync.json did not change the token")
	}
	if got := FileToken(dir); got != one {
		t.Fatal("token changed without a file change")
	}
}
```

در `backend-go/internal/market/service.go` بدنهٔ `dataToken` را به واگذاری تبدیل کنید (نام و امضا برایِ تست‌هایِ B1 دست‌نخورده):

```go
func dataToken(dataDir string) string { return datatoken.FileToken(dataDir) }
```

و `"borsterminal/backend/internal/datatoken"` را به importها اضافه کنید.

- [ ] **Step 2: Write the failing cache test**

`backend-go/internal/mstat/service_test.go`:

```go
package mstat

import (
	"database/sql"
	"errors"
	"os"
	"path/filepath"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

type fakeClock struct {
	mu sync.Mutex
	t  time.Time
}

func (c *fakeClock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.t
}

func (c *fakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	c.t = c.t.Add(d)
	c.mu.Unlock()
}

// newTestService یک بانکِ درون‌حافظه‌ای با جدولِ mstat_snap می‌سازد؛ بی‌آن،
// نشانهٔ کش وجود ندارد و پایتون هم (و حالا Go هم) کش را کامل دور می‌زند.
func newTestService(t *testing.T) (*Service, *fakeClock, string) {
	t.Helper()
	raw, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	raw.SetMaxOpenConns(1)
	t.Cleanup(func() { _ = raw.Close() })
	if _, err := raw.Exec("CREATE TABLE mstat_snap (d_even INTEGER, h_even INTEGER)"); err != nil {
		t.Fatal(err)
	}
	dir := t.TempDir()
	s := New(raw, dir, nil)
	clk := &fakeClock{t: time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)}
	s.clock = clk.Now
	return s, clk, dir
}

func waitCount(t *testing.T, n *int32, want int32) {
	t.Helper()
	deadline := time.Now().Add(2 * time.Second)
	for atomic.LoadInt32(n) < want && time.Now().Before(deadline) {
		time.Sleep(2 * time.Millisecond)
	}
	if got := atomic.LoadInt32(n); got != want {
		t.Fatalf("computes = %d, want %d", got, want)
	}
}

func TestCallCachesWithinTTL(t *testing.T) {
	s, clk, _ := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	s.Call("p", fn, Options{})
	if n != 1 {
		t.Fatalf("computes = %d, want 1", n)
	}
	clk.Advance(DefaultTTL + time.Second)
	stale := s.Call("p", fn, Options{StaleOK: true})
	if stale["status"] != "ok" {
		t.Fatalf("stale body = %v", stale)
	}
	waitCount(t, &n, 2)
	s.Call("p", fn, Options{StaleOK: true})
	if n != 2 {
		t.Fatalf("computes after rebuild = %d, want 2", n)
	}
}

func TestCallNoStaleWhenDisallowed(t *testing.T) {
	s, clk, _ := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	clk.Advance(DefaultTTL + time.Second)
	s.Call("p", fn, Options{}) // StaleOK=false ⇒ محاسبهٔ درون‌خطی
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}

func TestCallDoesNotCacheErrors(t *testing.T) {
	s, _, _ := newTestService(t)
	var n int32
	failing := true
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		if failing {
			return nil, errors.New("boom")
		}
		return map[string]any{"status": "ok"}, nil
	}
	out := s.Call("p", fn, Options{})
	if out["status"] != "error" || out["message"] != "boom" {
		t.Fatalf("error body = %v", out)
	}
	if out["source"] != "local:market.db" {
		t.Fatalf("source = %v", out["source"])
	}
	failing = false
	out2 := s.Call("p", fn, Options{})
	if out2["status"] != "ok" || n != 2 {
		t.Fatalf("after recovery: status=%v computes=%d", out2["status"], n)
	}
}

func TestCallSingleFlight(t *testing.T) {
	s, _, _ := newTestService(t)
	release := make(chan struct{})
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		<-release
		return map[string]any{"status": "ok"}, nil
	}
	var wg sync.WaitGroup
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() { defer wg.Done(); s.Call("p", fn, Options{}) }()
	}
	waitCount(t, &n, 1)
	close(release)
	wg.Wait()
	if n != 1 {
		t.Fatalf("computes = %d, want 1", n)
	}
}

func TestCallStateChangeInvalidates(t *testing.T) {
	s, _, dir := newTestService(t)
	var n int32
	fn := func() (map[string]any, error) {
		atomic.AddInt32(&n, 1)
		return map[string]any{"status": "ok"}, nil
	}
	s.Call("p", fn, Options{})
	if err := os.WriteFile(filepath.Join(dir, "market_sync.json"), []byte("{}"), 0o644); err != nil {
		t.Fatal(err)
	}
	s.Call("p", fn, Options{})
	if n != 2 {
		t.Fatalf("computes = %d, want 2", n)
	}
}
```

Run: `cd backend-go && go test ./internal/mstat/ -run Call`
Expected: FAIL — `Service`/`Options` undefined.

- [ ] **Step 3: Write `service.go`**

```go
package mstat

import (
	"database/sql"
	"fmt"
	"sync"
	"time"

	"borsterminal/backend/internal/datatoken"
)

const (
	// عینِ _MSTAT_TTL_S و _MSTAT_STALE_MAX_S در api/market_status.py.
	DefaultTTL = 45 * time.Second
	StaleMax   = 90 * time.Second
)

type entry struct {
	at   time.Time
	body map[string]any
}

// Options رفتارِ کشِ یکِ پنل را می‌گوید.
type Options struct {
	// TTL صفر یعنی پیش‌فرضِ ۴۵ثانیه‌ای؛ منفی یعنی بی‌کش (ttl_s=0ِ پایتون).
	TTL time.Duration
	// Inline معادلِ refresh="inline": بی‌کش و همیشه‌تازه.
	Inline bool
	// StaleOK=false برایِ پنل‌هایی است که عددشان از ساعتِ دیوار ساخته می‌شود
	// (phase): کهنه سرو نمی‌شود.
	StaleOK bool
}

// Service همان لایهٔ _mstat_call: کشِ هر-حالت، stale-while-revalidate،
// تک‌پروازگی برایِ cold miss، و خطا که هرگز کش نمی‌شود.
type Service struct {
	db      *sql.DB
	dataDir string
	flags   FlagSource

	mu      sync.Mutex
	cache   map[string]entry
	flights map[string]chan struct{}
	clock   func() time.Time
}

func New(db *sql.DB, dataDir string, flags FlagSource) *Service {
	return &Service{db: db, dataDir: dataDir, flags: flags,
		cache: map[string]entry{}, flights: map[string]chan struct{}{}, clock: time.Now}
}

func (s *Service) Call(key string, fn func() (map[string]any, error), opt Options) map[string]any {
	ttl := opt.TTL
	if ttl == 0 {
		ttl = DefaultTTL
	}
	if ttl < 0 || opt.Inline {
		return cloneMap(s.compute(fn))
	}
	state, ok := s.state()
	if !ok {
		// پایتون هم وقتی نشانه‌ای ندارد (جدولِ mstat_snap نیست) کش را کامل دور
		// می‌زند؛ بی‌این، Go رویِ بانکِ بی‌mstat_snap چیزی را کش می‌کرد که
		// پایتون نمی‌کرد.
		return cloneMap(s.compute(fn))
	}
	full := key + "\x00" + state
	now := s.clock()

	s.mu.Lock()
	hit, ok := s.cache[full]
	if ok && now.Sub(hit.at) < ttl {
		out := cloneMap(hit.body)
		s.mu.Unlock()
		return out
	}
	if ok && opt.StaleOK && now.Sub(hit.at) <= StaleMax {
		if _, busy := s.flights[full]; !busy {
			done := make(chan struct{})
			s.flights[full] = done
			s.mu.Unlock()
			go func() {
				s.store(full, s.compute(fn), s.clock())
				s.finish(full, done)
			}()
		} else {
			s.mu.Unlock()
		}
		return cloneMap(hit.body)
	}
	if done, busy := s.flights[full]; busy {
		// یکی دیگر دارندۀ همین cold miss است؛ منتظرِ همان یک نتیجه می‌مانیم،
		// بی‌این‌که دوباره بسازیم. بی‌پاسخ بماند، همان مسیرِ بی‌کش را می‌رویم.
		s.mu.Unlock()
		select {
		case <-done:
		case <-time.After(5*time.Second + ttl + StaleMax):
		}
		s.mu.Lock()
		hit2, ok2 := s.cache[full]
		s.mu.Unlock()
		if ok2 {
			return cloneMap(hit2.body)
		}
		return cloneMap(s.compute(fn))
	}
	done := make(chan struct{})
	s.flights[full] = done
	s.mu.Unlock()
	out := s.compute(fn)
	s.store(full, out, now)
	s.finish(full, done)
	return cloneMap(out)
}

func (s *Service) compute(fn func() (map[string]any, error)) map[string]any {
	out, err := fn()
	if err != nil {
		// یک پنلِ خراب نباید کل تب را ۵۰۰ کند؛ پایتون هم status=error می‌دهد.
		return map[string]any{"status": "error", "message": err.Error(),
			"source": "local:market.db"}
	}
	if out == nil {
		out = map[string]any{}
	}
	if _, ok := out["source"]; !ok {
		out["source"] = "local:market.db"
	}
	return out
}

func (s *Service) store(full string, body map[string]any, at time.Time) {
	if body == nil || body["status"] == "error" {
		return
	}
	s.mu.Lock()
	if len(s.cache) > 240 {
		s.cache = map[string]entry{}
	}
	s.cache[full] = entry{at: at, body: body}
	s.mu.Unlock()
}

func (s *Service) finish(full string, done chan struct{}) {
	s.mu.Lock()
	delete(s.flights, full)
	s.mu.Unlock()
	close(done)
}

// state همان نقشِ (revision، static_rev، session_day، marker)ِ پایتون را دارد:
// در فازِ الف شمارندهٔ درون‌پروسه‌ای نیست، پس نشانکِ فایل‌هایِ داده به‌جایِ آن
// می‌نشیند (همان قاعدهٔ کشِ تابلو در B1) و نشانِ mstat_snap جدا افزوده می‌شود.
func (s *Service) state() (string, bool) {
	d, h, ok := mstatMarker(s.db)
	if !ok {
		return "", false
	}
	return datatoken.FileToken(s.dataDir) + "|" + fmt.Sprintf("%d:%d", d, h), true
}

// mstatMarker همان _mstat_marker: آخرین (روز، ساعت)ِ ثبت‌شده در mstat_snap.
// نبودِ جدول یا نبودِ بانک ⇒ ok=false (کش بی‌استفاده می‌شود).
func mstatMarker(db *sql.DB) (int64, int64, bool) {
	if db == nil {
		return 0, 0, false
	}
	var d, h sql.NullInt64
	if err := db.QueryRow("SELECT MAX(d_even), MAX(h_even) FROM mstat_snap").Scan(&d, &h); err != nil {
		return 0, 0, false
	}
	return d.Int64, h.Int64, true
}

func cloneMap(m map[string]any) map[string]any {
	out := make(map[string]any, len(m))
	for k, v := range m {
		out[k] = v
	}
	return out
}
```

- [ ] **Step 4: Write `handlers.go`**

```go
package mstat

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"net/http"
	"strconv"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/marketphase"
)

// qstr همان Query(...)ِ FastAPI: نبودِ پارامتر ⇒ default، ولی ?group= تهی
// می‌ماند (FastAPI مقدارِ تهی را با نبودن یکی نمی‌کند؛ ?group= دستهٔ ناشناخته
// است و صفر ردیف می‌دهد).
func qstr(r *http.Request, name, def string) string {
	if !r.URL.Query().Has(name) {
		return def
	}
	return r.URL.Query().Get(name)
}

// fastBool همان مجموعهٔ رشته‌ایِ Pydantic است، نه strconv.ParseBool.
func fastBool(v string) (bool, bool) {
	switch strings.ToLower(strings.TrimSpace(v)) {
	case "1", "t", "true", "y", "yes", "on":
		return true, true
	case "0", "f", "false", "n", "no", "off":
		return false, true
	}
	return false, false
}

func writePanel(w http.ResponseWriter, body map[string]any) {
	httpapi.WriteJSON(w, http.StatusOK, body)
}

func (s *Service) Summary(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("summary", func() (map[string]any, error) {
		return summaryPanel(s.db, s.clock())
	}, Options{StaleOK: true}))
}

func (s *Service) Histogram(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("histogram|"+group, func() (map[string]any, error) {
		return histogramPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) Thermometer(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("thermometer|"+group, func() (map[string]any, error) {
		return thermometerPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) Depth(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "all")
	writePanel(w, s.Call("depth|"+group, func() (map[string]any, error) {
		return depthPanel(s.db, group)
	}, Options{StaleOK: true}))
}

func (s *Service) ClientSplit(w http.ResponseWriter, r *http.Request) {
	tab := qstr(r, "tab", "all")
	writePanel(w, s.Call("clientsplit|"+tab, func() (map[string]any, error) {
		return clientSplitPanel(s.db, tab)
	}, Options{StaleOK: true}))
}

func (s *Service) MarketSnapshot(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("market-snapshot", func() (map[string]any, error) {
		return marketSnapshotPanel(s.db, s.clock())
	}, Options{StaleOK: true}))
}

func (s *Service) Phase(w http.ResponseWriter, r *http.Request) {
	// stale_ok=False: تنها فیلدی که میانِ دو ساختِ یکسانِ حالتِ بانک فرق می‌کند
	// clock_now است، پس پنلِ ارزان درِ انقضا درون‌خطی ساخته می‌شود.
	writePanel(w, s.Call("phase", func() (map[string]any, error) {
		return phasePanel(s.db, s.clock())
	}, Options{StaleOK: false}))
}

func (s *Service) Mainwatch(w http.ResponseWriter, r *http.Request) {
	group := qstr(r, "group", "eq_all")
	industry := qstr(r, "industry", "")
	sortKey := qstr(r, "sort", "clock")
	desc := true
	if r.URL.Query().Has("desc") {
		raw := r.URL.Query().Get("desc")
		v, ok := fastBool(raw)
		if !ok {
			httpapi.UnprocessableAs(w, "bool_parsing", []string{"query", "desc"},
				"Input should be a valid boolean, unable to interpret input", raw)
			return
		}
		desc = v
	}
	limit := 120
	if r.URL.Query().Has("limit") {
		raw := r.URL.Query().Get("limit")
		v, err := strconv.Atoi(raw)
		if err != nil {
			httpapi.UnprocessableAs(w, "int_parsing", []string{"query", "limit"},
				"Input should be a valid integer, unable to parse string as an integer", raw)
			return
		}
		limit = v
	}
	key := fmt.Sprintf("mainwatch|%s|%s|%s|%t|%d", group, industry, sortKey, desc, limit)
	writePanel(w, s.Call(key, func() (map[string]any, error) {
		return mainwatchPanel(s.db, s.flags, group, industry, sortKey, desc, limit)
	}, Options{StaleOK: true}))
}

func (s *Service) Industries(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("industries", func() (map[string]any, error) {
		return industriesPanel(s.db)
	}, Options{StaleOK: true}))
}

func (s *Service) Timeline(w http.ResponseWriter, r *http.Request) {
	mode := qstr(r, "mode", "cum")
	writePanel(w, s.Call("timeline|"+mode, func() (map[string]any, error) {
		return timelinePanel(s.db, mode)
	}, Options{StaleOK: true}))
}

func (s *Service) Phases(w http.ResponseWriter, r *http.Request) {
	writePanel(w, s.Call("phases", func() (map[string]any, error) {
		return phasesPanel(s.db)
	}, Options{StaleOK: true}))
}

// phasePanel همان dict(MP.from_db(conn), status="ok").
func phasePanel(db *sql.DB, now time.Time) (map[string]any, error) {
	ph := marketphase.FromDB(db, now)
	raw, err := json.Marshal(ph)
	if err != nil {
		return nil, err
	}
	var out map[string]any
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	out["status"] = "ok"
	return out, nil
}
```

- [ ] **Step 5: Extend the HTTP layer**

`backend-go/internal/httpapi/errors.go` — `UnprocessableAs` را اضافه و `Unprocessable` را رویِ آن بنشانید:

```go
// UnprocessableAs همان 422ِ FastAPI با نوعِ خطایِ خودش (int_parsing،
// bool_parsing، …)؛ بدنهٔ مقایسه‌شده در پاریتی همین است.
func UnprocessableAs(w http.ResponseWriter, typ string, loc []string, msg string, input any) {
	WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []any{map[string]any{
			"type": typ, "loc": loc, "msg": msg, "input": input,
		}},
	})
}

func Unprocessable(w http.ResponseWriter, loc []string, msg string, input any) {
	UnprocessableAs(w, "value_error", loc, msg, input)
}
```

`backend-go/internal/httpapi/server.go`:

```go
// Mstat یازده مسیرِ GETِ تبِ وضعیت بازار؛ nil یعنی هیچ‌کدام پورت نشده.
type Mstat interface {
	Summary(http.ResponseWriter, *http.Request)
	Histogram(http.ResponseWriter, *http.Request)
	Thermometer(http.ResponseWriter, *http.Request)
	Depth(http.ResponseWriter, *http.Request)
	ClientSplit(http.ResponseWriter, *http.Request)
	MarketSnapshot(http.ResponseWriter, *http.Request)
	Phase(http.ResponseWriter, *http.Request)
	Mainwatch(http.ResponseWriter, *http.Request)
	Industries(http.ResponseWriter, *http.Request)
	Timeline(http.ResponseWriter, *http.Request)
	Phases(http.ResponseWriter, *http.Request)
}

func New(cfg config.Config, h *db.Handles, m Market, ms Mstat) http.Handler {
	...
	if ms != nil {
		mux.HandleFunc("GET /api/mstat/summary", ms.Summary)
		mux.HandleFunc("GET /api/mstat/histogram", ms.Histogram)
		mux.HandleFunc("GET /api/mstat/thermometer", ms.Thermometer)
		mux.HandleFunc("GET /api/mstat/depth", ms.Depth)
		mux.HandleFunc("GET /api/mstat/clientsplit", ms.ClientSplit)
		mux.HandleFunc("GET /api/mstat/market-snapshot", ms.MarketSnapshot)
		mux.HandleFunc("GET /api/mstat/phase", ms.Phase)
		mux.HandleFunc("GET /api/mstat/mainwatch", ms.Mainwatch)
		mux.HandleFunc("GET /api/mstat/industries", ms.Industries)
		mux.HandleFunc("GET /api/mstat/timeline", ms.Timeline)
		mux.HandleFunc("GET /api/mstat/phases", ms.Phases)
	}
	mux.HandleFunc("/", s.apiGate)
	return noCache(mux)
}
```

در `server_test.go`: `newServer` را به `New(cfg, nil, nil, nil)` برسانید و این را بیفزایید:

```go
// TestMstatRoutesAreNotPortedWhenServiceMissing همان قفلِ B1 است برایِ تبِ
// وضعیت بازار: بی سرویس، یازده مسیر ۵۰۱ِ NOT_PORTED می‌دهند، نه ۴۰۴.
func TestMstatRoutesAreNotPortedWhenServiceMissing(t *testing.T) {
	paths := []string{
		"/api/mstat/summary", "/api/mstat/histogram", "/api/mstat/thermometer",
		"/api/mstat/depth", "/api/mstat/clientsplit", "/api/mstat/market-snapshot",
		"/api/mstat/phase", "/api/mstat/mainwatch", "/api/mstat/industries",
		"/api/mstat/timeline", "/api/mstat/phases",
	}
	for _, path := range paths {
		rec := serve(t, "GET", path)
		if rec.Code != http.StatusNotImplemented {
			t.Fatalf("%s: status = %d", path, rec.Code)
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if body["code"] != "NOT_PORTED" || body["route"] != "GET "+path {
			t.Fatalf("%s: body = %s", path, rec.Body.String())
		}
	}
}
```

`backend-go/cmd/borsd/main.go`:

```go
mkt := market.New(handles, cfg.DataDir)
ms := mstat.New(handles.Market, cfg.DataDir, mkt)
srv := &http.Server{Addr: cfg.Addr, Handler: httpapi.New(cfg, handles, mkt, ms)}
```

و `"borsterminal/backend/internal/mstat"` را import کنید.

- [ ] **Step 6: Write the handler tests**

`backend-go/internal/mstat/handlers_test.go`:

```go
package mstat

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestHandlersReturnPanelsWithSource(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, "", stubFlags{map[string]map[string]bool{}, true})
	s.clock = func() time.Time { return pinnedNow }
	cases := []struct {
		name   string
		target string
		fn     http.HandlerFunc
	}{
		{"summary", "/api/mstat/summary", s.Summary},
		{"histogram", "/api/mstat/histogram?group=stock", s.Histogram},
		{"thermometer", "/api/mstat/thermometer", s.Thermometer},
		{"depth", "/api/mstat/depth?group=eq_funds", s.Depth},
		{"clientsplit", "/api/mstat/clientsplit?tab=stock", s.ClientSplit},
		{"market-snapshot", "/api/mstat/market-snapshot", s.MarketSnapshot},
		{"phase", "/api/mstat/phase", s.Phase},
		{"mainwatch", "/api/mstat/mainwatch?limit=5", s.Mainwatch},
		{"industries", "/api/mstat/industries", s.Industries},
		{"timeline", "/api/mstat/timeline?mode=inst", s.Timeline},
		{"phases", "/api/mstat/phases", s.Phases},
	}
	for _, c := range cases {
		rec := httptest.NewRecorder()
		c.fn(rec, httptest.NewRequest("GET", c.target, nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("%s: status = %d (%s)", c.name, rec.Code, rec.Body.String())
		}
		var body map[string]any
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: %v", c.name, err)
		}
		if body["status"] != "ok" {
			t.Fatalf("%s: status field = %v", c.name, body["status"])
		}
		if body["source"] != "local:market.db" {
			t.Fatalf("%s: source = %v", c.name, body["source"])
		}
	}
}

func TestMainwatchValidation422(t *testing.T) {
	h := openFixture(t)
	s := New(h.Market, "", nil)
	for _, tc := range []struct {
		target, typ, field string
	}{
		{"/api/mstat/mainwatch?limit=abc", "int_parsing", "limit"},
		{"/api/mstat/mainwatch?desc=xx", "bool_parsing", "desc"},
	} {
		rec := httptest.NewRecorder()
		s.Mainwatch(rec, httptest.NewRequest("GET", tc.target, nil))
		if rec.Code != http.StatusUnprocessableEntity {
			t.Fatalf("%s: status = %d", tc.target, rec.Code)
		}
		var body struct {
			Detail []struct {
				Type string `json:"type"`
				Loc  []string `json:"loc"`
			} `json:"detail"`
		}
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatal(err)
		}
		if len(body.Detail) != 1 || body.Detail[0].Type != tc.typ ||
			len(body.Detail[0].Loc) != 2 || body.Detail[0].Loc[1] != tc.field {
			t.Fatalf("%s: body = %s", tc.target, rec.Body.String())
		}
	}
}
```

Run: `cd backend-go && go test ./internal/mstat/ ./internal/httpapi/ ./internal/datatoken/`
Expected: PASS.

- [ ] **Step 7: Run the whole suite**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: no gofmt output, vet silent, all packages ok.

- [ ] **Step 8: Commit**

```bash
git add backend-go/internal/datatoken backend-go/internal/mstat/service.go \
        backend-go/internal/mstat/handlers.go backend-go/internal/mstat/service_test.go \
        backend-go/internal/mstat/handlers_test.go backend-go/internal/market/service.go \
        backend-go/internal/httpapi/errors.go backend-go/internal/httpapi/server.go \
        backend-go/internal/httpapi/server_test.go backend-go/cmd/borsd/main.go
git commit -F - <<'CLOSE'
feat(go): یازده مسیرِ GETِ وضعیت بازار با کشِ هر-حالت

- کش همان _mstat_call است: TTL ۴۵ثانیه، سقفِ کهنگی ۹۰ثانیه، سروِ کهنه با
  بازسازیِ پس‌زمینه، تک‌پروازگی برایِ cold miss، و خطایی که هرگز کش نمی‌شود.
- کلیدِ کش نشانکِ فایل‌هایِ داده به‌علاوهٔ آخرین نقطهٔ mstat_snap است.
- پارامترها به قاعدهٔ FastAPI خوانده می‌شوند؛ limit/desc نامعتبر همان ۴۲۲ِ
  int_parsing/bool_parsing را می‌دهند.
CLOSE
```

---

### Task 10: گیتِ B2a رویِ دو کپیِ یخ‌زده و شاهدِ عددی

**Files:**
- Create: `tools/parity/cases_b2a.json`
- Create: `tools/parity/gate_b2a.py`
- Create: `docs/superpowers/reports/2026-10-30-b2a-mstat-parity.md`
- Create (generated): `_audit/parity/B2a.json`, `_audit/parity/B2a-contract.json`

**Interfaces:**
- Consumes: `tools/parity/gate_b1.py` به‌عنوانِ ماژول (کپی/هش/گاردِ کناربانک/کشتنِ فقط PIDِ خودی)، `backend-go/bin/borsd`، `backend-go/bin/parity`.

- [ ] **Step 1: Write the cases file**

`tools/parity/cases_b2a.json` (توجه: `clock_now` عمداً بیرون است — هر دو کش تا ۴۵ ثانیه مقدارِ کهنه سرو می‌کنند و مقایسهٔ ثانیه‌ای دروغین می‌شد؛ gate خودش اعتبارِ timestamp را می‌سنجد):

```json
{
 "db_sha256": "",
 "cases": [
  {"name": "summary", "method": "GET", "path": "/api/mstat/summary", "exclude": ["phase.clock_now"]},
  {"name": "histogram-all", "method": "GET", "path": "/api/mstat/histogram", "exclude": []},
  {"name": "histogram-stock", "method": "GET", "path": "/api/mstat/histogram?group=stock", "exclude": []},
  {"name": "histogram-lev", "method": "GET", "path": "/api/mstat/histogram?group=lev", "exclude": []},
  {"name": "histogram-empty-group", "method": "GET", "path": "/api/mstat/histogram?group=", "exclude": []},
  {"name": "thermometer-all", "method": "GET", "path": "/api/mstat/thermometer", "exclude": []},
  {"name": "thermometer-eqfunds", "method": "GET", "path": "/api/mstat/thermometer?group=eq_funds", "exclude": []},
  {"name": "thermometer-gold", "method": "GET", "path": "/api/mstat/thermometer?group=gold", "exclude": []},
  {"name": "depth-all", "method": "GET", "path": "/api/mstat/depth", "exclude": []},
  {"name": "depth-stock", "method": "GET", "path": "/api/mstat/depth?group=stock", "exclude": []},
  {"name": "depth-fixed", "method": "GET", "path": "/api/mstat/depth?group=fixed", "exclude": []},
  {"name": "clientsplit-all", "method": "GET", "path": "/api/mstat/clientsplit", "exclude": []},
  {"name": "clientsplit-stock", "method": "GET", "path": "/api/mstat/clientsplit?tab=stock", "exclude": []},
  {"name": "clientsplit-unknown-tab", "method": "GET", "path": "/api/mstat/clientsplit?tab=bogus", "exclude": []},
  {"name": "market-snapshot", "method": "GET", "path": "/api/mstat/market-snapshot", "exclude": []},
  {"name": "phase", "method": "GET", "path": "/api/mstat/phase", "exclude": ["clock_now"]},
  {"name": "mainwatch-default", "method": "GET", "path": "/api/mstat/mainwatch", "exclude": []},
  {"name": "mainwatch-stock-5", "method": "GET", "path": "/api/mstat/mainwatch?group=stock&limit=5", "exclude": []},
  {"name": "mainwatch-val-asc", "method": "GET", "path": "/api/mstat/mainwatch?sort=val&desc=false&limit=10", "exclude": []},
  {"name": "mainwatch-symbol", "method": "GET", "path": "/api/mstat/mainwatch?sort=symbol&desc=true&limit=10", "exclude": []},
  {"name": "mainwatch-pctlast", "method": "GET", "path": "/api/mstat/mainwatch?sort=pct_last&desc=false&limit=10", "exclude": []},
  {"name": "mainwatch-power", "method": "GET", "path": "/api/mstat/mainwatch?sort=pow&limit=10", "exclude": []},
  {"name": "mainwatch-top50", "method": "GET", "path": "/api/mstat/mainwatch?group=top50&limit=3", "exclude": []},
  {"name": "mainwatch-limit-zero", "method": "GET", "path": "/api/mstat/mainwatch?limit=0", "exclude": []},
  {"name": "mainwatch-limit-negative", "method": "GET", "path": "/api/mstat/mainwatch?limit=-3", "exclude": []},
  {"name": "mainwatch-desc-upper", "method": "GET", "path": "/api/mstat/mainwatch?desc=FALSE&limit=4", "exclude": []},
  {"name": "mainwatch-limit-422", "method": "GET", "path": "/api/mstat/mainwatch?limit=abc", "exclude": []},
  {"name": "mainwatch-desc-422", "method": "GET", "path": "/api/mstat/mainwatch?desc=xx", "exclude": []},
  {"name": "industries", "method": "GET", "path": "/api/mstat/industries", "exclude": []},
  {"name": "timeline-cum", "method": "GET", "path": "/api/mstat/timeline", "exclude": []},
  {"name": "timeline-inst", "method": "GET", "path": "/api/mstat/timeline?mode=inst", "exclude": []},
  {"name": "timeline-bogus-mode", "method": "GET", "path": "/api/mstat/timeline?mode=bogus", "exclude": []},
  {"name": "phases", "method": "GET", "path": "/api/mstat/phases", "exclude": []}
 ]
}
```

`mainwatch?limit=0` مهم است: پایتون `int(limit or 120)` دارد، پس صفر «بی‌مقدار» است و ۱۲۰ می‌شود — نه ۱. `limit=-3` به ۱ بسته می‌شود.

- [ ] **Step 2: Write the gate**

`tools/parity/gate_b2a.py`:

```python
#!/usr/bin/env python
"""گیتِ B2a: یازده مسیرِ GETِ /api/mstat/* رویِ دو کپیِ یخ‌زده.

همان قواعدِ gate_b1 را از خودش قرض می‌گیرد: بانکِ عملیاتی با SQLite باز
نمی‌شود، هر کپی quick_check می‌خورد، گاردِ کناربانک پیش/پس مقایسه می‌شود، و
فقط PIDهایی کشته می‌شوند که همین اسکریپت بالا آورده.

سه سنجهٔ تازه:
* صفر اختلاف رویِ یازده مسیر (قرارداد) — دو ۴۲۲ و یک صنعتِ برگرفته از دادهٔ
  همان کپی هم در دسته‌اند.
* POST /api/mstat/snapshot در Go هنوز ۵۰۱ و در پایتون ۲۰۰ است — تفاوتِ
  اعلام‌شده تا B6.
* clock_now بیرونِ مقایسه است ولی هر دو باید timestampِ معتبر بدهند.

کدِ خروج: 0 سبز، 1 اندازه‌گیری شد و قرمز، 2 نتوانستیم اندازه بگیریم.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
import gate_b1 as base  # noqa: E402

ROOT = base.ROOT
GO = base.GO
CASES = os.path.join(HERE, "cases_b2a.json")
OUT = os.path.join(ROOT, "_audit", "parity", "B2a.json")
CONTRACT = os.path.join(ROOT, "_audit", "parity", "B2a-contract.json")
GO_PORT = int(os.environ.get("BORS_B2A_GO_PORT", "8296"))
PY_PORT = int(os.environ.get("BORS_B2A_PY_PORT", "8297"))


def post_json(url):
    req = urllib.request.Request(url, data=b"", method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read() or b"{}")
        except ValueError:
            body = {}
        return e.code, body


def industry_case(py_url):
    """نامِ نخستین صنعتِ دارایِ نماد از خودِ پایتون.

    صنعت‌ها در بانک با حرف‌هایِ عربی/فارسی ذخیره می‌شوند و نوشتنشان در فایلِ
    کیس شکننده است؛ از پاسخِ خودِ سرور برداشته و percent-encode می‌شود تا فیلتر
    رویِ دادهٔ واقعی بیفتد، نه رویِ صنعتِ ناموجود.
    """
    status, _, body = base.http_get(py_url + "/api/mstat/industries")
    if status != 200:
        return None
    try:
        rows = json.loads(body).get("rows") or []
    except ValueError:
        return None
    for row in rows:
        name = (row.get("industry") or "").strip()
        if name and (row.get("symbols") or 0) > 0:
            return name
    return None


def valid_clock(value):
    try:
        time.strptime(value, "%Y-%m-%d %H:%M:%S")
        return True
    except (TypeError, ValueError):
        return False


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    for target, out in (("./cmd/borsd", base.BORSD), ("./cmd/parity", base.PARITY)):
        rc, log = base.run(["go", "build", "-o", out, target], cwd=GO)
        if rc != 0:
            print(log)
            return 2
    rc, tests = base.run(["go", "test", "-count=1", "./..."], cwd=GO)
    if rc != 0:
        print(tests)
        return 2
    for port in (GO_PORT, PY_PORT):
        if not base.port_free(port):
            print("port %d is busy" % port)
            return 2
    commit = base.run(["git", "rev-parse", "--short", "HEAD"])[1].strip()

    before_sidecars = base.sidecar_state()
    tmp = tempfile.mkdtemp(prefix="bors-b2a-")
    go_dir = os.path.join(tmp, "go")
    py_dir = os.path.join(tmp, "py")
    os.makedirs(go_dir)
    os.makedirs(py_dir)
    procs = []
    result = 2
    try:
        for name in base.DB_NAMES:
            src = os.path.join(ROOT, name)
            if not os.path.exists(src):
                continue
            for dst_dir in (go_dir, py_dir):
                try:
                    check = base.snapshot_db(src, os.path.join(dst_dir, name))
                except Exception as err:  # noqa: BLE001 — کپیِ ناخوانا = اندازه‌گیری ناممکن
                    print("snapshot copy unusable: %s: %s" % (name, err))
                    return 2
                if check != ["ok"]:
                    print("quick_check failed for %s copy: %s" % (name, check))
                    return 2
        go_db = os.path.join(go_dir, "market.db")
        py_db = os.path.join(py_dir, "market.db")
        db_prints = base.db_fingerprint(go_db)
        if db_prints != base.db_fingerprint(py_db):
            print("the two copies are not identical")
            return 2

        py_env = dict(os.environ, BORS_DATA_DIR=py_dir, BORS_NO_FETCH_LOOPS="1",
                      BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
                      BORS_PARITY_PORT=str(PY_PORT), PYTHONIOENCODING="utf-8")
        py_log = open(os.path.join(tmp, "py.log"), "w", encoding="utf-8")
        procs.append((subprocess.Popen([sys.executable, base.SERVE], cwd=ROOT, env=py_env,
                                       stdout=py_log, stderr=subprocess.STDOUT), py_log))
        if not base.wait_json("http://127.0.0.1:%d/openapi.json" % PY_PORT, 60.0, lambda b: True):
            return 2
        go_proc = subprocess.Popen(
            [base.BORSD, "--port", str(GO_PORT), "--read-only", "--no-loops", "--db-dir", go_dir],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append((go_proc, None))
        if not base.wait_json("http://127.0.0.1:%d/healthz" % GO_PORT, 15.0,
                              lambda b: b.get("status") == "ok"):
            return 2
        _, _, health_body = base.http_get("http://127.0.0.1:%d/healthz" % GO_PORT)
        health = json.loads(health_body)
        if os.path.normcase(os.path.normpath(health.get("data_dir", ""))) != \
                os.path.normcase(os.path.normpath(go_dir)):
            print("healthz is not from this gate's server")
            return 2

        py_url = "http://127.0.0.1:%d" % PY_PORT
        go_url = "http://127.0.0.1:%d" % GO_PORT

        cases = json.load(open(CASES, encoding="utf-8"))
        picked = industry_case(py_url)
        if picked:
            cases["cases"].append({
                "name": "mainwatch-industry-live", "method": "GET",
                "path": "/api/mstat/mainwatch?industry=%s&limit=5"
                        % urllib.parse.quote(picked, safe=""),
                "exclude": []})
        dynamic_cases = os.path.join(tmp, "cases_b2a_run.json")
        with open(dynamic_cases, "w", encoding="utf-8") as f:
            json.dump(cases, f, ensure_ascii=False)
        case_count = len(cases["cases"])

        rc, log = base.run([base.PARITY, "--py", py_url, "--go", go_url,
                            "--cases", dynamic_cases, "--out", CONTRACT, "--commit", commit])
        print(log.strip())
        if rc == 2:
            print("contract batch could not run")
            return 2
        contract = json.load(open(CONTRACT, encoding="utf-8"))
        contract_ok = contract["failed"] == 0 and contract["passed"] == case_count

        # POST پس از دستهٔ قرارداد: نوشتنِ پایتون رویِ کپیِ خودش ممکن است نقطهٔ
        # تازه‌ای بسازد و تایم‌لاین را عوض کند.
        py_post, py_post_body = post_json(py_url + "/api/mstat/snapshot")
        go_post, go_post_body = post_json(go_url + "/api/mstat/snapshot")
        post_ok = (go_post == 501 and go_post_body.get("code") == "NOT_PORTED"
                   and py_post == 200 and py_post_body.get("status") == "ok")

        _, _, tl_py = base.http_get(py_url + "/api/mstat/timeline")
        _, _, tl_go = base.http_get(go_url + "/api/mstat/timeline")
        tl_py_j, tl_go_j = json.loads(tl_py), json.loads(tl_go)
        points_py, points_go = tl_py_j.get("points"), tl_go_j.get("points")
        timeline_ok = (points_py == points_go
                       and tl_py_j.get("ready") == tl_go_j.get("ready")
                       and points_py is not None)
        timeline_exercised = (points_py or 0) >= 2

        _, _, ph_py = base.http_get(py_url + "/api/mstat/phase")
        _, _, ph_go = base.http_get(go_url + "/api/mstat/phase")
        clock_py = json.loads(ph_py).get("clock_now")
        clock_go = json.loads(ph_go).get("clock_now")
        clock_ok = valid_clock(clock_py) and valid_clock(clock_go)

        base.stop(procs)
        go_db_unchanged = base.db_fingerprint(go_db) == db_prints

        checks = {"contract": contract_ok, "post_501": post_ok,
                  "timeline": timeline_ok, "clock": clock_ok,
                  "go_read_only": go_db_unchanged}
        payload = {
            "commit": commit,
            "python": sys.version.split()[0],
            "db": {"sha256": db_prints["market.db"],
                   "wal_sha256": db_prints.get("market.db-wal"),
                   "frozen_ok": True, "go_copy_unchanged": go_db_unchanged},
            "contract": {"passed": contract["passed"], "failed": contract["failed"],
                         "cases": case_count,
                         "report": os.path.relpath(CONTRACT, ROOT), "ok": contract_ok},
            "post": {"py": py_post, "go": go_post,
                     "go_code": go_post_body.get("code"), "ok": post_ok},
            "timeline": {"py_points": points_py, "go_points": points_go,
                         "py_ready": tl_py_j.get("ready"),
                         "go_ready": tl_go_j.get("ready"),
                         "exercised": timeline_exercised,
                         "industry_case": picked, "ok": timeline_ok},
            "phase": {"py_clock": clock_py, "go_clock": clock_go, "ok": clock_ok},
            "checks": checks,
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with open(OUT, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print("checks: " + " ".join("%s=%s" % kv for kv in checks.items()))
        print("contract %d/%d | timeline points py=%s go=%s (exercised=%s)"
              % (contract["passed"], case_count, points_py, points_go, timeline_exercised))
        result = 0 if all(checks.values()) else 1
    finally:
        base.stop(procs)
        after_sidecars = base.sidecar_state()
        problem = base.sidecar_problem(before_sidecars, after_sidecars)
        if problem:
            print("sidecar guard failed: %s" % problem)
            result = 2
        shutil.rmtree(tmp, ignore_errors=True)
    if result == 0:
        print("sidecar guard ok")
    return result


if __name__ == "__main__":
    sys.exit(main())
```

**دقت‌ها:**
- صنعت در فایلِ کیس نیست چون حرفِ `ي`/`ی` در بانک یکسان نیست؛ gate نامش را از `/api/mstat/industries`ِ همان کپی می‌گیرد و percent-encode می‌کند. اگر هیچ صنعتی نبود، آن کیس اضافه نمی‌شود و همین در شاهد نوشته می‌شود (`industry_case: null`).
- `timeline.exercised` جدا از `ok` است: با صفر نقطه، تطبیقِ دو بدنهٔ «بی‌نقطه» پاریتی است ولی مسیرِ عمیق اثبات نمی‌شود — عمقِ مسیر با طلایی‌هایِ Task 7 اثبات شده و این‌جا صادقانه ثبت می‌شود.
- POSTِ پایتون عمداً اجرا می‌شود تا معلوم شود تفاوت دقیقاً «۵۰۱ در برابر ۲۰۰» است، نه «Go ۵۰۱ و پایتون هم خراب».

Run: `python tools/parity/gate_b2a.py`
Expected: در دورِ اول یا سبز است یا اختلافِ واقعی نشان می‌دهد؛ هر اختلاف باید ریشه‌ای در پورتِ پنلِ مربوطه باشد، نه در گیت.

- [ ] **Step 3: Write the report**

`docs/superpowers/reports/2026-10-30-b2a-mstat-parity.md` — جدولِ RTLِ فارسی با این سطرها (اعداد از `_audit/parity/B2a.json` و `B2a-contract.json` کپی می‌شوند، نه از حافظه):

| سنجه | پایتون | Go | حکم |
| --- | --- | --- | --- |
| مسیرهایِ پوشیده | ۱۱ | ۱۱ | ۱۱ مسیر |
| کیس‌هایِ قرارداد | n | n | pass/fail |
| بیشینهٔ دلتایِ عددی | — | — | ۰ |
| POST snapshot | ۲۰۰ | ۵۰۱ | تفاوتِ اعلام‌شده (B6) |
| نقاطِ تایم‌لاین | p | p | exercised بله/خیر |
| کپیِ Go | — | بدونِ تغییر | read-only |
| گاردِ کناربانک | ok | ok | ok |

و بخش‌هایِ: «چه چیزی پورت شد»، «تفاوت‌هایِ اعلام‌شده» (POST ۵۰۱؛ `clock_now` بیرون از مقایسه؛ کلیدِ کش با نشانکِ فایل به‌جایِ شمارندهٔ درون‌پروسه)، «چه چیزی راستی‌آزمایی نشد» (`/api/mstat/board` و smart-money در B2-2؛ مسیرِ عمیقِ تایم‌لاین اگر `mstat_snap` خالی باشد؛ limitهایِ بزرگ‌تر از int64 که پایتون می‌پذیرد و Go ۴۲۲ می‌دهد).

- [ ] **Step 4: Commit the gate and the report**

```bash
git add tools/parity/cases_b2a.json tools/parity/gate_b2a.py \
        docs/superpowers/reports/2026-10-30-b2a-mstat-parity.md
git commit -F - <<'CLOSE'
test(tools): گیتِ B2a برایِ یازده مسیرِ وضعیت بازار

- دو کپیِ یخ‌زده، هر دو سرور هم‌زمان، و صفر اختلاف رویِ ۳۳ کیسِ قرارداد
  به‌علاوهٔ یک کیسِ صنعت که نامش از دادهٔ همان کپی برداشته می‌شود.
- POST snapshot عمداً در گیت است تا «۵۰۱ در برابرِ ۲۰۰» ثبت شود، نه فرض.
- clock_now بیرون از مقایسه و اعتبارش جدا سنجیده می‌شود.
CLOSE
```

- [ ] **Step 5: Re-run the gate on the committed tree**

Run: `python tools/parity/gate_b2a.py`
Expected: `checks: contract=True post_501=True timeline=True clock=True go_read_only=True`، سپس `sidecar guard ok`، exit 0. اگر قرمز شد، کدِ پنلِ همان مسیر اصلاح می‌شود — گیت هرگز شل نمی‌شود.

- [ ] **Step 6: Commit the evidence**

```bash
git add _audit/parity/B2a.json _audit/parity/B2a-contract.json
git commit -F - <<'CLOSE'
chore(evidence): شاهدِ B2a — صفر اختلاف رویِ یازده مسیرِ وضعیت بازار

- شاهد رویِ همین درختِ کامیت‌شده اندازه‌گیری شد؛ commit داخلِ JSON همان
  SHAی است که کدِ گیت و پنل‌ها در آن است.
- کپیِ Go پس از خاموشی دست‌نخورده است و گاردِ کناربانک سبز.
CLOSE
```

- [ ] **Step 7: Close the stage in the ledger**

در `.superpowers/sdd/2026-10-30-backend-b2-mstat/progress.md` یک بخشِ `### Task 10: complete` با SHAهایِ سه کامیت، اعدادِ `B2a.json`، و «چه چیزی به B2-2 موکول شد» بنویسید. (B2-2: `/api/mstat/smart-money`، `/api/mstat/board`، گیتِ کاملِ ۱۳ مسیر.)

---

## پس از این پلن

B2-2 (پلنِ جدا): `smart_money` و `board` رویِ همان زیرساخت، به‌علاوهٔ گیتِ نهاییِ ۱۳ مسیر و `day_verdict`/`market_state` اگر داورِ حکم لازم شد. تا آن روز `/api/mstat/board` و `/api/mstat/smart-money` در Go همان ۵۰۱ِ `NOT_PORTED` را می‌دهند و در `routes.json` دست‌نخورده می‌مانند.
