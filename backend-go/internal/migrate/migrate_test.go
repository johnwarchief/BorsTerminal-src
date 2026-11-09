package migrate

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
)

func openTempDB(t *testing.T, dir string) (*sql.DB, string) {
	t.Helper()
	path := filepath.Join(dir, "test.db")
	conn, err := db.OpenRWC(path)
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	return conn, path
}

func migrationsForTest() []Migration {
	return []Migration{
		{Version: 1, Name: "create_a", SQL: `CREATE TABLE a(v TEXT); INSERT INTO a(v) VALUES ('a1');`},
		{Version: 2, Name: "create_b", SQL: `CREATE TABLE b(v TEXT); INSERT INTO b(v) VALUES ('b1');`},
	}
}

func TestApplyIdempotentWithBackup(t *testing.T) {
	dataDir := t.TempDir()
	conn, dbPath := openTempDB(t, dataDir)
	if _, err := conn.Exec(`CREATE TABLE legacy(v TEXT); INSERT INTO legacy(v) VALUES ('keep-me')`); err != nil {
		t.Fatal(err)
	}
	backupDir := filepath.Join(dataDir, "backups")

	res, err := Apply(context.Background(), conn, dbPath, backupDir, migrationsForTest())
	if err != nil {
		t.Fatal(err)
	}
	if res.From != 0 || res.To != 2 || len(res.Applied) != 2 {
		t.Fatalf("result = %+v", res)
	}
	if res.BackupPath == "" {
		t.Fatal("missing backup path")
	}
	version, err := CurrentVersion(context.Background(), conn)
	if err != nil || version != 2 {
		t.Fatalf("version=%d err=%v", version, err)
	}
	var n int
	if err := conn.QueryRow("SELECT COUNT(*) FROM a").Scan(&n); err != nil || n != 1 {
		t.Fatalf("a rows=%d err=%v", n, err)
	}
	if err := conn.QueryRow("SELECT COUNT(*) FROM legacy").Scan(&n); err != nil || n != 1 {
		t.Fatalf("legacy rows=%d err=%v", n, err)
	}

	// Backup must be the pre-migration snapshot: version 0, legacy data, no a/b.
	backupConn, err := db.OpenRO(res.BackupPath)
	if err != nil {
		t.Fatal(err)
	}
	defer backupConn.Close()
	var bv int
	if err := backupConn.QueryRow("PRAGMA user_version").Scan(&bv); err != nil || bv != 0 {
		t.Fatalf("backup version=%d err=%v", bv, err)
	}
	if err := backupConn.QueryRow("SELECT COUNT(*) FROM legacy").Scan(&n); err != nil || n != 1 {
		t.Fatalf("backup legacy rows=%d err=%v", n, err)
	}

	// Second run: no-op, no new backup.
	res2, err := Apply(context.Background(), conn, dbPath, backupDir, migrationsForTest())
	if err != nil {
		t.Fatal(err)
	}
	if len(res2.Applied) != 0 || res2.To != 2 || res2.BackupPath != "" {
		t.Fatalf("second apply = %+v", res2)
	}
	entries, err := os.ReadDir(backupDir)
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("backup count = %d, want 1", len(entries))
	}
}

func TestFailedMigrationRollsBack(t *testing.T) {
	dataDir := t.TempDir()
	conn, dbPath := openTempDB(t, dataDir)
	backupDir := filepath.Join(dataDir, "backups")
	if _, err := Apply(context.Background(), conn, dbPath, backupDir, migrationsForTest()); err != nil {
		t.Fatal(err)
	}
	broken := append(migrationsForTest(), Migration{
		Version: 3,
		Name:    "broken",
		SQL:     `CREATE TABLE c(v TEXT); INSERT INTO missing_table(v) VALUES ('x');`,
	})
	if _, err := Apply(context.Background(), conn, dbPath, backupDir, broken); err == nil {
		t.Fatal("expected migration failure")
	}
	version, err := CurrentVersion(context.Background(), conn)
	if err != nil || version != 2 {
		t.Fatalf("version after failure = %d err=%v", version, err)
	}
	var n int
	if err := conn.QueryRow("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='c'").Scan(&n); err != nil || n != 0 {
		t.Fatalf("failed migration left table c behind (n=%d err=%v)", n, err)
	}
	if err := conn.QueryRow("SELECT COUNT(*) FROM schema_migrations").Scan(&n); err != nil || n != 2 {
		t.Fatalf("schema_migrations rows=%d err=%v", n, err)
	}
}

func TestRestoreBackup(t *testing.T) {
	dataDir := t.TempDir()
	conn, dbPath := openTempDB(t, dataDir)
	if _, err := conn.Exec(`CREATE TABLE legacy(v TEXT); INSERT INTO legacy(v) VALUES ('keep-me')`); err != nil {
		t.Fatal(err)
	}
	backupDir := filepath.Join(dataDir, "backups")
	res, err := Apply(context.Background(), conn, dbPath, backupDir, migrationsForTest())
	if err != nil {
		t.Fatal(err)
	}
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	if err := Restore(dbPath, res.BackupPath); err != nil {
		t.Fatal(err)
	}
	restored, err := db.OpenRW(dbPath)
	if err != nil {
		t.Fatal(err)
	}
	defer restored.Close()
	version, err := CurrentVersion(context.Background(), restored)
	if err != nil || version != 0 {
		t.Fatalf("restored version=%d err=%v", version, err)
	}
	var v string
	if err := restored.QueryRow("SELECT v FROM legacy").Scan(&v); err != nil || v != "keep-me" {
		t.Fatalf("legacy v=%q err=%v", v, err)
	}
}

func TestNewerDatabaseIsRejected(t *testing.T) {
	dataDir := t.TempDir()
	conn, dbPath := openTempDB(t, dataDir)
	if _, err := conn.Exec("PRAGMA user_version = 9"); err != nil {
		t.Fatal(err)
	}
	if _, err := Apply(context.Background(), conn, dbPath, filepath.Join(dataDir, "b"), migrationsForTest()); err == nil {
		t.Fatal("expected rejection of a newer database")
	}
}

func TestInvalidMigrationListsAreRejected(t *testing.T) {
	dataDir := t.TempDir()
	conn, dbPath := openTempDB(t, dataDir)
	for _, list := range [][]Migration{
		{{Version: 2, Name: "first", SQL: "CREATE TABLE x(v TEXT)"}},
		{{Version: 1, Name: "", SQL: "CREATE TABLE x(v TEXT)"}},
		{{Version: 1, Name: "empty", SQL: "  "}},
		{{Version: 2, Name: "dup", SQL: "CREATE TABLE x(v TEXT)"}, {Version: 2, Name: "dup2", SQL: "CREATE TABLE y(v TEXT)"}},
	} {
		if _, err := Apply(context.Background(), conn, dbPath, filepath.Join(dataDir, "b"), list); err == nil {
			t.Fatalf("expected invalid list to be rejected: %+v", list)
		}
	}
}
