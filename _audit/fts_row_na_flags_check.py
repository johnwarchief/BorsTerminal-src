# -*- coding: utf-8 -*-
"""_audit/fts_row_na_flags_check.py — پرچم‌هایِ تازهٔ ردیف در برابرِ خودِ کارت

سه کلید که درِ همین دور به ردیفِ `/api/screener` اضافه شد
(`i1b_applicable`, `i3_na`, `i4_na`) باید **همان چیزی را بگویند که کارتِ همان
نماد می‌گوید** — وگرنه فقط یک منبعِ دومِ حدس ساخته‌ایم، نه همگامی.
هر پرچم با `indicators` کارت مقابله می‌شود و شمارشِ واگرایی چاپ می‌گردد؛
نمونۀ برگزیدہ: هر نماد، با گامِ ثابت (بی‌۸۷۳ درخواستِ بی‌فایده).

نکتۀ پوشش: اگر کارتی پرچم را نداشت (مثلاً `volume` تهی) آن ردیف در شمارشِ
«بی‌حكم» می‌نشیند، نه در شمارشِ «موافق» — سنجشی که نتواند رد بگوید بی‌اعتبار است.
"""
import json
import sys
import urllib.parse
import urllib.request

APP = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8003").rstrip("/")
STEP = int(sys.argv[2]) if len(sys.argv) > 2 else 7


def get(path):
    with urllib.request.urlopen(APP + path, timeout=180) as r:
        return json.load(r)


def main():
    rows = get("/api/screener?limit=20000")["data"]
    picked = rows[::STEP]
    print(f"ردیف‌ها: {len(rows)}، نمونه: {len(picked)} (هر {STEP})")
    agree = {k: 0 for k in ("i1b_applicable", "i3_na", "i4_na")}
    bad = {k: [] for k in agree}
    unknown = {k: 0 for k in agree}
    for r in picked:
        try:
            c = get("/api/fundamental/" + urllib.parse.quote(r["symbol"]))
        except Exception as e:
            print("  card failed:", r["symbol"], str(e)[:60])
            continue
        cd = c.get("data") or c
        ind = cd.get("indicators") or {}
        vol = (ind.get("1") or {}).get("volume") or {}
        g3 = ind.get("3") or {}
        v4 = ind.get("4") or {}
        want = {
            "i1b_applicable": vol.get("applicable") if "applicable" in vol else None,
            "i3_na": g3.get("na") if ("na" in g3 or g3.get("band") is not None) else None,
            "i4_na": v4.get("na") if ("na" in v4 or "exempt" in v4) else None,
        }
        for k, w in want.items():
            if w is None:
                unknown[k] += 1
                continue
            w = bool(w) or (k == "i3_na" and g3.get("band") == "not_applicable")
            if bool(r.get(k)) == w:
                agree[k] += 1
            else:
                bad[k].append((r["symbol"], r.get(k), w))
    n = len(picked) - sum(unknown.values())
    print(f"\nموافق/معادلِ کارت (نمونۀ دارایِ حکم):")
    for k in agree:
        tot = agree[k] + len(bad[k])
        print(f"   {k:16s} موافق={agree[k]:4d}/{tot:4d}  واگرا={len(bad[k]):3d}  "
              f"بی‌حکمِ کارت={unknown[k]:3d}   نمونهٔ واگرایی: {bad[k][:4]}")
    dist = {k: sum(1 for r in rows if r.get(k) is True) for k in agree}
    print(f"\nتوزیع درِ کلِ {len(rows)} ردیف: " +
          "  ".join(f"{k}={v}" for k, v in dist.items()))
    json.dump({"sampled": len(picked), "agree": agree,
               "bad": {k: v[:60] for k, v in bad.items()}, "unknown": unknown,
               "distribution": dist},
              open("_audit/fts_row_na_flags_check.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("wrote _audit/fts_row_na_flags_check.json")
    return 1 if any(bad.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
