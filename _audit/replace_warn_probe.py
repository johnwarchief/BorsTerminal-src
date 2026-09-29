import os
import sys

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO)

import warnings  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

df = pd.DataFrame({
    "a": [1, 2, 3],
    "b": ["x", "y", "z"],
    "c": [np.inf, 1.0, 2.0],
    "d": [True, False, True],
    "e": [1.5, np.nan, 3.0],
})

with warnings.catch_warnings(record=True) as w:
    warnings.simplefilter("always")
    out = df.replace([np.inf, -np.inf], 0).fillna(0)
    print("replace warns:", [(str(x.message)[:80],
                              os.path.basename(x.filename), x.lineno) for x in w])
print("replace dtypes:", out.dtypes.to_dict())

with warnings.catch_warnings(record=True) as w2:
    warnings.simplefilter("always")
    num = df.select_dtypes("number")
    out2 = df.mask(np.isinf(num.astype("float64")).fillna(False), 0).fillna(0)
    print("mask warns:", [str(x.message)[:80] for x in w2])
print("mask dtypes:", out2.dtypes.to_dict())
print("values equal:", out.equals(out2))
print("pandas", pd.__version__, "numpy", np.__version__)
