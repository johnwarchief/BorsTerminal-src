// Package ocdata سطحِ کوچکِ مدیریتِ نسلِ داده است: چه نسلی سرو می‌شود،
// بارگذاریِ دوبارهٔ اشاره‌گر، و Rollback به نسل قبلی. هیچ نوشتنی در market.db
// ندارد؛ فقط اشاره‌گرِ نسل را می‌خواند/عوض می‌کند.
package ocdata

import (
	"net/http"

	"borsterminal/backend/internal/httpapi"
)

type Provider interface {
	DataStatus() map[string]any
	Reload() error
	Rollback() error
}

type Handler struct {
	p Provider
}

func NewHandler(p Provider) *Handler { return &Handler{p: p} }

func (h *Handler) Status(w http.ResponseWriter, r *http.Request) {
	httpapi.WriteJSON(w, http.StatusOK, h.p.DataStatus())
}

func (h *Handler) Reload(w http.ResponseWriter, r *http.Request) {
	if err := h.p.Reload(); err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "RELOAD_FAILED", "message": err.Error(),
			"data": h.p.DataStatus(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "data": h.p.DataStatus(),
	})
}

func (h *Handler) Rollback(w http.ResponseWriter, r *http.Request) {
	if err := h.p.Rollback(); err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "ROLLBACK_FAILED", "message": err.Error(),
			"data": h.p.DataStatus(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "ok", "data": h.p.DataStatus(),
	})
}
