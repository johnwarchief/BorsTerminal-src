package sync

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"borsterminal/backend/internal/snapshot"
)

// DownloadAndApplySnapshot fetches the latest snapshot manifest and assets from baseURL,
// verifies their Minisign signatures and SHA-256 hashes, unpacks them via Applier into a new generation,
// and updates active_generation.json and codal_db_status.json throughout all stages.
func (h *Handler) DownloadAndApplySnapshot(ctx context.Context, baseURL string) error {
	pubKey := h.pubKey
	if pubKey == "" {
		pubKey = DefaultUpdatePubKey
	}

	applier, err := snapshot.NewApplier(snapshot.ApplierConfig{
		DataDir:   h.dataDir,
		PubKeyStr: pubKey,
	})
	if err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در تنظیمات اپلاییر اسنپ‌شات", err.Error(), h.clock())
		return fmt.Errorf("init applier: %w", err)
	}

	stagingBase := filepath.Join(h.dataDir, "staging")
	if err := os.MkdirAll(stagingBase, 0755); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در ساخت پوشه موقت", err.Error(), h.clock())
		return fmt.Errorf("create staging base: %w", err)
	}
	stagingDir, err := os.MkdirTemp(stagingBase, "dl_*")
	if err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در ساخت پوشه موقت", err.Error(), h.clock())
		return fmt.Errorf("create staging dir: %w", err)
	}
	defer os.RemoveAll(stagingDir)

	// Stage: Downloading (manifest)
	_ = writeCodalDBStatus(h.dataDir, "downloading", 5.0, "در حال دریافت مانیفست اسنپ‌شات...", "", h.clock())

	manifestPath := filepath.Join(stagingDir, "manifest.json")
	manifestSigPath := filepath.Join(stagingDir, "manifest.json.sig")

	manifestURL := fmt.Sprintf("%s/manifest.json", strings.TrimRight(baseURL, "/"))
	manifestSigURL := fmt.Sprintf("%s/manifest.json.sig", strings.TrimRight(baseURL, "/"))

	if err := h.downloadFile(ctx, manifestURL, manifestPath); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در دانلود مانیفست", err.Error(), h.clock())
		return fmt.Errorf("download manifest: %w", err)
	}

	if err := h.downloadFile(ctx, manifestSigURL, manifestSigPath); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در دانلود امضای مانیفست", err.Error(), h.clock())
		return fmt.Errorf("download manifest signature: %w", err)
	}

	// Verify manifest signature and integrity
	_ = writeCodalDBStatus(h.dataDir, "verifying", 15.0, "در حال راستی‌آزمایی مانیفست...", "", h.clock())

	if err := snapshot.VerifyAsset(manifestPath, manifestSigPath, pubKey); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در راستی‌آزمایی امضای مانیفست", err.Error(), h.clock())
		return fmt.Errorf("verify manifest signature: %w", err)
	}

	manifest, err := snapshot.LoadManifest(manifestPath)
	if err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در بارگذاری مانیفست", err.Error(), h.clock())
		return fmt.Errorf("load manifest: %w", err)
	}
	if err := manifest.Validate(); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در اعتبارسنجی مانیفست", err.Error(), h.clock())
		return fmt.Errorf("validate manifest: %w", err)
	}
	if len(manifest.Assets) == 0 {
		errNoAssets := errors.New("مانیفست فاقد هرگونه دارایی است")
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "مانیفست خالی است", errNoAssets.Error(), h.clock())
		return errNoAssets
	}

	// Stage: Downloading assets
	assetNames := make([]string, 0, len(manifest.Assets))
	for name := range manifest.Assets {
		assetNames = append(assetNames, name)
	}
	sort.Strings(assetNames)

	totalAssets := len(assetNames)
	for i, name := range assetNames {
		meta := manifest.Assets[name]
		assetRelPath := meta.Path
		assetDest := filepath.Join(stagingDir, assetRelPath)
		assetSigDest := filepath.Join(stagingDir, assetRelPath+".sig")

		if err := os.MkdirAll(filepath.Dir(assetDest), 0755); err != nil {
			_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در ساخت پوشه دارایی", err.Error(), h.clock())
			return fmt.Errorf("create asset dir: %w", err)
		}

		pct := 20.0 + (float64(i)/float64(totalAssets))*55.0
		detail := fmt.Sprintf("در حال دانلود دارایی %s (%d/%d)...", filepath.Base(assetRelPath), i+1, totalAssets)
		_ = writeCodalDBStatus(h.dataDir, "downloading", pct, detail, "", h.clock())

		assetURL := fmt.Sprintf("%s/%s", strings.TrimRight(baseURL, "/"), filepath.ToSlash(assetRelPath))
		if err := h.downloadFile(ctx, assetURL, assetDest); err != nil {
			_ = writeCodalDBStatus(h.dataDir, "error", 0, fmt.Sprintf("خطا در دانلود %s", assetRelPath), err.Error(), h.clock())
			return fmt.Errorf("download asset %s: %w", assetRelPath, err)
		}

		assetSigURL := fmt.Sprintf("%s/%s.sig", strings.TrimRight(baseURL, "/"), filepath.ToSlash(assetRelPath))
		if err := h.downloadFile(ctx, assetSigURL, assetSigDest); err != nil {
			_ = writeCodalDBStatus(h.dataDir, "error", 0, fmt.Sprintf("خطا در دانلود امضای %s", assetRelPath), err.Error(), h.clock())
			return fmt.Errorf("download asset signature %s: %w", assetRelPath, err)
		}
	}

	// Stage: Verifying assets
	_ = writeCodalDBStatus(h.dataDir, "verifying", 80.0, "در حال راستی‌آزمایی امضا و سلامت اسنپ‌شات...", "", h.clock())

	for _, name := range assetNames {
		meta := manifest.Assets[name]
		assetDest := filepath.Join(stagingDir, meta.Path)
		sigDest := assetDest + ".sig"

		if err := snapshot.VerifyAsset(assetDest, sigDest, pubKey); err != nil {
			_ = writeCodalDBStatus(h.dataDir, "error", 0, fmt.Sprintf("خطا در راستی‌آزمایی امضای دارایی %s", name), err.Error(), h.clock())
			return fmt.Errorf("verify asset %s signature: %w", name, err)
		}

		compHash, err := hashFileSHA256(assetDest)
		if err != nil {
			_ = writeCodalDBStatus(h.dataDir, "error", 0, fmt.Sprintf("خطا در محاسبه هش دارایی %s", name), err.Error(), h.clock())
			return fmt.Errorf("hash asset %s: %w", name, err)
		}
		if !strings.EqualFold(compHash, meta.SHA256) {
			errHash := fmt.Errorf("asset %s sha256 mismatch: got %s, want %s", name, compHash, meta.SHA256)
			_ = writeCodalDBStatus(h.dataDir, "error", 0, fmt.Sprintf("عدم تطابق هش دارایی %s", name), errHash.Error(), h.clock())
			return errHash
		}
	}

	// Stage: Applying snapshot set via Applier
	_ = writeCodalDBStatus(h.dataDir, "applying", 90.0, "در حال اعمال اسنپ‌شات و تعویض نسل دیتابیس...", "", h.clock())

	if err := applier.ApplySnapshotSet(stagingDir, manifest); err != nil {
		_ = writeCodalDBStatus(h.dataDir, "error", 0, "خطا در اعمال اسنپ‌شات", err.Error(), h.clock())
		return fmt.Errorf("apply snapshot set: %w", err)
	}

	// Stage: Done
	_ = writeCodalDBStatus(h.dataDir, "done", 100.0, "اسنپ‌شات با موفقیت اعمال شد.", "", h.clock())
	return nil
}

func (h *Handler) downloadFile(ctx context.Context, fileURL, destPath string) error {
	client := h.httpClient
	if client == nil {
		client = http.DefaultClient
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, fileURL, nil)
	if err != nil {
		return fmt.Errorf("create request for %s: %w", fileURL, err)
	}

	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("GET %s: %w", fileURL, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("GET %s failed with status %d", fileURL, resp.StatusCode)
	}

	tmpDest := destPath + ".tmp"
	f, err := os.Create(tmpDest)
	if err != nil {
		return fmt.Errorf("create tmp dest %s: %w", tmpDest, err)
	}

	if _, err := io.Copy(f, resp.Body); err != nil {
		_ = f.Close()
		_ = os.Remove(tmpDest)
		return fmt.Errorf("write %s: %w", tmpDest, err)
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(tmpDest)
		return err
	}

	if err := os.Rename(tmpDest, destPath); err != nil {
		_ = os.Remove(destPath)
		return os.Rename(tmpDest, destPath)
	}
	return nil
}

func hashFileSHA256(path string) (string, error) {
	f, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer f.Close()

	hasher := sha256.New()
	if _, err := io.Copy(hasher, f); err != nil {
		return "", err
	}
	return hex.EncodeToString(hasher.Sum(nil)), nil
}
