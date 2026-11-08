package snapshot

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"
)

// PublisherConfig configures the GitHub Release snapshot publisher.
type PublisherConfig struct {
	Owner   string
	Repo    string
	Tag     string
	Token   string
	Client  *http.Client
	BaseURL string
}

// Publisher publishes snapshot sets, manifests, and Minisign signatures to GitHub Releases.
type Publisher struct {
	cfg PublisherConfig
}

type githubRelease struct {
	ID        int64         `json:"id"`
	TagName   string        `json:"tag_name"`
	UploadURL string        `json:"upload_url"`
	Assets    []githubAsset `json:"assets"`
}

type githubAsset struct {
	ID                 int64  `json:"id"`
	Name               string `json:"name"`
	URL                string `json:"url"`
	BrowserDownloadURL string `json:"browser_download_url"`
	State              string `json:"state"`
}

// NewPublisher initializes a new Publisher validating required parameters and reading GITHUB_TOKEN if not explicitly passed.
func NewPublisher(cfg PublisherConfig) (*Publisher, error) {
	if cfg.Token == "" {
		cfg.Token = os.Getenv("GITHUB_TOKEN")
	}
	cfg.Token = strings.TrimSpace(cfg.Token)
	if cfg.Token == "" {
		return nil, errors.New("github token is required (set via PublisherConfig.Token or GITHUB_TOKEN environment variable)")
	}

	cfg.Owner = strings.TrimSpace(cfg.Owner)
	if cfg.Owner == "" {
		return nil, errors.New("owner is required")
	}

	cfg.Repo = strings.TrimSpace(cfg.Repo)
	if cfg.Repo == "" {
		return nil, errors.New("repo is required")
	}

	cfg.Tag = strings.TrimSpace(cfg.Tag)
	if cfg.Tag == "" {
		return nil, errors.New("tag is required")
	}

	if cfg.Client == nil {
		cfg.Client = &http.Client{Timeout: 600 * time.Second}
	}

	if strings.TrimSpace(cfg.BaseURL) == "" {
		if envBase := os.Getenv("GITHUB_API_BASE_URL"); strings.TrimSpace(envBase) != "" {
			cfg.BaseURL = envBase
		} else {
			cfg.BaseURL = "https://api.github.com"
		}
	}
	cfg.BaseURL = strings.TrimRight(strings.TrimSpace(cfg.BaseURL), "/")

	return &Publisher{cfg: cfg}, nil
}

func (p *Publisher) setHeaders(req *http.Request, accept string) {
	req.Header.Set("Authorization", "Bearer "+p.cfg.Token)
	if accept != "" {
		req.Header.Set("Accept", accept)
	}
	req.Header.Set("X-GitHub-Api-Version", "2022-11-28")
}

func (p *Publisher) getOrCreateRelease(ctx context.Context) (*githubRelease, error) {
	tagURL := fmt.Sprintf("%s/repos/%s/%s/releases/tags/%s", p.cfg.BaseURL, p.cfg.Owner, p.cfg.Repo, url.PathEscape(p.cfg.Tag))
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, tagURL, nil)
	if err != nil {
		return nil, fmt.Errorf("create get release request: %w", err)
	}
	p.setHeaders(req, "application/vnd.github+json")

	resp, err := p.cfg.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("get release for tag %s: %w", p.cfg.Tag, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusOK {
		var rel githubRelease
		if err := json.NewDecoder(resp.Body).Decode(&rel); err != nil {
			return nil, fmt.Errorf("decode existing release: %w", err)
		}
		return &rel, nil
	}

	if resp.StatusCode != http.StatusNotFound {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status %d getting release for tag %s: %s", resp.StatusCode, p.cfg.Tag, string(body))
	}

	// Release not found (404), create it
	createURL := fmt.Sprintf("%s/repos/%s/%s/releases", p.cfg.BaseURL, p.cfg.Owner, p.cfg.Repo)
	createPayload := map[string]interface{}{
		"tag_name":    p.cfg.Tag,
		"name":        "Snapshot " + p.cfg.Tag,
		"body":        fmt.Sprintf("Automated database snapshot release for %s", p.cfg.Tag),
		"draft":       false,
		"prerelease":  false,
		"make_latest": "true",
	}
	payloadBytes, err := json.Marshal(createPayload)
	if err != nil {
		return nil, fmt.Errorf("marshal create release payload: %w", err)
	}

	createReq, err := http.NewRequestWithContext(ctx, http.MethodPost, createURL, bytes.NewReader(payloadBytes))
	if err != nil {
		return nil, fmt.Errorf("create post release request: %w", err)
	}
	p.setHeaders(createReq, "application/vnd.github+json")
	createReq.Header.Set("Content-Type", "application/json")

	createResp, err := p.cfg.Client.Do(createReq)
	if err != nil {
		return nil, fmt.Errorf("post create release: %w", err)
	}
	defer createResp.Body.Close()

	if createResp.StatusCode != http.StatusOK && createResp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(createResp.Body)
		return nil, fmt.Errorf("create release failed with status %d: %s", createResp.StatusCode, string(body))
	}

	var newRel githubRelease
	if err := json.NewDecoder(createResp.Body).Decode(&newRel); err != nil {
		return nil, fmt.Errorf("decode created release: %w", err)
	}
	return &newRel, nil
}

