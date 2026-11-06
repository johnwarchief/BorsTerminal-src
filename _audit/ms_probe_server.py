import os, sys
os.environ["BORS_NO_FETCH_LOOPS"] = "1"
ROOT = r"C:\Users\PCMOD\Desktop\BorsTerminal"
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import bors_config as B
B.DB_PATH = os.path.join(ROOT, "_audit", "live_ms_copy.db")
B.STATUS_PATH = os.path.join(ROOT, "_audit", "probe_status.json")
B.MARKET_STATUS_PATH = os.path.join(ROOT, "_audit", "probe_mstatus.json")
import uvicorn
from app import app
uvicorn.run(app, host="127.0.0.1", port=8003, log_level="warning")
