# B0 — پایهٔ بک‌اندِ Go و هارنسِ پاریتی (پلنِ اجرا)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** یک باینریِ Go با config، اتصالِ SQLite (market فقط‌خواندنی)، پاکتِ خطایِ سازگار با FastAPI، `/healthz`، پورتِ `internal/period` با تستِ طلایی، و ابزارِ پاریتی — همه با تست و کامیتِ مرحله‌ای.

**Architecture:** `backend-go/` یک ماژولِ Go با `cmd/borsd` (سرور) و `cmd/parity` (مقایسه‌گر) است. لایهٔ `db` تنها جایی است که SQLite باز می‌شود؛ `httpapi` تنها جایی است که JSON نوشته می‌شود؛ `period` پورتِ پایتون با وکتورهایِ طلایی است. در این مرحله هیچ مسیرِ `/api/*` پورت نمی‌شود: مسیرهایِ شناخته‌شدهٔ پایتون `501 NOT_PORTED` و ناشناخته‌ها `404` می‌گیرند، تا از روزِ اول مرزِ پوشش صادق باشد.

**Tech Stack:** Go 1.26.3 (windows/amd64، بدونِ cgo)، `net/http` استاندارد، `modernc.org/sqlite`، `log/slog`، `testing`؛ تولیدِ وکتورِ طلایی با پایتونِ همین مخزن.

**Spec:** `docs/superpowers/specs/2026-10-29-backend-go-rewrite-design.md`

## Global Constraints

- Go 1.26.3، ویندوز amd64، **بدونِ cgo**؛ ماژول `borsterminal/backend` در `backend-go/`.
- پورتِ پیش‌فرضِ Go در فاز A: **8198**؛ هارنسِ پاریتی: **8298** (Go) و **8299** (پایتون)؛ پورتِ محصول **8001** دست‌نخورده می‌ماند.
- `market.db` در فاز A فقط‌خواندنی؛ `user.db` خواندنی/نوشتنی با `busy_timeout`. **هیچ تغییرِ اسکیما، `journal_mode`، یا نوشتن در `market.db` مجاز نیست.**
- قراردادِ HTTP یخ‌زده: فقط افزودنِ فیلد. پاریتی **باگ‌به‌باگ**؛ رفعِ رفتار تصمیمِ جدا می‌خواهد.
- فیلدهایِ تازهٔ UI اول در پایتون اضافه می‌شوند؛ در این پلن فیلدِ تازه‌ای اضافه نمی‌شود.
- هیچ درخواستِ شبکه‌ای و هیچ کنترلِ ADB در تست‌ها/گیت‌ها اجرا نمی‌شود؛ هیچ کوکی/توکن/رمز خوانده یا لاگ نمی‌شود.
- هیچ DBِ عملیاتی حذف/بازنویسی نمی‌شود. تست‌ها فقط رویِ DBِ موقت یا کپی.
- هر کار: `gofmt -l` خالی، `go vet ./...` سبز، `go test ./...` سبز، **یک کامیت** با پیامِ فارسی از طریقِ heredoc و بدونِ بک‌تیک.
- `git add` همیشه با نامِ فایل؛ هرگز `git add -A` و هرگز stage کردنِ `_audit/FTS_TREND_COMPARE.csv` و `tools/market_state_probe.mts`.
- پس از هر ویرایشِ فارسی: `python dev/persian_glyph_guard.py` (فایل‌هایِ تازه پس از اولین کامیت اسکن می‌شوند).
- CRLF/LFِ فایل‌هایِ موجود حفظ شود؛ فایل‌هایِ تازه LF.

## توالیِ پلن‌ها

این پلن فقط **B0** است. هر مرحلهٔ بعدی پلنِ خودش را می‌گیرد، چون هر کدام یک زیرسیستمِ مستقل با پذیرشِ عددی است:

| پلن | مرحله | چرا جدا |
| --- | --- | --- |
| این پلن | B0 | پایه، خطاها، پریود، هارنس |
| بعدی | B1 | `/api/market` یک ماشینِ حالت‌دار است: قابِ ایستا، کشِ SWR، ETag، بازسازیِ پس‌زمینه، overlayِ `market_state` و ~۴۰۰ خط مشتقِ pandas (`api/market.py:1138`). پلنِ B1 باید با **پیلودِ واقعیِ یخ‌زده** نوشته شود. |
| بعدی | B2..B7 | مطابقِ جدولِ §۸ِ spec |

## نقشهٔ فایل‌ها

```
backend-go/
  go.mod                          module borsterminal/backend
  cmd/borsd/main.go               راه‌اندازی: config → db → httpapi → serve
  cmd/parity/main.go              مقایسهٔ دو سرور، نوشتنِ گزارش
  internal/config/config.go       پرچم‌ها، DataDir، مسیرهایِ DB
  internal/config/config_test.go
  internal/db/db.go               تنها محلِ باز کردنِ SQLite
  internal/db/db_test.go
  internal/httpapi/server.go      mux، /healthz، پاکتِ پاسخ
  internal/httpapi/errors.go      شکلِ ۴۰۴/۴۲۲/۵۰۱ عینِ FastAPI/برنامه
  internal/httpapi/routes.go      خواندنِ routes.json (فهرستِ مسیرهایِ پایتون)
  internal/httpapi/routes.json    تولیدشده — کامیت می‌شود
  internal/httpapi/server_test.go
  internal/period/period.go       پورتِ codal_periods (زیرمجموعهٔ خالص)
  internal/period/period_test.go
  internal/period/testdata/cases.json   تولیدشده — کامیت می‌شود
  internal/parity/canon.go        canonicalسازی و مقایسه
  internal/parity/canon_test.go
tools/parity/gen_routes.py        استخراجِ فهرستِ مسیرها از api/*.py
tools/parity/gen_golden.py        تولیدِ testdata/cases.json از پایتون
tools/parity/gate_b0.py           سنجشِ B0 و نوشتنِ _audit/parity/B0.json
_audit/parity/B0.json             شاهدِ گیت (کامیت می‌شود)
```

---

### Task 1: ماژول، config و CLI

**Files:**
- Create: `backend-go/go.mod`
- Create: `backend-go/internal/config/config.go`
- Create: `backend-go/internal/config/config_test.go`
- Create: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- Produces: `config.Config{Addr, DataDir, ReadOnly, NoLoops string|bool}`، `config.Load([]string, func(string) string) (Config, error)`، `Config.MarketDB() string`، `Config.UserDB() string`، ثابتِ `config.DefaultPort = 8198`.

- [ ] **Step 1: ماژول را بساز**

```
cd backend-go
go mod init borsterminal/backend
```

`go.mod` باید با `module borsterminal/backend` و `go 1.26` شروع شود.

- [ ] **Step 2: تستِ config را بنویس (قرمز)**

`backend-go/internal/config/config_test.go`:

```go
package config

import "testing"

func env(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestDefaults(t *testing.T) {
	cfg, err := Load(nil, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Addr != "127.0.0.1:8198" {
		t.Fatalf("addr = %q", cfg.Addr)
	}
	if cfg.ReadOnly || cfg.NoLoops {
		t.Fatalf("flags should default false")
	}
}

func TestPortFlagBeatsDefault(t *testing.T) {
	cfg, err := Load([]string{"--port", "8298"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.Addr != "127.0.0.1:8298" {
		t.Fatalf("addr = %q", cfg.Addr)
	}
}

func TestDataDirPrecedence(t *testing.T) {
	cfg, err := Load(nil, env(map[string]string{"BORS_DATA_DIR": "C:/data/a"}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != "C:\\data\\a" {
		t.Fatalf("env data dir = %q", cfg.DataDir)
	}
	cfg, err = Load([]string{"--db-dir", "C:/data/b"}, env(map[string]string{"BORS_DATA_DIR": "C:/data/a"}))
	if err != nil {
		t.Fatal(err)
	}
	if cfg.DataDir != "C:\\data\\b" {
		t.Fatalf("flag should win, got %q", cfg.DataDir)
	}
	if cfg.MarketDB() != "C:\\data\\b\\market.db" {
		t.Fatalf("market path = %q", cfg.MarketDB())
	}
	if cfg.UserDB() != "C:\\data\\b\\user.db" {
		t.Fatalf("user path = %q", cfg.UserDB())
	}
}

func TestReadOnlyAndNoLoops(t *testing.T) {
	cfg, err := Load([]string{"--read-only", "--no-loops"}, env(nil))
	if err != nil {
		t.Fatal(err)
	}
	if !cfg.ReadOnly || !cfg.NoLoops {
		t.Fatalf("flags not parsed: %+v", cfg)
	}
}
```

- [ ] **Step 3: اجرا کن و شکست را ببین**

Run: `cd backend-go && go test ./internal/config -v`
Expected: FAIL — `undefined: Load`.

