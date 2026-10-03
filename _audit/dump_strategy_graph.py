# -*- coding: utf-8 -*-
"""_audit/dump_strategy_graph.py — استخراجِ مکانیکیِ جدولِ ۴۶ گره و یال‌ها

متن‌ها/آستانه‌ها/قاعدها باید عیناً به مدلِ تازه منتقل شوند، پس هیچ رشته‌ای دستِ من
بازنویسی نمی‌شود: این اسکریپت شیءهایِ درونِ `getGraphNodes` و `getGraphLinks` را با
شمارشِ آکولاد جدا می‌کند، هر میدان را همان‌طور که هست بیرون می‌دهد و درِ
`_audit/strategy_graph_dump.json` می‌گذارد. خروجیِ این فایل ورودیِ `ftsChartModel.ts`
است (تولیدِ مکانیکی، نه تایپِ دوباره).
"""
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "frontend", "src", "features", "master",
                   "components", "ObsidianStrategyGraph.tsx")
OUT = os.path.join(ROOT, "_audit", "strategy_graph_dump.json")

FIELDS = ("id label fullTitle category stage stageName page description ruleFormula badge "
          "color radius x y editableParamKeys presets flow source target").split()


def objects(body):
    """همهٔ شیءهایِ سطح‌یکِ درونِ آرایه‌هایِ `return [ … ]` این بخش.

    پیمایش رشته‌آگاه است (متن‌هایِ RTL، گیومه و `${…}` آکولادِ درونِ رشته عمق نمی‌شمارد)
    و آکولادِ خودِ تابع درِ خطِ امضا کنار گذاشته می‌شود — نسخهٔ نخستِ همین اسکریپت همان
    را شمرد و «یک» شیء داد که کل بدنه بود.
    """
    out = []
    i, n = 0, len(body)
    while i < n:
        j = body.find("return [", i)
        if j < 0:
            break
        k, depth, buf = j + len("return "), 0, ""
        instr, quote, esc = False, "", False
        while k < n:
            c = body[k]
            if instr:
                buf += c
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == quote:
                    instr = False
                k += 1
                continue
            if c in "\"'`":
                instr, quote = True, c
                buf += c
                k += 1
                continue
            if c == "{":
                depth += 1
                if depth == 1:
                    buf = ""
                    k += 1
                    continue
            if c == "}":
                depth -= 1
                if depth == 0:
                    out.append(buf)
                    buf = ""
                    k += 1
                    continue
            if c == "]" and depth == 0:
                break
            if depth:
                buf += c
            k += 1
        i = k + 1
    return out


def split_fields(obj):
    """جداکردنِ «کلید: مقدار» در سطحِ بیرون؛ رشته‌هایِ چندسطری و template حفظ می‌شوند."""
    res, i, n = {}, 0, len(obj)
    while i < n:
        mm = re.match(r"\s*(\w+)\s*:\s*", obj[i:])
        if not mm:
            i += 1
            continue
        key = mm.group(1)
        j = i + mm.end()
        depth, instr, quote, esc = 0, False, "", False
        start = j
        while j < n:
            c = obj[j]
            if instr:
                if esc:
                    esc = False
                elif c == "\\":
                    esc = True
                elif c == quote:
                    instr = False
            else:
                if c in "\"'`":
                    instr, quote = True, c
                elif c in "{[(":
                    depth += 1
                elif c in "}])":
                    depth -= 1
                elif c == "," and depth == 0:
                    break
            j += 1
        res[key] = obj[start:j].strip()
        i = j + 1
    return res


def section(src, fn_name, next_marker):
    a = src.index("function %s" % fn_name) if src.count("function %s" % fn_name) else src.index(fn_name)
    b = src.index(next_marker, a)
    return src[a:b]


def main():
    src = io.open(SRC, encoding="utf-8").read()
    nsec = section(src, "getGraphNodes", "export function getGraphLinks")
    lsec = section(src, "getGraphLinks", "export interface ObsidianStrategyGraphProps")
    nodes = [split_fields(o) for o in objects(nsec)]
    links = [split_fields(o) for o in objects(lsec)]
    nodes = [n for n in nodes if n.get("id")]
    links = [l for l in links if l.get("source")]
    ids = [n["id"].strip("'\"") for n in nodes]
    print("گره:", len(nodes), "یکتا:", len(set(ids)), "یال:", len(links))
    json.dump({"node_ids": ids, "nodes": nodes, "links": links},
              io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("نوشته شد:", os.path.relpath(OUT, ROOT))
    # گزارشِ پوشش: کدام میدان‌ها واقعاً پراند
    cov = {f: sum(1 for n in nodes if f in n) for f in FIELDS}
    print("پوششِ میدان‌ها:", json.dumps(cov, ensure_ascii=False))
    dup = [i for i in set(ids) if ids.count(i) > 1]
    print("تکراریِ id:", dup or "هیچ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
