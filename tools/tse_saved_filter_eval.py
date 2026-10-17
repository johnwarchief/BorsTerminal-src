"""ارجح‌سنجِ رفتارِ اجراییِ فیلترِ ذخیره‌شدۀ TSETMC (مبنایِ تطبیق).

سایت هر ردیف را این‌جا می‌سنجد (cscriptExecFilter درِ `main.*.js` و همان منطق درِ
دیدۀبانِ پیشرفته):

    try { FilterResult = eval(mw.PrepareFilterCode(raw)) } catch { FilterResult = false }

سه پیامدِ که این ابزار عیناً بازتولید می‌کند:
  ۱) `raw` چندخطی است و `eval` **همۀ** خطوط را اجرا می‌کند؛ مقدارِ خطِ آخر
     برمی‌گردد، ولی اگر خطِ اول (`[ih][0..29]`) یا خطِ دوم (`[is5]`) استثنا بدهد،
     ردیف بیرون می‌افتد — حتی وقتی خطِ آخر درست می‌خواند.
  ۲) `[ih][k]`ِ غایب درِ JS `undefined` است و `.QTotTran5J` روی آن TypeError
     می‌دهد ⇒ «رد»، نه «صفر».
  ۳) `[isN]`ِ غایب هم `undefined` است؛ درِ `(tvol) > 1.5*[is6]` نتیجه NaN ⇒ false.

منبعِ داده، همان سه باندِ خودِ سایت است (نه بازسازیِ محلی):
  old.tsetmc.com/tsev2/data/ClosingPriceAll.aspx    → [ih]  (اسلات ۰..۵۹)
  old.tsetmc.com/tsev2/data/InstValue.aspx?t=a      → [isN]
  api/ClientType/GetClientTypeAll + GetMarketWatch  → (ct) و ستون‌هایِ ردیف

استفاده:
  PYTHONIOENCODING=utf-8 python tools/tse_saved_filter_eval.py            # هفت فایل
  PYTHONIOENCODING=utf-8 python tools/tse_saved_filter_eval.py --check     # با فهرستِ مرجع
"""
import argparse
import io
import json
import math
import os
import re
import sys
import urllib.request

sys.stdout.reconfigure(encoding="utf-8")

BASE = "https://cdn.tsetmc.com/api"
OLD_DATA = "https://old.tsetmc.com/tsev2/data/"
HDRS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Referer": "https://tsetmc.com/", "Origin": "https://tsetmc.com",
        "Accept": "application/json, text/plain, */*"}
FILTER_FILES = {
    "clock": "الگوی ساعت.txt",
    "roobi": "کف روبی صف فروش.txt",
    "susp": "حجم مشکوک.txt",
    "noqteh": "نقطه زنی.txt",
    "jet": "فیلتر جت.txt",
    "smart": "ورود پول هوشمند.txt",
    "legal": "ورود پول هوشمند و کد به کد حقوقی به حقیقی.txt",
}
IH_FIELDS = ("PClosing", "PDrCotVal", "ZTotTran", "QTotTran5J", "QTotCap",
             "PriceMin", "PriceMax", "PriceYesterday", "PriceFirst")


def jget(url, timeout=120):
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8", "replace"))


def cached_text(url, path):
    if os.path.exists(path):
        return io.open(path, encoding="utf-8", errors="replace").read()
    req = urllib.request.Request(url, headers=HDRS)
    with urllib.request.urlopen(req, timeout=180) as r:
        raw = r.read()
    if raw[:2] == b"\x1f\x8b":
        import gzip
        raw = gzip.decompress(raw)
    txt = raw.decode("utf-8", "replace")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(txt)
    return txt


def parse_inst_value(txt):
    out, cur = {}, ""
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 3:
            cur = c[0]
            out.setdefault(cur, {})[c[1]] = float(c[2])
        elif len(c) == 2 and cur:
            out.setdefault(cur, {})[c[0]] = float(c[1])
    return out


