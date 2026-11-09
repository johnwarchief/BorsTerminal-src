package chart

import (
	"bytes"
	"compress/gzip"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"testing"
)

type testPackRow struct {
	Symbol    string   `json:"symbol"`
	Timeframe string   `json:"timeframe"`
	Key       int      `json:"key"`
	DateTo    string   `json:"date_to"`
	Open      float64  `json:"open"`
	High      float64  `json:"high"`
	Low       float64  `json:"low"`
	Close     float64  `json:"close"`
	Volume    *float64 `json:"volume,omitempty"`
}

func writeTestPack(t *testing.T, dir string, rows []testPackRow, validHash bool) {
	t.Helper()
	var buf bytes.Buffer
	gz := gzip.NewWriter(&buf)
	for _, r := range rows {
		raw, err := json.Marshal(r)
		if err != nil {
			t.Fatal(err)
		}
		gz.Write(raw)
		gz.Write([]byte("\n"))
	}
	if err := gz.Close(); err != nil {
		t.Fatal(err)
	}
	barsPath := filepath.Join(dir, "wm_calendar_bars.ndjson.gz")
	if err := os.WriteFile(barsPath, buf.Bytes(), 0o644); err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(buf.Bytes())
	hash := hex.EncodeToString(sum[:])
	if !validHash {
		hash = "deadbeef"
	}
	manifest := map[string]any{
		"schema": "ra365-wm-calendar-pack-v1", "version": "test",
		"files":       map[string]string{"bars": "wm_calendar_bars.ndjson.gz"},
		"file_sha256": map[string]string{"bars": hash},
	}
	raw, _ := json.Marshal(manifest)
	if err := os.WriteFile(filepath.Join(dir, "manifest.json"), raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

func testWeekCandles() []candle {
	return []candle{
		{Time: "2026-10-17", Open: 100, High: 110, Low: 95, Close: 105, Volume: 10},
		{Time: "2026-10-18", Open: 105, High: 120, Low: 100, Close: 115, Volume: 20},
		{Time: "2026-10-19", Open: 115, High: 118, Low: 90, Close: 95, Volume: 30},
		{Time: "2026-10-20", Open: 95, High: 99, Low: 85, Close: 90, Volume: 40},
		{Time: "2026-10-21", Open: 90, High: 92, Low: 80, Close: 85, Volume: 50},
	}
}

// TestWMPackOverride: نوارِ مرجع رویِ سبدِ هفتگی/ماهانه می‌نشیند، حجم فقط وقتی
// مرجع حجم دارد، و نامِ نماد با ي/ی و ك/ک عربی یکی‌سازی می‌شود.
func TestWMPackOverride(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("BORS_WM_CALENDAR_DIR", dir)
	t.Setenv("BORS_WM_CALENDAR_DISABLE", "")
	vol := 777.0
	writeTestPack(t, dir, []testPackRow{
		// نماد با ي عربی؛ پرس‌وجو با ی فارسی.
		{Symbol: "عادي", Timeframe: "W", Key: 2963, DateTo: "2026-10-21",
			Open: 200, High: 300, Low: 150, Close: 250, Volume: &vol},
		{Symbol: "عادي", Timeframe: "M", Key: 16866, DateTo: "2026-10-22",
			Open: 400, High: 500, Low: 350, Close: 450},
	}, true)
	s := &Service{}
	w := s.resampleFor(testWeekCandles(), "W", "عادی")
	if len(w) != 1 {
		t.Fatalf("weekly rows=%d", len(w))
	}
	if w[0].Open != 200 || w[0].High != 300 || w[0].Low != 150 ||
		w[0].Close != 250 || w[0].Volume != 777 || w[0].Time != "2026-10-21" {
		t.Fatalf("weekly not overridden: %+v", w[0])
	}
	m := s.resampleFor(testWeekCandles(), "M", "عادی")
	if len(m) != 1 {
		t.Fatalf("monthly rows=%d", len(m))
	}
	if m[0].Open != 400 || m[0].High != 500 || m[0].Low != 350 ||
		m[0].Close != 450 || m[0].Time != "2026-10-22" {
		t.Fatalf("monthly not overridden: %+v", m[0])
	}
	// حجمِ مرجع غایب ⇒ حجمِ تجمیعیِ محصول می‌ماند (رفتارِ row.update).
	if m[0].Volume != 150 {
		t.Fatalf("monthly volume=%v, want aggregated 150", m[0].Volume)
	}
}

// TestWMPackCorruptHashIgnored: بستهٔ دست‌کاری‌شده پذیرفته نمی‌شود و تجمیعِ
// قبلی برمی‌گردد — نه دادهٔ نیمه‌معتبر.
func TestWMPackCorruptHashIgnored(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("BORS_WM_CALENDAR_DIR", dir)
	t.Setenv("BORS_WM_CALENDAR_DISABLE", "")
	writeTestPack(t, dir, []testPackRow{
		{Symbol: "عادی", Timeframe: "W", Key: 2963, DateTo: "2026-10-21",
			Open: 200, High: 300, Low: 150, Close: 250},
	}, false)
	s := &Service{}
	if p := s.wmPack(); p != nil {
		t.Fatalf("corrupt pack must be ignored, got %d rows", len(p.rows))
	}
	w := s.resampleFor(testWeekCandles(), "W", "عادی")
	if w[0].Open != 100 || w[0].High != 120 || w[0].Low != 80 || w[0].Close != 85 {
		t.Fatalf("aggregation changed despite corrupt pack: %+v", w[0])
	}
}

// TestWMPackDisable: خاموش‌کردنِ صریح همان رفتارِ نبودِ بسته است.
func TestWMPackDisable(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("BORS_WM_CALENDAR_DIR", dir)
	t.Setenv("BORS_WM_CALENDAR_DISABLE", "1")
	writeTestPack(t, dir, []testPackRow{
		{Symbol: "عادی", Timeframe: "W", Key: 2963, DateTo: "2026-10-21",
			Open: 200, High: 300, Low: 150, Close: 250},
	}, true)
	s := &Service{}
	if p := s.wmPack(); p != nil {
		t.Fatal("disabled pack must return nil")
	}
	if w := s.resampleFor(testWeekCandles(), "W", "عادی"); w[0].Open != 100 {
		t.Fatalf("disabled pack changed aggregation: %+v", w[0])
	}
}

// TestWMPackMissingManifest: نبودِ manifest یعنی رفتارِ قبلی، نه خطا.
func TestWMPackMissingManifest(t *testing.T) {
	dir := t.TempDir()
	t.Setenv("BORS_WM_CALENDAR_DIR", dir)
	t.Setenv("BORS_WM_CALENDAR_DISABLE", "")
	if p := (&Service{}).wmPack(); p != nil {
		t.Fatal("missing manifest must yield nil pack")
	}
}

// TestWMWeekKey: شنبه‌هایِ متوالی کلیدِ متوالی می‌دهند (لنگرِ ۱۹۷۰-۰۱-۰۳).
func TestWMWeekKey(t *testing.T) {
	for i, d := range []string{"2026-10-17", "2026-10-24", "2026-10-31"} {
		k, ok := wmWeekKey(d)
		if !ok {
			t.Fatalf("parse %s", d)
		}
		if i == 0 {
			if k != 2963 {
				t.Fatalf("anchor key=%d, want 2963", k)
			}
			continue
		}
		prev, _ := wmWeekKey([]string{"2026-10-17", "2026-10-24", "2026-10-31"}[i-1])
		if k != prev+1 {
			t.Fatalf("%s key=%d, prev=%d", d, k, prev)
		}
	}
	if _, ok := wmWeekKey("not-a-date"); ok {
		t.Fatal("invalid date must fail")
	}
}

func TestWMG2JMatchesCalendar(t *testing.T) {
	cases := []struct {
		gy, gm, gd int
		jy, jm     int
	}{
		{2026, 10, 21, 1405, 7},
		{2026, 10, 23, 1405, 8},
		{2025, 3, 21, 1404, 1},
		{2024, 3, 20, 1403, 1},
	}
	for _, c := range cases {
		jy, jm, _ := g2j(c.gy, c.gm, c.gd)
		if jy != c.jy || jm != c.jm {
			t.Errorf("g2j(%d-%d-%d)=%d/%d, want %d/%d", c.gy, c.gm, c.gd, jy, jm, c.jy, c.jm)
		}
	}
	// کلیدِ ماه همان قراردادِ پایتون است (jy*12+jm-1).
	jy, jm, _ := g2j(2026, 10, 21)
	if got := fmt.Sprintf("%06d", jy*12+jm-1); got != "016866" {
		t.Fatalf("month key=%s, want 016866", got)
	}
}
