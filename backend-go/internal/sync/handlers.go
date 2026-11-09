package sync

import (
	"context"
	"encoding/json"
	"net/http"
	"os"
	"strings"
	"time"

	"borsterminal/backend/internal/httpapi"
	"borsterminal/backend/internal/jobs"
)

const (
	CodalDBURL             = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download/codal.db.lzma"
	DefaultSnapshotBaseURL = "https://github.com/johnwarchief/BorsTerminal/releases/latest/download"
	DefaultUpdatePubKey    = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IDgzMEJGNzUyRUYxMDA3NgpSV1IyQVBFdWRiOHdDRllFSTQrRUZwV0ZDYWJ6eTdiVWlQNlNJckk0dldnb294aVlkTy9oSFRHQwo="

	// kindCodalDBDownload شناسهٔ Jobِ دانلود+Applyِ اسنپ‌شات است.
	kindCodalDBDownload = "codal_db_download"
)

type Handler struct {
	dataDir         string
	clock           func() time.Time
	prober          DiagProber
	pubKey          string
	snapshotBaseURL string
	httpClient      *http.Client
	reloadHook      func() error
	jobs            *jobs.Manager
}

func NewHandler(dataDir string) *Handler {
	return NewHandlerWithJobs(dataDir, jobs.NewManager())
}

// NewHandlerWithJobs همان NewHandler با مدیرِ Jobِ مشترکِ پروسه است تا وضعیتِ
// کارها پس از تعویضِ نسل/instance از دست نرود.
func NewHandlerWithJobs(dataDir string, mgr *jobs.Manager) *Handler {
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
		jobs:            mgr,
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

// SetReloadHook پس از Apply موفق صدا زده می‌شود تا borsd نسلِ تازه را بدون
// ری‌استارت سرو کند. خطای hook یعنی اسنپ‌شات روی دیسک اعمال شده ولی موتور
// هنوز نسل قبلی را سرو می‌کند — همان وضعیتِ «pending_reload» در /api/oc/data.
func (h *Handler) SetReloadHook(fn func() error) {
	h.reloadHook = fn
}

func (h *Handler) SyncStatus(w http.ResponseWriter, r *http.Request) {
	res := GetSyncStatus(h.dataDir, h.clock())
	httpapi.WriteJSON(w, http.StatusOK, res)
}

func (h *Handler) CodalDBStatus(w http.ResponseWriter, r *http.Request) {
	_, running := h.jobs.Running(kindCodalDBDownload)
	res := GetCodalDBStatus(h.dataDir, running)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

func (h *Handler) Diagnose(w http.ResponseWriter, r *http.Request) {
	res := Diagnose(h.dataDir, h.clock(), h.prober)
	httpapi.WriteJSON(w, http.StatusOK, res)
}

// notImplemented: این بک‌اند پیاده‌سازیِ واقعیِ این sync را ندارد. پاسخِ
// «۲۰۰ = شروع شد» بدونِ Job، همان نقصِ api-honesty است؛ این‌جا ۵۰۱ صریح است.
func notImplemented(w http.ResponseWriter, operation string) {
	httpapi.WriteJSON(w, http.StatusNotImplemented, map[string]any{
		"status": "error", "code": "NOT_IMPLEMENTED",
		"message":   operation + " is not implemented by this backend; no job was created",
		"retryable": false,
	})
}

func (h *Handler) SyncMarket(w http.ResponseWriter, r *http.Request) {
	notImplemented(w, "market sync")
}

func (h *Handler) SyncCodal(w http.ResponseWriter, r *http.Request) {
	notImplemented(w, "codal sync")
}

func (h *Handler) SyncCodalFTSRefresh(w http.ResponseWriter, r *http.Request) {
	notImplemented(w, "FTS refresh")
}

func (h *Handler) SyncCodalDBDownload(w http.ResponseWriter, r *http.Request) {
	baseURL := h.snapshotBaseURL
	if qURL := r.URL.Query().Get("url"); qURL != "" {
		baseURL = qURL
	}
	if baseURL == "" {
		baseURL = DefaultSnapshotBaseURL
	}

	_ = writeCodalDBStatus(h.dataDir, "queued", 0, "دانلود اسنپ‌شات در صف اجرا...", "", h.clock())

	job, existing, err := h.jobs.StartExclusive(r.Context(), kindCodalDBDownload, true,
		func(ctx context.Context) error {
			runCtx, cancel := context.WithTimeout(ctx, 45*time.Minute)
			defer cancel()
			return h.DownloadAndApplySnapshot(runCtx, baseURL)
		})
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "JOB_START_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	if existing != nil {
		httpapi.WriteJSON(w, http.StatusConflict, map[string]any{
			"status": "conflict", "code": "JOB_ALREADY_RUNNING",
			"job_id": existing.ID, "state": string(existing.State),
			"status_url": "/api/jobs/" + existing.ID, "retryable": true,
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusAccepted, map[string]any{
		"status": "started", "job_id": job.ID, "kind": job.Kind,
		"status_url": "/api/jobs/" + job.ID, "url": baseURL,
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
