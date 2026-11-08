package snapshot

import (
	"bytes"
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/db"
	_ "modernc.org/sqlite"
)

func TestManifest_SaveLoadValidate(t *testing.T) {
	// 1. Happy path: create, add asset, validate, save, load
	manifest := NewManifest("20261108T010000Z-deadbeef", 1)
	if manifest.SnapshotSetID != "20261108T010000Z-deadbeef" {
		t.Fatalf("unexpected snapshot_set_id: %s", manifest.SnapshotSetID)
	}
	if manifest.SchemaVersion != 1 {
		t.Fatalf("unexpected schema_version: %d", manifest.SchemaVersion)
	}
	if manifest.CreatedAtUTC == "" {
		t.Fatalf("expected non-empty created_at_utc")
	}

	validHash := strings.Repeat("a", 64)
	manifest.AddAsset("market", "market.db.lzma", validHash, 2048, 8192)

	if err := manifest.Validate(); err != nil {
		t.Fatalf("expected valid manifest, got: %v", err)
	}

	tmpDir := t.TempDir()
	manifestPath := filepath.Join(tmpDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		t.Fatalf("failed to save manifest: %v", err)
	}

	loaded, err := LoadManifest(manifestPath)
	if err != nil {
		t.Fatalf("failed to load manifest: %v", err)
	}

	if loaded.SnapshotSetID != manifest.SnapshotSetID {
		t.Errorf("loaded snapshot_set_id mismatch: got %s, want %s", loaded.SnapshotSetID, manifest.SnapshotSetID)
	}
	if loaded.SchemaVersion != manifest.SchemaVersion {
		t.Errorf("loaded schema_version mismatch: got %d, want %d", loaded.SchemaVersion, manifest.SchemaVersion)
	}
	if loaded.CreatedAtUTC != manifest.CreatedAtUTC {
		t.Errorf("loaded created_at_utc mismatch: got %s, want %s", loaded.CreatedAtUTC, manifest.CreatedAtUTC)
	}

	marketAsset, ok := loaded.Assets["market"]
	if !ok {
		t.Fatalf("market asset missing from loaded manifest")
	}
	if marketAsset.Path != "market.db.lzma" || marketAsset.SHA256 != validHash || marketAsset.SizeBytes != 2048 || marketAsset.UncompressedSizeBytes != 8192 {
		t.Errorf("loaded asset meta mismatch: %+v", marketAsset)
	}

	if err := loaded.Validate(); err != nil {
		t.Fatalf("loaded manifest failed validation: %v", err)
	}

	// 2. Validation failures
	t.Run("empty_set_id", func(t *testing.T) {
		m := NewManifest("", 1)
		m.AddAsset("market", "market.db.lzma", validHash, 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for empty snapshot_set_id, got nil")
		}
	})

	t.Run("empty_created_at", func(t *testing.T) {
		m := NewManifest("set1", 1)
		m.CreatedAtUTC = ""
		m.AddAsset("market", "market.db.lzma", validHash, 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for empty created_at_utc, got nil")
		}
	})

	t.Run("schema_version_below_1", func(t *testing.T) {
		m := NewManifest("set1", 0)
		m.AddAsset("market", "market.db.lzma", validHash, 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for schema_version 0, got nil")
		}
	})

	t.Run("no_assets", func(t *testing.T) {
		m := NewManifest("set1", 1)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for empty assets map, got nil")
		}
	})

	t.Run("bad_sha256_length", func(t *testing.T) {
		m := NewManifest("set1", 1)
		m.AddAsset("market", "market.db.lzma", "deadbeef", 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for short sha256, got nil")
		}
	})

	t.Run("bad_sha256_non_hex", func(t *testing.T) {
		m := NewManifest("set1", 1)
		m.AddAsset("market", "market.db.lzma", strings.Repeat("z", 64), 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for non-hex sha256, got nil")
		}
	})

	t.Run("zero_size_bytes", func(t *testing.T) {
		m := NewManifest("set1", 1)
		m.AddAsset("market", "market.db.lzma", validHash, 0, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for size_bytes=0, got nil")
		}
	})

	t.Run("empty_asset_path", func(t *testing.T) {
		m := NewManifest("set1", 1)
		m.AddAsset("market", "", validHash, 100, 200)
		if err := m.Validate(); err == nil {
			t.Errorf("expected error for empty asset path, got nil")
		}
	})
}

