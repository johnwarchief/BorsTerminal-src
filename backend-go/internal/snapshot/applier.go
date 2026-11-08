package snapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"borsterminal/backend/internal/db"
	_ "modernc.org/sqlite"
)

// GenerationPointer tracks the currently active database generation and rollback anchor.
type GenerationPointer struct {
	SnapshotSetID         string `json:"snapshot_set_id"`
	GenerationDir         string `json:"generation_dir"` // relative path to dataDir or absolute
	AppliedAtUTC          string `json:"applied_at_utc"`
	SchemaVersion         int    `json:"schema_version"`
	PreviousSnapshotSetID string `json:"previous_snapshot_set_id,omitempty"`
	PreviousGenerationDir string `json:"previous_generation_dir,omitempty"`
}

// ApplierConfig holds the configuration for the atomic snapshot applier.
type ApplierConfig struct {
	DataDir   string // Base directory containing gens/, staging/, active_generation.json
	PubKeyStr string // Minisign public key for verifying manifest and asset signatures
}

// Applier manages atomic ingestion and immutable generation switching on Windows and cross-platform.
type Applier struct {
	cfg ApplierConfig
}

// NewApplier creates and validates an Applier instance.
func NewApplier(cfg ApplierConfig) (*Applier, error) {
	cleanDir := strings.TrimSpace(cfg.DataDir)
	if cleanDir == "" {
		return nil, errors.New("dataDir is required")
	}

	cleanKey := strings.TrimSpace(cfg.PubKeyStr)
	if cleanKey == "" {
		return nil, errors.New("pubKeyStr is required")
	}

	if _, err := ParsePublicKey(cleanKey); err != nil {
		return nil, fmt.Errorf("invalid minisign public key: %w", err)
	}

	absDir, err := filepath.Abs(cleanDir)
	if err != nil {
		return nil, fmt.Errorf("resolve abs dataDir: %w", err)
	}

	gensDir := filepath.Join(absDir, "gens")
	if err := os.MkdirAll(gensDir, 0755); err != nil {
		return nil, fmt.Errorf("create gens dir %s: %w", gensDir, err)
	}

	cfg.DataDir = absDir
	return &Applier{cfg: cfg}, nil
}

// ActiveGeneration reads and unmarshals active_generation.json.
func (a *Applier) ActiveGeneration() (*GenerationPointer, error) {
	activeFile := filepath.Join(a.cfg.DataDir, "active_generation.json")
	data, err := os.ReadFile(activeFile)
	if err != nil {
		return nil, fmt.Errorf("read active generation: %w", err)
	}

	var ptr GenerationPointer
	if err := json.Unmarshal(data, &ptr); err != nil {
		return nil, fmt.Errorf("unmarshal active generation: %w", err)
	}

	if strings.TrimSpace(ptr.SnapshotSetID) == "" {
		return nil, errors.New("active generation missing snapshot_set_id")
	}
	if strings.TrimSpace(ptr.GenerationDir) == "" {
		return nil, errors.New("active generation missing generation_dir")
	}

	return &ptr, nil
}

// ActiveDBPath returns the absolute path to <dbName>.db inside the currently active generation.
func (a *Applier) ActiveDBPath(dbName string) (string, error) {
	cleanName := strings.TrimSpace(dbName)
	if cleanName == "" {
		return "", errors.New("dbName is required")
	}
	if !strings.HasSuffix(cleanName, ".db") {
		cleanName += ".db"
	}

	ptr, err := a.ActiveGeneration()
	if err != nil {
		return "", fmt.Errorf("get active generation for db %s: %w", cleanName, err)
	}

	genDir := ptr.GenerationDir
	if !filepath.IsAbs(genDir) {
		genDir = filepath.Join(a.cfg.DataDir, filepath.FromSlash(genDir))
	}

	target := filepath.Join(genDir, cleanName)
	if _, err := os.Stat(target); err != nil {
		return "", fmt.Errorf("active db file %s not found: %w", target, err)
	}

	return target, nil
}

