package main

import (
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"sort"
	"testing"

	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/snapshot"
)

func makeDB(t *testing.T, path string) {
	t.Helper()
	conn, err := db.OpenRWC(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("CREATE TABLE t(v TEXT)"); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("INSERT INTO t(v) VALUES ('x')"); err != nil {
		t.Fatal(err)
	}
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
}

func TestCollectProducerDBsAllowlist(t *testing.T) {
	dataDir := t.TempDir()
	for _, name := range []string{"market.db", "codal.db", "research.db", "oc_client.db", "user.db", "evil.db"} {
		makeDB(t, filepath.Join(dataDir, name))
	}

	dbs, err := collectProducerDBs(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		for _, conn := range dbs {
			_ = conn.Close()
		}
	}()
	if len(dbs) != 2 || dbs["market"] == nil || dbs["codal"] == nil {
		t.Fatalf("allowlist set = %v", keysOf(dbs))
	}

	rejected, err := rejectedProducerDBs(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"evil.db", "oc_client.db", "research.db", "user.db"}
	if len(rejected) != len(want) {
		t.Fatalf("rejected = %v, want %v", rejected, want)
	}
	for i := range want {
		if rejected[i] != want[i] {
			t.Fatalf("rejected = %v, want %v", rejected, want)
		}
	}
}

func TestCollectProducerDBsRequiresMarket(t *testing.T) {
	dataDir := t.TempDir()
	makeDB(t, filepath.Join(dataDir, "research.db"))
	if _, err := collectProducerDBs(dataDir); err == nil {
		t.Fatal("expected error without market.db")
	}
}

func TestCollectProducerDBsCorruptCodalFails(t *testing.T) {
	dataDir := t.TempDir()
	makeDB(t, filepath.Join(dataDir, "market.db"))
	if err := os.WriteFile(filepath.Join(dataDir, "codal.db"), []byte("not sqlite"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := collectProducerDBs(dataDir); err == nil {
		t.Fatal("corrupt codal.db must reject the snapshot set instead of publishing without it")
	}
}

func TestSnapshotSetHasOnlyAllowlistedAssets(t *testing.T) {
	dataDir := t.TempDir()
	for _, name := range []string{"market.db", "codal.db", "research.db", "oc_client.db", "user.db"} {
		makeDB(t, filepath.Join(dataDir, name))
	}
	dbs, err := collectProducerDBs(dataDir)
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		for _, conn := range dbs {
			_ = conn.Close()
		}
	}()

	outDir := filepath.Join(t.TempDir(), "snap")
	manifest, err := snapshot.BuildSnapshotSet(context.Background(), dbs, outDir, "allowlist-test")
	if err != nil {
		t.Fatal(err)
	}
	if len(manifest.Assets) != 2 {
		t.Fatalf("manifest assets = %v", manifest.Assets)
	}
	for _, name := range []string{"market", "codal"} {
		if _, ok := manifest.Assets[name]; !ok {
			t.Fatalf("manifest missing %s: %v", name, manifest.Assets)
		}
	}
	for _, name := range []string{"research", "oc_client", "user"} {
		if _, ok := manifest.Assets[name]; ok {
			t.Fatalf("manifest must not contain %s", name)
		}
	}
}

func keysOf(m map[string]*sql.DB) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}
