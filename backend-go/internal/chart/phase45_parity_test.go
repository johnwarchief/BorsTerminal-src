//go:build phase45

package chart

// phase45_parity_test.go — ابزارِ شاهدِ پاریتیِ ۳۰ نماد رویِ بانکِ آزمایشگاهی.
//
// با تگِ phase45 ساخته می‌شود و در اجرایِ معمولِ `go test ./...` وارد نمی‌شود.
// فقط‌خواندنی است و بانکِ مسیرِ P45_DB_DIR را باز می‌کند (که باید کپی باشد).

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/db"
)

func openPhase45(t *testing.T) (*Service, []string, context.Context) {
	t.Helper()
	dir := os.Getenv("P45_DB_DIR")
	symbolsFile := os.Getenv("P45_SYMBOLS")
	if dir == "" || symbolsFile == "" {
		t.Skip("P45_DB_DIR/P45_SYMBOLS not set")
	}
	raw, err := os.ReadFile(symbolsFile)
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	if err := json.Unmarshal(raw, &names); err != nil {
		t.Fatal(err)
	}
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { h.Close() })
	cal := filepath.Join(dir, "calendar", "cache.json")
	s := New(Config{
		Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: cal,
		Clock:        func() time.Time { return time.Now() },
	})
	t.Cleanup(func() { _ = s.Close() })
	return s, names, context.Background()
}

// TestPhase45DumpDerived مسیرهایِ مشتق (MA/الگوها) را کنارِ چارت می‌ریزد تا
// ثابت شود ضریبِ آن‌ها همان ضریبِ کانونیکِ چارت است، نه زنجیرهٔ دوم.
func TestPhase45DumpDerived(t *testing.T) {
	out := os.Getenv("P45_DERIVED_OUT")
	if out == "" {
		t.Skip("P45_DERIVED_OUT not set")
	}
	s, names, ctx := openPhase45(t)
	body := map[string]any{}
	for _, sym := range names {
		chartBody := s.chartDBBody(ctx, sym, 3)
		cands, _ := chartBody["candles"].([]map[string]any)
		facts, _ := chartBody["factors"].([]map[string]any)
		vols, _ := chartBody["volumes"].([]map[string]any)
		scaled := s.scaleCandles(cands, facts, vols, s.basis.Current())
		w := s.resampleFor(cleanCandles(scaled), "W", sym)
		weekly := make([]map[string]any, 0, len(w))
		for _, c := range w {
			weekly = append(weekly, map[string]any{"time": c.Time, "open": c.Open,
				"high": c.High, "low": c.Low, "close": c.Close, "volume": c.Volume})
		}
		body[sym] = map[string]any{
			"ma":       s.maBody(ctx, sym, 730),
			"patterns": s.patternsBody(ctx, sym),
			"weekly":   weekly,
		}
	}
	buf, err := json.MarshalIndent(body, "", " ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(out, append(buf, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestPhase45DumpChartDB(t *testing.T) {
	dir := os.Getenv("P45_DB_DIR")
	out := os.Getenv("P45_OUT")
	symbolsFile := os.Getenv("P45_SYMBOLS")
	if dir == "" || out == "" || symbolsFile == "" {
		t.Skip("P45_DB_DIR/P45_OUT/P45_SYMBOLS not set")
	}
	raw, err := os.ReadFile(symbolsFile)
	if err != nil {
		t.Fatal(err)
	}
	var names []string
	if err := json.Unmarshal(raw, &names); err != nil {
		t.Fatal(err)
	}
	h, err := db.Open(dir, false)
	if err != nil {
		t.Fatal(err)
	}
	defer h.Close()
	cal := filepath.Join(dir, "calendar", "cache.json")
	s := New(Config{
		Market: h.Market, User: h.User, DataDir: dir,
		CalendarPath: cal,
		Clock:        func() time.Time { return time.Now() },
	})
	defer s.Close()
	ctx := context.Background()
	body := map[string]any{}
	for _, sym := range names {
		body[sym] = s.chartDBBody(ctx, sym, 3)
	}
	buf, err := json.MarshalIndent(body, "", " ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(out, append(buf, '\n'), 0o644); err != nil {
		t.Fatal(err)
	}
}
