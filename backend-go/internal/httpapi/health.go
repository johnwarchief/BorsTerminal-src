package httpapi

import (
	"context"
	"net/http"
	"runtime"
	"time"
)

var version = "dev"

// Version نسخهٔ باینری است؛ پیش‌فرض dev و در Task 7 با
// ldflags -X borsterminal/backend/internal/httpapi.version=<v> ست می‌شود.
// تنها خوانندهٔ version همین تابع است تا /healthz و لاگِ شروع یک مقدار بدهند.
func Version() string { return version }

func contextWithTimeout(r *http.Request, d time.Duration) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), d)
}

// rssMB: MemStats.Sys معیارِ حافظهٔ رزروشدهٔ Go است؛ RSSِ واقعی در گیتِ B0
// با tasklist سنجیده می‌شود. نامِ کلید rss_mb عمداً ثابت است تا ابزارِ گیت
// بداند کدام عدد را با سقف مقایسه کند.
func rssMB() float64 {
	var m runtime.MemStats
	runtime.ReadMemStats(&m)
	return float64(m.Sys) / (1024 * 1024)
}
