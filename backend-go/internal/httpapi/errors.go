package httpapi

import (
	"encoding/json"
	"net/http"
)

func WriteJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	enc := json.NewEncoder(w)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(v)
}

// NotFound عینِ پاسخِ پیش‌فرضِ FastAPI است.
func NotFound(w http.ResponseWriter) {
	WriteJSON(w, http.StatusNotFound, map[string]any{"detail": "Not Found"})
}

// Unprocessable عینِ شکلِ 422ِ FastAPI؛ در B0 فقط واحد-تست می‌شود و
// پاریتیِ زندهٔ آن با اولین مسیرِ پارامتردار (B2/B3) می‌آید.
func Unprocessable(w http.ResponseWriter, loc []string, msg string, input any) {
	WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []any{map[string]any{
			"type": "value_error", "loc": loc, "msg": msg, "input": input,
		}},
	})
}

func NotPorted(w http.ResponseWriter, route string) {
	WriteJSON(w, http.StatusNotImplemented, map[string]any{
		"status": "error", "code": "NOT_PORTED", "route": route,
	})
}
