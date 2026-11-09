package ocnotify

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"borsterminal/backend/internal/ocdb"
)

func newTestStore(t *testing.T) *Store {
	t.Helper()
	store, err := ocdb.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = store.Close() })
	return NewStore(store.DB)
}

func validEvent() Event {
	return Event{
		EventID:  "evt-1",
		Type:     "strategy.approved",
		Category: "strategy",
		Severity: Important,
		Title:    "استراتژی تأیید شد",
		Body:     "نسخهٔ ۱.۲ از مالک تأیید گرفت",
		Source:   "strategy",
	}
}

func TestPublishAndDuplicate(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	pub, err := s.Publish(ctx, validEvent())
	if err != nil {
		t.Fatal(err)
	}
	if pub.Seq == 0 || pub.Occurrence != 1 || pub.Deduped {
		t.Fatalf("published = %+v", pub)
	}
	again, err := s.Publish(ctx, validEvent())
	if err != nil {
		t.Fatal(err)
	}
	if !again.Deduped || again.Occurrence != 2 || again.Seq != pub.Seq {
		t.Fatalf("duplicate = %+v", again)
	}
	rows, err := s.List(ctx, ListQuery{Limit: 10})
	if err != nil {
		t.Fatal(err)
	}
	if len(rows) != 1 || rows[0].OccurrenceCount != 2 {
		t.Fatalf("rows = %+v", rows)
	}
	if rows[0].Delivery["toast"] != "pending" || rows[0].Delivery["center"] != "shown" {
		t.Fatalf("delivery = %+v", rows[0].Delivery)
	}
}

func TestToastPolicyBySeverity(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	ev := validEvent()
	ev.EventID = "evt-normal"
	ev.Severity = Normal
	if _, err := s.Publish(ctx, ev); err != nil {
		t.Fatal(err)
	}
	rows, _ := s.List(ctx, ListQuery{})
	if len(rows) != 1 {
		t.Fatal("missing row")
	}
	if _, ok := rows[0].Delivery["toast"]; ok {
		t.Fatalf("normal events must not create a toast delivery: %+v", rows[0].Delivery)
	}
}

func TestValidationRejectsBadEvents(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	cases := map[string]func(e *Event){
		"bad severity":     func(e *Event) { e.Severity = "high" },
		"bad source":       func(e *Event) { e.Source = "codal-raw" },
		"bad deep link":    func(e *Event) { e.DeepLink = "javascript:alert(1)" },
		"outer deep link":  func(e *Event) { e.DeepLink = "https://example.com" },
		"ai important":     func(e *Event) { e.Source = "ai"; e.Severity = Important },
		"missing title":    func(e *Event) { e.Title = "" },
		"control char":     func(e *Event) { e.Title = "bad\x00title" },
		"bad event id":     func(e *Event) { e.EventID = "../escape" },
		"bad occurred_at":  func(e *Event) { e.OccurredAt = "yesterday" },
		"bad payload hash": func(e *Event) { e.PayloadHash = "xyz" },
	}
	for name, mutate := range cases {
		t.Run(name, func(t *testing.T) {
			ev := validEvent()
			ev.EventID = "evt-" + strings.ReplaceAll(name, " ", "-")
			mutate(&ev)
			if _, err := s.Publish(ctx, ev); err == nil {
				t.Fatalf("event %q must be rejected", name)
			}
		})
	}
	if pub, err := s.Publish(ctx, validEvent()); err != nil || pub.EventID != "evt-1" {
		t.Fatalf("valid control event rejected: %+v %v", pub, err)
	}
}

func TestDeliveryAckAndPending(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	ev := validEvent()
	if _, err := s.Publish(ctx, ev); err != nil {
		t.Fatal(err)
	}
	pending, err := s.Pending(ctx, 0, 10)
	if err != nil || len(pending) != 1 {
		t.Fatalf("pending = %+v err=%v", pending, err)
	}
	if err := s.AckDelivery(ctx, ev.EventID, "toast", "shown", ""); err != nil {
		t.Fatal(err)
	}
	pending, _ = s.Pending(ctx, 0, 10)
	if len(pending) != 0 {
		t.Fatalf("acked toast still pending: %+v", pending)
	}
	if err := s.AckDelivery(ctx, "missing", "toast", "shown", ""); err == nil {
		t.Fatal("ack for an unknown event must fail")
	}
	if err := s.AckDelivery(ctx, ev.EventID, "sms", "shown", ""); err == nil {
		t.Fatal("unknown channel must fail")
	}
	if err := s.AckDelivery(ctx, ev.EventID, "toast", "weird", ""); err == nil {
		t.Fatal("unknown state must fail")
	}
	// Idempotent ack.
	if err := s.AckDelivery(ctx, ev.EventID, "toast", "suppressed_os", ""); err != nil {
		t.Fatal(err)
	}
}

