package update

import (
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"aead.dev/minisign"
)

// Download starts fetching the installer advertised by the last Check. It
// returns as soon as the job is started; Progress reports the rest.
func (s *Service) Download(ctx context.Context) error {
	p, ok := s.preparedAsset()
	if !ok {
		res, err := s.Check(ctx)
		if err != nil {
			return err
		}
		if !res.Available || !res.Installable {
			return errors.New("نسخهٔ قابل‌نصبِ تازه‌ای موجود نیست")
		}
		p, ok = s.preparedAsset()
		if !ok {
			return errors.New("مانیفستِ به‌روزرسانی در دسترس نیست")
		}
	}

	s.mu.Lock()
	if s.state.Status == StatusDownloading || s.state.Status == StatusVerifying {
		s.mu.Unlock()
		return errors.New("دانلودِ دیگری در جریان است")
	}
	jobCtx, cancel := context.WithCancel(context.Background())
	s.job = &downloadJob{cancel: cancel}
	s.state = State{Status: StatusDownloading, Version: p.version, Total: p.asset.Size,
		UpdatedAt: s.cfg.Now().UTC().Format(time.RFC3339)}
	s.mu.Unlock()

	go s.runDownload(jobCtx, p)
	return nil
}

type preparedAsset struct {
	asset   Asset
	version string
}

func (s *Service) preparedAsset() (preparedAsset, bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if s.manifest == nil {
		return preparedAsset{}, false
	}
	asset, ok := s.manifest.Platforms[PlatformKey]
	if !ok || strings.TrimSpace(asset.URL) == "" {
		return preparedAsset{}, false
	}
	return preparedAsset{asset: asset, version: s.manifest.Version}, true
}

func (s *Service) runDownload(ctx context.Context, p preparedAsset) {
	dir := filepath.Join(os.TempDir(), "bors_update", "v"+safeSegment(p.version))
	if err := os.MkdirAll(dir, 0o755); err != nil {
		s.fail("ساختِ پوشهٔ دانلود ناموفق: "+err.Error(), "")
		return
	}
	final := filepath.Join(dir, artifactName(p.asset.URL))

	sum, size, err := s.fetchArtifact(ctx, p.asset, final+".part")
	if err != nil {
		_ = os.Remove(final + ".part")
		s.fail(err.Error(), "")
		return
	}
	if p.asset.Size > 0 && size != p.asset.Size {
		_ = os.Remove(final + ".part")
		s.fail(fmt.Sprintf("اندازهٔ فایل دانلودشده %d بایت است، مانیفست %d اعلام کرده بود", size, p.asset.Size), "")
		return
	}

	s.setState(func(st *State) {
		st.Status = StatusVerifying
		st.Downloaded = size
		st.SHA256 = sum
		st.Version = p.version
	})
	if p.asset.SHA256 != "" && !strings.EqualFold(p.asset.SHA256, sum) {
		_ = os.Remove(final + ".part")
		s.fail("sha256 فایل با مانیفست نمی‌خواند؛ فایل رد شد", "")
		return
	}
	if err := verifyArtifact(final+".part", p.asset.Signature); err != nil {
		_ = os.Remove(final + ".part")
		s.fail("راستی‌آزمایی امضای نصب‌کننده ناموفق: "+err.Error(), "")
		return
	}
	sigRaw, err := decodeSignature(p.asset.Signature)
	if err != nil {
		_ = os.Remove(final + ".part")
		s.fail("امضای مانیفست خوانا نیست: "+err.Error(), "")
		return
	}
	if err := os.Rename(final+".part", final); err != nil {
		_ = os.Remove(final + ".part")
		s.fail("جابه‌جاییِ فایلِ دانلودشده ناموفق: "+err.Error(), "")
		return
	}
	if err := os.WriteFile(final+".sig", sigRaw, 0o644); err != nil {
		_ = os.Remove(final)
		s.fail("نوشتنِ فایلِ امضا ناموفق: "+err.Error(), "")
		return
	}
	s.mu.Lock()
	s.state = State{Status: StatusReady, Downloaded: size, Total: size, Version: p.version,
		Path: final, Signature: p.asset.Signature, SHA256: sum,
		UpdatedAt: s.cfg.Now().UTC().Format(time.RFC3339)}
	s.manifest = nil
	s.job = nil
	s.mu.Unlock()
	s.log.Info("update artifact verified", "version", p.version, "bytes", size, "sha256", sum)
}

