package chart

import (
	"context"
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/db"

	_ "modernc.org/sqlite"
)

func memoryDB(t *testing.T) *sql.DB {
	t.Helper()
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { db.Close() })
	return db
}

func TestMeasuredFactorEventsMissingTableFallsBack(t *testing.T) {
	s := &Service{market: memoryDB(t)}
	if _, _, ok := s.measuredFactorEvents(context.Background(), "الف"); ok {
		t.Fatal("a DB without adjustment_factors must not claim coverage")
	}
}

func TestMeasuredFactorEventsReadsRevisionAndKind(t *testing.T) {
	db := memoryDB(t)
	if _, err := db.Exec(
		"CREATE TABLE adjustment_factors(symbol TEXT, date TEXT, ratio REAL, " +
			"kind TEXT, revision TEXT)"); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(
		"INSERT INTO adjustment_factors VALUES('الف','2026-01-03',0.5," +
			"'capital_increase','rev-1')"); err != nil {
		t.Fatal(err)
	}
	s := &Service{market: db}
	events, revision, ok := s.measuredFactorEvents(context.Background(), "الف")
	if !ok || len(events) != 1 || revision != "rev-1" {
		t.Fatalf("events=%v revision=%q ok=%v", events, revision, ok)
	}
	if events[0].Date != "2026-01-03" || events[0].Ratio != 0.5 ||
		events[0].Source != "rahavard-type7-type0" {
		t.Fatalf("unexpected event: %+v", events[0])
	}
	if events[0].Extra["kind"] != "capital_increase" {
		t.Fatalf("kind not exposed: %+v", events[0].Extra)
	}
}

func TestReferenceRawHistory(t *testing.T) {
	db := memoryDB(t)
	if _, err := db.Exec(
		"CREATE TABLE reference_raw(symbol TEXT, date TEXT, open REAL, high REAL, " +
			"low REAL, close REAL, volume REAL)"); err != nil {
		t.Fatal(err)
	}
	if _, err := db.Exec(
		"INSERT INTO reference_raw VALUES('الف','2026-01-01',0,105,95,100,10)"); err != nil {
		t.Fatal(err)
	}
	s := &Service{market: db}
	rows, ok, err := s.referenceRawHistory(context.Background(), "الف")
	if err != nil || !ok || len(rows) != 1 {
		t.Fatalf("rows=%v ok=%v err=%v", rows, ok, err)
	}
	r := rows[0]
	if r["src"] != "rahavard-type0" || r["open"] != 100.0 || r["close"] != 100.0 ||
		r["volume"] != 10.0 {
		t.Fatalf("unexpected row: %+v", r)
	}
	if r["high"] != 105.0 || r["low"] != 95.0 {
		t.Fatalf("reference extremes not served verbatim: %+v", r)
	}
}

func TestReferenceRawHistoryServesLiteralExtremes(t *testing.T) {
	db := memoryDB(t)
	if _, err := db.Exec(
		"CREATE TABLE reference_raw(symbol TEXT, date TEXT, open REAL, high REAL, " +
			"low REAL, close REAL, volume REAL)"); err != nil {
		t.Fatal(err)
	}
	for _, r := range referenceLiteralRows {
		if _, err := db.Exec("INSERT INTO reference_raw VALUES(?,?,?,?,?,?,?)",
			r.symbol, r.date, r.open, r.high, r.low, r.close, r.volume); err != nil {
			t.Fatal(err)
		}
	}
	s := &Service{market: db}
	seen := map[string]bool{}
	for _, want := range referenceLiteralRows {
		rows, ok, err := s.referenceRawHistory(context.Background(), want.symbol)
		if err != nil || !ok {
			t.Fatalf("%s: ok=%v err=%v", want.symbol, ok, err)
		}
		for _, got := range rows {
			if got["date"] != want.date {
				continue
			}
			seen[want.symbol+"|"+want.date] = true
			for _, f := range []struct {
				key  string
				want float64
			}{
				{"open", want.open}, {"high", want.high}, {"low", want.low},
				{"close", want.close}, {"volume", want.volume},
				{"high_raw", want.high}, {"low_raw", want.low},
			} {
				if got[f.key] != f.want {
					t.Errorf("%s %s: %s = %v, reference says %v",
						want.symbol, want.date, f.key, got[f.key], f.want)
				}
			}
		}
	}
	if len(seen) != len(referenceLiteralRows) {
		t.Fatalf("served %d of %d reference rows", len(seen), len(referenceLiteralRows))
	}
}

func referenceZeroEventDB(t *testing.T) *sql.DB {
	t.Helper()
	db := memoryDB(t)
	for _, stmt := range []string{
		"CREATE TABLE adjustment_factors(symbol TEXT, date TEXT, ratio REAL, " +
			"kind TEXT, revision TEXT)",
		"CREATE TABLE reference_raw(symbol TEXT, date TEXT, open REAL, high REAL, " +
			"low REAL, close REAL, volume REAL, run_id TEXT, capture_sha256 TEXT)",
	} {
		if _, err := db.Exec(stmt); err != nil {
			t.Fatal(err)
		}
	}
	for _, r := range referenceLiteralRows {
		if r.symbol != referenceZeroEventSymbol {
			continue
		}
		if _, err := db.Exec("INSERT INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
			r.symbol, r.date, r.open, r.high, r.low, r.close, r.volume,
			referenceZeroEventRun, referenceZeroEventCapture); err != nil {
			t.Fatal(err)
		}
	}
	return db
}

