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