package snapshot

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/ulikunitz/xz/lzma"
	_ "modernc.org/sqlite"
)

type countWriter struct {
	w       io.Writer
	written int64
}

func (c *countWriter) Write(p []byte) (int, error) {
	n, err := c.w.Write(p)
	c.written += int64(n)
	return n, err
}

// VacuumInto performs an atomic SQLite VACUUM INTO operation to targetPath.
// If targetPath already exists, it is deleted first because SQLite requires a clean target.
func VacuumInto(ctx context.Context, srcDB *sql.DB, targetPath string) error {
	if srcDB == nil {
		return errors.New("srcDB is nil")
	}
	if targetPath == "" {
		return errors.New("targetPath is empty")
	}

	cleanPath := filepath.Clean(targetPath)
	dir := filepath.Dir(cleanPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("create target dir %s: %w", dir, err)
	}

	if _, err := os.Stat(cleanPath); err == nil {
		if err := os.Remove(cleanPath); err != nil {
			return fmt.Errorf("remove existing target %s: %w", cleanPath, err)
		}
	}

	normalizedPath := filepath.ToSlash(cleanPath)
	// Try parameterized VACUUM INTO ? first; fallback to clean escaped string literal if needed.
	_, err := srcDB.ExecContext(ctx, "VACUUM INTO ?", normalizedPath)
	if err != nil {
		escaped := strings.ReplaceAll(normalizedPath, "'", "''")
		_, err = srcDB.ExecContext(ctx, fmt.Sprintf("VACUUM INTO '%s'", escaped))
		if err != nil {
			return fmt.Errorf("vacuum into %s: %w", cleanPath, err)
		}
	}

	fi, err := os.Stat(cleanPath)
	if err != nil {
		return fmt.Errorf("vacuum target file missing: %w", err)
	}
	if fi.Size() == 0 {
		return fmt.Errorf("vacuum target file is empty: %s", cleanPath)
	}
	return nil
}

// CompressLZMA compresses srcPath to dstPath using standard LZMA format,
// streaming data through a single pass while calculating raw and compressed sizes and SHA-256.
func CompressLZMA(srcPath, dstPath string) (compressedSHA256 string, compressedSize, rawSize int64, err error) {
	srcFile, err := os.Open(srcPath)
	if err != nil {
		return "", 0, 0, fmt.Errorf("open src %s: %w", srcPath, err)
	}
	defer srcFile.Close()

	if err := os.MkdirAll(filepath.Dir(dstPath), 0755); err != nil {
		return "", 0, 0, fmt.Errorf("create dst dir: %w", err)
	}

	dstFile, err := os.Create(dstPath)
	if err != nil {
		return "", 0, 0, fmt.Errorf("create dst %s: %w", dstPath, err)
	}
	defer func() {
		if err != nil {
			_ = dstFile.Close()
			_ = os.Remove(dstPath)
		}
	}()

	compHasher := sha256.New()
	compCounter := &countWriter{w: io.MultiWriter(dstFile, compHasher)}

	lzWriter, err := lzma.NewWriter(compCounter)
	if err != nil {
		_ = dstFile.Close()
		return "", 0, 0, fmt.Errorf("create lzma writer: %w", err)
	}

	rawHasher := sha256.New()
	rawCounter := &countWriter{w: io.MultiWriter(lzWriter, rawHasher)}

	buf := make([]byte, 1<<20) // 1MB buffer
	if _, err = io.CopyBuffer(rawCounter, srcFile, buf); err != nil {
		_ = lzWriter.Close()
		_ = dstFile.Close()
		return "", 0, 0, fmt.Errorf("compress stream copy: %w", err)
	}

	if err = lzWriter.Close(); err != nil {
		_ = dstFile.Close()
		return "", 0, 0, fmt.Errorf("close lzma writer: %w", err)
	}

	if err = dstFile.Sync(); err != nil {
		_ = dstFile.Close()
		return "", 0, 0, fmt.Errorf("sync dst file: %w", err)
	}

	if err = dstFile.Close(); err != nil {
		return "", 0, 0, fmt.Errorf("close dst file: %w", err)
	}

	compressedSHA256 = hex.EncodeToString(compHasher.Sum(nil))
	compressedSize = compCounter.written
	rawSize = rawCounter.written

	return compressedSHA256, compressedSize, rawSize, nil
}

