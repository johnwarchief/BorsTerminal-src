package researchdb

import (
	"context"
	"path/filepath"
	"testing"

	"borsterminal/backend/internal/migrate"
)

func TestOpenOutsideProducerAndIdempotent(t *testing.T) {
	researchDir := t.TempDir()
	producer := t.TempDir()
	store, err := Open(researchDir, producer)
	if err != nil {
		t.Fatal(err)
	}
	version, err := migrate.CurrentVersion(context.Background(), store.DB)
	if err != nil || version != 1 {
		t.Fatalf("version=%d err=%v", version, err)
	}
	for _, table := range []string{"hypotheses", "strategy_versions", "validations", "approvals", "audit_events"} {
		var n int
		if err := store.DB.QueryRow(
			"SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?", table).Scan(&n); err != nil || n != 1 {
			t.Fatalf("table %s missing (n=%d err=%v)", table, n, err)
		}
	}
	if err := store.Close(); err != nil {
		t.Fatal(err)
	}
	store2, err := Open(researchDir, producer)
	if err != nil {
		t.Fatal(err)
	}
	store2.Close()
}

func TestResearchDirInsideProducerIsRejected(t *testing.T) {
	producer := t.TempDir()
	if _, err := Open(filepath.Join(producer, "research"), producer); err == nil {
		t.Fatal("research dir inside producer data dir must be rejected")
	}
}
