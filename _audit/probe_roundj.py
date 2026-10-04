import sys
sys.path.insert(0, ".")
from api import chart as CH


def series(vals, spread=3.0):
    out = []
    for i, v in enumerate(vals):
        o = v * 0.99
        c = v
        out.append({"time": "2026-%02d-%02d" % (i // 28 + 1, i % 28 + 1),
                    "open": o, "high": max(o, c) * (1 + spread / 100),
                    "low": min(o, c) * (1 - spread / 100), "close": c,
                    "volume": 1000.0 + i})
    return out


def wave(cycles):
    vals = []
    for k in range(cycles):
        vals += [100 + k, 92 + k, 110 + k, 96 + k]
    return vals

c = series(wave(20))
sw = CH._fts_swings(c, k=CH._FTS_SWING_K)
print("1) no jet history:", [e["kind"] for e in CH._fts_setup_history(c, sw)].count("jet"),
      "| kinds:", sorted({e["kind"] for e in CH._fts_setup_history(c, sw)}))

ph = CH._fts_point_hunt(c, sw)
print("2) point_hunt:", {k: ph[k] for k in ("active", "touches", "bounced", "floor_date", "trigger_date")})
jet = CH._fts_jet_setup(c)
print("3) jet keys:", sorted(jet.keys()))
print("   jet resistance_date:", jet.get("resistance_date"), "ceiling_date:", jet.get("ceiling_date"))

short = series([100, 101, 99, 102, 100][:5])
l1 = CH._fts_exit_layer1([])
l3 = CH._fts_exit_layer3(series(wave(3)), CH._fts_swings(series(wave(3)), k=3))
l4 = CH._fts_exit_layer4(short)
print("4) L1 بی‌کندل:", l1["stop_hit"], l1["ma14_exit"], "| L3 کم‌سابقه:", l3, "| L4 کم‌سابقه:", l4["rsi_divergence"], l4["rsi_rollover"])
ex = CH._fts_exit_engine(short)
print("   verdict کم‌سابقه:", ex["verdict"], "| unmeasured:", ex["unmeasured"])

full = series(wave(25))
out = CH._fts_analyze_candles("تست", full)
st = out["status"]
print("5) status:", st["code"], "|", st["text"])
print("   trigger:", st["trigger"], "| exits:", st["exits"], "| warnings:", st["warnings"])
print("   roles sample:", {k: st["roles"][k] for k in ("jet", "fib_zone", "third_peak", "ma14_exit")})
print("6) setups بی‌جت:", all(e["kind"] != "jet" for e in out["setups"]), "| تعداد:", len(out["setups"]))
