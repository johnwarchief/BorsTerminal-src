package sync

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
)

const (
	CodalDBURL             = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download/codal.db.lzma"
	DefaultSnapshotBaseURL = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download"
	DefaultUpdatePubKey    = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3NgpSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="
)

type Handler struct {
	dataDir         string
	clock           func() time.Time
	prober          DiagProber
	pubKey          string
	snapshotBaseURL string
	httpClient      *http.Client
}

func NewHandler(dataDir string) *Handler {
	baseURL := os.Getenv("BORS_SNAPSHOT_URL")
	if baseURL == "" {
		baseURL = os.Getenv("BORS_SNAPSHOT_BASE_URL")
	}
	if baseURL == "" {
		baseURL = DefaultSnapshotBaseURL
	}

	pubKey := os.Getenv("BORS_UPDATE_PUBKEY")
	if pubKey == "" {
		pubKey = DefaultUpdatePubKey
	}

	// No client-wide Timeout: it also bounds response-body reads, and a full
	// snapshot set is ~80 MB. runSnapshotDownloadAndApply bounds the operation
	// with a context instead; the transport still fails fast on a dead peer.
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.ResponseHeaderTimeout = 60 * time.Second

	return &Handler{
		dataDir:         dataDir,
		clock:           time.Now,
		prober:          defaultProber{},
		pubKey:          pubKey,
		snapshotBaseURL: baseURL,
		httpClient:      &http.Client{Transport: transport},
	}
}

func (h *Handler) SetSnapshotBaseURL(url string) {
	h.snapshotBaseURL = url
}

func (h *Handler) SetPubKey(pubKey string) {
	h.pubKey = pubKey
}

func (h *Handler) SetHTTPClient(client *http.Client) {
	h.httpClient = client
}

func (h *Handler) SetClock(clock func() time.Time) {
	h.clock = clock
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
	dbdlRunning = true
	dbdlMu.Unlock()

	baseURL := h.snapshotBaseURL
	if qURL := r.URL.Query().Get("url"); qURL != "" {
		baseURL = qURL
	}
	if baseURL == "" {
		baseURL = DefaultSnapshotBaseURL
	}

	// Update status to downloading immediately
	_ = writeCodalDBStatus(h.dataDir, "downloading", 0, "شروع دانلود اسنپ‌شات...", "", h.clock())

	// Run background download and apply pipeline in a goroutine
	go h.runSnapshotDownloadAndApply(baseURL)

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"message": "دانلود دیتابیس کدال از گیت‌هاب آغاز شد.",
		"url":     baseURL,
	})
}

func (h *Handler) runSnapshotDownloadAndApply(baseURL string) {
	defer func() {
		dbdlMu.Lock()
		dbdlRunning = false
		dbdlMu.Unlock()
	}()

	ctx, cancel := context.WithTimeout(context.Background(), 45*time.Minute)
	defer cancel()

	_ = h.DownloadAndApplySnapshot(ctx, baseURL)
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