// ApplySnapshotSet unpacks, verifies, and atomically switches to a new snapshot generation.
func (a *Applier) ApplySnapshotSet(stagingDir string, manifest *Manifest) error {
	if strings.TrimSpace(stagingDir) == "" {
		return errors.New("stagingDir is required")
	}

	// 1. Validate manifest (load from stagingDir if nil)
	if manifest == nil {
		loadedManifest, err := LoadManifest(filepath.Join(stagingDir, "manifest.json"))
		if err != nil {
			return fmt.Errorf("load manifest from staging: %w", err)
		}
		manifest = loadedManifest
	}
	if err := manifest.Validate(); err != nil {
		return fmt.Errorf("manifest validation failed: %w", err)
	}

	// 2. Verify manifest cryptographic signature
	manifestFile := filepath.Join(stagingDir, "manifest.json")
	manifestSig := filepath.Join(stagingDir, "manifest.json.sig")
	if err := VerifyAsset(manifestFile, manifestSig, a.cfg.PubKeyStr); err != nil {
		return fmt.Errorf("verify manifest signature: %w", err)
	}

	// 3. Target generation path
	genDirName := "gen_" + manifest.SnapshotSetID
	genDir := filepath.Join(a.cfg.DataDir, "gens", genDirName)

	// Idempotency: if already active, return nil without doing redundant work
	currentPtr, _ := a.ActiveGeneration()
	if currentPtr != nil && currentPtr.SnapshotSetID == manifest.SnapshotSetID {
		if fi, statErr := os.Stat(genDir); statErr == nil && fi.IsDir() {
			return nil
		}
	}

	// If directory already exists but is not active (e.g. failed/partial previous attempt), clear it
	if _, err := os.Stat(genDir); err == nil {
		if err := os.RemoveAll(genDir); err != nil {
			return fmt.Errorf("clean incomplete generation dir %s: %w", genDir, err)
		}
	}

	if err := os.MkdirAll(genDir, 0755); err != nil {
		return fmt.Errorf("create generation dir %s: %w", genDir, err)
	}

	// Guard against incomplete generation directories on failure
	success := false
	defer func() {
		if !success {
			_ = os.RemoveAll(genDir)
		}
	}()

	// 4. For each asset in manifest.Assets (deterministic sorted order)
	assetNames := make([]string, 0, len(manifest.Assets))
	for name := range manifest.Assets {
		assetNames = append(assetNames, name)
	}
	sort.Strings(assetNames)

	ctx := context.Background()

	for _, name := range assetNames {
		asset := manifest.Assets[name]

		assetFile := asset.Path
		if !filepath.IsAbs(assetFile) {
			assetFile = filepath.Join(stagingDir, assetFile)
		}

		if fi, err := os.Stat(assetFile); err != nil || fi.IsDir() {
			return fmt.Errorf("asset file %s missing: %w", assetFile, err)
		}

		sigFile := assetFile + ".sig"
		if fi, err := os.Stat(sigFile); err != nil || fi.IsDir() {
			return fmt.Errorf("asset signature file %s missing: %w", sigFile, err)
		}

		// Verify Minisign signature
		if err := VerifyAsset(assetFile, sigFile, a.cfg.PubKeyStr); err != nil {
			return fmt.Errorf("asset %s signature verification failed: %w", name, err)
		}

		// Verify SHA-256 matches manifest
		compHash, err := hashFileSHA256(assetFile)
		if err != nil {
			return fmt.Errorf("hash asset %s: %w", name, err)
		}
		if !strings.EqualFold(compHash, asset.SHA256) {
			return fmt.Errorf("asset %s sha256 mismatch: got %s, want %s", name, compHash, asset.SHA256)
		}

		// Decompress LZMA to target database file in genDir
		targetDBFileName := name
		if !strings.HasSuffix(targetDBFileName, ".db") {
			targetDBFileName += ".db"
		}
		targetDBFile := filepath.Join(genDir, targetDBFileName)

		if err := DecompressLZMA(assetFile, targetDBFile); err != nil {
			return fmt.Errorf("decompress asset %s to %s: %w", name, targetDBFile, err)
		}

		// Verify SQLite database integrity via PRAGMA integrity_check
		if err := checkDBIntegrity(ctx, targetDBFile); err != nil {
			return fmt.Errorf("db integrity check failed on %s: %w", targetDBFile, err)
		}
	}

	// 5. Copy manifest.json and manifest.json.sig into genDir
	if err := copyFile(manifestFile, filepath.Join(genDir, "manifest.json")); err != nil {
		return fmt.Errorf("copy manifest to %s: %w", genDir, err)
	}
	if err := copyFile(manifestSig, filepath.Join(genDir, "manifest.json.sig")); err != nil {
		return fmt.Errorf("copy manifest signature to %s: %w", genDir, err)
	}

	// 6. Read current active_generation.json (if exists) for previous generation details
	var prevSetID, prevGenDir string
	if currentPtr != nil && currentPtr.SnapshotSetID != "" {
		prevSetID = currentPtr.SnapshotSetID
		prevGenDir = currentPtr.GenerationDir
	}

	// 7. Construct new GenerationPointer
	relGenDir := filepath.ToSlash(filepath.Join("gens", genDirName))
	newPointer := GenerationPointer{
		SnapshotSetID:         manifest.SnapshotSetID,
		GenerationDir:         relGenDir,
		AppliedAtUTC:          time.Now().UTC().Format(time.RFC3339),
		SchemaVersion:         manifest.SchemaVersion,
		PreviousSnapshotSetID: prevSetID,
		PreviousGenerationDir: prevGenDir,
	}

	// 8. Atomically write new active_generation.json (write to temp on same volume, then rename)
	activeFile := filepath.Join(a.cfg.DataDir, "active_generation.json")
	tmpFile := filepath.Join(a.cfg.DataDir, "active_generation.json.tmp")

	data, err := json.MarshalIndent(newPointer, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal generation pointer: %w", err)
	}
	data = append(data, '\n')

	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return fmt.Errorf("write active_generation.json.tmp: %w", err)
	}

	if err := os.Rename(tmpFile, activeFile); err != nil {
		_ = os.Remove(activeFile)
		if err2 := os.Rename(tmpFile, activeFile); err2 != nil {
			_ = os.Remove(tmpFile)
			return fmt.Errorf("atomic rename active generation pointer: %w", err2)
		}
	}

	success = true

	// 9. Retention policy: Keep current gen_N and gen_N-1. Clean up older folders gen_N-2...
	a.applyRetentionPolicy(newPointer)

	return nil
}

