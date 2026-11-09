package update

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"
)

const backupDirName = "app-before-update"

// userDataNames never enter the rollback backup and are never touched by a
// restore: they are the user's databases, settings and caches.
var userDataNames = map[string]bool{
	"market.db": true, "market.db-wal": true, "market.db-shm": true,
	"market.db.baseline": true, "market.db.gz": true, "market.db.lzma": true,
	"market.db.part": true, "market.db.seed.src": true,
	"market.db.seed.src-wal": true, "market.db.seed.src-shm": true,
	"user.db": true, "user.db-wal": true, "user.db-shm": true,
	"oc_client.db": true, "oc_client.db-wal": true, "oc_client.db-shm": true,
	"update_last.json": true, ".screener_cache.json": true,
	"bors_portable.flag": true, ".setup_password.iss": true, "setup.pw": true,
}

var userDataDirs = map[string]bool{"backups": true, "logs": true, "log": true, "updates": true, "oc": true}

type backupFile struct {
	Path   string `json:"path"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256"`
}

type backupManifest struct {
	Version   string       `json:"version"`
	CreatedAt string       `json:"created_at"`
	Files     []backupFile `json:"files"`
}

func excludedFromBackup(rel string) bool {
	rel = filepath.ToSlash(rel)
	if strings.Contains(rel, "/") {
		first := strings.SplitN(rel, "/", 2)[0]
		if userDataDirs[first] {
			return true
		}
		return false
	}
	if userDataNames[rel] {
		return true
	}
	return strings.HasSuffix(strings.ToLower(rel), ".log")
}

func isUserDataRel(rel string) bool {
	rel = filepath.ToSlash(rel)
	first := rel
	if i := strings.IndexByte(rel, '/'); i >= 0 {
		first = rel[:i]
	}
	if userDataDirs[first] {
		return true
	}
	return userDataNames[rel]
}

// backupProgramFiles snapshots every program file (never user data) into
// dataDir/backups/app-before-update and returns that directory.
func backupProgramFiles(installDir, dataDir, version string) (string, error) {
	installDir = filepath.Clean(installDir)
	backupRoot := filepath.Join(dataDir, "backups", backupDirName)
	staging := backupRoot + ".tmp"
	if err := os.RemoveAll(staging); err != nil {
		return "", err
	}
	if err := os.MkdirAll(staging, 0o755); err != nil {
		return "", err
	}
	manifest := backupManifest{Version: version, CreatedAt: time.Now().UTC().Format(time.RFC3339)}
	err := filepath.Walk(installDir, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if path == installDir {
			return nil
		}
		rel, err := filepath.Rel(installDir, path)
		if err != nil {
			return err
		}
		if info.IsDir() {
			if excludedFromBackup(rel) || firstSegmentIsUserDir(rel) {
				return filepath.SkipDir
			}
			return nil
		}
		if !info.Mode().IsRegular() || excludedFromBackup(rel) {
			return nil
		}
		sum, size, err := copyFileHashed(path, filepath.Join(staging, rel))
		if err != nil {
			return fmt.Errorf("backup %s: %w", rel, err)
		}
		manifest.Files = append(manifest.Files, backupFile{Path: filepath.ToSlash(rel), Size: size, SHA256: sum})
		return nil
	})
	if err != nil {
		_ = os.RemoveAll(staging)
		return "", err
	}
	body, err := json.MarshalIndent(manifest, "", "  ")
	if err != nil {
		_ = os.RemoveAll(staging)
		return "", err
	}
	if err := os.WriteFile(filepath.Join(staging, "backup.json"), body, 0o644); err != nil {
		_ = os.RemoveAll(staging)
		return "", err
	}
	if err := os.RemoveAll(backupRoot); err != nil {
		_ = os.RemoveAll(staging)
		return "", err
	}
	if err := os.Rename(staging, backupRoot); err != nil {
		return "", err
	}
	return backupRoot, nil
}

func firstSegmentIsUserDir(rel string) bool {
	rel = filepath.ToSlash(rel)
	first := strings.SplitN(rel, "/", 2)[0]
	return userDataDirs[first]
}