- [ ] **Step 4: پیاده‌سازیِ حداقلی**

`backend-go/internal/config/config.go`:

```go
package config

import (
	"flag"
	"path/filepath"
	"strconv"
)

const DefaultPort = 8198

type Config struct {
	Addr     string
	DataDir  string
	ReadOnly bool
	NoLoops  bool
}

func Load(args []string, getenv func(string) string) (Config, error) {
	fs := flag.NewFlagSet("borsd", flag.ContinueOnError)
	port := fs.Int("port", DefaultPort, "listen port on 127.0.0.1")
	dir := fs.String("db-dir", "", "directory holding market.db/user.db (default: BORS_DATA_DIR or .)")
	ro := fs.Bool("read-only", false, "open market.db read-only (phase A)")
	noLoops := fs.Bool("no-loops", false, "do not start sync/fetch loops")
	if err := fs.Parse(args); err != nil {
		return Config{}, err
	}
	data := *dir
	if data == "" {
		data = getenv("BORS_DATA_DIR")
	}
	if data == "" {
		data = "."
	}
	abs, err := filepath.Abs(data)
	if err != nil {
		return Config{}, err
	}
	return Config{
		Addr:     "127.0.0.1:" + strconv.Itoa(*port),
		DataDir:  abs,
		ReadOnly: *ro,
		NoLoops:  *noLoops,
	}, nil
}

func (c Config) MarketDB() string { return filepath.Join(c.DataDir, "market.db") }
func (c Config) UserDB() string   { return filepath.Join(c.DataDir, "user.db") }
```

`backend-go/cmd/borsd/main.go` (موقت — سرور در Task 3):

```go
package main

import (
	"log"
	"os"

	"borsterminal/backend/internal/config"
)

var version = "dev"

func main() {
	cfg, err := config.Load(os.Args[1:], os.Getenv)
	if err != nil {
		log.Fatal(err)
	}
	log.Printf("borsd %s data=%s addr=%s", version, cfg.DataDir, cfg.Addr)
}
```

- [ ] **Step 5: تست را سبز کن و کامیت**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: خروجیِ `gofmt -l` خالی، تست‌ها PASS.

```bash
git add backend-go/go.mod backend-go/internal/config/config.go backend-go/internal/config/config_test.go backend-go/cmd/borsd/main.go
git commit -m "$(cat <<'EOF'
feat(go): ماژول، config و CLI بک‌اند

پورتِ پیش‌فرضِ فاز A روی 8198 است و --db-dir بر BORS_DATA_DIR تقدم دارد.
EOF
)"
```

---

### Task 2: اتصالِ SQLite (market فقط‌خواندنی)

**Files:**
- Create: `backend-go/internal/db/db.go`
- Create: `backend-go/internal/db/db_test.go`
- Modify: `backend-go/go.mod` (افزودنِ وابستگی)

**Interfaces:**
- Consumes: `config.MarketDB()`، `config.UserDB()`.
- Produces: `db.Open(dataDir string, readOnly bool) (*db.Handles, error)`، `db.Handles{Market, User *sql.DB}`، `db.ErrMarketMissing`، `db.Ping(ctx)`.

- [ ] **Step 1: وابستگی را بگیر**

Run: `cd backend-go && go get modernc.org/sqlite`
Expected: `go.mod`/`go.sum` به‌روز.

- [ ] **Step 2: تست را بنویس (قرمز)**

`backend-go/internal/db/db_test.go`:

```go
package db

import (
	"context"
	"database/sql"
	"errors"
	"path/filepath"
	"testing"
)

func makeDB(t *testing.T, name string) string {
	t.Helper()
	dir := t.TempDir()
	path := filepath.Join(dir, name)
	raw, err := sql.Open("sqlite", dsn(path, "rw"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := raw.Exec("CREATE TABLE probe(x INTEGER); INSERT INTO probe VALUES (1);"); err != nil {
		t.Fatal(err)
	}
	if err := raw.Close(); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestMarketIsReadOnly(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if _, err := h.Market.Exec("INSERT INTO probe VALUES (2)"); err == nil {
		t.Fatal("write on market.db must fail")
	}
	var n int
	if err := h.Market.QueryRow("SELECT COUNT(*) FROM probe").Scan(&n); err != nil || n != 1 {
		t.Fatalf("read failed: %v n=%d", err, n)
	}
}

func TestUserIsWritable(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if _, err := h.User.Exec("CREATE TABLE w(x INTEGER)"); err != nil {
		t.Fatalf("user.db must be writable: %v", err)
	}
}

func TestMissingMarketDB(t *testing.T) {
	_, err := Open(t.TempDir(), true)
	if !errors.Is(err, ErrMarketMissing) {
		t.Fatalf("err = %v", err)
	}
}

func TestPing(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if err := h.Ping(context.Background()); err != nil {
		t.Fatal(err)
	}
}

func TestCloseIsIdempotent(t *testing.T) {
	dir := makeDB(t, "market.db")
	h, err := Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	if err := h.Close(); err != nil {
		t.Fatal(err)
	}
	if err := h.Close(); err != nil {
		t.Fatal(err)
	}
}
```

- [ ] **Step 3: اجرا کن و شکست را ببین**

Run: `cd backend-go && go test ./internal/db -v`
Expected: FAIL — `undefined: Open`.

- [ ] **Step 4: پیاده‌سازی**

`backend-go/internal/db/db.go`:

```go
package db

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"net/url"
	"os"
	"path/filepath"

	_ "modernc.org/sqlite"
)

var ErrMarketMissing = errors.New("Database market.db not found.")

type Handles struct {
	Market *sql.DB
	User   *sql.DB
}

// DSN: مسیرِ ویندوزی باید URI شود (file:///C:/...) وگرنه modernc آن را نامِ نسبی می‌خواند.
// _pragma در DSN می‌نشیند تا هر اتصالِ استخرِ database/sql آن را بگیرد؛ Exec بعد از Open
// فقط یک اتصال را می‌گیرد و بقیه بی‌تنظیم می‌مانند.
func dsn(path, mode string) string {
	u := url.URL{Scheme: "file", Path: "/" + filepath.ToSlash(path)}
	q := u.Query()
	q.Set("mode", mode)
	q.Add("_pragma", "busy_timeout(30000)")
	q.Add("_pragma", "cache_size(-64000)")
	q.Add("_pragma", "temp_store(MEMORY)")
	q.Add("_pragma", "mmap_size(268435456)")
	u.RawQuery = q.Encode()
	return u.String()
}

func open(path, mode string) (*sql.DB, error) {
	conn, err := sql.Open("sqlite", dsn(path, mode))
	if err != nil {
		return nil, err
	}
	conn.SetMaxOpenConns(4)
	return conn, nil
}

func Open(dataDir string, readOnly bool) (*Handles, error) {
	market := filepath.Join(dataDir, "market.db")
	if _, err := os.Stat(market); err != nil {
		return nil, ErrMarketMissing
	}
	mode := "rw"
	if readOnly {
		mode = "ro"
	}
	m, err := open(market, mode)
	if err != nil {
		return nil, fmt.Errorf("open market.db: %w", err)
	}
	u, err := open(filepath.Join(dataDir, "user.db"), "rw")
	if err != nil {
		m.Close()
		return nil, fmt.Errorf("open user.db: %w", err)
	}
	return &Handles{Market: m, User: u}, nil
}

func (h *Handles) Ping(ctx context.Context) error {
	if err := h.Market.PingContext(ctx); err != nil {
		return err
	}
	return h.User.PingContext(ctx)
}

func (h *Handles) Close() error {
	var errs []error
	if h.Market != nil {
		if err := h.Market.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	if h.User != nil {
		if err := h.User.Close(); err != nil {
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}
```

- [ ] **Step 5: تست را سبز کن و کامیت**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: PASS (چهار تستِ db + تست‌هایِ config).

```bash
git add backend-go/go.mod backend-go/go.sum backend-go/internal/db/db.go backend-go/internal/db/db_test.go
git commit -m "$(cat <<'EOF'
feat(go): اتصالِ SQLite با market فقط‌خواندنی

pragmaها از DSN اعمال می‌شوند تا هر اتصالِ استخر تنظیم باشد؛
نبودِ market.db همان خطای ۵۰۰ پایتون را می‌دهد.
EOF
)"
```

---

### Task 3: فهرستِ مسیرها، پاکتِ خطا و `/healthz`

**Files:**
- Create: `tools/parity/gen_routes.py`
- Create: `backend-go/internal/httpapi/routes.json` (تولیدشده)
- Create: `backend-go/internal/httpapi/routes.go`
- Create: `backend-go/internal/httpapi/errors.go`
- Create: `backend-go/internal/httpapi/server.go`
- Create: `backend-go/internal/httpapi/server_test.go`
- Modify: `backend-go/cmd/borsd/main.go`

