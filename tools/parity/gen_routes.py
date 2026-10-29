#!/usr/bin/env python
"""فهرستِ مسیرهایِ /api از decoratorهایِ api/*.py → backend-go/internal/httpapi/routes.json"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUT = os.path.join(ROOT, "backend-go", "internal", "httpapi", "routes.json")
ROUTE = re.compile(r'@router\.(get|post|put|delete|patch)\("(/api/[^"]+)"')
METHODS = ("get", "post", "put", "delete", "patch")


def main() -> int:
    found = set()
    for name in sorted(os.listdir(os.path.join(ROOT, "api"))):
        if not name.endswith(".py"):
            continue
        text = open(os.path.join(ROOT, "api", name), encoding="utf-8").read()
        for method, path in ROUTE.findall(text):
            found.add("%s %s" % (method.upper(), path))
    routes = sorted(found)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(routes, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("routes:", len(routes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
