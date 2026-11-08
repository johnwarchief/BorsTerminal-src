package snapshot

import (
	"crypto/rand"
	"encoding/base64"
	"os"
	"path/filepath"
	"testing"

	"aead.dev/minisign"
)

func TestSigner_GenerateTestKeyPair(t *testing.T) {
	pubStr, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}
	if pubStr == "" {
		t.Fatal("expected non-empty public key string")
	}
	if privStr == "" {
		t.Fatal("expected non-empty private key string")
	}

	pub, err := ParsePublicKey(pubStr)
	if err != nil {
		t.Fatalf("ParsePublicKey failed: %v", err)
	}

	priv, err := ParsePrivateKey(privStr, "")
	if err != nil {
		t.Fatalf("ParsePrivateKey failed: %v", err)
	}

	if pub.ID() != priv.ID() {
		t.Fatalf("key ID mismatch: pub=%d, priv=%d", pub.ID(), priv.ID())
	}
}

func TestSigner_ParsePublicKey_Base64(t *testing.T) {
	const rawB64 = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3NgpSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="
	pub, err := ParsePublicKey(rawB64)
	if err != nil {
		t.Fatalf("ParsePublicKey with base64 failed: %v", err)
	}
	if pub.ID() == 0 {
		t.Fatal("expected non-zero key ID")
	}
}

func TestSigner_ParsePrivateKey_Base64(t *testing.T) {
	_, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair failed: %v", err)
	}

	b64Priv := base64.StdEncoding.EncodeToString([]byte(privStr))
	priv, err := ParsePrivateKey(b64Priv, "")
	if err != nil {
		t.Fatalf("ParsePrivateKey with base64 failed: %v", err)
	}
	if priv.ID() == 0 {
		t.Fatal("expected non-zero key ID")
	}
}

func TestSigner_SignAndVerifyAsset_Success(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "test_asset.db.lzma")
	content := []byte("this is a test database snapshot payload with some entropy: 1234567890")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("write test file: %v", err)
	}

	pubStr, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("GenerateTestKeyPair: %v", err)
	}

	sigPath, err := SignAsset(testFile, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset failed: %v", err)
	}
	expectedSigPath := testFile + ".sig"
	if sigPath != expectedSigPath {
		t.Fatalf("expected sigPath %s, got %s", expectedSigPath, sigPath)
	}

	if _, err := os.Stat(sigPath); err != nil {
		t.Fatalf("signature file not found on disk: %v", err)
	}

	if err := VerifyAsset(testFile, sigPath, pubStr); err != nil {
		t.Fatalf("VerifyAsset failed: %v", err)
	}
}

func TestSigner_VerifyFails_TamperedContent(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "asset.bin")
	content := []byte("original uncorrupted snapshot bytes")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("write file: %v", err)
	}

	pubStr, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate keypair: %v", err)
	}

	sigPath, err := SignAsset(testFile, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset failed: %v", err)
	}

	// Tamper 1 byte of the content
	tamperedContent := append([]byte(nil), content...)
	tamperedContent[0] ^= 0xFF
	if err := os.WriteFile(testFile, tamperedContent, 0644); err != nil {
		t.Fatalf("write tampered file: %v", err)
	}

	err = VerifyAsset(testFile, sigPath, pubStr)
	if err == nil {
		t.Fatal("expected VerifyAsset to fail on tampered content, but it passed")
	}
}

func TestSigner_VerifyFails_TamperedSignature(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "asset.bin")
	content := []byte("original payload")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("write file: %v", err)
	}

	pubStr, privStr, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate keypair: %v", err)
	}

	sigPath, err := SignAsset(testFile, privStr, "")
	if err != nil {
		t.Fatalf("SignAsset failed: %v", err)
	}

	// Tamper signature file
	sigBytes, err := os.ReadFile(sigPath)
	if err != nil {
		t.Fatalf("read sig: %v", err)
	}
	sigBytes[len(sigBytes)/2] ^= 0x55
	if err := os.WriteFile(sigPath, sigBytes, 0644); err != nil {
		t.Fatalf("write tampered sig: %v", err)
	}

	err = VerifyAsset(testFile, sigPath, pubStr)
	if err == nil {
		t.Fatal("expected VerifyAsset to fail on corrupted signature, but it passed")
	}
}

func TestSigner_VerifyFails_WrongPublicKey(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "asset.bin")
	content := []byte("important financial snapshot data")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("write file: %v", err)
	}

	_, privStr1, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate keypair 1: %v", err)
	}
	pubStr2, _, err := GenerateTestKeyPair()
	if err != nil {
		t.Fatalf("generate keypair 2: %v", err)
	}

	sigPath, err := SignAsset(testFile, privStr1, "")
	if err != nil {
		t.Fatalf("SignAsset failed: %v", err)
	}

	err = VerifyAsset(testFile, sigPath, pubStr2)
	if err == nil {
		t.Fatal("expected VerifyAsset to fail with wrong public key, but it passed")
	}
}

func TestSigner_EncryptedPrivateKey(t *testing.T) {
	tempDir := t.TempDir()
	testFile := filepath.Join(tempDir, "data.lzma")
	content := []byte("confidential production snapshot")
	if err := os.WriteFile(testFile, content, 0644); err != nil {
		t.Fatalf("write file: %v", err)
	}

	pub, priv, err := minisign.GenerateKey(rand.Reader)
	if err != nil {
		t.Fatalf("minisign GenerateKey: %v", err)
	}

	password := "SecretPass123!#"
	encPrivBytes, err := minisign.EncryptKey(password, priv)
	if err != nil {
		t.Fatalf("EncryptKey: %v", err)
	}
	encPrivStr := string(encPrivBytes)

	pubBytes, err := pub.MarshalText()
	if err != nil {
		t.Fatalf("MarshalText: %v", err)
	}
	pubStr := string(pubBytes)

	// Decryption with wrong password should fail
	_, err = ParsePrivateKey(encPrivStr, "WrongPassword")
	if err == nil {
		t.Fatal("expected ParsePrivateKey with wrong password to fail, but it succeeded")
	}

	// Decryption with correct password should succeed
	decPriv, err := ParsePrivateKey(encPrivStr, password)
	if err != nil {
		t.Fatalf("ParsePrivateKey with correct password failed: %v", err)
	}
	if decPriv.ID() != pub.ID() {
		t.Fatalf("ID mismatch: decPriv=%d, pub=%d", decPriv.ID(), pub.ID())
	}

	// Sign with password-protected private key
	sigPath, err := SignAsset(testFile, encPrivStr, password)
	if err != nil {
		t.Fatalf("SignAsset with encrypted key failed: %v", err)
	}

	if err := VerifyAsset(testFile, sigPath, pubStr); err != nil {
		t.Fatalf("VerifyAsset failed for encrypted key signature: %v", err)
	}
}

func TestSigner_InvalidInputs(t *testing.T) {
	if _, err := ParsePublicKey(""); err == nil {
		t.Fatal("expected error on empty public key")
	}
	if _, err := ParsePublicKey("not-a-valid-minisign-key"); err == nil {
		t.Fatal("expected error on malformed public key")
	}

	if _, err := ParsePrivateKey("", ""); err == nil {
		t.Fatal("expected error on empty private key")
	}
	if _, err := ParsePrivateKey("invalid-priv-key", ""); err == nil {
		t.Fatal("expected error on malformed private key")
	}

	if _, err := SignAsset("", "key", ""); err == nil {
		t.Fatal("expected error on empty filePath in SignAsset")
	}

	if err := VerifyAsset("", "", "key"); err == nil {
		t.Fatal("expected error on empty paths in VerifyAsset")
	}
}