**Interfaces:**
- Consumes: `db.Handles`، `config.Config`.
- Produces: `httpapi.New(cfg config.Config, h *db.Handles) http.Handler`، `httpapi.Routes() []string` (فهرستِ مرتبِ مسیرهایِ شناخته‌شده)، `httpapi.WriteJSON(w, status, v)`، `httpapi.NotFound(w)`، `httpapi.NotPorted(w, route)`.

- [ ] **Step 1: تولیدکنندهٔ فهرستِ مسیرها را بنویس**

`tools/parity/gen_routes.py`:

```python
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
```

Run: `python tools/parity/gen_routes.py`
Expected: چاپِ `routes: <N>` با N نزدیک به ۱۰۳؛ فایلِ `routes.json` ساخته شود.

- [ ] **Step 2: تستِ HTTP را بنویس (قرمز)**

`backend-go/internal/httpapi/server_test.go`:

```go
package httpapi

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"borsterminal/backend/internal/config"
)

func newServer(t *testing.T) http.Handler {
	t.Helper()
	return New(config.Config{Addr: "127.0.0.1:8198", DataDir: t.TempDir(), ReadOnly: true, NoLoops: true}, nil)
}

func TestUnknownPathIsFastAPINotFound(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/api/does-not-exist", nil))
	if rec.Code != 404 {
		t.Fatalf("status = %d", rec.Code)
	}
	if strings.TrimSpace(rec.Body.String()) != `{"detail":"Not Found"}` {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestKnownButUnportedIs501(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/api/market", nil))
	if rec.Code != 501 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["code"] != "NOT_PORTED" || body["route"] != "GET /api/market" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestHealthzShape(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("GET", "/healthz", nil))
	if rec.Code != 200 {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	for _, key := range []string{"status", "version", "market_mode", "data_dir", "loops", "uptime_s"} {
		if _, ok := body[key]; !ok {
			t.Fatalf("missing %q in %s", key, rec.Body.String())
		}
	}
	if body["market_mode"] != "read-only" || body["loops"] != "off" {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestUnprocessableShape(t *testing.T) {
	rec := httptest.NewRecorder()
	Unprocessable(rec, []string{"query", "days"}, "Input should be a valid integer", "x")
	if rec.Code != 422 {
		t.Fatalf("status = %d", rec.Code)
	}
	want := `{"detail":[{"input":"x","loc":["query","days"],"msg":"Input should be a valid integer","type":"value_error"}]}`
	if strings.TrimSpace(rec.Body.String()) != want {
		t.Fatalf("body = %s", rec.Body.String())
	}
}

func TestRoutesInventoryNonEmpty(t *testing.T) {
	routes := Routes()
	if len(routes) < 90 {
		t.Fatalf("routes = %d", len(routes))
	}
	if routes[0] >= routes[len(routes)-1] {
		t.Fatalf("routes not sorted")
	}
}

func TestMethodMismatchIs404LikeFastAPI(t *testing.T) {
	rec := httptest.NewRecorder()
	newServer(t).ServeHTTP(rec, httptest.NewRequest("DELETE", "/healthz", nil))
	if rec.Code != 405 {
		t.Fatalf("status = %d", rec.Code)
	}
}
```

- [ ] **Step 3: اجرا کن و شکست را ببین**

Run: `cd backend-go && go test ./internal/httpapi -v`
Expected: FAIL — `undefined: New`.

- [ ] **Step 4: پیاده‌سازی**

`backend-go/internal/httpapi/errors.go`:

```go
package httpapi

import (
	"encoding/json"
	"net/http"
)

func WriteJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

// NotFound عینِ پاسخِ پیش‌فرضِ FastAPI است.
func NotFound(w http.ResponseWriter) {
	WriteJSON(w, http.StatusNotFound, map[string]any{"detail": "Not Found"})
}

// Unprocessable عینِ شکلِ 422ِ FastAPI؛ در B0 فقط واحد-تست می‌شود و
// پاریتیِ زندهٔ آن با اولین مسیرِ پارامتردار (B2/B3) می‌آید.
func Unprocessable(w http.ResponseWriter, loc []string, msg string, input any) {
	WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []any{map[string]any{
			"type": "value_error", "loc": loc, "msg": msg, "input": input,
		}},
	})
}

func NotPorted(w http.ResponseWriter, route string) {
	WriteJSON(w, http.StatusNotImplemented, map[string]any{
		"status": "error", "code": "NOT_PORTED", "route": route,
	})
}
```

`backend-go/internal/httpapi/routes.go`:

```go
package httpapi

import (
	_ "embed"
	"encoding/json"
)

//go:embed routes.json
var routesJSON []byte

var routeSet map[string]struct{}

func init() {
	var list []string
	if err := json.Unmarshal(routesJSON, &list); err != nil {
		panic("routes.json: " + err.Error())
	}
	routeSet = make(map[string]struct{}, len(list))
	for _, r := range list {
		routeSet[r] = struct{}{}
	}
}

func Routes() []string {
	var list []string
	for r := range routeSet {
		list = append(list, r)
	}
	for i := 1; i < len(list); i++ {
		for j := i; j > 0 && list[j] < list[j-1]; j-- {
			list[j], list[j-1] = list[j-1], list[j]
		}
	}
	return list
}
```

`backend-go/internal/httpapi/server.go`:

```go
package httpapi

import (
	"net/http"
	"runtime"
	"strings"
	"time"

	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
)

type Server struct {
	cfg     config.Config
	db      *db.Handles
	started time.Time
	rssMB   func() float64
}

func New(cfg config.Config, h *db.Handles) http.Handler {
	s := &Server{cfg: cfg, db: h, started: time.Now(), rssMB: rssMB}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /healthz", s.healthz)
	mux.HandleFunc("/", s.apiGate)
	return mux
}

func (s *Server) apiGate(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path == "/healthz" {
		w.Header().Set("Allow", "GET")
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	if !strings.HasPrefix(r.URL.Path, "/api/") {
		NotFound(w)
		return
	}
	route := r.Method + " " + r.URL.Path
	if _, known := routeSet[route]; known {
		NotPorted(w, route)
		return
	}
	NotFound(w)
}

func (s *Server) healthz(w http.ResponseWriter, r *http.Request) {
	mode := "read-write"
	if s.cfg.ReadOnly {
		mode = "read-only"
	}
	loops := "on"
	if s.cfg.NoLoops {
		loops = "off"
	}
	status := "ok"
	if s.db != nil {
		ctx, cancel := contextWithTimeout(r, 2*time.Second)
		defer cancel()
		if err := s.db.Ping(ctx); err != nil {
			status = "degraded"
		}
	}
	WriteJSON(w, http.StatusOK, map[string]any{
		"status":      status,
		"version":     version,
		"data_dir":    s.cfg.DataDir,
		"market_mode": mode,
		"loops":       loops,
		"go":          runtime.Version(),
		"uptime_s":    time.Since(s.started).Seconds(),
		"rss_mb":      s.rssMB(),
	})
}
```

`backend-go/internal/httpapi/health.go` (پلتفرمی؛ RSS با `runtime.MemStats.Sys` تا هیچ وابستگیِ سیستمی اضافه نشود):

```go
package httpapi

import (
	"context"
	"net/http"
	"runtime"
	"time"
)

var version = "dev"

func contextWithTimeout(r *http.Request, d time.Duration) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), d)
}

// rssMB: MemStats.Sys معیارِ حافظهٔ رزروشدهٔ Go است؛ RSSِ واقعی در گیتِ B0
// با tasklist سنجیده می‌شود. نامِ کلید rss_mb عمداً ثابت است تا ابزارِ گیت
// بداند کدام عدد را با سقف مقایسه کند.
func rssMB() float64 {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return float64(m.Sys) / (1024 * 1024)
}
```

`backend-go/cmd/borsd/main.go` — جایگزینِ کامل:

```go
package main

import (
	"context"
	"log"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/httpapi"
)

func main() {
	cfg, err := config.Load(os.Args[1:], os.Getenv)
	if err != nil {
		log.Fatal(err)
	}
	handles, err := db.Open(cfg.DataDir, cfg.ReadOnly)
	if err != nil {
		slog.Error("db open failed", "err", err)
		os.Exit(1)
	}
	defer handles.Close()

	srv := &http.Server{Addr: cfg.Addr, Handler: httpapi.New(cfg, handles)}
	go func() {
		slog.Info("listening", "addr", cfg.Addr, "data", cfg.DataDir, "version", version)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			slog.Error("serve failed", "err", err)
			os.Exit(1)
		}
	}()

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, os.Interrupt, syscall.SIGTERM)
	<-stop
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
}
```

