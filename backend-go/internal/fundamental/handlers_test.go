package fundamental

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
)

// pathEncode نمادِ فارسی را برایِ مسیرِ درخواست درصد-کدگذاری می‌کند؛ هندلر باید
// همان چیزی که FastAPI از مسیرِ decode شده می‌گیرد ببیند، نه بایتِ خام.
func pathEncode(s string) string { return url.PathEscape(s) }

// serve با همان الگویِ ثبتِ internal/httpapi جواب می‌دهد، تا `PathValue` و
// اعتبارسنجیِ کوئری درِ همان ترتیبِ واقعیِ مسیر سنجیده شوند.
func serve(t *testing.T, s *Service, target string) *httptest.ResponseRecorder {
	t.Helper()
	return serveCtx(t, s, context.Background(), target)
}

func serveCtx(t *testing.T, s *Service, ctx context.Context,
	target string) *httptest.ResponseRecorder {
	t.Helper()
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/fundamental/sectors", s.Sectors)
	mux.HandleFunc("GET /api/fundamental/{symbol}/quarters", s.Quarters)
	mux.HandleFunc("GET /api/fundamental/{symbol}", s.Card)
	rec := httptest.NewRecorder()
	req := httptest.NewRequest("GET", target, nil).WithContext(ctx)
	mux.ServeHTTP(rec, req)
	return rec
}

