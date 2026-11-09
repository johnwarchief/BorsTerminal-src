package sync

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"

	"borsterminal/backend/internal/pointerfile"
)

// safeReadJSON یک فایل JSON را خوانده و در صورت خطا map خالی برمی‌گرداند.
func safeReadJSON(path string) map[string]any {
	data, err := pointerfile.Read(path)
	if err != nil {
		return map[string]any{}
	}
	var res map[string]any
	if err := json.Unmarshal(data, &res); err != nil {
		return map[string]any{}
	}
	return res
}

func parseISO(ts string) (time.Time, error) {
	// ISO فرمت‌های رایج پایتون: 2026-10-31T12:00:00 یا همراه با میکروثانیه
	layouts := []string{
		"2006-01-02T15:04:05",
		"2006-01-02T15:04:05.999999",
		time.RFC3339,
	}
	for _, l := range layouts {
		if t, err := time.Parse(l, ts); err == nil {
			return t, nil
		}
	}
	return time.Time{}, os.ErrInvalid
}

// GetCodalDBStatus وضعیت دیتابیس کدال را از codal_db_status.json بازمی‌گرداند.
// در صورت وجود active_generation.json، اطلاعات نسل فعال اسنپ‌شات را نیز برمی‌گرداند.
func GetCodalDBStatus(dataDir string, running bool) map[string]any {
	stPath := filepath.Join(dataDir, "codal_db_status.json")
	st := safeReadJSON(stPath)

	stage, _ := st["stage"].(string)
	if stage == "" {
		stage = "idle"
	}
	pct, _ := st["percent"].(float64)
	detail, _ := st["detail"].(string)
	errStr, _ := st["error"].(string)
	ts, _ := st["ts"].(string)

	dbMap := map[string]any{
		"running": running,
		"stage":   stage,
		"percent": pct,
		"detail":  detail,
		"error":   errStr,
		"ts":      ts,
	}

	res := map[string]any{
		"status": "success",
		"db":     dbMap,
	}

	activeGenPath := filepath.Join(dataDir, "active_generation.json")
	if _, err := os.Stat(activeGenPath); err == nil {
		activeGen := safeReadJSON(activeGenPath)
		if len(activeGen) > 0 {
			dbMap["active_generation"] = activeGen
			res["active_generation"] = activeGen
		}
	}

	return res
}

// writeCodalDBStatus وضعیت دانلود اسنپ‌شات را به صورت اتمیک در codal_db_status.json ثبت می‌کند.
func writeCodalDBStatus(dataDir, stage string, percent float64, detail, errText string, now time.Time) error {
	stPath := filepath.Join(dataDir, "codal_db_status.json")
	tmpPath := stPath + ".tmp"

	data := map[string]any{
		"stage":   stage,
		"percent": percent,
		"detail":  detail,
		"error":   errText,
		"ts":      now.Format("2006-01-02T15:04:05"),
	}
	raw, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	if err := os.WriteFile(tmpPath, raw, 0644); err != nil {
		return err
	}
	if err := os.Rename(tmpPath, stPath); err != nil {
		_ = os.Remove(stPath)
		return os.Rename(tmpPath, stPath)
	}
	return nil
}