نکته: `healthz` از `version`ِ پکیجِ `httpapi` می‌خواند؛ در Task 7 با `-ldflags "-X borsterminal/backend/internal/httpapi.version=<v>"` قابلِ تنظیم است و الان `dev` است.

- [ ] **Step 5: سبز کن و کامیت**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: PASS. اگر `TestMethodMismatchIs404LikeFastAPI` رویِ Go 1.26 کدِ ۴۰۵ با بدنهٔ متنی برگرداند، تست را به «۴۰۵ و `Allow: GET`» تغییر بده — FastAPI هم ۴۰۵ می‌دهد؛ شکلِ بدنه در B2 با مسیرِ واقعی قفل می‌شود.

```bash
git add tools/parity/gen_routes.py backend-go/internal/httpapi/routes.json backend-go/internal/httpapi/routes.go backend-go/internal/httpapi/errors.go backend-go/internal/httpapi/server.go backend-go/internal/httpapi/health.go backend-go/internal/httpapi/server_test.go backend-go/cmd/borsd/main.go
git commit -m "$(cat <<'EOF'
feat(go): پاکتِ خطا، healthz و فهرستِ مسیرهایِ پایتون

مسیرِ شناخته‌شدهٔ پورتنشده 501 می‌دهد و ناشناخته 404 با شکلِ FastAPI؛
گیتِ پوشش از روزِ اول صادق است.
EOF
)"
```

---

### Task 4: درزِ `BORS_DATA_DIR` در پایتون

**Files:**
- Modify: `bors_config.py:139-162` (ابتدا بدنهٔ `_work_dir`)
- Create: `dev/test_bors_data_dir_seam.py`

**Interfaces:**
- Produces: اگر `BORS_DATA_DIR` تنظیم و غیرِخالی باشد، `WORK_DIR` همان مسیرِ مطلق است؛ در غیرِ این صورت رفتارِ امروز بدونِ تغییر. `DB_PATH` و `USER_DB_PATH` از `WORK_DIR` مشتق می‌شوند.

- [ ] **Step 1: تست را بنویس (قرمز)**

`dev/test_bors_data_dir_seam.py`:

```python
# dev/test_bors_data_dir_seam.py — درزِ داده برایِ پاریتی: BORS_DATA_DIR
"""اگر BORS_DATA_DIR تنظیم باشد، WORK_DIR/DB_PATH/USER_DB_PATH از آن می‌آیند؛
اگر نباشد، رفتارِ امروز دست‌نخورده است. بدونِ شبکه، فقط فایلِ موقت."""
import importlib
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

PASS = FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print("  ok   " + name)
    else:
        FAIL += 1
        print("  FAIL " + name + (" — " + detail if detail else ""))


def main():
    old = os.environ.pop("BORS_DATA_DIR", None)
    try:
        with tempfile.TemporaryDirectory() as tmp:
            open(os.path.join(tmp, "market.db"), "wb").close()
            os.environ["BORS_DATA_DIR"] = tmp
            import bors_config
            importlib.reload(bors_config)
            check("WORK_DIR follows BORS_DATA_DIR",
                  bors_config.WORK_DIR == os.path.abspath(tmp), bors_config.WORK_DIR)
            check("DB_PATH is inside it",
                  bors_config.DB_PATH == os.path.join(os.path.abspath(tmp), "market.db"),
                  bors_config.DB_PATH)
            check("USER_DB_PATH is inside it",
                  bors_config.USER_DB_PATH == os.path.join(os.path.abspath(tmp), "user.db"),
                  bors_config.USER_DB_PATH)
        del os.environ["BORS_DATA_DIR"]
        with tempfile.TemporaryDirectory() as tmp:
            check("unset changes nothing",
                  bors_config.WORK_DIR != os.path.abspath(tmp), bors_config.WORK_DIR)
    finally:
        os.environ.pop("BORS_DATA_DIR", None)
        if old is not None:
            os.environ["BORS_DATA_DIR"] = old
        import bors_config
        importlib.reload(bors_config)
    print("bors_data_dir_seam: %d passed / %d failed" % (PASS, FAIL))
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
```

Run: `python dev/test_bors_data_dir_seam.py`
Expected: FAIL — `WORK_DIR follows BORS_DATA_DIR` (چون درز وجود ندارد).

- [ ] **Step 2: درز را بزن**

در `bors_config.py`، ابتدایِ بدنهٔ `_work_dir()` (خط ۱۳۹) پیش از `if _FROZEN:` این سه خط را اضافه کن:

```python
    override = (os.environ.get("BORS_DATA_DIR") or "").strip()
    if override:
        return os.path.abspath(override)
```

توضیحِ یک‌خطی بالایِ آن (اختیاری، اگر ابهام باقی است): «درزِ پاریتی/CI؛ در نبودِ متغیر هیچ رفتاری عوض نمی‌شود.»

- [ ] **Step 3: سبز کن**

Run: `python dev/test_bors_data_dir_seam.py`
Expected: `bors_data_dir_seam: 4 passed / 0 failed`

- [ ] **Step 4: مجموعهٔ پایتونِ مرتبط را نسنجان (فقط این تست)**

Run: `python dev/persian_glyph_guard.py`
Expected: `4 passed / 0 failed` (فایلِ تازه پس از کامیت اسکن می‌شود؛ اگر هنوز untracked است، گارد نادیده‌اش می‌گیرد و در Task 7 دوباره اجرا می‌شود).

- [ ] **Step 5: کامیت**

```bash
git add bors_config.py dev/test_bors_data_dir_seam.py
git commit -m "$(cat <<'EOF'
feat(config): درزِ BORS_DATA_DIR برایِ پاریتی

پیش‌فرض دست‌نخورده است؛ فقط وقتی متغیر تنظیم شود WORK_DIR عوض می‌شود.
EOF
)"
```

---

### Task 5: `internal/period` — پورتِ خالصِ `codal_periods` با وکتورِ طلایی

**Files:**
- Create: `tools/parity/gen_golden.py`
- Create: `backend-go/internal/period/testdata/cases.json` (تولیدشده)
- Create: `backend-go/internal/period/period.go`
- Create: `backend-go/internal/period/period_test.go`

**Interfaces:**
- Produces (همه با صفرِ Python در `nil`):
  `period.Canonicalize(any) *string`، `FromTitle(string) *string`، `MonthsFromTitle(string) *int`، `Derive(datasourceEnd, title any) (*string, string)`، `EffectiveMonths(periodEnd, periodMonths any, title string) (*int, string)`، `IsCanonical(any) bool`، `IsUndated(any) bool`، `YM(any) (int, int, bool)`، `FiscalYear(any) *string`، `DescSortKey(any) string`، `Latest([]any) *string`.

- [ ] **Step 1: تولیدکنندهٔ وکتور را بنویس**

`tools/parity/gen_golden.py`:

```python
#!/usr/bin/env python
"""وکتورهایِ طلاییِ codal_periods از خودِ پایتون → backend-go/internal/period/testdata/cases.json

رقمِ فارسی/عربی با chr ساخته می‌شود (قیدِ AGENTS.md) تا ویرایشِ دستی رقم را ندزدد.
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
import codal_periods as CP  # noqa: E402

OUT = os.path.join(ROOT, "backend-go", "internal", "period", "testdata", "cases.json")


def digits(text, base):
    table = str.maketrans("0123456789", "".join(chr(base + d) for d in range(10)))
    return text.translate(table)


def main() -> int:
    fa = lambda s: digits(s, 0x06F0)  # noqa: E731
    ar = lambda s: digits(s, 0x0660)  # noqa: E731
    raw = [
        None, "", "1405/06/31", "1405-6-31", "1405/06/31 18:10:30",
        "1405/02/301", "1405/13/45", "1405/02/30", "زمان نامعلوم",
        fa("1405/06/31"), ar("1405/06/31"), fa("1405-6-3"),
        14050631.0, 1405, " 1405/06/31 ",
    ]
    titles = [
        "", "دوره ۶ ماهه", "صورت مالی 3 ماهه منتهی به 1404/12/29",
        "مجمع از 1403/01/01 تا 1403/12/29", "بدون دوره",
        fa("دوره ۱۲ ماهه منتهی به ۱۴۰۴/۱۲/۲۹"),
    ]
    months = [None, "", "6", "6.0", "0", "13", "abc", 6, 6.0]
    ends = [None, "1404/12/29", "1404/12/29 18:00:00", "1404-12-29", "1405/13/45"]

    out = {
        "canonicalize": [{"in": c, "out": CP.canonicalize(c)} for c in raw],
        "from_title": [{"in": t, "out": CP.from_title(t)} for t in titles],
        "months_from_title": [{"in": t, "out": CP.months_from_title(t)} for t in titles],
        "derive": [{"end": e, "title": t, "out": list(CP.derive(e, t))}
                   for e in ends for t in titles[:3]],
        "effective_months": [{"end": e, "months": m, "title": t, "out": list(CP.effective_months(e, m, t))}
                             for e in ends for m in months for t in titles[:3]],
        "is_canonical": [{"in": c, "out": CP.is_canonical(c)} for c in raw],
        "is_undated": [{"in": c, "out": CP.is_undated(c)} for c in raw],
        "ym": [{"in": c, "out": list(CP.ym(c))} for c in raw],
        "fiscal_year": [{"in": c, "out": CP.fiscal_year(c)} for c in raw],
        "desc_sort_key": [{"in": c, "out": CP.desc_sort_key(c)} for c in raw],
        "latest": [{"in": xs, "out": CP.latest(xs)} for xs in
                   ([], ["1404/01/01"], ["1404/01/01", "1405/02/02"], [None, "1405/13/45"], ["1405/02/02", None])],
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    total = sum(len(v) for v in out.values())
    print("golden cases:", total, "->", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

Run: `python tools/parity/gen_golden.py`
Expected: `golden cases: <N> -> .../cases.json`

- [ ] **Step 2: تستِ Go را بنویس (قرمز)**

`backend-go/internal/period/period_test.go`:

```go
package period