def parse_closing_all(txt):
    out, cur = {}, ""
    for row in txt.split(";"):
        if not row:
            continue
        c = row.split(",")
        if len(c) == 11:
            cur, slot, vals = c[0], int(float(c[1])), c[2:]
        elif len(c) == 10:
            slot, vals = int(float(c[0])), c[1:]
        else:
            continue
        out.setdefault(cur, {})[slot] = dict(zip(IH_FIELDS, [float(v) for v in vals]))
    return out


class Missing(Exception):
    """استثنایِ عینِ JS: عضوِ غایبِ آرایه ⇒ TypeError ⇒ ردیف بیرون می‌افتد."""


def js_div(a, b):
    """`a/b` درِ JS: صفر‌بر‌صفر NaN است، نه استثنا."""
    if b == 0:
        return float("nan")
    return a / b


def js_truthy(v):
    return bool(v) and not (isinstance(v, float) and math.isnan(v))


class Row:
    """محیطِ evalِ ردیف: (field)، [ih][k]، [isN]، (ct)."""

    def __init__(self, r, hist, inst, ct):
        self.r = r
        self.ih = hist or {}
        self.is_ = inst or {}
        self.ct = ct or {}

    def fld(self, name):
        v = self.r.get(name)
        if v is None or v == "":
            return 0.0
        try:
            return float(v)
        except ValueError:
            return v

    def ihv(self, k, field):
        rec = self.ih.get(k)
        if rec is None:
            raise Missing(f"[ih][{k}]")
        return rec.get(field) or 0.0

    def isv(self, key):
        if key not in self.is_:
            raise Missing(f"[is{key}]")
        return self.is_[key]

    def ctv(self, attr):
        # سایت برایِ ردیفِ بی‌ClientType صفر می‌گذارد (mw.ClientType[inscode] || 0-field)
        return float(self.ct.get(attr) or 0.0)


def translate(raw):
    """`PrepareFilterCode`ِ سایت: توکن‌ها را به فراخوانِ محیطِ بالا بدل می‌کند."""
    env = {"_f": "R.fld('{n}')", "_ih": "R.ihv({k},'{f}')", "_is": "R.isv('{k}')",
           "_ct": "R.ctv('{a}')"}
    code = raw
    code = re.sub(r"\[ih\]\[(\d+)\]\.(\w+)", lambda m: f"R.ihv({m.group(1)},'{m.group(2)}')", code)
    code = re.sub(r"\[is(\d+)\]", lambda m: f"R.isv('{m.group(1)}')", code)
    code = re.sub(r"\(\s*ct\s*\)\.(\w+)", lambda m: f"R.ctv('{m.group(1)}')", code)
    code = re.sub(r"\(\s*(l18|l30|cfield\d)\s*\)", lambda m: f"str(R.fld('{m.group(1)}'))", code)
    code = re.sub(r"\(\s*(tno|tvol|tval|predtran|buyop|z|bvol|cs)\s*\)",
                  lambda m: f"float(R.fld('{m.group(1)}'))", code)
    code = re.sub(r"\(\s*(pl|pc|py|pf|pmin|pmax|plc|plp|pcp|eps|pe|mv|tmin|tmax)\s*\)",
                  lambda m: f"float(R.fld('{m.group(1)}'))", code)
    code = re.sub(r"\(\s*(p[dzqo][1-5])\s*\)", lambda m: f"float(R.fld('{m.group(1)}'))", code)
    code = code.replace("\r", "\n")
    return code


