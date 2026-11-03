# -*- coding: utf-8 -*-
# B1: سطحِ importِ سوئیتِ پاریتی ⇄ فایل‌هایِ تغییرکردهٔ این شاخه (اگر اشتراک تهی باشد، timeout ازِ این تغییرها نیست).
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(WT)
sys.path.insert(0, WT)
import bors_config  # noqa: E402,F401
import fts_engine  # noqa: E402,F401
from api import fundamental  # noqa: E402,F401


def rel(p):
    return os.path.relpath(os.path.abspath(p), WT).replace(os.sep, "/")


loaded = sorted({rel(m.__file__) for m in list(sys.modules.values())
                 if getattr(m, "__file__", None) and os.path.abspath(m.__file__).lower().startswith(WT.lower())})
diff = subprocess.run(["git", "diff", "--name-only", "HEAD"], capture_output=True, text=True).stdout.split()
out = {"suite": "dev/fts_engine_paths_parity_v1076.py", "repo_modules_loaded": loaded,
       "changed_files_vs_HEAD": diff, "intersection": sorted(set(loaded) & set(diff))}
with open(os.path.join(HERE, "b1-parity-import-surface.json"), "w", encoding="utf-8") as fh:
    json.dump(out, fh, ensure_ascii=False, indent=1)
print(len(loaded), "loaded; intersection:", out["intersection"])
