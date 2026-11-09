package sync

import (
	"encoding/json"
	"os"
	"path/filepath"
	"time"
)

// WriteControl فرمان کنترلی کاربر (pause/resume/stop) را در codal_control.json می‌نویسد.
func WriteControl(dataDir, cmd string, now time.Time) error {
	controlPath := filepath.Join(dataDir, "codal_control.json")
	tmpPath := controlPath + ".tmp"

	data := map[string]string{
		"cmd": cmd,
		"ts":  now.Format("2006-01-02T15:04:05"),
	}
	raw, err := json.Marshal(data)
	if err != nil {
		return err
	}
	if err := os.WriteFile(tmpPath, raw, 0644); err != nil {
		return err
	}
	_ = os.Rename(tmpPath, controlPath)

	if cmd == "stop" {
		stPath := filepath.Join(dataDir, "sync_status.json")
		st := safeReadJSON(stPath)
		st["phase"] = "codal_stopped"
		st["detail"] = "اسکن توسط کاربر متوقف شد"
		st["ts"] = now.Format("2006-01-02T15:04:05")
		stRaw, err := json.Marshal(st)
		if err == nil {
			tmpSt := stPath + ".tmp"
			if err := os.WriteFile(tmpSt, stRaw, 0644); err == nil {
				_ = os.Rename(tmpSt, stPath)
			}
		}
	}
	return nil
}
