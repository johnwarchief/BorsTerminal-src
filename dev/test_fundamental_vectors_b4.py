#!/usr/bin/env python
"""گاردِ تازگیِ وکتورهایِ لایه‌ایِ بنیادی — `dev/run_all_tests.py`.

وکتورهایِ `backend-go/internal/fundamental/testdata/vectors/*.json` داورِ fan-outِ
کارتِ پنج‌محورند: هر شاخه باید خروجی‌اش با آن‌ها بخورد. اگر همین فایل‌ها دستی
ویرایش شوند، داوری بی‌صدا خریدنی می‌شود — پس اینجا دوباره از خودِ پایتون
تولید و بایت‌به‌بایت مقایسه می‌شود.

سه سنجه:
  ۱) تولیدِ تازه == فایلِ کامیت‌شده (هر دو اسکریپتِ اوراکل)؛
  ۲) هیچ فایلِ وکتوری درِ پوشه دستی‌نویس نمانده (فهرستِ صریحِ مجاز)؛
  ۳) کنترلِ منفی: یکِ عددِ داخلِ یکِ وکتور را عوض کن ⇒ سنجهٔ ۱ باید قرمز شود،
     وگرنه خودِ این گارد کور است.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
VEC = os.path.join(ROOT, "backend-go", "internal", "fundamental", "testdata", "vectors")
GENS = ("tools/parity/gen_fundamental_vectors.py",
        "tools/parity/gen_fundamental_layer_vectors.py")
ALLOWED = {"thresholds.json", "config.json", "series.json", "profile.json",
           "entity.json", "sector.json", "statements.json", "indicators.json",
           "annualize.json", "valuation.json", "text.json"}

PASS = FAIL = 0


def check(name, ok, detail=""):
    global PASS, FAIL
    if ok:
        PASS += 1
        print("  PASS %s%s" % (name, (" — " + detail) if detail else ""))
    else:
        FAIL += 1
        print("  FAIL %s%s" % (name, (" — " + detail) if detail else ""))


def regenerate(outdir):
    env = dict(os.environ, BORS_CODAL_OFFLINE="1", BORS_CODAL_AUTO="0",
               BORS_NO_FETCH_LOOPS="1", PYTHONIOENCODING="utf-8")
    for gen in GENS:
        r = subprocess.run([sys.executable, os.path.join(ROOT, gen), "--out", outdir],
                           cwd=ROOT, env=env, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        if r.returncode != 0:
            return False, "%s rc=%d %s" % (gen, r.returncode, (r.stderr or "")[-300:])
    return True, ""


def main() -> int:
    if not os.path.isdir(VEC):
        check("vectors directory exists", False, VEC)
        print("fundamental vector freshness guard: %d passed / %d failed" % (PASS, FAIL))
        return 1

    committed = sorted(f for f in os.listdir(VEC) if f.endswith(".json"))
    check("only the named vector files live there", set(committed) <= ALLOWED and bool(committed),
          "extra=%s" % sorted(set(committed) - ALLOWED))

    tmp = tempfile.mkdtemp(prefix="b4-vec-guard-")
    try:
        ok, why = regenerate(tmp)
        check("both oracle scripts run", ok, why)
        if not ok:
            print("fundamental vector freshness guard: %d passed / %d failed" % (PASS, FAIL))
            return 1
        fresh = sorted(f for f in os.listdir(tmp) if f.endswith(".json"))
        check("the fresh build produces the same file list", fresh == committed,
              "fresh=%s committed=%s" % (fresh, committed))
        drift = []
        total = 0
        for name in committed:
            if name not in fresh:
                drift.append("%s missing" % name)
                continue
            a = open(os.path.join(VEC, name), "rb").read()
            b = open(os.path.join(tmp, name), "rb").read()
            try:
                doc = json.load(open(os.path.join(VEC, name), encoding="utf-8"))
                total += sum(len(v) for v in doc.values() if isinstance(v, list))
            except Exception:                                     # noqa: BLE001
                drift.append("%s is not readable JSON" % name)
                continue
            if a != b:
                drift.append(name)
        check("every vector file is byte-identical to a fresh oracle run", not drift,
              "drift=%s" % drift[:4] if drift else "%d cases across %d files"
              % (total, len(committed)))
        check("the vectors carry real content", total >= 500, "total cases=%d" % total)

        # کنترلِ منفی: یکِ عددِ داخلِ thresholds را تکان بده — مقایسه باید قرمز شود.
        path = os.path.join(tmp, "thresholds.json")
        try:
            doc = json.load(open(path, encoding="utf-8"))
            first = doc["cases"][0]["out"]
            key = "margin_min" if "margin_min" in first else sorted(first)[0]
            first[key] = -12345.0
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(doc, f, ensure_ascii=False, indent=1, sort_keys=True)
                f.write("\n")
            differs = open(path, "rb").read() != open(os.path.join(VEC, "thresholds.json"),
                                                      "rb").read()
            check("a mutated vector is detected (the sensor is not blind)", differs)
        except Exception as exc:                                  # noqa: BLE001
            check("a mutated vector is detected (the sensor is not blind)", False, repr(exc))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("fundamental vector freshness guard: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
