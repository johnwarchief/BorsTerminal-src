package httpapi

import (
	"encoding/json"
	"net/http"
	"sort"
	"strings"
	"sync"
	"time"
)

// Orderbook watch is a process-local hot-window subscription, like Python's
// market_state.subscribe_orderbook. The live feed already carries five-level
// depth in the same marketwatch request, so this endpoint only tracks which
// windows still care; a subscription dies 15 minutes after its last heartbeat.
var (
	orderbookWatchMu = sync.Mutex{}
	orderbookWatched = map[string]time.Time{}
)

const orderbookSubTTL = 15 * time.Minute

func orderbookWatchHandler(w http.ResponseWriter, r *http.Request) {
	var body struct {
		InsCode string `json:"ins_code"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body)
	code := strings.TrimSpace(body.InsCode)
	if code == "" {
		WriteJSON(w, http.StatusOK, map[string]any{
			"status": "error", "message": "ins_code لازم است",
		})
		return
	}
	now := time.Now()
	orderbookWatchMu.Lock()
	for c, seen := range orderbookWatched {
		if now.Sub(seen) > orderbookSubTTL {
			delete(orderbookWatched, c)
		}
	}
	orderbookWatched[code] = now
	subs := make([]string, 0, len(orderbookWatched))
	for c := range orderbookWatched {
		subs = append(subs, c)
	}
	orderbookWatchMu.Unlock()
	sort.Strings(subs)
	WriteJSON(w, http.StatusOK, map[string]any{"status": "success", "subscribed": subs})
}