func TestVacuumInto_Success(t *testing.T) {
	ctx := context.Background()

	// 1. Create in-memory DB with data
	srcDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("failed to open memory db: %v", err)
	}
	defer srcDB.Close()

	_, err = srcDB.Exec(`
		CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT);
		INSERT INTO items (name) VALUES ('alpha'), ('beta');
	`)
	if err != nil {
		t.Fatalf("failed to create schema/insert: %v", err)
	}

	// 2. Vacuum into target file
	tmpDir := t.TempDir()
	targetPath := filepath.Join(tmpDir, "vacuumed.db")

	if err := VacuumInto(ctx, srcDB, targetPath); err != nil {
		t.Fatalf("VacuumInto failed: %v", err)
	}

	// 3. Verify target file exists and non-empty
	fi, err := os.Stat(targetPath)
	if err != nil {
		t.Fatalf("stat target file failed: %v", err)
	}
	if fi.Size() == 0 {
		t.Fatalf("target file is empty")
	}

	// 4. Open vacuumed target with db.OpenRO and verify rows
	dstDB, err := db.OpenRO(targetPath)
	if err != nil {
		t.Fatalf("failed to open vacuumed target db: %v", err)
	}

	var count int
	if err := dstDB.QueryRow("SELECT COUNT(*) FROM items").Scan(&count); err != nil {
		dstDB.Close()
		t.Fatalf("query count failed: %v", err)
	}
	if count != 2 {
		dstDB.Close()
		t.Fatalf("expected 2 items, got %d", count)
	}
	// Explicitly close before re-vacuuming since Windows locks open files
	if err := dstDB.Close(); err != nil {
		t.Fatalf("close dstDB failed: %v", err)
	}

	// 5. Test overwriting existing file
	if err := VacuumInto(ctx, srcDB, targetPath); err != nil {
		t.Fatalf("re-vacuum into existing target should succeed: %v", err)
	}

	// 6. Test error validation
	if err := VacuumInto(ctx, nil, targetPath); err == nil {
		t.Errorf("expected error for nil srcDB")
	}
	if err := VacuumInto(ctx, srcDB, ""); err == nil {
		t.Errorf("expected error for empty targetPath")
	}
}

func TestCompressAndDecompressLZMA(t *testing.T) {
	tmpDir := t.TempDir()
	rawPath := filepath.Join(tmpDir, "source_data.bin")
	compPath := filepath.Join(tmpDir, "compressed.bin.lzma")
	decompPath := filepath.Join(tmpDir, "decompressed.bin")

	// Generate repeated pseudo-random test payload (~64 KB)
	var originalData bytes.Buffer
	for i := 0; i < 2000; i++ {
		originalData.WriteString("BorsTerminal FTS Stage 3 Snapshot Builder Testing line: ")
		originalData.WriteByte(byte(i % 256))
		originalData.WriteString("\n")
	}
	payload := originalData.Bytes()

	if err := os.WriteFile(rawPath, payload, 0644); err != nil {
		t.Fatalf("failed to write raw data: %v", err)
	}

	hasher := sha256.New()
	hasher.Write(payload)
	expectedRawSHA256 := hex.EncodeToString(hasher.Sum(nil))

	// Compress
	compSHA256, compSize, rawSize, err := CompressLZMA(rawPath, compPath)
	if err != nil {
		t.Fatalf("CompressLZMA failed: %v", err)
	}

	if rawSize != int64(len(payload)) {
		t.Errorf("rawSize mismatch: got %d, want %d", rawSize, len(payload))
	}

	compFi, err := os.Stat(compPath)
	if err != nil {
		t.Fatalf("stat compressed file failed: %v", err)
	}
	if compSize != compFi.Size() {
		t.Errorf("compSize mismatch: got %d, stat says %d", compSize, compFi.Size())
	}

	// Verify compressed file sha256
	compBytes, err := os.ReadFile(compPath)
	if err != nil {
		t.Fatalf("read compressed file failed: %v", err)
	}
	compHasher := sha256.New()
	compHasher.Write(compBytes)
	actualCompSHA256 := hex.EncodeToString(compHasher.Sum(nil))
	if compSHA256 != actualCompSHA256 {
		t.Errorf("compressed sha256 mismatch: got %s, want %s", compSHA256, actualCompSHA256)
	}

	// Decompress
	if err := DecompressLZMA(compPath, decompPath); err != nil {
		t.Fatalf("DecompressLZMA failed: %v", err)
	}

	decompBytes, err := os.ReadFile(decompPath)
	if err != nil {
		t.Fatalf("read decompressed file failed: %v", err)
	}

	if !bytes.Equal(decompBytes, payload) {
		t.Fatalf("decompressed data does not match original data")
	}

	decompHasher := sha256.New()
	decompHasher.Write(decompBytes)
	decompSHA256 := hex.EncodeToString(decompHasher.Sum(nil))
	if decompSHA256 != expectedRawSHA256 {
		t.Errorf("decompressed sha256 mismatch: got %s, want %s", decompSHA256, expectedRawSHA256)
	}
}

