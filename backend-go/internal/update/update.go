// Package update implements the in-app application updater.
//
// The application is a Go backend + Tauri shell + SPA, shipped by the Inno
// Setup installer. The Tauri updater plugin can only install NSIS/MSI
// packages, not Inno Setup, so it cannot update this application. This
// package ports the signed contract the Python updater already used:
//
//	GET  /api/update/version    current version + rollback state
//	GET  /api/update/check      fetch the Go channel manifest (channel="go")
//	POST /api/update/download   download the installer and verify minisign
//	GET  /api/update/progress   download/verification state
//	POST /api/update/install    verify again, back up, install, restart
//	POST /api/update/rollback   restore the pre-update program files
//
// The artifact is trusted only through the embedded minisign public key; the
// manifest (served over HTTPS from the release) cannot make code trusted.
// User data (market.db*, user.db*, oc/, backups/, settings) is never part of
// the update or of the rollback backup.
package update

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
)

const (
	PlatformKey = "windows-x86_64"

	// DefaultManifestURL is the Go channel. The legacy latest.json points at
	// the Python installer and is deliberately not consumed: installing it
	// would replace this app with a different architecture.
	DefaultManifestURL = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download/latest-go.json"

	// productionPubKey is the minisign public key the Tauri signer uses. It is
	// public; the private key never exists in this repository or bundle.
	productionPubKey = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3NgpSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="

	maxManifestBytes = 4 << 20
	maxArtifactBytes = 1 << 30
)

// pubKey is overridden with -ldflags -X for isolated test channels.
// Production builds always use the embedded key.
var pubKey = productionPubKey

type Asset struct {
	URL       string `json:"url"`
	Signature string `json:"signature"`
	Size      int64  `json:"size"`
	SHA256    string `json:"sha256,omitempty"`
}

type Manifest struct {
	Channel   string           `json:"channel"`
	Version   string           `json:"version"`
	Notes     string           `json:"notes"`
	PubDate   string           `json:"pub_date"`
	Platforms map[string]Asset `json:"platforms"`
	Portable  *Asset           `json:"portable,omitempty"`
}

type Config struct {
	DataDir        string
	InstallDir     string
	CurrentVersion string
	Port           int
	Args           []string
	ManifestURL    string
	HTTPClient     *http.Client
	Logger         *slog.Logger
	Shutdown       func()
	// Now is overridable in tests; production uses time.Now.
	Now func() time.Time
}

type Status string

const (
	StatusIdle        Status = "idle"
	StatusDownloading Status = "downloading"
	StatusVerifying   Status = "verifying"
	StatusReady       Status = "ready"
	StatusInstalling  Status = "installing"
	StatusError       Status = "error"
)

type State struct {
	Status     Status `json:"status"`
	Downloaded int64  `json:"downloaded"`
	Total      int64  `json:"total"`
	Version    string `json:"version,omitempty"`
	Path       string `json:"path,omitempty"`
	Signature  string `json:"signature,omitempty"`
	SHA256     string `json:"sha256,omitempty"`
	Message    string `json:"message,omitempty"`
	UpdatedAt  string `json:"updated_at,omitempty"`
}

type CheckResult struct {
	Status         string `json:"status"`
	CurrentVersion string `json:"current_version"`
	LatestVersion  string `json:"latest_version"`
	Available      bool   `json:"available"`
	Notes          string `json:"notes,omitempty"`
	Date           string `json:"date,omitempty"`
	URL            string `json:"url,omitempty"`
	Signature      string `json:"signature,omitempty"`
	Size           int64  `json:"size,omitempty"`
	SHA256         string `json:"sha256,omitempty"`
	Portable       bool   `json:"portable"`
	Installable    bool   `json:"installable"`
	Delta          bool   `json:"delta"`
	Message        string `json:"message,omitempty"`
}

type LastUpdate struct {
	Status  string `json:"status"`
	From    string `json:"from,omitempty"`
	To      string `json:"to,omitempty"`
	At      string `json:"at,omitempty"`
	Message string `json:"message,omitempty"`
}

type VersionInfo struct {
	Version           string      `json:"version"`
	Mode              string      `json:"mode"`
	DataDir           string      `json:"data_dir"`
	InstallDir        string      `json:"install_dir"`
	RollbackAvailable bool        `json:"rollback_available"`
	RollbackVersion   string      `json:"rollback_version,omitempty"`
	LastUpdate        *LastUpdate `json:"last_update,omitempty"`
	Channel           string      `json:"channel"`
}