func TestReadStateAndCounts(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	for i := 0; i < 3; i++ {
		ev := validEvent()
		ev.EventID = "evt-" + string(rune('a'+i))
		ev.Type = "opportunity.valid"
		if _, err := s.Publish(ctx, ev); err != nil {
			t.Fatal(err)
		}
	}
	counts, err := s.UnreadCounts(ctx)
	if err != nil || counts["total"] != 3 || counts["important"] != 3 {
		t.Fatalf("counts = %+v err=%v", counts, err)
	}
	changed, err := s.MarkRead(ctx, "evt-a")
	if err != nil || !changed {
		t.Fatalf("mark read changed=%v err=%v", changed, err)
	}
	changed, _ = s.MarkRead(ctx, "evt-a")
	if changed {
		t.Fatal("second mark read must be a no-op")
	}
	counts, _ = s.UnreadCounts(ctx)
	if counts["total"] != 2 {
		t.Fatalf("counts after read = %+v", counts)
	}
	n, err := s.MarkAllRead(ctx)
	if err != nil || n != 2 {
		t.Fatalf("mark all = %d err=%v", n, err)
	}
}

func TestPrefsAndMutes(t *testing.T) {
	s := newTestStore(t)
	ctx := context.Background()
	prefs, err := s.Prefs(ctx)
	if err != nil {
		t.Fatal(err)
	}
	if prefs["toast_critical"] != true || prefs["toast_normal"] != false {
		t.Fatalf("defaults = %+v", prefs)
	}
	merged, err := s.SavePrefs(ctx, json.RawMessage(`{"toast_normal":true,"quiet_hours_start":"23:30"}`))
	if err != nil {
		t.Fatal(err)
	}
	if merged["toast_normal"] != true || merged["quiet_hours_start"] != "23:30" {
		t.Fatalf("merged = %+v", merged)
	}
	for _, bad := range []string{
		`{"unknown_key":true}`,
		`{"toast_critical":"yes"}`,
		`{"quiet_hours_start":"25:99"}`,
		`not json`,
	} {
		if _, err := s.SavePrefs(ctx, json.RawMessage(bad)); err == nil {
			t.Fatalf("prefs %q must be rejected", bad)
		}
	}
	if err := s.Mute(ctx, "price", "", "test"); err != nil {
		t.Fatal(err)
	}
	muted, err := s.IsMuted(ctx, "price", time.Now())
	if err != nil || !muted {
		t.Fatalf("muted=%v err=%v", muted, err)
	}
	if err := s.Mute(ctx, "signal", time.Now().Add(-time.Hour).UTC().Format(time.RFC3339), "expired"); err != nil {
		t.Fatal(err)
	}
	muted, _ = s.IsMuted(ctx, "signal", time.Now())
	if muted {
		t.Fatal("expired mute must not apply")
	}
}

func TestHTTPHandlers(t *testing.T) {
	ocStore, err := ocdb.Open(t.TempDir())
	if err != nil {
		t.Fatal(err)
	}
	defer ocStore.Close()
	store := NewStore(ocStore.DB)
	if _, err := store.Publish(context.Background(), validEvent()); err != nil {
		t.Fatal(err)
	}
	h := NewHandler(store)
	mux := http.NewServeMux()
	mux.HandleFunc("GET /api/oc/notifications", h.List)
	mux.HandleFunc("GET /api/oc/notifications/unread-count", h.UnreadCount)
	mux.HandleFunc("GET /api/oc/notifications/pending", h.Pending)
	mux.HandleFunc("POST /api/oc/notifications/read-all", h.MarkAllRead)
	mux.HandleFunc("GET /api/oc/notifications/preferences", h.GetPrefs)
	mux.HandleFunc("PUT /api/oc/notifications/preferences", h.PutPrefs)
	mux.HandleFunc("GET /api/oc/notifications/status", h.Status)
	mux.HandleFunc("POST /api/oc/notifications/{id}/read", h.MarkRead)
	mux.HandleFunc("POST /api/oc/notifications/{id}/ack", h.Ack)

	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/oc/notifications", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("list code = %d body=%s", rec.Code, rec.Body.String())
	}
	var list map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &list); err != nil {
		t.Fatal(err)
	}
	if list["schema"] != "oc.notification_list/1" || list["count"].(float64) != 1 {
		t.Fatalf("list body = %v", list)
	}

	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/oc/notifications/unread-count", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("unread code = %d", rec.Code)
	}

	rec = httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodPost, "/api/oc/notifications/evt-1/ack", strings.NewReader(`{"state":"shown"}`))
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("ack code = %d body=%s", rec.Code, rec.Body.String())
	}

	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodPut, "/api/oc/notifications/preferences", strings.NewReader(`{"toast_normal":true}`))
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("prefs code = %d body=%s", rec.Code, rec.Body.String())
	}

	rec = httptest.NewRecorder()
	req = httptest.NewRequest(http.MethodPut, "/api/oc/notifications/preferences", strings.NewReader(`{"nope":1}`))
	mux.ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("invalid prefs code = %d", rec.Code)
	}

	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/oc/notifications/status", nil))
	if rec.Code != http.StatusOK || !strings.Contains(rec.Body.String(), "not_built") {
		t.Fatalf("status code = %d body=%s", rec.Code, rec.Body.String())
	}
}
