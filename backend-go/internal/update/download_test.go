package update

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"aead.dev/minisign"
)

// signedAsset builds a loopback artifact server plus a manifest asset whose
// signature is base64-wrapped minisign text, the same shape latest.json uses.
func signedAsset(t *testing.T, payload, signedPayload []byte, declaredSize int64) (*httptest.Server, Asset, func()) {
	t.Helper()
	pub, priv, err := minisign.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	prev := pubKey
	pubText, err := pub.MarshalText()
	if err != nil {
		t.Fatal(err)
	}
	pubKey = string(pubText)
	restoreKey := func() { pubKey = prev }

	sig := minisign.Sign(priv, signedPayload)
	asset := Asset{
		Signature: base64.StdEncoding.EncodeToString(sig),
		Size:      declaredSize,
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/installer.exe":
			_, _ = w.Write(payload)
		case "/latest-go.json":
			_ = json.NewEncoder(w).Encode(Manifest{
				Channel: "go", Version: "1.0.96",
				Platforms: map[string]Asset{PlatformKey: asset},
			})
		default:
			http.NotFound(w, r)
		}
	}))
	asset.URL = srv.URL + "/installer.exe"
	return srv, asset, func() { srv.Close(); restoreKey() }
}

func waitStatus(t *testing.T, svc *Service, want Status) State {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		st := svc.Progress()
		if st.Status == want {
			return st
		}
		if st.Status == StatusError {
			t.Fatalf("state reached error while waiting for %s: %+v", want, st)
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("timeout waiting for status %s; state=%+v", want, svc.Progress())
	return State{}
}

func waitError(t *testing.T, svc *Service) State {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		st := svc.Progress()
		if st.Status == StatusError {
			return st
		}
		if st.Status == StatusReady {
			t.Fatalf("state reached ready; expected error: %+v", st)
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatalf("timeout waiting for error; state=%+v", svc.Progress())
	return State{}
}

func TestDownloadVerifiesSignedArtifact(t *testing.T) {
	payload := []byte("installer-bytes-1.0.96")
	srv, _, cleanup := signedAsset(t, payload, payload, int64(len(payload)))
	defer cleanup()

	data := t.TempDir()
	svc := New(Config{DataDir: data, InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	if _, err := svc.Check(context.Background()); err != nil {
		t.Fatalf("Check: %v", err)
	}
	if err := svc.Download(context.Background()); err != nil {
		t.Fatalf("Download: %v", err)
	}
	st := waitStatus(t, svc, StatusReady)
	raw, err := os.ReadFile(st.Path)
	if err != nil {
		t.Fatalf("artifact missing: %v", err)
	}
	if string(raw) != string(payload) {
		t.Fatalf("artifact bytes = %q", raw)
	}
	if st.Version != "1.0.96" || st.SHA256 == "" {
		t.Fatalf("state = %+v", st)
	}
	if _, err := os.Stat(st.Path + ".sig"); err != nil {
		t.Fatalf("signature sidecar missing: %v", err)
	}
}

func TestDownloadRejectsBadSignature(t *testing.T) {
	payload := []byte("installer-bytes")
	srv, _, cleanup := signedAsset(t, payload, []byte("signed-content-differs"), int64(len(payload)))
	defer cleanup()
	// The manifest served by signedAsset points at the artifact URL; repair the
	// asset so only the signature is wrong.
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	if _, err := svc.Check(context.Background()); err != nil {
		t.Fatalf("Check: %v", err)
	}
	if err := svc.Download(context.Background()); err != nil {
		t.Fatalf("Download start: %v", err)
	}
	st := waitError(t, svc)
	if st.Status != StatusError {
		t.Fatalf("state = %+v", st)
	}
	if st.Path != "" {
		if _, err := os.Stat(st.Path); err == nil {
			t.Fatalf("unverified artifact left on disk: %s", st.Path)
		}
	}
}

func TestDownloadRejectsSizeMismatch(t *testing.T) {
	payload := []byte("installer-bytes-with-wrong-declared-size")
	srv, _, cleanup := signedAsset(t, payload, payload, int64(len(payload)-3))
	defer cleanup()
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	if _, err := svc.Check(context.Background()); err != nil {
		t.Fatalf("Check: %v", err)
	}
	if err := svc.Download(context.Background()); err != nil {
		t.Fatalf("Download start: %v", err)
	}
	waitError(t, svc)
}

func TestDownloadNetworkLossLeavesNoReadyState(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/latest-go.json" {
			_ = json.NewEncoder(w).Encode(Manifest{
				Channel: "go", Version: "1.0.96",
				Platforms: map[string]Asset{PlatformKey: {
					URL: "http://" + r.Host + "/installer.exe", Signature: "c2ln", Size: 100,
				}},
			})
			return
		}
		hj, ok := w.(http.Hijacker)
		if !ok {
			t.Errorf("hijack unsupported")
			return
		}
		conn, _, err := hj.Hijack()
		if err == nil {
			_ = conn.Close()
		}
	}))
	defer srv.Close()
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: srv.URL + "/latest-go.json"})
	if _, err := svc.Check(context.Background()); err != nil {
		t.Fatalf("Check: %v", err)
	}
	if err := svc.Download(context.Background()); err != nil {
		t.Fatalf("Download start: %v", err)
	}
	waitError(t, svc)
}

func TestDecodeSignatureForms(t *testing.T) {
	raw := []byte("untrusted comment: x\nRUAAAA\n")
	if got, err := decodeSignature(string(raw)); err != nil || string(got) != string(raw) {
		t.Fatalf("raw signature: %q %v", got, err)
	}
	wrapped := base64.StdEncoding.EncodeToString(raw)
	if got, err := decodeSignature(wrapped); err != nil || string(got) != string(raw) {
		t.Fatalf("base64 signature: %q %v", got, err)
	}
	if _, err := decodeSignature("not a signature"); err == nil {
		t.Fatal("garbage signature accepted")
	}
}

func TestLocalManifestResolvesRelativeAsset(t *testing.T) {
	dir := t.TempDir()
	payload := []byte("local-installer-bytes")
	if err := os.WriteFile(filepath.Join(dir, "Setup.exe"), payload, 0o644); err != nil {
		t.Fatal(err)
	}
	pub, priv, err := minisign.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	prev := pubKey
	pubText, _ := pub.MarshalText()
	pubKey = string(pubText)
	defer func() { pubKey = prev }()
	sig := minisign.Sign(priv, payload)
	manifest := Manifest{Channel: "go", Version: "1.0.96", Platforms: map[string]Asset{
		PlatformKey: {URL: "Setup.exe", Signature: base64.StdEncoding.EncodeToString(sig), Size: int64(len(payload))},
	}}
	raw, _ := json.Marshal(manifest)
	manifestPath := filepath.Join(dir, "latest-go.json")
	if err := os.WriteFile(manifestPath, raw, 0o644); err != nil {
		t.Fatal(err)
	}
	svc := New(Config{DataDir: t.TempDir(), InstallDir: t.TempDir(), CurrentVersion: "1.0.95", ManifestURL: manifestPath})
	res, err := svc.Check(context.Background())
	if err != nil {
		t.Fatalf("Check: %v", err)
	}
	if !filepath.IsAbs(res.URL) {
		t.Fatalf("relative asset not resolved: %q", res.URL)
	}
	if err := svc.Download(context.Background()); err != nil {
		t.Fatalf("Download: %v", err)
	}
	st := waitStatus(t, svc, StatusReady)
	got, _ := os.ReadFile(st.Path)
	if string(got) != string(payload) {
		t.Fatalf("artifact bytes = %q", got)
	}
}
