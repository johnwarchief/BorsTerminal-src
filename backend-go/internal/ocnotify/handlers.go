package ocnotify

import (
	"encoding/json"
	"io"
	"net/http"
	"strconv"
	"time"

	"borsterminal/backend/internal/httpapi"
)

type Handler struct {
	store *Store
	now   func() time.Time
}

func NewHandler(store *Store) *Handler { return &Handler{store: store, now: time.Now} }

func envelope(schema, state string, extra map[string]any) map[string]any {
	out := map[string]any{
		"schema":     schema,
		"as_of":      time.Now().UTC().Format(time.RFC3339),
		"data_state": state,
	}
	for k, v := range extra {
		out[k] = v
	}
	return out
}

func badRequest(w http.ResponseWriter, code, msg string) {
	httpapi.WriteJSON(w, http.StatusBadRequest, map[string]any{
		"status": "error", "code": code, "message": msg, "retryable": false,
	})
}

func (h *Handler) List(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	limit, _ := strconv.Atoi(q.Get("limit"))
	if limit == 0 {
		limit = 50
	}
	before, _ := strconv.ParseInt(q.Get("before_seq"), 10, 64)
	unread := q.Get("unread") == "1" || q.Get("read") == "unread" || q.Get("read") == "false"
	rows, err := h.store.List(r.Context(), ListQuery{
		Limit: limit, BeforeSeq: before, Severity: q.Get("severity"),
		Category: q.Get("category"), Unread: unread,
	})
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "LIST_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	next := int64(0)
	if len(rows) == limit {
		next = rows[len(rows)-1].Seq
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_list/1", "ok", map[string]any{
		"items": rows, "count": len(rows), "next_cursor": next,
	}))
}

func (h *Handler) UnreadCount(w http.ResponseWriter, r *http.Request) {
	counts, err := h.store.UnreadCounts(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "COUNT_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	extra := make(map[string]any, len(counts))
	for k, v := range counts {
		extra[k] = v
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_unread/1", "ok", extra))
}

func (h *Handler) Pending(w http.ResponseWriter, r *http.Request) {
	after, _ := strconv.ParseInt(r.URL.Query().Get("after_seq"), 10, 64)
	limit, _ := strconv.Atoi(r.URL.Query().Get("limit"))
	rows, err := h.store.Pending(r.Context(), after, limit)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "PENDING_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_pending/1", "ok", map[string]any{
		"items": rows, "count": len(rows),
	}))
}

func (h *Handler) MarkRead(w http.ResponseWriter, r *http.Request) {
	id := r.PathValue("id")
	changed, err := h.store.MarkRead(r.Context(), id)
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "READ_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_read/1", "ok", map[string]any{
		"event_id": id, "changed": changed,
	}))
}

func (h *Handler) MarkAllRead(w http.ResponseWriter, r *http.Request) {
	n, err := h.store.MarkAllRead(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "READ_ALL_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_read_all/1", "ok", map[string]any{
		"changed": n,
	}))
}

func (h *Handler) Ack(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Channel string `json:"channel"`
		State   string `json:"state"`
		Error   string `json:"error"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 16<<10)).Decode(&body); err != nil {
		badRequest(w, "INVALID_JSON", err.Error())
		return
	}
	if body.Channel == "" {
		body.Channel = "toast"
	}
	if err := h.store.AckDelivery(r.Context(), r.PathValue("id"), body.Channel, body.State, body.Error); err != nil {
		badRequest(w, "ACK_REJECTED", err.Error())
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_ack/1", "ok", map[string]any{
		"event_id": r.PathValue("id"), "channel": body.Channel, "state": body.State,
	}))
}

func (h *Handler) GetPrefs(w http.ResponseWriter, r *http.Request) {
	prefs, err := h.store.Prefs(r.Context())
	if err != nil {
		httpapi.WriteJSON(w, http.StatusInternalServerError, map[string]any{
			"status": "error", "code": "PREFS_FAILED", "message": err.Error(), "retryable": true,
		})
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_prefs/1", "ok", map[string]any{
		"preferences": prefs,
	}))
}

func (h *Handler) PutPrefs(w http.ResponseWriter, r *http.Request) {
	raw, err := io.ReadAll(io.LimitReader(r.Body, 32<<10))
	if err != nil {
		badRequest(w, "BODY_READ_FAILED", err.Error())
		return
	}
	prefs, err := h.store.SavePrefs(r.Context(), raw)
	if err != nil {
		badRequest(w, "INVALID_PREFERENCES", err.Error())
		return
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_prefs/1", "ok", map[string]any{
		"preferences": prefs,
	}))
}

// Status وضعیتِ پایه است: مرکز محلی زنده است، اما پل/Toast هنوز ساخته نشده
// و ادعایِ «Toast شد» نمی‌شود.
func (h *Handler) Status(w http.ResponseWriter, r *http.Request) {
	counts, err := h.store.UnreadCounts(r.Context())
	if err != nil {
		counts = map[string]int{"total": 0}
	}
	httpapi.WriteJSON(w, http.StatusOK, envelope("oc.notification_status/1", "ok", map[string]any{
		"bridge":      "not_built",
		"os_toast":    "not_built",
		"quiet_hours": "policy_pending",
		"unread":      counts,
	}))
}
