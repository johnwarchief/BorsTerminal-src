# tools/phase497/separation/tests/test_technical.py
import sqlite3, pytest
from tools.phase497.separation import build_technical

def test_candle_cleaning_small(tmp_path, monkeypatch):
    # build a 2-record fake JSONL: one normal bar, one t=0 placeholder, one identical dup
    import json, os
    d = tmp_path / "jsonl"; d.mkdir()
    rec = {"asset_id":"591","trade_symbol":"x","name":"x","n":3,"bars":[
        {"time":1000,"utc":"1970-01-01T00:00:01Z","open":1,"high":2,"low":1,"close":2,"volume":5},
        {"time":0,"utc":"","open":0,"high":0,"low":0,"close":0,"volume":0},
        {"time":1000,"utc":"1970-01-01T00:00:01Z","open":1,"high":2,"low":1,"close":2,"volume":5}]}
    (d / "bars_D_close_type0.jsonl").write_text(json.dumps(rec)+"\n", encoding="utf-8")
    (d / "bars_D_real_close_type0.jsonl").write_text(json.dumps(rec)+"\n", encoding="utf-8")  # alias, skipped
    out = tmp_path / "technical.db"
    build_technical.build_candles(str(out), str(d))
    c = sqlite3.connect(str(out))
    assert c.execute("SELECT COUNT(*) FROM candle").fetchone()[0] == 1   # t=0 dropped, dup deduped, alias skipped
    assert c.execute("SELECT COUNT(*) FROM candle WHERE t=0").fetchone()[0] == 0
    assert c.execute("SELECT utc FROM candle").fetchone()[0] == "1970-01-01T00:00:01Z"
    c.close()

def test_adjustments_from_pack(tmp_path):
    out = tmp_path / "technical.db"
    build_technical.build_adjustments(str(out))
    c = sqlite3.connect(str(out))
    n = c.execute("SELECT COUNT(*) FROM adjustment_event").fetchone()[0]
    assert n == 8280
    f = c.execute("SELECT COUNT(*) FROM adjustment_factor").fetchone()[0]
    assert f > 0
    c.close()