type Service struct {
	cfg Config
	log *slog.Logger
	hc  *http.Client

	mu         sync.Mutex
	state      State
	manifest   *Manifest
	base       string // manifest location for relative asset URLs
	job        *downloadJob
	installing bool
}

type downloadJob struct {
	cancel context.CancelFunc
}

func New(cfg Config) *Service {
	if cfg.InstallDir == "" {
		if exe, err := os.Executable(); err == nil {
			cfg.InstallDir = filepath.Dir(exe)
		}
	}
	if cfg.CurrentVersion == "" {
		cfg.CurrentVersion = versionFromFile(cfg.InstallDir)
	}
	if cfg.ManifestURL == "" {
		cfg.ManifestURL = os.Getenv("BORS_UPDATE_MANIFEST")
	}
	if cfg.ManifestURL == "" {
		cfg.ManifestURL = DefaultManifestURL
	}
	if cfg.HTTPClient == nil {
		cfg.HTTPClient = &http.Client{
			Transport: &http.Transport{
				Proxy:                 http.ProxyFromEnvironment,
				ResponseHeaderTimeout: 30 * time.Second,
				IdleConnTimeout:       30 * time.Second,
			},
		}
	}
	if cfg.Now == nil {
		cfg.Now = time.Now
	}
	logger := cfg.Logger
	if logger == nil {
		logger = slog.Default()
	}
	return &Service{cfg: cfg, log: logger, hc: cfg.HTTPClient, state: State{Status: StatusIdle}}
}

func (s *Service) ManifestURL() string { return s.cfg.ManifestURL }

func (s *Service) CurrentVersion() string {
	if strings.TrimSpace(s.cfg.CurrentVersion) != "" {
		return strings.TrimSpace(s.cfg.CurrentVersion)
	}
	return versionFromFile(s.cfg.InstallDir)
}

func (s *Service) VersionInfo() VersionInfo {
	mode := "installed"
	if _, err := os.Stat(filepath.Join(s.cfg.InstallDir, "bors_portable.flag")); err == nil {
		mode = "portable"
	}
	info := VersionInfo{
		Version:    s.CurrentVersion(),
		Mode:       mode,
		DataDir:    s.cfg.DataDir,
		InstallDir: s.cfg.InstallDir,
		Channel:    s.cfg.ManifestURL,
		LastUpdate: readLastUpdate(s.cfg.DataDir),
	}
	if v, ok := backupVersion(s.cfg.DataDir); ok {
		info.RollbackAvailable = true
		info.RollbackVersion = v
	}
	return info
}

func (s *Service) Progress() State {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.state
}

func (s *Service) setState(fn func(*State)) {
	s.mu.Lock()
	defer s.mu.Unlock()
	fn(&s.state)
	s.state.UpdatedAt = s.cfg.Now().UTC().Format(time.RFC3339)
}

// Check fetches the Go update manifest and compares versions.
func (s *Service) Check(ctx context.Context) (CheckResult, error) {
	current := s.CurrentVersion()
	res := CheckResult{CurrentVersion: current, Status: "success"}
	manifest, base, err := s.fetchManifest(ctx)
	if err != nil {
		return CheckResult{Status: "error", CurrentVersion: current,
			Message: "دریافت مانیفست به‌روزرسانی ناموفق: " + err.Error()}, err
	}
	if err := s.validateManifest(manifest); err != nil {
		return CheckResult{Status: "error", CurrentVersion: current, Message: err.Error()}, err
	}
	asset := manifest.Platforms[PlatformKey]
	if err := validateAssetURL(asset.URL, base); err != nil {
		return CheckResult{Status: "error", CurrentVersion: current, Message: err.Error()}, err
	}
	asset.URL = resolvedAssetURL(asset.URL, base)
	manifest.Platforms[PlatformKey] = asset
	if manifest.Portable != nil && manifest.Portable.URL != "" {
		if err := validateAssetURL(manifest.Portable.URL, base); err != nil {
			return CheckResult{Status: "error", CurrentVersion: current, Message: err.Error()}, err
		}
		resolved := *manifest.Portable
		resolved.URL = resolvedAssetURL(resolved.URL, base)
		manifest.Portable = &resolved
	}
	s.mu.Lock()
	s.manifest = manifest
	s.base = base
	s.mu.Unlock()

	res.LatestVersion = manifest.Version
	res.Notes = manifest.Notes
	res.Date = manifest.PubDate
	res.Portable = s.VersionInfo().Mode == "portable"
	if current == "" || strings.EqualFold(current, "dev") {
		res.Message = "نسخهٔ فعلیِ این اجرا ناشناخته است (build توسعه)؛ به‌روزرسانی خودکار غیرفعال است."
		return res, nil
	}
	res.Available = compareVersions(manifest.Version, current) > 0
	if !res.Available {
		return res, nil
	}
	if res.Portable {
		if manifest.Portable != nil && manifest.Portable.URL != "" {
			res.URL = manifest.Portable.URL
			res.Size = manifest.Portable.Size
			res.SHA256 = manifest.Portable.SHA256
		}
		res.Installable = false
		res.Message = "این نسخه Portable است؛ ZIPِ نسخهٔ تازه را دانلود و در پوشه‌ای نو استخراج کنید."
		return res, nil
	}
	res.URL = asset.URL
	res.Signature = asset.Signature
	res.Size = asset.Size
	res.SHA256 = asset.SHA256
	res.Installable = true
	return res, nil
}

