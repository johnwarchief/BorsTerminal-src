# tools/phase497/separation/paths.py
import sqlite3
REF_DB = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all/reference_all.db"
JSONL_DIR = r"D:/BorsTerminal-worktrees/phase49-5-resume/_audit/phase49-5/api-all"
UNIVERSE = JSONL_DIR + "/universe.json"
PACK = r"D:/BorsTerminal-worktrees/phase49-5-resume/data/ra365_corrections/ra365-phase49-rebuild-full-v2"
OUT_DIR = r"D:/BorsTerminal-data/separation"
ASSET_CLASS = {"1":"equity","2":"fund","7":"rights","4":"bond","3":"future","17":"commodity_cert",
  "8":"currency","25":"crypto","27":"forex","16":"option","10":"contingent_option","13":"parallel_salaf",
  "6":"other","9":"commodity","5":"housing_point","12":"salaf","26":"intellectual"}
def ro_conn(db):
    return sqlite3.connect("file:" + db + "?mode=ro&immutable=1", uri=True)