// copyFixture فیکسچرِ یخ‌زدۀ تسکِ ۱ را درِ پوشۀ موقت می‌گذارد؛ بانکِ ریشه هرگز
// باز نمی‌شود (قیدِ گیت‌ها) و هر نوشتنی فقط رویِ همین کپی است.
func copyFixture(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		raw, err := os.ReadFile(filepath.Join("testdata", "fixture", name))
		if err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, name), raw, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func openFixtureService(t *testing.T) *Service {
	t.Helper()
	h, err := db.Open(copyFixture(t), true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	s := New(h.Market)
	t.Cleanup(func() { _ = s.Close() })
	return s
}

// brokenFixtureService همان کپی را می‌سازد و یکِ جدول را می‌اندازد، تا خطایِ
// SQLite واقعی باشد (no such table) و نه یکِ حدسِ درونِ تستِ واحد.
func brokenFixtureService(t *testing.T, table string) *Service {
	t.Helper()
	dir := copyFixture(t)
	conn, err := sql.Open("sqlite", filepath.Join(dir, "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("DROP TABLE " + table); err != nil {
		_ = conn.Close()
		t.Fatalf("drop %s: %v", table, err)
	}
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	h, err := db.Open(dir, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	s := New(h.Market)
	t.Cleanup(func() { _ = s.Close() })
	return s
}

// TestQuartersHandlerValidatesLimit همان بدنهٔ 422 که FastAPI می‌دهد: نوع، loc و
// input — و «پارس می‌شود ولی درِ رأی نقشی ندارد» (R6 برایِ months همین است).
func TestQuartersHandlerValidatesLimit(t *testing.T) {
	s := openFixtureService(t)
	sym, _ := loadGolden(t, "s1", "quarters_up")["symbol"].(string)
	if sym == "" {
		t.Fatal("golden carries no symbol to replay")
	}
	rec := serve(t, s, "/api/fundamental/"+pathEncode(sym)+"/quarters?limit=abc")
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
	var body struct {
		Detail []struct {
			Type  string   `json:"type"`
			Loc   []string `json:"loc"`
			Msg   string   `json:"msg"`
			Input string   `json:"input"`
		} `json:"detail"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if len(body.Detail) != 1 {
		t.Fatalf("detail = %s", rec.Body.String())
	}
	d := body.Detail[0]
	if d.Type != "int_parsing" || len(d.Loc) != 2 || d.Loc[0] != "query" || d.Loc[1] != "limit" ||
		d.Input != "abc" ||
		d.Msg != "Input should be a valid integer, unable to parse string as an integer" {
		t.Fatalf("422 body = %+v", d)
	}
}

// TestQuartersHandlerServesGolden نشان می‌دهد هندلر هم همان بدنهٔ طلایی را
// می‌دهد (بدنهٔ مسیر، نه فقط تابعِ داوری).
//
// کیسِ پیشین `quarters_thin` بود که `count: 0` دارد و مقایسه فقط «count و symbol»
// بود، یعنی آزمون `0 == 0` می‌کرد و هرگز قرمز نمی‌شد. اینجا همان هفتِ ردیفِ
// `quarters_up` با کلِ بدنه مقایسه می‌شود، به‌علاوه یکِ سنجهٔ مستقلِ تعدادِ ردیف
// تا خالی‌بودنِ دو طرف دیگر «برابر» خوانده نشود.
func TestQuartersHandlerServesGolden(t *testing.T) {
	s := openFixtureService(t)
	want := loadGolden(t, "s1", "quarters_up")
	sym, _ := want["symbol"].(string)
	if sym == "" {
		t.Fatal("golden carries no symbol to replay")
	}
	rec := serve(t, s, "/api/fundamental/"+pathEncode(sym)+"/quarters?limit=16")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if n, _ := got["count"].(float64); n != 7 {
		t.Fatalf("handler served count=%v want 7 rows: %s", got["count"], rec.Body.String())
	}
	compareGolden(t, "quarters_up(handler)", want, got)
}

func TestSectorsHandlerOK(t *testing.T) {
	s := openFixtureService(t)
	rec := serve(t, s, "/api/fundamental/sectors")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "success" {
		t.Fatalf("body = %s", rec.Body.String())
	}
	if n, _ := body["count"].(float64); n == 0 {
		t.Fatalf("empty sector list: %s", rec.Body.String())
	}
}

// contextDone نگهبانِ کرش: با ctx لغو‌شده هندلر باید ۵۰۰ بدهد و نه بدنهٔ
// «موفق/بی‌داده». درِ پایتون این مسیر هیچ ctx ندارد و کوئری را تمام می‌کند؛ اینجا
// کوئری لغو می‌شود و آن خطا مثلِ هر خطایِ بانک بالا می‌رود — «count: 0» رویِ
// بانکِ سالم هم دروغِ «گزارشی نیست» است، درست مثلِ بانکِ قفل‌شده.
func TestHandlerRespectsCancelledContext(t *testing.T) {
	s := openFixtureService(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	sym, _ := loadGolden(t, "s1", "quarters_up")["symbol"].(string)
	body, err := s.QuartersBody(ctx, sym, 16)
	if err == nil {
		t.Fatalf("cancelled ctx must surface an error, got body %+v", body)
	}
	if body != nil {
		t.Errorf("no success body beside an error, got %+v", body)
	}
	rec := serveCtx(t, s, ctx, "/api/fundamental/"+pathEncode(sym)+"/quarters")
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d body = %s want 500", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), `"success"`) {
		t.Fatalf("cancelled ctx served a fake success: %s", rec.Body.String())
	}
}

// TestQuarters500OnBrokenBank نقصِ اولِ پورت: SectorsBody/QuartersBody خطا را
// بلعه می‌کردند و `{"status":"success","count":0}` می‌دادند. اوراکل `try/finally`
// بی‌`except` دارد (api/fundamental.py:1992-1999 و :2251-2280)، پس SQLite error
// درِ FastAPI به ۵۰۰ می‌رسد؛ اینجا هم همان، با بدنهٔ الگوییِ خودِ مخزن
// (internal/market/service.go:178). سنجش رویِ کپیِ موقتِ فیکسچر با جدولِ انداخته.
func TestQuarters500OnBrokenBank(t *testing.T) {
	s := brokenFixtureService(t, "financial_statements")
	sym, _ := loadGolden(t, "s1", "quarters_up")["symbol"].(string)
	body, err := s.QuartersBody(context.Background(), sym, 16)
	if err == nil {
		t.Fatalf("dropping financial_statements must be an error, got %+v", body)
	}
	if body != nil {
		t.Errorf("no body beside an error, got %+v", body)
	}
	rec := serve(t, s, "/api/fundamental/"+pathEncode(sym)+"/quarters")
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d body = %s want 500", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["status"] != "error" {
		t.Fatalf("body = %s want the error envelope", rec.Body.String())
	}
	// نفیِ صریحِ دروغی که تریدر صادق به‌نظر می‌رسید: نه success، نه count: 0.
	if strings.Contains(rec.Body.String(), `"success"`) || strings.Contains(rec.Body.String(), `"count":0`) {
		t.Fatalf("a broken bank must not answer like an empty one: %s", rec.Body.String())
	}
	if msg, _ := got["message"].(string); !strings.Contains(msg, "financial_statements") {
		t.Errorf("message = %q want the SQLite error naming the missing table", msg)
	}
}

// TestSectors500OnBrokenBank همان نقص درِ `sectors`: نبودِ جدولِ ابزارها «این
// بازار صنعتی ندارد» نبود، خطاست.
func TestSectors500OnBrokenBank(t *testing.T) {
	s := brokenFixtureService(t, "instruments")
	if body, err := s.SectorsBody(context.Background()); err == nil {
		t.Fatalf("dropping instruments must be an error, got %+v", body)
	}
	rec := serve(t, s, "/api/fundamental/sectors")
	if rec.Code != http.StatusInternalServerError {
		t.Fatalf("status = %d body = %s want 500", rec.Code, rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), `"success"`) {
		t.Fatalf("fake empty sector list on a broken bank: %s", rec.Body.String())
	}
}

func TestCardHandlerOK(t *testing.T) {
	s := openFixtureService(t)
	rec := serve(t, s, "/api/fundamental/"+pathEncode("عادی01"))
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s want 200", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["status"] != "success" || got["verdict"] != "WATCH" || got["score"] != float64(4) {
		t.Fatalf("unexpected card payload: %+v", got)
	}
}

func TestCardHandlerNotFound(t *testing.T) {
	s := openFixtureService(t)
	// رقم فارسی با کدپوینت:
	symNotFound := "نیست" + string(rune(0x06F0)) + string(rune(0x06F1))
	rec := serve(t, s, "/api/fundamental/"+pathEncode(symNotFound))
	if rec.Code != http.StatusNotFound {
		t.Fatalf("status = %d body = %s want 404", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["detail"] != "Symbol not found" {
		t.Fatalf("detail = %v want 'Symbol not found'", got["detail"])
	}
}

func TestCardHandlerRouteOrder(t *testing.T) {
	s := openFixtureService(t)
	// روت sectors نباید توسط {symbol} بلعیده شود:
	rec := serve(t, s, "/api/fundamental/sectors")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s want 200", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["sectors"] == nil {
		t.Fatalf("sectors route swallowed by card route: %s", rec.Body.String())
	}
}

func TestCardHandlerValidatesMonths(t *testing.T) {
	s := openFixtureService(t)
	rec := serve(t, s, "/api/fundamental/"+pathEncode("عادی01")+"?months=abc")
	if rec.Code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d body = %s want 422", rec.Code, rec.Body.String())
	}
	var body struct {
		Detail []struct {
			Type  string   `json:"type"`
			Loc   []string `json:"loc"`
			Msg   string   `json:"msg"`
			Input string   `json:"input"`
		} `json:"detail"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if len(body.Detail) != 1 || body.Detail[0].Type != "int_parsing" || body.Detail[0].Loc[1] != "months" {
		t.Fatalf("422 detail = %+v", body.Detail)
	}
}

