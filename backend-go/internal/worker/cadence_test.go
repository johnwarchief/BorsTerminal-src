package worker

import (
	"context"
	"database/sql"
	"testing"
	"time"

	_ "modernc.org/sqlite"
)

func TestCadenceManager_Defaults(t *testing.T) {
	cm := NewCadenceManager(CadenceConfig{})

	if cm.PeakInterval() != 10*time.Minute {
		t.Fatalf("expected default peak interval 10m, got %v", cm.PeakInterval())
	}
	if cm.OffPeakInterval() != 2*time.Hour {
		t.Fatalf("expected default off-peak interval 2h, got %v", cm.OffPeakInterval())
	}
	if cm.Location() == nil {
		t.Fatal("expected non-nil default location")
	}
	_, offset := time.Now().In(cm.Location()).Zone()
	if offset != 3*3600+1800 {
		t.Fatalf("expected Tehran timezone offset +03:30 (12600s), got %d", offset)
	}
}

func TestCadenceManager_PeakHours(t *testing.T) {
	cm := NewCadenceManager(CadenceConfig{
		PeakInterval:    10 * time.Minute,
		OffPeakInterval: 2 * time.Hour,
	})
	loc := cm.Location()

	// Wednesday (business day)
	// Morning window: 09:00 to 13:30
	testCases := []struct {
		name     string
		year     int
		month    time.Month
		day      int
		hour     int
		minute   int
		expected bool
	}{
		{"Wednesday 10:30 (Morning Peak)", 2026, 11, 4, 10, 30, true},
		{"Wednesday 16:00 (Afternoon Peak)", 2026, 11, 4, 16, 0, true},
		{"Saturday 09:00 (Morning Boundary Start)", 2026, 11, 7, 9, 0, true},
		{"Saturday 13:30 (Morning Boundary End)", 2026, 11, 7, 13, 30, true},
		{"Monday 15:00 (Afternoon Boundary Start)", 2026, 11, 2, 15, 0, true},
		{"Monday 19:30 (Afternoon Boundary End)", 2026, 11, 2, 19, 30, true},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			checkTime := time.Date(tc.year, tc.month, tc.day, tc.hour, tc.minute, 0, 0, loc)
			isPeak := cm.IsPeak(checkTime)
			if isPeak != tc.expected {
				t.Fatalf("%s: expected IsPeak=%v, got %v", tc.name, tc.expected, isPeak)
			}
			interval := cm.Interval(checkTime)
			expectedInterval := 10 * time.Minute
			if interval != expectedInterval {
				t.Fatalf("%s: expected Interval=%v, got %v", tc.name, expectedInterval, interval)
			}
		})
	}
}

func TestCadenceManager_OffPeakHours(t *testing.T) {
	cm := NewCadenceManager(CadenceConfig{
		PeakInterval:    10 * time.Minute,
		OffPeakInterval: 2 * time.Hour,
	})
	loc := cm.Location()

	testCases := []struct {
		name   string
		year   int
		month  time.Month
		day    int
		hour   int
		minute int
	}{
		{"Wednesday 02:00 (Night)", 2026, 11, 4, 2, 0},
		{"Wednesday 14:00 (Midday Gap)", 2026, 11, 4, 14, 0},
		{"Saturday 08:59 (Before Morning Peak)", 2026, 11, 7, 8, 59},
		{"Sunday 13:31 (After Morning Peak)", 2026, 11, 8, 13, 31},
		{"Monday 14:30 (Before Afternoon Peak)", 2026, 11, 2, 14, 30},
		{"Tuesday 19:31 (After Afternoon Peak)", 2026, 11, 3, 19, 31},
		{"Wednesday 22:00 (Late Night)", 2026, 11, 4, 22, 0},
	}

	for _, tc := range testCases {
		t.Run(tc.name, func(t *testing.T) {
			checkTime := time.Date(tc.year, tc.month, tc.day, tc.hour, tc.minute, 0, 0, loc)
			if cm.IsPeak(checkTime) {
				t.Fatalf("%s: expected off-peak, got peak", tc.name)
			}
			if interval := cm.Interval(checkTime); interval != 2*time.Hour {
				t.Fatalf("%s: expected interval 2h, got %v", tc.name, interval)
			}
		})
	}
}

