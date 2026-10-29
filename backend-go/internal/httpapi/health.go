package httpapi

import (
	"context"
	"net/http"
	"runtime"
	"time"
)

var version = "dev"

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
