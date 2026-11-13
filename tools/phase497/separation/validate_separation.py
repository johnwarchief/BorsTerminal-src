# tools/phase497/separation/validate_separation.py
import sqlite3
from . import paths

def validate(shared, tech, ref=None, structural_only=False):
    """Validation gates for the separated data layer.

    structural_only=True runs ONLY the three structural gates (integrity,
    no_placeholder, no_dup_t) and never opens the reference connection;
    alias_reproduction and row_reconciliation are skipped (fast unit tests).
    structural_only=False (default) runs all five gates against the reference
    (read-only via paths.ro_conn) — used by the Task 6 orchestrator.
    """
    t = sqlite3.connect(tech); s = sqlite3.connect(shared)
    rep = {}
    rep["integrity"] = {"pass": t.execute("PRAGMA integrity_check").fetchone()[0]=="ok",
                        "evidence": "technical.db integrity_check"}
    ph = t.execute("SELECT COUNT(*) FROM candle WHERE t=0").fetchone()[0]
    rep["no_placeholder"] = {"pass": ph==0, "evidence": f"t=0 rows={ph}"}
    dup = t.execute("SELECT COUNT(*) FROM (SELECT asset_id,res,basis,adj,t FROM candle GROUP BY asset_id,res,basis,adj,t HAVING COUNT(*)>1)").fetchone()[0]
    rep["no_dup_t"] = {"pass": dup==0, "evidence": f"dup-t groups={dup}"}
    if not structural_only:
        ref = ref or paths.REF_DB
        r = paths.ro_conn(ref)
        # alias reproduction: real_close==last and type5==type0 on reference (sample asset 591)
        def ser(basis, adj):
            return {tt:cc for tt,cc in r.execute("SELECT t,c FROM candles WHERE asset_id=591 AND res='D' AND basis=? AND adj=?", (basis,adj))}
        rc, la, t0, t5 = ser("real_close","type0"), ser("last","type0"), ser("close","type0"), ser("close","type5")
        common = set(rc)&set(la)
        alias_ok = all(rc[k]==la[k] for k in common) and all(t0[k]==t5[k] for k in (set(t0)&set(t5)))
        rep["alias_reproduction"] = {"pass": alias_ok, "evidence": f"real_close==last & type0==type5 on 591 ({len(common)} bars)"}
        # row reconciliation: technical distinct-mode rows == deduped reference distinct-mode rows minus t=0 padding
        # (Ruling 9: COUNT(DISTINCT ...) with '/' separators — the technical build drops identical source dups)
        ref_distinct = r.execute("SELECT COUNT(DISTINCT asset_id||'/'||res||'/'||basis||'/'||adj||'/'||t) FROM candles WHERE basis!='real_close' AND adj!='type5' AND t>0").fetchone()[0]
        tech_rows = t.execute("SELECT COUNT(*) FROM candle").fetchone()[0]
        rep["row_reconciliation"] = {"pass": tech_rows==ref_distinct, "evidence": f"technical={tech_rows} ref_distinct_no_t0={ref_distinct}"}
        r.close()
    t.close(); s.close()
    rep["all_pass"] = all(g["pass"] for g in rep.values() if isinstance(g,dict))
    return rep