// GetSyncStatus تجمیع وضعیت‌های سینک را شبیه get_sync_status در api/_sync_codal.py انجام می‌دهد.
func GetSyncStatus(dataDir string, now time.Time) map[string]any {
	odPath := filepath.Join(dataDir, "sync_ondemand.json")
	stPath := filepath.Join(dataDir, "sync_status.json")
	msPath := filepath.Join(dataDir, "market_sync.json")

	od := safeReadJSON(odPath)
	st := safeReadJSON(stPath)
	ms := safeReadJSON(msPath)

	odStage, _ := od["stage"].(string)
	odActive := odStage != "" && odStage != "done"
	if odActive {
		if tsStr, ok := od["ts"].(string); ok && tsStr != "" {
			if t, err := parseISO(tsStr); err == nil {
				if now.Sub(t).Seconds() > 600 {
					odActive = false
				}
			} else {
				odActive = false
			}
		}
	}

	msStage, _ := ms["stage"].(string)
	msActive := msStage != "" && msStage != "done"
	if msActive {
		if tsStr, ok := ms["ts"].(string); ok && tsStr != "" {
			if t, err := parseISO(tsStr); err == nil {
				if now.Sub(t).Seconds() > 600 {
					msActive = false
				}
			} else {
				msActive = false
			}
		} else {
			msActive = false
		}
	}

	var merged map[string]any
	if odActive {
		merged = map[string]any{
			"source":  "od",
			"active":  true,
			"symbol":  getString(od, "symbol"),
			"stage":   getStringDefault(od, "stage", "idle"),
			"detail":  getString(od, "detail"),
			"phase":   getString(st, "phase"),
			"total":   getInt(st, "total"),
			"current": getInt(st, "current"),
			"percent": getFloat(st, "percent"),
			"elapsed": getFloat(st, "elapsed"),
			"ts":      getString(od, "ts"),
		}
	} else {
		stAlive := false
		stStage := getString(st, "stage")
		stPhase := getString(st, "phase")
		if stStage != "" && stStage != "done" && stStage != "idle" && stPhase != "codal_stopped" {
			if tsStr, ok := st["ts"].(string); ok && tsStr != "" {
				if t, err := parseISO(tsStr); err == nil {
					stAlive = now.Sub(t).Seconds() <= 60
				}
			}
		}

		merged = map[string]any{
			"source":  "global",
			"active":  stAlive,
			"symbol":  getString(st, "symbol"),
			"stage":   getStringDefault(st, "stage", "idle"),
			"detail":  getString(st, "detail"),
			"phase":   getString(st, "phase"),
			"total":   getInt(st, "total"),
			"current": getInt(st, "current"),
			"percent": getFloat(st, "percent"),
			"elapsed": getFloat(st, "elapsed"),
			"ts":      getString(st, "ts"),
		}

		if msActive && !stAlive {
			merged["source"] = "market"
			merged["active"] = true
			merged["symbol"] = getString(ms, "symbol")
			merged["stage"] = getStringDefault(ms, "stage", "tsetmc")
			merged["detail"] = getString(ms, "detail")
			merged["phase"] = getString(ms, "phase")
			merged["total"] = getInt(ms, "total")
			merged["current"] = getInt(ms, "current")
			merged["percent"] = getFloat(ms, "percent")
			merged["elapsed"] = getFloat(ms, "elapsed")
			merged["ts"] = getString(ms, "ts")
		}
	}

	merged["ban_until"] = getString(st, "ban_until")

	res := map[string]any{
		"status": "success",
		"sync":   merged,
	}

	activeGenPath := filepath.Join(dataDir, "active_generation.json")
	if _, err := os.Stat(activeGenPath); err == nil {
		activeGen := safeReadJSON(activeGenPath)
		if len(activeGen) > 0 {
			res["active_generation"] = activeGen
			merged["active_generation"] = activeGen
		}
	}

	return res
}

func getString(m map[string]any, key string) string {
	if v, ok := m[key].(string); ok {
		return v
	}
	return ""
}

func getStringDefault(m map[string]any, key, def string) string {
	if v, ok := m[key].(string); ok && v != "" {
		return v
	}
	return def
}

func getInt(m map[string]any, key string) int {
	switch v := m[key].(type) {
	case float64:
		return int(v)
	case int:
		return v
	case int64:
		return int(v)
	}
	return 0
}

func getFloat(m map[string]any, key string) float64 {
	switch v := m[key].(type) {
	case float64:
		return v
	case int:
		return float64(v)
	case int64:
		return float64(v)
	}
	return 0.0
}