// DecompressLZMA decompresses an LZMA file at srcPath to dstPath.
func DecompressLZMA(srcPath, dstPath string) error {
	srcFile, err := os.Open(srcPath)
	if err != nil {
		return fmt.Errorf("open src %s: %w", srcPath, err)
	}
	defer srcFile.Close()

	if err := os.MkdirAll(filepath.Dir(dstPath), 0755); err != nil {
		return fmt.Errorf("create dst dir: %w", err)
	}

	dstFile, err := os.Create(dstPath)
	if err != nil {
		return fmt.Errorf("create dst %s: %w", dstPath, err)
	}

	lzReader, err := lzma.NewReader(srcFile)
	if err != nil {
		_ = dstFile.Close()
		_ = os.Remove(dstPath)
		return fmt.Errorf("create lzma reader: %w", err)
	}

	buf := make([]byte, 1<<20)
	if _, err = io.CopyBuffer(dstFile, lzReader, buf); err != nil {
		_ = dstFile.Close()
		_ = os.Remove(dstPath)
		return fmt.Errorf("decompress stream copy: %w", err)
	}

	if err := dstFile.Sync(); err != nil {
		_ = dstFile.Close()
		_ = os.Remove(dstPath)
		return fmt.Errorf("sync dst: %w", err)
	}

	if err := dstFile.Close(); err != nil {
		_ = os.Remove(dstPath)
		return fmt.Errorf("close dst: %w", err)
	}

	return nil
}

// BuildSnapshotSet builds a consistent snapshot set for the given databases,
// vacuums each database atomically, compresses each to LZMA, records SHA-256 and sizes,
// and saves a unified manifest.json in outDir.
func BuildSnapshotSet(ctx context.Context, dbs map[string]*sql.DB, outDir string, setID string) (*Manifest, error) {
	if len(dbs) == 0 {
		return nil, errors.New("no databases provided for snapshot set")
	}

	if setID == "" {
		randBytes := make([]byte, 4)
		if _, err := rand.Read(randBytes); err != nil {
			return nil, fmt.Errorf("generate random snapshot set id: %w", err)
		}
		setID = fmt.Sprintf("%s-%s", time.Now().UTC().Format("20060102T150405Z"), hex.EncodeToString(randBytes))
	}

	if err := os.MkdirAll(outDir, 0755); err != nil {
		return nil, fmt.Errorf("create outDir %s: %w", outDir, err)
	}

	manifest := NewManifest(setID, 1)

	// Process databases in sorted order for determinism
	names := make([]string, 0, len(dbs))
	for name := range dbs {
		names = append(names, name)
	}
	sort.Strings(names)

	for _, name := range names {
		dbConn := dbs[name]
		if dbConn == nil {
			return nil, fmt.Errorf("database handle for %q is nil", name)
		}

		rawTmp := filepath.Join(outDir, name+".raw.tmp")
		defer os.Remove(rawTmp)

		if err := VacuumInto(ctx, dbConn, rawTmp); err != nil {
			return nil, fmt.Errorf("vacuum database %q: %w", name, err)
		}

		assetName := name + ".db.lzma"
		dstPath := filepath.Join(outDir, assetName)

		compSHA256, compSize, rawSize, err := CompressLZMA(rawTmp, dstPath)
		_ = os.Remove(rawTmp)
		if err != nil {
			return nil, fmt.Errorf("compress database %q: %w", name, err)
		}

		manifest.AddAsset(name, assetName, compSHA256, compSize, rawSize)
	}

	if err := manifest.Validate(); err != nil {
		return nil, fmt.Errorf("manifest validation: %w", err)
	}

	manifestPath := filepath.Join(outDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		return nil, fmt.Errorf("save manifest: %w", err)
	}

	return manifest, nil
}
