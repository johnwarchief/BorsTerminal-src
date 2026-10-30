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

// UnprocessableAs همان 422ِ FastAPI با نوعِ خطایِ خودش (int_parsing،
// bool_parsing، …)؛ بدنهٔ مقایسه‌شده در پاریتی همین است.
func UnprocessableAs(w http.ResponseWriter, typ string, loc []string, msg string, input any) {
	WriteJSON(w, http.StatusUnprocessableEntity, map[string]any{
		"detail": []any{map[string]any{
			"type": typ, "loc": loc, "msg": msg, "input": input,
		}},
	})
}

// Unprocessable عینِ شکلِ 422ِ FastAPI با نوعِ پیش‌فرضِ value_error.
func Unprocessable(w http.ResponseWriter, loc []string, msg string, input any) {
	UnprocessableAs(w, "value_error", loc, msg, input)
}

func NotPorted(w http.ResponseWriter, route string) {
	WriteJSON(w, http.StatusNotImplemented, map[string]any{
		"status": "error", "code": "NOT_PORTED", "route": route,
	})
}
