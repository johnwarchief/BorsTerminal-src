package seed

import (
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"github.com/ulikunitz/xz/lzma"
)

const testSchema = `
CREATE TABLE price_history (
	symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
	close REAL, volume REAL, last REAL, value REAL, src TEXT,
	PRIMARY KEY (symbol, date));
CREATE TABLE daily_prices (
	ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
	price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
	price_change REAL, fetched_at TEXT, market_cap REAL, market_cap_src TEXT,
	z_tot_tran REAL, p_last REAL, PRIMARY KEY (ins_code, d_even));
CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, d_even INTEGER, p_closing REAL);
CREATE TABLE user_watchlists (symbol_norm TEXT PRIMARY KEY, symbol TEXT, note TEXT);
CREATE TABLE adjust_events (symbol TEXT, date TEXT, ratio REAL, source TEXT);
CREATE TABLE session_anomalies (d_even INTEGER PRIMARY KEY, cause TEXT);
`

// currentSchema is the schema of an installed database: it predates the
// seed-only adjust_events table, so the merge must create that table.
const currentSchema = `
CREATE TABLE price_history (
	symbol TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL,
	close REAL, volume REAL, last REAL, value REAL, src TEXT,
	PRIMARY KEY (symbol, date));
CREATE TABLE daily_prices (
	ins_code TEXT, d_even INTEGER, p_closing REAL, price_min REAL, price_max REAL,
	price_yesterday REAL, price_first REAL, q_tot_tran REAL, q_tot_cap REAL,
	price_change REAL, fetched_at TEXT, market_cap REAL, market_cap_src TEXT,
	z_tot_tran REAL, p_last REAL, PRIMARY KEY (ins_code, d_even));
CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY, d_even INTEGER, p_closing REAL);
CREATE TABLE user_watchlists (symbol_norm TEXT PRIMARY KEY, symbol TEXT, note TEXT);
CREATE TABLE session_anomalies (d_even INTEGER PRIMARY KEY, cause TEXT);
`

