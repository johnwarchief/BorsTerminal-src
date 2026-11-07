import sys
import os
sys.path.insert(0, os.path.abspath("."))
import json
from app import app
from fastapi.routing import APIRoute

def get_all_routes(router_or_app, prefix=""):
    results = []
    routes = getattr(router_or_app, "routes", [])
    for r in routes:
        if hasattr(r, "original_router"):
            results.extend(get_all_routes(r.original_router, prefix))
        elif hasattr(r, "routes"):
            results.extend(get_all_routes(r, prefix + getattr(r, "path", "")))
        elif isinstance(r, APIRoute):
            path = prefix + r.path
            methods = sorted(list(r.methods - {"HEAD", "OPTIONS"} if r.methods else []))
            endpoint = r.endpoint
            mod = endpoint.__module__ if endpoint else ""
            fn = endpoint.__name__ if endpoint else ""
            for m in methods:
                results.append({
                    "method": m,
                    "path": path,
                    "module": mod,
                    "function": fn,
                    "name": r.name,
                    "summary": r.summary or "",
                    "description": r.description or ""
                })
        elif hasattr(r, "path") and hasattr(r, "endpoint"):
            path = prefix + r.path
            methods = sorted(list(getattr(r, "methods", ["GET"])))
            methods = [m for m in methods if m not in ("HEAD", "OPTIONS")]
            endpoint = r.endpoint
            mod = endpoint.__module__ if endpoint else ""
            fn = endpoint.__name__ if endpoint else ""
            for m in methods:
                results.append({
                    "method": m,
                    "path": path,
                    "module": mod,
                    "function": fn,
                    "name": getattr(r, "name", ""),
                    "summary": "",
                    "description": ""
                })
    return results

all_r = get_all_routes(app)
print(f"Total endpoints extracted: {len(all_r)}")
unique_pairs = {(r["method"], r["path"]) for r in all_r}
print(f"Unique (method, path) combinations: {len(unique_pairs)}")

with open("_audit/python_extracted_routes.json", "w", encoding="utf-8") as f:
    json.dump(all_r, f, ensure_ascii=False, indent=2)

for p in sorted(list(unique_pairs)):
    print(f"{p[0]:6} {p[1]}")
