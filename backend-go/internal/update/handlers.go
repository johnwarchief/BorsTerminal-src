package update

import (
	"context"
	"encoding/json"
	"net/http"
	"time"
)

func writeUpdateJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (s *Service) HandleVersion(w http.ResponseWriter, r *http.Request) {
	writeUpdateJSON(w, http.StatusOK, s.VersionInfo())
}

func (s *Service) HandleCheck(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 45*time.Second)
	defer cancel()
	res, err := s.Check(ctx)
	if err != nil {
		writeUpdateJSON(w, http.StatusOK, CheckResult{Status: "error",
			CurrentVersion: s.CurrentVersion(), Message: res.Message})
		return
	}
	writeUpdateJSON(w, http.StatusOK, res)
}

func (s *Service) HandleDownload(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := context.WithTimeout(r.Context(), 45*time.Second)
	defer cancel()
	if err := s.Download(ctx); err != nil {
		writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "started"})
}

func (s *Service) HandleProgress(w http.ResponseWriter, r *http.Request) {
	writeUpdateJSON(w, http.StatusOK, s.Progress())
}

func (s *Service) HandleInstall(w http.ResponseWriter, r *http.Request) {
	if err := s.Install(r.Context()); err != nil {
		writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "installing"})
}

func (s *Service) HandleRollback(w http.ResponseWriter, r *http.Request) {
	if err := s.Rollback(r.Context()); err != nil {
		writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "error", "message": err.Error()})
		return
	}
	writeUpdateJSON(w, http.StatusOK, map[string]any{"status": "rolling_back"})
}
