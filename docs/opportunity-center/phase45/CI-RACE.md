# گزارشِ جابِ race detector در GitHub Actions — فاز ۴٫۵

مأموریت §10: یک جابِ واقعیِ CI که `go test -race` را روی لینوکس با GCC/CGO اجرا کند،
نه آزمونِ محلی. این فایل شاهدِ اجرا است، نه ادعایِ محلی.

## خودِ اجرا

| قلم | مقدار |
| --- | --- |
| Workflow | `guards.yml` (`.github/workflows/guards.yml`) |
| جاب | `go race detector (cmd/borsd + generation runtime)` |
| Run | [42627365075](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42627365075) |
| Job | [129194484649](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42627365075/job/129194484649) |
| Head SHA | `10ea918ea3e1c0098b8fa50824134b8b398f52e8` |
| Branch | `mission/phase45-technical-data-integrity-2026-11-09` |
| نتیجهٔ جاب | **success** (۱m۴۹s؛ ۲۰۲۶-۱۱-۰۹ ۱۳:۳۹–۱۳:۴۱ UTC) |
| Runner | `ubuntu-latest`، Go `1.27.3`، `CGO_ENABLED=1`، گامِ `gcc --version` سبز |

## آخرین اجرا رویِ کدِ نهاییِ مأموریت

| قلم | مقدار |
| --- | --- |
| Run | [42644891809](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42644891809) |
| Head SHA | `6db018f25c692d84347e5079e13f9e59291b79e2` |
| جابِ race | **success** (۱m۵۵s) |
| go backend / frontend v2 / EOL / node --check | success / success / success / success |
| offline guard suites | failure — همان خطا و همان exit رویِ base `da513ae9` (run [42602016590](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42602016590)) |

## اجرایِ نخستِ جاب

گام‌هایِ جاب، همه سبز:

| گام | نتیجه |
| --- | --- |
| GCC (race detector requires cgo) | success |
| Race Detector (borsd) — `go test -race -count=1 ./cmd/borsd` | success |
| Race Detector (generation runtime) — `go test -race -count=1 ./internal/generation/... ./internal/snapshot/... ./internal/pointerfile/...` | success |

## قرمزیِ کلِ run — پیش‌ازاین‌موجود، نه از این branch

کلِ run `failure` است، ولی تنها جابِ قرمز `offline guard suites (python dev/run_all_tests.py)`
است و علت، گاردِ ایزولاسیونِ DB است:

```
[gate] unisolated invocation — delegating to dev/gate_db_guard.py
PROTECTED_DB_UNCHANGED logical_total=04137b38…
```

همین جاب روی خودِ base `da513ae939c26ed525465b6f85d305057da7ecf9` (run [42602016590](https://github.com/johnwarchief/BorsTerminal-src/actions/runs/42602016590)) هم
قرمز است و سایرِ جاب‌هایش سبزند — پس این قرمزی به این branch ربطی ندارد و در S11 جدا
گزارش می‌شود. طبقِ §10 فقط شکستِ واقعیِ خودِ race در دامنهٔ این جاب بود؛ چنین شکستی نبود.

## بازتولید

```bash
cd backend-go
CGO_ENABLED=1 go test -race -count=1 ./cmd/borsd
CGO_ENABLED=1 go test -race -count=1 ./internal/generation/... ./internal/snapshot/... ./internal/pointerfile/...
```

روی ویندوز race detector به GCCِ سازگار (mingw-w64) نیاز دارد؛ اگر نبود، شاهدِ معتبر
همان جابِ لینوکسیِ بالا است و نباید نتیجهٔ محلی جای آن را بگیرد.