func TestBuildSnapshotSet(t *testing.T) {
	ctx := context.Background()

	// 1. Create two in-memory SQLite DBs: market and codal
	marketDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open market db failed: %v", err)
	}
	defer marketDB.Close()

	_, err = marketDB.Exec(`
		CREATE TABLE instruments (
			id INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			close_price REAL NOT NULL
		);
		INSERT INTO instruments (symbol, close_price) VALUES
			('فولاد', 5200.0),
			('فملی', 7100.0);
	`)
	if err != nil {
		t.Fatalf("init market db failed: %v", err)
	}

	codalDB, err := sql.Open("sqlite", ":memory:")
	if err != nil {
		t.Fatalf("open codal db failed: %v", err)
	}
	defer codalDB.Close()

	_, err = codalDB.Exec(`
		CREATE TABLE codal_notices (
			tracing_no INTEGER PRIMARY KEY,
			symbol TEXT NOT NULL,
			title TEXT NOT NULL
		);
		INSERT INTO codal_notices (tracing_no, symbol, title) VALUES
			(12345, 'فولاد', 'گزارش فعالیت ماهانه دوره یک ماهه'),
			(67890, 'فملی', 'افشای اطلاعات بااهمیت');
	`)
	if err != nil {
		t.Fatalf("init codal db failed: %v", err)
	}

	dbs := map[string]*sql.DB{
		"market": marketDB,
		"codal":  codalDB,
	}

	outDir := t.TempDir()

	// 2. Build snapshot set with auto-generated setID
	manifest, err := BuildSnapshotSet(ctx, dbs, outDir, "")
	if err != nil {
		t.Fatalf("BuildSnapshotSet failed: %v", err)
	}

	if manifest == nil {
		t.Fatalf("expected non-nil manifest")
	}

	if !strings.Contains(manifest.SnapshotSetID, "Z-") {
		t.Errorf("snapshot_set_id %q does not match expected format <timestamp>Z-<rand>", manifest.SnapshotSetID)
	}

	// 3. Check manifest file on disk
	manifestPath := filepath.Join(outDir, "manifest.json")
	loadedManifest, err := LoadManifest(manifestPath)
	if err != nil {
		t.Fatalf("failed to load manifest from disk: %v", err)
	}
	if err := loadedManifest.Validate(); err != nil {
		t.Fatalf("manifest on disk failed validation: %v", err)
	}
	if loadedManifest.SnapshotSetID != manifest.SnapshotSetID {
		t.Errorf("snapshot_set_id mismatch: %s vs %s", loadedManifest.SnapshotSetID, manifest.SnapshotSetID)
	}

	// 4. Verify assets in manifest
	if len(loadedManifest.Assets) != 2 {
		t.Fatalf("expected 2 assets, got %d", len(loadedManifest.Assets))
	}

	for _, name := range []string{"market", "codal"} {
		assetMeta, ok := loadedManifest.Assets[name]
		if !ok {
			t.Fatalf("asset %q missing from manifest", name)
		}
		expectedFilename := name + ".db.lzma"
		if assetMeta.Path != expectedFilename {
			t.Errorf("asset path mismatch for %s: got %s, want %s", name, assetMeta.Path, expectedFilename)
		}
		if assetMeta.SizeBytes <= 0 {
			t.Errorf("asset size_bytes must be > 0: got %d", assetMeta.SizeBytes)
		}
		if assetMeta.UncompressedSizeBytes <= 0 {
			t.Errorf("asset uncompressed_size_bytes must be > 0: got %d", assetMeta.UncompressedSizeBytes)
		}

		// Verify asset file exists on disk
		assetDiskPath := filepath.Join(outDir, expectedFilename)
		fi, err := os.Stat(assetDiskPath)
		if err != nil {
			t.Fatalf("asset file %s missing on disk: %v", expectedFilename, err)
		}
		if fi.Size() != assetMeta.SizeBytes {
			t.Errorf("file size on disk (%d) mismatch with manifest (%d)", fi.Size(), assetMeta.SizeBytes)
		}

		// Verify disk sha256 matches manifest sha256
		diskBytes, err := os.ReadFile(assetDiskPath)
		if err != nil {
			t.Fatalf("read asset file %s: %v", expectedFilename, err)
		}
		hasher := sha256.New()
		hasher.Write(diskBytes)
		actualSHA256 := hex.EncodeToString(hasher.Sum(nil))
		if actualSHA256 != assetMeta.SHA256 {
			t.Errorf("asset %s sha256 mismatch: disk=%s, manifest=%s", name, actualSHA256, assetMeta.SHA256)
		}

		// Ensure raw temp file was removed
		rawTmpPath := filepath.Join(outDir, name+".raw.tmp")
		if _, err := os.Stat(rawTmpPath); !os.IsNotExist(err) {
			t.Errorf("expected temporary raw file %s to be removed, but it still exists", rawTmpPath)
		}
	}

	// 5. Decompress market.db.lzma and verify database integrity and contents
	decompMarketPath := filepath.Join(outDir, "restored_market.db")
	if err := DecompressLZMA(filepath.Join(outDir, "market.db.lzma"), decompMarketPath); err != nil {
		t.Fatalf("failed to decompress market.db.lzma: %v", err)
	}

	restoredMarketDB, err := db.OpenRO(decompMarketPath)
	if err != nil {
		t.Fatalf("failed to open restored market db: %v", err)
	}
	defer restoredMarketDB.Close()

	rows, err := restoredMarketDB.Query("SELECT symbol, close_price FROM instruments ORDER BY id")
	if err != nil {
		t.Fatalf("query restored market db failed: %v", err)
	}
	defer rows.Close()

	type inst struct {
		symbol string
		price  float64
	}
	var results []inst
	for rows.Next() {
		var it inst
		if err := rows.Scan(&it.symbol, &it.price); err != nil {
			t.Fatalf("scan row failed: %v", err)
		}
		results = append(results, it)
	}

	if len(results) != 2 {
		t.Fatalf("expected 2 restored rows, got %d", len(results))
	}
	if results[0].symbol != "فولاد" || results[0].price != 5200.0 {
		t.Errorf("row 0 mismatch: %+v", results[0])
	}
	if results[1].symbol != "فملی" || results[1].price != 7100.0 {
		t.Errorf("row 1 mismatch: %+v", results[1])
	}

	// 6. Test with custom setID and empty dbs
	customManifest, err := BuildSnapshotSet(ctx, dbs, t.TempDir(), "custom-set-id-12345")
	if err != nil {
		t.Fatalf("BuildSnapshotSet with custom setID failed: %v", err)
	}
	if customManifest.SnapshotSetID != "custom-set-id-12345" {
		t.Errorf("custom setID mismatch: got %s, want custom-set-id-12345", customManifest.SnapshotSetID)
	}

	_, err = BuildSnapshotSet(ctx, map[string]*sql.DB{}, t.TempDir(), "")
	if err == nil {
		t.Errorf("expected error for empty dbs map, got nil")
	}
}