func (s *Service) validateManifest(m *Manifest) error {
	if m == nil {
		return errors.New("مانیفست خالی است")
	}
	if m.Channel != "go" {
		return fmt.Errorf("این مانیفست کانالِ Go نیست (channel=%q)؛ نصابِ کانالِ قدیمی نصب نمی‌شود", m.Channel)
	}
	if strings.TrimSpace(m.Version) == "" {
		return errors.New("مانیفست نسخه ندارد")
	}
	asset, ok := m.Platforms[PlatformKey]
	if !ok {
		return fmt.Errorf("مانیفست برای %s دارایی ندارد", PlatformKey)
	}
	if strings.TrimSpace(asset.URL) == "" {
		return errors.New("نشانیِ نصب‌کننده در مانیفست خالی است")
	}
	if strings.TrimSpace(asset.Signature) == "" {
		return errors.New("امضای نصب‌کننده در مانیفست خالی است")
	}
	if asset.Size <= 0 || asset.Size > maxArtifactBytes {
		return fmt.Errorf("اندازهٔ نصب‌کننده در مانیفست نامعتبر است (%d)", asset.Size)
	}
	if asset.SHA256 != "" && !isHexSHA256(asset.SHA256) {
		return errors.New("sha256 مانیفست نامعتبر است")
	}
	return nil
}

func (s *Service) fetchManifest(ctx context.Context) (*Manifest, string, error) {
	raw, base, err := readManifestSource(ctx, s.hc, s.cfg.ManifestURL)
	if err != nil {
		return nil, "", err
	}
	var m Manifest
	if err := json.Unmarshal(raw, &m); err != nil {
		return nil, "", fmt.Errorf("مانیفست JSON نامعتبر است: %w", err)
	}
	return &m, base, nil
}

func readManifestSource(ctx context.Context, hc *http.Client, source string) ([]byte, string, error) {
	if local, ok := localPath(source); ok {
		raw, err := os.ReadFile(local)
		if err != nil {
			return nil, "", err
		}
		if len(raw) > maxManifestBytes {
			return nil, "", errors.New("مانیفست بیش از حد بزرگ است")
		}
		return raw, filepath.Dir(local), nil
	}
	u, err := url.Parse(source)
	if err != nil {
		return nil, "", fmt.Errorf("نشانیِ مانیفست نامعتبر: %w", err)
	}
	if err := validateTransportURL(u); err != nil {
		return nil, "", err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, u.String(), nil)
	if err != nil {
		return nil, "", err
	}
	req.Header.Set("User-Agent", "BorsTerminal-Updater")
	resp, err := hc.Do(req)
	if err != nil {
		return nil, "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return nil, "", fmt.Errorf("مانیفست: HTTP %d", resp.StatusCode)
	}
	raw, err := io.ReadAll(io.LimitReader(resp.Body, maxManifestBytes+1))
	if err != nil {
		return nil, "", err
	}
	if len(raw) > maxManifestBytes {
		return nil, "", errors.New("مانیفست بیش از حد بزرگ است")
	}
	base := *u
	base.Path = strings.TrimSuffix(base.Path, "/"+filepath.Base(base.Path))
	return raw, base.String(), nil
}

