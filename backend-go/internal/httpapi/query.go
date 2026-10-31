package httpapi

import (
	"net/http"
	"strconv"
)

// IntQuery پارامترِ صحیحِ مقولهٔ کوئری با همان بدنهٔ 422 که FastAPI می‌دهد
// (`int_parsing`، loc = ["query", name])؛ رشتهٔ خالی یعنی «کلید داده نشده» و
// پیش‌فرض می‌نشیند — دقیقاً مثلِ مقدارِ پیش‌فرضِ امضایِ پایتون.
func IntQuery(w http.ResponseWriter, r *http.Request, name string, def int) (int, bool) {
	raw := r.URL.Query().Get(name)
	if raw == "" {
		return def, true
	}
	v, err := strconv.Atoi(raw)
	if err != nil {
		UnprocessableAs(w, "int_parsing", []string{"query", name},
			"Input should be a valid integer, unable to parse string as an integer", raw)
		return 0, false
	}
	return v, true
}