import (
	"encoding/json"
	"os"
	"testing"
)

type golden struct {
	Canonicalize    []struct{ In any `json:"in"`; Out *string `json:"out"` } `json:"canonicalize"`
	FromTitle       []struct{ In string `json:"in"`; Out *string `json:"out"` } `json:"from_title"`
	MonthsFromTitle []struct{ In string `json:"in"`; Out *int `json:"out"` } `json:"months_from_title"`
	Derive          []struct{ End any `json:"end"`; Title any `json:"title"`; Out []any `json:"out"` } `json:"derive"`
	EffectiveMonths []struct{ End any `json:"end"`; Months any `json:"months"`; Title string `json:"title"`; Out []any `json:"out"` } `json:"effective_months"`
	IsCanonical     []struct{ In any `json:"in"`; Out bool `json:"out"` } `json:"is_canonical"`
	IsUndated       []struct{ In any `json:"in"`; Out bool `json:"out"` } `json:"is_undated"`
	YM              []struct{ In any `json:"in"`; Out []any `json:"out"` } `json:"ym"`
	FiscalYear      []struct{ In any `json:"in"`; Out *string `json:"out"` } `json:"fiscal_year"`
	DescSortKey     []struct{ In any `json:"in"`; Out string `json:"out"` } `json:"desc_sort_key"`
	Latest          []struct{ In []any `json:"in"`; Out *string `json:"out"` } `json:"latest"`
}

func load(t *testing.T) golden {
	t.Helper()
	raw, err := os.ReadFile("testdata/cases.json")
	if err != nil {
		t.Fatal(err)
	}
	var g golden
	if err := json.Unmarshal(raw, &g); err != nil {
		t.Fatal(err)
	}
	return g
}

func eqStr(a, b *string) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func eqInt(a, b *int) bool {
	if a == nil || b == nil {
		return a == nil && b == nil
	}
	return *a == *b
}