// fetchArtifact streams the asset into dst and returns its sha256 and size.
func (s *Service) fetchArtifact(ctx context.Context, asset Asset, dst string) (string, int64, error) {
	if local, ok := localPath(asset.URL); ok {
		in, err := os.Open(local)
		if err != nil {
			return "", 0, fmt.Errorf("باز کردن فایلِ محلی ناموفق: %w", err)
		}
		defer in.Close()
		return s.copyWithProgress(ctx, in, dst, asset.Size)
	}
	u, err := url.Parse(asset.URL)
	if err != nil {
		return "", 0, fmt.Errorf("نشانیِ دانلود نامعتبر: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return "", 0, err
	}
	req.Header.Set("User-Agent", "BorsTerminal-Updater")
	resp, err := s.hc.Do(req)
	if err != nil {
		return "", 0, fmt.Errorf("دریافتِ نصب‌کننده ناموفق: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return "", 0, fmt.Errorf("دریافتِ نصب‌کننده: HTTP %d", resp.StatusCode)
	}
	if resp.ContentLength > 0 && resp.ContentLength > maxArtifactBytes {
		return "", 0, fmt.Errorf("فایلِ نصب بزرگ‌تر از حدِ مجاز است (%d بایت)", resp.ContentLength)
	}
	return s.copyWithProgress(ctx, resp.Body, dst, asset.Size)
}

func (s *Service) copyWithProgress(ctx context.Context, src io.Reader, dst string, declared int64) (string, int64, error) {
	out, err := os.Create(dst)
	if err != nil {
		return "", 0, fmt.Errorf("ساختِ فایلِ موقت ناموفق: %w", err)
	}
	hasher := sha256.New()
	buf := make([]byte, 256<<10)
	var written int64
	last := time.Now()
	for {
		if err := ctx.Err(); err != nil {
			_ = out.Close()
			return "", written, err
		}
		n, readErr := src.Read(buf)
		if n > 0 {
			written += int64(n)
			if written > maxArtifactBytes || (declared > 0 && written > declared) {
				_ = out.Close()
				return "", written, errors.New("حجمِ دانلود از مقدارِ اعلام‌شده فراتر رفت")
			}
			if _, err := out.Write(buf[:n]); err != nil {
				_ = out.Close()
				return "", written, fmt.Errorf("نوشتنِ فایلِ دانلودشده ناموفق: %w", err)
			}
			hasher.Write(buf[:n])
			if time.Since(last) > 150*time.Millisecond {
				last = time.Now()
				s.setState(func(st *State) { st.Downloaded = written })
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			_ = out.Close()
			return "", written, fmt.Errorf("قطعِ دانلود: %w", readErr)
		}
	}
	if err := out.Sync(); err != nil {
		_ = out.Close()
		return "", written, err
	}
	if err := out.Close(); err != nil {
		return "", written, err
	}
	s.setState(func(st *State) { st.Downloaded = written })
	return hex.EncodeToString(hasher.Sum(nil)), written, nil
}

func (s *Service) fail(message, path string) {
	s.mu.Lock()
	s.state = State{Status: StatusError, Message: message, Path: path,
		UpdatedAt: s.cfg.Now().UTC().Format(time.RFC3339)}
	s.manifest = nil
	s.job = nil
	s.installing = false
	s.mu.Unlock()
	s.log.Warn("update failed", "err", message)
}

// verifyArtifact checks path against minisign text or its base64-wrapped form.
func verifyArtifact(path, signature string) error {
	sig, err := decodeSignature(signature)
	if err != nil {
		return err
	}
	pub, err := parsePublicKey(pubKey)
	if err != nil {
		return err
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	if !minisign.Verify(pub, raw, sig) {
		return errors.New("امضا معتبر نیست یا فایل دستکاری شده است")
	}
	return nil
}

// decodeSignature accepts raw minisign signature text and the base64 wrapper
// used by latest.json / tauri.conf.json.
func decodeSignature(signature string) ([]byte, error) {
	clean := strings.TrimSpace(signature)
	if clean == "" {
		return nil, errors.New("امضا خالی است")
	}
	if strings.HasPrefix(strings.TrimSpace(clean), "untrusted comment:") {
		return []byte(signature), nil
	}
	dec, err := base64.StdEncoding.DecodeString(clean)
	if err != nil {
		return nil, errors.New("امضا نه متنِ minisign است نه base64")
	}
	if !strings.HasPrefix(string(dec), "untrusted comment:") {
		return nil, errors.New("محتوای base64 امضای minisign نیست")
	}
	return dec, nil
}

func parsePublicKey(text string) (minisign.PublicKey, error) {
	clean := strings.TrimSpace(text)
	var pub minisign.PublicKey
	if err := pub.UnmarshalText([]byte(clean)); err == nil {
		return pub, nil
	}
	dec, err := base64.StdEncoding.DecodeString(clean)
	if err != nil {
		return pub, errors.New("کلیدِ عمومیِ minisign خوانا نیست")
	}
	if err := pub.UnmarshalText(dec); err != nil {
		return pub, errors.New("کلیدِ عمومیِ minisign خوانا نیست")
	}
	return pub, nil
}

var artifactSanitizer = regexp.MustCompile(`[^A-Za-z0-9._-]+`)

func artifactName(rawURL string) string {
	name := ""
	if local, ok := localPath(rawURL); ok {
		name = filepath.Base(local)
	} else if u, err := url.Parse(rawURL); err == nil {
		name = filepath.Base(u.Path)
	} else {
		name = filepath.Base(rawURL)
	}
	name = strings.TrimSpace(artifactSanitizer.ReplaceAllString(name, "_"))
	name = strings.Trim(name, "._")
	if name == "" || name == ".." {
		name = "setup.exe"
	}
	return name
}

func safeSegment(v string) string {
	out := artifactSanitizer.ReplaceAllString(strings.TrimSpace(v), "_")
	out = strings.Trim(out, "._")
	if out == "" {
		return "unknown"
	}
	return out
}
