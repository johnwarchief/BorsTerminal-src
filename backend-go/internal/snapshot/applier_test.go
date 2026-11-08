package snapshot

import (
	"bytes"
	"context"
	"database/sql"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	_ "modernc.org/sqlite"
)

func createSampleDatabases(t *testing.T, marketPrice float64, noticeTitle string) map[string]*sql.DB {
	t.Helper()

	marketDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open market memory db: %v", err)
	}

	_, err = marketDB.Exec(`
		CREATE TABLE instruments (
			id INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			close_price REAL NOT NULL
		);
		INSERT INTO instruments (id, symbol, close_price) VALUES
			(1, 'فولاد', ?),
			(2, 'فملی', ?);
	`, marketPrice, marketPrice*1.5)
	if err != nil {
		marketDB.Close()
		t.Fatalf("seed market db: %v", err)
	}

	codalDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		marketDB.Close()
		t.Fatalf("open codal memory db: %v", err)
	}

	_, err = codalDB.Exec(`
		CREATE TABLE codal_notices (
			tracing_no INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			title TEXT NOT NULL
		);
		INSERT INTO codal_notices (tracing_no, symbol, title) VALUES
			(1001, 'فولاد', ?),
			(1002, 'فملی', 'افشای اطلاعات بااهمیت');
	`, noticeTitle)
	if err != nil {
		marketDB.Close()
		codalDB.Close()
		t.Fatalf("seed codal db: %v", err)
	}

	return map[string]*sql.DB{
		"market": marketDB,
		"codal":  codalDB,
	}
}

func buildAndSignSnapshotSet(t *testing.T, ctx context.Context, dbs map[string]*sql.DB, stagingDir, setID, privKey string) *Manifest {
	t.Helper()

	manifest, err := BuildSnapshotSet(ctx, dbs, stagingDir, setID)
	if err != nil {
		t.Fatalf("BuildSnapshotSet failed: %v", err)
	}

	for _, asset := range manifest.Assets {
		assetFile := filepath.Join(stagingDir, asset.Path)
		if _, err := SignAsset(assetFile, privKey, ""); err != nil {
			t.Fatalf("SignAsset %s failed: %v", assetFile, err)
		}
	}

	manifestPath := filepath.Join(stagingDir, "manifest.json")
	if _, err := SignAsset(manifestPath, privKey, ""); err != nil {
		t.Fatalf("SignAsset manifest.json failed: %v", err)
	}

	return manifest
}

func TestApplier_ApplySnapshotSet_Success(t *testing.T) {
	ctx := context.Background()

	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	stagingDir := t.TempDir()

	dbs := createSampleDatabases(t, 5200.0, "گزارش فعالیت ماهانه")
	defer dbs["market"].Close()
	defer dbs["codal"].Close()

	setID := "20261108T010000Z-alpha1"
	manifest := buildAndSignSnapshotSet(t, ctx, dbs, stagingDir, setID, privKey)

	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	if err := applier.ApplySnapshotSet(stagingDir, manifest); err != nil {
		t.Fatalf("ApplySnapshotSet failed: %v", err)
	}

	// 1. Verify active_generation.json
	ptr, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration failed: %v", err)
	}
	if ptr.SnapshotSetID != setID {
		t.Errorf("expected snapshot_set_id %s, got %s", setID, ptr.SnapshotSetID)
	}
	if ptr.PreviousSnapshotSetID != "" {
		t.Errorf("expected empty previous_snapshot_set_id, got %s", ptr.PreviousSnapshotSetID)
	}
	if ptr.SchemaVersion != 1 {
		t.Errorf("expected schema_version 1, got %d", ptr.SchemaVersion)
	}

	// 2. Verify market.db contents
	marketPath, err := applier.ActiveDBPath("market")
	if err != nil {
		t.Fatalf("ActiveDBPath market failed: %v", err)
	}
	marketConn, err := db.OpenRO(marketPath)
	if err != nil {
		t.Fatalf("OpenRO market failed: %v", err)
	}
	var closePrice float64
	if err := marketConn.QueryRow("SELECT close_price FROM instruments WHERE id = 1").Scan(&closePrice); err != nil {
		marketConn.Close()
		t.Fatalf("query market instruments failed: %v", err)
	}
	if closePrice != 5200.0 {
		marketConn.Close()
		t.Errorf("expected close_price 5200.0, got %f", closePrice)
	}
	marketConn.Close()

	// 3. Verify codal.db contents
	codalPath, err := applier.ActiveDBPath("codal")
	if err != nil {
		t.Fatalf("ActiveDBPath codal failed: %v", err)
	}
	codalConn, err := db.OpenRO(codalPath)
	if err != nil {
		t.Fatalf("OpenRO codal failed: %v", err)
	}
	var title string
	if err := codalConn.QueryRow("SELECT title FROM codal_notices WHERE tracing_no = 1001").Scan(&title); err != nil {
		codalConn.Close()
		t.Fatalf("query codal notices failed: %v", err)
	}
	if title != "گزارش فعالیت ماهانه" {
		codalConn.Close()
		t.Errorf("expected title 'گزارش فعالیت ماهانه', got %q", title)
	}
	codalConn.Close()

	// 4. Verify idempotency
	if err := applier.ApplySnapshotSet(stagingDir, manifest); err != nil {
		t.Fatalf("idempotent ApplySnapshotSet failed: %v", err)
	}
	ptr2, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration after idempotent apply failed: %v", err)
	}
	if ptr2.SnapshotSetID != setID {
		t.Errorf("expected unchanged snapshot_set_id %s, got %s", setID, ptr2.SnapshotSetID)
	}
}

