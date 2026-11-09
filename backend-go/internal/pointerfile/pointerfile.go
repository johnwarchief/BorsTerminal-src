// Package pointerfile دسترسی به active_generation.json را هماهنگ می‌کند.
// رویِ ویندوز os.Rename از MoveFileEx استفاده می‌کند که تا وقتی خواننده‌ای
// فایل را باز دارد (حتی با FILE_SHARE_DELETE) با ACCESS_DENIED شکست می‌خورد؛
// یک poller کوتاه‌مدت می‌تواند Apply/Rollback را بشکند. قفلِ خواندن/نوشتن،
// خواننده‌هایِ همین پردازش را از rename کنار می‌گذارد و retry در لایهٔ ویندوز
// خواننده‌هایِ پردازش‌هایِ دیگر (مثل producer) را پوشش می‌دهد. اتمیک بودن
// حفظ می‌شود؛ remove-then-rename استفاده نمی‌شود.
package pointerfile

import (
	"os"
	"sync"
)

var mu sync.RWMutex

// Read فایل را زیرِ قفلِ خواندن می‌خواند تا Replace هم‌زمان با آن rename نکند.
func Read(path string) ([]byte, error) {
	mu.RLock()
	defer mu.RUnlock()
	return os.ReadFile(path)
}

// Replace زیرِ قفلِ نوشتن محتوایِ tmp را به dst منتقل می‌کند.
func Replace(tmp, dst string) error {
	mu.Lock()
	defer mu.Unlock()
	return replaceAtomic(tmp, dst)
}