func openTestDB(t *testing.T, path string) *sql.DB {
	t.Helper()
	conn, err := db.OpenRWC(path)
	if err != nil {
		t.Fatalf("open %s: %v", path, err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	return conn
}

func execAll(t *testing.T, conn *sql.DB, stmts ...string) {
	t.Helper()
	for _, s := range stmts {
		if _, err := conn.Exec(s); err != nil {
			t.Fatalf("exec %q: %v", s, err)
		}
	}
}

func makeSeedDB(t *testing.T, path string) {
	t.Helper()
	conn := openTestDB(t, path)
	execAll(t, conn, testSchema,
		`INSERT INTO price_history VALUES ('AAA','2020-01-01',10,11,9,10.5,100,10.5,1050,'seed')`,
		`INSERT INTO price_history VALUES ('AAA','2020-01-02',11,12,10,11.5,110,11.5,1265,'seed')`,
		`INSERT INTO price_history VALUES ('BBB','2020-01-02',20,21,19,20.5,200,20.5,4100,'seed')`,
		`INSERT INTO daily_prices VALUES ('I1',20200101,10,9,11,9.5,10,100,1000,0.5,'s',100, 'seed',10,10.2)`,
		`INSERT INTO market_watch VALUES ('I1',20200101,10)`,
		`INSERT INTO market_watch VALUES ('I2',20200101,20)`,
		`INSERT INTO user_watchlists VALUES ('seed-user','SEED','must not copy')`,
		`INSERT INTO adjust_events VALUES ('AAA','2020-01-03',1.1,'seed')`,
	)
	if err := conn.Close(); err != nil {
		t.Fatalf("close seed db: %v", err)
	}
}

func makeCurrentDB(t *testing.T, path string) {
	t.Helper()
	conn := openTestDB(t, path)
	execAll(t, conn, currentSchema,
		`INSERT INTO price_history VALUES ('AAA','2025-01-01',50,51,49,50.5,500,50.5,25250,'live')`,
		`INSERT INTO daily_prices VALUES ('I1',20250101,50,49,51,49.5,50,500,5000,0.5,'l',500,'live',50,50.2)`,
		`INSERT INTO market_watch VALUES ('I1',20250101,50)`,
		`INSERT INTO session_anomalies VALUES (20250101,'halted')`,
	)
	if err := conn.Close(); err != nil {
		t.Fatalf("close current db: %v", err)
	}
}

func packLZMA(t *testing.T, dbPath, lzmaPath string) {
	t.Helper()
	src, err := os.Open(dbPath)
	if err != nil {
		t.Fatalf("open db: %v", err)
	}
	defer src.Close()
	dst, err := os.Create(lzmaPath)
	if err != nil {
		t.Fatalf("create lzma: %v", err)
	}
	w, err := lzma.NewWriter(dst)
	if err != nil {
		_ = dst.Close()
		t.Fatalf("lzma writer: %v", err)
	}
	buf := make([]byte, 1<<16)
	for {
		n, rerr := src.Read(buf)
		if n > 0 {
			if _, werr := w.Write(buf[:n]); werr != nil {
				t.Fatalf("lzma write: %v", werr)
			}
		}
		if rerr != nil {
			break
		}
	}
	if err := w.Close(); err != nil {
		t.Fatalf("lzma close: %v", err)
	}
	if err := dst.Close(); err != nil {
		t.Fatalf("close lzma: %v", err)
	}
}

func fileSHA(t *testing.T, path string) string {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("read %s: %v", path, err)
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func priceCount(t *testing.T, path string) int {
	t.Helper()
	conn := openTestDB(t, path)
	defer conn.Close()
	var n int
	if err := conn.QueryRow(`SELECT count(*) FROM price_history`).Scan(&n); err != nil {
		t.Fatalf("count price_history: %v", err)
	}
	return n
}

func TestEnsureExtractsSeedWhenDatabaseMissing(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	seedLZMA := filepath.Join(dir, "market.db.lzma")
	packLZMA(t, seedDB, seedLZMA)

	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("Ensure: %v", err)
	}
	if !res.Applied || res.Mode != ModeExtract {
		t.Fatalf("expected applied extract, got %+v", res)
	}
	dbPath := filepath.Join(dir, "market.db")
	if _, err := os.Stat(dbPath); err != nil {
		t.Fatalf("market.db missing: %v", err)
	}
	if got := priceCount(t, dbPath); got != 3 {
		t.Fatalf("price_history rows = %d, want 3", got)
	}
	raw, err := os.ReadFile(filepath.Join(dir, StateFile))
	if err != nil {
		t.Fatalf("state file: %v", err)
	}
	var st State
	if err := json.Unmarshal(raw, &st); err != nil {
		t.Fatalf("state json: %v", err)
	}
	if st.Status != StatusApplied || st.PriceHistoryRows != 3 || st.PriceHistoryFirst != "2020-01-01" {
		t.Fatalf("state = %+v", st)
	}
	if st.SourceSHA256 != fileSHA(t, seedLZMA) {
		t.Fatalf("state seed sha mismatch: %s", st.SourceSHA256)
	}
}

func TestEnsureSecondRunIsNoOp(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))

	if _, err := Ensure(Options{DataDir: dir}); err != nil {
		t.Fatalf("first Ensure: %v", err)
	}
	dbPath := filepath.Join(dir, "market.db")
	before := fileSHA(t, dbPath)
	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("second Ensure: %v", err)
	}
	if res.Applied {
		t.Fatalf("second run applied again: %+v", res)
	}
	if after := fileSHA(t, dbPath); after != before {
		t.Fatalf("market.db changed on no-op run: %s -> %s", before, after)
	}
}

