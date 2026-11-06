import io, re, json

t = io.open("docs/RELEASE_NOTES.md", encoding="utf-8", newline="").read().split("\n")
start = next(i for i, l in enumerate(t) if l.rstrip("\r") == "## v1.0.73")
end = next(i for i in range(start + 1, len(t)) if t[i].rstrip("\r").startswith("## "))
lab = json.load(open("_audit/fts_lab_jet+choch+hunt+dbl+fib_b0_event.json", encoding="utf-8"))
bars = lab["jet"]["bars_evaluated"]
syms = lab["jet"]["symbols"]
base = lab["jet"]["base_rate"]["win"]
rows = []
for i in range(start, end):
    line = t[i].rstrip("\r")
    for m in re.finditer("[۰-۹٬٫]+[٪%]?", line):
        rows.append((i + 1, m.group(), line[max(0, m.start() - 22):m.start()], line[m.end():m.end() + 22]))
print("panel:", syms, "symbols /", bars, "bars / base", round(base, 3))
for ln, tok, before, after in rows:
    print(f"{ln:>4} | {tok:<12} | …{before} [[{tok}]] {after}…")