func TestGolden(t *testing.T) {
	g := load(t)
	for _, c := range g.Canonicalize {
		if got := Canonicalize(c.In); !eqStr(got, c.Out) {
			t.Errorf("Canonicalize(%v) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.FromTitle {
		if got := FromTitle(c.In); !eqStr(got, c.Out) {
			t.Errorf("FromTitle(%q) = %v, want %v", c.In, deref(got), deref(c.Out))
		}
	}
	for _, c := range g.MonthsFromTitle {
		if got := MonthsFromTitle(c.In); !eqInt(got, c.Out) {
			t.Errorf("MonthsFromTitle(%q) = %v, want %v", c.In, derefInt(got), derefInt(c.Out))
		}
	}
	for _, c := range g.Derive {
		p, src := Derive(c.End, c.Title)
		wantP, _ := c.Out[0].(string)
		wantS, _ := c.Out[1].(string)
		if !eqStr(p, strOrNil(wantP)) || src != wantS {
			t.Errorf("Derive(%v,%v) = %v,%q want %v,%q", c.End, c.Title, deref(p), src, wantP, wantS)
		}
	}
	for _, c := range g.EffectiveMonths {
		n, src := EffectiveMonths(c.End, c.Months, c.Title)
		wantN := -1
		if c.Out[0] != nil {
			wantN = int(c.Out[0].(float64))
		}
		wantS, _ := c.Out[1].(string)
		if (n == nil) != (wantN == -1) || (n != nil && *n != wantN) || src != wantS {
			t.Errorf("EffectiveMonths(%v,%v,%q) = %v,%q want %d,%q", c.End, c.Months, c.Title, derefInt(n), src, wantN, wantS)
		}
	}
	for _, c := range g.IsCanonical {
		if got := IsCanonical(c.In); got != c.Out {
			t.Errorf("IsCanonical(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.IsUndated {
		if got := IsUndated(c.In); got != c.Out {
			t.Errorf("IsUndated(%v) = %v", c.In, got)
		}
	}
	for _, c := range g.YM {
		y, m, ok := YM(c.In)
		wantY, wantM := -1, -1
		if c.Out[0] != nil {
			wantY = int(c.Out[0].(float64))
		}
		if c.Out[1] != nil {
			wantM = int(c.Out[1].(float64))
		}
		if ok != (wantY != -1) || (ok && (y != wantY || m != wantM)) {
			t.Errorf("YM(%v) = %d,%d,%v want %d,%d", c.In, y, m, ok, wantY, wantM)
		}
	}
	for _, c := range g.FiscalYear {
		if got := FiscalYear(c.In); !eqStr(got, c.Out) {
			t.Errorf("FiscalYear(%v) = %v", c.In, deref(got))
		}
	}
	for _, c := range g.DescSortKey {
		if got := DescSortKey(c.In); got != c.Out {
			t.Errorf("DescSortKey(%v) = %q want %q", c.In, got, c.Out)
		}
	}
	for _, c := range g.Latest {
		if got := Latest(c.In); !eqStr(got, c.Out) {
			t.Errorf("Latest(%v) = %v", c.In, deref(got))
		}
	}
}

func deref(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}

func derefInt(p *int) int {
	if p == nil {
		return -1
	}
	return *p
}

func strOrNil(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}
```

- [ ] **Step 3: اجرا کن و شکست را ببین**

Run: `cd backend-go && go test ./internal/period -v`
Expected: FAIL — `undefined: Canonicalize`.

- [ ] **Step 4: پیاده‌سازی**

`backend-go/internal/period/period.go`:

```go
package period

import (
	"fmt"
	"regexp"
	"strconv"
	"strings"
)

var (
	canonRe      = regexp.MustCompile(`^([0-9]{4})/([0-9]{2})/([0-9]{2})$`)
	looseRe      = regexp.MustCompile(`([0-9]{4})\s*[-/]\s*([0-9]{1,2})\s*[-/]\s*([0-9]{1,2})`)
	endAnchor    = regexp.MustCompile(`منتهی\s*به`)
	monthsAnchor = regexp.MustCompile(`([0-9]+)\s*ماهه`)
)

// pyStr مثلِ str(x) در پایتون برایِ انواعی که در JSONِ ورودی می‌آید.
func pyStr(v any) string {
	switch x := v.(type) {
	case string:
		return x
	case float64:
		return strconv.FormatFloat(x, 'f', -1, 64)
	case int:
		return strconv.Itoa(x)
	case int64:
		return strconv.FormatInt(x, 10)
	case bool:
		if x {
			return "True"
		}
		return "False"
	default:
		return fmt.Sprint(x)
	}
}

// digitFold: رقمِ فارسی (U+06F0..) و عربی (U+0660..) → ASCII، مثلِ _DIGITSِ پایتون.
func digitFold(s string) string {
	var b strings.Builder
	b.Grow(len(s))
	for _, r := range s {
		switch {
		case r >= '۰' && r <= '۹':
			b.WriteRune('0' + (r - '۰'))
		case r >= '٠' && r <= '٩':
			b.WriteRune('0' + (r - '٠'))
		default:
			b.WriteRune(r)
		}
	}
	return b.String()
}

func isASCIIDigit(c byte) bool { return c >= '0' && c <= '9' }

// Canonicalize پورتِ codal_periods.canonicalize است.
// تفاوتِ زبانی: RE2 نگاه‌به‌عقب ندارد، پس «(?<!\d)» و «(?!\d)» با بررسیِ بایتِ
// قبل/بعد انجام می‌شود؛ و مثلِ پایتون، **اولین** تطبیقِ عبورکرده از این دو شرط
// تصمیمِ نهایی است — اگر آن تطبیق ماه/روزِ نامعتبر داشت، None می‌دهیم و به
// تطبیقِ بعدی نمی‌رویم.
func Canonicalize(raw any) *string {
	if raw == nil {
		return nil
	}
	s := digitFold(pyStr(raw))
	for _, m := range looseRe.FindAllStringSubmatchIndex(s, -1) {
		start, end := m[0], m[1]
		if start > 0 && isASCIIDigit(s[start-1]) {
			continue
		}
		if end < len(s) && isASCIIDigit(s[end]) {
			continue
		}
		mo, err1 := strconv.Atoi(s[m[4]:m[5]])
		d, err2 := strconv.Atoi(s[m[6]:m[7]])
		if err1 != nil || err2 != nil || mo < 1 || mo > 12 || d < 1 || d > 31 {
			return nil
		}
		out := fmt.Sprintf("%s/%02d/%02d", s[m[2]:m[3]], mo, d)
		return &out
	}
	return nil
}

func FromTitle(title string) *string {
	s := title
	if m := endAnchor.FindStringIndex(s); m != nil {
		s = s[m[1]:]
	}
	return Canonicalize(s)
}

func MonthsFromTitle(title string) *int {
	m := monthsAnchor.FindStringSubmatch(digitFold(title))
	if m == nil {
		return nil
	}
	n, err := strconv.Atoi(m[1])
	if err != nil || n < 1 || n > 12 {
		return nil
	}
	return &n
}

func Derive(datasourceEnd, title any) (*string, string) {
	if pe := Canonicalize(datasourceEnd); pe != nil {
		return pe, "datasource"
	}
	if pe := Canonicalize(title); pe != nil {
		return pe, "title"
	}
	return nil, ""
}

func EffectiveMonths(periodEnd, periodMonths any, title string) (*int, string) {
	var col *int
	raw := ""
	if periodMonths != nil {
		raw = strings.TrimSpace(pyStr(periodMonths))
	}
	if raw != "" {
		if f, err := strconv.ParseFloat(raw, 64); err == nil {
			c := int(f)
			if c >= 1 && c <= 12 {
				col = &c
			}
		}
	}
	tm := MonthsFromTitle(title)
	if tm == nil {
		if col != nil {
			return col, "column"
		}
		return nil, ""
	}
	tp := FromTitle(title)
	pe := Canonicalize(periodEnd)
	if tp != nil && pe != nil && *tp != *pe {
		if col != nil {
			return col, "column"
		}
		return nil, ""
	}
	if col != nil && *col == *tm {
		return col, "column"
	}
	return tm, "title"
}

func IsCanonical(value any) bool {
	if value == nil {
		return false
	}
	return canonRe.MatchString(strings.TrimSpace(pyStr(value)))
}

func IsUndated(value any) bool { return !IsCanonical(value) }

func YM(period any) (int, int, bool) {
	pe := Canonicalize(period)
	if pe == nil {
		return 0, 0, false
	}
	parts := strings.Split(*pe, "/")
	y, _ := strconv.Atoi(parts[0])
	m, _ := strconv.Atoi(parts[1])
	return y, m, true
}

func FiscalYear(period any) *string {
	pe := Canonicalize(period)
	if pe == nil {
		return nil
	}
	y := (*pe)[:4]
	return &y
}

func DescSortKey(period any) string {
	if pe := Canonicalize(period); pe != nil {
		return *pe
	}
	return ""
}

func Latest(periods []any) *string {
	best := ""
	for _, p := range periods {
		if pe := Canonicalize(p); pe != nil && *pe > best {
			best = *pe
		}
	}
	if best == "" {
		return nil
	}
	return &best
}
```

- [ ] **Step 5: سبز کن و کامیت**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: PASS. اگر کیسی شکست، **پایتون مرجع است**؛ Go را اصلاح کن، وکتور را دست نزن.

```bash
git add tools/parity/gen_golden.py backend-go/internal/period/testdata/cases.json backend-go/internal/period/period.go backend-go/internal/period/period_test.go
git commit -m "$(cat <<'EOF'
feat(go): پورتِ خالصِ codal_periods با وکتورِ طلایی

اولین تطبیقِ معتبر تصمیمِ نهایی است و نگاه‌به‌عقبِ RE2 دستی بازسازی شد؛
وکتورها از خودِ پایتون تولید و کامیت شده‌اند.
EOF
)"
```

---

### Task 6: canonicalسازی و ابزارِ پاریتی

**Files:**
- Create: `backend-go/internal/parity/canon.go`
- Create: `backend-go/internal/parity/canon_test.go`
- Create: `backend-go/cmd/parity/main.go`
- Create: `backend-go/cmd/parity/main_test.go`

**Interfaces:**
- Produces: `parity.Compare(want, got any, opts Options) Result`، `parity.Options{Exclude []string}`، `parity.Result{Pass bool, Diffs []string, MaxDelta float64, Excluded []string}`، `parity.CaseReport` و `parity.Report` با تگ‌هایِ JSON؛ `cmd/parity --py URL --go URL --cases file.json --out file.json`.

- [ ] **Step 1: تست را بنویس (قرمز)**

`backend-go/internal/parity/canon_test.go`:

```go
package parity

import (
	"encoding/json"
	"testing"
)

func decode(t *testing.T, s string) any {
	t.Helper()
	var v any
	if err := json.Unmarshal([]byte(s), &v); err != nil {
		t.Fatal(err)
	}
	return v
}

func TestKeyOrderIrrelevant(t *testing.T) {
	r := Compare(decode(t, `{"a":1,"b":"x"}`), decode(t, `{"b":"x","a":1}`), Options{})
	if !r.Pass {
		t.Fatalf("diffs=%v", r.Diffs)
	}
}

func TestNumberForms(t *testing.T) {
	r := Compare(decode(t, `{"a":1.0}`), decode(t, `{"a":1}`), Options{})
	if !r.Pass {
		t.Fatalf("1 and 1.0 must match: %v", r.Diffs)
	}
	r = Compare(decode(t, `{"a":1.0}`), decode(t, `{"a":1.0000000001}`), Options{})
	if !r.Pass || r.MaxDelta == 0 {
		t.Fatalf("1e-9 tolerance failed: %+v", r)
	}
	r = Compare(decode(t, `{"a":1}`), decode(t, `{"a":1.01}`), Options{})
	if r.Pass {
		t.Fatal("1.01 must differ")
	}
}

func TestStringExactAndArrayOrder(t *testing.T) {
	r := Compare(decode(t, `{"s":"بیداده"}`), decode(t, `{"s":"بی داده"}`), Options{})
	if r.Pass {
		t.Fatal("strings must match exactly")
	}
	r = Compare(decode(t, `[1,2]`), decode(t, `[2,1]`), Options{})
	if r.Pass {
		t.Fatal("array order matters")
	}
	r = Compare(decode(t, `[1,2]`), decode(t, `[1,2,3]`), Options{})
	if r.Pass {
		t.Fatal("length matters")
	}
}

func TestExclusionsAreExplicitPaths(t *testing.T) {
	want := decode(t, `{"meta":{"generated_at":"a","n":2}}`)
	got := decode(t, `{"meta":{"generated_at":"b","n":2}}`)
	if Compare(want, got, Options{}).Pass {
		t.Fatal("without exclusion it must differ")
	}
	r := Compare(want, got, Options{Exclude: []string{"meta.generated_at"}})
	if !r.Pass {
		t.Fatalf("excluded path still differs: %v", r.Diffs)
	}
	if len(r.Excluded) != 1 || r.Excluded[0] != "meta.generated_at" {
		t.Fatalf("excluded = %v", r.Excluded)
	}
}

func TestNullVsMissingKey(t *testing.T) {
	r := Compare(decode(t, `{"a":null}`), decode(t, `{}`), Options{})
	if r.Pass {
		t.Fatal("missing key is not null")
	}
}
```

- [ ] **Step 2: اجرا کن و شکست را ببین**

Run: `cd backend-go && go test ./internal/parity -v`
Expected: FAIL — `undefined: Compare`.

- [ ] **Step 3: پیاده‌سازی**

`backend-go/internal/parity/canon.go`:

```go
package parity

import (
	"fmt"
	"math"
	"sort"
	"strings"
)

type Options struct {
	// Exclude مسیرهایِ دقیقِ JSON است (مثلِ "meta.generated_at")؛ الگویِ عام ممنوع.
	Exclude []string
}

type Result struct {
	Pass     bool     `json:"pass"`
	Diffs    []string `json:"diffs"`
	MaxDelta float64  `json:"max_delta"`
	Excluded []string `json:"excluded"`
}

type CaseReport struct {
	Name     string   `json:"name"`
	Method   string   `json:"method"`
	Path     string   `json:"path"`
	StatusPy int      `json:"status_py"`
	StatusGo int      `json:"status_go"`
	BytesPy  int      `json:"bytes_py"`
	BytesGo  int      `json:"bytes_go"`
	Pass     bool     `json:"pass"`
	MaxDelta float64  `json:"max_delta"`
	Diffs    []string `json:"diffs,omitempty"`
	Excluded []string `json:"excluded,omitempty"`
}

type Report struct {
	Commit   string       `json:"commit"`
	PyURL    string       `json:"py_url"`
	GoURL    string       `json:"go_url"`
	DBHash   string       `json:"db_sha256"`
	Passed   int          `json:"passed"`
	Failed   int          `json:"failed"`
	Cases    []CaseReport `json:"cases"`
	Finished string       `json:"finished_at"`
}

type walker struct {
	opts     Options
	excluded map[string]struct{}
	diffs    []string
	maxDelta float64
	used     map[string]struct{}
}

func Compare(want, got any, opts Options) Result {
	w := &walker{opts: opts, excluded: map[string]struct{}{}, used: map[string]struct{}{}}
	for _, p := range opts.Exclude {
		w.excluded[p] = struct{}{}
	}
	w.walk("", want, got)
	out := Result{Pass: len(w.diffs) == 0, Diffs: w.diffs, MaxDelta: w.maxDelta}
	for p := range w.used {
		out.Excluded = append(out.Excluded, p)
	}
	sort.Strings(out.Excluded)
	return out
}

func (w *walker) isExcluded(path string) bool {
	_, ok := w.excluded[path]
	if ok {
		w.used[path] = struct{}{}
	}
	return ok
}

func (w *walker) walk(path string, want, got any) {
	if w.isExcluded(path) {
		return
	}
	switch wantV := want.(type) {
	case map[string]any:
		gotV, ok := got.(map[string]any)
		if !ok {
			w.diff(path, "type", "object", kind(got))
			return
		}
		for k, v := range wantV {
			g, exists := gotV[k]
			if !exists {
				w.diff(path+"."+k, "missing in go", "present", "absent")
				continue
			}
			w.walk(join(path, k), v, g)
		}
		for k := range gotV {
			if _, exists := wantV[k]; !exists {
				w.diff(path+"."+k, "extra in go", "absent", "present")
			}
		}
	case []any:
		gotV, ok := got.([]any)
		if !ok {
			w.diff(path, "type", "array", kind(got))
			return
		}
		if len(wantV) != len(gotV) {
			w.diff(path, "array length", fmt.Sprint(len(wantV)), fmt.Sprint(len(gotV)))
			return
		}
		for i := range wantV {
			w.walk(fmt.Sprintf("%s[%d]", path, i), wantV[i], gotV[i])
		}
	case float64:
		gotV, ok := got.(float64)
		if !ok {
			w.diff(path, "type", "number", kind(got))
			return
		}
		if wantV == gotV {
			return
		}
		if math.IsNaN(wantV) || math.IsNaN(gotV) || math.IsInf(wantV, 0) || math.IsInf(gotV, 0) {
			w.diff(path, "non-finite", fmt.Sprint(wantV), fmt.Sprint(gotV))
			return
		}
		den := math.Max(math.Abs(wantV), 1e-12)
		delta := math.Abs(gotV-wantV) / den
		if delta > w.maxDelta {
			w.maxDelta = delta
		}
		if delta > 1e-9 {
			w.diff(path, "number", fmt.Sprintf("%v", wantV), fmt.Sprintf("%v", gotV))
		}
	default:
		if fmt.Sprint(want) != fmt.Sprint(got) {
			w.diff(path, "value", fmt.Sprint(want), fmt.Sprint(got))
		}
	}
}

func (w *walker) diff(path, what, want, got string) {
	if len(w.diffs) >= 40 {
		return
	}
	w.diffs = append(w.diffs, fmt.Sprintf("%s: %s (%s != %s)", path, what, want, got))
}

func join(path, key string) string {
	if path == "" {
		return key
	}
	return path + "." + key
}

func kind(v any) string {
	switch v.(type) {
	case nil:
		return "null"
	case map[string]any:
		return "object"
	case []any:
		return "array"
	case float64:
		return "number"
	case string:
		return "string"
	case bool:
		return "bool"
	default:
		return strings.TrimSpace(fmt.Sprintf("%T", v))
	}
}
```

`backend-go/cmd/parity/main.go`:

```go
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"

	"borsterminal/backend/internal/parity"
)

type testCase struct {
	Name    string   `json:"name"`
	Method  string   `json:"method"`
	Path    string   `json:"path"`
	Exclude []string `json:"exclude"`
}

type caseFile struct {
	DBHash string     `json:"db_sha256"`
	Cases  []testCase `json:"cases"`
}

type fetched struct {
	status int
	body   []byte
	value  any
	ms     float64
}

func fetch(base string, c testCase) (fetched, error) {
	req, err := http.NewRequest(c.Method, base+c.Path, nil)
	if err != nil {
		return fetched{}, err
	}
	start := time.Now()
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fetched{}, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fetched{}, err
	}
	out := fetched{status: resp.StatusCode, body: body, ms: float64(time.Since(start).Microseconds()) / 1000.0}
	if err := json.Unmarshal(body, &out.value); err != nil {
		return fetched{}, fmt.Errorf("%s: body is not JSON: %w", c.Path, err)
	}
	return out, nil
}

func main() {
	py := flag.String("py", "http://127.0.0.1:8299", "python base URL")
	goURL := flag.String("go", "http://127.0.0.1:8298", "go base URL")
	cases := flag.String("cases", "", "cases JSON")
	out := flag.String("out", "_audit/parity/run.json", "report path")
	commit := flag.String("commit", "unknown", "git commit being measured")
	flag.Parse()
	if *cases == "" {
		fmt.Fprintln(os.Stderr, "--cases is required")
		os.Exit(2)
	}
	raw, err := os.ReadFile(*cases)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	var cf caseFile
	if err := json.Unmarshal(raw, &cf); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	report := parity.Report{Commit: *commit, PyURL: *py, GoURL: *goURL, DBHash: cf.DBHash}
	for _, c := range cf.Cases {
		row, err := compareCase(*py, *goURL, c)
		if err != nil {
			fmt.Fprintln(os.Stderr, err)
			os.Exit(2)
		}
		if row.Pass {
			report.Passed++
		} else {
			report.Failed++
		}
		report.Cases = append(report.Cases, row)
	}
	report.Finished = time.Now().UTC().Format(time.RFC3339)
	blob, _ := json.MarshalIndent(report, "", " ")
	if err := os.MkdirAll(dirOf(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	if err := os.WriteFile(*out, append(blob, '\n'), 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(2)
	}
	fmt.Printf("parity: %d passed / %d failed -> %s\n", report.Passed, report.Failed, *out)
	if report.Failed > 0 {
		os.Exit(1)
	}
}

func compareCase(pyBase, goBase string, c testCase) (parity.CaseReport, error) {
	a, err := fetch(pyBase, c)
	if err != nil {
		return parity.CaseReport{}, fmt.Errorf("py %s: %w", c.Path, err)
	}
	b, err := fetch(goBase, c)
	if err != nil {
		return parity.CaseReport{}, fmt.Errorf("go %s: %w", c.Path, err)
	}
	row := parity.CaseReport{
		Name: c.Name, Method: c.Method, Path: c.Path,
		StatusPy: a.status, StatusGo: b.status,
		BytesPy: len(a.body), BytesGo: len(b.body),
	}
	if a.status != b.status {
		row.Diffs = []string{fmt.Sprintf("status: %d != %d", a.status, b.status)}
		return row, nil
	}
	res := parity.Compare(a.value, b.value, parity.Options{Exclude: c.Exclude})
	row.Pass, row.Diffs, row.MaxDelta, row.Excluded = res.Pass, res.Diffs, res.MaxDelta, res.Excluded
	return row, nil
}

func dirOf(path string) string {
	for i := len(path) - 1; i >= 0; i-- {
		if path[i] == '/' || path[i] == '\\' {
			return path[:i]
		}
	}
	return "."
}
```

- [ ] **Step 4: تستِ CLI را بنویس (قبل از سبزکردن)**

`backend-go/cmd/parity/main_test.go`:

```go
package main

import (
	"net/http"
	"net/http/httptest"
	"testing"
)

func server(body string) *httptest.Server {
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(body))
	}))
}

