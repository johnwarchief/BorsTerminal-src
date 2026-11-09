// Package instance تضمین می‌کند فقط یک borsd روی یک dataDir اجرا شود.
// دو نمونه هم‌زمان رویِ یک oc_client.db یعنی دو نویسنده و تاریخچهٔ اعلانِ
// درهم؛ قفل در سطحِ فایل (نه شمارشِ PID) و توسطِ خودِ OS اعمال می‌شود.
package instance

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

var ErrAlreadyRunning = errors.New("another borsd instance is already running on this data dir")

const lockRelPath = "oc/runtime/borsd.lock"

type Lock struct {
	path string
	file *os.File
}

func Acquire(dataDir string) (*Lock, error) {
	dir := filepath.Join(dataDir, "oc", "runtime")
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, fmt.Errorf("create runtime dir: %w", err)
	}
	path := filepath.Join(dataDir, filepath.FromSlash(lockRelPath))
	return acquire(path)
}

func (l *Lock) Path() string { return l.path }

func (l *Lock) Release() error {
	if l == nil || l.file == nil {
		return nil
	}
	return release(l)
}
