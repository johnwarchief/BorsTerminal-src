# به‌روزرسانی رویدادمحور ۵ شاخص بنیادی — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** کوتاه‌کردن فاصلهٔ «انتشار اطلاعیه در کدال» تا «تازه‌شدن ۵ شاخص» از ~۳ ساعت/یک روز به ≤۱۵ دقیقه در پنجرهٔ انتشار، با باطل‌سازی فوری عدد کهنه، قفل متقابل با خط شبانه، و نمایش `as_of` هر شاخص.

**Architecture:** زیرساخت موجود `codal_pipeline` (کشف افزایشی با watermark، صف با claim/retry، `pipeline_dirty`، `recompute_dirty`) حفظ می‌شود. سه تغییر معماری: (۱) فاصلهٔ شبکهٔ ثابت ۳ساعته با مدل پنجرهٔ انتشارِ یادگرفته‌شده تطبیقی می‌شود؛ (۲) باطل‌سازی `fts_results` از محاسبهٔ سنگین جدا و فوری می‌شود؛ (۳) worker و orchestrator شبانه با ترتیب دو قفل موجود از نوشتن هم‌زمان منع می‌شوند. تازگی per-symbol از canonical مشتق می‌شود (بدون جدول جدید).

**Tech Stack:** Python 3 (stdlib + FastAPI), SQLite (`market.db`), pytest-style standalone guards in `dev/`, React 18 + TypeScript + Zod + Vitest in `frontend-v2`.

**Spec:** `docs/superpowers/specs/2026-11-03-codal-event-driven-5axis-update-design.md`

## Global Constraints

- شاخهٔ کار: `integration/4axes-main-2026-11-03`؛ **push نکن** مگر با اجازهٔ صریح مالک.
- هر commit فقط با فایل‌های همان Task و با هویت: `git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit ...`. هرگز `git config` ننویس و هرگز `git add -A` نزن.
- تغییراتِ uncommitted مربوط به پورت Go (`backend-go/...`) بخشی از این پلن نیست؛ آن‌ها را stage/commit نکن.
- آزمون‌های پایتون به‌صورت پیش‌فرض آفلاین‌اند: `BORS_CODAL_OFFLINE=1` و `PYTHONIOENCODING=utf-8`. هیچ تستی نباید به `search.codal.ir` یا ADB دست بزند، مگر گیتِ زندهٔ opt-in در Task 9.
- هیچ جدول تازه‌ای به `market.db` اضافه نمی‌شود؛ تازگی مشتق است.
- فرمول/آستانهٔ ۵ شاخص، خط شبانهٔ ۱۸:۳۰، snapshot GitHub، و دکمهٔ دستی ADB تغییر نمی‌کنند.
- رشته‌های کاربر-دیدنی فارسی و RTL؛ اعداد در فرانت با `faNum`/`toFaDigits`؛ هیچ عدد دست‌نویس در متن.
- تنها تعریفِ «پایان‌یافته» در `codal_fetcher.ledger_terminal_sql` است؛ تعریف دوم نساز.
- `codal_pipeline` stdlib-only می‌ماند: importهای تازه فقط `codal_cadence` (stdlib) و `codal_row_gate` (stdlib، ریشه) هستند؛ `api`/`fts_engine` فقط دیرهنگام (lazy) import می‌شوند.

---

## File Structure

| فایل | مسئولیت |
|---|---|
| `codal_cadence.py` (جدید) | محاسبهٔ خالصِ پنجرهٔ انتشار، `inside_window`، `gap_seconds`؛ بدون I/O |
| `codal_pipeline.py` | اتصال پنجره به DB، کادنس تطبیقی در `worker_once`/`next_wakeup`، باطل‌سازی فوری در `run_cycle`، `orchestrator_busy`، فیلدهای status |
| `codal_row_gate.py` (جدید، ریشه) | `validate_extracted_row()` برای گیتِ ردیفیِ نوشتنِ افزایشی؛ stdlib-only و قابلِ بسته‌بندی در frozen |
| `codal_fetcher.py` | افزودن `quarantined` به وضعیت‌های پایان‌یافته |
| `dev/codal_auto_update.py` | انتظار برای آزادشدن `pipeline_lock` پیش از کپی staging |
| `api/fundamental.py` | `freshness_of()`، route دسته‌ای، افزودن `freshness` به کارت |
| `codal_periods.py` | `j2g_date()` و `g2j_tuple()` برای تبدیل تاریخ (لازمِ گیتِ ردیفی و `as_of`) |
| `frontend-v2/src/features/fundamental/api/useFtsCard.ts` | schema برای `freshness` |
| `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx` | نشان «تازه تا …» + tooltip |
| `dev/test_codal_event_update.py` (جدید) | گارد آفلاین همهٔ رفتارهای بالا |
| `dev/run_all_tests.py` | ثبت گارد جدید |

---

### Task 0: Baseline سبزِ گاردهای موجود

**Files:** هیچ تغییری.

**Interfaces:**
- Consumes: none
- Produces: شاهدِ «قبل از تغییر، این دو گارد سبز بودند».

- [ ] **Step 1: اجرای گاردِ زمان‌بندی موجود**

```bash
cd "D:/BorsTerminal-worktrees/4axes-main-integration"
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
```

Expected: خروجی شامل `N passed / 0 failed` و exit code 0.

- [ ] **Step 2: اجرای گاردِ orchestrate شبانه**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_auto_update_v11.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 3: ثبت baseline**

اگر هر دو سبز نبودند، **متوقف شو** و علت را گزارش کن؛ تغییرات این پلن روی baseline قرمز سوار نمی‌شوند.

---

### Task 1: ماژول خالصِ کادنس انتشار

**Files:**
- Create: `codal_cadence.py`
- Test: `dev/test_codal_event_update.py` (بخش ۱)

**Interfaces:**
- Produces:
  - `windows_from_hour_counts(counts: dict[int, int], min_samples: int = 200, share: float = 0.25) -> list[tuple[float, float]]`
  - `inside_window(hour: float, windows: list[tuple[float, float]]) -> bool`
  - `gap_seconds(hour: float, windows, enabled: bool = True, fast: int = 600, slow: int = 10800, jitter_s: float = 0.0) -> int`
  - `window_labels(windows) -> list[str]`
  - constants: `FAST_GAP_S=600`، `SLOW_GAP_S=10800`، `MIN_GAP_S=60`، `DEFAULT_WINDOWS=((8.0, 20.0),)`

- [ ] **Step 1: نوشتن تستِ شکست‌خورده**

`dev/test_codal_event_update.py` را بساز و این بخش را در آن بگذار:

```python
# -*- coding: utf-8 -*-
"""dev/test_codal_event_update.py — گارد آفلاین به‌روزرسانی رویدادمحور ۵ شاخص.

Run: PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
"""
import datetime
import json
import os
import shutil
import sqlite3
import sys
import tempfile

os.environ["BORS_CODAL_OFFLINE"] = "1"
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "dev"))

import codal_cadence as CAD          # noqa: E402
import codal_fetcher as CF           # noqa: E402
import codal_pipeline as PL          # noqa: E402

CHECKS = []


def ck(cond, msg, detail=""):
    CHECKS.append(bool(cond))
    print("  %s %s%s" % ("PASS" if cond else "FAIL", msg,
                         ("   ← " + str(detail)) if (detail and not cond) else ""))
    return bool(cond)


TMP = tempfile.mkdtemp(prefix="codal_event_update_")


def section(name):
    print("\n== %s ==" % name)


# ── ۱) ماژول خالصِ کادنس ──────────────────────────────────────────────────
section("cadence: windows / gap")
counts = {h: 0 for h in range(24)}
for h, n in ((8, 10), (9, 100), (10, 100), (11, 90),
             (16, 100), (17, 100), (18, 80)):
    counts[h] = n
w = CAD.windows_from_hour_counts(counts, min_samples=200, share=0.25)
ck(len(w) == 2 and w[0][0] <= 9 and w[0][1] >= 12 and w[1][0] <= 16 and w[1][1] >= 19,
   "دو قلهٔ انتشار ⇒ دو پنجرهٔ جدا", w)
ck(CAD.windows_from_hour_counts({h: 1 for h in range(24)}, min_samples=200)
   == list(CAD.DEFAULT_WINDOWS),
   "نمونهٔ کم ⇒ پیش‌فرضِ محافظه‌کارانه 08:00–20:00")
ck(CAD.inside_window(9.5, w) and not CAD.inside_window(14.0, w),
   "inside_window مرزها را درست می‌فهمد", (w,))
ck(CAD.gap_seconds(9.5, w, enabled=True) == 600,
   "داخلِ پنجره ⇒ ۶۰۰ ثانیه")
ck(CAD.gap_seconds(14.0, w, enabled=True) == 10800,
   "بیرونِ پنجره ⇒ ۳ ساعت")
ck(CAD.gap_seconds(9.5, w, enabled=False) == 10800,
   "خاموش ⇒ همیشه ۳ ساعت")
ck(CAD.gap_seconds(9.5, w, enabled=True, jitter_s=-100000) == 60,
   "jitter هرگز زیرِ کفِ ۶۰ ثانیه نمی‌رود")
ck(CAD.window_labels(w)[0] == "08:30-12:30",
   "برچسبِ پنجره برای status", CAD.window_labels(w))
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `ModuleNotFoundError: No module named 'codal_cadence'`.

- [ ] **Step 3: پیاده‌سازیِ حداقلی**

`codal_cadence.py`:

```python
# -*- coding: utf-8 -*-
"""codal_cadence.py — محاسبهٔ خالصِ پنجرهٔ انتشار و فاصلهٔ شبکه.

بدون I/O و بدون import از پروژه؛ `codal_pipeline` دادهٔ ساعت را می‌دهد و این
ماژول فقط تصمیم می‌گیرد «الان داخل پنجره‌ایم؟ چند ثانیه صبر کنیم؟».
"""
from __future__ import annotations