func TestCompareCasePassesOnKeyOrder(t *testing.T) {
	py, gs := server(`{"a":1,"b":"x"}`), server(`{"b":"x","a":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "k", Method: "GET", Path: "/p"})
	if err != nil || !row.Pass {
		t.Fatalf("err=%v row=%+v", err, row)
	}
}

func TestCompareCaseFailsOnValue(t *testing.T) {
	py, gs := server(`{"a":1}`), server(`{"a":2}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{Name: "v", Method: "GET", Path: "/p"})
	if err != nil {
		t.Fatal(err)
	}
	if row.Pass || len(row.Diffs) == 0 {
		t.Fatalf("row=%+v", row)
	}
}

func TestCompareCaseExclusion(t *testing.T) {
	py, gs := server(`{"meta":{"t":"a"},"n":1}`), server(`{"meta":{"t":"b"},"n":1}`)
	defer py.Close()
	defer gs.Close()
	row, err := compareCase(py.URL, gs.URL, testCase{
		Name: "e", Method: "GET", Path: "/p", Exclude: []string{"meta.t"},
	})
	if err != nil || !row.Pass || len(row.Excluded) != 1 {
		t.Fatalf("err=%v row=%+v", err, row)
	}
}
```

- [ ] **Step 5: تست را سبز کن و کامیت**

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: PASS (شاملِ سه تستِ cmd/parity).

```bash
git add backend-go/internal/parity/canon.go backend-go/internal/parity/canon_test.go backend-go/cmd/parity/main.go backend-go/cmd/parity/main_test.go
git commit -m "$(cat <<'EOF'
feat(go): canonicalسازی و ابزارِ پاریتی