func TestCadenceManager_WeekendAndThursday(t *testing.T) {
	cm := NewCadenceManager(CadenceConfig{
		PeakInterval:    10 * time.Minute,
		OffPeakInterval: 2 * time.Hour,
	})
	loc := cm.Location()

	// Friday is weekend in Iran (2026-11-06 is Friday)
	friMorning := time.Date(2026, 11, 6, 10, 30, 0, 0, loc)
	if cm.IsPeak(friMorning) {
		t.Fatal("expected Friday 10:30 to be off-peak (weekend), but got peak")
	}
	if interval := cm.Interval(friMorning); interval != 2*time.Hour {
		t.Fatalf("expected Friday interval 2h, got %v", interval)
	}

	friAfternoon := time.Date(2026, 11, 6, 16, 0, 0, 0, loc)
	if cm.IsPeak(friAfternoon) {
		t.Fatal("expected Friday 16:00 to be off-peak (weekend), but got peak")
	}
	if interval := cm.Interval(friAfternoon); interval != 2*time.Hour {
		t.Fatalf("expected Friday afternoon interval 2h, got %v", interval)
	}

	// Thursday: Morning is business (peak), Afternoon (>13:30) is off-peak
	// 2026-11-05 is Thursday
	thuMorning := time.Date(2026, 11, 5, 10, 30, 0, 0, loc)
	if !cm.IsPeak(thuMorning) {
		t.Fatal("expected Thursday 10:30 to be peak (morning business), but got off-peak")
	}
	if interval := cm.Interval(thuMorning); interval != 10*time.Minute {
		t.Fatalf("expected Thursday morning interval 10m, got %v", interval)
	}

	thuAfternoon1 := time.Date(2026, 11, 5, 14, 0, 0, 0, loc)
	if cm.IsPeak(thuAfternoon1) {
		t.Fatal("expected Thursday 14:00 to be off-peak, but got peak")
	}

	thuAfternoon2 := time.Date(2026, 11, 5, 16, 0, 0, 0, loc)
	if cm.IsPeak(thuAfternoon2) {
		t.Fatal("expected Thursday 16:00 to be off-peak, but got peak")
	}
	if interval := cm.Interval(thuAfternoon2); interval != 2*time.Hour {
		t.Fatalf("expected Thursday afternoon interval 2h, got %v", interval)
	}
}

func TestCadenceManager_AnalyzeHistoricalPeaks(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open in-memory sqlite db: %v", err)
	}
	defer db.Close()

	// Create codal_notices table
	_, err = db.Exec(`
		CREATE TABLE codal_notices (
			tracing_no INTEGER PRIMARY KEY,
			symbol TEXT,
			publish_date TEXT,
			sent_date TEXT
		);
	`)
	if err != nil {
		t.Fatalf("failed to create table: %v", err)
	}

	// Insert notices concentrated at hour 10 and hour 16, plus Persian digits
	notices := []struct {
		pub  string
		sent string
	}{
		{"1402/12/29 10:15:00", "1402/12/29 10:10:00"},
		{"1402/12/29 10:45:00", ""},
		{"1403/01/02 10:05:00", "1403/01/02 10:05:00"},
		{"۱۴۰۲/۱۲/۲۹ ۱۰:۳۰:۰۰", ""},                    // Persian digits at hour 10
		{"1403/01/05 16:20:00", "1403/01/05 16:15:00"}, // Hour 16
		{"1403/01/06 16:50:00", ""},                    // Hour 16
		{"1403/01/07 02:10:00", ""},                    // Hour 2 (single notice)
	}

	for i, n := range notices {
		_, err := db.Exec("INSERT INTO codal_notices (tracing_no, symbol, publish_date, sent_date) VALUES (?, 'FOOLAD', ?, ?)",
			i+1, n.pub, n.sent)
		if err != nil {
			t.Fatalf("failed to insert notice: %v", err)
		}
	}

	cm := NewCadenceManager(CadenceConfig{
		PeakInterval:    10 * time.Minute,
		OffPeakInterval: 2 * time.Hour,
	})

	ctx := context.Background()
	dist, err := cm.AnalyzeHistoricalPeaks(ctx, db)
	if err != nil {
		t.Fatalf("unexpected error analyzing historical peaks: %v", err)
	}

	// Verify distribution
	if dist[10] != 4 {
		t.Fatalf("expected 4 notices at hour 10, got %d", dist[10])
	}
	if dist[16] != 2 {
		t.Fatalf("expected 2 notices at hour 16, got %d", dist[16])
	}
	if dist[2] != 1 {
		t.Fatalf("expected 1 notice at hour 2, got %d", dist[2])
	}
	if dist[5] != 0 {
		t.Fatalf("expected 0 notices at hour 5, got %d", dist[5])
	}

	// Verify identified dynamic peaks include 10 and 16
	dynamicPeaks := cm.DynamicPeaks()
	if !dynamicPeaks[10] {
		t.Fatal("expected hour 10 to be identified as dynamic peak")
	}
	if !dynamicPeaks[16] {
		t.Fatal("expected hour 16 to be identified as dynamic peak")
	}

	// Verify IsPeak reflects the dynamic peaks on a business day
	loc := cm.Location()
	wednesday10 := time.Date(2026, 11, 4, 10, 0, 0, 0, loc)
	if !cm.IsPeak(wednesday10) {
		t.Fatal("expected Wednesday 10:00 to be peak under dynamic peak rules")
	}

	wednesday02 := time.Date(2026, 11, 4, 2, 0, 0, 0, loc)
	if cm.IsPeak(wednesday02) {
		t.Fatal("expected Wednesday 02:00 to be off-peak under dynamic peak rules")
	}
}

