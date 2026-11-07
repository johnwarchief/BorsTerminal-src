import json

with open('_audit/python_extracted_routes.json', encoding='utf-8') as f:
    py_routes = json.load(f)

with open('backend-go/internal/httpapi/routes.json', encoding='utf-8') as f:
    go_known = json.load(f)

py_api = sorted({f"{r['method']} {r['path']}" for r in py_routes if r['path'].startswith('/api/')})
py_non_api = sorted({f"{r['method']} {r['path']}" for r in py_routes if not r['path'].startswith('/api/')})
go_set = set(go_known)

print(f"Total Python /api/* routes: {len(py_api)}")
print(f"Total Python non-api routes: {len(py_non_api)}")
print(f"Total Go cataloged routes: {len(go_set)}")

missing_in_go = sorted(set(py_api) - go_set)
print(f"\nAPI routes in Python but NOT in Go routes.json ({len(missing_in_go)}):")
for r in missing_in_go:
    print('  +', r)
