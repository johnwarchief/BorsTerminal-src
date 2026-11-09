package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"borsterminal/backend/internal/config"
	"borsterminal/backend/internal/db"
	"borsterminal/backend/internal/generation"
)

func writeMarkerMarket(t *testing.T, path, value string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	conn, err := db.OpenRWC(path)
	if err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("CREATE TABLE generation_marker(value TEXT NOT NULL)"); err != nil {
		t.Fatal(err)
	}
	if _, err := conn.Exec("INSERT INTO generation_marker(value) VALUES (?)", value); err != nil {
		t.Fatal(err)
	}
	if err := conn.Close(); err != nil {
		t.Fatal(err)
	}
}

func writeGenPointer(t *testing.T, dataDir string, p generation.Pointer) {
	t.Helper()
	raw, err := json.Marshal(p)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dataDir, generation.PointerFile), raw, 0o644); err != nil {
		t.Fatal(err)
	}
}

func testConfig(dataDir string) config.Config {
	return config.Config{Addr: "127.0.0.1:0", DataDir: dataDir, ReadOnly: true, NoLoops: true, NoShell: true}
}

func currentMarker(t *testing.T, rt *runtime) string {
	t.Helper()
	inst := rt.current()
	if inst == nil {
		t.Fatal("no active instance")
	}
	var v string
	if err := inst.handles.Market.QueryRow("SELECT value FROM generation_marker").Scan(&v); err != nil {
		t.Fatal(err)
	}
	return v
}

func servingField(t *testing.T, rt *runtime, key string) any {
	t.Helper()
	serving, _ := rt.DataStatus()["serving"].(map[string]any)
	if serving == nil {
		t.Fatalf("no serving block: %+v", rt.DataStatus())
	}
	return serving[key]
}

func TestGenerationApplyRestartQueryRollback(t *testing.T) {
	t.Setenv("BORS_GO_LIVE", "0")
	dataDir := t.TempDir()
	writeMarkerMarket(t, filepath.Join(dataDir, "gens", "gen_one", "market.db"), "one")
	writeMarkerMarket(t, filepath.Join(dataDir, "gens", "gen_two", "market.db"), "two")
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "one", GenerationDir: "gens/gen_one", SchemaVersion: 1,
		AppliedAtUTC: "2026-11-09T00:00:00Z",
	})

	rt, err := newRuntime(context.Background(), testConfig(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(rt.Close)

	if got := servingField(t, rt, "snapshot_set_id"); got != "one" {
		t.Fatalf("startup generation = %v, want one", got)
	}
	if got := currentMarker(t, rt); got != "one" {
		t.Fatalf("startup data = %q", got)
	}

	srv := httptest.NewServer(rt)
	t.Cleanup(srv.Close)
	var status map[string]any
	resp, err := http.Get(srv.URL + "/api/oc/data")
	if err != nil {
		t.Fatal(err)
	}
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if got := status["serving"].(map[string]any)["snapshot_set_id"]; got != "one" {
		t.Fatalf("http generation = %v", got)
	}

	// Restart: a fresh runtime must read the same pointer.
	rtRestart, err := newRuntime(context.Background(), testConfig(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	if got := servingField(t, rtRestart, "snapshot_set_id"); got != "one" {
		t.Fatalf("restart generation = %v", got)
	}
	rtRestart.Close()

	// Apply: pointer moves to gen_two; reload swaps without restart.
	old := rt.current()
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "two", GenerationDir: "gens/gen_two", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:10:00Z",
		PreviousSnapshotSetID: "one", PreviousGenerationDir: "gens/gen_one",
	})
	if err := rt.Reload(); err != nil {
		t.Fatal(err)
	}
	if got := servingField(t, rt, "snapshot_set_id"); got != "two" {
		t.Fatalf("after reload = %v, want two", got)
	}
	if got := currentMarker(t, rt); got != "two" {
		t.Fatalf("after reload data = %q", got)
	}
	select {
	case <-old.closed:
	case <-time.After(2 * time.Second):
		t.Fatal("retired instance was not closed after drain")
	}
	if status := rt.DataStatus(); status["pending_reload"] != false {
		t.Fatalf("pending_reload = %v", status["pending_reload"])
	}

	resp, err = http.Get(srv.URL + "/api/oc/data")
	if err != nil {
		t.Fatal(err)
	}
	status = nil
	if err := json.NewDecoder(resp.Body).Decode(&status); err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if got := status["serving"].(map[string]any)["snapshot_set_id"]; got != "two" {
		t.Fatalf("http after reload = %v", got)
	}

	// Pointer changed but not reloaded: status must say pending_reload, serving stays two.
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "one", GenerationDir: "gens/gen_one", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:20:00Z",
		PreviousSnapshotSetID: "two", PreviousGenerationDir: "gens/gen_two",
	})
	if status := rt.DataStatus(); status["pending_reload"] != true {
		t.Fatalf("expected pending_reload=true, got %+v", status)
	}
	if got := servingField(t, rt, "snapshot_set_id"); got != "two" {
		t.Fatalf("serving must stay two before reload, got %v", got)
	}
	writeGenPointer(t, dataDir, generation.Pointer{
		SnapshotSetID: "two", GenerationDir: "gens/gen_two", SchemaVersion: 1,
		AppliedAtUTC:          "2026-11-09T00:10:00Z",
		PreviousSnapshotSetID: "one", PreviousGenerationDir: "gens/gen_one",
	})

	// Rollback: pointer goes back to the previous generation and reload serves it.
	if err := rt.Rollback(); err != nil {
		t.Fatal(err)
	}
	if got := servingField(t, rt, "snapshot_set_id"); got != "one" {
		t.Fatalf("after rollback = %v, want one", got)
	}
	if got := currentMarker(t, rt); got != "one" {
		t.Fatalf("after rollback data = %q", got)
	}

	rtAfterRollback, err := newRuntime(context.Background(), testConfig(dataDir))
	if err != nil {
		t.Fatal(err)
	}
	if got := servingField(t, rtAfterRollback, "snapshot_set_id"); got != "one" {
		t.Fatalf("restart after rollback = %v", got)
	}
	rtAfterRollback.Close()
}

func TestCorruptPointerRefusesStartup(t *testing.T) {
	dataDir := t.TempDir()
	writeMarkerMarket(t, filepath.Join(dataDir, "market.db"), "legacy")
	if err := os.WriteFile(filepath.Join(dataDir, generation.PointerFile), []byte("{broken"), 0o644); err != nil {
		t.Fatal(err)
	}
	if _, err := newRuntime(context.Background(), testConfig(dataDir)); err == nil {
		t.Fatal("expected startup to fail on a corrupt pointer")
	}
}

func TestBindListenerFailsFastWhenPortIsOccupied(t *testing.T) {
	first, err := bindListener("127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer first.Close()
	if second, err := bindListener(first.Addr().String()); err == nil {
		second.Close()
		t.Fatal("second bind on the same port must fail")
	}
}