func TestCadenceManager_AnalyzeHistoricalPeaks_FallbackEmpty(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open db: %v", err)
	}
	defer db.Close()

	// Empty table
	_, _ = db.Exec("CREATE TABLE codal_notices (publish_date TEXT, sent_date TEXT)")

	cm := NewCadenceManager(CadenceConfig{})
	dist, err := cm.AnalyzeHistoricalPeaks(context.Background(), db)
	if err != nil {
		t.Fatalf("expected no error on empty table, got: %v", err)
	}
	if len(dist) != 24 {
		t.Fatalf("expected 24 hour buckets in distribution, got %d", len(dist))
	}

	// Verify fallback to default peak window
	loc := cm.Location()
	wednesdayMorning := time.Date(2026, 11, 4, 10, 30, 0, 0, loc)
	if !cm.IsPeak(wednesdayMorning) {
		t.Fatal("expected fallback to default peak window (Wednesday 10:30 should be peak)")
	}
	wednesdayNight := time.Date(2026, 11, 4, 22, 0, 0, 0, loc)
	if cm.IsPeak(wednesdayNight) {
		t.Fatal("expected Wednesday 22:00 to be off-peak")
	}
}

func TestCadenceManager_AnalyzeHistoricalPeaks_FallbackMissingTable(t *testing.T) {
	db, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open db: %v", err)
	}
	defer db.Close()

	// No codal_notices table
	cm := NewCadenceManager(CadenceConfig{})
	dist, err := cm.AnalyzeHistoricalPeaks(context.Background(), db)
	if err != nil {
		t.Fatalf("expected clean fallback without error, got: %v", err)
	}
	if len(dist) != 24 {
		t.Fatalf("expected 24 hour buckets, got %d", len(dist))
	}

	// Verify fallback to default peak window
	loc := cm.Location()
	wednesday16 := time.Date(2026, 11, 4, 16, 0, 0, 0, loc)
	if !cm.IsPeak(wednesday16) {
		t.Fatal("expected fallback to default peak window (Wednesday 16:00 should be peak)")
	}
}

func TestCadenceManager_AnalyzeHistoricalPeaks_NilDB(t *testing.T) {
	cm := NewCadenceManager(CadenceConfig{})
	dist, err := cm.AnalyzeHistoricalPeaks(context.Background(), nil)
	if err != nil {
		t.Fatalf("expected no error with nil db, got: %v", err)
	}
	if len(dist) != 24 {
		t.Fatalf("expected 24 hour buckets, got %d", len(dist))
	}
}