func copyFileHashed(src, dst string) (string, int64, error) {
	if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
		return "", 0, err
	}
	in, err := os.Open(src)
	if err != nil {
		return "", 0, err
	}
	defer in.Close()
	out, err := os.Create(dst)
	if err != nil {
		return "", 0, err
	}
	h := sha256.New()
	n, err := io.Copy(io.MultiWriter(out, h), in)
	if closeErr := out.Close(); err == nil {
		err = closeErr
	}
	if err != nil {
		return "", n, err
	}
	return hex.EncodeToString(h.Sum(nil)), n, nil
}

// readBackupManifest loads and validates backup.json.
func readBackupManifest(backupDir string) (backupManifest, error) {
	var m backupManifest
	raw, err := os.ReadFile(filepath.Join(backupDir, "backup.json"))
	if err != nil {
		return m, err
	}
	if err := json.Unmarshal(raw, &m); err != nil {
		return m, err
	}
	if strings.TrimSpace(m.Version) == "" || len(m.Files) == 0 {
		return m, errors.New("backup manifest is empty")
	}
	return m, nil
}

// restoreBackup validates every backed-up file before touching the install,
// copies the old program files back, and prunes files the new version added.
func restoreBackup(installDir, backupDir string) error {
	installDir = filepath.Clean(installDir)
	manifest, err := readBackupManifest(backupDir)
	if err != nil {
		return fmt.Errorf("backup manifest: %w", err)
	}
	for _, f := range manifest.Files {
		clean, err := confinedRel(f.Path)
		if err != nil {
			return err
		}
		if isUserDataRel(clean) {
			return fmt.Errorf("backup unexpectedly contains user data %q", f.Path)
		}
		sum, _, err := hashFile(filepath.Join(backupDir, filepath.FromSlash(clean)))
		if err != nil {
			return fmt.Errorf("backup file %s: %w", f.Path, err)
		}
		if !strings.EqualFold(sum, f.SHA256) {
			return fmt.Errorf("backup file %s is corrupt", f.Path)
		}
	}
	for _, f := range manifest.Files {
		clean, err := confinedRel(f.Path)
		if err != nil {
			return err
		}
		if _, _, err := copyFileHashed(filepath.Join(backupDir, filepath.FromSlash(clean)),
			filepath.Join(installDir, filepath.FromSlash(clean))); err != nil {
			return fmt.Errorf("restore %s: %w", f.Path, err)
		}
	}
	// Files created by the failed new version inside program directories must
	// not survive next to the restored old binaries.
	keep := make(map[string]bool, len(manifest.Files))
	for _, f := range manifest.Files {
		keep[filepath.ToSlash(f.Path)] = true
	}
	for _, dir := range []string{"frontend", "data"} {
		root := filepath.Join(installDir, dir)
		if _, err := os.Stat(root); err != nil {
			continue
		}
		_ = filepath.Walk(root, func(path string, info os.FileInfo, walkErr error) error {
			if walkErr != nil || info == nil || info.IsDir() {
				return nil
			}
			rel, err := filepath.Rel(installDir, path)
			if err != nil {
				return nil
			}
			if !keep[filepath.ToSlash(rel)] {
				_ = os.Remove(path)
			}
			return nil
		})
	}
	return nil
}

func confinedRel(rel string) (string, error) {
	clean := filepath.Clean(filepath.FromSlash(rel))
	if clean == "." || filepath.IsAbs(clean) || strings.HasPrefix(clean, "..") {
		return "", fmt.Errorf("backup path escapes the install directory: %q", rel)
	}
	return filepath.ToSlash(clean), nil
}

func hashFile(path string) (string, int64, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	h := sha256.New()
	n, err := io.Copy(h, f)
	if err != nil {
		return "", n, err
	}
	return hex.EncodeToString(h.Sum(nil)), n, nil
}

func removeBackup(dataDir string) {
	_ = os.RemoveAll(filepath.Join(dataDir, "backups", backupDirName))
}
