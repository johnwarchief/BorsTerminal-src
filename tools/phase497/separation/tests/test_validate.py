# tools/phase497/separation/tests/test_validate.py
import os, sqlite3
from tools.phase497.separation import validate_separation as V, build_technical

def _synthetic_tech(path):
    c = sqlite3.connect(str(path))
    schema = os.path.join(os.path.dirname(build_technical.__file__), "schema_technical.sql")
    c.executescript(open(schema, encoding="utf-8").read())
    for t in (1000, 2000):
        c.execute("INSERT INTO candle(asset_id,res,basis,adj,t,utc,o,h,l,c,v) VALUES (591,'D','close','type0',?,'1970-01-01T00:00:01Z',1,2,1,2,5)", (t,))
    c.commit(); c.close()

def test_structural_gates_pass_on_clean(tmp_path):
    tech = tmp_path/"t.db"; shared = tmp_path/"s.db"
    _synthetic_tech(tech); sqlite3.connect(str(shared)).close()
    rep = V.validate(str(shared), str(tech), structural_only=True)
    assert rep["integrity"]["pass"] is True
    assert rep["no_placeholder"]["pass"] is True
    assert rep["no_dup_t"]["pass"] is True
    assert "alias_reproduction" not in rep and "row_reconciliation" not in rep

def test_no_placeholder_gate_detects_violation(tmp_path):
    tech = tmp_path/"t.db"; shared = tmp_path/"s.db"
    _synthetic_tech(tech)
    c = sqlite3.connect(str(tech)); c.execute("INSERT INTO candle(asset_id,res,basis,adj,t,utc,o,h,l,c,v) VALUES (591,'D','close','type0',0,'',0,0,0,0,0)"); c.commit(); c.close()
    sqlite3.connect(str(shared)).close()
    rep = V.validate(str(shared), str(tech), structural_only=True)
    assert rep["no_placeholder"]["pass"] is False   # gate must DETECT the t=0 row
    assert rep["all_pass"] is False                 # violation must propagate to the rollup

def _synthetic_ref(path, with_591=True):
    c = sqlite3.connect(str(path))
    c.execute("CREATE TABLE candles(asset_id INTEGER, res TEXT, basis TEXT, adj TEXT, t INTEGER, o REAL, h REAL, l REAL, c REAL, v INTEGER)")
    if with_591:
        for basis, adj in (("real_close","type0"),("last","type0"),("close","type0"),("close","type5")):
            for t, cl in ((1000,2.0),(2000,3.0)):
                c.execute("INSERT INTO candles VALUES (591,'D',?,?,?,1,2,1,?,5)", (basis, adj, t, cl))
    c.commit(); c.close()

def test_alias_gate_non_vacuous(tmp_path):
    tech = tmp_path/"t.db"; shared = tmp_path/"s.db"; ref = tmp_path/"r.db"
    # technical.db with ALL 4 kept-mode rows (last/type0 + close/type0 at t=1000,2000)
    c = sqlite3.connect(str(tech))
    schema = os.path.join(os.path.dirname(build_technical.__file__), "schema_technical.sql")
    c.executescript(open(schema, encoding="utf-8").read())
    for basis in ("last", "close"):
        for t in (1000, 2000):
            c.execute("INSERT INTO candle(asset_id,res,basis,adj,t,utc,o,h,l,c,v) VALUES (591,'D',?,'type0',?,'1970-01-01T00:00:01Z',1,2,1,2,5)", (basis, t))
    c.commit(); c.close()
    sqlite3.connect(str(shared)).close()
    _synthetic_ref(ref, with_591=True)
    rep = V.validate(str(shared), str(tech), ref=str(ref), structural_only=False)
    # measured synthetic counts: ref keeps last/type0 + close/type0 (real_close and
    # close/type5 excluded by the Ruling 9 WHERE) = 2 series x 2 t = 4 distinct keys
    assert rep["alias_reproduction"]["pass"] is True    # non-empty identical sample (2 bars)
    assert rep["row_reconciliation"]["pass"] is True    # tech 4 rows == ref distinct 4 keys
    assert rep["all_pass"] is True
    # empty reference -> alias gate must FAIL (proves the non-vacuity guard)
    ref_empty = tmp_path/"r_empty.db"; _synthetic_ref(ref_empty, with_591=False)
    rep2 = V.validate(str(shared), str(tech), ref=str(ref_empty), structural_only=False)
    assert rep2["alias_reproduction"]["pass"] is False
    assert rep2["row_reconciliation"]["pass"] is False  # tech 4 != ref distinct 0
    # empty technical + empty reference -> 0==0 must NOT pass (reconciliation guard)
    tech_empty = tmp_path/"t_empty.db"
    c = sqlite3.connect(str(tech_empty))
    c.executescript(open(schema, encoding="utf-8").read())
    c.commit(); c.close()
    rep3 = V.validate(str(shared), str(tech_empty), ref=str(ref_empty), structural_only=False)
    assert rep3["row_reconciliation"]["pass"] is False
    assert rep3["all_pass"] is False