func TestEnsureMergePreservesExistingAndAddsHistory(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))
	cur := filepath.Join(dir, "market.db")
	makeCurrentDB(t, cur)
	before := fileSHA(t, cur)

	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("Ensure: %v", err)
	}
	if !res.Applied || res.Mode != ModeMerge {
		t.Fatalf("expected applied merge, got %+v", res)
	}
	// seed 3 + current 1; AAA 2025 is preserved, AAA 2020 rows added.
	if got := priceCount(t, cur); got != 4 {
		t.Fatalf("price_history rows = %d, want 4", got)
	}
	conn := openTestDB(t, cur)
	var close2025 float64
	if err := conn.QueryRow(`SELECT close FROM price_history WHERE symbol='AAA' AND date='2025-01-01'`).Scan(&close2025); err != nil {
		t.Fatalf("read existing row: %v", err)
	}
	if close2025 != 50.5 {
		t.Fatalf("existing row overwritten: close=%v", close2025)
	}
	var anomalies int
	if err := conn.QueryRow(`SELECT count(*) FROM session_anomalies`).Scan(&anomalies); err != nil {
		t.Fatalf("session_anomalies: %v", err)
	}
	if anomalies != 1 {
		t.Fatalf("current-only table lost: %d", anomalies)
	}
	var userRows int
	if err := conn.QueryRow(`SELECT count(*) FROM user_watchlists`).Scan(&userRows); err != nil {
		t.Fatalf("user_watchlists: %v", err)
	}
	if userRows != 0 {
		t.Fatalf("seed user_watchlists copied into main: %d", userRows)
	}
	var boardRows int
	if err := conn.QueryRow(`SELECT count(*) FROM market_watch`).Scan(&boardRows); err != nil {
		t.Fatalf("market_watch: %v", err)
	}
	if boardRows != 1 {
		t.Fatalf("stale seed board rows copied into main: %d", boardRows)
	}
	var adj int
	if err := conn.QueryRow(`SELECT count(*) FROM adjust_events`).Scan(&adj); err != nil {
		t.Fatalf("adjust_events: %v", err)
	}
	if adj != 1 {
		t.Fatalf("seed-only table not created/filled: %d", adj)
	}
	// A recoverable backup of the pre-merge database must exist.
	backups, err := filepath.Glob(filepath.Join(dir, "backups", "market.db.before-seed-*"))
	if err != nil || len(backups) != 1 {
		t.Fatalf("backup files = %v, err=%v", backups, err)
	}
	if got := fileSHA(t, backups[0]); got != before {
		t.Fatalf("backup is not the pre-merge database")
	}
}

