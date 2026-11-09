package ocdb

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/migrate"
)

func TestOpenCreatesSchemaAndIsIdempotent(t *testing.T) {
	dataDir := t.TempDir()
	store, err := Open(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	version, err := migrate.CurrentVersion(context.Background(), store.DB)
	if err != nil || version != 1 {
		t.Fatalf("version=%d err=%v", version, err)
	}
	for _, table := range []string{
		"notification_events", "notification_deliveries", "notification_prefs",
		"notification_mutes", "installed_bundles", "opportunity_snapshots", "audit_events",
	} {
		var n int
		if err := store.DB.QueryRow(
			"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", table).Scan(&n); err != nil || n != 1 {
			t.Fatalf("table %s missing (n=%d err=%v)", table, n, err)
		}
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}
	entries, err := os.ReadDir(BackupDir(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("first open backups=%d, want 1", len(entries))
	}

	store2, err := Open(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	if err := store2.Close(); err != nil {
		t.Fatal(err)
	}
	entries, err = os.ReadDir(BackupDir(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("second open must not create a backup; backups=%d", len(entries))
	}
}

func TestUserDBIsNotTouched(t *testing.T) {
	dataDir := t.TempDir()
	userPath := filepath.Join(dataDir, "user.db")
	conn, err := db.OpenRWC(userPath)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("CREATE TABLE personal(v TEXT); INSERT INTO personal(v) VALUES ('x')"); err != nil {
		t.Fatal(err)
	}
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
	before := fileHash(t, userPath)

	store, err := Open(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}
	after := fileHash(t, userPath)
	if before != after {
		t.Fatalf("user.db changed: %s -> %s", before, after)
	}
}

func TestSeverityConstraint(t *testing.T) {
	dataDir := t.TempDir()
	store, err := Open(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	defer store.Close()
	_, err = store.DB.Exec(`INSERT INTO notification_events
		(event_id,event_type,category,severity,title,body,subject_json,dedupe_key,group_key,source,payload_hash,preview_json,actions_json,occurred_at,first_seen_at,last_seen_at,created_at)
		VALUES ('e1','x','y','high','t','b','{}','d','g','s','h','{}','[]','2026-11-09T00:00:00Z','2026-11-09T00:00:00Z','2026-11-09T00:00:00Z','2026-11-09T00:00:00Z')`)
	if err == nil {
		t.Fatal("severity outside the policy set must be rejected")
	}
}

func fileHash(t *testing.T, path string) string {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}
