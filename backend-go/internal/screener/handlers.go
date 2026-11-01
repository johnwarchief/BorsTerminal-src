package screener

import (
	"net/http"
	"net/url"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

// History هندلر دریافت تاریخچه قیمت نماد: GET /api/history/{symbol}
func (s *Service) History(w http.ResponseWriter, r *http.Request) {
	sym := r.PathValue("symbol")
	if sym == "" {
		parts := strings.Split(r.URL.Path, "/")
		if len(parts) > 0 {
			sym = parts[len(parts)-1]
		}
	}
	if decoded, err := url.PathUnescape(sym); err == nil && decoded != "" {
		sym = decoded
	}

	payload, err := s.GetHistory(r.Context(), sym)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "empty",
			"candles": []any{},
			"volumes": []any{},
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, payload)
}

// Screener هندلر جدول غربالگری ۵ شاخص FTS: GET /api/screener?symbols=...&preset=...&chain=...
func (s *Service) Screener(w http.ResponseWriter, r *http.Request) {
	symbols := r.URL.Query().Get("symbols")
	preset := r.URL.Query().Get("preset")
	if preset == "" {
		preset = "trend"
	}
	chain := r.URL.Query().Get("chain")

	payload, err := s.GetScreener(r.Context(), symbols, preset, chain)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
			"data":    []any{},
			"count":   0,
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, payload)
}
