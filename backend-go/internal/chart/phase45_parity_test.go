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
