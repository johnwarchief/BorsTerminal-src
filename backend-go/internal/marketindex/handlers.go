package marketindex

import (
	"net/http"
	"strconv"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

// TEDPIX هندلر دریافت سری زمانی شاخص کل: GET /api/index/tedpix?limit=...&refresh=...
func (s *Service) TEDPIX(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("limit")
	limit := 0
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed >= 0 {
			if parsed > 5000 {
				parsed = 5000
			}
			limit = parsed
		}
	}

	refreshStr := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("refresh")))
	refresh := refreshStr == "true" || refreshStr == "1"

	payload, code, err := s.BuildTedpixPayload(r.Context(), TedpixInsCode, limit, refresh)
	if err != nil {
		errResp := map[string]any{
			"status":     "error",
			"message":    err.Error(),
			"ins_code":   TedpixInsCode,
			"source":     IndexSource,
			"has_volume": false,
			"candles":    []any{},
			"count":      0,
		}
		httpapi.WriteJSON(w, code, errResp)
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, payload)
}
