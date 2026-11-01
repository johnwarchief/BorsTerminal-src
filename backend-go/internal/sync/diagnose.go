package sync

import (
	"context"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

// DiagProber رابط برای استعلام وضعیت پردازه‌ها و ADB است تا تست‌ها بدون وابستگی به محیط خارجی ایزوله باشند.
type DiagProber interface {
	CountProcs(name string) int
	FindADB() string
	HasADBDevice(adbPath string) bool
	IsTetherUp() bool
}

type defaultProber struct{}

func (d defaultProber) CountProcs(name string) int {
	return 0
}

func (d defaultProber) FindADB() string {
	for _, p := range []string{"adb.exe", "tools/adb.exe", "C:/platform-tools/adb.exe"} {
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	if path, err := exec.LookPath("adb"); err == nil {
		return path
	}
	return ""
}

func (d defaultProber) HasADBDevice(adbPath string) bool {
	if adbPath == "" {
		return false
	}
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	defer cancel()
	cmd := exec.CommandContext(ctx, adbPath, "devices")
	out, err := cmd.Output()
	if err != nil {
		return false
	}
	lines := strings.Split(string(out), "\n")
	for _, l := range lines {
		fields := strings.Fields(l)
		if len(fields) >= 2 && fields[1] == "device" {
			return true
		}
	}
	return false
}

func (d defaultProber) IsTetherUp() bool {
	return false
}

// Diagnose گزارش تشخیصی فرآیندها، سن فایل وضعیت و اتصالات را تولید می‌کند.
func Diagnose(dataDir string, now time.Time, prober DiagProber) map[string]any {
	if prober == nil {
		prober = defaultProber{}
	}

	codalCount := prober.CountProcs("codal_fetcher")
	appCount := prober.CountProcs("app.py")
	adbPath := prober.FindADB()
	adbFound := adbPath != ""
	adbDevice := false
	if adbFound {
		adbDevice = prober.HasADBDevice(adbPath)
	}

	stPath := filepath.Join(dataDir, "sync_status.json")
	var statusAge float64 = -1.0
	statusFrozen := false

	if fi, err := os.Stat(stPath); err == nil {
		age := now.Sub(fi.ModTime()).Seconds()
		statusAge = math.Round(age*10) / 10
		statusFrozen = age > 60 && codalCount > 0
	}

	st := safeReadJSON(stPath)

	info := map[string]any{
		"codal_process_running": codalCount > 0,
		"app_processes":         appCount,
		"adb_found":             adbFound,
		"adb_device":            adbDevice,
		"adb_enabled":           false,
		"status_file_age_sec":   statusAge,
		"status_frozen":         statusFrozen,
		"adb_tether_up":         prober.IsTetherUp(),
		"phase":                 getString(st, "phase"),
		"detail":                getString(st, "detail"),
		"symbol":                getString(st, "symbol"),
		"ts":                    getString(st, "ts"),
	}

	return map[string]any{
		"status": "success",
		"diag":   info,
	}
}
