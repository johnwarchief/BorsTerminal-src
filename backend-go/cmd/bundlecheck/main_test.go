package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestScanCleanBundle(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "borsd.exe"), []byte("MZ fake go binary"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "manifest.json"), []byte(`{"schema":"oc.bundle/1"}`), 0o644); err != nil {
		t.Fatal(err)
	}
	findings, err := Scan(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(findings) != 0 {
		t.Fatalf("clean bundle findings = %v", findings)
	}
}

func TestScanFindsPythonArtifacts(t *testing.T) {
	cases := []struct {
		name   string
		reason string
	}{
		{"python.exe", "python interpreter"},
		{"python311.dll", "python runtime library"},
		{"uvicorn.exe", "uvicorn artifact"},
		{"fastapi_server.dll", "fastapi artifact"},
		{"service.py", "python source"},
		{"module.pyc", "python bytecode"},
		{"vendor/libpython3.14.so", "python runtime library"},
		{"PyInstaller.exe", "pyinstaller artifact"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			dir := t.TempDir()
			path := filepath.Join(dir, tc.name)
			if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(path, []byte("x"), 0o644); err != nil {
				t.Fatal(err)
			}
			findings, err := Scan(dir)
			if err != nil {
				t.Fatal(err)
			}
			if len(findings) != 1 || findings[0].Reason != tc.reason {
				t.Fatalf("findings = %+v, want reason %q", findings, tc.reason)
			}
		})
	}
}

func TestScanFindsEmbeddedNeedles(t *testing.T) {
	dir := t.TempDir()
	binary := append([]byte("MZ\x90\x00 some padding "), []byte("Import-Uvicorn-App")...)
	if err := os.WriteFile(filepath.Join(dir, "helper.exe"), binary, 0o644); err != nil {
		t.Fatal(err)
	}
	findings, err := Scan(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(findings) != 1 || !strings.Contains(findings[0].Reason, "uvicorn") {
		t.Fatalf("findings = %+v", findings)
	}
}

func TestPlainTextMentionIsNotABinaryFinding(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "README.txt"), []byte("we removed uvicorn and fastapi"), 0o644); err != nil {
		t.Fatal(err)
	}
	findings, err := Scan(dir)
	if err != nil {
		t.Fatal(err)
	}
	if len(findings) != 0 {
		t.Fatalf("text prose must not fail the binary contract: %v", findings)
	}
}

func TestRunExitCodes(t *testing.T) {
	clean := t.TempDir()
	if err := os.WriteFile(filepath.Join(clean, "borsd.exe"), []byte("MZ"), 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	if code := run([]string{"-path", clean}, &out); code != 0 {
		t.Fatalf("clean exit = %d: %s", code, out.String())
	}
	if !strings.Contains(out.String(), "contract OK") {
		t.Fatalf("output = %s", out.String())
	}

	dirty := t.TempDir()
	if err := os.WriteFile(filepath.Join(dirty, "python.exe"), []byte("MZ"), 0o644); err != nil {
		t.Fatal(err)
	}
	out.Reset()
	if code := run([]string{"-path", dirty}, &out); code != 1 {
		t.Fatalf("dirty exit = %d: %s", code, out.String())
	}
	if !strings.Contains(out.String(), "FORBIDDEN") {
		t.Fatalf("output = %s", out.String())
	}

	out.Reset()
	if code := run([]string{}, &out); code != 2 {
		t.Fatalf("missing path exit = %d", code)
	}
}
