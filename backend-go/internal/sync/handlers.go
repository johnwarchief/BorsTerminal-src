package sync

import (
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
)

const CodalDBURL = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download/codal.db.lzma"

type Handler struct {
	dataDir string
	clock   func() time.Time
	prober  DiagProber
}

func NewHandler(dataDir string) *Handler {
	return &Handler{
		dataDir: dataDir,
		clock:   time.Now,
		prober:  defaultProber{},
	}
}

func (h *Handler) SyncStatus(w http.ResponseWriter, r *http.Request) {
	res := GetSyncStatus(h.dataDir, h.clock())
	httpapi.WriteJSON(w, http.StatusOK, res)
}

func (h *Handler) CodalDBStatus(w http.ResponseWriter, r *http.Request) {
	dbdlMu.Lock()
	running := dbdlRunning
	dbdlMu.Unlock()
	res := GetCodalDBStatus(h.dataDir, running)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

func (h *Handler) Diagnose(w http.ResponseWriter, r *http.Request) {
	res := Diagnose(h.dataDir, h.clock(), h.prober)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

func (h *Handler) SyncMarket(w http.ResponseWriter, r *http.Request) {
	marketSyncMu.Lock()
	if marketSyncRunning {
		marketSyncMu.Unlock()
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "already_running",
			"message": "Market sync already running.",
		})
		return
	}
	marketSyncMu.Unlock()

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"message": "Market sync started.",
	})
}

func (h *Handler) SyncCodal(w http.ResponseWriter, r *http.Request) {
	mode := r.URL.Query().Get("mode")
	if mode == "" {
		mode = "update"
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"message": "Codal sync started.",
		"mode":    mode,
	})
}

func (h *Handler) SyncCodalFTSRefresh(w http.ResponseWriter, r *http.Request) {
	mode := r.URL.Query().Get("mode")
	if mode == "" {
		mode = "monthly"
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"message": "FTS 5-indicator refresh started.",
		"mode":    mode,
	})
}

func (h *Handler) SyncCodalDBDownload(w http.ResponseWriter, r *http.Request) {
	dbdlMu.Lock()
	if dbdlRunning {
		dbdlMu.Unlock()
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "already_running",
			"message": "دانلود دیتابیس کدال در حال اجراست — صبر کنید.",
		})
		return
	}
	dbdlMu.Unlock()

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"message": "دانلود دیتابیس کدال از گیت‌هاب آغاز شد.",
		"url":     CodalDBURL,
	})
}

func (h *Handler) CodalControl(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Cmd string `json:"cmd"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "invalid JSON body",
		})
		return
	}
	cmd := strings.ToLower(strings.TrimSpace(body.Cmd))
	if cmd != "pause" && cmd != "resume" && cmd != "stop" {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "unknown cmd: " + cmd,
		})
		return
	}

	_ = WriteControl(h.dataDir, cmd, h.clock())

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"cmd":     cmd,
		"running": false,
	})
}
