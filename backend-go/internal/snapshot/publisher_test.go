package snapshot

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

type mockGitHubServer struct {
	mu             sync.Mutex
	server         *httptest.Server
	releases       map[string]*githubRelease
	uploadOrder    []string
	authHeaders    []string
	verifyRequests []string
	deletedAssets  []int64
	failUpload     bool
	failVerify     bool
	requireAuth    bool
	expectedToken  string
	nextAssetID    int64
}

func newMockGitHubServer(t *testing.T, expectedToken string) *mockGitHubServer {
	t.Helper()

	mock := &mockGitHubServer{
		releases:      make(map[string]*githubRelease),
		expectedToken: expectedToken,
		requireAuth:   true,
		nextAssetID:   100,
	}

	mux := http.NewServeMux()

	// Handler for /repos/{owner}/{repo}/releases/tags/{tag}
	mux.HandleFunc("/repos/", func(w http.ResponseWriter, r *http.Request) {
		mock.mu.Lock()
		defer mock.mu.Unlock()

		auth := r.Header.Get("Authorization")
		mock.authHeaders = append(mock.authHeaders, auth)
		if mock.requireAuth && mock.expectedToken != "" {
			expectedAuth := "Bearer " + mock.expectedToken
			if auth != expectedAuth {
				http.Error(w, `{"message":"Bad credentials"}`, http.StatusUnauthorized)
				return
			}
		}

		path := r.URL.Path

		// DELETE asset: /repos/{owner}/{repo}/releases/assets/{id}
		if r.Method == http.MethodDelete && strings.Contains(path, "/releases/assets/") {
			var assetID int64
			fmt.Sscanf(path[strings.LastIndex(path, "/")+1:], "%d", &assetID)
			mock.deletedAssets = append(mock.deletedAssets, assetID)
			w.WriteHeader(http.StatusNoContent)
			return
		}

		// GET release by tag: /repos/{owner}/{repo}/releases/tags/{tag}
		if r.Method == http.MethodGet && strings.Contains(path, "/releases/tags/") {
			tag := path[strings.LastIndex(path, "/")+1:]
			rel, ok := mock.releases[tag]
			if !ok {
				http.Error(w, `{"message":"Not Found"}`, http.StatusNotFound)
				return
			}
			w.Header().Set("Content-Type", "application/vnd.github+json")
			_ = json.NewEncoder(w).Encode(rel)
			return
		}

		// POST create release: /repos/{owner}/{repo}/releases
		if r.Method == http.MethodPost && strings.HasSuffix(path, "/releases") {
			var body struct {
				TagName string `json:"tag_name"`
			}
			_ = json.NewDecoder(r.Body).Decode(&body)
			rel := &githubRelease{
				ID:        501,
				TagName:   body.TagName,
				UploadURL: mock.server.URL + fmt.Sprintf("/repos/owner/repo/releases/501/assets{?name,label}"),
				Assets:    []githubAsset{},
			}
			mock.releases[body.TagName] = rel
			w.WriteHeader(http.StatusCreated)
			w.Header().Set("Content-Type", "application/vnd.github+json")
			_ = json.NewEncoder(w).Encode(rel)
			return
		}

		// POST upload asset: /repos/{owner}/{repo}/releases/{id}/assets?name={name}
		if r.Method == http.MethodPost && strings.Contains(path, "/assets") {
			name := r.URL.Query().Get("name")
			mock.uploadOrder = append(mock.uploadOrder, name)

			if mock.failUpload {
				http.Error(w, `{"message":"Simulated upload failure"}`, http.StatusInternalServerError)
				return
			}

			// Read uploaded body
			_, _ = io.ReadAll(r.Body)

			mock.nextAssetID++
			asset := githubAsset{
				ID:                 mock.nextAssetID,
				Name:               name,
				BrowserDownloadURL: mock.server.URL + "/download/" + name,
				State:              "uploaded",
			}

			// Find matching release and append
			for _, rel := range mock.releases {
				rel.Assets = append(rel.Assets, asset)
			}

			w.WriteHeader(http.StatusCreated)
			w.Header().Set("Content-Type", "application/vnd.github+json")
			_ = json.NewEncoder(w).Encode(asset)
			return
		}

		http.Error(w, `{"message":"Unknown endpoint"}`, http.StatusNotFound)
	})

	// Handler for /download/{name} (verification check)
	mux.HandleFunc("/download/", func(w http.ResponseWriter, r *http.Request) {
		mock.mu.Lock()
		defer mock.mu.Unlock()

		auth := r.Header.Get("Authorization")
		mock.authHeaders = append(mock.authHeaders, auth)
		if mock.requireAuth && mock.expectedToken != "" {
			expectedAuth := "Bearer " + mock.expectedToken
			if auth != expectedAuth {
				http.Error(w, `{"message":"Bad credentials"}`, http.StatusUnauthorized)
				return
			}
		}

		name := r.URL.Path[strings.LastIndex(r.URL.Path, "/")+1:]
		mock.verifyRequests = append(mock.verifyRequests, name)

		if mock.failVerify {
			http.Error(w, `{"message":"Simulated verification check failure"}`, http.StatusInternalServerError)
			return
		}

		w.WriteHeader(http.StatusOK)
		_, _ = w.Write([]byte("ok"))
	})

	mock.server = httptest.NewServer(mux)
	t.Cleanup(func() {
		mock.server.Close()
	})

	return mock
}