func (p *Publisher) deleteExistingAsset(ctx context.Context, assetID int64) error {
	delURL := fmt.Sprintf("%s/repos/%s/%s/releases/assets/%d", p.cfg.BaseURL, p.cfg.Owner, p.cfg.Repo, assetID)
	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, delURL, nil)
	if err != nil {
		return err
	}
	p.setHeaders(req, "application/vnd.github+json")

	resp, err := p.cfg.Client.Do(req)
	if err != nil {
		return fmt.Errorf("delete asset %d: %w", assetID, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusNoContent && resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusNotFound {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("delete asset %d returned status %d: %s", assetID, resp.StatusCode, string(body))
	}
	return nil
}

func (p *Publisher) uploadAsset(ctx context.Context, release *githubRelease, localFilePath string) (*githubAsset, error) {
	fileName := filepath.Base(localFilePath)
	file, err := os.Open(localFilePath)
	if err != nil {
		return nil, fmt.Errorf("open asset file %s: %w", localFilePath, err)
	}
	defer file.Close()

	fi, err := file.Stat()
	if err != nil {
		return nil, fmt.Errorf("stat asset file %s: %w", localFilePath, err)
	}

	// Delete existing asset if present in release
	for _, existing := range release.Assets {
		if existing.Name == fileName {
			_ = p.deleteExistingAsset(ctx, existing.ID)
			break
		}
	}

	uploadBase := release.UploadURL
	if idx := strings.Index(uploadBase, "{"); idx != -1 {
		uploadBase = uploadBase[:idx]
	}
	if uploadBase == "" {
		uploadBase = fmt.Sprintf("%s/repos/%s/%s/releases/%d/assets", p.cfg.BaseURL, p.cfg.Owner, p.cfg.Repo, release.ID)
	} else if strings.HasPrefix(uploadBase, "/") {
		uploadBase = p.cfg.BaseURL + uploadBase
	} else if !strings.HasPrefix(uploadBase, "http://") && !strings.HasPrefix(uploadBase, "https://") {
		uploadBase = p.cfg.BaseURL + "/" + strings.TrimLeft(uploadBase, "/")
	}

	uploadURL := fmt.Sprintf("%s?name=%s", uploadBase, url.QueryEscape(fileName))
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, uploadURL, file)
	if err != nil {
		return nil, fmt.Errorf("create upload request for %s: %w", fileName, err)
	}

	p.setHeaders(req, "application/vnd.github+json")
	req.Header.Set("Content-Type", "application/octet-stream")
	req.ContentLength = fi.Size()

	resp, err := p.cfg.Client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("upload asset %s: %w", fileName, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("upload asset %s failed (status %d): %s", fileName, resp.StatusCode, string(body))
	}

	var asset githubAsset
	if err := json.NewDecoder(resp.Body).Decode(&asset); err != nil {
		return nil, fmt.Errorf("decode asset response for %s: %w", fileName, err)
	}
	return &asset, nil
}

