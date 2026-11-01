package notifications

import (
	"net/http"
	"strings"

	"borsterminal/backend/internal/httpapi"
)

type Handler struct {
	svc *Service
}

func NewHandler(svc *Service) *Handler {
	return &Handler{svc: svc}
}

func (h *Handler) Sources(w http.ResponseWriter, r *http.Request) {
	out, err := h.svc.Sources(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, out)
}

func (h *Handler) Feed(w http.ResponseWriter, r *http.Request) {
	since := httpapi.StringQuery(r, "since", "")
	levelsRaw := httpapi.StringQuery(r, "levels", "")
	var levels []string
	if levelsRaw != "" {
		for _, part := range strings.Split(levelsRaw, ",") {
			if trimmed := strings.TrimSpace(part); trimmed != "" {
				levels = append(levels, trimmed)
			}
		}
	}

	limit, ok := httpapi.IntQuery(w, r, "limit", 120)
	if !ok {
		return
	}

	symbol := httpapi.StringQuery(r, "symbol", "")

	out, err := h.svc.Feed(r.Context(), since, levels, limit, symbol)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, out)
}