FAST_GAP_S = 600
SLOW_GAP_S = 3 * 3600
MIN_GAP_S = 60
DEFAULT_WINDOWS = ((8.0, 20.0),)


def windows_from_hour_counts(counts, min_samples=200, share=0.25):
    """هیستوگرامِ ۲۴ساعته ⇒ بازه‌های پیوستهٔ انتشار.

    نمونهٔ کم ⇒ پیش‌فرضِ ۸ تا ۲۰ (محافظه‌کارانه، بی‌ادعا). هر ساعتِ فعال =
    سهمی ≥ ۲۵٪ اوج؛ حاشیهٔ نیم‌ساعت چپ و یک‌ساعت‌ونیم راست؛ پنجره‌های نزدیک
    (< ۲ ساعت فاصله) یکی می‌شوند.
    """
    total = sum(int(v or 0) for v in (counts or {}).values())
    if total < int(min_samples):
        return list(DEFAULT_WINDOWS)
    peak = max([int(v or 0) for v in counts.values()] or [0])
    threshold = max(1, int(peak * float(share)))
    active = sorted(h for h in range(24) if int(counts.get(h, 0)) >= threshold)
    if not active:
        return list(DEFAULT_WINDOWS)
    spans = []
    start = prev = active[0]
    for h in active[1:]:
        if h == prev + 1:
            prev = h
            continue
        spans.append((start, prev))
        start = prev = h
    spans.append((start, prev))
    windows = []
    for a, b in spans:
        lo = max(0.0, float(a) - 0.5)
        hi = min(24.0, float(b) + 1.5)
        if windows and lo - windows[-1][1] < 2.0:
            windows[-1] = (windows[-1][0], max(windows[-1][1], hi))
        else:
            windows.append((lo, hi))
    return windows


def inside_window(hour, windows):
    h = float(hour)
    return any(float(lo) <= h < float(hi) for lo, hi in (windows or ()))


def gap_seconds(hour, windows, enabled=True, fast=FAST_GAP_S,
                slow=SLOW_GAP_S, jitter_s=0.0):
    base = fast if (enabled and inside_window(hour, windows)) else slow
    return max(MIN_GAP_S, int(base + float(jitter_s)))


def window_labels(windows):
    def fmt(x):
        h = int(x)
        m = int(round((float(x) - h) * 60))
        if m == 60:
            h, m = h + 1, 0
        return "%02d:%02d" % (h, m)
    return ["%s-%s" % (fmt(a), fmt(b)) for a, b in (windows or ())]
```

- [ ] **Step 4: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها تا این بخش؛ exit 0.

- [ ] **Step 5: Commit**

```bash
git add codal_cadence.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(codal): ماژول خالصِ پنجرهٔ انتشار و فاصلهٔ شبکه"
```

---

### Task 2: اتصال پنجرهٔ انتشار به `codal_pipeline`

**Files:**
- Modify: `codal_pipeline.py` (imports، constants، `publication_windows`، `current_network_gap`، `worker_once`، `__all__`)
- Test: `dev/test_codal_event_update.py` (بخش ۲)

**Interfaces:**
- Consumes: `codal_cadence.windows_from_hour_counts`، `inside_window`، `gap_seconds`
- Produces:
  - `publication_windows(conn, now=None) -> {"day","windows","source","samples"}`
  - `current_network_gap(conn, now=None, jitter=True) -> (gap_s: int, publication: dict)`
  - `worker_once` خروجی‌اش کلیدهای `publication` و `network_gap_s` را دارد؛ امضای تابع تغییر نمی‌کند و gap را درون‌خطی از `current_network_gap` می‌گیرد.

- [ ] **Step 1: تستِ شکست‌خورده را به فایل تست اضافه کن**

```python
# ── ۲) پنجره از دادهٔ واقعیِ codal_notices ────────────────────────────────
section("pipeline: publication windows from DB")


def fresh_db():
    c = sqlite3.connect(":memory:", timeout=60, isolation_level=None)
    c.row_factory = sqlite3.Row
    CF.create_schema(c)
    CF.migrate_schema(c)
    PL.ensure_schema(c)
    c.execute("CREATE TABLE IF NOT EXISTS instruments (ins_code TEXT PRIMARY KEY,"
              " l_val18 TEXT, l_val30 TEXT, paper_type INTEGER)")
    return c


def add_notice(c, tn, sym, pub="1405/07/20 10:00:00",
               title="گزارش فعالیت ماهانه دوره ۱ ماهه منتهی به ۱۴۰۵/۰۷/۳۰"):
    c.execute("INSERT OR REPLACE INTO codal_notices (tracing_no, symbol,"
              " company_name, title, letter_code, publish_date, sent_date, url,"
              " fetched_at, pdf_url, excel_url) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (tn, sym, sym, title, "1", pub, pub,
               "https://codal.ir/L/Detail/%d" % tn, "2026-11-03 00:00:00", "", ""))


c = fresh_db()
for i in range(240):
    add_notice(c, 1000 + i, "نماد%d" % i,
               pub="1405/07/20 %02d:10:00" % (9 + (i % 3)))
pub = PL.publication_windows(c, now="2026-11-03 10:00:00")
ck(pub["source"] == "learned" and pub["samples"] >= 200,
   "نمونهٔ کافی ⇒ پنجره از داده یاد گرفته می‌شود", pub)
ck(any(a <= 9 and b >= 12 for a, b in pub["windows"]),
   "پنجرهٔ صبح درست ساخته شد", pub["windows"])
cache = PL.publication_windows(c, now="2026-11-03 18:00:00")
ck(cache.get("day") == pub.get("day") and cache["windows"] == pub["windows"],
   "کشِ روزانه دوباره SQL نمی‌زند")

c2 = fresh_db()
for i in range(3):
    add_notice(c2, 2000 + i, "کم%d" % i, pub="1405/07/20 10:00:00")
low = PL.publication_windows(c2, now="2026-11-03 10:00:00")
ck(low["source"] == "default"
   and low["windows"] == [list(x) for x in CAD.DEFAULT_WINDOWS],
   "نمونهٔ کم ⇒ پیش‌فرضِ ۸ تا ۲۰", low)

gap_in, pub_in = PL.current_network_gap(c, now="2026-11-03 10:00:00", jitter=False)
gap_out, _ = PL.current_network_gap(c, now="2026-11-03 14:00:00", jitter=False)
ck(gap_in == 600, "داخلِ پنجرهٔ یادگرفته ⇒ ۶۰۰ ثانیه", gap_in)
ck(gap_out == 10800, "بیرون ⇒ ۳ ساعت", gap_out)
ck("windows" in pub_in and "samples" in pub_in,
   "خروجیِ publication برای status کامل است", pub_in)
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `AttributeError: module 'codal_pipeline' has no attribute 'publication_windows'`.

- [ ] **Step 3: پیاده‌سازی**

در `codal_pipeline.py`:

1. به importها اضافه کن:

```python
import json
import random
```

و بعد از `import codal_fetcher as CF`:

```python
import codal_cadence as CAD
```

2. ثابت‌ها را نزدیک `DISCOVERY_MIN_GAP_S` اضافه کن:

```python
PUB_WINDOWS_CURSOR = "pub_windows_v1"
PUB_WINDOWS_LOOKBACK_ROWS = 20000
PUB_WINDOWS_MIN_SAMPLES = 200
FAST_GAP_S = CAD.FAST_GAP_S
SLOW_GAP_S = CAD.SLOW_GAP_S
DAILY_REQUEST_CURSOR = "codal_daily_requests"
DAILY_REQUEST_CAP = 200
```

3. تابع‌های تازه را پس از `watermarks`/`discover_auto` (قبل از بخشِ instrument) بگذار:

