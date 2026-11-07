package ftsconfig

import (
	"encoding/json"
	"io"
	"net/http"

	"borsterminal/backend/internal/httpapi"
)

type Handler struct {
	store    *Store
	readOnly bool
}

func NewHandler(store *Store, readOnly bool) *Handler {
	return &Handler{
		store:    store,
		readOnly: readOnly,
	}
}

func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	cfg, err := h.store.Get(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "success",
		"config": cfg,
	})
}

func (h *Handler) Post(w http.ResponseWriter, r *http.Request) {
	if h.readOnly {
		httpapi.WriteJSON(w, http.StatusForbidden, map[string]any{
			"status":  "error",
			"message": "read-only mode",
		})
		return
	}

	body, err := io.ReadAll(r.Body)
	if err != nil || len(body) == 0 {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "بدنهٔ درخواست خالی است",
		})
		return
	}

	var payload map[string]any
	if err := json.Unmarshal(body, &payload); err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "قالب JSON نامعتبر است",
		})
		return
	}

	updated, err := h.store.Save(r.Context(), payload)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"config":  updated,
		"message": "saved",
	})
}