ترتیبِ کلید بی‌اثر، رشته دقیق، عدد صحیح برابرِ عددی و اعشاری با 1e-9 و
گزارشِ بیشینهٔ دلتا؛ حذف‌ها فقط مسیرِ صریح‌اند و در گزارش چاپ می‌شوند.
EOF
)"
```

**اصلاحیهٔ بازبینی (ruling 2026-10-29):**

- برابریِ برگ‌ها نوع‌سخت است: رشته با عدد یا بولی، و رشتهٔ «<nil>» با null هرگز برابر شمرده نمی‌شوند و اختلاف با نشانگرِ نوع گزارش می‌شود.
- استثناها بر کلیدهایِ غایب و اضافی هم اعمال می‌شوند و مسیرِ گزارش‌شده از ریشه و بدونِ نقطهٔ آغازین است.
- استثنایِ تهی (یا فقط فاصله) نادیده گرفته می‌شود و کلِ سند را سرکوب نمی‌کند.
- صفر پرونده در فایلِ cases خطای 2 است و گزارشی نوشته نمی‌شود؛ خطایِ واکشی یا بدنهٔ غیر-JSON یک پروندهٔ شکست‌خورده است، نه توقفِ اجرا.
- اختلاف‌ها به ترتیبِ کلیدِ مرتب گزارش می‌شوند و پس از 40 مورد، نشانگرِ بریده‌شدن می‌آید.

---

### Task 7: گیتِ B0 — سنجش، شاهد و گزارش

**Files:**
- Create: `tools/parity/gate_b0.py`
- Create: `_audit/parity/B0.json` (تولیدشده — کامیت می‌شود)

**Interfaces:**
- Consumes: `backend-go/bin/borsd.exe`، خروجیِ تست‌های Go.
- Produces: فایلِ `_audit/parity/B0.json` با `startup_ms`، `rss_mb`، `healthz`، `go_version`، `commit`، و سه بولیِ گیت (`startup_ok`، `rss_ok`، `tests_ok`).

- [ ] **Step 1: اسکریپتِ گیت را بنویس**

`tools/parity/gate_b0.py` (رویِ **کپیِ** DB اجرا می‌شود؛ خودِ DBِ عملیاتی فقط خوانده می‌شود):

```python
#!/usr/bin/env python
"""گیتِ B0: بیلد، تست، شروعِ سرد، RSS، healthz و نوشتنِ شاهد.

DB با backup API به یک پوشهٔ موقت کپی می‌شود تا هیچ فایلِ WAL کنارِ بانکِ
عملیاتی ساخته نشود. فقط PIDی کشته می‌شود که همین اسکریپت بالا آورده.
هیچ شبکه و هیچ ADB.
"""
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
GO = os.path.join(ROOT, "backend-go")
BIN = os.path.join(GO, "bin", "borsd.exe")
OUT = os.path.join(ROOT, "_audit", "parity", "B0.json")
PORT = 8298


def snapshot_db(src, dst):
    s = sqlite3.connect("file:%s?mode=ro" % src.replace("\\", "/"), uri=True)
    try:
        d = sqlite3.connect(dst)
        try:
            s.backup(d)
        finally:
            d.close()
    finally:
        s.close()


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def rss_mb(pid):
    rc, out = run(["tasklist", "/FI", "PID eq %d" % pid, "/FO", "CSV", "/NH"], ROOT)
    if rc != 0 or "," not in out:
        return None
    for cell in out.split(","):
        cell = cell.strip().strip('"').replace(",", "")
        if cell.endswith(" K"):
            return round(int(cell[:-2].replace(",", "")) / 1024.0, 1)
    return None


def wait_health(deadline_s=10.0):
    start = time.perf_counter()
    while time.perf_counter() - start < deadline_s:
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/healthz" % PORT, timeout=0.5) as r:
                if r.status == 200:
                    return round((time.perf_counter() - start) * 1000.0, 1), json.loads(r.read())
        except Exception:
            time.sleep(0.02)
    return None, None


def main() -> int:
    os.makedirs(os.path.join(GO, "bin"), exist_ok=True)
    rc, log = run(["go", "build", "-o", BIN, "./cmd/borsd"], GO)
    if rc != 0:
        print(log)
        return 2
    rc, tests = run(["go", "test", "./..."], GO)
    if rc != 0:
        print(tests)
        return 2
    commit = run(["git", "rev-parse", "--short", "HEAD"], ROOT)[1].strip()
    go_version = run(["go", "version"], ROOT)[1].strip()
    tmp = tempfile.mkdtemp(prefix="bors-b0-")
    try:
        for name in ("market.db", "user.db"):
            src = os.path.join(ROOT, name)
            if os.path.exists(src):
                snapshot_db(src, os.path.join(tmp, name))
        proc = subprocess.Popen(
            [BIN, "--port", str(PORT), "--read-only", "--no-loops", "--db-dir", tmp],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            startup_ms, health = wait_health()
            if startup_ms is None:
                print("healthz never came up")
                return 2
            time.sleep(1.0)
            mem = rss_mb(proc.pid)
            payload = {
                "commit": commit,
                "go_version": go_version,
                "startup_ms": startup_ms,
                "rss_mb": mem,
                "healthz": health,
                "tests_ok": True,
                "startup_ok": startup_ms < 500.0,
                "rss_ok": mem is not None and mem < 80.0,
                "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            os.makedirs(os.path.dirname(OUT), exist_ok=True)
            with open(OUT, "w", encoding="utf-8", newline="\n") as f:
                json.dump(payload, f, ensure_ascii=False, indent=1)
                f.write("\n")
            print("startup_ms=%.1f rss_mb=%s tests_ok=True" % (startup_ms, mem))
            return 0 if (payload["startup_ok"] and payload["rss_ok"]) else 1
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: اجرا کن**

Run: `python tools/parity/gate_b0.py`
Expected: `startup_ms=<...> rss_mb=<...> tests_ok=True`؛ فایلِ `_audit/parity/B0.json` ساخته شود و `startup_ok`/`rss_ok` هر دو `true`.

اگر RSSِ واقعی بالایِ ۸۰MB بود: اول `db.SetMaxOpenConns(2)` و بعد `_pragma=mmap_size(0)` را بسنج و عددِ هر دو حالت را در گزارش بنویس؛ **سقف را عوض نکن** — انحرافِ هدف رأیِ مالک می‌خواهد.

- [ ] **Step 3: گاردِ گلیف و کلِ تست**

Run: `python dev/persian_glyph_guard.py`
Expected: `4 passed / 0 failed`.

Run: `cd backend-go && gofmt -l . && go vet ./... && go test ./...`
Expected: خروجیِ خالی و PASS.

Run: `grep -rn "modernc.org/sqlite" backend-go --include=*.go | grep -v "internal/db/"`
Expected: خروجیِ خالی — تنها `internal/db` به درایورِ SQLite وابسته است.

- [ ] **Step 4: کامیت و پوش**

```bash
git add tools/parity/gate_b0.py _audit/parity/B0.json
git commit -m "$(cat <<'EOF'
test(go): گیتِ B0 با شاهدِ عددی

شروعِ سرد و RSSِ واقعی با tasklist سنجیده و در _audit/parity/B0.json ثبت شد.
EOF
)"
git push github mission/4-axes-2026-10-10
git ls-remote github refs/heads/mission/4-axes-2026-10-10
```

- [ ] **Step 5: گزارش به مالک**

جدولِ کوتاه: `startup_ms`، `rss_mb`، تعدادِ مسیرهایِ فهرست، تعدادِ وکتورِ طلایی، و نتیجهٔ `go test`. سپس پلنِ B1 نوشته می‌شود.
