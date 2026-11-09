package auth

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"borsterminal/backend/internal/securefile"
)

// Token یک رازِ per-launch است که SPA از کوکی و پلِ Tauri از فایل می‌خواند.
// هیچ‌جا در URL یا لاگ نوشته نمی‌شود.
type Token struct {
	Value string
	File  string
}

// NewToken: اگر BORS_API_TOKEN ست شده باشد (فقط dev/test) همان استفاده
// می‌شود؛ وگرنه ۳۲ بایت تصادفیِ تازه در هر اجرا ساخته و در فایلِ ACL‌دار
// dataDir/oc/runtime/api_token نوشته می‌شود.
func NewToken(dataDir string, getenv func(string) string) (*Token, error) {
	if v := strings.TrimSpace(getenv("BORS_API_TOKEN")); v != "" {
		if len(v) < 16 {
			return nil, errors.New("BORS_API_TOKEN must be at least 16 characters")
		}
		return &Token{Value: v}, nil
	}
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return nil, fmt.Errorf("generate api token: %w", err)
	}
	value := hex.EncodeToString(buf)

	dir := filepath.Join(dataDir, "oc", "runtime")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, fmt.Errorf("create runtime dir: %w", err)
	}
	tmp, err := os.CreateTemp(dir, ".api_token-*")
	if err != nil {
		return nil, fmt.Errorf("create token temp: %w", err)
	}
	tmpName := tmp.Name()
	defer os.Remove(tmpName)
	if err := tmp.Chmod(0o600); err != nil {
		_ = tmp.Close()
		return nil, fmt.Errorf("chmod token temp: %w", err)
	}
	if _, err := tmp.WriteString(value + "\n"); err != nil {
		_ = tmp.Close()
		return nil, fmt.Errorf("write token temp: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return nil, err
	}
	if err := tmp.Close(); err != nil {
		return nil, err
	}
	if err := securefile.Restrict(tmpName); err != nil {
		return nil, fmt.Errorf("restrict token acl: %w", err)
	}
	final := filepath.Join(dir, "api_token")
	if err := os.Rename(tmpName, final); err != nil {
		return nil, fmt.Errorf("commit token file: %w", err)
	}
	return &Token{Value: value, File: final}, nil
}
