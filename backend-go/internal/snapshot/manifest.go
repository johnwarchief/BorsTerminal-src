package snapshot

import (
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// AssetMeta stores integrity and size metadata for an individual asset in a snapshot set.
type AssetMeta struct {
	Path                  string `json:"path"`
	SHA256                string `json:"sha256"`
	SizeBytes             int64  `json:"size_bytes"`
	UncompressedSizeBytes int64  `json:"uncompressed_size_bytes,omitempty"`
}

// Manifest represents the unified set manifest for a consistent multi-database snapshot release.
type Manifest struct {
	SnapshotSetID string               `json:"snapshot_set_id"`
	CreatedAtUTC  string               `json:"created_at_utc"`
	SchemaVersion int                  `json:"schema_version"`
	Assets        map[string]AssetMeta `json:"assets"`
}

// NewManifest creates an initialized Manifest with the current UTC timestamp.
func NewManifest(setID string, schemaVersion int) *Manifest {
	return &Manifest{
		SnapshotSetID: setID,
		CreatedAtUTC:  time.Now().UTC().Format(time.RFC3339),
		SchemaVersion: schemaVersion,
		Assets:        make(map[string]AssetMeta),
	}
}

// AddAsset registers an asset with its relative or base path and cryptographic hash.
func (m *Manifest) AddAsset(name, relOrBaseName, sha256Hex string, sizeBytes, uncompressedSizeBytes int64) {
	if m.Assets == nil {
		m.Assets = make(map[string]AssetMeta)
	}
	m.Assets[name] = AssetMeta{
		Path:                  relOrBaseName,
		SHA256:                strings.ToLower(strings.TrimSpace(sha256Hex)),
		SizeBytes:             sizeBytes,
		UncompressedSizeBytes: uncompressedSizeBytes,
	}
}

// Save marshals and writes the manifest to outPath atomically.
func (m *Manifest) Save(outPath string) error {
	if outPath == "" {
		return errors.New("outPath is empty")
	}
	dir := filepath.Dir(outPath)
	if err := os.MkdirAll(dir, 0755); err != nil {
		return fmt.Errorf("create manifest dir: %w", err)
	}

	data, err := json.MarshalIndent(m, "", "  ")
	if err != nil {
		return fmt.Errorf("marshal manifest: %w", err)
	}
	data = append(data, '\n')

	tmpPath := outPath + ".tmp"
	if err := os.WriteFile(tmpPath, data, 0644); err != nil {
		return fmt.Errorf("write manifest tmp: %w", err)
	}
	if err := os.Rename(tmpPath, outPath); err != nil {
		_ = os.Remove(tmpPath)
		return fmt.Errorf("commit manifest: %w", err)
	}
	return nil
}

// LoadManifest reads and unmarshals a manifest from the given path.
func LoadManifest(inPath string) (*Manifest, error) {
	data, err := os.ReadFile(inPath)
	if err != nil {
		return nil, fmt.Errorf("read manifest %s: %w", inPath, err)
	}
	var m Manifest
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, fmt.Errorf("unmarshal manifest %s: %w", inPath, err)
	}
	if m.Assets == nil {
		m.Assets = make(map[string]AssetMeta)
	}
	return &m, nil
}

// Validate verifies structural completeness and cryptographic integrity fields.
func (m *Manifest) Validate() error {
	if strings.TrimSpace(m.SnapshotSetID) == "" {
		return errors.New("snapshot_set_id is required")
	}
	if strings.TrimSpace(m.CreatedAtUTC) == "" {
		return errors.New("created_at_utc is required")
	}
	if m.SchemaVersion < 1 {
		return fmt.Errorf("invalid schema_version %d: must be >= 1", m.SchemaVersion)
	}
	if len(m.Assets) == 0 {
		return errors.New("manifest has no assets")
	}
	for name, asset := range m.Assets {
		if strings.TrimSpace(name) == "" {
			return errors.New("asset name cannot be empty")
		}
		if strings.TrimSpace(asset.Path) == "" {
			return fmt.Errorf("asset %q has empty path", name)
		}
		if len(asset.SHA256) != 64 {
			return fmt.Errorf("asset %q sha256 must be 64 hex characters, got %d", name, len(asset.SHA256))
		}
		if _, err := hex.DecodeString(asset.SHA256); err != nil {
			return fmt.Errorf("asset %q sha256 contains invalid hex: %w", name, err)
		}
		if asset.SizeBytes <= 0 {
			return fmt.Errorf("asset %q size_bytes must be > 0, got %d", name, asset.SizeBytes)
		}
	}
	return nil
}