func setupTestSnapshotFiles(t *testing.T) (manifestDir string, manifest *Manifest, pubStr, privStr string) {
	t.Helper()

	tempDir := t.TempDir()

	pubStr, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair: %v", err)
	}

	manifest = NewManifest("set-test-20261108", 1)

	// Create 2 mock database compressed assets
	for _, name := range []string{"codal", "market"} {
		fileName := name + ".db.lzma"
		filePath := filepath.Join(tempDir, fileName)
		data := []byte(fmt.Sprintf("compressed SQLite database payload for %s", name))
		if err := os.WriteFile(filePath, data, 0644); err != nil {
			t.Fatalf("write asset file %s: %v", filePath, err)
		}

		hash := sha256.Sum256(data)
		shaHex := hex.EncodeToString(hash[:])
		manifest.AddAsset(name, fileName, shaHex, int64(len(data)), int64(len(data)*2))
	}

	manifestPath := filepath.Join(tempDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		t.Fatalf("save manifest: %v", err)
	}

	return tempDir, manifest, pubStr, privStr
}

func TestPublisher_PublishSnapshotSet_Success(t *testing.T) {
	token := "ghp_validToken123456789"
	mock := newMockGitHubServer(t, token)

	// Pre-create existing release for tag
	tag := "v1.5.0-data"
	mock.releases[tag] = &githubRelease{
		ID:        201,
		TagName:   tag,
		UploadURL: mock.server.URL + "/repos/testowner/testrepo/releases/201/assets{?name,label}",
		Assets:    []githubAsset{},
	}

	manifestDir, manifest, pubStr, privStr := setupTestSnapshotFiles(t)

	pub, err := NewPublisher(PublisherConfig{
		Owner:   "testowner",
		Repo:    "testrepo",
		Tag:     tag,
		Token:   token,
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher failed: %v", err)
	}

	ctx := context.Background()
	if err := pub.PublishSnapshotSet(ctx, manifestDir, manifest, privStr, ""); err != nil {
		t.Fatalf("PublishSnapshotSet failed: %v", err)
	}

	mock.mu.Lock()
	defer mock.mu.Unlock()

	// Verify upload count and exact ordering
	// Expected assets: codal.db.lzma, codal.db.lzma.sig, market.db.lzma, market.db.lzma.sig
	// Followed strictly by: manifest.json, manifest.json.sig LAST!
	expectedUploadCount := 6
	if len(mock.uploadOrder) != expectedUploadCount {
		t.Fatalf("expected %d uploaded files, got %d: %v", expectedUploadCount, len(mock.uploadOrder), mock.uploadOrder)
	}

	// Verify that the last 2 uploads are strictly manifest.json and manifest.json.sig
	last1 := mock.uploadOrder[expectedUploadCount-2]
	last2 := mock.uploadOrder[expectedUploadCount-1]
	if last1 != "manifest.json" || last2 != "manifest.json.sig" {
		t.Fatalf("manifest files were NOT uploaded last! Got last1=%s, last2=%s (full order: %v)", last1, last2, mock.uploadOrder)
	}

	// Verify data assets were uploaded before manifest
	dataUploads := mock.uploadOrder[:expectedUploadCount-2]
	for _, name := range []string{"codal.db.lzma", "codal.db.lzma.sig", "market.db.lzma", "market.db.lzma.sig"} {
		found := false
		for _, u := range dataUploads {
			if u == name {
				found = true
				break
			}
		}
		if !found {
			t.Fatalf("expected data upload %s in data uploads %v", name, dataUploads)
		}
	}

	// Verify verification checks were executed for each data asset and their .sig
	if len(mock.verifyRequests) != 4 {
		t.Fatalf("expected 4 verify requests for data assets, got %d: %v", len(mock.verifyRequests), mock.verifyRequests)
	}

	// Verify generated signatures on disk are cryptographically valid
	manifestPath := filepath.Join(manifestDir, "manifest.json")
	if err := VerifyAsset(manifestPath, manifestPath+".sig", pubStr); err != nil {
		t.Fatalf("VerifyAsset failed on generated manifest signature: %v", err)
	}

	for _, meta := range manifest.Assets {
		assetPath := filepath.Join(manifestDir, meta.Path)
		if err := VerifyAsset(assetPath, assetPath+".sig", pubStr); err != nil {
			t.Fatalf("VerifyAsset failed on asset signature %s: %v", meta.Path, err)
		}
	}
}

func TestPublisher_MissingToken(t *testing.T) {
	// Temporarily clear GITHUB_TOKEN
	orig := os.Getenv("GITHUB_TOKEN")
	_ = os.Unsetenv("GITHUB_TOKEN")
	defer func() {
		if orig != "" {
			_ = os.Setenv("GITHUB_TOKEN", orig)
		}
	}()

	_, err := NewPublisher(PublisherConfig{
		Owner: "owner",
		Repo:  "repo",
		Tag:   "v1.0.0",
		Token: "",
	})
	if err == nil {
		t.Fatal("expected error when token is missing, got nil")
	}
	if !strings.Contains(err.Error(), "github token is required") {
		t.Fatalf("unexpected error message: %v", err)
	}
}

func TestPublisher_TokenFromEnv(t *testing.T) {
	orig := os.Getenv("GITHUB_TOKEN")
	_ = os.Setenv("GITHUB_TOKEN", "env-token-xyz")
	defer func() {
		if orig != "" {
			_ = os.Setenv("GITHUB_TOKEN", orig)
		} else {
			_ = os.Unsetenv("GITHUB_TOKEN")
		}
	}()

	pub, err := NewPublisher(PublisherConfig{
		Owner: "owner",
		Repo:  "repo",
		Tag:   "v1.0.0",
	})
	if err != nil {
		t.Fatalf("expected NewPublisher to read GITHUB_TOKEN from env: %v", err)
	}
	if pub.cfg.Token != "env-token-xyz" {
		t.Fatalf("expected token 'env-token-xyz', got %q", pub.cfg.Token)
	}
}

func TestPublisher_AuthorizationHeader(t *testing.T) {
	expectedToken := "ghp_correct_token"
	mock := newMockGitHubServer(t, expectedToken)

	tag := "v1.0.0"
	mock.releases[tag] = &githubRelease{
		ID:        1,
		TagName:   tag,
		UploadURL: mock.server.URL + "/repos/owner/repo/releases/1/assets{?name,label}",
	}

	manifestDir, manifest, _, privStr := setupTestSnapshotFiles(t)

	// Publisher with wrong token should fail authentication
	pub, err := NewPublisher(PublisherConfig{
		Owner:   "owner",
		Repo:    "repo",
		Tag:     tag,
		Token:   "ghp_wrong_token",
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}

	err = pub.PublishSnapshotSet(context.Background(), manifestDir, manifest, privStr, "")
	if err == nil {
		t.Fatal("expected 401 unauthorized failure, got nil")
	}
}

func TestPublisher_UploadFailure(t *testing.T) {
	token := "ghp_token_upload_fail"
	mock := newMockGitHubServer(t, token)
	mock.failUpload = true

	tag := "v1.0.0"
	mock.releases[tag] = &githubRelease{
		ID:        1,
		TagName:   tag,
		UploadURL: mock.server.URL + "/repos/owner/repo/releases/1/assets{?name,label}",
	}

	manifestDir, manifest, _, privStr := setupTestSnapshotFiles(t)

	pub, err := NewPublisher(PublisherConfig{
		Owner:   "owner",
		Repo:    "repo",
		Tag:     tag,
		Token:   token,
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}

	err = pub.PublishSnapshotSet(context.Background(), manifestDir, manifest, privStr, "")
	if err == nil {
		t.Fatal("expected error on simulated upload failure, got nil")
	}

	// manifest.json must NOT have been uploaded
	for _, uploaded := range mock.uploadOrder {
		if uploaded == "manifest.json" || uploaded == "manifest.json.sig" {
			t.Fatalf("manifest was uploaded despite data asset failure!")
		}
	}
}

func TestPublisher_VerificationFailure(t *testing.T) {
	token := "ghp_token_verify_fail"
	mock := newMockGitHubServer(t, token)
	mock.failVerify = true // Verification check returns HTTP 500

	tag := "v1.0.0"
	mock.releases[tag] = &githubRelease{
		ID:        1,
		TagName:   tag,
		UploadURL: mock.server.URL + "/repos/owner/repo/releases/1/assets{?name,label}",
	}

	manifestDir, manifest, _, privStr := setupTestSnapshotFiles(t)

	pub, err := NewPublisher(PublisherConfig{
		Owner:   "owner",
		Repo:    "repo",
		Tag:     tag,
		Token:   token,
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}

	err = pub.PublishSnapshotSet(context.Background(), manifestDir, manifest, privStr, "")
	if err == nil {
		t.Fatal("expected error on verification failure, got nil")
	}

	// manifest.json and manifest.json.sig must NEVER be uploaded if verification fails
	for _, uploaded := range mock.uploadOrder {
		if uploaded == "manifest.json" || uploaded == "manifest.json.sig" {
			t.Fatalf("manifest was uploaded despite asset verification check failure!")
		}
	}
}

func TestPublisher_CreateReleaseIfTagNotFound(t *testing.T) {
	token := "ghp_token_create_rel"
	mock := newMockGitHubServer(t, token)
	// mock.releases is empty initially -> GET /releases/tags/tag will return 404

	tag := "v2.0.0-new"
	manifestDir, manifest, _, privStr := setupTestSnapshotFiles(t)

	pub, err := NewPublisher(PublisherConfig{
		Owner:   "owner",
		Repo:    "repo",
		Tag:     tag,
		Token:   token,
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}

	if err := pub.PublishSnapshotSet(context.Background(), manifestDir, manifest, privStr, ""); err != nil {
		t.Fatalf("PublishSnapshotSet failed on missing tag: %v", err)
	}

	// Check that release was created on mock server
	mock.mu.Lock()
	defer mock.mu.Unlock()
	if _, ok := mock.releases[tag]; !ok {
		t.Fatalf("release for tag %s was not created on mock server", tag)
	}
}

func TestPublisher_DeleteConflictingAsset(t *testing.T) {
	token := "ghp_token_conflict"
	mock := newMockGitHubServer(t, token)

	tag := "v1.0.0"
	mock.releases[tag] = &githubRelease{
		ID:        1,
		TagName:   tag,
		UploadURL: mock.server.URL + "/repos/owner/repo/releases/1/assets{?name,label}",
		Assets: []githubAsset{
			{ID: 999, Name: "market.db.lzma"},
		},
	}

	manifestDir, manifest, _, privStr := setupTestSnapshotFiles(t)

	pub, err := NewPublisher(PublisherConfig{
		Owner:   "owner",
		Repo:    "repo",
		Tag:     tag,
		Token:   token,
		BaseURL: mock.server.URL,
	})
	if err != nil {
		t.Fatalf("NewPublisher: %v", err)
	}

	if err := pub.PublishSnapshotSet(context.Background(), manifestDir, manifest, privStr, ""); err != nil {
		t.Fatalf("PublishSnapshotSet failed with conflicting asset: %v", err)
	}

	mock.mu.Lock()
	defer mock.mu.Unlock()

	foundDeleted := false
	for _, id := range mock.deletedAssets {
		if id == 999 {
			foundDeleted = true
			break
		}
	}
	if !foundDeleted {
		t.Fatalf("conflicting asset ID 999 was not deleted before upload: %v", mock.deletedAssets)
	}
}