```python
def publication_windows(conn, now=None):
    """پنجره‌های انتشار از هیستوگرامِ ساعتِ اطلاعیه‌های اخیر.

    کش روزانه در `pipeline_cursor`؛ خطای DB/ستون ⇒ پیش‌فرض، نه استثنا.
    """
    today = str(now or now_s())[:10]
    try:
        cached = json.loads(cursor_get(conn, PUB_WINDOWS_CURSOR) or "{}")
    except (TypeError, ValueError, sqlite3.Error):
        cached = {}
    if isinstance(cached, dict) and cached.get("day") == today \
            and cached.get("windows"):
        return cached
    counts = {h: 0 for h in range(24)}
    samples = 0
    try:
        sql = (
            "SELECT %s, %s FROM codal_notices"
            " ORDER BY rowid DESC LIMIT ?"
            % (CF.CP.pub_canon_sql("publish_date"),
               CF.CP.pub_canon_sql("sent_date")))
        rows = conn.execute(sql, (PUB_WINDOWS_LOOKBACK_ROWS,)).fetchall()
    except sqlite3.Error:
        rows = []
    for pub, sent in rows:
        stamp = pub if len(pub or "") >= 16 else (sent or "")
        if len(stamp) >= 13 and stamp[11:13].isdigit():
            h = int(stamp[11:13])
            if 0 <= h < 24:
                counts[h] += 1
                samples += 1
    windows = CAD.windows_from_hour_counts(counts,
                                           min_samples=PUB_WINDOWS_MIN_SAMPLES)
    out = {
        "day": today,
        "windows": [list(w) for w in windows],
        "source": "learned" if samples >= PUB_WINDOWS_MIN_SAMPLES else "default",
        "samples": samples,
    }
    try:
        cursor_set(conn, PUB_WINDOWS_CURSOR, json.dumps(out, ensure_ascii=False),
                   note="publication windows")
    except sqlite3.Error:
        pass
    return out


def current_network_gap(conn, now=None, jitter=True):
    """فاصلهٔ مجازِ پاسِ شبکه + توصیفِ پنجره برای status."""
    at = _to_dt(now) or datetime.datetime.now()
    pub = publication_windows(conn, now=now)
    enabled = str(os.environ.get("BORS_CODAL_FAST_WINDOW", "1")).strip().lower() \
        not in ("0", "false", "no", "off")
    jitter_s = random.uniform(-60.0, 60.0) if jitter and enabled else 0.0
    hour = at.hour + at.minute / 60.0
    gap = CAD.gap_seconds(hour, pub["windows"], enabled=enabled,
                          fast=FAST_GAP_S, slow=SLOW_GAP_S, jitter_s=jitter_s)
    info = dict(pub)
    info["inside_window"] = CAD.inside_window(hour, pub["windows"])
    info["labels"] = CAD.window_labels(pub["windows"])
    info["network_gap_s"] = gap
    info["enabled"] = enabled
    return gap, info
```

4. در `worker_once`:

- ابتدای تابع، بعد از `now = now or now_s()` و بازکردنِ اتصال، **بعد از** بررسیِ `orchestrator_busy` (Task 5) این را بگذار:

```python
network_gap_s, publication = current_network_gap(conn, now=now, jitter=True)
```

- شرطِ `want` را عوض کن:

```python
want = age_net is None or age_net >= int(network_gap_s)
```

- `recalc` را عوض کن:

```python
recalc=("invalidate" if defer_recalc and recalc is None
        else (recalc or "auto")),
```

- بعد از `res["network"] = use_network` اضافه کن:

```python
res["publication"] = publication
res["network_gap_s"] = int(network_gap_s)
```

- `next_wakeup` را با gap صدا بزن:

```python
res["wakeup"] = next_wakeup(conn, now=now, network_gap_s=network_gap_s)
```

- `res["recalc_deferred"]` را دست نزن (با `recalc is None` همچنان true است).

5. در `__all__` این نام‌ها را اضافه کن:

```python
"publication_windows", "current_network_gap",
"PUB_WINDOWS_CURSOR", "DAILY_REQUEST_CURSOR", "DAILY_REQUEST_CAP",
"FAST_GAP_S", "SLOW_GAP_S",
```

(`orchestrator_busy` در Task 5 به `__all__` اضافه می‌شود، چون آن‌جا تعریف می‌شود.)

- [ ] **Step 4: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 5: اجرای گاردِ زمان‌بندی (رگرسیون)**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
```

Expected: `0 failed`. اگر شکست خورد، به‌جای تغییر انتظارها، کد را درست کن.

- [ ] **Step 6: Commit**

```bash
git add codal_pipeline.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(codal): کادنسِ تطبیقی از پنجرهٔ انتشارِ یادگرفته‌شده"
```

---

### Task 3: باطل‌سازیِ فوریِ `fts_results` + حالتِ invalidate-only

**Files:**
- Modify: `codal_pipeline.py` (`run_cycle`، `worker_once`)
- Test: `dev/test_codal_event_update.py` (بخش ۳)

**Interfaces:**
- Consumes: `process_claimed` tallyِ موجود با کلید `symbols`؛ `_invalidate_materialized`
- Produces: `run_cycle` خروجی‌های `touched`، `invalidated_symbols`، `recalc_invalidate_only`؛ رفتارِ `recalc="invalidate"`.

- [ ] **Step 1: تستِ شکست‌خورده**

```python
# ── ۳) نوشتنِ تازه ⇒ باطل‌سازیِ فوری، حتی در بازارِ باز ──────────────────
section("pipeline: immediate invalidation")


def ms_row(tn, sym, pe="1405/06/31", pub="1405/07/20 10:00:00"):
    return ("ms", (tn, sym, "گزارش فعالیت ماهانه", pe, 1405, 6,
                   1000.0, 6000.0, 900.0, 5400.0, 10.0, 60.0, "عدد",
                   "https://codal.ir/PDF/%d" % tn, ""), "ok")


c = fresh_db()
add_notice(c, 3001, "فولاد")
PL.enqueue(c, [(3001, "ms")])
calls = []
real_invalidate = PL._invalidate_materialized
PL._invalidate_materialized = lambda conn, symbols: (calls.append(list(symbols)),
                                                     len(symbols))[1]
try:
    out = PL.run_cycle(c, "test", discover=None,
                       scrape=lambda n: ms_row(3001, "فولاد"),
                       recalc="invalidate", now="2026-11-03 10:30:00",
                       instruments=lambda conn: {})
finally:
    PL._invalidate_materialized = real_invalidate
ck(out.get("touched") == ["فولاد"], "نمادِ نوشته‌شده در touched ثبت شد", out)
ck(calls == [["فولاد"]], "باطل‌سازیِ فوری با همان نماد صدا زده شد", calls)
ck(PL.dirty_count(c) == 1, "نماد در pipeline_dirty می‌ماند برای محاسبهٔ بعدی")
ck(out.get("recalc_invalidate_only") is True,
   "حالتِ invalidate-only اعلام شد", out)
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `touched`/`invalidated_symbols` غایب یا `calls == []`.

- [ ] **Step 3: پیاده‌سازی**

در `run_cycle`، قبل از حلقهٔ پردازش:

```python
touched = set()
```

داخلِ حلقه، بعد از `out["rejected"] += tally["rejected"]`:

```python
touched.update(tally.get("symbols") or [])
```

بعد از حلقه و **قبل از** `out["symbols"] = ...`:

```python
if touched:
    out["touched"] = sorted(touched)
    out["invalidated_symbols"] = _invalidate_materialized(conn, sorted(touched))
    # کشِ payload اسکرینر سراسری است؛ یک‌بار در هر چرخه، نه per-symbol.
    try:
        from api.screener import invalidate_screener_cache
        invalidate_screener_cache(drop_materialized=False)
    except Exception:
        pass
```

بعد از `if recalc == "auto":` این را قبلش بگذار:

```python
if recalc == "invalidate":
    recalc = None
    out["recalc_invalidate_only"] = True
if recalc == "auto":
    recalc = recompute_dirty
```

- [ ] **Step 4: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 5: رگرسیونِ scheduler و recalc افزایشی**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_incremental_recalc_v1104.py
```

Expected: `0 failed` در هر دو.

- [ ] **Step 6: Commit**

```bash
git add codal_pipeline.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(codal): باطل‌سازیِ فوریِ ردیف کهنه و حالت invalidate-only"
```

---

### Task 4: گیتِ ردیفی و قرنطینه

**Files:**
- Create: `codal_row_gate.py`
- Modify: `codal_periods.py` (`_j2g`، `_g2j`، `g2j_tuple`، `j2g_date`)
- Modify: `codal_fetcher.py` (`LEDGER_DONE_STATES` و `ledger_terminal_sql`)
- Modify: `codal_pipeline.py` (`process_claimed`، `run_cycle`، `counts`)
- Test: `dev/test_codal_event_update.py` (بخش ۴)

**Interfaces:**
- Produces:
  - `codal_row_gate.validate_extracted_row(kind: str, row: tuple, today=None) -> tuple[bool, str]`
  - `codal_periods.g2j_tuple(gy, gm, gd) -> (jy, jm, jd)`
  - `codal_periods.j2g_date(raw) -> str | None`
  - `codal_pipeline.process_claimed(conn, rows, scrape, now=None, validate=None)`
  - حالتِ `quarantined` در `codal_extracted`؛ `counts()["quarantined"]`؛ `claim` آن را برنمی‌دارد.

**چرا ماژولِ ریشه‌ای:** `dev/codal_validation.py` فقط در حالت سورس وجود دارد و در بیلد frozen بسته‌بندی نمی‌شود؛ `codal_pipeline` که در بیلد frozen اجرا می‌شود نمی‌تواند از `dev` import کند. گیتِ ردیفی باید در ریشه و stdlib-only باشد.

- [ ] **Step 1: تستِ شکست‌خورده**

```python
# ── ۴) گیتِ ردیفی: ردیف خراب هرگز در canonical نمی‌نشیند ─────────────────
section("validation: row gate + quarantine")
from codal_row_gate import validate_extracted_row  # noqa: E402