// Rollback rolls back the active generation pointer to the previous generation (gen_N-1).
func (a *Applier) Rollback() error {
	ptr, err := a.ActiveGeneration()
	if err != nil {
		return fmt.Errorf("read active generation for rollback: %w", err)
	}

	if strings.TrimSpace(ptr.PreviousGenerationDir) == "" || strings.TrimSpace(ptr.PreviousSnapshotSetID) == "" {
		return errors.New("no previous generation available for rollback")
	}

	prevDir := ptr.PreviousGenerationDir
	if !filepath.IsAbs(prevDir) {
		prevDir = filepath.Join(a.cfg.DataDir, filepath.FromSlash(prevDir))
	}

	fi, err := os.Stat(prevDir)
	if err != nil || !fi.IsDir() {
		return fmt.Errorf("previous generation directory %s not found on disk: %w", prevDir, err)
	}

	schemaVersion := ptr.SchemaVersion
	prevManifestPath := filepath.Join(prevDir, "manifest.json")
	if prevM, err := LoadManifest(prevManifestPath); err == nil && prevM.SchemaVersion > 0 {
		schemaVersion = prevM.SchemaVersion
	}

	rolledBackPointer := GenerationPointer{
		SnapshotSetID:         ptr.PreviousSnapshotSetID,
		GenerationDir:         ptr.PreviousGenerationDir,
		AppliedAtUTC:          time.Now().UTC().Format(time.RFC3339),
		SchemaVersion:         schemaVersion,
		PreviousSnapshotSetID: "",
		PreviousGenerationDir: "",
	}

	activeFile := filepath.Join(a.cfg.DataDir, "active_generation.json")
	tmpFile := filepath.Join(a.cfg.DataDir, "active_generation.json.tmp")

	data, err := json.MarshalIndent(rolledBackPointer, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal rollback pointer: %w", err)
	}
	data = append(data, '\n')

	if err := os.WriteFile(tmpFile, data, 0644); err != nil {
		return fmt.Errorf("write active_generation.json.tmp for rollback: %w", err)
	}

	if err := os.Rename(tmpFile, activeFile); err != nil {
		_ = os.Remove(activeFile)
		if err2 := os.Rename(tmpFile, activeFile); err2 != nil {
			_ = os.Remove(tmpFile)
			return fmt.Errorf("atomic rename active generation pointer during rollback: %w", err2)
		}
	}

	return nil
}

