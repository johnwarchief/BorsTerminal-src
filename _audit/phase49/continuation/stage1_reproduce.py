"""Phase 4.9 — Stage 1 reproduction against the restored Phase 4.8 DB copies.

Reproduces, from restored-source.db (pre-backfill) and restored-work.db
(post-backfill):

  * price_history totals and the 30-symbol subset (source vs work),
  * new rows and changed existing rows (whole DB, column by column),
  * src split of the 30-symbol work rows,
  * chain totals from the local ledgers and the tracked correction pack
    (product events, pack replace steps, official rows).

Read-only: both connections open with mode=ro. Writes only a JSON report.
"""
import json
import os
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", ".."))
CONT = os.path.join(ROOT, "_audit", "phase49", "continuation")
SOURCE = os.path.join(CONT, "db", "restored-source.db")
WORK = os.path.join(CONT, "db", "restored-work.db")
PACK = os.path.join(ROOT, "data", "ra365_corrections", "ra365-r32b-v2", "factors.jsonl")
OUT = os.path.join(CONT, "evidence", "stage1-reproduction.json")

FIELDS = ["open", "high", "low", "close", "volume", "last", "value", "src"]


def ro(path):
    return sqlite3.connect("file:" + path.replace("\\", "/") + "?mode=ro", uri=True)


def symbols30():
    import csv
    with open(os.path.join(CONT, "symbols30.csv"), encoding="utf-8-sig") as f:
        return [r["symbol"] for r in csv.DictReader(f) if r["symbol"]]


def pack_by_ins():
    rows = {}
    with open(PACK, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("action") != "replace_step":
                continue
            rows.setdefault(str(r.get("ins_code") or ""), []).append(r)
    return rows


def main():
    syms = symbols30()
    pack = pack_by_ins()
    rep = {"symbols": len(syms)}

    src = ro(SOURCE)
    work = ro(WORK)
    try:
        rep["source_rows_total"] = src.execute(
            "SELECT COUNT(*) FROM price_history").fetchone()[0]
        rep["work_rows_total"] = work.execute(
            "SELECT COUNT(*) FROM price_history").fetchone()[0]
        rep["new_rows_total"] = (rep["work_rows_total"] - rep["source_rows_total"])

        # Whole-DB row identity on the common key set, inside SQL via ATTACH.
        src.execute("ATTACH DATABASE ? AS w", ("file:" + WORK.replace("\\", "/") + "?mode=ro",))
        mism = 0
        for f in FIELDS:
            q = ("SELECT COUNT(*) FROM price_history s JOIN w.price_history x "
                 "ON x.symbol=s.symbol AND x.date=s.date WHERE "
                 + " OR ".join("IFNULL(x.%s,'')<>IFNULL(s.%s,'')" % (k, k) for k in FIELDS))
            mism += src.execute(q).fetchone()[0]
        rep["existing_rows_changed"] = mism
        rep["existing_rows_compared"] = src.execute(
            "SELECT COUNT(*) FROM price_history s JOIN w.price_history x "
            "ON x.symbol=s.symbol AND x.date=s.date").fetchone()[0]
        src.execute("DETACH DATABASE w")

        qmarks = ",".join("?" * len(syms))
        rep["source_rows_30"] = src.execute(
            "SELECT COUNT(*) FROM price_history WHERE symbol IN (%s)" % qmarks,
            syms).fetchone()[0]
        rep["work_rows_30"] = work.execute(
            "SELECT COUNT(*) FROM price_history WHERE symbol IN (%s)" % qmarks,
            syms).fetchone()[0]
        rep["new_rows_30"] = rep["work_rows_30"] - rep["source_rows_30"]
        rep["src_split_30"] = dict(work.execute(
            "SELECT src, COUNT(*) FROM price_history WHERE symbol IN (%s) "
            "GROUP BY src" % qmarks, syms).fetchall())

        # Chain totals: product ledger events, pack replace steps, official rows.
        product = src.execute(
            "SELECT COUNT(*) FROM adjust_events WHERE ratio>0 AND symbol IN (%s)" % qmarks,
            syms).fetchone()[0]
        per_symbol = []
        total_pack = total_official = 0
        for s in syms:
            ins = src.execute(
                "SELECT ins_code FROM instruments WHERE l_val18=? "
                "ORDER BY updated_at DESC LIMIT 1", (s,)).fetchone()
            ins = str(ins[0]) if ins and ins[0] else ""
            psteps = len(pack.get(ins, [])) if ins else 0
            if not psteps and not ins:
                psteps = 0
            official = 0
            if ins:
                official = src.execute(
                    "SELECT (SELECT COUNT(*) FROM price_adjust_events WHERE ins_code=?) + "
                    "(SELECT COUNT(*) FROM share_change_events WHERE ins_code=?)",
                    (ins, ins)).fetchone()[0]
            p_events = src.execute(
                "SELECT COUNT(*) FROM adjust_events WHERE ratio>0 AND symbol=?",
                (s,)).fetchone()[0]
            per_symbol.append({"symbol": s, "ins_code": ins or None,
                               "product_events": p_events, "pack_steps": psteps,
                               "official_rows": official})
            total_pack += psteps
            total_official += official
        rep["chain_totals"] = {
            "product_events": product,
            "pack_steps": total_pack,
            "official_rows": total_official,
        }
        rep["per_symbol"] = per_symbol
        rep["status"] = "ok"
    finally:
        src.close()
        work.close()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in rep.items() if k != "per_symbol"},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
