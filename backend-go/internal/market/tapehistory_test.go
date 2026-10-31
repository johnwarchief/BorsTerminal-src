package market

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/tapehistory"
)

// tapeService رویِ فیکسچرِ B4 می‌نشیند (همان user.db که جدول‌هایِ تاریخچه را دارد)؛
// فیکسچرِ تابلو این دو جدول را ندارد.
func tapeService(t *testing.T) *Service {
	t.Helper()
	src, err := filepath.Abs(filepath.Join("..", "fundamental", "testdata", "fixture"))
	if err != nil {
		t.Fatal(err)
	}
	dst := t.TempDir()
	for _, name := range []string{"market.db", "user.db"} {
		raw, err := os.ReadFile(filepath.Join(src, name))
		if err != nil {
			t.Fatalf("B4 fixture missing %s: %v", name, err)
		}
		if err := os.WriteFile(filepath.Join(dst, name), raw, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	h, err := db.Open(dst, true)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = h.Close() })
	return New(h, dst)
}

func getTape(t *testing.T, s *Service, target string) (int, map[string]any, *httptest.ResponseRecorder) {
	t.Helper()
	rec := httptest.NewRecorder()
	s.TapeHistory(rec, httptest.NewRequest("GET", target, nil))
	var body map[string]any
	if rec.Body.Len() > 0 {
		if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
			t.Fatalf("%s: body = %q", target, rec.Body.String())
		}
	}
	return rec.Code, body, rec
}

func TestTapeHistoryRoute(t *testing.T) {
	s := tapeService(t)
	code, body, rec := getTape(t, s, "/api/tape-history?codes=INS-%D8%B9%D8%A7%D8%AF%DB%8C01&days=20")
	if code != http.StatusOK {
		t.Fatalf("status = %d body = %s", code, rec.Body.String())
	}
	if body["status"] != "success" {
		t.Errorf("status = %v", body["status"])
	}
	if got := rec.Header().Get("Cache-Control"); got != "no-store" {
		t.Errorf("Cache-Control = %q want no-store (عینِ _ORJ_JSON)", got)
	}
	flags, _ := body["flags"].([]any)
	if len(flags) != len(tapehistory.Flags) {
		t.Fatalf("flags = %v want %v", flags, tapehistory.Flags)
	}
	for i, f := range flags {
		if f != tapehistory.Flags[i] {
			t.Errorf("flags order changed at %d: %v", i, f)
		}
	}
	days, _ := body["days"].([]any)
	if len(days) != 4 {
		t.Errorf("days = %v want the four watched days", days)
	}
	if v, ok := body["write_error"]; !ok || v != nil {
		t.Errorf("write_error must be present and null in a fresh process, got %v (ok=%v)", v, ok)
	}
	by, _ := body["by_symbol"].(map[string]any)
	if len(by) != 1 {
		t.Fatalf("by_symbol = %v want one requested code", by)
	}
	per, _ := by["INS-عادی01"].(map[string]any)
	if len(per) != len(tapehistory.Flags) {
		t.Errorf("per-symbol flags = %d want %d (placeholder loop must fill all seven)",
			len(per), len(tapehistory.Flags))
	}
}

// TestTapeHistoryEmptyCodes: بی‌`codes` تقویم و پرچم‌ها می‌آیند و `by_symbol` تهی
// است — کوئریِ بی‌`IN ()` هرگز نمی‌دود.
func TestTapeHistoryEmptyCodes(t *testing.T) {
	s := tapeService(t)
	code, body, _ := getTape(t, s, "/api/tape-history")
	if code != http.StatusOK {
		t.Fatalf("status = %d", code)
	}
	if by, _ := body["by_symbol"].(map[string]any); len(by) != 0 {
		t.Errorf("by_symbol = %v want empty", by)
	}
	if days, _ := body["days"].([]any); len(days) != 4 {
		t.Errorf("calendar should still be listed: %v", days)
	}
}

// TestTapeHistoryBadDays همان 422ِ FastAPI؛ و `days=0` صفر نیست، ۲۰ است
// (`int(days or 20)`).
func TestTapeHistoryBadDays(t *testing.T) {
	s := tapeService(t)
	code, body, _ := getTape(t, s, "/api/tape-history?days=abc")
	if code != http.StatusUnprocessableEntity {
		t.Fatalf("status = %d", code)
	}
	detail, _ := body["detail"].([]any)
	if len(detail) != 1 {
		t.Fatalf("detail = %v", body["detail"])
	}
	d, _ := detail[0].(map[string]any)
	if d["type"] != "int_parsing" {
		t.Errorf("type = %v", d["type"])
	}
	loc, _ := d["loc"].([]any)
	if len(loc) != 2 || loc[0] != "query" || loc[1] != "days" {
		t.Errorf("loc = %v want [query days]", loc)
	}

	code, body, _ = getTape(t, s, "/api/tape-history?codes=INS-%D8%B9%D8%A7%D8%AF%DB%8C01&days=0")
	if code != http.StatusOK {
		t.Fatalf("days=0 status = %d", code)
	}
	if days, _ := body["days"].([]any); len(days) != 4 {
		t.Errorf("days=0 must read as 20 (four watched days), got %v", days)
	}
}

// TestTapeHistoryRespectsCap دو چیزِ جدا: پنجاه کدِ **تکراری** یکِ کلید می‌ماند
// (dict درِ پایتون کلید را یکی می‌کند — همان کیسِ `tape_cap_codes`ِ طلایی)، و
// پنجاه کدِ **متفاوت** دقیقاً تا سقفِ ۴۰۰ بریده می‌شود. بی‌تفکیکِ این دو، یک
// `set()` اضافه هم آزمون را گول می‌زند.
func TestTapeHistoryRespectsCap(t *testing.T) {
	s := tapeService(t)
	dup := make([]string, 0, 500)
	for i := 0; i < 500; i++ {
		dup = append(dup, "INS-x")
	}
	code, body, _ := getTape(t, s, "/api/tape-history?codes="+strings.Join(dup, ",")+"&days=20")
	if code != http.StatusOK {
		t.Fatalf("dup status = %d", code)
	}
	if by, _ := body["by_symbol"].(map[string]any); len(by) != 1 {
		t.Errorf("500 identical codes must collapse to one key, got %d", len(by))
	}

	uniq := make([]string, 0, 500)
	for i := 0; i < 500; i++ {
		uniq = append(uniq, "INS-"+strconv.Itoa(i))
	}
	code, body, _ = getTape(t, s, "/api/tape-history?codes="+strings.Join(uniq, ",")+"&days=20")
	if code != http.StatusOK {
		t.Fatalf("uniq status = %d", code)
	}
	by, _ := body["by_symbol"].(map[string]any)
	if len(by) != 400 {
		t.Errorf("distinct codes in reply = %d want 400 (the cap)", len(by))
	}
}