func TestApplier_WindowsLockSimulation(t *testing.T) {
	ctx := context.Background()

	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// 1. Build and apply Generation 1
	stagingDir1 := t.TempDir()
	dbs1 := createSampleDatabases(t, 1000.0, "اطلاعیه دوره ۱")
	manifest1 := buildAndSignSnapshotSet(t, ctx, dbs1, stagingDir1, "20261108T010000Z-gen1", privKey)
	dbs1["market"].Close()
	dbs1["codal"].Close()

	if err := applier.ApplySnapshotSet(stagingDir1, manifest1); err != nil {
		t.Fatalf("apply generation 1 failed: %v", err)
	}

	// 2. Open connection to Generation 1 market.db and hold a read transaction open
	gen1MarketPath, err := applier.ActiveDBPath("market")
	if err != nil {
		t.Fatalf("ActiveDBPath for gen 1 failed: %v", err)
	}

	heldConn, err := db.OpenRO(gen1MarketPath)
	if err != nil {
		t.Fatalf("OpenRO on gen 1 market failed: %v", err)
	}
	defer heldConn.Close()

	tx, err := heldConn.Begin()
	if err != nil {
		t.Fatalf("begin transaction on gen 1 failed: %v", err)
	}
	defer func() {
		_ = tx.Rollback()
	}()

	var gen1Price float64
	if err := tx.QueryRow("SELECT close_price FROM instruments WHERE id = 1").Scan(&gen1Price); err != nil {
		t.Fatalf("query on held gen 1 conn failed: %v", err)
	}
	if gen1Price != 1000.0 {
		t.Fatalf("expected gen 1 price 1000.0, got %f", gen1Price)
	}

	// 3. Build and apply Generation 2 while heldConn still holds Generation 1 open
	stagingDir2 := t.TempDir()
	dbs2 := createSampleDatabases(t, 2500.0, "اطلاعیه دوره ۲")
	manifest2 := buildAndSignSnapshotSet(t, ctx, dbs2, stagingDir2, "20261108T020000Z-gen2", privKey)
	dbs2["market"].Close()
	dbs2["codal"].Close()

	// On Windows, this would fail with ERROR_SHARING_VIOLATION if in-place overwrites were attempted.
	// With immutable generations, ApplySnapshotSet writes to gen_gen2 and swaps the pointer atomically.
	if err := applier.ApplySnapshotSet(stagingDir2, manifest2); err != nil {
		t.Fatalf("ApplySnapshotSet for gen 2 failed with open reader on gen 1: %v", err)
	}

	// 4. Verify ActiveDBPath returns the new generation 2 database
	gen2MarketPath, err := applier.ActiveDBPath("market")
	if err != nil {
		t.Fatalf("ActiveDBPath for gen 2 failed: %v", err)
	}
	if filepath.Clean(gen2MarketPath) == filepath.Clean(gen1MarketPath) {
		t.Fatalf("expected active DB path to change between generations, got same path: %s", gen2MarketPath)
	}

	newConn, err := db.OpenRO(gen2MarketPath)
	if err != nil {
		t.Fatalf("OpenRO on gen 2 market failed: %v", err)
	}
	defer newConn.Close()

	var gen2Price float64
	if err := newConn.QueryRow("SELECT close_price FROM instruments WHERE id = 1").Scan(&gen2Price); err != nil {
		t.Fatalf("query on gen 2 failed: %v", err)
	}
	if gen2Price != 2500.0 {
		t.Errorf("expected gen 2 price 2500.0, got %f", gen2Price)
	}

	// 5. Verify held connection on generation 1 can still read without crashing
	var recheckPrice float64
	if err := tx.QueryRow("SELECT close_price FROM instruments WHERE id = 1").Scan(&recheckPrice); err != nil {
		t.Fatalf("subsequent read on held gen 1 transaction failed: %v", err)
	}
	if recheckPrice != 1000.0 {
		t.Errorf("expected held gen 1 price 1000.0, got %f", recheckPrice)
	}

	var gen1Count int
	if err := heldConn.QueryRow("SELECT COUNT(*) FROM instruments").Scan(&gen1Count); err != nil {
		t.Fatalf("query count on held gen 1 conn failed: %v", err)
	}
	if gen1Count != 2 {
		t.Errorf("expected count 2 in gen 1, got %d", gen1Count)
	}
}