// applyRetentionPolicy removes generation directories that are neither active nor previous.
func (a *Applier) applyRetentionPolicy(current GenerationPointer) {
	gensDir := filepath.Join(a.cfg.DataDir, "gens")
	entries, err := os.ReadDir(gensDir)
	if err != nil {
		return
	}

	keepDirs := make(map[string]bool)
	if current.GenerationDir != "" {
		keepDirs[filepath.Base(filepath.FromSlash(current.GenerationDir))] = true
	}
	if current.PreviousGenerationDir != "" {
		keepDirs[filepath.Base(filepath.FromSlash(current.PreviousGenerationDir))] = true
	}

	for _, entry := range entries {
		if !entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasPrefix(name, "gen_") {
			continue
		}
		if !keepDirs[name] {
			// Older generation gen_N-2... Clean up best-effort (ignore lock errors on open files)
			_ = os.RemoveAll(filepath.Join(gensDir, name))
		}
	}
}

// checkDBIntegrity opens the SQLite database read-only and asserts PRAGMA integrity_check is "ok".
func checkDBIntegrity(ctx context.Context, targetDBFile string) error {
	chkDB, err := db.OpenRO(targetDBFile)
	if err != nil {
		return fmt.Errorf("open ro for integrity check: %w", err)
	}
	defer chkDB.Close()

	rows, err := chkDB.QueryContext(ctx, "PRAGMA integrity_check")
	if err != nil {
		return fmt.Errorf("query integrity_check: %w", err)
	}
	defer rows.Close()

	var results []string
	for rows.Next() {
		var line string
		if err := rows.Scan(&line); err != nil {
			return fmt.Errorf("scan integrity result: %w", err)
		}
		results = append(results, strings.TrimSpace(line))
	}
	if err := rows.Err(); err != nil {
		return fmt.Errorf("rows error: %w", err)
	}

	if len(results) == 0 {
		return errors.New("no result returned from PRAGMA integrity_check")
	}

	if len(results) != 1 || !strings.EqualFold(results[0], "ok") {
		return fmt.Errorf("integrity check reported errors: %s", strings.Join(results, "; "))
	}

	return nil
}

// hashFileSHA256 returns the hex-encoded SHA-256 digest of filePath.
func hashFileSHA256(filePath string) (string, error) {
	f, err := os.Open(filePath)
	if err != nil {
		return "", err
	}
	defer f.Close()

	h := sha256.New()
	if _, err := io.Copy(h, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// copyFile copies a file from src to dst atomically.
func copyFile(src, dst string) error {
	in, err := os.Open(src)
	if err != nil {
		return err
	}
	defer in.Close()

	if err := os.MkdirAll(filepath.Dir(dst), 0755); err != nil {
		return err
	}

	out, err := os.Create(dst)
	if err != nil {
		return err
	}
	defer func() {
		_ = out.Close()
	}()

	if _, err := io.Copy(out, in); err != nil {
		return err
	}
	return out.Sync()
}
