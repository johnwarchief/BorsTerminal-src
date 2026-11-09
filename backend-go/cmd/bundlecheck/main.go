// Command bundlecheck قراردادِ P0.7 را می‌سنجد: بستهٔ کلاینت نباید هیچ فایل یا
// رشتهٔ Python/Uvicorn/FastAPI داشته باشد. کلاینت Go باید بدونِ مفسر/فریم‌ورکِ
// پایتون اجرا شود؛ وجودِ هر یک از این نشانه‌ها یعنی بسته از مسیرِ قدیمی ساخته شده.
package main

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
)

type Finding struct {
	Path   string `json:"path"`
	Reason string `json:"reason"`
}

var forbiddenExtensions = map[string]string{
	".py":   "python source",
	".pyc":  "python bytecode",
	".pyo":  "python bytecode",
	".pyd":  "python extension module",
	".pyz":  "python zip app",
	".pyw":  "python source",
}

var binaryExtensions = map[string]bool{
	".exe": true, ".dll": true, ".pyd": true, ".so": true,
	".node": true, ".bin": true, ".dylib": true,
}

var forbiddenNeedles = []string{
	"uvicorn",
	"fastapi",
	"pyinstaller",
	"libpython",
}

func nameFinding(name string) string {
	lower := strings.ToLower(name)
	if reason, ok := forbiddenExtensions[strings.ToLower(filepath.Ext(name))]; ok {
		return reason
	}
	switch {
	case strings.HasPrefix(lower, "python") && strings.HasSuffix(lower, ".exe"):
		return "python interpreter"
	case strings.HasPrefix(lower, "python") && strings.HasSuffix(lower, ".dll"):
		return "python runtime library"
	case strings.HasPrefix(lower, "libpython"):
		return "python runtime library"
	case strings.HasPrefix(lower, "uvicorn"):
		return "uvicorn artifact"
	case strings.HasPrefix(lower, "fastapi"):
		return "fastapi artifact"
	case strings.HasPrefix(lower, "pyinstaller"):
		return "pyinstaller artifact"
	}
	return ""
}

func contentFindings(path, name string) ([]Finding, error) {
	if !binaryExtensions[strings.ToLower(filepath.Ext(name))] {
		return nil, nil
	}
	fi, err := os.Stat(path)
	if err != nil {
		return nil, err
	}
	if fi.Size() == 0 || fi.Size() > 512<<20 {
		return nil, nil
	}
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()

	// پنجرهٔ هم‌پوشان تا رشته‌ای که روی مرزِ بافر می‌افتد از دست نرود.
	const chunk = 1 << 20
	buf := make([]byte, chunk)
	carry := make([]byte, 0, len(forbiddenNeedles[0]))
	var out []Finding
	for {
		n, readErr := f.Read(buf)
		if n > 0 {
			window := append(append([]byte(nil), carry...), buf[:n]...)
			lower := strings.ToLower(string(window))
			for _, needle := range forbiddenNeedles {
				if strings.Contains(lower, needle) {
					out = append(out, Finding{Path: path, Reason: "binary contains " + needle})
					return out, nil
				}
			}
			if len(window) > 64 {
				carry = append(carry[:0], window[len(window)-64:]...)
			}
		}
		if readErr == io.EOF {
			break
		}
		if readErr != nil {
			return nil, readErr
		}
	}
	return out, nil
}

// Scan پوشه را بازگشتی می‌پیماید. پوشه‌هایِ به‌وضوح غیرِ محصولی (تست/داک) را
// نمی‌شود نادیده گرفت: اگر آن‌ها داخلِ بستهٔ کلاینت باشند، همان هم نقض است.
func Scan(root string) ([]Finding, error) {
	fi, err := os.Stat(root)
	if err != nil {
		return nil, err
	}
	if !fi.IsDir() {
		return nil, fmt.Errorf("%s is not a directory", root)
	}
	var findings []Finding
	err = filepath.Walk(root, func(path string, info os.FileInfo, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if info.IsDir() {
			return nil
		}
		if reason := nameFinding(info.Name()); reason != "" {
			findings = append(findings, Finding{Path: path, Reason: reason})
			return nil
		}
		content, err := contentFindings(path, info.Name())
		if err != nil {
			return err
		}
		findings = append(findings, content...)
		return nil
	})
	return findings, err
}

func run(args []string, stdout io.Writer) int {
	fs := flag.NewFlagSet("bundlecheck", flag.ContinueOnError)
	fs.SetOutput(stdout)
	root := fs.String("path", "", "client bundle directory to scan")
	asJSON := fs.Bool("json", false, "emit findings as JSON")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *root == "" {
		fmt.Fprintln(stdout, "--path is required")
		return 2
	}
	findings, err := Scan(*root)
	if err != nil {
		fmt.Fprintln(stdout, err)
		return 2
	}
	if *asJSON {
		blob, _ := json.MarshalIndent(findings, "", "  ")
		fmt.Fprintln(stdout, string(blob))
	} else {
		for _, f := range findings {
			fmt.Fprintf(stdout, "FORBIDDEN %s: %s\n", f.Path, f.Reason)
		}
	}
	if len(findings) > 0 {
		fmt.Fprintf(stdout, "bundle contract violated: %d finding(s)\n", len(findings))
		return 1
	}
	fmt.Fprintln(stdout, "bundle contract OK: no python/uvicorn/fastapi artifacts")
	return 0
}

func main() {
	os.Exit(run(os.Args[1:], os.Stdout))
}