func TestMeasuredFactorEventsCoversZeroEventReferenceSymbol(t *testing.T) {
	s := &Service{market: referenceZeroEventDB(t)}
	events, revision, ok := s.measuredFactorEvents(
		context.Background(), referenceZeroEventSymbol)
	if !ok {
		t.Fatal("a reference-covered symbol with zero events must still be covered")
	}
	if len(events) != 0 {
		t.Fatalf("zero-event symbol produced %d events", len(events))
	}
	if revision != referenceZeroEventCapture {
		t.Fatalf("revision = %q, want the capture identity %q",
			revision, referenceZeroEventCapture)
	}
}

// سنجه از خودِ HTTP می‌گذرد، نه از chartDBBody: مصرف‌کنندۀ واقعی
// (frontend-v2/useChart) همین پاسخِ /api/chart-db را می‌گیرد و wrapperِ نمایشی
// پس از price_basis اجرا می‌شود.
func TestChartDBAPIServesZeroEventReferenceSymbol(t *testing.T) {
	s := openZeroEventService(t)
	want := map[string]struct{ open, high, low, close, volume float64 }{}
	for _, r := range referenceLiteralRows {
		if r.symbol != referenceZeroEventSymbol {
			continue
		}
		want[r.date] = struct{ open, high, low, close, volume float64 }{
			r.open, r.high, r.low, r.close, r.volume}
	}
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/chart-db/{symbol}", s.ChartDB)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(
		"GET", "/api/chart-db/"+referenceZeroEventSymbol, nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("chart-db status = %d body=%s", rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["status"] != "success" {
		t.Fatalf("status = %v (%v)", body["status"], body["message"])
	}
	if body["adjustSource"] != "local-measured-factors" {
		t.Fatalf("adjustSource = %v, want local-measured-factors", body["adjustSource"])
	}
	if body["liveInjected"] != false {
		t.Fatalf("live bar injected: %v", body["liveInjected"])
	}
	candles, _ := body["candles"].([]any)
	factors, _ := body["factors"].([]any)
	if len(candles) != len(want) || len(factors) != len(want) {
		t.Fatalf("candles=%d factors=%d want=%d",
			len(candles), len(factors), len(want))
	}
	for i, raw := range candles {
		c, _ := raw.(map[string]any)
		d, _ := c["date"].(string)
		w, ok := want[d]
		if !ok {
			t.Fatalf("unexpected candle date %q", d)
		}
		for _, f := range []struct {
			key  string
			want float64
		}{
			{"open", w.open}, {"high", w.high}, {"low", w.low},
			{"close", w.close}, {"volume", w.volume},
		} {
			if c[f.key] != f.want {
				t.Errorf("%s %s = %v, reference says %v", d, f.key, c[f.key], f.want)
			}
		}
		fc, _ := factors[i].(map[string]any)
		if fc["factor"] != 1.0 {
			t.Errorf("%s factor = %v, want 1 (no measured event)", d, fc["factor"])
		}
	}
}

// market.db در Go همیشه mode=ro باز می‌شود؛ پس جدول‌های مرجع پیش از ساختنِ
// Service و از دستهٔ نوشتنیِ تست کاشته می‌شوند.
func openZeroEventService(t *testing.T) *Service {
	t.Helper()
	dir := copyFixture(t)
	w, err := db.OpenWritableForTest(dir)
	if err != nil {
		t.Fatal(err)
	}
	for _, stmt := range []string{
		"CREATE TABLE adjustment_factors(symbol TEXT, date TEXT, ratio REAL, " +
			"kind TEXT, revision TEXT)",
		"CREATE TABLE reference_raw(symbol TEXT, date TEXT, open REAL, high REAL, " +
			"low REAL, close REAL, volume REAL, run_id TEXT, capture_sha256 TEXT)",
	} {
		if _, err := w.Market.Exec(stmt); err != nil {
			t.Fatal(err)
		}
	}
	for _, r := range referenceLiteralRows {
		if r.symbol != referenceZeroEventSymbol {
			continue
		}
		if _, err := w.Market.Exec("INSERT INTO reference_raw VALUES(?,?,?,?,?,?,?,?,?)",
			r.symbol, r.date, r.open, r.high, r.low, r.close, r.volume,
			referenceZeroEventRun, referenceZeroEventCapture); err != nil {
			t.Fatal(err)
		}
	}
	w.Close()
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	s := New(Config{
		Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: filepath.Join("testdata", "fixture", "calendar", "cache.json"),
		Clock: func() time.Time {
			return time.Date(2026, 10, 28, 10, 30, 0, 0, time.Local)
		},
	})
	t.Cleanup(func() { s.Close(); h.Close() })
	return s
}
