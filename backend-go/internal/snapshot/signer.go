package snapshot

import (
	"crypto/rand"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"aead.dev/minisign"
)

// GenerateTestKeyPair generates an unencrypted Minisign ed25519 keypair in memory for testing and development.
func GenerateTestKeyPair() (pubKeyStr, privKeyStr string, err error) {
	pub, priv, err := minisign.GenerateKey(rand.Reader)
	if err != nil {
		return "", "", fmt.Errorf("generate minisign keypair: %w", err)
	}

	pubBytes, err := pub.MarshalText()
	if err != nil {
		return "", "", fmt.Errorf("marshal public key: %w", err)
	}

	privBytes, err := priv.MarshalText()
	if err != nil {
		return "", "", fmt.Errorf("marshal private key: %w", err)
	}

	return string(pubBytes), string(privBytes), nil
}

// ParsePrivateKey decodes a Minisign private key string, handling unencrypted keys via UnmarshalText
// or password-encrypted keys via DecryptKey.
func ParsePrivateKey(privKeyStr, password string) (minisign.PrivateKey, error) {
	clean := strings.TrimSpace(privKeyStr)
	if clean == "" {
		return minisign.PrivateKey{}, errors.New("private key string is empty")
	}

	raw := []byte(clean)

	if minisign.IsEncrypted(raw) {
		key, err := minisign.DecryptKey(password, raw)
		if err != nil {
			return minisign.PrivateKey{}, fmt.Errorf("decrypt private key: %w", err)
		}
		return key, nil
	}

	var key minisign.PrivateKey
	if err := key.UnmarshalText(raw); err != nil {
		// If UnmarshalText failed and a password is provided, attempt decryption as fallback
		if password != "" {
			if decKey, decErr := minisign.DecryptKey(password, raw); decErr == nil {
				return decKey, nil
			}
		}
		return minisign.PrivateKey{}, fmt.Errorf("parse private key: %w", err)
	}
	return key, nil
}

// ParsePublicKey decodes a Minisign public key string via UnmarshalText.
func ParsePublicKey(pubKeyStr string) (minisign.PublicKey, error) {
	clean := strings.TrimSpace(pubKeyStr)
	if clean == "" {
		return minisign.PublicKey{}, errors.New("public key string is empty")
	}

	var pub minisign.PublicKey
	if err := pub.UnmarshalText([]byte(clean)); err != nil {
		return minisign.PublicKey{}, fmt.Errorf("parse public key: %w", err)
	}
	return pub, nil
}

// SignAsset signs the file at filePath using the provided Minisign private key and password,
// writes the signature to <filePath>.sig alongside the asset, and returns the signature file path.
func SignAsset(filePath string, privKeyStr, password string) (sigPath string, err error) {
	if strings.TrimSpace(filePath) == "" {
		return "", errors.New("filePath is required")
	}

	privKey, err := ParsePrivateKey(privKeyStr, password)
	if err != nil {
		return "", fmt.Errorf("parse private key for %s: %w", filePath, err)
	}

	msg, err := os.ReadFile(filePath)
	if err != nil {
		return "", fmt.Errorf("read asset %s to sign: %w", filePath, err)
	}

	trustedComment := fmt.Sprintf("timestamp:%d\tfile:%s", time.Now().UTC().Unix(), filepath.Base(filePath))
	untrustedComment := fmt.Sprintf("signature from BorsTerminal snapshot key: %016X", privKey.ID())

	sigBytes := minisign.SignWithComments(privKey, msg, trustedComment, untrustedComment)

	sigPath = filePath + ".sig"
	if err := os.WriteFile(sigPath, sigBytes, 0644); err != nil {
		return "", fmt.Errorf("write signature to %s: %w", sigPath, err)
	}

	return sigPath, nil
}

// VerifyAsset verifies that the asset file at filePath matches the Minisign signature at sigPath
// using the given public key string. Returns nil if valid, or an error if invalid or tampered.
func VerifyAsset(filePath string, sigPath string, pubKeyStr string) error {
	if strings.TrimSpace(filePath) == "" {
		return errors.New("filePath is required")
	}
	if strings.TrimSpace(sigPath) == "" {
		return errors.New("sigPath is required")
	}

	pubKey, err := ParsePublicKey(pubKeyStr)
	if err != nil {
		return fmt.Errorf("invalid public key: %w", err)
	}

	msg, err := os.ReadFile(filePath)
	if err != nil {
		return fmt.Errorf("read asset %s for verification: %w", filePath, err)
	}

	sigBytes, err := os.ReadFile(sigPath)
	if err != nil {
		return fmt.Errorf("read signature %s: %w", sigPath, err)
	}

	if !minisign.Verify(pubKey, msg, sigBytes) {
		return fmt.Errorf("verification failed for %s: signature invalid or content tampered", filePath)
	}

	return nil
}