def eval_filter(raw, row):
    """ارزشِ خطِ آخر، با منطقِ try/catch سایت روی همۀ خطوط."""
    lines = [ln for ln in translate(raw).split("\n") if ln.strip()]
    val = False
    for ln in lines:
        try:
            val = eval(ln, {"__builtins__": {}}, {"R": row, "str": str, "float": float,
                                                  "parseInt": lambda x: float(x),
                                                  "round": round, "abs": abs,
                                                  "isnan": lambda x: x != x})
        except Missing:
            return False, "throw:" + ""
        except ZeroDivisionError:
            return False, "zerodiv"
        except Exception as e:                      # noqa: BLE001 - عینِ catch سایت
            return False, type(e).__name__
    return js_truthy(val), None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="_audit/tse_saved_filter_eval.json")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ref", default="_audit/tse_saved_filter_runs_14050719.json")
    a = ap.parse_args()

    hist = parse_closing_all(cached_text(OLD_DATA + "ClosingPriceAll.aspx",
                                         "_audit/tse_cache_ClosingPriceAll.txt"))
    inst = parse_inst_value(cached_text(OLD_DATA + "InstValue.aspx?t=a",
                                        "_audit/tse_cache_InstValue.txt"))
    mw = jget(f"{BASE}/ClientType/GetClientTypeAll").get("clientTypeAllDto") or []
    ct_all = {str(x.get("insCode")): x for x in mw}
    rows = jget(("%s/ClosingPrice/GetMarketWatch?market=0&%s&showTraded=false"
                 "&withBestLimits=true&hEven=0") % (
        BASE, "&".join(f"paperTypes[{i}]={i+1}" for i in range(9)))).get("marketwatch") or []

    src = {}
    for key, fn in FILTER_FILES.items():
        p = os.path.join("docs", fn)
        src[key] = io.open(p, encoding="utf-8").read()

    res = {k: set() for k in FILTER_FILES}
    errors = {k: 0 for k in FILTER_FILES}
    for r in rows:
        code = str(r.get("insCode"))
        if not code:
            continue
        mapped = {"inscode": code, "l18": r.get("lVal18"), "l30": r.get("lVal30"),
                  "tvol": r.get("qTotTran5J"), "tno": r.get("zTotTran"),
                  "tval": r.get("qTotCap"), "pc": r.get("pClosing"), "pl": r.get("pLast"),
                  "py": r.get("pYesterday"), "pmin": r.get("priceMin"), "pmax": r.get("priceMax"),
                  "plp": r.get("pGrPerc"), "pcp": r.get("pcpGrPerc"), "z": r.get("zTitad"),
                  "tmin": r.get("minWeeklyPrice"), "tmax": r.get("maxWeeklyPrice"),
                  "bvol": r.get("baseVol")}
        book = r.get("orderBook") or [{}]
        b = book[0] if book and isinstance(book[0], dict) else {}
        mapped.update({"pd1": b.get("buyPrice"), "qd1": b.get("buyVol"), "zd1": b.get("buyTran"),
                       "po1": b.get("sellPrice"), "qo1": b.get("sellVol"), "zo1": b.get("sellTran")})
        row = Row(mapped, hist.get(code), inst.get(code), ct_all.get(code))
        for key, raw in src.items():
            ok, err = eval_filter(raw, row)
            if ok:
                res[key].add(code)
            if err:
                errors[key] += 1

    out = {"rows": len(rows), "hist_codes": len(hist), "inst_codes": len(inst),
           "ct_codes": len(ct_all),
           "counts": {k: len(v) for k, v in res.items()},
           "throw_rows": errors,
           "codes": {k: " ".join(sorted(v)) for k, v in res.items()}}
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with io.open(a.out, "w", encoding="utf-8", newline="") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)

    print("rows:", len(rows))
    print("counts:", json.dumps(out["counts"]))
    print("throws:", json.dumps(errors))
    if a.check and os.path.exists(a.ref):
        ref = json.load(io.open(a.ref, encoding="utf-8"))
        site = ref.get("site_results") or {}
        name = {"clock": "f0_clock", "roobi": "f1_roobi", "susp": "f2_susp",
                "noqteh": "f3_noqteh", "jet": "f4_jet", "smart": "f5_smart",
                "legal": "f6_legal"}
        print("\n== خودسنجی در برابرِ فهرستِ مرجع (اجرایِ واقعیِ سایت درِ نشستِ مالک)")
        for k, key in name.items():
            want = set((site.get(key) or {}).get("codes", "").split())
            got = res[k]
            print(f"   {k:6s} مرجع={len(want):4d} بازتولید={len(got):4d} "
                  f"مش chung={len(want & got):4d} فقط‌مرجع={len(want - got):3d} "
                  f"فقط‌این={len(got - want):3d}")
    print("wrote", a.out)


if __name__ == "__main__":
    main()