def fs_row(tn, sym, rev=1000.0, gross=300.0, url="https://codal.ir/PDF/x",
           pe="1405/06/31"):
    row = [tn, sym, sym, "صورت‌های مالی سالانه حسابرسی‌شده", "FS", 12, pe,
           "1405/07/20 10:00:00"]
    row += [rev, gross, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    row += ["میلیون ریال", url, "2026-11-03 10:00:00", 1, 0, "1404", "mrl"]
    return tuple(row)


ok, code = validate_extracted_row("fs", fs_row(1, "فولاد"))
ck(ok and code == "", "ردیفِ سالم پذیرفته می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(2, "فولاد", rev=-1))
ck(not ok and code == "negative_revenue:revenue", "درآمد منفی رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(3, "فولاد", rev=100, gross=101))
ck(not ok and code == "gross_gt_revenue", "سود ناخالص > درآمد رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(4, "فولاد", url=""))
ck(not ok and code == "missing_provenance", "بی‌منبع رد می‌شود", code)
ok, code = validate_extracted_row("fs", fs_row(5, "فولاد", pe="1406/12/29"),
                                  today=datetime.date(2026, 11, 3))
ck(not ok and code == "future_period", "دورهٔ آینده رد می‌شود", code)

c = fresh_db()
add_notice(c, 4001, "فولاد")
PL.enqueue(c, [(4001, "fs")])
out = PL.run_cycle(
    c, "test", discover=None,
    scrape=lambda n: ("fs", fs_row(4001, "فولاد", rev=-5), "ok"),
    now="2026-11-03 20:00:00", instruments=lambda conn: {})
state = c.execute("SELECT state, last_error FROM codal_extracted WHERE tracing_no=4001").fetchone()
ck(tuple(state) == ("quarantined", "negative_revenue:revenue"),
   "ردیفِ خراب قرنطینه شد و نوشته نشد", tuple(state))
rows = c.execute("SELECT COUNT(*) FROM financial_statements").fetchone()[0]
ck(rows == 0, "هیچ ردیفِ خرابی در canonical نیست", rows)
ck(out.get("quarantined") == 1, "شمارشِ چرخه قرنطینه را گزارش می‌کند", out)
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `ImportError: cannot import name 'validate_extracted_row'`.

- [ ] **Step 3: پیاده‌سازی تاریخ و گیتِ ردیفی**

**۳الف — به `codal_periods.py` اضافه کن** (کنار `canonicalize`):

```python
def _g2j(gy, gm, gd):
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = 355666 + (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) \
        + ((gy2 + 399) // 400) + gd + g_d_m[gm - 1]
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + (days // 31)
        jd = 1 + (days % 31)
    else:
        jm = 7 + ((days - 186) // 30)
        jd = 1 + ((days - 186) % 30)
    return jy, jm, jd


def _j2g(jy, jm, jd):
    jy += 1595
    days = -355668 + (365 * jy) + ((jy // 33) * 8) + (((jy % 33) + 3) // 4) + jd
    if jm < 7:
        days += (jm - 1) * 31
    else:
        days += ((jm - 7) * 30) + 186
    gy = 400 * (days // 146097)
    days %= 146097
    if days > 36524:
        days -= 1
        gy += 100 * (days // 36524)
        days %= 36524
        if days >= 365:
            days += 1
    gy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        gy += (days - 1) // 365
        days = (days - 1) % 365
    gd = days + 1
    leap = (gy % 4 == 0 and gy % 100 != 0) or (gy % 400 == 0)
    sal_a = [31, 29 if leap else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    gm = 0
    while gm < 12 and gd > sal_a[gm]:
        gd -= sal_a[gm]
        gm += 1
    return gy, gm + 1, gd


def g2j_tuple(gy, gm, gd):
    """میلادی ⇒ شمسی؛ برای مقایسهٔ دورهٔ آینده."""
    return _g2j(int(gy), int(gm), int(gd))


def j2g_date(raw):
    """'1405/06/31[ 12:10:00]' ⇒ '2026-09-22[ 12:10:00]'؛ نامعتبر ⇒ None."""
    s = str(raw or "").translate(_DIGITS)
    m = _LOOSE.search(s)
    if not m:
        return None
    jy, jm, jd = int(m.group(1)), int(m.group(2)), int(m.group(3))
    if not 1 <= jm <= 12 or not 1 <= jd <= 31:
        return None
    gy, gm, gd = _j2g(jy, jm, jd)
    out = "%04d-%02d-%02d" % (gy, gm, gd)
    tm = re.search(r"(?<!\d)(\d{1,2}):(\d{2})(?::(\d{2}))?", s)
    if tm:
        out += " %02d:%02d:%02d" % (int(tm.group(1)), int(tm.group(2)),
                                    int(tm.group(3) or 0))
    return out
```

**۳ب — `codal_row_gate.py` را بساز:**

```python
# -*- coding: utf-8 -*-
"""codal_row_gate.py — گیتِ ردیفیِ نوشتنِ افزایشی (stdlib-only، در بیلد frozen هم هست)."""
from __future__ import annotations

import datetime as _dt

import codal_periods as CP


def _to_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_extracted_row(kind, row, today=None):
    """(ok, code) — همان بررسی‌هایِ ردیفیِ staging، رویِ یک ردیفِ استخراج‌شده.

    شاخص‌ها از قراردادِ tupleِ `codal_fetcher.scrape_notice_row` می‌آیند:
    MS: 3=period_end، 6=monthly_revenue، 7=ytd_revenue، 13/14=provenance
    FS: 6=period_end، 8=revenue، 9=gross_profit، 19=url
    """
    if not row:
        return False, "empty_row"
    if kind == "ms":
        for idx, name in ((6, "monthly_revenue"), (7, "ytd_revenue")):
            v = _to_float(row[idx])
            if v is not None and v < 0:
                return False, "negative_revenue:%s" % name
        if not (str(row[13] or "").strip() or str(row[14] or "").strip()):
            return False, "missing_provenance"
        period = row[3]
    else:
        revenue = _to_float(row[8])
        gross = _to_float(row[9])
        if revenue is not None and revenue < 0:
            return False, "negative_revenue:revenue"
        if revenue is not None and gross is not None and gross > revenue:
            return False, "gross_gt_revenue"
        if not str(row[19] or "").strip():
            return False, "missing_provenance"
        period = row[6]
    parsed = CP.canonicalize(period)
    if parsed:
        jy, jm, jd = (int(x) for x in parsed.split("/"))
        day = today or _dt.date.today()
        ty, tm, td = CP.g2j_tuple(day.year, day.month, day.day)
        if (jy, jm, jd) > (ty, tm, td):
            return False, "future_period"
    return True, ""
```

- [ ] **Step 4: پیاده‌سازیِ قرنطینه در `codal_pipeline`**

1. بالای فایل:

```python
from codal_row_gate import validate_extracted_row
```

2. در `process_claimed` امضای تابع را عوض کن:

```python
def process_claimed(conn, rows, scrape, now=None, validate=None):
```

و `tally` را:

```python
tally = {"done": 0, "empty": 0, "failed": 0, "rejected": 0,
         "quarantined": 0, "symbols": set()}
```

3. بعد از `if derived is None: ... continue` و **قبل از** `if k == "ms":`:

```python
if validate:
    ok_row, code = validate(k, derived)
    if not ok_row:
        conn.execute(
            "UPDATE codal_extracted SET state='quarantined', error_kind='validation',"
            " last_error=?, updated_at=?, finished_at=?, claim_owner=NULL,"
            " claimed_at=NULL, next_attempt_at=NULL WHERE tracing_no=?",
            (str(code)[:300], now, now, int(tn)))
        conn.commit()
        tally["quarantined"] += 1
        continue
```

4. در `run_cycle` فراخوانی را عوض کن:

```python
tally = process_claimed(conn, rows, scrape or (lambda n: (None, None, "failed")),
                        now=now, validate=validate_extracted_row)
```

و بعد از `out["rejected"] += tally["rejected"]`:

```python
out["quarantined"] = int(out.get("quarantined") or 0) + tally["quarantined"]
```

5. در `counts()` مقدار پیش‌فرض را اضافه کن:

```python
out = {"queued": 0, "running": 0, "done": 0, "empty": 0, "failed": 0,
       "unresolved": 0, "quarantined": 0, "total": 0}
```

6. در `codal_fetcher.py`، `LEDGER_DONE_STATES` را عوض کن:

```python
LEDGER_DONE_STATES = ("done", "empty", "unresolved", "quarantined")
```

و `ledger_terminal_sql` را:

```python
return ("(%s IS NULL OR %s IN ('done','empty','unresolved','quarantined'))"
        % (col, col))
```

- [ ] **Step 5: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 6: رگرسیونِ discovery و scheduler**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_discovery_v1101.py
```

Expected: `0 failed` در هر دو.

- [ ] **Step 7: Commit**

```bash
git add codal_row_gate.py codal_periods.py codal_fetcher.py codal_pipeline.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(codal): گیتِ ردیفی پیش از نوشتن و قرنطینهٔ دادهٔ خراب"
```

---

### Task 5: قفلِ متقابل با خط شبانه

**Files:**
- Modify: `codal_pipeline.py` (`orchestrator_busy`، `worker_once`)
- Modify: `dev/codal_auto_update.py` (`_pipeline_lock_free`، انتظار پیش از staging)
- Test: `dev/test_codal_event_update.py` (بخش ۵)

**Interfaces:**
- Produces:
  - `orchestrator_busy(now=None, work_dir=None) -> {"busy","reason","stage"}`
  - `worker_once` خروجیِ `{"skipped":"orchestrator-busy", ...}` با wakeup ۳۰۰ثانیه‌ای.
  - `dev.codal_auto_update._pipeline_lock_free(db_path) -> bool`

- [ ] **Step 1: تستِ شکست‌خورده**

```python
# ── ۵) قفلِ متقابل با خط شبانه ───────────────────────────────────────────
section("locks: orchestrator vs incremental worker")


def write_lock(work, age_s=30):
    p = os.path.join(work, "codal_auto.lock")
    open(p, "w", encoding="utf-8").write("1 test")
    ts = datetime.datetime.now().timestamp() - age_s
    os.utime(p, (ts, ts))


work = tempfile.mkdtemp(prefix="codal_lock_", dir=TMP)
write_lock(work, age_s=30)
b = PL.orchestrator_busy(work_dir=work)
ck(b["busy"] is True and b["reason"] == "lock-fresh",
   "قفلِ تازهٔ شبانه ⇒ مشغول", b)
os.utime(os.path.join(work, "codal_auto.lock"),
         (datetime.datetime.now().timestamp() - 7 * 3600,) * 2)
b = PL.orchestrator_busy(work_dir=work)
ck(b["busy"] is False, "قفلِ کهنه‌تر از ۶ ساعت ⇒ آزاد", b)

real_busy = PL.orchestrator_busy
PL.orchestrator_busy = lambda *a, **k: {"busy": True, "reason": "lock-fresh",
                                        "stage": "fetching"}
try:
    r = PL.worker_once(conn=fresh_db(), now="2026-11-03 10:30:00",
                       network=False, busy={"busy": False, "reason": "idle"})
finally:
    PL.orchestrator_busy = real_busy
ck(r.get("skipped") == "orchestrator-busy"
   and r.get("wakeup", {}).get("seconds") == 300,
   "worker در پنجرهٔ شبانه هیچ کاری نمی‌کند", r)

import codal_auto_update as A  # noqa: E402  (مسیرِ dev از قبل در sys.path است)
db = os.path.join(TMP, "lockprobe.db")
conn = sqlite3.connect(db)
conn.execute("CREATE TABLE pipeline_lock (key TEXT PRIMARY KEY, owner TEXT,"
             " heartbeat_at TEXT, note TEXT)")
conn.execute("INSERT INTO pipeline_lock VALUES ('codal_pipeline','x',?, '')",
             (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
conn.commit()
conn.close()
ck(A._pipeline_lock_free(db) is False, "قفلِ تازهٔ pipeline ⇒ آزاد نیست")
conn = sqlite3.connect(db)
conn.execute("UPDATE pipeline_lock SET heartbeat_at=?",
             ((datetime.datetime.now() - datetime.timedelta(seconds=600))
              .strftime("%Y-%m-%d %H:%M:%S"),))
conn.commit()
conn.close()
ck(A._pipeline_lock_free(db) is True, "قفلِ کهنه (۱۰ دقیقه) ⇒ آزاد")
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `AttributeError: ... orchestrator_busy`.

- [ ] **Step 3: پیاده‌سازی در `codal_pipeline.py`**

`time` را به importهای بالای فایل اضافه کن (کنار `datetime`/`os`/`sqlite3`/`sys`).

ثابت‌ها:

```python
ORCHESTRATOR_LOCK_STALE_S = 6 * 3600
ORCHESTRATOR_TERMINAL_STAGES = frozenset({
    "done", "dry_run_ok", "paused", "locked", "client_busy",
    "backup_failed", "fetch_failed", "validation_failed", "merge_failed",
    "materialize_failed", "snapshot_failed", "sign_failed", "publish_failed",
    "failed",
})
```

تابع (نزدیک `crawler_busy`):

```python
def orchestrator_busy(now=None, work_dir=None):
    """آیا خط شبانهٔ ۱۸:۳۰ در حال اجراست؟ (فقط خواندنِ فایل، بدونِ importِ api)"""
    work = work_dir or ROOT
    lock = os.path.join(work, "codal_auto.lock")
    try:
        age = time.time() - os.path.getmtime(lock)
        if 0 <= age <= ORCHESTRATOR_LOCK_STALE_S:
            return {"busy": True, "reason": "lock-fresh", "stage": "lock"}
    except OSError:
        pass
    status_path = os.path.join(work, "codal_auto_status.json")
    try:
        with open(status_path, "r", encoding="utf-8") as fh:
            status = json.load(fh)
    except (OSError, ValueError):
        status = {}
    if not isinstance(status, dict):
        status = {}
    stage = str(status.get("stage") or "").strip().lower()
    if stage and stage not in ORCHESTRATOR_TERMINAL_STAGES:
        age_s = _age_s(status.get("updated_at") or status.get("started_at"),
                       _to_dt(now))
        if age_s is not None and -300 <= age_s <= ORCHESTRATOR_LOCK_STALE_S:
            return {"busy": True, "reason": "status-active", "stage": stage}
    return {"busy": False, "reason": "", "stage": stage}
```

`time` را import کن (اگر نیست). در `__all__` این را اضافه کن:

```python
"orchestrator_busy", "ORCHESTRATOR_LOCK_STALE_S",
```

در `worker_once`، قبل از محاسبهٔ `age_net`:

```python
orch = orchestrator_busy(_to_dt(now))
if orch["busy"]:
    return {"skipped": "orchestrator-busy", "reason": orch.get("reason", ""),
            "network": False,
            "wakeup": {"seconds": 300, "reason": "orchestrator-busy",
                       "need_network": False,
                       "at": now, "queue": counts(conn)}}
```

- [ ] **Step 4: پیاده‌سازی در `dev/codal_auto_update.py`**

ثابت:

```python
PIPELINE_LOCK_WAIT_S = 120
```

تابع (نزدیک `_acquire_lock`):

```python
def _pipeline_lock_free(db_path):
    """آیا قفلِ heartbeat-دارِ worker آزاد/کهنه است؟ خطای DB ⇒ آزاد (fail-open
    برای این گیتِ کوتاه؛ خودِ merge بعداً با قفلِ codal_auto محافظت می‌شود)."""
    try:
        uri = pathlib.Path(db_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=5)
        try:
            row = conn.execute(
                "SELECT heartbeat_at FROM pipeline_lock WHERE key='codal_pipeline'"
            ).fetchone()
        finally:
            conn.close()
    except Exception:
        return True
    if not row or not row[0]:
        return True
    try:
        hb = datetime.datetime.strptime(
            str(row[0])[:19].replace("T", " "), "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return True
    return (datetime.datetime.now() - hb).total_seconds() > 180
```

در `run`، بعد از گرفتنِ `lock` و **قبل از** `_write_status(stage="backing_up")`:

```python
_write_status(stage="pipeline_wait", mode=mode, started_at=started_at,
              last_error=None, published=False)
deadline = time.time() + PIPELINE_LOCK_WAIT_S
while not _pipeline_lock_free(main_db):
    if time.time() >= deadline:
        return _fail(result, "pipeline_busy",
                     "pipeline_lock still held after %ds" % PIPELINE_LOCK_WAIT_S)
    time.sleep(2)
```

- [ ] **Step 5: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 6: رگرسیونِ شبانه**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_auto_update_v11.py
```

Expected: همهٔ `PASS`ها. اگر سناریوی `client_busy` شکست خورد، بررسی کن که انتظارِ `pipeline_lock` پیش از `backing_up` گذاشته شده باشد.

- [ ] **Step 7: Commit**

```bash
git add codal_pipeline.py dev/codal_auto_update.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "fix(codal): قفلِ متقابل worker افزایشی و خط شبانه"
```

---

### Task 6: تازگی و منشأ per-symbol + API

**Files:**
- Modify: `api/fundamental.py` (`freshness_of`، route دسته‌ای، بلوک کارت)
- Test: `dev/test_codal_event_update.py` (بخش ۶)

**Interfaces:**
- Consumes: `codal_periods.j2g_date` (در Task 4 ساخته شد)
- Produces:
  - `api.fundamental.freshness_of(conn, symbol, now=None) -> dict`
  - `GET /api/fundamental/freshness` (پیش از `/{symbol}`)
  - کلید `freshness` در پاسخِ کارت

- [ ] **Step 1: تستِ شکست‌خورده**

```python
# ── ۶) تازگی و منشأ ───────────────────────────────────────────────────────
section("freshness: as_of / source / state")
import codal_periods as CP  # noqa: E402

ck(CP.j2g_date("1405/01/01") == "2026-03-21", "نوروز ۱۴۰۵ ⇒ 2026-03-21",
   CP.j2g_date("1405/01/01"))
ck(CP.j2g_date("1405/06/31 12:10:00") == "2026-09-22 12:10:00",
   "تاریخ+ساعت حفظ می‌شود", CP.j2g_date("1405/06/31 12:10:00"))
ck(CP.j2g_date("") is None, "تاریخ خالی ⇒ None")

from api.fundamental import freshness_of  # noqa: E402

c = fresh_db()
c.execute("INSERT INTO instruments (ins_code, l_val18, l_val30, paper_type)"
          " VALUES ('1','فولاد','فولاد مبارکه',1)")
c.execute("CREATE TABLE market_watch (ins_code TEXT, d_even INTEGER, pcl REAL,"
          " pmn REAL, pmx REAL, py REAL, pf REAL, qtj REAL, qtc REAL, ztt REAL,"
          " pc REAL, eps REAL, pe REAL, ztd REAL, h_even INTEGER,"
          " PRIMARY KEY (ins_code, d_even))")
c.execute("INSERT INTO market_watch (ins_code, d_even) VALUES ('1', 20261103)")
c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date,"
          " sent_date, fetched_at) VALUES (9100,'فولاد','گزارش فعالیت ماهانه',"
          " '1405/06/31 09:00:00','1405/06/31 09:00:00','2026-10-14 00:00:00')")
c.execute("INSERT INTO monthly_sales (tracing_no, symbol, title, period_end,"
          " year, month, monthly_revenue, ytd_revenue) VALUES"
          " (9100,'فولاد','گزارش', '1405/06/31', 1405, 6, 1000, 6000)")
c.execute("INSERT INTO codal_notices (tracing_no, symbol, title, publish_date,"
          " sent_date, fetched_at) VALUES (9200,'فولاد','صورت‌های مالی',"
          " '1405/05/10 09:00:00','1405/05/10 09:00:00','2026-10-14 00:00:00')")
c.execute("INSERT INTO financial_statements (tracing_no, symbol, title, period_end,"
          " publish_date, revenue, gross_profit, is_audited, is_consolidated)"
          " VALUES (9200,'فولاد','صورت‌ها','1404/12/29','1405/05/10 09:00:00',"
          " 1000, 300, 1, 0)")
PL.dirty_mark(c, "فولاد", "monthly_sales", reason="test")

fr = freshness_of(c, "فولاد")
ck(fr["axes"]["1_growth"]["state"] == "stale",
   "شاخص ۱ dirty ⇒ stale", fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["as_of"] == "2026-09-22 09:00:00",
   "as_of از publish_date شمسی به میلادی تبدیل شد", fr["axes"]["1_growth"])
ck(fr["axes"]["1_growth"]["source"] == "monthly_sales"
   and fr["axes"]["1_growth"]["tracing_no"] == 9100,
   "منبع و tracing_no درست است", fr["axes"]["1_growth"])
ck(fr["axes"]["2_eps_trend"]["state"] == "fresh"
   and fr["axes"]["2_eps_trend"]["period_end"] == "1404/12/29",
   "شاخص ۲ از FS حسابرسی‌شده و fresh است", fr["axes"]["2_eps_trend"])
ck(fr["axes"]["5_industry"]["as_of"] == "2026-11-03",
   "شاخص ۵ از روزِ تابلو", fr["axes"]["5_industry"])
ck(fr["as_of"] == "2026-11-03", "as_of کارت بیشینهٔ محورهاست", fr["as_of"])
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `ImportError: cannot import name 'freshness_of' from 'api.fundamental'` (تست‌های `j2g_date` چون در Task 4 اضافه شده‌اند سبز می‌شوند).

- [ ] **Step 3: تأییدِ `j2g_date` از Task 4**

`j2g_date` در Task 4 به `codal_periods.py` اضافه شده است؛ اینجا فقط حضورش را تأیید کن:

```bash
PYTHONIOENCODING=utf-8 python -c "import codal_periods as CP; assert CP.j2g_date('1405/01/01') == '2026-03-21'; print('j2g_date ok')"
```

Expected: `j2g_date ok`.

- [ ] **Step 4: پیاده‌سازی `freshness_of`**

در `api/fundamental.py`، پیش از `@router.get("/api/fundamental/freshness")` این را بگذار:

```python
def _sym_where(conn, column, symbol, domain=None):
    return fts_engine.sym_in(conn, column, symbol, domain)


def freshness_of(conn, symbol, now=None):
    """تازگیِ هر یک از ۵ محور از canonical — بدونِ جدولِ تازه.

    `as_of` تاریخِ منبع است (میلادی)، نه زمانِ اجرای برنامه. ترتیبِ وضعیت:
    quarantined > stale > missing > fresh.
    """
    ms_where, ms_params = _sym_where(conn, "ms.symbol", symbol)
    ms = conn.execute(
        "SELECT ms.tracing_no, ms.period_end, n.publish_date"
        " FROM monthly_sales ms"
        " LEFT JOIN codal_notices n ON n.tracing_no = ms.tracing_no"
        " WHERE " + ms_where + " ORDER BY " + CP.order_expr("ms")
        + ", ms.tracing_no DESC LIMIT 1", ms_params).fetchone()
    fs_where, fs_params = _sym_where(conn, "fs.symbol", symbol)
    fs = conn.execute(
        "SELECT fs.tracing_no, fs.period_end, fs.publish_date"
        " FROM financial_statements fs"
        " WHERE " + fs_where + " AND COALESCE(fs.is_audited,0)=1"
        " AND COALESCE(fs.is_consolidated,0)=0"
        " ORDER BY " + CP.order_expr("fs") + ", fs.tracing_no DESC LIMIT 1",
        fs_params).fetchone()
    board = None
    try:
        b_where, b_params = _sym_where(conn, "i.l_val18", symbol, "board")
        board = conn.execute(
            "SELECT MAX(m.d_even) FROM instruments i"
            " JOIN market_watch m ON m.ins_code = i.ins_code"
            " WHERE " + b_where, b_params).fetchone()[0]
    except sqlite3.Error:
        board = None
    variants = {symbol, fts_engine.norm_fa(symbol)}
    q = "SELECT axis FROM pipeline_dirty WHERE symbol IN (%s)" % ",".join("?" * len(variants))
    try:
        dirty = {r[0] for r in conn.execute(q, tuple(variants))}
    except sqlite3.Error:
        dirty = set()
    q_where, q_params = _sym_where(conn, "n.symbol", symbol)
    try:
        qrows = conn.execute(
            "SELECT e.kind, e.last_error FROM codal_extracted e"
            " JOIN codal_notices n ON n.tracing_no = e.tracing_no"
            " WHERE e.state='quarantined' AND " + q_where, q_params).fetchall()
    except sqlite3.Error:
        qrows = []
    q_axes = {}
    for kind, err in qrows:
        for ax in (("1_growth", "4_sales_to_mcap") if kind == "ms"
                   else ("2_eps_trend", "3_gross_margin", "1_growth",
                         "4_sales_to_mcap")):
            q_axes.setdefault(ax, err or "validation")
    board_iso = str(board) if board else None
    if board_iso and len(board_iso) == 8:
        board_iso = "%s-%s-%s" % (board_iso[:4], board_iso[4:6], board_iso[6:])
    ms_asof = CP.j2g_date(ms[2]) if ms and ms[2] else (
        CP.j2g_date(ms[1]) if ms else None)
    fs_asof = CP.j2g_date(fs[2]) if fs and fs[2] else (
        CP.j2g_date(fs[1]) if fs else None)

    def axis(name, source, as_of, tracing_no=None, period_end=None,
             present=True):
        state = "missing"
        if not present:
            state = "missing"
        elif name in dirty:
            state = "stale"
        else:
            state = "fresh"
        if name in q_axes:
            state = "quarantined"
        return {"as_of": as_of, "source": source,
                "tracing_no": tracing_no,
                "period_end": CP.canonicalize(period_end) if period_end else None,
                "state": state,
                "reason": q_axes.get(name, "")}

    axes = {
        "1_growth": axis("1_growth", "monthly_sales", ms_asof,
                         ms[0] if ms else None, ms[1] if ms else None,
                         present=bool(ms)),
        "2_eps_trend": axis("2_eps_trend", "financial_statements", fs_asof,
                            fs[0] if fs else None, fs[1] if fs else None,
                            present=bool(fs)),
        "3_gross_margin": axis("3_gross_margin", "financial_statements", fs_asof,
                               fs[0] if fs else None, fs[1] if fs else None,
                               present=bool(fs)),
        "4_sales_to_mcap": axis("4_sales_to_mcap", "monthly_sales+market_watch",
                                max([x for x in (ms_asof, board_iso) if x],
                                    default=None),
                                ms[0] if ms else None, ms[1] if ms else None,
                                present=bool(ms and board_iso)),
        "5_industry": axis("5_industry", "instruments", board_iso,
                           present=bool(board_iso)),
    }
    stamps = [a["as_of"] for a in axes.values() if a.get("as_of")]
    return {"symbol": symbol, "as_of": max(stamps) if stamps else None,
            "axes": axes}
```

- [ ] **Step 5: route و کارت**

1. **دقیقاً پیش از** `@router.get("/api/fundamental/{symbol}")` این route را بگذار (وگرنه `freshness` به‌عنوان نماد گرفته می‌شود):

```python
@router.get("/api/fundamental/freshness")
def api_fundamental_freshness(symbols: str = ""):
    """تازگیِ ۵ محور برای فهرستِ نمادها (حداکثر ۲۰۰)."""
    conn = get_db()
    try:
        syms = [s.strip() for s in symbols.split(",") if s.strip()]
        if not syms:
            syms = [r[0] for r in conn.execute(
                "SELECT l_val18 FROM instruments WHERE COALESCE(paper_type,1)=1"
                " ORDER BY l_val18 LIMIT 200").fetchall()]
        syms = syms[:200]
        return {"status": "success", "count": len(syms),
                "items": [freshness_of(conn, s) for s in syms]}
    finally:
        conn.close()
```

2. در `return {"status": "success", ...}` کارت (نزدیک `"ref_symbol": ref_symbol`) اضافه کن:

```python
"freshness": freshness_of(conn, norm_symbol),
```

- [ ] **Step 6: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 7: آزمونِ ترتیبِ route (در همان فایل تست، انتهای بخش ۶)**

```python
from api.fundamental import router as FR  # noqa: E402
paths = [r.path for r in FR.routes]
ck(paths.index("/api/fundamental/freshness") < paths.index("/api/fundamental/{symbol}"),
   "route تازگی پیش از مسیرِ پویا ثبت شده است", paths)
```

- [ ] **Step 8: Commit**

```bash
git add codal_periods.py api/fundamental.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(fundamental): تازگی و منشأ per-symbol + API"
```

---

### Task 7: نشانِ تازگی در کارت v2

**Files:**
- Modify: `frontend-v2/src/features/fundamental/api/useFtsCard.ts`
- Modify: `frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx`
- Test: `frontend-v2/src/__tests__/fundamental-summary.spec.tsx`

**Interfaces:**
- Consumes: `FtsCard.freshness` از API.
- Produces: `data-testid="fundamental-freshness"` فقط وقتی `freshness.as_of` موجود باشد.

- [ ] **Step 1: تستِ شکست‌خورده را اضافه کن**

در `frontend-v2/src/__tests__/fundamental-summary.spec.tsx`، داخل `describe('FundamentalCards')`:

```tsx
it('shows the source freshness timestamp only when the API supplies it', () => {
  serve({
    ...card,
    freshness: {
      as_of: '2026-11-03T12:10:00+03:30',
      axes: {
        '1_growth': { as_of: '2026-11-03', source: 'monthly_sales', state: 'fresh' },
        '3_gross_margin': { as_of: '2026-09-20', source: 'financial_statements', state: 'stale' },
      },
    },
  } as unknown as FtsCard);
  render(<FundamentalCards symbol="فولاد" />);
  const badge = screen.getByTestId('fundamental-freshness');
  expect(badge.textContent).toContain('تازه');
  expect(badge.getAttribute('title')).toContain('3_gross_margin');
});

it('does not invent freshness when the API omits it', () => {
  serve(card);
  render(<FundamentalCards symbol="فولاد" />);
  expect(screen.queryByTestId('fundamental-freshness')).toBeNull();
});
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
cd frontend-v2
npx vitest run src/__tests__/fundamental-summary.spec.tsx
```

Expected: FAIL — `freshness` در schema نیست و `fundamental-freshness` وجود ندارد.

- [ ] **Step 3: schema**

در `useFtsCard.ts`، بعد از `Axis5Schema`:

```ts
const FreshnessAxisSchema = z.looseObject({
  as_of: Str,
  source: Str,
  tracing_no: Num,
  period_end: Str,
  state: z.enum(['fresh', 'stale', 'missing', 'quarantined']).nullish(),
  reason: Str,
});

const FreshnessSchema = z.looseObject({
  as_of: Str,
  axes: z.record(z.string(), FreshnessAxisSchema).nullish(),
});
```

و در `FtsCardSchema` پس از `sector`:

```ts
freshness: FreshnessSchema.nullish(),
```

- [ ] **Step 4: نشان در `FundamentalCards.tsx`**

بالای `FundamentalCards` اضافه کن:

```tsx
function freshnessBadge(card: FtsCard): { text: string; title: string } | null {
  const fresh = card.freshness;
  if (!fresh?.as_of) return null;
  const date = new Date(fresh.as_of);
  const time = Number.isNaN(date.getTime())
    ? fresh.as_of
    : new Intl.DateTimeFormat('fa-IR', {
        hour: '2-digit', minute: '2-digit',
      }).format(date);
  const needsAttention = Object.entries(fresh.axes ?? {})
    .filter(([, axis]) => axis?.state && axis.state !== 'fresh')
    .map(([key, axis]) => `${key} (${axis.state})`);
  return {
    text: `تازه تا ${time}`,
    title: needsAttention.length
      ? `نیازمند توجه: ${needsAttention.join('، ')}`
      : 'همهٔ محورها از منبع تازه‌اند',
  };
}
```

و بدنهٔ `return` کامپوننت را با این diff عوض کن (دقیقاً یک wrapper بیرونی و یک badge؛ محتوای `cardFacts(...).map(...)` دست‌نخورده می‌ماند):

```diff
+  const fresh = freshnessBadge(query.data);
   return (
-    <div data-testid="fundamental-cards"
-      className="grid min-h-0 grid-cols-[repeat(auto-fit,minmax(160px,1fr))] content-start gap-1 overflow-y-auto p-1">
-      {cardFacts(query.data).map((fact) => {
+    <div className="flex min-h-0 flex-col gap-1">
+      {fresh ? (
+        <div data-testid="fundamental-freshness" title={fresh.title}
+          className="flex items-center gap-1 px-1 pt-1 t-85 text-text-3">
+          <span className="inline-block h-1.5 w-1.5 rounded-full bg-up" aria-hidden />
+          <span>{fresh.text}</span>
+        </div>
+      ) : null}
+      <div data-testid="fundamental-cards"
+        className="grid min-h-0 grid-cols-[repeat(auto-fit,minmax(160px,1fr))] content-start gap-1 overflow-y-auto p-1">
+        {cardFacts(query.data).map((fact) => {
-      })}
+        })}
+      </div>
     </div>
   );
```

- [ ] **Step 5: اجرا و سبز شدن**

```bash
cd frontend-v2
npx vitest run src/__tests__/fundamental-summary.spec.tsx
npm run typecheck
```

Expected: همهٔ تست‌ها PASS؛ `tsc -b` بدون خطا.

- [ ] **Step 6: Commit**

```bash
git add frontend-v2/src/features/fundamental/api/useFtsCard.ts \
        frontend-v2/src/features/fundamental/ui/FundamentalCards.tsx \
        frontend-v2/src/__tests__/fundamental-summary.spec.tsx
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(ui): نشان تازگیِ منبع روی کارت پنج‌محور"
```

---

### Task 8: وضعیت، بودجه و شکاف در `health`

**Files:**
- Modify: `codal_pipeline.py` (`discover_auto`، `run_cycle`، `worker_once`، `health`)
- Test: `dev/test_codal_event_update.py` (بخش ۷)

**Interfaces:**
- Produces:
  - `health()` کلیدهای `publication`، `last_new_notice_at`، `gap_flag`، `incomplete_streak`، `daily_requests`.
  - `run_cycle` کلید `pages`؛ `discover_auto` پرچم شکاف را در cursor می‌نویسد.

- [ ] **Step 1: تستِ شکست‌خورده**

```python
# ── ۷) وضعیت، پرچم شکاف و بودجهٔ روزانه ─────────────────────────────────
section("status: gap flag / daily budget / publication")
c = fresh_db()
for i in range(240):
    add_notice(c, 5000 + i, "نماد%d" % i,
               pub="1405/07/20 %02d:10:00" % (9 + (i % 3)))
h = PL.health(c)
ck("publication" in h and "network_gap_s" in h["publication"],
   "health پنجره و gap را گزارش می‌کند", h.get("publication"))
ck("daily_requests" in h and "gap_flag" in h
   and "incomplete_streak" in h and "last_new_notice_at" in h,
   "کلیدهای تازهٔ status حاضرند", sorted(h.keys()))

c2 = fresh_db()
blocked = PL.discover_auto(c2, fetch=lambda *a, **k: None,
                           now="2026-11-03 20:00:00")
ck(blocked.get("complete") is False and blocked.get("blocked") is True,
   "فیدِ بی‌پاسخ ⇒ پاسِ ناقص/بلاک اعلام می‌شود", blocked)
ck(PL.cursor_get(c2, "notice_gap_flag") == "1",
   "پاسِ ناقص ⇒ پرچم شکاف روشن")
ck(int(PL.cursor_get(c2, "notice_incomplete_streak", "0") or 0) >= 1,
   "شمارندهٔ شکافِ پیاپی افزایش یافت")

c3 = fresh_db()
real_disc = PL.discover_auto
PL.discover_auto = lambda *a, **k: {"found": 0, "enqueued": 0, "items": [],
                                    "floors": {}, "complete": True,
                                    "blocked": False, "pages": 2}
try:
    out = PL.run_cycle(c3, "test", discover=PL.discover_auto,
                       scrape=lambda n: (None, None, "empty"),
                       now="2026-11-03 20:00:00", instruments=lambda conn: {})
finally:
    PL.discover_auto = real_disc
ck(out.get("pages") == 2, "run_cycle تعداد صفحه‌های فید را گزارش می‌کند", out)
```

- [ ] **Step 2: اجرا و دیدن شکست**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: `KeyError`/`None` برای کلیدهای تازه.

- [ ] **Step 3: پیاده‌سازی**

1. در `discover_auto`، بعد از `res.setdefault("found", 0)`:

```python
if res.get("complete", True) and not res.get("blocked"):
    cursor_set(conn, "notice_gap_flag", "0", note="discovery complete")
    cursor_set(conn, "notice_incomplete_streak", "0", note="discovery complete")
else:
    cursor_set(conn, "notice_gap_flag", "1", note="discovery incomplete")
    try:
        streak = int(cursor_get(conn, "notice_incomplete_streak", "0") or 0) + 1
    except (TypeError, ValueError):
        streak = 1
    cursor_set(conn, "notice_incomplete_streak", str(streak),
               note="discovery incomplete")
```

2. در `run_cycle`، بعد از `out["found"]`:

```python
out["pages"] = int(found.get("pages") or 0)
```

3. در `worker_once`، پیش از `want`، بودجه را بخوان:

```python
day = str(now)[:10]
try:
    req = json.loads(cursor_get(conn, DAILY_REQUEST_CURSOR) or "{}")
except (TypeError, ValueError, sqlite3.Error):
    req = {}
if not isinstance(req, dict) or req.get("day") != day:
    req = {"day": day, "count": 0}
budget_left = DAILY_REQUEST_CAP - int(req.get("count") or 0)
```

و بعد از `use_network = want if network is None else bool(network)`:

```python
if budget_left <= 0:
    use_network = False
```

و بعد از `res["network"] = use_network` و وقتی `use_network`:

```python
used = int(res.get("pages") or 0) or 1
req["count"] = int(req.get("count") or 0) + used
try:
    cursor_set(conn, DAILY_REQUEST_CURSOR, json.dumps(req),
               note="pages=%d" % used)
except sqlite3.Error:
    pass
res["daily_requests"] = req
```

4. در `health()`، قبل از `return`:

```python
try:
    gap, pub = current_network_gap(conn, now=None, jitter=False)
except Exception:
    gap, pub = SLOW_GAP_S, {"windows": [list(w) for w in CAD.DEFAULT_WINDOWS],
                            "source": "default", "samples": 0,
                            "labels": CAD.window_labels(CAD.DEFAULT_WINDOWS),
                            "inside_window": False, "network_gap_s": SLOW_GAP_S,
                            "enabled": False}
try:
    req = json.loads(cursor_get(conn, DAILY_REQUEST_CURSOR) or "{}")
except (TypeError, ValueError, sqlite3.Error):
    req = {}
if not isinstance(req, dict):
    req = {}
```

و در dict بازگشتی `health` اضافه کن:

```python
"publication": pub,
"last_new_notice_at": _scalar("SELECT MAX(fetched_at) FROM codal_notices"),
"gap_flag": cursor_get(conn, "notice_gap_flag") == "1",
"incomplete_streak": int(cursor_get(conn, "notice_incomplete_streak", "0") or 0),
"daily_requests": {"day": req.get("day"), "count": int(req.get("count") or 0)},
```

- [ ] **Step 4: اجرا و سبز شدن**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
```

Expected: همهٔ `PASS`ها؛ exit 0.

- [ ] **Step 5: رگرسیونِ status موجود**

```bash
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
```

Expected: `0 failed`.

- [ ] **Step 6: Commit**

```bash
git add codal_pipeline.py dev/test_codal_event_update.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "feat(codal): status تازگی، پرچم شکاف و بودجهٔ روزانه"
```

---

### Task 9: ثبت در سوئیت، رگرسیون کامل و گیتِ زندهٔ opt-in

**Files:**
- Modify: `dev/run_all_tests.py` (لیست `SUITES`، نزدیک `dev/test_codal_auto_update_v11.py`)
- Test: همان گاردها

**Interfaces:**
- Consumes: همهٔ Taskهای قبل
- Produces: گارد جدید در سوئیت؛ گزارشِ نهایی.

- [ ] **Step 1: ثبت گارد**

در `dev/run_all_tests.py`، بعد از سطر `('dev/test_codal_auto_update_v11.py', ...)` اضافه کن:

```python
    ('dev/test_codal_event_update.py',
                                     'codal event-driven 5-axis: cadence, invalidate, quarantine, locks, freshness'),
```

- [ ] **Step 2: اجرای گاردهای کدال**

```bash
cd "D:/BorsTerminal-worktrees/4axes-main-integration"
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_event_update.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_scheduler_v1103.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/test_codal_auto_update_v11.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_discovery_v1101.py
PYTHONIOENCODING=utf-8 BORS_CODAL_OFFLINE=1 python dev/codal_incremental_recalc_v1104.py
```

Expected: هر پنج فرمان exit 0 و صفر `FAIL`.

- [ ] **Step 3: اجرای تست‌های فرانت**

```bash
cd frontend-v2
npx vitest run src/__tests__/fundamental-summary.spec.tsx
npm run typecheck
```

Expected: PASS و tsc بدون خطا.

- [ ] **Step 4: گیتِ زندهٔ اختیاری (فقط با تأیید مالک)**

این گام بخشی از CI نیست و نباید در حالتِ پیش‌فرض اجرا شود. در ابتدای `dev/test_codal_event_update.py`، سطرِ `os.environ["BORS_CODAL_OFFLINE"] = "1"` را با این عوض کن:

```python
LIVE = "--live" in sys.argv
if not LIVE:
    os.environ["BORS_CODAL_OFFLINE"] = "1"
```

و در **انتهای** فایل، پیش از summary، این بلوک را بگذار:

```python
if LIVE:
    section("live: read-only CODAL page (no writes)")
    try:
        sess = CF.make_session()
        try:
            letters = CF.fetch_page(sess, 1, CF.feed_query("3", 1, "1405/01/01"))
        finally:
            sess.close()
    except Exception as exc:
        print("  SKIP live probe: %s" % exc)
    else:
        if letters is None:
            print("  SKIP live probe: blocked/no response")
        else:
            ck(isinstance(letters, list) and len(letters) > 0,
               "فید کدال یک صفحهٔ غیرخالی برگرداند (بی‌نوشتن)")
```

اجرا (فقط با اجازهٔ صریح مالک):

```bash
PYTHONIOENCODING=utf-8 python dev/test_codal_event_update.py --live
```

اگر شبکه/کدال در دسترس نبود، گیتِ زنده `SKIP` می‌شود، نه PASS جعلی. این پروب هیچ نوشتنی در `market.db` ندارد.

- [ ] **Step 5: summary و exit code**

در انتهای فایل تست (بعد از بلوکِ زنده) اضافه کن:

```python
failed = CHECKS.count(False)
print("\n%d passed / %d failed" % (CHECKS.count(True), failed))
try:
    shutil.rmtree(TMP, ignore_errors=True)
except Exception:
    pass
sys.exit(1 if failed else 0)
```

- [ ] **Step 6: گزارش و Commit**

```bash
git add dev/run_all_tests.py
git -c user.name="johnwarchief" -c user.email="johnwarchief@users.noreply.github.com" commit -m "test(codal): گارد رویدادمحور در سوئیت + گیت زندهٔ opt-in"
```

---

## Self-Review

- **پوشش spec:**
  - کادنس تطبیقی ≤۱۵ دقیقه → Task 1/2.
  - باطل‌سازی فوری در بازار → Task 3.
  - گیت ردیفی و قرنطینه → Task 4.
  - قفل متقابل شبانه → Task 5.
  - `as_of`/منبع/وضعیت per-symbol + نشان کارت → Task 6/7.
  - پرچم شکاف/بودجه/status → Task 8.
  - عرضه/آزمون/گیت زنده → Task 9.
- **بدون placeholder:** همهٔ گام‌ها کد/فرمان/انتظارِ مشخص دارند.
- **سازگاری نام‌ها:** `publication_windows`، `current_network_gap`، `orchestrator_busy`، `validate_extracted_row`، `freshness_of`، `j2g_date` در همهٔ تسک‌ها یکسان‌اند.
- **انحرافِ آگاهانه از spec:** `health().freshness` به‌صورت شمارشِ کاملِ fresh/stale/missing/quarantined پیاده نشد؛ در فاز ۱ شمارنده‌های دقیقِ `queue.quarantined`، `gap_flag` و `publication` می‌آیند و وضعیت per-symbol از `freshness_of` خوانده می‌شود. دلیل: جلوگیری از کوئریِ N+1 روی ۱۵۰۰ نماد و از ادعای شمارشِ تقریبی. اگر مالک شمارشِ تجمیعیِ دقیق بخواهد، تسکِ جدا لازم است.
- **انحرافِ آگاهانه از spec:** اولویت‌دهی watchlist در فاز ۲ است؛ صفِ موجود canonical می‌ماند.
