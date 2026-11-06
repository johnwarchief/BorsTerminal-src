import os, sys
os.environ["BORS_NO_FETCH_LOOPS"] = "1"
ROOT = r"C:\Users\PCMOD\Desktop\BorsTerminal"
sys.path.insert(0, ROOT); os.chdir(ROOT)
import bors_config as B
B.DB_PATH = os.path.join(ROOT, sys.argv[1])
B.STATUS_PATH = os.path.join(ROOT, "_audit", "probe2_status.json")
B.MARKET_STATUS_PATH = os.path.join(ROOT, "_audit", "probe2_mstatus.json")
import uvicorn
from app import app
uvicorn.run(app, host="127.0.0.1", port=int(sys.argv[2]), log_level="warning")