func TestApplier_Rollback(t *testing.T) {
	ctx := context.Background()

	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// Rollback before any generation applied must fail
	if err := applier.Rollback(); err == nil {
		t.Fatalf("expected error on rollback with no active generation, got nil")
	}

	// 1. Apply Generation 1
	stagingDir1 := t.TempDir()
	dbs1 := createSampleDatabases(t, 111.0, "گزارش اول")
	manifest1 := buildAndSignSnapshotSet(t, ctx, dbs1, stagingDir1, "20261108T010000Z-gen1", privKey)
	dbs1["market"].Close()
	dbs1["codal"].Close()
	if err := applier.ApplySnapshotSet(stagingDir1, manifest1); err != nil {
		t.Fatalf("apply gen 1 failed: %v", err)
	}

	// Rollback when only 1 generation exists must fail (no previous generation)
	if err := applier.Rollback(); err == nil {
		t.Fatalf("expected error on rollback with no previous generation, got nil")
	}

	// 2. Apply Generation 2
	stagingDir2 := t.TempDir()
	dbs2 := createSampleDatabases(t, 222.0, "گزارش دوم")
	manifest2 := buildAndSignSnapshotSet(t, ctx, dbs2, stagingDir2, "20261108T020000Z-gen2", privKey)
	dbs2["market"].Close()
	dbs2["codal"].Close()
	if err := applier.ApplySnapshotSet(stagingDir2, manifest2); err != nil {
		t.Fatalf("apply gen 2 failed: %v", err)
	}

	// Verify Gen 2 is active
	ptrBefore, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration failed: %v", err)
	}
	if ptrBefore.SnapshotSetID != "20261108T020000Z-gen2" {
		t.Fatalf("expected gen 2 active, got %s", ptrBefore.SnapshotSetID)
	}
	if ptrBefore.PreviousSnapshotSetID != "20261108T010000Z-gen1" {
		t.Fatalf("expected gen 1 as previous, got %s", ptrBefore.PreviousSnapshotSetID)
	}

	// 3. Perform Rollback
	if err := applier.Rollback(); err != nil {
		t.Fatalf("Rollback failed: %v", err)
	}

	// 4. Verify ActiveGeneration now points back to Generation 1
	ptrAfter, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration after rollback failed: %v", err)
	}
	if ptrAfter.SnapshotSetID != "20261108T010000Z-gen1" {
		t.Errorf("expected rolled back snapshot set to be gen 1, got %s", ptrAfter.SnapshotSetID)
	}
	if ptrAfter.PreviousSnapshotSetID != "" {
		t.Errorf("expected empty previous_snapshot_set_id after rollback, got %s", ptrAfter.PreviousSnapshotSetID)
	}

	// 5. Verify ActiveDBPath queries Generation 1 data
	marketPath, err := applier.ActiveDBPath("market")
	if err != nil {
		t.Fatalf("ActiveDBPath after rollback failed: %v", err)
	}
	conn, err := db.OpenRO(marketPath)
	if err != nil {
		t.Fatalf("OpenRO after rollback failed: %v", err)
	}
	defer conn.Close()

	var rolledBackPrice float64
	if err := conn.QueryRow("SELECT close_price FROM instruments WHERE id = 1").Scan(&rolledBackPrice); err != nil {
		t.Fatalf("query price after rollback failed: %v", err)
	}
	if rolledBackPrice != 111.0 {
		t.Errorf("expected price 111.0 after rollback, got %f", rolledBackPrice)
	}
}

