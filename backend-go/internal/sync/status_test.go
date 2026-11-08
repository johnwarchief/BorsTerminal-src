package sync

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
	"time"
)

func TestGetCodalDBStatus(t *testing.T) {
	tmp := t.TempDir()
	stPath := filepath.Join(tmp, "codal_db_status.json")

	// حالت نبود فایل
	res := GetCodalDBStatus(tmp, false)
	dbMap, ok := res["db"].(map[string]any)
	if !ok || dbMap["stage"] != "idle" || dbMap["running"] != false {
		t.Fatalf("expected idle not running, got %v", res)
	}

	// ایجاد فایل وضعیت دانلود
	stData := map[string]any{
		"stage":   "downloading",
		"percent": 45.5,
		"detail":  "45.5MB / 100MB",
		"error":   "",
		"ts":      "2026-10-31T12:00:00",
	}
	raw, _ := json.Marshal(stData)
	_ = os.WriteFile(stPath, raw, 0644)

	res = GetCodalDBStatus(tmp, true)
	dbMap, _ = res["db"].(map[string]any)
	if dbMap["stage"] != "downloading" || dbMap["running"] != true || dbMap["percent"] != 45.5 {
		t.Fatalf("expected downloading running with 45.5%%, got %v", dbMap)
	}
}

func TestGetSyncStatusMerging(t *testing.T) {
	tmp := t.TempDir()
	now := time.Date(2026, 10, 31, 12, 0, 0, 0, time.UTC)

	// ۱. دایرکتوری خالی -> وضعیت global غیرفعال
	res := GetSyncStatus(tmp, now)
	syncMap, ok := res["sync"].(map[string]any)
	if !ok || syncMap["active"] != false || syncMap["source"] != "global" {
		t.Fatalf("expected inactive global, got %v", syncMap)
	}

	// ۲. وضعیت on-demand فعال (تازه‌تر از ۶۰۰ ثانیه)
	odPath := filepath.Join(tmp, "sync_ondemand.json")
	odData := map[string]any{
		"stage":  "fetching",
		"symbol": "فولاد",
		"ts":     "2026-10-31T11:55:00", // ۵ دقیقه پیش
		"detail": "در حال دریافت",
	}
	raw, _ := json.Marshal(odData)
	_ = os.WriteFile(odPath, raw, 0644)

	res = GetSyncStatus(tmp, now)
	syncMap = res["sync"].(map[string]any)
	if syncMap["active"] != true || syncMap["source"] != "od" || syncMap["symbol"] != "فولاد" {
		t.Fatalf("expected active od for فولاد, got %v", syncMap)
	}

	// ۳. کهنه شدن on-demand (> ۶۰۰ ثانیه) -> سقوط به global
	odData["ts"] = "2026-10-31T11:40:00" // ۲۰ دقیقه پیش
	raw, _ = json.Marshal(odData)
	_ = os.WriteFile(odPath, raw, 0644)

	res = GetSyncStatus(tmp, now)
	syncMap = res["sync"].(map[string]any)
	if syncMap["source"] != "global" || syncMap["active"] != false {
		t.Fatalf("expected fallback to global, got %v", syncMap)
	}

	// ۴. وضعیت global زنده (<= ۶۰ ثانیه)
	stPath := filepath.Join(tmp, "sync_status.json")
	stData := map[string]any{
		"stage":  "scanning",
		"phase":  "parse",
		"symbol": "فملی",
		"ts":     "2026-10-31T11:59:30", // ۳۰ ثانیه پیش
		"total":  100,
	}
	raw, _ = json.Marshal(stData)
	_ = os.WriteFile(stPath, raw, 0644)

	res = GetSyncStatus(tmp, now)
	syncMap = res["sync"].(map[string]any)
	if syncMap["source"] != "global" || syncMap["active"] != true || syncMap["symbol"] != "فملی" {
		t.Fatalf("expected active global for فملی, got %v", syncMap)
	}
}

func TestGetSyncStatus_ActiveGeneration(t *testing.T) {
	tmp := t.TempDir()
	now := time.Date(2026, 11, 8, 12, 0, 0, 0, time.UTC)

	// Without active_generation.json
	res := GetSyncStatus(tmp, now)
	if _, ok := res["active_generation"]; ok {
		t.Errorf("expected no active_generation when file absent")
	}

	// With active_generation.json
	activeData := map[string]any{
		"snapshot_set_id": "gen_test_99",
		"generation_dir":  "gens/gen_test_99",
		"applied_at_utc":  "2026-11-08T12:00:00Z",
	}
	raw, _ := json.Marshal(activeData)
	_ = os.WriteFile(filepath.Join(tmp, "active_generation.json"), raw, 0644)

	res = GetSyncStatus(tmp, now)
	ag, ok := res["active_generation"].(map[string]any)
	if !ok || ag["snapshot_set_id"] != "gen_test_99" {
		t.Fatalf("expected active_generation with snapshot_set_id gen_test_99, got %v", res)
	}
}
