package main

import (
	"bytes"
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/codal"
	"borsterminal/backend/internal/db"
)

func TestAuditUniverseCLI(t *testing.T) {
	ctx := context.Background()
	tmp := t.TempDir()
	marketPath := filepath.Join(tmp, "market.db")

	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}

	// Seed test schema and data
	ddl := `
	CREATE TABLE instruments (ins_code TEXT PRIMARY KEY, l_val18 TEXT, l_val30 TEXT, sector_code TEXT, sector_name TEXT);
	CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, p_closing REAL);
	CREATE TABLE client_type (ins_code TEXT, d_even INTEGER, buy_i_vol REAL);
	CREATE TABLE client_type_value (ins_code TEXT, d_even INTEGER, buy_i_val REAL);
	CREATE TABLE price_adjust_events (ins_code TEXT, d_even INTEGER, symbol TEXT, PRIMARY KEY (ins_code, d_even));
	CREATE TABLE share_change_events (ins_code TEXT, d_even INTEGER, symbol TEXT, PRIMARY KEY (ins_code, d_even));
	CREATE TABLE codal_notices (tracing_no INTEGER, symbol TEXT, title TEXT, letter_code TEXT, sent_date TEXT, publish_date TEXT, processed_at TEXT);
	CREATE TABLE financial_statements (tracing_no INTEGER, symbol TEXT, period_end TEXT, revenue REAL);
	CREATE TABLE monthly_sales (tracing_no INTEGER, symbol TEXT, year INTEGER, month INTEGER, monthly_revenue REAL);
	CREATE TABLE codal_quarantine (tracing_no INTEGER, symbol TEXT, report_type TEXT, reason TEXT, raw_content TEXT, quarantined_at TEXT);
	CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INTEGER, verdict TEXT);
	CREATE TABLE pipeline_dirty (symbol TEXT, source TEXT, created_at_utc TEXT, PRIMARY KEY (symbol, source));

	INSERT INTO instruments VALUES ('1001', 'فولاد', 'فولاد مبارکه', '27', 'فلزات اساسی');
	INSERT INTO instruments VALUES ('1002', 'شستا', 'تامین اجتماعی', '39', 'سرمایه گذاری');
	INSERT INTO market_watch VALUES ('1001', 5000);
	INSERT INTO market_watch VALUES ('1002', 1200);
	INSERT INTO client_type VALUES ('1001', 20261101, 1000);
	INSERT INTO client_type_value VALUES ('1001', 20261101, 5000000);
	INSERT INTO price_adjust_events VALUES ('1001', 20261015, 'فولاد');
	INSERT INTO share_change_events VALUES ('1001', 20261015, 'فولاد');

	-- 1 duplicate tracing_no
	INSERT INTO codal_notices VALUES (999, 'فولاد', 'گزارش 1', 'ن-۱', '1405/08/01', '1405/08/01', '2026-11-08');
	INSERT INTO codal_notices VALUES (999, 'فولاد', 'گزارش 1 کپی', 'ن-۱', '1405/08/01', '1405/08/01', '2026-11-08');

	-- monthly sales with month sequence gap: 1405/01 to 1405/04 (missing 02, 03)
	INSERT INTO monthly_sales VALUES (101, 'فولاد', 1405, 1, 10000);
	INSERT INTO monthly_sales VALUES (102, 'فولاد', 1405, 4, 15000);

	-- quarantine record
	INSERT INTO codal_quarantine VALUES (555, 'فولاد', 'monthly', 'unsupported unit', '{}', '2026-11-08');

	-- FTS results
	INSERT INTO fts_results VALUES ('فولاد', 5, 'STRONG');
	`
	if _, err := dbConn.Exec(ddl); err != nil {
		dbConn.Close()
		t.Fatalf("seed data: %v", err)
	}
	dbConn.Close()

	outJSON := filepath.Join(tmp, "audit_report.json")
	var stdout, stderr bytes.Buffer
	code := Run(ctx, []string{"audit", "universe", "--data-dir=" + tmp, "--out=" + outJSON}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("audit universe failed with code %d, stderr: %s", code, stderr.String())
	}

	outStr := stdout.String()
	if !strings.Contains(outStr, "BorsTerminal Market Universe Audit Report") {
		t.Errorf("stdout does not contain report header: %s", outStr)
	}
	if !strings.Contains(outStr, "Instruments Total:       2") {
		t.Errorf("expected 2 instruments in stdout: %s", outStr)
	}
	if !strings.Contains(outStr, "Quarantined Records:     1") {
		t.Errorf("expected 1 quarantine record: %s", outStr)
	}

	// Verify JSON report
	data, err := os.ReadFile(outJSON)
	if err != nil {
		t.Fatalf("read JSON report %s: %v", outJSON, err)
	}
	var report codal.UniverseAuditReport
	if err := json.Unmarshal(data, &report); err != nil {
		t.Fatalf("unmarshal JSON report: %v", err)
	}
	if report.InstrumentCount != 2 {
		t.Errorf("expected 2 instruments, got %d", report.InstrumentCount)
	}
	if report.DuplicateNoticesCount != 1 {
		t.Errorf("expected 1 duplicate notice, got %d", report.DuplicateNoticesCount)
	}
	if report.QuarantineCount != 1 {
		t.Errorf("expected 1 quarantine, got %d", report.QuarantineCount)
	}
	if len(report.DataAnomalies) == 0 {
		t.Errorf("expected data anomalies to be detected")
	}
}

func TestCodalRecalcCLI(t *testing.T) {
	ctx := context.Background()
	tmp := t.TempDir()
	marketPath := filepath.Join(tmp, "market.db")

	dbConn, err := db.OpenRWC(marketPath)
	if err != nil {
		t.Fatalf("open market.db: %v", err)
	}

	ddl := `
	CREATE TABLE financial_statements (tracing_no INTEGER, symbol TEXT, period_end TEXT, revenue REAL);
	CREATE TABLE monthly_sales (tracing_no INTEGER, symbol TEXT, year INTEGER, month INTEGER, monthly_revenue REAL);
	CREATE TABLE pipeline_dirty (symbol TEXT, source TEXT, created_at_utc TEXT, PRIMARY KEY (symbol, source));
	CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INTEGER, verdict TEXT);

	INSERT INTO monthly_sales VALUES (1, 'فولاد', 1405, 1, 1000);
	INSERT INTO financial_statements VALUES (2, 'شستا', '1405/06/31', 2000);
	`
	if _, err := dbConn.Exec(ddl); err != nil {
		dbConn.Close()
		t.Fatalf("seed data: %v", err)
	}
	dbConn.Close()

	// 1. Recalc with specific symbol
	var stdout, stderr bytes.Buffer
	code := Run(ctx, []string{"codal", "recalc", "--data-dir=" + tmp, "--symbols=فولاد"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("recalc symbols failed: code=%d, stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Recalculating FTS for 1 specified symbols") {
		t.Errorf("unexpected stdout: %s", stdout.String())
	}

	// 2. Recalc with --all
	stdout.Reset()
	stderr.Reset()
	code = Run(ctx, []string{"codal", "recalc", "--data-dir=" + tmp, "--all"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("recalc all failed: code=%d, stderr=%s", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Full universe FTS recalculation complete") {
		t.Errorf("unexpected stdout for --all: %s", stdout.String())
	}
}
