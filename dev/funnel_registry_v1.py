# -*- coding: utf-8 -*-
"""dev/funnel_registry_v1.py — گاردِ رجیستریِ فیلترهایِ قیف FTS

چه چیزی را می‌گیرد: `funnel_registry.py` ادعا می‌کند هر عددش از یک فایلِ
منبعِ مالک آمده و هر فیلترش درِ بک‌اند پیاده است. این ادعا بدونِ گارد، با
زمان فاسد می‌شود — یک عدد درِ `tape_flags` عوض می‌شود و منبعِ همان سطر
درِ رجیستری حرفِ دیگری می‌زند، یا یک فایلِ فیلترِ تازه به `docs/` اضافه
می‌شود و هیچ‌وقت درِ قیف جا نمی‌گیرد (همان چیزی که بر سرِ دو فایلِ «ورود
پول هوشمند» آمد).

پنج چیز سنجیده می‌شود:
  ۱) هر `docs/*.txt` درِ رجیستری هست و برعکس؛
  ۲) sha256ِ پین‌شده با فایلِ رویِ دیسک می‌خواند (منبع عوض شد ⇒ گارد قرمز)؛
  ۳) هر `backend_impl` واقعاً import و callable است؛
  ۴) هر عددِ پارامتر درِ متنِ فایلِ ارجاع‌داده‌شده پیدا می‌شود (با نرمال‌سازی
     دلتا: ۰٫۰۲ ← `1.02`، و قدرمطلق برایِ کرانِ منفی)؛
  ۵) نسخهٔ ruleset با یک تغییرِ عدد عوض می‌شود و بی‌تغییری ثابت می‌ماند
     (کنترلِ منفی: سنسور باید خودش را ببیند).
"""
from __future__ import annotations

import glob
import hashlib
import importlib
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import funnel_registry as R  # noqa: E402

FAILED: list[str] = []


def ck(cond: bool, msg: str) -> None:
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILED.append(msg)


def sha12(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


def numbers_in(text: str) -> set[float]:
    out: set[float] = set()
    for m in re.finditer(r"\d+(?:\.\d+)?", text):
        try:
            out.add(float(m.group()))
        except ValueError:
            pass
    return out


def appears_in(value: float, tokens: set[float]) -> bool:
    """عدد درِ منبع هست؟ دلتاهایِ ضربی و کرانِ منفی هم پذیرفته می‌شوند."""
    cands = {value, abs(value), 1.0 + value, 1.0 - abs(value)}
    return any(abs(c - t) < 1e-9 for c in cands for t in tokens)


# ── ۱ و ۲) پوششِ فایل‌ها و اثرِ انگشتی ─────────────────────────────────────
txt_files = sorted(glob.glob(os.path.join(REPO, "docs", "*.txt")))
txt_names = {os.path.basename(p) for p in txt_files}
reg_names = {os.path.basename(f.source_file) for f in R.FILTERS}
ck(bool(txt_names), f"{len(txt_names)} فایلِ فیلتر درِ docs/ پیدا شد")
ck(reg_names <= txt_names, "هر فایلِ ارجاع‌داده‌شده درِ docs/ واقعاً هست")
ck(txt_names == reg_names,
   f"همۀ فایل‌هایِ docs/*.txt درِ رجیستری‌اند (رجیسترشده {len(reg_names)} از {len(txt_names)})")
missing = sorted(txt_names - reg_names)
if missing:
    print("        بی‌جایگاه:", ", ".join(missing))

for f in R.FILTERS:
    path = os.path.join(REPO, f.source_file)
    if not os.path.exists(path):
        ck(False, f"منبعِ {f.filter_id} رویِ دیسک نیست: {f.source_file}")
        continue
    ck(sha12(path) == f.source_sha256,
       f"sha256ِ {f.filter_id} با فایلِ منبع می‌خواند ({f.source_sha256})")

# ── ۳) backend_impl زنده است ──────────────────────────────────────────────
for f in R.FILTERS:
    mod_name, _, attr = f.backend_impl.rpartition(".")
    try:
        fn = getattr(importlib.import_module(mod_name), attr)
    except Exception as e:  # noqa: BLE001 — پیامِ خطا خودش شاهد است
        ck(False, f"{f.filter_id}: {f.backend_impl} قابلِ import نیست → {e}")
        continue
    ck(callable(fn), f"{f.filter_id} درِ {f.backend_impl} قابلِ فراخوانی است")

# ── ۴) هر عدد درِ منبعش ───────────────────────────────────────────────────
for f in R.FILTERS:
    src_path = os.path.join(REPO, f.source_file)
    if not os.path.exists(src_path):
        continue
    tokens = numbers_in(open(src_path, encoding="utf-8").read())
    for p in f.params:
        if p.value is None:
            continue
        cited = p.source.split(":")[0].strip("` ")
        if not cited.startswith("docs/"):
            continue
        cited_path = os.path.join(REPO, cited)
        if os.path.exists(cited_path):
            tokens |= numbers_in(open(cited_path, encoding="utf-8").read())
        ck(appears_in(p.value, tokens),
           f"{f.filter_id}.{p.param_id} = {p.value} درِ متنِ {os.path.basename(cited)} پیدا شد")

# ── ۵) presetها ───────────────────────────────────────────────────────────
ids = set(R.filter_ids())
for p in R.PRESETS:
    ck(set(p.chain) <= ids, f"زنجیرۀ {p.preset_id} فقط فیلترِ رجیستری دارد")
ck(R.PRESET_BY_ID["hourglass"].chain == (),
   "ساعت‌شنی فیلترِ تابلوییِ بی‌منبع ندارد (زنجیره تهی، منتظرِ رأیِ مالک)")
ck(R.PRESET_BY_ID["hourglass"].status == "unverified",
   "ساعت‌شنی صریح unverified برچسب خورده است")
ck(R.PRESET_BY_ID["swing"].chain == ("f_clock", "f_jet", "f_susp"),
   "نوسان‌گیر همان چیدمانِ چارت ۳ است")
ck(R.PRESET_BY_ID["trend"].chain == ("f_roobi", "f_noqteh"),
   "روندگیر کف‌روبی + نقطه‌زنی است و حجم مشکوک ندارد")
ck("f_smart" in ids and "f_legal" in ids,
   "دو فیلترِ پولِ هوشمند/کد‌به‌کد از چیپِ تابلو به رجیستریِ قیف رسیده‌اند")

# ── ۶) نسخهٔ ruleset: کنترلِ منفی ────────────────────────────────────────
v0 = R.RULESET_VERSION
ck(v0 == R._fingerprint(), f"ruleset_version پایدار است ({v0})")
import tape_flags as TF  # noqa: E402
_orig = TF.CLOCK_DELTA
try:
    TF.CLOCK_DELTA = _orig + 0.001
    importlib.reload(R)
    ck(R.RULESET_VERSION != v0,
       "کنترلِ منفی: با تکانِ یک آستانه، ruleset_version عوض می‌شود")
finally:
    TF.CLOCK_DELTA = _orig
    importlib.reload(R)
ck(R.RULESET_VERSION == v0, "کنترلِ منفی برگشت و نسخه به عددِ اولش برگشت")

print()
if FAILED:
    print(f"funnel_registry guard: {len(FAILED)} FAILED")
    sys.exit(1)
print(f"funnel_registry guard OK — {len(R.FILTERS)} فیلتر، "
      f"{sum(len(f.params) for f in R.FILTERS)} پارامتر، ruleset {v0}")