func TestApplier_TamperedAsset_Rejected(t *testing.T) {
	ctx := context.Background()

	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	stagingDir := t.TempDir()

	dbs := createSampleDatabases(t, 333.0, "اطلاعیه آزمون دستکاری")
	manifest := buildAndSignSnapshotSet(t, ctx, dbs, stagingDir, "20261108T010000Z-tamper", privKey)
	dbs["market"].Close()
	dbs["codal"].Close()

	// Tamper 1 byte in market.db.lzma
	assetPath := filepath.Join(stagingDir, "market.db.lzma")
	data, err := os.ReadFile(assetPath)
	if err != nil {
		t.Fatalf("read asset failed: %v", err)
	}
	data[len(data)/2] ^= 0xFF
	if err := os.WriteFile(assetPath, data, 0644); err != nil {
		t.Fatalf("write tampered asset failed: %v", err)
	}

	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// Apply must fail on cryptographic signature or sha256 mismatch
	err = applier.ApplySnapshotSet(stagingDir, manifest)
	if err == nil {
		t.Fatalf("expected error for tampered asset, got nil")
	}

	// Active generation must NOT be created
	if _, err := applier.ActiveGeneration(); err == nil {
		t.Fatalf("active generation pointer should not exist after failed apply")
	}
}

func TestApplier_CorruptDB_IntegrityCheckFailed(t *testing.T) {
	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	stagingDir := t.TempDir()

	// Create an invalid SQLite file compressed as market.db.lzma (valid signature and hash, corrupt SQLite)
	corruptRaw := filepath.Join(stagingDir, "corrupt.raw")
	garbage := bytes.Repeat([]byte("INVALID_SQLITE_HEADER_CORRUPTED_DATABASE_PAGE_0000\n"), 25)
	if err := os.WriteFile(corruptRaw, garbage, 0644); err != nil {
		t.Fatalf("write corrupt raw failed: %v", err)
	}

	targetLZMA := filepath.Join(stagingDir, "market.db.lzma")
	compSHA, compSize, rawSize, err := CompressLZMA(corruptRaw, targetLZMA)
	if err != nil {
		t.Fatalf("CompressLZMA on corrupt payload failed: %v", err)
	}
	_ = os.Remove(corruptRaw)

	manifest := NewManifest("20261108T010000Z-corrupt", 1)
	manifest.AddAsset("market", "market.db.lzma", compSHA, compSize, rawSize)
	if err := manifest.Save(filepath.Join(stagingDir, "manifest.json")); err != nil {
		t.Fatalf("save manifest failed: %v", err)
	}

	if _, err := SignAsset(targetLZMA, privKey, ""); err != nil {
		t.Fatalf("sign targetLZMA failed: %v", err)
	}
	if _, err := SignAsset(filepath.Join(stagingDir, "manifest.json"), privKey, ""); err != nil {
		t.Fatalf("sign manifest.json failed: %v", err)
	}

	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// PRAGMA integrity_check must detect invalid SQLite format and reject application
	err = applier.ApplySnapshotSet(stagingDir, manifest)
	if err == nil {
		t.Fatalf("expected PRAGMA integrity_check error for corrupt DB, got nil")
	}
	if !strings.Contains(err.Error(), "integrity") && !strings.Contains(err.Error(), "database") {
		t.Errorf("expected error to mention integrity or database, got: %v", err)
	}

	// Active generation must NOT be set
	if _, err := applier.ActiveGeneration(); err == nil {
		t.Fatalf("active generation pointer should not exist after integrity check failure")
	}
}