func (p *Publisher) verifyAssetAvailability(ctx context.Context, asset *githubAsset) error {
	verifyURL := asset.BrowserDownloadURL
	if verifyURL == "" {
		verifyURL = fmt.Sprintf("%s/repos/%s/%s/releases/assets/%d", p.cfg.BaseURL, p.cfg.Owner, p.cfg.Repo, asset.ID)
	} else if strings.HasPrefix(verifyURL, "/") {
		verifyURL = p.cfg.BaseURL + verifyURL
	} else if !strings.HasPrefix(verifyURL, "http://") && !strings.HasPrefix(verifyURL, "https://") {
		verifyURL = p.cfg.BaseURL + "/" + strings.TrimLeft(verifyURL, "/")
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodGet, verifyURL, nil)
	if err != nil {
		return fmt.Errorf("create verify request for %s: %w", asset.Name, err)
	}
	p.setHeaders(req, "application/octet-stream")

	resp, err := p.cfg.Client.Do(req)
	if err != nil {
		return fmt.Errorf("verify asset %s availability: %w", asset.Name, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("verify asset %s returned HTTP %d, expected 200 OK", asset.Name, resp.StatusCode)
	}
	return nil
}

// PublishSnapshotSet publishes all assets described in manifest following strict consistency ordering:
//  1. Sign all assets in manifest.Assets: produces <asset>.sig.
//  2. Sign manifest.json: produces manifest.json.sig.
//  3. Locate or create release for Tag on GitHub.
//  4. Upload all compressed data assets and their .sig files to the release.
//  5. Verification check: Verify each uploaded data asset returns HTTP 200 OK.
//  6. Upload manifest.json and manifest.json.sig LAST to guarantee consistency.
func (p *Publisher) PublishSnapshotSet(ctx context.Context, manifestDir string, manifest *Manifest, privKeyStr, password string) error {
	if manifest == nil {
		return errors.New("manifest is nil")
	}
	if err := manifest.Validate(); err != nil {
		return fmt.Errorf("invalid manifest: %w", err)
	}
	if strings.TrimSpace(manifestDir) == "" {
		return errors.New("manifestDir is required")
	}

	// 1. Sign all assets in manifest.Assets
	assetNames := make([]string, 0, len(manifest.Assets))
	for name := range manifest.Assets {
		assetNames = append(assetNames, name)
	}
	sort.Strings(assetNames)

	type assetFilePair struct {
		dataFilePath string
		sigFilePath  string
	}
	dataPairs := make([]assetFilePair, 0, len(assetNames))

	for _, name := range assetNames {
		meta := manifest.Assets[name]
		assetFilePath := meta.Path
		if !filepath.IsAbs(assetFilePath) {
			assetFilePath = filepath.Join(manifestDir, assetFilePath)
		}

		sigPath, err := SignAsset(assetFilePath, privKeyStr, password)
		if err != nil {
			return fmt.Errorf("sign asset %s (%s): %w", name, assetFilePath, err)
		}

		dataPairs = append(dataPairs, assetFilePair{
			dataFilePath: assetFilePath,
			sigFilePath:  sigPath,
		})
	}

	// 2. Sign manifest.json
	manifestPath := filepath.Join(manifestDir, "manifest.json")
	if err := manifest.Save(manifestPath); err != nil {
		return fmt.Errorf("save manifest %s: %w", manifestPath, err)
	}
	manifestSigPath, err := SignAsset(manifestPath, privKeyStr, password)
	if err != nil {
		return fmt.Errorf("sign manifest %s: %w", manifestPath, err)
	}

	// 3. Locate or create release for Tag on GitHub
	release, err := p.getOrCreateRelease(ctx)
	if err != nil {
		return fmt.Errorf("locate or create release for tag %s: %w", p.cfg.Tag, err)
	}

	// 4. Upload all compressed data assets and their .sig files
	var uploadedDataAssets []*githubAsset
	for _, pair := range dataPairs {
		dataAsset, err := p.uploadAsset(ctx, release, pair.dataFilePath)
		if err != nil {
			return fmt.Errorf("upload data asset %s: %w", filepath.Base(pair.dataFilePath), err)
		}
		uploadedDataAssets = append(uploadedDataAssets, dataAsset)

		sigAsset, err := p.uploadAsset(ctx, release, pair.sigFilePath)
		if err != nil {
			return fmt.Errorf("upload signature %s: %w", filepath.Base(pair.sigFilePath), err)
		}
		uploadedDataAssets = append(uploadedDataAssets, sigAsset)
	}

	// 5. Verification check: Verify each uploaded data asset returns HTTP 200 OK
	for _, asset := range uploadedDataAssets {
		if err := p.verifyAssetAvailability(ctx, asset); err != nil {
			return fmt.Errorf("asset verification check failed for %s: %w", asset.Name, err)
		}
	}

	// 6. Upload manifest.json and manifest.json.sig LAST
	if _, err := p.uploadAsset(ctx, release, manifestPath); err != nil {
		return fmt.Errorf("upload manifest.json: %w", err)
	}

	if _, err := p.uploadAsset(ctx, release, manifestSigPath); err != nil {
		return fmt.Errorf("upload manifest.json.sig: %w", err)
	}

	return nil
}

// PublishSnapshotSet creates a Publisher and executes PublishSnapshotSet.
// An optional baseURL can be provided (e.g. for mock testing or staging); if omitted,
// it uses GITHUB_API_BASE_URL env or "https://api.github.com".
func PublishSnapshotSet(ctx context.Context, client *http.Client, token, owner, repo, tag, manifestDir string, manifest *Manifest, privKeyStr, password string, baseURL ...string) error {
	var base string
	if len(baseURL) > 0 && strings.TrimSpace(baseURL[0]) != "" {
		base = strings.TrimSpace(baseURL[0])
	}
	pub, err := NewPublisher(PublisherConfig{
		Owner:   owner,
		Repo:    repo,
		Tag:     tag,
		Token:   token,
		Client:  client,
		BaseURL: base,
	})
	if err != nil {
		return err
	}
	return pub.PublishSnapshotSet(ctx, manifestDir, manifest, privKeyStr, password)
}
