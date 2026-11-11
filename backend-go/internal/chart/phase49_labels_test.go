package chart

// Phase 4.9.1 C5: the chart payload must never claim a history is
// "verified"/"live" on its own. `history_validity.status` is the authority
// (see docs/opportunity-center/phase49 FINAL-SEED-MANIFEST and the seed
// manifest counts: most symbols are `unverified`). This test pins the seed
// row to `unverified` and fails if /api/chart-db answers with a true
// `verified`/`live` flag anywhere in the body.

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
)

func writeValidityFixture(t *testing.T, dir string) {
	t.Helper()
	h, err := db.OpenWritableForTest(dir)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	if _, err := h.Market.Exec(`CREATE TABLE history_validity (
		symbol TEXT PRIMARY KEY,
		rows INTEGER,
		first_date TEXT,
		last_date TEXT,
		status TEXT NOT NULL,
		notes TEXT)`); err != nil {
		t.Fatal(err)
	}
	for _, row := range [][2]string{
		{goldUp, "unverified"},
		{goldDown, "verified"},
	} {
		if _, err := h.Market.Exec(
			"INSERT INTO history_validity(symbol, status) VALUES (?, ?)", row[0], row[1]); err != nil {
			t.Fatal(err)
		}
	}
}

func openServiceWithValidity(t *testing.T) *Service {
	t.Helper()
	dir := copyFixture(t)
	writeValidityFixture(t, dir)
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	s := New(Config{
		Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: filepath.Join("testdata", "fixture", "calendar", "cache.json"),
		Clock:        func() time.Time { return time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local) },
	})
	t.Cleanup(func() { s.Close(); h.Close() })
	return s
}

// claimLabels are the boolean keys the UI would render as a hard-coded
// "Verified"/"Live" badge. None may be true when history_validity says
// `unverified`.
var claimLabels = map[string]bool{
	"live": true, "verified": true, "is_live": true, "is_verified": true,
}

func scanClaims(t *testing.T, path string, v any) {
	t.Helper()
	switch x := v.(type) {
	case map[string]any:
		for k, child := range x {
			lk := strings.ToLower(k)
			if claimLabels[lk] {
				if b, ok := child.(bool); ok && b {
					t.Fatalf("%s.%s is true but history_validity.status is unverified", path, k)
				}
			}
			if (lk == "validity" || lk == "history_validity") && child != nil {
				inner, _ := child.(map[string]any)
				if st, _ := inner["status"].(string); st != "" && st != "unverified" {
					t.Fatalf("%s.%s.status = %q, want unverified", path, k, st)
				}
			}
			scanClaims(t, path+"."+k, child)
		}
	case []any:
		for i, child := range x {
			scanClaims(t, path+"[]", child)
			_ = i
		}
	}
}

func TestChartDBReportsNoFalseVerifiedLiveLabels(t *testing.T) {
	s := openServiceWithValidity(t)
	row := s.market.QueryRow("SELECT status FROM history_validity WHERE symbol = ?", goldUp)
	var status string
	if err := row.Scan(&status); err != nil {
		t.Fatalf("validity fixture row: %v", err)
	}
	if status != "unverified" {
		t.Fatalf("fixture status = %q, want unverified", status)
	}

	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/chart-db/{symbol}", s.ChartDB)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/chart-db/"+goldUp, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("chart-db status = %d body=%s", rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "success" {
		t.Fatalf("chart-db body status = %v", body["status"])
	}
	scanClaims(t, "$", body)
}