func TestApplier_RetentionPolicy(t *testing.T) {
	ctx := context.Background()

	pubKey, privKey, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	dataDir := t.TempDir()
	applier, err := NewApplier(ApplierConfig{DataDir: dataDir, PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// Apply 3 generations sequentially: gen1, gen2, gen3
	for i := 1; i <= 3; i++ {
		staging := t.TempDir()
		dbs := createSampleDatabases(t, float64(i*100), "گزارش")
		setID := "set-" + string(rune('0'+i))
		manifest := buildAndSignSnapshotSet(t, ctx, dbs, staging, setID, privKey)
		dbs["market"].Close()
		dbs["codal"].Close()

		if err := applier.ApplySnapshotSet(staging, manifest); err != nil {
			t.Fatalf("apply gen %d failed: %v", i, err)
		}
	}

	// Active should be set-3, previous should be set-2
	ptr, err := applier.ActiveGeneration()
	if err != nil {
		t.Fatalf("ActiveGeneration failed: %v", err)
	}
	if ptr.SnapshotSetID != "set-3" {
		t.Errorf("expected active set-3, got %s", ptr.SnapshotSetID)
	}
	if ptr.PreviousSnapshotSetID != "set-2" {
		t.Errorf("expected previous set-2, got %s", ptr.PreviousSnapshotSetID)
	}

	// Verify gens/ directory: gen_set-1 should be deleted, gen_set-2 and gen_set-3 should exist
	gensDir := filepath.Join(dataDir, "gens")
	if _, err := os.Stat(filepath.Join(gensDir, "gen_set-1")); !os.IsNotExist(err) {
		t.Errorf("expected gen_set-1 to be deleted by retention policy, but it exists")
	}
	if _, err := os.Stat(filepath.Join(gensDir, "gen_set-2")); err != nil {
		t.Errorf("expected gen_set-2 to be retained as previous, stat err: %v", err)
	}
	if _, err := os.Stat(filepath.Join(gensDir, "gen_set-3")); err != nil {
		t.Errorf("expected gen_set-3 to be retained as active, stat err: %v", err)
	}
}

func TestApplier_InvalidInputs(t *testing.T) {
	// Empty DataDir
	if _, err := NewApplier(ApplierConfig{DataDir: "", PubKeyStr: "somekey"}); err == nil {
		t.Errorf("expected error for empty DataDir")
	}

	// Empty PubKeyStr
	if _, err := NewApplier(ApplierConfig{DataDir: t.TempDir(), PubKeyStr: ""}); err == nil {
		t.Errorf("expected error for empty PubKeyStr")
	}

	// Malformed PubKeyStr
	if _, err := NewApplier(ApplierConfig{DataDir: t.TempDir(), PubKeyStr: "not-a-minisign-key"}); err == nil {
		t.Errorf("expected error for invalid PubKeyStr")
	}

	pubKey, _, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	applier, err := NewApplier(ApplierConfig{DataDir: t.TempDir(), PubKeyStr: pubKey})
	if err != nil {
		t.Fatalf("NewApplier failed: %v", err)
	}

	// Empty stagingDir
	if err := applier.ApplySnapshotSet("", nil); err == nil {
		t.Errorf("expected error for empty stagingDir")
	}

	// Empty dbName in ActiveDBPath
	if _, err := applier.ActiveDBPath(""); err == nil {
		t.Errorf("expected error for empty dbName")
	}
}
