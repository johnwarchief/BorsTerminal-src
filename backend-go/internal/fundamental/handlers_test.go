package fundamental

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
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
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/fundamental/sectors", s.Sectors)
	mux.HandleFunc("GET /api/fundamental/{symbol}/quarters", s.Quarters)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", target, nil))
	return rec
}

func openFixtureService(t *testing.T) *Service {
	t.Helper()
	dir := t.TempDir()
	raw, err := os.ReadFile(filepath.Join("testdata", "fixture", "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "market.db"), raw, 0o644); err != nil {
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
func TestQuartersHandlerServesGolden(t *testing.T) {
	s := openFixtureService(t)
	want := loadGolden(t, "s1", "quarters_thin")
	sym, _ := want["symbol"].(string)
	rec := serve(t, s, "/api/fundamental/"+pathEncode(sym)+"/quarters?limit=4")
	if rec.Code != http.StatusOK {
		t.Fatalf("status = %d body = %s", rec.Code, rec.Body.String())
	}
	var got map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &got); err != nil {
		t.Fatal(err)
	}
	if got["count"] != want["count"] || got["symbol"] != sym {
		t.Errorf("envelope = %v/%v want %v/%v", got["count"], got["symbol"],
			want["count"], sym)
	}
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

// contextDone نگهبانِ کرش: با ctx لغو‌شده، هندلر باید یکِ بدنهٔ سالم بدهد (نه
// panic). درِ پایتون این مسیر هیچ ctx ندارد و کوئری را تمام می‌کند؛ تفاوت فقط
// وقتی دیده می‌شود که کلاینت وسطِ درخواست برود و پاسخ به جایی نرود.
func TestHandlerRespectsCancelledContext(t *testing.T) {
	s := openFixtureService(t)
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	sym, _ := loadGolden(t, "s1", "quarters_up")["symbol"].(string)
	body := s.QuartersBody(ctx, sym, 16)
	if body["status"] != "success" || body["quarters"] == nil {
		t.Fatalf("cancelled ctx body = %+v", body)
	}
	if n, _ := body["count"].(int); n != 0 {
		t.Errorf("cancelled ctx must not return rows, got %d", n)
	}
}
