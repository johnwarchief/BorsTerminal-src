package sync

import (
	"testing"
	"time"
)

type mockProber struct {
	codalProcs int
	appProcs   int
	adbPath    string
	hasDevice  bool
	tetherUp   bool
}

func (m mockProber) CountProcs(name string) int {
	if name == "codal_fetcher" {
		return m.codalProcs
	}
	if name == "app.py" {
		return m.appProcs
	}
	return 0
}

func (m mockProber) FindADB() string {
	return m.adbPath
}

func (m mockProber) HasADBDevice(adbPath string) bool {
	return m.hasDevice
}

func (m mockProber) IsTetherUp() bool {
	return m.tetherUp
}

func TestDiagnose(t *testing.T) {
	tmp := t.TempDir()
	now := time.Now()

	p := mockProber{
		codalProcs: 2,
		appProcs:   1,
		adbPath:    "C:/platform-tools/adb.exe",
		hasDevice:  true,
		tetherUp:   true,
	}

	res := Diagnose(tmp, now, p)
	diag, ok := res["diag"].(map[string]any)
	if !ok {
		t.Fatalf("expected diag map, got %v", res)
	}

	if diag["codal_process_running"] != true {
		t.Errorf("expected codal_process_running=true")
	}
	if diag["app_processes"] != 1 {
		t.Errorf("expected app_processes=1, got %v", diag["app_processes"])
	}
	if diag["adb_found"] != true {
		t.Errorf("expected adb_found=true")
	}
	if diag["adb_device"] != true {
		t.Errorf("expected adb_device=true")
	}
	if diag["adb_tether_up"] != true {
		t.Errorf("expected adb_tether_up=true")
	}
}
