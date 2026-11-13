# tools/phase497/separation/tests/test_shared.py
import os, sqlite3, pytest
from tools.phase497.separation import paths, build_shared

def test_asset_count_and_crosswalk(tmp_path):
    out = tmp_path / "shared_metadata.db"
    build_shared.build_all(str(out))
    c = sqlite3.connect(str(out))
    n = c.execute("SELECT COUNT(*) FROM asset").fetchone()[0]
    assert n == 45157
    # asset_id unique (PK)
    dup = c.execute("SELECT asset_id FROM asset GROUP BY asset_id HAVING COUNT(*)>1").fetchall()
    assert dup == []
    # dollar asset present
    row = c.execute("SELECT type_name FROM asset WHERE asset_id=2").fetchone()
    assert row is not None
    # crosswalk has ins_code for pack assets
    cw = c.execute("SELECT COUNT(*) FROM id_crosswalk WHERE ins_code IS NOT NULL").fetchone()[0]
    assert cw >= 800
    c.close()

def test_mode_def_and_usd_rate(tmp_path):
    out = tmp_path / "shared_metadata.db"; build_shared.build_all(str(out))
    c = sqlite3.connect(str(out))
    assert c.execute("SELECT COUNT(*) FROM mode_def").fetchone()[0] == 63
    assert c.execute("SELECT alias_of FROM mode_def WHERE mode_key='D/real_close/type0'").fetchone()[0] == "D/last/type0"
    assert c.execute("SELECT alias_of FROM mode_def WHERE mode_key='D/close/type5'").fetchone()[0] == "D/close/type0"
    # usd_rate matches measured close/close_usd ratio (~2.64e6 on 2026-11-11)
    r = c.execute("SELECT rate_rial FROM usd_rate ORDER BY date DESC LIMIT 1").fetchone()[0]
    assert 2_000_000 < r < 3_000_000
    c.close()