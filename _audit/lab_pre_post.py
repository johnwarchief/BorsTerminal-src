import json, io

PRE = json.load(io.open("_audit/fts_lab_pre-holefix.json", encoding="utf-8"))
POST = json.load(io.open("_audit/fts_lab_jet+choch+hunt+dbl+fib_b0_event.json", encoding="utf-8"))
FA = "".join(chr(0x06F0 + d) for d in range(10))


def fa(x, grp=True):
    s = f"{x:,}" if grp else str(x)
    return "".join(FA[int(c)] if c.isdigit() else ("٬" if c == "," else c) for c in s)


print("پنل پیش:", fa(PRE["jet"]["symbols"]), "نماد /", fa(PRE["jet"]["bars_evaluated"]), "کندل",
      "| پس:", fa(POST["jet"]["symbols"]), "/", fa(POST["jet"]["bars_evaluated"]))
print("نرخِ پایه پیش:", round(PRE["jet"]["base_rate"]["win"], 3),
      "پس:", round(POST["jet"]["base_rate"]["win"], 3))
for sig in ("jet", "choch", "hunt", "dbl", "fib"):
    a = PRE.get(sig, {}).get("variants", {})
    b = POST.get(sig, {}).get("variants", {})
    if not b:
        continue
    print(f"\n### {sig}")
    print("  variant".ljust(34), "| آتش پیش→پس".ljust(20), "| دقت پیش→پس")
    for k in sorted(b, key=lambda x: -b[x]["precision"]):
        pa = a.get(k, {}).get("precision")
        fa_ = a.get(k, {}).get("fires")
        print(f"  {k:<32} | {fa(fa_ or 0):>7}→{fa(b[k]['fires']):>7}    | "
              f"{('%.3f' % pa) if pa is not None else '  —  '}→{b[k]['precision']:.3f}"
              + ("   (از دست رفته)" if k not in a else ""))
    best_pre = max(a, key=lambda x: a[x]["precision"]) if a else None
    best_post = max(b, key=lambda x: b[x]["precision"])
    print("  بهترینِ پیش:", best_pre, "| بهترینِ پس:", best_post,
          "| یکی است؟", best_pre == best_post)
