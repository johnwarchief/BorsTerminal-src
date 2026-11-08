package sync

import (
	"database/sql"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestCodalPipelineHealth(t *testing.T) {
	dir := t.TempDir()
	db, err := sql.Open("sqlite", filepath.Join(dir, "market.db"))
	if err != nil {
		t.Fatal(err)
	}
	stmts := []string{
		`CREATE TABLE codal_extracted (tracing_no INTEGER, state TEXT, tried_at TEXT)`,
		`INSERT INTO codal_extracted VALUES (1,'done','2026-11-01 10:00:00')`,
		`INSERT INTO codal_extracted VALUES (2,'queued',NULL)`,
		`INSERT INTO codal_extracted VALUES (3,'failed',NULL)`,
		`INSERT INTO codal_extracted VALUES (4,'quarantined',NULL)`,
		`CREATE TABLE pipeline_dirty (symbol TEXT, axis TEXT, reason TEXT)`,
		`INSERT INTO pipeline_dirty VALUES ('فولاد','1_growth','x')`,
		`INSERT INTO pipeline_dirty VALUES ('فولاد','4_sales_to_mcap','y')`,
		`INSERT INTO pipeline_dirty VALUES ('خساپا','2_eps_trend','z')`,
		`CREATE TABLE pipeline_cursor (key TEXT, value TEXT)`,
		`INSERT INTO pipeline_cursor VALUES ('notice_gap_flag','1')`,
		`CREATE TABLE pipeline_runs (id INTEGER PRIMARY KEY, started_at TEXT, finished_at TEXT,
			cycle TEXT, phase TEXT, error TEXT, found INTEGER, enqueued INTEGER,
			processed INTEGER, done INTEGER, empty INTEGER, failed INTEGER, unresolved INTEGER)`,
		`INSERT INTO pipeline_runs VALUES (1,'2026-11-01 09:00:00','2026-11-01 09:05:00',
			'update','done',NULL,1,2,3,2,1,1,0)`,
		`CREATE TABLE codal_quarantine (tracing_no INTEGER PRIMARY KEY, symbol TEXT, reason TEXT)`,
		`INSERT INTO codal_quarantine VALUES (901, 'فولاد', 'invalid format')`,
		`CREATE TABLE fts_results (symbol TEXT PRIMARY KEY, score INTEGER, verdict TEXT, created_at TEXT)`,
		`INSERT INTO fts_results VALUES ('فولاد', 75, 'STRONG', '2026-11-08 14:00:00')`,
		`CREATE TABLE tsetmc_market_watch (ins_code TEXT PRIMARY KEY, d_even INTEGER)`,
		`INSERT INTO tsetmc_market_watch VALUES ('1001', 20261108)`,
	}
	for _, stmt := range stmts {
		if _, err := db.Exec(stmt); err != nil {
			t.Fatalf("%s: %v", stmt, err)
		}
	}
	db.Close()

	activeGen := map[string]any{
		"active_generation_dir": filepath.Join(dir, "gens", "gen_20261108"),
		"active_snapshot_set_id": "20261108T120000Z-test",
		"installed_at_utc": "2026-11-08T12:00:00Z",
	}
	rawGen, _ := json.Marshal(activeGen)
	if err := os.WriteFile(filepath.Join(dir, "active_generation.json"), rawGen, 0644); err != nil {
		t.Fatal(err)
	}

	h := NewHandler(dir)
	h.clock = func() time.Time { return time.Date(2026, 11, 4, 12, 0, 0, 0, time.Local) }
	rec := httptest.NewRecorder()
	h.CodalPipeline(rec, httptest.NewRequest(http.MethodGet, "/api/sync/codal/pipeline", nil))

	var out map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &out); err != nil {
		t.Fatal(err)
	}
	if out["status"] != "success" || out["gap_flag"] != true {
		t.Fatalf("out=%v", out)
	}
	if out["quarantine_count"].(float64) != 1 {
		t.Fatalf("expected quarantine_count 1, got %v", out["quarantine_count"])
	}
	ftsCov, ok := out["fts_coverage"].(map[string]any)
	if !ok || ftsCov["evaluated_symbols"].(float64) != 1 {
		t.Fatalf("expected fts_coverage with evaluated_symbols=1, got %v", ftsCov)
	}
	if out["last_market_sync"] != "20261108" {
		t.Fatalf("expected last_market_sync 20261108, got %v", out["last_market_sync"])
	}
	actGen, ok := out["active_generation"].(map[string]any)
	if !ok || actGen["active_snapshot_set_id"] != "20261108T120000Z-test" {
		t.Fatalf("expected active_generation in pipeline output, got %v", actGen)
	}
	q := out["queue"].(map[string]any)
	if q["queued"].(float64) != 1 || q["failed"].(float64) != 1 || q["quarantined"].(float64) != 1 {
		t.Fatalf("queue=%v", q)
	}
	if out["dirty_symbols"].(float64) != 2 {
		t.Fatalf("dirty_symbols=%v want 2 distinct symbols", out["dirty_symbols"])
	}
	lastSyncOk := out["last_successful_sync"].(map[string]any)
	if lastSyncOk["at"] != "2026-11-01 09:05:00" {
		t.Fatalf("last_successful_sync=%v", lastSyncOk)
	}
	if out["last_data_update"] != "2026-11-01 10:00:00" {
		t.Fatalf("last_data_update=%v", out["last_data_update"])
	}
}
