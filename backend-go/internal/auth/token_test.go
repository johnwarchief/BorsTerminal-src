package auth

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"borsterminal/backend/internal/securefile"
)

func TestTokenFromEnvironment(t *testing.T) {
	getenv := func(k string) string {
		if k == "BORS_API_TOKEN" {
			return "short"
		}
		return ""
	}
	if _, err := NewToken(t.TempDir(), getenv); err == nil {
		t.Fatal("short env token must be rejected")
	}
	getenv = func(k string) string {
		if k == "BORS_API_TOKEN" {
			return "0123456789abcdef-dev"
		}
		return ""
	}
	tok, err := NewToken(t.TempDir(), getenv)
	if err != nil {
		t.Fatal(err)
	}
	if tok.Value != "0123456789abcdef-dev" || tok.File != "" {
		t.Fatalf("token = %+v", tok)
	}
}

func TestRandomTokenFileIsRestricted(t *testing.T) {
	dataDir := t.TempDir()
	tok, err := NewToken(dataDir, func(string) string { return "" })
	if err != nil {
		t.Fatal(err)
	}
	if len(tok.Value) != 64 {
		t.Fatalf("token length = %d", len(tok.Value))
	}
	if tok.File != filepath.Join(dataDir, "oc", "runtime", "api_token") {
		t.Fatalf("token file = %s", tok.File)
	}
	raw, err := os.ReadFile(tok.File)
	if err != nil {
		t.Fatal(err)
	}
	if strings.TrimSpace(string(raw)) != tok.Value {
		t.Fatal("token file content mismatch")
	}
	if err := securefile.Verify(tok.File); err != nil {
		t.Fatalf("token file ACL: %v", err)
	}
	// Per-launch: the next process launch must not reuse the old token.
	tok2, err := NewToken(dataDir, func(string) string { return "" })
	if err != nil {
		t.Fatal(err)
	}
	if tok2.Value == tok.Value {
		t.Fatal("token was reused across launches")
	}
}
