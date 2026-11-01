package watchlist

import (
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/url"

	"borsterminal/backend/internal/httpapi"
)

type Handler struct {
	store *Store
}

func NewHandler(store *Store) *Handler {
	return &Handler{store: store}
}

func (h *Handler) Get(w http.ResponseWriter, r *http.Request) {
	rows, limit, err := h.store.List(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status": "success",
		"count":  len(rows),
		"data":   rows,
		"limit":  limit,
	})
}

type postPayload struct {
	Symbol string `json:"symbol"`
	Name   string `json:"name"`
	Note   string `json:"note"`
}

func (h *Handler) Post(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(r.Body)
	if err != nil || len(body) == 0 {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "بدنهٔ درخواست خالی است — کلید symbol لازم است",
		})
		return
	}

	var payload postPayload
	if err := json.Unmarshal(body, &payload); err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "بدنهٔ درخواست خالی است — کلید symbol لازم است",
		})
		return
	}

	if payload.Symbol == "" {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": "نماد ارسال نشده",
		})
		return
	}

	res, err := h.store.Add(r.Context(), payload.Symbol, payload.Name, payload.Note, "")
	if err != nil {
		var capErr *CapError
		if errors.As(err, &capErr) {
			httpapi.WriteJSON(w, http.StatusOK, map[string]any{
				"status":  "error",
				"message": capErr.Error(),
				"limit":   capErr.Cap,
			})
			return
		}
		if errors.Is(err, ErrInvalidSymbol) {
			httpapi.WriteJSON(w, http.StatusOK, map[string]any{
				"status":  "error",
				"message": "نماد نامعتبر (تهی پس از نرمال‌سازی)",
			})
			return
		}
		if errors.Is(err, ErrEmptySymbol) {
			httpapi.WriteJSON(w, http.StatusOK, map[string]any{
				"status":  "error",
				"message": "نماد ارسال نشده",
			})
			return
		}
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}

	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"watch":   res.Watch,
		"count":   res.Count,
		"limit":   res.Limit,
		"existed": res.Existed,
	})
}

func (h *Handler) Delete(w http.ResponseWriter, r *http.Request) {
	sym := r.PathValue("symbol")
	if unescaped, err := url.PathUnescape(sym); err == nil && unescaped != "" {
		sym = unescaped
	}
	n, err := h.store.Remove(r.Context(), sym)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusOK, map[string]any{
			"status":  "error",
			"message": err.Error(),
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, map[string]any{
		"status":  "success",
		"deleted": n,
	})
}