// validateAssetURL accepts HTTPS, loopback HTTP (isolated test channels), and
// local paths/file URLs (a lab manifest may live on disk). Everything else is
// refused before any byte is downloaded.
func validateAssetURL(raw, base string) error {
	if strings.TrimSpace(raw) == "" {
		return errors.New("نشانیِ دارایی خالی است")
	}
	if _, ok := localPath(raw); ok {
		return nil
	}
	u, err := url.Parse(raw)
	if err != nil {
		return fmt.Errorf("نشانیِ دارایی نامعتبر: %w", err)
	}
	if !u.IsAbs() {
		if strings.HasPrefix(base, "http://") || strings.HasPrefix(base, "https://") {
			b, err := url.Parse(base)
			if err != nil {
				return err
			}
			u = b.ResolveReference(u)
		} else {
			// local manifest: resolve against its directory
			p := filepath.Join(base, filepath.FromSlash(u.Path))
			if _, err := os.Stat(p); err != nil {
				return fmt.Errorf("داراییِ محلی پیدا نشد: %w", err)
			}
			return nil
		}
	}
	return validateTransportURL(u)
}

// resolvedAssetURL turns a manifest-relative asset reference into an absolute
// URL or local path, so Download never depends on the process working dir.
func resolvedAssetURL(raw, base string) string {
	if local, ok := localPath(raw); ok {
		if filepath.IsAbs(local) {
			return local
		}
		return filepath.Join(base, filepath.FromSlash(local))
	}
	u, err := url.Parse(raw)
	if err != nil || u.IsAbs() {
		return raw
	}
	if b, err := url.Parse(base); err == nil && (b.Scheme == "http" || b.Scheme == "https") {
		return b.ResolveReference(u).String()
	}
	return filepath.Join(base, filepath.FromSlash(u.Path))
}

func validateTransportURL(u *url.URL) error {
	switch strings.ToLower(u.Scheme) {
	case "https":
		return nil
	case "http":
		host := strings.ToLower(u.Hostname())
		if host == "127.0.0.1" || host == "localhost" || host == "::1" {
			return nil
		}
		return fmt.Errorf("HTTPِ غیرِ‌لوکال مجاز نیست (%s)؛ فقط HTTPS", u.Host)
	case "file":
		return nil
	default:
		return fmt.Errorf("schemeِ %q مجاز نیست", u.Scheme)
	}
}

func localPath(source string) (string, bool) {
	if strings.HasPrefix(strings.ToLower(source), "file://") {
		u, err := url.Parse(source)
		if err != nil {
			return "", false
		}
		return filepath.FromSlash(u.Path), true
	}
	// Windows drive paths look like a URL scheme ("C:") to net/url; they are
	// local manifests or local artifacts for lab channels.
	if len(source) >= 2 && source[1] == ':' && (source[0] >= 'A' && source[0] <= 'Z' || source[0] >= 'a' && source[0] <= 'z') {
		return source, true
	}
	if filepath.IsAbs(source) {
		return source, true
	}
	u, err := url.Parse(source)
	if err != nil || u.Scheme != "" {
		return "", false
	}
	return source, true
}

func compareVersions(a, b string) int {
	pa := versionParts(a)
	pb := versionParts(b)
	for i := 0; i < 3; i++ {
		if pa[i] < pb[i] {
			return -1
		}
		if pa[i] > pb[i] {
			return 1
		}
	}
	return 0
}

var versionDigits = regexp.MustCompile(`\d+`)

func versionParts(v string) [3]int {
	var out [3]int
	parts := versionDigits.FindAllString(v, 3)
	for i, p := range parts {
		n, _ := strconv.Atoi(p)
		out[i] = n
	}
	return out
}

func versionFromFile(installDir string) string {
	raw, err := os.ReadFile(filepath.Join(installDir, "Version.txt"))
	if err != nil {
		return ""
	}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(strings.ToLower(line), "app_version=") {
			return strings.TrimSpace(line[len("app_version="):])
		}
	}
	return ""
}

func isHexSHA256(s string) bool {
	if len(s) != 64 {
		return false
	}
	for _, r := range strings.ToLower(s) {
		if !(r >= '0' && r <= '9' || r >= 'a' && r <= 'f') {
			return false
		}
	}
	return true
}

func readLastUpdate(dataDir string) *LastUpdate {
	raw, err := os.ReadFile(filepath.Join(dataDir, "update_last.json"))
	if err != nil {
		return nil
	}
	var last LastUpdate
	if err := json.Unmarshal(raw, &last); err != nil || last.Status == "" {
		return nil
	}
	return &last
}

func backupVersion(dataDir string) (string, bool) {
	raw, err := os.ReadFile(filepath.Join(dataDir, "backups", backupDirName, "backup.json"))
	if err != nil {
		return "", false
	}
	var b struct {
		Version string `json:"version"`
	}
	if err := json.Unmarshal(raw, &b); err != nil || b.Version == "" {
		return "", false
	}
	return b.Version, true
}