func TestEnsureCorruptSeedKeepsExisting(t *testing.T) {
	dir := t.TempDir()
	cur := filepath.Join(dir, "market.db")
	makeCurrentDB(t, cur)
	before := fileSHA(t, cur)
	if err := os.WriteFile(filepath.Join(dir, "market.db.lzma"), []byte("not an lzma stream"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := Ensure(Options{DataDir: dir}); err == nil {
		t.Fatal("expected error for corrupt seed")
	}
	if got := fileSHA(t, cur); got != before {
		t.Fatalf("existing database changed on failure")
	}
	if _, err := os.Stat(filepath.Join(dir, "market.db.part")); !os.IsNotExist(err) {
		t.Fatalf("staging file left behind: %v", err)
	}
	var st State
	raw, err := os.ReadFile(filepath.Join(dir, StateFile))
	if err != nil {
		t.Fatalf("state file after failure: %v", err)
	}
	if err := json.Unmarshal(raw, &st); err != nil {
		t.Fatal(err)
	}
	if st.Status != StatusFailed {
		t.Fatalf("state status = %q, want failed", st.Status)
	}
}

func TestEnsureSkipsWhenActiveGenerationExists(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))
	if err := os.WriteFile(filepath.Join(dir, "active_generation.json"), []byte(`{"snapshot_set_id":"x"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("Ensure: %v", err)
	}
	if res.Applied || res.Reason != ReasonGenerationActive {
		t.Fatalf("expected generation skip, got %+v", res)
	}
	if _, err := os.Stat(filepath.Join(dir, "market.db")); !os.IsNotExist(err) {
		t.Fatalf("market.db should not be created when generation is active")
	}
}

func TestEnsureReappliesWhenDatabaseLost(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))
	if _, err := Ensure(Options{DataDir: dir}); err != nil {
		t.Fatalf("first Ensure: %v", err)
	}
	if err := os.Remove(filepath.Join(dir, "market.db")); err != nil {
		t.Fatal(err)
	}
	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("second Ensure: %v", err)
	}
	if !res.Applied {
		t.Fatalf("expected re-extract after database loss, got %+v", res)
	}
	if got := priceCount(t, filepath.Join(dir, "market.db")); got != 3 {
		t.Fatalf("rows = %d, want 3", got)
	}
}

func TestEnsureRejectsSeedWithoutPriceHistory(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	conn := openTestDB(t, seedDB)
	execAll(t, conn, `CREATE TABLE market_watch (ins_code TEXT PRIMARY KEY)`, `INSERT INTO market_watch VALUES ('I1')`)
	_ = conn.Close()
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))
	if _, err := Ensure(Options{DataDir: dir}); err == nil {
		t.Fatal("expected error for seed without price_history")
	}
	if _, err := os.Stat(filepath.Join(dir, "market.db")); !os.IsNotExist(err) {
		t.Fatalf("market.db should not be activated from an invalid seed")
	}
}

func TestEnsureMergeIsIdempotentWithoutState(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	packLZMA(t, seedDB, filepath.Join(dir, "market.db.lzma"))
	cur := filepath.Join(dir, "market.db")
	makeCurrentDB(t, cur)

	if _, err := Ensure(Options{DataDir: dir}); err != nil {
		t.Fatalf("first Ensure: %v", err)
	}
	first := priceCount(t, cur)
	// Losing the marker must not duplicate rows on the next run.
	if err := os.Remove(filepath.Join(dir, StateFile)); err != nil {
		t.Fatal(err)
	}
	if _, err := Ensure(Options{DataDir: dir}); err != nil {
		t.Fatalf("second Ensure: %v", err)
	}
	if got := priceCount(t, cur); got != first {
		t.Fatalf("price_history rows changed on re-merge: %d -> %d", first, got)
	}
	conn := openTestDB(t, cur)
	var adj int
	if err := conn.QueryRow(`SELECT count(*) FROM adjust_events`).Scan(&adj); err != nil {
		t.Fatalf("adjust_events: %v", err)
	}
	if adj != 1 {
		t.Fatalf("seed-only table duplicated: %d rows", adj)
	}
}

func TestEnsureTruncatedSeedKeepsExisting(t *testing.T) {
	dir := t.TempDir()
	seedDB := filepath.Join(t.TempDir(), "seed.db")
	makeSeedDB(t, seedDB)
	full := filepath.Join(t.TempDir(), "full.lzma")
	packLZMA(t, seedDB, full)
	raw, err := os.ReadFile(full)
	if err != nil {
		t.Fatal(err)
	}
	truncated := filepath.Join(dir, "market.db.lzma")
	if err := os.WriteFile(truncated, raw[:len(raw)/2], 0o644); err != nil {
		t.Fatal(err)
	}
	cur := filepath.Join(dir, "market.db")
	makeCurrentDB(t, cur)
	before := fileSHA(t, cur)
	if _, err := Ensure(Options{DataDir: dir}); err == nil {
		t.Fatal("expected error for truncated seed")
	}
	if got := fileSHA(t, cur); got != before {
		t.Fatalf("existing database changed on truncated seed")
	}
}

// TestRealSeedMerge runs the real bundled template and the real 445k-row seed.
// CI sets the two paths from the assembled dist; locally it is skipped so the
// package stays fast and does not depend on gitignored data.
func TestRealSeedMerge(t *testing.T) {
	seedPath := os.Getenv("BORS_REAL_SEED")
	template := os.Getenv("BORS_REAL_TEMPLATE")
	if seedPath == "" || template == "" {
		t.Skip("BORS_REAL_SEED/BORS_REAL_TEMPLATE not set")
	}
	dir := t.TempDir()
	if err := copyFile(template, filepath.Join(dir, "market.db")); err != nil {
		t.Fatalf("copy template: %v", err)
	}
	if err := copyFile(seedPath, filepath.Join(dir, "market.db.gz")); err != nil {
		t.Fatalf("copy seed: %v", err)
	}
	res, err := Ensure(Options{DataDir: dir})
	if err != nil {
		t.Fatalf("Ensure: %v", err)
	}
	if !res.Applied || res.Mode != ModeMerge {
		t.Fatalf("result = %+v", res)
	}
	if res.State.PriceHistoryRows < 445000 {
		t.Fatalf("price_history rows = %d, want >= 445000", res.State.PriceHistoryRows)
	}
	if res.State.PriceHistoryFirst > "2024-08-25" {
		t.Fatalf("first candle = %s", res.State.PriceHistoryFirst)
	}
	conn := openTestDB(t, filepath.Join(dir, "market.db"))
	defer conn.Close()
	var boardRows int
	if err := conn.QueryRow(`SELECT count(*) FROM market_watch`).Scan(&boardRows); err != nil {
		t.Fatalf("market_watch: %v", err)
	}
	var templateRows int
	tc := openTestDB(t, template)
	if err := tc.QueryRow(`SELECT count(*) FROM market_watch`).Scan(&templateRows); err != nil {
		t.Fatalf("template market_watch: %v", err)
	}
	_ = tc.Close()
	if boardRows != templateRows {
		t.Fatalf("board rows changed by merge: %d -> %d", templateRows, boardRows)
	}
}
