package chart

import (
	"context"
	"database/sql"
	"testing"

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
		t.Fatalf("widen failed: %+v", r)
	}
}
